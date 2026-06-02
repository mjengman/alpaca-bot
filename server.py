#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import mimetypes
import os
import re
import threading
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
    DATA_BASE_URL_DEFAULT,
    EdgeWalkerBot,
    INVERSE_BOT,
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
    parse_clock_time,
)
from market_data import StreamingMarketDataService


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_ROOT = PROJECT_ROOT / "web"
ASSETS_ROOT = PROJECT_ROOT / "assets"
HOST = "127.0.0.1"
PORT = 8765
ACTIVITY_PATH = PROJECT_ROOT / ".bot_activity.json"
OPERATOR_SPREADSHEET_POST_STATE_PATH = PROJECT_ROOT / ".operator_spreadsheet_posts.json"
NARRATIVE_CACHE_PATH = PROJECT_ROOT / ".narrative_cache.json"
ENV_PATH = PROJECT_ROOT / ".env"
LOGS_ROOT = PROJECT_ROOT / "logs"
NY_TZ = ZoneInfo("America/New_York")
BOT_PERFORMANCE_ORDER = (MOMENTUM_BOT, CHOP_BOT, INVERSE_BOT)
NARRATIVE_GROUNDING_VERSION = "ledger-grounded-v2"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
VALID_TIMEFRAMES = {"1D", "1W", "1M", "3M", "YTD", "MAX", "CUSTOM"}
OPERATOR_SPREADSHEET_COLUMNS = [
    "date",
    "mode",
    "starting_account_value",
    "ending_account_value",
    "realized_pl_dollars",
    "account_change_percent",
    "account_result_status",
    "closed_trades",
    "wins",
    "losses",
    "momentum_pl",
    "chop_pl",
    "inverse_pl",
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
    "reconciliation_confidence",
    "config_version",
    "strategy_version",
    "symbol_primary",
    "symbol_inverse",
    "position_sizing_mode",
    "position_notional",
    "position_allocation_percent",
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
    "adaptive_shadow_enabled",
    "dry_run",
    "active_environment",
    "data_feed",
    "operator_notes",
    "daily_narrative",
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
    adaptive_shadow_enabled: bool
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

    def start(self, config: BotConfig) -> RunnerSnapshot:
        with self._lock:
            if self._running:
                return self._snapshot_locked()

            self._config = config
            self._market_data.ensure_running(config)
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
                args=(config, stop_event),
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

    def run_once(self, config: BotConfig) -> RunnerSnapshot:
        with self._lock:
            self._config = config
            self._market_data.ensure_running(config)
        self._run_cycle(config)
        return self.snapshot()

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

    def _run_cycle(self, config: BotConfig) -> None:
        output = io.StringIO()
        error: str | None = None
        edgewalker_status: dict[str, Any] | None = None
        broker_state = broker_constraint_payload(broker_constraint_ok())
        run_timestamp = datetime.now(timezone.utc)
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                self._market_data.ensure_running(config)
                status = EdgeWalkerBot(
                    config,
                    AlpacaClient(config),
                    market_data=self._market_data,
                ).run_once()
                edgewalker_status = asdict(status)
        except BotError as exc:
            error = str(exc)
            broker_state = self._broker_state_for_cycle_error(error, run_timestamp)
        except Exception as exc:  # Keep the local control server alive on surprises.
            error = f"{type(exc).__name__}: {exc}"
            broker_state = broker_constraint_payload(classify_broker_error(error))

        lines = [line for line in output.getvalue().splitlines() if line.strip()]
        if error:
            lines.append(f"[error] {error}")

        with self._lock:
            self._config = config
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
                config=config,
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
            adaptive_shadow_enabled=self._config.adaptive_shadow_enabled,
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
            last_error=self._last_error,
        )


