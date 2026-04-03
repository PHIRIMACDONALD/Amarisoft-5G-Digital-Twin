import time
import json
import pprint
import os
import subprocess
import random
import math
from datetime import datetime
import prometheus_client as prom

# Set LOCAL True for running locally
LOCAL = True

if LOCAL:
    # HARDCODED ENV variables
    TARGET_ENB = "10.196.30.239:9001"  # Socket for Amarisoft gNB (Simulated)
    INTERVAL = 5.0  # Time between API requests and bitrate calculations
    LOG_AMARISOFT = "amarisoft.log"  # Path of the log to store filtered API responses
    LOG_UPF = "upf.log"  # Path for the UPF log file
    CONTAINER = "upf_default"  # Docker container name
    INTERFACE = "ogstun"  # Network interface name
else:
    # ENV variables from Dockerfile
    TARGET_ENB = str(os.environ.get("TARGET_ENB"))
    TARGET_MME = str(os.environ.get("TARGET_MME"))
    INTERVAL = float(os.environ.get("INTERVAL"))
    LOG_AMARISOFT = str(os.environ.get("LOG_AMARISOFT"))
    LOG_UPF = str(os.environ.get("LOG_UPF"))
    CONTAINER = str(os.environ.get("CONTAINER"))
    INTERFACE = str(os.environ.get("INTERFACE"))

# Prometheus metrics to expose
AMARISOFT_COUNTER = prom.Gauge('counter', 'Naive counter')
AMARISOFT_CQI_GAUGE = prom.Gauge('cqi', 'Channel quality indicator (CQI)', ["ue"])
AMARISOFT_DL_BITRATE_GAUGE = prom.Gauge('dl_bitrate', 'DL bitrate in Mbps', ["ue"])
AMARISOFT_DL_MCS_GAUGE = prom.Gauge('dl_mcs', 'DL MCS', ["ue"])
AMARISOFT_EPRE_GAUGE = prom.Gauge('epre', 'Energy per resource element (EPRE) in dBm', ["ue"])
AMARISOFT_PUSCH_SNR_GAUGE = prom.Gauge('pusch_snr', 'Physical uplink shared channel (PUSCH) SNR', ["ue"])
AMARISOFT_UL_BITRATE_GAUGE = prom.Gauge('ul_bitrate', 'UL bitrate in Mbps', ["ue"])
AMARISOFT_UL_MCS_GAUGE = prom.Gauge('ul_mcs', 'UL MCS', ["ue"])
AMARISOFT_UL_PATHLOSS_GAUGE = prom.Gauge('ul_path_loss', 'UL path Loss (PUSCH) SNR in dB', ["ue"])
UPF_DL_BITRATE_GAUGE = prom.Gauge('upf_dl_bitrate', 'UPF DL bitrate in Mbps', ['interface'])
UPF_UL_BITRATE_GAUGE = prom.Gauge('upf_ul_bitrate', 'UPF UL bitrate in Mbps', ['interface'])
PROMETHEUS_SERVER = 8000  # Changed to 8000 to avoid permission issues if running locally

pp = pprint.PrettyPrinter(indent=4)

# --- SIMULATION HELPERS ---
def simulate_amarisoft_payload(request_count):
    """
    Simulates the JSON response from an Amarisoft Callbox.
    Data fluctuates slightly to look realistic over 20 minutes.
    """
    # Base values
    base_dl_bitrate = 25000000  # 25 Mbps
    base_ul_bitrate = 5000000   # 5 Mbps

    # Add random fluctuation (+/- 10%)
    fluctuation = random.uniform(0.9, 1.1)

    # Simulate a slight drop in quality every ~10 requests
    quality_factor = 0.8 if request_count % 10 == 0 else 1.0

    dl_bitrate = base_dl_bitrate * fluctuation * quality_factor
    ul_bitrate = base_ul_bitrate * fluctuation * quality_factor

    # Simulate CQI (0-15), usually high for good connection
    cqi = int(15 * quality_factor) if quality_factor < 1 else random.randint(13, 15)

    return {
        "message": "ue_get",
        "stats": True,
        "ue_list": [
            {
                "ue_id": 1,
                "ran_ue_id": 1,
                "cells": [
                    {
                        "cqi": cqi,
                        "dl_bitrate": int(dl_bitrate),
                        "dl_mcs": random.randint(20, 26),
                        "epre": random.randint(-85, -75),
                        "pusch_snr": round(random.uniform(18.0, 22.0), 1),
                        "ul_bitrate": int(ul_bitrate),
                        "ul_mcs": random.randint(16, 20),
                        "ul_path_loss": random.randint(68, 72)
                    }
                ]
            }
        ]
    }

