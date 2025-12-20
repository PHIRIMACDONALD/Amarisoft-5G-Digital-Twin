#!/bin/bash

# List of container names
containers=("upf_default" "upf_internet" "upf_ims" "upf_sos")

for c in "${containers[@]}"; do
    echo "Starting node_exporter in container: $c"
    docker exec -d $c /usr/local/bin/node_exporter --web.listen-address=":9100"
done

echo "Node Exporter started in all UPF containers on internal port 9100."

