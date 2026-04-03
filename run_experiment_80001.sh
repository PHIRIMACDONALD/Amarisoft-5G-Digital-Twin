#!/bin/bash
set -euo pipefail

# This script automates the full workflow for setting up and running the
# digital twin experiment, with a robust check for container readiness.

BASE_DIR="/home/ubuntu/comnetsemu/app/Amarisoft.digital.twin"
PROMETHEUS_DIR="$BASE_DIR/monitoring/prometheus"
PROMETHEUS_YML="$PROMETHEUS_DIR/prometheus.yml"

SCRAPER_PY="$BASE_DIR/combined_scraper_sim.py"
REPLAY_PY="$BASE_DIR/test.pcap_replay_twin_sim.py"

SCRAPER_LOG="$BASE_DIR/combined_scraper.out"
REPLAY_LOG="$BASE_DIR/pcap_replay.out"
PROM_LOG="$BASE_DIR/prometheus.out"

GRAFANA_NAME="grafana-local"
GRAFANA_PORT="8000"
SCRAPER_PORT="8001"
PROM_PORT="9090"

echo "🚀 Starting the full automation script for Multipass..."
echo "================================================="

# -------------------------------------------------
# PRE-STEP: Stop previous runs cleanly (more reliable than killing ports)
# -------------------------------------------------
echo "🧹 Stopping previous processes (Prometheus / Grafana / Scraper / Replay)..."

# Stop python background jobs we start
sudo pkill -f "combined_scraper_sim\.py" >/dev/null 2>&1 || true
sudo pkill -f "test\.pcap_replay_twin_sim\.py" >/dev/null 2>&1 || true

# Stop prometheus
sudo pkill -x prometheus >/dev/null 2>&1 || true

# Stop/remove grafana container (this frees port 8000 cleanly)
if sudo docker ps -a --format '{{.Names}}' | grep -qx "$GRAFANA_NAME"; then
  sudo docker rm -f "$GRAFANA_NAME" >/dev/null 2>&1 || true
fi

echo "✅ Previous processes stopped."
echo "-------------------------------------------------"

# -------------------------------------------------
# Step: Clear only ports that are real host processes (NOT docker-proxy:8000)
# -------------------------------------------------
echo "🔎 Checking and clearing network ports..."
PORTS_TO_CLEAR="80 ${SCRAPER_PORT} ${PROM_PORT}"