def lifecycle_performance_summary(
    records: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    session_date = _ny_date_text(now)
    lots_by_symbol: dict[str, list[dict[str, Any]]] = {}
    realized_trades: list[dict[str, Any]] = []
    unmatched_exit_qty = Decimal("0")
    ignored_fill_count = 0

    for record in records:
        if record.get("event_type") not in {
            LIFECYCLE_PARTIAL_FILL,
            LIFECYCLE_FULL_FILL,
        }:
            continue
        created_at = _record_created_at(record)
        if created_at is None or _ny_date_text(created_at) != session_date:
            continue

        symbol = record.get("symbol")
        side = str(record.get("side") or "").lower()
        fill_qty = _record_decimal(record, "fill_delta_qty") or _record_decimal(
            record,
            "filled_qty",
        )
        fill_price = _record_decimal(record, "filled_avg_price")
        if not isinstance(symbol, str) or side not in {"buy", "sell"}:
            ignored_fill_count += 1
            continue
        if fill_qty is None or fill_qty <= 0 or fill_price is None:
            ignored_fill_count += 1
            continue

        if side == "buy":
            lots_by_symbol.setdefault(symbol, []).append(
                {
                    "qty": fill_qty,
                    "price": fill_price,
                    "bot": record.get("bot"),
                    "created_at": created_at,
                    "order_id": record.get("order_id"),
                }
            )
            continue

        remaining = fill_qty
        matched_qty = Decimal("0")
        cost_basis = Decimal("0")
        matched_lot_bots: list[tuple[str | None, Decimal]] = []
        lots = lots_by_symbol.setdefault(symbol, [])
        while remaining > 0 and lots:
            lot = lots[0]
            lot_qty = lot["qty"]
            consumed_qty = min(remaining, lot_qty)
            matched_qty += consumed_qty
            cost_basis += consumed_qty * lot["price"]
            matched_lot_bots.append((_optional_text(lot.get("bot")), consumed_qty))
            remaining -= consumed_qty
            lot["qty"] = lot_qty - consumed_qty
            if lot["qty"] <= 0:
                lots.pop(0)

        if matched_qty <= 0:
            unmatched_exit_qty += remaining
            continue

        unmatched_exit_qty += max(remaining, Decimal("0"))
        proceeds = matched_qty * fill_price
        realized_pl = proceeds - cost_basis
        avg_entry_price = cost_basis / matched_qty
        realized_pl_percent = (
            realized_pl / cost_basis * Decimal("100")
            if cost_basis > 0
            else None
        )
        realized_trades.append(
            {
                "symbol": symbol,
                "bot": _optional_text(record.get("bot"))
                or _dominant_bot(matched_lot_bots),
                "qty": format_decimal(matched_qty),
                "avg_entry_price": format_decimal(avg_entry_price),
                "exit_price": format_decimal(fill_price),
                "realized_pl": format_decimal(realized_pl),
                "realized_pl_percent": (
                    format_decimal(realized_pl_percent)
                    if realized_pl_percent is not None
                    else None
                ),
                "exit_reason": record.get("reason"),
                "exit_order_id": record.get("order_id"),
                "closed_at": created_at.astimezone(timezone.utc).isoformat(
                    timespec="seconds"
                ),
            }
        )

    total_realized = sum(
        (
            _record_decimal(trade, "realized_pl") or Decimal("0")
            for trade in realized_trades
        ),
        Decimal("0"),
    )
    open_qty = sum(
        (lot["qty"] for lots in lots_by_symbol.values() for lot in lots),
        Decimal("0"),
    )
    open_cost_basis = sum(
        (lot["qty"] * lot["price"] for lots in lots_by_symbol.values() for lot in lots),
        Decimal("0"),
    )
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
        unmatched_exit_qty,
        ignored_fill_count,
    )

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
        "open_lot_qty": format_decimal(open_qty),
        "open_lot_cost_basis": format_decimal(open_cost_basis),
        "unmatched_exit_qty": format_decimal(unmatched_exit_qty),
        "ignored_fill_count": ignored_fill_count,
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

    return [_bot_performance_payload(aggregates[bot]) for bot in order]


def _blank_bot_performance(bot: str) -> dict[str, Any]:
    return {
        "bot": bot,
        "realized_pl_value": Decimal("0"),
        "trade_count": 0,
        "wins": 0,
        "losses": 0,
        "last_trade": None,
    }


