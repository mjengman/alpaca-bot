#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path
from typing import Any


TRADING_BASE_URL_DEFAULT = "https://paper-api.alpaca.markets/v2"
DATA_BASE_URL_DEFAULT = "https://data.alpaca.markets/v2"
STATE_PATH_DEFAULT = Path(__file__).resolve().with_name(".bot_state.json")
FRACTIONAL_QTY_STEP = Decimal("0.000000001")
SOXL = "SOXL"
SOXS = "SOXS"
UPTREND = "UPTREND"
SIDEWAYS = "SIDEWAYS"
DOWNTREND = "DOWNTREND"
MOMENTUM_BOT = "MomentumBot"
CHOP_BOT = "ChopBot"
INVERSE_BOT = "InverseBot"


class BotError(Exception):
    pass


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env_decimal(name: str, default: str) -> Decimal:
    value = os.environ.get(name, default)
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise BotError(f"{name} must be a valid number, got {value!r}") from exc


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise BotError(f"{name} must be an integer, got {value!r}") from exc


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BotConfig:
    trading_base_url: str
    data_base_url: str
    api_key_id: str
    api_secret_key: str
    symbol: str
    position_notional: Decimal
    trail_percent: Decimal
    fast_sma_minutes: int
    slow_sma_minutes: int
    poll_seconds: int
    close_liquidate_minutes: int
    regime_gap_threshold: Decimal
    chop_entry_discount_percent: Decimal
    data_feed: str
    dry_run: bool

    @classmethod
    def from_env(cls) -> "BotConfig":
        api_key_id = os.environ.get("ALPACA_API_KEY_ID", "").strip()
        api_secret_key = os.environ.get("ALPACA_API_SECRET_KEY", "").strip()
        if not api_key_id or not api_secret_key:
            raise BotError("Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY in .env")

        fast_sma = env_int("FAST_SMA_MINUTES", 5)
        slow_sma = env_int("SLOW_SMA_MINUTES", 20)
        if fast_sma < 2:
            raise BotError("FAST_SMA_MINUTES must be at least 2")
        if slow_sma <= fast_sma:
            raise BotError("SLOW_SMA_MINUTES must be greater than FAST_SMA_MINUTES")

        trail_percent = env_decimal("TRAIL_PERCENT", "1.5")
        if trail_percent <= 0:
            raise BotError("TRAIL_PERCENT must be greater than 0")

        position_notional = env_decimal("POSITION_NOTIONAL", "25")
        if position_notional <= 0:
            raise BotError("POSITION_NOTIONAL must be greater than 0")

        poll_seconds = env_int("POLL_SECONDS", 60)
        if poll_seconds < 5:
            raise BotError("POLL_SECONDS must be at least 5")

        close_liquidate_minutes = env_int("CLOSE_LIQUIDATE_MINUTES", 5)
        if close_liquidate_minutes < 1:
            raise BotError("CLOSE_LIQUIDATE_MINUTES must be at least 1")

        regime_gap_threshold = env_decimal("REGIME_GAP_THRESHOLD", "0.20")
        if regime_gap_threshold < 0:
            raise BotError("REGIME_GAP_THRESHOLD must be at least 0")

        chop_entry_discount_percent = env_decimal("CHOP_ENTRY_DISCOUNT_PERCENT", "0.50")
        if chop_entry_discount_percent < 0:
            raise BotError("CHOP_ENTRY_DISCOUNT_PERCENT must be at least 0")

        return cls(
            trading_base_url=os.environ.get(
                "ALPACA_TRADING_BASE_URL", TRADING_BASE_URL_DEFAULT
            ).rstrip("/"),
            data_base_url=os.environ.get(
                "ALPACA_DATA_BASE_URL", DATA_BASE_URL_DEFAULT
            ).rstrip("/"),
            api_key_id=api_key_id,
            api_secret_key=api_secret_key,
            symbol=os.environ.get("SYMBOL", SOXL).strip().upper(),
            position_notional=position_notional,
            trail_percent=trail_percent,
            fast_sma_minutes=fast_sma,
            slow_sma_minutes=slow_sma,
            poll_seconds=poll_seconds,
            close_liquidate_minutes=close_liquidate_minutes,
            regime_gap_threshold=regime_gap_threshold,
            chop_entry_discount_percent=chop_entry_discount_percent,
            data_feed=os.environ.get("DATA_FEED", "iex").strip(),
            dry_run=env_bool("DRY_RUN", True),
        )


