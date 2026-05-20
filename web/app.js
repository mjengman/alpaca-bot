const state = {
  running: false,
  hydrated: false,
  logHydrated: false,
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
  closeout: document.querySelector("#closeoutInput"),
  regimeGap: document.querySelector("#regimeGapInput"),
  fast: document.querySelector("#fastInput"),
  slow: document.querySelector("#slowInput"),
  dryRun: document.querySelector("#dryRunInput"),
  runOnce: document.querySelector("#runOnceButton"),
  toggle: document.querySelector("#toggleButton"),
  mode: document.querySelector("#modeValue"),
  lastRun: document.querySelector("#lastRunValue"),
  nextRun: document.querySelector("#nextRunValue"),
  cycles: document.querySelector("#cycleValue"),
  regime: document.querySelector("#regimeValue"),
  activeBot: document.querySelector("#activeBotValue"),
  routedSymbol: document.querySelector("#routedSymbolValue"),
  action: document.querySelector("#actionValue"),
  portfolio: document.querySelector("#portfolioValue"),
  dayPl: document.querySelector("#dayPlValue"),
  buyingPower: document.querySelector("#buyingPowerValue"),
  sourcePrice: document.querySelector("#sourcePriceValue"),
  gap: document.querySelector("#gapValue"),
  position: document.querySelector("#positionValue"),
  positionPl: document.querySelector("#positionPlValue"),
  trailExit: document.querySelector("#trailExitValue"),
  error: document.querySelector("#errorText"),
  log: document.querySelector("#logOutput"),
};

const settingInputs = [
  els.symbol,
  els.notional,
  els.trail,
  els.poll,
  els.closeout,
  els.regimeGap,
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
    closeLiquidateMinutes: els.closeout.value,
    regimeGapThreshold: els.regimeGap.value,
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
  els.symbol.value = data.symbol || "SOXL";
  els.notional.value = data.position_notional || "25";
  els.trail.value = data.trail_percent || "1.5";
  els.poll.value = data.poll_seconds || "60";
  els.closeout.value = data.close_liquidate_minutes || "5";
  els.regimeGap.value = data.regime_gap_threshold || "0.20";
  els.fast.value = data.fast_sma_minutes || "5";
  els.slow.value = data.slow_sma_minutes || "20";
  els.dryRun.checked = Boolean(data.dry_run);
  state.hydrated = true;
}

function renderMode(isDryRun) {
  document.body.classList.toggle("live-paper", !isDryRun);
  els.mode.textContent = isDryRun ? "Dry run" : "Paper live";
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatMoney(value) {
  const parsed = numberOrNull(value);
  if (parsed === null) {
    return "--";
  }
  return parsed.toLocaleString([], {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatPrice(value) {
  const parsed = numberOrNull(value);
  if (parsed === null) {
    return "--";
  }
  return `$${parsed.toLocaleString([], {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })}`;
}

function formatPercent(value, { fraction = false } = {}) {
  const parsed = numberOrNull(value);
  if (parsed === null) {
    return "--";
  }
  const percent = fraction ? parsed * 100 : parsed;
  return `${percent >= 0 ? "+" : ""}${percent.toFixed(2)}%`;
}

function formatQty(value) {
  const parsed = numberOrNull(value);
  if (parsed === null) {
    return null;
  }
  return parsed.toLocaleString([], {
    minimumFractionDigits: 0,
    maximumFractionDigits: 6,
  });
}

function formatLabel(value) {
  if (!value) {
    return "--";
  }
  const labels = {
    chop_no_trade_placeholder: "Standing Aside",
    no_entry_signal: "No Entry Signal",
    close_stale_position_no_same_cycle_reversal: "Closed Stale Exposure",
    wait_for_stale_close: "Waiting For Stale Close",
    manage_open_position: "Managing Position",
    market_buy: "Market Buy",
    market_close_liquidation: "Closing Before Bell",
    closeout_window_no_position: "Flat Into Close",
    wait_for_closeout_order: "Waiting For Closeout",
    wait_for_open_order: "Waiting For Buy Order",
    wait_for_data: "Waiting For Data",
    no_entry: "No Entry",
    noop: "No Action",
  };
  if (labels[value]) {
    return labels[value];
  }
  return String(value)
    .replace(/Bot$/, " Bot")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function setTone(element, value) {
  element.classList.remove("is-positive", "is-negative", "is-neutral");
  const parsed = numberOrNull(value);
  if (parsed === null || parsed === 0) {
    element.classList.add("is-neutral");
  } else {
    element.classList.add(parsed > 0 ? "is-positive" : "is-negative");
  }
}

function renderDecision(status) {
  if (!status) {
    els.regime.textContent = "Waiting";
    els.activeBot.textContent = "Waiting";
    els.routedSymbol.textContent = "None";
    els.action.textContent = "Waiting";
    return;
  }

  const regime = status.regime || "Waiting";
  els.regime.textContent = regime;
  els.regime.className = `regime-value regime-${regime.toLowerCase()}`;
  els.activeBot.textContent = formatLabel(status.active_bot);
  els.routedSymbol.textContent = status.routed_symbol || "None";
  els.action.textContent = formatLabel(status.action_taken);
  els.portfolio.textContent = formatMoney(status.portfolio_value);
  els.buyingPower.textContent = formatMoney(status.buying_power);
  els.sourcePrice.textContent = formatPrice(status.source_price);
  els.gap.textContent = formatPercent(status.gap_percent);

  const dayPlText = `${formatMoney(status.day_pl)} ${formatPercent(status.day_pl_percent)}`;
  els.dayPl.textContent = status.day_pl === null ? "--" : dayPlText;
  setTone(els.dayPl, status.day_pl);

  if (status.position_symbol && status.position_qty) {
    const qty = formatQty(status.position_qty) || status.position_qty;
    const marketValue = formatMoney(status.position_market_value);
    els.position.textContent = `${status.position_symbol} ${qty} (${marketValue})`;
  } else {
    els.position.textContent = "Flat";
  }

  const positionPlText = `${formatMoney(status.position_unrealized_pl)} ${formatPercent(
    status.position_unrealized_pl_percent,
    { fraction: true },
  )}`;
  els.positionPl.textContent =
    status.position_unrealized_pl === null ? "--" : positionPlText;
  setTone(els.positionPl, status.position_unrealized_pl);

  els.trailExit.textContent = status.trailing_exit_price
    ? formatPrice(status.trailing_exit_price)
    : "--";
}

function renderLog(data) {
  const logText =
    data.activity_log && data.activity_log.length
      ? data.activity_log.join("\n")
      : data.last_output && data.last_output.length
      ? data.last_output.join("\n")
      : "Waiting for a run.";

  if (els.log.textContent === logText) {
    return;
  }

  const previousHeight = els.log.scrollHeight;
  const previousTop = els.log.scrollTop;
  const wasNearBottom =
    previousHeight - previousTop - els.log.clientHeight < 48;

  els.log.textContent = logText;

  if (!state.logHydrated || wasNearBottom) {
    els.log.scrollTop = els.log.scrollHeight;
  } else {
    els.log.scrollTop = previousTop + (els.log.scrollHeight - previousHeight);
  }

  state.logHydrated = true;
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
  renderDecision(data.edgewalker_status);
  renderLog(data);
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
