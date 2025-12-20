#!/bin/bash

# List of container names
containers=("upf_default" "upf_internet" "upf_ims" "upf_sos")

# Node Exporter version and architecture
VER="1.8.1"
ARCH="arm64"

for c in "${containers[@]}"; do
    echo "→ Processing container: $c"

    echo "→ Checking if node_exporter exists in $c..."
    docker exec $c test -x /usr/local/bin/node_exporter

    if [ $? -ne 0 ]; then
        echo "→ Installing node_exporter in $c..."
        docker exec $c bash -c "
            apt update && apt install -y curl tar && \
            curl -L -o /tmp/node_exporter.tar.gz https://github.com/prometheus/node_exporter/releases/download/v${VER}/node_exporter-${VER}.linux-${ARCH}.tar.gz && \
            tar -C /tmp -xzf /tmp/node_exporter.tar.gz && \
            mv /tmp/node_exporter-${VER}.linux-${ARCH}/node_exporter /usr/local/bin/ && \
            chmod +x /usr/local/bin/node_exporter
        "
    else
        echo "→ node_exporter already installed in $c."
    fi

    echo "→ Starting node_exporter in $c..."
    docker exec -d $c /usr/local/bin/node_exporter --web.listen-address=":9100"
    echo "✔️  Done with $c"
done

echo "✅ Node Exporter installed and started in all UPF containers."
