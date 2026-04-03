# Amarisoft Digital Twin — Automation & Observability

> A 5G network digital twin built on Comnetsemu, Open5GS, and UERANSIM.  
> Captures real traffic from an Amarisoft testbed and replays it in a fully emulated environment — with automated Prometheus/Grafana observability, all launched from a single command.

---

## What This Project Does

This platform creates a software replica of a physical Amarisoft 5G base station. It:

- Runs a full 5G core (Open5GS) and RAN (UERANSIM) inside Docker containers using Comnetsemu
- Captures real traffic from a physical Amarisoft testbed across 4 UPF network slices
- Replays that captured traffic inside the digital twin using `tcpreplay`
- Collects metrics from both the physical and digital twin simultaneously
- Displays everything in a Grafana dashboard that opens automatically — with no manual configuration

The entire experiment — from environment startup to live dashboard — runs with a single command.

---

## Architecture Overview

```
┌─────────────────────────┐          ┌──────────────────────────────────────┐
│   Physical Twin          │          │   Digital Twin (Multipass VM)        │
│   Amarisoft CALLBOX      │          │                                      │
│                          │  PCAP    │   Comnetsemu / Containernet          │
│   • gNB (real radio)     │ capture  │   ┌──────────────────────────────┐  │
│   • 4 UPF slices:        │ ──────►  │   │ Open5GS Core                 │  │
│     - default            │          │   │ AMF · SMF · NRF · AUSF       │  │
│     - ims                │          │   │ PCF · UDM · UDR · BSF        │  │
│     - internet           │          │   │                              │  │
│     - sos                │          │   │ 4 UPF slices (mirrored)      │  │
│                          │          │   │ 5 × UERANSIM UEs             │  │
└─────────────────────────┘          │   └──────────────────────────────┘  │
                                      │                                      │
                                      │   Prometheus → Grafana               │
                                      │   combined_scraper.py                │
                                      │   Flask controller UI                │
                                      └──────────────────────────────────────┘
```

---

## Prerequisites

Before you begin, you need:

