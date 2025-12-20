#!/bin/bash

set -e

# Step 1: Setup node_exporter in each UPF container
declare -A upf_ports=(
  [upf_default]=9100
  [upf_internet]=9100
  [upf_ims]=9100
  [upf_sos]=9100
)

echo "🔧 Installing and launching node_exporter in UPF containers..."
for upf in "${!upf_ports[@]}"; do
  port="${upf_ports[$upf]}"
  echo "▶ $upf on port $port"

  docker exec -i "$upf" bash -c "
    apt update &&
    apt install -y curl tar &&
    VER='1.9.1' &&
    curl -L -o /tmp/node_exporter.tar.gz https://github.com/prometheus/node_exporter/releases/download/v\${VER}/node_exporter-\${VER}.linux-arm64.tar.gz &&
    tar -C /tmp -xzf /tmp/node_exporter.tar.gz &&
    mv /tmp/node_exporter-\${VER}.linux-arm64/node_exporter /usr/local/bin/node_exporter &&
    chmod +x /usr/local/bin/node_exporter &&
    nohup /usr/local/bin/node_exporter --web.listen-address=\":$port\" >/dev/null 2>&1 &
  "
  echo "✅ $upf running node_exporter"
done

# Step 2: Start cAdvisor if not already running
if ! docker ps | grep -q cadvisor; then
  echo "🚀 Starting cAdvisor..."
  docker run \
    --volume=/:/rootfs:ro \
    --volume=/var/run:/var/run:ro \
    --volume=/sys:/sys:ro \
    --volume=/var/lib/docker/:/var/lib/docker:ro \
    --publish=8080:8080 \
    --detach=true \
    --name=cadvisor \
    gcr.io/cadvisor/cadvisor:latest
else
  echo "🔁 Restarting existing cAdvisor container..."
  docker restart cadvisor
fi

echo "✅ All monitoring services are deployed and running!"
