const state = {
  running: false,
  hydrated: false,
  busy: false,
};

const API_BASE =
  window.location.protocol === "file:" ? "http://127.0.0.1:8765" : "";

const els = {
  statusPill: document.querySelector("#statusPill"),
  statusText: document.querySelector("#statusText"),
  symbol: document.querySelector("#symbolInput"),
  notional: document.querySelector("#notionalInput"),
  trail: document.querySelector("#trailInput"),
  poll: document.querySelector("#pollInput"),
  fast: document.querySelector("#fastInput"),
  slow: document.querySelector("#slowInput"),
  dryRun: document.querySelector("#dryRunInput"),
  runOnce: document.querySelector("#runOnceButton"),
  toggle: document.querySelector("#toggleButton"),
  mode: document.querySelector("#modeValue"),
  lastRun: document.querySelector("#lastRunValue"),
  nextRun: document.querySelector("#nextRunValue"),
  cycles: document.querySelector("#cycleValue"),
  error: document.querySelector("#errorText"),
  log: document.querySelector("#logOutput"),
};

const settingInputs = [
  els.symbol,
  els.notional,
  els.trail,
  els.poll,
  els.fast,
  els.slow,
  els.dryRun,
];

const tooltipBubble = document.createElement("div");
tooltipBubble.className = "tooltip-bubble";
tooltipBubble.setAttribute("role", "tooltip");
tooltipBubble.setAttribute("aria-hidden", "true");
document.body.appendChild(tooltipBubble);

function payloadFromForm() {
  return {
    symbol: els.symbol.value.trim().toUpperCase(),
    positionNotional: els.notional.value,
    trailPercent: els.trail.value,
    pollSeconds: els.poll.value,
    fastSmaMinutes: els.fast.value,
    slowSmaMinutes: els.slow.value,
    dryRun: els.dryRun.checked,
  };
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function formatTime(value, fallback) {
  if (!value) {
    return fallback;
  }
  return new Date(value).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
}

function hydrateForm(data) {
  if (state.hydrated || document.activeElement.tagName === "INPUT") {
    return;
  }
  els.symbol.value = data.symbol || "F";
  els.notional.value = data.position_notional || "25";
  els.trail.value = data.trail_percent || "1.5";
  els.poll.value = data.poll_seconds || "60";
  els.fast.value = data.fast_sma_minutes || "5";
  els.slow.value = data.slow_sma_minutes || "20";
  els.dryRun.checked = Boolean(data.dry_run);
  state.hydrated = true;
}

function renderMode(isDryRun) {
  document.body.classList.toggle("live-paper", !isDryRun);
  els.mode.textContent = isDryRun ? "Dry run" : "Paper live";
}

function render(data) {
  state.running = Boolean(data.running);
  hydrateForm(data);

  els.statusPill.classList.toggle("is-running", state.running);
  els.statusText.textContent = state.running ? "Online" : "Offline";
  els.toggle.textContent = state.running ? "Turn Off" : "Turn On";
  els.toggle.dataset.tooltip = state.running
    ? "Stop the repeating bot loop after the current cycle."
    : "Start the repeating bot loop with the current settings.";
  els.toggle.classList.toggle("is-stop", state.running);
  els.runOnce.disabled = state.running || state.busy;
  els.toggle.disabled = state.busy;
  settingInputs.forEach((input) => {
    input.disabled = state.running || state.busy;
  });

  const isDryRun = state.running ? Boolean(data.dry_run) : els.dryRun.checked;
  renderMode(isDryRun);
  els.lastRun.textContent = formatTime(data.last_run_at, "Never");
  els.nextRun.textContent = state.running
    ? formatTime(data.next_run_at, "Queued")
    : "Idle";
  els.cycles.textContent = String(data.cycle_count || 0);
  els.error.textContent = data.last_error || "";
  els.log.textContent =
    data.last_output && data.last_output.length
      ? data.last_output.join("\n")
      : "Waiting for a run.";
}

async function refresh() {
  try {
    const data = await request("/api/status");
    render(data);
  } catch (error) {
    els.error.textContent = error.message;
  }
}

async function postAction(path) {
  state.busy = true;
  els.toggle.disabled = true;
  els.runOnce.disabled = true;
  try {
    const data = await request(path, {
      method: "POST",
      body: JSON.stringify(payloadFromForm()),
    });
    render(data);
  } catch (error) {
    els.error.textContent = error.message;
  } finally {
    state.busy = false;
    await refresh();
  }
}

function showTooltip(target) {
  const message = target.dataset.tooltip;
  if (!message) {
    return;
  }

  tooltipBubble.textContent = message;
  tooltipBubble.setAttribute("aria-hidden", "false");
  tooltipBubble.classList.add("is-visible");
  const targetRect = target.getBoundingClientRect();
  const bubbleRect = tooltipBubble.getBoundingClientRect();
  const viewportPadding = 8;
  const topCandidate = targetRect.top - bubbleRect.height - 8;
  const top =
    topCandidate >= viewportPadding ? topCandidate : targetRect.bottom + 8;
  const left = Math.min(
    Math.max(targetRect.left, viewportPadding),
    window.innerWidth - bubbleRect.width - viewportPadding,
  );

  tooltipBubble.style.left = `${left}px`;
  tooltipBubble.style.top = `${top}px`;
}

function hideTooltip() {
  tooltipBubble.classList.remove("is-visible");
  tooltipBubble.setAttribute("aria-hidden", "true");
}

function setupTooltips() {
  document.querySelectorAll("[data-tooltip]").forEach((target) => {
    target.addEventListener("mouseenter", () => showTooltip(target));
    target.addEventListener("mouseleave", hideTooltip);
    target.addEventListener("focus", () => showTooltip(target));
    target.addEventListener("blur", hideTooltip);
  });
  window.addEventListener("scroll", hideTooltip, { passive: true });
  window.addEventListener("resize", hideTooltip);
}

els.toggle.addEventListener("click", () => {
  postAction(state.running ? "/api/stop" : "/api/start");
});

els.runOnce.addEventListener("click", () => {
  postAction("/api/run-once");
});

els.symbol.addEventListener("input", () => {
  els.symbol.value = els.symbol.value.toUpperCase();
});

els.dryRun.addEventListener("change", () => {
  renderMode(els.dryRun.checked);
});

setupTooltips();
refresh();
setInterval(refresh, 2000);
