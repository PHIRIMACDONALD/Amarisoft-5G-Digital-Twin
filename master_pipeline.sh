#!/bin/bash
set -e  # Stop on first error

# Amarisoft info
AMARISOFT_IP=10.196.30.239
AMARISOFT_PASS='5gbasestation+!'
SSH_OPTS="-o StrictHostKeyChecking=no"

# Paths
VM_PATH=/home/ubuntu/comnetsemu/app/Amarisoft.digital.twin
PROM_PATH=$VM_PATH/monitoring/prometheus

echo "[0/10] Run clean.sh first..."
cd $VM_PATH
sudo bash clean.sh

echo "[1/10] Run twin_data_collector.py (Digital Twin)..."
sudo python3 twin_data_collector.py

echo "[2/10] Run modified.digital_twin_setup.py in background (wait 1 min)..."
sudo nohup python3 modified.digital_twin_setup.py > setup.log 2>&1 &
sleep 60

echo "[3/10] Install tcpreplay in UPFs..."
sudo bash install_tcpreplay_in_upfs.sh

echo "[4/10] Start Prometheus..."
cd $PROM_PATH
sudo nohup ./prometheus --config.file=prometheus.yml > prometheus.log 2>&1 &

echo "[5/10] Start Grafana container on port 8000..."
if ! sudo docker ps | grep -q grafana; then
    sudo docker run -d -p 8000:3000 --name grafana_$RANDOM grafana/grafana
else
    echo "Grafana container already running."
fi

echo "Grafana and Prometheus ready ✅"

echo "[6/10] Run combined_scraper.py..."
cd $VM_PATH
sudo python3 combined_scraper.py

echo "[7/10] Clean old PCAPs on Amarisoft..."
sudo sshpass -p "$AMARISOFT_PASS" ssh $SSH_OPTS root@$AMARISOFT_IP \
    "rm -f /root/Desktop/traffic/*.pcap /root/Desktop/traffic/iteration/*.pcap"

echo "[8/10] Run regenerationtaffic.py on Amarisoft (background)..."
sudo sshpass -p "$AMARISOFT_PASS" ssh $SSH_OPTS root@$AMARISOFT_IP \
    "nohup python3 /root/regenerationtaffic.py > /root/regeneration.log 2>&1 &"

echo "   Waiting 2 mins 15s before running replay..."
sleep 135

echo "[9/10] Run test.pcap_replay_twin.py (Digital Twin)..."
cd $VM_PATH
sudo python3 test.pcap_replay_twin.py

echo "✅ Master pipeline complete."
echo "   - Prometheus UI → http://192.168.2.2:9090/targets"
echo "   - Grafana UI    → http://192.168.2.2:8000"
