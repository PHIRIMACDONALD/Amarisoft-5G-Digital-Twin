#!/bin/bash

declare -A upf_ports=(
  [upf_default]=9100
  [upf_internet]=9101
  [upf_ims]=9102
  [upf_sos]=9103
)

for upf in "${!upf_ports[@]}"; do
  port="${upf_ports[$upf]}"
  echo "▶ Setting up node_exporter in $upf on port $port..."
  
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
  
  echo "✅ $upf ready on port $port"
done