class AlpacaClient:
    def __init__(self, config: BotConfig) -> None:
        self.config = config

    def get_account(self) -> dict[str, Any]:
        return self._trading_request("GET", "/account")

    def get_clock(self) -> dict[str, Any]:
        return self._trading_request("GET", "/clock")

    def get_position(self, symbol: str) -> dict[str, Any] | None:
        try:
            return self._trading_request("GET", f"/positions/{symbol}")
        except BotError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise

    def get_asset(self, symbol: str) -> dict[str, Any]:
        return self._trading_request("GET", f"/assets/{symbol}")

    def list_open_orders(self) -> list[dict[str, Any]]:
        orders = self._trading_request(
            "GET",
            "/orders",
            {"status": "open", "limit": "100", "direction": "desc", "nested": "false"},
        )
        if not isinstance(orders, list):
            raise BotError(f"Unexpected orders response: {orders!r}")
        return orders

    def get_recent_bars(self, symbol: str, minutes: int) -> list[dict[str, Any]]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=max(minutes * 3, minutes + 15))
        params = {
            "timeframe": "1Min",
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "limit": str(minutes),
            "adjustment": "raw",
            "feed": self.config.data_feed,
            "sort": "asc",
        }

        data = self._data_request("GET", f"/stocks/{symbol}/bars", params)
        bars = data.get("bars") or []

        if isinstance(bars, dict):
            bars = bars.get(symbol) or []
        if not isinstance(bars, list):
            raise BotError(f"Unexpected bars response: {data!r}")

        return bars

    def submit_market_buy(self, symbol: str, notional: Decimal) -> dict[str, Any] | None:
        payload = {
            "symbol": symbol,
            "notional": str(notional),
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
        }
        if self.config.dry_run:
            print(f"[dry-run] Would submit market buy: {json.dumps(payload)}")
            return None
        return self._trading_request("POST", "/orders", payload=payload)

    def submit_market_buy_qty(self, symbol: str, qty: Decimal) -> dict[str, Any] | None:
        payload = {
            "symbol": symbol,
            "qty": format_decimal(qty),
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
        }
        if self.config.dry_run:
            print(f"[dry-run] Would submit market buy: {json.dumps(payload)}")
            return None
        return self._trading_request("POST", "/orders", payload=payload)

    def submit_market_sell_qty(self, symbol: str, qty: Decimal) -> dict[str, Any] | None:
        payload = {
            "symbol": symbol,
            "qty": format_decimal(qty),
            "side": "sell",
            "type": "market",
            "time_in_force": "day",
        }
        if self.config.dry_run:
            print(f"[dry-run] Would submit market sell: {json.dumps(payload)}")
            return None
        return self._trading_request("POST", "/orders", payload=payload)

    def submit_trailing_stop_sell(
        self, symbol: str, qty: Decimal, trail_percent: Decimal
    ) -> dict[str, Any] | None:
        payload = {
            "symbol": symbol,
            "qty": format_decimal(qty),
            "side": "sell",
            "type": "trailing_stop",
            "time_in_force": "gtc",
            "trail_percent": str(trail_percent),
        }
        if self.config.dry_run:
            print(f"[dry-run] Would submit trailing stop sell: {json.dumps(payload)}")
            return None
        return self._trading_request("POST", "/orders", payload=payload)

    def _trading_request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return self._request(
            method,
            f"{self.config.trading_base_url}{path}",
            params=params,
            payload=payload,
        )

    def _data_request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        return self._request(
            method,
            f"{self.config.data_base_url}{path}",
            params=params,
        )

    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        body = None
        headers = {
            "APCA-API-KEY-ID": self.config.api_key_id,
            "APCA-API-SECRET-KEY": self.config.api_secret_key,
            "Accept": "application/json",
        }

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise BotError(f"HTTP {exc.code} from {url}: {details}") from exc
        except urllib.error.URLError as exc:
            raise BotError(f"Network error calling {url}: {exc.reason}") from exc

        if not raw:
            return None

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BotError(f"Invalid JSON from {url}: {raw[:250]}") from exc


def format_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f")


