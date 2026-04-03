import os
import re
import time
import datetime
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor

# -----------------------------
# CONFIG
# -----------------------------
logging.basicConfig(
    filename='file_transfer.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

SOURCE_DATA_DIR = "/home/ubuntu/comnetsemu/app/Amarisoft.digital.twin/physicaltwindata"

file_patterns = ["upf_default", "upf_internet", "upf_sos", "upf_ims"]

CYCLE_INTERVAL_SECONDS = 120
LOOP_FOREVER = True

REPLAY_INTERFACE = "ogstun"

# Put pcaps here inside containers (so you can easily check them)
CONTAINER_PCAP_DIR = "/open5gs/pcaps"


# -----------------------------
# UTILS
# -----------------------------
def sh(cmd: str) -> subprocess.CompletedProcess:
    """Run a shell command and return the CompletedProcess."""
    return subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def ensure_container_dir(container: str, path: str):
    r = sh(f"docker exec {container} mkdir -p {path}")
    if r.returncode != 0:
        raise RuntimeError(f"mkdir failed in {container}: {r.stderr.strip()}")


def docker_cp(local_path: str, container: str, target_dir: str):
    r = sh(f"docker cp '{local_path}' {container}:'{target_dir}/'")
    if r.returncode != 0:
        raise RuntimeError(f"docker cp failed: {r.stderr.strip()}")


def tcpreplay(container: str, pcap_inside: str):
    cmd = f"tcpreplay -i {REPLAY_INTERFACE} '{pcap_inside}'"
    r = sh(f"docker exec {container} {cmd}")
    if r.returncode != 0:
        raise RuntimeError(f"tcpreplay failed in {container}: {r.stderr.strip()}")
    return r.stdout.strip()


def discover_counters_forgiving(source_dir: str):
    """
    Forgiving discovery:
    Accept filenames like:
      upf_default1.pcap
      upf_default_1.pcap
      upf_default-1.pcap
      anything_upf_default1_anything.pcap  (as long as it contains pattern + number and ends with .pcap)
    Returns sorted counters.
    """
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    counters = set()
    all_files = os.listdir(source_dir)

    for fname in all_files:
        if not fname.endswith(".pcap"):
            continue
        for p in file_patterns:
            if p not in fname:
                continue
            # find the first number after the pattern
            m = re.search(rf"{re.escape(p)}\D*(\d+)", fname)
            if m:
                counters.add(int(m.group(1)))
                break

    return sorted(counters)


def find_file_for_pattern_and_counter(source_dir: str, pattern: str, counter: int):
    """
    Find a single file in source_dir that corresponds to (pattern, counter),
    forgiving matching (pattern then optional non-digits then the counter, ends with .pcap).
    """
    rx = re.compile(rf".*{re.escape(pattern)}\D*{counter}\D*\.pcap$")
    for fname in os.listdir(source_dir):
        if rx.match(fname):
            return os.path.join(source_dir, fname), fname
    return None, None


def process_one_pattern(counter: int, pattern: str):
    """
    For a given counter and pattern:
      - locate local pcap
      - copy to corresponding container
      - replay with tcpreplay
    """
    local_path, fname = find_file_for_pattern_and_counter(SOURCE_DATA_DIR, pattern, counter)
    container = pattern  # container name matches pattern: upf_default, upf_internet, ...

    if not local_path:
        msg = f"[cycle {counter}] Missing pcap for {pattern}{counter} in {SOURCE_DATA_DIR} (skipping)"
        print(msg)
        logging.warning(msg)
        return

    try:
        ensure_container_dir(container, CONTAINER_PCAP_DIR)
        docker_cp(local_path, container, CONTAINER_PCAP_DIR)

        inside_path = f"{CONTAINER_PCAP_DIR}/{os.path.basename(local_path)}"
        out = tcpreplay(container, inside_path)

        msg = f"[cycle {counter}] OK: {fname} -> {container}:{inside_path} replayed"
        print(msg)
        logging.info(msg)
        if out:
            logging.info(f"[cycle {counter}] tcpreplay output ({container}):\n{out}")

    except Exception as e:
        msg = f"[cycle {counter}] ERROR processing {pattern}: {e}"
        print(msg)
        logging.error(msg)


def run_cycle(counter: int):
    print(f"\n=== Starting cycle {counter} ({datetime.datetime.now()}) ===")
    logging.info(f"=== Starting cycle {counter} ===")

    with ThreadPoolExecutor(max_workers=len(file_patterns)) as ex:
        futures = [ex.submit(process_one_pattern, counter, p) for p in file_patterns]
        for f in futures:
            f.result()

    print(f"=== Completed cycle {counter} ===")
    logging.info(f"=== Completed cycle {counter} ===")


def main():
    counters = discover_counters_forgiving(SOURCE_DATA_DIR)
    if not counters:
        print(f"No .pcap counters discovered in: {SOURCE_DATA_DIR}")
        print("Run: find <dir> -type f -name '*.pcap' | head -n 50")
        logging.error("No counters discovered; nothing to replay.")
        return

    print(f"Discovered counters: {counters}")
    logging.info(f"Discovered counters: {counters}")

    idx = 0
    while True:
        run_cycle(counters[idx])

        idx += 1
        if idx >= len(counters):
            if LOOP_FOREVER:
                idx = 0
                print("Reached end; looping back to start.")
                logging.info("Reached end; looping back to start.")
            else:
                print("Reached end; stopping.")
                logging.info("Reached end; stopping.")
                break

        time.sleep(CYCLE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