for PORT in $PORTS_TO_CLEAR; do
    PID=$(sudo lsof -t -i :$PORT 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo "   - Port $PORT is in use by PID(s): $PID. Terminating..."
        sudo kill -9 $PID >/dev/null 2>&1 || true
        sleep 1
        echo "   - Process(es) on port $PORT terminated."
    else
        echo "   - Port $PORT is already free."
    fi
done

echo "✅ Required ports are clear (except $GRAFANA_PORT managed by Docker)."
echo "-------------------------------------------------"

# --- Step 0: Initial Cleanup ---
echo "[0/9] Cleaning the digital twin environment..."
sudo bash "$BASE_DIR/clean.sh"
echo "✅ Environment cleaned."
echo "-------------------------------------------------"

# --- Step 1: Run Twin Data Collector ---
echo "[1/9] Starting the twin data collector in the background..."
# sudo python3 "$BASE_DIR/twin_data_collector.py" &
echo "✅ Data collector is running."
echo "-------------------------------------------------"

# --- Step 2: Run Digital Twin Setup & Wait Intelligently ---
echo "[2/9] Starting modified digital twin setup in the background..."
sudo python3 "$BASE_DIR/modified.digital_twin_setup.py" --no-cli > "$BASE_DIR/digital_twin_setup.log" 2>&1 &

echo "⏳ Waiting for the network containers to be ready..."
WAIT_SECONDS=0
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
sudo bash "$BASE_DIR/install_tcpreplay_in_upfs.sh"
echo "✅ TCPreplay installation complete."
echo "-------------------------------------------------"

# --- Step 4: Fix ONLY prometheus target port for amarisoft + Start Prometheus ---
echo "[4/9] Starting Prometheus monitoring server..."

if [ -f "$PROMETHEUS_YML" ]; then
  # Backup once per run
  sudo cp -f "$PROMETHEUS_YML" "$PROMETHEUS_YML.bak" >/dev/null 2>&1 || true

  # Only modify inside the amarisoft job block: replace localhost:<port> or 127.0.0.1:<port> with 127.0.0.1:8001
  # (does NOT touch other jobs)
  sudo python3 - <<PY
from pathlib import Path
import re

p = Path("$PROMETHEUS_YML")
t = p.read_text()

m = re.search(r"(?ms)^- job_name:\s*['\\"]?amarisoft['\\"]?\s*\n.*?(?=^\s*- job_name:|\Z)", t)
if not m:
    # If job doesn't exist, do nothing (keep original file)
    print("ℹ️ No amarisoft job block found in prometheus.yml (no change).")
else:
    block = m.group(0)
    new_block = re.sub(r"\b(?:127\.0\.0\.1|localhost):\d+\b", "127.0.0.1:$SCRAPER_PORT", block)
    new_block = new_block.replace("127.0.0.1:800101", "127.0.0.1:$SCRAPER_PORT")
    t2 = t[:m.start()] + new_block + t[m.end():]
    p.write_text(t2)
    print("✅ Patched amarisoft target to 127.0.0.1:$SCRAPER_PORT (only inside amarisoft job).")
PY
fi

if [ -d "$PROMETHEUS_DIR" ]; then
    # Start Prometheus with logs
    ( cd "$PROMETHEUS_DIR" && sudo -E nohup ./prometheus --config.file=prometheus.yml > "$PROM_LOG" 2>&1 & )
    echo "✅ Prometheus is running in the background. (logs: $PROM_LOG)"
else
    echo "⚠️ Prometheus directory not found at $PROMETHEUS_DIR. Skipping."
fi
echo "-------------------------------------------------"

# --- Step 5: Start Grafana ---
echo "[5/9] Starting Grafana container..."
sudo docker run -d --name "$GRAFANA_NAME" -p ${GRAFANA_PORT}:3000 grafana/grafana >/dev/null
echo "✅ Grafana and Prometheus ready"
echo "-------------------------------------------------"

# --- Step 6: Run Combined Scraper ---
echo "[6/9] Starting the combined data scraper..."
sudo -E nohup python3 "$SCRAPER_PY" > "$SCRAPER_LOG" 2>&1 &
echo "✅ Scraper is running in the background. (logs: $SCRAPER_LOG)"
echo "-------------------------------------------------"

# --- Step 7: Skip Amarisoft Cleanup (LOCAL MODE) ---
echo "[7/9] Skipping Amarisoft cleanup (local PCAP mode)..."
echo "✅ Using local pcaps from: $BASE_DIR/physicaltwindata"
echo "-------------------------------------------------"

# --- Step 8: Skip Amarisoft Regeneration (LOCAL MODE) ---
echo "[8/9] Skipping Amarisoft traffic regeneration (local PCAP mode)..."
echo "✅ Traffic will be generated by tcpreplay from local files."
echo "-------------------------------------------------"

# --- Step 9: Start LOCAL PCAP Replay (Background) ---
echo "[9/9] Starting local PCAP replay on the digital twin (background)..."

sudo -E nohup python3 "$REPLAY_PY" >> "$REPLAY_LOG" 2>&1 &
REPLAY_PID=$!
echo "$REPLAY_PID" | sudo tee /tmp/pcap_replay.pid >/dev/null

echo "✅ PCAP replay started. PID=$REPLAY_PID"
echo "   Logs: tail -f $REPLAY_LOG"
echo "-------------------------------------------------"

echo "🎉 Automation script finished successfully!"
echo "================================================="

echo
echo "Useful checks:"
echo "  - Prometheus targets:  http://127.0.0.1:${PROM_PORT}/targets"
echo "  - Scraper metrics:     curl -sSf http://127.0.0.1:${SCRAPER_PORT}/metrics | head"
echo "  - Prometheus log:      tail -f $PROM_LOG"
echo "  - Scraper log:         tail -f $SCRAPER_LOG"
echo "  - Replay log:          tail -f $REPLAY_LOG"