def decimal_from_api(value: Any, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise BotError(f"Could not parse {field_name} value {value!r}") from exc


def optional_decimal_from_api(value: Any, field_name: str) -> Decimal | None:
    if value in (None, ""):
        return None
    return decimal_from_api(value, field_name)


def sma(values: list[Decimal]) -> Decimal:
    return sum(values) / Decimal(len(values))


def crossed_above(
    fast_now_values: list[Decimal],
    fast_prev_values: list[Decimal],
    slow_now_values: list[Decimal],
    slow_prev_values: list[Decimal],
) -> bool:
    fast_now = sma(fast_now_values)
    fast_prev = sma(fast_prev_values)
    slow_now = sma(slow_now_values)
    slow_prev = sma(slow_prev_values)
    return fast_prev <= slow_prev and fast_now > slow_now


def latest_close_prices(bars: list[dict[str, Any]]) -> list[Decimal]:
    prices: list[Decimal] = []
    for bar in bars:
        if "c" not in bar:
            continue
        prices.append(decimal_from_api(bar["c"], "bar close"))
    return prices


@dataclass(frozen=True)
class SmaSnapshot:
    symbol: str
    price: Decimal
    fast_sma: Decimal
    slow_sma: Decimal
    fast_now_values: list[Decimal]
    fast_prev_values: list[Decimal]
    slow_now_values: list[Decimal]
    slow_prev_values: list[Decimal]

    @property
    def gap_percent(self) -> Decimal:
        if self.slow_sma == 0:
            return Decimal("0")
        return abs(self.fast_sma - self.slow_sma) / self.slow_sma * Decimal("100")

    @property
    def crossed_above(self) -> bool:
        return crossed_above(
            self.fast_now_values,
            self.fast_prev_values,
            self.slow_now_values,
            self.slow_prev_values,
        )


@dataclass(frozen=True)
class RegimeSignal:
    source_symbol: str
    price: Decimal
    fast_sma: Decimal
    slow_sma: Decimal
    gap_percent: Decimal
    regime: str


@dataclass(frozen=True)
class BotRoute:
    active_bot: str
    routed_symbol: str | None
    allows_entry: bool


@dataclass(frozen=True)
class EdgeWalkerStatus:
    checked_at: str
    market_open: bool
    next_open: str | None
    next_close: str | None
    buying_power: str | None
    portfolio_value: str | None
    cash: str | None
    day_pl: str | None
    day_pl_percent: str | None
    source_symbol: str
    source_price: str | None
    fast_sma: str | None
    slow_sma: str | None
    gap_percent: str | None
    regime: str | None
    active_bot: str | None
    routed_symbol: str | None
    entry_signal: bool | None
    action_taken: str
    position_symbol: str | None
    position_qty: str | None
    position_market_value: str | None
    position_avg_entry_price: str | None
    position_unrealized_pl: str | None
    position_unrealized_pl_percent: str | None
    position_current_price: str | None
    position_owner: str | None
    high_water_mark: str | None
    trailing_exit_price: str | None


def parse_clock_time(value: Any, field_name: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise BotError(f"Could not parse Alpaca clock {field_name}: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def closeout_status(
    clock: dict[str, Any],
    close_liquidate_minutes: int,
) -> tuple[datetime | None, float | None, bool]:
    next_close = parse_clock_time(clock.get("next_close"), "next_close")
    if next_close is None:
        return None, None, False

    seconds_to_close = (next_close - datetime.now(timezone.utc)).total_seconds()
    closeout_due = 0 <= seconds_to_close <= close_liquidate_minutes * 60
    return next_close, seconds_to_close, closeout_due


def config_for_symbol(config: BotConfig, symbol: str) -> BotConfig:
    return BotConfig(**{**config.__dict__, "symbol": symbol})


class BotStateStore:
    def __init__(self, path: Path = STATE_PATH_DEFAULT) -> None:
        self.path = path

    def get_high_water_mark(self, symbol: str) -> Decimal | None:
        data = self._read()
        raw = data.get("trailing", {}).get(symbol, {}).get("high_water_mark")
        if raw is None:
            return None
        return decimal_from_api(raw, f"{symbol} high water mark")

    def set_high_water_mark(self, symbol: str, value: Decimal) -> None:
        data = self._read()
        trailing = data.setdefault("trailing", {})
        symbol_state = trailing.setdefault(symbol, {})
        symbol_state["high_water_mark"] = format_decimal(value)
        symbol_state["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(data)

    def get_position_owner(self, symbol: str) -> str | None:
        data = self._read()
        owner = data.get("trailing", {}).get(symbol, {}).get("owner")
        if not owner:
            return None
        return str(owner)

    def set_position_owner(self, symbol: str, owner: str) -> None:
        data = self._read()
        trailing = data.setdefault("trailing", {})
        symbol_state = trailing.setdefault(symbol, {})
        symbol_state["owner"] = owner
        symbol_state["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(data)

    def clear_symbol(self, symbol: str) -> None:
        data = self._read()
        trailing = data.get("trailing", {})
        if symbol in trailing:
            del trailing[symbol]
            self._write(data)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"trailing": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BotError(f"Invalid bot state file {self.path}") from exc
        if not isinstance(data, dict):
            raise BotError(f"Invalid bot state file {self.path}")
        data.setdefault("trailing", {})
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


class TrailingStopBot:
    def __init__(
        self,
        config: BotConfig,
        client: AlpacaClient,
        state_store: BotStateStore | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.state_store = state_store or BotStateStore()

    def run_forever(self) -> None:
        print(
            f"Starting {self.config.symbol} bot. "
            f"dry_run={self.config.dry_run}, poll_seconds={self.config.poll_seconds}"
        )
        while True:
            try:
                self.run_once()
            except BotError as exc:
                print(f"[error] {exc}", file=sys.stderr)
            time.sleep(self.config.poll_seconds)

    def run_once(self) -> None:
        clock = self.client.get_clock()
        account = self.client.get_account()
        market_open = bool(clock.get("is_open"))
        next_close, seconds_to_close, closeout_due = closeout_status(
            clock,
            self.config.close_liquidate_minutes,
        )
        next_close_text = next_close.isoformat(timespec="seconds") if next_close else "unknown"
        print(
            f"[{datetime.now().isoformat(timespec='seconds')}] "
            f"market_open={market_open} "
            f"next_close={next_close_text} "
            f"buying_power={account.get('buying_power')} "
            f"portfolio_value={account.get('portfolio_value')}"
        )

        symbol = self.config.symbol
        orders = self.client.list_open_orders()
        symbol_orders = [order for order in orders if order.get("symbol") == symbol]
        position = self.client.get_position(symbol)

        if position:
            if closeout_due:
                self._liquidate_before_close(
                    symbol,
                    position,
                    symbol_orders,
                    seconds_to_close,
                )
                return
            self._manage_trailing_stop(symbol, position, symbol_orders)
            return

        self.state_store.clear_symbol(symbol)

        if closeout_due:
            print(
                f"{symbol}: inside final {self.config.close_liquidate_minutes} "
                "minutes before close; no new entry orders will be submitted."
            )
            return

        if not market_open:
            print(f"{symbol}: market is closed; no new entry orders will be submitted.")
            return

        if any(order.get("side") == "buy" for order in symbol_orders):
            print(f"{symbol}: buy order already open; waiting.")
            return

        self._maybe_enter(symbol)

    def _liquidate_before_close(
        self,
        symbol: str,
        position: dict[str, Any],
        symbol_orders: list[dict[str, Any]],
        seconds_to_close: float | None,
    ) -> None:
        if any(order.get("side") == "sell" for order in symbol_orders):
            print(f"{symbol}: closeout window active, sell order already open.")
            return

        qty = decimal_from_api(position.get("qty"), "position qty")
        if qty <= 0:
            print(f"{symbol}: closeout window active, no long position to sell.")
            return

        qty = qty.quantize(FRACTIONAL_QTY_STEP, rounding=ROUND_DOWN)
        minutes_text = "unknown"
        if seconds_to_close is not None:
            minutes_text = f"{max(seconds_to_close, 0) / 60:.1f}"
        print(
            f"{symbol}: market closes in {minutes_text} minutes; "
            f"selling all shares qty={format_decimal(qty)}."
        )
        self.client.submit_market_sell_qty(symbol, qty)
        self.state_store.clear_symbol(symbol)

    def _manage_trailing_stop(
        self,
        symbol: str,
        position: dict[str, Any],
        symbol_orders: list[dict[str, Any]],
    ) -> None:
        if any(order.get("side") == "sell" for order in symbol_orders):
            print(f"{symbol}: sell order already open; waiting for it to resolve.")
            return

        qty = decimal_from_api(position.get("qty"), "position qty")
        if qty <= 0:
            print(f"{symbol}: non-long position qty={qty}; no trailing stop submitted.")
            return

        current_price = self._latest_price(symbol)
        if current_price is None:
            print(f"{symbol}: no recent price available; trailing stop not evaluated.")
            return

        avg_entry_price = decimal_from_api(
            position.get("avg_entry_price", current_price), "avg entry price"
        )
        high_water_mark = self.state_store.get_high_water_mark(symbol)
        reference_price = max(current_price, avg_entry_price)

        if high_water_mark is None or reference_price > high_water_mark:
            high_water_mark = reference_price
            self.state_store.set_high_water_mark(symbol, high_water_mark)

        stop_price = high_water_mark * (
            Decimal("1") - (self.config.trail_percent / Decimal("100"))
        )
        qty = qty.quantize(FRACTIONAL_QTY_STEP, rounding=ROUND_DOWN)

        print(
            f"{symbol}: position qty={format_decimal(qty)} current={current_price:.4f} "
            f"hwm={high_water_mark:.4f} bot_stop={stop_price:.4f}"
        )

        if current_price <= stop_price:
            print(f"{symbol}: trailing stop breached; submitting fractional market sell.")
            self.client.submit_market_sell_qty(symbol, qty)
            self.state_store.clear_symbol(symbol)
        else:
            print(f"{symbol}: trailing stop holding.")

    def _latest_price(self, symbol: str) -> Decimal | None:
        bars = self.client.get_recent_bars(symbol, 1)
        prices = latest_close_prices(bars)
        if not prices:
            return None
        return prices[-1]

    def _sma_snapshot(self, symbol: str) -> SmaSnapshot | None:
        bars_needed = self.config.slow_sma_minutes + 1
        bars = self.client.get_recent_bars(symbol, bars_needed)
        prices = latest_close_prices(bars)
        if len(prices) < bars_needed:
            print(
                f"{symbol}: need {bars_needed} one-minute bars, got {len(prices)}; "
                "waiting for more data."
            )
            return None

        fast_now_values = prices[-self.config.fast_sma_minutes :]
        fast_prev_values = prices[-(self.config.fast_sma_minutes + 1) : -1]
        slow_now_values = prices[-self.config.slow_sma_minutes :]
        slow_prev_values = prices[-(self.config.slow_sma_minutes + 1) : -1]

        return SmaSnapshot(
            symbol=symbol,
            price=prices[-1],
            fast_sma=sma(fast_now_values),
            slow_sma=sma(slow_now_values),
            fast_now_values=fast_now_values,
            fast_prev_values=fast_prev_values,
            slow_now_values=slow_now_values,
            slow_prev_values=slow_prev_values,
        )

    def _maybe_enter(self, symbol: str) -> None:
        asset = self.client.get_asset(symbol)
        if not asset.get("fractionable"):
            print(f"{symbol}: asset is not fractionable; no notional entry submitted.")
            return

        snapshot = self._sma_snapshot(symbol)
        if snapshot is None:
            return

        has_entry_signal = snapshot.crossed_above

        print(
            f"{symbol}: last={snapshot.price:.4f} "
            f"fast_sma={snapshot.fast_sma:.4f} slow_sma={snapshot.slow_sma:.4f} "
            f"entry_signal={has_entry_signal}"
        )

        if not has_entry_signal:
            print(f"{symbol}: no entry signal.")
            return

        print(
            f"{symbol}: entry signal detected; "
            f"submitting ${self.config.position_notional} market buy."
        )
        self.client.submit_market_buy(symbol, self.config.position_notional)


class RegimeDetector:
    def __init__(self, config: BotConfig, client: AlpacaClient) -> None:
        self.config = config
        self.client = client

    def detect(self) -> tuple[RegimeSignal | None, SmaSnapshot | None]:
        probe = TrailingStopBot(config_for_symbol(self.config, SOXL), self.client)
        snapshot = probe._sma_snapshot(SOXL)
        if snapshot is None:
            return None, None

        gap_percent = snapshot.gap_percent
        if gap_percent < self.config.regime_gap_threshold:
            regime = SIDEWAYS
        elif snapshot.fast_sma > snapshot.slow_sma:
            regime = UPTREND
        else:
            regime = DOWNTREND

        return (
            RegimeSignal(
                source_symbol=SOXL,
                price=snapshot.price,
                fast_sma=snapshot.fast_sma,
                slow_sma=snapshot.slow_sma,
                gap_percent=gap_percent,
                regime=regime,
            ),
            snapshot,
        )


class RegimeRouter:
    def route(self, regime: str) -> BotRoute:
        if regime == UPTREND:
            return BotRoute(MOMENTUM_BOT, SOXL, True)
        if regime == DOWNTREND:
            return BotRoute(INVERSE_BOT, SOXS, True)
        return BotRoute(CHOP_BOT, SOXL, True)


class EdgeWalkerBot:
    basket_symbols = (SOXL, SOXS)

    def __init__(
        self,
        config: BotConfig,
        client: AlpacaClient,
        state_store: BotStateStore | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.state_store = state_store or BotStateStore()

    def run_once(self) -> EdgeWalkerStatus:
        clock = self.client.get_clock()
        account = self.client.get_account()
        market_open = bool(clock.get("is_open"))
        next_open = parse_clock_time(clock.get("next_open"), "next_open")
        next_close, seconds_to_close, closeout_due = closeout_status(
            clock,
            self.config.close_liquidate_minutes,
        )
        next_close_text = next_close.isoformat(timespec="seconds") if next_close else "unknown"
        checked_at = datetime.now().isoformat(timespec="seconds")
        print(
            f"[{checked_at}] "
            f"edgewalker=True market_open={market_open} "
            f"next_close={next_close_text} "
            f"buying_power={account.get('buying_power')} "
            f"portfolio_value={account.get('portfolio_value')}"
        )

        detector = RegimeDetector(self.config, self.client)
        signal, soxl_snapshot = detector.detect()
        if signal is None or soxl_snapshot is None:
            print("EdgeWalker: no regime decision; entry_signal=False action_taken=wait_for_data")
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                None,
                None,
                {},
                False,
                "wait_for_data",
            )

        route = RegimeRouter().route(signal.regime)
        routed_symbol = route.routed_symbol or "NONE"
        print(
            f"{SOXL} regime check: price={signal.price:.4f} "
            f"fast_sma={signal.fast_sma:.4f} slow_sma={signal.slow_sma:.4f} "
            f"gap={signal.gap_percent:.2f}% threshold={self.config.regime_gap_threshold}%"
        )
        print(
            f"regime={signal.regime} active_bot={route.active_bot} "
            f"routed_symbol={routed_symbol}"
        )

        orders = self.client.list_open_orders()
        positions = {symbol: self.client.get_position(symbol) for symbol in self.basket_symbols}

        if closeout_due:
            action_taken = self._liquidate_all_before_close(positions, orders, seconds_to_close)
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                action_taken,
            )

        if not market_open:
            print("EdgeWalker: market is closed; entry_signal=False action_taken=no_entry")
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                "no_entry",
            )

        stale_symbol = self._stale_symbol(route, positions)
        if stale_symbol:
            action_taken = self._close_stale_position(
                stale_symbol,
                positions[stale_symbol],
                orders,
                signal.regime,
                route.active_bot,
                self.state_store.get_position_owner(stale_symbol),
            )
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                action_taken,
            )

        if not route.allows_entry or route.routed_symbol is None:
            print("entry_signal=False action_taken=chop_no_trade_placeholder")
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                "chop_no_trade_placeholder",
            )

        routed_position = positions.get(route.routed_symbol)
        routed_orders = [
            order for order in orders if order.get("symbol") == route.routed_symbol
        ]
        routed_bot = TrailingStopBot(
            config_for_symbol(self.config, route.routed_symbol),
            self.client,
            self.state_store,
        )

        if routed_position:
            if route.active_bot == CHOP_BOT:
                action_taken = self._maybe_exit_chop_position(
                    route.routed_symbol,
                    routed_position,
                    routed_orders,
                    soxl_snapshot,
                )
                if action_taken:
                    return self._build_status(
                        checked_at,
                        market_open,
                        next_open,
                        next_close,
                        account,
                        signal,
                        route,
                        positions,
                        False,
                        action_taken,
                    )

            routed_bot._manage_trailing_stop(route.routed_symbol, routed_position, routed_orders)
            print("entry_signal=False action_taken=manage_open_position")
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                "manage_open_position",
            )

        if any(order.get("side") == "buy" for order in routed_orders):
            print(
                f"{route.routed_symbol}: buy order already open; "
                "entry_signal=False action_taken=wait_for_open_order"
            )
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                "wait_for_open_order",
            )

        entry_signal = self._entry_signal_for_route(route, soxl_snapshot)
        print(f"entry_signal={entry_signal}")
        if not entry_signal:
            print("action_taken=no_entry_signal")
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                "no_entry_signal",
            )

        asset = self.client.get_asset(route.routed_symbol)
        if not asset.get("fractionable"):
            print(
                f"{route.routed_symbol}: asset is not fractionable; "
                "action_taken=no_entry"
            )
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                True,
                "no_entry",
            )

        print(
            f"{route.active_bot}: submitting ${self.config.position_notional} "
            f"market buy for {route.routed_symbol}."
        )
        self.client.submit_market_buy(route.routed_symbol, self.config.position_notional)
        if not self.config.dry_run:
            self.state_store.set_position_owner(route.routed_symbol, route.active_bot)
        print("action_taken=market_buy")
        return self._build_status(
            checked_at,
            market_open,
            next_open,
            next_close,
            account,
            signal,
            route,
            positions,
            True,
            "market_buy",
        )

    def _build_status(
        self,
        checked_at: str,
        market_open: bool,
        next_open: datetime | None,
        next_close: datetime | None,
        account: dict[str, Any],
        signal: RegimeSignal | None,
        route: BotRoute | None,
        positions: dict[str, dict[str, Any] | None],
        entry_signal: bool | None,
        action_taken: str,
    ) -> EdgeWalkerStatus:
        position_symbol, position = self._active_position(positions)
        position_owner = None
        high_water_mark = None
        trailing_exit_price = None

        if position_symbol:
            position_owner = self.state_store.get_position_owner(position_symbol)
            high_water_mark = self.state_store.get_high_water_mark(position_symbol)
            if high_water_mark is not None:
                trailing_exit_price = high_water_mark * (
                    Decimal("1") - (self.config.trail_percent / Decimal("100"))
                )

        day_pl, day_pl_percent = self._account_day_pl(account)

        return EdgeWalkerStatus(
            checked_at=checked_at,
            market_open=market_open,
            next_open=next_open.isoformat(timespec="seconds") if next_open else None,
            next_close=next_close.isoformat(timespec="seconds") if next_close else None,
            buying_power=self._raw_text(account.get("buying_power")),
            portfolio_value=self._raw_text(account.get("portfolio_value") or account.get("equity")),
            cash=self._raw_text(account.get("cash")),
            day_pl=self._decimal_text(day_pl),
            day_pl_percent=self._decimal_text(day_pl_percent),
            source_symbol=SOXL,
            source_price=self._decimal_text(signal.price if signal else None),
            fast_sma=self._decimal_text(signal.fast_sma if signal else None),
            slow_sma=self._decimal_text(signal.slow_sma if signal else None),
            gap_percent=self._decimal_text(signal.gap_percent if signal else None),
            regime=signal.regime if signal else None,
            active_bot=route.active_bot if route else None,
            routed_symbol=route.routed_symbol if route and route.routed_symbol else None,
            entry_signal=entry_signal,
            action_taken=action_taken,
            position_symbol=position_symbol,
            position_qty=self._raw_text(position.get("qty")) if position else None,
            position_market_value=self._raw_text(position.get("market_value")) if position else None,
            position_avg_entry_price=(
                self._raw_text(position.get("avg_entry_price")) if position else None
            ),
            position_unrealized_pl=(
                self._raw_text(position.get("unrealized_pl")) if position else None
            ),
            position_unrealized_pl_percent=(
                self._raw_text(position.get("unrealized_plpc")) if position else None
            ),
            position_current_price=(
                self._raw_text(position.get("current_price")) if position else None
            ),
            position_owner=position_owner,
            high_water_mark=self._decimal_text(high_water_mark),
            trailing_exit_price=self._decimal_text(trailing_exit_price),
        )

    def _active_position(
        self,
        positions: dict[str, dict[str, Any] | None],
    ) -> tuple[str | None, dict[str, Any] | None]:
        for symbol in self.basket_symbols:
            position = positions.get(symbol)
            if self._position_qty(position) > 0:
                return str(position.get("symbol") or symbol), position
        return None, None

    def _account_day_pl(self, account: dict[str, Any]) -> tuple[Decimal | None, Decimal | None]:
        equity = optional_decimal_from_api(
            account.get("equity") or account.get("portfolio_value"),
            "account equity",
        )
        last_equity = optional_decimal_from_api(account.get("last_equity"), "last equity")
        if equity is None or last_equity is None:
            return None, None

        day_pl = equity - last_equity
        if last_equity == 0:
            return day_pl, None
        return day_pl, day_pl / last_equity * Decimal("100")

    def _raw_text(self, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value)

    def _decimal_text(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return format_decimal(value)

    def _entry_signal_for_route(self, route: BotRoute, soxl_snapshot: SmaSnapshot) -> bool:
        if route.active_bot == MOMENTUM_BOT:
            return soxl_snapshot.crossed_above

        if route.active_bot == CHOP_BOT:
            if soxl_snapshot.slow_sma == 0:
                print(
                    "ChopBot entry check: slow_sma=0.0000 "
                    "entry_signal=False"
                )
                return False
            discount_percent = (
                (soxl_snapshot.slow_sma - soxl_snapshot.price)
                / soxl_snapshot.slow_sma
                * Decimal("100")
            )
            entry_signal = soxl_snapshot.price <= soxl_snapshot.slow_sma * (
                Decimal("1")
                - (self.config.chop_entry_discount_percent / Decimal("100"))
            )
            print(
                f"ChopBot entry check: price={soxl_snapshot.price:.4f} "
                f"slow_sma={soxl_snapshot.slow_sma:.4f} "
                f"discount={discount_percent:.2f}% "
                f"threshold={self.config.chop_entry_discount_percent}%"
            )
            return entry_signal

        if route.active_bot == INVERSE_BOT and route.routed_symbol:
            inverse_bot = TrailingStopBot(
                config_for_symbol(self.config, route.routed_symbol),
                self.client,
                self.state_store,
            )
            snapshot = inverse_bot._sma_snapshot(route.routed_symbol)
            if snapshot is None:
                return False
            print(
                f"{route.routed_symbol} entry check: price={snapshot.price:.4f} "
                f"fast_sma={snapshot.fast_sma:.4f} slow_sma={snapshot.slow_sma:.4f}"
            )
            return snapshot.crossed_above

        return False

    def _stale_symbol(
        self,
        route: BotRoute,
        positions: dict[str, dict[str, Any] | None],
    ) -> str | None:
        for symbol in self.basket_symbols:
            position = positions.get(symbol)
            if self._position_qty(position) <= 0:
                continue
            owner = self.state_store.get_position_owner(symbol)
            if symbol != route.routed_symbol or owner != route.active_bot:
                return symbol
        return None

    def _position_qty(self, position: dict[str, Any] | None) -> Decimal:
        if not position:
            return Decimal("0")
        return decimal_from_api(position.get("qty"), "position qty")

    def _close_stale_position(
        self,
        symbol: str,
        position: dict[str, Any] | None,
        orders: list[dict[str, Any]],
        regime: str,
        active_bot: str,
        owner: str | None,
    ) -> str:
        owner_text = owner or "UNKNOWN"
        symbol_orders = [order for order in orders if order.get("symbol") == symbol]
        if any(order.get("side") == "sell" for order in symbol_orders):
            print(
                f"{symbol}: regime={regime} owner={owner_text} "
                f"active_bot={active_bot} stale exposure, sell order already open; "
                "entry_signal=False action_taken=wait_for_stale_close"
            )
            return "wait_for_stale_close"

        qty = self._position_qty(position).quantize(
            FRACTIONAL_QTY_STEP,
            rounding=ROUND_DOWN,
        )
        if qty <= 0:
            print(f"{symbol}: stale exposure not found; entry_signal=False action_taken=noop")
            return "noop"

        print(
            f"{symbol}: stale exposure under regime={regime}; "
            f"owner={owner_text} active_bot={active_bot}; "
            f"selling qty={format_decimal(qty)}."
        )
        self.client.submit_market_sell_qty(symbol, qty)
        self.state_store.clear_symbol(symbol)
        print("entry_signal=False action_taken=close_stale_position_no_same_cycle_reversal")
        return "close_stale_position_no_same_cycle_reversal"

    def _maybe_exit_chop_position(
        self,
        symbol: str,
        position: dict[str, Any],
        symbol_orders: list[dict[str, Any]],
        soxl_snapshot: SmaSnapshot,
    ) -> str | None:
        reclaim = soxl_snapshot.price >= soxl_snapshot.slow_sma
        print(
            f"ChopBot exit check: price={soxl_snapshot.price:.4f} "
            f"slow_sma={soxl_snapshot.slow_sma:.4f} reclaim={reclaim}"
        )
        if not reclaim:
            return None

        if any(order.get("side") == "sell" for order in symbol_orders):
            print(
                f"{symbol}: ChopBot slow SMA reclaim, sell order already open; "
                "entry_signal=False action_taken=wait_for_chop_exit_order"
            )
            return "wait_for_chop_exit_order"

        qty = self._position_qty(position).quantize(
            FRACTIONAL_QTY_STEP,
            rounding=ROUND_DOWN,
        )
        if qty <= 0:
            print(f"{symbol}: ChopBot exit found no long position; action_taken=noop")
            return "noop"

        print(
            f"{symbol}: ChopBot slow SMA reclaim; "
            f"selling qty={format_decimal(qty)}."
        )
        self.client.submit_market_sell_qty(symbol, qty)
        self.state_store.clear_symbol(symbol)
        print("entry_signal=False action_taken=chop_exit_reclaim_slow_sma")
        return "chop_exit_reclaim_slow_sma"

    def _liquidate_all_before_close(
        self,
        positions: dict[str, dict[str, Any] | None],
        orders: list[dict[str, Any]],
        seconds_to_close: float | None,
    ) -> str:
        minutes_text = "unknown"
        if seconds_to_close is not None:
            minutes_text = f"{max(seconds_to_close, 0) / 60:.1f}"

        sold_any = False
        sell_pending = False
        for symbol in self.basket_symbols:
            position = positions.get(symbol)
            qty = self._position_qty(position)
            if qty <= 0:
                continue

            symbol_orders = [order for order in orders if order.get("symbol") == symbol]
            if any(order.get("side") == "sell" for order in symbol_orders):
                print(f"{symbol}: closeout window active, sell order already open.")
                sell_pending = True
                continue

            qty = qty.quantize(FRACTIONAL_QTY_STEP, rounding=ROUND_DOWN)
            print(
                f"{symbol}: market closes in {minutes_text} minutes; "
                f"selling all shares qty={format_decimal(qty)}."
            )
            self.client.submit_market_sell_qty(symbol, qty)
            self.state_store.clear_symbol(symbol)
            sold_any = True

        if sold_any:
            print("entry_signal=False action_taken=market_close_liquidation")
            return "market_close_liquidation"
        elif sell_pending:
            print("entry_signal=False action_taken=wait_for_closeout_order")
            return "wait_for_closeout_order"
        else:
            print("entry_signal=False action_taken=closeout_window_no_position")
            return "closeout_window_no_position"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Alpaca trailing stop bot POC")
    parser.add_argument("--once", action="store_true", help="Run one polling cycle")
    parser.add_argument("--edgewalker", action="store_true", help="Run EdgeWalker router")
    parser.add_argument("--symbol", help="Override SYMBOL")
    parser.add_argument("--notional", type=Decimal, help="Override POSITION_NOTIONAL")
    parser.add_argument("--trail-percent", type=Decimal, help="Override TRAIL_PERCENT")
    parser.add_argument(
        "--close-liquidate-minutes",
        type=int,
        help="Override CLOSE_LIQUIDATE_MINUTES",
    )
    parser.add_argument(
        "--regime-gap-threshold",
        type=Decimal,
        help="Override REGIME_GAP_THRESHOLD",
    )
    parser.add_argument("--buy-qty", type=Decimal, help="Submit a manual market buy")
    parser.add_argument("--sell-qty", type=Decimal, help="Submit a manual market sell")
    run_mode = parser.add_mutually_exclusive_group()
    run_mode.add_argument("--dry-run", action="store_true", help="Do not place orders")
    run_mode.add_argument("--live", action="store_true", help="Place paper orders")
    return parser.parse_args()


def apply_arg_overrides(config: BotConfig, args: argparse.Namespace) -> BotConfig:
    updates: dict[str, Any] = {}
    if args.symbol:
        updates["symbol"] = args.symbol.strip().upper()
    if args.notional is not None:
        if args.notional <= 0:
            raise BotError("POSITION_NOTIONAL must be greater than 0")
        updates["position_notional"] = args.notional
    if args.trail_percent is not None:
        if args.trail_percent <= 0:
            raise BotError("TRAIL_PERCENT must be greater than 0")
        updates["trail_percent"] = args.trail_percent
    if args.close_liquidate_minutes is not None:
        if args.close_liquidate_minutes < 1:
            raise BotError("CLOSE_LIQUIDATE_MINUTES must be at least 1")
        updates["close_liquidate_minutes"] = args.close_liquidate_minutes
    if args.dry_run:
        updates["dry_run"] = True
    if args.live:
        updates["dry_run"] = False
    if args.regime_gap_threshold is not None:
        if args.regime_gap_threshold < 0:
            raise BotError("REGIME_GAP_THRESHOLD must be at least 0")
        updates["regime_gap_threshold"] = args.regime_gap_threshold

    if not updates:
        return config

    return BotConfig(**{**config.__dict__, **updates})


def main() -> int:
    load_dotenv(Path(".env"))
    args = parse_args()
    config = apply_arg_overrides(BotConfig.from_env(), args)
    client = AlpacaClient(config)
    bot = TrailingStopBot(config, client)

    if args.buy_qty and args.sell_qty:
        raise BotError("Use either --buy-qty or --sell-qty, not both")

    if args.buy_qty:
        result = bot.client.submit_market_buy_qty(config.symbol, args.buy_qty)
        if result:
            print(
                f"Submitted buy order id={result.get('id')} "
                f"symbol={result.get('symbol')} qty={result.get('qty')} "
                f"status={result.get('status')}"
            )
    elif args.sell_qty:
        result = bot.client.submit_market_sell_qty(config.symbol, args.sell_qty)
        if result:
            print(
                f"Submitted sell order id={result.get('id')} "
                f"symbol={result.get('symbol')} qty={result.get('qty')} "
                f"status={result.get('status')}"
            )
    elif args.once:
        if args.edgewalker:
            EdgeWalkerBot(config, client).run_once()
        else:
            bot.run_once()
    else:
        if args.edgewalker:
            print(
                f"Starting EdgeWalker. dry_run={config.dry_run}, "
                f"poll_seconds={config.poll_seconds}"
            )
            while True:
                EdgeWalkerBot(config, client).run_once()
                time.sleep(config.poll_seconds)
        else:
            bot.run_forever()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
        raise SystemExit(130)
    except BotError as exc:
        print(f"[fatal] {exc}", file=sys.stderr)
        raise SystemExit(1)
