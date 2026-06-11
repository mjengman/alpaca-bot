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
  latestAccountValue: null,
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
  narrativeCacheLoading: false,
  activeEnvironment: "paper",
  liveTradingArmed: false,
  liveCredentialsReady: false,
  audioscapeEnabled: false,
  audioHydrated: false,
  lastOrderFillSignature: null,
  lastInterventionSignature: null,
  lastPositionSignature: null,
  lastTrailingExitPrice: null,
  protectionPositionSignature: null,
  trailProtectionPlayed: false,
  dryRun: false,
  researchModeEnabled: false,
  researchBusy: false,
  researchProgressTimer: null,
  researchProgressStartedAt: null,
  researchProgressLabel: "",
  lastResearchResult: null,
  activeStrategyConfig: null,
  tooltipsSetup: false,
};

const THEME_KEY = "edgewalker-theme";
const AUDIOSCAPE_KEY = "edgewalker-audioscape-enabled";
const LOG_COLLAPSED_KEY = "edgewalker-log-collapsed";
const LOG_EXPANDED_KEY = "edgewalker-log-expanded";
const SECTION_COLLAPSED_PREFIX = "edgewalker-section-collapsed:";
const NARRATIVE_CACHE_KEY = "edgewalker-narrative-cache-v2";
const RESEARCH_PRESETS_KEY = "edgewalker-research-presets-v1";
const PRESET_AUTHORITY_MODE_KEY = "edgewalker-preset-authority-mode-v1";
const ACTIVE_STRATEGY_CONFIG_KEY = "edgewalker-active-strategy-config-v1";
const PRESET_AUTHORITY_MODE_V6 = "V6_0945";
const GO_LIVE_ROUTER_NAME = "Router_StrictAuthority_ChopFirewall";
const GO_LIVE_ROUTER_VERSION = "v3";
const REFRESH_INTERVAL_MS = 2000;
const API_BASE =
  window.location.protocol === "file:" ? "http://127.0.0.1:8765" : "";
const SOUND_BASE = `${API_BASE}/assets/sounds`;
const SOUND_LIBRARY = {
  uiClick: { file: "UI_click.wav", volume: 0.28 },
  botStarted: { file: "Bot_started.wav", volume: 0.42 },
  botDeactivated: { file: "Bot_deactivated.wav", volume: 0.42 },
  limitMovedUp: { file: "Limit_moved_up.wav", volume: 0.34 },
  trailProtected: { file: "Position_secured.wav", volume: 0.34 },
  orderFilled: { file: "Order_filled.wav", volume: 0.46 },
  positionClosed: { file: "Position_closed.wav", volume: 0.46 },
  humanIntervention: {
    file: "Error.wav",
    volume: 0.52,
  },
};
const INTERVENTION_BROKER_STATES = new Set([
  "RESTRICTED",
  "EXIT_BLOCKED",
  "BUYING_POWER_LIMITED",
]);

const els = {
  settingsMenuToggle: document.querySelector("#settingsMenuToggle"),
  settingsMenu: document.querySelector("#settingsMenu"),
  settingsOpen: document.querySelector("#settingsOpen"),
  settingsDialog: document.querySelector("#settingsDialog"),
  settingsClose: document.querySelector("#settingsClose"),
  settingsMessage: document.querySelector("#settingsMessage"),
  settingsSave: document.querySelector("#settingsSave"),
  operatorSpreadsheetOpen: document.querySelector("#operatorSpreadsheetOpen"),
  operatorSpreadsheetDialog: document.querySelector("#operatorSpreadsheetDialog"),
  operatorSpreadsheetClose: document.querySelector("#operatorSpreadsheetClose"),
  spreadsheetMessage: document.querySelector("#spreadsheetMessage"),
  spreadsheetSave: document.querySelector("#spreadsheetSave"),
  notificationsOpen: document.querySelector("#notificationsOpen"),
  notificationsDialog: document.querySelector("#notificationsDialog"),
  notificationsClose: document.querySelector("#notificationsClose"),
  notificationsMessage: document.querySelector("#notificationsMessage"),
  notificationsSave: document.querySelector("#notificationsSave"),
  notificationTest: document.querySelector("#notificationTest"),
  activeEnvironment: document.querySelector("#activeEnvironmentInput"),
  dataBaseUrl: document.querySelector("#dataBaseUrlInput"),
  dataFeed: document.querySelector("#dataFeedInput"),
  paperTradingUrl: document.querySelector("#paperTradingUrlInput"),
  paperApiKey: document.querySelector("#paperApiKeyInput"),
  paperApiSecret: document.querySelector("#paperApiSecretInput"),
  liveTradingUrl: document.querySelector("#liveTradingUrlInput"),
  liveApiKey: document.querySelector("#liveApiKeyInput"),
  liveApiSecret: document.querySelector("#liveApiSecretInput"),
  testPaperConnection: document.querySelector("#testPaperConnection"),
  testLiveConnection: document.querySelector("#testLiveConnection"),
  liveArmStatus: document.querySelector("#liveArmStatus"),
  liveArmInput: document.querySelector("#liveArmInput"),
  liveArmButton: document.querySelector("#liveArmButton"),
  liveDisarmButton: document.querySelector("#liveDisarmButton"),
  spreadsheetUrl: document.querySelector("#spreadsheetUrlInput"),
  spreadsheetPostEndpoint: document.querySelector("#spreadsheetPostEndpointInput"),
  researchSpreadsheetUrl: document.querySelector("#researchSpreadsheetUrlInput"),
  researchSpreadsheetPostEndpoint: document.querySelector(
    "#researchSpreadsheetPostEndpointInput",
  ),
  spreadsheetIncludeNarrative: document.querySelector(
    "#spreadsheetIncludeNarrativeInput",
  ),
  spreadsheetAutoPost: document.querySelector("#spreadsheetAutoPostInput"),
  spreadsheetOperatorNotes: document.querySelector("#spreadsheetOperatorNotesInput"),
  notificationsEnabled: document.querySelector("#notificationsEnabledInput"),
  notificationEmail: document.querySelector("#notificationEmailInput"),
  notificationAppsScriptUrl: document.querySelector(
    "#notificationAppsScriptUrlInput",
  ),
  notificationAppsScriptSecret: document.querySelector(
    "#notificationAppsScriptSecretInput",
  ),
  notificationErrorCooldown: document.querySelector(
    "#notificationErrorCooldownInput",
  ),
  notifyTradeEntered: document.querySelector("#notifyTradeEnteredInput"),
  notifyTradeExited: document.querySelector("#notifyTradeExitedInput"),
  notifyDailySummary: document.querySelector("#notifyDailySummaryInput"),
  notifyWarmup: document.querySelector("#notifyWarmupInput"),
  notifyDataErrors: document.querySelector("#notifyDataErrorsInput"),
  openOperatorSpreadsheet: document.querySelector("#openOperatorSpreadsheet"),
  openResearchSpreadsheet: document.querySelector("#openResearchSpreadsheet"),
  postSpreadsheetDailyRow: document.querySelector("#postSpreadsheetDailyRow"),
  operatorGuideOpen: document.querySelector("#operatorGuideOpen"),
  operatorGuideDialog: document.querySelector("#operatorGuideDialog"),
  operatorGuideClose: document.querySelector("#operatorGuideClose"),
  themeToggle: document.querySelector("#themeToggle"),
  audioscapeToggle: document.querySelector("#audioscapeToggle"),
  researchMode: document.querySelector("#researchModeInput"),
  statusPill: document.querySelector("#statusPill"),
  statusText: document.querySelector("#statusText"),
  symbol: document.querySelector("#symbolInput"),
  notional: document.querySelector("#notionalInput"),
  positionSizing: document.querySelector("#positionSizingInput"),
  customAllocationField: document.querySelector("#customAllocationField"),
  customAllocation: document.querySelector("#customAllocationInput"),
  trail: document.querySelector("#trailInput"),
  poll: document.querySelector("#pollInput"),
  closeout: document.querySelector("#closeoutInput"),
  regimeGap: document.querySelector("#regimeGapInput"),
  regimeExitGap: document.querySelector("#regimeExitGapInput"),
  chopDiscount: document.querySelector("#chopDiscountInput"),
  directionalModes: document.querySelectorAll('input[name="directionalMode"]'),
  presetAuthorityMode: document.querySelector("#presetAuthorityModeInput"),
  directionalMaxExtension: document.querySelector("#directionalMaxExtensionInput"),
  directionalStrongChase: document.querySelector("#directionalStrongChaseInput"),
  directionalMinStrength: document.querySelector("#directionalMinStrengthInput"),
  directionalCooldown: document.querySelector("#directionalCooldownInput"),
  adaptiveShadow: document.querySelector("#adaptiveShadowInput"),
  adaptiveShadowLabel: document.querySelector("#adaptiveShadowInput")
    ?.closest(".switch")
    ?.querySelector(".switch-label"),
  fast: document.querySelector("#fastInput"),
  slow: document.querySelector("#slowInput"),
  dryRun: document.querySelector("#dryRunInput"),
  controlsActionRow: document.querySelector("#controlsActionRow"),
  researchControls: document.querySelector("#researchControls"),
  researchMessage: document.querySelector("#researchMessage"),
  researchProgress: document.querySelector("#researchProgress"),
  researchProgressText: document.querySelector("#researchProgressText"),
  backtestDate: document.querySelector("#backtestDateInput"),
  backtestFeed: document.querySelector("#backtestFeedInput"),
  backtestStartingAccount: document.querySelector("#backtestStartingAccountInput"),
  backtestFillModel: document.querySelector("#backtestFillModelInput"),
  backtestSlippage: document.querySelector("#backtestSlippageInput"),
  backtestPresetName: document.querySelector("#backtestPresetNameInput"),
  backtestPresetVersion: document.querySelector("#backtestPresetVersionInput"),
  researchPresetLibrary: document.querySelector("#researchPresetLibraryInput"),
  researchPresetNotes: document.querySelector("#researchPresetNotesInput"),
  researchCompareDates: document.querySelector("#researchCompareDatesInput"),
  researchComparePresets: document.querySelector("#researchComparePresetsInput"),
  selectAllResearchComparePresets: document.querySelector(
    "#selectAllResearchComparePresetsButton",
  ),
  seedChopResearchPresets: document.querySelector("#seedChopResearchPresetsButton"),
  seedMomentumResearchPresets: document.querySelector(
    "#seedMomentumResearchPresetsButton",
  ),
  seedCombinedResearchPresets: document.querySelector(
    "#seedCombinedResearchPresetsButton",
  ),
  saveResearchPreset: document.querySelector("#saveResearchPresetButton"),
  loadResearchPreset: document.querySelector("#loadResearchPresetButton"),
  deleteResearchPreset: document.querySelector("#deleteResearchPresetButton"),
  runBacktest: document.querySelector("#runBacktestButton"),
  runResearchCompare: document.querySelector("#runResearchCompareButton"),
  runShadowRouter: document.querySelector("#runShadowRouterButton"),
  researchResults: document.querySelector("#researchResults"),
  applyGoLiveRouter: document.querySelector("#applyGoLiveRouterButton"),
  liveStrategyBadge: document.querySelector("#liveStrategyBadge"),
  runOnce: document.querySelector("#runOnceButton"),
  toggle: document.querySelector("#toggleButton"),
  edgeRunState: document.querySelector("#edgeRunStateValue"),
  positionSizeSummary: document.querySelector("#positionSizeSummaryValue"),
  mode: document.querySelector("#modeValue"),
  dataStatus: document.querySelector("#dataStatusValue"),
  brokerState: document.querySelector("#brokerStateValue"),
  priorClose: document.querySelector("#priorCloseValue"),
  adaptive: document.querySelector("#adaptiveValue"),
  sessionRealizedPl: document.querySelector("#sessionRealizedPlValue"),
  sessionTrades: document.querySelector("#sessionTradesValue"),
  botPerformanceSummary: document.querySelector("#botPerformanceSummaryValue"),
  botPerformanceGrid: document.querySelector("#botPerformanceGrid"),
  lastRun: document.querySelector("#lastRunValue"),
  nextRun: document.querySelector("#nextRunValue"),
  regime: document.querySelector("#regimeValue"),
  activeBot: document.querySelector("#activeBotValue"),
  routedSymbol: document.querySelector("#routedSymbolValue"),
  action: document.querySelector("#actionValue"),
  actionReason: document.querySelector("#actionReasonValue"),
  authority: document.querySelector("#authorityValue"),
  portfolio: document.querySelector("#portfolioValue"),
  dayPl: document.querySelector("#dayPlValue"),
  buyingPower: document.querySelector("#buyingPowerValue"),
  sourcePrice: document.querySelector("#sourcePriceValue"),
  inversePrice: document.querySelector("#inversePriceValue"),
  gap: document.querySelector("#gapValue"),
  position: document.querySelector("#positionValue"),
  positionPl: document.querySelector("#positionPlValue"),
  maxLossLabel: document.querySelector("#maxLossLabel"),
  maxLoss: document.querySelector("#maxLossValue"),
  entryPrice: document.querySelector("#entryPriceValue"),
  trailExit: document.querySelector("#trailExitValue"),
  orderSummary: document.querySelector("#orderSummaryValue"),
  orderEvents: document.querySelector("#orderEventsList"),
  error: document.querySelector("#errorText"),
  activityPanel: document.querySelector("#activityPanel"),
  activityTab: document.querySelector("#activityTab"),
  narrativeTab: document.querySelector("#narrativeTab"),
  activityCopy: document.querySelector("#activityCopy"),
  activityCopyLabel: document.querySelector("#activityCopyLabel"),
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
  els.customAllocation,
  els.trail,
  els.poll,
  els.closeout,
  els.regimeGap,
  els.regimeExitGap,
  els.chopDiscount,
  ...els.directionalModes,
  els.presetAuthorityMode,
  els.directionalMaxExtension,
  els.directionalStrongChase,
  els.directionalMinStrength,
  els.directionalCooldown,
  els.adaptiveShadow,
  els.fast,
  els.slow,
  els.dryRun,
].filter(Boolean);

const sizingControlInputs = new Set(
  [els.notional, els.positionSizing, els.customAllocation].filter(Boolean),
);

const lockedStrategyInputs = settingInputs.filter(
  (input) => !sizingControlInputs.has(input),
);

const tooltipBubble = document.createElement("div");
tooltipBubble.className = "tooltip-bubble";
tooltipBubble.setAttribute("role", "tooltip");
tooltipBubble.setAttribute("aria-hidden", "true");
document.body.appendChild(tooltipBubble);

const soundCache = new Map();

function strategyControlsPayload() {
  const selectedDirectionalMode =
    [...els.directionalModes].find((input) => input.checked)?.value || "BALANCED";
  const sizingValue = els.positionSizing ? els.positionSizing.value : "FIXED";
  const positionSizingMode = sizingValue === "FIXED" ? "FIXED" : "DYNAMIC";
  const positionAllocationPercent =
    sizingValue === "FIXED" ? "25" : selectedAllocationPercent();
  if (positionSizingMode === "DYNAMIC") {
    validateAllocationPercent(positionAllocationPercent);
  }
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
    adaptiveShadowEnabled: els.adaptiveShadow ? els.adaptiveShadow.checked : true,
    fastSmaMinutes: els.fast.value,
    slowSmaMinutes: els.slow.value,
    dryRun: state.dryRun,
  };
}

