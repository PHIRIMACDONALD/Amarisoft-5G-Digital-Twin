# -----------------------------------------------------------
# Iteratively requests the config of the gNB through a WebSocket and writes it in a file.
#
# 
# -----------------------------------------------------------

import asyncio
import websockets   # Install locally through command pip install "websockets==8.1"
import time
import json
import pprint
import os
from datetime import datetime
import prometheus_client as prom
import logging

# Set LOCAL True for running locally
LOCAL = True

if LOCAL:
    # HARDCODED ENV variables (comment if using Dockerfile)
    TARGET_ENB = "10.196.30.239:9001"  # Socket for of Amarisoft gNB (or eNB)
    INTERVAL = 5.0  # Time between two API requests
    LOG = "amarisoft.log"   # Path of the log to store filtered API responses
else:
    # ENV variables from Dockerfile
    TARGET_ENB = str(os.environ.get("TARGET_ENB"))
    TARGET_MME = str(os.environ.get("TARGET_MME"))
    INTERVAL = float(os.environ.get("INTERVAL"))
    LOG = str(os.environ.get("LOG"))

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
PROMETHEUS_SERVER = 80

pp = pprint.PrettyPrinter(indent=4)

async def amarisoft_api_request(target, msg):
    uri = "ws://" + target

    print("Requesting to API uri: ", uri)

    async with websockets.connect(uri, origin="Test") as websocket:

        ready = await websocket.recv()
        await websocket.send(msg)   
        rsp = await websocket.recv()
        # pp.pprint(json.loads(rsp))

        return json.loads(rsp)


def write_log(json_response: dict, now: datetime):
    """Writes latest log (filtered API response) in log file"""

    res = json_response
    dump = {'time': now.timestamp()}

    if len(res['ue_list']) == 0:
        dump.setdefault('ue_list', [])
    else:
        dump.setdefault('ue_list', res['ue_list'])

    #pprint.pprint(dump)

    # Overwrite in logs file
    with open(LOG, 'w') as output:
        output.write(json.dumps(dump))
    output.close()

def expose_prometheus_metrics(requests_sent, json_gnb_ueget):

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
            # Read from logs.
            
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
            

def main():

    print("Amarisoft sampling function exposing Prometheus metrics")
    print("Starting Prometheus server (exposing metrics) in port ", PROMETHEUS_SERVER)
    prom.start_http_server(PROMETHEUS_SERVER)

    requests_sent = 0

    while True:

        print("Starting requests to Amarisoft Callbox")
        requests_sent += 1
        # print("\n *********** REQUEST " + str(requests_sent) + " ***********")
        print("- request " + str(requests_sent))

        now = datetime.now()

        json_gnb_ueget = None
        while json_gnb_ueget is None:
            try:
                # connect
                json_gnb_ueget = asyncio.run(amarisoft_api_request(TARGET_ENB, API_MESSAGE_ENB_UEGET))
            except:
                print("EXCEPTION: something went wrong when connecting to Amarisoft API. Retrying in " + str(INTERVAL) + " seconds...")
                time.sleep(INTERVAL)
        
        #json_mme_ueget = asyncio.run(amarisoft_api_request(TARGET_MME, API_MESSAGE_GNB_UEGET)())

        #print("\n ------- MME -------")
        #pp.pprint(json_response_mme)
        
        #print("\n ------- gNB -------")
        pp.pprint(json_gnb_ueget)

        # TODO: Code snippet here to map 'amf_ue_id' or 'ran_ue_id' to 'imsi' or 'suci'.
        
        write_log(json_gnb_ueget, now)

        # Expose Prometheus metrics
        expose_prometheus_metrics(requests_sent, json_gnb_ueget)

        # Sleep
        time.sleep(INTERVAL)

        print("\n\n")

if __name__ == "__main__":
    main()
