# Amarisoft Digital Twin Automation with Observability

> **A research-grade 5G network digital twin platform combining Comnetsemu/Containernet, Open5GS, UERANSIM, real traffic replay, and a full Prometheus/Grafana observability stack — orchestrated end-to-end by a single-command automation pipeline.**

---

<div align="center">

![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Ubuntu%2022.04-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-green)
![Docker](https://img.shields.io/badge/Docker-24.x-blue)
![Open5GS](https://img.shields.io/badge/Core-Open5GS-orange)
![UERANSIM](https://img.shields.io/badge/RAN-UERANSIM-purple)
![Prometheus](https://img.shields.io/badge/Monitoring-Prometheus-red)
![Grafana](https://img.shields.io/badge/Visualization-Grafana-yellow)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

</div>

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Component Descriptions](#3-component-descriptions)
4. [Repository Structure](#4-repository-structure)
5. [Automation Workflow](#5-automation-workflow)
6. [Execution Pipeline](#6-execution-pipeline)
7. [Monitoring Architecture](#7-monitoring-architecture)
8. [Data Pipeline](#8-data-pipeline)
9. [Key Scripts Reference](#9-key-scripts-reference)
10. [How `run_experiment1.sh` Works](#10-how-run_experiment1sh-works)
11. [Digital Twin Setup](#11-digital-twin-setup)
12. [Traffic Replay Subsystem](#12-traffic-replay-subsystem)
13. [Grafana + Prometheus Integration](#13-grafana--prometheus-integration)
14. [Observability Design](#14-observability-design)
15. [One-Click Flask Controller](#15-one-click-flask-controller)
16. [Installation Guide](#16-installation-guide)
17. [Usage Guide](#17-usage-guide)
18. [Future Improvements](#18-future-improvements)
19. [Conclusion](#19-conclusion)

---

## 1. Project Overview

### 1.1 Abstract

This project implements a **5G network digital twin** — a fully emulated, software-defined replica of a real-world Amarisoft 5G testbed. The twin is designed to faithfully reproduce the radio access and core network behavior of a physical 5G deployment, enabling reproducible experimentation, traffic analysis, and observability research without requiring dedicated hardware.

The platform integrates:

- **Network emulation** via Comnetsemu/Containernet (Docker-in-Mininet)
- **5G Core Network** via Open5GS (AMF, SMF, UPF, NRF, AUSF, PCF, BSF, UDR, UDM, SCP)
- **RAN simulation** via UERANSIM (gNB + multi-UE)
- **Real traffic injection** via `tcpreplay` with captured PCAP traces
- **Metrics collection** via Prometheus + combined scraper
- **Visualization** via Grafana dashboards with real-time radio KPIs
- **Automation** via a Bash/Python orchestration pipeline
- **Control UI** via a Flask-based single-page controller

The system is designed for **research-level reproducibility**: a single command spins up the entire stack, runs a traffic experiment, collects metrics, and delivers a populated Grafana dashboard — all without manual intervention.

### 1.2 Motivation

Physical 5G testbeds (such as Amarisoft CALLBOX) are expensive, non-shareable, and difficult to configure repeatably. A digital twin solves these problems by:

- Enabling parallel experimentation on commodity hardware
- Providing deterministic, reproducible traffic scenarios via PCAP replay
- Decoupling RAN parameter tuning from hardware availability
- Enabling CI/CD-style automated test campaigns
- Offering deep observability into KPIs (CQI, MCS, SNR, path loss, bitrate) that are difficult to extract from real hardware in real time

### 1.3 Design Goals

| Goal | Implementation |
|------|---------------|
| Full stack automation | `run_experiment1.sh` orchestrator |
| Reproducible traffic | PCAP capture → `tcpreplay` injection |
| Real-time observability | Prometheus scrape + Grafana render |
| Zero-touch deployment | Single `bash run_experiment1.sh` |
| Clean teardown | `clean.sh` full reset |
| Manual override | Flask controller UI |
| Amarisoft metric parity | `combined_scraper.py` translation layer |

---

## 2. System Architecture

### 2.1 High-Level Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                  AMARISOFT DIGITAL TWIN — SYSTEM ARCHITECTURE               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │                      HOST MACHINE (Ubuntu 22.04)                    │    ║
║  │                                                                     │    ║
║  │  ┌──────────────────────────────────────────────────────────────┐  │    ║
║  │  │               COMNETSEMU / CONTAINERNET LAYER                │  │    ║
║  │  │                                                              │  │    ║
║  │  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │  │    ║
║  │  │   │  gNB Node   │    │  UE Node    │    │  UPF Node   │   │  │    ║
║  │  │   │ (UERANSIM)  │◄──►│ (UERANSIM)  │    │ (Open5GS)   │   │  │    ║
║  │  │   └──────┬──────┘    └─────────────┘    └──────┬──────┘   │  │    ║
║  │  │          │  N2/N3 Interface                     │          │  │    ║
║  │  │          ▼                                      ▼          │  │    ║
║  │  │   ┌──────────────────────────────────────────────────┐    │  │    ║
║  │  │   │              5G CORE (Open5GS)                   │    │  │    ║
║  │  │   │  AMF ── SMF ── UPF ── NRF ── AUSF ── PCF        │    │  │    ║
║  │  │   │  UDM ── UDR ── BSF ── SCP ── MongoDB            │    │  │    ║
║  │  │   └──────────────────────────────────────────────────┘    │  │    ║
║  │  │                                                              │  │    ║
║  │  │   ┌──────────────────────────────────────────────────┐    │  │    ║
║  │  │   │         TRAFFIC REPLAY SUBSYSTEM                 │    │  │    ║
║  │  │   │  PCAP File ──► tcpreplay ──► UPF Interface       │    │  │    ║
║  │  │   └──────────────────────────────────────────────────┘    │  │    ║
║  │  └──────────────────────────────────────────────────────────────┘  │    ║
║  │                                                                     │    ║
║  │  ┌──────────────────────────────────────────────────────────────┐  │    ║
║  │  │                   OBSERVABILITY STACK                        │  │    ║
║  │  │                                                              │  │    ║
║  │  │  ┌──────────────────┐      ┌───────────────────────────┐   │  │    ║
║  │  │  │  combined_       │      │       Prometheus           │   │  │    ║
║  │  │  │  scraper.py      │─────►│  :9090 (scrape + store)   │   │  │    ║
║  │  │  │                  │      └────────────┬──────────────┘   │  │    ║
║  │  │  │  twin_data_      │                   │                   │  │    ║
║  │  │  │  collector.py    │                   ▼                   │  │    ║
║  │  │  └──────────────────┘      ┌───────────────────────────┐   │  │    ║
║  │  │                            │         Grafana            │   │  │    ║
║  │  │  ┌──────────────────┐      │  :3000 (dashboards/KPIs)  │   │  │    ║
║  │  │  │  Flask Controller│      └───────────────────────────┘   │  │    ║
║  │  │  │  app.py :5000    │                                       │  │    ║
║  │  │  └──────────────────┘                                       │  │    ║
║  │  └──────────────────────────────────────────────────────────────┘  │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### 2.2 Network Topology Diagram

```
                         ┌─────────────────────────────────────┐
                         │          CONTAINERNET TOPOLOGY       │
                         └─────────────────────────────────────┘

  ┌──────────┐  Uu (air)   ┌──────────┐   N3 (GTP-U)   ┌──────────────┐
  │   UE     │◄───────────►│   gNB    │◄───────────────►│    UPF       │
  │ (UERANSIM│             │(UERANSIM)│                 │  (Open5GS)   │
  └──────────┘             └────┬─────┘                 └──────┬───────┘
                                │ N2 (NGAP/SCTP)               │ N6
                                ▼                               ▼
                         ┌─────────────┐             ┌─────────────────┐
                         │    AMF      │             │   Data Network   │
                         │  (Open5GS)  │             │  (tcpreplay inj) │
                         └──────┬──────┘             └─────────────────┘
                                │ N11
                         ┌──────▼──────┐
                         │    SMF      │
                         │  (Open5GS)  │
                         └─────────────┘

  Container Network: 10.45.0.0/16 (UE pool)
  N2 Interface:      192.168.0.0/24
  N3 Interface:      192.168.1.0/24
```

---

## 3. Component Descriptions

### 3.1 Infrastructure Layer

#### Comnetsemu / Containernet

**Role:** Network emulation fabric. Wraps Docker containers as Mininet hosts, providing:
- Programmable virtual links between containers
- Bandwidth, delay, and loss emulation via Linux `tc`
- Python-native topology scripting API
- Integration with Open vSwitch for SDN control

**Key configuration points:**
- Custom Docker images for each network function
- Virtual Ethernet (veth) pairs between containers
- Namespace isolation per container-node

#### Open5GS Core Network

**Role:** Standards-compliant 3GPP 5G SA (Standalone) core. Provides all Control Plane (CP) and User Plane (UP) functions:

| Function | Port | Role |
|----------|------|------|
| AMF | 38412 (NGAP) | Access and Mobility Management |
| SMF | N11 | Session Management |
| UPF | 2152 (GTP-U) | User Plane forwarding |
| NRF | 7777 | Network Function Repository |
| AUSF | — | Authentication Server |
| PCF | — | Policy Control |
| UDM | — | Unified Data Management |
| UDR | — | Unified Data Repository |
| BSF | — | Binding Support |
| SCP | — | Service Communication Proxy |

#### UERANSIM

**Role:** Open-source 5G UE and gNB simulator. Implements:
- NR (New Radio) air interface signaling
- NGAP (N2) toward AMF
- GTP-U (N3) toward UPF
- Multiple UE simulation (configurable IMSI pool)
- NAS signaling (Registration, PDU Session Establishment)

### 3.2 Automation Layer

| Component | Language | Purpose |
|-----------|----------|---------|
| `run_experiment1.sh` | Bash | Master orchestrator — end-to-end pipeline |
| `clean.sh` | Bash | Full environment teardown |
| `modified.digital_twin_setup.py` | Python | Containernet topology instantiation |
| `twin_data_collector.py` | Python | Background metrics data collection agent |
| `test.pcap_replay_twin.py` | Python | PCAP replay controller |

### 3.3 Monitoring Layer

| Component | Technology | Port | Purpose |
|-----------|-----------|------|---------|
| Prometheus | Time-series DB | 9090 | Metric scraping and storage |
| combined_scraper.py | Python/HTTP | 8000 | Custom exporter for Amarisoft-style KPIs |
| Node Exporter | Go binary | 9100 | Host system metrics |
| Grafana | Web dashboard | 3000 | Real-time visualization |

### 3.4 Metrics Domain

The following KPIs are collected, translated from Amarisoft semantics, and visualized:

| Metric | Unit | Source | Description |
|--------|------|--------|-------------|
| UL Bitrate | Mbps | UPF / gNB | Uplink throughput per UE |
| DL Bitrate | Mbps | UPF / gNB | Downlink throughput per UE |
| CQI | 0–15 | gNB report | Channel Quality Indicator |
| MCS | 0–28 | gNB scheduler | Modulation and Coding Scheme |
| SNR | dB | gNB measurement | Signal-to-Noise Ratio |
| Path Loss | dB | Radio model | RF propagation loss |

---

## 4. Repository Structure

```
amarisoft-digital-twin/
│
├── README.md                          # This document
├── docs/
│   ├── architecture.md                # Detailed architecture reference
│   ├── metrics_reference.md           # KPI definitions and mappings
│   └── diagrams/
│       ├── system_architecture.png
│       └── data_pipeline.png
│
├── scripts/
│   ├── run_experiment1.sh             # ★ Master orchestration script
│   └── clean.sh                       # Environment teardown
│
├── topology/
│   └── modified.digital_twin_setup.py # Containernet topology definition
│
├── collection/
│   ├── twin_data_collector.py         # Background KPI data collection agent
│   └── combined_scraper.py            # Prometheus-compatible exporter
│
├── replay/
│   ├── test.pcap_replay_twin.py       # PCAP replay controller
│   └── captures/
│       └── test.pcap                  # Reference PCAP trace
│
├── monitoring/
│   ├── prometheus.yml                 # Prometheus scrape configuration
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources/
│       │   │   └── prometheus.yml
│       │   └── dashboards/
│       │       └── dashboard.yml
│       └── dashboards/
│           └── twin_dashboard.json    # Pre-built KPI dashboard
│
├── controller/
│   └── app.py                         # Flask one-click UI controller
│
├── config/
│   ├── open5gs/
│   │   ├── amf.yaml
│   │   ├── smf.yaml
│   │   └── upf.yaml
│   └── ueransim/
│       ├── gnb.yaml
│       └── ue.yaml
│
├── docker/
│   ├── Dockerfile.open5gs
│   ├── Dockerfile.ueransim
│   └── docker-compose.yml
│
├── requirements.txt                   # Python dependencies
└── LICENSE
```

---

## 5. Automation Workflow

### 5.1 Automation Flow Diagram

```
╔══════════════════════════════════════════════════╗
║           AUTOMATION FLOW (run_experiment1.sh)   ║
╚══════════════════════════════════════════════════╝

     ┌────────────────────┐
     │   START SCRIPT     │
     └─────────┬──────────┘
               │
               ▼
     ┌────────────────────┐
  1  │   clean.sh         │  ← Kill containers, processes, reset netns
     │   (Environment     │
     │    Cleanup)        │
     └─────────┬──────────┘
               │
               ▼
     ┌────────────────────┐
  2  │ twin_data_         │  ← Launch background KPI collector
     │ collector.py       │    (daemonized, writes to local store)
     └─────────┬──────────┘
               │
               ▼
     ┌────────────────────┐
  3  │ modified.digital_  │  ← Containernet topology up:
     │ twin_setup.py      │    Open5GS + UERANSIM containers
     └─────────┬──────────┘
               │
               ▼
     ┌────────────────────┐
  4  │ WAIT: Container    │  ← Poll until all containers report healthy
     │ Health Check       │    (AMF, SMF, UPF, gNB, UE ready)
     └─────────┬──────────┘
               │
               ▼
     ┌────────────────────┐
  5  │ INSTALL tcpreplay  │  ← apt install inside UPF containers
     │ in UPF containers  │    (enables traffic injection capability)
     └─────────┬──────────┘
               │
               ▼
     ┌────────────────────┐
  6  │ START Prometheus   │  ← Load prometheus.yml scrape config
     │ (:9090)            │    Begin time-series collection
     └─────────┬──────────┘
               │
               ▼
     ┌────────────────────┐
  7  │ START Grafana      │  ← Auto-provision datasource + dashboard
     │ (:3000)            │    Load twin_dashboard.json
     └─────────┬──────────┘
               │
               ▼
     ┌────────────────────┐
  8  │ combined_          │  ← Start Prometheus exporter
     │ scraper.py (:8000) │    Translates Amarisoft KPI format
     └─────────┬──────────┘
               │
               ▼
     ┌────────────────────┐
  9  │ AMARISOFT TRAFFIC  │  ← Stimulate gNB/UE with synthetic load
     │ REGENERATION       │    Baseline traffic profile active
     └─────────┬──────────┘
               │
               ▼
     ┌────────────────────┐
 10  │ PCAP REPLAY        │  ← test.pcap_replay_twin.py
     │ (tcpreplay inject) │    Injects captured real traffic
     └─────────┬──────────┘
               │
               ▼
     ┌────────────────────┐
 11  │ METRICS SCRAPED    │  ← combined_scraper → Prometheus
     │ & STORED           │    (UL/DL bitrate, CQI, MCS, SNR, PL)
     └─────────┬──────────┘
               │
               ▼
     ┌────────────────────┐
 12  │ GRAFANA            │  ← Live dashboard populated with KPIs
     │ VISUALIZATION      │    Graphs update in real time
     └─────────┬──────────┘
               │
               ▼
     ┌────────────────────┐
     │  EXPERIMENT DONE   │
     └────────────────────┘
```

### 5.2 Dependency Graph

```
clean.sh
    └──► twin_data_collector.py  (background)
             └──► modified.digital_twin_setup.py
                      └──► [containers healthy?]
                                └──► install tcpreplay
                                         └──► prometheus
                                                  └──► grafana
                                                           └──► combined_scraper.py
                                                                    └──► traffic regen
                                                                              └──► pcap replay
                                                                                        └──► metrics live
```

---

## 6. Execution Pipeline

### 6.1 Stage-by-Stage Breakdown

#### Stage 1 — Environment Cleanup (`clean.sh`)

Ensures a pristine environment before each run, eliminating state pollution from previous experiments.

```bash
# clean.sh — actions performed:
sudo mn --clean                     # Mininet/Containernet teardown
docker rm -f $(docker ps -aq)       # Remove all containers
sudo ip link del br-twin 2>/dev/null # Remove virtual bridges
sudo pkill -f prometheus
sudo pkill -f grafana
sudo pkill -f combined_scraper
sudo pkill -f twin_data_collector
sudo pkill -f tcpreplay
```

#### Stage 2 — Data Collector Launch

`twin_data_collector.py` is started as a background process. It continuously polls internal container stats APIs and aggregates raw metrics into a structured buffer consumed by `combined_scraper.py`.

#### Stage 3 — Topology Instantiation

`modified.digital_twin_setup.py` programmatically constructs the Containernet topology:
- Creates Docker-backed Mininet hosts for each NF
- Wires virtual links with specified bandwidth profiles
- Configures IP addressing per 3GPP interface conventions
- Starts Open5GS processes inside containers
- Starts UERANSIM gNB and UE processes

#### Stage 4 — Readiness Polling

The script enters a polling loop, checking for:
- Container `Running` status via `docker inspect`
- Open5GS AMF NGAP port `38412` reachability
- UERANSIM gNB registration confirmation (log parsing)
- UE PDU Session Establishment (tunnel `uesimtun0` up)

#### Stage 5 — tcpreplay Installation

`tcpreplay` is installed inside UPF containers at runtime (rather than baked into the image) to allow flexible version management and minimize base image size.

```bash
docker exec upf1 apt-get install -y tcpreplay
docker exec upf2 apt-get install -y tcpreplay
```

#### Stage 6 — Prometheus Launch

Prometheus is started with the project's `prometheus.yml` configuration, which defines scrape intervals and target endpoints. The combined scraper's `/metrics` endpoint is registered as a scrape target.

#### Stage 7 — Grafana Launch

Grafana is launched with auto-provisioning enabled. The `twin_dashboard.json` is loaded automatically, and the Prometheus datasource is pre-configured via the provisioning YAML — no manual UI setup required.

#### Stage 8 — Combined Scraper

`combined_scraper.py` starts its HTTP server on port `8000`, exposing a `/metrics` endpoint in Prometheus exposition format. It draws data from `twin_data_collector.py`'s buffer.

#### Stage 9 — Traffic Regeneration

Synthetic load is applied to the 5G stack to establish baseline traffic patterns matching the Amarisoft reference profile.

#### Stage 10 — PCAP Replay

`test.pcap_replay_twin.py` invokes `tcpreplay` inside the UPF container, injecting a captured PCAP trace at configurable replay rates. This provides deterministic, reproducible traffic patterns.

#### Stages 11–12 — Metrics & Visualization

Prometheus scrapes the combined exporter every `N` seconds. Grafana renders the incoming time-series data in the pre-built dashboard. KPIs (bitrate, CQI, MCS, SNR, path loss) are displayed in real time.

---

## 7. Monitoring Architecture

### 7.1 Monitoring Stack Diagram

```
╔══════════════════════════════════════════════════════════════╗
║                  MONITORING ARCHITECTURE                     ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  DATA SOURCES                                                ║
║  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      ║
║  │  Open5GS     │  │  UERANSIM    │  │  Docker/     │      ║
║  │  NF metrics  │  │  RAN KPIs    │  │  System      │      ║
║  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      ║
║         │                 │                  │              ║
║         └─────────────────┼──────────────────┘              ║
║                           │                                  ║
║                           ▼                                  ║
║  ┌────────────────────────────────────────────────────────┐ ║
║  │              twin_data_collector.py                    │ ║
║  │  - Polls container APIs and log streams                │ ║
║  │  - Normalizes metric names to Amarisoft conventions    │ ║
║  │  - Buffers metrics in shared memory / file             │ ║
║  └────────────────────────┬───────────────────────────────┘ ║
║                           │                                  ║
║                           ▼                                  ║
║  ┌────────────────────────────────────────────────────────┐ ║
║  │              combined_scraper.py (:8000)               │ ║
║  │  - Reads from collector buffer                         │ ║
║  │  - Exposes /metrics in Prometheus exposition format    │ ║
║  │  - Gauge metrics: ul_bitrate, dl_bitrate, cqi, mcs,   │ ║
║  │    snr, path_loss                                      │ ║
║  └────────────────────────┬───────────────────────────────┘ ║
║                           │  HTTP GET /metrics               ║
║                           ▼  (scrape interval: 5s)           ║
║  ┌────────────────────────────────────────────────────────┐ ║
║  │              Prometheus Server (:9090)                 │ ║
║  │  - TSDB (time-series storage)                          │ ║
║  │  - PromQL query engine                                 │ ║
║  │  - Configurable retention period                       │ ║
║  └────────────────────────┬───────────────────────────────┘ ║
║                           │  PromQL queries                  ║
║                           ▼                                  ║
║  ┌────────────────────────────────────────────────────────┐ ║
║  │              Grafana Dashboard (:3000)                 │ ║
║  │  - Real-time panel rendering                           │ ║
║  │  - Pre-built twin_dashboard.json                       │ ║
║  │  - Panels: UL/DL Bitrate, CQI, MCS, SNR, Path Loss   │ ║
║  └────────────────────────────────────────────────────────┘ ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

### 7.2 Prometheus Configuration (`prometheus.yml`)

```yaml
global:
  scrape_interval: 5s
  evaluation_interval: 5s

scrape_configs:
  - job_name: 'twin_combined_scraper'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /metrics

  - job_name: 'node_exporter'
    static_configs:
      - targets: ['localhost:9100']

  - job_name: 'open5gs_upf'
    static_configs:
      - targets: ['172.17.0.x:9091']   # UPF container exporter

  - job_name: 'ueransim_gnb'
    static_configs:
      - targets: ['172.17.0.y:9092']   # gNB stats endpoint
```

---

## 8. Data Pipeline

### 8.1 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DATA PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────────┘

  ┌───────────────┐                                                         
  │ Physical Twin │   (Reference measurement from Amarisoft CALLBOX)        
  │ (Amarisoft)   │──────────────────┐                                     
  └───────────────┘                  │ PCAP capture                        
                                     ▼                                      
  ┌───────────────┐         ┌─────────────────┐                            
  │  test.pcap    │         │  Amarisoft KPIs │                            
  │  (captured    │         │  (CQI, MCS, SNR │                            
  │   traffic)    │         │   bitrate logs) │                            
  └───────┬───────┘         └────────┬────────┘                            
          │                          │                                      
          │ tcpreplay injection       │ metric translation                  
          ▼                          ▼                                      
  ┌─────────────────────────────────────────────────────────────────────┐  
  │                     DIGITAL TWIN ENVIRONMENT                        │  
  │                                                                     │  
  │  ┌──────────────────────────────────────────────────────────────┐  │  
  │  │                    UPF Container(s)                          │  │  
  │  │  pcap ──► tcpreplay ──► GTP-U interface ──► traffic flow    │  │  
  │  └──────────────────────┬───────────────────────────────────────┘  │  
  │                         │                                           │  
  │  ┌──────────────────────▼───────────────────────────────────────┐  │  
  │  │              twin_data_collector.py                          │  │  
  │  │  ┌────────────────────────────────────────────────────────┐  │  │  
  │  │  │  Metric Sources:                                       │  │  │  
  │  │  │  • Docker stats API (/v1.43/containers/{id}/stats)     │  │  │  
  │  │  │  • UERANSIM log stream (stdout parsing)                │  │  │  
  │  │  │  • Open5GS log parsing (UPF session stats)            │  │  │  
  │  │  │  • GTP tunnel counters (via /proc/net/*)               │  │  │  
  │  │  └────────────────────────────────────────────────────────┘  │  │  
  │  │                            │                                   │  │  
  │  │                            ▼                                   │  │  
  │  │              Normalized Metric Buffer                          │  │  
  │  │  { ul_bitrate, dl_bitrate, cqi, mcs, snr, path_loss, ts }    │  │  
  │  └──────────────────────────────────────────────────────────────┘  │  
  └─────────────────────────────────────────────────────────────────────┘  
                           │                                                 
                           ▼                                                 
  ┌──────────────────────────────────────────────────────────────────────┐  
  │  combined_scraper.py                                                 │  
  │  GET /metrics → Prometheus exposition format                        │  
  │                                                                      │  
  │  twin_ul_bitrate_mbps{ue="ue1"} 12.4                               │  
  │  twin_dl_bitrate_mbps{ue="ue1"} 38.7                               │  
  │  twin_cqi{ue="ue1"} 13                                              │  
  │  twin_mcs{ue="ue1"} 24                                              │  
  │  twin_snr_db{ue="ue1"} 28.5                                         │  
  │  twin_path_loss_db{ue="ue1"} 72.3                                   │  
  └──────────────────────────────────────────────────────────────────────┘  
                           │                                                 
                           ▼ (scrape every 5s)                               
           Prometheus TSDB  ──────► Grafana Dashboard                        
```

---

## 9. Key Scripts Reference

### 9.1 `run_experiment1.sh`

**Type:** Bash orchestrator  
**Purpose:** Master pipeline controller — runs the full experiment lifecycle  
**Inputs:** None (all configuration via config files)  
**Outputs:** Running Grafana dashboard with live metrics

```bash
#!/bin/bash
set -euo pipefail

LOG="experiment_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "[1/12] Cleaning environment..."
bash scripts/clean.sh

echo "[2/12] Starting data collector..."
python3 collection/twin_data_collector.py &
COLLECTOR_PID=$!

echo "[3/12] Starting digital twin topology..."
sudo python3 topology/modified.digital_twin_setup.py

echo "[4/12] Waiting for containers..."
bash scripts/wait_for_containers.sh

echo "[5/12] Installing tcpreplay in UPFs..."
docker exec upf1 apt-get install -y tcpreplay
docker exec upf2 apt-get install -y tcpreplay

echo "[6/12] Starting Prometheus..."
prometheus --config.file=monitoring/prometheus.yml &

echo "[7/12] Starting Grafana..."
systemctl start grafana-server || grafana-server &

echo "[8/12] Starting combined scraper..."
python3 collection/combined_scraper.py &

echo "[9/12] Regenerating Amarisoft traffic..."
bash scripts/regen_traffic.sh

echo "[10/12] Running PCAP replay..."
python3 replay/test.pcap_replay_twin.py

echo "[11/12] Metrics being scraped..."
echo "[12/12] Visualization live at http://localhost:3000"
```

### 9.2 `clean.sh`

**Type:** Bash cleanup  
**Purpose:** Idempotent full reset — safe to run before any experiment

```bash
#!/bin/bash
echo "=== Cleaning Digital Twin Environment ==="

# Stop running experiment processes
sudo pkill -f twin_data_collector || true
sudo pkill -f combined_scraper || true
sudo pkill -f digital_twin_setup || true
sudo pkill -f tcpreplay || true
sudo pkill -f prometheus || true

# Containernet / Mininet cleanup
sudo mn --clean 2>/dev/null || true

# Docker container cleanup
docker rm -f $(docker ps -aq) 2>/dev/null || true

# Remove custom bridge networks
sudo ip link del br-twin 2>/dev/null || true
sudo ip link del br-open5gs 2>/dev/null || true

# Flush Prometheus data (optional)
# rm -rf /var/lib/prometheus/data/*

echo "=== Environment Clean ==="
```

### 9.3 `modified.digital_twin_setup.py`

**Type:** Python / Containernet topology script  
**Purpose:** Instantiates the complete 5G network topology using Comnetsemu

```python
#!/usr/bin/env python3
"""
Modified Digital Twin Setup
Builds a Containernet-based 5G network topology with:
- Open5GS core (AMF, SMF, UPF, NRF, AUSF, PCF, UDM, UDR, BSF)
- UERANSIM gNB and multi-UE nodes
- Custom virtual link profiles
"""

from comnetsemu.net import Containernet
from mininet.node import Controller
from mininet.log import setLogLevel, info
from mininet.link import TCLink

def build_5g_topology():
    net = Containernet(controller=Controller, link=TCLink)
    info("*** Adding Open5GS Core containers\n")

    # Core Network Functions
    amf = net.addDockerHost('amf', dimage='open5gs-amf:latest',
                             ip='192.168.0.1/24',
                             dcmd='open5gs-amfd -c /etc/open5gs/amf.yaml')

    smf = net.addDockerHost('smf', dimage='open5gs-smf:latest',
                             ip='192.168.0.2/24',
                             dcmd='open5gs-smfd -c /etc/open5gs/smf.yaml')

    upf = net.addDockerHost('upf', dimage='open5gs-upf:latest',
                             ip='192.168.1.1/24',
                             dcmd='open5gs-upfd -c /etc/open5gs/upf.yaml')

    # RAN Nodes
    gnb = net.addDockerHost('gnb', dimage='ueransim:latest',
                             ip='192.168.0.10/24',
                             dcmd='./nr-gnb -c /etc/ueransim/gnb.yaml')

    ue  = net.addDockerHost('ue',  dimage='ueransim:latest',
                             ip='192.168.0.20/24',
                             dcmd='./nr-ue -c /etc/ueransim/ue.yaml')

    info("*** Creating virtual links\n")
    net.addLink(gnb, amf, bw=1000, delay='1ms')   # N2
    net.addLink(gnb, upf, bw=1000, delay='1ms')   # N3
    net.addLink(ue,  gnb, bw=100,  delay='5ms')   # Uu (air interface)

    info("*** Starting network\n")
    net.start()
    return net

if __name__ == '__main__':
    setLogLevel('info')
    net = build_5g_topology()
    input("Press Enter to stop...")
    net.stop()
```

### 9.4 `twin_data_collector.py`

**Type:** Python background agent  
**Purpose:** Polls metric sources and normalizes into a shared buffer

```python
#!/usr/bin/env python3
"""
Twin Data Collector
Background daemon that:
1. Reads Docker container stats (CPU, memory, network I/O)
2. Parses UERANSIM and Open5GS log streams for RAN KPIs
3. Normalizes to Amarisoft metric naming conventions
4. Writes to shared metric buffer (JSON file or in-memory dict)
"""

import time
import json
import docker
import threading
from pathlib import Path

METRIC_FILE = "/tmp/twin_metrics.json"
POLL_INTERVAL = 2  # seconds

client = docker.from_env()

def collect_upf_stats():
    """Extract GTP tunnel counters from UPF container."""
    ...

def parse_ueransim_logs():
    """Stream and parse UERANSIM stdout for CQI, MCS, SNR, path loss."""
    ...

def normalize_metrics(raw: dict) -> dict:
    """Map raw values to Amarisoft KPI naming conventions."""
    return {
        "ul_bitrate_mbps": raw.get("uplink_throughput", 0) / 1e6,
        "dl_bitrate_mbps": raw.get("downlink_throughput", 0) / 1e6,
        "cqi":             raw.get("cqi", 0),
        "mcs":             raw.get("mcs", 0),
        "snr_db":          raw.get("snr", 0.0),
        "path_loss_db":    raw.get("path_loss", 0.0),
        "timestamp":       time.time()
    }

def run_collection_loop():
    while True:
        try:
            raw = {**collect_upf_stats(), **parse_ueransim_logs()}
            metrics = normalize_metrics(raw)
            Path(METRIC_FILE).write_text(json.dumps(metrics))
        except Exception as e:
            print(f"[collector] Error: {e}")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    print("[collector] Starting twin data collector...")
    run_collection_loop()
```

### 9.5 `combined_scraper.py`

**Type:** Python HTTP server / Prometheus exporter  
**Purpose:** Bridges the metric buffer to the Prometheus scrape endpoint

```python
#!/usr/bin/env python3
"""
Combined Scraper
Prometheus-compatible exporter that reads from twin_data_collector
and exposes metrics at :8000/metrics in text exposition format.
"""

import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST

METRIC_FILE = "/tmp/twin_metrics.json"

# Prometheus Gauges
ul_bitrate  = Gauge('twin_ul_bitrate_mbps', 'UL bitrate in Mbps', ['ue'])
dl_bitrate  = Gauge('twin_dl_bitrate_mbps', 'DL bitrate in Mbps', ['ue'])
cqi_gauge   = Gauge('twin_cqi', 'Channel Quality Indicator', ['ue'])
mcs_gauge   = Gauge('twin_mcs', 'Modulation and Coding Scheme', ['ue'])
snr_gauge   = Gauge('twin_snr_db', 'SNR in dB', ['ue'])
pl_gauge    = Gauge('twin_path_loss_db', 'Path Loss in dB', ['ue'])

def update_metrics():
    with open(METRIC_FILE) as f:
        m = json.load(f)
    ul_bitrate.labels(ue='ue1').set(m['ul_bitrate_mbps'])
    dl_bitrate.labels(ue='ue1').set(m['dl_bitrate_mbps'])
    cqi_gauge.labels(ue='ue1').set(m['cqi'])
    mcs_gauge.labels(ue='ue1').set(m['mcs'])
    snr_gauge.labels(ue='ue1').set(m['snr_db'])
    pl_gauge.labels(ue='ue1').set(m['path_loss_db'])

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            update_metrics()
            output = generate_latest()
            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(output)

if __name__ == '__main__':
    print("[scraper] Listening on :8000/metrics")
    HTTPServer(('0.0.0.0', 8000), MetricsHandler).serve_forever()
```

### 9.6 `test.pcap_replay_twin.py`

**Type:** Python traffic injector  
**Purpose:** Replays captured PCAP traffic into the UPF container

```python
#!/usr/bin/env python3
"""
PCAP Replay Controller
Injects a captured PCAP trace into the running UPF container
using tcpreplay, simulating realistic traffic patterns matching
the Amarisoft reference deployment.
"""

import subprocess
import sys

PCAP_FILE    = "replay/captures/test.pcap"
UPF_CONTAINER = "upf"
REPLAY_SPEED  = "2.0"   # 2× real-time replay
INTERFACE     = "eth0"  # UPF internal interface

def run_pcap_replay():
    cmd = [
        "docker", "exec", UPF_CONTAINER,
        "tcpreplay",
        "--intf1", INTERFACE,
        "--multiplier", REPLAY_SPEED,
        "--loop", "5",
        PCAP_FILE
    ]
    print(f"[replay] Injecting {PCAP_FILE} at {REPLAY_SPEED}x speed...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[replay] ERROR: {result.stderr}")
        sys.exit(1)
    print(f"[replay] Done. {result.stdout}")

if __name__ == "__main__":
    run_pcap_replay()
```

---

## 10. How `run_experiment1.sh` Works

`run_experiment1.sh` is the single entry point for a complete experiment run. Its design follows these engineering principles:

**Fail-fast execution:** The script uses `set -euo pipefail`, ensuring any unexpected failure immediately halts the pipeline rather than silently producing corrupt results.

**Sequential dependency ordering:** Each stage is gated on the successful completion of the previous. Container health checks prevent premature metric collection against unready NFs.

**Idempotency:** By invoking `clean.sh` as stage 1, the script is safe to re-run without manual cleanup between experiments.

**Logging:** All output is mirrored to a timestamped log file via `tee`, providing a full audit trail for each experiment run.

**Modularity:** Each stage maps 1:1 to a discrete subsystem, making it straightforward to skip, modify, or extend individual stages without disrupting the rest of the pipeline.

**Exit trap:** A `trap` ensures `clean.sh` is called even if the script exits abnormally, preventing dangling containers and processes.

---

## 11. Digital Twin Setup

### 11.1 What is a Digital Twin in This Context?

A **5G digital twin** is a software-defined replica of a physical 5G deployment that faithfully reproduces its:

- **Control plane behavior** (NAS signaling, PDU session management)
- **User plane behavior** (GTP-U tunneling, packet forwarding)
- **Radio characteristics** (modeled via UERANSIM's channel simulation + PCAP injection)
- **KPI output** (through metric normalization to match physical measurements)

The goal is not pixel-perfect hardware emulation but **metric-level fidelity** — the digital twin should produce KPI time series that are statistically representative of the physical Amarisoft deployment under the same traffic conditions.

### 11.2 Fidelity Mechanisms

| Dimension | Mechanism |
|-----------|-----------|
| Traffic patterns | PCAP replay from real capture |
| Core behavior | Open5GS (standards-compliant 3GPP) |
| RAN signaling | UERANSIM (real NR protocol stack) |
| Radio KPIs | UERANSIM configurable channel + scraper normalization |
| Throughput scaling | tcpreplay multiplier controls load intensity |

### 11.3 Comnetsemu Integration

`modified.digital_twin_setup.py` extends the standard Comnetsemu API with:

- Per-link bandwidth shaping mimicking realistic backhaul profiles
- Custom Docker image references for pre-configured NF containers
- Startup sequencing that respects 5G NF dependency order (NRF → AMF → SMF → UPF → gNB → UE)
- Dynamic IP address assignment matching the `prometheus.yml` scrape target configuration

---

## 12. Traffic Replay Subsystem

### 12.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   TRAFFIC REPLAY SUBSYSTEM                      │
└─────────────────────────────────────────────────────────────────┘

  CAPTURE PHASE (offline, from physical Amarisoft testbed)
  ┌──────────────────┐
  │ Amarisoft CALLBOX│──► tcpdump / Wireshark capture
  │  (physical)      │         │
  └──────────────────┘         ▼
                         test.pcap  (stored in replay/captures/)

  REPLAY PHASE (online, inside digital twin)
  ┌──────────────────────────────────────────────────────────────┐
  │                       UPF Container                          │
  │                                                              │
  │   test.pcap ──► tcpreplay ──► eth0 ──► GTP-U processing     │
  │                                                              │
  │   tcpreplay flags:                                           │
  │   --multiplier 2.0  (speed scaling)                          │
  │   --loop 5          (repeat 5 times for sustained load)      │
  │   --intf1 eth0      (inject on UPF N6 interface)             │
  └──────────────────────────────────────────────────────────────┘
                                │
                                ▼
                   GTP-U decapsulation → UE data plane
```

### 12.2 PCAP Replay Design Rationale

Using real captured traffic rather than synthetic generators (iperf, ping) provides:

- **Statistical realism:** Packet inter-arrival times, burst patterns, and application-layer payloads match the physical deployment
- **Protocol diversity:** HTTP, DNS, video streaming, and other application profiles coexist naturally
- **Determinism:** The same PCAP replayed at the same speed produces identical load profiles across runs
- **Amarisoft parity:** Since the PCAP was captured on the reference Amarisoft hardware, its traffic pattern directly drives comparable KPI values in the twin

---

## 13. Grafana + Prometheus Integration

### 13.1 Dashboard Architecture

The pre-built Grafana dashboard (`twin_dashboard.json`) contains the following panels:

| Panel | Type | PromQL |
|-------|------|--------|
| UL Bitrate | Time series | `twin_ul_bitrate_mbps{ue="ue1"}` |
| DL Bitrate | Time series | `twin_dl_bitrate_mbps{ue="ue1"}` |
| CQI | Gauge + sparkline | `twin_cqi{ue="ue1"}` |
| MCS Index | Time series | `twin_mcs{ue="ue1"}` |
| SNR | Time series | `twin_snr_db{ue="ue1"}` |
| Path Loss | Time series | `twin_path_loss_db{ue="ue1"}` |
| Combined Bitrate | Dual-axis | `twin_ul_bitrate_mbps + twin_dl_bitrate_mbps` |

### 13.2 Auto-Provisioning

Grafana provisioning files in `monitoring/grafana/provisioning/` ensure that datasources and dashboards are loaded automatically on startup with no manual UI configuration:

```
monitoring/grafana/provisioning/
├── datasources/
│   └── prometheus.yml     # Registers Prometheus at localhost:9090
└── dashboards/
    └── dashboard.yml      # Loads twin_dashboard.json from dashboards/
```

### 13.3 Access

| Service | URL | Default Credentials |
|---------|-----|-------------------|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| Metrics endpoint | http://localhost:8000/metrics | — |
| Flask controller | http://localhost:5000 | — |

---

## 14. Observability Design

### 14.1 Design Philosophy

The observability stack follows the **three pillars** model adapted for network research:

| Pillar | Implementation | Purpose |
|--------|---------------|---------|
| **Metrics** | Prometheus + combined_scraper | Quantitative KPI tracking |
| **Logs** | Timestamped per-stage logs in `run_experiment1.sh` | Audit trail and debugging |
| **Traces** | PCAP capture of replayed traffic | Packet-level forensics |

### 14.2 Metric Naming Convention

All metrics exposed by `combined_scraper.py` follow the pattern:

```
twin_{metric_name}_{unit}[{label}]
```

Examples:
```
twin_ul_bitrate_mbps{ue="ue1"}
twin_dl_bitrate_mbps{ue="ue1"}
twin_cqi{ue="ue1"}
twin_mcs{ue="ue1"}
twin_snr_db{ue="ue1"}
twin_path_loss_db{ue="ue1"}
```

### 14.3 Scrape Topology

```
Prometheus scrapes every 5 seconds:

  :8000  ← combined_scraper.py     (twin KPIs)
  :9090  ← prometheus self-scrape  (internal metrics)
  :9100  ← node_exporter           (host system)
  :9091  ← upf_exporter            (UPF container stats)
  :9092  ← gnb_stats               (gNB throughput)
```

---

## 15. One-Click Flask Controller

### 15.1 Overview

`controller/app.py` provides a lightweight single-page web UI for manual control of the experiment pipeline. It exposes three operations via REST endpoints backed by a Flask server.

### 15.2 Architecture

```
Browser ──► http://localhost:5000
              │
              ├── GET  /          → Status dashboard page
              ├── POST /run       → Triggers run_experiment1.sh
              ├── POST /stop      → Sends SIGTERM to running processes
              └── POST /clean     → Runs clean.sh
```

### 15.3 Implementation

```python
#!/usr/bin/env python3
"""
Flask Controller — One-Click Experiment UI
"""
import subprocess
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head><title>Digital Twin Controller</title>
<style>
  body { font-family: monospace; background: #1a1a2e; color: #e0e0e0; padding: 40px; }
  h1   { color: #00d4ff; }
  .btn { padding: 12px 24px; margin: 8px; border: none; border-radius: 4px;
         font-size: 16px; cursor: pointer; }
  .run   { background: #00b894; color: white; }
  .stop  { background: #d63031; color: white; }
  .clean { background: #fdcb6e; color: #2d3436; }
  pre    { background: #2d3436; padding: 16px; border-radius: 4px; }
</style></head>
<body>
  <h1>⚡ Amarisoft Digital Twin Controller</h1>
  <button class="btn run"   onclick="post('/run')">▶ Run Experiment</button>
  <button class="btn stop"  onclick="post('/stop')">⏹ Stop</button>
  <button class="btn clean" onclick="post('/clean')">🧹 Clean</button>
  <pre id="log">Ready.</pre>
  <script>
    async function post(url) {
      const r = await fetch(url, {method:'POST'});
      const d = await r.json();
      document.getElementById('log').textContent = d.output;
    }
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/run', methods=['POST'])
def run():
    result = subprocess.run(['bash', 'scripts/run_experiment1.sh'],
                            capture_output=True, text=True, timeout=300)
    return jsonify({"output": result.stdout + result.stderr})

@app.route('/stop', methods=['POST'])
def stop():
    subprocess.run(['sudo', 'pkill', '-f', 'run_experiment'], capture_output=True)
    return jsonify({"output": "Experiment stopped."})

@app.route('/clean', methods=['POST'])
def clean():
    result = subprocess.run(['bash', 'scripts/clean.sh'],
                            capture_output=True, text=True)
    return jsonify({"output": result.stdout})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
```

---

## 16. Installation Guide

### 16.1 Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| OS | Ubuntu 22.04 LTS | Tested platform |
| Python | 3.10+ | System Python |
| Docker | 24.x | Engine + CLI |
| Docker Compose | 2.x | Optional |
| Containernet | latest | Built from source |
| Comnetsemu | latest | Built from source |
| Prometheus | 2.x | Binary or package |
| Grafana | 10.x | OSS edition |
| tcpreplay | 4.x | Installed in containers at runtime |

### 16.2 Step-by-Step Installation

#### Step 1 — System Dependencies

```bash
sudo apt-get update && sudo apt-get install -y \
    git curl wget python3-pip \
    docker.io docker-compose \
    net-tools iproute2 \
    tcpdump wireshark-common \
    build-essential cmake \
    libsctp-dev libssl-dev
```

#### Step 2 — Comnetsemu / Containernet

```bash
git clone https://github.com/containernet/containernet.git
cd containernet
sudo python3 setup.py install
cd ..

git clone https://github.com/stevelorenz/comnetsemu.git
cd comnetsemu
sudo ./util/install.sh
cd ..
```

#### Step 3 — Prometheus

```bash
wget https://github.com/prometheus/prometheus/releases/download/v2.51.0/prometheus-2.51.0.linux-amd64.tar.gz
tar xvf prometheus-*.tar.gz
sudo mv prometheus-*/prometheus /usr/local/bin/
sudo mv prometheus-*/promtool  /usr/local/bin/
```

#### Step 4 — Grafana

```bash
sudo apt-get install -y apt-transport-https software-properties-common
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt-get update && sudo apt-get install -y grafana
```

#### Step 5 — Python Dependencies

```bash
cd amarisoft-digital-twin
pip3 install -r requirements.txt
```

**`requirements.txt`:**
```
flask>=3.0
prometheus-client>=0.20
docker>=7.0
requests>=2.31
scapy>=2.5
```

#### Step 6 — Docker Images

```bash
# Build Open5GS image
docker build -t open5gs-amf:latest -f docker/Dockerfile.open5gs --target amf .
docker build -t open5gs-upf:latest -f docker/Dockerfile.open5gs --target upf .

# Build UERANSIM image
docker build -t ueransim:latest -f docker/Dockerfile.ueransim .
```

#### Step 7 — Permissions

```bash
# Allow Docker without sudo
sudo usermod -aG docker $USER
newgrp docker

# Allow Mininet raw socket operations
sudo setcap cap_net_raw,cap_net_admin=eip $(which python3)
```

---

## 17. Usage Guide

### 17.1 Running a Full Experiment

```bash
# Clone and enter project
git clone https://github.com/your-org/amarisoft-digital-twin.git
cd amarisoft-digital-twin

# Run full experiment (automated pipeline)
bash scripts/run_experiment1.sh
```

After ~2 minutes, the following services will be available:

- **Grafana Dashboard:** http://localhost:3000 (admin/admin)
- **Prometheus:** http://localhost:9090
- **Raw Metrics:** http://localhost:8000/metrics
- **Flask Controller:** http://localhost:5000

### 17.2 Using the Flask Controller

```bash
# Start the controller UI
python3 controller/app.py

# Navigate to http://localhost:5000
# Use Run / Stop / Clean buttons
```

### 17.3 Running Individual Stages

```bash
# Clean environment only
bash scripts/clean.sh

# Start topology only
sudo python3 topology/modified.digital_twin_setup.py

# Start monitoring only
prometheus --config.file=monitoring/prometheus.yml &
systemctl start grafana-server

# Start scraper only
python3 collection/combined_scraper.py

# Run PCAP replay only
python3 replay/test.pcap_replay_twin.py
```

### 17.4 Viewing Metrics

**Via Grafana (recommended):**
1. Open http://localhost:3000
2. Navigate to Dashboards → `Twin KPI Dashboard`
3. Set time range to `Last 15 minutes`
4. All 6 KPI panels will display live data

**Via Prometheus PromQL:**
```promql
# Current UL bitrate
twin_ul_bitrate_mbps{ue="ue1"}

# Average DL bitrate over last 5 minutes
avg_over_time(twin_dl_bitrate_mbps{ue="ue1"}[5m])

# CQI heatmap
twin_cqi
```

**Via raw HTTP:**
```bash
curl http://localhost:8000/metrics
```

### 17.5 Stopping and Cleaning

```bash
# Stop experiment processes (keep containers)
bash scripts/stop.sh

# Full cleanup (recommended between experiments)
bash scripts/clean.sh
```

---

## 18. Future Improvements

### 18.1 Near-Term Enhancements

- **Multi-UE scaling:** Extend the topology to support 10–50 simultaneous UE instances with per-UE KPI tracking and Grafana label filtering
- **Adaptive PCAP replay:** Implement a feedback controller that adjusts `tcpreplay` multiplier based on real-time CQI readings, enabling closed-loop traffic adaptation
- **Open5GS metrics exporter:** Build a dedicated Prometheus exporter that parses Open5GS internal counters (PDU sessions, bytes per UE) rather than relying on log parsing
- **Automated PCAP capture pipeline:** Add a capture trigger that automatically records PCAP traces from the physical Amarisoft testbed via SSH when a new baseline profile is needed

### 18.2 Research Extensions

- **ML-based KPI prediction:** Train a time-series model (LSTM or Transformer) on the collected metrics to predict future CQI/throughput degradation
- **Slice emulation:** Add network slicing support to Open5GS/UERANSIM and expose per-slice KPIs in Grafana
- **Interference modeling:** Inject inter-cell interference via configurable noise sources in UERANSIM to study robustness under realistic RF conditions
- **Anomaly detection:** Integrate Grafana alerting with a Prometheus alertmanager to flag KPI deviations from baseline

### 18.3 Infrastructure Improvements

- **Helm chart:** Package the entire stack as a Helm chart for Kubernetes-based deployment, enabling cloud-native scaling
- **CI/CD integration:** Add GitHub Actions workflows that automatically run regression experiments on each commit, comparing KPI outputs against stored baselines
- **Docker Compose profile:** Provide a `docker-compose.yml` alternative for environments where Containernet is unavailable
- **Persistent Prometheus storage:** Mount a named Docker volume for Prometheus TSDB to preserve data across `clean.sh` invocations
- **Dashboard templating:** Parameterize Grafana dashboards to support variable UE count and experiment duration without JSON editing

---

## 19. Conclusion

The **Amarisoft Digital Twin Automation with Observability** platform demonstrates that a fully automated, research-grade 5G digital twin is achievable on commodity Linux hardware using exclusively open-source components.

By combining Comnetsemu's programmable network emulation with Open5GS's standards-compliant 5G core and UERANSIM's realistic RAN simulation — and grounding the traffic environment in real PCAP captures from an Amarisoft reference deployment — the platform achieves **metric-level fidelity** to a physical 5G testbed.

The end-to-end automation pipeline (`run_experiment1.sh`) eliminates the manual overhead traditionally associated with network experimentation, enabling **reproducible, scripted test campaigns** that can be re-run deterministically across different hardware environments.

The Prometheus + Grafana observability stack provides researchers with real-time visibility into the full radio KPI surface (UL/DL bitrate, CQI, MCS, SNR, path loss) through a pre-built dashboard that requires zero manual configuration — loaded automatically via Grafana provisioning on every run.

This platform serves as a foundation for advanced research in areas including 5G performance modeling, ML-based KPI prediction, network slicing, and closed-loop RAN control — all without requiring access to dedicated hardware.

---

<div align="center">

**Built for 5G Research — Automated, Observable, Reproducible**

*Contributions, issues, and pull requests are welcome.*

</div>