def _bot_performance_payload(aggregate: dict[str, Any]) -> dict[str, Any]:
    trade_count = int(aggregate["trade_count"])
    wins = int(aggregate["wins"])
    losses = int(aggregate["losses"])
    last_trade = aggregate.get("last_trade")
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
        "adaptive_shadow_enabled": config.adaptive_shadow_enabled,
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
    aliases: tuple[str, ...] = (),
) -> Decimal:
    raw = payload_value(payload, key, str(fallback), aliases)
    try:
        value = Decimal(str(raw))
    except InvalidOperation as exc:
        raise BotError(f"{key} must be a valid number") from exc
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
        adaptive_shadow_enabled=adaptive_shadow_enabled,
        position_sizing_mode=position_sizing_mode,
        position_allocation_percent=position_allocation_percent,
        position_notional=decimal_from_payload(
            payload, "positionNotional", base.position_notional
        ),
        trail_percent=decimal_from_payload(payload, "trailPercent", base.trail_percent),
        fast_sma_minutes=fast_sma,
        slow_sma_minutes=slow_sma,
    )


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
    lots_by_symbol: dict[str, list[dict[str, Any]]] = {}
    realized_trades: list[dict[str, Any]] = []

    for record in lifecycle_records:
        if record.get("event_type") not in {
            LIFECYCLE_PARTIAL_FILL,
            LIFECYCLE_FULL_FILL,
        }:
            continue
        created_at = _record_created_at(record)
        if created_at is None or _ny_date_text(created_at) != log_date:
            continue

        symbol = record.get("symbol")
        side = str(record.get("side") or "").lower()
        fill_qty = _record_decimal(record, "fill_delta_qty") or _record_decimal(
            record,
            "filled_qty",
        )
        fill_price = _record_decimal(record, "filled_avg_price")
        if not isinstance(symbol, str) or side not in {"buy", "sell"}:
            continue
        if fill_qty is None or fill_qty <= 0 or fill_price is None:
            continue

        if side == "buy":
            lots_by_symbol.setdefault(symbol, []).append(
                {
                    "qty": fill_qty,
                    "price": fill_price,
                    "bot": record.get("bot"),
                    "created_at": created_at,
                    "order_id": record.get("order_id"),
                }
            )
            continue

        remaining = fill_qty
        matched_qty = Decimal("0")
        cost_basis = Decimal("0")
        matched_lot_bots: list[tuple[str | None, Decimal]] = []
        lots = lots_by_symbol.setdefault(symbol, [])
        while remaining > 0 and lots:
            lot = lots[0]
            lot_qty = lot["qty"]
            consumed_qty = min(remaining, lot_qty)
            matched_qty += consumed_qty
            cost_basis += consumed_qty * lot["price"]
            matched_lot_bots.append((_optional_text(lot.get("bot")), consumed_qty))
            remaining -= consumed_qty
            lot["qty"] = lot_qty - consumed_qty
            if lot["qty"] <= 0:
                lots.pop(0)

        if matched_qty <= 0:
            continue

        proceeds = matched_qty * fill_price
        realized_pl = proceeds - cost_basis
        avg_entry_price = cost_basis / matched_qty
        realized_pl_percent = (
            realized_pl / cost_basis * Decimal("100")
            if cost_basis > 0
            else None
        )
        realized_trades.append(
            {
                "symbol": symbol,
                "bot": _optional_text(record.get("bot"))
                or _dominant_bot(matched_lot_bots),
                "qty": format_decimal(matched_qty),
                "avg_entry_price": format_decimal(avg_entry_price),
                "exit_price": format_decimal(fill_price),
                "realized_pl": format_decimal(realized_pl),
                "realized_pl_percent": (
                    format_decimal(realized_pl_percent)
                    if realized_pl_percent is not None
                    else None
                ),
                "exit_reason": record.get("reason"),
                "exit_order_id": record.get("order_id"),
                "closed_at": created_at.astimezone(timezone.utc).isoformat(
                    timespec="seconds"
                ),
            }
        )

    return realized_trades


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

    lifecycle_records = LifecycleLedger().read_all()
    performance = lifecycle_performance_summary(
        lifecycle_records,
        datetime.fromisoformat(target_date).replace(tzinfo=NY_TZ),
    )
    session_metrics = _session_metrics_summary(records, lifecycle_records, target_date)
    realized_trades = _realized_trades_for_date(lifecycle_records, target_date)

    first = records[0]
    last = records[-1]
    last_config = last.get("config") if isinstance(last.get("config"), dict) else {}
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
        "starting_account_value": _rounded_number(starting_account),
        "ending_account_value": _rounded_number(ending_account),
        "realized_pl_dollars": _rounded_number(realized_pl),
        "account_change_percent": _rounded_number(account_change_percent),
        "account_result_status": result_status,
        "closed_trades": int(performance.get("session_trade_count") or 0),
        "wins": int(performance.get("session_wins") or 0),
        "losses": int(performance.get("session_losses") or 0),
        "momentum_pl": _rounded_number(bot_pl.get(MOMENTUM_BOT)),
        "chop_pl": _rounded_number(bot_pl.get(CHOP_BOT)),
        "inverse_pl": _rounded_number(bot_pl.get(INVERSE_BOT)),
        "top_pl_bot": _top_pl_bot(bot_pl),
        "bottom_pl_bot": _bottom_pl_bot(bot_pl),
        "regime_transitions": int(
            session_metrics.get("regime_transition_count") or 0
        ),
        "cycles": len(records),
        "stale_cycles": int(session_metrics.get("stale_bar_cycles") or 0),
        "stream_error_cycles": sum(
            1
            for record in records
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
        "adaptive_shadow_enabled": bool(
            last_config.get("adaptive_shadow_enabled", False)
        ),
        "dry_run": bool(last_config.get("dry_run", False)),
        "active_environment": _config_snapshot_text(
            last_config,
            "active_environment",
            current_alpaca_environment(),
        ),
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
                snapshot = self.runner.start(config_from_payload(payload))
            elif self.path == "/api/stop":
                snapshot = self.runner.stop()
            elif self.path == "/api/run-once":
                snapshot = self.runner.run_once(config_from_payload(payload))
            else:
                self.send_json({"error": "Not found"}, status=404)
                return
            self.send_json(asdict(snapshot))
        except BotError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except json.JSONDecodeError:
            self.send_json({"error": "Invalid JSON"}, status=400)

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
