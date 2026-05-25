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
LIVE_TRADING_BASE_URL_DEFAULT = "https://api.alpaca.markets/v2"
DATA_BASE_URL_DEFAULT = "https://data.alpaca.markets/v2"
STATE_PATH_DEFAULT = Path(__file__).resolve().with_name(".bot_state.json")
LIFECYCLE_PATH_DEFAULT = (
    Path(__file__).resolve().with_name("logs") / "position_lifecycle.jsonl"
)
FRACTIONAL_QTY_STEP = Decimal("0.000000001")
MARKET_DATA_MAX_AGE_SECONDS = 90
SOXL = "SOXL"
SOXS = "SOXS"
WARMUP = "WARMUP"
UPTREND = "UPTREND"
SIDEWAYS = "SIDEWAYS"
DOWNTREND = "DOWNTREND"
DIRECTIONAL_MODE_CONSERVATIVE = "CONSERVATIVE"
DIRECTIONAL_MODE_BALANCED = "BALANCED"
DIRECTIONAL_MODE_AGGRESSIVE = "AGGRESSIVE"
DIRECTIONAL_MODE_ADAPTIVE = "ADAPTIVE"
DIRECTIONAL_MODES = {
    DIRECTIONAL_MODE_CONSERVATIVE,
    DIRECTIONAL_MODE_BALANCED,
    DIRECTIONAL_MODE_AGGRESSIVE,
    DIRECTIONAL_MODE_ADAPTIVE,
}
REGIME_STRENGTH_RANGE = "RANGE"
REGIME_STRENGTH_WEAK = "WEAK"
REGIME_STRENGTH_MODERATE = "MODERATE"
REGIME_STRENGTH_STRONG = "STRONG"
REGIME_STRENGTHS = {
    REGIME_STRENGTH_WEAK,
    REGIME_STRENGTH_MODERATE,
    REGIME_STRENGTH_STRONG,
}
REGIME_STRENGTH_ORDER = {
    REGIME_STRENGTH_WEAK: 1,
    REGIME_STRENGTH_MODERATE: 2,
    REGIME_STRENGTH_STRONG: 3,
}
MOMENTUM_BOT = "MomentumBot"
CHOP_BOT = "ChopBot"
INVERSE_BOT = "InverseBot"
POSITION_SIZING_FIXED = "FIXED"
POSITION_SIZING_DYNAMIC = "DYNAMIC"
POSITION_SIZING_MODES = {
    POSITION_SIZING_FIXED,
    POSITION_SIZING_DYNAMIC,
}
LIFECYCLE_INTENDED_ENTRY = "INTENDED_ENTRY"
LIFECYCLE_INTENDED_EXIT = "INTENDED_EXIT"
LIFECYCLE_ORDER_SUBMITTED = "ORDER_SUBMITTED"
LIFECYCLE_ORDER_REJECTED = "ORDER_REJECTED"
LIFECYCLE_ORDER_ACCEPTED = "ORDER_ACCEPTED"
LIFECYCLE_PARTIAL_FILL = "PARTIAL_FILL"
LIFECYCLE_FULL_FILL = "FULL_FILL"
LIFECYCLE_POSITION_OPENED = "POSITION_OPENED"
LIFECYCLE_POSITION_CLOSED = "POSITION_CLOSED"
LIFECYCLE_POSITION_MANAGED = "POSITION_MANAGED"
LIFECYCLE_ADAPTIVE_POSTURE_SELECTED = "ADAPTIVE_POSTURE_SELECTED"
BROKER_STATE_OK = "OK"
BROKER_STATE_RESTRICTED = "RESTRICTED"
BROKER_STATE_EXIT_BLOCKED = "EXIT_BLOCKED"
BROKER_STATE_BUYING_POWER_LIMITED = "BUYING_POWER_LIMITED"
BROKER_STATE_ORDER_PENDING = "ORDER_PENDING"
BROKER_CATEGORY_PDT = "PDT"
BROKER_CATEGORY_INSUFFICIENT_BUYING_POWER = "INSUFFICIENT_BUYING_POWER"
BROKER_CATEGORY_MARKET_CLOSED = "MARKET_CLOSED"
BROKER_CATEGORY_DUPLICATE_ORDER = "DUPLICATE_ORDER"
BROKER_CATEGORY_NOTIONAL_TOO_LARGE = "NOTIONAL_TOO_LARGE"
BROKER_CATEGORY_ASSET_NOT_TRADABLE = "ASSET_NOT_TRADABLE"
BROKER_CATEGORY_GENERIC_REJECTION = "GENERIC_BROKER_REJECTION"
BUYING_POWER_ORDER_BUFFER_PERCENT = Decimal("5")
MONEY_STEP = Decimal("0.01")


class BotError(Exception):
    pass


