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

        return cls(
            trading_base_url=os.environ.get(
                "ALPACA_TRADING_BASE_URL", TRADING_BASE_URL_DEFAULT
            ).rstrip("/"),
            data_base_url=os.environ.get(
                "ALPACA_DATA_BASE_URL", DATA_BASE_URL_DEFAULT
            ).rstrip("/"),
            api_key_id=api_key_id,
            api_secret_key=api_secret_key,
            symbol=os.environ.get("SYMBOL", "F").strip().upper(),
            position_notional=position_notional,
            trail_percent=trail_percent,
            fast_sma_minutes=fast_sma,
            slow_sma_minutes=slow_sma,
            poll_seconds=poll_seconds,
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
        bars = data.get("bars", [])

        if isinstance(bars, dict):
            bars = bars.get(symbol, [])
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
        trailing[symbol] = {
            "high_water_mark": format_decimal(value),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
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
        print(
            f"[{datetime.now().isoformat(timespec='seconds')}] "
            f"market_open={market_open} "
            f"buying_power={account.get('buying_power')} "
            f"portfolio_value={account.get('portfolio_value')}"
        )

        symbol = self.config.symbol
        orders = self.client.list_open_orders()
        symbol_orders = [order for order in orders if order.get("symbol") == symbol]
        position = self.client.get_position(symbol)

        if position:
            self._manage_trailing_stop(symbol, position, symbol_orders)
            return

        self.state_store.clear_symbol(symbol)

        if not market_open:
            print(f"{symbol}: market is closed; no new entry orders will be submitted.")
            return

        if any(order.get("side") == "buy" for order in symbol_orders):
            print(f"{symbol}: buy order already open; waiting.")
            return

        self._maybe_enter(symbol)

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

    def _maybe_enter(self, symbol: str) -> None:
        asset = self.client.get_asset(symbol)
        if not asset.get("fractionable"):
            print(f"{symbol}: asset is not fractionable; no notional entry submitted.")
            return

        bars_needed = self.config.slow_sma_minutes + 1
        bars = self.client.get_recent_bars(symbol, bars_needed)
        prices = latest_close_prices(bars)
        if len(prices) < bars_needed:
            print(
                f"{symbol}: need {bars_needed} one-minute bars, got {len(prices)}; "
                "waiting for more data."
            )
            return

        fast_now_values = prices[-self.config.fast_sma_minutes :]
        fast_prev_values = prices[-(self.config.fast_sma_minutes + 1) : -1]
        slow_now_values = prices[-self.config.slow_sma_minutes :]
        slow_prev_values = prices[-(self.config.slow_sma_minutes + 1) : -1]

        fast_now = sma(fast_now_values)
        slow_now = sma(slow_now_values)
        last_price = prices[-1]
        has_entry_signal = crossed_above(
            fast_now_values,
            fast_prev_values,
            slow_now_values,
            slow_prev_values,
        )

        print(
            f"{symbol}: last={last_price:.4f} "
            f"fast_sma={fast_now:.4f} slow_sma={slow_now:.4f} "
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Alpaca trailing stop bot POC")
    parser.add_argument("--once", action="store_true", help="Run one polling cycle")
    parser.add_argument("--symbol", help="Override SYMBOL")
    parser.add_argument("--notional", type=Decimal, help="Override POSITION_NOTIONAL")
    parser.add_argument("--trail-percent", type=Decimal, help="Override TRAIL_PERCENT")
    parser.add_argument("--buy-qty", type=Decimal, help="Submit a manual market buy")
    parser.add_argument("--sell-qty", type=Decimal, help="Submit a manual market sell")
    run_mode = parser.add_mutually_exclusive_group()
    run_mode.add_argument("--dry-run", action="store_true", help="Do not place orders")
    run_mode.add_argument("--live", action="store_true", help="Place paper orders")
    return parser.parse_args()


def apply_arg_overrides(config: BotConfig, args: argparse.Namespace) -> BotConfig:
    updates: dict[str, Any] = {}
    if args.symbol:
        updates["symbol"] = args.symbol.upper()
    if args.notional:
        updates["position_notional"] = args.notional
    if args.trail_percent:
        updates["trail_percent"] = args.trail_percent
    if args.dry_run:
        updates["dry_run"] = True
    if args.live:
        updates["dry_run"] = False

    if not updates:
        return config

    return BotConfig(**{**config.__dict__, **updates})


def main() -> int:
    load_dotenv(Path(".env"))
    args = parse_args()
    config = apply_arg_overrides(BotConfig.from_env(), args)
    bot = TrailingStopBot(config, AlpacaClient(config))

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
        bot.run_once()
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
