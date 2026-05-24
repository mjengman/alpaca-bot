const state = {
  running: false,
  hydrated: false,
  logHydrated: false,
  logCollapsed: false,
  logExpanded: false,
  logText: "",
  busy: false,
  fixedNotionalValue: "25",
  latestBuyingPower: null,
  lastSizingValue: "FIXED",
  activeTab: "activity",
  narrativeTimeframe: "1D",
  narrativeCustomStart: "",
  narrativeCustomEnd: "",
  narrativeCache: {},
  narrativeText: null,
  narrativeSections: null,
  narrativeDate: null,
  narrativeDisplayDate: null,
  narrativeCycles: null,
  narrativeLoading: false,
};

const THEME_KEY = "edgewalker-theme";
const LOG_COLLAPSED_KEY = "edgewalker-log-collapsed";
const LOG_EXPANDED_KEY = "edgewalker-log-expanded";
const NARRATIVE_CACHE_KEY = "edgewalker-narrative-cache-v1";
const API_BASE =
  window.location.protocol === "file:" ? "http://127.0.0.1:8765" : "";

const els = {
  operatorGuideOpen: document.querySelector("#operatorGuideOpen"),
  operatorGuideDialog: document.querySelector("#operatorGuideDialog"),
  operatorGuideClose: document.querySelector("#operatorGuideClose"),
  themeToggle: document.querySelector("#themeToggle"),
  statusPill: document.querySelector("#statusPill"),
  statusText: document.querySelector("#statusText"),
  symbol: document.querySelector("#symbolInput"),
  notional: document.querySelector("#notionalInput"),
  positionSizing: document.querySelector("#positionSizingInput"),
  trail: document.querySelector("#trailInput"),
  poll: document.querySelector("#pollInput"),
  closeout: document.querySelector("#closeoutInput"),
  regimeGap: document.querySelector("#regimeGapInput"),
  regimeExitGap: document.querySelector("#regimeExitGapInput"),
  chopDiscount: document.querySelector("#chopDiscountInput"),
  directionalModes: document.querySelectorAll('input[name="directionalMode"]'),
  directionalMaxExtension: document.querySelector("#directionalMaxExtensionInput"),
  directionalStrongChase: document.querySelector("#directionalStrongChaseInput"),
  directionalMinStrength: document.querySelector("#directionalMinStrengthInput"),
  directionalCooldown: document.querySelector("#directionalCooldownInput"),
  fast: document.querySelector("#fastInput"),
  slow: document.querySelector("#slowInput"),
  dryRun: document.querySelector("#dryRunInput"),
  runOnce: document.querySelector("#runOnceButton"),
  toggle: document.querySelector("#toggleButton"),
  mode: document.querySelector("#modeValue"),
  dataStatus: document.querySelector("#dataStatusValue"),
  brokerState: document.querySelector("#brokerStateValue"),
  sessionRealizedPl: document.querySelector("#sessionRealizedPlValue"),
  sessionTrades: document.querySelector("#sessionTradesValue"),
  botPerformanceSummary: document.querySelector("#botPerformanceSummaryValue"),
  botPerformanceGrid: document.querySelector("#botPerformanceGrid"),
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
  orderSummary: document.querySelector("#orderSummaryValue"),
  pendingOrders: document.querySelector("#pendingOrdersList"),
  orderEvents: document.querySelector("#orderEventsList"),
  error: document.querySelector("#errorText"),
  activityPanel: document.querySelector("#activityPanel"),
  activityTab: document.querySelector("#activityTab"),
  narrativeTab: document.querySelector("#narrativeTab"),
  activityCopy: document.querySelector("#activityCopy"),
  activityExpand: document.querySelector("#activityExpand"),
  activityToggle: document.querySelector("#activityToggle"),
  narrativeGenerate: document.querySelector("#narrativeGenerate"),
  narrativeOutput: document.querySelector("#narrativeOutput"),
  narrativeContent: document.querySelector("#narrativeContent"),
  customRange: document.querySelector("#customRange"),
  customStartDate: document.querySelector("#customStartDate"),
  customEndDate: document.querySelector("#customEndDate"),
  log: document.querySelector("#logOutput"),
};

const settingInputs = [
  els.notional,
  els.positionSizing,
  els.trail,
  els.poll,
  els.closeout,
  els.regimeGap,
  els.regimeExitGap,
  els.chopDiscount,
  ...els.directionalModes,
  els.directionalMaxExtension,
  els.directionalStrongChase,
  els.directionalMinStrength,
  els.directionalCooldown,
  els.fast,
  els.slow,
  els.dryRun,
].filter(Boolean);

const tooltipBubble = document.createElement("div");
tooltipBubble.className = "tooltip-bubble";
tooltipBubble.setAttribute("role", "tooltip");
tooltipBubble.setAttribute("aria-hidden", "true");
document.body.appendChild(tooltipBubble);