def _last_completed_bar_end(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    return current.replace(second=0, microsecond=0) - timedelta(microseconds=1)


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


def normalize_alpaca_base_url(value: str) -> str:
    normalized = str(value).strip().rstrip("/")
    if not normalized:
        return normalized

    parsed = urllib.parse.urlparse(normalized)
    alpaca_hosts = {
        "api.alpaca.markets",
        "paper-api.alpaca.markets",
        "data.alpaca.markets",
    }
    if parsed.scheme in {"http", "https"} and parsed.netloc.lower() in alpaca_hosts:
        if parsed.path.rstrip("/") in {"", "/"}:
            return urllib.parse.urlunparse(
                (parsed.scheme, parsed.netloc, "/v2", "", "", "")
            )

    return normalized


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
    position_sizing_mode: str
    position_allocation_percent: Decimal
    trail_percent: Decimal
    fast_sma_minutes: int
    slow_sma_minutes: int
    poll_seconds: int
    close_liquidate_minutes: int
    regime_gap_threshold: Decimal
    regime_exit_gap_threshold: Decimal
    chop_entry_discount_percent: Decimal
    directional_mode: str
    directional_max_extension_percent: Decimal
    directional_strong_chase_max_extension_percent: Decimal
    directional_min_strength: str
    directional_cooldown_minutes: int
    adaptive_shadow_enabled: bool
    data_feed: str
    dry_run: bool

    @classmethod
    def from_env(cls) -> "BotConfig":
        alpaca_environment = os.environ.get("ALPACA_ENVIRONMENT", "paper").strip().lower()
        if alpaca_environment not in {"paper", "live"}:
            raise BotError("ALPACA_ENVIRONMENT must be paper or live")

        if alpaca_environment == "live":
            api_key_id = os.environ.get("ALPACA_LIVE_API_KEY_ID", "").strip()
            api_secret_key = os.environ.get("ALPACA_LIVE_API_SECRET_KEY", "").strip()
            trading_base_url = os.environ.get(
                "ALPACA_LIVE_TRADING_BASE_URL",
                LIVE_TRADING_BASE_URL_DEFAULT,
            )
        else:
            api_key_id = (
                os.environ.get("ALPACA_PAPER_API_KEY_ID")
                or os.environ.get("ALPACA_API_KEY_ID", "")
            ).strip()
            api_secret_key = (
                os.environ.get("ALPACA_PAPER_API_SECRET_KEY")
                or os.environ.get("ALPACA_API_SECRET_KEY", "")
            ).strip()
            trading_base_url = (
                os.environ.get("ALPACA_PAPER_TRADING_BASE_URL")
                or os.environ.get("ALPACA_TRADING_BASE_URL")
                or TRADING_BASE_URL_DEFAULT
            )
        if not api_key_id or not api_secret_key:
            raise BotError(
                "Set Alpaca API key and secret for the selected environment in .env"
            )

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

        position_sizing_mode = os.environ.get(
            "POSITION_SIZING_MODE",
            POSITION_SIZING_FIXED,
        ).strip().upper()
        if position_sizing_mode not in POSITION_SIZING_MODES:
            raise BotError("POSITION_SIZING_MODE must be FIXED or DYNAMIC")

        position_allocation_percent = env_decimal("POSITION_ALLOCATION_PERCENT", "25")
        if position_allocation_percent <= 0 or position_allocation_percent > 100:
            raise BotError("POSITION_ALLOCATION_PERCENT must be between 0 and 100")

        poll_seconds = env_int("POLL_SECONDS", 60)
        if poll_seconds < 5:
            raise BotError("POLL_SECONDS must be at least 5")

        close_liquidate_minutes = env_int("CLOSE_LIQUIDATE_MINUTES", 5)
        if close_liquidate_minutes < 1:
            raise BotError("CLOSE_LIQUIDATE_MINUTES must be at least 1")

        regime_gap_threshold = env_decimal("REGIME_GAP_THRESHOLD", "0.20")
        if regime_gap_threshold < 0:
            raise BotError("REGIME_GAP_THRESHOLD must be at least 0")

        regime_exit_gap_threshold = env_decimal("REGIME_EXIT_GAP_THRESHOLD", "0.10")
        if regime_exit_gap_threshold < 0:
            raise BotError("REGIME_EXIT_GAP_THRESHOLD must be at least 0")

        chop_entry_discount_percent = env_decimal("CHOP_ENTRY_DISCOUNT_PERCENT", "0.50")
        if chop_entry_discount_percent < 0:
            raise BotError("CHOP_ENTRY_DISCOUNT_PERCENT must be at least 0")

        directional_mode = os.environ.get(
            "DIRECTIONAL_MODE",
            os.environ.get("MOMENTUM_MODE", DIRECTIONAL_MODE_BALANCED),
        ).strip().upper()
        if directional_mode not in DIRECTIONAL_MODES:
            raise BotError(
                "DIRECTIONAL_MODE must be CONSERVATIVE, BALANCED, AGGRESSIVE, or ADAPTIVE"
            )

        directional_max_extension_percent = env_decimal(
            "DIRECTIONAL_MAX_EXTENSION_PERCENT",
            os.environ.get("MOMENTUM_MAX_EXTENSION_PERCENT", "0.50"),
        )
        if directional_max_extension_percent < 0:
            raise BotError("DIRECTIONAL_MAX_EXTENSION_PERCENT must be at least 0")

        directional_strong_chase_max_extension_percent = env_decimal(
            "DIRECTIONAL_STRONG_CHASE_MAX_EXTENSION_PERCENT",
            os.environ.get("MOMENTUM_STRONG_CHASE_MAX_EXTENSION_PERCENT", "1.00"),
        )
        if directional_strong_chase_max_extension_percent < 0:
            raise BotError(
                "DIRECTIONAL_STRONG_CHASE_MAX_EXTENSION_PERCENT must be at least 0"
            )

        directional_min_strength = os.environ.get(
            "DIRECTIONAL_MIN_STRENGTH",
            os.environ.get("MOMENTUM_MIN_STRENGTH", REGIME_STRENGTH_MODERATE),
        ).strip().upper()
        if directional_min_strength not in REGIME_STRENGTHS:
            raise BotError("DIRECTIONAL_MIN_STRENGTH must be WEAK, MODERATE, or STRONG")

        directional_cooldown_minutes = env_int(
            "DIRECTIONAL_COOLDOWN_MINUTES",
            env_int("MOMENTUM_COOLDOWN_MINUTES", 5),
        )
        if directional_cooldown_minutes < 0:
            raise BotError("DIRECTIONAL_COOLDOWN_MINUTES must be at least 0")

        return cls(
            trading_base_url=normalize_alpaca_base_url(trading_base_url),
            data_base_url=normalize_alpaca_base_url(
                os.environ.get("ALPACA_DATA_BASE_URL", DATA_BASE_URL_DEFAULT)
            ),
            api_key_id=api_key_id,
            api_secret_key=api_secret_key,
            symbol=os.environ.get("SYMBOL", SOXL).strip().upper(),
            position_notional=position_notional,
            position_sizing_mode=position_sizing_mode,
            position_allocation_percent=position_allocation_percent,
            trail_percent=trail_percent,
            fast_sma_minutes=fast_sma,
            slow_sma_minutes=slow_sma,
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
            adaptive_shadow_enabled=env_bool("ADAPTIVE_SHADOW_ENABLED", True),
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
        end = _last_completed_bar_end()
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

    def get_latest_trade(self, symbol: str) -> dict[str, Any] | None:
        data = self._data_request(
            "GET",
            f"/stocks/{symbol}/trades/latest",
            {"feed": self.config.data_feed},
        )
        trade = data.get("trade")
        if trade is None:
            return None
        if not isinstance(trade, dict):
            raise BotError(f"Unexpected latest trade response: {data!r}")
        return trade

    def get_latest_quote(self, symbol: str) -> dict[str, Any] | None:
        data = self._data_request(
            "GET",
            f"/stocks/{symbol}/quotes/latest",
            {"feed": self.config.data_feed},
        )
        quote = data.get("quote")
        if quote is None:
            return None
        if not isinstance(quote, dict):
            raise BotError(f"Unexpected latest quote response: {data!r}")
        return quote

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

    def get_order(self, order_id: str) -> dict[str, Any]:
        order = self._trading_request("GET", f"/orders/{order_id}")
        if not isinstance(order, dict):
            raise BotError(f"Unexpected order response: {order!r}")
        return order

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


def lifecycle_json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format_decimal(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): lifecycle_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [lifecycle_json_value(item) for item in value]
    return value


@dataclass(frozen=True)
class BrokerConstraint:
    state: str
    category: str | None
    message: str | None
    side: str | None = None
    symbol: str | None = None
    code: str | None = None


def broker_constraint_ok() -> BrokerConstraint:
    return BrokerConstraint(
        state=BROKER_STATE_OK,
        category=None,
        message=None,
    )


def broker_constraint_payload(constraint: BrokerConstraint) -> dict[str, Any]:
    return {
        "state": constraint.state,
        "category": constraint.category,
        "message": constraint.message,
        "side": constraint.side,
        "symbol": constraint.symbol,
        "code": constraint.code,
    }


def classify_broker_error(
    message: str,
    side: str | None = None,
    symbol: str | None = None,
) -> BrokerConstraint:
    payload = broker_error_payload(message)
    payload_message = str(payload.get("message") or "") if payload else ""
    code = str(payload.get("code")) if payload and payload.get("code") else None
    text = f"{message} {payload_message}".lower()
    normalized_side = side.lower() if isinstance(side, str) else None

    category = BROKER_CATEGORY_GENERIC_REJECTION
    state = BROKER_STATE_RESTRICTED
    if "pattern day" in text or "pdt" in text:
        category = BROKER_CATEGORY_PDT
    elif "insufficient buying power" in text or code == "40310000":
        category = BROKER_CATEGORY_INSUFFICIENT_BUYING_POWER
        state = BROKER_STATE_BUYING_POWER_LIMITED
    elif (
        "market closed" in text
        or "market is closed" in text
        or "market is not open" in text
        or "outside of trading" in text
    ):
        category = BROKER_CATEGORY_MARKET_CLOSED
    elif "duplicate" in text or "already open" in text:
        category = BROKER_CATEGORY_DUPLICATE_ORDER
        state = BROKER_STATE_ORDER_PENDING
    elif "notional" in text and (
        "too large" in text
        or "exceed" in text
        or "greater" in text
    ):
        category = BROKER_CATEGORY_NOTIONAL_TOO_LARGE
    elif (
        "not tradable" in text
        or "not fractionable" in text
        or "asset" in text
        and "tradable" in text
    ):
        category = BROKER_CATEGORY_ASSET_NOT_TRADABLE

    if normalized_side == "sell" and state != BROKER_STATE_ORDER_PENDING:
        state = BROKER_STATE_EXIT_BLOCKED

    return BrokerConstraint(
        state=state,
        category=category,
        message=payload_message or message,
        side=normalized_side,
        symbol=symbol,
        code=code,
    )


def broker_error_payload(message: str) -> dict[str, Any] | None:
    start = message.find("{")
    if start == -1:
        return None
    try:
        payload = json.loads(message[start:])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


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


def latest_complete_bar(bars: list[dict[str, Any]]) -> dict[str, Any] | None:
    for bar in reversed(bars):
        if "c" in bar:
            return bar
    return None


def parse_market_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = trim_timestamp_fraction(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def trim_timestamp_fraction(value: str) -> str:
    dot_index = value.find(".")
    if dot_index == -1:
        return value

    suffix_index = len(value)
    for index in range(dot_index + 1, len(value)):
        if not value[index].isdigit():
            suffix_index = index
            break

    fraction = value[dot_index + 1 : suffix_index]
    if len(fraction) <= 6:
        return value
    return f"{value[: dot_index + 1]}{fraction[:6]}{value[suffix_index:]}"


def age_seconds(
    timestamp: datetime | None,
    now: datetime | None = None,
) -> float | None:
    if timestamp is None:
        return None
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return max((current.astimezone(timezone.utc) - timestamp).total_seconds(), 0.0)


def bar_end_age_seconds(
    bar_start: datetime | None,
    now: datetime | None = None,
) -> float | None:
    if bar_start is None:
        return None
    return age_seconds(bar_start + timedelta(minutes=1), now)


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
    latest_bar_time: datetime | None

    @property
    def gap_percent(self) -> Decimal:
        if self.slow_sma == 0:
            return Decimal("0")
        return abs(self.fast_sma - self.slow_sma) / self.slow_sma * Decimal("100")

    @property
    def has_cross_context(self) -> bool:
        return (
            len(self.fast_now_values) == len(self.fast_prev_values)
            and len(self.slow_now_values) == len(self.slow_prev_values)
        )

    @property
    def crossed_above(self) -> bool:
        if not self.has_cross_context:
            return False
        return crossed_above(
            self.fast_now_values,
            self.fast_prev_values,
            self.slow_now_values,
            self.slow_prev_values,
        )


@dataclass(frozen=True)
class MarketDataFreshness:
    symbol: str
    latest_bar_time: datetime | None
    latest_bar_close: Decimal | None
    latest_trade_time: datetime | None
    latest_trade_price: Decimal | None
    latest_quote_time: datetime | None
    latest_quote_bid: Decimal | None
    latest_quote_ask: Decimal | None
    bar_age_seconds: float | None
    trade_age_seconds: float | None
    quote_age_seconds: float | None
    trade_error: str | None = None
    quote_error: str | None = None

    @property
    def is_stale(self) -> bool:
        return (
            self.bar_age_seconds is None
            or self.bar_age_seconds > MARKET_DATA_MAX_AGE_SECONDS
        )

    @property
    def has_live_trade_or_quote(self) -> bool:
        return any(
            age is not None and age <= MARKET_DATA_MAX_AGE_SECONDS
            for age in (self.trade_age_seconds, self.quote_age_seconds)
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
class EntryDecision:
    signal: bool
    reason: str


@dataclass(frozen=True)
class AdaptivePosture:
    selected_mode: str
    confidence: str
    reasons: tuple[str, ...]
    constraints: tuple[str, ...]
    active: bool
    shadow: bool


@dataclass(frozen=True)
class EdgeWalkerStatus:
    checked_at: str
    market_open: bool
    next_open: str | None
    next_close: str | None
    buying_power: str | None
    portfolio_value: str | None
    cash: str | None
    position_sizing_mode: str
    position_allocation_percent: str
    effective_position_notional: str | None
    directional_mode: str
    effective_directional_mode: str | None
    adaptive_posture: str | None
    adaptive_confidence: str | None
    adaptive_reasons: list[str]
    adaptive_constraints: list[str]
    adaptive_shadow: bool
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
    data_source: str | None
    data_feed: str | None
    data_status: str | None
    stream_connected: bool | None
    stream_authenticated: bool | None
    stream_subscribed: bool | None
    stream_error: str | None
    stream_bar_count: int | None
    stream_last_message_at: str | None
    latest_bar_time: str | None
    bar_age_seconds: float | None
    latest_trade_time: str | None
    trade_age_seconds: float | None
    latest_quote_time: str | None
    quote_age_seconds: float | None


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

    def get_last_entry_at(self, bot_name: str, symbol: str) -> datetime | None:
        data = self._read()
        raw = data.get("entries", {}).get(bot_name, {}).get(symbol)
        return parse_market_timestamp(raw)

    def set_last_entry_at(
        self,
        bot_name: str,
        symbol: str,
        value: datetime | None = None,
    ) -> None:
        data = self._read()
        entries = data.setdefault("entries", {})
        bot_entries = entries.setdefault(bot_name, {})
        timestamp = value or datetime.now(timezone.utc)
        bot_entries[symbol] = timestamp.astimezone(timezone.utc).isoformat()
        self._write(data)

    def get_regime_state(self) -> dict[str, Any]:
        data = self._read()
        regime_state = data.get("regime", {})
        return regime_state if isinstance(regime_state, dict) else {}

    def set_regime_state(self, regime: str, gap_percent: Decimal) -> None:
        data = self._read()
        data["regime"] = {
            "regime": regime,
            "gap_percent": format_decimal(gap_percent),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write(data)

    def get_pending_orders(self) -> dict[str, dict[str, Any]]:
        data = self._read()
        orders = data.get("orders", {})
        return orders if isinstance(orders, dict) else {}

    def get_pending_order(self, order_id: str) -> dict[str, Any] | None:
        order = self.get_pending_orders().get(order_id)
        return order if isinstance(order, dict) else None

    def track_order(self, order_id: str, metadata: dict[str, Any]) -> None:
        data = self._read()
        orders = data.setdefault("orders", {})
        existing_order = orders.get(order_id)
        existing = existing_order if isinstance(existing_order, dict) else {}
        existing.update(lifecycle_json_value(metadata))
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        orders[order_id] = existing
        self._write(data)

    def clear_order(self, order_id: str) -> None:
        data = self._read()
        orders = data.get("orders", {})
        if order_id in orders:
            del orders[order_id]
            self._write(data)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"trailing": {}, "entries": {}, "regime": {}, "orders": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BotError(f"Invalid bot state file {self.path}") from exc
        if not isinstance(data, dict):
            raise BotError(f"Invalid bot state file {self.path}")
        data.setdefault("trailing", {})
        data.setdefault("entries", {})
        data.setdefault("regime", {})
        data.setdefault("orders", {})
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


class LifecycleLedger:
    def __init__(self, path: Path = LIFECYCLE_PATH_DEFAULT) -> None:
        self.path = path

    def record(self, event_type: str, **fields: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "event_type": event_type,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **{key: lifecycle_json_value(value) for key, value in fields.items()},
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records


class OrderLifecycleTracker:
    ACCEPTED_STATUSES = {
        "accepted",
        "accepted_for_bidding",
        "new",
        "pending_new",
        "partially_filled",
        "filled",
        "done_for_day",
    }
    TERMINAL_STATUSES = {"filled", "canceled", "expired", "rejected"}

    def __init__(
        self,
        client: AlpacaClient,
        state_store: BotStateStore,
        lifecycle_ledger: LifecycleLedger,
        runtime: str,
        dry_run: bool,
    ) -> None:
        self.client = client
        self.state_store = state_store
        self.lifecycle_ledger = lifecycle_ledger
        self.runtime = runtime
        self.dry_run = dry_run

    def track_submitted_order(
        self,
        order: dict[str, Any] | None,
        bot_name: str | None,
        reason: str,
    ) -> None:
        order_id = self._order_id(order)
        if order_id is None or order is None:
            return

        metadata = {
            "bot": bot_name,
            "reason": reason,
            "symbol": order.get("symbol"),
            "side": order.get("side"),
            "last_status": None,
            "last_filled_qty": "0",
            "position_opened_recorded": False,
            "position_closed_recorded": False,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        self.state_store.track_order(order_id, metadata)
        self.reconcile_order(order_id, order)

    def reconcile_pending_orders(self) -> None:
        for order_id in list(self.state_store.get_pending_orders().keys()):
            try:
                order = self.client.get_order(order_id)
            except BotError as exc:
                print(f"[ORDER] {order_id}: reconciliation failed: {exc}")
                continue
            self.reconcile_order(order_id, order)

    def reconcile_order(
        self,
        order_id: str,
        order: dict[str, Any],
    ) -> None:
        pending = self.state_store.get_pending_order(order_id) or {}
        status = self._order_status(order)
        side = self._order_side(order, pending)
        symbol = self._order_symbol(order, pending)
        filled_qty = self._filled_qty(order)
        previous_status = pending.get("last_status")
        previous_filled_qty = optional_decimal_from_api(
            pending.get("last_filled_qty"),
            "last filled qty",
        ) or Decimal("0")
        filled_avg_price = optional_decimal_from_api(
            order.get("filled_avg_price"),
            "filled avg price",
        )
        bot_name = self._field(order, pending, "bot")
        reason = self._field(order, pending, "reason")

        if (
            status in self.ACCEPTED_STATUSES
            and status != previous_status
            and not pending.get("accepted_recorded")
        ):
            self._record(
                LIFECYCLE_ORDER_ACCEPTED,
                order_id=order_id,
                bot=bot_name,
                symbol=symbol,
                side=side,
                status=status,
                reason=reason,
                order=order,
            )
            pending["accepted_recorded"] = True

        if (
            status == "rejected"
            and status != previous_status
            and not pending.get("rejected_recorded")
        ):
            self._record(
                LIFECYCLE_ORDER_REJECTED,
                order_id=order_id,
                bot=bot_name,
                symbol=symbol,
                side=side,
                status=status,
                reason=reason,
                error=str(order.get("reject_reason") or "order rejected"),
                order=order,
            )
            pending["rejected_recorded"] = True

        if filled_qty > previous_filled_qty:
            fill_event = (
                LIFECYCLE_FULL_FILL
                if status == "filled"
                else LIFECYCLE_PARTIAL_FILL
            )
            fill_delta = filled_qty - previous_filled_qty
            self._record(
                fill_event,
                order_id=order_id,
                bot=bot_name,
                symbol=symbol,
                side=side,
                status=status,
                filled_qty=filled_qty,
                fill_delta_qty=fill_delta,
                filled_avg_price=filled_avg_price,
                reason=reason,
                order=order,
            )
            if side == "buy" and not pending.get("position_opened_recorded"):
                self._record(
                    LIFECYCLE_POSITION_OPENED,
                    order_id=order_id,
                    bot=bot_name,
                    symbol=symbol,
                    side=side,
                    qty=filled_qty,
                    avg_entry_price=filled_avg_price,
                    reason=reason,
                )
                pending["position_opened_recorded"] = True
            if (
                side == "sell"
                and status == "filled"
                and not pending.get("position_closed_recorded")
            ):
                self._record(
                    LIFECYCLE_POSITION_CLOSED,
                    order_id=order_id,
                    bot=bot_name,
                    symbol=symbol,
                    side=side,
                    qty=filled_qty,
                    exit_price=filled_avg_price,
                    reason=reason,
                )
                pending["position_closed_recorded"] = True

        pending.update(
            {
                "bot": bot_name,
                "reason": reason,
                "symbol": symbol,
                "side": side,
                "last_status": status,
                "last_filled_qty": format_decimal(filled_qty),
                "accepted_recorded": pending.get("accepted_recorded", False),
                "position_opened_recorded": pending.get(
                    "position_opened_recorded",
                    False,
                ),
                "position_closed_recorded": pending.get(
                    "position_closed_recorded",
                    False,
                ),
                "rejected_recorded": pending.get("rejected_recorded", False),
            }
        )

        if status in self.TERMINAL_STATUSES:
            self.state_store.clear_order(order_id)
        else:
            self.state_store.track_order(order_id, pending)

    def _record(self, event_type: str, **fields: Any) -> None:
        payload = {
            "runtime": self.runtime,
            "dry_run": self.dry_run,
        }
        payload.update(fields)
        self.lifecycle_ledger.record(event_type, **payload)

    def _field(
        self,
        order: dict[str, Any],
        pending: dict[str, Any],
        key: str,
    ) -> str | None:
        value = order.get(key) or pending.get(key)
        return str(value) if value not in (None, "") else None

    def _order_id(self, order: dict[str, Any] | None) -> str | None:
        if not order:
            return None
        value = order.get("id")
        return str(value) if value else None

    def _order_status(self, order: dict[str, Any]) -> str:
        return str(order.get("status") or "unknown").lower()

    def _order_side(
        self,
        order: dict[str, Any],
        pending: dict[str, Any],
    ) -> str | None:
        value = order.get("side") or pending.get("side")
        return str(value).lower() if value else None

    def _order_symbol(
        self,
        order: dict[str, Any],
        pending: dict[str, Any],
    ) -> str | None:
        value = order.get("symbol") or pending.get("symbol")
        return str(value) if value else None

    def _filled_qty(self, order: dict[str, Any]) -> Decimal:
        filled_qty = optional_decimal_from_api(order.get("filled_qty"), "filled qty")
        if filled_qty is not None:
            return filled_qty
        if self._order_status(order) == "filled":
            return optional_decimal_from_api(order.get("qty"), "order qty") or Decimal(
                "0"
            )
        return Decimal("0")


class TrailingStopBot:
    def __init__(
        self,
        config: BotConfig,
        client: AlpacaClient,
        state_store: BotStateStore | None = None,
        market_data: Any | None = None,
        lifecycle_ledger: LifecycleLedger | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.state_store = state_store or BotStateStore()
        self.market_data = market_data
        self.lifecycle_ledger = lifecycle_ledger or LifecycleLedger()
        self.order_tracker = OrderLifecycleTracker(
            self.client,
            self.state_store,
            self.lifecycle_ledger,
            "TrailingStopBot",
            self.config.dry_run,
        )

    def _record_lifecycle(self, event_type: str, **fields: Any) -> None:
        payload = {
            "runtime": "TrailingStopBot",
            "dry_run": self.config.dry_run,
        }
        payload.update(fields)
        self.lifecycle_ledger.record(event_type, **payload)

    def _broker_rejection_payload(
        self,
        exc: BotError,
        side: str,
        symbol: str,
    ) -> dict[str, Any]:
        return broker_constraint_payload(
            classify_broker_error(str(exc), side=side, symbol=symbol)
        )

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
        self.order_tracker.reconcile_pending_orders()

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
        self._record_lifecycle(
            LIFECYCLE_INTENDED_EXIT,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason="closeout_window",
            seconds_to_close=seconds_to_close,
        )
        try:
            order = self.client.submit_market_sell_qty(symbol, qty)
        except BotError as exc:
            self._record_lifecycle(
                LIFECYCLE_ORDER_REJECTED,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="closeout_window",
                error=str(exc),
                broker_constraint=self._broker_rejection_payload(exc, "sell", symbol),
            )
            raise
        self._record_lifecycle(
            LIFECYCLE_ORDER_SUBMITTED,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason="closeout_window",
            order=order,
        )
        self.order_tracker.track_submitted_order(order, None, "closeout_window")
        self.state_store.clear_symbol(symbol)

    def _manage_trailing_stop(
        self,
        symbol: str,
        position: dict[str, Any],
        symbol_orders: list[dict[str, Any]],
        require_live_mark: bool = False,
    ) -> None:
        if any(order.get("side") == "sell" for order in symbol_orders):
            print(f"{symbol}: sell order already open; waiting for it to resolve.")
            return

        qty = decimal_from_api(position.get("qty"), "position qty")
        if qty <= 0:
            print(f"{symbol}: non-long position qty={qty}; no trailing stop submitted.")
            return

        current_price = self._latest_price(symbol, require_live_mark=require_live_mark)
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
            f"[RISK] {symbol}: position qty={format_decimal(qty)} current={current_price:.4f} "
            f"hwm={high_water_mark:.4f} bot_stop={stop_price:.4f}"
        )
        stop_breached = current_price <= stop_price
        self._record_lifecycle(
            LIFECYCLE_POSITION_MANAGED,
            symbol=symbol,
            side="long",
            qty=qty,
            current_price=current_price,
            avg_entry_price=avg_entry_price,
            high_water_mark=high_water_mark,
            stop_price=stop_price,
            stop_breached=stop_breached,
            require_live_mark=require_live_mark,
        )

        if stop_breached:
            print(f"[RISK] {symbol}: trailing stop breached; submitting fractional market sell.")
            self._record_lifecycle(
                LIFECYCLE_INTENDED_EXIT,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="trailing_stop_breached",
                current_price=current_price,
                stop_price=stop_price,
                high_water_mark=high_water_mark,
            )
            try:
                order = self.client.submit_market_sell_qty(symbol, qty)
            except BotError as exc:
                self._record_lifecycle(
                    LIFECYCLE_ORDER_REJECTED,
                    symbol=symbol,
                    side="sell",
                    qty=qty,
                    reason="trailing_stop_breached",
                    error=str(exc),
                    broker_constraint=self._broker_rejection_payload(exc, "sell", symbol),
                )
                raise
            self._record_lifecycle(
                LIFECYCLE_ORDER_SUBMITTED,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="trailing_stop_breached",
                order=order,
            )
            self.order_tracker.track_submitted_order(
                order,
                None,
                "trailing_stop_breached",
            )
            self.state_store.clear_symbol(symbol)
        else:
            print(f"[RISK] {symbol}: trailing stop holding.")

    def _latest_price(
        self,
        symbol: str,
        require_live_mark: bool = False,
    ) -> Decimal | None:
        max_age_seconds = MARKET_DATA_MAX_AGE_SECONDS if require_live_mark else None
        current_mark = self._latest_market_mark(symbol, max_age_seconds=max_age_seconds)
        if current_mark is not None:
            return current_mark

        if require_live_mark:
            return None

        bars = self._recent_bars(symbol, 1)
        prices = latest_close_prices(bars)
        if not prices:
            return None
        return prices[-1]

    def _sma_snapshot(
        self,
        symbol: str,
        require_cross_context: bool = True,
    ) -> SmaSnapshot | None:
        bars_needed = self.config.slow_sma_minutes + (1 if require_cross_context else 0)
        bars = self._recent_bars(symbol, bars_needed)
        prices = latest_close_prices(bars)
        latest_bar = latest_complete_bar(bars)
        latest_bar_time = (
            parse_market_timestamp(latest_bar.get("t")) if latest_bar else None
        )
        if len(prices) < bars_needed:
            reason = "warming up." if not require_cross_context else "waiting for more data."
            print(
                f"{symbol}: need {bars_needed} one-minute bars, got {len(prices)}; "
                f"{reason}"
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
            latest_bar_time=latest_bar_time,
        )

    def _recent_bars(self, symbol: str, minutes: int) -> list[dict[str, Any]]:
        if self.market_data is not None:
            return self.market_data.get_recent_bars(symbol, minutes)
        return self.client.get_recent_bars(symbol, minutes)

    def _latest_market_mark(
        self,
        symbol: str,
        max_age_seconds: int | None = None,
    ) -> Decimal | None:
        data_source = self.market_data or self.client

        quote = data_source.get_latest_quote(symbol)
        if quote and self._market_timestamp_is_recent(quote.get("t"), max_age_seconds):
            bid = optional_decimal_from_api(quote.get("bp"), "latest quote bid")
            ask = optional_decimal_from_api(quote.get("ap"), "latest quote ask")
            if bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid:
                return (bid + ask) / Decimal("2")

        trade = data_source.get_latest_trade(symbol)
        if trade and self._market_timestamp_is_recent(trade.get("t"), max_age_seconds):
            return optional_decimal_from_api(trade.get("p"), "latest trade price")

        return None

    def _market_timestamp_is_recent(
        self,
        value: Any,
        max_age_seconds: int | None,
    ) -> bool:
        if max_age_seconds is None:
            return True
        timestamp = parse_market_timestamp(value)
        current_age = age_seconds(timestamp)
        return current_age is not None and current_age <= max_age_seconds

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
        self._record_lifecycle(
            LIFECYCLE_INTENDED_ENTRY,
            symbol=symbol,
            side="buy",
            notional=self.config.position_notional,
            reason="sma_crossed_above",
        )
        try:
            order = self.client.submit_market_buy(symbol, self.config.position_notional)
        except BotError as exc:
            self._record_lifecycle(
                LIFECYCLE_ORDER_REJECTED,
                symbol=symbol,
                side="buy",
                notional=self.config.position_notional,
                reason="sma_crossed_above",
                error=str(exc),
                broker_constraint=self._broker_rejection_payload(exc, "buy", symbol),
            )
            raise
        self._record_lifecycle(
            LIFECYCLE_ORDER_SUBMITTED,
            symbol=symbol,
            side="buy",
            notional=self.config.position_notional,
            reason="sma_crossed_above",
            order=order,
        )
        self.order_tracker.track_submitted_order(order, None, "sma_crossed_above")


class RegimeDetector:
    def __init__(
        self,
        config: BotConfig,
        client: AlpacaClient,
        market_data: Any | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.market_data = market_data

    def detect(self) -> tuple[RegimeSignal | None, SmaSnapshot | None]:
        probe = TrailingStopBot(
            config_for_symbol(self.config, SOXL),
            self.client,
            market_data=self.market_data,
        )
        snapshot = probe._sma_snapshot(SOXL, require_cross_context=False)
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
        market_data: Any | None = None,
        lifecycle_ledger: LifecycleLedger | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.state_store = state_store or BotStateStore()
        self.market_data = market_data
        self.lifecycle_ledger = lifecycle_ledger or LifecycleLedger()
        self.order_tracker = OrderLifecycleTracker(
            self.client,
            self.state_store,
            self.lifecycle_ledger,
            "EdgeWalker",
            self.config.dry_run,
        )
        self._latest_freshness: MarketDataFreshness | None = None
        self._adaptive_posture: AdaptivePosture | None = None

    def _record_lifecycle(self, event_type: str, **fields: Any) -> None:
        payload = {
            "runtime": "EdgeWalker",
            "dry_run": self.config.dry_run,
        }
        payload.update(fields)
        self.lifecycle_ledger.record(event_type, **payload)

    def _broker_rejection_payload(
        self,
        exc: BotError,
        side: str,
        symbol: str,
    ) -> dict[str, Any]:
        return broker_constraint_payload(
            classify_broker_error(str(exc), side=side, symbol=symbol)
        )

    def run_once(self) -> EdgeWalkerStatus:
        self._latest_freshness = None
        self._adaptive_posture = None
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
            f"[SYSTEM] [{checked_at}] "
            f"edgewalker=True market_open={market_open} "
            f"next_close={next_close_text} "
            f"buying_power={account.get('buying_power')} "
            f"portfolio_value={account.get('portfolio_value')}"
        )
        self.order_tracker.reconcile_pending_orders()

        detector = RegimeDetector(self.config, self.client, self.market_data)
        signal, soxl_snapshot = detector.detect()
        if signal is None or soxl_snapshot is None:
            self.state_store.set_regime_state(WARMUP, Decimal("0"))
            self._print_market_data_status(SOXL)
            print(
                "[REGIME] regime=WARMUP active_bot=NONE routed_symbol=NONE "
                "entry_signal=False action_taken=collecting_data"
            )
            positions = {
                symbol: self.client.get_position(symbol)
                for symbol in self.basket_symbols
            }
            if closeout_due:
                orders = self.client.list_open_orders()
                action_taken = self._liquidate_all_before_close(
                    positions,
                    orders,
                    seconds_to_close,
                )
                return self._build_status(
                    checked_at,
                    market_open,
                    next_open,
                    next_close,
                    account,
                    None,
                    None,
                    positions,
                    False,
                    action_taken,
                    regime_override=WARMUP,
                )

            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                None,
                None,
                positions,
                False,
                "collecting_data",
                regime_override=WARMUP,
            )

        previous_regime_state = self.state_store.get_regime_state()
        signal = self._apply_regime_hysteresis(signal, previous_regime_state)
        self.state_store.set_regime_state(signal.regime, signal.gap_percent)
        route = RegimeRouter().route(signal.regime)
        routed_symbol = route.routed_symbol or "NONE"
        strength = self._regime_strength(signal)
        print(
            f"[REGIME] {SOXL} regime check: price={signal.price:.4f} "
            f"fast_sma={signal.fast_sma:.4f} slow_sma={signal.slow_sma:.4f} "
            f"gap={signal.gap_percent:.2f}% threshold={self.config.regime_gap_threshold}% "
            f"exit_threshold={self._regime_exit_threshold()}% "
            f"strength={strength}"
        )
        print(
            f"[ROUTER] regime={signal.regime} active_bot={route.active_bot} "
            f"routed_symbol={routed_symbol}"
        )

        orders = self.client.list_open_orders()
        positions = {symbol: self.client.get_position(symbol) for symbol in self.basket_symbols}
        freshness = self._market_data_freshness(SOXL, soxl_snapshot)
        self._latest_freshness = freshness

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
            print(
                "[SYSTEM] market is closed; "
                "entry_signal=False action_taken=no_entry"
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
                "no_entry",
            )

        self._maybe_update_adaptive_posture(
            signal,
            route,
            freshness,
            positions,
            account,
            previous_regime_state,
        )

        market_data_blocks_entries = freshness.is_stale or self._market_data_blocks_trading(
            SOXL
        )
        if market_data_blocks_entries:
            active_symbol, active_position = self._active_position(positions)
            if active_symbol and active_position:
                symbol_orders = [
                    order for order in orders if order.get("symbol") == active_symbol
                ]
                print(
                    "[DATA] bar data is not fresh enough for entries; "
                    "regime exits paused, live risk management remains active."
                )
                risk_bot = TrailingStopBot(
                    config_for_symbol(self.config, active_symbol),
                    self.client,
                    self.state_store,
                    self.market_data,
                    self.lifecycle_ledger,
                )
                risk_bot._manage_trailing_stop(
                    active_symbol,
                    active_position,
                    symbol_orders,
                    require_live_mark=True,
                )
                print("entry_signal=False action_taken=manage_open_position_stale_bars")
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
                    "manage_open_position_stale_bars",
                )

        if freshness.is_stale:
            print(
                "[DATA] stale market data; "
                "entry_signal=False action_taken=wait_stale_market_data"
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
                "wait_stale_market_data",
            )

        if self._market_data_blocks_trading(SOXL):
            status = self._market_data_status(SOXL)
            print(
                "[DATA] stream market data is not live; "
                f"data_status={status.get('data_status')} "
                "entry_signal=False action_taken=wait_stream_market_data"
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
                "wait_stream_market_data",
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
            print("[ENTRY] BLOCKED reason=route_disallows_entry")
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
            self.market_data,
            self.lifecycle_ledger,
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
                f"[ENTRY] {route.routed_symbol}: buy order already open; "
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

        entry_decision = self._entry_decision_for_route(route, soxl_snapshot)
        entry_signal = entry_decision.signal
        print(
            f"[ENTRY] {route.active_bot} check: "
            f"entry_signal={entry_signal} reason={entry_decision.reason} "
            f"mode={self._directional_mode_for_route(route)}"
        )
        print(f"entry_signal={entry_signal}")
        if not entry_signal:
            print(
                f"[ENTRY] BLOCKED bot={route.active_bot} "
                f"symbol={route.routed_symbol} reason={entry_decision.reason} "
                f"mode={self._directional_mode_for_route(route)}"
            )
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
                f"[ENTRY] {route.routed_symbol}: asset is not fractionable; "
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
            f"[ENTRY] APPROVED bot={route.active_bot} "
            f"symbol={route.routed_symbol} reason={entry_decision.reason} "
            f"mode={self._directional_mode_for_route(route)}"
        )
        effective_notional, requested_notional, buying_power = (
            self._effective_position_notional(account)
        )
        if effective_notional is None or effective_notional <= 0:
            print(
                "[ENTRY] BLOCKED reason=insufficient_buying_power "
                f"buying_power={format_decimal(buying_power) if buying_power is not None else 'unknown'}"
            )
            print("entry_signal=False action_taken=insufficient_buying_power")
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
                "insufficient_buying_power",
            )

        allocation_text = (
            f" allocation={format_decimal(self.config.position_allocation_percent)}%"
            if self.config.position_sizing_mode == POSITION_SIZING_DYNAMIC
            else ""
        )
        requested_text = (
            format_decimal(requested_notional) if requested_notional is not None else "unknown"
        )
        buying_power_text = format_decimal(buying_power) if buying_power is not None else "unknown"
        print(
            "[RISK] position sizing: "
            f"mode={self.config.position_sizing_mode}{allocation_text} "
            f"buying_power={buying_power_text} requested=${requested_text} "
            f"effective=${format_decimal(effective_notional)}"
        )
        print(
            f"[TRADE] {route.active_bot}: submitting ${format_decimal(effective_notional)} "
            f"market buy for {route.routed_symbol}."
        )
        self._record_lifecycle(
            LIFECYCLE_INTENDED_ENTRY,
            bot=route.active_bot,
            symbol=route.routed_symbol,
            side="buy",
            notional=effective_notional,
            requested_notional=requested_notional,
            buying_power=buying_power,
            position_sizing_mode=self.config.position_sizing_mode,
            position_allocation_percent=self.config.position_allocation_percent,
            regime=signal.regime,
            reason=entry_decision.reason,
            mode=self._directional_mode_for_route(route),
        )
        try:
            order = self.client.submit_market_buy(route.routed_symbol, effective_notional)
        except BotError as exc:
            self._record_lifecycle(
                LIFECYCLE_ORDER_REJECTED,
                bot=route.active_bot,
                symbol=route.routed_symbol,
                side="buy",
                notional=effective_notional,
                requested_notional=requested_notional,
                buying_power=buying_power,
                regime=signal.regime,
                reason=entry_decision.reason,
                mode=self._directional_mode_for_route(route),
                error=str(exc),
                broker_constraint=self._broker_rejection_payload(
                    exc,
                    "buy",
                    route.routed_symbol,
                ),
            )
            raise
        self._record_lifecycle(
            LIFECYCLE_ORDER_SUBMITTED,
            bot=route.active_bot,
            symbol=route.routed_symbol,
            side="buy",
            notional=effective_notional,
            requested_notional=requested_notional,
            buying_power=buying_power,
            regime=signal.regime,
            reason=entry_decision.reason,
            mode=self._directional_mode_for_route(route),
            order=order,
        )
        self.order_tracker.track_submitted_order(
            order,
            route.active_bot,
            entry_decision.reason,
        )
        if not self.config.dry_run:
            self.state_store.set_position_owner(route.routed_symbol, route.active_bot)
            self.state_store.set_last_entry_at(route.active_bot, route.routed_symbol)
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
        regime_override: str | None = None,
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
        data_status = self._market_data_status(SOXL)
        freshness = self._latest_freshness
        effective_notional, _, _ = self._effective_position_notional(account)
        adaptive = self._adaptive_posture
        effective_directional_mode = self._current_effective_directional_mode()

        return EdgeWalkerStatus(
            checked_at=checked_at,
            market_open=market_open,
            next_open=next_open.isoformat(timespec="seconds") if next_open else None,
            next_close=next_close.isoformat(timespec="seconds") if next_close else None,
            buying_power=self._raw_text(account.get("buying_power")),
            portfolio_value=self._raw_text(account.get("portfolio_value") or account.get("equity")),
            cash=self._raw_text(account.get("cash")),
            position_sizing_mode=self.config.position_sizing_mode,
            position_allocation_percent=format_decimal(
                self.config.position_allocation_percent
            ),
            effective_position_notional=self._decimal_text(effective_notional),
            directional_mode=self.config.directional_mode,
            effective_directional_mode=effective_directional_mode,
            adaptive_posture=adaptive.selected_mode if adaptive else None,
            adaptive_confidence=adaptive.confidence if adaptive else None,
            adaptive_reasons=list(adaptive.reasons) if adaptive else [],
            adaptive_constraints=list(adaptive.constraints) if adaptive else [],
            adaptive_shadow=bool(adaptive and adaptive.shadow),
            day_pl=self._decimal_text(day_pl),
            day_pl_percent=self._decimal_text(day_pl_percent),
            source_symbol=SOXL,
            source_price=self._decimal_text(signal.price if signal else None),
            fast_sma=self._decimal_text(signal.fast_sma if signal else None),
            slow_sma=self._decimal_text(signal.slow_sma if signal else None),
            gap_percent=self._decimal_text(signal.gap_percent if signal else None),
            regime=regime_override or (signal.regime if signal else None),
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
            data_source=data_status.get("data_source"),
            data_feed=data_status.get("data_feed"),
            data_status=data_status.get("data_status"),
            stream_connected=data_status.get("stream_connected"),
            stream_authenticated=data_status.get("stream_authenticated"),
            stream_subscribed=data_status.get("stream_subscribed"),
            stream_error=data_status.get("stream_error"),
            stream_bar_count=data_status.get("stream_bar_count"),
            stream_last_message_at=data_status.get("stream_last_message_at"),
            latest_bar_time=(
                self._time_text(freshness.latest_bar_time)
                if freshness
                else data_status.get("latest_bar_time")
            ),
            bar_age_seconds=(
                self._rounded_seconds(freshness.bar_age_seconds)
                if freshness
                else data_status.get("bar_age_seconds")
            ),
            latest_trade_time=(
                self._time_text(freshness.latest_trade_time)
                if freshness
                else data_status.get("latest_trade_time")
            ),
            trade_age_seconds=(
                self._rounded_seconds(freshness.trade_age_seconds)
                if freshness
                else data_status.get("trade_age_seconds")
            ),
            latest_quote_time=(
                self._time_text(freshness.latest_quote_time)
                if freshness
                else data_status.get("latest_quote_time")
            ),
            quote_age_seconds=(
                self._rounded_seconds(freshness.quote_age_seconds)
                if freshness
                else data_status.get("quote_age_seconds")
            ),
        )

    def _current_effective_directional_mode(self) -> str | None:
        if self.config.directional_mode == DIRECTIONAL_MODE_ADAPTIVE:
            if self._adaptive_posture is None:
                return None
            return self._adaptive_posture.selected_mode
        return self.config.directional_mode

    def _active_position(
        self,
        positions: dict[str, dict[str, Any] | None],
    ) -> tuple[str | None, dict[str, Any] | None]:
        for symbol in self.basket_symbols:
            position = positions.get(symbol)
            if self._position_qty(position) > 0:
                return str(position.get("symbol") or symbol), position
        return None, None

    def _effective_position_notional(
        self,
        account: dict[str, Any],
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        buying_power = optional_decimal_from_api(
            account.get("buying_power"),
            "buying power",
        )
        if self.config.position_sizing_mode == POSITION_SIZING_DYNAMIC:
            if buying_power is None:
                return None, None, buying_power
            requested = buying_power * (
                self.config.position_allocation_percent / Decimal("100")
            )
        else:
            requested = self.config.position_notional

        effective = requested
        if buying_power is not None:
            max_notional = buying_power * (
                (Decimal("100") - BUYING_POWER_ORDER_BUFFER_PERCENT) / Decimal("100")
            )
            effective = min(requested, max_notional)

        return (
            effective.quantize(MONEY_STEP, rounding=ROUND_DOWN),
            requested.quantize(MONEY_STEP, rounding=ROUND_DOWN),
            buying_power,
        )

    def _maybe_update_adaptive_posture(
        self,
        signal: RegimeSignal,
        route: BotRoute,
        freshness: MarketDataFreshness,
        positions: dict[str, dict[str, Any] | None],
        account: dict[str, Any],
        previous_regime_state: dict[str, Any] | None = None,
    ) -> None:
        if not self._adaptive_should_evaluate():
            return

        posture = self._select_adaptive_posture(
            signal,
            route,
            freshness,
            positions,
            account,
            previous_regime_state,
        )
        self._adaptive_posture = posture
        scope = "ACTIVE" if posture.active else "SHADOW"
        reasons = ",".join(posture.reasons) if posture.reasons else "none"
        constraints = ",".join(posture.constraints) if posture.constraints else "none"
        print(
            f"[ADAPTIVE] posture={posture.selected_mode} "
            f"confidence={posture.confidence} scope={scope} "
            f"reasons={reasons} constraints={constraints}"
        )
        self._record_lifecycle(
            LIFECYCLE_ADAPTIVE_POSTURE_SELECTED,
            selected_posture=posture.selected_mode,
            confidence=posture.confidence,
            active=posture.active,
            shadow=posture.shadow,
            configured_directional_mode=self.config.directional_mode,
            reasons=posture.reasons,
            constraints=posture.constraints,
            regime=signal.regime,
            regime_strength=self._regime_strength(signal),
            gap_percent=signal.gap_percent,
            active_bot=route.active_bot,
            routed_symbol=route.routed_symbol,
            position_symbol=self._active_position(positions)[0],
        )

    def _adaptive_should_evaluate(self) -> bool:
        return (
            self.config.directional_mode == DIRECTIONAL_MODE_ADAPTIVE
            or self.config.adaptive_shadow_enabled
        )

    def _select_adaptive_posture(
        self,
        signal: RegimeSignal,
        route: BotRoute,
        freshness: MarketDataFreshness,
        positions: dict[str, dict[str, Any] | None],
        account: dict[str, Any],
        previous_regime_state: dict[str, Any] | None = None,
    ) -> AdaptivePosture:
        active = self.config.directional_mode == DIRECTIONAL_MODE_ADAPTIVE
        shadow = not active
        reasons: list[str] = []
        constraints: list[str] = []
        selected_mode = DIRECTIONAL_MODE_BALANCED
        confidence = "MODERATE"

        active_position_symbol, _active_position = self._active_position(positions)
        stream_not_live = self._market_data_blocks_trading(SOXL)
        effective_notional, _requested_notional, buying_power = (
            self._effective_position_notional(account)
        )

        if active_position_symbol:
            constraints.append("position_open")
            reasons.append("adaptive_entry_posture_paused")
            selected_mode = DIRECTIONAL_MODE_BALANCED
            confidence = "HIGH"
        elif freshness.is_stale:
            constraints.append("bars_stale")
            reasons.append("entries_require_fresh_bars")
            selected_mode = DIRECTIONAL_MODE_CONSERVATIVE
            confidence = "HIGH"
        elif stream_not_live:
            constraints.append("stream_not_live")
            reasons.append("entries_require_live_stream")
            selected_mode = DIRECTIONAL_MODE_CONSERVATIVE
            confidence = "HIGH"
        elif effective_notional is None or effective_notional <= 0:
            constraints.append("buying_power_limited")
            reasons.append("effective_notional_unavailable")
            selected_mode = DIRECTIONAL_MODE_CONSERVATIVE
            confidence = "HIGH"
        elif route.active_bot == CHOP_BOT:
            reasons.append("sideways_route_chopbot")
            reasons.append("directional_posture_standby")
            selected_mode = DIRECTIONAL_MODE_BALANCED
            confidence = "LOW"
        else:
            strength = self._regime_strength(signal)
            if strength == REGIME_STRENGTH_STRONG:
                reasons.append("strong_directional_regime")
                selected_mode = DIRECTIONAL_MODE_AGGRESSIVE
                confidence = "HIGH"
            elif strength == REGIME_STRENGTH_MODERATE:
                reasons.append("moderate_directional_regime")
                selected_mode = DIRECTIONAL_MODE_BALANCED
                confidence = "MODERATE"
            else:
                reasons.append("weak_directional_regime")
                selected_mode = DIRECTIONAL_MODE_CONSERVATIVE
                confidence = "LOW"

        previous_regime_source = (
            previous_regime_state or self.state_store.get_regime_state()
        )
        previous_regime = str(previous_regime_source.get("regime") or "").upper()
        if previous_regime and previous_regime != signal.regime:
            constraints.append("regime_shift_detected")
            if selected_mode == DIRECTIONAL_MODE_AGGRESSIVE:
                selected_mode = DIRECTIONAL_MODE_BALANCED
                reasons.append("fresh_regime_shift_tempers_aggression")

        if buying_power is None:
            constraints.append("buying_power_unknown")

        if not reasons:
            reasons.append("default_balanced_posture")

        return AdaptivePosture(
            selected_mode=selected_mode,
            confidence=confidence,
            reasons=tuple(reasons),
            constraints=tuple(constraints),
            active=active,
            shadow=shadow,
        )

    def _apply_regime_hysteresis(
        self,
        signal: RegimeSignal,
        previous_regime_state: dict[str, Any] | None = None,
    ) -> RegimeSignal:
        raw_regime = signal.regime
        previous_regime_source = (
            previous_regime_state or self.state_store.get_regime_state()
        )
        previous_regime = str(previous_regime_source.get("regime") or "").upper()
        directional_regime = self._directional_regime_for_signal(signal)
        exit_threshold = self._regime_exit_threshold()

        if (
            raw_regime == SIDEWAYS
            and previous_regime in {UPTREND, DOWNTREND}
            and directional_regime == previous_regime
            and signal.gap_percent >= exit_threshold
        ):
            print(
                "[REGIME] hysteresis hold: "
                f"raw={raw_regime} previous={previous_regime} "
                f"gap={signal.gap_percent:.2f}% "
                f"exit_threshold={exit_threshold}%"
            )
            return RegimeSignal(
                source_symbol=signal.source_symbol,
                price=signal.price,
                fast_sma=signal.fast_sma,
                slow_sma=signal.slow_sma,
                gap_percent=signal.gap_percent,
                regime=previous_regime,
            )

        return signal

    def _directional_regime_for_signal(self, signal: RegimeSignal) -> str:
        if signal.fast_sma > signal.slow_sma:
            return UPTREND
        if signal.fast_sma < signal.slow_sma:
            return DOWNTREND
        return SIDEWAYS

    def _regime_exit_threshold(self) -> Decimal:
        return min(self.config.regime_exit_gap_threshold, self.config.regime_gap_threshold)

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

    def _regime_strength(self, signal: RegimeSignal) -> str:
        return self._strength_for_gap(signal.regime, signal.gap_percent)

    def _strength_for_gap(self, regime: str, gap_percent: Decimal) -> str:
        threshold = self.config.regime_gap_threshold
        if regime == SIDEWAYS or threshold <= 0:
            return REGIME_STRENGTH_RANGE
        if gap_percent < threshold * Decimal("1.5"):
            return REGIME_STRENGTH_WEAK
        if gap_percent < threshold * Decimal("3"):
            return REGIME_STRENGTH_MODERATE
        return REGIME_STRENGTH_STRONG

    def _strength_meets_minimum(self, strength: str) -> bool:
        return REGIME_STRENGTH_ORDER.get(strength, 0) >= REGIME_STRENGTH_ORDER.get(
            self.config.directional_min_strength,
            REGIME_STRENGTH_ORDER[REGIME_STRENGTH_MODERATE],
        )

    def _market_data_status(self, symbol: str) -> dict[str, Any]:
        if self.market_data is None:
            status = "LIVE" if self._latest_freshness and not self._latest_freshness.is_stale else "REST"
            return {
                "data_source": "rest",
                "data_feed": self.config.data_feed,
                "data_status": status,
                "stream_connected": None,
                "stream_authenticated": None,
                "stream_subscribed": None,
                "stream_error": None,
                "stream_bar_count": None,
                "stream_last_message_at": None,
                "latest_bar_time": None,
                "bar_age_seconds": None,
                "latest_trade_time": None,
                "trade_age_seconds": None,
                "latest_quote_time": None,
                "quote_age_seconds": None,
            }

        return self.market_data.status(
            symbol,
            required_bars=self.config.slow_sma_minutes,
        )

    def _print_market_data_status(self, symbol: str) -> None:
        status = self._market_data_status(symbol)
        print(f"[DATA] HEALTH {self._status_summary(status)}")
        if status.get("stream_error"):
            print(f"[DATA] ERROR stream_error={status.get('stream_error')}")

    def _market_data_blocks_trading(self, symbol: str) -> bool:
        if self.market_data is None:
            return False
        return self._market_data_status(symbol).get("data_status") != "LIVE"

    def _market_data_freshness(
        self,
        symbol: str,
        snapshot: SmaSnapshot,
    ) -> MarketDataFreshness:
        now = datetime.now(timezone.utc)
        trade = None
        quote = None
        trade_error = None
        quote_error = None

        data_source = self.market_data or self.client

        try:
            trade = data_source.get_latest_trade(symbol)
        except BotError as exc:
            trade_error = str(exc)

        try:
            quote = data_source.get_latest_quote(symbol)
        except BotError as exc:
            quote_error = str(exc)

        latest_trade_time = parse_market_timestamp(trade.get("t")) if trade else None
        latest_quote_time = parse_market_timestamp(quote.get("t")) if quote else None
        freshness = MarketDataFreshness(
            symbol=symbol,
            latest_bar_time=snapshot.latest_bar_time,
            latest_bar_close=snapshot.price,
            latest_trade_time=latest_trade_time,
            latest_trade_price=(
                optional_decimal_from_api(trade.get("p"), "latest trade price")
                if trade
                else None
            ),
            latest_quote_time=latest_quote_time,
            latest_quote_bid=(
                optional_decimal_from_api(quote.get("bp"), "latest quote bid")
                if quote
                else None
            ),
            latest_quote_ask=(
                optional_decimal_from_api(quote.get("ap"), "latest quote ask")
                if quote
                else None
            ),
            bar_age_seconds=bar_end_age_seconds(snapshot.latest_bar_time, now),
            trade_age_seconds=age_seconds(latest_trade_time, now),
            quote_age_seconds=age_seconds(latest_quote_time, now),
            trade_error=trade_error,
            quote_error=quote_error,
        )
        print(f"[DATA] HEALTH {self._freshness_summary(freshness)}")
        if freshness.is_stale or freshness.trade_error or freshness.quote_error:
            print(f"[DATA] DETAILS market_data_freshness={self._freshness_payload(freshness)}")
        return freshness

    def _freshness_payload(self, freshness: MarketDataFreshness) -> str:
        payload = {
            "symbol": freshness.symbol,
            "now": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "latestBarTime": self._time_text(freshness.latest_bar_time),
            "latestBarClose": self._float_value(freshness.latest_bar_close),
            "latestTradeTime": self._time_text(freshness.latest_trade_time),
            "latestTradePrice": self._float_value(freshness.latest_trade_price),
            "latestQuoteTime": self._time_text(freshness.latest_quote_time),
            "latestQuoteBid": self._float_value(freshness.latest_quote_bid),
            "latestQuoteAsk": self._float_value(freshness.latest_quote_ask),
            "barAgeSeconds": self._rounded_seconds(freshness.bar_age_seconds),
            "tradeAgeSeconds": self._rounded_seconds(freshness.trade_age_seconds),
            "quoteAgeSeconds": self._rounded_seconds(freshness.quote_age_seconds),
            "maxAgeSeconds": MARKET_DATA_MAX_AGE_SECONDS,
            "isStale": freshness.is_stale,
        }
        if freshness.trade_error:
            payload["latestTradeError"] = freshness.trade_error
        if freshness.quote_error:
            payload["latestQuoteError"] = freshness.quote_error
        return json.dumps(payload, sort_keys=True)

    def _time_text(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00",
            "Z",
        )

    def _float_value(self, value: Decimal | None) -> float | None:
        if value is None:
            return None
        return float(value)

    def _rounded_seconds(self, value: float | None) -> float | None:
        if value is None:
            return None
        return round(value, 3)

    def _freshness_summary(self, freshness: MarketDataFreshness) -> str:
        status = self._market_data_status(freshness.symbol)
        stream_state = "CONNECTED" if status.get("stream_connected") else "DISCONNECTED"
        if status.get("data_status") and status.get("data_status") not in {"LIVE", "REST"}:
            stream_state = str(status.get("data_status"))
        return (
            f"bars={self._health_piece(freshness.bar_age_seconds)} "
            f"quotes={self._health_piece(freshness.quote_age_seconds)} "
            f"trades={self._health_piece(freshness.trade_age_seconds)} "
            f"stream={stream_state}"
        )

    def _status_summary(self, status: dict[str, Any]) -> str:
        stream_state = "CONNECTED" if status.get("stream_connected") else "DISCONNECTED"
        if status.get("data_status") and status.get("data_status") not in {"LIVE", "REST"}:
            stream_state = str(status.get("data_status"))
        bar_count = status.get("stream_bar_count")
        bars = status.get("data_status") or "UNKNOWN"
        if bar_count is not None:
            bars = f"{bars} bars={bar_count}/{self.config.slow_sma_minutes}"
        return (
            f"bars={bars} ({self._age_label(status.get('bar_age_seconds'))}) "
            f"quotes={self._health_piece(status.get('quote_age_seconds'))} "
            f"trades={self._health_piece(status.get('trade_age_seconds'))} "
            f"stream={stream_state}"
        )

    def _health_piece(self, age: float | None) -> str:
        if age is None:
            return "WAITING"
        if age > MARKET_DATA_MAX_AGE_SECONDS:
            return f"STALE ({self._age_label(age)})"
        return f"LIVE ({self._age_label(age)})"

    def _age_label(self, value: Any) -> str:
        if value is None:
            return "--"
        seconds = float(value)
        if seconds < 1:
            return "<1s"
        return f"{round(seconds)}s"

    def _directional_mode_for_route(self, route: BotRoute) -> str:
        if route.active_bot in {MOMENTUM_BOT, INVERSE_BOT}:
            return self._effective_directional_mode_for_bot(route.active_bot)
        return "NA"

    def _effective_directional_mode_for_bot(self, bot_name: str) -> str:
        if (
            bot_name in {MOMENTUM_BOT, INVERSE_BOT}
            and self.config.directional_mode == DIRECTIONAL_MODE_ADAPTIVE
            and self._adaptive_posture is not None
        ):
            return self._adaptive_posture.selected_mode
        if self.config.directional_mode == DIRECTIONAL_MODE_ADAPTIVE:
            return DIRECTIONAL_MODE_BALANCED
        return self.config.directional_mode

    def _entry_decision_for_route(
        self,
        route: BotRoute,
        soxl_snapshot: SmaSnapshot,
    ) -> EntryDecision:
        if route.active_bot == MOMENTUM_BOT:
            snapshot = self._directional_entry_snapshot(SOXL, soxl_snapshot)
            return self._directional_entry_decision(
                bot_name=MOMENTUM_BOT,
                symbol=SOXL,
                snapshot=snapshot,
                source_strength=self._strength_for_gap(UPTREND, soxl_snapshot.gap_percent),
            )

        if route.active_bot == CHOP_BOT:
            if soxl_snapshot.slow_sma == 0:
                print(
                    "[ENTRY] ChopBot entry check: slow_sma=0.0000 "
                    "entry_signal=False"
                )
                return EntryDecision(False, "invalid_mean")
            discount_percent = (
                (soxl_snapshot.slow_sma - soxl_snapshot.price)
                / soxl_snapshot.slow_sma
                * Decimal("100")
            )
            entry_signal = soxl_snapshot.price <= soxl_snapshot.slow_sma * (
                Decimal("1")
                - (self.config.chop_entry_discount_percent / Decimal("100"))
            )
            if entry_signal:
                reason = "discount_confirmed"
            elif discount_percent <= 0:
                reason = "price_above_mean"
            else:
                reason = "discount_insufficient"
            print(
                f"[ENTRY] ChopBot entry check: price={soxl_snapshot.price:.4f} "
                f"slow_sma={soxl_snapshot.slow_sma:.4f} "
                f"discount={discount_percent:.2f}% "
                f"threshold={self.config.chop_entry_discount_percent}% "
                f"reason={reason}"
            )
            return EntryDecision(entry_signal, reason)

        if route.active_bot == INVERSE_BOT and route.routed_symbol:
            snapshot = self._directional_entry_snapshot(route.routed_symbol)
            if snapshot is None:
                return EntryDecision(False, "inverse_confirmation_missing")
            return self._directional_entry_decision(
                bot_name=INVERSE_BOT,
                symbol=route.routed_symbol,
                snapshot=snapshot,
                source_strength=self._strength_for_gap(
                    DOWNTREND,
                    soxl_snapshot.gap_percent,
                ),
            )

        return EntryDecision(False, "route_not_supported")

    def _directional_entry_decision(
        self,
        bot_name: str,
        symbol: str,
        snapshot: SmaSnapshot,
        source_strength: str,
    ) -> EntryDecision:
        cooldown_active, cooldown_remaining = self._directional_cooldown_status(
            bot_name,
            symbol,
        )
        directional_mode = self._effective_directional_mode_for_bot(bot_name)
        extension_percent = self._extension_above_fast_sma(snapshot)
        symbol_strength = self._strength_for_gap(UPTREND, snapshot.gap_percent)
        print(
            f"[ENTRY] {bot_name} entry check: symbol={symbol} "
            f"price={snapshot.price:.4f} fast_sma={snapshot.fast_sma:.4f} "
            f"slow_sma={snapshot.slow_sma:.4f} "
            f"source_strength={source_strength} symbol_strength={symbol_strength} "
            f"extension={extension_percent:.2f}% "
            f"max_extension={self.config.directional_max_extension_percent}% "
            f"chase_max={self.config.directional_strong_chase_max_extension_percent}% "
            f"min_strength={self.config.directional_min_strength} "
            f"mode={directional_mode} "
            f"crossed_above={snapshot.crossed_above}"
        )

        if cooldown_active:
            return EntryDecision(
                False,
                f"directional_cooldown_active_{cooldown_remaining}m",
            )
        if snapshot.crossed_above:
            return EntryDecision(True, "fresh_cross_confirmed")
        if directional_mode == DIRECTIONAL_MODE_CONSERVATIVE:
            return EntryDecision(False, "mode_requires_fresh_cross")
        if not self._strength_meets_minimum(source_strength):
            return EntryDecision(False, "directional_strength_below_minimum")
        if snapshot.fast_sma <= snapshot.slow_sma:
            return EntryDecision(False, self._directional_weak_reason(bot_name))
        if snapshot.price < snapshot.slow_sma:
            return EntryDecision(False, self._directional_weak_reason(bot_name))
        if extension_percent <= self.config.directional_max_extension_percent:
            return EntryDecision(True, "trend_continuation_allowed")
        if (
            directional_mode == DIRECTIONAL_MODE_AGGRESSIVE
            and source_strength == REGIME_STRENGTH_STRONG
            and extension_percent
            <= self.config.directional_strong_chase_max_extension_percent
        ):
            return EntryDecision(True, "strong_trend_chase_allowed")
        return EntryDecision(False, "already_extended_above_fast_sma")

    def _directional_weak_reason(self, bot_name: str) -> str:
        if bot_name == INVERSE_BOT:
            return "soxs_momentum_weak"
        return "trend_strength_weakening"

    def _directional_entry_snapshot(
        self,
        symbol: str,
        fallback: SmaSnapshot | None = None,
    ) -> SmaSnapshot | None:
        probe = TrailingStopBot(
            config_for_symbol(self.config, symbol),
            self.client,
            self.state_store,
            self.market_data,
            self.lifecycle_ledger,
        )
        snapshot = probe._sma_snapshot(symbol, require_cross_context=True)
        if snapshot is not None:
            return snapshot
        if fallback is not None:
            return fallback
        return probe._sma_snapshot(symbol, require_cross_context=False)

    def _extension_above_fast_sma(self, snapshot: SmaSnapshot) -> Decimal:
        if snapshot.fast_sma == 0:
            return Decimal("0")
        return (snapshot.price - snapshot.fast_sma) / snapshot.fast_sma * Decimal("100")

    def _directional_cooldown_status(self, bot_name: str, symbol: str) -> tuple[bool, int]:
        cooldown_minutes = self.config.directional_cooldown_minutes
        if cooldown_minutes <= 0:
            return False, 0

        last_entry_at = self.state_store.get_last_entry_at(bot_name, symbol)
        if last_entry_at is None:
            return False, 0

        elapsed_seconds = age_seconds(last_entry_at)
        if elapsed_seconds is None:
            return False, 0

        cooldown_seconds = cooldown_minutes * 60
        if elapsed_seconds >= cooldown_seconds:
            return False, 0

        remaining = int((cooldown_seconds - elapsed_seconds + 59) // 60)
        return True, max(remaining, 1)

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
                f"[RISK] {symbol}: regime={regime} owner={owner_text} "
                f"active_bot={active_bot} stale exposure, sell order already open; "
                "entry_signal=False action_taken=wait_for_stale_close"
            )
            return "wait_for_stale_close"

        qty = self._position_qty(position).quantize(
            FRACTIONAL_QTY_STEP,
            rounding=ROUND_DOWN,
        )
        if qty <= 0:
            print(f"[RISK] {symbol}: stale exposure not found; entry_signal=False action_taken=noop")
            return "noop"

        print(
            f"[RISK] {symbol}: stale exposure under regime={regime}; "
            f"owner={owner_text} active_bot={active_bot}; "
            f"selling qty={format_decimal(qty)}."
        )
        self._record_lifecycle(
            LIFECYCLE_INTENDED_EXIT,
            bot=owner_text,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason="stale_position_regime_mismatch",
            regime=regime,
            active_bot=active_bot,
            owner=owner_text,
        )
        try:
            order = self.client.submit_market_sell_qty(symbol, qty)
        except BotError as exc:
            self._record_lifecycle(
                LIFECYCLE_ORDER_REJECTED,
                bot=owner_text,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="stale_position_regime_mismatch",
                regime=regime,
                active_bot=active_bot,
                owner=owner_text,
                error=str(exc),
                broker_constraint=self._broker_rejection_payload(exc, "sell", symbol),
            )
            raise
        self._record_lifecycle(
            LIFECYCLE_ORDER_SUBMITTED,
            bot=owner_text,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason="stale_position_regime_mismatch",
            regime=regime,
            active_bot=active_bot,
            owner=owner_text,
            order=order,
        )
        self.order_tracker.track_submitted_order(
            order,
            owner_text,
            "stale_position_regime_mismatch",
        )
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
            f"[RISK] ChopBot exit check: price={soxl_snapshot.price:.4f} "
            f"slow_sma={soxl_snapshot.slow_sma:.4f} reclaim={reclaim}"
        )
        if not reclaim:
            return None

        if any(order.get("side") == "sell" for order in symbol_orders):
            print(
                f"[RISK] {symbol}: ChopBot slow SMA reclaim, sell order already open; "
                "entry_signal=False action_taken=wait_for_chop_exit_order"
            )
            return "wait_for_chop_exit_order"

        qty = self._position_qty(position).quantize(
            FRACTIONAL_QTY_STEP,
            rounding=ROUND_DOWN,
        )
        if qty <= 0:
            print(f"[RISK] {symbol}: ChopBot exit found no long position; action_taken=noop")
            return "noop"

        print(
            f"[TRADE] {symbol}: ChopBot slow SMA reclaim; "
            f"selling qty={format_decimal(qty)}."
        )
        self._record_lifecycle(
            LIFECYCLE_INTENDED_EXIT,
            bot=CHOP_BOT,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason="chop_reclaim_slow_sma",
            price=soxl_snapshot.price,
            slow_sma=soxl_snapshot.slow_sma,
        )
        try:
            order = self.client.submit_market_sell_qty(symbol, qty)
        except BotError as exc:
            self._record_lifecycle(
                LIFECYCLE_ORDER_REJECTED,
                bot=CHOP_BOT,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="chop_reclaim_slow_sma",
                error=str(exc),
                broker_constraint=self._broker_rejection_payload(exc, "sell", symbol),
            )
            raise
        self._record_lifecycle(
            LIFECYCLE_ORDER_SUBMITTED,
            bot=CHOP_BOT,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason="chop_reclaim_slow_sma",
            price=soxl_snapshot.price,
            slow_sma=soxl_snapshot.slow_sma,
            order=order,
        )
        self.order_tracker.track_submitted_order(
            order,
            CHOP_BOT,
            "chop_reclaim_slow_sma",
        )
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
                print(f"[RISK] {symbol}: closeout window active, sell order already open.")
                sell_pending = True
                continue

            qty = qty.quantize(FRACTIONAL_QTY_STEP, rounding=ROUND_DOWN)
            print(
                f"[TRADE] {symbol}: market closes in {minutes_text} minutes; "
                f"selling all shares qty={format_decimal(qty)}."
            )
            owner = self.state_store.get_position_owner(symbol) or "UNKNOWN"
            self._record_lifecycle(
                LIFECYCLE_INTENDED_EXIT,
                bot=owner,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="market_close_liquidation",
                seconds_to_close=seconds_to_close,
            )
            try:
                order = self.client.submit_market_sell_qty(symbol, qty)
            except BotError as exc:
                self._record_lifecycle(
                    LIFECYCLE_ORDER_REJECTED,
                    bot=owner,
                    symbol=symbol,
                    side="sell",
                    qty=qty,
                    reason="market_close_liquidation",
                    error=str(exc),
                    broker_constraint=self._broker_rejection_payload(exc, "sell", symbol),
                )
                raise
            self._record_lifecycle(
                LIFECYCLE_ORDER_SUBMITTED,
                bot=owner,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="market_close_liquidation",
                seconds_to_close=seconds_to_close,
                order=order,
            )
            self.order_tracker.track_submitted_order(
                order,
                owner,
                "market_close_liquidation",
            )
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
