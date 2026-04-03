import subprocess
import time
import json
import pprint
from datetime import datetime

# Configuration
INTERVAL = 5.0  # Time between calculations in seconds
LOG = "upf.log"  # Path for the log file
CONTAINERS = ["ue1", "ue2"]  # Docker container names
INTERFACES = ["uesimtun0", "uesimtun1", "uesimtun2"]  # Network interface names

pp = pprint.PrettyPrinter(indent=4)

def check_container_running(container):
    """Check if the container is running."""
    try:
        output = subprocess.check_output(
            ['docker', 'ps', '-q', '-f', f'name={container}'],
            stderr=subprocess.STDOUT
        ).decode().strip()
        return bool(output)
    except subprocess.CalledProcessError as e:
        print(f"Error checking container {container}: {e.output.decode().strip()}")
        return False

def check_interface_exists(container, interface):
    """Check if the interface exists in the container."""
    try:
        output = subprocess.check_output(
            ['docker', 'exec', container, 'ls', f'/sys/class/net/{interface}/statistics/'],
            stderr=subprocess.STDOUT
        ).decode().strip()
        return 'rx_bytes' in output and 'tx_bytes' in output
    except subprocess.CalledProcessError as e:
        print(f"Error checking interface {interface} in {container}: {e.output.decode().strip()}")
        return False

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
        print(f"Error reading {direction}_bytes for {interface} in {container}: {e.output.decode().strip()}")
        return None
    except (ValueError, FileNotFoundError) as e:
        print(f"Error reading {direction}_bytes for {interface} in {container}: {e}")
        return None

def write_log(metrics_list, now):
    """Writes latest bitrates for all containers and interfaces to log file as JSON."""
    dump = {
        'time': now.timestamp(),
        'containers': metrics_list
    }
    with open(LOG, 'w') as output:
        json.dump(dump, output, indent=4)

def main():
    print("UE bitrate sampling function for multiple interfaces")
    print(f"Monitoring containers: {', '.join(CONTAINERS)}")
    print(f"Interfaces: {', '.join(INTERFACES)}")
    print(f"Interval: {INTERVAL} seconds, Log file: {LOG}")
    print()

    # Check if containers are running
    for container in CONTAINERS:
        if not check_container_running(container):
            print(f"Error: Container '{container}' is not running. Exiting.")
            return

    # Check if interfaces exist
    for container in CONTAINERS:
        for interface in INTERFACES:
            if not check_interface_exists(container, interface):
                print(f"Warning: Interface '{interface}' not found in {container}. Skipping this interface.")
                INTERFACES.remove(interface)  # Remove invalid interface

    if not INTERFACES:
        print("Error: No valid interfaces found in any container. Exiting.")
        return

    requests_sent = 0
    prev_data = {container: {interface: {'rx': None, 'tx': None} for interface in INTERFACES} for container in CONTAINERS}
    prev_time = None

    while True:
        requests_sent += 1
        print(f"- request {requests_sent}")

        now = datetime.now()
        current_time = time.time()

        metrics_list = []

        for container in CONTAINERS:
            container_metrics = {'container': container, 'interfaces': []}

            for interface in INTERFACES:
                # Get RX and TX bytes
                rx_bytes = get_bytes(container, interface, "rx")
                tx_bytes = get_bytes(container, interface, "tx")

                if rx_bytes is None or tx_bytes is None:
                    print(f"Failed to read bytes for {interface} in {container}. Skipping...")
                    continue

                # Calculate bitrates
                if prev_data[container][interface]['rx'] is None or prev_data[container][interface]['tx'] is None:
                    # First iteration: no rate yet
                    dl_bitrate = 0.0
                    ul_bitrate = 0.0
                    interface_metrics = {
                        'interface': interface,
                        'rx_bytes': rx_bytes,
                        'tx_bytes': tx_bytes,
                        'dl_bitrate': dl_bitrate,
                        'ul_bitrate': ul_bitrate
                    }
                else:
                    delta_rx = rx_bytes - prev_data[container][interface]['rx']
                    delta_tx = tx_bytes - prev_data[container][interface]['tx']
                    delta_t = current_time - prev_time

                    if delta_t > 0:
                        ul_bitrate = (delta_rx * 8 / delta_t) / 1e6  # RX = UL
                        dl_bitrate = (delta_tx * 8 / delta_t) / 1e6  # TX = DL
                    else:
                        ul_bitrate = 0.0
                        dl_bitrate = 0.0

                    interface_metrics = {
                        'interface': interface,
                        'rx_bytes': rx_bytes,
                        'tx_bytes': tx_bytes,
                        'delta_rx': delta_rx,
                        'delta_tx': delta_tx,
                        'delta_time': round(delta_t, 2),
                        'dl_bitrate': round(dl_bitrate, 2),
                        'ul_bitrate': round(ul_bitrate, 2)
                    }

                container_metrics['interfaces'].append(interface_metrics)

                # Update previous values
                prev_data[container][interface]['rx'] = rx_bytes
                prev_data[container][interface]['tx'] = tx_bytes

            # Display metrics
            print(f"Requesting stats for container: {container}")
            pp.pprint(container_metrics)
            print()

            metrics_list.append(container_metrics)

        # Write to log file
        write_log(metrics_list, now)

        # Update previous time
        prev_time = current_time

        # Sleep
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
