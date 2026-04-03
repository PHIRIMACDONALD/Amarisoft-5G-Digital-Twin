#!/bin/bash
echo "🚀 Starting PHYSICAL TWIN ONLY Test..."

# --- 1. Preparation ---
# We still need ports clear for the collector/Prometheus/Grafana
echo "🔎 Checking and clearing network ports..."
PORTS_TO_CLEAR="80 8000 9090"
for PORT in $PORTS_TO_CLEAR; do
    PID=$(sudo lsof -t -i :$PORT 2>/dev/null)
    if [ -n "$PID" ]; then
        sudo kill -9 $PID
    fi
done

# --- 2. Infrastructure Setup ---
# Even for physical only, we need the collector and visualization tools
echo "[1/4] Starting the twin data collector..."
sudo python3 twin_data_collector.py &

echo "[2/4] Starting Prometheus and Grafana..."
PROMETHEUS_DIR="/home/ubuntu/comnetsemu/app/Amarisoft.digital.twin/monitoring/prometheus"
(cd "$PROMETHEUS_DIR" && sudo ./prometheus --config.file=prometheus.yml &)
sudo docker run -d -p 8000:3000 grafana/grafana > /dev/null

# --- 3. Run Physical Scraper ---
# CRITICAL: You must use a scraper here that DOES NOT look for local containers.
# If 'combined_scraper.py' fails when Docker is down, you need a 'physical_scraper.py'.
echo "[3/4] Starting the PHYSICAL scraper..."
# sudo python3 combined_scraper.py --physical-only &  <-- Conceptual Example
sudo python3 physical_scraper.py & 

# --- 4. Trigger Physical Traffic (The Amarisoft part) ---
echo "[4/4] Triggering traffic on Physical Amarisoft..."
sshpass -p '5gbasestation+!' ssh -o StrictHostKeyChecking=no root@10.196.30.239 "rm -f /root/Desktop/traffic/*.pcap /root/Desktop/traffic/iteration/*.pcap"
sshpass -p '5gbasestation+!' ssh -o StrictHostKeyChecking=no root@10.196.30.239 "nohup python3 /root/regenerationtaffic.py > /dev/null 2>&1 &"

echo "✅ Physical test initiated. Check Grafana to see if real-world data is appearing."
