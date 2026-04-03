(() => {
  const btnRun = document.getElementById("btnRun");
  const btnStop = document.getElementById("btnStop");
  const btnDash = document.getElementById("btnDash");
  const logBox = document.getElementById("logBox");
  const logFilter = document.getElementById("logFilter");
  const autoScroll = document.getElementById("autoScroll");

  const stateDot = document.getElementById("stateDot");
  const stateText = document.getElementById("stateText");
  const grafanaDot = document.getElementById("grafanaDot");
  const grafanaText = document.getElementById("grafanaText");

  const toast = document.getElementById("toast");

  const State = {
    IDLE: "IDLE",
    RUNNING: "RUNNING",
    STOPPING: "STOPPING",
    CLEANING: "CLEANING",
  };

  let currentState = State.IDLE;
  let offset = 0;
  let pollTimer = null;
  let healthTimer = null;
  let allLines = []; // store raw lines for filtering

  function showToast(msg, ms = 2600) {
    toast.textContent = msg;
    toast.style.display = "block";
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => (toast.style.display = "none"), ms);
  }

  function setState(st) {
    currentState = st;

    if (st === State.IDLE) {
      stateText.textContent = "Idle";
      stateDot.className = "dot";
      btnRun.disabled = false;
      btnStop.disabled = false; // allow cleanup anytime
    }

    if (st === State.RUNNING) {
      stateText.textContent = "Running";
      stateDot.className = "dot ok";
      btnRun.disabled = true;
      btnStop.disabled = false;
    }

    if (st === State.STOPPING) {
      stateText.textContent = "Stopping…";
      stateDot.className = "dot bad";
      btnRun.disabled = true;
      btnStop.disabled = true;
    }

    if (st === State.CLEANING) {
      stateText.textContent = "Cleaning…";
      stateDot.className = "dot bad";
      btnRun.disabled = true;
      btnStop.disabled = true;
    }
  }

  function atBottom(el) {
    // "near bottom" detection
    return el.scrollTop + el.clientHeight >= el.scrollHeight - 40;
  }

  function renderLogs() {
    const q = (logFilter.value || "").trim().toLowerCase();
    const filtered = q
      ? allLines.filter((l) => l.toLowerCase().includes(q))
      : allLines;

    const shouldStick = autoScroll.checked && atBottom(logBox);

    logBox.textContent = filtered.join("\n");

    if (autoScroll.checked && shouldStick) {
      logBox.scrollTop = logBox.scrollHeight;
    }
  }

  async function pollStatus() {
    try {
      const res = await fetch(`/status?offset=${offset}`);
      const data = await res.json();

      if (!data.ok) return;

      if (data.lines && data.lines.length) {
        allLines.push(...data.lines);
        offset = data.next_offset;
        renderLogs();
      }

      // backend truth for running state
      if (data.running) {
        if (currentState !== State.RUNNING) setState(State.RUNNING);
      } else {
        // if we were running/stopping/cleaning and now not running -> idle
        if (currentState !== State.IDLE) setState(State.IDLE);
      }
    } catch (e) {
      // do nothing noisy; transient issues happen
    }
  }

  async function refreshGrafanaHealth() {
    try {
      const res = await fetch("/grafana_health");
      const data = await res.json();
      if (data.ok) {
        grafanaDot.className = "dot ok";
        grafanaText.textContent = "Grafana: OK";
      } else {
        grafanaDot.className = "dot bad";
        grafanaText.textContent = "Grafana: check…";
      }
    } catch {
      grafanaDot.className = "dot bad";
      grafanaText.textContent = "Grafana: check…";
    }
  }

  function startPolling() {
    if (!pollTimer) pollTimer = setInterval(pollStatus, 500);
    if (!healthTimer) healthTimer = setInterval(refreshGrafanaHealth, 2500);
  }

  btnRun.addEventListener("click", async () => {
    try {
      // reset logs for this run
      allLines = [];
      offset = 0;
      renderLogs();

      const res = await fetch("/run_twin", { method: "POST" });
      const data = await res.json();
      if (!data.ok) {
        showToast(data.msg || "Run failed");
        return;
      }
      showToast("Twin started");
      setState(State.RUNNING);
      startPolling();
    } catch (e) {
      showToast("Run error (check backend)");
    }
  });

  btnStop.addEventListener("click", async () => {
    try {
      setState(State.STOPPING);
      showToast("Stopping & cleaning…");

      const res = await fetch("/stop_clean", { method: "POST" });
      const data = await res.json();
      if (!data.ok) {
        showToast(data.msg || "Stop/Clean failed");
        setState(State.IDLE);
        return;
      }
      setState(State.IDLE);
      showToast("Cleanup complete");
    } catch (e) {
      showToast("Stop/Clean error (check backend)");
      setState(State.IDLE);
    }
  });

  btnDash.addEventListener("click", async () => {
    try {
      const res = await fetch("/open_dashboard");
      const data = await res.json();

      if (!data.ok) {
        alert(data.msg || "Could not open dashboard.");
        return;
      }

      if (data.warning) showToast(data.warning, 4500);

      window.open(data.url, "_blank", "noopener,noreferrer");
    } catch (e) {
      alert("Dashboard open failed (backend unreachable).");
    }
  });

  logFilter.addEventListener("input", renderLogs);

  // Start polling immediately so UI reflects reality on refresh
  startPolling();
  refreshGrafanaHealth();
  pollStatus();
})();
