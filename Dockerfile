# Start from your existing image
FROM my5gc_v2-4-4

# Install wget + node_exporter
RUN apt-get update && apt-get install -y wget tar && \
    wget https://github.com/prometheus/node_exporter/releases/download/v1.8.1/node_exporter-1.8.1.linux-amd64.tar.gz && \
    tar -xzf node_exporter-1.8.1.linux-amd64.tar.gz && \
    mv node_exporter-1.8.1.linux-amd64/node_exporter /usr/local/bin/ && \
    rm -rf node_exporter-1.8.1.linux-amd64* && \
    apt-get clean

# By default, run UPF and Node Exporter together
CMD /open5gs/install/bin/open5gs-upfd & \
    /usr/local/bin/node_exporter --web.listen-address=":9100"
