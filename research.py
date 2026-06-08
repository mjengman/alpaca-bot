from __future__ import annotations

import contextlib
import io
import json
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import bot as bot_module
from bot import (
    BotConfig,
    BotError,
    BotStateStore,
    EdgeWalkerBot,
    LifecycleLedger,
    MONEY_STEP,
    SOXL,
    SOXS,
    format_decimal,
    parse_market_timestamp,
)
from trade_metrics import (
    analyze_lifecycle_trades,
    bot_archaeology_report,
    enrich_trades_with_bar_extremes,
    trade_quality_averages,
)


NY_TZ = ZoneInfo("America/New_York")
RESEARCH_FILL_MODEL_NEXT_BAR_OPEN = "next_bar_open"
RESEARCH_FILL_MODELS = {RESEARCH_FILL_MODEL_NEXT_BAR_OPEN}


@dataclass(frozen=True)
class ResearchRunRequest:
    date: str
    data_feed: str
    fill_model: str = RESEARCH_FILL_MODEL_NEXT_BAR_OPEN
    slippage_bps: Decimal = Decimal("0")
    preset_name: str = "Current Controls"
    preset_version: str = "v1"
    starting_account_value: Decimal = Decimal("100000")


class _FrozenDateTime(datetime):
    _current: datetime = datetime.now(timezone.utc)

    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        value = cls._current
        if tz is not None:
            value = value.astimezone(tz)
        else:
            value = value.replace(tzinfo=None)
        return cls(
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
            tzinfo=value.tzinfo,
            fold=getattr(value, "fold", 0),
        )


@contextlib.contextmanager
def _patched_bot_time(current: datetime):
    previous = bot_module.datetime
    _FrozenDateTime._current = current.astimezone(timezone.utc)
    bot_module.datetime = _FrozenDateTime
    try:
        yield
    finally:
        bot_module.datetime = previous


def _validate_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise BotError("Backtest date must use YYYY-MM-DD format.") from exc
    return value