# --- END SIMULATION HELPERS ---

def write_amarisoft_log(json_response: dict, now: datetime):
    """Writes latest log (filtered API response) in Amarisoft log file"""
    res = json_response
    dump = {'time': now.timestamp()}
    if len(res['ue_list']) == 0:
        dump.setdefault('ue_list', [])
    else:
        dump.setdefault('ue_list', res['ue_list'])
    with open(LOG_AMARISOFT, 'w') as output:
        output.write(json.dumps(dump))
    # output.close() # valid context manager handles close automatically

def expose_prometheus_metrics(requests_sent, json_gnb_ueget, dl_bitrate_upf, ul_bitrate_upf):
    AMARISOFT_COUNTER.set(requests_sent)
    num_ues_registered = len(json_gnb_ueget['ue_list'])
    if num_ues_registered == 0:
        dl_bitrate = -1
        ul_bitrate = -1
        pusch_snr = -1
        ul_path_loss = -1
    else:
        for ue_ix in range(num_ues_registered):
            ue_id = str(num_ues_registered - ue_ix)
            cell_data = json_gnb_ueget['ue_list'][ue_ix]['cells'][0]

            cqi = cell_data['cqi']
            AMARISOFT_CQI_GAUGE.labels(ue=str(ue_id)).set(cqi)

            dl_bitrate = cell_data['dl_bitrate']
            AMARISOFT_DL_BITRATE_GAUGE.labels(ue=str(ue_id)).set(dl_bitrate)

            try:
                dl_mcs = cell_data['dl_mcs']
            except:
                dl_mcs = 0
            AMARISOFT_DL_MCS_GAUGE.labels(ue=str(ue_id)).set(dl_mcs)

            epre = cell_data['epre']
            AMARISOFT_EPRE_GAUGE.labels(ue=str(ue_id)).set(epre)

            pusch_snr = cell_data['pusch_snr']
            AMARISOFT_PUSCH_SNR_GAUGE.labels(ue=str(ue_id)).set(pusch_snr)

            ul_bitrate = cell_data['ul_bitrate']
            AMARISOFT_UL_BITRATE_GAUGE.labels(ue=str(ue_id)).set(ul_bitrate)

            try:
                ul_mcs = cell_data['ul_mcs']
            except:
                ul_mcs = 0
            AMARISOFT_UL_MCS_GAUGE.labels(ue=str(ue_id)).set(ul_mcs)

            ul_path_loss = cell_data['ul_path_loss']
            AMARISOFT_UL_PATHLOSS_GAUGE.labels(ue=str(ue_id)).set(ul_path_loss)

    UPF_DL_BITRATE_GAUGE.labels(interface=INTERFACE).set(dl_bitrate_upf)
    UPF_UL_BITRATE_GAUGE.labels(interface=INTERFACE).set(ul_bitrate_upf)

def check_interface_exists(container, interface):
    """Check if the interface exists in the container."""
    try:
        output = subprocess.check_output(
            ['docker', 'exec', container, 'ls', f'/sys/class/net/{interface}/statistics/'],
            stderr=subprocess.STDOUT
        ).decode().strip()
        return 'rx_bytes' in output and 'tx_bytes' in output
    except (subprocess.CalledProcessError, FileNotFoundError):
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
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return None

def write_upf_log(dl_bitrate, ul_bitrate, rx_bytes, tx_bytes, now):
    """Writes latest bitrates and bytes to UPF log file as JSON."""
    dump = {
        'time': now.timestamp(),
        'interface': INTERFACE,
        'metrics': {
            'dl_bitrate': round(dl_bitrate, 2),
            'ul_bitrate': round(ul_bitrate, 2),
            'rx_bytes': rx_bytes,
            'tx_bytes': tx_bytes
        }
    }
    with open(LOG_UPF, 'w') as output:
        json.dump(dump, output, indent=4)

