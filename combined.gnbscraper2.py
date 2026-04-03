# -----------------------------------------------------------
# Combined Prometheus Exporter:
# - UE stats (UL/DL bitrate) from Amarisoft gNB via WebSocket
# - Core UPF (UL/DL bitrate) from ogstun interface inside upf_default container
# -----------------------------------------------------------

import asyncio
import websockets
import time
import json
import os
import subprocess
from datetime import datetime
import prometheus_client as prom
import pprint

# ---------------- CONFIGURATION ----------------
LOCAL = True

if LOCAL:
    # Amarisoft
    TARGET_ENB = "10.196.30.239:9001"
    # UPF container info
    CONTAINER_NAME = "upf_default"
    INTERFACE = "ogstun"
    INTERVAL = 5.0  # seconds
    LOG = "amarisoft.log"
else:
    TARGET_ENB = str(os.environ.get("TARGET_ENB"))
    CONTAINER_NAME = str(os.environ.get("CONTAINER_NAME", "upf_default"))
    INTERFACE = str(os.environ.get("INTERFACE", "ogstun"))
    INTERVAL = float(os.environ.get("INTERVAL", 5.0))
    LOG = str(os.environ.get("LOG", "amarisoft.log"))

PROMETHEUS_PORT = 80

# ---------------- PROMETHEUS METRICS ----------------
# gNB metrics per UE
DL_BITRATE_GAUGE = prom.Gauge('gnb_dl_bitrate_mbps', 'gNB Downlink bitrate in Mbps', ["ue"])
UL_BITRATE_GAUGE = prom.Gauge('gnb_ul_bitrate_mbps', 'gNB Uplink bitrate in Mbps', ["ue"])

# UPF ogstun metrics
UPF_DL_BITRATE = prom.Gauge('upf_dl_bitrate_mbps', 'UPF Downlink bitrate (TX on ogstun) in Mbps')
UPF_UL_BITRATE = prom.Gauge('upf_ul_bitrate_mbps', 'UPF Uplink bitrate (RX on ogstun) in Mbps')

pp = pprint.PrettyPrinter(indent=4)

# ---------------- AMARISOFT FUNCTIONS ----------------

API_MESSAGE_ENB_UEGET = '{"message":"ue_get","stats": true}'

async def amarisoft_api_request(target, msg):
    """Request UE stats from Amarisoft via WebSocket"""
    uri = "ws://" + target
    async with websockets.connect(uri, origin="Test") as websocket:
        await websocket.recv()  # Wait for ready message
        await websocket.send(msg)
        rsp = await websocket.recv()
        return json.loads(rsp)

def write_log(json_response, now):
    """Store latest UE stats in a log file."""
    dump = {'time': now.timestamp()}
    dump['ue_list'] = json_response.get('ue_list', [])
    with open(LOG, 'w') as output:
        output.write(json.dumps(dump, indent=2))

def expose_gnb_bitrate_metrics(json_gnb_ueget):
    """Extract and expose UL/DL bitrates per UE."""
    ue_list = json_gnb_ueget.get('ue_list', [])
    for ue_ix, ue in enumerate(ue_list):
        ue_id = str(ue_ix + 1)
        cell = ue['cells'][0]
        dl_bitrate = cell.get('dl_bitrate', 0)
        ul_bitrate = cell.get('ul_bitrate', 0)
        DL_BITRATE_GAUGE.labels(ue=ue_id).set(dl_bitrate)
        UL_BITRATE_GAUGE.labels(ue=ue_id).set(ul_bitrate)

# ---------------- UPF OGSTUN FUNCTIONS ----------------

def read_interface_bytes(container, iface):
    """Read RX and TX bytes from ogstun inside the container."""
    try:
        rx_bytes = int(subprocess.check_output(
            ["docker", "exec", container, "cat", f"/sys/class/net/{iface}/statistics/rx_bytes"]
        ).strip())
        tx_bytes = int(subprocess.check_output(
            ["docker", "exec", container, "cat", f"/sys/class/net/{iface}/statistics/tx_bytes"]
        ).strip())
        return rx_bytes, tx_bytes
    except subprocess.CalledProcessError:
        print(f"Error: could not read interface stats for {iface} in {container}")
        return None, None

def update_upf_metrics(prev_rx, prev_tx, prev_time):
    """Compute UL/DL bitrate for ogstun and expose via Prometheus."""
    curr_rx, curr_tx = read_interface_bytes(CONTAINER_NAME, INTERFACE)
    curr_time = time.time()

    if None in (curr_rx, curr_tx, prev_rx, prev_tx):
        return prev_rx, prev_tx, curr_time

    delta_time = curr_time - prev_time
    if delta_time <= 0:
        return prev_rx, prev_tx, curr_time

    rx_mbps = (curr_rx - prev_rx) * 8 / delta_time / 1e6  # UL = RX
    tx_mbps = (curr_tx - prev_tx) * 8 / delta_time / 1e6  # DL = TX

    UPF_UL_BITRATE.set(rx_mbps)
    UPF_DL_BITRATE.set(tx_mbps)

    print(f"[UPF ogstun] UL: {rx_mbps:.2f} Mbps, DL: {tx_mbps:.2f} Mbps")

    return curr_rx, curr_tx, curr_time

# ---------------- MAIN LOOP ----------------

def main():
    print(f"Starting Combined Prometheus Exporter on port {PROMETHEUS_PORT}")
    prom.start_http_server(PROMETHEUS_PORT)

    requests_sent = 0
    prev_rx, prev_tx = read_interface_bytes(CONTAINER_NAME, INTERFACE)
    prev_time = time.time()

    while True:
        requests_sent += 1
        print(f"\n--- Iteration {requests_sent} ---")
        now = datetime.now()

        # 1. Get Amarisoft gNB metrics
        try:
            json_gnb_ueget = asyncio.run(amarisoft_api_request(TARGET_ENB, API_MESSAGE_ENB_UEGET))
            write_log(json_gnb_ueget, now)
            expose_gnb_bitrate_metrics(json_gnb_ueget)
        except Exception as e:
            print(f"Amarisoft connection error: {e}")

        # 2. Get UPF ogstun metrics
        prev_rx, prev_tx, prev_time = update_upf_metrics(prev_rx, prev_tx, prev_time)

        # Optional: print UEs for debug
        pp.pprint(json_gnb_ueget.get('ue_list', []))

        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