def _regular_session_bounds(date_text: str) -> tuple[datetime, datetime]:
    date = datetime.strptime(date_text, "%Y-%m-%d").date()
    start = datetime.combine(date, datetime.min.time(), NY_TZ).replace(
        hour=9,
        minute=30,
    )
    end = datetime.combine(date, datetime.min.time(), NY_TZ).replace(
        hour=16,
        minute=0,
    )
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def fetch_historical_bars(config: BotConfig, symbols: tuple[str, ...], date_text: str) -> dict[str, list[dict[str, Any]]]:
    start, end = _regular_session_bounds(date_text)
    params = {
        "symbols": ",".join(symbols),
        "timeframe": "1Min",
        "start": start.isoformat().replace("+00:00", "Z"),
        "end": end.isoformat().replace("+00:00", "Z"),
        "limit": "1000",
        "adjustment": "raw",
        "feed": config.data_feed,
        "sort": "asc",
    }
    bars_by_symbol: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in symbols}
    page_token: str | None = None

    while True:
        request_params = dict(params)
        if page_token:
            request_params["page_token"] = page_token
        url = f"{config.data_base_url}/stocks/bars?{urllib.parse.urlencode(request_params)}"
        request = urllib.request.Request(
            url,
            headers={
                "APCA-API-KEY-ID": config.api_key_id,
                "APCA-API-SECRET-KEY": config.api_secret_key,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise BotError(
                f"Historical bar request failed with HTTP {exc.code}: {details[:240]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise BotError(f"Historical bar request failed: {exc.reason}") from exc

        bars = payload.get("bars")
        if not isinstance(bars, dict):
            raise BotError(f"Unexpected historical bars response: {payload!r}")
        for symbol in symbols:
            symbol_bars = bars.get(symbol) or []
            if not isinstance(symbol_bars, list):
                raise BotError(f"Unexpected historical bars for {symbol}: {symbol_bars!r}")
            bars_by_symbol[symbol].extend(symbol_bars)
        page_token = payload.get("next_page_token")
        if not page_token:
            break

    for symbol in symbols:
        bars_by_symbol[symbol].sort(key=lambda bar: str(bar.get("t") or ""))
        if not bars_by_symbol[symbol]:
            raise BotError(f"No {symbol} historical bars found for {date_text}.")
    return bars_by_symbol


class ReplayMarketData:
    source_name = "research"

    def __init__(self, bars_by_symbol: dict[str, list[dict[str, Any]]], data_feed: str) -> None:
        self.bars_by_symbol = bars_by_symbol
        self.data_feed = data_feed
        self.current_index = 0

    def set_index(self, index: int) -> None:
        self.current_index = max(index, 0)

    def current_bar(self, symbol: str) -> dict[str, Any] | None:
        bars = self.bars_by_symbol.get(symbol) or []
        if self.current_index >= len(bars):
            return None
        return bars[self.current_index]

    def current_price(self, symbol: str) -> Decimal | None:
        bar = self.current_bar(symbol)
        if not bar:
            return None
        raw = bar.get("o") if bar.get("o") is not None else bar.get("c")
        if raw is None:
            return None
        return Decimal(str(raw))

    def get_recent_bars(self, symbol: str, minutes: int) -> list[dict[str, Any]]:
        bars = self.bars_by_symbol.get(symbol) or []
        visible = bars[: self.current_index]
        return visible[-minutes:]

    def get_latest_trade(self, symbol: str) -> dict[str, Any] | None:
        price = self.current_price(symbol)
        bar = self.current_bar(symbol)
        if price is None or not bar:
            return None
        return {"p": format_decimal(price), "t": bar.get("t")}

    def get_latest_quote(self, symbol: str) -> dict[str, Any] | None:
        price = self.current_price(symbol)
        bar = self.current_bar(symbol)
        if price is None or not bar:
            return None
        return {"bp": format_decimal(price), "ap": format_decimal(price), "t": bar.get("t")}

    def status(self, symbol: str, required_bars: int | None = None) -> dict[str, Any]:
        visible = self.bars_by_symbol.get(symbol, [])[: self.current_index]
        latest = visible[-1] if visible else None
        latest_time = parse_market_timestamp(latest.get("t")) if latest else None
        return {
            "data_source": "research",
            "data_feed": self.data_feed,
            "data_status": "LIVE" if len(visible) >= (required_bars or 1) else "WARMING_UP",
            "stream_connected": True,
            "stream_authenticated": True,
            "stream_subscribed": True,
            "stream_error": None,
            "stream_bar_count": len(visible),
            "stream_last_message_at": None,
            "latest_bar_time": (
                latest_time.isoformat().replace("+00:00", "Z") if latest_time else None
            ),
            "bar_age_seconds": 0 if latest_time else None,
            "latest_trade_time": self.current_bar(symbol).get("t") if self.current_bar(symbol) else None,
            "trade_age_seconds": 0 if self.current_bar(symbol) else None,
            "latest_quote_time": self.current_bar(symbol).get("t") if self.current_bar(symbol) else None,
            "quote_age_seconds": 0 if self.current_bar(symbol) else None,
        }


class SimulatedBroker:
    def __init__(
        self,
        config: BotConfig,
        market_data: ReplayMarketData,
        *,
        start: datetime,
        end: datetime,
        starting_account_value: Decimal,
        slippage_bps: Decimal,
    ) -> None:
        self.config = config
        self.market_data = market_data
        self.start = start
        self.end = end
        self.current_time = start
        self.starting_account_value = starting_account_value
        self.cash = starting_account_value
        self.positions: dict[str, dict[str, Decimal]] = {}
        self.orders: dict[str, dict[str, Any]] = {}
        self.order_count = 0
        self.slippage_bps = slippage_bps

    def set_time(self, current_time: datetime) -> None:
        self.current_time = current_time.astimezone(timezone.utc)

    def get_clock(self) -> dict[str, Any]:
        return {
            "is_open": self.start <= self.current_time < self.end,
            "next_open": self.start.isoformat().replace("+00:00", "Z"),
            "next_close": self.end.isoformat().replace("+00:00", "Z"),
        }

    def get_account(self) -> dict[str, Any]:
        equity = self._equity()
        return {
            "buying_power": format_decimal(max(self.cash, Decimal("0"))),
            "portfolio_value": format_decimal(equity),
            "equity": format_decimal(equity),
            "cash": format_decimal(self.cash),
            "last_equity": format_decimal(self.starting_account_value),
            "status": "ACTIVE",
        }

    def get_asset(self, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol, "fractionable": True}

    def list_open_orders(self) -> list[dict[str, Any]]:
        return []

    def get_order(self, order_id: str) -> dict[str, Any]:
        if order_id not in self.orders:
            raise BotError(f"Simulated order not found: {order_id}")
        return self.orders[order_id]

    def get_position(self, symbol: str) -> dict[str, Any] | None:
        lot = self.positions.get(symbol)
        if not lot or lot["qty"] <= 0:
            return None
        current_price = self._mark(symbol)
        qty = lot["qty"]
        avg_entry = lot["avg_entry_price"]
        market_value = qty * current_price
        unrealized_pl = (current_price - avg_entry) * qty
        unrealized_plpc = unrealized_pl / (avg_entry * qty) if avg_entry > 0 and qty > 0 else Decimal("0")
        return {
            "symbol": symbol,
            "qty": format_decimal(qty),
            "avg_entry_price": format_decimal(avg_entry),
            "current_price": format_decimal(current_price),
            "market_value": format_decimal(market_value),
            "unrealized_pl": format_decimal(unrealized_pl),
            "unrealized_plpc": format_decimal(unrealized_plpc),
        }

    def submit_market_buy(self, symbol: str, notional: Decimal) -> dict[str, Any]:
        price = self._fill_price(symbol, "buy")
        qty = (notional / price).quantize(Decimal("0.000000001"), rounding=ROUND_DOWN)
        if qty <= 0:
            raise BotError("Simulated buy quantity was zero.")
        self.cash -= qty * price
        existing = self.positions.get(symbol)
        if existing and existing["qty"] > 0:
            total_qty = existing["qty"] + qty
            total_cost = existing["avg_entry_price"] * existing["qty"] + price * qty
            existing["qty"] = total_qty
            existing["avg_entry_price"] = total_cost / total_qty
        else:
            self.positions[symbol] = {"qty": qty, "avg_entry_price": price}
        return self._filled_order(symbol, "buy", qty, price)

    def submit_market_buy_qty(self, symbol: str, qty: Decimal) -> dict[str, Any]:
        price = self._fill_price(symbol, "buy")
        notional = qty * price
        self.cash -= notional
        self.positions[symbol] = {"qty": qty, "avg_entry_price": price}
        return self._filled_order(symbol, "buy", qty, price)

    def submit_market_sell_qty(self, symbol: str, qty: Decimal) -> dict[str, Any]:
        lot = self.positions.get(symbol)
        if not lot or lot["qty"] <= 0:
            raise BotError(f"No simulated {symbol} position to sell.")
        qty = min(qty, lot["qty"]).quantize(Decimal("0.000000001"), rounding=ROUND_DOWN)
        price = self._fill_price(symbol, "sell")
        self.cash += qty * price
        lot["qty"] -= qty
        if lot["qty"] <= 0:
            del self.positions[symbol]
        return self._filled_order(symbol, "sell", qty, price)

    def _filled_order(self, symbol: str, side: str, qty: Decimal, price: Decimal) -> dict[str, Any]:
        self.order_count += 1
        order = {
            "id": f"research-{self.order_count}",
            "symbol": symbol,
            "side": side,
            "status": "filled",
            "filled_qty": format_decimal(qty),
            "filled_avg_price": format_decimal(price),
            "submitted_at": self.current_time.isoformat().replace("+00:00", "Z"),
            "filled_at": self.current_time.isoformat().replace("+00:00", "Z"),
        }
        self.orders[order["id"]] = order
        return order

    def _fill_price(self, symbol: str, side: str) -> Decimal:
        price = self._mark(symbol)
        adjustment = self.slippage_bps / Decimal("10000")
        if adjustment <= 0:
            return price
        if side == "buy":
            return price * (Decimal("1") + adjustment)
        return price * (Decimal("1") - adjustment)

    def _mark(self, symbol: str) -> Decimal:
        price = self.market_data.current_price(symbol)
        if price is None:
            raise BotError(f"No simulated mark for {symbol}.")
        return price

    def _equity(self) -> Decimal:
        total = self.cash
        for symbol, lot in self.positions.items():
            total += lot["qty"] * self._mark(symbol)
        return total.quantize(MONEY_STEP)


def _performance_from_lifecycle(
    records: list[dict[str, Any]],
    date_text: str,
    bars_by_symbol: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    analysis = analyze_lifecycle_trades(records, date_text, session_tz=NY_TZ)
    trades = analysis["realized_trades"]
    if bars_by_symbol is not None:
        trades = enrich_trades_with_bar_extremes(trades, bars_by_symbol)

    total = sum((Decimal(str(trade["realized_pl"])) for trade in trades), Decimal("0"))
    wins = sum(1 for trade in trades if Decimal(str(trade["realized_pl"])) > 0)
    losses = sum(1 for trade in trades if Decimal(str(trade["realized_pl"])) < 0)
    bot_items = []
    for bot_name in ("MomentumBot", "ChopBot", "InverseBot"):
        bot_trades = [trade for trade in trades if trade.get("bot") == bot_name]
        bot_pl = sum((Decimal(str(trade["realized_pl"])) for trade in bot_trades), Decimal("0"))
        bot_wins = sum(1 for trade in bot_trades if Decimal(str(trade["realized_pl"])) > 0)
        bot_losses = sum(1 for trade in bot_trades if Decimal(str(trade["realized_pl"])) < 0)
        win_rate = (
            Decimal(bot_wins) / Decimal(len(bot_trades)) * Decimal("100")
            if bot_trades
            else Decimal("0")
        )
        quality = trade_quality_averages(bot_trades)
        bot_items.append(
            {
                "bot": bot_name,
                "realized_pl": format_decimal(bot_pl),
                "trade_count": len(bot_trades),
                "wins": bot_wins,
                "losses": bot_losses,
                "win_rate_percent": format_decimal(win_rate),
                "avg_mfe_percent": quality.get("avg_mfe_percent"),
                "avg_mae_percent": quality.get("avg_mae_percent"),
                "avg_capture_ratio_percent": quality.get(
                    "avg_capture_ratio_percent"
                ),
                "avg_hold_seconds": quality.get("avg_hold_seconds"),
            }
        )
    quality = trade_quality_averages(trades)
    return (
        {
            "source": "research_lifecycle",
            "session_date": date_text,
            "session_realized_pl": format_decimal(total),
            "reconciliation_confidence": "HIGH",
            "reconciliation_notes": ["simulated_fills_matched"],
            "session_trade_count": len(trades),
            "session_wins": wins,
            "session_losses": losses,
            "bot_performance": bot_items,
            "realized_trades": trades,
            "trade_quality": quality,
            "inversebot_archaeology": bot_archaeology_report(trades, "InverseBot"),
        },
        trades,
    )


def _rounded(value: Any) -> float:
    decimal_value = Decimal(str(value or 0))
    return float(decimal_value.quantize(Decimal("0.01")))


def _quality_number(value: Any) -> float | str:
    if value in (None, ""):
        return ""
    return _rounded(value)


def _trade_quality_source(trades: list[dict[str, Any]]) -> str:
    sources = sorted(
        {
            str(source)
            for trade in trades
            if (source := trade.get("mfe_mae_source")) not in (None, "")
        }
    )
    return ",".join(sources)


def _bot_performance_by_name(
    performance: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("bot")): item
        for item in performance.get("bot_performance") or []
        if isinstance(item, dict) and item.get("bot")
    }


def _trade_quality_row_values(
    performance: dict[str, Any],
    trades: list[dict[str, Any]],
) -> dict[str, Any]:
    session_quality = performance.get("trade_quality")
    if not isinstance(session_quality, dict):
        session_quality = trade_quality_averages(trades)
    by_bot = _bot_performance_by_name(performance)
    inverse_report = performance.get("inversebot_archaeology")
    if not isinstance(inverse_report, dict):
        inverse_report = bot_archaeology_report(trades, "InverseBot")

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
        "mfe_mae_source": _trade_quality_source(trades),
    }
    for bot_name, prefix in (
        ("MomentumBot", "momentum"),
        ("ChopBot", "chop"),
        ("InverseBot", "inverse"),
    ):
        quality = by_bot.get(bot_name) or {}
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


def _bot_pl_map(performance: dict[str, Any]) -> dict[str, Decimal]:
    result = {"MomentumBot": Decimal("0"), "ChopBot": Decimal("0"), "InverseBot": Decimal("0")}
    for item in performance.get("bot_performance") or []:
        bot_name = str(item.get("bot") or "")
        if bot_name in result:
            result[bot_name] = Decimal(str(item.get("realized_pl") or 0))
    return result


def _session_metrics(records: list[dict[str, Any]], trades: list[dict[str, Any]]) -> dict[str, Any]:
    transitions = sum(1 for record in records if record.get("regime_transition"))
    trend_scores = [
        int(record.get("trend_trust", {}).get("score"))
        for record in records
        if isinstance(record.get("trend_trust"), dict)
        and record.get("trend_trust", {}).get("score") is not None
    ]
    entry_ages = []
    early_entries = 0
    early_entries_by_bot = {
        "MomentumBot": 0,
        "ChopBot": 0,
        "InverseBot": 0,
    }
    v8_block_counts = {
        "v8_regime_too_young": 0,
        "v8_trend_trust_below_minimum": 0,
        "v8_noisy_water_filter": 0,
    }
    v9_counts = {
        "context_activations": 0,
        "inverse_suppressions": 0,
        "context_invalidations": 0,
    }
    v9_context_summary: dict[str, Any] = {}
    v9_activation_keys: set[str] = set()
    v9_invalidation_keys: set[str] = set()
    for record in records:
        console_lines = record.get("console_lines") or []
        if isinstance(console_lines, list):
            console_text = "\n".join(str(line) for line in console_lines)
            for reason in v8_block_counts:
                if f"reason={reason}" in console_text:
                    v8_block_counts[reason] += 1
            if "reason=v9_momentum_context_suppresses_inverse" in console_text:
                v9_counts["inverse_suppressions"] += 1
        v9_context = record.get("v9_momentum_context")
        if isinstance(v9_context, dict):
            activation_reason = v9_context.get("activation_reason")
            if (
                v9_context.get("evaluated")
                and not v9_context_summary
                and "not_momentum_context" not in str(activation_reason or "")
            ):
                v9_context_summary = {
                    "activation_reason": activation_reason,
                    "observer_preset": v9_context.get("observer_preset"),
                    "trust_score": v9_context.get("trend_trust_score"),
                    "soxl_percent": v9_context.get(
                        "source_open_to_current_percent"
                    ),
                    "early_transition_count": v9_context.get(
                        "early_transition_count"
                    ),
                    "early_transitions_per_hour": v9_context.get(
                        "early_transitions_per_hour"
                    ),
                    "early_non_warmup_transition_count": v9_context.get(
                        "early_non_warmup_transition_count"
                    ),
                    "early_non_warmup_transitions_per_hour": v9_context.get(
                        "early_non_warmup_transitions_per_hour"
                    ),
                    "early_transition_window_minutes": v9_context.get(
                        "early_transition_window_minutes"
                    ),
                }
            activated_at = v9_context.get("activated_at")
            if activated_at and activated_at not in v9_activation_keys:
                v9_activation_keys.add(str(activated_at))
                v9_counts["context_activations"] += 1
                v9_context_summary = {
                    "activation_reason": activation_reason,
                    "observer_preset": v9_context.get("observer_preset"),
                    "trust_score": v9_context.get("trend_trust_score"),
                    "soxl_percent": v9_context.get(
                        "source_open_to_current_percent"
                    ),
                    "early_transition_count": v9_context.get(
                        "early_transition_count"
                    ),
                    "early_transitions_per_hour": v9_context.get(
                        "early_transitions_per_hour"
                    ),
                    "early_non_warmup_transition_count": v9_context.get(
                        "early_non_warmup_transition_count"
                    ),
                    "early_non_warmup_transitions_per_hour": v9_context.get(
                        "early_non_warmup_transitions_per_hour"
                    ),
                    "early_transition_window_minutes": v9_context.get(
                        "early_transition_window_minutes"
                    ),
                }
            invalidated_at = v9_context.get("invalidated_at")
            if invalidated_at and invalidated_at not in v9_invalidation_keys:
                v9_invalidation_keys.add(str(invalidated_at))
                v9_counts["context_invalidations"] += 1
                v9_context_summary["invalidation_reason"] = v9_context.get(
                    "invalidation_reason"
                )
        if record.get("action_taken") != "market_buy":
            continue
        trust = record.get("trend_trust")
        age = trust.get("regime_age_minutes") if isinstance(trust, dict) else None
        if age is None:
            continue
        age_decimal = Decimal(str(age))
        entry_ages.append(age_decimal)
        if age_decimal <= Decimal("3"):
            early_entries += 1
            bot_name = str(record.get("active_bot") or "")
            if bot_name in early_entries_by_bot:
                early_entries_by_bot[bot_name] += 1
    exit_reason_counts: dict[str, int] = {}
    exit_reason_pl: dict[str, Decimal] = {}
    for trade in trades:
        reason = str(trade.get("exit_reason") or "UNKNOWN")
        exit_reason_counts[reason] = exit_reason_counts.get(reason, 0) + 1
        exit_reason_pl[reason] = exit_reason_pl.get(reason, Decimal("0")) + Decimal(
            str(trade.get("realized_pl") or 0)
        )
    entry_median = Decimal("0")
    if entry_ages:
        sorted_ages = sorted(entry_ages)
        entry_median = sorted_ages[len(sorted_ages) // 2]
    return {
        "regime_transitions": transitions,
        "trend_trust_avg": (
            sum(trend_scores) / len(trend_scores) if trend_scores else 0
        ),
        "entry_regime_age_median": entry_median,
        "early_entry_count": early_entries,
        "momentum_early_entry_count": early_entries_by_bot["MomentumBot"],
        "chop_early_entry_count": early_entries_by_bot["ChopBot"],
        "inverse_early_entry_count": early_entries_by_bot["InverseBot"],
        "v8_young_regime_blocks": v8_block_counts["v8_regime_too_young"],
        "v8_low_trust_blocks": v8_block_counts[
            "v8_trend_trust_below_minimum"
        ],
        "v8_noisy_water_blocks": v8_block_counts["v8_noisy_water_filter"],
        "v9_momentum_context_activations": v9_counts["context_activations"],
        "v9_inverse_suppression_blocks": v9_counts["inverse_suppressions"],
        "v9_momentum_context_invalidations": v9_counts["context_invalidations"],
        "v9_momentum_context_activation_reason": v9_context_summary.get(
            "activation_reason"
        ),
        "v9_momentum_context_observer_preset": v9_context_summary.get(
            "observer_preset"
        ),
        "v9_momentum_context_trust_score": v9_context_summary.get("trust_score"),
        "v9_momentum_context_soxl_percent": v9_context_summary.get("soxl_percent"),
        "v9_momentum_context_early_transition_count": v9_context_summary.get(
            "early_transition_count"
        ),
        "v9_momentum_context_early_transitions_per_hour": v9_context_summary.get(
            "early_transitions_per_hour"
        ),
        "v9_momentum_context_early_non_warmup_transition_count": (
            v9_context_summary.get("early_non_warmup_transition_count")
        ),
        "v9_momentum_context_early_non_warmup_transitions_per_hour": (
            v9_context_summary.get("early_non_warmup_transitions_per_hour")
        ),
        "v9_momentum_context_early_window_minutes": v9_context_summary.get(
            "early_transition_window_minutes"
        ),
        "v9_momentum_context_invalidation_reason": v9_context_summary.get(
            "invalidation_reason"
        ),
        "exit_reason_counts": exit_reason_counts,
        "exit_reason_pl": exit_reason_pl,
    }


def _config_value(config: BotConfig, key: str) -> Any:
    return getattr(config, key)


def run_research_backtest(config: BotConfig, request: ResearchRunRequest) -> dict[str, Any]:
    date_text = _validate_date(request.date)
    if request.fill_model not in RESEARCH_FILL_MODELS:
        raise BotError("Research fill model must be next_bar_open.")

    bars_by_symbol = fetch_historical_bars(config, (SOXL, SOXS), date_text)
    start, end = _regular_session_bounds(date_text)
    market_data = ReplayMarketData(bars_by_symbol, config.data_feed)
    client = SimulatedBroker(
        config,
        market_data,
        start=start,
        end=end,
        starting_account_value=request.starting_account_value,
        slippage_bps=request.slippage_bps,
    )
    records: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        state_store = BotStateStore(Path(tmpdir) / "research_state.json")
        lifecycle_ledger = LifecycleLedger(Path(tmpdir) / "research_lifecycle.jsonl")
        max_cycles = min(len(bars_by_symbol[SOXL]), len(bars_by_symbol[SOXS]))
        previous_regime: str | None = None
        for index in range(max_cycles):
            current_bar = bars_by_symbol[SOXL][index]
            inverse_bar = bars_by_symbol[SOXS][index]
            current_time = parse_market_timestamp(current_bar.get("t"))
            if current_time is None:
                continue
            market_data.set_index(index)
            client.set_time(current_time)
            output = io.StringIO()
            edgewalker_status = None
            error = None
            with _patched_bot_time(current_time), contextlib.redirect_stdout(output):
                try:
                    edgewalker_status = EdgeWalkerBot(
                        config,
                        client,
                        state_store,
                        market_data,
                        lifecycle_ledger,
                    ).run_once()
                except BotError as exc:
                    error = str(exc)
            status_dict = asdict(edgewalker_status) if edgewalker_status else None
            regime_transition = None
            if status_dict:
                regime = status_dict.get("regime")
                if previous_regime is not None and regime != previous_regime:
                    regime_transition = {
                        "from": previous_regime,
                        "to": regime,
                        "gap_percent": status_dict.get("gap_percent"),
                    }
                previous_regime = regime
            lifecycle_records = lifecycle_ledger.read_all()
            performance, _trades = _performance_from_lifecycle(
                lifecycle_records,
                date_text,
                bars_by_symbol,
            )
            records.append(
                {
                    "timestamp": current_time.isoformat(timespec="seconds").replace("+00:00", "Z"),
                    "trading_date": date_text,
                    "cycle_id": index + 1,
                    "config": {
                        "symbol": config.symbol,
                        "dry_run": False,
                        "active_environment": "research",
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
                        "directional_strong_chase_max_extension_percent": str(config.directional_strong_chase_max_extension_percent),
                        "directional_min_strength": config.directional_min_strength,
                        "directional_cooldown_minutes": config.directional_cooldown_minutes,
                        "adaptive_shadow_enabled": config.adaptive_shadow_enabled,
                        "data_feed": config.data_feed,
                    },
                    "console_lines": output.getvalue().splitlines()[-12:],
                    "error": error,
                    "regime_transition": regime_transition,
                    **(status_dict or {}),
                    "source_bar_open": current_bar.get("o"),
                    "source_bar_high": current_bar.get("h"),
                    "source_bar_low": current_bar.get("l"),
                    "source_bar_close": current_bar.get("c"),
                    "inverse_bar_open": inverse_bar.get("o"),
                    "inverse_bar_high": inverse_bar.get("h"),
                    "inverse_bar_low": inverse_bar.get("l"),
                    "inverse_bar_close": inverse_bar.get("c"),
                    "price": (status_dict or {}).get("source_price"),
                    "account_value": (status_dict or {}).get("portfolio_value"),
                    "performance": performance,
                    "bot_performance": performance.get("bot_performance"),
                    "session_realized_pl": performance.get("session_realized_pl"),
                    "session_trade_count": performance.get("session_trade_count"),
                    "pl_reconciliation_confidence": performance.get("reconciliation_confidence"),
                }
            )

        lifecycle_records = lifecycle_ledger.read_all()

    performance, trades = _performance_from_lifecycle(
        lifecycle_records,
        date_text,
        bars_by_symbol,
    )
    metrics = _session_metrics(records, trades)
    bot_pl = _bot_pl_map(performance)
    realized_pl = Decimal(str(performance.get("session_realized_pl") or 0))
    starting = request.starting_account_value
    ending = starting + realized_pl
    account_change_percent = realized_pl / starting * Decimal("100") if starting > 0 else Decimal("0")
    top_bot = max((item for item in bot_pl.items() if item[1] != 0), key=lambda item: item[1], default=("", Decimal("0")))[0]
    losses = [item for item in bot_pl.items() if item[1] < 0]
    bottom_bot = min(losses, key=lambda item: item[1])[0] if losses else ""
    result_status = "GREEN" if realized_pl > 0 else "RED" if realized_pl < 0 else "FLAT"
    trade_count = int(performance.get("session_trade_count") or 0)
    wins = int(performance.get("session_wins") or 0)
    losses_count = int(performance.get("session_losses") or 0)
    win_rate = (
        Decimal(wins) / Decimal(trade_count) * Decimal("100")
        if trade_count > 0
        else Decimal("0")
    )
    exit_counts = metrics["exit_reason_counts"]
    exit_pl = metrics["exit_reason_pl"]
    row = {
        "is_backtest": True,
        "run_id": str(uuid.uuid4()),
        "run_timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "backtest_date": date_text,
        "fill_model": request.fill_model,
        "slippage_bps": _rounded(request.slippage_bps),
        "preset_name": request.preset_name,
        "preset_version": request.preset_version,
        "entry_regime_age_median": _rounded(metrics["entry_regime_age_median"]),
        "early_entry_count": int(metrics["early_entry_count"]),
        "momentum_early_entry_count": int(metrics["momentum_early_entry_count"]),
        "chop_early_entry_count": int(metrics["chop_early_entry_count"]),
        "inverse_early_entry_count": int(metrics["inverse_early_entry_count"]),
        "v8_young_regime_blocks": int(metrics["v8_young_regime_blocks"]),
        "v8_low_trust_blocks": int(metrics["v8_low_trust_blocks"]),
        "v8_noisy_water_blocks": int(metrics["v8_noisy_water_blocks"]),
        "v9_momentum_context_activations": int(
            metrics["v9_momentum_context_activations"]
        ),
        "v9_inverse_suppression_blocks": int(
            metrics["v9_inverse_suppression_blocks"]
        ),
        "v9_momentum_context_invalidations": int(
            metrics["v9_momentum_context_invalidations"]
        ),
        "v9_momentum_context_activation_reason": metrics[
            "v9_momentum_context_activation_reason"
        ],
        "v9_momentum_context_observer_preset": metrics[
            "v9_momentum_context_observer_preset"
        ],
        "v9_momentum_context_trust_score": metrics[
            "v9_momentum_context_trust_score"
        ],
        "v9_momentum_context_soxl_percent": metrics[
            "v9_momentum_context_soxl_percent"
        ],
        "v9_momentum_context_early_transition_count": metrics[
            "v9_momentum_context_early_transition_count"
        ],
        "v9_momentum_context_early_transitions_per_hour": metrics[
            "v9_momentum_context_early_transitions_per_hour"
        ],
        "v9_momentum_context_early_non_warmup_transition_count": metrics[
            "v9_momentum_context_early_non_warmup_transition_count"
        ],
        "v9_momentum_context_early_non_warmup_transitions_per_hour": metrics[
            "v9_momentum_context_early_non_warmup_transitions_per_hour"
        ],
        "v9_momentum_context_early_window_minutes": metrics[
            "v9_momentum_context_early_window_minutes"
        ],
        "v9_momentum_context_invalidation_reason": metrics[
            "v9_momentum_context_invalidation_reason"
        ],
        "date": date_text,
        "mode": config.directional_mode,
        "starting_account_value": _rounded(starting),
        "ending_account_value": _rounded(ending),
        "realized_pl_dollars": _rounded(realized_pl),
        "account_change_percent": _rounded(account_change_percent),
        "account_result_status": result_status,
        "closed_trades": trade_count,
        "wins": wins,
        "losses": losses_count,
        "win_rate": _rounded(win_rate),
        "momentum_pl": _rounded(bot_pl["MomentumBot"]),
        "chop_pl": _rounded(bot_pl["ChopBot"]),
        "inverse_pl": _rounded(bot_pl["InverseBot"]),
        "top_pl_bot": top_bot,
        "bottom_pl_bot": bottom_bot,
        "regime_transitions": int(metrics["regime_transitions"]),
        "cycles": len(records),
        "stale_cycles": 0,
        "stream_error_cycles": 0,
        "session_trend_trust_avg": _rounded(metrics["trend_trust_avg"]),
        "route_invalidation_exits": int(exit_counts.get("route_invalidated_exit", 0)),
        "route_invalidation_pl": _rounded(exit_pl.get("route_invalidated_exit", Decimal("0"))),
        "trailing_stop_exits": int(exit_counts.get("trailing_stop_breached", 0)),
        "trailing_stop_pl": _rounded(exit_pl.get("trailing_stop_breached", Decimal("0"))),
        "market_close_exits": int(exit_counts.get("market_close_liquidation", 0)),
        "market_close_pl": _rounded(exit_pl.get("market_close_liquidation", Decimal("0"))),
        **_trade_quality_row_values(performance, trades),
        "reconciliation_confidence": performance.get("reconciliation_confidence") or "",
        "config_version": "research-v1",
        "strategy_version": "research-v1",
        "symbol_primary": SOXL,
        "symbol_inverse": SOXS,
        "position_sizing_mode": config.position_sizing_mode,
        "position_notional": _rounded(config.position_notional),
        "position_allocation_percent": _rounded(config.position_allocation_percent),
        "poll_seconds": config.poll_seconds,
        "trail_percent": _rounded(config.trail_percent),
        "fast_sma_minutes": config.fast_sma_minutes,
        "slow_sma_minutes": config.slow_sma_minutes,
        "regime_gap_percent": _rounded(config.regime_gap_threshold),
        "regime_exit_gap_percent": _rounded(config.regime_exit_gap_threshold),
        "chop_discount_percent": _rounded(config.chop_entry_discount_percent),
        "close_liquidate_minutes": config.close_liquidate_minutes,
        "directional_max_extension_percent": _rounded(config.directional_max_extension_percent),
        "directional_strong_chase_max_extension_percent": _rounded(config.directional_strong_chase_max_extension_percent),
        "directional_min_strength": config.directional_min_strength,
        "directional_cooldown_minutes": config.directional_cooldown_minutes,
        "adaptive_shadow_enabled": config.adaptive_shadow_enabled,
        "dry_run": False,
        "active_environment": "research",
        "data_feed": config.data_feed,
        "operator_notes": "",
        "daily_narrative": "",
    }
    return {
        "status": "completed",
        "date": date_text,
        "records": records,
        "performance": performance,
        "trades": trades,
        "row": row,
    }