- A host machine (macOS, Windows, or Linux — including Apple Silicon M1/M2)
- [Multipass](https://multipass.run/) installed on the host
- SSH access to an Amarisoft CALLBOX on your network (for the physical twin traffic)
- ~20 GB free disk space inside the VM
- A stable internet connection for the initial setup

---

## Step 1 — Create the Virtual Machine

All project software runs inside a **Ubuntu 20.04 Multipass VM**. Run these commands on your host machine:

```bash
# Create and launch the VM
multipass launch 20.04 --name myVM

# Open a shell inside the VM
multipass shell myVM
```

> All commands from this point forward are run **inside the VM** unless stated otherwise.

To transfer files between your host and the VM:

```bash
# Host → VM
multipass transfer /path/on/host myVM:/home/ubuntu/

# VM → Host
multipass transfer myVM:/path/in/vm /destination/on/host/
```

---

## Step 2 — Install System Dependencies

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
  git iperf iperf3 make pkg-config \
  python3 python3-dev python3-pip \
  sudo ansible
```

---

## Step 3 — Install Comnetsemu

Comnetsemu is the network emulation framework that runs Docker containers as network nodes.

```bash
# Clone the repository
git clone https://git.comnets.net/public-repo/comnetsemu

# Run the full installer (takes 10–20 minutes)
cd comnetsemu/util/
bash ./install.sh -a
```

Verify the installation:

```bash
sudo mn
# You should see the Mininet CLI prompt: mininet>
# Type 'exit' to quit
```

> **Source:** [Granelli Lab — Comnetsemu Labs](https://www.granelli-lab.org/researches/relevant-projects/comnetsemu-labs), Option B (Multipass)

---

## Step 4 — Get the 5G Network Base

Clone the Granelli Lab 5G topology repository into the Comnetsemu apps directory:

```bash
cd ~/comnetsemu/app/
git clone https://github.com/fabrizio-granelli/comnetsemu_5Gnet
```

Build or pull the required Docker images:

```bash
cd comnetsemu_5Gnet/build/

# Option A — Pull pre-built images (faster)
bash dockerhub_pull.sh

# Option B — Build locally
bash build.sh
```

---

## Step 5 — Clone This Repository

```bash
cd ~/comnetsemu/app/
git clone https://github.com/<your-username>/Amarisoft.digital.twin
cd Amarisoft.digital.twin
```

Install Python dependencies:

```bash
pip3 install prometheus-client flask requests docker scapy
```

---

## Step 6 — Configure Your Environment

### 6.1 — Set the Amarisoft IP Address

Open `run_experiment1.sh` and replace the Amarisoft connection details with your own:

```bash
AMARISOFT_IP="<YOUR_AMARISOFT_IP>"
```

### 6.2 — Set the VM IP Address

Check your VM's IP address:

```bash
ip addr show | grep "inet " | grep -v 127.0.0.1
```

Open `dashboard_automation/provisioning/datasources/ds.yaml` and confirm the Prometheus URL matches:

```yaml
url: http://<YOUR_VM_IP>:9090
```

The Docker bridge host address is typically `172.17.0.1` when Prometheus runs natively on the VM host. Adjust if your network differs.

### 6.3 — Verify Open5GS Configuration

The Open5GS config files are in `open5gs/config/`. The four UPF slices are pre-configured:

```
open5gs/config/
├── upf_default.yaml     # General data traffic
├── upf_ims.yaml         # IMS / voice & video
├── upf_internet.yaml    # Internet breakout
└── upf_sos.yaml         # Emergency services
```

No changes are required here for a standard setup.

### 6.4 — Add Subscriber Profiles to MongoDB

Before the first run, load the UE subscriber profiles:

```bash
sudo python3 update_subcribers.py
```

This registers the 5 simulated UEs (IMSI profiles in `python_modules/`) into the Open5GS MongoDB instance.

---

## Step 7 — Run the Experiment

### Option A — One Command (Recommended)

```bash
sudo bash run_experiment1.sh
```

This single script runs the entire pipeline automatically:

| Step | Action |
|------|--------|
| 1 | Starts `twin_data_collector.py` in the background |
| 2 | Launches the Containernet topology (`modified.digital_twin_setup.py`) |
| 3 | Waits 60 seconds for all Open5GS NFs to register |
| 4 | Installs `tcpreplay` inside the UPF containers |
| 5 | Starts Prometheus |
| 6 | Starts Grafana (Docker, with auto-provisioned dashboard) |
| 7 | Starts `combined_scraper.py` |
| 8 | SSHes into the Amarisoft CALLBOX and runs traffic regeneration |
| 9 | Runs PCAP replay on the digital twin |
| — | Grafana dashboard opens automatically |

> **Timing note:** The Amarisoft traffic regeneration script runs for exactly **2 minutes 15 seconds**. This is intentional — do not interrupt it.

### Option B — Flask Controller UI

```bash
python3 dashboard_automation/app.py
```

Then open `http://<VM_IP>:5000` in your browser. The UI provides:

- **Run Twin** — starts the full pipeline with live log output
- **Stop / Clean** — stops all processes and resets the environment
- **Open Grafana** — opens the dashboard once it is ready

---

## Step 8 — Access the Running System

Once the experiment is running, the following are available:

| Service | URL |
|---------|-----|
| Grafana Dashboard | `http://<VM_IP>:8000/d/cfajos0kkl81sb/unitn-digital-twin` |
| Grafana Home | `http://<VM_IP>:8000` |
| Prometheus | `http://<VM_IP>:9090` |
| Prometheus Targets | `http://<VM_IP>:9090/targets` |
| Flask Controller | `http://<VM_IP>:5000` |

Grafana default login: `admin / admin`

The dashboard shows four panels updated in real time:
- Physical Twin — UL Bitrate
- Physical Twin — DL Bitrate
- Digital Twin — UPF UL Bitrate
- Digital Twin — UPF DL Bitrate

---

## Stopping and Cleaning Up

To stop the experiment and reset the environment:

```bash
bash clean.sh
```

This kills all running processes, removes Docker containers, and clears virtual network interfaces. It is safe to run between experiments and before every new run.

---

## Repository Structure

```
Amarisoft.digital.twin/
│
├── run_experiment1.sh              Master pipeline script
├── clean.sh                        Full environment reset
├── modified.digital_twin_setup.py  Containernet 5G topology
├── twin_data_collector.py          Background KPI collector
├── combined_scraper.py             Prometheus metrics exporter
├── test.pcap_replay_twin.py        PCAP replay into UPF containers
├── install_tcpreplay_in_upfs.sh    Installs tcpreplay at runtime
│
├── dashboard_automation/           One-click observability module
│   ├── app.py                      Flask controller backend
│   ├── templates/index.html        Web UI
│   ├── static/                     Frontend JS and CSS
│   └── provisioning/               Mounted into Grafana on start
│       ├── datasources/ds.yaml     Auto-registers Prometheus datasource
│       └── dashboards/
│           ├── provider.yaml       Tells Grafana where to load dashboards
│           └── UniTN_Digital_Twin.json   Pre-built KPI dashboard
│
├── open5gs/config/                 Open5GS NF configuration files
├── ueransim/config/                gNB and UE (×5) configuration files
├── digitaltwin.traffic/            PCAP files for digital twin replay
├── physicaltwin.traffic/           PCAP captures from Amarisoft
├── amarisoft_physical_twin/        Scripts that run on the CALLBOX
├── monitoring/prometheus/          Prometheus binary and config
├── build/                          Docker image build files
└── log/                            Per-NF log files
```

---

## How the Grafana Automation Works

The standard approach to adding a Grafana dashboard requires logging in, pasting JSON, and copying a randomly generated UID — steps that must be repeated every time Grafana restarts.

This project eliminates that entirely using **Grafana provisioning**: configuration files are mounted directly into the Grafana Docker container at startup. Grafana reads them before it finishes booting, so the datasource and dashboard are available from the first second with no manual steps.

The dashboard has a fixed `uid` (`cfajos0kkl81sb`) so its URL never changes between runs:

```
http://<VM_IP>:8000/d/cfajos0kkl81sb/unitn-digital-twin
```

The Docker command that enables this:

```bash
sudo docker run -d -p 8000:3000 \
  --name grafana_automation \
  -v $(pwd)/dashboard_automation/provisioning/datasources:/etc/grafana/provisioning/datasources \
  -v $(pwd)/dashboard_automation/provisioning/dashboards:/etc/grafana/provisioning/dashboards \
  grafana/grafana
```

---

## Troubleshooting

**Mininet fails to start**
```bash
sudo mn --clean
# Then retry
sudo python3 modified.digital_twin_setup.py
```

**Grafana not reachable after startup**
```bash
# Check if the container is running
docker ps | grep grafana

# Check container logs
docker logs grafana_automation
```

**Prometheus targets showing as DOWN**
```bash
# Check combined_scraper is running
ps aux | grep combined_scraper

# Manually test the metrics endpoint
curl http://localhost:9091/metrics
```

**tcpreplay not found inside UPF containers**
```bash
bash install_tcpreplay_in_upfs.sh
```

**SSH to Amarisoft fails**
- Confirm the CALLBOX is powered on and reachable: `ping <AMARISOFT_IP>`
- Confirm `sshpass` is installed: `sudo apt install sshpass`

---

## Traffic Capture Reference

### Digital Twin PCAP Files

40 files organized by UPF slice and capture day (d1–d10):

```
digitaltwin.traffic/
├── upf_defaultd1.pcap  →  upf_defaultd10.pcap    (default slice)
├── upf_imsd1.pcap      →  upf_imsd10.pcap         (IMS slice)
├── upf_internetd1.pcap →  upf_internetd10.pcap    (internet slice)
└── upf_sosd1.pcap      →  upf_sosd10.pcap         (SOS slice)
```

### Physical Twin PCAP Files

Captured directly from the Amarisoft CALLBOX:

```
physicaltwin.traffic/
├── upf_default1.pcap → upf_default10.pcap
├── upf_ims1168.pcap
├── upf_internet1168.pcap
└── upf_sos1168.pcap
```

---

## Acknowledgements

This project is built on the work of:

- **Granelli Lab — Comnetsemu**  
  https://www.granelli-lab.org/researches/relevant-projects/comnetsemu-labs

- **Granelli Lab — comnetsemu_5Gnet** (5G Containernet topology)  
  https://github.com/fabrizio-granelli/comnetsemu_5Gnet

- **TatendaHZ — Amarisoft.digital.twin** (digital twin base and PCAP pipeline)  
  https://github.com/TatendaHZ/Amarisoft.digital.twin

- **Open5GS** — https://open5gs.org  
- **UERANSIM** — https://github.com/aligungr/UERANSIM

The `dashboard_automation/` module, Grafana provisioning configuration, and full `run_experiment1.sh` pipeline are original contributions to this codebase.

---

## License

MIT License — see `LICENSE` for details.