function payloadFromForm() {
  return {
    ...(state.activeStrategyConfig || {}),
    ...strategyControlsPayload(),
    ...presetAuthorityPayload(),
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
  return "CUSTOM";
}

function buyingPowerFromData(data) {
  const value = data.edgewalker_status?.buying_power ?? null;
  return numberOrNull(value);
}

function accountValueFromData(data) {
  const value =
    data.edgewalker_status?.portfolio_value ??
    data.edgewalker_status?.account_value ??
    null;
  return numberOrNull(value);
}

function formatResearchAccountValue(value) {
  const parsed = numberOrNull(value);
  if (parsed === null) {
    return "";
  }
  return parsed.toFixed(2);
}

function syncResearchStartingAccount({ force = false } = {}) {
  if (!els.backtestStartingAccount) {
    return;
  }
  const isInitialDefault =
    els.backtestStartingAccount.value === "100" &&
    els.backtestStartingAccount.dataset.autoValue !== "false";
  if (
    document.activeElement === els.backtestStartingAccount ||
    (!force &&
      els.backtestStartingAccount.value &&
      !isInitialDefault &&
      els.backtestStartingAccount.dataset.autoValue !== "true")
  ) {
    return;
  }
  const value = state.latestAccountValue ?? state.latestBuyingPower;
  if (value !== null) {
    els.backtestStartingAccount.value = formatResearchAccountValue(value);
    els.backtestStartingAccount.dataset.autoValue = "true";
  }
}

function dynamicNotionalPreview() {
  if (!els.positionSizing || els.positionSizing.value === "FIXED") {
    return null;
  }
  const buyingPower = state.latestBuyingPower;
  const allocation = numberOrNull(selectedAllocationPercent());
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
  const customSizing = els.positionSizing.value === "CUSTOM";
  if (els.customAllocationField) {
    els.customAllocationField.hidden = !customSizing;
  }
  if (els.customAllocation) {
    els.customAllocation.disabled = state.running || state.busy || !customSizing;
  }
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
  renderPositionSizeSummary();
}

function selectedAllocationPercent() {
  if (!els.positionSizing || els.positionSizing.value === "FIXED") {
    return "25";
  }
  if (els.positionSizing.value === "CUSTOM") {
    return els.customAllocation?.value.trim() || "";
  }
  return els.positionSizing.value;
}

function renderPositionSizeSummary(status = null) {
  if (!els.positionSizeSummary || !els.positionSizing) {
    return;
  }
  const mode = els.positionSizing.value;
  const effectiveNotional =
    status?.effective_position_notional !== undefined
      ? status.effective_position_notional
      : dynamicNotionalPreview();
  if (mode === "FIXED") {
    els.positionSizeSummary.textContent = `${formatMoney(els.notional.value)} fixed`;
    return;
  }
  const allocation = selectedAllocationPercent();
  const dollars = formatMoney(effectiveNotional);
  els.positionSizeSummary.textContent =
    effectiveNotional === null || effectiveNotional === undefined
      ? `${allocation}% BP`
      : `${allocation}% BP · ${dollars}`;
}

function validateAllocationPercent(value) {
  const parsed = numberOrNull(value);
  if (parsed === null || parsed <= 0 || parsed > 100) {
    throw new Error("Sizing percent must be greater than 0 and at most 100.");
  }
}

function researchPresetId(name, version) {
  return `${name.trim()}::${(version || "v1").trim()}`;
}

function readResearchPresets() {
  try {
    const raw = localStorage.getItem(RESEARCH_PRESETS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed)
      ? parsed.filter((preset) => preset && preset.id && preset.name)
      : [];
  } catch {
    return [];
  }
}

function presetRoleForName(name) {
  const text = String(name || "").toLowerCase();
  if (text.includes("general")) return "generalist";
  if (text.includes("momentum")) return "momentum";
  if (text.includes("inverse")) return "inverse";
  return null;
}

function authorityLeadPresets() {
  const roles = {};
  readResearchPresets().forEach((preset) => {
    const role = presetRoleForName(preset.name);
    if (role && !roles[role]) {
      roles[role] = preset;
    }
  });
  return roles;
}

function presetAuthorityPayload() {
  const mode = els.presetAuthorityMode?.value || "OFF";
  if (mode !== PRESET_AUTHORITY_MODE_V6) {
    return {
      presetAuthorityMode: "OFF",
      presetAuthorityPresets: [],
    };
  }

  const roles = authorityLeadPresets();
  const missing = ["generalist", "momentum", "inverse"].filter(
    (role) => !roles[role],
  );
  if (missing.length) {
    throw new Error(
      `v6 authority needs saved Lead presets for: ${missing.join(", ")}.`,
    );
  }

  return {
    presetAuthorityMode: PRESET_AUTHORITY_MODE_V6,
    presetAuthorityPresets: ["generalist", "momentum", "inverse"].map((role) => {
      const preset = roles[role];
      return {
        role,
        name: preset.name,
        version: preset.version || "v1",
        config: preset.config || {},
      };
    }),
  };
}

function syncPresetAuthorityBaseConfig() {
  if (!els.presetAuthorityMode || els.presetAuthorityMode.value !== PRESET_AUTHORITY_MODE_V6) {
    return false;
  }
  if (state.running || state.busy) {
    return false;
  }
  const roles = authorityLeadPresets();
  if (!roles.generalist?.config) {
    return false;
  }
  applyStrategyConfig(roles.generalist.config);
  return true;
}

function setupPresetAuthorityMode() {
  if (!els.presetAuthorityMode) return;
  const saved = localStorage.getItem(PRESET_AUTHORITY_MODE_KEY);
  if (saved === PRESET_AUTHORITY_MODE_V6) {
    els.presetAuthorityMode.value = PRESET_AUTHORITY_MODE_V6;
  }
  els.presetAuthorityMode.addEventListener("change", () => {
    localStorage.setItem(PRESET_AUTHORITY_MODE_KEY, els.presetAuthorityMode.value);
    const synced = syncPresetAuthorityBaseConfig();
    if (synced) {
      setResearchMessage(
        "v6 authority loaded Lead_Generalist into Strategy Controls. Momentum and Inverse remain in the authority bundle.",
        "success",
      );
    }
  });
}

function goLiveRouterFirewallConfig() {
  const current = strategyControlsPayload();
  return {
    ...current,
    presetName: GO_LIVE_ROUTER_NAME,
    presetVersion: GO_LIVE_ROUTER_VERSION,
    presetAuthorityMode: "OFF",
    presetAuthorityPresets: [],
    positionSizingMode: "DYNAMIC",
    positionAllocationPercent: "25",
    enabledBots: ["MomentumBot", "ChopBot", "InverseBot"],
    directionalMode: "BALANCED",
    directionalMaxExtensionPercent: "0.40",
    directionalStrongChaseMaxExtensionPercent: "1.00",
    directionalMinStrength: "MODERATE",
    directionalCooldownMinutes: "4",
    regimeGapThreshold: "0.20",
    regimeExitGapThreshold: "0.10",
    fastSmaMinutes: "5",
    slowSmaMinutes: "20",
    trailPercent: "1.50",
    momentumAuthorityRequired: true,
    momentumAuthorityRevokeExits: true,
    momentumAuthorityLatchOnceActive: false,
    momentumAuthorityMinTrustScore: "66",
    momentumAuthorityMinSourcePercent: "4.00",
    momentumAuthorityMaxTransitionsPerHour: "8",
    momentumAuthorityReclaimEnabled: false,
    momentumAuthorityReclaimMinTrustScore: "58",
    momentumAuthorityReclaimMinSourcePercent: "4.00",
    momentumAuthorityReclaimMaxRawTransitionCount: "1",
    momentumAuthorityReclaimMaxNonWarmupTransitionCount: "0",
    momentumAuthorityReclaimStartMinutes: "60",
    momentumAuthorityReclaimEndMinutes: "60",
    chopEntryDiscountPercent: "0.35",
    chopPermissionMode: "FIREWALL",
    chopPermissionMaxAbsSourcePercent: "2.00",
    inverseCascadeMode: "SUSTAINED",
    v9ObserverContext: {
      observer_preset: "BalancedPure_LiveObserver",
      runtime_observer: true,
      execution_rights: "none",
    },
    v10ForceNoAuthority: false,
  };
}

function writeActiveStrategyConfig(config) {
  state.activeStrategyConfig = config && typeof config === "object" ? config : null;
  try {
    if (state.activeStrategyConfig) {
      localStorage.setItem(
        ACTIVE_STRATEGY_CONFIG_KEY,
        JSON.stringify(state.activeStrategyConfig),
      );
    } else {
      localStorage.removeItem(ACTIVE_STRATEGY_CONFIG_KEY);
    }
  } catch {
    setResearchMessage("Could not persist the active live build in this browser.", "warning");
  }
  syncActiveStrategyBadge();
}

function readActiveStrategyConfig() {
  try {
    const raw = localStorage.getItem(ACTIVE_STRATEGY_CONFIG_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

function syncActiveStrategyBadge() {
  if (!els.liveStrategyBadge) return;
  const activeName = state.activeStrategyConfig?.presetName;
  els.liveStrategyBadge.classList.toggle("is-active", Boolean(activeName));
  els.liveStrategyBadge.textContent = activeName
    ? `${activeName} · CP-FW`
    : "Manual controls";
  els.liveStrategyBadge.dataset.tooltip = activeName
    ? "Turn On will post the validated StrictAuthority plus ChopFirewall router payload."
    : "Turn On will post only the visible manual Strategy Controls plus any selected authority mode.";
}

function setupActiveStrategyConfig() {
  const saved = readActiveStrategyConfig();
  if (!saved) {
    syncActiveStrategyBadge();
    return;
  }
  state.activeStrategyConfig = saved;
  applyStrategyConfig(saved);
  syncActiveStrategyBadge();
}

function applyGoLiveRouterFirewall() {
  const config = goLiveRouterFirewallConfig();
  if (els.presetAuthorityMode) {
    els.presetAuthorityMode.value = "OFF";
    localStorage.setItem(PRESET_AUTHORITY_MODE_KEY, "OFF");
  }
  applyStrategyConfig(config);
  writeActiveStrategyConfig(config);
  setResearchMessage(
    "Go-live build applied: StrictAuthority Momentum plus ChopFirewall Router. Turn On when ready.",
    "success",
  );
}

function writeResearchPresets(presets) {
  try {
    localStorage.setItem(RESEARCH_PRESETS_KEY, JSON.stringify(presets));
  } catch {
    setResearchMessage("Could not save preset library in this browser.", "danger");
  }
}

function chopResearchBaseConfig() {
  const roles = authorityLeadPresets();
  const sourceConfig = roles.generalist?.config || payloadFromForm();
  const base = { ...sourceConfig };
  delete base.dryRun;
  return {
    ...base,
    positionSizingMode: "FIXED",
    positionNotional: "25",
    positionAllocationPercent: "25",
    presetAuthorityMode: "OFF",
    presetAuthorityPresets: [],
    enabledBots: ["ChopBot"],
    directionalMode: "CONSERVATIVE",
    chopPermissionMode: "OFF",
    chopPermissionMaxAbsSourcePercent: "2.00",
    momentumAuthorityMinTrustScore: "66",
    momentumAuthorityMinSourcePercent: "4.00",
    momentumAuthorityMaxTransitionsPerHour: "8",
    v10ForceNoAuthority: false,
  };
}

function chopResearchCandidatePresets() {
  const base = chopResearchBaseConfig();
  const savedAt = new Date().toISOString();
  const definitions = [
    {
      name: "Chop_Ungated",
      notes:
        "Round 4 Chop permission baseline: Chop_Gap020 with no permission gate, used to measure raw ChopBot damage.",
      overrides: {
        chopEntryDiscountPercent: "0.35",
        trailPercent: "1.10",
        regimeGapThreshold: "0.20",
        regimeExitGapThreshold: "0.08",
        directionalCooldownMinutes: "4",
        fastSmaMinutes: "5",
        slowSmaMinutes: "20",
        chopPermissionMode: "OFF",
      },
    },
    {
      name: "Chop_Gated_Loose",
      notes:
        "Round 4 Chop permission candidate: Chop_Gap020 trades only when strict Momentum authority is inactive and dirty-tape drawdown context is absent.",
      overrides: {
        chopEntryDiscountPercent: "0.35",
        trailPercent: "1.10",
        regimeGapThreshold: "0.20",
        regimeExitGapThreshold: "0.08",
        directionalCooldownMinutes: "4",
        fastSmaMinutes: "5",
        slowSmaMinutes: "20",
        chopPermissionMode: "LOOSE",
      },
    },
    {
      name: "Chop_Gated_Strict",
      notes:
        "Round 4 Chop permission candidate: Loose gate plus first-30m raw transitions must be zero and live SOXL must stay within a +/-2.00% non-directional band.",
      overrides: {
        chopEntryDiscountPercent: "0.35",
        trailPercent: "1.10",
        regimeGapThreshold: "0.20",
        regimeExitGapThreshold: "0.08",
        directionalCooldownMinutes: "4",
        fastSmaMinutes: "5",
        slowSmaMinutes: "20",
        chopPermissionMode: "STRICT",
        chopPermissionMaxAbsSourcePercent: "2.00",
      },
    },
  ];

  return definitions.map((definition) => {
    const version = "v4";
    return {
      id: researchPresetId(definition.name, version),
      name: definition.name,
      version,
      notes: definition.notes,
      saved_at: savedAt,
      config: {
        ...base,
        ...definition.overrides,
      },
    };
  });
}

function momentumResearchBaseConfig() {
  const roles = authorityLeadPresets();
  const sourceConfig =
    roles.momentum?.config || roles.generalist?.config || payloadFromForm();
  const base = { ...sourceConfig };
  delete base.dryRun;
  return {
    ...base,
    positionSizingMode: "FIXED",
    positionNotional: "25",
    positionAllocationPercent: "25",
    presetAuthorityMode: "OFF",
    presetAuthorityPresets: [],
    enabledBots: ["MomentumBot"],
    momentumAuthorityRequired: false,
    momentumAuthorityRevokeExits: false,
    momentumAuthorityLatchOnceActive: false,
    momentumAuthorityMinTrustScore: "45",
    momentumAuthorityMinSourcePercent: "2.00",
    momentumAuthorityMaxTransitionsPerHour: "8",
    momentumAuthorityReclaimEnabled: false,
    momentumAuthorityReclaimMinTrustScore: "58",
    momentumAuthorityReclaimMinSourcePercent: "4.00",
    momentumAuthorityReclaimMaxRawTransitionCount: "1",
    momentumAuthorityReclaimMaxNonWarmupTransitionCount: "0",
    momentumAuthorityReclaimStartMinutes: "45",
    momentumAuthorityReclaimEndMinutes: "60",
    chopEntryDiscountPercent: "0.35",
    v10ForceNoAuthority: false,
  };
}

function momentumResearchCandidatePresets() {
  const base = momentumResearchBaseConfig();
  const savedAt = new Date().toISOString();
  const definitions = [
    {
      name: "Momentum_BalancedTight_CurrentV10",
      notes:
        "Round 7 baseline: BalancedTight executable MomentumBot with the current v10 authority behavior.",
      overrides: {
        directionalMode: "BALANCED",
        directionalMaxExtensionPercent: "0.40",
        directionalStrongChaseMaxExtensionPercent: "1.00",
        directionalMinStrength: "MODERATE",
        directionalCooldownMinutes: "4",
        regimeGapThreshold: "0.20",
        regimeExitGapThreshold: "0.10",
        fastSmaMinutes: "5",
        slowSmaMinutes: "20",
        trailPercent: "1.50",
        momentumAuthorityRequired: false,
        momentumAuthorityRevokeExits: false,
        momentumAuthorityLatchOnceActive: false,
        momentumAuthorityMinTrustScore: "45",
        momentumAuthorityMinSourcePercent: "2.00",
        momentumAuthorityMaxTransitionsPerHour: "8",
        momentumAuthorityReclaimEnabled: false,
        v10ForceNoAuthority: false,
      },
    },
    {
      name: "Momentum_BalancedTight_Permission",
      notes:
        "Round 7 executable baseline: BalancedTight can trade only while Momentum authority is active, with dirty-tape revoke exits enabled.",
      overrides: {
        directionalMode: "BALANCED",
        directionalMaxExtensionPercent: "0.40",
        directionalStrongChaseMaxExtensionPercent: "1.00",
        directionalMinStrength: "MODERATE",
        directionalCooldownMinutes: "4",
        regimeGapThreshold: "0.20",
        regimeExitGapThreshold: "0.10",
        fastSmaMinutes: "5",
        slowSmaMinutes: "20",
        trailPercent: "1.50",
        momentumAuthorityRequired: true,
        momentumAuthorityRevokeExits: true,
        momentumAuthorityLatchOnceActive: false,
        momentumAuthorityMinTrustScore: "45",
        momentumAuthorityMinSourcePercent: "2.00",
        momentumAuthorityMaxTransitionsPerHour: "8",
        momentumAuthorityReclaimEnabled: false,
        v10ForceNoAuthority: false,
      },
    },
    {
      name: "Momentum_BalancedTight_StrictAuthority",
      notes:
        "Round 7 incumbent: BalancedTight requires active Momentum authority plus stronger observer trust and a larger SOXL reclaim before trading, with revoke exits enabled.",
      overrides: {
        directionalMode: "BALANCED",
        directionalMaxExtensionPercent: "0.40",
        directionalStrongChaseMaxExtensionPercent: "1.00",
        directionalMinStrength: "MODERATE",
        directionalCooldownMinutes: "4",
        regimeGapThreshold: "0.20",
        regimeExitGapThreshold: "0.10",
        fastSmaMinutes: "5",
        slowSmaMinutes: "20",
        trailPercent: "1.50",
        momentumAuthorityRequired: true,
        momentumAuthorityRevokeExits: true,
        momentumAuthorityLatchOnceActive: false,
        momentumAuthorityMinTrustScore: "66",
        momentumAuthorityMinSourcePercent: "4.00",
        momentumAuthorityMaxTransitionsPerHour: "8",
        momentumAuthorityReclaimEnabled: false,
        v10ForceNoAuthority: false,
      },
    },
    {
      name: "Momentum_BalancedTight_StrictReclaim",
      notes:
        "Round 7 reclaim probe: start from StrictAuthority, then allow a 10:30 retry only if live SOXL has reclaimed, first-30m noise stayed clean, and no non-warmup flip appeared by reclaim time.",
      overrides: {
        directionalMode: "BALANCED",
        directionalMaxExtensionPercent: "0.40",
        directionalStrongChaseMaxExtensionPercent: "1.00",
        directionalMinStrength: "MODERATE",
        directionalCooldownMinutes: "4",
        regimeGapThreshold: "0.20",
        regimeExitGapThreshold: "0.10",
        fastSmaMinutes: "5",
        slowSmaMinutes: "20",
        trailPercent: "1.50",
        momentumAuthorityRequired: true,
        momentumAuthorityRevokeExits: true,
        momentumAuthorityLatchOnceActive: false,
        momentumAuthorityMinTrustScore: "66",
        momentumAuthorityMinSourcePercent: "4.00",
        momentumAuthorityMaxTransitionsPerHour: "8",
        momentumAuthorityReclaimEnabled: true,
        momentumAuthorityReclaimMinTrustScore: "58",
        momentumAuthorityReclaimMinSourcePercent: "4.00",
        momentumAuthorityReclaimMaxRawTransitionCount: "1",
        momentumAuthorityReclaimMaxNonWarmupTransitionCount: "0",
        momentumAuthorityReclaimStartMinutes: "60",
        momentumAuthorityReclaimEndMinutes: "60",
        v10ForceNoAuthority: false,
      },
    },
    {
      name: "Momentum_BalancedPure_Shadow",
      notes:
        "Round 7 shadow probe: raw BalancedPure signal is preserved for diagnostics without execution authority.",
      overrides: {
        directionalMode: "BALANCED",
        directionalMaxExtensionPercent: "0.50",
        directionalStrongChaseMaxExtensionPercent: "1.00",
        directionalMinStrength: "MODERATE",
        directionalCooldownMinutes: "4",
        regimeGapThreshold: "0.20",
        regimeExitGapThreshold: "0.10",
        fastSmaMinutes: "5",
        slowSmaMinutes: "20",
        trailPercent: "1.50",
        momentumAuthorityRequired: true,
        momentumAuthorityRevokeExits: false,
        momentumAuthorityLatchOnceActive: false,
        momentumAuthorityMinTrustScore: "45",
        momentumAuthorityMinSourcePercent: "2.00",
        momentumAuthorityMaxTransitionsPerHour: "8",
        momentumAuthorityReclaimEnabled: false,
        v10ForceNoAuthority: true,
      },
    },
  ];

  return definitions.map((definition) => {
    const version = "v7";
    return {
      id: researchPresetId(definition.name, version),
      name: definition.name,
      version,
      notes: definition.notes,
      saved_at: savedAt,
      config: {
        ...base,
        ...definition.overrides,
      },
    };
  });
}

function combinedRouterValidationBaseConfig() {
  const roles = authorityLeadPresets();
  const sourceConfig =
    roles.momentum?.config || roles.generalist?.config || payloadFromForm();
  const base = { ...sourceConfig };
  delete base.dryRun;
  return {
    ...base,
    positionSizingMode: "FIXED",
    positionNotional: "25",
    positionAllocationPercent: "25",
    presetAuthorityMode: "OFF",
    presetAuthorityPresets: [],
    directionalMode: "BALANCED",
    directionalMaxExtensionPercent: "0.40",
    directionalStrongChaseMaxExtensionPercent: "1.00",
    directionalMinStrength: "MODERATE",
    directionalCooldownMinutes: "4",
    regimeGapThreshold: "0.20",
    regimeExitGapThreshold: "0.10",
    fastSmaMinutes: "5",
    slowSmaMinutes: "20",
    trailPercent: "1.50",
    momentumAuthorityRequired: true,
    momentumAuthorityRevokeExits: true,
    momentumAuthorityLatchOnceActive: false,
    momentumAuthorityMinTrustScore: "66",
    momentumAuthorityMinSourcePercent: "4.00",
    momentumAuthorityMaxTransitionsPerHour: "8",
    momentumAuthorityReclaimEnabled: false,
    chopEntryDiscountPercent: "0.35",
    chopPermissionMode: "FIREWALL",
    chopPermissionMaxAbsSourcePercent: "2.00",
    v10ForceNoAuthority: false,
  };
}

function combinedRouterValidationPresets() {
  const base = combinedRouterValidationBaseConfig();
  const savedAt = new Date().toISOString();
  const definitions = [
    {
      name: "Generalist_BalancedPure_Observer",
      notes:
        "Combined Router validation observer: BalancedPure telemetry source only, with execution suppressed.",
      overrides: {
        enabledBots: ["MomentumBot"],
        directionalMode: "BALANCED",
        directionalMaxExtensionPercent: "0.50",
        directionalStrongChaseMaxExtensionPercent: "1.00",
        directionalMinStrength: "MODERATE",
        directionalCooldownMinutes: "4",
        regimeGapThreshold: "0.20",
        regimeExitGapThreshold: "0.10",
        fastSmaMinutes: "5",
        slowSmaMinutes: "20",
        trailPercent: "1.50",
        momentumAuthorityRequired: true,
        momentumAuthorityRevokeExits: false,
        momentumAuthorityLatchOnceActive: false,
        momentumAuthorityMinTrustScore: "45",
        momentumAuthorityMinSourcePercent: "2.00",
        momentumAuthorityMaxTransitionsPerHour: "8",
        momentumAuthorityReclaimEnabled: false,
        chopPermissionMode: "OFF",
        v10ForceNoAuthority: true,
      },
    },
    {
      name: "Router_StrictAuthority_ChopFirewall",
      notes:
        "Combined Router validation: MomentumBot uses BalancedTight StrictAuthority; ChopBot uses Chop_Gap020 with the dirty-tape firewall gate; InverseBot uses sustained cascade mode; BalancedPure remains observer-only.",
      overrides: {
        enabledBots: ["MomentumBot", "ChopBot", "InverseBot"],
        chopPermissionMode: "FIREWALL",
        inverseCascadeMode: "SUSTAINED",
      },
    },
    {
      name: "Momentum_StrictAuthority_Only",
      notes:
        "Combined Router validation control: MomentumBot BalancedTight StrictAuthority only, with ChopBot disabled.",
      overrides: {
        enabledBots: ["MomentumBot"],
        chopPermissionMode: "OFF",
      },
    },
  ];

  return definitions.map((definition) => {
    const version = "v3";
    return {
      id: researchPresetId(definition.name, version),
      name: definition.name,
      version,
      notes: definition.notes,
      saved_at: savedAt,
      config: {
        ...base,
        ...definition.overrides,
      },
    };
  });
}

function seedResearchCandidatePresets(candidates, successMessage) {
  const candidateIds = new Set(candidates.map((preset) => preset.id));
  const candidateNames = new Set(candidates.map((preset) => preset.name));
  const presets = readResearchPresets().filter(
    (preset) => !candidateIds.has(preset.id) && !candidateNames.has(preset.name),
  );
  presets.push(...candidates);
  presets.sort((a, b) => `${a.name} ${a.version}`.localeCompare(`${b.name} ${b.version}`));
  writeResearchPresets(presets);
  renderResearchPresetLibrary(candidates[0]?.id || "");
  if (els.researchComparePresets) {
    Array.from(els.researchComparePresets.options).forEach((option) => {
      option.selected = candidateIds.has(option.value);
    });
  }
  syncResearchPresetButtons();
  setResearchMessage(successMessage, "success");
}

function seedChopResearchPresets() {
  let candidates;
  try {
    candidates = chopResearchCandidatePresets();
  } catch (error) {
    setResearchMessage(error.message, "danger");
    return;
  }
  seedResearchCandidatePresets(
    candidates,
    "Seeded and selected 3 Round 4 Chop permission candidates. Run them across 20 dates for 60 replays plus Flat control.",
  );
}

function seedMomentumResearchPresets() {
  let candidates;
  try {
    candidates = momentumResearchCandidatePresets();
  } catch (error) {
    setResearchMessage(error.message, "danger");
    return;
  }
  seedResearchCandidatePresets(
    candidates,
    "Seeded and selected 5 Round 7 Momentum authority candidates. Run them across 20 dates for 100 replays plus Flat control.",
  );
}

function seedCombinedResearchPresets() {
  let candidates;
  try {
    candidates = combinedRouterValidationPresets();
  } catch (error) {
    setResearchMessage(error.message, "danger");
    return;
  }
  seedResearchCandidatePresets(
    candidates,
    "Seeded and selected BalancedPure observer, ChopFirewall Router, and StrictAuthority-only control. Run each 20-date pack for 60 replays plus Flat control.",
  );
}

function renderResearchPresetLibrary(selectedId = "") {
  if (!els.researchPresetLibrary && !els.researchComparePresets) return;
  const presets = readResearchPresets();
  const optionHtml = presets
    .map(
      (preset) =>
        `<option value="${escapeHtml(preset.id)}">${escapeHtml(
          `${preset.name} ${preset.version ? `(${preset.version})` : ""}`.trim(),
        )}</option>`,
    )
    .join("");
  if (els.researchPresetLibrary) {
    els.researchPresetLibrary.innerHTML = presets.length
      ? `<option value="">Choose saved preset</option>${optionHtml}`
      : '<option value="">No saved presets</option>';
    els.researchPresetLibrary.value = selectedId;
  }
  if (els.researchComparePresets) {
    const selectedCompareIds = new Set(
      Array.from(els.researchComparePresets.selectedOptions || []).map(
        (option) => option.value,
      ),
    );
    els.researchComparePresets.innerHTML = presets.length
      ? optionHtml
      : '<option value="">No saved presets</option>';
    Array.from(els.researchComparePresets.options).forEach((option) => {
      option.selected = selectedCompareIds.has(option.value);
    });
  }
  syncResearchPresetButtons();
}

function syncResearchPresetButtons() {
  const selected = Boolean(els.researchPresetLibrary?.value);
  const compareSelectedCount = Array.from(
    els.researchComparePresets?.selectedOptions || [],
  ).filter((option) => option.value).length;
  const hasCompareOptions = Array.from(els.researchComparePresets?.options || []).some(
    (option) => option.value,
  );
  const locked = state.running || state.busy || state.researchBusy;
  if (els.saveResearchPreset) {
    els.saveResearchPreset.disabled = locked;
  }
  if (els.loadResearchPreset) {
    els.loadResearchPreset.disabled = locked || !selected;
  }
  if (els.deleteResearchPreset) {
    els.deleteResearchPreset.disabled = locked || !selected;
  }
  if (els.selectAllResearchComparePresets) {
    els.selectAllResearchComparePresets.disabled = locked || !hasCompareOptions;
  }
  if (els.seedChopResearchPresets) {
    els.seedChopResearchPresets.disabled = locked;
  }
  if (els.seedMomentumResearchPresets) {
    els.seedMomentumResearchPresets.disabled = locked;
  }
  if (els.seedCombinedResearchPresets) {
    els.seedCombinedResearchPresets.disabled = locked;
  }
  if (els.applyGoLiveRouter) {
    els.applyGoLiveRouter.disabled = locked;
  }
  if (els.runResearchCompare) {
    els.runResearchCompare.disabled = locked || compareSelectedCount < 2;
  }
  if (els.runShadowRouter) {
    els.runShadowRouter.disabled = locked || compareSelectedCount < 2;
  }
}

function saveResearchPreset() {
  const name = (els.backtestPresetName?.value || "").trim();
  const version = (els.backtestPresetVersion?.value || "v1").trim() || "v1";
  if (!name) {
    setResearchMessage("Name the preset before saving it.", "warning");
    return;
  }
  let config;
  try {
    config = payloadFromForm();
  } catch (error) {
    setResearchMessage(error.message, "danger");
    return;
  }
  delete config.dryRun;
  const id = researchPresetId(name, version);
  const presets = readResearchPresets();
  const nextPreset = {
    id,
    name,
    version,
    notes: els.researchPresetNotes?.value || "",
    saved_at: new Date().toISOString(),
    config,
  };
  const existingIndex = presets.findIndex((preset) => preset.id === id);
  if (existingIndex >= 0) {
    presets[existingIndex] = nextPreset;
  } else {
    presets.push(nextPreset);
  }
  presets.sort((a, b) => `${a.name} ${a.version}`.localeCompare(`${b.name} ${b.version}`));
  writeResearchPresets(presets);
  renderResearchPresetLibrary(id);
  setResearchMessage(`Saved preset ${name} (${version}).`, "success");
}

function selectedResearchPreset() {
  const id = els.researchPresetLibrary?.value;
  if (!id) {
    return null;
  }
  return readResearchPresets().find((preset) => preset.id === id) || null;
}

function selectedResearchComparePresets() {
  const selectedIds = new Set(
    Array.from(els.researchComparePresets?.selectedOptions || [])
      .map((option) => option.value)
      .filter(Boolean),
  );
  if (!selectedIds.size) {
    return [];
  }
  return readResearchPresets().filter((preset) => selectedIds.has(preset.id));
}

function selectAllResearchComparePresets() {
  if (!els.researchComparePresets) return;
  Array.from(els.researchComparePresets.options).forEach((option) => {
    option.selected = Boolean(option.value);
  });
  syncResearchPresetButtons();
  setResearchMessage("Selected all saved presets for comparison.", "success");
}

function loadResearchPreset() {
  const preset = selectedResearchPreset();
  if (!preset) {
    setResearchMessage("Choose a saved preset first.", "warning");
    return;
  }
  applyStrategyConfig(preset.config || {});
  if (els.backtestPresetName) {
    els.backtestPresetName.value = preset.name || "Current Controls";
  }
  if (els.backtestPresetVersion) {
    els.backtestPresetVersion.value = preset.version || "v1";
  }
  if (els.researchPresetNotes) {
    els.researchPresetNotes.value = preset.notes || "";
  }
  setResearchMessage(`Loaded preset ${preset.name}. Save settings or run a backtest to apply it.`, "success");
}

function deleteResearchPreset() {
  const preset = selectedResearchPreset();
  if (!preset) {
    setResearchMessage("Choose a saved preset first.", "warning");
    return;
  }
  const presets = readResearchPresets().filter((item) => item.id !== preset.id);
  writeResearchPresets(presets);
  renderResearchPresetLibrary();
  setResearchMessage(`Deleted preset ${preset.name}.`, "success");
}

function applyStrategyConfig(config) {
  if (!config || typeof config !== "object") {
    return;
  }
  if (els.symbol && config.symbol) {
    els.symbol.value = String(config.symbol).toUpperCase();
  }
  if (els.presetAuthorityMode && config.presetAuthorityMode) {
    const mode = String(config.presetAuthorityMode).toUpperCase();
    els.presetAuthorityMode.value =
      mode === PRESET_AUTHORITY_MODE_V6 ? PRESET_AUTHORITY_MODE_V6 : "OFF";
    localStorage.setItem(PRESET_AUTHORITY_MODE_KEY, els.presetAuthorityMode.value);
  }
  const sizingMode = config.positionSizingMode || "FIXED";
  const allocation = String(config.positionAllocationPercent || "25");
  if (els.positionSizing) {
    if (sizingMode === "DYNAMIC") {
      els.positionSizing.value = ["25", "50", "75", "95"].includes(allocation)
        ? allocation
        : "CUSTOM";
      if (els.customAllocation) {
        els.customAllocation.value = allocation;
      }
    } else {
      els.positionSizing.value = "FIXED";
    }
    state.lastSizingValue = els.positionSizing.value;
  }
  if (config.positionNotional) {
    state.fixedNotionalValue = String(config.positionNotional);
    if (els.notional && (!els.positionSizing || els.positionSizing.value === "FIXED")) {
      els.notional.value = state.fixedNotionalValue;
    }
  }
  if (els.trail && config.trailPercent !== undefined) {
    els.trail.value = config.trailPercent;
  }
  if (els.poll && config.pollSeconds !== undefined) {
    els.poll.value = config.pollSeconds;
  }
  if (els.closeout && config.closeLiquidateMinutes !== undefined) {
    els.closeout.value = config.closeLiquidateMinutes;
  }
  if (els.regimeGap && config.regimeGapThreshold !== undefined) {
    els.regimeGap.value = config.regimeGapThreshold;
  }
  if (els.regimeExitGap && config.regimeExitGapThreshold !== undefined) {
    els.regimeExitGap.value = config.regimeExitGapThreshold;
  }
  if (els.chopDiscount && config.chopEntryDiscountPercent !== undefined) {
    els.chopDiscount.value = config.chopEntryDiscountPercent;
  }
  if (config.directionalMode) {
    els.directionalModes.forEach((input) => {
      input.checked = input.value === config.directionalMode;
    });
  }
  if (els.directionalMaxExtension && config.directionalMaxExtensionPercent !== undefined) {
    els.directionalMaxExtension.value = config.directionalMaxExtensionPercent;
  }
  if (
    els.directionalStrongChase &&
    config.directionalStrongChaseMaxExtensionPercent !== undefined
  ) {
    els.directionalStrongChase.value =
      config.directionalStrongChaseMaxExtensionPercent;
  }
  if (els.directionalMinStrength && config.directionalMinStrength !== undefined) {
    els.directionalMinStrength.value = config.directionalMinStrength;
  }
  if (els.directionalCooldown && config.directionalCooldownMinutes !== undefined) {
    els.directionalCooldown.value = config.directionalCooldownMinutes;
  }
  if (els.adaptiveShadow && config.adaptiveShadowEnabled !== undefined) {
    els.adaptiveShadow.checked = Boolean(config.adaptiveShadowEnabled);
  }
  if (els.fast && config.fastSmaMinutes !== undefined) {
    els.fast.value = config.fastSmaMinutes;
  }
  if (els.slow && config.slowSmaMinutes !== undefined) {
    els.slow.value = config.slowSmaMinutes;
  }
  syncSizingControls();
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
    const allocation = String(data.position_allocation_percent || "25");
    const sizingValue = sizingValueFromData(data);
    els.positionSizing.value = sizingValue;
    state.lastSizingValue = els.positionSizing.value;
    if (els.customAllocation) {
      els.customAllocation.value = allocation;
    }
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
  if (els.adaptiveShadow) {
    els.adaptiveShadow.checked = data.adaptive_shadow_enabled !== false;
  }
  els.fast.value = data.fast_sma_minutes || "5";
  els.slow.value = data.slow_sma_minutes || "20";
  state.dryRun = Boolean(data.dry_run);
  if (els.dryRun) {
    els.dryRun.checked = state.dryRun;
  }
  if (state.activeStrategyConfig) {
    applyStrategyConfig(state.activeStrategyConfig);
  }
  syncSizingControls();
  state.hydrated = true;
}

function renderMode(
  isDryRun,
  environment = state.activeEnvironment,
  liveArmed = state.liveTradingArmed,
  liveCredentialsReady = state.liveCredentialsReady,
) {
  document.body.classList.toggle("live-paper", !isDryRun);
  let label = "Dry run";
  let tooltip = "Orders are simulated and not sent to Alpaca.";
  if (isDryRun) {
    label = environment === "live" ? "Live dry run" : "Dry run";
    tooltip =
      environment === "live"
        ? "Live credentials/environment selected, but orders are still simulated."
        : "Orders are simulated and not sent to Alpaca.";
  } else if (environment === "live") {
    if (!liveCredentialsReady) {
      label = "Live incomplete";
      tooltip = "Live environment is selected, but live API credentials are not configured.";
    } else if (!liveArmed) {
      label = "Live blocked";
      tooltip = 'Live environment is selected, but live trading is not armed. Type "LIVE" in Settings to arm it.';
    } else {
      label = "Live orders";
      tooltip = "Live environment is armed. Orders can be sent to the live Alpaca account.";
    }
  } else {
    label = "Paper orders";
    tooltip = "Dry run is off. Orders can be sent to the Alpaca paper account.";
  }
  els.mode.textContent = label;
  els.mode.dataset.tooltip = tooltip;
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
    els.dataStatus.dataset.tooltip = "Market data status has not loaded yet.";
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
  if (age) {
    pieces.push(age);
  }
  els.dataStatus.textContent = pieces.join(" · ");
  els.dataStatus.dataset.tooltip = [
    `Status: ${label}`,
    feed ? `Feed: ${feed}` : null,
    age ? `Latest completed bar age: ${age}` : null,
  ].filter(Boolean).join(" · ");

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

function renderPriorCloseStatus(status) {
  if (!els.priorClose) {
    return;
  }
  els.priorClose.classList.remove("data-live", "data-warn", "data-danger");

  const contextText = JSON.stringify(status?.v9_momentum_context || {});
  if (contextText.includes("source_prior_close_unavailable")) {
    els.priorClose.textContent = "Missing";
    els.priorClose.dataset.tooltip =
      "A specialist gate reported missing previous-session close context and failed closed.";
    els.priorClose.classList.add("data-danger");
    return;
  }

  els.priorClose.textContent = "Guarded";
  els.priorClose.dataset.tooltip =
    "Previous-session close is fetched on demand by Momentum Surge and Inverse Cascade. If unavailable, those gates fail closed.";
  els.priorClose.classList.add("data-live");
}

function renderAdaptiveStatus(status) {
  if (!els.adaptive) {
    return;
  }

  els.adaptive.classList.remove("data-live", "data-warn", "data-danger");

  if (!status) {
    els.adaptive.textContent = "Waiting";
    els.adaptive.dataset.tooltip = "Adaptive posture has not evaluated yet.";
    els.adaptive.classList.add("data-warn");
    return;
  }

  const posture = status.adaptive_posture;
  const configuredMode = status.directional_mode || "BALANCED";
  const effectiveMode = status.effective_directional_mode || posture;
  const confidence = status.adaptive_confidence
    ? formatLabel(status.adaptive_confidence)
    : null;
  const reasons = Array.isArray(status.adaptive_reasons)
    ? status.adaptive_reasons
    : [];
  const constraints = Array.isArray(status.adaptive_constraints)
    ? status.adaptive_constraints
    : [];

  if (!posture) {
    const shadowLabel = els.adaptiveShadow?.checked ? "Shadow armed" : "Off";
    els.adaptive.textContent =
      configuredMode === "ADAPTIVE" ? "Waiting" : shadowLabel;
    els.adaptive.dataset.tooltip =
      configuredMode === "ADAPTIVE"
        ? "Adaptive is selected and will evaluate once market data is available."
        : "Adaptive has not evaluated this cycle.";
    els.adaptive.classList.add("data-warn");
    return;
  }

  const active = configuredMode === "ADAPTIVE" && !status.adaptive_shadow;
  els.adaptive.textContent = active
    ? `${formatLabel(posture)}${confidence ? ` · ${confidence}` : ""}`
    : `Shadow: ${formatLabel(posture)}`;
  const tooltipParts = [
    active
      ? `Adaptive is actively using ${formatLabel(effectiveMode)} posture.`
      : `Manual ${formatLabel(configuredMode)} remains in control; Adaptive would use ${formatLabel(posture)}.`,
  ];
  if (reasons.length) {
    tooltipParts.push(`Reasons: ${reasons.map(formatLabel).join(", ")}`);
  }
  if (constraints.length) {
    tooltipParts.push(`Constraints: ${constraints.map(formatLabel).join(", ")}`);
  }
  els.adaptive.dataset.tooltip = tooltipParts.join(" ");

  if (posture === "AGGRESSIVE") {
    els.adaptive.classList.add(active ? "data-live" : "data-warn");
  } else if (posture === "CONSERVATIVE") {
    els.adaptive.classList.add("data-warn");
  } else {
    els.adaptive.classList.add("data-live");
  }
}

function renderPerformance(performance) {
  const realizedPl = performance?.session_realized_pl ?? null;
  const tradeCount = performance?.session_trade_count ?? 0;
  const lastTradePl = performance?.last_trade_realized_pl ?? null;
  const reconciliationConfidence =
    performance?.reconciliation_confidence || "UNKNOWN";
  const reconciliationNotes = Array.isArray(performance?.reconciliation_notes)
    ? performance.reconciliation_notes
    : [];

  els.sessionRealizedPl.textContent =
    realizedPl === null ? "--" : formatMoney(realizedPl);
  els.sessionRealizedPl.dataset.tooltip = [
    `Reconciliation confidence: ${formatLabel(reconciliationConfidence)}`,
    ...reconciliationNotes.map(formatLabel),
  ].join(" · ");
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
    els.themeToggle.checked = useDark;
  }
}

function setupTheme() {
  const preferred = window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
  applyTheme(savedTheme() || preferred);
}

function toggleTheme() {
  const nextTheme =
    els.themeToggle && "checked" in els.themeToggle
      ? els.themeToggle.checked
        ? "dark"
        : "light"
      : document.body.classList.contains("dark-theme")
      ? "light"
      : "dark";
  applyTheme(nextTheme);
  saveTheme(nextTheme);
}

function savedAudioscape() {
  try {
    return localStorage.getItem(AUDIOSCAPE_KEY) === "1";
  } catch {
    return false;
  }
}

function saveAudioscape(enabled) {
  try {
    localStorage.setItem(AUDIOSCAPE_KEY, enabled ? "1" : "0");
  } catch {
    return;
  }
}

function applyAudioscape(enabled) {
  const isEnabled = Boolean(enabled);
  state.audioscapeEnabled = isEnabled;
  document.body.classList.toggle("audioscape-enabled", isEnabled);
  if (els.audioscapeToggle) {
    els.audioscapeToggle.checked = isEnabled;
  }
  if (isEnabled) {
    prepareSound("uiClick");
  }
}

function setupAudioscapePreference() {
  applyAudioscape(savedAudioscape());
  if (els.audioscapeToggle) {
    els.audioscapeToggle.addEventListener("change", () => {
      applyAudioscape(els.audioscapeToggle.checked);
      saveAudioscape(state.audioscapeEnabled);
      if (state.audioscapeEnabled) {
        playSound("uiClick", { force: true });
      }
    });
  }
}

function soundUrl(filename) {
  return `${SOUND_BASE}/${filename.split("/").map(encodeURIComponent).join("/")}`;
}

function prepareSound(soundName) {
  if (soundCache.has(soundName)) {
    return soundCache.get(soundName);
  }
  const soundConfig = SOUND_LIBRARY[soundName];
  if (!soundConfig) {
    return null;
  }
  const sound = new Audio(soundUrl(soundConfig.file));
  sound.preload = "auto";
  sound.volume = soundConfig.volume;
  sound.load();
  soundCache.set(soundName, sound);
  return sound;
}

function playSound(soundName, { force = false } = {}) {
  if (!force && !state.audioscapeEnabled) {
    return;
  }
  const sound = prepareSound(soundName);
  if (!sound) {
    return;
  }
  try {
    sound.pause();
    sound.currentTime = 0;
    const playback = sound.play();
    if (playback && typeof playback.catch === "function") {
      playback.catch(() => {});
    }
  } catch {
    return;
  }
}

function isUiSoundTarget(target) {
  if (!(target instanceof Element)) {
    return false;
  }
  const control = target.closest(
    'button, select, summary, input[type="checkbox"], input[type="radio"], .switch, .segmented-control label, [role="tab"]',
  );
  if (!control || control.closest(".is-disabled")) {
    return false;
  }
  if ("disabled" in control && control.disabled) {
    return false;
  }
  return true;
}

function setupUiSounds() {
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (isUiSoundTarget(event.target)) {
        playSound("uiClick");
      }
    },
    true,
  );
  document.addEventListener(
    "keydown",
    (event) => {
      if (!["Enter", " "].includes(event.key)) {
        return;
      }
      if (isUiSoundTarget(event.target)) {
        playSound("uiClick");
      }
    },
    true,
  );
}

function signatureFromParts(parts) {
  return parts.map((part) => part ?? "").join("|");
}

function orderFillSignature(orderState) {
  const events = Array.isArray(orderState?.recent_events)
    ? orderState.recent_events
    : [];
  const latestFill =
    orderState?.latest_fill ||
    events.find((event) => event.event_type === "FULL_FILL");
  if (!latestFill) {
    return null;
  }
  return signatureFromParts([
    latestFill.event_type || "FULL_FILL",
    latestFill.order_id,
    latestFill.symbol,
    latestFill.side,
    latestFill.filled_qty,
    latestFill.fill_delta_qty,
    latestFill.filled_avg_price,
    latestFill.created_at,
  ]);
}

function interventionSignature(data) {
  if (data.last_error) {
    return signatureFromParts(["error", data.last_error]);
  }
  const brokerState = data.broker_state?.state;
  if (!INTERVENTION_BROKER_STATES.has(brokerState)) {
    return null;
  }
  return signatureFromParts([
    "broker",
    brokerState,
    data.broker_state?.category,
    data.broker_state?.message,
    data.broker_state?.side,
    data.broker_state?.symbol,
    data.broker_state?.code,
  ]);
}

function positionSignature(status) {
  if (!status?.position_symbol || !numberOrNull(status.position_qty)) {
    return null;
  }
  return signatureFromParts([
    status.position_symbol,
    status.position_qty,
    status.position_owner,
  ]);
}

function trailingExitPrice(status) {
  return numberOrNull(status?.trailing_exit_price);
}

function trailProtectionState(status) {
  const entryPrice = numberOrNull(status?.position_avg_entry_price);
  const trailPrice = numberOrNull(status?.trailing_exit_price);
  if (entryPrice === null || trailPrice === null) {
    return { label: "--", protected: false, active: false };
  }
  if (trailPrice >= entryPrice) {
    return { label: "Trail >= entry", protected: true, active: true };
  }
  return { label: "Trail below entry", protected: false, active: true };
}

function projectedTrailPl(status) {
  const qty = numberOrNull(status?.position_qty);
  const entryPrice = numberOrNull(status?.position_avg_entry_price);
  const trailPrice = numberOrNull(status?.trailing_exit_price);
  if (!status?.position_symbol || qty === null || qty <= 0) {
    return null;
  }
  if (entryPrice === null || trailPrice === null) {
    return null;
  }
  return (trailPrice - entryPrice) * qty;
}

function hydrateAudioBaselines(data) {
  const currentPositionSignature = positionSignature(data.edgewalker_status);
  state.lastOrderFillSignature = orderFillSignature(data.order_state);
  state.lastInterventionSignature = interventionSignature(data);
  state.lastPositionSignature = currentPositionSignature;
  state.lastTrailingExitPrice = trailingExitPrice(data.edgewalker_status);
  state.protectionPositionSignature = currentPositionSignature;
  state.trailProtectionPlayed = trailProtectionState(
    data.edgewalker_status,
  ).protected;
  state.audioHydrated = true;
}

function handleRuntimeSounds(data, wasRunning) {
  if (!state.audioHydrated) {
    hydrateAudioBaselines(data);
    return;
  }

  if (!wasRunning && state.running) {
    playSound("botStarted");
  } else if (wasRunning && !state.running) {
    playSound("botDeactivated");
  }

  const fillSignature = orderFillSignature(data.order_state);
  if (fillSignature && fillSignature !== state.lastOrderFillSignature) {
    playSound("orderFilled");
  }
  state.lastOrderFillSignature = fillSignature;

  const currentInterventionSignature = interventionSignature(data);
  if (
    currentInterventionSignature &&
    currentInterventionSignature !== state.lastInterventionSignature
  ) {
    playSound("humanIntervention");
  }
  state.lastInterventionSignature = currentInterventionSignature;

  const currentPositionSignature = positionSignature(data.edgewalker_status);
  if (state.lastPositionSignature && !currentPositionSignature) {
    playSound("positionClosed");
  }
  state.lastPositionSignature = currentPositionSignature;

  const currentProtection = trailProtectionState(data.edgewalker_status);
  if (!currentPositionSignature) {
    state.protectionPositionSignature = null;
    state.trailProtectionPlayed = false;
  } else if (currentPositionSignature !== state.protectionPositionSignature) {
    state.protectionPositionSignature = currentPositionSignature;
    state.trailProtectionPlayed = false;
  }

  let playedTrailProtectionCue = false;
  if (
    currentPositionSignature &&
    currentProtection.protected &&
    !state.trailProtectionPlayed
  ) {
    playSound("trailProtected");
    state.trailProtectionPlayed = true;
    playedTrailProtectionCue = true;
  }

  const currentTrailingExitPrice = trailingExitPrice(data.edgewalker_status);
  if (
    currentTrailingExitPrice !== null &&
    state.lastTrailingExitPrice !== null &&
    currentTrailingExitPrice > state.lastTrailingExitPrice &&
    !playedTrailProtectionCue
  ) {
    playSound("limitMovedUp");
  }
  state.lastTrailingExitPrice = currentTrailingExitPrice;
}

function setSettingsMenuOpen(open) {
  if (!els.settingsMenu || !els.settingsMenuToggle) return;
  els.settingsMenu.hidden = !open;
  els.settingsMenuToggle.classList.toggle("is-open", open);
  els.settingsMenuToggle.setAttribute("aria-expanded", String(open));
}

function setupSettingsMenu() {
  if (!els.settingsMenu || !els.settingsMenuToggle) return;

  els.settingsMenuToggle.addEventListener("click", (event) => {
    event.stopPropagation();
    hideTooltip();
    setSettingsMenuOpen(els.settingsMenu.hidden);
  });

  els.settingsMenu.addEventListener("click", (event) => {
    event.stopPropagation();
  });

  els.settingsMenu.querySelectorAll(".menu-action").forEach((button) => {
    button.addEventListener("click", () => setSettingsMenuOpen(false));
  });

  document.addEventListener("click", () => setSettingsMenuOpen(false));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setSettingsMenuOpen(false);
    }
  });
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

