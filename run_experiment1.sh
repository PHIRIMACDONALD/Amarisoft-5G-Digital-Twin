#!/bin/bash

# This script automates the full workflow for setting up and running the
# digital twin experiment, with a robust check for container readiness.

echo "🚀 Starting the full automation script for Multipass..."
echo "================================================="

# --- New Step: Check and Clear Required Ports ---
echo "🔎 Checking and clearing network ports..."
PORTS_TO_CLEAR="80 3000 8000 9090"

for PORT in $PORTS_TO_CLEAR; do
    # The '-t' flag gives us only the PID, which is perfect for scripting.
    # We redirect stderr to /dev/null to suppress messages if no process is found.
    PID=$(sudo lsof -t -i :$PORT 2>/dev/null)

    if [ -n "$PID" ]; then
        echo "   - Port $PORT is in use by PID(s): $PID. Terminating..."
        # The output of lsof can be multiple PIDs, so we pass them all to kill.
        sudo kill -9 $PID
        # Add a small delay to allow the OS to release the port.
        sleep 1
        echo "   - Process(es) on port $PORT terminated."
    else
        echo "   - Port $PORT is already free."
    fi
done
echo "✅ All required ports are clear."
echo "-------------------------------------------------"


# --- Step 0: Initial Cleanup ---
echo "[0/9] Cleaning the digital twin environment..."
sudo bash clean.sh
echo "✅ Environment cleaned."
echo "-------------------------------------------------"

# --- Step 1: Run Twin Data Collector ---
echo "[1/9] Starting the twin data collector in the background..."
sudo python3 twin_data_collector.py &
echo "✅ Data collector is running."
echo "-------------------------------------------------"

# --- Step 2: Run Digital Twin Setup & Wait Intelligently ---
echo "[2/9] Starting modified digital twin setup in the background..."
sudo python3 modified.digital_twin_setup.py --no-cli > digital_twin_setup.log 2>&1 &

echo "⏳ Waiting for the network containers to be ready..."
WAIT_SECONDS=0
# Loop until the 'upf_default' container is found in a 'running' state, with a 3-minute timeout.
while ! sudo docker ps --format '{{.Names}}' | grep -q "upf_default"; do
    if [ $WAIT_SECONDS -ge 180 ]; then
        echo "⛔️ Timed out after 3 minutes waiting for containers. Check digital_twin_setup.log for errors."
        exit 1
    fi
    sleep 5
    WAIT_SECONDS=$((WAIT_SECONDS + 5))
    echo "   ... still waiting for containers ($WAIT_SECONDS seconds elapsed)"
done
echo "✅ All network containers are up and running!"
echo "-------------------------------------------------"

# --- Step 3: Install TCPreplay in UPFs ---
echo "[3/9] Installing tcpreplay in the UPFs..."
sudo bash install_tcpreplay_in_upfs.sh
echo "✅ TCPreplay installation complete."
echo "-------------------------------------------------"

sudo pkill -f "prometheus --config.file=prometheus.yml" 2>/dev/null || true
sleep 1

# --- Step 4: Start Prometheus (FIXED PATH) ---
echo "[4/9] Starting Prometheus monitoring server..."
# Corrected path from 'Prometheus' to 'prometheus'
PROMETHEUS_DIR="/home/ubuntu/comnetsemu/app/Amarisoft.digital.twin/monitoring/prometheus"
if [ -d "$PROMETHEUS_DIR" ]; then
    (cd "$PROMETHEUS_DIR" && sudo ./prometheus --config.file=prometheus.yml &)
    echo "✅ Prometheus is running in the background."
else
    echo "⚠️ Prometheus directory not found at $PROMETHEUS_DIR. Skipping."
fi
echo "-------------------------------------------------"

# --- Step 5: Start Grafana ---
echo "[5/9] Starting Grafana container..."
# --- Step 5: Start Grafana (provisioned) ---
echo "[5/9] Starting Grafana container (with provisioning)..."
sudo docker rm -f grafana_automation >/dev/null 2>&1 || true

sudo docker run -d \
  --name grafana_automation \
  -p 8000:3000 \
  --add-host=host.docker.internal:host-gateway \
  -v "$PWD/dashboard_automation/provisioning/datasources:/etc/grafana/provisioning/datasources" \
  -v "$PWD/dashboard_automation/provisioning/dashboards:/etc/grafana/provisioning/dashboards" \
  grafana/grafana >/dev/null

echo "✅ Grafana provisioned (datasource name: Prometheus, dashboard loaded automatically)."
echo "-------------------------------------------------"

# --- Step 6: Run Combined Scraper ---
echo "[6/9] Starting the combined data scraper..."
sudo python3 combined_scraper.py &
echo "✅ Scraper is running in the background."
echo "-------------------------------------------------"

# --- Step 7: Clean PCAP files on Amarisoft ---
echo "[7/9] Connecting to Amarisoft to delete old pcap files..."
sshpass -p '5gbasestation+!' ssh -o StrictHostKeyChecking=no root@10.196.30.239 "rm -f /root/Desktop/traffic/*.pcap /root/Desktop/traffic/iteration/*.pcap"
echo "✅ Old pcap files deleted on Amarisoft."
echo "-------------------------------------------------"

# --- Step 8: Regenerate Traffic on Amarisoft ---
echo "[8/9] Connecting to Amarisoft to start traffic regeneration..."
sshpass -p '5gbasestation+!' ssh -o StrictHostKeyChecking=no root@10.196.30.239 "nohup python3 /root/regenerationtaffic.py > /dev/null 2>&1 &"
echo "✅ Traffic regeneration started on Amarisoft."
echo "-------------------------------------------------"

# --- Step 9: Wait and Run PCAP Replay ---
echo "[9/9] Waiting 2 minutes and 15 seconds for new traffic generation..."
sleep 135
echo "⏳ Wait complete. Starting pcap replay on the digital twin..."
sudo python3 test.pcap_replay_twin.py
echo "-------------------------------------------------"

echo "🎉 Automation script finished successfully!"
echo "================================================="