function payloadFromForm() {
  const selectedDirectionalMode =
    [...els.directionalModes].find((input) => input.checked)?.value || "BALANCED";
  const sizingValue = els.positionSizing ? els.positionSizing.value : "FIXED";
  const positionSizingMode = sizingValue === "FIXED" ? "FIXED" : "DYNAMIC";
  const positionAllocationPercent =
    sizingValue === "FIXED" ? "25" : sizingValue;
  return {
    symbol: els.symbol ? els.symbol.value.trim().toUpperCase() : "SOXL",
    positionNotional:
      positionSizingMode === "FIXED"
        ? els.notional.value
        : state.fixedNotionalValue,
    positionSizingMode,
    positionAllocationPercent,
    trailPercent: els.trail.value,
    pollSeconds: els.poll.value,
    closeLiquidateMinutes: els.closeout ? els.closeout.value : "5",
    regimeGapThreshold: els.regimeGap.value,
    regimeExitGapThreshold: els.regimeExitGap.value,
    chopEntryDiscountPercent: els.chopDiscount.value,
    directionalMode: selectedDirectionalMode,
    directionalMaxExtensionPercent: els.directionalMaxExtension.value,
    directionalStrongChaseMaxExtensionPercent: els.directionalStrongChase.value,
    directionalMinStrength: els.directionalMinStrength.value,
    directionalCooldownMinutes: els.directionalCooldown.value,
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

function formatCountdown(value) {
  if (!value) {
    return "soon";
  }
  const target = new Date(value).getTime();
  if (!Number.isFinite(target)) {
    return "soon";
  }

  const totalSeconds = Math.max(0, Math.ceil((target - Date.now()) / 1000));
  if (totalSeconds <= 0) {
    return "now";
  }

  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (days > 0) {
    return `${days}d ${hours}h ${minutes}m`;
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

function formatNextCheck(data) {
  if (!state.running) {
    return "Idle";
  }
  if (!data.next_run_at) {
    return "Queued";
  }
  if (data.next_run_reason === "market_open") {
    const countdown = formatCountdown(data.next_run_at);
    return countdown === "now" ? "Opens now" : `Opens in ${countdown}`;
  }
  return formatTime(data.next_run_at, "Queued");
}

function sizingValueFromData(data) {
  if (data.position_sizing_mode !== "DYNAMIC") {
    return "FIXED";
  }
  const allocation = String(data.position_allocation_percent || "25");
  const exact = ["25", "50", "75", "95"].find((value) => value === allocation);
  if (exact) {
    return exact;
  }
  const numeric = Number(allocation);
  if (numeric >= 90) {
    return "95";
  }
  if (numeric >= 75) {
    return "75";
  }
  if (numeric >= 50) {
    return "50";
  }
  return "25";
}

function buyingPowerFromData(data) {
  const value = data.edgewalker_status?.buying_power ?? null;
  return numberOrNull(value);
}

function dynamicNotionalPreview() {
  if (!els.positionSizing || els.positionSizing.value === "FIXED") {
    return null;
  }
  const buyingPower = state.latestBuyingPower;
  const allocation = numberOrNull(els.positionSizing.value);
  if (buyingPower === null || allocation === null) {
    return null;
  }

  const requested = buyingPower * (allocation / 100);
  const maxNotional = buyingPower * 0.95;
  return Math.floor(Math.min(requested, maxNotional) * 100) / 100;
}

function formatNotionalInput(value) {
  const parsed = numberOrNull(value);
  if (parsed === null) {
    return "";
  }
  return parsed.toFixed(2);
}

function syncSizingControls() {
  if (!els.positionSizing || !els.notional) {
    return;
  }
  const dynamicSizing = els.positionSizing.value !== "FIXED";
  if (dynamicSizing) {
    const preview = dynamicNotionalPreview();
    els.notional.value = preview === null ? "" : formatNotionalInput(preview);
    els.notional.placeholder = preview === null ? "--" : "";
    els.notional.setAttribute(
      "aria-label",
      "Estimated dynamic position dollars",
    );
  } else {
    els.notional.placeholder = "";
    els.notional.setAttribute("aria-label", "Position dollars");
  }
  els.notional.disabled = state.running || state.busy || dynamicSizing;
  els.notional.closest(".field")?.classList.toggle("is-disabled", dynamicSizing);
}

function hydrateForm(data) {
  if (
    state.hydrated ||
    ["INPUT", "SELECT"].includes(document.activeElement.tagName)
  ) {
    return;
  }
  if (els.symbol) {
    els.symbol.value = data.symbol || "SOXL";
  }
  state.fixedNotionalValue = data.position_notional || state.fixedNotionalValue || "25";
  els.notional.value = state.fixedNotionalValue;
  if (els.positionSizing) {
    els.positionSizing.value = sizingValueFromData(data);
    state.lastSizingValue = els.positionSizing.value;
  }
  els.trail.value = data.trail_percent || "1.5";
  els.poll.value = data.poll_seconds || "60";
  if (els.closeout) {
    els.closeout.value = data.close_liquidate_minutes || "5";
  }
  els.regimeGap.value = data.regime_gap_threshold || "0.20";
  els.regimeExitGap.value = data.regime_exit_gap_threshold || "0.10";
  els.chopDiscount.value = data.chop_entry_discount_percent || "0.50";
  const directionalMode = data.directional_mode || "BALANCED";
  els.directionalModes.forEach((input) => {
    input.checked = input.value === directionalMode;
  });
  els.directionalMaxExtension.value =
    data.directional_max_extension_percent || "0.50";
  els.directionalStrongChase.value =
    data.directional_strong_chase_max_extension_percent || "1.00";
  els.directionalMinStrength.value = data.directional_min_strength || "MODERATE";
  els.directionalCooldown.value = data.directional_cooldown_minutes || "5";
  els.fast.value = data.fast_sma_minutes || "5";
  els.slow.value = data.slow_sma_minutes || "20";
  els.dryRun.checked = Boolean(data.dry_run);
  syncSizingControls();
  state.hydrated = true;
}

function renderMode(isDryRun) {
  document.body.classList.toggle("live-paper", !isDryRun);
  els.mode.textContent = isDryRun ? "Dry run" : "Paper live";
}

function formatAgeSeconds(value) {
  const parsed = numberOrNull(value);
  if (parsed === null) {
    return null;
  }
  if (parsed < 1) {
    return "<1s";
  }
  return `${Math.round(parsed)}s`;
}

function renderDataHealth(status) {
  if (!els.dataStatus) {
    return;
  }

  els.dataStatus.classList.remove("data-live", "data-warn", "data-danger");

  if (!status) {
    els.dataStatus.textContent = "Waiting";
    els.dataStatus.classList.add("data-warn");
    return;
  }

  const labels = {
    LIVE: "Live",
    WARMING_UP: "Warming",
    CONNECTING: "Connecting",
    DISCONNECTED: "Disconnected",
    STALE: "Stale",
    MISSING_DEPENDENCY: "Missing WebSocket",
    ERROR: "Error",
    REST: "REST",
  };
  const rawStatus = status.data_status || "Waiting";
  const label = labels[rawStatus] || formatLabel(rawStatus);
  const feed = status.data_feed ? status.data_feed.toUpperCase() : null;
  const age = formatAgeSeconds(status.bar_age_seconds);
  const pieces = [label];
  if (feed) {
    pieces.push(feed);
  }
  if (age) {
    pieces.push(age);
  }
  els.dataStatus.textContent = pieces.join(" · ");

  if (rawStatus === "LIVE") {
    els.dataStatus.classList.add("data-live");
  } else if (
    rawStatus === "STALE" ||
    rawStatus === "ERROR" ||
    rawStatus === "MISSING_DEPENDENCY"
  ) {
    els.dataStatus.classList.add("data-danger");
  } else {
    els.dataStatus.classList.add("data-warn");
  }
}

function renderBrokerState(brokerState) {
  if (!els.brokerState) {
    return;
  }

  els.brokerState.classList.remove("data-live", "data-warn", "data-danger");
  const stateValue = brokerState?.state || "OK";
  const labels = {
    OK: "OK",
    RESTRICTED: "Restricted",
    EXIT_BLOCKED: "Exit Blocked",
    BUYING_POWER_LIMITED: "Buying Power",
    ORDER_PENDING: "Order Pending",
  };
  els.brokerState.textContent = labels[stateValue] || formatLabel(stateValue);

  if (brokerState?.message) {
    const category = brokerState.category
      ? `${formatLabel(brokerState.category)}: `
      : "";
    els.brokerState.dataset.tooltip = `${category}${brokerState.message}`;
  } else {
    els.brokerState.dataset.tooltip = "No broker constraint is currently active.";
  }

  if (stateValue === "OK") {
    els.brokerState.classList.add("data-live");
  } else if (stateValue === "ORDER_PENDING" || stateValue === "BUYING_POWER_LIMITED") {
    els.brokerState.classList.add("data-warn");
  } else {
    els.brokerState.classList.add("data-danger");
  }
}

function renderPerformance(performance) {
  const realizedPl = performance?.session_realized_pl ?? null;
  const tradeCount = performance?.session_trade_count ?? 0;
  const lastTradePl = performance?.last_trade_realized_pl ?? null;

  els.sessionRealizedPl.textContent =
    realizedPl === null ? "--" : formatMoney(realizedPl);
  setTone(els.sessionRealizedPl, realizedPl);

  if (tradeCount > 0 && lastTradePl !== null) {
    els.sessionTrades.textContent = `${tradeCount} / last ${formatMoney(lastTradePl)}`;
    setTone(els.sessionTrades, lastTradePl);
  } else {
    els.sessionTrades.textContent = String(tradeCount || 0);
    setTone(els.sessionTrades, 0);
  }

  renderBotPerformance(performance?.bot_performance || []);
}

function renderBotPerformance(botPerformance) {
  const rows = Array.isArray(botPerformance) ? botPerformance : [];
  const totalTrades = rows.reduce(
    (sum, row) => sum + (numberOrNull(row.trade_count) || 0),
    0,
  );
  els.botPerformanceSummary.textContent =
    totalTrades > 0 ? `${totalTrades} closed trades` : "No closed trades";
  els.botPerformanceSummary.classList.remove(
    "is-positive",
    "is-negative",
    "is-neutral",
  );
  els.botPerformanceSummary.classList.add("is-neutral");

  els.botPerformanceGrid.innerHTML = rows.length
    ? rows.map(renderBotPerformanceCard).join("")
    : '<div class="bot-performance-empty">No closed trades yet.</div>';
}

function renderBotPerformanceCard(row) {
  const realized = row.realized_pl ?? "0";
  const trades = numberOrNull(row.trade_count) || 0;
  const winRate = row.win_rate_percent === null ? "--" : formatPercent(row.win_rate_percent);
  const lastTrade =
    row.last_trade_realized_pl === null
      ? "No trade"
      : `${formatMoney(row.last_trade_realized_pl)} ${
          row.last_trade_symbol || ""
        }`.trim();
  const toneClass =
    numberOrNull(realized) === null || numberOrNull(realized) === 0
      ? "is-neutral"
      : numberOrNull(realized) > 0
      ? "is-positive"
      : "is-negative";
  return `
    <div class="bot-performance-card">
      <span>${escapeHtml(formatLabel(row.bot || "Bot"))}</span>
      <strong class="${toneClass}">${escapeHtml(formatMoney(realized))}</strong>
      <div class="bot-performance-stats">
        <span>${escapeHtml(String(trades))} trades</span>
        <span>${escapeHtml(String(row.wins || 0))}W/${escapeHtml(String(row.losses || 0))}L</span>
        <span>${escapeHtml(winRate)}</span>
      </div>
      <small>${escapeHtml(lastTrade)}</small>
    </div>
  `;
}

function savedTheme() {
  try {
    return localStorage.getItem(THEME_KEY);
  } catch {
    return null;
  }
}

function saveTheme(theme) {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    return;
  }
}

function applyTheme(theme) {
  const useDark = theme === "dark";
  document.body.classList.toggle("dark-theme", useDark);
  if (els.themeToggle) {
    els.themeToggle.setAttribute("aria-pressed", String(useDark));
    els.themeToggle.dataset.tooltip = useDark
      ? "Switch to light mode."
      : "Switch to dark mode.";
  }
}

function setupTheme() {
  const preferred = window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
  applyTheme(savedTheme() || preferred);
}

function toggleTheme() {
  const nextTheme = document.body.classList.contains("dark-theme")
    ? "light"
    : "dark";
  applyTheme(nextTheme);
  saveTheme(nextTheme);
}

function setupOperatorGuide() {
  if (!els.operatorGuideDialog || !els.operatorGuideOpen) return;
  const closeGuide = () => {
    if (els.operatorGuideDialog.open) {
      els.operatorGuideDialog.close();
    }
  };

  els.operatorGuideOpen.addEventListener("click", () => {
    hideTooltip();
    if (typeof els.operatorGuideDialog.showModal === "function") {
      els.operatorGuideDialog.showModal();
    } else {
      els.operatorGuideDialog.setAttribute("open", "");
    }
  });

  if (els.operatorGuideClose) {
    els.operatorGuideClose.addEventListener("click", closeGuide);
  }
  els.operatorGuideDialog.addEventListener("click", (event) => {
    if (event.target === els.operatorGuideDialog) {
      closeGuide();
    }
  });
}

function saveLogCollapsed(collapsed) {
  try {
    localStorage.setItem(LOG_COLLAPSED_KEY, collapsed ? "1" : "0");
  } catch {
    return;
  }
}

function saveLogExpanded(expanded) {
  try {
    localStorage.setItem(LOG_EXPANDED_KEY, expanded ? "1" : "0");
  } catch {
    return;
  }
}

function loadLogCollapsed() {
  try {
    return localStorage.getItem(LOG_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

function loadLogExpanded() {
  try {
    return localStorage.getItem(LOG_EXPANDED_KEY) === "1";
  } catch {
    return false;
  }
}

function setLogCollapsed(collapsed) {
  state.logCollapsed = collapsed;
  if (!els.activityPanel || !els.activityToggle) {
    return;
  }
  els.activityPanel.classList.toggle("is-collapsed", collapsed);
  els.activityToggle.textContent = collapsed ? "Show" : "Hide";
  els.activityToggle.setAttribute("aria-expanded", String(!collapsed));
  els.activityToggle.dataset.tooltip = collapsed
    ? "Show the rolling activity log."
    : "Hide the rolling activity log.";
  if (els.activityExpand) {
    els.activityExpand.disabled = collapsed;
  }
  saveLogCollapsed(collapsed);
}

function setLogExpanded(expanded) {
  state.logExpanded = expanded;
  if (!els.activityPanel || !els.activityExpand) {
    return;
  }
  els.activityPanel.classList.toggle("is-expanded", expanded);
  els.activityExpand.textContent = expanded ? "v" : "^";
  els.activityExpand.setAttribute("aria-pressed", String(expanded));
  els.activityExpand.dataset.tooltip = expanded
    ? "Return the activity log to compact height."
    : "Expand the activity log vertically for review.";
  saveLogExpanded(expanded);
}

async function copyActivityLog() {
  if (!els.activityCopy) {
    return;
  }

  const isNarrative = state.activeTab === "narrative";
  const text = isNarrative
    ? (state.narrativeText || "")
    : (state.logText || els.log?.textContent || "");
  const originalText = els.activityCopy.textContent;
  const originalTooltip = els.activityCopy.dataset.tooltip;

  if (!text.trim()) {
    els.activityCopy.textContent = "Empty";
    els.activityCopy.dataset.tooltip = isNarrative
      ? "There is no narrative to copy yet."
      : "There is no activity log text to copy yet.";
    window.setTimeout(() => {
      els.activityCopy.textContent = originalText;
      els.activityCopy.dataset.tooltip = originalTooltip;
    }, 1400);
    return;
  }

  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    els.activityCopy.textContent = "Copied";
    els.activityCopy.dataset.tooltip = isNarrative
      ? "Narrative copied."
      : "Activity log copied.";
  } catch {
    els.activityCopy.textContent = "Failed";
    els.activityCopy.dataset.tooltip = "Could not copy.";
  } finally {
    window.setTimeout(() => {
      els.activityCopy.textContent = originalText;
      els.activityCopy.dataset.tooltip = originalTooltip;
    }, 1400);
  }
}

function switchTab(tab) {
  state.activeTab = tab;
  const isActivity = tab === "activity";

  if (els.activityTab) {
    els.activityTab.classList.toggle("is-active", isActivity);
    els.activityTab.setAttribute("aria-selected", String(isActivity));
  }
  if (els.narrativeTab) {
    els.narrativeTab.classList.toggle("is-active", !isActivity);
    els.narrativeTab.setAttribute("aria-selected", String(!isActivity));
  }
  if (els.log) els.log.hidden = !isActivity;
  if (els.narrativeOutput) els.narrativeOutput.hidden = isActivity;
  if (els.activityExpand) {
    els.activityExpand.disabled = state.logCollapsed;
  }
}

function localDateInputValue(date = new Date()) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function loadNarrativeCache() {
  try {
    const raw = window.sessionStorage.getItem(NARRATIVE_CACHE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    state.narrativeCache = parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    state.narrativeCache = {};
  }
}

function persistNarrativeCache() {
  try {
    window.sessionStorage.setItem(
      NARRATIVE_CACHE_KEY,
      JSON.stringify(state.narrativeCache),
    );
  } catch {
    // Session storage is a convenience cache; losing it should not block use.
  }
}

function ensureCustomDateDefaults() {
  const today = localDateInputValue();
  if (!state.narrativeCustomStart) {
    state.narrativeCustomStart = today;
  }
  if (!state.narrativeCustomEnd) {
    state.narrativeCustomEnd = state.narrativeCustomStart;
  }
  if (els.customStartDate) {
    els.customStartDate.value = state.narrativeCustomStart;
  }
  if (els.customEndDate) {
    els.customEndDate.value = state.narrativeCustomEnd;
  }
}

function narrativeSelectionKey() {
  if (state.narrativeTimeframe === "CUSTOM") {
    return `CUSTOM:${state.narrativeCustomStart || ""}:${state.narrativeCustomEnd || ""}`;
  }
  return state.narrativeTimeframe;
}

function clearNarrativeState() {
  state.narrativeText = null;
  state.narrativeSections = null;
  state.narrativeDate = null;
  state.narrativeDisplayDate = null;
  state.narrativeCycles = null;
}

function applyNarrativeSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    clearNarrativeState();
    return;
  }
  state.narrativeSections = normalizeNarrativeSections(snapshot.sections);
  state.narrativeDate = snapshot.date || null;
  state.narrativeDisplayDate = snapshot.displayDate || null;
  state.narrativeCycles = snapshot.cycles || null;
  state.narrativeText = state.narrativeSections
    ? narrativeCopyText()
    : legacyNarrativeText(snapshot.text);
}

function currentNarrativeSnapshot() {
  return {
    text: state.narrativeText,
    sections: state.narrativeSections,
    date: state.narrativeDate,
    displayDate: state.narrativeDisplayDate,
    cycles: state.narrativeCycles,
    savedAt: new Date().toISOString(),
  };
}

function saveCurrentNarrativeToCache() {
  if (!state.narrativeText && !state.narrativeSections) return;
  state.narrativeCache[narrativeSelectionKey()] = currentNarrativeSnapshot();
  persistNarrativeCache();
}

function updateNarrativeGenerateButton() {
  if (!els.narrativeGenerate || state.narrativeLoading) return;
  els.narrativeGenerate.textContent =
    state.narrativeText || state.narrativeSections ? "Regenerate" : "Generate";
}

function renderNarrativeControls() {
  const isCustom = state.narrativeTimeframe === "CUSTOM";
  if (isCustom) {
    ensureCustomDateDefaults();
  }
  if (els.customRange) {
    els.customRange.hidden = !isCustom;
  }
  document.querySelectorAll(".timeframe-btn").forEach((btn) => {
    btn.classList.toggle(
      "is-active",
      btn.dataset.timeframe === state.narrativeTimeframe,
    );
  });
}

function restoreNarrativeForSelection() {
  const snapshot = state.narrativeCache[narrativeSelectionKey()];
  if (snapshot) {
    applyNarrativeSnapshot(snapshot);
  } else {
    clearNarrativeState();
  }
  renderNarrative();
  updateNarrativeGenerateButton();
}

function renderNarrative() {
  if (!els.narrativeContent) return;
  if (!state.narrativeText && !state.narrativeSections) {
    els.narrativeContent.innerHTML =
      '<p class="narrative-empty">No narrative generated yet.</p>';
    return;
  }
  const metaLabel = state.narrativeDisplayDate || state.narrativeDate;
  const meta = metaLabel
    ? `<p class="narrative-meta">${escapeHtml(metaLabel)} · ${state.narrativeCycles || "?"} cycles</p>`
    : "";
  if (!state.narrativeSections) {
    const body = (state.narrativeText || "")
      .split(/\n\n+/)
      .map((p) => `<p>${escapeHtml(p.trim()).replace(/\n/g, "<br>")}</p>`)
      .join("");
    els.narrativeContent.innerHTML = meta + body;
    return;
  }

  const sections = state.narrativeSections;
  const botPerformance = renderNarrativeBotPerformance(sections.bot_performance);
  const html = [
    meta,
    sections.tldr
      ? `<section class="narrative-tldr"><strong>TL;DR:</strong> ${escapeHtml(sections.tldr)}</section>`
      : "",
    narrativeSectionHtml("Highlight", sections.highlight),
    botPerformance
      ? `<section class="narrative-section"><h3>Bot Performance</h3>${botPerformance}</section>`
      : "",
    narrativeSectionHtml("Market Conditions", sections.market_conditions),
    narrativeSectionHtml("Operational Issues", sections.operational_issues),
    narrativeSectionHtml("Analysis", sections.analysis),
    narrativeSectionHtml("Bottom Line", sections.bottom_line),
  ].join("");
  els.narrativeContent.innerHTML = html || meta;
}

function narrativeSectionHtml(title, text) {
  if (!text) return "";
  return `<section class="narrative-section"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(text).replace(/\n/g, "<br>")}</p></section>`;
}

function renderNarrativeBotPerformance(botPerformance) {
  if (!botPerformance) return "";
  if (typeof botPerformance === "string") {
    return `<p>${escapeHtml(botPerformance)}</p>`;
  }
  return Object.entries(botPerformance)
    .filter(([, text]) => text)
    .map(
      ([bot, text]) =>
        `<div class="narrative-bot-row"><strong>${escapeHtml(bot)}</strong><span>${escapeHtml(String(text))}</span></div>`,
    )
    .join("");
}

function narrativeCopyText() {
  const metaLabel = state.narrativeDisplayDate || state.narrativeDate;
  const meta = metaLabel
    ? `${metaLabel} · ${state.narrativeCycles || "?"} cycles`
    : "";
  if (!state.narrativeSections) {
    return [meta, state.narrativeText || ""].filter(Boolean).join("\n\n");
  }
  const sections = state.narrativeSections;
  const botLines = sections.bot_performance && typeof sections.bot_performance === "object"
    ? Object.entries(sections.bot_performance)
        .filter(([, text]) => text)
        .map(([bot, text]) => `${bot}: ${text}`)
        .join("\n")
    : (sections.bot_performance || "");
  return [
    meta,
    sections.tldr ? `TL;DR: ${sections.tldr}` : "",
    sections.highlight ? `Highlight: ${sections.highlight}` : "",
    botLines ? `Bot Performance:\n${botLines}` : "",
    sections.market_conditions ? `Market Conditions: ${sections.market_conditions}` : "",
    sections.operational_issues ? `Operational Issues: ${sections.operational_issues}` : "",
    sections.analysis ? `Analysis: ${sections.analysis}` : "",
    sections.bottom_line ? `Bottom Line: ${sections.bottom_line}` : "",
  ]
    .filter(Boolean)
    .join("\n\n");
}

function normalizeNarrativeSections(sections) {
  if (!sections || typeof sections !== "object") return null;
  return {
    tldr: sections.tldr || "",
    highlight: sections.highlight || "",
    bot_performance: sections.bot_performance || null,
    market_conditions: sections.market_conditions || "",
    operational_issues: sections.operational_issues || "",
    analysis: sections.analysis || "",
    bottom_line: sections.bottom_line || "",
  };
}

function legacyNarrativeText(text) {
  return (text || "")
    .split(/\n\n+/)
    .map((p) => p.trim())
    .filter(Boolean)
    .join("\n\n");
}

async function generateNarrative() {
  if (state.narrativeLoading) return;
  state.narrativeLoading = true;
  if (els.narrativeGenerate) {
    els.narrativeGenerate.textContent = "Generating…";
    els.narrativeGenerate.disabled = true;
  }
  if (els.narrativeContent) {
    els.narrativeContent.innerHTML =
      '<p class="narrative-loading">Generating session debrief…</p>';
  }
  try {
    const payload = { timeframe: state.narrativeTimeframe };
    if (state.narrativeTimeframe === "CUSTOM") {
      state.narrativeCustomStart =
        els.customStartDate?.value || state.narrativeCustomStart;
      state.narrativeCustomEnd =
        els.customEndDate?.value || state.narrativeCustomEnd;
      payload.start_date = state.narrativeCustomStart;
      payload.end_date = state.narrativeCustomEnd;
    }
    const data = await request("/api/summary", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.narrativeSections = normalizeNarrativeSections(data.narrative);
    state.narrativeDate = data.date;
    state.narrativeDisplayDate = data.display_date;
    state.narrativeCycles = data.cycle_count;
    state.narrativeText = state.narrativeSections
      ? narrativeCopyText()
      : legacyNarrativeText(data.summary);
    saveCurrentNarrativeToCache();
    renderNarrative();
  } catch (error) {
    if (els.narrativeContent) {
      els.narrativeContent.innerHTML = `<p class="narrative-empty">Error: ${escapeHtml(error.message)}</p>`;
    }
  } finally {
    state.narrativeLoading = false;
    updateNarrativeGenerateButton();
    if (els.narrativeGenerate) {
      els.narrativeGenerate.disabled = false;
    }
  }
}

function setupActivityLog() {
  loadNarrativeCache();
  setLogExpanded(loadLogExpanded());
  setLogCollapsed(loadLogCollapsed());
  if (els.activityCopy) {
    els.activityCopy.addEventListener("click", copyActivityLog);
  }
  if (els.activityToggle) {
    els.activityToggle.addEventListener("click", () => {
      setLogCollapsed(!state.logCollapsed);
    });
  }
  if (els.activityExpand) {
    els.activityExpand.addEventListener("click", () => {
      setLogExpanded(!state.logExpanded);
    });
  }
  if (els.activityTab) {
    els.activityTab.addEventListener("click", () => switchTab("activity"));
  }
  if (els.narrativeTab) {
    els.narrativeTab.addEventListener("click", () => switchTab("narrative"));
  }
  if (els.narrativeGenerate) {
    els.narrativeGenerate.addEventListener("click", generateNarrative);
  }

  document.querySelectorAll(".timeframe-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tf = btn.dataset.timeframe;
      if (!tf || tf === state.narrativeTimeframe) return;
      state.narrativeTimeframe = tf;
      renderNarrativeControls();
      restoreNarrativeForSelection();
    });
  });
  const syncCustomDates = () => {
    if (els.customStartDate) {
      state.narrativeCustomStart = els.customStartDate.value;
    }
    if (els.customEndDate) {
      state.narrativeCustomEnd = els.customEndDate.value;
    }
    restoreNarrativeForSelection();
  };
  if (els.customStartDate) {
    els.customStartDate.addEventListener("input", syncCustomDates);
    els.customStartDate.addEventListener("change", syncCustomDates);
  }
  if (els.customEndDate) {
    els.customEndDate.addEventListener("input", syncCustomDates);
    els.customEndDate.addEventListener("change", syncCustomDates);
  }
  renderNarrativeControls();
  restoreNarrativeForSelection();
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
    collecting_data: "Collecting Data",
    no_entry_signal: "No Entry Signal",
    close_stale_position_no_same_cycle_reversal: "Closed Stale Exposure",
    wait_for_stale_close: "Waiting For Stale Close",
    manage_open_position: "Managing Position",
    chop_exit_reclaim_slow_sma: "Chop Exit Reclaim",
    wait_for_chop_exit_order: "Waiting For Chop Exit",
    market_buy: "Market Buy",
    market_close_liquidation: "Closing Before Bell",
    closeout_window_no_position: "Flat Into Close",
    wait_for_closeout_order: "Waiting For Closeout",
    wait_for_open_order: "Waiting For Buy Order",
    wait_for_data: "Waiting For Data",
    wait_stale_market_data: "Stale Market Data",
    wait_stream_market_data: "Waiting For Stream",
    manage_open_position_stale_bars: "Live Risk On Stale Bars",
    insufficient_buying_power: "Insufficient Buying Power",
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
  els.activeBot.textContent = status.active_bot
    ? formatLabel(status.active_bot)
    : "None";
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
    const owner = status.position_owner
      ? `${formatLabel(status.position_owner)}, `
      : "";
    els.position.textContent = `${status.position_symbol} ${qty} (${owner}${marketValue})`;
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

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatOrderEventType(value) {
  const labels = {
    ORDER_ACCEPTED: "Accepted",
    ORDER_REJECTED: "Rejected",
    PARTIAL_FILL: "Partial Fill",
    FULL_FILL: "Full Fill",
  };
  return labels[value] || formatLabel(value || "event");
}

function formatOrderQty(value) {
  return formatQty(value) || value || "--";
}

function renderPendingOrder(order) {
  const side = order.side ? order.side.toUpperCase() : "--";
  const symbol = order.symbol || "--";
  const bot = order.bot ? formatLabel(order.bot) : "Unassigned";
  const reason = order.reason ? formatLabel(order.reason) : "Pending";
  const status = order.status ? formatLabel(order.status) : "Submitted";
  const filled = formatOrderQty(order.filled_qty);
  const updated = formatTime(order.updated_at || order.submitted_at, "--");
  return `
    <div class="order-row">
      <div>
        <strong>${escapeHtml(symbol)} ${escapeHtml(side)}</strong>
        <span>${escapeHtml(bot)} · ${escapeHtml(reason)}</span>
      </div>
      <div>
        <strong>${escapeHtml(status)}</strong>
        <span>${escapeHtml(filled)} filled · ${escapeHtml(updated)}</span>
      </div>
    </div>
  `;
}

function renderOrderEvent(event) {
  const side = event.side ? event.side.toUpperCase() : "--";
  const symbol = event.symbol || "--";
  const eventLabel = formatOrderEventType(event.event_type);
  const time = formatTime(event.created_at, "--");
  const qty = formatOrderQty(event.fill_delta_qty || event.filled_qty);
  const price = event.filled_avg_price ? ` @ ${formatPrice(event.filled_avg_price)}` : "";
  const reason = event.reason ? formatLabel(event.reason) : event.status || "Lifecycle";
  const detail =
    event.error ||
    `${qty}${price} · ${formatLabel(reason)}`;
  return `
    <div class="order-row">
      <div>
        <strong>${escapeHtml(eventLabel)}</strong>
        <span>${escapeHtml(symbol)} ${escapeHtml(side)} · ${escapeHtml(time)}</span>
      </div>
      <div>
        <strong>${escapeHtml(event.order_id || "--")}</strong>
        <span>${escapeHtml(detail)}</span>
      </div>
    </div>
  `;
}

function renderOrderState(orderState) {
  const pending = Array.isArray(orderState?.pending_orders)
    ? orderState.pending_orders
    : [];
  const events = Array.isArray(orderState?.recent_events)
    ? orderState.recent_events
    : [];
  const latestFill = orderState?.latest_fill || null;

  if (pending.length > 0) {
    els.orderSummary.textContent = `${pending.length} pending`;
    els.orderSummary.classList.remove("is-positive", "is-negative", "is-neutral");
    els.orderSummary.classList.add("data-warn");
  } else if (latestFill) {
    els.orderSummary.textContent = `Last fill ${formatOrderQty(
      latestFill.fill_delta_qty || latestFill.filled_qty,
    )}`;
    els.orderSummary.classList.remove("data-warn");
    els.orderSummary.classList.add("is-neutral");
  } else {
    els.orderSummary.textContent = "No pending orders";
    els.orderSummary.classList.remove("data-warn");
    els.orderSummary.classList.add("is-neutral");
  }

  els.pendingOrders.innerHTML = pending.length
    ? pending.map(renderPendingOrder).join("")
    : '<div class="order-empty">None</div>';
  els.orderEvents.innerHTML = events.length
    ? events.map(renderOrderEvent).join("")
    : '<div class="order-empty">No events</div>';
}

function logToneForLine(line) {
  const lower = line.toLowerCase();
  if (lower.includes("regime change")) {
    if (lower.includes("-> uptrend")) {
      return "log-green";
    }
    if (lower.includes("-> downtrend")) {
      return "log-red";
    }
    return "log-yellow";
  }
  if (lower.includes("[data] health")) {
    if (
      lower.includes("stale") ||
      lower.includes("disconnected") ||
      lower.includes("error")
    ) {
      return "log-red";
    }
    if (lower.includes("warming") || lower.includes("waiting")) {
      return "log-yellow";
    }
    return "log-green";
  }
  if (
    lower.includes("[error]") ||
    lower.includes("[fatal]") ||
    lower.includes("wait_stale_market_data") ||
    lower.includes("wait_stream_market_data") ||
    lower.includes("stale market data") ||
    lower.includes("stream market data is not live") ||
    lower.includes('"isstale": true') ||
    lower.includes("downtrend") ||
    lower.includes("stale exposure") ||
    lower.includes("selling") ||
    lower.includes("sell order") ||
    lower.includes("trailing stop breached") ||
    lower.includes("market_close_liquidation") ||
    lower.includes("closing before bell")
  ) {
    return "log-red";
  }
  if (
    lower.includes("regime=uptrend") ||
    lower.includes("[entry] confirmed") ||
    lower.includes("[entry] approved") ||
    lower.includes("fresh_cross_confirmed") ||
    lower.includes("trend_continuation_allowed") ||
    lower.includes("strong_trend_chase_allowed") ||
    lower.includes("market_buy") ||
    lower.includes("chop exit") ||
    lower.includes("chop_exit") ||
    lower.includes("entry signal detected") ||
    lower.includes("trailing stop holding") ||
    lower.includes("manage_open_position")
  ) {
    return "log-green";
  }
  if (
    lower.includes("regime=sideways") ||
    lower.includes("[entry] blocked") ||
    lower.includes("waiting") ||
    lower.includes("warmup") ||
    lower.includes("collecting_data") ||
    lower.includes("collecting data") ||
    lower.includes("market closed") ||
    lower.includes("no_entry") ||
    lower.includes("no entry") ||
    lower.includes("armed") ||
    lower.includes("closeout_window_no_position") ||
    lower.includes("flat into close")
  ) {
    return "log-yellow";
  }
  return "log-white";
}

function logClassesForLine(line) {
  const classes = ["log-line", logToneForLine(line)];
  const lower = line.toLowerCase();
  if (lower.includes("regime change")) {
    classes.push("log-transition");
  }
  if (line.startsWith("[")) {
    classes.push("log-tagged");
  }
  return classes.join(" ");
}

function renderLogLine(line) {
  return `<span class="${logClassesForLine(line)}">${escapeHtml(line) || "&nbsp;"}</span>`;
}

function renderLog(data) {
  const logText =
    data.activity_log && data.activity_log.length
      ? data.activity_log.join("\n")
      : data.last_output && data.last_output.length
      ? data.last_output.join("\n")
      : "Waiting for a run.";

  if (state.logText === logText) {
    return;
  }

  const previousHeight = els.log.scrollHeight;
  const previousTop = els.log.scrollTop;
  const wasNearBottom =
    previousHeight - previousTop - els.log.clientHeight < 48;

  els.log.innerHTML = logText.split("\n").map(renderLogLine).join("");
  state.logText = logText;

  if (!state.logHydrated || wasNearBottom) {
    els.log.scrollTop = els.log.scrollHeight;
  } else {
    els.log.scrollTop = previousTop + (els.log.scrollHeight - previousHeight);
  }

  state.logHydrated = true;
}

function render(data) {
  state.running = Boolean(data.running);
  const latestBuyingPower = buyingPowerFromData(data);
  if (latestBuyingPower !== null) {
    state.latestBuyingPower = latestBuyingPower;
  }
  hydrateForm(data);

  const waitingForOpen =
    state.running && data.next_run_reason === "market_open";
  els.statusPill.classList.toggle("is-running", state.running && !waitingForOpen);
  els.statusPill.classList.toggle("is-armed", waitingForOpen);
  els.statusText.textContent = waitingForOpen
    ? "Armed"
    : state.running
    ? "Online"
    : "Offline";
  els.statusPill.dataset.tooltip = waitingForOpen
    ? "The bot is armed and will resume when the regular market opens."
    : state.running
    ? "The repeating bot loop is running. It arms itself outside regular market hours."
    : "The repeating bot loop is stopped.";
  els.toggle.textContent = state.running ? "Turn Off" : "Turn On";
  els.toggle.dataset.tooltip = state.running
    ? "Stop the repeating bot loop after the current cycle."
    : "Start the repeating bot loop. If the market is closed, it will arm itself for the next open.";
  els.toggle.classList.toggle("is-stop", state.running);
  els.runOnce.disabled = state.running || state.busy;
  els.toggle.disabled = state.busy;
  settingInputs.forEach((input) => {
    input.disabled = state.running || state.busy;
  });
  syncSizingControls();

  const isDryRun = state.running ? Boolean(data.dry_run) : els.dryRun.checked;
  renderMode(isDryRun);
  renderDataHealth(data.edgewalker_status || data.market_data_status);
  renderBrokerState(data.broker_state);
  renderPerformance(data.performance);
  renderOrderState(data.order_state);
  els.lastRun.textContent = formatTime(data.last_run_at, "Never");
  els.nextRun.textContent = formatNextCheck(data);
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

if (els.symbol) {
  els.symbol.addEventListener("input", () => {
    els.symbol.value = els.symbol.value.toUpperCase();
  });
}

if (els.positionSizing) {
  els.positionSizing.addEventListener("change", () => {
    if (state.lastSizingValue === "FIXED" && els.notional.value) {
      state.fixedNotionalValue = els.notional.value;
    }
    state.lastSizingValue = els.positionSizing.value;
    if (els.positionSizing.value === "FIXED") {
      els.notional.value = state.fixedNotionalValue || "25";
    }
    syncSizingControls();
  });
}

if (els.notional) {
  els.notional.addEventListener("input", () => {
    if (!els.positionSizing || els.positionSizing.value === "FIXED") {
      state.fixedNotionalValue = els.notional.value;
    }
  });
}

els.dryRun.addEventListener("change", () => {
  renderMode(els.dryRun.checked);
});

if (els.themeToggle) {
  els.themeToggle.addEventListener("click", toggleTheme);
}

setupTheme();
setupOperatorGuide();
setupActivityLog();
setupTooltips();
refresh();
setInterval(refresh, 2000);