function setSettingsMessage(message, tone = "neutral") {
  if (!els.settingsMessage) return;
  els.settingsMessage.textContent = message || "";
  els.settingsMessage.classList.remove("is-success", "is-danger", "is-warning");
  if (tone !== "neutral") {
    els.settingsMessage.classList.add(`is-${tone}`);
  }
}

function setSpreadsheetMessage(message, tone = "neutral") {
  if (!els.spreadsheetMessage) return;
  els.spreadsheetMessage.textContent = message || "";
  els.spreadsheetMessage.classList.remove("is-success", "is-danger", "is-warning");
  if (tone !== "neutral") {
    els.spreadsheetMessage.classList.add(`is-${tone}`);
  }
}

function setNotificationsMessage(message, tone = "neutral") {
  if (!els.notificationsMessage) return;
  els.notificationsMessage.textContent = message || "";
  els.notificationsMessage.classList.remove(
    "is-success",
    "is-danger",
    "is-warning",
  );
  if (tone !== "neutral") {
    els.notificationsMessage.classList.add(`is-${tone}`);
  }
}

function setResearchMessage(message, tone = "neutral") {
  if (!els.researchMessage) return;
  els.researchMessage.textContent = message || "";
  els.researchMessage.classList.remove("is-success", "is-danger", "is-warning");
  if (tone !== "neutral") {
    els.researchMessage.classList.add(`is-${tone}`);
  }
}

