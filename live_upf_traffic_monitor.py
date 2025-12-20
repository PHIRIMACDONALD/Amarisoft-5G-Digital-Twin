#!/usr/bin/env python3
import psutil
import time
import os

def get_interface_stats(interface):
    """Return bytes sent/received for a given network interface"""
    io_counters = psutil.net_io_counters(pernic=True)
    if interface in io_counters:
        stats = io_counters[interface]
        return stats.bytes_sent, stats.bytes_recv
    else:
        return None, None

def human_readable(size_bytes):
    """Convert bytes to human-readable (Mbps)"""
    return round((size_bytes * 8) / (1024 * 1024), 2)  # bits → Mbps

def main():
    os.system('clear')
    print("📡 UPF Real-Time Traffic Monitor")
    print("──────────────────────────────────────")
    interface = os.getenv("UPF_INTERFACE", "ogstun")  # Default interface

    print(f"Monitoring interface: {interface}")
    print(f"{'Time':<10} {'Downlink (Mbps)':<20} {'Uplink (Mbps)':<20}")
    print("-" * 55)

    prev_tx, prev_rx = get_interface_stats(interface)
    prev_time = time.time()

    while True:
        time.sleep(1)
        curr_tx, curr_rx = get_interface_stats(interface)
        curr_time = time.time()

        if None in (curr_tx, curr_rx, prev_tx, prev_rx):
            print("⚠️  Interface not found, check name and permissions.")
            break

        # Calculate rate in Mbps
        elapsed = curr_time - prev_time
        uplink_rate = human_readable(curr_tx - prev_tx) / elapsed
        downlink_rate = human_readable(curr_rx - prev_rx) / elapsed

        print(f"{time.strftime('%H:%M:%S'):<10} {downlink_rate:<20.2f} {uplink_rate:<20.2f}")

        prev_tx, prev_rx = curr_tx, curr_rx
        prev_time = curr_time

if __name__ == "__main__":
    main()