def main():
    print("Amarisoft (Simulated) and UPF sampling function exposing Prometheus metrics")

    # Robust port selection logic
    server_started = False
    for port_offset in range(20):  # Try up to 20 ports
        current_port = PROMETHEUS_SERVER + port_offset
        try:
            print(f"Attempting to start Prometheus server on port {current_port}...")
            prom.start_http_server(current_port)
            print(f"SUCCESS: Prometheus server running on port {current_port}")
            server_started = True
            break
        except OSError:
            print(f"Port {current_port} is in use. Trying next port...")

    if not server_started:
        print(f"CRITICAL ERROR: Could not find an open port starting from {PROMETHEUS_SERVER}. Exiting.")
        return

    print(f"Monitoring container: {CONTAINER}, interface: {INTERFACE}")
    print(f"Interval: {INTERVAL} seconds, Amarisoft Log: {LOG_AMARISOFT}, UPF Log: {LOG_UPF}")
    print("--- Simulation Mode: Active for Amarisoft Data ---")
    print()

    # Check if container and interface are valid
    upf_available = True
    try:
        subprocess.check_output(['docker', 'ps'], stderr=subprocess.STDOUT)
        if not subprocess.check_output(['docker', 'ps', '-q', '-f', f'name={CONTAINER}']).decode().strip():
            print(f"WARNING: Container '{CONTAINER}' is not running. UPF metrics will be 0.")
            upf_available = False
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("WARNING: Docker not found or error checking container. UPF metrics will be 0.")
        upf_available = False

    if upf_available and not check_interface_exists(CONTAINER, INTERFACE):
        print(f"WARNING: Interface '{INTERFACE}' does not exist or lacks stats. UPF metrics will be 0.")
        upf_available = False

    requests_sent = 0
    prev_rx = None
    prev_tx = None
    prev_time = None

    # Simulation duration setup (20 minutes)
    start_time_simulation = time.time()
    simulation_duration = 20 * 60  # 20 minutes in seconds

    while True:
        # Check if 20 mins have passed
        if time.time() - start_time_simulation > simulation_duration:
            print("Simulation duration (20 mins) reached. Stopping.")
            break

        requests_sent += 1
        print(f"- request {requests_sent}")
        now = datetime.now()
        current_time = time.time()

        # --- Amarisoft API request (SIMULATED) ---
        json_gnb_ueget = simulate_amarisoft_payload(requests_sent)

        print("\n ------- gNB (Simulated) -------")
        pp.pprint(json_gnb_ueget)
        write_amarisoft_log(json_gnb_ueget, now)

        # --- UPF bitrate calculation ---
        rx_bytes = None
        tx_bytes = None

        if upf_available:
            rx_bytes = get_bytes(CONTAINER, INTERFACE, "rx")
            tx_bytes = get_bytes(CONTAINER, INTERFACE, "tx")

        # If UPF is unavailable or failed to read, we set to 0 to keep script running
        if rx_bytes is None or tx_bytes is None:
            if upf_available:
                print(f"Failed to read bytes from {INTERFACE}. (If this persists, check Docker)")
            dl_bitrate_upf = 0.0
            ul_bitrate_upf = 0.0
        else:
            if prev_rx is None or prev_tx is None:
                dl_bitrate_upf = 0.0
                ul_bitrate_upf = 0.0
            else:
                delta_rx = rx_bytes - prev_rx
                delta_tx = tx_bytes - prev_tx
                delta_t = current_time - prev_time

                if delta_t > 0:
                    ul_bitrate_upf = (delta_rx * 8 / delta_t) / 1e6  # RX = UL
                    dl_bitrate_upf = (delta_tx * 8 / delta_t) / 1e6  # TX = DL
                else:
                    ul_bitrate_upf = 0.0
                    dl_bitrate_upf = 0.0

        metrics = {
            'interface': INTERFACE,
            'rx_bytes': rx_bytes if rx_bytes else 0,
            'tx_bytes': tx_bytes if tx_bytes else 0,
            'dl_bitrate': round(dl_bitrate_upf, 2),
            'ul_bitrate': round(ul_bitrate_upf, 2)
        }

        print(f"\nRequesting interface stats: {INTERFACE}")
        pp.pprint(metrics)
        print()

        write_upf_log(dl_bitrate_upf, ul_bitrate_upf, rx_bytes, tx_bytes, now)
        expose_prometheus_metrics(requests_sent, json_gnb_ueget, dl_bitrate_upf, ul_bitrate_upf)

        if rx_bytes is not None:
            prev_rx = rx_bytes
            prev_tx = tx_bytes

        prev_time = current_time
        time.sleep(INTERVAL)
        print("\n\n")

if __name__ == "__main__":
    main()