function updateResearchProgressText() {
  if (!els.researchProgressText || !state.researchProgressStartedAt) return;
  const elapsedSeconds = Math.max(
    Math.floor((Date.now() - state.researchProgressStartedAt) / 1000),
    0,
  );
  els.researchProgressText.textContent = `${state.researchProgressLabel} · ${formatDurationSeconds(
    elapsedSeconds,
  )} elapsed`;
}

function startResearchProgress(label) {
  state.researchProgressLabel = label || "Research run in progress";
  state.researchProgressStartedAt = Date.now();
  if (els.researchProgress) {
    els.researchProgress.hidden = false;
  }
  updateResearchProgressText();
  if (state.researchProgressTimer) {
    clearInterval(state.researchProgressTimer);
  }
  state.researchProgressTimer = window.setInterval(updateResearchProgressText, 1000);
}

function stopResearchProgress() {
  if (state.researchProgressTimer) {
    clearInterval(state.researchProgressTimer);
  }
  state.researchProgressTimer = null;
  state.researchProgressStartedAt = null;
  state.researchProgressLabel = "";
  if (els.researchProgress) {
    els.researchProgress.hidden = true;
  }
}

const RESEARCH_TOOLTIP_TEXT = {
  "Aggregate Leader": "Preset with the highest total realized P/L across the selected comparison dates.",
  "Leader Total P/L": "Total realized P/L for the aggregate leader across all replayed dates.",
  "Leader Date Wins": "Number of comparison dates where this preset had the highest realized P/L.",
  "Max Wrong-Cost": "Largest observed opportunity gap between the date winner and an inferior preset choice.",
  "Fill Model": "Historical replay fill assumption. Next Bar Open fills at the next one-minute bar open after the decision.",
  Slippage: "Execution penalty applied to simulated buys and sells, measured in basis points.",
  Observer: "Baseline preset used as the pre-checkpoint/default observer for shadow router switch scoring.",
  "09:45 Authority P/L": "Total checkpoint-to-close P/L under the v6 09:45 authority gate.",
  "Authority Δ": "Authority P/L minus staying with Lead_Generalist for the same checkpoint-to-close window.",
  "Routes / Blocked": "Specialist routes granted by v6 versus HIGH-confidence signals blocked for review.",
  "Best Checkpoint": "Checkpoint with the strongest switch model score in this replay pack.",
  "Best Switch P/L": "Total P/L if the router switched at that checkpoint on every tested date.",
  "Best Switch Accuracy": "Share of checkpoint selections matching the best post-checkpoint preset.",
  "All Snapshot Accuracy": "Aggregate hit rate across every checkpoint snapshot in the replay.",
  Dates: "Number of dates included in this summary row.",
  Hit: "Correct authority selections divided by total dates.",
  Accuracy: "Hit count expressed as a percentage of total dates.",
  "Authority P/L": "P/L produced by the authority policy, using Lead_Generalist unless v6 grants a route.",
  "Generalist P/L": "P/L from staying with Lead_Generalist under the same checkpoint-to-close scoring model.",
  "Δ vs Gen": "Difference between the selected policy and Lead_Generalist for the same window.",
  "Best Switch": "Best possible checkpoint-to-close P/L among the available presets for those dates.",
  Cost: "Opportunity cost versus the best available switch result.",
  Route: "Count of HIGH-confidence specialist calls that v6 allowed to route.",
  Blocked: "Count of HIGH-confidence specialist calls quarantined by v6 blocks.",
  Advisory: "Count of MODERATE specialist calls logged only, with authority staying Generalist.",
  Default: "Count of dates where v6 stayed with Lead_Generalist by default.",
  Checkpoint: "Time of day when the simulated switch decision was made.",
  "Switch Hit": "Times the raw checkpoint router selected the best post-checkpoint preset.",
  "Switch Acc": "Switch hits divided by dates for this checkpoint.",
  "High Conf": "Count of HIGH-confidence router calls at this checkpoint.",
  "Switch P/L": "P/L from running Lead_Generalist before the checkpoint, then the selected preset after it.",
  "Switch Cost": "Gap between the raw switch result and the best post-checkpoint preset.",
  "Proxy P/L": "Older full-day proxy score for the selected preset, included for comparison.",
  Date: "Replay trading date.",
  Time: "Checkpoint time for this row.",
  Pick: "Preset selected by the shadow router at this checkpoint.",
  Authority: "v6 authority action: route, block, advisory, default, or log-only.",
  "Auth P/L": "P/L produced by the v6 authority decision for this row.",
  "Auth Δ": "Authority P/L minus Lead_Generalist for this row.",
  "Post Best": "Best preset from checkpoint to close.",
  Switch: "Whether the raw checkpoint pick matched the post-checkpoint winner.",
  "Δ Gen": "Raw switch P/L minus Lead_Generalist for this row.",
  "Full-Day Winner": "Preset that won the full-day proxy experiment.",
  "Proxy Cost": "Full-day proxy opportunity cost of the selected preset versus the full-day winner.",
  "Router Conf": "Router confidence bucket assigned to this checkpoint decision.",
  "SOXL %": "SOXL percent change from the regular-session open to the checkpoint.",
  "SOXL DD": "Maximum SOXL drawdown from the regular-session open observed by the checkpoint.",
  "Trans/hr": "Regime transition density, measured as transitions per hour.",
  "Regime min": "Average regime duration in minutes; higher values imply more persistent regimes.",
  Trust: "Trend trust score from the fingerprint engine.",
  Regime: "Current detected regime at the checkpoint.",
  Reason: "Router explanation for the pick or authority action.",
  Preset: "Saved strategy preset used for this replay row.",
  "Target Bot": "Bot that should express this specialist preset's main thesis.",
  "Total P/L": "Total realized P/L for this preset across selected dates.",
  "Target P/L": "Realized P/L contributed by the preset's target bot.",
  "Avg %": "Average account-change percentage across the replayed dates.",
  "Date Wins": "Number of dates this preset won outright.",
  "Green/Red": "Count of positive-P/L dates versus negative-P/L dates.",
  Purity: "Target bot absolute P/L divided by total absolute bot P/L; higher means the specialist identity is clearer.",
  "Non-target Damage": "Total negative P/L from bots outside this preset's target bot.",
  "Home Capture": "Target bot P/L on the five largest home-turf move days divided by the theoretical target-instrument opportunity.",
  "Home Target Share": "Target bot's share of preset P/L on the five largest home-turf move days.",
  "Home Miss": "Theoretical home-turf target opportunity not captured by the target bot.",
  Diagnosis: "First-pass audit label for whether the specialist is confirmed, polluted, weak, or still mixed.",
  Momentum: "Realized P/L attributed to MomentumBot trades.",
  Chop: "Realized P/L attributed to ChopBot trades.",
  Inverse: "Realized P/L attributed to InverseBot trades.",
  "Worst Date": "Date with this preset's weakest realized P/L.",
  Winner: "Preset with the best realized P/L for this date.",
  Margin: "Winner's lead over the second-place preset.",
  Confidence: "Confidence label assigned to the date winner from the research comparison.",
  "Worst Cost": "Largest loss of choosing the wrong preset on this date.",
  "30m Trans/hr": "Transition density measured in the first 30 regular-session minutes.",
  "60m Trans/hr": "Transition density measured in the first 60 regular-session minutes.",
  "P/L": "Realized replay P/L for this run.",
  "%": "Replay account-change percentage for this run.",
  Trades: "Closed strategy trade count for this replay run.",
  "Win Rate": "Percent of closed trades that finished positive.",
  MFE: "Average maximum favorable excursion for closed trades.",
  Capture: "Average portion of favorable excursion captured by realized exits.",
  "Early M/C/I": "Market-buy entries with regime age at or below 3 minutes, split Momentum/Chop/Inverse.",
  "V8 Blocks Y/T/N": "v8 entry veto counts split by young regime, low trend trust, and noisy-water flip pressure.",
  "V9 C/S/I": "v9 Momentum-context counts split by context activations, InverseBot suppressions, and hard invalidations.",
  "V9 Context": "v9 activation fingerprint: observer preset, trust score, SOXL percent from open, raw first-window transitions, and non-warmup transition count/rate.",
  Auth: "Momentum authority config flags: AR means authority required, RE means revoke exits enabled, LAT means authority latches after one clean activation, V10F means forced no-authority shadow mode.",
  "V10 D/M/I": "v10 No-Authority suppression counts split by total directional, MomentumBot, and InverseBot suppressions.",
  "V10 Context": "v10 No-Authority observer fingerprint. Shows the first suppressed-entry context, or the evaluated no-authority context when no post-checkpoint directional entries appeared.",
};

function researchTooltip(label) {
  return RESEARCH_TOOLTIP_TEXT[label] || "";
}

function researchTooltipLabel(label, tooltip = researchTooltip(label)) {
  const safeLabel = escapeHtml(label);
  if (!tooltip) {
    return safeLabel;
  }
  return `<span class="has-tooltip" tabindex="0" data-tooltip="${escapeHtml(
    tooltip,
  )}">${safeLabel}</span>`;
}

function researchTh(label, tooltip = researchTooltip(label)) {
  return `<th>${researchTooltipLabel(label, tooltip)}</th>`;
}

function renderResearchResults(result = state.lastResearchResult) {
  if (!els.researchResults) return;
  if (!state.researchModeEnabled || !result) {
    els.researchResults.hidden = true;
    els.researchResults.innerHTML = "";
    return;
  }
  if (result.kind === "comparison") {
    renderResearchComparison(result);
    return;
  }
  if (result.kind === "shadow_router") {
    renderShadowRouterReplay(result);
    return;
  }

  const row = result.row || {};
  const performance = result.performance || {};
  const trades = Array.isArray(result.trades) ? result.trades : [];
  const quality = performance.trade_quality || {};
  const archaeology = result.inversebot_archaeology || {};
  const botPerformance = Array.isArray(performance.bot_performance)
    ? performance.bot_performance
    : [];
  const realizedPl = numberOrNull(row.realized_pl_dollars);
  const accountChange = numberOrNull(row.account_change_percent);
  const tradeCount = numberOrNull(row.closed_trades) ?? trades.length;
  const winRate = numberOrNull(row.win_rate);
  const posted = result.posted ? "Posted" : "Not posted";
  const title = `${row.date || result.date || "Backtest"} · ${
    row.mode || "Research"
  }`;

  els.researchResults.hidden = false;
  els.researchResults.innerHTML = `
    <div class="research-results-head">
      <div>
        <p class="eyebrow">BACKTEST RESULT</p>
        <strong>${escapeHtml(title)}</strong>
      </div>
      <div class="research-result-actions">
        <span class="research-result-status">${escapeHtml(posted)}</span>
        <button
          id="copyResearchOutputButton"
          type="button"
          class="secondary"
        >
          Copy Output
        </button>
      </div>
    </div>
    <div class="research-summary-grid">
      ${renderResearchMetric("Realized P/L", formatMoney(realizedPl), realizedPl)}
      ${renderResearchMetric(
        "Account Change",
        accountChange === null ? "--" : formatPercent(accountChange),
        accountChange,
      )}
      ${renderResearchMetric("Closed Trades", String(tradeCount || 0))}
      ${renderResearchMetric(
        "Win Rate",
        winRate === null ? "--" : formatPercent(winRate),
        winRate,
      )}
      ${renderResearchMetric(
        "Avg MFE",
        quality.avg_mfe_percent === null || quality.avg_mfe_percent === undefined
          ? "--"
          : formatPercent(quality.avg_mfe_percent),
        quality.avg_mfe_percent,
      )}
      ${renderResearchMetric(
        "Avg MAE",
        quality.avg_mae_percent === null || quality.avg_mae_percent === undefined
          ? "--"
          : formatPercent(quality.avg_mae_percent),
        quality.avg_mae_percent,
      )}
      ${renderResearchMetric(
        "Avg Capture",
        quality.avg_capture_ratio_percent === null ||
          quality.avg_capture_ratio_percent === undefined
          ? "--"
          : formatPercent(quality.avg_capture_ratio_percent),
        quality.avg_capture_ratio_percent,
      )}
      ${renderResearchMetric(
        "Avg Hold",
        formatDurationSeconds(quality.avg_hold_seconds),
      )}
    </div>
    ${renderResearchBotQuality(botPerformance)}
    ${renderResearchArchaeology(archaeology)}
    ${renderResearchTrades(trades)}
  `;
  wireResearchResultActions();
}

function renderResearchComparison(result) {
  const presetSummaries = Array.isArray(result.preset_summaries)
    ? result.preset_summaries
    : [];
  const dateSummaries = Array.isArray(result.date_summaries)
    ? result.date_summaries
    : [];
  const results = Array.isArray(result.results) ? result.results : [];
  const leader = presetSummaries[0] || null;
  const biggestWrongCost = dateSummaries.reduce((maxValue, summary) => {
    const cost = numberOrNull(summary.worst_misclassification_cost_dollars) || 0;
    return Math.max(maxValue, cost);
  }, 0);

  els.researchResults.hidden = false;
  els.researchResults.innerHTML = `
    <div class="research-results-head">
      <div>
        <p class="eyebrow">PRESET COMPARISON</p>
        <strong>${escapeHtml(result.run_count || 0)} replay runs</strong>
      </div>
      <div class="research-result-actions">
        <span class="research-result-status">${escapeHtml(
          `${result.preset_count || 0} presets · ${dateSummaries.length} dates`,
        )}</span>
        <button
          id="copyResearchOutputButton"
          type="button"
          class="secondary"
        >
          Copy Output
        </button>
      </div>
    </div>
    <div class="research-summary-grid">
      ${renderResearchMetric(
        "Aggregate Leader",
        leader ? leader.preset_name : "--",
        leader?.total_pl,
      )}
      ${renderResearchMetric(
        "Leader Total P/L",
        leader ? formatMoney(leader.total_pl) : "--",
        leader?.total_pl,
      )}
      ${renderResearchMetric(
        "Leader Date Wins",
        leader ? String(leader.date_wins || 0) : "--",
      )}
      ${renderResearchMetric(
        "Max Wrong-Cost",
        formatMoney(biggestWrongCost),
        biggestWrongCost,
      )}
      ${renderResearchMetric("Fill Model", formatLabel(result.fill_model || "--"))}
      ${renderResearchMetric(
        "Slippage",
        `${escapeHtml(result.slippage_bps ?? "0")} bps`,
      )}
    </div>
    ${renderResearchPresetSummaryTable(presetSummaries)}
    ${renderSpecialistAuditTable(result.specialist_audit || [])}
    ${renderResearchDateSummaryTable(dateSummaries)}
    ${renderResearchComparisonRunTable(results)}
  `;
  wireResearchResultActions();
}

function renderShadowRouterReplay(result) {
  const checkpointSummaries = Array.isArray(result.checkpoint_summaries)
    ? result.checkpoint_summaries
    : [];
  const decisions = Array.isArray(result.decisions) ? result.decisions : [];
  const authority = result.authority_summary || {};
  const best = result.best_checkpoint || checkpointSummaries[0] || null;
  const dateCount = Array.isArray(result.date_summaries)
    ? result.date_summaries.length
    : 0;
  const correctTotal = checkpointSummaries.reduce(
    (total, row) => total + (numberOrNull(row.correct) || 0),
    0,
  );
  const decisionTotal = checkpointSummaries.reduce(
    (total, row) => total + (numberOrNull(row.dates) || 0),
    0,
  );
  const aggregateAccuracy = decisionTotal
    ? (correctTotal / decisionTotal) * 100
    : null;

  els.researchResults.hidden = false;
  els.researchResults.innerHTML = `
    <div class="research-results-head">
      <div>
        <p class="eyebrow">SHADOW ROUTER REPLAY</p>
        <strong>${escapeHtml(result.run_count || 0)} replay runs</strong>
      </div>
      <div class="research-result-actions">
        <span class="research-result-status">${escapeHtml(
          `${result.preset_count || 0} presets · ${dateCount} dates`,
        )}</span>
        <button
          id="copyResearchOutputButton"
          type="button"
          class="secondary"
        >
          Copy Output
        </button>
      </div>
    </div>
    <div class="research-summary-grid">
      ${renderResearchMetric("Observer", result.observer_preset || "--")}
      ${renderResearchMetric(
        "09:45 Authority P/L",
        formatMoney(authority.authority_total_pl),
        authority.authority_total_pl,
      )}
      ${renderResearchMetric(
        "Authority Δ",
        formatMoney(authority.authority_delta_vs_generalist),
        authority.authority_delta_vs_generalist,
      )}
      ${renderResearchMetric(
        "Routes / Blocked",
        `${authority.routes || 0} / ${authority.blocked || 0}`,
      )}
      ${renderResearchMetric(
        "Best Checkpoint",
        best ? best.checkpoint : "--",
        best?.switch_total_pl ?? best?.selected_total_pl,
      )}
      ${renderResearchMetric(
        "Best Switch P/L",
        best ? formatMoney(best.switch_total_pl ?? best.selected_total_pl) : "--",
        best?.switch_total_pl ?? best?.selected_total_pl,
      )}
      ${renderResearchMetric(
        "Best Switch Accuracy",
        best
          ? formatPercentMaybe(best.switch_accuracy_percent ?? best.accuracy_percent)
          : "--",
        best?.switch_accuracy_percent ?? best?.accuracy_percent,
      )}
      ${renderResearchMetric(
        "All Snapshot Accuracy",
        aggregateAccuracy === null ? "--" : formatPercentMaybe(aggregateAccuracy),
        aggregateAccuracy,
      )}
      ${renderResearchMetric("Fill Model", formatLabel(result.fill_model || "--"))}
    </div>
    ${renderShadowAuthoritySummary(authority)}
    ${renderShadowCheckpointTable(checkpointSummaries)}
    ${renderShadowDecisionTable(decisions)}
  `;
  wireResearchResultActions();
}

