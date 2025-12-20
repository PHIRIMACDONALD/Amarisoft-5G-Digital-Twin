#!/usr/bin/env python3
import subprocess
import time
from datetime import datetime

# Configuration
CONTAINER = "upf_default"
INTERFACE = "ogstun"
INTERVAL = 5.0  # seconds
LOG_FILE = "upf.log"

def get_bytes(direction):
    """
    direction: 'rx' or 'tx'
    Reads byte counters for the ogstun interface inside the UPF container.
    """
    cmd = f"docker exec {CONTAINER} cat /sys/class/net/{INTERFACE}/statistics/{direction}_bytes"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return int(result.stdout.strip())

def main():
    print(f"Monitoring UL/DL bitrate on {INTERFACE} inside {CONTAINER}")
    print(f"Interval: {INTERVAL}s, log file: {LOG_FILE}")
    print("Press Ctrl+C to stop.\n")

    # Initialize previous counters
    prev_rx = get_bytes("rx")
    prev_tx = get_bytes("tx")

    with open(LOG_FILE, "a") as f:
        f.write("timestamp,dl_mbps,ul_mbps\n")

    while True:
        time.sleep(INTERVAL)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Read new counters
        rx = get_bytes("rx")
        tx = get_bytes("tx")

        # Compute bitrates
        dl_bitrate = (rx - prev_rx) * 8 / (INTERVAL * 1e6)  # Mbps
        ul_bitrate = (tx - prev_tx) * 8 / (INTERVAL * 1e6)  # Mbps

        prev_rx, prev_tx = rx, tx

        # Display
        print(f"[{now}] DL: {dl_bitrate:.3f} Mbps | UL: {ul_bitrate:.3f} Mbps")

        # Log
        with open(LOG_FILE, "a") as f:
            f.write(f"{now},{dl_bitrate:.3f},{ul_bitrate:.3f}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
