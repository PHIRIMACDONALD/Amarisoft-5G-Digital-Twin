#!/bin/bash

# List of UPF containers
containers=("upf_default" "upf_internet" "upf_ims" "upf_sos")

# Node Exporter version
VER="1.8.1"

for c in "${containers[@]}"; do
    echo "🛠️  Installing node_exporter in container: $c"
    
    docker exec $c bash -c "
        apt update && apt install -y curl tar && \
        VER=${VER} && \
        curl -L -o /tmp/node_exporter.tar.gz \"https://github.com/prometheus/node_exporter/releases/download/v\${VER}/node_exporter-\${VER}.linux-arm64.tar.gz\" && \
        tar -C /tmp -xzf /tmp/node_exporter.tar.gz && \
        mv /tmp/node_exporter-\${VER}.linux-arm64/node_exporter /usr/local/bin/node_exporter && \
        chmod +x /usr/local/bin/node_exporter && \
        /usr/local/bin/node_exporter --web.listen-address=\":9100\"
    "

    echo "✅ Finished setting up $c"
done

echo "✅✅ All UPF containers now have node_exporter installed and running on port 9100."