function renderShadowAuthoritySummary(row) {
  if (!row || !row.dates) return "";
  return `
    <div class="research-section">
      <div class="research-section-head">
        <span>09:45 Authority Candidate</span>
        <small>v6 gate</small>
      </div>
      <div class="research-table-wrap">
        <table class="research-table research-comparison-table">
          <thead>
            <tr>
              ${researchTh("Dates")}
              ${researchTh("Hit")}
              ${researchTh("Accuracy")}
              ${researchTh("Authority P/L")}
              ${researchTh("Generalist P/L")}
              ${researchTh("Δ vs Gen")}
              ${researchTh("Best Switch")}
              ${researchTh("Cost")}
              ${researchTh("Route")}
              ${researchTh("Blocked")}
              ${researchTh("Advisory")}
              ${researchTh("Default")}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>${escapeHtml(String(row.dates || 0))}</td>
              <td>${escapeHtml(`${row.correct || 0}/${row.dates || 0}`)}</td>
              <td>${escapeHtml(formatPercentMaybe(row.accuracy_percent))}</td>
              <td class="${researchToneClass(row.authority_total_pl)}">${escapeHtml(
                formatMoney(row.authority_total_pl),
              )}</td>
              <td class="${researchToneClass(row.generalist_total_pl)}">${escapeHtml(
                formatMoney(row.generalist_total_pl),
              )}</td>
              <td class="${researchToneClass(row.authority_delta_vs_generalist)}">${escapeHtml(
                formatMoney(row.authority_delta_vs_generalist),
              )}</td>
              <td class="${researchToneClass(row.best_switch_total_pl)}">${escapeHtml(
                formatMoney(row.best_switch_total_pl),
              )}</td>
              <td class="${researchToneClass(-numberOrNull(row.authority_total_cost_dollars))}">${escapeHtml(
                formatMoney(row.authority_total_cost_dollars),
              )}</td>
              <td>${escapeHtml(String(row.routes || 0))}</td>
              <td>${escapeHtml(String(row.blocked || 0))}</td>
              <td>${escapeHtml(String(row.advisory_only || 0))}</td>
              <td>${escapeHtml(String(row.generalist_default || 0))}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderShadowCheckpointTable(rows) {
  if (!rows.length) return "";
  return `
    <div class="research-section">
      <div class="research-section-head">
        <span>Checkpoint Scores</span>
        <small>${rows.length} checkpoints</small>
      </div>
      <div class="research-table-wrap">
        <table class="research-table research-comparison-table">
          <thead>
            <tr>
              ${researchTh("Checkpoint")}
              ${researchTh("Switch Hit")}
              ${researchTh("Switch Acc")}
              ${researchTh("High Conf")}
              ${researchTh("Switch P/L")}
              ${researchTh("Δ vs Gen")}
              ${researchTh("Best Switch")}
              ${researchTh("Switch Cost")}
              ${researchTh("Proxy P/L")}
            </tr>
          </thead>
          <tbody>
            ${rows
              .map(
                (row) => `
                  <tr>
                    <td>${escapeHtml(row.checkpoint || "--")}</td>
                    <td>${escapeHtml(`${row.switch_correct || 0}/${row.dates || 0}`)}</td>
                    <td>${escapeHtml(
                      formatPercentMaybe(row.switch_accuracy_percent),
                    )}</td>
                    <td>${escapeHtml(String(row.high_confidence_count || 0))}</td>
                    <td class="${researchToneClass(row.switch_total_pl)}">${escapeHtml(
                      formatMoney(row.switch_total_pl),
                    )}</td>
                    <td class="${researchToneClass(row.switch_delta_vs_generalist_total)}">${escapeHtml(
                      formatMoney(row.switch_delta_vs_generalist_total),
                    )}</td>
                    <td class="${researchToneClass(row.checkpoint_best_total_pl)}">${escapeHtml(
                      formatMoney(row.checkpoint_best_total_pl),
                    )}</td>
                    <td class="${researchToneClass(-numberOrNull(row.switch_total_cost_dollars))}">${escapeHtml(
                      formatMoney(row.switch_total_cost_dollars),
                    )}</td>
                    <td class="${researchToneClass(row.selected_total_pl)}">${escapeHtml(
                      formatMoney(row.selected_total_pl),
                    )}</td>
                  </tr>
                `,
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderShadowDecisionTable(rows) {
  if (!rows.length) return "";
  return `
    <div class="research-section">
      <div class="research-section-head">
        <span>Checkpoint Decisions</span>
        <small>${rows.length} snapshots</small>
      </div>
      <div class="research-table-wrap">
        <table class="research-table research-comparison-table">
          <thead>
            <tr>
              ${researchTh("Date")}
              ${researchTh("Time")}
              ${researchTh("Pick")}
              ${researchTh("Authority")}
              ${researchTh("Auth P/L")}
              ${researchTh("Auth Δ")}
              ${researchTh("Post Best")}
              ${researchTh("Switch")}
              ${researchTh("Switch P/L")}
              ${researchTh("Δ Gen")}
              ${researchTh("Switch Cost")}
              ${researchTh("Full-Day Winner")}
              ${researchTh("Proxy Cost")}
              ${researchTh("Router Conf")}
              ${researchTh("SOXL %")}
              ${researchTh("SOXL DD")}
              ${researchTh("Trans/hr")}
              ${researchTh("Regime min")}
              ${researchTh("Trust")}
              ${researchTh("Regime")}
              ${researchTh("Reason")}
            </tr>
          </thead>
          <tbody>
            ${rows
              .map((row) => {
                const fingerprint = row.fingerprint || {};
                const reasons = Array.isArray(row.reasons) ? row.reasons : [];
                return `
                  <tr>
                    <td>${escapeHtml(row.date || "--")}</td>
                    <td>${escapeHtml(row.checkpoint || "--")}</td>
                    <td>${escapeHtml(row.selected_preset || "--")}</td>
                    <td>${escapeHtml(row.authority_action || "--")}</td>
                    <td class="${researchToneClass(row.authority_pl)}">${escapeHtml(
                      formatMoney(row.authority_pl),
                    )}</td>
                    <td class="${researchToneClass(row.authority_delta_vs_generalist)}">${escapeHtml(
                      formatMoney(row.authority_delta_vs_generalist),
                    )}</td>
                    <td>${escapeHtml(row.checkpoint_best_preset || "--")}</td>
                    <td>${escapeHtml(row.switch_correct ? "HIT" : "MISS")}</td>
                    <td class="${researchToneClass(row.switch_pl)}">${escapeHtml(
                      formatMoney(row.switch_pl),
                    )}</td>
                    <td class="${researchToneClass(row.switch_delta_vs_generalist)}">${escapeHtml(
                      formatMoney(row.switch_delta_vs_generalist),
                    )}</td>
                    <td class="${researchToneClass(-numberOrNull(row.switch_cost_dollars))}">${escapeHtml(
                      formatMoney(row.switch_cost_dollars),
                    )}</td>
                    <td>${escapeHtml(row.winner || "--")}${row.correct ? " HIT" : ""}</td>
                    <td class="${researchToneClass(-numberOrNull(row.cost_dollars))}">${escapeHtml(
                      formatMoney(row.cost_dollars),
                    )}</td>
                    <td>${escapeHtml(row.router_confidence || "--")}</td>
                    <td class="${researchToneClass(fingerprint.source_open_to_current_percent)}">${escapeHtml(
                      formatPercentMaybe(fingerprint.source_open_to_current_percent),
                    )}</td>
                    <td class="${researchToneClass(fingerprint.source_max_drawdown_from_open_percent)}">${escapeHtml(
                      formatPercentMaybe(fingerprint.source_max_drawdown_from_open_percent),
                    )}</td>
                    <td>${escapeHtml(formatNumberMaybe(fingerprint.transitions_per_hour))}</td>
                    <td>${escapeHtml(formatNumberMaybe(fingerprint.avg_regime_duration_minutes))}</td>
                    <td>${escapeHtml(formatNumberMaybe(fingerprint.trend_trust_avg))}</td>
                    <td>${escapeHtml(fingerprint.current_regime || "--")}</td>
                    <td>${escapeHtml(reasons.join(" "))}</td>
                  </tr>
                `;
              })
              .join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderResearchPresetSummaryTable(rows) {
  if (!rows.length) {
    return "";
  }
  return `
    <div class="research-section">
      <div class="research-section-head">
        <span>Aggregate Preset Results</span>
        <small>${rows.length} presets</small>
      </div>
      <div class="research-table-wrap">
        <table class="research-table research-comparison-table">
          <thead>
            <tr>
              ${researchTh("Preset")}
              ${researchTh("Total P/L")}
              ${researchTh("Avg %")}
              ${researchTh("Date Wins")}
              ${researchTh("Green/Red")}
              ${researchTh("Momentum")}
              ${researchTh("Chop")}
              ${researchTh("Inverse")}
              ${researchTh("Worst Date")}
            </tr>
          </thead>
          <tbody>
            ${rows
              .map(
                (row) => `
                  <tr>
                    <td>${escapeHtml(row.preset_name || "--")}</td>
                    <td class="${researchToneClass(row.total_pl)}">${escapeHtml(
                      formatMoney(row.total_pl),
                    )}</td>
                    <td class="${researchToneClass(row.avg_account_change_percent)}">${escapeHtml(
                      formatPercentMaybe(row.avg_account_change_percent),
                    )}</td>
                    <td>${escapeHtml(String(row.date_wins || 0))}</td>
                    <td>${escapeHtml(`${row.green_days || 0}/${row.red_days || 0}`)}</td>
                    <td class="${researchToneClass(row.momentum_pl)}">${escapeHtml(
                      formatMoney(row.momentum_pl),
                    )}</td>
                    <td class="${researchToneClass(row.chop_pl)}">${escapeHtml(
                      formatMoney(row.chop_pl),
                    )}</td>
                    <td class="${researchToneClass(row.inverse_pl)}">${escapeHtml(
                      formatMoney(row.inverse_pl),
                    )}</td>
                    <td>${escapeHtml(row.worst_date || "--")} ${escapeHtml(
                      formatMoney(row.worst_pl),
                    )}</td>
                  </tr>
                `,
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderSpecialistAuditTable(rows) {
  if (!rows.length) {
    return "";
  }
  return `
    <div class="research-section">
      <div class="research-section-head">
        <span>Specialist Differentiation Audit</span>
        <small>target-bot purity</small>
      </div>
      <div class="research-table-wrap">
        <table class="research-table research-comparison-table">
          <thead>
            <tr>
              ${researchTh("Preset")}
              ${researchTh("Target Bot")}
              ${researchTh("Total P/L")}
              ${researchTh("Target P/L")}
              ${researchTh("Purity")}
              ${researchTh("Non-target Damage")}
              ${researchTh("Home Capture")}
              ${researchTh("Home Target Share")}
              ${researchTh("Home Miss")}
              ${researchTh("Diagnosis")}
            </tr>
          </thead>
          <tbody>
            ${rows.map(renderSpecialistAuditRow).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderSpecialistAuditRow(row) {
  return `
    <tr>
      <td>${escapeHtml(row.preset_name || "--")}</td>
      <td>${escapeHtml(row.target_bot || "--")}</td>
      <td class="${researchToneClass(row.total_pl)}">${escapeHtml(
        formatMoney(row.total_pl),
      )}</td>
      <td class="${researchToneClass(row.target_bot_pl)}">${escapeHtml(
        formatMoney(row.target_bot_pl),
      )}</td>
      <td>${escapeHtml(formatPercentMaybe(row.target_purity_percent))}</td>
      <td class="${researchToneClass(-Number(row.non_target_damage || 0))}">${escapeHtml(
        formatMoney(row.non_target_damage),
      )}</td>
      <td class="${researchToneClass(row.home_turf_capture_efficiency_percent)}">${escapeHtml(
        formatPercentMaybe(row.home_turf_capture_efficiency_percent),
      )}</td>
      <td>${escapeHtml(formatPercentMaybe(row.home_turf_target_share_percent))}</td>
      <td>${escapeHtml(formatMoney(row.home_turf_missed_opportunity))}</td>
      <td>${escapeHtml(formatLabel(row.diagnosis || "--"))}</td>
    </tr>
  `;
}

function renderResearchDateSummaryTable(rows) {
  if (!rows.length) {
    return "";
  }
  return `
    <div class="research-section">
      <div class="research-section-head">
        <span>Date Winners & Fingerprints</span>
        <small>winner fingerprint shown</small>
      </div>
      <div class="research-table-wrap">
        <table class="research-table research-comparison-table">
          <thead>
            <tr>
              ${researchTh("Date")}
              ${researchTh("Winner")}
              ${researchTh("Margin")}
              ${researchTh("Confidence")}
              ${researchTh("Worst Cost")}
              ${researchTh("Trans/hr")}
              ${researchTh("Regime min")}
              ${researchTh("Trust")}
              ${researchTh("30m Trans/hr")}
              ${researchTh("60m Trans/hr")}
            </tr>
          </thead>
          <tbody>
            ${rows.map(renderResearchDateSummaryRow).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderResearchDateSummaryRow(row) {
  const fingerprint = row.winner_fingerprint || {};
  const early30 = row.winner_early_windows?.["30"] || {};
  const early60 = row.winner_early_windows?.["60"] || {};
  return `
    <tr>
      <td>${escapeHtml(row.date || "--")}</td>
      <td>${escapeHtml(row.winner || "--")}</td>
      <td class="${researchToneClass(row.margin_dollars)}">${escapeHtml(
        `${formatMoney(row.margin_dollars)} · ${formatPercentMaybe(row.margin_percent)}`,
      )}</td>
      <td>${escapeHtml(row.winner_confidence || "--")}</td>
      <td class="${researchToneClass(row.worst_misclassification_cost_dollars)}">${escapeHtml(
        formatMoney(row.worst_misclassification_cost_dollars),
      )}</td>
      <td>${escapeHtml(formatNumberMaybe(fingerprint.transitions_per_hour))}</td>
      <td>${escapeHtml(formatNumberMaybe(fingerprint.avg_regime_duration_minutes))}</td>
      <td>${escapeHtml(formatNumberMaybe(fingerprint.trend_trust_avg))}</td>
      <td>${escapeHtml(formatNumberMaybe(early30.transitions_per_hour))}</td>
      <td>${escapeHtml(formatNumberMaybe(early60.transitions_per_hour))}</td>
    </tr>
  `;
}

function formatV9Context(row) {
  const activated = Number(row.v9_momentum_context_activations || 0) > 0;
  if (!activated && !row.v9_momentum_context_activation_reason) {
    return "--";
  }
  const trust = formatNumberMaybe(row.v9_momentum_context_trust_score);
  const soxl = formatPercentMaybe(row.v9_momentum_context_soxl_percent);
  const windowMinutes =
    row.v9_momentum_context_early_window_minutes == null
      ? "30"
      : formatNumberMaybe(row.v9_momentum_context_early_window_minutes);
  const earlyCount = formatNumberMaybe(
    row.v9_momentum_context_early_transition_count,
  );
  const earlyRate = formatNumberMaybe(
    row.v9_momentum_context_early_transitions_per_hour,
  );
  const nonWarmupCount = formatNumberMaybe(
    row.v9_momentum_context_early_non_warmup_transition_count,
  );
  const nonWarmupRate = formatNumberMaybe(
    row.v9_momentum_context_early_non_warmup_transitions_per_hour,
  );
  const observer = row.v9_momentum_context_observer_preset
    ? `O ${row.v9_momentum_context_observer_preset} · `
    : "";
  const activationReason = row.v9_momentum_context_activation_reason;
  const blocker =
    activationReason && activationReason !== "v9_momentum_clean_tape_context"
      ? ` · ${activationReason}`
      : "";
  const invalidation = row.v9_momentum_context_invalidation_reason
    ? ` · ${row.v9_momentum_context_invalidation_reason}`
    : "";
  return `${observer}T ${trust} · SOXL ${soxl} · ${windowMinutes}m raw ${earlyCount}/${earlyRate} · NW ${nonWarmupCount}/${nonWarmupRate}${blocker}${invalidation}`;
}

function formatAuthorityConfig(row) {
  const flags = [];
  const chopPermissionMode = String(row.chop_permission_mode || "OFF").toUpperCase();
  if (chopPermissionMode === "LOOSE") flags.push("CP-L");
  if (chopPermissionMode === "FIREWALL") flags.push("CP-FW");
  if (chopPermissionMode === "STRICT") {
    flags.push("CP-S");
    const chopMaxSource = numberOrNull(row.chop_permission_max_abs_source_percent);
    if (chopMaxSource !== null && chopMaxSource !== 2) {
      flags.push(`CS${formatNumberMaybe(chopMaxSource)}`);
    }
  }
  if (row.momentum_authority_required) flags.push("AR");
  if (row.momentum_authority_revoke_exits) flags.push("RE");
  if (row.momentum_authority_latch_once_active) flags.push("LAT");
  const minTrust = numberOrNull(row.momentum_authority_min_trust_score);
  if (minTrust !== null && minTrust !== 45) {
    flags.push(`T${formatNumberMaybe(minTrust)}`);
  }
  const minSource = numberOrNull(row.momentum_authority_min_source_percent);
  if (minSource !== null && minSource !== 2) {
    flags.push(`S${formatNumberMaybe(minSource)}`);
  }
  const maxTransitions = numberOrNull(
    row.momentum_authority_max_transitions_per_hour,
  );
  if (maxTransitions !== null && maxTransitions !== 8) {
    flags.push(`X${formatNumberMaybe(maxTransitions)}`);
  }
  if (row.momentum_authority_reclaim_enabled) {
    flags.push("RC");
    const reclaimTrust = numberOrNull(
      row.momentum_authority_reclaim_min_trust_score,
    );
    if (reclaimTrust !== null && reclaimTrust !== 58) {
      flags.push(`RT${formatNumberMaybe(reclaimTrust)}`);
    }
    const reclaimSource = numberOrNull(
      row.momentum_authority_reclaim_min_source_percent,
    );
    if (reclaimSource !== null && reclaimSource !== 4) {
      flags.push(`RS${formatNumberMaybe(reclaimSource)}`);
    }
    const reclaimRaw = numberOrNull(
      row.momentum_authority_reclaim_max_raw_transition_count,
    );
    if (reclaimRaw !== null && reclaimRaw !== 1) {
      flags.push(`RR${formatNumberMaybe(reclaimRaw)}`);
    }
    const reclaimNw = numberOrNull(
      row.momentum_authority_reclaim_max_non_warmup_transition_count,
    );
    if (reclaimNw !== null && reclaimNw !== 0) {
      flags.push(`RNW${formatNumberMaybe(reclaimNw)}`);
    }
  }
  if (row.v10_force_no_authority) flags.push("V10F");
  return flags.length ? flags.join("/") : "--";
}

function hasResearchValue(value) {
  return value !== null && value !== undefined && value !== "";
}

function formatV10Context(row) {
  const suppressions = Number(
    row.v10_no_authority_directional_suppression_blocks || 0,
  );
  const hasContext = [
    row.v10_no_authority_context_activation_reason,
    row.v10_no_authority_context_observer_preset,
    row.v10_no_authority_context_trust_score,
    row.v10_no_authority_context_soxl_percent,
    row.v10_no_authority_context_early_transition_count,
    row.v10_no_authority_context_early_non_warmup_transition_count,
  ].some(hasResearchValue);
  if (!suppressions && !hasContext) {
    return "--";
  }
  const trust = formatNumberMaybe(row.v10_no_authority_context_trust_score);
  const soxl = formatPercentMaybe(row.v10_no_authority_context_soxl_percent);
  const runup = formatPercentMaybe(row.v10_no_authority_context_soxl_runup_percent);
  const drawdown = formatPercentMaybe(
    row.v10_no_authority_context_soxl_drawdown_percent,
  );
  const windowMinutes =
    !hasResearchValue(row.v10_no_authority_context_early_window_minutes)
      ? "30"
      : formatNumberMaybe(row.v10_no_authority_context_early_window_minutes);
  const earlyCount = formatNumberMaybe(
    row.v10_no_authority_context_early_transition_count,
  );
  const earlyRate = formatNumberMaybe(
    row.v10_no_authority_context_early_transitions_per_hour,
  );
  const nonWarmupCount = formatNumberMaybe(
    row.v10_no_authority_context_early_non_warmup_transition_count,
  );
  const nonWarmupRate = formatNumberMaybe(
    row.v10_no_authority_context_early_non_warmup_transitions_per_hour,
  );
  const observer = row.v10_no_authority_context_observer_preset
    ? `O ${row.v10_no_authority_context_observer_preset} · `
    : "";
  const activationReason = row.v10_no_authority_context_activation_reason
    ? ` · ${row.v10_no_authority_context_activation_reason}`
    : "";
  const authorityGate = row.v10_no_authority_context_authority_gate
    ? ` · gate ${row.v10_no_authority_context_authority_gate}`
    : "";
  const shadowStatus = row.v10_suppressed_directional_shadow_status
    ? ` · shadow ${row.v10_suppressed_directional_shadow_status}`
    : "";
  const suppressionStatus = suppressions ? "" : " · no post-checkpoint directional suppressions";
  return `${observer}T ${trust} · SOXL ${soxl} · RU ${runup} · DD ${drawdown} · ${windowMinutes}m raw ${earlyCount}/${earlyRate} · NW ${nonWarmupCount}/${nonWarmupRate}${activationReason}${authorityGate}${shadowStatus}${suppressionStatus}`;
}

function renderResearchComparisonRunTable(rows) {
  if (!rows.length) {
    return "";
  }
  return `
    <div class="research-section">
      <div class="research-section-head">
        <span>All Runs</span>
        <small>${rows.length} rows</small>
      </div>
      <div class="research-table-wrap">
        <table class="research-table research-comparison-table">
          <thead>
            <tr>
              ${researchTh("Date")}
              ${researchTh("Preset")}
              ${researchTh("P/L")}
              ${researchTh("%")}
              ${researchTh("Trades")}
              ${researchTh("Win Rate")}
              ${researchTh("Momentum")}
              ${researchTh("Chop")}
              ${researchTh("Inverse")}
              ${researchTh("MFE")}
              ${researchTh("Capture")}
              ${researchTh("Trans/hr")}
              ${researchTh("Early M/C/I")}
              ${researchTh("V8 Blocks Y/T/N")}
              ${researchTh("V9 C/S/I")}
              ${researchTh("V9 Context")}
              ${researchTh("Auth")}
              ${researchTh("V10 D/M/I")}
              ${researchTh("V10 Context")}
            </tr>
          </thead>
          <tbody>
            ${rows.map(renderResearchComparisonRunRow).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderResearchComparisonRunRow(result) {
  const row = result.row || {};
  const fingerprint = result.fingerprint || {};
  return `
    <tr>
      <td>${escapeHtml(result.date || row.date || "--")}</td>
      <td>${escapeHtml(result.preset_name || "--")}</td>
      <td class="${researchToneClass(row.realized_pl_dollars)}">${escapeHtml(
        formatMoney(row.realized_pl_dollars),
      )}</td>
      <td class="${researchToneClass(row.account_change_percent)}">${escapeHtml(
        formatPercentMaybe(row.account_change_percent),
      )}</td>
      <td>${escapeHtml(String(row.closed_trades ?? "--"))}</td>
      <td>${escapeHtml(formatPercentMaybe(row.win_rate))}</td>
      <td class="${researchToneClass(row.momentum_pl)}">${escapeHtml(
        formatMoney(row.momentum_pl),
      )}</td>
      <td class="${researchToneClass(row.chop_pl)}">${escapeHtml(
        formatMoney(row.chop_pl),
      )}</td>
      <td class="${researchToneClass(row.inverse_pl)}">${escapeHtml(
        formatMoney(row.inverse_pl),
      )}</td>
      <td>${escapeHtml(formatPercentMaybe(row.session_avg_mfe_percent))}</td>
      <td class="${researchToneClass(row.session_avg_capture_ratio_percent)}">${escapeHtml(
        formatPercentMaybe(row.session_avg_capture_ratio_percent),
      )}</td>
      <td>${escapeHtml(formatNumberMaybe(fingerprint.transitions_per_hour))}</td>
      <td>${escapeHtml(
        `${row.momentum_early_entry_count ?? 0}/${row.chop_early_entry_count ?? 0}/${row.inverse_early_entry_count ?? 0}`,
      )}</td>
      <td>${escapeHtml(
        `${row.v8_young_regime_blocks ?? 0}/${row.v8_low_trust_blocks ?? 0}/${row.v8_noisy_water_blocks ?? 0}`,
      )}</td>
      <td>${escapeHtml(
        `${row.v9_momentum_context_activations ?? 0}/${row.v9_inverse_suppression_blocks ?? 0}/${row.v9_momentum_context_invalidations ?? 0}`,
      )}</td>
      <td>${escapeHtml(formatV9Context(row))}</td>
      <td>${escapeHtml(formatAuthorityConfig(row))}</td>
      <td>${escapeHtml(
        `${row.v10_no_authority_directional_suppression_blocks ?? 0}/${row.v10_no_authority_momentum_suppression_blocks ?? 0}/${row.v10_no_authority_inverse_suppression_blocks ?? 0}`,
      )}</td>
      <td>${escapeHtml(formatV10Context(row))}</td>
    </tr>
  `;
}

function wireResearchResultActions() {
  const copyButton = document.querySelector("#copyResearchOutputButton");
  if (copyButton) {
    copyButton.addEventListener("click", copyResearchOutput);
  }
}

function markdownCell(value) {
  return String(value ?? "--").replace(/\|/g, "\\|").replace(/\n/g, " ");
}

function markdownRow(cells) {
  return `| ${cells.map(markdownCell).join(" | ")} |`;
}

function markdownDivider(count) {
  return `| ${Array.from({ length: count }, () => "---").join(" | ")} |`;
}

function researchComparisonMarkdown(result) {
  const presetSummaries = Array.isArray(result.preset_summaries)
    ? result.preset_summaries
    : [];
  const dateSummaries = Array.isArray(result.date_summaries)
    ? result.date_summaries
    : [];
  const runs = Array.isArray(result.results) ? result.results : [];
  const specialistAudit = Array.isArray(result.specialist_audit)
    ? result.specialist_audit
    : [];
  const leader = presetSummaries[0] || {};
  const lines = [
    "# EdgeWalker Preset Comparison",
    "",
    `Runs: ${result.run_count || 0}`,
    `Presets: ${result.preset_count || presetSummaries.length}`,
    `Dates: ${dateSummaries.length}`,
    `Fill model: ${formatLabel(result.fill_model || "--")}`,
    `Slippage: ${result.slippage_bps ?? "0"} bps`,
    `Aggregate leader: ${leader.preset_name || "--"} (${formatMoney(
      leader.total_pl,
    )}, ${formatPercentMaybe(leader.avg_account_change_percent)} avg)`,
    "",
    "## Aggregate Preset Results",
    markdownRow([
      "Preset",
      "Total P/L",
      "Avg %",
      "Date Wins",
      "Green/Red",
      "Momentum",
      "Chop",
      "Inverse",
      "Worst Date",
    ]),
    markdownDivider(9),
    ...presetSummaries.map((row) =>
      markdownRow([
        row.preset_name || "--",
        formatMoney(row.total_pl),
        formatPercentMaybe(row.avg_account_change_percent),
        row.date_wins || 0,
        `${row.green_days || 0}/${row.red_days || 0}`,
        formatMoney(row.momentum_pl),
        formatMoney(row.chop_pl),
        formatMoney(row.inverse_pl),
        `${row.worst_date || "--"} ${formatMoney(row.worst_pl)}`,
      ]),
    ),
    "",
    "## Specialist Differentiation Audit",
    markdownRow([
      "Preset",
      "Target Bot",
      "Total P/L",
      "Target P/L",
      "Purity",
      "Non-target Damage",
      "Home Capture",
      "Home Target Share",
      "Home Miss",
      "Home-Turf Dates",
      "Diagnosis",
    ]),
    markdownDivider(11),
    ...specialistAudit.map((row) =>
      markdownRow([
        row.preset_name || "--",
        row.target_bot || "--",
        formatMoney(row.total_pl),
        formatMoney(row.target_bot_pl),
        formatPercentMaybe(row.target_purity_percent),
        formatMoney(row.non_target_damage),
        formatPercentMaybe(row.home_turf_capture_efficiency_percent),
        formatPercentMaybe(row.home_turf_target_share_percent),
        formatMoney(row.home_turf_missed_opportunity),
        Array.isArray(row.home_turf_dates)
          ? row.home_turf_dates.join(", ")
          : "--",
        formatLabel(row.diagnosis || "--"),
      ]),
    ),
    "",
    "## Date Winners & Fingerprints",
    markdownRow([
      "Date",
      "Winner",
      "Margin",
      "Confidence",
      "Worst Cost",
      "Trans/hr",
      "Regime Min",
      "Trust",
      "30m Trans/hr",
      "60m Trans/hr",
    ]),
    markdownDivider(10),
    ...dateSummaries.map((row) => {
      const fingerprint = row.winner_fingerprint || {};
      const early30 = row.winner_early_windows?.["30"] || {};
      const early60 = row.winner_early_windows?.["60"] || {};
      return markdownRow([
        row.date || "--",
        row.winner || "--",
        `${formatMoney(row.margin_dollars)} ${formatPercentMaybe(
          row.margin_percent,
        )}`,
        row.winner_confidence || "--",
        formatMoney(row.worst_misclassification_cost_dollars),
        formatNumberMaybe(fingerprint.transitions_per_hour),
        formatNumberMaybe(fingerprint.avg_regime_duration_minutes),
        formatNumberMaybe(fingerprint.trend_trust_avg),
        formatNumberMaybe(early30.transitions_per_hour),
        formatNumberMaybe(early60.transitions_per_hour),
      ]);
    }),
    "",
    "## All Runs",
    markdownRow([
      "Date",
      "Preset",
      "P/L",
      "%",
      "Trades",
      "Win Rate",
      "Momentum",
      "Chop",
      "Inverse",
      "MFE",
      "Capture",
      "Trans/hr",
      "Early M/C/I",
      "V8 Blocks Y/T/N",
      "V9 C/S/I",
      "V9 Context",
      "Auth",
      "V10 D/M/I",
      "V10 Context",
    ]),
    markdownDivider(19),
    ...runs.map((resultRow) => {
      const row = resultRow.row || {};
      const fingerprint = resultRow.fingerprint || {};
      return markdownRow([
        resultRow.date || row.date || "--",
        resultRow.preset_name || "--",
        formatMoney(row.realized_pl_dollars),
        formatPercentMaybe(row.account_change_percent),
        row.closed_trades ?? "--",
        formatPercentMaybe(row.win_rate),
        formatMoney(row.momentum_pl),
        formatMoney(row.chop_pl),
        formatMoney(row.inverse_pl),
        formatPercentMaybe(row.session_avg_mfe_percent),
        formatPercentMaybe(row.session_avg_capture_ratio_percent),
        formatNumberMaybe(fingerprint.transitions_per_hour),
        `${row.momentum_early_entry_count ?? 0}/${row.chop_early_entry_count ?? 0}/${row.inverse_early_entry_count ?? 0}`,
        `${row.v8_young_regime_blocks ?? 0}/${row.v8_low_trust_blocks ?? 0}/${row.v8_noisy_water_blocks ?? 0}`,
        `${row.v9_momentum_context_activations ?? 0}/${row.v9_inverse_suppression_blocks ?? 0}/${row.v9_momentum_context_invalidations ?? 0}`,
        formatV9Context(row),
        formatAuthorityConfig(row),
        `${row.v10_no_authority_directional_suppression_blocks ?? 0}/${row.v10_no_authority_momentum_suppression_blocks ?? 0}/${row.v10_no_authority_inverse_suppression_blocks ?? 0}`,
        formatV10Context(row),
      ]);
    }),
  ];
  return lines.join("\n");
}

function researchShadowRouterMarkdown(result) {
  const checkpointSummaries = Array.isArray(result.checkpoint_summaries)
    ? result.checkpoint_summaries
    : [];
  const decisions = Array.isArray(result.decisions) ? result.decisions : [];
  const authority = result.authority_summary || {};
  const best = result.best_checkpoint || {};
  const lines = [
    "# EdgeWalker Shadow Router Replay",
    "",
    `Runs: ${result.run_count || 0}`,
    `Presets: ${result.preset_count || 0}`,
    `Dates: ${Array.isArray(result.date_summaries) ? result.date_summaries.length : 0}`,
    `Observer preset: ${result.observer_preset || "--"}`,
    `Fill model: ${formatLabel(result.fill_model || "--")}`,
    `Slippage: ${result.slippage_bps ?? "0"} bps`,
    `Best checkpoint: ${best.checkpoint || "--"} (${formatMoney(
      best.switch_total_pl ?? best.selected_total_pl,
    )}, ${formatPercentMaybe(
      best.switch_accuracy_percent ?? best.accuracy_percent,
    )} switch accuracy)`,
    `Switch model: Generalist pre-checkpoint closed P/L + selected preset trades opened at/after checkpoint`,
    `Authority model: v6 09:45 only; HIGH-confidence specialists route; MODERATE/LOW stay Generalist; extreme early Inverse selloffs and flush-rebound Inverse patterns are blocked for review`,
    "",
    "## 09:45 Authority Candidate",
    markdownRow([
      "Dates",
      "Hit",
      "Accuracy",
      "Authority P/L",
      "Generalist P/L",
      "Δ vs Generalist",
      "Best Switch P/L",
      "Authority Cost",
      "Routes",
      "Blocked",
      "Advisory",
      "Default",
    ]),
    markdownDivider(12),
    markdownRow([
      authority.dates || 0,
      `${authority.correct || 0}/${authority.dates || 0}`,
      formatPercentMaybe(authority.accuracy_percent),
      formatMoney(authority.authority_total_pl),
      formatMoney(authority.generalist_total_pl),
      formatMoney(authority.authority_delta_vs_generalist),
      formatMoney(authority.best_switch_total_pl),
      formatMoney(authority.authority_total_cost_dollars),
      authority.routes || 0,
      authority.blocked || 0,
      authority.advisory_only || 0,
      authority.generalist_default || 0,
    ]),
    "",
    "## Checkpoint Scores",
    markdownRow([
      "Checkpoint",
      "Switch Hit",
      "Switch Accuracy",
      "High Conf",
      "Switch P/L",
      "Δ vs Generalist",
      "Best Switch P/L",
      "Switch Cost",
      "Proxy Selected P/L",
      "Proxy Winner P/L",
    ]),
    markdownDivider(10),
    ...checkpointSummaries.map((row) =>
      markdownRow([
        row.checkpoint || "--",
        `${row.switch_correct || 0}/${row.dates || 0}`,
        formatPercentMaybe(row.switch_accuracy_percent),
        row.high_confidence_count || 0,
        formatMoney(row.switch_total_pl),
        formatMoney(row.switch_delta_vs_generalist_total),
        formatMoney(row.checkpoint_best_total_pl),
        formatMoney(row.switch_total_cost_dollars),
        formatMoney(row.selected_total_pl),
        formatMoney(row.winner_total_pl),
      ]),
    ),
    "",
    "## Checkpoint Decisions",
    markdownRow([
      "Date",
      "Time",
      "Pick",
      "Authority",
      "Auth P/L",
      "Auth Δ",
      "Post Best",
      "Switch Hit",
      "Switch P/L",
      "Δ Gen",
      "Switch Cost",
      "Full-Day Winner",
      "Proxy Correct",
      "Proxy Cost",
      "Router Conf",
      "SOXL %",
      "SOXL DD",
      "Trans/hr",
      "Regime Min",
      "Trust",
      "Regime",
      "Reasons",
    ]),
    markdownDivider(22),
    ...decisions.map((row) => {
      const fingerprint = row.fingerprint || {};
      const reasons = Array.isArray(row.reasons) ? row.reasons.join(" ") : "";
      return markdownRow([
        row.date || "--",
        row.checkpoint || "--",
        row.selected_preset || "--",
        row.authority_action || "--",
        formatMoney(row.authority_pl),
        formatMoney(row.authority_delta_vs_generalist),
        row.checkpoint_best_preset || "--",
        row.switch_correct ? "YES" : "NO",
        formatMoney(row.switch_pl),
        formatMoney(row.switch_delta_vs_generalist),
        formatMoney(row.switch_cost_dollars),
        row.winner || "--",
        row.correct ? "YES" : "NO",
        formatMoney(row.cost_dollars),
        row.router_confidence || "--",
        formatPercentMaybe(fingerprint.source_open_to_current_percent),
        formatPercentMaybe(fingerprint.source_max_drawdown_from_open_percent),
        formatNumberMaybe(fingerprint.transitions_per_hour),
        formatNumberMaybe(fingerprint.avg_regime_duration_minutes),
        formatNumberMaybe(fingerprint.trend_trust_avg),
        fingerprint.current_regime || "--",
        reasons,
      ]);
    }),
  ];
  return lines.join("\n");
}

function researchSingleRunMarkdown(result) {
  const row = result.row || {};
  const performance = result.performance || {};
  const botPerformance = Array.isArray(performance.bot_performance)
    ? performance.bot_performance
    : [];
  const lines = [
    "# EdgeWalker Backtest Result",
    "",
    `Date: ${row.date || result.date || "--"}`,
    `Preset: ${row.preset_name || "--"} (${row.preset_version || "--"})`,
    `P/L: ${formatMoney(row.realized_pl_dollars)} (${formatPercentMaybe(
      row.account_change_percent,
    )})`,
    `Trades: ${row.closed_trades || 0}`,
    `Win rate: ${formatPercentMaybe(row.win_rate)}`,
    `Avg MFE: ${formatPercentMaybe(row.session_avg_mfe_percent)}`,
    `Avg MAE: ${formatPercentMaybe(row.session_avg_mae_percent)}`,
    `Avg capture: ${formatPercentMaybe(row.session_avg_capture_ratio_percent)}`,
    "",
    "## Bot Quality",
    markdownRow(["Bot", "P/L", "MFE", "MAE", "Capture", "Hold"]),
    markdownDivider(6),
    ...botPerformance.map((bot) =>
      markdownRow([
        bot.bot || "--",
        formatMoney(bot.realized_pl),
        formatPercentMaybe(bot.avg_mfe_percent),
        formatPercentMaybe(bot.avg_mae_percent),
        formatPercentMaybe(bot.avg_capture_ratio_percent),
        formatDurationSeconds(bot.avg_hold_seconds),
      ]),
    ),
  ];
  return lines.join("\n");
}

async function copyResearchOutput() {
  const result = state.lastResearchResult;
  if (!result) {
    setResearchMessage("No research output to copy yet.", "warning");
    return;
  }
  const text =
    result.kind === "comparison"
      ? researchComparisonMarkdown(result)
      : result.kind === "shadow_router"
      ? researchShadowRouterMarkdown(result)
      : researchSingleRunMarkdown(result);
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    setResearchMessage("Copied research output to clipboard.", "success");
  } catch (error) {
    setResearchMessage(`Copy failed: ${error.message}`, "danger");
  }
}

function renderResearchMetric(label, value, toneValue = null, tooltip = researchTooltip(label)) {
  return `
    <div class="research-metric">
      ${researchTooltipLabel(label, tooltip)}
      <strong class="${researchToneClass(toneValue)}">${escapeHtml(value)}</strong>
    </div>
  `;
}

function renderResearchBotQuality(rows) {
  const botRows = Array.isArray(rows) ? rows : [];
  if (!botRows.length) {
    return "";
  }
  return `
    <div class="research-section">
      <div class="research-section-head">
        <span>Bot Quality</span>
      </div>
      <div class="research-bot-grid">
        ${botRows.map(renderResearchBotCard).join("")}
      </div>
    </div>
  `;
}

function renderResearchBotCard(row) {
  const realized = numberOrNull(row.realized_pl);
  const capture = row.avg_capture_ratio_percent;
  return `
    <div class="research-bot-card">
      <span>${escapeHtml(formatLabel(row.bot || "Bot"))}</span>
      <strong class="${researchToneClass(realized)}">${escapeHtml(
        formatMoney(realized),
      )}</strong>
      <dl>
        <div>
          <dt>MFE</dt>
          <dd>${escapeHtml(formatPercentMaybe(row.avg_mfe_percent))}</dd>
        </div>
        <div>
          <dt>MAE</dt>
          <dd>${escapeHtml(formatPercentMaybe(row.avg_mae_percent))}</dd>
        </div>
        <div>
          <dt>Capture</dt>
          <dd class="${researchToneClass(capture)}">${escapeHtml(
            formatPercentMaybe(capture),
          )}</dd>
        </div>
        <div>
          <dt>Hold</dt>
          <dd>${escapeHtml(formatDurationSeconds(row.avg_hold_seconds))}</dd>
        </div>
      </dl>
    </div>
  `;
}

function renderResearchArchaeology(report) {
  if (!report || !report.bot) {
    return "";
  }
  const quality = report.quality || {};
  const hypotheses = Array.isArray(report.hypotheses) ? report.hypotheses : [];
  return `
    <div class="research-section">
      <div class="research-section-head">
        <span>${escapeHtml(formatLabel(report.bot))} Archaeology</span>
        <small>${escapeHtml(String(report.trade_count || 0))} trades</small>
      </div>
      <div class="research-archaeology-grid">
        ${renderResearchMetric(
          "Near-zero MFE",
          `${report.near_zero_mfe_count || 0}/${report.trade_count || 0}`,
        )}
        ${renderResearchMetric(
          "Low Capture",
          `${report.meaningful_mfe_low_capture_count || 0}/${
            report.trade_count || 0
          }`,
        )}
        ${renderResearchMetric(
          "Adverse > Favorable",
          `${report.larger_adverse_than_favorable_count || 0}/${
            report.trade_count || 0
          }`,
        )}
        ${renderResearchMetric(
          "Avg Capture",
          formatPercentMaybe(quality.avg_capture_ratio_percent),
          quality.avg_capture_ratio_percent,
        )}
      </div>
      ${
        hypotheses.length
          ? `<ol class="research-hypotheses">${hypotheses
              .map(
                (item) => `
                  <li>
                    <strong>${escapeHtml(item.hypothesis || "Hypothesis")}</strong>
                    <span>${escapeHtml(item.evidence || "")}</span>
                  </li>
                `,
              )
              .join("")}</ol>`
          : ""
      }
    </div>
  `;
}

function renderResearchTrades(trades) {
  const rows = Array.isArray(trades) ? trades : [];
  if (!rows.length) {
    return `
      <div class="research-section">
        <div class="research-section-head">
          <span>Closed Trades</span>
        </div>
        <p class="research-empty">No closed trades in this replay.</p>
      </div>
    `;
  }
  return `
    <div class="research-section">
      <div class="research-section-head">
        <span>Closed Trades</span>
        <small>${rows.length} rows</small>
      </div>
      <div class="research-table-wrap">
        <table class="research-table">
          <thead>
            <tr>
              <th>Bot</th>
              <th>Symbol</th>
              <th>P/L</th>
              <th>MFE</th>
              <th>MAE</th>
              <th>Capture</th>
              <th>Hold</th>
              <th>Exit</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(renderResearchTradeRow).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderResearchTradeRow(trade) {
  const realized = numberOrNull(trade.realized_pl);
  return `
    <tr>
      <td>${escapeHtml(formatLabel(trade.bot || "Bot"))}</td>
      <td>${escapeHtml(trade.symbol || "--")}</td>
      <td class="${researchToneClass(realized)}">${escapeHtml(
        formatMoney(realized),
      )}</td>
      <td>${escapeHtml(formatPercentMaybe(trade.mfe_percent))}</td>
      <td>${escapeHtml(formatPercentMaybe(trade.mae_percent))}</td>
      <td class="${researchToneClass(trade.capture_ratio_percent)}">${escapeHtml(
        formatPercentMaybe(trade.capture_ratio_percent),
      )}</td>
      <td>${escapeHtml(formatDurationSeconds(trade.hold_seconds))}</td>
      <td>${escapeHtml(formatLabel(trade.exit_reason || "Exit"))}</td>
    </tr>
  `;
}

function renderResearchMode() {
  if (els.researchMode) {
    els.researchMode.checked = state.researchModeEnabled;
  }
  if (els.researchControls) {
    els.researchControls.hidden = !state.researchModeEnabled;
  }
  if (els.controlsActionRow) {
    els.controlsActionRow.hidden = state.researchModeEnabled;
  }
  document.body.classList.toggle("research-mode", state.researchModeEnabled);
  renderResearchResults();
}

function applySettings(settings) {
  if (!settings) return;
  state.activeEnvironment = settings.active_environment || "paper";
  state.liveTradingArmed = Boolean(settings.live_trading_armed);
  state.liveCredentialsReady = Boolean(
    settings.live?.has_api_key_id && settings.live?.has_api_secret_key,
  );
  if (els.activeEnvironment) {
    els.activeEnvironment.value = state.activeEnvironment;
  }
  if (els.dataBaseUrl) {
    els.dataBaseUrl.value = settings.data_base_url || "";
  }
  if (els.dataFeed) {
    els.dataFeed.value = settings.data_feed || "";
  }
  if (els.paperTradingUrl) {
    els.paperTradingUrl.value = settings.paper?.trading_base_url || "";
  }
  if (els.liveTradingUrl) {
    els.liveTradingUrl.value = settings.live?.trading_base_url || "";
  }
  if (els.spreadsheetUrl) {
    els.spreadsheetUrl.value =
      settings.operator_spreadsheet?.spreadsheet_url || "";
  }
  if (els.spreadsheetPostEndpoint) {
    els.spreadsheetPostEndpoint.value =
      settings.operator_spreadsheet?.post_endpoint_url || "";
  }
  if (els.researchSpreadsheetUrl) {
    els.researchSpreadsheetUrl.value =
      settings.operator_spreadsheet?.research_spreadsheet_url || "";
  }
  if (els.researchSpreadsheetPostEndpoint) {
    els.researchSpreadsheetPostEndpoint.value =
      settings.operator_spreadsheet?.research_post_endpoint_url || "";
  }
  state.researchModeEnabled = Boolean(
    settings.operator_spreadsheet?.research_mode_enabled,
  );
  renderResearchMode();
  if (els.spreadsheetIncludeNarrative) {
    els.spreadsheetIncludeNarrative.checked =
      settings.operator_spreadsheet?.include_daily_narrative !== false;
  }
  if (els.spreadsheetAutoPost) {
    els.spreadsheetAutoPost.checked = Boolean(
      settings.operator_spreadsheet?.auto_post_enabled,
    );
  }
  const notifications = settings.notifications || {};
  if (els.notificationsEnabled) {
    els.notificationsEnabled.checked = Boolean(notifications.enabled);
  }
  if (els.notificationEmail) {
    els.notificationEmail.value = notifications.email || "";
  }
  if (els.notificationAppsScriptUrl) {
    els.notificationAppsScriptUrl.value = notifications.apps_script_url || "";
  }
  if (els.notificationErrorCooldown) {
    els.notificationErrorCooldown.value =
      notifications.error_cooldown_minutes || 30;
  }
  if (els.notifyTradeEntered) {
    els.notifyTradeEntered.checked = notifications.notify_trade_entered !== false;
  }
  if (els.notifyTradeExited) {
    els.notifyTradeExited.checked = notifications.notify_trade_exited !== false;
  }
  if (els.notifyDailySummary) {
    els.notifyDailySummary.checked = notifications.notify_daily_summary !== false;
  }
  if (els.notifyWarmup) {
    els.notifyWarmup.checked = notifications.notify_warmup === true;
  }
  if (els.notifyDataErrors) {
    els.notifyDataErrors.checked = notifications.notify_data_errors !== false;
  }

  const secretFields = [
    [els.paperApiKey, settings.paper?.api_key_id_masked],
    [els.paperApiSecret, settings.paper?.api_secret_key_masked],
    [els.liveApiKey, settings.live?.api_key_id_masked],
    [els.liveApiSecret, settings.live?.api_secret_key_masked],
    [
      els.notificationAppsScriptSecret,
      notifications.apps_script_secret_masked,
    ],
  ];
  secretFields.forEach(([input, masked]) => {
    if (!input) return;
    input.value = "";
    input.placeholder = masked || "Not configured";
  });
  if (els.liveArmStatus) {
    els.liveArmStatus.textContent = state.liveTradingArmed
      ? "Live trading armed"
      : "Live trading not armed";
    els.liveArmStatus.classList.toggle("is-armed", state.liveTradingArmed);
  }
  renderMode(
    state.dryRun,
    state.activeEnvironment,
    state.liveTradingArmed,
    state.liveCredentialsReady,
  );
}

async function loadSettings() {
  const settings = await request("/api/settings");
  applySettings(settings);
  return settings;
}

function settingsPayloadFromForm() {
  return {
    active_environment: els.activeEnvironment?.value || "paper",
    data_base_url: els.dataBaseUrl?.value || "",
    data_feed: els.dataFeed?.value || "iex",
    paper: {
      trading_base_url: els.paperTradingUrl?.value || "",
      api_key_id: els.paperApiKey?.value || "",
      api_secret_key: els.paperApiSecret?.value || "",
    },
    live: {
      trading_base_url: els.liveTradingUrl?.value || "",
      api_key_id: els.liveApiKey?.value || "",
      api_secret_key: els.liveApiSecret?.value || "",
    },
    operator_spreadsheet: {
      spreadsheet_url: els.spreadsheetUrl?.value || "",
      post_endpoint_url: els.spreadsheetPostEndpoint?.value || "",
      research_spreadsheet_url: els.researchSpreadsheetUrl?.value || "",
      research_post_endpoint_url: els.researchSpreadsheetPostEndpoint?.value || "",
      research_mode_enabled: Boolean(els.researchMode?.checked),
      auto_post_enabled: Boolean(els.spreadsheetAutoPost?.checked),
      include_daily_narrative: Boolean(els.spreadsheetIncludeNarrative?.checked),
    },
    notifications: {
      enabled: Boolean(els.notificationsEnabled?.checked),
      email: els.notificationEmail?.value || "",
      apps_script_url: els.notificationAppsScriptUrl?.value || "",
      apps_script_secret: els.notificationAppsScriptSecret?.value || "",
      notify_trade_entered: Boolean(els.notifyTradeEntered?.checked),
      notify_trade_exited: Boolean(els.notifyTradeExited?.checked),
      notify_daily_summary: Boolean(els.notifyDailySummary?.checked),
      notify_warmup: Boolean(els.notifyWarmup?.checked),
      notify_data_errors: Boolean(els.notifyDataErrors?.checked),
      error_cooldown_minutes: els.notificationErrorCooldown?.value || "30",
    },
  };
}

async function saveSettings({
  rethrow = false,
  messageSetter = setSettingsMessage,
  button = els.settingsSave,
} = {}) {
  if (button) button.disabled = true;
  messageSetter("Saving settings...");
  try {
    const settings = await request("/api/settings", {
      method: "POST",
      body: JSON.stringify(settingsPayloadFromForm()),
    });
    applySettings(settings);
    messageSetter("Settings saved.", "success");
  } catch (error) {
    messageSetter(error.message, "danger");
    if (rethrow) {
      throw error;
    }
  } finally {
    if (button) button.disabled = false;
  }
}

async function testConnection(environment) {
  const button =
    environment === "live" ? els.testLiveConnection : els.testPaperConnection;
  if (button) button.disabled = true;
  setSettingsMessage(`Testing ${environment} connection...`);
  try {
    await saveSettings({ rethrow: true });
    const result = await request("/api/settings/test", {
      method: "POST",
      body: JSON.stringify({ environment }),
    });
    const value = result.portfolio_value
      ? ` Portfolio ${formatMoney(result.portfolio_value)}.`
      : "";
    setSettingsMessage(
      `${environment === "live" ? "Live" : "Paper"} connection OK.${value}`,
      "success",
    );
  } catch (error) {
    setSettingsMessage(error.message, "danger");
  } finally {
    if (button) button.disabled = false;
  }
}

async function armLiveTrading() {
  const confirmation = els.liveArmInput?.value || "";
  if (els.liveArmButton) els.liveArmButton.disabled = true;
  setSettingsMessage("Arming live trading...");
  try {
    const settings = await request("/api/live-arm", {
      method: "POST",
      body: JSON.stringify({ confirmation }),
    });
    applySettings(settings);
    if (els.liveArmInput) els.liveArmInput.value = "";
    setSettingsMessage(
      "Live trading armed. Confirm the active environment before starting the loop.",
      "warning",
    );
  } catch (error) {
    setSettingsMessage(error.message, "danger");
  } finally {
    if (els.liveArmButton) els.liveArmButton.disabled = false;
  }
}

async function disarmLiveTrading() {
  if (els.liveDisarmButton) els.liveDisarmButton.disabled = true;
  setSettingsMessage("Disarming live trading...");
  try {
    const settings = await request("/api/live-disarm", {
      method: "POST",
      body: JSON.stringify({}),
    });
    applySettings(settings);
    setSettingsMessage("Live trading disarmed.", "success");
  } catch (error) {
    setSettingsMessage(error.message, "danger");
  } finally {
    if (els.liveDisarmButton) els.liveDisarmButton.disabled = false;
  }
}

function openOperatorSpreadsheet() {
  const url = (els.spreadsheetUrl?.value || "").trim();
  if (!url) {
    setSpreadsheetMessage("Add an Operator Spreadsheet URL first.", "warning");
    return;
  }
  window.open(url, "_blank", "noopener");
}

function openResearchSpreadsheet() {
  const url = (els.researchSpreadsheetUrl?.value || "").trim();
  if (!url) {
    setSpreadsheetMessage("Add a Research Spreadsheet URL first.", "warning");
    return;
  }
  window.open(url, "_blank", "noopener");
}

function saveSpreadsheetSettings() {
  return saveSettings({
    messageSetter: setSpreadsheetMessage,
    button: els.spreadsheetSave,
  });
}

function saveNotificationSettings() {
  return saveSettings({
    messageSetter: setNotificationsMessage,
    button: els.notificationsSave,
  });
}

async function sendTestNotification() {
  if (els.notificationTest) {
    els.notificationTest.disabled = true;
  }
  setNotificationsMessage("Saving notification settings...");
  try {
    await saveSettings({
      rethrow: true,
      messageSetter: setNotificationsMessage,
      button: els.notificationsSave,
    });
    setNotificationsMessage("Sending test email...");
    await request("/api/notifications/test", {
      method: "POST",
      body: JSON.stringify({}),
    });
    setNotificationsMessage("Test email sent.", "success");
  } catch (error) {
    setNotificationsMessage(error.message, "danger");
  } finally {
    if (els.notificationTest) {
      els.notificationTest.disabled = false;
    }
  }
}

function defaultBacktestDate() {
  const now = new Date();
  const candidate = new Date(now);
  if (candidate.getHours() < 16) {
    candidate.setDate(candidate.getDate() - 1);
  }
  while (candidate.getDay() === 0 || candidate.getDay() === 6) {
    candidate.setDate(candidate.getDate() - 1);
  }
  const month = String(candidate.getMonth() + 1).padStart(2, "0");
  const day = String(candidate.getDate()).padStart(2, "0");
  return `${candidate.getFullYear()}-${month}-${day}`;
}

function ensureBacktestDefaults() {
  if (els.backtestDate && !els.backtestDate.value) {
    els.backtestDate.value = defaultBacktestDate();
  }
  if (els.backtestFeed && !els.backtestFeed.value) {
    els.backtestFeed.value = els.dataFeed?.value || "iex";
  }
  syncResearchStartingAccount({ force: !els.backtestStartingAccount?.value });
  if (els.backtestFillModel && !els.backtestFillModel.value) {
    els.backtestFillModel.value = "next_bar_open";
  }
  if (els.backtestPresetName && !els.backtestPresetName.value) {
    els.backtestPresetName.value = "Current Controls";
  }
  if (els.backtestPresetVersion && !els.backtestPresetVersion.value) {
    els.backtestPresetVersion.value = "v1";
  }
}

function parseResearchCompareDates() {
  const raw = els.researchCompareDates?.value || "";
  const dates = raw
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  return Array.from(new Set(dates));
}

async function runBacktest() {
  ensureBacktestDefaults();
  if (!els.backtestDate?.value) {
    setResearchMessage("Choose a backtest date first.", "warning");
    return;
  }
  state.researchBusy = true;
  if (els.runBacktest) {
    els.runBacktest.disabled = true;
  }
  syncResearchPresetButtons();
  setResearchMessage("Saving settings...");
  try {
    await saveSettings({
      rethrow: true,
      messageSetter: setResearchMessage,
      button: null,
    });
    setResearchMessage("Running historical replay...");
    startResearchProgress("Running 1 historical replay");
    const payload = {
      ...payloadFromForm(),
      backtest_date: els.backtestDate.value,
      data_feed: els.backtestFeed?.value || els.dataFeed?.value || "iex",
      starting_account_value: els.backtestStartingAccount?.value || "100000",
      fill_model: els.backtestFillModel?.value || "next_bar_open",
      slippage_bps: els.backtestSlippage?.value || "0",
      preset_name: els.backtestPresetName?.value || "Current Controls",
      preset_version: els.backtestPresetVersion?.value || "v1",
      research_post_endpoint_url:
        els.researchSpreadsheetPostEndpoint?.value || "",
    };
    const result = await request("/api/research/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.lastResearchResult = result;
    renderResearchResults(result);
    const postedText = result.posted ? " Posted to research sheet." : "";
    setResearchMessage(
      `Backtest complete: ${formatMoney(result.row?.realized_pl_dollars || 0)} across ${result.trade_count || 0} trades.${postedText}`,
      "success",
    );
  } catch (error) {
    setResearchMessage(error.message, "danger");
  } finally {
    stopResearchProgress();
    state.researchBusy = false;
    if (els.runBacktest) {
      els.runBacktest.disabled = false;
    }
    syncResearchPresetButtons();
  }
}

async function runResearchComparison() {
  ensureBacktestDefaults();
  const dates = parseResearchCompareDates();
  if (!dates.length) {
    setResearchMessage("Add at least one comparison date.", "warning");
    return;
  }
  const presets = selectedResearchComparePresets();
  if (presets.length < 2) {
    setResearchMessage("Choose at least two saved presets to compare.", "warning");
    return;
  }
  state.researchBusy = true;
  syncResearchPresetButtons();
  const runCount = dates.length * presets.length;
  setResearchMessage(
    `Comparing ${presets.length} presets across ${dates.length} dates...`,
  );
  startResearchProgress(`Running ${runCount} replay runs`);
  try {
    await saveSettings({
      rethrow: true,
      messageSetter: setResearchMessage,
      button: null,
    });
    const payload = {
      dates,
      data_feed: els.backtestFeed?.value || els.dataFeed?.value || "iex",
      starting_account_value: els.backtestStartingAccount?.value || "100000",
      fill_model: els.backtestFillModel?.value || "next_bar_open",
      slippage_bps: els.backtestSlippage?.value || "0",
      presets: presets.map((preset) => ({
        name: preset.name,
        version: preset.version || "v1",
        notes: preset.notes || "",
        config: preset.config || {},
      })),
    };
    const result = await request("/api/research/compare", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.lastResearchResult = result;
    renderResearchResults(result);
    const leader = Array.isArray(result.preset_summaries)
      ? result.preset_summaries[0]
      : null;
    const leaderText = leader
      ? ` Leader: ${leader.preset_name} at ${formatMoney(leader.total_pl)}.`
      : "";
    setResearchMessage(
      `Comparison complete: ${result.run_count || 0} replay runs.${leaderText}`,
      "success",
    );
  } catch (error) {
    setResearchMessage(error.message, "danger");
  } finally {
    stopResearchProgress();
    state.researchBusy = false;
    syncResearchPresetButtons();
  }
}

async function runShadowRouterReplay() {
  ensureBacktestDefaults();
  const dates = parseResearchCompareDates();
  if (!dates.length) {
    setResearchMessage("Add at least one comparison date.", "warning");
    return;
  }
  const presets = selectedResearchComparePresets();
  if (presets.length < 2) {
    setResearchMessage("Choose at least two saved presets to evaluate.", "warning");
    return;
  }
  state.researchBusy = true;
  syncResearchPresetButtons();
  const runCount = dates.length * presets.length;
  setResearchMessage(
    `Evaluating shadow router across ${dates.length} dates...`,
  );
  startResearchProgress(`Running ${runCount} replay runs for shadow router`);
  try {
    await saveSettings({
      rethrow: true,
      messageSetter: setResearchMessage,
      button: null,
    });
    const payload = {
      dates,
      data_feed: els.backtestFeed?.value || els.dataFeed?.value || "iex",
      starting_account_value: els.backtestStartingAccount?.value || "100000",
      fill_model: els.backtestFillModel?.value || "next_bar_open",
      slippage_bps: els.backtestSlippage?.value || "0",
      presets: presets.map((preset) => ({
        name: preset.name,
        version: preset.version || "v1",
        notes: preset.notes || "",
        config: preset.config || {},
      })),
    };
    const result = await request("/api/research/shadow-router", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.lastResearchResult = result;
    renderResearchResults(result);
    const best = result.best_checkpoint || {};
    const authority = result.authority_summary || {};
    const bestText = best.checkpoint
      ? ` Best raw checkpoint: ${best.checkpoint} at ${formatMoney(
          best.switch_total_pl ?? best.selected_total_pl,
        )}. 09:45 authority: ${formatMoney(authority.authority_total_pl)}.`
      : "";
    setResearchMessage(
      `Shadow router replay complete: ${result.run_count || 0} replay runs.${bestText}`,
      "success",
    );
  } catch (error) {
    setResearchMessage(error.message, "danger");
  } finally {
    stopResearchProgress();
    state.researchBusy = false;
    syncResearchPresetButtons();
  }
}

async function postSpreadsheetDailyRow() {
  if (els.postSpreadsheetDailyRow) {
    els.postSpreadsheetDailyRow.disabled = true;
  }
  setSpreadsheetMessage("Saving spreadsheet settings...");
  try {
    await saveSettings({
      rethrow: true,
      messageSetter: setSpreadsheetMessage,
      button: els.spreadsheetSave,
    });
    setSpreadsheetMessage("Posting latest daily row...");
    const result = await request("/api/spreadsheet/post", {
      method: "POST",
      body: JSON.stringify({
        post_endpoint_url: els.spreadsheetPostEndpoint?.value || "",
        operator_notes: els.spreadsheetOperatorNotes?.value || "",
        include_daily_narrative: Boolean(els.spreadsheetIncludeNarrative?.checked),
      }),
    });
    const narrativeWarning = result.narrative_error
      ? ` Narrative was skipped: ${result.narrative_error.slice(0, 120)}`
      : "";
    setSpreadsheetMessage(
      `Posted ${result.date || "latest session"} to Operator Spreadsheet.${narrativeWarning}`,
      result.narrative_error ? "warning" : "success",
    );
    if (els.spreadsheetOperatorNotes) {
      els.spreadsheetOperatorNotes.value = "";
    }
  } catch (error) {
    setSpreadsheetMessage(error.message, "danger");
  } finally {
    if (els.postSpreadsheetDailyRow) {
      els.postSpreadsheetDailyRow.disabled = false;
    }
  }
}

function setupOperatorSpreadsheetModal() {
  if (!els.operatorSpreadsheetDialog || !els.operatorSpreadsheetOpen) return;
  const closeSpreadsheet = () => {
    if (els.operatorSpreadsheetDialog.open) {
      els.operatorSpreadsheetDialog.close();
    }
  };

  els.operatorSpreadsheetOpen.addEventListener("click", async () => {
    hideTooltip();
    setSpreadsheetMessage("Loading spreadsheet settings...");
    if (typeof els.operatorSpreadsheetDialog.showModal === "function") {
      els.operatorSpreadsheetDialog.showModal();
    } else {
      els.operatorSpreadsheetDialog.setAttribute("open", "");
    }
    try {
      await loadSettings();
      setSpreadsheetMessage("");
    } catch (error) {
      setSpreadsheetMessage(error.message, "danger");
    }
  });

  if (els.operatorSpreadsheetClose) {
    els.operatorSpreadsheetClose.addEventListener("click", closeSpreadsheet);
  }
  els.operatorSpreadsheetDialog.addEventListener("click", (event) => {
    if (event.target === els.operatorSpreadsheetDialog) {
      closeSpreadsheet();
    }
  });
  if (els.spreadsheetSave) {
    els.spreadsheetSave.addEventListener("click", saveSpreadsheetSettings);
  }
  if (els.openOperatorSpreadsheet) {
    els.openOperatorSpreadsheet.addEventListener("click", openOperatorSpreadsheet);
  }
  if (els.openResearchSpreadsheet) {
    els.openResearchSpreadsheet.addEventListener("click", openResearchSpreadsheet);
  }
  if (els.postSpreadsheetDailyRow) {
    els.postSpreadsheetDailyRow.addEventListener("click", postSpreadsheetDailyRow);
  }
}

function setupNotificationsModal() {
  if (!els.notificationsDialog || !els.notificationsOpen) return;
  const closeNotifications = () => {
    if (els.notificationsDialog.open) {
      els.notificationsDialog.close();
    }
  };

  els.notificationsOpen.addEventListener("click", async () => {
    hideTooltip();
    setNotificationsMessage("Loading notification settings...");
    if (typeof els.notificationsDialog.showModal === "function") {
      els.notificationsDialog.showModal();
    } else {
      els.notificationsDialog.setAttribute("open", "");
    }
    try {
      await loadSettings();
      setNotificationsMessage("");
    } catch (error) {
      setNotificationsMessage(error.message, "danger");
    }
  });

  if (els.notificationsClose) {
    els.notificationsClose.addEventListener("click", closeNotifications);
  }
  els.notificationsDialog.addEventListener("click", (event) => {
    if (event.target === els.notificationsDialog) {
      closeNotifications();
    }
  });
  if (els.notificationsSave) {
    els.notificationsSave.addEventListener("click", saveNotificationSettings);
  }
  if (els.notificationTest) {
    els.notificationTest.addEventListener("click", sendTestNotification);
  }
}

function setupSettingsModal() {
  if (!els.settingsDialog || !els.settingsOpen) return;
  const closeSettings = () => {
    if (els.settingsDialog.open) {
      els.settingsDialog.close();
    }
  };
  els.settingsOpen.addEventListener("click", async () => {
    hideTooltip();
    setSettingsMessage("Loading settings...");
    if (typeof els.settingsDialog.showModal === "function") {
      els.settingsDialog.showModal();
    } else {
      els.settingsDialog.setAttribute("open", "");
    }
    try {
      await loadSettings();
      setSettingsMessage("");
    } catch (error) {
      setSettingsMessage(error.message, "danger");
    }
  });
  if (els.settingsClose) {
    els.settingsClose.addEventListener("click", closeSettings);
  }
  els.settingsDialog.addEventListener("click", (event) => {
    if (event.target === els.settingsDialog) {
      closeSettings();
    }
  });
  if (els.settingsSave) {
    els.settingsSave.addEventListener("click", saveSettings);
  }
  if (els.testPaperConnection) {
    els.testPaperConnection.addEventListener("click", () => testConnection("paper"));
  }
  if (els.testLiveConnection) {
    els.testLiveConnection.addEventListener("click", () => testConnection("live"));
  }
  if (els.liveArmButton) {
    els.liveArmButton.addEventListener("click", armLiveTrading);
  }
  if (els.liveDisarmButton) {
    els.liveDisarmButton.addEventListener("click", disarmLiveTrading);
  }
}

async function persistResearchModeToggle() {
  state.researchModeEnabled = Boolean(els.researchMode?.checked);
  renderResearchMode();
  ensureBacktestDefaults();
  await saveSettings({
    messageSetter: () => {},
    button: null,
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

function sectionCollapseStorageKey(key) {
  return `${SECTION_COLLAPSED_PREFIX}${key}`;
}

function saveSectionCollapsed(key, collapsed) {
  try {
    localStorage.setItem(sectionCollapseStorageKey(key), collapsed ? "1" : "0");
  } catch {
    return;
  }
}

function loadSectionCollapsed(key) {
  try {
    return localStorage.getItem(sectionCollapseStorageKey(key)) === "1";
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

function setCollapsibleSection(button, collapsed, persist = true) {
  const targetSelector = button.dataset.collapseTarget;
  const target = targetSelector ? document.querySelector(targetSelector) : null;
  const panel = button.closest(".collapsible-panel");
  if (!target || !panel) {
    return;
  }
  const label = button.dataset.collapseLabel || "section";
  const key = button.dataset.collapseKey || targetSelector;
  panel.classList.toggle("is-collapsed", collapsed);
  target.hidden = collapsed;
  button.textContent = collapsed ? "Show" : "Hide";
  button.setAttribute("aria-expanded", String(!collapsed));
  button.dataset.tooltip = collapsed ? `Show ${label}.` : `Hide ${label}.`;
  if (persist) {
    saveSectionCollapsed(key, collapsed);
  }
}

function setupCollapsibleSections() {
  document.querySelectorAll("[data-collapse-target]").forEach((button) => {
    const key = button.dataset.collapseKey || button.dataset.collapseTarget;
    setCollapsibleSection(button, loadSectionCollapsed(key), false);
    button.addEventListener("click", () => {
      const collapsed = button.getAttribute("aria-expanded") === "true";
      setCollapsibleSection(button, collapsed);
    });
  });
}

function setCopyButtonState(label, tooltip, stateName = "") {
  if (!els.activityCopy) {
    return;
  }
  els.activityCopy.setAttribute("aria-label", label);
  els.activityCopy.dataset.tooltip = tooltip;
  if (stateName) {
    els.activityCopy.dataset.copyState = stateName;
  } else {
    delete els.activityCopy.dataset.copyState;
  }
  if (els.activityCopyLabel) {
    els.activityCopyLabel.textContent = label;
  }
}

async function copyActivityLog() {
  if (!els.activityCopy) {
    return;
  }

  const isNarrative = state.activeTab === "narrative";
  const text = isNarrative
    ? (state.narrativeText || "")
    : (state.logText || els.log?.textContent || "");
  const originalLabel =
    els.activityCopy.getAttribute("aria-label") || "Copy current tab text";
  const originalTooltip = els.activityCopy.dataset.tooltip;
  const originalState = els.activityCopy.dataset.copyState || "";

  if (!text.trim()) {
    setCopyButtonState(
      "Nothing to copy",
      isNarrative
        ? "There is no narrative to copy yet."
        : "There is no activity log text to copy yet.",
      "empty",
    );
    window.setTimeout(() => {
      setCopyButtonState(originalLabel, originalTooltip, originalState);
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
    setCopyButtonState(
      "Copied",
      isNarrative ? "Narrative copied." : "Activity log copied.",
      "success",
    );
  } catch {
    setCopyButtonState("Copy failed", "Could not copy.", "error");
  } finally {
    window.setTimeout(() => {
      setCopyButtonState(originalLabel, originalTooltip, originalState);
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
  if (!isActivity) {
    loadServerNarrativeCacheForSelection();
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

function applyNarrativeData(data) {
  state.narrativeSections = normalizeNarrativeSections(data.narrative);
  state.narrativeDate = data.date;
  state.narrativeDisplayDate = data.display_date;
  state.narrativeCycles = data.cycle_count;
  state.narrativeText = state.narrativeSections
    ? narrativeCopyText()
    : legacyNarrativeText(data.summary);
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
  if (!snapshot) {
    loadServerNarrativeCacheForSelection();
  }
}

async function loadServerNarrativeCacheForSelection() {
  if (
    state.narrativeCacheLoading ||
    state.narrativeLoading ||
    state.narrativeText ||
    state.narrativeSections
  ) {
    return;
  }

  state.narrativeCacheLoading = true;
  try {
    const payload = { timeframe: state.narrativeTimeframe };
    if (state.narrativeTimeframe === "CUSTOM") {
      ensureCustomDateDefaults();
      payload.start_date = state.narrativeCustomStart;
      payload.end_date = state.narrativeCustomEnd;
    }
    const data = await request("/api/summary/cache", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (!data.available) {
      return;
    }
    applyNarrativeData(data);
    saveCurrentNarrativeToCache();
    renderNarrative();
    updateNarrativeGenerateButton();
  } catch {
    // Server-side narrative cache is optional; absence should not interrupt the UI.
  } finally {
    state.narrativeCacheLoading = false;
  }
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
    if (state.narrativeText || state.narrativeSections) {
      payload.force = true;
    }
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
    applyNarrativeData(data);
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
    maximumFractionDigits: 2,
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

function formatPercentMaybe(value) {
  return value === null || value === undefined ? "--" : formatPercent(value);
}

function formatNumberMaybe(value, digits = 2) {
  const parsed = numberOrNull(value);
  if (parsed === null) {
    return "--";
  }
  return parsed.toLocaleString([], {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function formatDurationSeconds(value) {
  const parsed = numberOrNull(value);
  if (parsed === null) {
    return "--";
  }
  const totalSeconds = Math.max(Math.round(parsed), 0);
  if (totalSeconds < 60) {
    return `${totalSeconds}s`;
  }
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes < 60) {
    return seconds ? `${minutes}m ${seconds}s` : `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

function researchToneClass(value) {
  const parsed = numberOrNull(value);
  if (parsed === null || parsed === 0) {
    return "is-neutral";
  }
  return parsed > 0 ? "is-positive" : "is-negative";
}

function strategyDayPl(status, performance) {
  const realized = numberOrNull(performance?.session_realized_pl);
  const unrealized = numberOrNull(status?.position_unrealized_pl);
  if (realized === null && unrealized === null) {
    return { value: null, percent: null };
  }

  const value = (realized ?? 0) + (unrealized ?? 0);
  const accountValue = numberOrNull(status?.portfolio_value);
  const startingValue =
    accountValue === null ? null : Math.max(0, accountValue - value);
  const percent =
    startingValue === null || startingValue === 0
      ? null
      : (value / startingValue) * 100;

  return { value, percent };
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

function formatPositionQty(value) {
  const parsed = numberOrNull(value);
  if (parsed === null) {
    return null;
  }
  return parsed.toLocaleString([], {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
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
    close_route_invalidated_position_no_same_cycle_reversal:
      "Closed Invalidated Route",
    close_stale_position_no_same_cycle_reversal: "Closed Stale Exposure",
    wait_for_route_invalidated_close: "Waiting For Route Close",
    wait_for_route_invalidated_close_order: "Waiting For Route Close",
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

function formatAuthorityRole(value) {
  const labels = {
    generalist: "Generalist",
    momentum: "Momentum",
    inverse: "Inverse",
  };
  const normalized = String(value || "").toLowerCase();
  return labels[normalized] || formatLabel(value || "Generalist");
}

function renderPresetAuthority(authority) {
  if (!els.authority) return;
  if (!authority) {
    const armed = els.presetAuthorityMode?.value === PRESET_AUTHORITY_MODE_V6;
    els.authority.textContent = armed ? "v6 armed" : "Off";
    els.authority.dataset.tooltip = armed
      ? "v6 authority is selected locally. Start Edgewalker to arm the saved Lead preset bundle."
      : "Preset authority is disabled.";
    return;
  }

  const action = authority.authority_action || "PENDING";
  const selectedRole = authority.selected_role || "generalist";
  const rawRole = authority.raw_role || selectedRole;
  const confidence = authority.router_confidence || "--";
  if (action === "ROUTE") {
    els.authority.textContent = `v6 ${formatAuthorityRole(selectedRole)}`;
  } else if (action === "BLOCKED_REVIEW") {
    els.authority.textContent = "v6 blocked";
  } else if (action === "ADVISORY_ONLY") {
    els.authority.textContent = "v6 advisory";
  } else if (action === "GENERALIST_DEFAULT") {
    els.authority.textContent = "Generalist";
  } else if (action === "PENDING") {
    els.authority.textContent = "v6 pending";
  } else {
    els.authority.textContent = formatLabel(action);
  }

  const reason = authority.authority_reason || "No authority reason reported yet.";
  els.authority.dataset.tooltip = `${formatLabel(action)}. Raw: ${formatAuthorityRole(
    rawRole,
  )}. Selected: ${formatAuthorityRole(selectedRole)}. Confidence: ${confidence}. ${reason}`;
}

function renderRunState(data, waitingForOpen) {
  if (!els.edgeRunState) {
    return;
  }
  const status = data?.edgewalker_status;
  let label = "Stopped";
  let tooltip = "The repeating Edgewalker loop is stopped.";
  let tone = "is-neutral";

  if (state.busy) {
    label = "Checking";
    tooltip = "Edgewalker is running a status check or command.";
    tone = "data-warn";
  } else if (state.running) {
    if (status?.position_symbol) {
      label = "Position Open";
      tooltip = "Edgewalker is online and managing an open position.";
      tone = "data-live";
    } else if (waitingForOpen) {
      label = "Armed";
      tooltip = "Edgewalker is armed and waiting for the regular market open.";
      tone = "data-warn";
    } else if (status?.market_open === false) {
      label = "Market Closed";
      tooltip = "Edgewalker is online, but Alpaca reports the market is closed.";
      tone = "data-warn";
    } else {
      label = "Waiting";
      tooltip = "Edgewalker is online and waiting for a specialist lane to qualify.";
      tone = "data-live";
    }
  }

  els.edgeRunState.classList.remove("data-live", "data-warn", "data-danger", "is-neutral");
  els.edgeRunState.textContent = label;
  els.edgeRunState.dataset.tooltip = tooltip;
  els.edgeRunState.classList.add(tone);
}

function compactReasonDetails(value) {
  return String(value || "")
    .split(",")
    .map((item) => formatLabel(item.trim()))
    .filter(Boolean)
    .join(", ");
}

function decisionReason(status) {
  if (!status) {
    return {
      label: "Awaiting Status",
      tooltip: "Edgewalker has not received a strategy status yet.",
    };
  }
  if (status.position_symbol) {
    return {
      label: "Managing Risk",
      tooltip: "An open position exists, so Edgewalker is managing exits and risk.",
    };
  }
  if (status.market_open === false) {
    return {
      label: "Market Closed",
      tooltip: "Alpaca reports that the regular market is closed.",
    };
  }
  const momentumReason =
    status.v9_momentum_context?.activation_reason ||
    status.v9_momentum_context?.invalidation_reason;
  if (momentumReason) {
    return {
      label: "Gate Closed",
      tooltip: `Detailed gate context: ${compactReasonDetails(momentumReason)}.`,
    };
  }
  if (status.entry_signal === true) {
    return {
      label: "Signal Approved",
      tooltip: "The active specialist reported an entry signal.",
    };
  }
  if (status.action_taken === "no_entry_signal") {
    return {
      label: "Gates Closed",
      tooltip: "No active specialist entry gate qualified on the latest check.",
    };
  }
  if (!status.routed_symbol || status.routed_symbol === "NONE") {
    return {
      label: "No Route",
      tooltip: "No specialist route is currently allowed to place an entry.",
    };
  }
  return {
    label: formatLabel(status.action_taken || "Waiting"),
    tooltip: "Reason follows the latest strategy action.",
  };
}

function setTone(element, value) {
  if (!element) {
    return;
  }
  element.classList.remove("is-positive", "is-negative", "is-neutral");
  const parsed = numberOrNull(value);
  if (parsed === null || parsed === 0) {
    element.classList.add("is-neutral");
  } else {
    element.classList.add(parsed > 0 ? "is-positive" : "is-negative");
  }
}

function renderDecision(status, performance, presetAuthority = null) {
  if (!status) {
    els.regime.textContent = "Waiting";
    els.activeBot.textContent = "Waiting";
    els.routedSymbol.textContent = "None";
    els.action.textContent = "Waiting";
    if (els.actionReason) {
      els.actionReason.textContent = "Awaiting Status";
      els.actionReason.dataset.tooltip = "Edgewalker has not received a strategy status yet.";
    }
    renderPresetAuthority(presetAuthority);
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
  if (els.actionReason) {
    const reason = decisionReason(status);
    els.actionReason.textContent = reason.label;
    els.actionReason.dataset.tooltip = reason.tooltip;
  }
  renderPresetAuthority(status.preset_authority || presetAuthority);
  els.portfolio.textContent = formatMoney(status.portfolio_value);
  els.buyingPower.textContent = formatMoney(status.buying_power);
  els.sourcePrice.textContent = formatPrice(status.source_price);
  if (els.inversePrice) {
    els.inversePrice.textContent = formatPrice(
      status.inverse_price || status.symbol_prices?.SOXS,
    );
  }
  if (els.gap) {
    els.gap.textContent = formatPercent(status.gap_percent);
  }

  const dayPl = strategyDayPl(status, performance);
  const dayPlText = `${formatMoney(dayPl.value)} ${formatPercent(dayPl.percent)}`;
  els.dayPl.textContent = dayPl.value === null ? "--" : dayPlText;
  els.dayPl.dataset.tooltip =
    "Strategy/session P/L from realized trades plus open-position P/L. External deposits and withdrawals are not counted.";
  setTone(els.dayPl, dayPl.value);

  if (status.position_symbol && status.position_qty) {
    const qty = formatPositionQty(status.position_qty) || status.position_qty;
    if (els.position) {
      els.position.textContent = `${status.position_symbol} ${qty}`;
    }
  } else if (els.position) {
    els.position.textContent = "Flat";
  }

  const positionPlText = `${formatMoney(status.position_unrealized_pl)} ${formatPercent(
    status.position_unrealized_pl_percent,
    { fraction: true },
  )}`;
  els.positionPl.textContent =
    status.position_unrealized_pl === null ? "--" : positionPlText;
  setTone(els.positionPl, status.position_unrealized_pl);

  const projectedExitPl = projectedTrailPl(status);
  const riskLabel = projectedExitPl !== null ? "Trail P/L" : "Max loss";
  if (els.maxLossLabel) {
    els.maxLossLabel.textContent = riskLabel;
    els.maxLossLabel.dataset.tooltip =
      projectedExitPl !== null
        ? "Approximate P/L if the current bot-managed trailing exit price fills as shown. Market orders can slip through that trigger."
        : "Approximate worst-case P/L if the current bot-managed exit price fills as shown. Market orders can slip through that trigger.";
  }
  els.maxLoss.textContent =
    projectedExitPl === null ? "--" : formatMoney(projectedExitPl);
  if (projectedExitPl === null) {
    setTone(els.maxLoss, null);
  } else if (projectedExitPl >= 0) {
    els.maxLoss.classList.remove("is-negative", "is-neutral");
    els.maxLoss.classList.add("is-positive");
  } else {
    setTone(els.maxLoss, projectedExitPl);
  }

  els.entryPrice.textContent = status.position_avg_entry_price
    ? formatPrice(status.position_avg_entry_price)
    : "--";
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

function formatPositionLifecycleState(value) {
  const labels = {
    OPENING: "Opening",
    OPEN: "Open",
    CLOSING: "Closing",
    CLOSED: "Closed",
  };
  return labels[value] || formatLabel(value || "Closed");
}

function formatOrderQty(value) {
  return formatQty(value) || value || "--";
}

function formatOrderDetail(event) {
  if (event.error) {
    return event.error;
  }
  const reason = event.reason
    ? formatLabel(event.reason)
    : formatLabel(event.status || "Lifecycle");
  const lifecycle = event.position_lifecycle_state
    ? `${formatPositionLifecycleState(event.position_lifecycle_state)} · `
    : "";
  const fillQty = event.fill_delta_qty || event.filled_qty;
  if (fillQty) {
    const qty = formatOrderQty(fillQty);
    const price = event.filled_avg_price
      ? ` @ ${formatPrice(event.filled_avg_price)}`
      : "";
    return `${lifecycle}${qty}${price} · ${reason}`;
  }
  const status = event.status ? formatLabel(event.status) : "Submitted";
  return `${lifecycle}${status} · ${reason}`;
}

function renderOrderEvent(event) {
  const side = event.side ? event.side.toUpperCase() : "--";
  const symbol = event.symbol || "--";
  const eventLabel = formatOrderEventType(event.event_type);
  const time = formatTime(event.created_at, "--");
  const owner = event.bot
    ? formatLabel(event.bot)
    : formatLabel(event.status || "Broker Event");
  const detail = formatOrderDetail(event);
  return `
    <div class="order-row">
      <div>
        <strong>${escapeHtml(eventLabel)}</strong>
        <span>${escapeHtml(symbol)} ${escapeHtml(side)} · ${escapeHtml(time)}</span>
      </div>
      <div>
        <strong>${escapeHtml(owner)}</strong>
        <span>${escapeHtml(detail)}</span>
      </div>
    </div>
  `;
}

function renderPendingOrder(order) {
  const side = order.side ? order.side.toUpperCase() : "--";
  const symbol = order.symbol || "--";
  const lifecycle = formatPositionLifecycleState(order.position_lifecycle_state);
  const time = formatTime(order.updated_at || order.submitted_at, "--");
  const owner = order.bot ? formatLabel(order.bot) : "Pending Order";
  const filled = order.filled_qty ? `filled ${formatOrderQty(order.filled_qty)}` : "";
  const status = order.status ? formatLabel(order.status) : "Submitted";
  const reason = order.reason ? ` · ${formatLabel(order.reason)}` : "";
  const detail = [status, filled].filter(Boolean).join(" · ");
  return `
    <div class="order-row">
      <div>
        <strong>${escapeHtml(lifecycle)}</strong>
        <span>${escapeHtml(symbol)} ${escapeHtml(side)} · ${escapeHtml(time)}</span>
      </div>
      <div>
        <strong>${escapeHtml(owner)}</strong>
        <span>${escapeHtml(detail + reason)}</span>
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
  const lifecycle = formatPositionLifecycleState(
    orderState?.position_lifecycle_state,
  );

  if (pending.length > 0) {
    els.orderSummary.textContent = `${lifecycle} · ${pending.length} pending`;
    els.orderSummary.classList.remove("is-positive", "is-negative", "is-neutral");
    els.orderSummary.classList.add("data-warn");
  } else if (latestFill) {
    els.orderSummary.textContent = `${lifecycle} · Last fill ${formatOrderQty(
      latestFill.fill_delta_qty || latestFill.filled_qty,
    )}`;
    els.orderSummary.classList.remove("data-warn");
    els.orderSummary.classList.add("is-neutral");
  } else {
    els.orderSummary.textContent = lifecycle;
    els.orderSummary.classList.remove("data-warn");
    els.orderSummary.classList.add("is-neutral");
  }

  const rows = [
    ...pending.map(renderPendingOrder),
    ...events.map(renderOrderEvent),
  ];
  els.orderEvents.innerHTML = rows.length
    ? rows.join("")
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
  if (lower.includes("[adaptive]")) {
    if (lower.includes("posture=conservative")) {
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
    lower.includes("route invalidated") ||
    lower.includes("route_invalidated") ||
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
  const wasRunning = state.running;
  state.running = Boolean(data.running);
  state.activeEnvironment = data.active_environment || state.activeEnvironment;
  state.liveTradingArmed = Boolean(data.live_trading_armed);
  state.liveCredentialsReady = Boolean(data.live_credentials_ready);
  const latestBuyingPower = buyingPowerFromData(data);
  if (latestBuyingPower !== null) {
    state.latestBuyingPower = latestBuyingPower;
  }
  const latestAccountValue = accountValueFromData(data);
  if (latestAccountValue !== null) {
    state.latestAccountValue = latestAccountValue;
  }
  hydrateForm(data);
  if (!state.running && !state.busy) {
    syncPresetAuthorityBaseConfig();
  }
  syncResearchStartingAccount();

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
  renderRunState(data, waitingForOpen);
  els.toggle.textContent = state.running ? "Turn Off" : "Turn On";
  els.toggle.dataset.tooltip = state.running
    ? "Stop the repeating bot loop after the current cycle."
    : "Start the repeating bot loop. If the market is closed, it will arm itself for the next open.";
  els.toggle.classList.toggle("is-stop", state.running);
  els.runOnce.disabled = state.running || state.busy;
  els.toggle.disabled = state.busy;
  const settingsLocked = state.running || state.busy;
  lockedStrategyInputs.forEach((input) => {
    input.disabled = true;
    input.closest(".switch")?.classList.add("is-disabled");
    input.closest(".field")?.classList.add("is-disabled");
  });
  sizingControlInputs.forEach((input) => {
    input.disabled = settingsLocked;
    input.closest(".switch")?.classList.toggle("is-disabled", settingsLocked);
    input.closest(".field")?.classList.toggle("is-disabled", settingsLocked);
  });
  if (els.runBacktest) {
    els.runBacktest.disabled = state.running || state.busy || state.researchBusy;
  }
  syncResearchPresetButtons();
  if (els.adaptiveShadowLabel) {
    els.adaptiveShadowLabel.dataset.tooltip = settingsLocked
      ? "Stop Edgewalker before changing Adaptive shadow telemetry."
      : "When enabled, Adaptive logs the posture it would select while manual directional modes remain in control.";
  }
  syncSizingControls();

  const isDryRun = state.running ? Boolean(data.dry_run) : state.dryRun;
  renderMode(
    isDryRun,
    state.activeEnvironment,
    state.liveTradingArmed,
    state.liveCredentialsReady,
  );
  renderDataHealth(data.edgewalker_status || data.market_data_status);
  renderBrokerState(data.broker_state);
  renderPriorCloseStatus(data.edgewalker_status);
  renderPerformance(data.performance);
  renderOrderState(data.order_state);
  els.lastRun.textContent = formatTime(data.last_run_at, "Never");
  els.nextRun.textContent = formatNextCheck(data);
  els.error.textContent = data.last_error || "";
  renderDecision(
    data.edgewalker_status,
    data.performance,
    data.edgewalker_status?.preset_authority || data.preset_authority,
  );
  renderPositionSizeSummary(data.edgewalker_status);
  renderLog(data);
  handleRuntimeSounds(data, wasRunning);
}

async function refresh() {
  try {
    const data = await request("/api/status");
    render(data);
  } catch (error) {
    els.error.textContent = error.message;
  }
}

function startRefreshLoop() {
  const run = async () => {
    await refresh();
    window.setTimeout(run, REFRESH_INTERVAL_MS);
  };
  run();
}

async function postAction(path) {
  state.busy = true;
  els.toggle.disabled = true;
  els.runOnce.disabled = true;
  try {
    const shouldPlayStartCueAfterRender =
      path === "/api/start" && !state.running && !state.audioHydrated;
    const data = await request(path, {
      method: "POST",
      body: JSON.stringify(payloadFromForm()),
    });
    render(data);
    if (shouldPlayStartCueAfterRender && data.running) {
      playSound("botStarted");
    }
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
  if (state.tooltipsSetup) {
    return;
  }
  state.tooltipsSetup = true;
  document.addEventListener("mouseover", (event) => {
    const target = event.target.closest?.("[data-tooltip]");
    if (target) {
      showTooltip(target);
    }
  });
  document.addEventListener("mouseout", (event) => {
    const target = event.target.closest?.("[data-tooltip]");
    if (target && !target.contains(event.relatedTarget)) {
      hideTooltip();
    }
  });
  document.addEventListener("focusin", (event) => {
    const target = event.target.closest?.("[data-tooltip]");
    if (target) {
      showTooltip(target);
    }
  });
  document.addEventListener("focusout", (event) => {
    const target = event.target.closest?.("[data-tooltip]");
    if (target) {
      hideTooltip();
    }
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

if (els.runBacktest) {
  els.runBacktest.addEventListener("click", runBacktest);
}

if (els.runResearchCompare) {
  els.runResearchCompare.addEventListener("click", runResearchComparison);
}

if (els.runShadowRouter) {
  els.runShadowRouter.addEventListener("click", runShadowRouterReplay);
}

if (els.saveResearchPreset) {
  els.saveResearchPreset.addEventListener("click", saveResearchPreset);
}

if (els.loadResearchPreset) {
  els.loadResearchPreset.addEventListener("click", loadResearchPreset);
}

if (els.deleteResearchPreset) {
  els.deleteResearchPreset.addEventListener("click", deleteResearchPreset);
}

if (els.researchPresetLibrary) {
  els.researchPresetLibrary.addEventListener("change", syncResearchPresetButtons);
}

if (els.researchComparePresets) {
  els.researchComparePresets.addEventListener("change", syncResearchPresetButtons);
}

if (els.selectAllResearchComparePresets) {
  els.selectAllResearchComparePresets.addEventListener(
    "click",
    selectAllResearchComparePresets,
  );
}
if (els.seedChopResearchPresets) {
  els.seedChopResearchPresets.addEventListener("click", seedChopResearchPresets);
}
if (els.seedMomentumResearchPresets) {
  els.seedMomentumResearchPresets.addEventListener(
    "click",
    seedMomentumResearchPresets,
  );
}
if (els.seedCombinedResearchPresets) {
  els.seedCombinedResearchPresets.addEventListener(
    "click",
    seedCombinedResearchPresets,
  );
}

if (els.applyGoLiveRouter) {
  els.applyGoLiveRouter.addEventListener("click", applyGoLiveRouterFirewall);
}

if (els.backtestStartingAccount) {
  els.backtestStartingAccount.addEventListener("input", () => {
    els.backtestStartingAccount.dataset.autoValue = "false";
  });
}

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

if (els.customAllocation) {
  els.customAllocation.addEventListener("input", syncSizingControls);
}

if (els.notional) {
  els.notional.addEventListener("input", () => {
    if (!els.positionSizing || els.positionSizing.value === "FIXED") {
      state.fixedNotionalValue = els.notional.value;
    }
  });
}

if (els.dryRun) {
  els.dryRun.addEventListener("change", () => {
    state.dryRun = els.dryRun.checked;
    renderMode(
      state.dryRun,
      state.activeEnvironment,
      state.liveTradingArmed,
      state.liveCredentialsReady,
    );
  });
}

if (els.researchMode) {
  els.researchMode.addEventListener("change", () => {
    persistResearchModeToggle();
  });
}

if (els.themeToggle) {
  els.themeToggle.addEventListener("change", toggleTheme);
}

setupTheme();
setupAudioscapePreference();
setupSettingsMenu();
setupUiSounds();
setupSettingsModal();
setupOperatorSpreadsheetModal();
setupNotificationsModal();
setupOperatorGuide();
setupCollapsibleSections();
setupActivityLog();
setupTooltips();
setupPresetAuthorityMode();
setupActiveStrategyConfig();
ensureBacktestDefaults();
renderResearchPresetLibrary();
syncPresetAuthorityBaseConfig();
renderResearchMode();
loadSettings().catch((error) => {
  if (els.error) {
    els.error.textContent = error.message;
  }
});
startRefreshLoop();
