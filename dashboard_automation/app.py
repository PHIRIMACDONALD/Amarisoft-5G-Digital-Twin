import os
import time
import signal
import socket
import subprocess
import threading
from collections import deque

from flask import Flask, jsonify, render_template, request


# -----------------------------
# Paths (repo root + scripts)
# -----------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))          # .../dashboard_automation
REPO_ROOT = os.path.abspath(os.path.join(APP_DIR, ".."))      # .../Amarisoft.digital.twin

RUN_SCRIPT = os.path.join(REPO_ROOT, "run_experiment1.sh")
CLEAN_SCRIPT = os.path.join(REPO_ROOT, "clean.sh")


# -----------------------------
# Grafana addressing (IMPORTANT)
# -----------------------------
# INTERNAL: used by Flask backend (runs on VM) to health-check Grafana.
# If Grafana is started with: docker run -p 8000:3000 ...
# then on the VM host itself Grafana is reachable via 127.0.0.1:8000
INTERNAL_GRAFANA_BASE = os.environ.get("INTERNAL_GRAFANA_BASE", "http://127.0.0.1:8000")

# EXTERNAL: what the browser should open (your Mac -> VM IP).
# Default: auto-detect VM IP.
def _get_vm_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

VM_IP = os.environ.get("VM_IP", _get_vm_ip())
EXTERNAL_GRAFANA_BASE = os.environ.get("EXTERNAL_GRAFANA_BASE", f"http://{VM_IP}:8000")

GRAFANA_HEALTH = f"{INTERNAL_GRAFANA_BASE}/api/health"

# Deterministic dashboard UID + slug (what your URL uses)
DASH_UID = os.environ.get("DASH_UID", "unitn-digital-twin")
DASH_SLUG = os.environ.get("DASH_SLUG", "unitn-digital-twin")
DASH_URL = f"{EXTERNAL_GRAFANA_BASE}/d/{DASH_UID}/{DASH_SLUG}"


# -----------------------------
# Flask app + log buffer
# -----------------------------
app = Flask(__name__)

proc = None
logbuf = deque(maxlen=600)     # keep more lines
log_lock = threading.Lock()


def _append_log(line: str):
    with log_lock:
        logbuf.append(line.rstrip("\n"))


def _reader_thread(p: subprocess.Popen):
    try:
        for line in iter(p.stdout.readline, ""):
            if not line:
                break
            _append_log(line)
    finally:
        _append_log("[DONE] Process exited.")


def _is_running() -> bool:
    return bool(proc and proc.poll() is None)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run_twin", methods=["POST"])
def run_twin():
    global proc

    if _is_running():
        return jsonify({"ok": False, "msg": "Twin is already running."}), 400

    if not os.path.exists(RUN_SCRIPT):
        return jsonify({"ok": False, "msg": f"Missing: {RUN_SCRIPT}"}), 500

    _append_log("[UI] Starting run_experiment1.sh ...")

    # Start script and stream output
    proc = subprocess.Popen(
        ["bash", RUN_SCRIPT],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        preexec_fn=os.setsid,  # so Stop can kill the entire process group
    )

    t = threading.Thread(target=_reader_thread, args=(proc,), daemon=True)
    t.start()

    return jsonify({"ok": True})


@app.route("/stop_clean", methods=["POST"])
def stop_clean():
    global proc

    # Stop running process tree
    if _is_running():
        try:
            _append_log("[UI] Stopping running process ...")
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            time.sleep(1.0)
            if _is_running():
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            _append_log("[UI] Process stopped.")
        except Exception as e:
            _append_log(f"[UI] Stop error: {e}")

    proc = None

    # Run cleanup
    if not os.path.exists(CLEAN_SCRIPT):
        _append_log(f"[UI] Missing: {CLEAN_SCRIPT}")
        return jsonify({"ok": False, "msg": "clean.sh missing"}), 500

    try:
        _append_log("[UI] Running clean.sh ...")
        out = subprocess.check_output(
            ["bash", CLEAN_SCRIPT],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.STDOUT,
        )
        for line in out.splitlines():
            _append_log(line)
        _append_log("[UI] Cleanup complete.")
    except subprocess.CalledProcessError as e:
        _append_log("[UI] Cleanup failed:")
        _append_log(e.output)

    return jsonify({"ok": True})


@app.route("/status", methods=["GET"])
def status():
    # client sends offset, we return new lines since offset
    try:
        offset = int(request.args.get("offset", "0"))
    except Exception:
        offset = 0

    with log_lock:
        lines = list(logbuf)

    new_lines = lines[offset:]
    return jsonify({
        "ok": True,
        "lines": new_lines,
        "next_offset": len(lines),
        "running": _is_running(),
        "dash_url": DASH_URL,
    })


@app.route("/open_dashboard", methods=["GET"])
def open_dashboard():
    """
    This endpoint should NEVER "hard fail" just because Grafana is still starting.
    It returns:
      - 200 + URL when Grafana is healthy
      - 503 when not ready yet
    """
    import requests

    # Poll quickly (short) — frontend can call repeatedly
    try:
        r = requests.get(GRAFANA_HEALTH, timeout=1.5)
        if r.status_code == 200:
            return jsonify({"ok": True, "url": DASH_URL})
        return jsonify({"ok": False, "msg": f"Grafana not healthy (HTTP {r.status_code})"}), 503
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Grafana not reachable yet: {e}"}), 503


@app.route("/config", methods=["GET"])
def config():
    # Useful for debugging from browser
    return jsonify({
        "internal_grafana_base": INTERNAL_GRAFANA_BASE,
        "external_grafana_base": EXTERNAL_GRAFANA_BASE,
        "grafana_health": GRAFANA_HEALTH,
        "dash_uid": DASH_UID,
        "dash_slug": DASH_SLUG,
        "dash_url": DASH_URL,
        "repo_root": REPO_ROOT,
    })


if __name__ == "__main__":
    # LAN-accessible so your Mac can open it via http://192.168.2.2:5000
    app.run(host="0.0.0.0", port=5000, debug=True)
