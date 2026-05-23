#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import mimetypes
import os
import threading
import urllib.error
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
    EdgeWalkerBot,
    INVERSE_BOT,
    LIFECYCLE_FULL_FILL,
    LIFECYCLE_ORDER_ACCEPTED,
    LIFECYCLE_ORDER_REJECTED,
    LIFECYCLE_ORDER_SUBMITTED,
    LIFECYCLE_PARTIAL_FILL,
    LifecycleLedger,
    MOMENTUM_BOT,
    DIRECTIONAL_MODES,
    POSITION_SIZING_MODES,
    REGIME_STRENGTHS,
    SOXL,
    SOXS,
    broker_constraint_ok,
    broker_constraint_payload,
    classify_broker_error,
    format_decimal,
    load_dotenv,
    parse_clock_time,
)
from market_data import StreamingMarketDataService


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_ROOT = PROJECT_ROOT / "web"
HOST = "127.0.0.1"
PORT = 8765
ACTIVITY_PATH = PROJECT_ROOT / ".bot_activity.json"
LOGS_ROOT = PROJECT_ROOT / "logs"
NY_TZ = ZoneInfo("America/New_York")
BOT_PERFORMANCE_ORDER = (MOMENTUM_BOT, CHOP_BOT, INVERSE_BOT)
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
VALID_TIMEFRAMES = {"1D", "1W", "1M", "3M", "YTD", "MAX"}
ALLOWED_UI_ORIGINS = {
    f"http://{HOST}:{PORT}",
    f"http://localhost:{PORT}",
}


@dataclass
class RunnerSnapshot:
    running: bool
    symbol: str
    dry_run: bool
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
        self._config = BotConfig.from_env()
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
        self._last_error: str | None = None
        self._market_idle_logged_for: str | None = None
        self._last_regime: str | None = None

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
        market_data_status = self._market_data.status(
            SOXL,
            required_bars=self._config.slow_sma_minutes,
        )
        lifecycle_records = LifecycleLedger().read_all()
        return RunnerSnapshot(
            running=self._running,
            symbol=self._config.symbol,
            dry_run=self._config.dry_run,
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

    return {
        "source": "position_lifecycle",
        "session_date": session_date,
        "session_realized_pl": format_decimal(total_realized),
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
    }


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
        "reason": _optional_text(record.get("reason")),
        "filled_qty": _optional_text(record.get("filled_qty")),
        "fill_delta_qty": _optional_text(record.get("fill_delta_qty")),
        "filled_avg_price": _optional_text(record.get("filled_avg_price")),
        "error": _optional_text(record.get("error")),
    }


def _optional_text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


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
    return {
        "symbol": config.symbol,
        "dry_run": config.dry_run,
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
        "final_state": {
            "portfolio_value": last.get("portfolio_value") or last.get("account_value"),
            "buying_power": last.get("buying_power"),
            "open_position": last.get("position_symbol"),
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


def _build_summary_prompt(context: dict[str, Any]) -> str:
    session = context.get("session", {})
    config = context.get("config", {})
    market = context.get("market", {})
    transitions = context.get("regime_transitions", [])
    trades = context.get("trades", [])
    error_count = context.get("error_count", 0)
    error_samples = context.get("error_samples", [])
    performance = context.get("performance")
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
        parts.append(f"  Closed trades: {performance.get('session_trade_count')}")
        parts.append(
            f"  Wins/Losses: {performance.get('session_wins')}/{performance.get('session_losses')}"
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
        "Write a concise trading debrief for the operator. 3–4 short paragraphs covering:",
        "  1. Market conditions — how did SOXL trend? What regimes dominated?",
        "  2. Bot decisions — what entries/exits happened, and what was blocked?",
        "  3. Operational issues — any errors, rejections, or data problems worth noting?",
        "  4. Bottom line — how did the session go overall?",
        "",
        "Style: plain prose, operator-facing, direct. No bullet lists. No headers. No markdown formatting. No fluff.",
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
        f"PERIOD: {period_label} ({timeframe}) | {context['day_count']} trading day(s) with data",
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
        f"Write a concise trading debrief for the {timeframe} period. 3–5 short paragraphs covering:",
        "  1. Overall market conditions — what regimes dominated and how did SOXL move?",
        "  2. Bot behavior — what trades happened, what patterns or tendencies emerged?",
        "  3. Operational issues — any recurring errors, rejections, or anomalies worth noting?",
        "  4. Bottom line — how did the period go overall? Any trends the operator should watch?",
        "",
        "Style: plain prose, operator-facing, direct. No bullet lists. No headers."
        " No markdown formatting. No fluff.",
    ]
    return "\n".join(parts)


def generate_session_summary(
    date: str | None = None,
    timeframe: str = "1D",
) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise BotError(
            "OPENAI_API_KEY is not configured. Add it to your .env file."
        )

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
        narrative = _call_openai(prompt, api_key)
        return {
            "summary": narrative,
            "date": target_date,
            "cycle_count": len(records),
            "generated_at": now_iso(),
        }

    # Multi-day timeframes
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
    narrative = _call_openai(prompt, api_key)
    actual_start = context["days"][0]["session"]["date"]
    actual_end = context["days"][-1]["session"]["date"]
    date_label = (
        f"{actual_start} to {actual_end}" if actual_start != actual_end else actual_start
    )
    return {
        "summary": narrative,
        "date": date_label,
        "cycle_count": context["total_cycles"],
        "generated_at": now_iso(),
    }


def build_summary_prompt(
    date: str | None = None,
    timeframe: str = "1D",
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
        return {"timeframe": timeframe, "date": target_date, "prompt": prompt}

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
    return {"timeframe": timeframe, "date": date_label, "prompt": prompt}


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

        self.serve_static()

    def do_POST(self) -> None:
        try:
            payload = self.read_json()
            if self.path == "/api/summary":
                self.require_local_ai_request()
                date_str = _optional_text(payload.get("date"))
                timeframe = str(payload.get("timeframe", "1D")).strip().upper()
                self.send_json(generate_session_summary(date_str, timeframe))
                return
            if self.path == "/api/prompt":
                self.require_local_ai_request()
                date_str = _optional_text(payload.get("date"))
                timeframe = str(payload.get("timeframe", "1D")).strip().upper()
                self.send_json(build_summary_prompt(date_str, timeframe))
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

    def require_local_ai_request(self) -> None:
        origin = self.headers.get("Origin")
        referer = self.headers.get("Referer")
        if origin and not _is_allowed_ui_origin(origin):
            raise BotError("AI narrative requests must come from the local EdgeWalker UI.")
        if not origin and not _is_allowed_ui_referer(referer):
            raise BotError("AI narrative requests must come from the local EdgeWalker UI.")

    def serve_static(self) -> None:
        route = self.path.split("?", 1)[0]
        if route == "/":
            route = "/index.html"

        path = (WEB_ROOT / route.lstrip("/")).resolve()
        if not str(path).startswith(str(WEB_ROOT.resolve())) or not path.is_file():
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
