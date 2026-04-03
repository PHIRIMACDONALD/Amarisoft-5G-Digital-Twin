# Automated Amarisoft 5G Digital Twin

**Author:** Macdonald PHIRI
**Supervisor:** Prof. Fabrizio Granelli - DISI, University of Trento
**Project:** Progettazione e sviluppo di Network Digital Twin
**Funding:** PNRR SPRINT - CUP E83C22004640001
**Platform:** MacBook Air M4, macOS Tahoe 26.2 - Multipass Ubuntu 20.04

## Quick Start

bash ./run_experiment1.sh

## What This Does

Fully automated 5G Digital Twin built on ComNetsEmu.
One command starts everything in 8-12 minutes:
- Open5GS 5G Core (AMF, SMF, UPF, NRF)
- UERANSIM RAN (gNB + UE)
- Network Slicing (eMBB, URLLC, mMTC)
- Amarisoft Digital Twin integration
- PCAP traffic capture and replay
- Prometheus + Grafana monitoring
- Flask web controller at port 5000

## Access

Grafana:    http://VM_IP:3000  (admin/admin)
Prometheus: http://VM_IP:9090
Controller: http://VM_IP:5000

## Contact

Macdonald PHIRI - phiriygt1@gmail.com
Supervised by Prof. Fabrizio Granelli - fabrizio.granelli@unitn.it
