#!/usr/bin/env python3
import sys
import os
import time
import logging
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor

# -----------------------------
# CONFIG
# -----------------------------
LOG_FILE = "file_transfer.log"

SOURCE_DATA_DIR = "/home/ubuntu/comnetsemu/app/Amarisoft.digital.twin/physicaltwindata"
file_patterns = ["upf_default", "upf_internet", "upf_sos", "upf_ims"]

CYCLE_INTERVAL_SECONDS = 120
LOOP_FOREVER = True

REPLAY_INTERFACE = "ogstun"
CONTAINER_TARGET_DIR = "/open5gs"

# -----------------------------
# LOGGING: FILE + CONSOLE
# -----------------------------
logger = logging.getLogger("pcap_replay")
logger.setLevel(logging.INFO)

fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

fh = logging.FileHandler(LOG_FILE)
fh.setFormatter(fmt)
fh.setLevel(logging.INFO)

sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(fmt)
sh.setLevel(logging.INFO)

logger.handlers.clear()
logger.addHandler(fh)
logger.addHandler(sh)


# -----------------------------
# DOCKER COMMAND SELECTOR
# -----------------------------
def pick_docker_cmd() -> list:
    """If current user can't talk to docker, fall back to sudo docker."""
    # Try docker without sudo
    try:
        subprocess.run(
            ["docker", "ps"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        return ["docker"]
    except Exception:
        # Try sudo docker
        try:
            subprocess.run(
                ["sudo", "-n", "docker", "ps"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
            logger.info("Docker requires sudo on this machine. Using: sudo docker")
            return ["sudo", "docker"]
        except subprocess.CalledProcessError as e:
            logger.error("Docker is not accessible (no permission).")
            logger.error("Fix: either run this script with sudo OR add user to docker group:")
            logger.error("  sudo usermod -aG docker $USER  &&  newgrp docker")
            logger.error(f"sudo docker ps error: {e.stderr.strip()}")
            raise


DOCKER = pick_docker_cmd()


# -----------------------------
# HELPERS
# -----------------------------
def run_cmd(cmd: list, desc: str = "") -> subprocess.CompletedProcess:
    """Run command with strong error reporting."""
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        if desc:
            logger.info(f"OK: {desc}")
        return r
    except subprocess.CalledProcessError as e:
        if desc:
            logger.error(f"FAILED: {desc}")
        logger.error(f"Command: {' '.join(cmd)}")
        if e.stdout:
            logger.error(f"STDOUT:\n{e.stdout.strip()}")
        if e.stderr:
            logger.error(f"STDERR:\n{e.stderr.strip()}")
        raise


def discover_available_by_counter(source_dir: str) -> dict:
    """Discover which prefixes exist for each counter.

    Returns dict like:
      {1: ['upf_default', 'upf_ims'], 2: ['upf_default','upf_internet','upf_sos','upf_ims'], ...}

    This prevents "Missing local PCAP" spam when some files don't exist.
    """
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    available = {}
    for fname in os.listdir(source_dir):
        for p in file_patterns:
            m = re.fullmatch(rf"{re.escape(p)}(\d+)\.pcap", fname)
            if m:
                c = int(m.group(1))
                available.setdefault(c, set()).add(p)
                break

    # Keep prefix order consistent with file_patterns
    order = {p: i for i, p in enumerate(file_patterns)}
    available_sorted = {c: sorted(list(ps), key=lambda x: order[x]) for c, ps in available.items()}

    # Sort by counter
    return dict(sorted(available_sorted.items()))


def build_container_targets(counter: int):
    return {f"{p}{counter}.pcap": f"{p}:{CONTAINER_TARGET_DIR}/{p}{counter}.pcap" for p in file_patterns}


def build_tcpreplay_commands(counter: int):
    return {
        f"{p}{counter}.pcap": ["tcpreplay", "-i", REPLAY_INTERFACE, f"{CONTAINER_TARGET_DIR}/{p}{counter}.pcap"]
        for p in file_patterns
    }


def ensure_container_dir(container: str):
    run_cmd(
        DOCKER + ["exec", container, "mkdir", "-p", CONTAINER_TARGET_DIR],
        desc=f"ensure {CONTAINER_TARGET_DIR} exists in {container}",
    )


def docker_copy_file_to_container(local_file_path: str, container: str, target_path: str):
    run_cmd(
        DOCKER + ["cp", local_file_path, f"{container}:{target_path}"],
        desc=f"docker cp {os.path.basename(local_file_path)} -> {container}:{target_path}",
    )

    # verify copied
    run_cmd(
        DOCKER + ["exec", container, "ls", "-l", target_path],
        desc=f"verify file exists in {container}:{target_path}",
    )


def analyze_in_container(container: str, tcpreplay_cmd: list, pcap_name: str):
    r = run_cmd(
        DOCKER + ["exec", container] + tcpreplay_cmd,
        desc=f"tcpreplay {pcap_name} inside {container}",
    )
    out = (r.stdout or "").strip()
    if out:
        logger.info(f"tcpreplay output ({pcap_name}):\n{out}")


def process_one_pcap(filename: str, containers_map: dict, tcpreplay_map: dict):
    local_path = os.path.join(SOURCE_DATA_DIR, filename)

    if not os.path.isfile(local_path):
        # With the new discovery logic, this should rarely happen — but keep it safe.
        logger.warning(f"Missing local PCAP, skipping: {local_path}")
        return

    container_target = containers_map.get(filename)
    if not container_target:
        logger.warning(f"No container mapping for {filename}, skipping.")
        return

    container, target_path = container_target.split(":", 1)

    try:
        ensure_container_dir(container)
        docker_copy_file_to_container(local_path, container, target_path)

        tcpreplay_cmd = tcpreplay_map.get(filename)
        if not tcpreplay_cmd:
            logger.warning(f"No tcpreplay mapping for {filename}, skipping replay.")
            return

        analyze_in_container(container, tcpreplay_cmd, filename)

    except Exception as e:
        logger.error(f"Failed processing {filename}: {e}")


def run_cycle(counter: int, prefixes_for_counter: list):
    """Run one iteration like original code, but only for prefixes that exist for this counter."""
    containers_map = build_container_targets(counter)
    tcpreplay_map = build_tcpreplay_commands(counter)

    logger.info(f"=== Starting cycle {counter} (pcaps: {prefixes_for_counter}) ===")

    # Only spawn workers for the files that actually exist
    with ThreadPoolExecutor(max_workers=max(1, len(prefixes_for_counter))) as executor:
        futures = []
        for p in prefixes_for_counter:
            fname = f"{p}{counter}.pcap"
            futures.append(executor.submit(process_one_pcap, fname, containers_map, tcpreplay_map))
        for f in futures:
            f.result()

    logger.info(f"=== Cycle {counter} completed ===")


def replay_local_pcaps_periodically():
    available = discover_available_by_counter(SOURCE_DATA_DIR)
    if not available:
        logger.error(f"No matching PCAP files found in {SOURCE_DATA_DIR}.")
        logger.error("Expected names like: upf_default1.pcap, upf_internet1.pcap, upf_sos1.pcap, upf_ims1.pcap")
        sys.exit(1)

    counters = list(available.keys())
    logger.info(f"Discovered counters (with available pcaps): {available}")

    idx = 0
    while True:
        counter = counters[idx]
        run_cycle(counter, available[counter])

        idx += 1
        if idx >= len(counters):
            if LOOP_FOREVER:
                idx = 0
                logger.info("Reached end of demo PCAPs; looping back to start.")
            else:
                logger.info("Reached end of demo PCAPs; stopping.")
                break

        logger.info(f"Sleeping {CYCLE_INTERVAL_SECONDS}s before next cycle...")
        time.sleep(CYCLE_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        replay_local_pcaps_periodically()
    except KeyboardInterrupt:
        logger.info("Replay interrupted by user (Ctrl+C).")
        sys.exit(0)
