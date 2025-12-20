import asyncio
import websockets
import time
import json
import pprint
import os
import subprocess
from datetime import datetime
import prometheus_client as prom
import logging

# Set LOCAL True for running locally
LOCAL = True

if LOCAL:
    # HARDCODED ENV variables (comment if using Dockerfile)
    TARGET_ENB = "10.196.30.239:9001"  # Socket for Amarisoft gNB (or eNB)
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

# Amarisoft API messages
API_MESSAGE_ENB_UEGET = '{"message":"ue_get","stats": true}'
API_MESSAGE_MME_UEGET = '{"message":"ue_get"}'

# Prometheus metrics to expose
AMARISOFT_COUNTER = prom.Gauge('counter', 'Naive counter')  # Dummy variable for validating behavior
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
PROMETHEUS_SERVER = 80

pp = pprint.PrettyPrinter(indent=4)

async def amarisoft_api_request(target, msg):
    uri = "ws://" + target
    print("Requesting to API uri: ", uri)
    async with websockets.connect(uri, origin="Test") as websocket:
        ready = await websocket.recv()
        await websocket.send(msg)
        rsp = await websocket.recv()
        return json.loads(rsp)

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
    output.close()

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
            cqi = json_gnb_ueget['ue_list'][ue_ix]['cells'][0]['cqi']
            AMARISOFT_CQI_GAUGE.labels(ue=str(ue_id)).set(cqi)
            dl_bitrate = json_gnb_ueget['ue_list'][ue_ix]['cells'][0]['dl_bitrate']
            AMARISOFT_DL_BITRATE_GAUGE.labels(ue=str(ue_id)).set(dl_bitrate)
            try:
                dl_mcs = json_gnb_ueget['ue_list'][ue_ix]['cells'][0]['dl_mcs']
            except:
                dl_mcs = 0
            AMARISOFT_DL_MCS_GAUGE.labels(ue=str(ue_id)).set(dl_mcs)
            epre = json_gnb_ueget['ue_list'][ue_ix]['cells'][0]['epre']
            AMARISOFT_EPRE_GAUGE.labels(ue=str(ue_id)).set(epre)
            pusch_snr = json_gnb_ueget['ue_list'][ue_ix]['cells'][0]['pusch_snr']
            AMARISOFT_PUSCH_SNR_GAUGE.labels(ue=str(ue_id)).set(pusch_snr)
            ul_bitrate = json_gnb_ueget['ue_list'][ue_ix]['cells'][0]['ul_bitrate']
            AMARISOFT_UL_BITRATE_GAUGE.labels(ue=str(ue_id)).set(ul_bitrate)
            try:
                ul_mcs = json_gnb_ueget['ue_list'][ue_ix]['cells'][0]['ul_mcs']
            except:
                ul_mcs = 0
            AMARISOFT_UL_MCS_GAUGE.labels(ue=str(ue_id)).set(ul_mcs)
            ul_path_loss = json_gnb_ueget['ue_list'][ue_ix]['cells'][0]['ul_path_loss']
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
    except subprocess.CalledProcessError as e:
        print(f"Error checking interface {interface}: {e.output.decode().strip()}")
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
        print(f"Error reading {direction}_bytes: {e.output.decode().strip()}")
        return None
    except (ValueError, FileNotFoundError) as e:
        print(f"Error reading {direction}_bytes: {e}")
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
    print("Amarisoft and UPF sampling function exposing Prometheus metrics")
    print(f"Starting Prometheus server (exposing metrics) in port {PROMETHEUS_SERVER}")
    prom.start_http_server(PROMETHEUS_SERVER)
    print(f"Monitoring container: {CONTAINER}, interface: {INTERFACE}")
    print(f"Interval: {INTERVAL} seconds, Amarisoft Log: {LOG_AMARISOFT}, UPF Log: {LOG_UPF}")
    print()

    # Check if container and interface are valid
    try:
        subprocess.check_output(['docker', 'ps'], stderr=subprocess.STDOUT)
        if not subprocess.check_output(['docker', 'ps', '-q', '-f', f'name={CONTAINER}']).decode().strip():
            print(f"Error: Container '{CONTAINER}' is not running.")
            return
    except subprocess.CalledProcessError as e:
        print(f"Error checking container: {e.output.decode().strip()}")
        return

    if not check_interface_exists(CONTAINER, INTERFACE):
        print(f"Error: Interface '{INTERFACE}' does not exist or lacks rx_bytes/tx_bytes.")
        return

    requests_sent = 0
    prev_rx = None
    prev_tx = None
    prev_time = None

    while True:
        requests_sent += 1
        print(f"- request {requests_sent}")
        now = datetime.now()
        current_time = time.time()

        # Amarisoft API request
        json_gnb_ueget = None
        while json_gnb_ueget is None:
            try:
                json_gnb_ueget = asyncio.run(amarisoft_api_request(TARGET_ENB, API_MESSAGE_ENB_UEGET))
            except:
                print(f"EXCEPTION: something went wrong when connecting to Amarisoft API. Retrying in {INTERVAL} seconds...")
                time.sleep(INTERVAL)

        print("\n ------- gNB -------")
        pp.pprint(json_gnb_ueget)
        write_amarisoft_log(json_gnb_ueget, now)

        # UPF bitrate calculation
        rx_bytes = get_bytes(CONTAINER, INTERFACE, "rx")
        tx_bytes = get_bytes(CONTAINER, INTERFACE, "tx")

        if rx_bytes is None or tx_bytes is None:
            print(f"Failed to read bytes from {INTERFACE}. Retrying in {INTERVAL} seconds...")
            time.sleep(INTERVAL)
            continue

        if prev_rx is None or prev_tx is None:
            dl_bitrate_upf = 0.0
            ul_bitrate_upf = 0.0
            metrics = {
                'interface': INTERFACE,
                'rx_bytes': rx_bytes,
                'tx_bytes': tx_bytes,
                'dl_bitrate': dl_bitrate_upf,
                'ul_bitrate': ul_bitrate_upf
            }
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
                'rx_bytes': rx_bytes,
                'tx_bytes': tx_bytes,
                'delta_rx': delta_rx,
                'delta_tx': delta_tx,
                'delta_time': round(delta_t, 2),
                'dl_bitrate': round(dl_bitrate_upf, 2),
                'ul_bitrate': round(ul_bitrate_upf, 2)
            }

        print(f"\nRequesting interface stats: {INTERFACE}")
        pp.pprint(metrics)
        print()

        write_upf_log(dl_bitrate_upf, ul_bitrate_upf, rx_bytes, tx_bytes, now)
        expose_prometheus_metrics(requests_sent, json_gnb_ueget, dl_bitrate_upf, ul_bitrate_upf)

        prev_rx = rx_bytes
        prev_tx = tx_bytes
        prev_time = current_time
        time.sleep(INTERVAL)
        print("\n\n")

if __name__ == "__main__":
    main()
