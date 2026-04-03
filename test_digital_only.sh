#!/bin/bash
echo "🚀 Starting DIGITAL TWIN ONLY Test..."

# --- 1. Preparation ---
echo "🔎 Checking and clearing network ports..."
PORTS_TO_CLEAR="80 8000 9090"
for PORT in $PORTS_TO_CLEAR; do
    PID=$(sudo lsof -t -i :$PORT 2>/dev/null)
    if [ -n "$PID" ]; then
        sudo kill -9 $PID
    fi
done

echo "[0/5] Cleaning environment..."
sudo bash clean.sh

# --- 2. Infrastructure Setup ---
echo "[1/5] Starting data collector..."
sudo python3 twin_data_collector.py &

# --- 3. Digital Environment Setup ---
echo "[2/5] Starting Digital Twin Containers..."
sudo python3 modified.digital_twin_setup.py --no-cli > digital_twin_setup.log 2>&1 &

# Wait loop is essential here so the scraper doesn't start too early
echo "⏳ Waiting for containers..."
WAIT_SECONDS=0
while ! sudo docker ps --format '{{.Names}}' | grep -q "upf_default"; do
    if [ $WAIT_SECONDS -ge 180 ]; then exit 1; fi
    sleep 5
    WAIT_SECONDS=$((WAIT_SECONDS + 5))
done

echo "[3/5] Installing tools in containers..."
sudo bash install_tcpreplay_in_upfs.sh

# --- 4. Monitoring & Scraping ---
echo "[4/5] Starting Prometheus, Grafana, and Scraper..."
PROMETHEUS_DIR="/home/ubuntu/comnetsemu/app/Amarisoft.digital.twin/monitoring/prometheus"
(cd "$PROMETHEUS_DIR" && sudo ./prometheus --config.file=prometheus.yml &)
sudo docker run -d -p 8000:3000 grafana/grafana > /dev/null

# CRITICAL: Use a scraper that ONLY looks at local Docker containers.
# sudo python3 combined_scraper.py --digital-only & <-- Conceptual Example
sudo python3 digital_scraper.py &

# --- 5. Trigger Digital Traffic ---
echo "[5/5] Replaying PCAP traffic in Digital Twin..."
# We use the local replay script, NOT the SSH commands
sudo python3 test.pcap_replay_twin.py

echo "✅ Digital test initiated. Check Grafana to see if simulation data is appearing."
