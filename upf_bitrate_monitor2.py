# -----------------------------------------------------------
# Iteratively computes UL/DL bitrates for the 'ogstun' interface
# inside the 'upf_default' Docker container.
# Displays results on screen and writes latest to 'upf.log'.
#
# Assumptions:
# - Docker is installed and accessible on the host.
# - Container 'upf_default' is running.
# - 'ogstun' interface exists inside the container.
# - UL bitrate: based on RX bytes (traffic from gNB to UPF).
# - DL bitrate: based on TX bytes (traffic from UPF to gNB).
# - Bitrates in Mbps.
# -----------------------------------------------------------

import subprocess
import time
import json
import pprint
from datetime import datetime

# Configuration
INTERVAL = 5.0  # Time between calculations in seconds
LOG = "upf.log"  # Path for the log file
CONTAINER = "upf_default"  # Docker container name
INTERFACE = "ogstun"  # Network interface name

pp = pprint.PrettyPrinter(indent=4)

def get_bytes(container, interface, direction):
    """Retrieve RX or TX bytes from the interface inside the container."""
    stat_file = f"/sys/class/net/{interface}/statistics/{direction}_bytes"
    try:
        output = subprocess.check_output(
            ['docker', 'exec', container, 'cat', stat_file],
            stderr=subprocess.STDOUT
        ).decode().strip()
        return int(output)
    except subprocess.CalledProcessError as e:
        print(f"Error reading {direction}_bytes: {e.output.decode().strip()}")
        return None
    except (ValueError, FileNotFoundError) as e:
        print(f"Error reading {direction}_bytes: {e}")
        return None

def write_log(dl_bitrate, ul_bitrate, now):
    """Writes latest bitrates to log file as JSON."""
    dump = {
        'time': now.timestamp(),
        'interface': INTERFACE,
        'metrics': {
            'dl_bitrate': dl_bitrate,
            'ul_bitrate': ul_bitrate
        }
    }
    with open(LOG, 'w') as output:
        json.dump(dump, output, indent=4)

def main():
    print("UPF bitrate sampling function for ogstun interface")
    print(f"Monitoring container: {CONTAINER}, interface: {INTERFACE}")
    print(f"Interval: {INTERVAL} seconds, Log file: {LOG}")
    print()

    requests_sent = 0
    prev_rx = None
    prev_tx = None
    prev_time = None

    while True:
        requests_sent += 1
        print(f"- request {requests_sent}")

        now = datetime.now()
        current_time = time.time()

        # Get RX and TX bytes
        rx_bytes = get_bytes(CONTAINER, INTERFACE, "rx")
        tx_bytes = get_bytes(CONTAINER, INTERFACE, "tx")

        if rx_bytes is None or tx_bytes is None:
            print(f"Failed to read bytes from {INTERFACE}. Retrying in {INTERVAL} seconds...")
            time.sleep(INTERVAL)
            continue

        # Calculate bitrates
        if prev_rx is None or prev_tx is None:
            # First iteration: no rate yet
            dl_bitrate = 0.0
            ul_bitrate = 0.0
            metrics = {
                'interface': INTERFACE,
                'rx_bytes': rx_bytes,
                'tx_bytes': tx_bytes,
                'dl_bitrate': dl_bitrate,
                'ul_bitrate': ul_bitrate
            }
        else:
            delta_rx = rx_bytes - prev_rx
            delta_tx = tx_bytes - prev_tx
            delta_t = current_time - prev_time

            if delta_t > 0:
                # Convert bytes to bits (x8) and to Mbps (/1e6)
                ul_bitrate = (delta_rx * 8 / delta_t) / 1e6  # RX = UL
                dl_bitrate = (delta_tx * 8 / delta_t) / 1e6  # TX = DL
            else:
                ul_bitrate = 0.0
                dl_bitrate = 0.0

            metrics = {
                'interface': INTERFACE,
                'rx_bytes': rx_bytes,
                'tx_bytes': tx_bytes,
                'dl_bitrate': round(dl_bitrate, 2),
                'ul_bitrate': round(ul_bitrate, 2)
            }

        # Display metrics in Amarisoft-like format
        print(f"Requesting interface stats: {INTERFACE}")
        pp.pprint(metrics)
        print()

        # Write to log file
        write_log(round(dl_bitrate, 2), round(ul_bitrate, 2), now)

        # Update previous values
        prev_rx = rx_bytes
        prev_tx = tx_bytes
        prev_time = current_time

        # Sleep
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
