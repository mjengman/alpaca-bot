#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import copy
import io
import json
import mimetypes
import os
import re
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from bot import (
    AlpacaClient,
    BotConfig,
    BotError,
    BotStateStore,
    CHOP_BOT,
    CHOP_PERMISSION_MODES,
    DATA_BASE_URL_DEFAULT,
    EDGEWALKER_BOTS,
    EdgeWalkerBot,
    INVERSE_BOT,
    INVERSE_CASCADE_MODE_SUSTAINED,
    INVERSE_CASCADE_MODES,
    LIFECYCLE_FULL_FILL,
    LIFECYCLE_ORDER_ACCEPTED,
    LIFECYCLE_ORDER_REJECTED,
    LIFECYCLE_ORDER_SUBMITTED,
    LIFECYCLE_PARTIAL_FILL,
    LifecycleLedger,
    LIVE_TRADING_BASE_URL_DEFAULT,
    MOMENTUM_BOT,
    DIRECTIONAL_MODES,
    POSITION_SIZING_MODES,
    POSITION_LIFECYCLE_CLOSED,
    POSITION_LIFECYCLE_CLOSING,
    POSITION_LIFECYCLE_OPEN,
    POSITION_LIFECYCLE_OPENING,
    REGIME_STRENGTHS,
    SOXL,
    SOXS,
    TRADING_BASE_URL_DEFAULT,
    broker_constraint_ok,
    broker_constraint_payload,
    classify_broker_error,
    format_decimal,
    load_dotenv,
    normalize_alpaca_base_url,
    normalize_enabled_bots,
    parse_clock_time,
)
from market_data import StreamingMarketDataService
from research import (
    RESEARCH_FILL_MODEL_NEXT_BAR_OPEN,
    ResearchRunRequest,
    build_roster_dress_rehearsal_scoreboard,
    run_research_backtest,
)
from trade_metrics import (
    analyze_lifecycle_trades,
    bot_archaeology_report,
    trade_quality_averages,
)


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_ROOT = PROJECT_ROOT / "web"
ASSETS_ROOT = PROJECT_ROOT / "assets"
HOST = "127.0.0.1"
PORT = 8765
ACTIVITY_PATH = PROJECT_ROOT / ".bot_activity.json"
OPERATOR_SPREADSHEET_POST_STATE_PATH = PROJECT_ROOT / ".operator_spreadsheet_posts.json"
NOTIFICATION_STATE_PATH = PROJECT_ROOT / ".notification_events.json"
NARRATIVE_CACHE_PATH = PROJECT_ROOT / ".narrative_cache.json"
ENV_PATH = PROJECT_ROOT / ".env"
LOGS_ROOT = PROJECT_ROOT / "logs"
NY_TZ = ZoneInfo("America/New_York")
BOT_PERFORMANCE_ORDER = (MOMENTUM_BOT, CHOP_BOT, INVERSE_BOT)
SPECIALIST_DISPLAY_NAMES = {
    MOMENTUM_BOT: "Momentum Surge",
    CHOP_BOT: "Chop Firewall",
    INVERSE_BOT: "Inverse Cascade",
}
LOCKED_FULL_ROSTER_PROFILE = "FULL_ROSTER_LOCKED"
UNKNOWN_MARKET_ENVIRONMENT = ""
NOTIFICATION_PROVIDER_APPS_SCRIPT = "apps_script"
NOTIFICATION_DEFAULT_ERROR_COOLDOWN_MINUTES = 30
NOTIFICATION_SENT_EVENT_LIMIT = 500
NARRATIVE_GROUNDING_VERSION = "ledger-grounded-v2"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
VALID_TIMEFRAMES = {"1D", "1W", "1M", "3M", "YTD", "MAX", "CUSTOM"}
PRESET_AUTHORITY_MODE_V6 = "V6_0945"
PRESET_AUTHORITY_MODEL_V6 = "v6_0945_high_confidence_with_rebound_block"
OPERATOR_SPREADSHEET_COLUMNS = [
    "date",
    "mode",
    "build_profile",
    "enabled_specialists",
    "starting_account_value",
    "ending_account_value",
    "realized_pl_dollars",
    "account_change_percent",
    "account_result_status",
    "closed_trades",
    "wins",
    "losses",
    "win_rate",
    "momentum_pl",
    "chop_pl",
    "inverse_pl",
    "momentum_trades",
    "chop_trades",
    "inverse_trades",
    "top_pl_bot",
    "bottom_pl_bot",
    "regime_transitions",
    "cycles",
    "stale_cycles",
    "stream_error_cycles",
    "session_trend_trust_avg",
    "route_invalidation_exits",
    "route_invalidation_pl",
    "trailing_stop_exits",
    "trailing_stop_pl",
    "market_close_exits",
    "market_close_pl",
    "session_avg_mfe_percent",
    "session_avg_mae_percent",
    "session_avg_capture_ratio_percent",
    "session_avg_hold_seconds",
    "momentum_avg_mfe_percent",
    "momentum_avg_mae_percent",
    "momentum_avg_capture_ratio_percent",
    "momentum_avg_hold_seconds",
    "chop_avg_mfe_percent",
    "chop_avg_mae_percent",
    "chop_avg_capture_ratio_percent",
    "chop_avg_hold_seconds",
    "inverse_avg_mfe_percent",
    "inverse_avg_mae_percent",
    "inverse_avg_capture_ratio_percent",
    "inverse_avg_hold_seconds",
    "inverse_near_zero_mfe_count",
    "inverse_meaningful_mfe_low_capture_count",
    "inverse_adverse_gt_favorable_count",
    "mfe_mae_source",
    "reconciliation_confidence",
    "config_version",
    "strategy_version",
    "symbol_primary",
    "symbol_inverse",
    "position_sizing_mode",
    "position_notional",
    "position_allocation_percent",
    "effective_position_notional",
    "poll_seconds",
    "trail_percent",
    "fast_sma_minutes",
    "slow_sma_minutes",
    "regime_gap_percent",
    "regime_exit_gap_percent",
    "chop_discount_percent",
    "close_liquidate_minutes",
    "directional_max_extension_percent",
    "directional_strong_chase_max_extension_percent",
    "directional_min_strength",
    "directional_cooldown_minutes",
    "chop_permission_mode",
    "chop_permission_max_abs_source_percent",
    "adaptive_shadow_enabled",
    "enabled_bots",
    "momentum_authority_required",
    "momentum_authority_revoke_exits",
    "momentum_authority_latch_once_active",
    "momentum_authority_min_trust_score",
    "momentum_authority_min_source_percent",
    "momentum_authority_max_transitions_per_hour",
    "momentum_authority_reclaim_enabled",
    "momentum_authority_reclaim_min_trust_score",
    "momentum_authority_reclaim_min_source_percent",
    "momentum_authority_reclaim_max_raw_transition_count",
    "momentum_authority_reclaim_max_non_warmup_transition_count",
    "momentum_authority_reclaim_start_minutes",
    "momentum_authority_reclaim_end_minutes",
    "v10_force_no_authority",
    "dry_run",
    "order_mode",
    "active_environment",
    "market_environment",
    "primary_no_trade_reason",
    "route_reason_summary",
    "prior_close_status",
    "data_feed",
    "operator_notes",
    "daily_narrative",
]
RESEARCH_SPREADSHEET_COLUMNS = [
    "is_backtest",
    "run_id",
    "run_timestamp",
    "backtest_date",
    "fill_model",
    "slippage_bps",
    "preset_name",
    "preset_version",
    "entry_regime_age_median",
    "early_entry_count",
    "momentum_early_entry_count",
    "chop_early_entry_count",
    "inverse_early_entry_count",
    "v8_young_regime_blocks",
    "v8_low_trust_blocks",
    "v8_noisy_water_blocks",
    "v9_momentum_context_activations",
    "v9_inverse_suppression_blocks",
    "v9_momentum_context_invalidations",
    "v10_no_authority_directional_suppression_blocks",
    "v10_no_authority_momentum_suppression_blocks",
    "v10_no_authority_inverse_suppression_blocks",
    "v10_suppressed_directional_shadow_pl",
    "v10_suppressed_directional_shadow_status",
    "v10_no_authority_context_activation_reason",
    "v10_no_authority_context_observer_preset",
    "v10_no_authority_context_authority_gate",
    "v10_no_authority_context_trust_score",
    "v10_no_authority_context_soxl_percent",
    "v10_no_authority_context_soxl_runup_percent",
    "v10_no_authority_context_soxl_drawdown_percent",
    "v10_no_authority_context_early_transition_count",
    "v10_no_authority_context_early_transitions_per_hour",
    "v10_no_authority_context_early_non_warmup_transition_count",
    "v10_no_authority_context_early_non_warmup_transitions_per_hour",
    "v10_no_authority_context_early_window_minutes",
    "v9_momentum_context_activation_reason",
    "v9_momentum_context_observer_preset",
    "v9_momentum_context_trust_score",
    "v9_momentum_context_soxl_percent",
    "v9_momentum_context_early_transition_count",
    "v9_momentum_context_early_transitions_per_hour",
    "v9_momentum_context_early_non_warmup_transition_count",
    "v9_momentum_context_early_non_warmup_transitions_per_hour",
    "v9_momentum_context_early_window_minutes",
    "v9_momentum_context_invalidation_reason",
    *OPERATOR_SPREADSHEET_COLUMNS,
]
ALLOWED_UI_ORIGINS = {
    f"http://{HOST}:{PORT}",
    f"http://localhost:{PORT}",
}
MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
NARRATIVE_BOTS = (MOMENTUM_BOT, CHOP_BOT, INVERSE_BOT)
ENV_KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
SECRET_PLACEHOLDER = "__EDGEWALKER_KEEP_SECRET__"


@dataclass
class RunnerSnapshot:
    running: bool
    symbol: str
    dry_run: bool
    active_environment: str
    live_trading_armed: bool
    live_credentials_ready: bool
    poll_seconds: int
    close_liquidate_minutes: int
    regime_gap_threshold: str
    regime_exit_gap_threshold: str
    chop_entry_discount_percent: str
    directional_mode: str
    directional_max_extension_percent: str
    directional_strong_chase_max_extension_percent: str
    directional_min_strength: str
    directional_cooldown_minutes: int
    chop_permission_mode: str
    chop_permission_max_abs_source_percent: str
    adaptive_shadow_enabled: bool
    enabled_bots: list[str]
    momentum_authority_required: bool
    momentum_authority_revoke_exits: bool
    momentum_authority_latch_once_active: bool
    momentum_authority_min_trust_score: int
    momentum_authority_min_source_percent: str
    momentum_authority_max_transitions_per_hour: str
    momentum_authority_reclaim_enabled: bool
    momentum_authority_reclaim_min_trust_score: int
    momentum_authority_reclaim_min_source_percent: str
    momentum_authority_reclaim_max_raw_transition_count: int
    momentum_authority_reclaim_max_non_warmup_transition_count: int
    momentum_authority_reclaim_start_minutes: int
    momentum_authority_reclaim_end_minutes: int
    position_notional: str
    position_sizing_mode: str
    position_allocation_percent: str
    trail_percent: str
    fast_sma_minutes: int
    slow_sma_minutes: int
    cycle_count: int
    last_started_at: str | None
    last_stopped_at: str | None
    last_run_at: str | None
    next_run_at: str | None
    next_run_reason: str | None
    last_output: list[str]
    activity_log: list[str]
    edgewalker_status: dict[str, Any] | None
    market_data_status: dict[str, Any] | None
    broker_state: dict[str, Any]
    performance: dict[str, Any]
    order_state: dict[str, Any]
    preset_authority: dict[str, Any] | None
    last_error: str | None


class BotRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        LOGS_ROOT.mkdir(parents=True, exist_ok=True)
        self._config, startup_error = self._initial_config()
        self._market_data = StreamingMarketDataService(self._config, symbols=(SOXL, SOXS))
        self._market_data.ensure_running(self._config)
        self._running = False
        self._cycle_count = 0
        self._last_started_at: str | None = None
        self._last_stopped_at: str | None = None
        self._last_run_at: str | None = None
        self._next_run_at: str | None = None
        self._next_run_reason: str | None = None
        self._last_output: list[str] = []
        self._activity_log: list[tuple[datetime, str]] = self._load_activity_log()
        self._edgewalker_status: dict[str, Any] | None = None
        self._broker_state: dict[str, Any] = broker_constraint_payload(
            broker_constraint_ok()
        )
        self._last_error: str | None = startup_error
        self._market_idle_logged_for: str | None = None
        self._last_regime: str | None = None
        self._spreadsheet_auto_posted_dates = self._load_spreadsheet_posted_dates()
        self._spreadsheet_auto_post_attempted_dates: set[str] = set()
        self._notification_state = _load_notification_state()
        self._preset_authority_plan: dict[str, Any] | None = None
        self._preset_authority_state: dict[str, Any] = {}

    def _initial_config(self) -> tuple[BotConfig, str | None]:
        try:
            return BotConfig.from_env(), None
        except BotError as exc:
            if current_alpaca_environment() != "live":
                raise
            try:
                fallback = BotConfig.from_env(environment_override="paper")
            except BotError:
                raise exc
            return fallback, f"Live environment incomplete: {exc}"

    def snapshot(self) -> RunnerSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def start(
        self,
        config: BotConfig,
        preset_authority_plan: dict[str, Any] | None = None,
    ) -> RunnerSnapshot:
        with self._lock:
            if self._running:
                return self._snapshot_locked()

            launch_config = self._preset_authority_launch_config(
                config,
                preset_authority_plan,
            )
            self._config = launch_config
            self._preset_authority_plan = preset_authority_plan
            self._preset_authority_state = {}
            self._market_data.ensure_running(launch_config)
            self._running = True
            self._last_started_at = now_iso()
            self._last_stopped_at = None
            self._last_error = None
            self._broker_state = broker_constraint_payload(broker_constraint_ok())
            self._next_run_at = None
            self._next_run_reason = None
            self._market_idle_logged_for = None
            self._last_output = ["Bot started."]
            self._append_activity_locked(self._last_output)
            stop_event = threading.Event()
            self._stop_event = stop_event
            self._thread = threading.Thread(
                target=self._loop,
                args=(launch_config, stop_event),
                name="alpaca-bot-runner",
                daemon=True,
            )
            self._thread.start()
            return self._snapshot_locked()

    def stop(self) -> RunnerSnapshot:
        with self._lock:
            if self._stop_event:
                self._stop_event.set()
            self._running = False
            self._next_run_at = None
            self._next_run_reason = None
            self._market_idle_logged_for = None
            self._last_stopped_at = now_iso()
            self._last_output = ["Bot stopped.", *self._last_output[:39]]
            self._append_activity_locked(["Bot stopped."])
            return self._snapshot_locked()

    def shutdown(self) -> None:
        self.stop()
        self._market_data.stop()

    def run_once(
        self,
        config: BotConfig,
        preset_authority_plan: dict[str, Any] | None = None,
    ) -> RunnerSnapshot:
        launch_config = self._preset_authority_launch_config(
            config,
            preset_authority_plan,
        )
        with self._lock:
            self._config = launch_config
            self._preset_authority_plan = preset_authority_plan
            self._preset_authority_state = {}
            self._market_data.ensure_running(launch_config)
        self._run_cycle(launch_config)
        return self.snapshot()

    def _preset_authority_launch_config(
        self,
        config: BotConfig,
        preset_authority_plan: dict[str, Any] | None,
    ) -> BotConfig:
        if (
            preset_authority_plan
            and preset_authority_plan.get("mode") == PRESET_AUTHORITY_MODE_V6
        ):
            role_configs = preset_authority_plan.get("role_configs")
            if isinstance(role_configs, dict):
                generalist_config = role_configs.get("generalist")
                if isinstance(generalist_config, BotConfig):
                    return generalist_config
        return config

    def _loop(self, config: BotConfig, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            if self._idle_if_market_closed(config, stop_event):
                continue

            self._run_cycle(config)
            next_run = datetime.now() + timedelta(seconds=config.poll_seconds)
            with self._lock:
                if self._stop_event is stop_event and self._running:
                    self._next_run_at = next_run.isoformat(timespec="seconds")
                    self._next_run_reason = "poll"
            stop_event.wait(config.poll_seconds)

        with self._lock:
            if self._stop_event is stop_event:
                self._running = False
                self._next_run_at = None
                self._next_run_reason = None
                self._last_stopped_at = self._last_stopped_at or now_iso()

    def _idle_if_market_closed(
        self,
        config: BotConfig,
        stop_event: threading.Event,
    ) -> bool:
        try:
            clock = AlpacaClient(config).get_clock()
            market_open = bool(clock.get("is_open"))
            next_open = parse_clock_time(clock.get("next_open"), "next_open")
        except BotError as exc:
            self._record_scheduler_error(config, exc)
            stop_event.wait(config.poll_seconds)
            return True

        if market_open:
            with self._lock:
                self._market_idle_logged_for = None
            return False

        self._arm_until_market_open(config, stop_event, next_open)
        return True

    def _arm_until_market_open(
        self,
        config: BotConfig,
        stop_event: threading.Event,
        next_open: datetime | None,
    ) -> None:
        next_open_text = (
            next_open.isoformat(timespec="seconds") if next_open else None
        )
        if next_open_text:
            line = (
                "Market closed. EdgeWalker armed; "
                f"next market open at {next_open_text}."
            )
        else:
            line = "Market closed. EdgeWalker armed for the next regular open."
        idle_key = next_open_text or "unknown"

        with self._lock:
            if self._stop_event is not stop_event or not self._running:
                return

            self._next_run_at = next_open_text
            self._next_run_reason = "market_open"
            if self._market_idle_logged_for != idle_key:
                self._last_output = [line, *self._last_output[:39]]
                self._append_activity_locked([line])
                self._market_idle_logged_for = idle_key

        self._maybe_auto_post_operator_spreadsheet(next_open)
        self._maybe_send_daily_summary_notification(next_open)

        wait_seconds = config.poll_seconds
        if next_open is not None:
            seconds_to_open = max(
                (next_open - datetime.now(timezone.utc)).total_seconds(),
                1,
            )
            wait_seconds = min(config.poll_seconds, seconds_to_open)
        stop_event.wait(wait_seconds)

    def _record_scheduler_error(self, config: BotConfig, exc: BotError) -> None:
        next_run = datetime.now() + timedelta(seconds=config.poll_seconds)
        lines = [f"[error] Could not check market clock: {exc}"]
        with self._lock:
            self._last_error = str(exc)
            self._broker_state = broker_constraint_payload(
                classify_broker_error(str(exc))
            )
            self._last_output = lines
            self._next_run_at = next_run.isoformat(timespec="seconds")
            self._next_run_reason = "poll"
            self._append_activity_locked(lines)
        self._maybe_send_error_notification(
            category="market_clock",
            subject="Edgewalker market clock check failed",
            body=f"Edgewalker could not check the market clock:\n\n{exc}",
        )

    def _maybe_auto_post_operator_spreadsheet(
        self,
        next_open: datetime | None,
    ) -> None:
        target_date = self._operator_spreadsheet_auto_post_date(next_open)
        if not target_date:
            return

        with self._lock:
            if not hasattr(self, "_spreadsheet_auto_posted_dates"):
                self._spreadsheet_auto_posted_dates = set()
            if not hasattr(self, "_spreadsheet_auto_post_attempted_dates"):
                self._spreadsheet_auto_post_attempted_dates = set()
            if (
                target_date in self._spreadsheet_auto_posted_dates
                or target_date in self._spreadsheet_auto_post_attempted_dates
            ):
                return
            self._spreadsheet_auto_post_attempted_dates.add(target_date)

        try:
            result = post_operator_spreadsheet_daily_row({"date": target_date})
        except BotError as exc:
            self._record_operator_spreadsheet_auto_post(
                f"[SPREADSHEET] Auto-post failed for {target_date}: {exc}",
                error=str(exc),
            )
            return

        with self._lock:
            self._spreadsheet_auto_posted_dates.add(target_date)
            self._save_spreadsheet_posted_dates()

        narrative_note = (
            " Narrative skipped."
            if result.get("narrative_error")
            else ""
        )
        self._record_operator_spreadsheet_auto_post(
            f"[SPREADSHEET] Auto-posted daily row for {target_date}.{narrative_note}"
        )

    def _operator_spreadsheet_auto_post_date(
        self,
        next_open: datetime | None,
    ) -> str | None:
        settings = operator_spreadsheet_settings()
        if not settings.get("auto_post_enabled"):
            return None
        if not _optional_text(settings.get("post_endpoint_url")):
            return None

        now_ny = datetime.now(NY_TZ)
        today = now_ny.date().isoformat()
        if next_open is not None:
            next_open_day = next_open.astimezone(NY_TZ).date().isoformat()
            if next_open_day == today:
                return None
        elif now_ny.hour < 16:
            return None

        latest_log_date = _most_recent_log_date(market_open_only=True)
        if latest_log_date != today:
            return None
        return today

    def _record_operator_spreadsheet_auto_post(
        self,
        line: str,
        *,
        error: str | None = None,
    ) -> None:
        with self._lock:
            if error:
                self._last_error = error
            self._last_output = [line, *self._last_output[:39]]
            self._append_activity_locked([line])

    def _load_spreadsheet_posted_dates(self) -> set[str]:
        if not OPERATOR_SPREADSHEET_POST_STATE_PATH.exists():
            return set()
        try:
            payload = json.loads(
                OPERATOR_SPREADSHEET_POST_STATE_PATH.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            return set()
        if isinstance(payload, dict):
            posted_dates = payload.get("posted_dates")
            if isinstance(posted_dates, list):
                return {date for date in posted_dates if isinstance(date, str)}
        if isinstance(payload, list):
            return {date for date in payload if isinstance(date, str)}
        return set()

    def _save_spreadsheet_posted_dates(self) -> None:
        payload = {
            "posted_dates": sorted(self._spreadsheet_auto_posted_dates),
        }
        OPERATOR_SPREADSHEET_POST_STATE_PATH.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def _notification_state_locked(self) -> dict[str, Any]:
        if not hasattr(self, "_notification_state"):
            self._notification_state = _load_notification_state()
        return self._notification_state

    def _save_notification_state_locked(self) -> None:
        _save_notification_state(self._notification_state_locked())

    def _record_notification_activity(
        self,
        line: str,
        *,
        error: str | None = None,
    ) -> None:
        with self._lock:
            if error:
                self._last_error = error
            self._last_output = [line, *self._last_output[:39]]
            self._append_activity_locked([line])

    def send_test_notification(self) -> dict[str, Any]:
        try:
            result = send_test_notification_email()
        except BotError as exc:
            self._record_notification_activity(
                f"[NOTIFY] Test notification failed: {exc}",
                error=str(exc),
            )
            raise
        self._record_notification_activity("[NOTIFY] Sent test notification.")
        return result

    def _notification_cooldown_active_locked(
        self,
        category: str,
        now_utc: datetime,
    ) -> bool:
        cooldowns = self._notification_state_locked().setdefault("cooldowns", {})
        if not isinstance(cooldowns, dict):
            return False
        raw_until = cooldowns.get(category)
        if not isinstance(raw_until, str):
            return False
        try:
            until = datetime.fromisoformat(raw_until.replace("Z", "+00:00"))
        except ValueError:
            return False
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        return until > now_utc

    def _set_notification_cooldown_locked(
        self,
        category: str,
        now_utc: datetime,
        minutes: int,
    ) -> None:
        cooldowns = self._notification_state_locked().setdefault("cooldowns", {})
        if not isinstance(cooldowns, dict):
            cooldowns = {}
            self._notification_state_locked()["cooldowns"] = cooldowns
        cooldowns[category] = _utc_timestamp(now_utc + timedelta(minutes=minutes))

    def _deliver_notification_event(
        self,
        *,
        event_id: str,
        subject: str,
        body: str,
        html: str | None = None,
        cooldown_category: str | None = None,
        cooldown_minutes: int | None = None,
    ) -> dict[str, Any]:
        settings = notification_settings()
        if not settings.get("enabled"):
            return {"status": "disabled"}

        now_utc = datetime.now(timezone.utc)
        effective_cooldown_category = cooldown_category or f"delivery:{event_id}"
        effective_cooldown_minutes = cooldown_minutes or int(
            settings.get("error_cooldown_minutes") or 30
        )
        with self._lock:
            state = self._notification_state_locked()
            sent_ids = state.setdefault("sent_event_ids", [])
            if not isinstance(sent_ids, list):
                sent_ids = []
                state["sent_event_ids"] = sent_ids
            if event_id in sent_ids:
                return {"status": "duplicate"}
            if (
                effective_cooldown_category
                and effective_cooldown_minutes
                and self._notification_cooldown_active_locked(
                    effective_cooldown_category,
                    now_utc,
                )
            ):
                return {"status": "cooldown"}

        try:
            result = send_notification_email(subject=subject, text=body, html=html)
        except BotError as exc:
            with self._lock:
                if effective_cooldown_category and effective_cooldown_minutes:
                    self._set_notification_cooldown_locked(
                        effective_cooldown_category,
                        now_utc,
                        effective_cooldown_minutes,
                    )
                    self._save_notification_state_locked()
            self._record_notification_activity(
                f"[NOTIFY] Failed: {subject}: {exc}",
                error=str(exc),
            )
            return {"status": "failed", "error": str(exc)}

        with self._lock:
            state = self._notification_state_locked()
            sent_ids = state.setdefault("sent_event_ids", [])
            if not isinstance(sent_ids, list):
                sent_ids = []
                state["sent_event_ids"] = sent_ids
            if event_id not in sent_ids:
                sent_ids.append(event_id)
            if cooldown_category and cooldown_minutes:
                self._set_notification_cooldown_locked(
                    cooldown_category,
                    now_utc,
                    cooldown_minutes,
                )
            self._save_notification_state_locked()

        self._record_notification_activity(f"[NOTIFY] Sent: {subject}")
        return result

    def _maybe_send_error_notification(
        self,
        *,
        category: str,
        subject: str,
        body: str,
    ) -> None:
        settings = notification_settings()
        if not (
            settings.get("enabled")
            and settings.get("notify_data_errors")
        ):
            return
        now_utc = datetime.now(timezone.utc)
        event_id = f"error:{category}:{_utc_timestamp(now_utc)[:16]}"
        self._deliver_notification_event(
            event_id=event_id,
            subject=subject,
            body=body,
            cooldown_category=f"error:{category}",
            cooldown_minutes=int(settings.get("error_cooldown_minutes") or 30),
        )

    def _maybe_send_lifecycle_notifications(self, run_timestamp: datetime) -> None:
        settings = notification_settings()
        if not settings.get("enabled"):
            return
        records = LifecycleLedger().read_all()
        session_date = _ny_date_text(run_timestamp)

        if settings.get("notify_trade_entered"):
            for record in records:
                if record.get("event_type") not in {
                    LIFECYCLE_PARTIAL_FILL,
                    LIFECYCLE_FULL_FILL,
                }:
                    continue
                if str(record.get("side") or "").lower() != "buy":
                    continue
                created_at = _record_created_at(record)
                if created_at is None or _ny_date_text(created_at) != session_date:
                    continue
                self._send_trade_entry_notification(record, created_at)

        if settings.get("notify_trade_exited"):
            for trade in _realized_trades_for_date(records, session_date):
                self._send_trade_exit_notification(trade)

    def _send_trade_entry_notification(
        self,
        record: dict[str, Any],
        created_at: datetime,
    ) -> None:
        symbol = _optional_text(record.get("symbol")) or "position"
        bot = _optional_text(record.get("bot")) or "Unknown"
        order_id = _optional_text(record.get("order_id")) or created_at.isoformat()
        reason = _optional_text(record.get("reason")) or "entry"
        qty = _optional_text(record.get("fill_delta_qty") or record.get("filled_qty"))
        price = _optional_text(record.get("filled_avg_price"))
        subject = f"Edgewalker entered {symbol} via {_specialist_display_name(bot)}"
        lines = [
            subject,
            "",
            f"Time: {created_at.astimezone(NY_TZ).isoformat(timespec='seconds')}",
            f"Specialist: {_specialist_display_name(bot)}",
            f"Reason: {reason}",
        ]
        if qty:
            lines.append(f"Quantity: {qty}")
        if price:
            lines.append(f"Average fill: ${price}")
        self._deliver_notification_event(
            event_id=f"trade-entered:{order_id}:{symbol}",
            subject=subject,
            body="\n".join(lines),
        )

    def _send_trade_exit_notification(self, trade: dict[str, Any]) -> None:
        symbol = _optional_text(trade.get("symbol")) or "position"
        bot = _optional_text(trade.get("bot")) or "Unknown"
        closed_at = _optional_text(trade.get("closed_at")) or now_iso()
        order_id = _optional_text(trade.get("exit_order_id")) or closed_at
        realized_pl = _narrative_money(trade.get("realized_pl"))
        subject = (
            f"Edgewalker closed {symbol}: {realized_pl} "
            f"({_specialist_display_name(bot)})"
        )
        lines = [
            subject,
            "",
            f"Opened: {_optional_text(trade.get('opened_at')) or '--'}",
            f"Closed: {closed_at}",
            f"Specialist: {_specialist_display_name(bot)}",
            f"Exit reason: {_optional_text(trade.get('exit_reason')) or '--'}",
            f"Quantity: {_optional_text(trade.get('qty')) or '--'}",
            f"Entry price: ${_optional_text(trade.get('avg_entry_price')) or '--'}",
            f"Exit price: ${_optional_text(trade.get('exit_price')) or '--'}",
            f"Realized P/L: {realized_pl}",
            f"MFE: {_optional_text(trade.get('mfe_percent')) or '--'}%",
            f"MAE: {_optional_text(trade.get('mae_percent')) or '--'}%",
            f"Capture: {_optional_text(trade.get('capture_ratio_percent')) or '--'}%",
        ]
        self._deliver_notification_event(
            event_id=f"trade-exited:{order_id}:{symbol}",
            subject=subject,
            body="\n".join(lines),
        )

    def _maybe_send_daily_summary_notification(
        self,
        next_open: datetime | None,
    ) -> None:
        settings = notification_settings()
        if not (
            settings.get("enabled")
            and settings.get("notify_daily_summary")
        ):
            return
        target_date = self._daily_summary_notification_date(next_open)
        if not target_date:
            return
        try:
            payload = build_operator_spreadsheet_daily_row(
                target_date,
                include_daily_narrative=False,
            )
        except BotError as exc:
            self._record_notification_activity(
                f"[NOTIFY] Daily summary failed for {target_date}: {exc}",
                error=str(exc),
            )
            return
        row = payload.get("row") if isinstance(payload, dict) else {}
        if not isinstance(row, dict):
            row = {}
        result = _optional_text(row.get("account_result_status")) or "SESSION"
        realized = _narrative_money(row.get("realized_pl_dollars"))
        trade_count = int(_float_from_value(row.get("closed_trades")) or 0)
        next_open_text = (
            next_open.astimezone(NY_TZ).isoformat(timespec="seconds")
            if next_open
            else "Unknown"
        )
        subject = f"Edgewalker EOD {target_date}: {realized} ({result})"
        body = "\n".join(
            [
                subject,
                "",
                f"Closed trades: {trade_count}",
                f"Account value: {_narrative_money(row.get('ending_account_value'))}",
                f"Momentum: {_narrative_money(row.get('momentum_pl'))}",
                f"Chop: {_narrative_money(row.get('chop_pl'))}",
                f"Inverse: {_narrative_money(row.get('inverse_pl'))}",
                f"Next market open: {next_open_text}",
            ]
        )
        self._deliver_notification_event(
            event_id=f"daily-summary:{target_date}",
            subject=subject,
            body=body,
        )

    def _daily_summary_notification_date(
        self,
        next_open: datetime | None,
    ) -> str | None:
        now_ny = datetime.now(NY_TZ)
        today = now_ny.date().isoformat()
        if next_open is not None:
            next_open_day = next_open.astimezone(NY_TZ).date().isoformat()
            if next_open_day == today:
                return None
        elif now_ny.hour < 16:
            return None

        latest_log_date = _most_recent_log_date(market_open_only=True)
        if latest_log_date != today:
            return None
        return today

    def _preset_authority_effective_config(
        self,
        base_config: BotConfig,
        run_timestamp: datetime,
    ) -> tuple[BotConfig, list[str], dict[str, Any] | None]:
        plan = self._preset_authority_plan
        if not plan or plan.get("mode") != PRESET_AUTHORITY_MODE_V6:
            return base_config, [], None

        role_configs = plan.get("role_configs")
        if not isinstance(role_configs, dict):
            return base_config, [], None

        now_ny = run_timestamp.astimezone(NY_TZ)
        session_date = now_ny.date().isoformat()
        state = self._preset_authority_state
        if state.get("session_date") != session_date:
            state = {
                "session_date": session_date,
                "evaluated": False,
                "selected_role": "generalist",
                "authority_action": "PENDING",
                "authority_reason": "Waiting for 09:45 ET authority checkpoint.",
            }
            self._preset_authority_state = state

        selected_role = _optional_text(state.get("selected_role")) or "generalist"
        if state.get("evaluated"):
            return role_configs.get(selected_role, base_config), [], dict(state)

        current_minutes = now_ny.hour * 60 + now_ny.minute
        checkpoint_minutes = 9 * 60 + 45
        expiry_minutes = 10 * 60
        if current_minutes < checkpoint_minutes:
            return role_configs.get("generalist", base_config), [], dict(state)

        if current_minutes >= expiry_minutes:
            state.update(
                {
                    "evaluated": True,
                    "selected_role": "generalist",
                    "authority_action": "GENERALIST_DEFAULT",
                    "router_confidence": "LOW",
                    "authority_reason": (
                        "v6 09:45 authority window expired before evaluation; "
                        "staying with Lead_Generalist."
                    ),
                    "evaluated_at": now_ny.isoformat(timespec="seconds"),
                }
            )
            return (
                role_configs.get("generalist", base_config),
                [self._preset_authority_log_line(state)],
                dict(state),
            )

        decision = self._preset_authority_v6_decision(plan)
        selected_role = (
            _optional_text(decision.get("selected_role")) or "generalist"
        )
        state.update(decision)
        state.update(
            {
                "session_date": session_date,
                "evaluated": True,
                "selected_role": selected_role,
                "evaluated_at": now_ny.isoformat(timespec="seconds"),
            }
        )
        return (
            role_configs.get(selected_role, base_config),
            [self._preset_authority_log_line(state)],
            dict(state),
        )

    def _preset_authority_v6_decision(
        self,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        role_names = plan.get("role_names") if isinstance(plan.get("role_names"), dict) else {}
        bars = self._market_data.get_recent_bars(SOXL, 120)
        path = _runtime_source_price_path(bars)
        source_return = path.get("source_open_to_current_percent")
        source_drawdown = path.get("source_max_drawdown_from_open_percent")
        source_runup = path.get("source_max_runup_from_open_percent")

        if source_return is None or source_drawdown is None:
            return {
                "authority_model": PRESET_AUTHORITY_MODEL_V6,
                "authority_action": "GENERALIST_DEFAULT",
                "selected_role": "generalist",
                "raw_role": "generalist",
                "router_confidence": "LOW",
                "authority_preset": role_names.get("generalist", "Lead_Generalist"),
                "authority_reason": (
                    "v6 authority could not read enough regular-session SOXL bars; "
                    "staying with Lead_Generalist."
                ),
                **path,
            }

        raw_role = "generalist"
        confidence = "LOW"
        reasons: list[str] = []
        if source_return >= 2.75 and source_drawdown > -1.5:
            raw_role = "momentum"
            confidence = "HIGH" if source_return >= 4 else "MODERATE"
            reasons.append(f"SOXL is positive early from open ({source_return:g}%).")
            if source_runup is not None:
                reasons.append(f"SOXL early runup reached {source_runup:g}%.")
        elif source_return <= -4 and source_drawdown <= -4:
            raw_role = "inverse"
            confidence = "HIGH"
            reasons.append(f"SOXL is sharply negative early ({source_return:g}%).")
            reasons.append(f"SOXL early drawdown reached {source_drawdown:g}%.")
        else:
            reasons.append("No specialist threshold cleared; stay with the generalist.")

        action = "GENERALIST_DEFAULT"
        selected_role = "generalist"
        authority_reason = " ".join(reasons)
        if raw_role != "generalist" and confidence != "HIGH":
            action = "ADVISORY_ONLY"
            authority_reason = (
                f"09:45 {raw_role} signal was {confidence}; v6 only grants "
                "authority to HIGH-confidence specialist calls. "
                + authority_reason
            )
        elif raw_role == "inverse" and source_return <= -7 and source_drawdown <= -7:
            action = "BLOCKED_REVIEW"
            authority_reason = (
                "Extreme 09:45 selloff is quarantined for review; v6 stays "
                "with Lead_Generalist. "
                + authority_reason
            )
        elif raw_role == "inverse" and source_return - source_drawdown >= 1.5:
            action = "BLOCKED_REVIEW"
            rebound_gap = source_return - source_drawdown
            authority_reason = (
                "09:45 Inverse signal already bounced materially from the early "
                f"drawdown ({rebound_gap:g} percentage points); v6 stays with "
                "Lead_Generalist. "
                + authority_reason
            )
        elif raw_role in {"momentum", "inverse"} and confidence == "HIGH":
            action = "ROUTE"
            selected_role = raw_role
            authority_reason = (
                f"09:45 {raw_role} signal is HIGH confidence and no v6 block fired. "
                + authority_reason
            )

        return {
            "authority_model": PRESET_AUTHORITY_MODEL_V6,
            "authority_action": action,
            "selected_role": selected_role,
            "raw_role": raw_role,
            "router_confidence": confidence,
            "authority_preset": role_names.get(
                selected_role,
                role_names.get("generalist", "Lead_Generalist"),
            ),
            "authority_reason": authority_reason,
            **path,
        }

    def _preset_authority_log_line(self, state: dict[str, Any]) -> str:
        source_return = state.get("source_open_to_current_percent")
        source_drawdown = state.get("source_max_drawdown_from_open_percent")
        soxl_text = (
            f" soxl={source_return:+.2f}%"
            if isinstance(source_return, (int, float))
            else ""
        )
        drawdown_text = (
            f" dd={source_drawdown:+.2f}%"
            if isinstance(source_drawdown, (int, float))
            else ""
        )
        return (
            "[AUTHORITY] "
            f"model={state.get('authority_model') or PRESET_AUTHORITY_MODEL_V6} "
            f"action={state.get('authority_action')} "
            f"raw={state.get('raw_role') or '--'} "
            f"selected={state.get('selected_role') or 'generalist'} "
            f"confidence={state.get('router_confidence') or '--'}"
            f"{soxl_text}{drawdown_text} "
            f"reason={state.get('authority_reason') or '--'}"
        )

    def _run_cycle(self, config: BotConfig) -> None:
        output = io.StringIO()
        error: str | None = None
        edgewalker_status: dict[str, Any] | None = None
        authority_state: dict[str, Any] | None = None
        broker_state = broker_constraint_payload(broker_constraint_ok())
        run_timestamp = datetime.now(timezone.utc)
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                self._market_data.ensure_running(config)
                effective_config, authority_lines, authority_state = (
                    self._preset_authority_effective_config(config, run_timestamp)
                )
                if effective_config.data_feed != config.data_feed:
                    self._market_data.ensure_running(effective_config)
                for line in authority_lines:
                    print(line)
                status = EdgeWalkerBot(
                    effective_config,
                    AlpacaClient(effective_config),
                    market_data=self._market_data,
                ).run_once()
                edgewalker_status = asdict(status)
                if authority_state:
                    edgewalker_status["preset_authority"] = authority_state
        except BotError as exc:
            error = str(exc)
            broker_state = self._broker_state_for_cycle_error(error, run_timestamp)
        except Exception as exc:  # Keep the local control server alive on surprises.
            error = f"{type(exc).__name__}: {exc}"
            broker_state = broker_constraint_payload(classify_broker_error(error))

        lines = [line for line in output.getvalue().splitlines() if line.strip()]
        if error:
            lines.append(f"[error] {error}")

        logged_config = effective_config if "effective_config" in locals() else config
        with self._lock:
            self._config = logged_config
            self._cycle_count += 1
            cycle_id = self._cycle_count
            self._last_run_at = now_iso()
            self._last_error = error
            self._broker_state = broker_state
            transition = self._regime_transition_locked(edgewalker_status)
            if transition:
                lines.append(_format_regime_transition(transition))
            if edgewalker_status:
                self._edgewalker_status = edgewalker_status
            self._last_output = lines[-40:] if lines else ["Cycle complete."]
            self._append_activity_locked(self._last_output)
            self._append_cycle_log_locked(
                config=logged_config,
                cycle_id=cycle_id,
                timestamp=run_timestamp,
                console_lines=lines,
                error=error,
                edgewalker_status=edgewalker_status,
                broker_state=broker_state,
                regime_transition=transition,
            )

    def _broker_state_for_cycle_error(
        self,
        error: str,
        run_timestamp: datetime,
    ) -> dict[str, Any]:
        recent_rejection = self._latest_recent_order_rejection(run_timestamp)
        if recent_rejection:
            constraint = recent_rejection.get("broker_constraint")
            if isinstance(constraint, dict):
                return constraint
        return broker_constraint_payload(classify_broker_error(error))

    def _latest_recent_order_rejection(
        self,
        run_timestamp: datetime,
    ) -> dict[str, Any] | None:
        records = LifecycleLedger().read_all()
        for record in reversed(records):
            if record.get("event_type") != LIFECYCLE_ORDER_REJECTED:
                continue
            created_at = record.get("created_at")
            if not isinstance(created_at, str):
                continue
            try:
                parsed = datetime.fromisoformat(created_at)
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed.astimezone(timezone.utc) >= run_timestamp - timedelta(seconds=2):
                return record
            return None
        return None

    def _append_activity_locked(self, lines: list[str]) -> None:
        now = datetime.now(NY_TZ)
        for line in lines:
            self._activity_log.append((now, line))
        self._activity_log = _current_ny_activity(self._activity_log, now)
        self._save_activity_log()

    def _load_activity_log(self) -> list[tuple[datetime, str]]:
        if not ACTIVITY_PATH.exists():
            return []

        try:
            raw_entries = json.loads(ACTIVITY_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        if not isinstance(raw_entries, list):
            return []

        now = datetime.now(NY_TZ)
        entries: list[tuple[datetime, str]] = []
        for entry in raw_entries:
            if not isinstance(entry, dict):
                continue
            created_at_raw = entry.get("created_at")
            line = entry.get("line")
            if not isinstance(created_at_raw, str) or not isinstance(line, str):
                continue
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except ValueError:
                continue
            entries.append((created_at, line))
        return _current_ny_activity(entries, now)

    def _regime_transition_locked(
        self,
        edgewalker_status: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not edgewalker_status:
            return None

        regime = edgewalker_status.get("regime")
        if not isinstance(regime, str) or not regime:
            return None

        previous = self._last_regime
        self._last_regime = regime
        if previous is None or previous == regime:
            return None

        return {
            "from": previous,
            "to": regime,
            "gap_percent": edgewalker_status.get("gap_percent"),
        }

    def _append_cycle_log_locked(
        self,
        config: BotConfig,
        cycle_id: int,
        timestamp: datetime,
        console_lines: list[str],
        error: str | None,
        edgewalker_status: dict[str, Any] | None,
        broker_state: dict[str, Any],
        regime_transition: dict[str, Any] | None,
    ) -> None:
        lifecycle_records = LifecycleLedger().read_all()
        performance = lifecycle_performance_summary(lifecycle_records, timestamp)
        order_state = order_visibility_summary(
            lifecycle_records,
            BotStateStore().get_pending_orders(),
            timestamp,
        )
        record = _cycle_log_record(
            config=config,
            cycle_id=cycle_id,
            timestamp=timestamp,
            console_lines=console_lines,
            error=error,
            edgewalker_status=edgewalker_status,
            broker_state=broker_state,
            regime_transition=regime_transition,
            performance=performance,
                order_state=order_state,
            )

        self._maybe_send_lifecycle_notifications(run_timestamp)
        if error:
            self._maybe_send_error_notification(
                category="cycle_error",
                subject="Edgewalker cycle error",
                body=f"Edgewalker hit a cycle error:\n\n{error}",
            )
        try:
            _append_daily_jsonl(record, timestamp)
        except OSError as exc:
            line = f"[error] Could not write daily log: {exc}"
            self._last_error = line
            self._last_output = [*self._last_output, line][-40:]
            self._activity_log.append((datetime.now(NY_TZ), line))
            self._activity_log = _current_ny_activity(self._activity_log)
            self._save_activity_log()

    def _save_activity_log(self) -> None:
        payload = [
            {"created_at": created_at.isoformat(timespec="seconds"), "line": line}
            for created_at, line in self._activity_log
        ]
        ACTIVITY_PATH.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def _snapshot_locked(self) -> RunnerSnapshot:
        self._activity_log = _current_ny_activity(self._activity_log)
        environment_settings = alpaca_environment_settings()
        market_data_status = self._market_data.status(
            SOXL,
            required_bars=self._config.slow_sma_minutes,
        )
        lifecycle_records = LifecycleLedger().read_all()
        return RunnerSnapshot(
            running=self._running,
            symbol=self._config.symbol,
            dry_run=self._config.dry_run,
            active_environment=environment_settings["active_environment"],
            live_trading_armed=environment_settings["live_trading_armed"],
            live_credentials_ready=bool(
                environment_settings["live"]["has_api_key_id"]
                and environment_settings["live"]["has_api_secret_key"]
            ),
            poll_seconds=self._config.poll_seconds,
            close_liquidate_minutes=self._config.close_liquidate_minutes,
            regime_gap_threshold=str(self._config.regime_gap_threshold),
            regime_exit_gap_threshold=str(self._config.regime_exit_gap_threshold),
            chop_entry_discount_percent=str(self._config.chop_entry_discount_percent),
            directional_mode=self._config.directional_mode,
            directional_max_extension_percent=str(
                self._config.directional_max_extension_percent
            ),
            directional_strong_chase_max_extension_percent=str(
                self._config.directional_strong_chase_max_extension_percent
            ),
            directional_min_strength=self._config.directional_min_strength,
            directional_cooldown_minutes=self._config.directional_cooldown_minutes,
            chop_permission_mode=self._config.chop_permission_mode,
            chop_permission_max_abs_source_percent=str(
                self._config.chop_permission_max_abs_source_percent
            ),
            adaptive_shadow_enabled=self._config.adaptive_shadow_enabled,
            enabled_bots=list(self._config.enabled_bots),
            momentum_authority_required=self._config.momentum_authority_required,
            momentum_authority_revoke_exits=self._config.momentum_authority_revoke_exits,
            momentum_authority_latch_once_active=(
                self._config.momentum_authority_latch_once_active
            ),
            momentum_authority_min_trust_score=(
                self._config.momentum_authority_min_trust_score
            ),
            momentum_authority_min_source_percent=str(
                self._config.momentum_authority_min_source_percent
            ),
            momentum_authority_max_transitions_per_hour=str(
                self._config.momentum_authority_max_transitions_per_hour
            ),
            momentum_authority_reclaim_enabled=(
                self._config.momentum_authority_reclaim_enabled
            ),
            momentum_authority_reclaim_min_trust_score=(
                self._config.momentum_authority_reclaim_min_trust_score
            ),
            momentum_authority_reclaim_min_source_percent=str(
                self._config.momentum_authority_reclaim_min_source_percent
            ),
            momentum_authority_reclaim_max_raw_transition_count=(
                self._config.momentum_authority_reclaim_max_raw_transition_count
            ),
            momentum_authority_reclaim_max_non_warmup_transition_count=(
                self._config.momentum_authority_reclaim_max_non_warmup_transition_count
            ),
            momentum_authority_reclaim_start_minutes=(
                self._config.momentum_authority_reclaim_start_minutes
            ),
            momentum_authority_reclaim_end_minutes=(
                self._config.momentum_authority_reclaim_end_minutes
            ),
            position_notional=str(self._config.position_notional),
            position_sizing_mode=self._config.position_sizing_mode,
            position_allocation_percent=str(self._config.position_allocation_percent),
            trail_percent=str(self._config.trail_percent),
            fast_sma_minutes=self._config.fast_sma_minutes,
            slow_sma_minutes=self._config.slow_sma_minutes,
            cycle_count=self._cycle_count,
            last_started_at=self._last_started_at,
            last_stopped_at=self._last_stopped_at,
            last_run_at=self._last_run_at,
            next_run_at=self._next_run_at,
            next_run_reason=self._next_run_reason,
            last_output=self._last_output,
            activity_log=[line for _, line in self._activity_log],
            edgewalker_status=self._edgewalker_status,
            market_data_status=market_data_status,
            broker_state=self._broker_state,
            performance=lifecycle_performance_summary(lifecycle_records),
            order_state=order_visibility_summary(
                lifecycle_records,
                BotStateStore().get_pending_orders(),
            ),
            preset_authority=self._preset_authority_snapshot_locked(),
            last_error=self._last_error,
        )

    def _preset_authority_snapshot_locked(self) -> dict[str, Any] | None:
        plan = self._preset_authority_plan
        if not plan or plan.get("mode") != PRESET_AUTHORITY_MODE_V6:
            return None
        if self._preset_authority_state:
            return dict(self._preset_authority_state)
        role_names = plan.get("role_names") if isinstance(plan.get("role_names"), dict) else {}
        return {
            "authority_model": PRESET_AUTHORITY_MODEL_V6,
            "authority_action": "PENDING",
            "selected_role": "generalist",
            "raw_role": "generalist",
            "router_confidence": None,
            "authority_preset": role_names.get("generalist", "Lead_Generalist"),
            "authority_reason": (
                "v6 authority is armed and waiting for the 09:45 ET checkpoint."
            ),
        }


def lifecycle_performance_summary(
    records: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    session_date = _ny_date_text(now)
    analysis = analyze_lifecycle_trades(records, session_date, session_tz=NY_TZ)
    realized_trades = analysis["realized_trades"]

    total_realized = sum(
        (
            _record_decimal(trade, "realized_pl") or Decimal("0")
            for trade in realized_trades
        ),
        Decimal("0"),
    )
    open_qty = analysis["open_qty"]
    open_cost_basis = analysis["open_cost_basis"]
    wins = sum(
        1
        for trade in realized_trades
        if (_record_decimal(trade, "realized_pl") or Decimal("0")) > 0
    )
    losses = sum(
        1
        for trade in realized_trades
        if (_record_decimal(trade, "realized_pl") or Decimal("0")) < 0
    )
    last_trade = realized_trades[-1] if realized_trades else None
    bot_performance = bot_performance_summary(realized_trades)
    reconciliation_confidence, reconciliation_notes = _pl_reconciliation_confidence(
        open_qty,
        analysis["unmatched_exit_qty"],
        analysis["ignored_fill_count"],
    )
    quality = trade_quality_averages(realized_trades)

    return {
        "source": "position_lifecycle",
        "session_date": session_date,
        "session_realized_pl": format_decimal(total_realized),
        "reconciliation_confidence": reconciliation_confidence,
        "reconciliation_notes": reconciliation_notes,
        "session_trade_count": len(realized_trades),
        "session_wins": wins,
        "session_losses": losses,
        "last_trade": last_trade,
        "last_trade_realized_pl": (
            last_trade.get("realized_pl") if last_trade else None
        ),
        "bot_performance": bot_performance,
        "realized_trades": realized_trades,
        "trade_quality": quality,
        "inversebot_archaeology": bot_archaeology_report(
            realized_trades,
            INVERSE_BOT,
        ),
        "open_lot_qty": format_decimal(open_qty),
        "open_lot_cost_basis": format_decimal(open_cost_basis),
        "unmatched_exit_qty": format_decimal(analysis["unmatched_exit_qty"]),
        "ignored_fill_count": analysis["ignored_fill_count"],
    }


def _pl_reconciliation_confidence(
    open_qty: Decimal,
    unmatched_exit_qty: Decimal,
    ignored_fill_count: int,
) -> tuple[str, list[str]]:
    notes: list[str] = []
    if unmatched_exit_qty > 0:
        notes.append(f"unmatched_exit_qty={format_decimal(unmatched_exit_qty)}")
    if ignored_fill_count > 0:
        notes.append(f"ignored_fill_records={ignored_fill_count}")
    if notes:
        return "LOW", notes

    if open_qty > 0:
        return "MEDIUM", [f"open_lot_qty={format_decimal(open_qty)}"]

    return "HIGH", ["all_fills_matched"]


def order_visibility_summary(
    records: list[dict[str, Any]],
    pending_orders: dict[str, dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    session_date = _ny_date_text(now)
    pending = [
        _pending_order_payload(order_id, order)
        for order_id, order in pending_orders.items()
        if isinstance(order, dict)
    ]
    pending.sort(key=lambda order: order.get("updated_at") or "", reverse=True)

    recent_events: list[dict[str, Any]] = []
    for record in records:
        if record.get("event_type") not in {
            LIFECYCLE_ORDER_ACCEPTED,
            LIFECYCLE_ORDER_REJECTED,
            LIFECYCLE_PARTIAL_FILL,
            LIFECYCLE_FULL_FILL,
        }:
            continue
        created_at = _record_created_at(record)
        if created_at is None or _ny_date_text(created_at) != session_date:
            continue
        recent_events.append(_order_event_payload(record, created_at))

    recent_events = list(reversed(recent_events[-8:]))
    latest_fill = next(
        (
            event
            for event in recent_events
            if event["event_type"] in {LIFECYCLE_PARTIAL_FILL, LIFECYCLE_FULL_FILL}
        ),
        None,
    )
    return {
        "source": "position_lifecycle",
        "session_date": session_date,
        "position_lifecycle_state": _position_lifecycle_state(pending, recent_events),
        "pending_count": len(pending),
        "pending_orders": pending,
        "recent_events": recent_events,
        "latest_fill": latest_fill,
    }


def bot_performance_summary(realized_trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregates: dict[str, dict[str, Any]] = {
        bot: _blank_bot_performance(bot) for bot in BOT_PERFORMANCE_ORDER
    }
    order = list(BOT_PERFORMANCE_ORDER)

    for trade in realized_trades:
        bot = _optional_text(trade.get("bot")) or "UNKNOWN"
        if bot not in aggregates:
            aggregates[bot] = _blank_bot_performance(bot)
            order.append(bot)
        aggregate = aggregates[bot]
        realized_pl = _record_decimal(trade, "realized_pl") or Decimal("0")
        aggregate["realized_pl_value"] += realized_pl
        aggregate["trade_count"] += 1
        if realized_pl > 0:
            aggregate["wins"] += 1
        elif realized_pl < 0:
            aggregate["losses"] += 1
        aggregate["last_trade"] = trade
        aggregate["trades"].append(trade)

    return [_bot_performance_payload(aggregates[bot]) for bot in order]


def _blank_bot_performance(bot: str) -> dict[str, Any]:
    return {
        "bot": bot,
        "realized_pl_value": Decimal("0"),
        "trade_count": 0,
        "wins": 0,
        "losses": 0,
        "last_trade": None,
        "trades": [],
    }


def _bot_performance_payload(aggregate: dict[str, Any]) -> dict[str, Any]:
    trade_count = int(aggregate["trade_count"])
    wins = int(aggregate["wins"])
    losses = int(aggregate["losses"])
    last_trade = aggregate.get("last_trade")
    trades = aggregate.get("trades")
    trades = trades if isinstance(trades, list) else []
    quality = trade_quality_averages(trades)
    win_rate = (
        Decimal(wins) / Decimal(trade_count) * Decimal("100")
        if trade_count > 0
        else None
    )
    return {
        "bot": aggregate["bot"],
        "realized_pl": format_decimal(aggregate["realized_pl_value"]),
        "trade_count": trade_count,
        "wins": wins,
        "losses": losses,
        "win_rate_percent": format_decimal(win_rate) if win_rate is not None else None,
        "last_trade_realized_pl": (
            last_trade.get("realized_pl") if isinstance(last_trade, dict) else None
        ),
        "last_trade_symbol": (
            last_trade.get("symbol") if isinstance(last_trade, dict) else None
        ),
        "last_trade_closed_at": (
            last_trade.get("closed_at") if isinstance(last_trade, dict) else None
        ),
        "avg_mfe_percent": quality.get("avg_mfe_percent"),
        "avg_mae_percent": quality.get("avg_mae_percent"),
        "avg_capture_ratio_percent": quality.get("avg_capture_ratio_percent"),
        "avg_hold_seconds": quality.get("avg_hold_seconds"),
    }


def _pending_order_payload(order_id: str, order: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_id": order_id,
        "symbol": _optional_text(order.get("symbol")),
        "side": _optional_text(order.get("side")),
        "bot": _optional_text(order.get("bot")),
        "reason": _optional_text(order.get("reason")),
        "status": _optional_text(order.get("last_status")) or "submitted",
        "filled_qty": _optional_text(order.get("last_filled_qty")) or "0",
        "position_lifecycle_state": _optional_text(
            order.get("position_lifecycle_state")
        ),
        "submitted_at": _optional_text(order.get("submitted_at")),
        "updated_at": _optional_text(order.get("updated_at")),
    }


def _order_event_payload(
    record: dict[str, Any],
    created_at: datetime,
) -> dict[str, Any]:
    return {
        "event_type": _optional_text(record.get("event_type")),
        "created_at": created_at.astimezone(timezone.utc).isoformat(
            timespec="seconds"
        ),
        "order_id": _optional_text(record.get("order_id")),
        "symbol": _optional_text(record.get("symbol")),
        "side": _optional_text(record.get("side")),
        "bot": _optional_text(record.get("bot")),
        "status": _optional_text(record.get("status")),
        "position_lifecycle_state": _optional_text(
            record.get("position_lifecycle_state")
        ),
        "reason": _optional_text(record.get("reason")),
        "filled_qty": _optional_text(record.get("filled_qty")),
        "fill_delta_qty": _optional_text(record.get("fill_delta_qty")),
        "filled_avg_price": _optional_text(record.get("filled_avg_price")),
        "error": _optional_text(record.get("error")),
    }


def _position_lifecycle_state(
    pending_orders: list[dict[str, Any]],
    recent_events: list[dict[str, Any]],
) -> str:
    pending_states = {
        order.get("position_lifecycle_state")
        for order in pending_orders
        if order.get("position_lifecycle_state")
    }
    if POSITION_LIFECYCLE_CLOSING in pending_states:
        return POSITION_LIFECYCLE_CLOSING
    if POSITION_LIFECYCLE_OPENING in pending_states:
        return POSITION_LIFECYCLE_OPENING

    for event in recent_events:
        state = event.get("position_lifecycle_state")
        if state in {POSITION_LIFECYCLE_OPEN, POSITION_LIFECYCLE_CLOSED}:
            return state

    return POSITION_LIFECYCLE_CLOSED


def _optional_text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _env_bool_text(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def _payload_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return _env_bool_text(str(value))


def _notification_cooldown_minutes(value: Any) -> int:
    if value in (None, ""):
        return NOTIFICATION_DEFAULT_ERROR_COOLDOWN_MINUTES
    try:
        minutes = int(str(value).strip())
    except ValueError as exc:
        raise BotError("Notification error cooldown must be a whole number.") from exc
    if minutes < 1:
        raise BotError("Notification error cooldown must be at least 1 minute.")
    return minutes


def _is_secret_placeholder(value: str | None) -> bool:
    return value in (None, "", SECRET_PLACEHOLDER)


def _mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "********"
    return f"********{value[-4:]}"


def _read_env_values(path: Path | None = None) -> dict[str, str]:
    path = path or ENV_PATH
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = ENV_KEY_RE.match(raw_line)
        if not match:
            continue
        key = match.group(1)
        _, raw_value = raw_line.split("=", 1)
        value = raw_value.strip().strip('"').strip("'")
        values[key] = value
    return values


def _quote_env_value(value: str) -> str:
    if value == "" or any(char.isspace() or char in value for char in "\"'#"):
        return json.dumps(value)
    return value


def _write_env_updates(updates: dict[str, str], path: Path | None = None) -> None:
    path = path or ENV_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    updated_lines: list[str] = []
    for line in lines:
        match = ENV_KEY_RE.match(line)
        if match and match.group(1) in updates:
            key = match.group(1)
            updated_lines.append(f"{key}={_quote_env_value(updates[key])}")
            seen.add(key)
        else:
            updated_lines.append(line)

    if updates:
        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        for key, value in updates.items():
            if key not in seen:
                updated_lines.append(f"{key}={_quote_env_value(value)}")
    path.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")
    for key, value in updates.items():
        os.environ[key] = value


def _env_first(values: dict[str, str], *keys: str, default: str = "") -> str:
    for key in keys:
        if values.get(key):
            return values[key]
    return default


def _live_credentials_ready(values: dict[str, str] | None = None) -> bool:
    values = values if values is not None else _read_env_values()
    live_key = values.get("ALPACA_LIVE_API_KEY_ID") or os.environ.get(
        "ALPACA_LIVE_API_KEY_ID",
        "",
    )
    live_secret = values.get("ALPACA_LIVE_API_SECRET_KEY") or os.environ.get(
        "ALPACA_LIVE_API_SECRET_KEY",
        "",
    )
    return bool(live_key and live_secret)


def live_trading_armed() -> bool:
    values = _read_env_values()
    raw_armed = _env_bool_text(
        os.environ.get("LIVE_TRADING_ARMED") or values.get("LIVE_TRADING_ARMED")
    )
    return raw_armed and _live_credentials_ready(values)


def _is_live_trading_url(url: str) -> bool:
    normalized = url.rstrip("/").lower()
    return "paper-api" not in normalized and "api.alpaca.markets" in normalized


def current_alpaca_environment() -> str:
    values = _read_env_values()
    environment = (
        os.environ.get("ALPACA_ENVIRONMENT")
        or values.get("ALPACA_ENVIRONMENT")
        or "paper"
    ).strip().lower()
    return environment if environment in {"paper", "live"} else "paper"


def _live_trading_guard_required(url: str) -> bool:
    return current_alpaca_environment() == "live" or _is_live_trading_url(url)


def operator_spreadsheet_settings(values: dict[str, str] | None = None) -> dict[str, Any]:
    values = values or _read_env_values()
    return {
        "spreadsheet_url": _env_first(values, "OPERATOR_SPREADSHEET_URL"),
        "post_endpoint_url": _env_first(values, "OPERATOR_SPREADSHEET_POST_URL"),
        "research_spreadsheet_url": _env_first(
            values,
            "OPERATOR_RESEARCH_SPREADSHEET_URL",
        ),
        "research_post_endpoint_url": _env_first(
            values,
            "OPERATOR_RESEARCH_SPREADSHEET_POST_URL",
        ),
        "research_mode_enabled": _env_bool_text(
            _env_first(
                values,
                "EDGEWALKER_RESEARCH_MODE",
                default="false",
            )
        ),
        "auto_post_enabled": _env_bool_text(
            _env_first(
                values,
                "OPERATOR_SPREADSHEET_AUTO_POST",
                default="false",
            )
        ),
        "include_daily_narrative": _env_bool_text(
            _env_first(
                values,
                "OPERATOR_SPREADSHEET_INCLUDE_NARRATIVE",
                default="true",
            )
        ),
    }


def notification_settings(values: dict[str, str] | None = None) -> dict[str, Any]:
    values = values or _read_env_values()
    provider = _env_first(
        values,
        "NOTIFICATION_PROVIDER",
        default=NOTIFICATION_PROVIDER_APPS_SCRIPT,
    ).strip().lower()
    if provider != NOTIFICATION_PROVIDER_APPS_SCRIPT:
        provider = NOTIFICATION_PROVIDER_APPS_SCRIPT
    cooldown_minutes = _notification_cooldown_minutes(
        _env_first(
            values,
            "NOTIFICATION_ERROR_COOLDOWN_MINUTES",
            default=str(NOTIFICATION_DEFAULT_ERROR_COOLDOWN_MINUTES),
        )
    )
    apps_script_secret = _env_first(values, "NOTIFICATION_APPS_SCRIPT_SECRET")
    return {
        "enabled": _env_bool_text(
            _env_first(values, "NOTIFICATIONS_ENABLED", default="false")
        ),
        "email": _env_first(values, "NOTIFICATION_EMAIL"),
        "provider": provider,
        "apps_script_url": _env_first(
            values,
            "NOTIFICATION_APPS_SCRIPT_URL",
            "NOTIFICATION_APPS_SCRIPT_ENDPOINT",
        ),
        "apps_script_secret_masked": _mask_secret(apps_script_secret),
        "has_apps_script_secret": bool(apps_script_secret),
        "notify_trade_entered": _env_bool_text(
            _env_first(values, "NOTIFY_TRADE_ENTERED", default="true")
        ),
        "notify_trade_exited": _env_bool_text(
            _env_first(values, "NOTIFY_TRADE_EXITED", default="true")
        ),
        "notify_daily_summary": _env_bool_text(
            _env_first(values, "NOTIFY_DAILY_SUMMARY", default="true")
        ),
        "notify_data_errors": _env_bool_text(
            _env_first(values, "NOTIFY_DATA_ERRORS", default="true")
        ),
        "error_cooldown_minutes": cooldown_minutes,
    }


def alpaca_environment_settings() -> dict[str, Any]:
    values = _read_env_values()
    active_environment = current_alpaca_environment()

    paper_key = _env_first(values, "ALPACA_PAPER_API_KEY_ID", "ALPACA_API_KEY_ID")
    paper_secret = _env_first(
        values,
        "ALPACA_PAPER_API_SECRET_KEY",
        "ALPACA_API_SECRET_KEY",
    )
    live_key = _env_first(values, "ALPACA_LIVE_API_KEY_ID")
    live_secret = _env_first(values, "ALPACA_LIVE_API_SECRET_KEY")

    return {
        "active_environment": active_environment,
        "live_trading_armed": live_trading_armed(),
        "operator_spreadsheet": operator_spreadsheet_settings(values),
        "notifications": notification_settings(values),
        "data_base_url": normalize_alpaca_base_url(
            _env_first(
                values,
                "ALPACA_DATA_BASE_URL",
                default=DATA_BASE_URL_DEFAULT,
            )
        ),
        "data_feed": _env_first(values, "DATA_FEED", default="iex"),
        "paper": {
            "trading_base_url": normalize_alpaca_base_url(
                _env_first(
                    values,
                    "ALPACA_PAPER_TRADING_BASE_URL",
                    "ALPACA_TRADING_BASE_URL",
                    default=TRADING_BASE_URL_DEFAULT,
                )
            ),
            "api_key_id_masked": _mask_secret(paper_key),
            "api_secret_key_masked": _mask_secret(paper_secret),
            "has_api_key_id": bool(paper_key),
            "has_api_secret_key": bool(paper_secret),
        },
        "live": {
            "trading_base_url": normalize_alpaca_base_url(
                _env_first(
                    values,
                    "ALPACA_LIVE_TRADING_BASE_URL",
                    default=LIVE_TRADING_BASE_URL_DEFAULT,
                )
            ),
            "api_key_id_masked": _mask_secret(live_key),
            "api_secret_key_masked": _mask_secret(live_secret),
            "has_api_key_id": bool(live_key),
            "has_api_secret_key": bool(live_secret),
        },
    }


def _settings_updates_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    active_environment = str(
        payload.get("active_environment")
        or payload.get("activeEnvironment")
        or "paper"
    ).strip().lower()
    if active_environment not in {"paper", "live"}:
        raise BotError("Active environment must be paper or live.")

    updates = {
        "ALPACA_ENVIRONMENT": active_environment,
        "ALPACA_DATA_BASE_URL": normalize_alpaca_base_url(
            str(
                payload.get("data_base_url")
                or payload.get("dataBaseUrl")
                or DATA_BASE_URL_DEFAULT
            )
        ),
        "DATA_FEED": str(
            payload.get("data_feed") or payload.get("dataFeed") or "iex"
        ).strip(),
    }

    spreadsheet = payload.get("operator_spreadsheet") or payload.get(
        "operatorSpreadsheet"
    )
    if not isinstance(spreadsheet, dict):
        spreadsheet = {}
    updates["OPERATOR_SPREADSHEET_URL"] = _optional_text(
        spreadsheet.get("spreadsheet_url") or spreadsheet.get("spreadsheetUrl")
    ) or ""
    updates["OPERATOR_SPREADSHEET_POST_URL"] = _optional_text(
        spreadsheet.get("post_endpoint_url") or spreadsheet.get("postEndpointUrl")
    ) or ""
    updates["OPERATOR_RESEARCH_SPREADSHEET_URL"] = _optional_text(
        spreadsheet.get("research_spreadsheet_url")
        or spreadsheet.get("researchSpreadsheetUrl")
    ) or ""
    updates["OPERATOR_RESEARCH_SPREADSHEET_POST_URL"] = _optional_text(
        spreadsheet.get("research_post_endpoint_url")
        or spreadsheet.get("researchPostEndpointUrl")
    ) or ""
    research_mode_enabled = spreadsheet.get("research_mode_enabled")
    if research_mode_enabled is None:
        research_mode_enabled = spreadsheet.get("researchModeEnabled")
    updates["EDGEWALKER_RESEARCH_MODE"] = (
        "true" if _payload_bool(research_mode_enabled, default=False) else "false"
    )
    auto_post_enabled = spreadsheet.get("auto_post_enabled")
    if auto_post_enabled is None:
        auto_post_enabled = spreadsheet.get("autoPostEnabled")
    updates["OPERATOR_SPREADSHEET_AUTO_POST"] = (
        "true" if _payload_bool(auto_post_enabled, default=False) else "false"
    )
    include_daily_narrative = spreadsheet.get("include_daily_narrative")
    if include_daily_narrative is None:
        include_daily_narrative = spreadsheet.get("includeDailyNarrative")
    updates["OPERATOR_SPREADSHEET_INCLUDE_NARRATIVE"] = (
        "true" if _payload_bool(include_daily_narrative, default=True) else "false"
    )

    notifications = payload.get("notifications")
    if not isinstance(notifications, dict):
        notifications = {}
    updates["NOTIFICATIONS_ENABLED"] = (
        "true"
        if _payload_bool(notifications.get("enabled"), default=False)
        else "false"
    )
    updates["NOTIFICATION_EMAIL"] = _optional_text(
        notifications.get("email")
    ) or ""
    updates["NOTIFICATION_PROVIDER"] = NOTIFICATION_PROVIDER_APPS_SCRIPT
    updates["NOTIFICATION_APPS_SCRIPT_URL"] = _optional_text(
        notifications.get("apps_script_url")
        or notifications.get("appsScriptUrl")
        or notifications.get("endpoint_url")
        or notifications.get("endpointUrl")
    ) or ""
    apps_script_secret = _optional_text(
        notifications.get("apps_script_secret")
        or notifications.get("appsScriptSecret")
    )
    if not _is_secret_placeholder(apps_script_secret):
        updates["NOTIFICATION_APPS_SCRIPT_SECRET"] = apps_script_secret.strip()
    updates["NOTIFY_TRADE_ENTERED"] = (
        "true"
        if _payload_bool(notifications.get("notify_trade_entered"), default=True)
        else "false"
    )
    updates["NOTIFY_TRADE_EXITED"] = (
        "true"
        if _payload_bool(notifications.get("notify_trade_exited"), default=True)
        else "false"
    )
    updates["NOTIFY_DAILY_SUMMARY"] = (
        "true"
        if _payload_bool(notifications.get("notify_daily_summary"), default=True)
        else "false"
    )
    updates["NOTIFY_DATA_ERRORS"] = (
        "true"
        if _payload_bool(notifications.get("notify_data_errors"), default=True)
        else "false"
    )
    cooldown_raw = notifications.get("error_cooldown_minutes")
    if cooldown_raw is None:
        cooldown_raw = notifications.get("errorCooldownMinutes")
    updates["NOTIFICATION_ERROR_COOLDOWN_MINUTES"] = str(
        _notification_cooldown_minutes(cooldown_raw)
    )

    for env_name, prefix in (("paper", "ALPACA_PAPER"), ("live", "ALPACA_LIVE")):
        section = payload.get(env_name)
        if not isinstance(section, dict):
            section = {}
        trading_url = _optional_text(
            section.get("trading_base_url") or section.get("tradingBaseUrl")
        )
        if trading_url:
            updates[f"{prefix}_TRADING_BASE_URL"] = normalize_alpaca_base_url(
                trading_url
            )
        key_id = _optional_text(section.get("api_key_id") or section.get("apiKeyId"))
        secret = _optional_text(
            section.get("api_secret_key") or section.get("apiSecretKey")
        )
        if not _is_secret_placeholder(key_id):
            updates[f"{prefix}_API_KEY_ID"] = key_id.strip()
        if not _is_secret_placeholder(secret):
            updates[f"{prefix}_API_SECRET_KEY"] = secret.strip()
    return updates


def save_alpaca_environment_settings(payload: dict[str, Any]) -> dict[str, Any]:
    updates = _settings_updates_from_payload(payload)
    live_section = payload.get("live")
    if not isinstance(live_section, dict):
        live_section = {}
    live_credentials_changed = not _is_secret_placeholder(
        _optional_text(live_section.get("api_key_id") or live_section.get("apiKeyId"))
    ) or not _is_secret_placeholder(
        _optional_text(
            live_section.get("api_secret_key") or live_section.get("apiSecretKey")
        )
    )
    _write_env_updates(updates)
    settings = alpaca_environment_settings()
    if live_credentials_changed or not (
        settings["live"]["has_api_key_id"] and settings["live"]["has_api_secret_key"]
    ):
        _write_env_updates({"LIVE_TRADING_ARMED": "false"})
        settings = alpaca_environment_settings()
    return settings


def _load_notification_state() -> dict[str, Any]:
    if not NOTIFICATION_STATE_PATH.exists():
        return {"sent_event_ids": [], "cooldowns": {}}
    try:
        payload = json.loads(NOTIFICATION_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"sent_event_ids": [], "cooldowns": {}}
    if not isinstance(payload, dict):
        return {"sent_event_ids": [], "cooldowns": {}}
    sent_ids = payload.get("sent_event_ids")
    cooldowns = payload.get("cooldowns")
    return {
        "sent_event_ids": [
            event_id for event_id in sent_ids if isinstance(event_id, str)
        ]
        if isinstance(sent_ids, list)
        else [],
        "cooldowns": {
            key: value
            for key, value in cooldowns.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        if isinstance(cooldowns, dict)
        else {},
    }


def _save_notification_state(state: dict[str, Any]) -> None:
    sent_ids = state.get("sent_event_ids")
    if not isinstance(sent_ids, list):
        sent_ids = []
    cooldowns = state.get("cooldowns")
    if not isinstance(cooldowns, dict):
        cooldowns = {}
    payload = {
        "sent_event_ids": sent_ids[-NOTIFICATION_SENT_EVENT_LIMIT:],
        "cooldowns": cooldowns,
    }
    NOTIFICATION_STATE_PATH.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def _apps_script_error_message(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8")
    except Exception:
        body = ""
    if body:
        return f"Apps Script HTTP {exc.code}: {body[:240]}"
    return f"Apps Script HTTP {exc.code}"


def send_notification_email(
    *,
    subject: str,
    text: str,
    html: str | None = None,
) -> dict[str, Any]:
    values = _read_env_values()
    settings = notification_settings(values)
    if settings["provider"] != NOTIFICATION_PROVIDER_APPS_SCRIPT:
        raise BotError("Only Google Apps Script notifications are supported.")
    recipient = _optional_text(settings.get("email"))
    endpoint = _optional_text(settings.get("apps_script_url"))
    shared_secret = _env_first(values, "NOTIFICATION_APPS_SCRIPT_SECRET")
    if not recipient:
        raise BotError("Add a notification email address first.")
    if not endpoint:
        raise BotError("Add an Apps Script notification endpoint first.")

    payload = {
        "kind": "notification",
        "to": recipient,
        "subject": subject,
        "body": text,
    }
    if shared_secret:
        payload["shared_secret"] = shared_secret
    if html:
        payload["html_body"] = html
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response_body = response.read().decode("utf-8")
            try:
                parsed = json.loads(response_body) if response_body else {}
            except json.JSONDecodeError:
                parsed = {"raw": response_body}
            if parsed.get("status") == "error":
                raise BotError(
                    str(parsed.get("message") or "Apps Script notification failed.")
                )
            return {
                "status": "sent",
                "provider": settings["provider"],
                "recipient": recipient,
                "response": parsed,
            }
    except urllib.error.HTTPError as exc:
        raise BotError(_apps_script_error_message(exc)) from exc
    except urllib.error.URLError as exc:
        raise BotError(f"Notification send failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise BotError("Notification send timed out.") from exc


def send_test_notification_email() -> dict[str, Any]:
    now_text = datetime.now(NY_TZ).isoformat(timespec="seconds")
    return send_notification_email(
        subject="Edgewalker test notification",
        text=(
            "Edgewalker notification test succeeded.\n\n"
            f"Sent at {now_text}."
        ),
        html=(
            "<p><strong>Edgewalker notification test succeeded.</strong></p>"
            f"<p>Sent at {now_text}.</p>"
        ),
    )


def _config_for_alpaca_environment(environment: str) -> BotConfig:
    environment = environment.strip().lower()
    if environment not in {"paper", "live"}:
        raise BotError("Environment must be paper or live.")
    return replace(BotConfig.from_env(environment_override=environment), dry_run=True)


def test_alpaca_connection(environment: str) -> dict[str, Any]:
    config = _config_for_alpaca_environment(environment)
    account = AlpacaClient(config).get_account()
    return {
        "environment": environment.strip().lower(),
        "status": "ok",
        "account_status": account.get("status"),
        "account_number": _mask_secret(_optional_text(account.get("account_number"))),
        "portfolio_value": _optional_text(account.get("portfolio_value")),
        "buying_power": _optional_text(account.get("buying_power")),
        "trading_blocked": bool(account.get("trading_blocked")),
        "account_blocked": bool(account.get("account_blocked")),
    }


def set_live_trading_armed(confirmation: str) -> dict[str, Any]:
    if confirmation != "LIVE":
        raise BotError('Type "LIVE" to arm live trading.')
    settings = alpaca_environment_settings()
    if not (
        settings["live"]["has_api_key_id"]
        and settings["live"]["has_api_secret_key"]
    ):
        raise BotError("Add live API key and secret before arming live trading.")
    _write_env_updates({"LIVE_TRADING_ARMED": "true"})
    return alpaca_environment_settings()


def set_live_trading_disarmed() -> dict[str, Any]:
    _write_env_updates({"LIVE_TRADING_ARMED": "false"})
    return alpaca_environment_settings()


def _dominant_bot(matched_lot_bots: list[tuple[str | None, Decimal]]) -> str | None:
    totals: dict[str, Decimal] = {}
    for bot, qty in matched_lot_bots:
        if bot is None:
            continue
        totals[bot] = totals.get(bot, Decimal("0")) + qty
    if not totals:
        return None
    return max(totals.items(), key=lambda item: item[1])[0]


def _record_created_at(record: dict[str, Any]) -> datetime | None:
    raw = record.get("created_at")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _record_decimal(record: dict[str, Any], key: str) -> Decimal | None:
    raw = record.get(key)
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _specialist_display_name(bot: str | None) -> str:
    if not bot:
        return "Unknown"
    return SPECIALIST_DISPLAY_NAMES.get(bot, bot)


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00",
        "Z",
    )


def _ny_date_text(value: datetime | None = None) -> str:
    current = value or datetime.now(NY_TZ)
    if current.tzinfo is None:
        return current.date().isoformat()
    return current.astimezone(NY_TZ).date().isoformat()


def _current_ny_activity(
    entries: list[tuple[datetime, str]],
    now: datetime | None = None,
) -> list[tuple[datetime, str]]:
    current_date = _ny_date_text(now)
    return [
        (created_at, line)
        for created_at, line in entries
        if _ny_date_text(created_at) == current_date
    ]


def _config_log_payload(config: BotConfig) -> dict[str, Any]:
    values = _read_env_values()
    return {
        "config_version": _env_first(
            values,
            "OPERATOR_CONFIG_VERSION",
            default="v1",
        ),
        "strategy_version": _env_first(
            values,
            "OPERATOR_STRATEGY_VERSION",
            default="v1",
        ),
        "symbol": config.symbol,
        "dry_run": config.dry_run,
        "active_environment": current_alpaca_environment(),
        "poll_seconds": config.poll_seconds,
        "position_notional": str(config.position_notional),
        "position_sizing_mode": config.position_sizing_mode,
        "position_allocation_percent": str(config.position_allocation_percent),
        "trail_percent": str(config.trail_percent),
        "fast_sma_minutes": config.fast_sma_minutes,
        "slow_sma_minutes": config.slow_sma_minutes,
        "close_liquidate_minutes": config.close_liquidate_minutes,
        "regime_gap_threshold": str(config.regime_gap_threshold),
        "regime_exit_gap_threshold": str(config.regime_exit_gap_threshold),
        "chop_entry_discount_percent": str(config.chop_entry_discount_percent),
        "directional_mode": config.directional_mode,
        "directional_max_extension_percent": str(config.directional_max_extension_percent),
        "directional_strong_chase_max_extension_percent": str(
            config.directional_strong_chase_max_extension_percent
        ),
        "directional_min_strength": config.directional_min_strength,
        "directional_cooldown_minutes": config.directional_cooldown_minutes,
        "chop_permission_mode": config.chop_permission_mode,
        "chop_permission_max_abs_source_percent": str(
            config.chop_permission_max_abs_source_percent
        ),
        "adaptive_shadow_enabled": config.adaptive_shadow_enabled,
        "enabled_bots": list(config.enabled_bots),
        "momentum_authority_required": config.momentum_authority_required,
        "momentum_authority_revoke_exits": config.momentum_authority_revoke_exits,
        "momentum_authority_latch_once_active": (
            config.momentum_authority_latch_once_active
        ),
        "momentum_authority_min_trust_score": config.momentum_authority_min_trust_score,
        "momentum_authority_min_source_percent": str(
            config.momentum_authority_min_source_percent
        ),
        "momentum_authority_max_transitions_per_hour": str(
            config.momentum_authority_max_transitions_per_hour
        ),
        "momentum_authority_reclaim_enabled": config.momentum_authority_reclaim_enabled,
        "momentum_authority_reclaim_min_trust_score": (
            config.momentum_authority_reclaim_min_trust_score
        ),
        "momentum_authority_reclaim_min_source_percent": str(
            config.momentum_authority_reclaim_min_source_percent
        ),
        "momentum_authority_reclaim_max_raw_transition_count": (
            config.momentum_authority_reclaim_max_raw_transition_count
        ),
        "momentum_authority_reclaim_max_non_warmup_transition_count": (
            config.momentum_authority_reclaim_max_non_warmup_transition_count
        ),
        "momentum_authority_reclaim_start_minutes": (
            config.momentum_authority_reclaim_start_minutes
        ),
        "momentum_authority_reclaim_end_minutes": (
            config.momentum_authority_reclaim_end_minutes
        ),
        "data_feed": config.data_feed,
    }


def _cycle_log_record(
    config: BotConfig,
    cycle_id: int,
    timestamp: datetime,
    console_lines: list[str],
    error: str | None,
    edgewalker_status: dict[str, Any] | None,
    broker_state: dict[str, Any],
    regime_transition: dict[str, Any] | None,
    performance: dict[str, Any] | None = None,
    order_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "timestamp": _utc_timestamp(timestamp),
        "trading_date": _ny_date_text(timestamp),
        "cycle_id": cycle_id,
        "config": _config_log_payload(config),
        "console_lines": console_lines,
        "broker_state": broker_state,
    }
    if edgewalker_status:
        record.update(edgewalker_status)
        record["price"] = edgewalker_status.get("source_price")
        record["account_value"] = edgewalker_status.get("portfolio_value")
    if error:
        record["error"] = error
    if regime_transition:
        record["regime_transition"] = regime_transition
    if performance:
        record["performance"] = performance
        record["bot_performance"] = performance.get("bot_performance")
        record["session_realized_pl"] = performance.get("session_realized_pl")
        record["session_trade_count"] = performance.get("session_trade_count")
        record["pl_reconciliation_confidence"] = performance.get(
            "reconciliation_confidence"
        )
    if order_state:
        record["order_state"] = order_state
        record["pending_order_count"] = order_state.get("pending_count")
    return record


def _daily_log_path(
    timestamp: datetime,
    logs_root: Path = LOGS_ROOT,
) -> Path:
    return logs_root / f"edgewalker-{_ny_date_text(timestamp)}.jsonl"


def _append_daily_jsonl(
    record: dict[str, Any],
    timestamp: datetime,
    logs_root: Path = LOGS_ROOT,
) -> None:
    logs_root.mkdir(parents=True, exist_ok=True)
    path = _daily_log_path(timestamp, logs_root)
    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record) + "\n")


def _format_regime_transition(transition: dict[str, Any]) -> str:
    gap = transition.get("gap_percent")
    gap_text = f" gap={gap}%" if gap is not None else ""
    return f"[REGIME] REGIME CHANGE: {transition['from']} -> {transition['to']}{gap_text}"


def decimal_from_payload(
    payload: dict[str, Any],
    key: str,
    fallback: Decimal,
    allow_zero: bool = False,
    allow_negative: bool = False,
    aliases: tuple[str, ...] = (),
) -> Decimal:
    raw = payload_value(payload, key, str(fallback), aliases)
    try:
        value = Decimal(str(raw))
    except InvalidOperation as exc:
        raise BotError(f"{key} must be a valid number") from exc
    if allow_negative:
        return value
    if allow_zero:
        if value < 0:
            raise BotError(f"{key} must be at least 0")
        return value
    if value <= 0:
        raise BotError(f"{key} must be greater than 0")
    return value


def int_from_payload(
    payload: dict[str, Any],
    key: str,
    fallback: int,
    minimum: int,
    aliases: tuple[str, ...] = (),
) -> int:
    raw = payload_value(payload, key, fallback, aliases)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise BotError(f"{key} must be an integer") from exc
    if value < minimum:
        raise BotError(f"{key} must be at least {minimum}")
    return value


def choice_from_payload(
    payload: dict[str, Any],
    key: str,
    fallback: str,
    allowed: set[str],
    aliases: tuple[str, ...] = (),
) -> str:
    value = str(payload_value(payload, key, fallback, aliases)).strip().upper()
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise BotError(f"{key} must be one of: {choices}")
    return value


def payload_value(
    payload: dict[str, Any],
    key: str,
    fallback: Any,
    aliases: tuple[str, ...] = (),
) -> Any:
    for candidate in (key, *aliases):
        if candidate in payload:
            return payload[candidate]
    return fallback


def config_from_payload(payload: dict[str, Any]) -> BotConfig:
    base = BotConfig.from_env()
    symbol = str(payload.get("symbol", base.symbol)).strip().upper()
    if not symbol:
        raise BotError("symbol is required")

    fast_sma = int_from_payload(payload, "fastSmaMinutes", base.fast_sma_minutes, 2)
    slow_sma = int_from_payload(payload, "slowSmaMinutes", base.slow_sma_minutes, fast_sma + 1)
    if slow_sma <= fast_sma:
        raise BotError("slowSmaMinutes must be greater than fastSmaMinutes")

    poll_seconds = int_from_payload(payload, "pollSeconds", base.poll_seconds, 5)
    close_liquidate_minutes = int_from_payload(
        payload,
        "closeLiquidateMinutes",
        base.close_liquidate_minutes,
        1,
    )
    regime_gap_threshold = decimal_from_payload(
        payload,
        "regimeGapThreshold",
        base.regime_gap_threshold,
        allow_zero=True,
    )
    regime_exit_gap_threshold = decimal_from_payload(
        payload,
        "regimeExitGapThreshold",
        base.regime_exit_gap_threshold,
        allow_zero=True,
    )
    chop_entry_discount_percent = decimal_from_payload(
        payload,
        "chopEntryDiscountPercent",
        base.chop_entry_discount_percent,
        allow_zero=True,
    )
    directional_mode = choice_from_payload(
        payload,
        "directionalMode",
        base.directional_mode,
        DIRECTIONAL_MODES,
        aliases=("momentumMode",),
    )
    directional_max_extension_percent = decimal_from_payload(
        payload,
        "directionalMaxExtensionPercent",
        base.directional_max_extension_percent,
        allow_zero=True,
        aliases=("momentumMaxExtensionPercent",),
    )
    directional_strong_chase_max_extension_percent = decimal_from_payload(
        payload,
        "directionalStrongChaseMaxExtensionPercent",
        base.directional_strong_chase_max_extension_percent,
        allow_zero=True,
        aliases=("momentumStrongChaseMaxExtensionPercent",),
    )
    directional_min_strength = choice_from_payload(
        payload,
        "directionalMinStrength",
        base.directional_min_strength,
        REGIME_STRENGTHS,
        aliases=("momentumMinStrength",),
    )
    directional_cooldown_minutes = int_from_payload(
        payload,
        "directionalCooldownMinutes",
        base.directional_cooldown_minutes,
        0,
        aliases=("momentumCooldownMinutes",),
    )
    chop_permission_mode = choice_from_payload(
        payload,
        "chopPermissionMode",
        base.chop_permission_mode,
        CHOP_PERMISSION_MODES,
        aliases=("chop_permission_mode",),
    )
    chop_permission_max_abs_source_percent = decimal_from_payload(
        payload,
        "chopPermissionMaxAbsSourcePercent",
        base.chop_permission_max_abs_source_percent,
        allow_zero=True,
        aliases=("chop_permission_max_abs_source_percent",),
    )
    inverse_cascade_mode = choice_from_payload(
        payload,
        "inverseCascadeMode",
        base.inverse_cascade_mode,
        INVERSE_CASCADE_MODES,
        aliases=("inverse_cascade_mode",),
    )
    inverse_cascade_velocity_window_minutes = int_from_payload(
        payload,
        "inverseCascadeVelocityWindowMinutes",
        base.inverse_cascade_velocity_window_minutes,
        1,
        aliases=("inverse_cascade_velocity_window_minutes",),
    )
    inverse_cascade_sustain_minutes = int_from_payload(
        payload,
        "inverseCascadeSustainMinutes",
        base.inverse_cascade_sustain_minutes,
        1,
        aliases=("inverse_cascade_sustain_minutes",),
    )
    inverse_cascade_trail_percent = decimal_from_payload(
        payload,
        "inverseCascadeTrailPercent",
        base.inverse_cascade_trail_percent,
        aliases=("inverse_cascade_trail_percent",),
    )
    inverse_cascade_route_invalidation_grace_minutes = int_from_payload(
        payload,
        "inverseCascadeRouteInvalidationGraceMinutes",
        base.inverse_cascade_route_invalidation_grace_minutes,
        0,
        aliases=("inverse_cascade_route_invalidation_grace_minutes",),
    )
    inverse_cascade_proven_mfe_percent = decimal_from_payload(
        payload,
        "inverseCascadeProvenMfePercent",
        base.inverse_cascade_proven_mfe_percent,
        allow_zero=True,
        aliases=("inverse_cascade_proven_mfe_percent",),
    )
    inverse_cascade_proven_trail_percent = decimal_from_payload(
        payload,
        "inverseCascadeProvenTrailPercent",
        base.inverse_cascade_proven_trail_percent,
        aliases=("inverse_cascade_proven_trail_percent",),
    )
    inverse_cascade_proven_trail_tighten_mfe_percent = decimal_from_payload(
        payload,
        "inverseCascadeProvenTrailTightenMfePercent",
        base.inverse_cascade_proven_trail_tighten_mfe_percent,
        allow_zero=True,
        aliases=("inverse_cascade_proven_trail_tighten_mfe_percent",),
    )
    inverse_cascade_proven_route_recovery_min_source_percent = decimal_from_payload(
        payload,
        "inverseCascadeProvenRouteRecoveryMinSourcePercent",
        base.inverse_cascade_proven_route_recovery_min_source_percent,
        allow_negative=True,
        aliases=("inverse_cascade_proven_route_recovery_min_source_percent",),
    )
    adaptive_shadow_enabled = bool(
        payload.get("adaptiveShadowEnabled", base.adaptive_shadow_enabled)
    )
    position_sizing_mode = choice_from_payload(
        payload,
        "positionSizingMode",
        base.position_sizing_mode,
        POSITION_SIZING_MODES,
    )
    position_allocation_percent = decimal_from_payload(
        payload,
        "positionAllocationPercent",
        base.position_allocation_percent,
    )
    if position_allocation_percent > 100:
        raise BotError("positionAllocationPercent must be at most 100")
    dry_run = bool(payload.get("dryRun", base.dry_run))
    if not dry_run and _live_trading_guard_required(base.trading_base_url):
        if not live_trading_armed():
            raise BotError(
                'Live trading is not armed. Open Settings and type "LIVE" first.'
            )
    v9_observer_context = payload.get("v9ObserverContext")
    if not isinstance(v9_observer_context, dict):
        v9_observer_context = payload.get("v9_observer_context")
    if not isinstance(v9_observer_context, dict):
        v9_observer_context = base.v9_observer_context
    enabled_bots = normalize_enabled_bots(
        payload.get("enabledBots", payload.get("enabled_bots", base.enabled_bots))
    )
    momentum_authority_required = _payload_bool(
        payload.get(
            "momentumAuthorityRequired",
            payload.get("momentum_authority_required"),
        ),
        default=base.momentum_authority_required,
    )
    momentum_authority_revoke_exits = _payload_bool(
        payload.get(
            "momentumAuthorityRevokeExits",
            payload.get("momentum_authority_revoke_exits"),
        ),
        default=base.momentum_authority_revoke_exits,
    )
    momentum_authority_latch_once_active = _payload_bool(
        payload.get(
            "momentumAuthorityLatchOnceActive",
            payload.get("momentum_authority_latch_once_active"),
        ),
        default=base.momentum_authority_latch_once_active,
    )
    momentum_authority_min_trust_score = int_from_payload(
        payload,
        "momentumAuthorityMinTrustScore",
        base.momentum_authority_min_trust_score,
        0,
        aliases=("momentum_authority_min_trust_score",),
    )
    momentum_authority_min_source_percent = decimal_from_payload(
        payload,
        "momentumAuthorityMinSourcePercent",
        base.momentum_authority_min_source_percent,
        allow_zero=True,
        aliases=("momentum_authority_min_source_percent",),
    )
    momentum_authority_max_transitions_per_hour = decimal_from_payload(
        payload,
        "momentumAuthorityMaxTransitionsPerHour",
        base.momentum_authority_max_transitions_per_hour,
        aliases=("momentum_authority_max_transitions_per_hour",),
    )
    momentum_authority_reclaim_enabled = _payload_bool(
        payload.get(
            "momentumAuthorityReclaimEnabled",
            payload.get("momentum_authority_reclaim_enabled"),
        ),
        default=base.momentum_authority_reclaim_enabled,
    )
    momentum_authority_reclaim_min_trust_score = int_from_payload(
        payload,
        "momentumAuthorityReclaimMinTrustScore",
        base.momentum_authority_reclaim_min_trust_score,
        0,
        aliases=("momentum_authority_reclaim_min_trust_score",),
    )
    momentum_authority_reclaim_min_source_percent = decimal_from_payload(
        payload,
        "momentumAuthorityReclaimMinSourcePercent",
        base.momentum_authority_reclaim_min_source_percent,
        allow_zero=True,
        aliases=("momentum_authority_reclaim_min_source_percent",),
    )
    momentum_authority_reclaim_max_raw_transition_count = int_from_payload(
        payload,
        "momentumAuthorityReclaimMaxRawTransitionCount",
        base.momentum_authority_reclaim_max_raw_transition_count,
        0,
        aliases=("momentum_authority_reclaim_max_raw_transition_count",),
    )
    momentum_authority_reclaim_max_non_warmup_transition_count = int_from_payload(
        payload,
        "momentumAuthorityReclaimMaxNonWarmupTransitionCount",
        base.momentum_authority_reclaim_max_non_warmup_transition_count,
        0,
        aliases=("momentum_authority_reclaim_max_non_warmup_transition_count",),
    )
    momentum_authority_reclaim_start_minutes = int_from_payload(
        payload,
        "momentumAuthorityReclaimStartMinutes",
        base.momentum_authority_reclaim_start_minutes,
        0,
        aliases=("momentum_authority_reclaim_start_minutes",),
    )
    momentum_authority_reclaim_end_minutes = int_from_payload(
        payload,
        "momentumAuthorityReclaimEndMinutes",
        base.momentum_authority_reclaim_end_minutes,
        momentum_authority_reclaim_start_minutes,
        aliases=("momentum_authority_reclaim_end_minutes",),
    )

    return replace(
        base,
        symbol=symbol,
        dry_run=dry_run,
        poll_seconds=poll_seconds,
        close_liquidate_minutes=close_liquidate_minutes,
        regime_gap_threshold=regime_gap_threshold,
        regime_exit_gap_threshold=regime_exit_gap_threshold,
        chop_entry_discount_percent=chop_entry_discount_percent,
        directional_mode=directional_mode,
        directional_max_extension_percent=directional_max_extension_percent,
        directional_strong_chase_max_extension_percent=(
            directional_strong_chase_max_extension_percent
        ),
        directional_min_strength=directional_min_strength,
        directional_cooldown_minutes=directional_cooldown_minutes,
        chop_permission_mode=chop_permission_mode,
        chop_permission_max_abs_source_percent=(
            chop_permission_max_abs_source_percent
        ),
        inverse_cascade_mode=inverse_cascade_mode,
        inverse_cascade_velocity_window_minutes=(
            inverse_cascade_velocity_window_minutes
        ),
        inverse_cascade_sustain_minutes=inverse_cascade_sustain_minutes,
        inverse_cascade_trail_percent=inverse_cascade_trail_percent,
        inverse_cascade_route_invalidation_grace_minutes=(
            inverse_cascade_route_invalidation_grace_minutes
        ),
        inverse_cascade_proven_mfe_percent=inverse_cascade_proven_mfe_percent,
        inverse_cascade_proven_trail_percent=inverse_cascade_proven_trail_percent,
        inverse_cascade_proven_trail_tighten_mfe_percent=(
            inverse_cascade_proven_trail_tighten_mfe_percent
        ),
        inverse_cascade_proven_route_recovery_min_source_percent=(
            inverse_cascade_proven_route_recovery_min_source_percent
        ),
        adaptive_shadow_enabled=adaptive_shadow_enabled,
        enabled_bots=enabled_bots,
        momentum_authority_required=momentum_authority_required,
        momentum_authority_revoke_exits=momentum_authority_revoke_exits,
        momentum_authority_latch_once_active=momentum_authority_latch_once_active,
        momentum_authority_min_trust_score=momentum_authority_min_trust_score,
        momentum_authority_min_source_percent=momentum_authority_min_source_percent,
        momentum_authority_max_transitions_per_hour=(
            momentum_authority_max_transitions_per_hour
        ),
        momentum_authority_reclaim_enabled=momentum_authority_reclaim_enabled,
        momentum_authority_reclaim_min_trust_score=(
            momentum_authority_reclaim_min_trust_score
        ),
        momentum_authority_reclaim_min_source_percent=(
            momentum_authority_reclaim_min_source_percent
        ),
        momentum_authority_reclaim_max_raw_transition_count=(
            momentum_authority_reclaim_max_raw_transition_count
        ),
        momentum_authority_reclaim_max_non_warmup_transition_count=(
            momentum_authority_reclaim_max_non_warmup_transition_count
        ),
        momentum_authority_reclaim_start_minutes=(
            momentum_authority_reclaim_start_minutes
        ),
        momentum_authority_reclaim_end_minutes=momentum_authority_reclaim_end_minutes,
        position_sizing_mode=position_sizing_mode,
        position_allocation_percent=position_allocation_percent,
        position_notional=decimal_from_payload(
            payload, "positionNotional", base.position_notional
        ),
        trail_percent=decimal_from_payload(payload, "trailPercent", base.trail_percent),
        fast_sma_minutes=fast_sma,
        slow_sma_minutes=slow_sma,
        preset_name=_optional_text(
            payload.get("presetName")
            or payload.get("preset_name")
            or payload.get("name")
        ),
        v9_observer_context=(
            dict(v9_observer_context)
            if isinstance(v9_observer_context, dict)
            else None
        ),
        v10_force_no_authority=_payload_bool(
            payload.get("v10ForceNoAuthority", payload.get("v10_force_no_authority")),
            default=base.v10_force_no_authority,
        ),
    )


def _preset_authority_role_from_payload(item: dict[str, Any]) -> str | None:
    explicit_role = _optional_text(item.get("role"))
    if explicit_role:
        normalized = explicit_role.strip().lower()
        if normalized in {"generalist", "momentum", "inverse"}:
            return normalized
    name = _optional_text(item.get("name") or item.get("preset_name"))
    if not name:
        return None
    lowered = name.lower()
    if "general" in lowered:
        return "generalist"
    if "momentum" in lowered:
        return "momentum"
    if "inverse" in lowered:
        return "inverse"
    return None


def preset_authority_plan_from_payload(
    payload: dict[str, Any],
    base_config: BotConfig,
) -> dict[str, Any] | None:
    mode = str(payload.get("presetAuthorityMode", "OFF")).strip().upper()
    if mode in {"", "OFF", "NONE"}:
        return None
    if mode != PRESET_AUTHORITY_MODE_V6:
        raise BotError("presetAuthorityMode must be OFF or V6_0945.")

    raw_presets = payload.get("presetAuthorityPresets")
    if not isinstance(raw_presets, list):
        raise BotError("v6 preset authority requires saved Lead preset payloads.")

    role_configs: dict[str, BotConfig] = {}
    role_names: dict[str, str] = {}
    for item in raw_presets:
        if not isinstance(item, dict):
            continue
        role = _preset_authority_role_from_payload(item)
        config_payload = item.get("config")
        if role is None or not isinstance(config_payload, dict):
            continue
        merged_payload = {
            **config_payload,
            "dryRun": base_config.dry_run,
            "presetName": (
                _optional_text(item.get("name") or item.get("preset_name"))
                or role.title()
            ),
        }
        role_configs[role] = config_from_payload(merged_payload)
        role_names[role] = (
            _optional_text(item.get("name") or item.get("preset_name"))
            or role.title()
        )

    missing = [
        role
        for role in ("generalist", "momentum", "inverse")
        if role not in role_configs
    ]
    if missing:
        raise BotError(
            "v6 preset authority requires saved Lead presets for: "
            + ", ".join(missing)
        )

    return {
        "mode": PRESET_AUTHORITY_MODE_V6,
        "model": PRESET_AUTHORITY_MODEL_V6,
        "role_configs": role_configs,
        "role_names": role_names,
    }


def _log_date_from_path(path: Path) -> str | None:
    stem = path.stem
    if not stem.startswith("edgewalker-"):
        return None
    return stem[len("edgewalker-"):]


def _most_recent_log_date(
    *,
    market_open_only: bool = False,
    logs_root: Path | None = None,
) -> str | None:
    root = logs_root or LOGS_ROOT
    paths = sorted(root.glob("edgewalker-*.jsonl"), reverse=True)
    for path in paths:
        log_date = _log_date_from_path(path)
        if log_date is None:
            continue
        if market_open_only and not _log_has_market_open(path):
            continue
        return log_date
    return None


def _load_log_records(log_path: Path) -> list[dict[str, Any]]:
    records = []
    for raw in log_path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            records.append(json.loads(raw))
        except json.JSONDecodeError:
            pass
    return records


def _parse_datetime_text(raw: Any, *, default_tz: ZoneInfo | timezone) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=default_tz)
    return parsed


def _log_record_timestamp(record: dict[str, Any]) -> datetime | None:
    timestamp = _parse_datetime_text(record.get("timestamp"), default_tz=timezone.utc)
    if timestamp is not None:
        return timestamp
    created_at = _record_created_at(record)
    if created_at is not None:
        return created_at
    return _parse_datetime_text(record.get("checked_at"), default_tz=NY_TZ)


def _record_active_environment(record: dict[str, Any]) -> str | None:
    config = record.get("config")
    raw = None
    if isinstance(config, dict):
        raw = config.get("active_environment")
    if raw is None:
        raw = record.get("active_environment")
    value = _optional_text(raw)
    if not value:
        return None
    value = value.lower()
    if value not in {"paper", "live", "research"}:
        return None
    return value


def _records_for_export_environment(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    export_environment = next(
        (
            environment
            for record in reversed(records)
            if (environment := _record_active_environment(record))
        ),
        None,
    )
    if not export_environment:
        return records, None

    filtered = [
        record
        for record in records
        if (environment := _record_active_environment(record)) is None
        or environment == export_environment
    ]
    return filtered or records, export_environment


def _records_time_window(
    records: list[dict[str, Any]],
) -> tuple[datetime | None, datetime | None]:
    timestamps = [
        timestamp
        for record in records
        if (timestamp := _log_record_timestamp(record)) is not None
    ]
    if not timestamps:
        return None, None
    return min(timestamps), max(timestamps)


def _lifecycle_records_within_window(
    lifecycle_records: list[dict[str, Any]],
    start: datetime | None,
    end: datetime | None,
) -> list[dict[str, Any]]:
    if start is None or end is None:
        return lifecycle_records
    end_with_grace = end + timedelta(minutes=10)
    filtered = []
    for record in lifecycle_records:
        created_at = _record_created_at(record)
        if created_at is None:
            continue
        if start <= created_at <= end_with_grace:
            filtered.append(record)
    return filtered


def _log_has_market_open(log_path: Path) -> bool:
    return any(bool(record.get("market_open")) for record in _load_log_records(log_path))


def _resolve_1d_log_path(date: str | None) -> tuple[str, Path]:
    if date:
        log_path = LOGS_ROOT / f"edgewalker-{date}.jsonl"
        if not log_path.exists():
            raise BotError(f"No session log found for {date}.")
        return date, log_path

    target_date = _most_recent_log_date(market_open_only=True)
    if target_date is None:
        target_date = _most_recent_log_date()
    if target_date is None:
        raise BotError("No session logs found.")
    return target_date, LOGS_ROOT / f"edgewalker-{target_date}.jsonl"


def _to_ny_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(NY_TZ).strftime("%I:%M %p")
    except (ValueError, AttributeError):
        return ts


def _record_time_text(record: dict[str, Any]) -> str:
    created_at = _record_created_at(record)
    if created_at is not None:
        return _to_ny_time(created_at.isoformat())
    return _to_ny_time(_optional_text(record.get("created_at")) or "")


def _record_order_id(record: dict[str, Any]) -> str | None:
    order_id = _optional_text(record.get("order_id"))
    if order_id:
        return order_id
    order = record.get("order")
    if isinstance(order, dict):
        return _optional_text(order.get("id"))
    return None


def _record_order_value(record: dict[str, Any], key: str) -> str | None:
    value = _optional_text(record.get(key))
    if value is not None:
        return value
    order = record.get("order")
    if isinstance(order, dict):
        return _optional_text(order.get(key))
    return None


def _lifecycle_records_for_date(
    lifecycle_records: list[dict[str, Any]],
    log_date: str,
) -> list[dict[str, Any]]:
    records = []
    for record in lifecycle_records:
        created_at = _record_created_at(record)
        if created_at is None or _ny_date_text(created_at) != log_date:
            continue
        records.append(record)
    return records


def _extract_lifecycle_trade_actions(
    lifecycle_records: list[dict[str, Any]],
    log_date: str,
) -> list[dict[str, Any]]:
    submitted = [
        record
        for record in _lifecycle_records_for_date(lifecycle_records, log_date)
        if record.get("event_type") == LIFECYCLE_ORDER_SUBMITTED
    ]
    source_records = submitted
    if not source_records:
        source_records = [
            record
            for record in _lifecycle_records_for_date(lifecycle_records, log_date)
            if record.get("event_type") in {LIFECYCLE_PARTIAL_FILL, LIFECYCLE_FULL_FILL}
        ]

    trades: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str, str, str]] = set()
    for record in source_records:
        side = str(record.get("side") or "").lower()
        if side not in {"buy", "sell"}:
            continue
        symbol = _optional_text(record.get("symbol")) or _record_order_value(
            record,
            "symbol",
        )
        action = "BUY" if side == "buy" else "SELL"
        order_id = _record_order_id(record)
        reason = _optional_text(record.get("reason"))
        key = (
            order_id,
            action,
            _optional_text(record.get("created_at")) or "",
            symbol or "",
        )
        if key in seen:
            continue
        seen.add(key)
        trades.append(
            {
                "at": _record_time_text(record),
                "bot": _optional_text(record.get("bot")),
                "action": action,
                "symbol": symbol,
                "price": _record_order_value(record, "filled_avg_price")
                or _record_order_value(record, "price")
                or _optional_text(record.get("current_price")),
                "notional": _record_order_value(record, "notional"),
                "qty": _record_order_value(record, "qty")
                or _record_order_value(record, "filled_qty")
                or _record_order_value(record, "fill_delta_qty"),
                "reason": reason,
            }
        )
    return trades


def _cycle_position_owner(record: dict[str, Any]) -> str | None:
    owner = _optional_text(record.get("position_owner"))
    if owner:
        return owner
    for line in record.get("console_lines") or []:
        if not isinstance(line, str) or "owner=" not in line:
            continue
        owner_text = line.split("owner=", 1)[1].split()[0].strip(" ;,.")
        if owner_text:
            return owner_text
    return _optional_text(record.get("active_bot"))


def _extract_cycle_trade_actions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trades = []
    exit_actions = {
        "trailing_stop_sell",
        "market_close_liquidation",
        "chop_exit_reclaim_slow_sma",
        "close_stale_position_no_same_cycle_reversal",
        "close_route_invalidated_position_no_same_cycle_reversal",
    }
    for record in records:
        action = record.get("action_taken")
        if action == "market_buy":
            trades.append(
                {
                    "at": _to_ny_time(record.get("timestamp", "")),
                    "bot": record.get("active_bot"),
                    "action": "BUY",
                    "symbol": record.get("routed_symbol"),
                    "price": record.get("source_price"),
                    "notional": record.get("effective_position_notional")
                    or record.get("config", {}).get("position_notional"),
                    "reason": record.get("entry_reason"),
                }
            )
        elif action in exit_actions:
            trades.append(
                {
                    "at": _to_ny_time(record.get("timestamp", "")),
                    "bot": _cycle_position_owner(record),
                    "action": "SELL",
                    "reason": action,
                    "symbol": record.get("position_symbol") or record.get("routed_symbol"),
                    "price": record.get("position_current_price")
                    or record.get("source_price"),
                    "qty": record.get("position_qty"),
                }
            )
    return trades


def _increment_count(counts: dict[str, int], key: Any) -> None:
    text = _optional_text(key) or "UNKNOWN"
    counts[text] = counts.get(text, 0) + 1


def _counts_payload(counts: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {"name": key, "count": count}
        for key, count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _float_from_value(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bar_float(bar: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _float_from_value(bar.get(key))
        if value is not None:
            return value
    return None


def _runtime_source_price_path(bars: list[dict[str, Any]]) -> dict[str, Any]:
    open_price: float | None = None
    current_price: float | None = None
    lows: list[float] = []
    highs: list[float] = []

    for bar in bars:
        if not isinstance(bar, dict):
            continue
        bar_open = _bar_float(bar, "o", "open", "c", "close")
        bar_high = _bar_float(bar, "h", "high", "c", "close", "o", "open")
        bar_low = _bar_float(bar, "l", "low", "c", "close", "o", "open")
        bar_close = _bar_float(bar, "c", "close", "o", "open")
        if open_price is None and bar_open is not None:
            open_price = bar_open
        if bar_high is not None:
            highs.append(bar_high)
        if bar_low is not None:
            lows.append(bar_low)
        if bar_close is not None:
            current_price = bar_close

    if open_price is None or current_price is None or open_price == 0:
        return {
            "source_open_to_current_percent": None,
            "source_max_drawdown_from_open_percent": None,
            "source_max_runup_from_open_percent": None,
        }

    low_price = min(lows) if lows else current_price
    high_price = max(highs) if highs else current_price
    return {
        "source_open_to_current_percent": round(
            (current_price - open_price) / open_price * 100,
            2,
        ),
        "source_max_drawdown_from_open_percent": round(
            (low_price - open_price) / open_price * 100,
            2,
        ),
        "source_max_runup_from_open_percent": round(
            (high_price - open_price) / open_price * 100,
            2,
        ),
    }


def _entry_block_reason_from_line(line: str) -> str | None:
    if "[ENTRY]" not in line or "reason=" not in line:
        return None
    if "BLOCKED" not in line and "entry_signal=False" not in line:
        return None
    match = re.search(r"\breason=([A-Za-z0-9_]+)", line)
    if match:
        return match.group(1)
    return None


def _record_has_stale_bars(record: dict[str, Any]) -> bool:
    if record.get("data_status") == "STALE":
        return True
    if record.get("action_taken") in {
        "wait_stale_market_data",
        "manage_open_position_stale_bars",
    }:
        return True
    return any(
        isinstance(line, str) and "[DATA] HEALTH bars=STALE" in line
        for line in record.get("console_lines") or []
    )


def _session_metrics_summary(
    records: list[dict[str, Any]],
    lifecycle_records: list[dict[str, Any]],
    log_date: str,
) -> dict[str, Any]:
    action_counts: dict[str, int] = {}
    adaptive_counts: dict[str, int] = {}
    entry_block_counts: dict[str, int] = {}
    trend_label_counts: dict[str, int] = {}
    trust_scores: list[float] = []
    trust_ages: list[float] = []
    trust_flips: list[float] = []
    stale_bar_cycles = 0
    backfill_repair_cycles = 0
    backfill_unchanged_cycles = 0
    backfill_error_cycles = 0

    for record in records:
        _increment_count(action_counts, record.get("action_taken"))
        posture = _optional_text(record.get("adaptive_posture"))
        if posture:
            _increment_count(adaptive_counts, posture)

        if _record_has_stale_bars(record):
            stale_bar_cycles += 1

        lines = record.get("console_lines") or []
        if any(
            isinstance(line, str) and "[DATA] BAR BACKFILL repaired" in line
            for line in lines
        ):
            backfill_repair_cycles += 1
        if any(
            isinstance(line, str) and "[DATA] BAR BACKFILL unchanged" in line
            for line in lines
        ):
            backfill_unchanged_cycles += 1
        if any(
            isinstance(line, str) and "[DATA] BAR BACKFILL error" in line
            for line in lines
        ):
            backfill_error_cycles += 1

        for line in lines:
            if not isinstance(line, str):
                continue
            reason = _entry_block_reason_from_line(line)
            if reason:
                _increment_count(entry_block_counts, reason)

        trend_trust = record.get("trend_trust")
        if isinstance(trend_trust, dict):
            score = _float_from_value(trend_trust.get("score"))
            if score is not None:
                trust_scores.append(score)
            age = _float_from_value(trend_trust.get("regime_age_minutes"))
            if age is not None:
                trust_ages.append(age)
            flips = _float_from_value(trend_trust.get("recent_flip_count_60m"))
            if flips is not None:
                trust_flips.append(flips)
            label = _optional_text(trend_trust.get("label"))
            if label:
                _increment_count(trend_label_counts, label)

    lifecycle_for_date = _lifecycle_records_for_date(lifecycle_records, log_date)
    submitted_sell_records = [
        record
        for record in lifecycle_for_date
        if record.get("event_type") == LIFECYCLE_ORDER_SUBMITTED
        and str(record.get("side") or "").lower() == "sell"
    ]
    sell_source = submitted_sell_records or [
        record
        for record in lifecycle_for_date
        if record.get("event_type") in {LIFECYCLE_PARTIAL_FILL, LIFECYCLE_FULL_FILL}
        and str(record.get("side") or "").lower() == "sell"
    ]
    exit_reason_counts: dict[str, int] = {}
    route_invalidation_scaffold_count = 0
    for record in sell_source:
        reason = _optional_text(record.get("reason")) or "UNKNOWN"
        _increment_count(exit_reason_counts, reason)
        context = record.get("lifecycle_context")
        if (
            reason == "route_invalidated_exit"
            and isinstance(context, dict)
            and context.get("kind") == "route_invalidation_exit"
        ):
            route_invalidation_scaffold_count += 1

    def average(values: list[float]) -> str | None:
        if not values:
            return None
        return f"{sum(values) / len(values):.1f}"

    return {
        "regime_transition_count": sum(
            1 for record in records if record.get("regime_transition")
        ),
        "stale_bar_cycles": stale_bar_cycles,
        "backfill_repair_cycles": backfill_repair_cycles,
        "backfill_unchanged_cycles": backfill_unchanged_cycles,
        "backfill_error_cycles": backfill_error_cycles,
        "action_counts": _counts_payload(action_counts),
        "adaptive_posture_counts": _counts_payload(adaptive_counts),
        "top_entry_blocks": _counts_payload(entry_block_counts)[:6],
        "exit_reason_counts": _counts_payload(exit_reason_counts),
        "route_invalidation_exit_count": exit_reason_counts.get(
            "route_invalidated_exit",
            0,
        ),
        "route_invalidation_scaffold_count": route_invalidation_scaffold_count,
        "trailing_stop_exit_count": exit_reason_counts.get(
            "trailing_stop_breached",
            0,
        ),
        "trend_trust": {
            "observations": len(trust_scores),
            "average_score": average(trust_scores),
            "average_regime_age_minutes": average(trust_ages),
            "max_recent_flips_60m": max(trust_flips) if trust_flips else None,
            "label_counts": _counts_payload(trend_label_counts),
        },
    }


def _decimal_from_value(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _rounded_number(value: Any, places: str = "0.01") -> float:
    decimal_value = _decimal_from_value(value) or Decimal("0")
    return float(decimal_value.quantize(Decimal(places)))


def _realized_trades_for_date(
    lifecycle_records: list[dict[str, Any]],
    log_date: str,
) -> list[dict[str, Any]]:
    return analyze_lifecycle_trades(
        lifecycle_records,
        log_date,
        session_tz=NY_TZ,
    )["realized_trades"]


def _bot_pl_map(performance: dict[str, Any] | None) -> dict[str, Decimal]:
    bot_pl = {bot: Decimal("0") for bot in BOT_PERFORMANCE_ORDER}
    if not isinstance(performance, dict):
        return bot_pl
    items = performance.get("bot_performance")
    if not isinstance(items, list):
        return bot_pl
    for item in items:
        if not isinstance(item, dict):
            continue
        bot = _optional_text(item.get("bot"))
        if not bot:
            continue
        bot_pl[bot] = _decimal_from_value(item.get("realized_pl")) or Decimal("0")
    return bot_pl


def _top_pl_bot(bot_pl: dict[str, Decimal]) -> str:
    active = [(bot, value) for bot, value in bot_pl.items() if value != 0]
    if not active:
        return ""
    return max(active, key=lambda item: item[1])[0]


def _bottom_pl_bot(bot_pl: dict[str, Decimal]) -> str:
    losses = [(bot, value) for bot, value in bot_pl.items() if value < 0]
    if not losses:
        return ""
    return min(losses, key=lambda item: item[1])[0]


def _quality_number(value: Any) -> float | str:
    if value in (None, ""):
        return ""
    return _rounded_number(value)


def _bot_performance_by_name(
    performance: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(performance, dict):
        return {}
    items = performance.get("bot_performance")
    if not isinstance(items, list):
        return {}
    return {
        bot: item
        for item in items
        if isinstance(item, dict)
        and (bot := _optional_text(item.get("bot"))) in BOT_PERFORMANCE_ORDER
    }


def _trade_quality_source(trades: list[dict[str, Any]]) -> str:
    sources = sorted(
        {
            source
            for trade in trades
            if (source := _optional_text(trade.get("mfe_mae_source")))
        }
    )
    return ",".join(sources)


def _trade_quality_row_values(
    performance: dict[str, Any],
    realized_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    session_quality = performance.get("trade_quality")
    if not isinstance(session_quality, dict):
        session_quality = trade_quality_averages(realized_trades)
    by_bot = _bot_performance_by_name(performance)
    inverse_report = performance.get("inversebot_archaeology")
    if not isinstance(inverse_report, dict):
        inverse_report = bot_archaeology_report(realized_trades, INVERSE_BOT)

    row = {
        "session_avg_mfe_percent": _quality_number(
            session_quality.get("avg_mfe_percent")
        ),
        "session_avg_mae_percent": _quality_number(
            session_quality.get("avg_mae_percent")
        ),
        "session_avg_capture_ratio_percent": _quality_number(
            session_quality.get("avg_capture_ratio_percent")
        ),
        "session_avg_hold_seconds": _quality_number(
            session_quality.get("avg_hold_seconds")
        ),
        "inverse_near_zero_mfe_count": int(
            inverse_report.get("near_zero_mfe_count") or 0
        ),
        "inverse_meaningful_mfe_low_capture_count": int(
            inverse_report.get("meaningful_mfe_low_capture_count") or 0
        ),
        "inverse_adverse_gt_favorable_count": int(
            inverse_report.get("larger_adverse_than_favorable_count") or 0
        ),
        "mfe_mae_source": _trade_quality_source(realized_trades),
    }
    for bot, prefix in (
        (MOMENTUM_BOT, "momentum"),
        (CHOP_BOT, "chop"),
        (INVERSE_BOT, "inverse"),
    ):
        quality = by_bot.get(bot) or {}
        row[f"{prefix}_avg_mfe_percent"] = _quality_number(
            quality.get("avg_mfe_percent")
        )
        row[f"{prefix}_avg_mae_percent"] = _quality_number(
            quality.get("avg_mae_percent")
        )
        row[f"{prefix}_avg_capture_ratio_percent"] = _quality_number(
            quality.get("avg_capture_ratio_percent")
        )
        row[f"{prefix}_avg_hold_seconds"] = _quality_number(
            quality.get("avg_hold_seconds")
        )
    return row


def _narrative_money(value: Any) -> str:
    decimal_value = _decimal_from_value(value) or Decimal("0")
    sign = "-" if decimal_value < 0 else ""
    return f"{sign}${abs(decimal_value):,.2f}"


def _narrative_percent(value: Any) -> str:
    decimal_value = _decimal_from_value(value) or Decimal("0")
    return f"{decimal_value.quantize(Decimal('0.01'))}%"


def _ledger_bot_performance_sections(
    performance: dict[str, Any] | None,
) -> dict[str, str]:
    if not isinstance(performance, dict):
        return {}

    items = performance.get("bot_performance")
    if not isinstance(items, list):
        return {}

    by_bot = {
        _optional_text(item.get("bot")): item
        for item in items
        if isinstance(item, dict) and _optional_text(item.get("bot"))
    }
    sections: dict[str, str] = {}
    for bot in BOT_PERFORMANCE_ORDER:
        item = by_bot.get(bot)
        if not item:
            sections[bot] = "No closed trades; realized P/L $0.00."
            continue

        trade_count = int(item.get("trade_count") or 0)
        realized_pl = _narrative_money(item.get("realized_pl"))
        if trade_count <= 0:
            sections[bot] = f"No closed trades; realized P/L {realized_pl}."
            continue

        wins = int(item.get("wins") or 0)
        losses = int(item.get("losses") or 0)
        win_rate = _narrative_percent(item.get("win_rate_percent"))
        trade_word = "trade" if trade_count == 1 else "trades"
        last_trade_pl = _decimal_from_value(item.get("last_trade_realized_pl"))
        last_trade_symbol = _optional_text(item.get("last_trade_symbol"))
        last_trade = ""
        if last_trade_pl is not None and last_trade_symbol:
            last_trade = (
                f" Last closed trade: {_narrative_money(last_trade_pl)} "
                f"{last_trade_symbol}."
            )

        sections[bot] = (
            f"{trade_count} closed {trade_word}, {wins}W/{losses}L, "
            f"{win_rate} win rate, realized P/L {realized_pl}."
            f"{last_trade}"
        )

    return sections


def _ground_narrative_sections(
    sections: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    grounded = dict(sections)
    bot_sections = _ledger_bot_performance_sections(context.get("performance"))
    if bot_sections:
        grounded["bot_performance"] = bot_sections
    return grounded


def _narrative_for_spreadsheet(summary: dict[str, Any]) -> str:
    sections = summary.get("narrative")
    if not isinstance(sections, dict):
        return _narrative_text(summary.get("summary"))

    parts: list[str] = []
    display_date = _narrative_text(summary.get("display_date") or summary.get("date"))
    cycles = summary.get("cycle_count")
    if display_date:
        parts.append(
            f"{display_date} · {cycles or '?'} cycles"
            if cycles is not None
            else display_date
        )

    if sections.get("tldr"):
        parts.append(f"TL;DR: {_narrative_text(sections.get('tldr'))}")
    if sections.get("highlight"):
        parts.append(f"Highlight: {_narrative_text(sections.get('highlight'))}")

    bot_performance = sections.get("bot_performance")
    if isinstance(bot_performance, dict) and bot_performance:
        bot_lines = [
            f"{bot}: {_narrative_text(text)}"
            for bot, text in bot_performance.items()
            if _narrative_text(text)
        ]
        if bot_lines:
            parts.append("Bot Performance:\n" + "\n".join(bot_lines))

    section_labels = (
        ("Market Conditions", "market_conditions"),
        ("Operational Issues", "operational_issues"),
        ("Analysis", "analysis"),
        ("Bottom Line", "bottom_line"),
    )
    for label, key in section_labels:
        text = _narrative_text(sections.get(key))
        if text:
            parts.append(f"{label}: {text}")
    return "\n\n".join(parts)


def _config_snapshot_text(
    config: dict[str, Any],
    key: str,
    default: str = "",
) -> str:
    return _optional_text(config.get(key)) or default


def _config_snapshot_number(
    config: dict[str, Any],
    key: str,
    default: Any = 0,
) -> float:
    return _rounded_number(config.get(key) if key in config else default)


def _config_snapshot_int(
    config: dict[str, Any],
    key: str,
    default: int = 0,
) -> int:
    value = config.get(key) if key in config else default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _config_enabled_bots(config: dict[str, Any]) -> list[str]:
    raw = config.get("enabled_bots")
    if isinstance(raw, list):
        return [_optional_text(bot) for bot in raw if _optional_text(bot)]
    if isinstance(raw, str):
        return [bot.strip() for bot in raw.split(",") if bot.strip()]
    return []


def _enabled_specialists_text(enabled_bots: list[str]) -> str:
    return " | ".join(
        SPECIALIST_DISPLAY_NAMES.get(bot, bot)
        for bot in enabled_bots
        if bot in BOT_PERFORMANCE_ORDER
    )


def _build_profile(config: dict[str, Any]) -> str:
    enabled_bots = _config_enabled_bots(config)
    if tuple(enabled_bots) == tuple(EDGEWALKER_BOTS) or set(enabled_bots) == set(
        EDGEWALKER_BOTS
    ):
        return LOCKED_FULL_ROSTER_PROFILE
    return "CUSTOM"


def _effective_position_notional(
    config: dict[str, Any],
    account_value: Decimal,
) -> float:
    sizing_mode = _config_snapshot_text(config, "position_sizing_mode")
    if sizing_mode == "DYNAMIC":
        allocation = _decimal_from_value(config.get("position_allocation_percent"))
        if allocation is None:
            return 0.0
        return _rounded_number(account_value * allocation / Decimal("100"))
    return _config_snapshot_number(config, "position_notional")


def _bot_trade_count(performance: dict[str, Any], bot: str) -> int:
    item = _bot_performance_by_name(performance).get(bot) or {}
    return int(item.get("trade_count") or 0)


def _record_contains_text(record: dict[str, Any], needle: str) -> bool:
    try:
        return needle in json.dumps(record, default=str)
    except (TypeError, ValueError):
        return False


def _prior_close_status(record: dict[str, Any]) -> str:
    if _record_contains_text(record, "source_prior_close_unavailable"):
        return "MISSING"
    return "GUARDED"


def _primary_no_trade_reason(record: dict[str, Any]) -> str:
    if record.get("position_symbol"):
        return ""
    action = _optional_text(record.get("action_taken"))
    if action and action != "no_entry_signal":
        return action
    for context_key in ("v9_momentum_context", "v10_no_authority_context"):
        context = record.get(context_key)
        if isinstance(context, dict):
            reason = _optional_text(
                context.get("invalidation_reason") or context.get("activation_reason")
            )
            if reason:
                return reason
    for line in record.get("console_lines") or []:
        match = re.search(r"reason=([a-zA-Z0-9_,-]+)", str(line))
        if match:
            return match.group(1)
    return action or ""


def _route_reason_summary(record: dict[str, Any]) -> str:
    parts = []
    active_bot = _optional_text(record.get("active_bot"))
    routed_symbol = _optional_text(record.get("routed_symbol"))
    action = _optional_text(record.get("action_taken"))
    reason = _primary_no_trade_reason(record)
    if active_bot:
        parts.append(f"bot={active_bot}")
    if routed_symbol:
        parts.append(f"route={routed_symbol}")
    if action:
        parts.append(f"action={action}")
    if reason and reason != action:
        parts.append(f"reason={reason}")
    return "; ".join(parts)


def build_operator_spreadsheet_daily_row(
    date: str | None = None,
    *,
    operator_notes: str = "",
    include_daily_narrative: bool = False,
) -> dict[str, Any]:
    target_date, log_path = _resolve_1d_log_path(date)
    records = _load_log_records(log_path)
    if not records:
        raise BotError(f"Session log for {target_date} is empty.")
    export_records, export_environment = _records_for_export_environment(records)
    export_start, export_end = _records_time_window(export_records)

    lifecycle_records = _lifecycle_records_within_window(
        LifecycleLedger().read_all(),
        export_start,
        export_end,
    )
    performance = lifecycle_performance_summary(
        lifecycle_records,
        datetime.fromisoformat(target_date).replace(tzinfo=NY_TZ),
    )
    session_metrics = _session_metrics_summary(
        export_records,
        lifecycle_records,
        target_date,
    )
    realized_trades = _realized_trades_for_date(lifecycle_records, target_date)

    first = export_records[0]
    last = export_records[-1]
    last_config = last.get("config") if isinstance(last.get("config"), dict) else {}
    enabled_bots = _config_enabled_bots(last_config)
    starting_account = _decimal_from_value(
        first.get("portfolio_value") or first.get("account_value")
    ) or Decimal("0")
    ending_account = _decimal_from_value(
        last.get("portfolio_value") or last.get("account_value")
    ) or Decimal("0")
    realized_pl = _decimal_from_value(performance.get("session_realized_pl")) or Decimal(
        "0"
    )
    account_change_percent = (
        realized_pl / starting_account * Decimal("100")
        if starting_account > 0
        else Decimal("0")
    )
    if realized_pl > 0:
        result_status = "GREEN"
    elif realized_pl < 0:
        result_status = "RED"
    else:
        result_status = "FLAT"
    trade_count = int(performance.get("session_trade_count") or 0)
    wins = int(performance.get("session_wins") or 0)
    losses = int(performance.get("session_losses") or 0)
    win_rate = (
        Decimal(wins) / Decimal(trade_count) * Decimal("100")
        if trade_count > 0
        else Decimal("0")
    )

    bot_pl = _bot_pl_map(performance)
    exit_reason_counts: dict[str, int] = {}
    exit_reason_pl: dict[str, Decimal] = {}
    for trade in realized_trades:
        reason = _optional_text(trade.get("exit_reason")) or "UNKNOWN"
        _increment_count(exit_reason_counts, reason)
        exit_reason_pl[reason] = exit_reason_pl.get(reason, Decimal("0")) + (
            _decimal_from_value(trade.get("realized_pl")) or Decimal("0")
        )

    daily_narrative = ""
    narrative_error = None
    if include_daily_narrative:
        try:
            daily_narrative = _narrative_for_spreadsheet(
                generate_session_summary(target_date, "1D")
            )
        except BotError as exc:
            narrative_error = str(exc)

    row = {
        "date": target_date,
        "mode": last.get("config", {}).get("directional_mode")
        or last.get("directional_mode")
        or "",
        "build_profile": _build_profile(last_config),
        "enabled_specialists": _enabled_specialists_text(enabled_bots),
        "starting_account_value": _rounded_number(starting_account),
        "ending_account_value": _rounded_number(ending_account),
        "realized_pl_dollars": _rounded_number(realized_pl),
        "account_change_percent": _rounded_number(account_change_percent),
        "account_result_status": result_status,
        "closed_trades": trade_count,
        "wins": wins,
        "losses": losses,
        "win_rate": _rounded_number(win_rate),
        "momentum_pl": _rounded_number(bot_pl.get(MOMENTUM_BOT)),
        "chop_pl": _rounded_number(bot_pl.get(CHOP_BOT)),
        "inverse_pl": _rounded_number(bot_pl.get(INVERSE_BOT)),
        "momentum_trades": _bot_trade_count(performance, MOMENTUM_BOT),
        "chop_trades": _bot_trade_count(performance, CHOP_BOT),
        "inverse_trades": _bot_trade_count(performance, INVERSE_BOT),
        "top_pl_bot": _top_pl_bot(bot_pl),
        "bottom_pl_bot": _bottom_pl_bot(bot_pl),
        "regime_transitions": int(
            session_metrics.get("regime_transition_count") or 0
        ),
        "cycles": len(export_records),
        "stale_cycles": int(session_metrics.get("stale_bar_cycles") or 0),
        "stream_error_cycles": sum(
            1
            for record in export_records
            if record.get("data_status") == "ERROR" or record.get("stream_error")
        ),
        "session_trend_trust_avg": _rounded_number(
            session_metrics.get("trend_trust", {}).get("average_score")
        ),
        "route_invalidation_exits": int(
            exit_reason_counts.get("route_invalidated_exit", 0)
        ),
        "route_invalidation_pl": _rounded_number(
            exit_reason_pl.get("route_invalidated_exit")
        ),
        "trailing_stop_exits": int(
            exit_reason_counts.get("trailing_stop_breached", 0)
        ),
        "trailing_stop_pl": _rounded_number(
            exit_reason_pl.get("trailing_stop_breached")
        ),
        "market_close_exits": int(
            exit_reason_counts.get("market_close_liquidation", 0)
        ),
        "market_close_pl": _rounded_number(
            exit_reason_pl.get("market_close_liquidation")
        ),
        **_trade_quality_row_values(performance, realized_trades),
        "reconciliation_confidence": performance.get("reconciliation_confidence")
        or "",
        "config_version": _config_snapshot_text(
            last_config,
            "config_version",
            _env_first(_read_env_values(), "OPERATOR_CONFIG_VERSION", default="v1"),
        ),
        "strategy_version": _config_snapshot_text(
            last_config,
            "strategy_version",
            _env_first(_read_env_values(), "OPERATOR_STRATEGY_VERSION", default="v1"),
        ),
        "symbol_primary": _config_snapshot_text(last_config, "symbol", SOXL),
        "symbol_inverse": SOXS,
        "position_sizing_mode": _config_snapshot_text(
            last_config,
            "position_sizing_mode",
        ),
        "position_notional": _config_snapshot_number(
            last_config,
            "position_notional",
        ),
        "position_allocation_percent": _config_snapshot_number(
            last_config,
            "position_allocation_percent",
        ),
        "effective_position_notional": _effective_position_notional(
            last_config,
            starting_account,
        ),
        "poll_seconds": _config_snapshot_int(last_config, "poll_seconds"),
        "trail_percent": _config_snapshot_number(last_config, "trail_percent"),
        "fast_sma_minutes": _config_snapshot_int(last_config, "fast_sma_minutes"),
        "slow_sma_minutes": _config_snapshot_int(last_config, "slow_sma_minutes"),
        "regime_gap_percent": _config_snapshot_number(
            last_config,
            "regime_gap_threshold",
        ),
        "regime_exit_gap_percent": _config_snapshot_number(
            last_config,
            "regime_exit_gap_threshold",
        ),
        "chop_discount_percent": _config_snapshot_number(
            last_config,
            "chop_entry_discount_percent",
        ),
        "close_liquidate_minutes": _config_snapshot_int(
            last_config,
            "close_liquidate_minutes",
        ),
        "directional_max_extension_percent": _config_snapshot_number(
            last_config,
            "directional_max_extension_percent",
        ),
        "directional_strong_chase_max_extension_percent": _config_snapshot_number(
            last_config,
            "directional_strong_chase_max_extension_percent",
        ),
        "directional_min_strength": _config_snapshot_text(
            last_config,
            "directional_min_strength",
        ),
        "directional_cooldown_minutes": _config_snapshot_int(
            last_config,
            "directional_cooldown_minutes",
        ),
        "chop_permission_mode": _config_snapshot_text(
            last_config,
            "chop_permission_mode",
        ),
        "chop_permission_max_abs_source_percent": _config_snapshot_number(
            last_config,
            "chop_permission_max_abs_source_percent",
        ),
        "adaptive_shadow_enabled": bool(
            last_config.get("adaptive_shadow_enabled", False)
        ),
        "enabled_bots": ",".join(enabled_bots),
        "momentum_authority_required": bool(
            last_config.get("momentum_authority_required", False)
        ),
        "momentum_authority_revoke_exits": bool(
            last_config.get("momentum_authority_revoke_exits", False)
        ),
        "momentum_authority_latch_once_active": bool(
            last_config.get("momentum_authority_latch_once_active", False)
        ),
        "momentum_authority_min_trust_score": _config_snapshot_int(
            last_config,
            "momentum_authority_min_trust_score",
        ),
        "momentum_authority_min_source_percent": _config_snapshot_number(
            last_config,
            "momentum_authority_min_source_percent",
        ),
        "momentum_authority_max_transitions_per_hour": _config_snapshot_number(
            last_config,
            "momentum_authority_max_transitions_per_hour",
        ),
        "momentum_authority_reclaim_enabled": bool(
            last_config.get("momentum_authority_reclaim_enabled", False)
        ),
        "momentum_authority_reclaim_min_trust_score": _config_snapshot_int(
            last_config,
            "momentum_authority_reclaim_min_trust_score",
        ),
        "momentum_authority_reclaim_min_source_percent": _config_snapshot_number(
            last_config,
            "momentum_authority_reclaim_min_source_percent",
        ),
        "momentum_authority_reclaim_max_raw_transition_count": _config_snapshot_int(
            last_config,
            "momentum_authority_reclaim_max_raw_transition_count",
        ),
        "momentum_authority_reclaim_max_non_warmup_transition_count": (
            _config_snapshot_int(
                last_config,
                "momentum_authority_reclaim_max_non_warmup_transition_count",
            )
        ),
        "momentum_authority_reclaim_start_minutes": _config_snapshot_int(
            last_config,
            "momentum_authority_reclaim_start_minutes",
        ),
        "momentum_authority_reclaim_end_minutes": _config_snapshot_int(
            last_config,
            "momentum_authority_reclaim_end_minutes",
        ),
        "v10_force_no_authority": bool(
            last_config.get("v10_force_no_authority", False)
        ),
        "dry_run": bool(last_config.get("dry_run", False)),
        "order_mode": _config_snapshot_text(
            last_config,
            "active_environment",
            export_environment or current_alpaca_environment(),
        ),
        "active_environment": _config_snapshot_text(
            last_config,
            "active_environment",
            export_environment or current_alpaca_environment(),
        ),
        "market_environment": UNKNOWN_MARKET_ENVIRONMENT,
        "primary_no_trade_reason": _primary_no_trade_reason(last),
        "route_reason_summary": _route_reason_summary(last),
        "prior_close_status": _prior_close_status(last),
        "data_feed": _config_snapshot_text(last_config, "data_feed"),
        "operator_notes": operator_notes,
        "daily_narrative": daily_narrative,
    }

    return {
        "date": target_date,
        "columns": OPERATOR_SPREADSHEET_COLUMNS,
        "row": {column: row.get(column, "") for column in OPERATOR_SPREADSHEET_COLUMNS},
        "values": [row.get(column, "") for column in OPERATOR_SPREADSHEET_COLUMNS],
        "narrative_error": narrative_error,
    }


def post_operator_spreadsheet_daily_row(payload: dict[str, Any]) -> dict[str, Any]:
    settings = operator_spreadsheet_settings()
    endpoint_url = _optional_text(
        payload.get("post_endpoint_url")
        or payload.get("postEndpointUrl")
        or settings.get("post_endpoint_url")
    )
    if not endpoint_url:
        raise BotError("Add an Operator Spreadsheet post endpoint URL first.")

    include_daily_narrative = _payload_bool(
        payload.get("include_daily_narrative")
        if payload.get("include_daily_narrative") is not None
        else payload.get("includeDailyNarrative"),
        default=bool(settings.get("include_daily_narrative")),
    )
    row_payload = build_operator_spreadsheet_daily_row(
        _optional_text(payload.get("date")),
        operator_notes=_optional_text(payload.get("operator_notes")) or "",
        include_daily_narrative=include_daily_narrative,
    )

    body = json.dumps(row_payload["row"]).encode("utf-8")
    request = urllib.request.Request(
        endpoint_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            status_code = response.status
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise BotError(
            f"Spreadsheet post failed with HTTP {exc.code}: {response_body[:240]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise BotError(f"Spreadsheet post failed: {exc.reason}") from exc

    try:
        parsed_response = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise BotError(
            "Spreadsheet endpoint did not return JSON. "
            f"Response started with: {response_body[:240]}"
        ) from exc

    if isinstance(parsed_response, dict) and parsed_response.get("status") == "error":
        raise BotError(
            f"Spreadsheet endpoint error: {parsed_response.get('message') or 'unknown'}"
        )

    return {
        "status": "posted",
        "http_status": status_code,
        "endpoint_response": parsed_response,
        "row": row_payload["row"],
        "columns": row_payload["columns"],
        "date": row_payload["date"],
        "narrative_error": row_payload.get("narrative_error"),
    }


def _post_json_to_spreadsheet_endpoint(
    endpoint_url: str,
    row: dict[str, Any],
) -> tuple[int, Any]:
    body = json.dumps(row).encode("utf-8")
    request = urllib.request.Request(
        endpoint_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            status_code = response.status
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise BotError(
            f"Spreadsheet post failed with HTTP {exc.code}: {response_body[:240]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise BotError(f"Spreadsheet post failed: {exc.reason}") from exc

    try:
        parsed_response = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise BotError(
            "Spreadsheet endpoint did not return JSON. "
            f"Response started with: {response_body[:240]}"
        ) from exc

    if isinstance(parsed_response, dict) and parsed_response.get("status") == "error":
        raise BotError(
            f"Spreadsheet endpoint error: {parsed_response.get('message') or 'unknown'}"
        )

    return status_code, parsed_response


def config_from_research_payload(payload: dict[str, Any]) -> BotConfig:
    config_payload = dict(payload)
    config_payload["dryRun"] = True
    config = config_from_payload(config_payload)
    data_feed = str(
        payload.get("data_feed") or payload.get("dataFeed") or config.data_feed
    ).strip()
    if not data_feed:
        data_feed = "iex"
    return replace(
        config,
        dry_run=False,
        data_feed=data_feed,
        trading_base_url="research://simulated-broker",
        preset_name=_optional_text(
            payload.get("preset_name")
            or payload.get("presetName")
            or payload.get("name")
        ),
    )


def research_request_from_payload(payload: dict[str, Any], config: BotConfig) -> ResearchRunRequest:
    raw_date = _optional_text(
        payload.get("backtest_date") or payload.get("backtestDate") or payload.get("date")
    )
    if not raw_date:
        raise BotError("Choose a backtest date first.")
    fill_model = _optional_text(
        payload.get("fill_model") or payload.get("fillModel")
    ) or RESEARCH_FILL_MODEL_NEXT_BAR_OPEN
    slippage_raw = payload.get("slippage_bps")
    if slippage_raw is None:
        slippage_raw = payload.get("slippageBps")
    try:
        slippage_bps = Decimal(str(slippage_raw if slippage_raw not in (None, "") else 0))
    except InvalidOperation as exc:
        raise BotError("slippage_bps must be a number.") from exc
    if slippage_bps < 0:
        raise BotError("slippage_bps must be at least 0.")

    starting_raw = payload.get("starting_account_value")
    if starting_raw is None:
        starting_raw = payload.get("startingAccountValue")
    try:
        starting_account_value = Decimal(
            str(starting_raw if starting_raw not in (None, "") else 100000)
        )
    except InvalidOperation as exc:
        raise BotError("starting_account_value must be a number.") from exc
    if starting_account_value <= 0:
        raise BotError("starting_account_value must be greater than 0.")

    return ResearchRunRequest(
        date=raw_date,
        data_feed=config.data_feed,
        fill_model=fill_model,
        slippage_bps=slippage_bps,
        preset_name=_optional_text(payload.get("preset_name") or payload.get("presetName"))
        or "Current Controls",
        preset_version=_optional_text(
            payload.get("preset_version") or payload.get("presetVersion")
        )
        or "v1",
        starting_account_value=starting_account_value,
    )


def run_research_backtest_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    config = config_from_research_payload(payload)
    request = research_request_from_payload(payload, config)
    result = run_research_backtest(config, request)
    row = {
        column: result["row"].get(column, "")
        for column in RESEARCH_SPREADSHEET_COLUMNS
    }
    spreadsheet_settings = operator_spreadsheet_settings()
    endpoint_url = _optional_text(
        payload.get("research_post_endpoint_url")
        or payload.get("researchPostEndpointUrl")
        or payload.get("post_endpoint_url")
        or payload.get("postEndpointUrl")
        or spreadsheet_settings.get("research_post_endpoint_url")
        or spreadsheet_settings.get("post_endpoint_url")
    )
    post_result: dict[str, Any] | None = None
    if endpoint_url:
        status_code, parsed_response = _post_json_to_spreadsheet_endpoint(
            endpoint_url,
            row,
        )
        post_result = {
            "status": "posted",
            "http_status": status_code,
            "endpoint_response": parsed_response,
        }

    return {
        "status": result["status"],
        "posted": post_result,
        "columns": RESEARCH_SPREADSHEET_COLUMNS,
        "row": row,
        "date": result["date"],
        "performance": result["performance"],
        "inversebot_archaeology": result["performance"].get(
            "inversebot_archaeology"
        ),
        "trades": result["trades"],
        "trade_count": len(result["trades"]),
        "cycles": len(result["records"]),
    }


def run_roster_dress_rehearsal_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    config = config_from_research_payload(payload)
    dates = _parse_research_compare_dates(payload)
    starting_raw = payload.get("starting_account_value")
    if starting_raw is None:
        starting_raw = payload.get("startingAccountValue")
    try:
        starting_account_value = Decimal(
            str(starting_raw if starting_raw not in (None, "") else 100)
        )
    except InvalidOperation as exc:
        raise BotError("starting_account_value must be a number.") from exc
    if starting_account_value <= 0:
        raise BotError("starting_account_value must be greater than 0.")

    full_roster_config = replace(
        config,
        enabled_bots=EDGEWALKER_BOTS,
        inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
    )
    return build_roster_dress_rehearsal_scoreboard(
        full_roster_config,
        dates,
        starting_account_value=starting_account_value,
        preset_name=_optional_text(payload.get("preset_name") or payload.get("presetName"))
        or "Full_Roster_Dress_Rehearsal",
        preset_version=_optional_text(
            payload.get("preset_version") or payload.get("presetVersion")
        )
        or "v1",
    )


def _parse_research_compare_dates(payload: dict[str, Any]) -> list[str]:
    raw_dates = (
        payload.get("dates")
        or payload.get("backtest_dates")
        or payload.get("backtestDates")
    )
    if isinstance(raw_dates, str):
        candidates = re.split(r"[\s,]+", raw_dates)
    elif isinstance(raw_dates, list):
        candidates = [str(item) for item in raw_dates]
    else:
        candidates = []

    dates: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        date_text = candidate.strip()
        if not date_text or date_text in seen:
            continue
        try:
            datetime.strptime(date_text, "%Y-%m-%d")
        except ValueError as exc:
            raise BotError("Comparison dates must use YYYY-MM-DD format.") from exc
        dates.append(date_text)
        seen.add(date_text)
    if not dates:
        raise BotError("Add at least one comparison date.")
    return dates


def _parse_research_compare_presets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_presets = payload.get("presets")
    if not isinstance(raw_presets, list):
        raise BotError("Choose at least two saved presets to compare.")

    presets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_presets, start=1):
        if not isinstance(item, dict):
            raise BotError(f"Comparison preset #{index} is invalid.")
        config = item.get("config")
        if not isinstance(config, dict):
            raise BotError(f"Comparison preset #{index} is missing a config snapshot.")
        name = _optional_text(
            item.get("name") or item.get("preset_name") or item.get("presetName")
        ) or f"Preset {index}"
        version = _optional_text(
            item.get("version")
            or item.get("preset_version")
            or item.get("presetVersion")
        ) or "v1"
        preset_id = f"{name}::{version}"
        if preset_id in seen:
            continue
        seen.add(preset_id)
        presets.append(
            {
                "id": preset_id,
                "name": name,
                "version": version,
                "config": dict(config),
                "notes": _optional_text(item.get("notes")) or "",
            }
        )

    if len(presets) < 2:
        raise BotError("Choose at least two saved presets to compare.")
    return presets


def _research_has_lead_router_suite(presets: list[dict[str, Any]]) -> bool:
    roles = {presetRole for presetRole in ("general", "momentum", "inverse")}
    found: set[str] = set()
    for preset in presets:
        name = str(preset.get("name") or "").lower()
        for role in roles:
            if role in name:
                found.add(role)
    return roles.issubset(found)


def _record_datetime(record: dict[str, Any]) -> datetime | None:
    raw = _optional_text(record.get("timestamp"))
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _window_records(
    records: list[dict[str, Any]],
    window_minutes: int | None,
) -> list[dict[str, Any]]:
    if window_minutes is None or not records:
        return records
    first_at = _record_datetime(records[0])
    if first_at is None:
        return records[:window_minutes]
    cutoff = first_at + timedelta(minutes=window_minutes)
    windowed = [
        record
        for record in records
        if (record_at := _record_datetime(record)) is not None and record_at < cutoff
    ]
    return windowed or records[:window_minutes]


def _trades_closed_in_window(
    trades: list[dict[str, Any]],
    records: list[dict[str, Any]],
    window_minutes: int | None,
) -> list[dict[str, Any]]:
    if window_minutes is None or not records:
        return trades
    first_at = _record_datetime(records[0])
    if first_at is None:
        return []
    cutoff = first_at + timedelta(minutes=window_minutes)
    closed: list[dict[str, Any]] = []
    for trade in trades:
        raw_closed_at = _optional_text(trade.get("closed_at"))
        if not raw_closed_at:
            continue
        try:
            closed_at = datetime.fromisoformat(raw_closed_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if closed_at <= cutoff:
            closed.append(trade)
    return closed


def _trade_datetime(trade: dict[str, Any], key: str) -> datetime | None:
    raw_value = _optional_text(trade.get(key))
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _trades_opened_at_or_after_window(
    trades: list[dict[str, Any]],
    records: list[dict[str, Any]],
    window_minutes: int | None,
) -> list[dict[str, Any]]:
    if window_minutes is None or not records:
        return trades
    first_at = _record_datetime(records[0])
    if first_at is None:
        return []
    cutoff = first_at + timedelta(minutes=window_minutes)
    opened: list[dict[str, Any]] = []
    for trade in trades:
        opened_at = _trade_datetime(trade, "opened_at")
        if opened_at is not None and opened_at >= cutoff:
            opened.append(trade)
    return opened


def _trade_window_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    total = Decimal("0")
    wins = 0
    for trade in trades:
        value = _decimal_from_value(trade.get("realized_pl"))
        if value is None:
            continue
        total += value
        if value > 0:
            wins += 1
    trade_count = len(trades)
    return {
        "pl": _rounded_number(total),
        "trade_count": trade_count,
        "win_rate": round(wins / trade_count * 100, 2) if trade_count else 0,
    }


def _research_checkpoint_trade_windows(
    records: list[dict[str, Any]],
    trades: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    windows: dict[str, dict[str, Any]] = {}
    for window_minutes in (15, 30, 60, 90):
        first_at = _record_datetime(records[0]) if records else None
        cutoff = first_at + timedelta(minutes=window_minutes) if first_at else None
        pre_summary = _trade_window_summary(
            _trades_closed_in_window(trades, records, window_minutes)
        )
        post_summary = _trade_window_summary(
            _trades_opened_at_or_after_window(trades, records, window_minutes)
        )
        windows[str(window_minutes)] = {
            "cutoff": cutoff.isoformat(timespec="seconds") if cutoff else None,
            "pre_pl": pre_summary["pl"],
            "pre_trade_count": pre_summary["trade_count"],
            "pre_win_rate": pre_summary["win_rate"],
            "post_pl": post_summary["pl"],
            "post_trade_count": post_summary["trade_count"],
            "post_win_rate": post_summary["win_rate"],
        }
    return windows


def _research_regime_segments(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current_regime: str | None = None
    current_count = 0
    for record in records:
        regime = _optional_text(record.get("regime")) or "UNKNOWN"
        if current_regime is None:
            current_regime = regime
            current_count = 1
            continue
        if regime == current_regime:
            current_count += 1
            continue
        segments.append({"regime": current_regime, "minutes": current_count})
        current_regime = regime
        current_count = 1
    if current_regime is not None:
        segments.append({"regime": current_regime, "minutes": current_count})
    return segments


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    middle = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return sorted_values[middle]
    return (sorted_values[middle - 1] + sorted_values[middle]) / 2


def _rounded_float(value: Any, places: int = 2) -> float | None:
    numeric = _float_from_value(value)
    if numeric is None:
        return None
    return round(numeric, places)


def _research_fingerprint(
    records: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    *,
    window_minutes: int | None = None,
) -> dict[str, Any]:
    window_records = _window_records(records, window_minutes)
    window_trades = _trades_closed_in_window(trades, records, window_minutes)
    cycles = len(window_records)
    transitions = sum(1 for record in window_records if record.get("regime_transition"))
    non_warmup_transition_count = 0
    for record in window_records:
        transition = record.get("regime_transition")
        if not isinstance(transition, dict):
            continue
        from_regime = str(transition.get("from") or "").upper()
        to_regime = str(transition.get("to") or "").upper()
        if not from_regime or not to_regime:
            continue
        if from_regime in {"WARMUP", "UNKNOWN", "NONE"}:
            continue
        if to_regime in {"WARMUP", "UNKNOWN", "NONE"}:
            continue
        non_warmup_transition_count += 1
    hours = max(cycles / 60, 1 / 60)
    segments = _research_regime_segments(window_records)
    active_segments = [
        segment
        for segment in segments
        if segment["regime"] not in {"WARMUP", "UNKNOWN", "NONE"}
    ]
    duration_source = active_segments or segments
    durations = [float(segment["minutes"]) for segment in duration_source]
    trust_scores: list[float] = []
    for record in window_records:
        trend_trust = record.get("trend_trust")
        if isinstance(trend_trust, dict):
            score = _float_from_value(trend_trust.get("score"))
            if score is not None:
                trust_scores.append(score)
    quality = trade_quality_averages(window_trades)
    wins = sum(
        1
        for trade in window_trades
        if (_float_from_value(trade.get("realized_pl")) or 0) > 0
    )
    trade_count = len(window_trades)
    win_rate = wins / trade_count * 100 if trade_count else None
    route_invalidations = [
        trade
        for trade in window_trades
        if _optional_text(trade.get("exit_reason")) == "route_invalidated_exit"
    ]
    trailing_stops = [
        trade
        for trade in window_trades
        if _optional_text(trade.get("exit_reason")) == "trailing_stop_breached"
    ]

    empty_price_path = {
        "open_to_current_percent": None,
        "max_drawdown_from_open_percent": None,
        "max_runup_from_open_percent": None,
    }

    def first_float(*values: Any) -> float | None:
        for value in values:
            parsed = _float_from_value(value)
            if parsed is not None:
                return parsed
        return None

    def price_path_from_components(
        *,
        open_price: float | None,
        current_price: float | None,
        lows: list[float],
        highs: list[float],
    ) -> dict[str, Any]:
        if open_price is None or current_price is None or open_price == 0:
            return dict(empty_price_path)
        low_price = min(lows) if lows else current_price
        high_price = max(highs) if highs else current_price
        return {
            "open_to_current_percent": round(
                (current_price - open_price) / open_price * 100,
                2,
            ),
            "max_drawdown_from_open_percent": round(
                (low_price - open_price) / open_price * 100,
                2,
            ),
            "max_runup_from_open_percent": round(
                (high_price - open_price) / open_price * 100,
                2,
            ),
        }

    def fallback_price_path(*keys: str) -> dict[str, Any]:
        prices: list[float] = []
        for record in window_records:
            for key in keys:
                price = _float_from_value(record.get(key))
                if price is not None:
                    prices.append(price)
                    break
        return price_path_from_components(
            open_price=prices[0] if prices else None,
            current_price=prices[-1] if prices else None,
            lows=prices,
            highs=prices,
        )

    def bar_price_path(prefix: str, *fallback_keys: str) -> dict[str, Any]:
        open_price: float | None = None
        current_price: float | None = None
        lows: list[float] = []
        highs: list[float] = []
        saw_bar = False
        for record in window_records:
            bar_open = _float_from_value(record.get(f"{prefix}_bar_open"))
            bar_high = _float_from_value(record.get(f"{prefix}_bar_high"))
            bar_low = _float_from_value(record.get(f"{prefix}_bar_low"))
            bar_close = _float_from_value(record.get(f"{prefix}_bar_close"))
            if all(
                value is None for value in (bar_open, bar_high, bar_low, bar_close)
            ):
                continue
            saw_bar = True
            cycle_open = first_float(bar_open, bar_close, bar_high, bar_low)
            cycle_high = first_float(bar_high, bar_close, bar_open, bar_low)
            cycle_low = first_float(bar_low, bar_close, bar_open, bar_high)
            cycle_close = first_float(bar_close, bar_open, bar_high, bar_low)
            if open_price is None and cycle_open is not None:
                open_price = cycle_open
            if cycle_high is not None:
                highs.append(cycle_high)
            if cycle_low is not None:
                lows.append(cycle_low)
            if cycle_close is not None:
                current_price = cycle_close
        if not saw_bar:
            return fallback_price_path(*fallback_keys)
        return price_path_from_components(
            open_price=open_price,
            current_price=current_price,
            lows=lows,
            highs=highs,
        )

    source_path = bar_price_path("source", "source_price", "price")
    inverse_path = bar_price_path("inverse", "inverse_price")
    regime_counts = {
        "uptrend_minutes": sum(
            1 for record in window_records if record.get("regime") == "UPTREND"
        ),
        "downtrend_minutes": sum(
            1 for record in window_records if record.get("regime") == "DOWNTREND"
        ),
        "sideways_minutes": sum(
            1 for record in window_records if record.get("regime") == "SIDEWAYS"
        ),
    }

    def realized_total(rows: list[dict[str, Any]]) -> float:
        total = Decimal("0")
        for row in rows:
            value = _decimal_from_value(row.get("realized_pl"))
            if value is not None:
                total += value
        return _rounded_number(total)

    return {
        "window_minutes": window_minutes,
        "cycles": cycles,
        "is_full_session": cycles >= 350 if window_minutes is None else None,
        "regime_transitions": transitions,
        "transitions_per_hour": round(transitions / hours, 2),
        "non_warmup_regime_transitions": non_warmup_transition_count,
        "non_warmup_transitions_per_hour": round(
            non_warmup_transition_count / hours,
            2,
        ),
        "avg_regime_duration_minutes": (
            round(sum(durations) / len(durations), 2) if durations else None
        ),
        "median_regime_duration_minutes": (
            round(_median(durations), 2) if durations else None
        ),
        "max_regime_duration_minutes": round(max(durations), 2) if durations else None,
        "warmup_cycles": sum(
            1 for record in window_records if record.get("regime") == "WARMUP"
        ),
        "trend_trust_avg": (
            round(sum(trust_scores) / len(trust_scores), 2) if trust_scores else None
        ),
        "closed_trades": trade_count,
        "win_rate": round(win_rate, 2) if win_rate is not None else None,
        "route_invalidation_rate": (
            round(len(route_invalidations) / trade_count * 100, 2)
            if trade_count
            else None
        ),
        "route_invalidation_pl": realized_total(route_invalidations),
        "trailing_stop_rate": (
            round(len(trailing_stops) / trade_count * 100, 2)
            if trade_count
            else None
        ),
        "trailing_stop_pl": realized_total(trailing_stops),
        "avg_mfe_percent": _rounded_float(quality.get("avg_mfe_percent")),
        "avg_mae_percent": _rounded_float(quality.get("avg_mae_percent")),
        "avg_capture_ratio_percent": _rounded_float(
            quality.get("avg_capture_ratio_percent")
        ),
        "avg_hold_seconds": _rounded_float(quality.get("avg_hold_seconds")),
        "current_regime": (
            _optional_text(window_records[-1].get("regime")) if window_records else None
        ),
        "source_open_to_current_percent": source_path["open_to_current_percent"],
        "source_max_drawdown_from_open_percent": source_path[
            "max_drawdown_from_open_percent"
        ],
        "source_max_runup_from_open_percent": source_path[
            "max_runup_from_open_percent"
        ],
        "inverse_open_to_current_percent": inverse_path["open_to_current_percent"],
        "inverse_max_drawdown_from_open_percent": inverse_path[
            "max_drawdown_from_open_percent"
        ],
        "inverse_max_runup_from_open_percent": inverse_path[
            "max_runup_from_open_percent"
        ],
        **regime_counts,
    }


def _research_result_summary(
    result: dict[str, Any],
    preset: dict[str, Any],
) -> dict[str, Any]:
    row = dict(result.get("row") or {})
    performance = result.get("performance") if isinstance(result.get("performance"), dict) else {}
    trades = result.get("trades") if isinstance(result.get("trades"), list) else []
    records = result.get("records") if isinstance(result.get("records"), list) else []
    return {
        "date": _optional_text(row.get("date") or result.get("date")) or "",
        "preset_id": preset["id"],
        "preset_name": preset["name"],
        "preset_version": preset["version"],
        "row": row,
        "bot_performance": performance.get("bot_performance") or [],
        "inversebot_archaeology": performance.get("inversebot_archaeology") or {},
        "fingerprint": _research_fingerprint(records, trades),
        "early_windows": {
            "15": _research_fingerprint(records, trades, window_minutes=15),
            "30": _research_fingerprint(records, trades, window_minutes=30),
            "60": _research_fingerprint(records, trades, window_minutes=60),
            "90": _research_fingerprint(records, trades, window_minutes=90),
        },
        "checkpoint_trade_windows": _research_checkpoint_trade_windows(
            records,
            trades,
        ),
        "trade_count": len(trades),
        "cycles": len(records),
    }


def _v9_observer_context_from_result(
    result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    early_windows = result.get("early_windows")
    if not isinstance(early_windows, dict):
        return None
    fingerprint = early_windows.get("30")
    if not isinstance(fingerprint, dict):
        return None

    transition_count = _float_from_value(fingerprint.get("regime_transitions"))
    transitions_per_hour = _float_from_value(fingerprint.get("transitions_per_hour"))
    non_warmup_transition_count = _float_from_value(
        fingerprint.get("non_warmup_regime_transitions")
    )
    non_warmup_transitions_per_hour = _float_from_value(
        fingerprint.get("non_warmup_transitions_per_hour")
    )
    trend_trust = _float_from_value(fingerprint.get("trend_trust_avg"))
    source_percent = _float_from_value(
        fingerprint.get("source_open_to_current_percent")
    )
    window_minutes = _float_from_value(fingerprint.get("window_minutes")) or 30

    return {
        "observer_preset": result.get("preset_name"),
        "early_transition_count": int(transition_count or 0),
        "early_transitions_per_hour": (
            _rounded_number(transitions_per_hour)
            if transitions_per_hour is not None
            else None
        ),
        "early_non_warmup_transition_count": int(
            non_warmup_transition_count or 0
        ),
        "early_non_warmup_transitions_per_hour": (
            _rounded_number(non_warmup_transitions_per_hour)
            if non_warmup_transitions_per_hour is not None
            else None
        ),
        "trend_trust_score": int(round(trend_trust)) if trend_trust is not None else None,
        "source_open_to_current_percent": (
            _rounded_number(source_percent) if source_percent is not None else None
        ),
        "early_transition_window_minutes": int(window_minutes),
    }


ROUTER_V1_PRESET_ID = "Router_v1::v10"
ROUTER_V1_PRESET_NAME = "Router_v1"
ROUTER_V1_PRESET_VERSION = "v10"
ROUTER_V1_FALLBACK_PRESET_ID = "Router_v1_NoAuthority::v10"
ROUTER_V1_FALLBACK_PRESET_NAME = "Router_v1_NoAuthority"
CHOP_SPECIALIST_PRESET_ID = "Lead_Chop_Specialist::v10"
CHOP_SPECIALIST_PRESET_NAME = "Lead_Chop_Specialist"
FLAT_CONTROL_PRESET_ID = "Flat_NoTrade::v10"
FLAT_CONTROL_PRESET_NAME = "Flat_NoTrade"
RESEARCH_COMPARISON_MAX_REPLAY_RUNS = 120


def _research_row_decimal(result: dict[str, Any], key: str) -> Decimal:
    row = result.get("row") if isinstance(result.get("row"), dict) else {}
    return _decimal_from_value(row.get(key)) or Decimal("0")


def _research_has_momentum_authority(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    return _research_row_decimal(result, "v9_momentum_context_activations") > 0


def _research_router_v1_summary(
    *,
    date_text: str,
    momentum_summary: dict[str, Any] | None,
    fallback_summary: dict[str, Any],
) -> dict[str, Any]:
    momentum_authority = _research_has_momentum_authority(momentum_summary)
    source = momentum_summary if momentum_authority and momentum_summary else fallback_summary
    router_summary = copy.deepcopy(source)
    source_name = source.get("preset_name") or "--"
    router_decision = (
        "MOMENTUM_AUTHORITY"
        if momentum_authority
        else "NO_AUTHORITY_CHOP_FALLBACK"
    )

    router_summary.update(
        {
            "date": date_text,
            "preset_id": ROUTER_V1_PRESET_ID,
            "preset_name": ROUTER_V1_PRESET_NAME,
            "preset_version": ROUTER_V1_PRESET_VERSION,
            "router_decision": router_decision,
            "router_source_preset": source_name,
        }
    )
    row = router_summary.get("row")
    if not isinstance(row, dict):
        row = {}
        router_summary["row"] = row
    row.update(
        {
            "preset_name": ROUTER_V1_PRESET_NAME,
            "preset_version": ROUTER_V1_PRESET_VERSION,
            "router_decision": router_decision,
            "router_source_preset": source_name,
            "router_authority_state": "momentum" if momentum_authority else "none",
            "router_fallback_preset": ROUTER_V1_FALLBACK_PRESET_NAME,
            "router_momentum_authority_preset": (
                momentum_summary.get("preset_name")
                if isinstance(momentum_summary, dict)
                else None
            ),
        }
    )
    return router_summary


def _research_chop_specialist_summary(
    *,
    date_text: str,
    fallback_summary: dict[str, Any],
) -> dict[str, Any]:
    chop_summary = copy.deepcopy(fallback_summary)
    chop_summary.update(
        {
            "date": date_text,
            "preset_id": CHOP_SPECIALIST_PRESET_ID,
            "preset_name": CHOP_SPECIALIST_PRESET_NAME,
            "preset_version": ROUTER_V1_PRESET_VERSION,
            "specialist_source_preset": fallback_summary.get("preset_name") or "--",
        }
    )
    row = chop_summary.get("row")
    if not isinstance(row, dict):
        row = {}
        chop_summary["row"] = row
    row.update(
        {
            "preset_name": CHOP_SPECIALIST_PRESET_NAME,
            "preset_version": ROUTER_V1_PRESET_VERSION,
            "specialist_target_bot": CHOP_BOT,
            "specialist_source_preset": fallback_summary.get("preset_name") or "--",
        }
    )
    return chop_summary


def _research_flat_bot_performance() -> list[dict[str, Any]]:
    return [
        {
            "bot": bot,
            "realized_pl": "0",
            "trade_count": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_percent": None,
            "last_trade_realized_pl": None,
            "last_trade_symbol": None,
            "last_trade_closed_at": None,
            "avg_mfe_percent": None,
            "avg_mae_percent": None,
            "avg_capture_ratio_percent": None,
            "avg_hold_seconds": None,
        }
        for bot in BOT_PERFORMANCE_ORDER
    ]


def _research_flat_no_trade_summary(
    *,
    date_text: str,
    reference_summary: dict[str, Any],
) -> dict[str, Any]:
    flat_summary = copy.deepcopy(reference_summary)
    flat_summary.update(
        {
            "date": date_text,
            "preset_id": FLAT_CONTROL_PRESET_ID,
            "preset_name": FLAT_CONTROL_PRESET_NAME,
            "preset_version": ROUTER_V1_PRESET_VERSION,
            "bot_performance": _research_flat_bot_performance(),
            "inversebot_archaeology": {},
            "checkpoint_trade_windows": {},
            "trade_count": 0,
        }
    )
    row = flat_summary.get("row")
    if not isinstance(row, dict):
        row = {}
        flat_summary["row"] = row
    ending_account = row.get("starting_account_value") or row.get(
        "ending_account_value"
    )
    zero_keys = (
        "realized_pl_dollars",
        "account_change_percent",
        "closed_trades",
        "wins",
        "losses",
        "win_rate",
        "momentum_pl",
        "chop_pl",
        "inverse_pl",
        "route_invalidation_exits",
        "route_invalidation_pl",
        "trailing_stop_exits",
        "trailing_stop_pl",
        "market_close_exits",
        "market_close_pl",
        "mfe_percent",
        "avg_mfe_percent",
        "avg_mae_percent",
        "avg_capture_ratio_percent",
        "avg_hold_seconds",
        "v8_entry_blocks",
        "v8_entry_block_target_hits",
        "v8_entry_block_non_hits",
        "v9_momentum_context_activations",
        "v9_directional_suppressions",
        "v9_momentum_context_intrusions",
        "v10_directional_suppressions",
        "v10_momentum_authority_activations",
        "v10_momentum_authority_intrusions",
        "v10_no_authority_directional_suppression_blocks",
        "v10_no_authority_momentum_suppression_blocks",
        "v10_no_authority_inverse_suppression_blocks",
        "v9_inverse_suppression_blocks",
        "v9_momentum_context_invalidations",
    )
    for key in zero_keys:
        row[key] = 0
    clear_keys = (
        "v10_suppressed_directional_shadow_pl",
        "v10_suppressed_directional_shadow_status",
        "v10_no_authority_context_activation_reason",
        "v10_no_authority_context_observer_preset",
        "v10_no_authority_context_authority_gate",
        "v10_no_authority_context_trust_score",
        "v10_no_authority_context_soxl_percent",
        "v10_no_authority_context_soxl_runup_percent",
        "v10_no_authority_context_soxl_drawdown_percent",
        "v10_no_authority_context_early_transition_count",
        "v10_no_authority_context_early_transitions_per_hour",
        "v10_no_authority_context_early_non_warmup_transition_count",
        "v10_no_authority_context_early_non_warmup_transitions_per_hour",
        "v10_no_authority_context_early_window_minutes",
        "enabled_bots",
    )
    for key in clear_keys:
        row[key] = ""
    row.update(
        {
            "date": date_text,
            "ending_account_value": ending_account,
            "account_result_status": "FLAT",
            "preset_name": FLAT_CONTROL_PRESET_NAME,
            "preset_version": ROUTER_V1_PRESET_VERSION,
            "top_pl_bot": "",
            "bottom_pl_bot": "",
            "reconciliation_confidence": "",
            "operator_notes": "flat_no_trade_control",
            "daily_narrative": "",
            "v9_context": "--",
            "v10_context": "--",
            "momentum_authority_required": False,
            "momentum_authority_revoke_exits": False,
            "momentum_authority_latch_once_active": False,
            "v10_force_no_authority": False,
        }
    )
    return flat_summary


def _research_target_bot_for_preset(preset_name: str) -> str | None:
    normalized = preset_name.lower()
    if "router" in normalized or "flat" in normalized or "no_trade" in normalized:
        return None
    if "momentum" in normalized:
        return MOMENTUM_BOT
    if "chop" in normalized:
        return CHOP_BOT
    if "inverse" in normalized:
        return INVERSE_BOT
    return None


def _research_bot_pl(row: dict[str, Any], bot_name: str) -> Decimal:
    key_by_bot = {
        MOMENTUM_BOT: "momentum_pl",
        CHOP_BOT: "chop_pl",
        INVERSE_BOT: "inverse_pl",
    }
    return _decimal_from_value(row.get(key_by_bot.get(bot_name, ""))) or Decimal("0")


def _research_bot_trade_count(result: dict[str, Any], bot_name: str) -> int:
    for item in result.get("bot_performance") or []:
        if not isinstance(item, dict) or item.get("bot") != bot_name:
            continue
        return int(_float_from_value(item.get("trade_count")) or 0)
    return 0


def _research_position_budget(row: dict[str, Any]) -> Decimal:
    starting = _decimal_from_value(row.get("starting_account_value")) or Decimal("0")
    allocation = _decimal_from_value(row.get("position_allocation_percent"))
    notional = _decimal_from_value(row.get("position_notional"))
    sizing_mode = (_optional_text(row.get("position_sizing_mode")) or "").upper()
    if sizing_mode == "DYNAMIC" and allocation is not None:
        return starting * allocation / Decimal("100")
    return notional or Decimal("0")


def _research_target_move_percent(result: dict[str, Any], target_bot: str) -> Decimal:
    fingerprint = result.get("fingerprint") if isinstance(result.get("fingerprint"), dict) else {}
    if target_bot == MOMENTUM_BOT:
        return max(
            _decimal_from_value(
                fingerprint.get("source_max_runup_from_open_percent")
            )
            or Decimal("0"),
            Decimal("0"),
        )
    if target_bot == INVERSE_BOT:
        return max(
            _decimal_from_value(
                fingerprint.get("inverse_max_runup_from_open_percent")
            )
            or Decimal("0"),
            Decimal("0"),
        )
    if target_bot == CHOP_BOT:
        source_runup = max(
            _decimal_from_value(
                fingerprint.get("source_max_runup_from_open_percent")
            )
            or Decimal("0"),
            Decimal("0"),
        )
        source_drawdown = min(
            _decimal_from_value(
                fingerprint.get("source_max_drawdown_from_open_percent")
            )
            or Decimal("0"),
            Decimal("0"),
        )
        return source_runup + abs(source_drawdown)
    return Decimal("0")


def _research_theoretical_target_pl(result: dict[str, Any], target_bot: str) -> Decimal:
    row = result.get("row") if isinstance(result.get("row"), dict) else {}
    return _research_position_budget(row) * _research_target_move_percent(
        result,
        target_bot,
    ) / Decimal("100")


def _percent_decimal(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return numerator / denominator * Decimal("100")


def _rounded_optional_number(value: Decimal | None) -> float | str:
    if value is None:
        return ""
    return _rounded_number(value)


def _research_specialist_audit(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault(result["preset_id"], []).append(result)

    audits: list[dict[str, Any]] = []
    for preset_id, preset_results in grouped.items():
        first = preset_results[0]
        preset_name = first["preset_name"]
        target_bot = _research_target_bot_for_preset(preset_name)
        if not target_bot:
            continue

        target_pl = Decimal("0")
        total_pl = Decimal("0")
        total_abs_bot_pl = Decimal("0")
        non_target_pl = Decimal("0")
        non_target_damage = Decimal("0")
        target_trades = 0
        total_trades = 0
        home_rows = sorted(
            preset_results,
            key=lambda row: _research_target_move_percent(row, target_bot),
            reverse=True,
        )[:5]
        home_target_pl = Decimal("0")
        home_preset_pl = Decimal("0")
        home_non_target_pl = Decimal("0")
        home_non_target_damage = Decimal("0")
        home_theoretical_pl = Decimal("0")
        home_target_trades = 0
        home_total_trades = 0

        for result in preset_results:
            row = result.get("row") if isinstance(result.get("row"), dict) else {}
            row_total_pl = (
                _decimal_from_value(row.get("realized_pl_dollars")) or Decimal("0")
            )
            row_target_pl = _research_bot_pl(row, target_bot)
            total_pl += row_total_pl
            target_pl += row_target_pl
            target_trades += _research_bot_trade_count(result, target_bot)
            total_trades += int(_float_from_value(row.get("closed_trades")) or 0)
            for bot_name in BOT_PERFORMANCE_ORDER:
                bot_pl = _research_bot_pl(row, bot_name)
                total_abs_bot_pl += abs(bot_pl)
                if bot_name == target_bot:
                    continue
                non_target_pl += bot_pl
                if bot_pl < 0:
                    non_target_damage += abs(bot_pl)

        for result in home_rows:
            row = result.get("row") if isinstance(result.get("row"), dict) else {}
            row_total_pl = (
                _decimal_from_value(row.get("realized_pl_dollars")) or Decimal("0")
            )
            row_target_pl = _research_bot_pl(row, target_bot)
            home_preset_pl += row_total_pl
            home_target_pl += row_target_pl
            home_theoretical_pl += _research_theoretical_target_pl(result, target_bot)
            home_target_trades += _research_bot_trade_count(result, target_bot)
            home_total_trades += int(_float_from_value(row.get("closed_trades")) or 0)
            for bot_name in BOT_PERFORMANCE_ORDER:
                if bot_name == target_bot:
                    continue
                bot_pl = _research_bot_pl(row, bot_name)
                home_non_target_pl += bot_pl
                if bot_pl < 0:
                    home_non_target_damage += abs(bot_pl)

        purity = _percent_decimal(abs(target_pl), total_abs_bot_pl)
        trade_share = _percent_decimal(
            Decimal(target_trades),
            Decimal(total_trades),
        )
        home_target_share = _percent_decimal(home_target_pl, home_preset_pl)
        if home_target_share is not None and home_target_share < 0:
            home_target_share = None
        home_capture = _percent_decimal(home_target_pl, home_theoretical_pl)
        home_missed = home_theoretical_pl - home_target_pl
        if home_missed < 0:
            home_missed = Decimal("0")

        if (
            target_pl > 0
            and home_preset_pl > 0
            and home_target_pl > 0
            and (home_target_share or Decimal("0")) >= Decimal("70")
            and (home_capture or Decimal("0")) >= Decimal("20")
        ):
            diagnosis = "SPECIALIST_CONFIRMED"
        elif target_pl > 0 and non_target_damage > abs(target_pl):
            diagnosis = "REAL_BUT_POLLUTED"
        elif (
            target_pl <= 0
            or home_target_trades == 0
            or (home_capture or Decimal("0")) < Decimal("10")
        ):
            diagnosis = "WEAK_TARGET_ENGINE"
        else:
            diagnosis = "MIXED_OR_UNPROVEN"

        audits.append(
            {
                "preset_id": preset_id,
                "preset_name": preset_name,
                "preset_version": first["preset_version"],
                "target_bot": target_bot,
                "total_pl": _rounded_number(total_pl),
                "target_bot_pl": _rounded_number(target_pl),
                "non_target_bot_pl": _rounded_number(non_target_pl),
                "non_target_damage": _rounded_number(non_target_damage),
                "target_purity_percent": _rounded_optional_number(purity),
                "target_trade_share_percent": _rounded_optional_number(trade_share),
                "home_turf_dates": [row["date"] for row in home_rows],
                "home_turf_preset_pl": _rounded_number(home_preset_pl),
                "home_turf_target_bot_pl": _rounded_number(home_target_pl),
                "home_turf_non_target_bot_pl": _rounded_number(home_non_target_pl),
                "home_turf_non_target_damage": _rounded_number(
                    home_non_target_damage
                ),
                "home_turf_target_share_percent": _rounded_optional_number(
                    home_target_share
                ),
                "home_turf_capture_efficiency_percent": _rounded_optional_number(
                    home_capture
                ),
                "home_turf_missed_opportunity": _rounded_number(home_missed),
                "home_turf_target_trades": home_target_trades,
                "home_turf_total_trades": home_total_trades,
                "diagnosis": diagnosis,
            }
        )

    return sorted(
        audits,
        key=lambda row: (
            _decimal_from_value(row.get("home_turf_preset_pl")) or Decimal("0"),
            _decimal_from_value(row.get("target_bot_pl")) or Decimal("0"),
        ),
        reverse=True,
    )


def _research_winner_confidence(margin_percent: Decimal) -> str:
    margin = abs(margin_percent)
    if margin >= Decimal("1.00"):
        return "HIGH"
    if margin >= Decimal("0.25"):
        return "MODERATE"
    return "LOW"


def _research_compare_date_summary(
    date_text: str,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    ranked = sorted(
        results,
        key=lambda item: _decimal_from_value(item["row"].get("realized_pl_dollars"))
        or Decimal("0"),
        reverse=True,
    )
    winner = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else ranked[0]
    worst = ranked[-1]
    winner_pl = _decimal_from_value(winner["row"].get("realized_pl_dollars")) or Decimal("0")
    runner_pl = _decimal_from_value(runner_up["row"].get("realized_pl_dollars")) or Decimal("0")
    worst_pl = _decimal_from_value(worst["row"].get("realized_pl_dollars")) or Decimal("0")
    winner_pct = _decimal_from_value(winner["row"].get("account_change_percent")) or Decimal("0")
    runner_pct = _decimal_from_value(runner_up["row"].get("account_change_percent")) or Decimal("0")
    margin_pl = winner_pl - runner_pl
    margin_pct = winner_pct - runner_pct
    costs = [
        {
            "preset_name": result["preset_name"],
            "preset_version": result["preset_version"],
            "cost_dollars": _rounded_number(
                winner_pl
                - (
                    _decimal_from_value(result["row"].get("realized_pl_dollars"))
                    or Decimal("0")
                )
            ),
            "cost_percent": _rounded_number(
                winner_pct
                - (
                    _decimal_from_value(result["row"].get("account_change_percent"))
                    or Decimal("0")
                )
            ),
        }
        for result in ranked
        if result is not winner
    ]
    return {
        "date": date_text,
        "winner": winner["preset_name"],
        "winner_version": winner["preset_version"],
        "winner_pl": _rounded_number(winner_pl),
        "winner_account_change_percent": _rounded_number(winner_pct),
        "runner_up": runner_up["preset_name"],
        "runner_up_version": runner_up["preset_version"],
        "runner_up_pl": _rounded_number(runner_pl),
        "worst": worst["preset_name"],
        "worst_version": worst["preset_version"],
        "worst_pl": _rounded_number(worst_pl),
        "margin_dollars": _rounded_number(margin_pl),
        "margin_percent": _rounded_number(margin_pct),
        "winner_confidence": _research_winner_confidence(margin_pct),
        "worst_misclassification_cost_dollars": _rounded_number(winner_pl - worst_pl),
        "worst_misclassification_cost_percent": _rounded_number(
            winner_pct
            - (
                _decimal_from_value(worst["row"].get("account_change_percent"))
                or Decimal("0")
            )
        ),
        "misclassification_costs": costs,
        "winner_fingerprint": winner["fingerprint"],
        "winner_early_windows": winner["early_windows"],
    }


def _research_compare_preset_summaries(
    results: list[dict[str, Any]],
    date_summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    date_winners = {
        summary["date"]: f"{summary['winner']}::{summary['winner_version']}"
        for summary in date_summaries
    }
    buckets: dict[str, dict[str, Any]] = {}
    for result in results:
        key = result["preset_id"]
        row = result["row"]
        bucket = buckets.setdefault(
            key,
            {
                "preset_name": result["preset_name"],
                "preset_version": result["preset_version"],
                "runs": 0,
                "date_wins": 0,
                "green_days": 0,
                "red_days": 0,
                "total_pl": Decimal("0"),
                "total_account_change_percent": Decimal("0"),
                "momentum_pl": Decimal("0"),
                "chop_pl": Decimal("0"),
                "inverse_pl": Decimal("0"),
                "closed_trades": 0,
                "best_date": "",
                "best_pl": None,
                "worst_date": "",
                "worst_pl": None,
            },
        )
        realized_pl = _decimal_from_value(row.get("realized_pl_dollars")) or Decimal("0")
        account_change = _decimal_from_value(row.get("account_change_percent")) or Decimal("0")
        bucket["runs"] += 1
        bucket["total_pl"] += realized_pl
        bucket["total_account_change_percent"] += account_change
        bucket["momentum_pl"] += _decimal_from_value(row.get("momentum_pl")) or Decimal("0")
        bucket["chop_pl"] += _decimal_from_value(row.get("chop_pl")) or Decimal("0")
        bucket["inverse_pl"] += _decimal_from_value(row.get("inverse_pl")) or Decimal("0")
        bucket["closed_trades"] += int(_float_from_value(row.get("closed_trades")) or 0)
        if realized_pl > 0:
            bucket["green_days"] += 1
        elif realized_pl < 0:
            bucket["red_days"] += 1
        if date_winners.get(result["date"]) == key:
            bucket["date_wins"] += 1
        if bucket["best_pl"] is None or realized_pl > bucket["best_pl"]:
            bucket["best_pl"] = realized_pl
            bucket["best_date"] = result["date"]
        if bucket["worst_pl"] is None or realized_pl < bucket["worst_pl"]:
            bucket["worst_pl"] = realized_pl
            bucket["worst_date"] = result["date"]

    summaries = []
    for bucket in buckets.values():
        runs = int(bucket["runs"] or 1)
        summaries.append(
            {
                "preset_name": bucket["preset_name"],
                "preset_version": bucket["preset_version"],
                "runs": bucket["runs"],
                "date_wins": bucket["date_wins"],
                "green_days": bucket["green_days"],
                "red_days": bucket["red_days"],
                "total_pl": _rounded_number(bucket["total_pl"]),
                "avg_pl": _rounded_number(bucket["total_pl"] / Decimal(runs)),
                "total_account_change_percent": _rounded_number(
                    bucket["total_account_change_percent"]
                ),
                "avg_account_change_percent": _rounded_number(
                    bucket["total_account_change_percent"] / Decimal(runs)
                ),
                "momentum_pl": _rounded_number(bucket["momentum_pl"]),
                "chop_pl": _rounded_number(bucket["chop_pl"]),
                "inverse_pl": _rounded_number(bucket["inverse_pl"]),
                "closed_trades": bucket["closed_trades"],
                "best_date": bucket["best_date"],
                "best_pl": _rounded_number(bucket["best_pl"]),
                "worst_date": bucket["worst_date"],
                "worst_pl": _rounded_number(bucket["worst_pl"]),
            }
        )
    return sorted(summaries, key=lambda item: item["total_pl"], reverse=True)


def run_research_comparison_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    dates = _parse_research_compare_dates(payload)
    presets = _parse_research_compare_presets(payload)
    run_count = len(dates) * len(presets)
    if run_count > RESEARCH_COMPARISON_MAX_REPLAY_RUNS:
        raise BotError(
            "Limit one comparison batch to "
            f"{RESEARCH_COMPARISON_MAX_REPLAY_RUNS} replay runs."
        )

    results: list[dict[str, Any]] = []
    include_router_suite = _research_has_lead_router_suite(presets)
    role_presets = _shadow_router_role_presets(presets)
    observer_preset = role_presets["generalist"]
    observer_preset_id = observer_preset["id"]
    ordered_presets = [
        observer_preset,
        *[preset for preset in presets if preset["id"] != observer_preset_id],
    ]
    for date_text in dates:
        observer_summary: dict[str, Any] | None = None
        date_results: dict[str, dict[str, Any]] = {}
        shared_run_fields = {
            "backtest_date": date_text,
            "data_feed": payload.get("data_feed")
            or payload.get("dataFeed")
            or observer_preset["config"].get("dataFeed")
            or "iex",
            "starting_account_value": payload.get("starting_account_value")
            or payload.get("startingAccountValue")
            or "100000",
            "fill_model": payload.get("fill_model")
            or payload.get("fillModel")
            or RESEARCH_FILL_MODEL_NEXT_BAR_OPEN,
            "slippage_bps": payload.get("slippage_bps")
            if payload.get("slippage_bps") is not None
            else payload.get("slippageBps", "0"),
        }
        for preset in ordered_presets:
            run_payload = {
                **preset["config"],
                **shared_run_fields,
                "data_feed": shared_run_fields["data_feed"]
                or preset["config"].get("dataFeed")
                or "iex",
                "preset_name": preset["name"],
                "preset_version": preset["version"],
            }
            if observer_summary is not None and preset["id"] != observer_preset_id:
                observer_context = _v9_observer_context_from_result(observer_summary)
                if observer_context is not None:
                    run_payload["v9ObserverContext"] = observer_context
            config = config_from_research_payload(run_payload)
            request = research_request_from_payload(run_payload, config)
            result = run_research_backtest(config, request)
            summary = _research_result_summary(result, preset)
            date_results[preset["id"]] = summary
            if preset["id"] == observer_preset_id:
                observer_summary = summary
        fallback_summary: dict[str, Any] | None = None
        observer_context = _v9_observer_context_from_result(observer_summary)
        if include_router_suite and observer_context is not None:
            fallback_payload = {
                **observer_preset["config"],
                **shared_run_fields,
                "preset_name": ROUTER_V1_FALLBACK_PRESET_NAME,
                "preset_version": ROUTER_V1_PRESET_VERSION,
                "v9ObserverContext": observer_context,
                "v10ForceNoAuthority": True,
            }
            fallback_config = config_from_research_payload(fallback_payload)
            fallback_request = research_request_from_payload(
                fallback_payload,
                fallback_config,
            )
            fallback_result = run_research_backtest(
                fallback_config,
                fallback_request,
            )
            fallback_summary = _research_result_summary(
                fallback_result,
                {
                    "id": ROUTER_V1_FALLBACK_PRESET_ID,
                    "name": ROUTER_V1_FALLBACK_PRESET_NAME,
                    "version": ROUTER_V1_PRESET_VERSION,
                },
            )
        for preset in presets:
            summary = date_results.get(preset["id"])
            if summary is not None:
                results.append(summary)
        if include_router_suite and fallback_summary is not None:
            results.append(
                _research_chop_specialist_summary(
                    date_text=date_text,
                    fallback_summary=fallback_summary,
                )
            )
        if observer_summary is not None:
            results.append(
                _research_flat_no_trade_summary(
                    date_text=date_text,
                    reference_summary=observer_summary,
                )
            )
        if include_router_suite and fallback_summary is not None:
            results.append(
                _research_router_v1_summary(
                    date_text=date_text,
                    momentum_summary=date_results.get(role_presets["momentum"]["id"]),
                    fallback_summary=fallback_summary,
                )
            )

    date_summaries = [
        _research_compare_date_summary(
            date_text,
            [result for result in results if result["date"] == date_text],
        )
        for date_text in dates
    ]
    preset_summaries = _research_compare_preset_summaries(results, date_summaries)
    specialist_audit = _research_specialist_audit(results)
    return {
        "status": "completed",
        "kind": "comparison",
        "dates": dates,
        "preset_count": len(presets) + (3 if include_router_suite else 1),
        "run_count": len(results),
        "selected_run_count": run_count,
        "router_preset": ROUTER_V1_PRESET_NAME if include_router_suite else None,
        "chop_specialist_preset": (
            CHOP_SPECIALIST_PRESET_NAME if include_router_suite else None
        ),
        "flat_control_preset": FLAT_CONTROL_PRESET_NAME,
        "fill_model": payload.get("fill_model")
        or payload.get("fillModel")
        or RESEARCH_FILL_MODEL_NEXT_BAR_OPEN,
        "slippage_bps": payload.get("slippage_bps")
        if payload.get("slippage_bps") is not None
        else payload.get("slippageBps", "0"),
        "results": results,
        "date_summaries": date_summaries,
        "preset_summaries": preset_summaries,
        "specialist_audit": specialist_audit,
    }


SHADOW_ROUTER_CHECKPOINTS = (
    {"label": "09:45", "window_minutes": 15},
    {"label": "10:00", "window_minutes": 30},
    {"label": "10:30", "window_minutes": 60},
    {"label": "11:00", "window_minutes": 90},
)


def _shadow_router_role_presets(
    presets: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    def find_role(pattern: str) -> dict[str, Any] | None:
        for preset in presets:
            if pattern in preset["name"].lower():
                return preset
        return None

    generalist = find_role("general") or find_role("ungated") or presets[0]
    momentum = find_role("momentum") or generalist
    inverse = find_role("inverse") or generalist
    return {
        "generalist": generalist,
        "momentum": momentum,
        "inverse": inverse,
    }


def _shadow_router_pick(fingerprint: dict[str, Any]) -> dict[str, Any]:
    transitions_per_hour = _float_from_value(fingerprint.get("transitions_per_hour"))
    avg_regime_minutes = _float_from_value(
        fingerprint.get("avg_regime_duration_minutes")
    )
    trend_trust = _float_from_value(fingerprint.get("trend_trust_avg"))
    source_return = _float_from_value(
        fingerprint.get("source_open_to_current_percent")
    )
    source_drawdown = _float_from_value(
        fingerprint.get("source_max_drawdown_from_open_percent")
    )
    source_runup = _float_from_value(
        fingerprint.get("source_max_runup_from_open_percent")
    )
    current_regime = _optional_text(fingerprint.get("current_regime")) or ""
    uptrend_minutes = _float_from_value(fingerprint.get("uptrend_minutes")) or 0
    downtrend_minutes = _float_from_value(fingerprint.get("downtrend_minutes")) or 0
    reasons: list[str] = []

    if transitions_per_hour is None:
        return {
            "role": "generalist",
            "confidence": "LOW",
            "reasons": ["No transition fingerprint available."],
        }

    is_warmup_checkpoint = (
        current_regime == "WARMUP"
        or (transitions_per_hour == 0 and trend_trust is None)
    )
    if is_warmup_checkpoint:
        if (
            source_return is not None
            and source_return >= 2.75
            and (source_drawdown is None or source_drawdown > -1.5)
        ):
            reasons.append(f"SOXL is positive early from open ({source_return:g}%).")
            if source_runup is not None:
                reasons.append(f"SOXL early runup reached {source_runup:g}%.")
            return {
                "role": "momentum",
                "confidence": "HIGH" if source_return >= 4 else "MODERATE",
                "reasons": reasons,
            }
        if (
            source_return is not None
            and source_return <= -4
            and source_drawdown is not None
            and source_drawdown <= -4
        ):
            reasons.append(f"SOXL is sharply negative early ({source_return:g}%).")
            reasons.append(f"SOXL early drawdown reached {source_drawdown:g}%.")
            return {
                "role": "inverse",
                "confidence": "HIGH",
                "reasons": reasons,
            }
        reasons.append("No specialist threshold cleared; stay with the generalist.")
        return {
            "role": "generalist",
            "confidence": "LOW",
            "reasons": reasons,
        }

    bearish_price = source_return is not None and source_return <= -1.5
    bearish_damage = source_drawdown is not None and source_drawdown <= -2.5
    bullish_price = source_return is not None and source_return >= 1.5
    downside_context = (
        current_regime == "DOWNTREND"
        or bearish_damage
        or (trend_trust is not None and trend_trust < 45)
        or downtrend_minutes > uptrend_minutes
    )
    hostile_churn = (
        transitions_per_hour >= 5
        and avg_regime_minutes is not None
        and avg_regime_minutes < 6
        and (trend_trust is None or trend_trust < 45)
    )
    rebound_momentum = (
        source_return is not None
        and source_return >= 2.25
        and source_drawdown is not None
        and source_drawdown <= -2.5
        and current_regime == "UPTREND"
        and transitions_per_hour <= 3.5
        and avg_regime_minutes is not None
        and avg_regime_minutes >= 13
        and trend_trust is not None
        and trend_trust >= 60
    )

    if rebound_momentum:
        reasons.append(f"SOXL reclaimed from open ({source_return:g}%).")
        reasons.append(f"Earlier drawdown reached {source_drawdown:g}%.")
        reasons.append(
            f"Low transition pressure ({transitions_per_hour:g}/hr) with mature UPTREND structure."
        )
        reasons.append(f"Trend Trust is supportive ({trend_trust:g}).")
        return {
            "role": "momentum",
            "confidence": "HIGH" if source_return >= 4 else "MODERATE",
            "reasons": reasons,
        }

    if bearish_price and downside_context:
        reasons.append(f"SOXL is negative from open ({source_return:g}%).")
        if current_regime == "DOWNTREND":
            reasons.append("Current regime is DOWNTREND.")
        if bearish_damage:
            reasons.append(f"SOXL drawdown from open reached {source_drawdown:g}%.")
        if trend_trust is not None and trend_trust < 45:
            reasons.append(f"Trend Trust is weak ({trend_trust:g}).")
        if downtrend_minutes > uptrend_minutes:
            reasons.append("Downtrend minutes exceed uptrend minutes.")
        confidence = (
            "HIGH"
            if source_return <= -3
            and (bearish_damage or current_regime == "DOWNTREND")
            else "MODERATE"
        )
        return {
            "role": "inverse",
            "confidence": confidence,
            "reasons": reasons,
        }

    if hostile_churn:
        reasons.append(f"High transition pressure ({transitions_per_hour:g}/hr).")
        reasons.append(f"Very short average regime duration ({avg_regime_minutes:g}m).")
        if trend_trust is not None:
            reasons.append(f"Trend Trust is weak ({trend_trust:g}).")
        return {
            "role": "inverse",
            "confidence": "MODERATE",
            "reasons": reasons,
        }

    if (
        bullish_price
        and
        transitions_per_hour <= 3.5
        and avg_regime_minutes is not None
        and avg_regime_minutes >= 16
        and trend_trust is not None
        and trend_trust >= 50
        and current_regime != "DOWNTREND"
        and (source_drawdown is None or source_drawdown > -2.5)
    ):
        reasons.append(f"SOXL is positive from open ({source_return:g}%).")
        reasons.append(
            f"Low transition pressure ({transitions_per_hour:g}/hr) with mature regimes."
        )
        reasons.append(f"Trend Trust is supportive ({trend_trust:g}).")
        if source_runup is not None:
            reasons.append(f"SOXL runup from open reached {source_runup:g}%.")
        confidence = (
            "HIGH"
            if source_return >= 3
            and transitions_per_hour <= 2.5
            and avg_regime_minutes >= 20
            and trend_trust >= 50
            else "MODERATE"
        )
        return {
            "role": "momentum",
            "confidence": confidence,
            "reasons": reasons,
        }

    reasons.append("No specialist threshold cleared; stay with the generalist.")
    return {
        "role": "generalist",
        "confidence": "LOW",
        "reasons": reasons,
    }


def _result_by_preset_id(
    results: list[dict[str, Any]],
    date_text: str,
    preset_id: str,
) -> dict[str, Any] | None:
    for result in results:
        if result["date"] == date_text and result["preset_id"] == preset_id:
            return result
    return None


def _checkpoint_window_decimal(
    result: dict[str, Any] | None,
    window_key: str,
    field: str,
) -> Decimal:
    if not result:
        return Decimal("0")
    windows = (
        result.get("checkpoint_trade_windows")
        if isinstance(result.get("checkpoint_trade_windows"), dict)
        else {}
    )
    window = windows.get(window_key) if isinstance(windows, dict) else None
    if not isinstance(window, dict):
        return Decimal("0")
    return _decimal_from_value(window.get(field)) or Decimal("0")


def _checkpoint_window_number(
    result: dict[str, Any] | None,
    window_key: str,
    field: str,
) -> int:
    if not result:
        return 0
    windows = (
        result.get("checkpoint_trade_windows")
        if isinstance(result.get("checkpoint_trade_windows"), dict)
        else {}
    )
    window = windows.get(window_key) if isinstance(windows, dict) else None
    if not isinstance(window, dict):
        return 0
    value = _float_from_value(window.get(field))
    return int(value or 0)


def _shadow_router_switch_context(
    *,
    date_text: str,
    window_key: str,
    observer_result: dict[str, Any],
    selected_result: dict[str, Any] | None,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    generalist_pre_pl = _checkpoint_window_decimal(
        observer_result,
        window_key,
        "pre_pl",
    )
    generalist_post_pl = _checkpoint_window_decimal(
        observer_result,
        window_key,
        "post_pl",
    )
    selected_post_pl = _checkpoint_window_decimal(
        selected_result,
        window_key,
        "post_pl",
    )
    switch_pl = generalist_pre_pl + selected_post_pl
    generalist_checkpoint_pl = generalist_pre_pl + generalist_post_pl
    date_results = [result for result in results if result.get("date") == date_text]
    best_result = max(
        date_results,
        key=lambda result: _checkpoint_window_decimal(
            result,
            window_key,
            "post_pl",
        ),
        default=None,
    )
    checkpoint_best_post_pl = _checkpoint_window_decimal(
        best_result,
        window_key,
        "post_pl",
    )
    checkpoint_best_switch_pl = generalist_pre_pl + checkpoint_best_post_pl
    selected_preset_id = selected_result.get("preset_id") if selected_result else None
    checkpoint_best_preset_id = (
        best_result.get("preset_id") if isinstance(best_result, dict) else None
    )
    checkpoint_best_name = (
        best_result.get("preset_name") if isinstance(best_result, dict) else None
    )
    return {
        "switch_model": "generalist_pre_then_selected_opened_after_checkpoint",
        "generalist_pre_pl": _rounded_number(generalist_pre_pl),
        "generalist_post_pl": _rounded_number(generalist_post_pl),
        "generalist_checkpoint_pl": _rounded_number(generalist_checkpoint_pl),
        "selected_post_pl": _rounded_number(selected_post_pl),
        "selected_post_trades": _checkpoint_window_number(
            selected_result,
            window_key,
            "post_trade_count",
        ),
        "generalist_post_trades": _checkpoint_window_number(
            observer_result,
            window_key,
            "post_trade_count",
        ),
        "switch_pl": _rounded_number(switch_pl),
        "switch_delta_vs_generalist": _rounded_number(
            selected_post_pl - generalist_post_pl
        ),
        "checkpoint_best_preset": checkpoint_best_name,
        "checkpoint_best_preset_id": checkpoint_best_preset_id,
        "checkpoint_best_post_pl": _rounded_number(checkpoint_best_post_pl),
        "checkpoint_best_switch_pl": _rounded_number(checkpoint_best_switch_pl),
        "switch_correct": bool(
            selected_preset_id and selected_preset_id == checkpoint_best_preset_id
        ),
        "switch_cost_dollars": _rounded_number(
            checkpoint_best_switch_pl - switch_pl
        ),
    }


def _shadow_router_switch_update_from_decision(
    current_decision: dict[str, Any],
    selected_result: dict[str, Any] | None,
) -> dict[str, Any]:
    window_minutes = current_decision.get("window_minutes")
    if window_minutes is None:
        return {}
    window_key = str(window_minutes)
    generalist_pre_pl = (
        _decimal_from_value(current_decision.get("generalist_pre_pl"))
        or Decimal("0")
    )
    generalist_post_pl = (
        _decimal_from_value(current_decision.get("generalist_post_pl"))
        or Decimal("0")
    )
    selected_post_pl = _checkpoint_window_decimal(
        selected_result,
        window_key,
        "post_pl",
    )
    switch_pl = generalist_pre_pl + selected_post_pl
    checkpoint_best_switch_pl = (
        _decimal_from_value(current_decision.get("checkpoint_best_switch_pl"))
        or Decimal("0")
    )
    selected_preset_id = selected_result.get("preset_id") if selected_result else None
    checkpoint_best_preset_id = _optional_text(
        current_decision.get("checkpoint_best_preset_id")
    )
    return {
        "selected_post_pl": _rounded_number(selected_post_pl),
        "selected_post_trades": _checkpoint_window_number(
            selected_result,
            window_key,
            "post_trade_count",
        ),
        "switch_pl": _rounded_number(switch_pl),
        "switch_delta_vs_generalist": _rounded_number(
            selected_post_pl - generalist_post_pl
        ),
        "switch_correct": bool(
            selected_preset_id and selected_preset_id == checkpoint_best_preset_id
        ),
        "switch_cost_dollars": _rounded_number(
            checkpoint_best_switch_pl - switch_pl
        ),
    }


def _shadow_router_authority_update_from_decision(
    current_decision: dict[str, Any],
    authority_result: dict[str, Any] | None,
) -> dict[str, Any]:
    window_minutes = current_decision.get("window_minutes")
    if window_minutes is None:
        return {}
    window_key = str(window_minutes)
    generalist_pre_pl = (
        _decimal_from_value(current_decision.get("generalist_pre_pl"))
        or Decimal("0")
    )
    generalist_post_pl = (
        _decimal_from_value(current_decision.get("generalist_post_pl"))
        or Decimal("0")
    )
    authority_post_pl = _checkpoint_window_decimal(
        authority_result,
        window_key,
        "post_pl",
    )
    authority_pl = generalist_pre_pl + authority_post_pl
    checkpoint_best_switch_pl = (
        _decimal_from_value(current_decision.get("checkpoint_best_switch_pl"))
        or Decimal("0")
    )
    authority_preset_id = (
        authority_result.get("preset_id") if authority_result else None
    )
    checkpoint_best_preset_id = _optional_text(
        current_decision.get("checkpoint_best_preset_id")
    )
    return {
        "authority_post_pl": _rounded_number(authority_post_pl),
        "authority_post_trades": _checkpoint_window_number(
            authority_result,
            window_key,
            "post_trade_count",
        ),
        "authority_pl": _rounded_number(authority_pl),
        "authority_delta_vs_generalist": _rounded_number(
            authority_post_pl - generalist_post_pl
        ),
        "authority_correct": bool(
            authority_preset_id and authority_preset_id == checkpoint_best_preset_id
        ),
        "authority_cost_dollars": _rounded_number(
            checkpoint_best_switch_pl - authority_pl
        ),
    }


def _shadow_router_authority_decision(
    *,
    decision: dict[str, Any],
    observer_result: dict[str, Any],
    role_presets: dict[str, dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    checkpoint = _optional_text(decision.get("checkpoint")) or ""
    raw_role = _optional_text(decision.get("selected_role")) or "generalist"
    raw_confidence = _optional_text(decision.get("router_confidence")) or "LOW"
    fingerprint = decision.get("fingerprint") if isinstance(decision.get("fingerprint"), dict) else {}
    source_return = _float_from_value(
        fingerprint.get("source_open_to_current_percent")
    )
    source_drawdown = _float_from_value(
        fingerprint.get("source_max_drawdown_from_open_percent")
    )
    transitions_per_hour = _float_from_value(fingerprint.get("transitions_per_hour"))
    trend_trust = _float_from_value(fingerprint.get("trend_trust_avg"))
    avg_regime_minutes = _float_from_value(
        fingerprint.get("avg_regime_duration_minutes")
    )
    reasons: list[str] = []

    def authority_payload(
        *,
        action: str,
        role: str,
        preset: dict[str, Any],
        reason: str,
        enabled: bool,
    ) -> dict[str, Any]:
        result = _result_by_preset_id(
            results,
            decision["date"],
            preset["id"],
        )
        if result is None and preset["id"] == observer_result.get("preset_id"):
            result = observer_result
        return {
            "authority_model": "v6_0945_high_confidence_with_rebound_block",
            "authority_enabled": enabled,
            "authority_action": action,
            "authority_role": role,
            "authority_preset": preset["name"],
            "authority_version": preset["version"],
            "authority_reason": reason,
            **_shadow_router_authority_update_from_decision(decision, result),
        }

    generalist_preset = role_presets["generalist"]

    if checkpoint != "09:45":
        return authority_payload(
            action="LOG_ONLY",
            role="generalist",
            preset=generalist_preset,
            reason="v6 authority is limited to the 09:45 checkpoint; later checkpoints are logged for research only.",
            enabled=False,
        )

    if raw_role == "generalist":
        return authority_payload(
            action="GENERALIST_DEFAULT",
            role="generalist",
            preset=generalist_preset,
            reason="09:45 did not clear a specialist threshold.",
            enabled=True,
        )

    if raw_confidence != "HIGH":
        return authority_payload(
            action="ADVISORY_ONLY",
            role="generalist",
            preset=generalist_preset,
            reason=(
                f"09:45 {raw_role} signal was {raw_confidence}; v6 only grants "
                "authority to HIGH-confidence specialist calls."
            ),
            enabled=True,
        )

    extreme_early_selloff = (
        raw_role == "inverse"
        and source_return is not None
        and source_return <= -7
        and source_drawdown is not None
        and source_drawdown <= -7
    )
    if extreme_early_selloff:
        return authority_payload(
            action="BLOCKED_REVIEW",
            role="generalist",
            preset=generalist_preset,
            reason=(
                "Extreme 09:45 selloff is quarantined for human review; "
                "research split between May 18 false-positive and May 27 correct "
                "Inverse mitigation."
            ),
            enabled=True,
        )

    inverse_flush_rebound_risk = (
        raw_role == "inverse"
        and source_return is not None
        and source_drawdown is not None
        and source_return - source_drawdown >= 1.5
    )
    if inverse_flush_rebound_risk:
        rebound_gap = source_return - source_drawdown
        return authority_payload(
            action="BLOCKED_REVIEW",
            role="generalist",
            preset=generalist_preset,
            reason=(
                "09:45 Inverse signal already bounced materially from the early "
                f"drawdown ({rebound_gap:g} percentage points); v6 blocks "
                "automatic Inverse because the panic evidence may have expired."
            ),
            enabled=True,
        )

    sustained_bear_false_positive_risk = (
        raw_role == "inverse"
        and source_drawdown is not None
        and source_drawdown <= -7
        and (transitions_per_hour is None or transitions_per_hour <= 3)
        and trend_trust is not None
        and trend_trust >= 60
        and avg_regime_minutes is not None
        and avg_regime_minutes >= 13
    )
    if sustained_bear_false_positive_risk:
        return authority_payload(
            action="BLOCKED_REVIEW",
            role="generalist",
            preset=generalist_preset,
            reason=(
                "Large downside tape has stable, trusted structure; v6 blocks "
                "automatic Inverse because this resembles the sustained-bear "
                "false-positive family."
            ),
            enabled=True,
        )

    authority_preset = role_presets.get(raw_role, generalist_preset)
    reasons.append(
        f"09:45 {raw_role} signal is HIGH confidence and no v6 block fired."
    )
    return authority_payload(
        action="ROUTE",
        role=raw_role,
        preset=authority_preset,
        reason=" ".join(reasons),
        enabled=True,
    )


def _shadow_router_decision(
    *,
    date_summary: dict[str, Any],
    checkpoint: dict[str, Any],
    observer_result: dict[str, Any],
    role_presets: dict[str, dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    date_text = date_summary["date"]
    window_key = str(checkpoint["window_minutes"])
    fingerprint = observer_result.get("early_windows", {}).get(window_key) or {}
    pick = _shadow_router_pick(fingerprint)
    selected_preset = role_presets[pick["role"]]
    selected_result = _result_by_preset_id(results, date_text, selected_preset["id"])
    winner_id = f"{date_summary['winner']}::{date_summary['winner_version']}"
    selected_pl = (
        _decimal_from_value(selected_result["row"].get("realized_pl_dollars"))
        if selected_result
        else Decimal("0")
    ) or Decimal("0")
    selected_pct = (
        _decimal_from_value(selected_result["row"].get("account_change_percent"))
        if selected_result
        else Decimal("0")
    ) or Decimal("0")
    winner_pl = _decimal_from_value(date_summary.get("winner_pl")) or Decimal("0")
    winner_pct = (
        _decimal_from_value(date_summary.get("winner_account_change_percent"))
        or Decimal("0")
    )
    cost_dollars = winner_pl - selected_pl
    cost_percent = winner_pct - selected_pct
    correct = selected_preset["id"] == winner_id
    switch_context = _shadow_router_switch_context(
        date_text=date_text,
        window_key=window_key,
        observer_result=observer_result,
        selected_result=selected_result,
        results=results,
    )
    return {
        "date": date_text,
        "checkpoint": checkpoint["label"],
        "window_minutes": checkpoint["window_minutes"],
        "observer_preset": observer_result["preset_name"],
        "selected_role": pick["role"],
        "selected_preset": selected_preset["name"],
        "selected_version": selected_preset["version"],
        "selected_pl": _rounded_number(selected_pl),
        "selected_account_change_percent": _rounded_number(selected_pct),
        "winner": date_summary["winner"],
        "winner_version": date_summary["winner_version"],
        "winner_pl": date_summary["winner_pl"],
        "winner_account_change_percent": date_summary[
            "winner_account_change_percent"
        ],
        "eventual_winner_confidence": date_summary["winner_confidence"],
        "router_confidence": pick["confidence"],
        "correct": correct,
        "cost_dollars": _rounded_number(cost_dollars),
        "cost_percent": _rounded_number(cost_percent),
        "fingerprint": fingerprint,
        "reasons": pick["reasons"],
        **switch_context,
    }


def _shadow_router_allows_persistence_override(
    persisted_decision: dict[str, Any],
    current_decision: dict[str, Any],
) -> bool:
    persisted_role = _optional_text(persisted_decision.get("selected_role"))
    current_role = _optional_text(current_decision.get("selected_role"))
    if not persisted_role or not current_role:
        return True
    if current_role == persisted_role:
        return True
    return (
        current_role != "generalist"
        and _optional_text(current_decision.get("router_confidence")) == "HIGH"
    )


def _shadow_router_persist_decision(
    *,
    current_decision: dict[str, Any],
    persisted_decision: dict[str, Any],
    role_presets: dict[str, dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    date_text = current_decision["date"]
    persisted_role = _optional_text(persisted_decision.get("selected_role"))
    if not persisted_role or persisted_role not in role_presets:
        return current_decision
    selected_preset = role_presets[persisted_role]
    selected_result = _result_by_preset_id(results, date_text, selected_preset["id"])
    selected_pl = (
        _decimal_from_value(selected_result["row"].get("realized_pl_dollars"))
        if selected_result
        else Decimal("0")
    ) or Decimal("0")
    selected_pct = (
        _decimal_from_value(selected_result["row"].get("account_change_percent"))
        if selected_result
        else Decimal("0")
    ) or Decimal("0")
    winner_id = f"{current_decision['winner']}::{current_decision['winner_version']}"
    winner_pl = _decimal_from_value(current_decision.get("winner_pl")) or Decimal("0")
    winner_pct = (
        _decimal_from_value(current_decision.get("winner_account_change_percent"))
        or Decimal("0")
    )
    persisted_name = selected_preset["name"]
    current_name = _optional_text(current_decision.get("selected_preset")) or "--"
    current_confidence = (
        _optional_text(current_decision.get("router_confidence")) or "--"
    )
    reasons = [
        (
            f"Retained 09:45 HIGH-confidence {persisted_name} bias; "
            f"current raw pick was {current_name} ({current_confidence})."
        ),
        *list(current_decision.get("reasons") or []),
    ]
    switch_updates = _shadow_router_switch_update_from_decision(
        current_decision,
        selected_result,
    )
    return {
        **current_decision,
        "selected_role": persisted_role,
        "selected_preset": persisted_name,
        "selected_version": selected_preset["version"],
        "selected_pl": _rounded_number(selected_pl),
        "selected_account_change_percent": _rounded_number(selected_pct),
        "router_confidence": "HIGH",
        "persistence_applied": True,
        "correct": selected_preset["id"] == winner_id,
        "cost_dollars": _rounded_number(winner_pl - selected_pl),
        "cost_percent": _rounded_number(winner_pct - selected_pct),
        "reasons": reasons,
        **switch_updates,
    }


def _shadow_router_checkpoint_summaries(
    decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for checkpoint in SHADOW_ROUTER_CHECKPOINTS:
        rows = [
            row
            for row in decisions
            if row["window_minutes"] == checkpoint["window_minutes"]
        ]
        total = len(rows)
        correct = sum(1 for row in rows if row["correct"])
        switch_correct = sum(1 for row in rows if row.get("switch_correct"))
        selected_pl = sum(
            (_decimal_from_value(row.get("selected_pl")) or Decimal("0"))
            for row in rows
        )
        winner_pl = sum(
            (_decimal_from_value(row.get("winner_pl")) or Decimal("0"))
            for row in rows
        )
        total_cost = sum(
            (_decimal_from_value(row.get("cost_dollars")) or Decimal("0"))
            for row in rows
        )
        switch_pl = sum(
            (_decimal_from_value(row.get("switch_pl")) or Decimal("0"))
            for row in rows
        )
        generalist_checkpoint_pl = sum(
            (_decimal_from_value(row.get("generalist_checkpoint_pl")) or Decimal("0"))
            for row in rows
        )
        checkpoint_best_switch_pl = sum(
            (_decimal_from_value(row.get("checkpoint_best_switch_pl")) or Decimal("0"))
            for row in rows
        )
        switch_cost = sum(
            (_decimal_from_value(row.get("switch_cost_dollars")) or Decimal("0"))
            for row in rows
        )
        high_confidence_rows = [
            row for row in rows if row.get("router_confidence") == "HIGH"
        ]
        summaries.append(
            {
                "checkpoint": checkpoint["label"],
                "window_minutes": checkpoint["window_minutes"],
                "dates": total,
                "correct": correct,
                "accuracy_percent": round(correct / total * 100, 2) if total else 0,
                "switch_correct": switch_correct,
                "switch_accuracy_percent": (
                    round(switch_correct / total * 100, 2) if total else 0
                ),
                "high_confidence_count": len(high_confidence_rows),
                "switch_total_pl": _rounded_number(switch_pl),
                "generalist_checkpoint_total_pl": _rounded_number(
                    generalist_checkpoint_pl
                ),
                "switch_delta_vs_generalist_total": _rounded_number(
                    switch_pl - generalist_checkpoint_pl
                ),
                "checkpoint_best_total_pl": _rounded_number(
                    checkpoint_best_switch_pl
                ),
                "switch_total_cost_dollars": _rounded_number(switch_cost),
                "avg_switch_cost_dollars": _rounded_number(
                    switch_cost / Decimal(total or 1)
                ),
                "selected_total_pl": _rounded_number(selected_pl),
                "winner_total_pl": _rounded_number(winner_pl),
                "total_cost_dollars": _rounded_number(total_cost),
                "avg_cost_dollars": _rounded_number(
                    total_cost / Decimal(total or 1)
                ),
            }
        )
    return summaries


def _shadow_router_authority_summary(
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = [
        row
        for row in decisions
        if row.get("checkpoint") == "09:45" and row.get("authority_enabled")
    ]
    total = len(rows)
    authority_pl = sum(
        (_decimal_from_value(row.get("authority_pl")) or Decimal("0"))
        for row in rows
    )
    generalist_pl = sum(
        (_decimal_from_value(row.get("generalist_checkpoint_pl")) or Decimal("0"))
        for row in rows
    )
    best_pl = sum(
        (_decimal_from_value(row.get("checkpoint_best_switch_pl")) or Decimal("0"))
        for row in rows
    )
    authority_cost = sum(
        (_decimal_from_value(row.get("authority_cost_dollars")) or Decimal("0"))
        for row in rows
    )
    correct = sum(1 for row in rows if row.get("authority_correct"))
    action_counts: dict[str, int] = {}
    for row in rows:
        action = _optional_text(row.get("authority_action")) or "UNKNOWN"
        action_counts[action] = action_counts.get(action, 0) + 1
    return {
        "checkpoint": "09:45",
        "dates": total,
        "correct": correct,
        "accuracy_percent": round(correct / total * 100, 2) if total else 0,
        "authority_total_pl": _rounded_number(authority_pl),
        "generalist_total_pl": _rounded_number(generalist_pl),
        "authority_delta_vs_generalist": _rounded_number(
            authority_pl - generalist_pl
        ),
        "best_switch_total_pl": _rounded_number(best_pl),
        "authority_total_cost_dollars": _rounded_number(authority_cost),
        "avg_authority_cost_dollars": _rounded_number(
            authority_cost / Decimal(total or 1)
        ),
        "routes": action_counts.get("ROUTE", 0),
        "blocked": action_counts.get("BLOCKED_REVIEW", 0),
        "advisory_only": action_counts.get("ADVISORY_ONLY", 0),
        "generalist_default": action_counts.get("GENERALIST_DEFAULT", 0),
        "action_counts": action_counts,
    }


def run_research_shadow_router_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = run_research_comparison_from_payload(payload)
    dates = comparison["dates"]
    presets = _parse_research_compare_presets(payload)
    role_presets = _shadow_router_role_presets(presets)
    observer_preset = role_presets["generalist"]
    results = comparison["results"]
    decisions: list[dict[str, Any]] = []
    for date_summary in comparison["date_summaries"]:
        observer_result = _result_by_preset_id(
            results,
            date_summary["date"],
            observer_preset["id"],
        )
        if not observer_result:
            continue
        persisted_decision: dict[str, Any] | None = None
        for checkpoint in SHADOW_ROUTER_CHECKPOINTS:
            decision = _shadow_router_decision(
                date_summary=date_summary,
                checkpoint=checkpoint,
                observer_result=observer_result,
                role_presets=role_presets,
                results=results,
            )
            if (
                checkpoint["label"] == "09:45"
                and decision["selected_role"] != "generalist"
                and decision["router_confidence"] == "HIGH"
            ):
                persisted_decision = decision
            elif persisted_decision and not _shadow_router_allows_persistence_override(
                persisted_decision,
                decision,
            ):
                decision = _shadow_router_persist_decision(
                    current_decision=decision,
                    persisted_decision=persisted_decision,
                    role_presets=role_presets,
                    results=results,
                )
            decision = {
                **decision,
                **_shadow_router_authority_decision(
                    decision=decision,
                    observer_result=observer_result,
                    role_presets=role_presets,
                    results=results,
                ),
            }
            decisions.append(decision)

    checkpoint_summaries = _shadow_router_checkpoint_summaries(decisions)
    authority_summary = _shadow_router_authority_summary(decisions)
    best_checkpoint = sorted(
        checkpoint_summaries,
        key=lambda row: (
            _decimal_from_value(row.get("switch_total_pl")) or Decimal("0"),
            _decimal_from_value(row.get("switch_accuracy_percent")) or Decimal("0"),
        ),
        reverse=True,
    )[0] if checkpoint_summaries else None
    return {
        **comparison,
        "kind": "shadow_router",
        "observer_preset": observer_preset["name"],
        "role_presets": {
            role: {
                "preset_name": preset["name"],
                "preset_version": preset["version"],
            }
            for role, preset in role_presets.items()
        },
        "checkpoints": list(SHADOW_ROUTER_CHECKPOINTS),
        "decisions": decisions,
        "checkpoint_summaries": checkpoint_summaries,
        "authority_summary": authority_summary,
        "best_checkpoint": best_checkpoint,
        "research_note": (
            "Shadow router replay is research-only. The legacy proxy compares "
            "whole-day selected preset results; switch scoring uses Generalist "
            "pre-checkpoint closed P/L plus selected-preset trades opened at or "
            "after the checkpoint."
        ),
        "dates": dates,
    }


def _extract_session_context(
    records: list[dict[str, Any]],
    log_date: str,
    lifecycle_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not records:
        return {}

    first = records[0]
    last = records[-1]

    transitions = []
    for r in records:
        t = r.get("regime_transition")
        if t:
            transitions.append({
                "at": _to_ny_time(r["timestamp"]),
                "from": t["from"],
                "to": t["to"],
            })

    trades = _extract_lifecycle_trade_actions(lifecycle_records or [], log_date)
    if not trades:
        trades = _extract_cycle_trade_actions(records)

    error_records = [r for r in records if r.get("error")]
    error_samples = [
        {
            "at": _to_ny_time(r["timestamp"]),
            "cycle": r.get("cycle_id"),
            "error": str(r.get("error", ""))[:200],
        }
        for r in error_records[:8]
    ]

    prices = []
    for r in records:
        try:
            prices.append(float(r["source_price"]))
        except (TypeError, ValueError, KeyError):
            pass
    price_range = (
        f"${min(prices):.2f} – ${max(prices):.2f}" if prices else "N/A"
    )

    perf = next(
        (r.get("performance") for r in reversed(records) if r.get("performance")),
        None,
    )
    session_metrics = _session_metrics_summary(
        records,
        lifecycle_records or [],
        log_date,
    )
    trend_trust = next(
        (r.get("trend_trust") for r in reversed(records) if r.get("trend_trust")),
        None,
    )
    last_config = last.get("config", {})
    market_was_open = any(bool(r.get("market_open")) for r in records)

    return {
        "session": {
            "date": log_date,
            "start": _to_ny_time(first["timestamp"]),
            "end": _to_ny_time(last["timestamp"]),
            "total_cycles": len(records),
        },
        "config": {
            "directional_mode": last_config.get("directional_mode"),
            "dry_run": last_config.get("dry_run"),
            "position_notional": f"${last_config.get('position_notional', '?')}",
        },
        "market": {
            "symbol": "SOXL",
            "price_range": price_range,
            "initial_regime": first.get("regime", "UNKNOWN"),
            "was_open": market_was_open,
        },
        "regime_transitions": transitions,
        "trades": trades,
        "error_count": len(error_records),
        "error_samples": error_samples,
        "performance": perf,
        "session_metrics": session_metrics,
        "final_state": {
            "portfolio_value": last.get("portfolio_value") or last.get("account_value"),
            "buying_power": last.get("buying_power"),
            "open_position": last.get("position_symbol"),
            "trend_trust": trend_trust,
        },
    }


def _trade_size_text(trade: dict[str, Any]) -> str:
    notional = _optional_text(trade.get("notional"))
    if notional:
        return f"notional={notional}"
    qty = _optional_text(trade.get("qty"))
    if qty:
        return f"qty={qty}"
    return "size=unknown"


def _trade_price_text(trade: dict[str, Any]) -> str:
    price = _optional_text(trade.get("price"))
    return f" @ ${price}" if price else ""


def _summary_counts_text(items: Any, limit: int = 4) -> str:
    if not isinstance(items, list) or not items:
        return "none"
    parts = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        count = item.get("count")
        if name is not None and count is not None:
            parts.append(f"{name}={count}")
    return ", ".join(parts) if parts else "none"


def _display_date_text(date_text: str) -> str:
    try:
        parsed = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return date_text
    return f"{MONTH_NAMES[parsed.month - 1]} {parsed.day} {parsed.year}"


def _display_date_label(date_label: str) -> str:
    if " to " not in date_label:
        return _display_date_text(date_label)
    start, end = date_label.split(" to ", 1)
    return f"{_display_date_text(start)} to {_display_date_text(end)}"


def _narrative_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _narrative_bot_performance(value: Any) -> dict[str, str]:
    result = {bot: "" for bot in NARRATIVE_BOTS}
    if isinstance(value, dict):
        for key, item in value.items():
            bot = str(key)
            result[bot] = _narrative_text(item)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                bot = _narrative_text(item.get("bot") or item.get("name"))
                summary = _narrative_text(
                    item.get("summary")
                    or item.get("blurb")
                    or item.get("performance")
                    or item.get("text")
                )
                if bot:
                    result[bot] = summary
            elif item:
                result.setdefault("Overall", "")
                result["Overall"] = " ".join(
                    part for part in (result["Overall"], _narrative_text(item)) if part
                )
    elif value:
        result["Overall"] = _narrative_text(value)
    return {bot: summary for bot, summary in result.items() if summary or bot in NARRATIVE_BOTS}


def _extract_json_object_text(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return stripped


def _empty_narrative_sections() -> dict[str, Any]:
    return {
        "tldr": "",
        "highlight": "",
        "bot_performance": {bot: "" for bot in NARRATIVE_BOTS},
        "market_conditions": "",
        "operational_issues": "",
        "analysis": "",
        "bottom_line": "",
    }


def _parse_narrative_response(raw: str) -> dict[str, Any]:
    cleaned = _extract_json_object_text(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        sections = _empty_narrative_sections()
        sections["bottom_line"] = cleaned.strip()
        return sections
    if not isinstance(parsed, dict):
        sections = _empty_narrative_sections()
        sections["bottom_line"] = raw.strip()
        return sections

    sections = _empty_narrative_sections()
    sections["tldr"] = _narrative_text(parsed.get("tldr") or parsed.get("tl_dr"))
    sections["highlight"] = _narrative_text(parsed.get("highlight"))
    sections["bot_performance"] = _narrative_bot_performance(
        parsed.get("bot_performance") or parsed.get("botPerformance")
    )
    sections["market_conditions"] = _narrative_text(
        parsed.get("market_conditions") or parsed.get("marketConditions")
    )
    sections["operational_issues"] = _narrative_text(
        parsed.get("operational_issues") or parsed.get("operationalIssues")
    )
    sections["analysis"] = _narrative_text(parsed.get("analysis"))
    sections["bottom_line"] = _narrative_text(
        parsed.get("bottom_line") or parsed.get("bottomLine")
    )
    return sections


def _build_summary_prompt(context: dict[str, Any]) -> str:
    session = context.get("session", {})
    config = context.get("config", {})
    market = context.get("market", {})
    transitions = context.get("regime_transitions", [])
    trades = context.get("trades", [])
    error_count = context.get("error_count", 0)
    error_samples = context.get("error_samples", [])
    performance = context.get("performance")
    metrics = context.get("session_metrics")
    final = context.get("final_state", {})

    mode = (
        "DRY RUN (simulated, no real orders)"
        if config.get("dry_run")
        else "PAPER LIVE (orders sent to Alpaca paper account)"
    )
    market_status = (
        "OPEN (regular trading day)"
        if market.get("was_open")
        else "CLOSED (weekend or holiday — no trades possible)"
    )

    parts = [
        "You are the debrief assistant for EdgeWalker, an autonomous semiconductor trading bot.",
        "",
        "EdgeWalker classifies the SOXL market regime and routes to specialist bots:",
        "  MomentumBot — buys SOXL when the trend is up",
        "  InverseBot — buys SOXS when the trend is down",
        "  ChopBot — buys SOXL at a discount to the slow SMA when the market is sideways",
        "",
        f"SESSION: {session.get('date')} | {session.get('start')} – {session.get('end')} ET",
        f"MARKET: {market_status}",
        f"CYCLES: {session.get('total_cycles')} | MODE: {mode}",
        f"POSITION SIZE: {config.get('position_notional')} | DIRECTIONAL MODE: {config.get('directional_mode')}",
        f"SOXL PRICE RANGE: {market.get('price_range')} | OPENING REGIME: {market.get('initial_regime')}",
        "",
    ]

    if isinstance(metrics, dict):
        trend_metrics = metrics.get("trend_trust")
        trend_metrics = trend_metrics if isinstance(trend_metrics, dict) else {}
        parts.append("SESSION METRICS:")
        parts.append(
            f"  Regime transitions: {metrics.get('regime_transition_count')} | "
            f"Stale bar cycles: {metrics.get('stale_bar_cycles')} | "
            f"Backfill repairs: {metrics.get('backfill_repair_cycles')}"
        )
        parts.append(
            "  Exits: "
            f"route_invalidated={metrics.get('route_invalidation_exit_count')} | "
            f"trailing_stop={metrics.get('trailing_stop_exit_count')}"
        )
        parts.append(
            "  Adaptive posture counts: "
            f"{_summary_counts_text(metrics.get('adaptive_posture_counts'))}"
        )
        parts.append(
            "  Top entry blocks: "
            f"{_summary_counts_text(metrics.get('top_entry_blocks'))}"
        )
        parts.append(
            "  Trend Trust observations: "
            f"{trend_metrics.get('observations')} | "
            f"avg_score={trend_metrics.get('average_score')} | "
            f"avg_age={trend_metrics.get('average_regime_age_minutes')}m | "
            f"labels={_summary_counts_text(trend_metrics.get('label_counts'))}"
        )
        parts.append("")

    if transitions:
        parts.append(f"REGIME CHANGES ({len(transitions)}):")
        for t in transitions:
            parts.append(f"  {t['at']} — {t['from']} → {t['to']}")
        parts.append("")

    if trades:
        buys = [t for t in trades if t["action"] == "BUY"]
        sells = [t for t in trades if t["action"] == "SELL"]
        parts.append(f"TRADE ACTIONS — {len(buys)} entries, {len(sells)} exits:")
        for t in trades:
            if t["action"] == "BUY":
                parts.append(
                    f"  {t['at']} BUY  {t.get('symbol')}{_trade_price_text(t)}"
                    f"  {_trade_size_text(t)}  bot={t.get('bot')}"
                )
            else:
                parts.append(
                    f"  {t['at']} SELL {t.get('symbol')}{_trade_price_text(t)}"
                    f"  reason={t.get('reason')}  bot={t.get('bot')}"
                    f"  {_trade_size_text(t)}"
                )
        parts.append("")
    else:
        parts.append("TRADE ACTIONS: None executed this session.")
        parts.append("")

    if error_count:
        parts.append(f"ERRORS / REJECTIONS ({error_count} total):")
        for e in error_samples:
            parts.append(f"  {e['at']} (cycle {e['cycle']}): {e['error']}")
        parts.append("")

    if performance:
        parts.append("REALIZED PERFORMANCE (from lifecycle ledger):")
        parts.append(f"  Session P/L: {performance.get('session_realized_pl')}")
        parts.append(
            "  Reconciliation confidence: "
            f"{performance.get('reconciliation_confidence')}"
        )
        parts.append(f"  Closed trades: {performance.get('session_trade_count')}")
        parts.append(
            f"  Wins/Losses: {performance.get('session_wins')}/{performance.get('session_losses')}"
        )
        bot_sections = _ledger_bot_performance_sections(performance)
        if bot_sections:
            parts.append("  Bot performance source of truth:")
            for bot, text in bot_sections.items():
                parts.append(f"    {bot}: {text}")
        parts.append("")

    trend_trust = final.get("trend_trust")
    if isinstance(trend_trust, dict):
        parts.append("TREND TRUST (shadow telemetry):")
        parts.append(
            f"  Score: {trend_trust.get('score')} "
            f"({trend_trust.get('label')})"
        )
        parts.append(
            f"  Age: {trend_trust.get('regime_age_minutes')}m | "
            f"Flips 60m: {trend_trust.get('recent_flip_count_60m')} | "
            f"Efficiency: {trend_trust.get('directional_efficiency')}"
        )
        parts.append("")

    pv = final.get("portfolio_value")
    pos = final.get("open_position")
    if pv is not None:
        parts.append("SESSION END:")
        parts.append(f"  Portfolio value: ${pv}")
        parts.append(f"  Open position: {pos or 'None (flat)'}")
        parts.append("")

    parts += [
        "---",
        "Return valid JSON only. Do not use markdown. Do not include any text outside the JSON object.",
        "Use exactly these keys:",
        "{",
        '  "tldr": "One very brief one-sentence summary.",',
        '  "highlight": "What was especially noteworthy for this session.",',
        '  "bot_performance": {',
        '    "MomentumBot": "Short behavior/performance blurb.",',
        '    "ChopBot": "Short behavior/performance blurb.",',
        '    "InverseBot": "Short behavior/performance blurb."',
        "  },",
        '  "market_conditions": "How the market behaved: trend/range, price action, regime churn.",',
        '  "operational_issues": "Errors, rejections, stale data, missing data, or none noted.",',
        '  "analysis": "Cautious operator-facing tuning ideas, or say evidence is too thin to recommend changes.",',
        '  "bottom_line": "Plain-English judgment of how the session went overall."',
        "}",
        "",
        "The REALIZED PERFORMANCE section is the source of truth for trade counts, wins/losses, bot P/L, and bot-level summaries.",
        "Do not recount trade actions or invent bot statistics. Use the exact bot performance facts provided above.",
        "Be direct and operator-facing. If exact bot-level P/L is not available, say what can be inferred from behavior and do not invent profitability.",
        "For analysis, do not claim optimal settings. Recommend parameter changes only when repeated evidence supports them; otherwise suggest what to watch next session.",
    ]

    return "\n".join(parts)


def _call_openai(prompt: str, api_key: str) -> str:
    payload = json.dumps({
        "model": OPENAI_DEFAULT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 700,
        "temperature": 0.4,
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENAI_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise BotError(f"OpenAI API error {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise BotError(f"OpenAI connection error: {exc.reason}") from exc


def _load_narrative_cache() -> dict[str, Any]:
    if not NARRATIVE_CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(NARRATIVE_CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_narrative_cache(cache: dict[str, Any]) -> None:
    NARRATIVE_CACHE_PATH.write_text(
        json.dumps(cache, indent=2),
        encoding="utf-8",
    )


def _narrative_cache_key(
    timeframe: str,
    date_label: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    if timeframe == "1D":
        return f"1D:{date_label}"
    if timeframe == "CUSTOM":
        return f"CUSTOM:{start_date or ''}:{end_date or ''}"
    return f"{timeframe}:{start_date or ''}:{end_date or ''}:{date_label}"


def _narrative_cache_signature(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _one_day_summary_signature(
    records: list[dict[str, Any]],
    context: dict[str, Any],
) -> str:
    first = records[0] if records else {}
    last = records[-1] if records else {}
    performance = context.get("performance")
    return _narrative_cache_signature(
        {
            "grounding_version": NARRATIVE_GROUNDING_VERSION,
            "cycle_count": len(records),
            "first_timestamp": first.get("timestamp"),
            "last_timestamp": last.get("timestamp"),
            "last_cycle_id": last.get("cycle_id"),
            "session_realized_pl": (
                performance.get("session_realized_pl")
                if isinstance(performance, dict)
                else None
            ),
            "session_trade_count": (
                performance.get("session_trade_count")
                if isinstance(performance, dict)
                else None
            ),
        }
    )


def _period_summary_signature(context: dict[str, Any]) -> str:
    days = context.get("days")
    day_signatures = []
    if isinstance(days, list):
        for day in days:
            if not isinstance(day, dict):
                continue
            session = day.get("session")
            performance = day.get("performance")
            day_signatures.append(
                {
                    "date": (
                        session.get("date") if isinstance(session, dict) else None
                    ),
                    "cycle_count": (
                        session.get("total_cycles")
                        if isinstance(session, dict)
                        else None
                    ),
                    "end": session.get("end") if isinstance(session, dict) else None,
                    "session_realized_pl": (
                        performance.get("session_realized_pl")
                        if isinstance(performance, dict)
                        else None
                    ),
                    "session_trade_count": (
                        performance.get("session_trade_count")
                        if isinstance(performance, dict)
                        else None
                    ),
                }
            )
    return _narrative_cache_signature(
        {
            "day_count": context.get("day_count"),
            "total_cycles": context.get("total_cycles"),
            "total_trades": context.get("total_trades"),
            "days": day_signatures,
        }
    )


def _cached_narrative_summary(
    cache_key: str,
    signature: str,
) -> dict[str, Any] | None:
    cache = _load_narrative_cache()
    entry = cache.get(cache_key)
    if not isinstance(entry, dict) or entry.get("signature") != signature:
        return None
    summary = entry.get("summary")
    if not isinstance(summary, dict):
        return None
    cached = dict(summary)
    cached["cached"] = True
    cached["available"] = True
    return cached


def _store_narrative_summary(
    cache_key: str,
    signature: str,
    summary: dict[str, Any],
) -> None:
    cache = _load_narrative_cache()
    cache[cache_key] = {
        "signature": signature,
        "saved_at": now_iso(),
        "summary": summary,
    }
    _save_narrative_cache(cache)


def _summary_cache_miss_payload(
    *,
    timeframe: str,
    date_label: str,
    display_date: str,
    cycle_count: int,
) -> dict[str, Any]:
    return {
        "available": False,
        "cached": False,
        "timeframe": timeframe,
        "date": date_label,
        "display_date": display_date,
        "cycle_count": cycle_count,
    }


def _date_range_for_timeframe(timeframe: str) -> tuple[str, str]:
    from datetime import date as _date
    today = datetime.now(NY_TZ).date()
    if timeframe == "1W":
        start = today - timedelta(days=7)
    elif timeframe == "1M":
        start = today - timedelta(days=30)
    elif timeframe == "3M":
        start = today - timedelta(days=90)
    elif timeframe == "YTD":
        start = _date(today.year, 1, 1)
    else:  # MAX
        start = _date(2000, 1, 1)
    return start.isoformat(), today.isoformat()


def _validate_log_date(value: str, field_name: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise BotError(f"{field_name} must use YYYY-MM-DD format.") from exc
    return value


def _resolve_custom_date_range(
    start_date: str | None,
    end_date: str | None,
) -> tuple[str, str]:
    start = _optional_text(start_date)
    end = _optional_text(end_date)
    if not start and not end:
        raise BotError("Custom summaries require a start date or end date.")
    start = start or end
    end = end or start
    start = _validate_log_date(start, "Start date")
    end = _validate_log_date(end, "End date")
    if start > end:
        raise BotError("Start date must be on or before end date.")
    return start, end


def _find_log_files_in_range(start_date: str, end_date: str) -> list[Path]:
    files = []
    for path in sorted(LOGS_ROOT.glob("edgewalker-*.jsonl")):
        date_str = path.stem[len("edgewalker-"):]
        if start_date <= date_str <= end_date:
            files.append(path)
    return files


def _extract_period_context(
    log_files: list[Path],
    lifecycle_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    days: list[dict[str, Any]] = []
    total_cycles = 0
    total_trades = 0
    total_errors = 0
    for log_path in log_files:
        date_str = log_path.stem[len("edgewalker-"):]
        records = _load_log_records(log_path)
        if not records:
            continue
        ctx = _extract_session_context(records, date_str, lifecycle_records)
        days.append(ctx)
        total_cycles += len(records)
        total_trades += len(ctx.get("trades", []))
        total_errors += ctx.get("error_count", 0)
    return {
        "day_count": len(days),
        "total_cycles": total_cycles,
        "total_trades": total_trades,
        "total_errors": total_errors,
        "days": days,
    }


def _build_period_prompt(
    context: dict[str, Any],
    timeframe: str,
    date_range: tuple[str, str],
) -> str:
    days = context.get("days", [])
    start, end = date_range
    period_label = f"{start} to {end}" if start != end else start

    parts = [
        "You are the debrief assistant for EdgeWalker, an autonomous semiconductor trading bot.",
        "",
        "EdgeWalker classifies the SOXL market regime and routes to specialist bots:",
        "  MomentumBot — buys SOXL when the trend is up",
        "  InverseBot — buys SOXS when the trend is down",
        "  ChopBot — buys SOXL at a discount to the slow SMA when the market is sideways",
        "",
        f"PERIOD: {period_label} ({timeframe}) | {context['day_count']} day(s) with log data",
        f"TOTAL CYCLES: {context['total_cycles']} | TOTAL TRADES: {context['total_trades']}"
        f" | TOTAL ERRORS: {context['total_errors']}",
        "",
        "DAY-BY-DAY:",
    ]

    for day in days:
        session = day.get("session", {})
        trades = day.get("trades", [])
        transitions = day.get("regime_transitions", [])
        errors = day.get("error_count", 0)
        perf = day.get("performance")
        config = day.get("config", {})
        market = day.get("market", {})

        buys = len([t for t in trades if t.get("action") == "BUY"])
        sells = len([t for t in trades if t.get("action") == "SELL"])
        mode = "DRY RUN" if config.get("dry_run") else "PAPER LIVE"
        market_open = market.get("was_open", False)
        market_tag = "MARKET OPEN" if market_open else "MARKET CLOSED (weekend/holiday)"
        regime_chain = " → ".join(
            f"{t['from']}→{t['to']}" for t in transitions
        ) if transitions else "no changes"
        pl_str = (
            f" | P/L: {perf['session_realized_pl']}"
            if perf and perf.get("session_realized_pl")
            else ""
        )
        if market_open:
            parts.append(
                f"  {session.get('date', '?')} [{mode}] | {market_tag}"
                f" | {session.get('total_cycles', '?')} cycles"
                f" | SOXL {market.get('price_range', '?')}"
                f" | Trades: {buys}B/{sells}S | Errors: {errors}{pl_str}"
                f" | Regimes: {regime_chain[:100]}"
            )
        else:
            parts.append(
                f"  {session.get('date', '?')} [{mode}] | {market_tag}"
                f" | {session.get('total_cycles', '?')} warmup cycles only — no trading possible"
            )

    parts += [
        "",
        "---",
        "Return valid JSON only. Do not use markdown. Do not include any text outside the JSON object.",
        "Use exactly these keys:",
        "{",
        '  "tldr": "One very brief one-sentence summary.",',
        '  "highlight": "What was especially noteworthy for this period.",',
        '  "bot_performance": {',
        '    "MomentumBot": "Short behavior/performance blurb.",',
        '    "ChopBot": "Short behavior/performance blurb.",',
        '    "InverseBot": "Short behavior/performance blurb."',
        "  },",
        '  "market_conditions": "How the market behaved across the period.",',
        '  "operational_issues": "Errors, rejections, stale data, missing data, or none noted.",',
        '  "analysis": "Cautious operator-facing tuning ideas, or say evidence is too thin to recommend changes.",',
        '  "bottom_line": "Plain-English judgment of how the period went overall."',
        "}",
        "",
        "Be direct and operator-facing. If exact bot-level P/L is not available, say what can be inferred from behavior and do not invent profitability.",
        "For analysis, do not claim optimal settings. Recommend parameter changes only when repeated evidence supports them; otherwise suggest what to watch next session.",
    ]
    return "\n".join(parts)


def generate_session_summary(
    date: str | None = None,
    timeframe: str = "1D",
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    force: bool = False,
    cache_only: bool = False,
) -> dict[str, Any]:
    if timeframe not in VALID_TIMEFRAMES:
        raise BotError(
            f"Invalid timeframe. Must be one of: {', '.join(sorted(VALID_TIMEFRAMES))}"
        )

    if timeframe == "1D":
        target_date, log_path = _resolve_1d_log_path(date)
        records = _load_log_records(log_path)
        if not records:
            raise BotError(f"Session log for {target_date} is empty.")
        context = _extract_session_context(
            records,
            target_date,
            LifecycleLedger().read_all(),
        )
        cache_key = _narrative_cache_key("1D", target_date)
        signature = _one_day_summary_signature(records, context)
        if not force:
            cached = _cached_narrative_summary(cache_key, signature)
            if cached is not None:
                return cached
        if cache_only:
            return _summary_cache_miss_payload(
                timeframe="1D",
                date_label=target_date,
                display_date=_display_date_label(target_date),
                cycle_count=len(records),
            )

        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise BotError(
                "OPENAI_API_KEY is not configured. Add it to your .env file."
            )
        prompt = _build_summary_prompt(context)
        raw_narrative = _call_openai(prompt, api_key)
        narrative_sections = _ground_narrative_sections(
            _parse_narrative_response(raw_narrative),
            context,
        )
        summary = {
            "available": True,
            "cached": False,
            "timeframe": "1D",
            "summary": raw_narrative,
            "narrative": narrative_sections,
            "date": target_date,
            "display_date": _display_date_label(target_date),
            "cycle_count": len(records),
            "generated_at": now_iso(),
        }
        _store_narrative_summary(cache_key, signature, summary)
        return summary

    # Multi-day and custom timeframes
    if timeframe == "CUSTOM":
        start_date, end_date = _resolve_custom_date_range(start_date, end_date)
    else:
        start_date, end_date = _date_range_for_timeframe(timeframe)
    log_files = _find_log_files_in_range(start_date, end_date)
    if not log_files:
        raise BotError(
            f"No session logs found for {timeframe} ({start_date} to {end_date})."
        )
    context = _extract_period_context(log_files, LifecycleLedger().read_all())
    if not context["days"]:
        raise BotError(f"No usable session data found for {timeframe}.")
    actual_start = context["days"][0]["session"]["date"]
    actual_end = context["days"][-1]["session"]["date"]
    date_label = (
        f"{actual_start} to {actual_end}" if actual_start != actual_end else actual_start
    )
    cache_key = _narrative_cache_key(
        timeframe,
        date_label,
        start_date=start_date,
        end_date=end_date,
    )
    signature = _period_summary_signature(context)
    if not force:
        cached = _cached_narrative_summary(cache_key, signature)
        if cached is not None:
            return cached
    if cache_only:
        return _summary_cache_miss_payload(
            timeframe=timeframe,
            date_label=date_label,
            display_date=_display_date_label(date_label),
            cycle_count=int(context["total_cycles"] or 0),
        )

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise BotError(
            "OPENAI_API_KEY is not configured. Add it to your .env file."
        )
    prompt = _build_period_prompt(context, timeframe, (start_date, end_date))
    raw_narrative = _call_openai(prompt, api_key)
    summary = {
        "available": True,
        "cached": False,
        "timeframe": timeframe,
        "summary": raw_narrative,
        "narrative": _parse_narrative_response(raw_narrative),
        "date": date_label,
        "display_date": _display_date_label(date_label),
        "cycle_count": context["total_cycles"],
        "generated_at": now_iso(),
    }
    _store_narrative_summary(cache_key, signature, summary)
    return summary


def build_summary_prompt(
    date: str | None = None,
    timeframe: str = "1D",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Return the raw prompt that would be sent to OpenAI, without calling it."""
    if timeframe not in VALID_TIMEFRAMES:
        raise BotError(
            f"Invalid timeframe. Must be one of: {', '.join(sorted(VALID_TIMEFRAMES))}"
        )

    if timeframe == "1D":
        target_date, log_path = _resolve_1d_log_path(date)
        records = _load_log_records(log_path)
        if not records:
            raise BotError(f"Session log for {target_date} is empty.")
        context = _extract_session_context(
            records,
            target_date,
            LifecycleLedger().read_all(),
        )
        prompt = _build_summary_prompt(context)
        return {
            "timeframe": timeframe,
            "date": target_date,
            "display_date": _display_date_label(target_date),
            "prompt": prompt,
        }

    if timeframe == "CUSTOM":
        start_date, end_date = _resolve_custom_date_range(start_date, end_date)
    else:
        start_date, end_date = _date_range_for_timeframe(timeframe)
    log_files = _find_log_files_in_range(start_date, end_date)
    if not log_files:
        raise BotError(
            f"No session logs found for {timeframe} ({start_date} to {end_date})."
        )
    context = _extract_period_context(log_files, LifecycleLedger().read_all())
    if not context["days"]:
        raise BotError(f"No usable session data found for {timeframe}.")
    prompt = _build_period_prompt(context, timeframe, (start_date, end_date))
    actual_start = context["days"][0]["session"]["date"]
    actual_end = context["days"][-1]["session"]["date"]
    date_label = (
        f"{actual_start} to {actual_end}" if actual_start != actual_end else actual_start
    )
    return {
        "timeframe": timeframe,
        "date": date_label,
        "display_date": _display_date_label(date_label),
        "prompt": prompt,
    }


def _is_allowed_ui_origin(origin: str | None) -> bool:
    return origin in ALLOWED_UI_ORIGINS


def _is_allowed_ui_referer(referer: str | None) -> bool:
    if not referer:
        return True
    return any(
        referer == origin or referer.startswith(f"{origin}/")
        for origin in ALLOWED_UI_ORIGINS
    )


class AppHandler(BaseHTTPRequestHandler):
    runner: BotRunner

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_common_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/api/status":
            self.send_json(asdict(self.runner.snapshot()))
            return
        if self.path == "/api/settings":
            self.require_local_ui_request()
            self.send_json(alpaca_environment_settings())
            return

        self.serve_static()

    def do_POST(self) -> None:
        try:
            payload = self.read_json()
            if self.path == "/api/settings":
                self.require_local_ui_request()
                self.send_json(save_alpaca_environment_settings(payload))
                return
            if self.path == "/api/settings/test":
                self.require_local_ui_request()
                environment = str(payload.get("environment", "paper"))
                self.send_json(test_alpaca_connection(environment))
                return
            if self.path == "/api/notifications/test":
                self.require_local_ui_request("notification test requests")
                self.send_json(self.runner.send_test_notification())
                return
            if self.path == "/api/spreadsheet/row":
                self.require_local_ui_request("operator spreadsheet requests")
                self.send_json(
                    build_operator_spreadsheet_daily_row(
                        _optional_text(payload.get("date")),
                        operator_notes=_optional_text(payload.get("operator_notes"))
                        or "",
                        include_daily_narrative=_payload_bool(
                            payload.get("include_daily_narrative")
                            if payload.get("include_daily_narrative") is not None
                            else payload.get("includeDailyNarrative"),
                            default=False,
                        ),
                    )
                )
                return
            if self.path == "/api/spreadsheet/post":
                self.require_local_ui_request("operator spreadsheet requests")
                self.send_json(post_operator_spreadsheet_daily_row(payload))
                return
            if self.path == "/api/research/run":
                self.require_local_ui_request("research backtest requests")
                if self.runner.snapshot().running:
                    raise BotError("Stop the live/paper loop before running research.")
                self.send_json(run_research_backtest_from_payload(payload))
                return
            if self.path == "/api/research/compare":
                self.require_local_ui_request("research comparison requests")
                if self.runner.snapshot().running:
                    raise BotError("Stop the live/paper loop before running research.")
                self.send_json(run_research_comparison_from_payload(payload))
                return
            if self.path == "/api/research/dress-rehearsal":
                self.require_local_ui_request("research dress rehearsal requests")
                if self.runner.snapshot().running:
                    raise BotError("Stop the live/paper loop before running research.")
                self.send_json(run_roster_dress_rehearsal_from_payload(payload))
                return
            if self.path == "/api/research/shadow-router":
                self.require_local_ui_request("research shadow router requests")
                if self.runner.snapshot().running:
                    raise BotError("Stop the live/paper loop before running research.")
                self.send_json(run_research_shadow_router_from_payload(payload))
                return
            if self.path == "/api/live-arm":
                self.require_local_ui_request()
                confirmation = str(payload.get("confirmation", ""))
                self.send_json(set_live_trading_armed(confirmation))
                return
            if self.path == "/api/live-disarm":
                self.require_local_ui_request()
                self.send_json(set_live_trading_disarmed())
                return
            if self.path == "/api/summary":
                self.require_local_ui_request("AI narrative requests")
                date_str = _optional_text(payload.get("date"))
                timeframe = str(payload.get("timeframe", "1D")).strip().upper()
                start_date = _optional_text(
                    payload.get("start_date") or payload.get("startDate")
                )
                end_date = _optional_text(
                    payload.get("end_date") or payload.get("endDate")
                )
                force = _payload_bool(payload.get("force"), default=False)
                self.send_json(
                    generate_session_summary(
                        date_str,
                        timeframe,
                        start_date=start_date,
                        end_date=end_date,
                        force=force,
                    )
                )
                return
            if self.path == "/api/summary/cache":
                self.require_local_ui_request("AI narrative requests")
                date_str = _optional_text(payload.get("date"))
                timeframe = str(payload.get("timeframe", "1D")).strip().upper()
                start_date = _optional_text(
                    payload.get("start_date") or payload.get("startDate")
                )
                end_date = _optional_text(
                    payload.get("end_date") or payload.get("endDate")
                )
                self.send_json(
                    generate_session_summary(
                        date_str,
                        timeframe,
                        start_date=start_date,
                        end_date=end_date,
                        cache_only=True,
                    )
                )
                return
            if self.path == "/api/prompt":
                self.require_local_ui_request("AI narrative requests")
                date_str = _optional_text(payload.get("date"))
                timeframe = str(payload.get("timeframe", "1D")).strip().upper()
                start_date = _optional_text(
                    payload.get("start_date") or payload.get("startDate")
                )
                end_date = _optional_text(
                    payload.get("end_date") or payload.get("endDate")
                )
                self.send_json(
                    build_summary_prompt(
                        date_str,
                        timeframe,
                        start_date=start_date,
                        end_date=end_date,
                    )
                )
                return
            if self.path == "/api/start":
                config = config_from_payload(payload)
                snapshot = self.runner.start(
                    config,
                    preset_authority_plan_from_payload(payload, config),
                )
            elif self.path == "/api/stop":
                snapshot = self.runner.stop()
            elif self.path == "/api/run-once":
                config = config_from_payload(payload)
                snapshot = self.runner.run_once(
                    config,
                    preset_authority_plan_from_payload(payload, config),
                )
            else:
                self.send_json({"error": "Not found"}, status=404)
                return
            self.send_json(asdict(snapshot))
        except BotError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except json.JSONDecodeError:
            self.send_json({"error": "Invalid JSON"}, status=400)
        except Exception as exc:
            traceback.print_exc()
            self.send_json({"error": f"Internal server error: {exc}"}, status=500)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise BotError("JSON body must be an object")
        return data

    def require_local_ui_request(self, label: str = "Local app requests") -> None:
        origin = self.headers.get("Origin")
        referer = self.headers.get("Referer")
        if origin and not _is_allowed_ui_origin(origin):
            raise BotError(f"{label} must come from the local EdgeWalker UI.")
        if not origin and not _is_allowed_ui_referer(referer):
            raise BotError(f"{label} must come from the local EdgeWalker UI.")

    def serve_static(self) -> None:
        route = urllib.parse.unquote(self.path.split("?", 1)[0])
        if route == "/":
            route = "/index.html"

        is_asset_route = route.startswith("/assets/")
        root = ASSETS_ROOT if is_asset_route else WEB_ROOT
        if is_asset_route:
            relative_route = route.removeprefix("/assets/")
        else:
            relative_route = route.lstrip("/")

        path = (root / relative_route).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            self.send_json({"error": "Not found"}, status=404)
            return

        if not path.is_file():
            self.send_json({"error": "Not found"}, status=404)
            return

        content = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_common_headers()
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_common_headers()
        self.end_headers()
        self.wfile.write(content)

    def send_common_headers(self) -> None:
        origin = self.headers.get("Origin")
        if _is_allowed_ui_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    AppHandler.runner = BotRunner()
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Alpaca Bot UI running at http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        AppHandler.runner.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
