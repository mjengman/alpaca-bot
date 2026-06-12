from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from bot import (
    MARKET_DATA_MAX_AGE_SECONDS,
    BotConfig,
    BotError,
    age_seconds,
    bar_end_age_seconds,
    parse_market_timestamp,
)

try:
    import websocket  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - exercised by integration environment.
    websocket = None


STREAM_STATE_PATH_DEFAULT = Path(__file__).resolve().with_name(
    ".market_data_state.json"
)
NY_TZ = ZoneInfo("America/New_York")
REGULAR_SESSION_START_SECONDS = 9 * 60 * 60 + 30 * 60
REGULAR_SESSION_END_SECONDS = 16 * 60 * 60
STREAM_STATUS_LIVE = "LIVE"
STREAM_STATUS_WARMING_UP = "WARMING_UP"
STREAM_STATUS_CONNECTING = "CONNECTING"
STREAM_STATUS_DISCONNECTED = "DISCONNECTED"
STREAM_STATUS_STALE = "STALE"
STREAM_STATUS_MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
STREAM_STATUS_ERROR = "ERROR"


class StreamingMarketDataService:
    def __init__(
        self,
        config: BotConfig,
        symbols: tuple[str, ...],
        state_path: Path = STREAM_STATE_PATH_DEFAULT,
        max_bars: int = 600,
    ) -> None:
        self.symbols = tuple(dict.fromkeys(symbol.upper() for symbol in symbols))
        self.state_path = state_path
        self.max_bars = max_bars
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._ws: Any | None = None
        self._bars: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in self.symbols}
        self._latest_trades: dict[str, dict[str, Any]] = {}
        self._latest_quotes: dict[str, dict[str, Any]] = {}
        self._feed = config.data_feed
        self._data_base_url = config.data_base_url
        self._api_key_id = config.api_key_id
        self._api_secret_key = config.api_secret_key
        self._previous_session_closes: dict[tuple[str, str, str], Decimal] = {}
        self._previous_session_close_failures: set[tuple[str, str, str]] = set()
        self._connected = False
        self._authenticated = False
        self._subscribed = False
        self._last_message_at: datetime | None = None
        self._last_error: str | None = None
        self._last_save_monotonic = 0.0
        self._last_repair_monotonic: dict[str, float] = {}
        self._load_state()

    @property
    def source_name(self) -> str:
        return "stream"

    def ensure_running(self, config: BotConfig) -> None:
        with self._lock:
            if self._needs_reconnect(config):
                self._stop_locked()
                self._feed = config.data_feed
                self._data_base_url = config.data_base_url
                self._api_key_id = config.api_key_id
                self._api_secret_key = config.api_secret_key
                self._previous_session_closes.clear()
                self._previous_session_close_failures.clear()
                self._connected = False
                self._authenticated = False
                self._subscribed = False
                self._last_error = None

            if self._thread and self._thread.is_alive():
                return

            if websocket is None:
                self._last_error = (
                    "websocket-client is not installed; run "
                    "python3 -m pip install -r requirements.txt"
                )
                return

            self._stop_event = threading.Event()
            self._thread = threading.Thread(
                target=self._run,
                args=(self._stop_event,),
                name="alpaca-market-data-stream",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()
            self._save_state_locked(force=True)

    def get_recent_bars(self, symbol: str, minutes: int) -> list[dict[str, Any]]:
        with self._lock:
            bars = self._regular_session_bars_locked(symbol.upper())
            return [dict(bar) for bar in bars[-minutes:]]

    def get_latest_trade(self, symbol: str) -> dict[str, Any] | None:
        with self._lock:
            trade = self._latest_trades.get(symbol.upper())
            return dict(trade) if trade else None

    def get_latest_quote(self, symbol: str) -> dict[str, Any] | None:
        with self._lock:
            quote = self._latest_quotes.get(symbol.upper())
            return dict(quote) if quote else None

    def get_previous_session_close(self, symbol: str) -> Decimal | None:
        symbol = symbol.upper()
        target_date = datetime.now(NY_TZ).date()
        cache_key = (symbol, self._feed, target_date.isoformat())
        with self._lock:
            cached = self._previous_session_closes.get(cache_key)
            if cached is not None:
                return cached
            data_base_url = self._data_base_url
            feed = self._feed
            api_key_id = self._api_key_id
            api_secret_key = self._api_secret_key

        close = self._fetch_previous_session_close(
            symbol,
            target_date,
            data_base_url,
            feed,
            api_key_id,
            api_secret_key,
        )
        if close is not None:
            with self._lock:
                self._previous_session_closes[cache_key] = close
                self._previous_session_close_failures.discard(cache_key)
        else:
            with self._lock:
                self._previous_session_close_failures.add(cache_key)
        return close

    def previous_session_close_status(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper()
        target_date = datetime.now(NY_TZ).date()
        cache_key = (symbol, self._feed, target_date.isoformat())
        with self._lock:
            cached = self._previous_session_closes.get(cache_key)
            if cached is not None:
                return {
                    "status": "Loaded",
                    "symbol": symbol,
                    "value": str(cached),
                    "feed": self._feed,
                }
            if cache_key in self._previous_session_close_failures:
                return {
                    "status": "Unavailable",
                    "symbol": symbol,
                    "value": None,
                    "feed": self._feed,
                }
            return {
                "status": "Pending",
                "symbol": symbol,
                "value": None,
                "feed": self._feed,
            }

    def status(self, symbol: str, required_bars: int | None = None) -> dict[str, Any]:
        with self._lock:
            symbol = symbol.upper()
            bars = self._regular_session_bars_locked(symbol)
            latest_bar = bars[-1] if bars else None
            latest_bar_time = (
                parse_market_timestamp(latest_bar.get("t")) if latest_bar else None
            )
            latest_trade = self._latest_trades.get(symbol)
            latest_quote = self._latest_quotes.get(symbol)
            latest_trade_time = (
                parse_market_timestamp(latest_trade.get("t")) if latest_trade else None
            )
            latest_quote_time = (
                parse_market_timestamp(latest_quote.get("t")) if latest_quote else None
            )
            bar_age = bar_end_age_seconds(latest_bar_time)
            status = self._status_text_locked(
                required_bars,
                bar_age,
                bar_count=len(bars),
            )

            return {
                "data_source": self.source_name,
                "data_feed": self._feed,
                "data_status": status,
                "stream_connected": self._connected,
                "stream_authenticated": self._authenticated,
                "stream_subscribed": self._subscribed,
                "stream_error": self._last_error,
                "stream_bar_count": len(bars),
                "stream_last_message_at": self._time_text(self._last_message_at),
                "latest_bar_time": self._time_text(latest_bar_time),
                "bar_age_seconds": self._rounded_seconds(bar_age),
                "latest_trade_time": self._time_text(latest_trade_time),
                "trade_age_seconds": self._rounded_seconds(age_seconds(latest_trade_time)),
                "latest_quote_time": self._time_text(latest_quote_time),
                "quote_age_seconds": self._rounded_seconds(age_seconds(latest_quote_time)),
            }

    def repair_stale_bars(
        self,
        client: Any,
        symbols: tuple[str, ...] | None = None,
        required_bars: int | None = None,
        max_age_seconds: int = MARKET_DATA_MAX_AGE_SECONDS,
        min_interval_seconds: int = 30,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        checked_at = now or datetime.now(timezone.utc)
        candidates: list[dict[str, Any]] = []
        current_monotonic = time.monotonic()
        target_symbols = tuple(dict.fromkeys((symbols or self.symbols)))

        with self._lock:
            for raw_symbol in target_symbols:
                symbol = raw_symbol.upper()
                if symbol not in self.symbols:
                    continue
                reason = self._bar_repair_reason_locked(
                    symbol,
                    required_bars,
                    max_age_seconds,
                    checked_at,
                )
                if reason is None:
                    continue
                last_repair = self._last_repair_monotonic.get(symbol, 0.0)
                if current_monotonic - last_repair < min_interval_seconds:
                    continue
                self._last_repair_monotonic[symbol] = current_monotonic
                candidates.append({"symbol": symbol, "reason": reason})

        result: dict[str, Any] = {
            "attempted": bool(candidates),
            "candidate_symbols": [candidate["symbol"] for candidate in candidates],
            "repaired_symbols": [],
            "unchanged_symbols": [],
            "errors": [],
            "reasons": {
                candidate["symbol"]: candidate["reason"] for candidate in candidates
            },
        }
        if not candidates:
            return result

        fetch_minutes = max(required_bars or 1, 1)
        changed_any = False
        for candidate in candidates:
            symbol = candidate["symbol"]
            try:
                fetched_bars = client.get_recent_bars(symbol, fetch_minutes)
            except BotError as exc:
                result["errors"].append({"symbol": symbol, "error": str(exc)})
                continue

            with self._lock:
                before = self._regular_session_bars_locked(symbol)
                before_latest = before[-1].get("t") if before else None
                changed = self._merge_backfill_bars_locked(symbol, fetched_bars)
                self._prune_current_trading_day_locked()
                after = self._regular_session_bars_locked(symbol)
                after_latest = after[-1].get("t") if after else None

            changed_any = changed_any or changed
            if changed and (len(after) != len(before) or after_latest != before_latest):
                result["repaired_symbols"].append(symbol)
            else:
                result["unchanged_symbols"].append(symbol)

        if changed_any:
            with self._lock:
                self._save_state_locked(force=True)

        return result

    def _run(self, stop_event: threading.Event) -> None:
        backoff_seconds = 1.0
        while not stop_event.is_set():
            url = f"wss://stream.data.alpaca.markets/v2/{self._feed}"
            try:
                app = websocket.WebSocketApp(
                    url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                with self._lock:
                    self._ws = app
                    self._connected = False
                    self._authenticated = False
                    self._subscribed = False
                app.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as exc:  # Keep reconnecting; surface the error in status.
                with self._lock:
                    self._last_error = f"{type(exc).__name__}: {exc}"
                    self._connected = False
                    self._authenticated = False
                    self._subscribed = False

            if stop_event.is_set():
                break

            stop_event.wait(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 30.0)

    def _on_open(self, ws: Any) -> None:
        with self._lock:
            self._connected = True
            self._authenticated = False
            self._subscribed = False
            self._last_error = None
        ws.send(
            json.dumps(
                {
                    "action": "auth",
                    "key": self._api_key_id,
                    "secret": self._api_secret_key,
                }
            )
        )

    def _on_message(self, ws: Any, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            with self._lock:
                self._last_error = f"Invalid stream JSON: {message[:250]}"
            return

        messages = payload if isinstance(payload, list) else [payload]
        with self._lock:
            self._handle_messages_locked(messages, ws)

    def _handle_messages_locked(self, messages: list[Any], ws: Any | None = None) -> None:
        self._last_message_at = datetime.now(timezone.utc)
        bars_changed = False
        for message in messages:
            if not isinstance(message, dict):
                continue

            message_type = message.get("T")
            if message_type == "success":
                self._handle_success_locked(message, ws)
            elif message_type == "subscription":
                self._subscribed = True
                self._last_error = None
            elif message_type == "error":
                self._last_error = self._stream_error_text(message)
            elif message_type in {"b", "u"}:
                bars_changed = self._record_bar_locked(message) or bars_changed
            elif message_type == "t":
                symbol = str(message.get("S", "")).upper()
                if symbol in self.symbols:
                    self._latest_trades[symbol] = dict(message)
            elif message_type == "q":
                symbol = str(message.get("S", "")).upper()
                if symbol in self.symbols:
                    self._latest_quotes[symbol] = dict(message)

        if bars_changed:
            self._prune_current_trading_day_locked()
            self._save_state_locked()

    def _handle_success_locked(self, message: dict[str, Any], ws: Any | None) -> None:
        msg = str(message.get("msg", "")).lower()
        if msg == "connected":
            self._connected = True
            return
        if msg == "authenticated":
            self._authenticated = True
            self._last_error = None
            if ws:
                ws.send(
                    json.dumps(
                        {
                            "action": "subscribe",
                            "trades": list(self.symbols),
                            "quotes": list(self.symbols),
                            "bars": list(self.symbols),
                            "updatedBars": list(self.symbols),
                        }
                    )
                )

    def _record_bar_locked(self, message: dict[str, Any]) -> bool:
        symbol = str(message.get("S", "")).upper()
        return self._upsert_bar_locked(symbol, message, self.source_name)

    def _merge_backfill_bars_locked(
        self,
        symbol: str,
        bars: list[dict[str, Any]],
    ) -> bool:
        changed = False
        for bar in bars:
            if not isinstance(bar, dict):
                continue
            changed = self._upsert_bar_locked(symbol, bar, "rest_backfill") or changed
        return changed

    def _upsert_bar_locked(
        self,
        symbol: str,
        message: dict[str, Any],
        source: str,
    ) -> bool:
        timestamp = message.get("t")
        if symbol not in self.symbols or not isinstance(timestamp, str):
            return False

        bar = {
            key: message[key]
            for key in ("S", "o", "h", "l", "c", "v", "n", "vw", "t")
            if key in message
        }
        bar["S"] = str(bar.get("S") or symbol).upper()
        bar["source"] = source
        existing_bars = self._bars.setdefault(symbol, [])
        existing = next(
            (item for item in existing_bars if item.get("t") == timestamp),
            None,
        )
        if existing == bar:
            return False

        bars = [item for item in existing_bars if item.get("t") != timestamp]
        bars.append(bar)
        bars.sort(key=lambda item: self._bar_sort_key(item))
        self._bars[symbol] = bars[-self.max_bars :]
        return True

    def _bar_sort_key(self, bar: dict[str, Any]) -> str:
        timestamp = parse_market_timestamp(bar.get("t"))
        if timestamp is None:
            return str(bar.get("t", ""))
        return timestamp.isoformat()

    def _status_text_locked(
        self,
        required_bars: int | None,
        bar_age: float | None,
        bar_count: int,
    ) -> str:
        if websocket is None:
            return STREAM_STATUS_MISSING_DEPENDENCY
        if self._last_error and not self._subscribed:
            return STREAM_STATUS_ERROR
        if not self._connected or not self._authenticated or not self._subscribed:
            return STREAM_STATUS_CONNECTING if self._thread else STREAM_STATUS_DISCONNECTED
        if bar_age is None:
            return STREAM_STATUS_WARMING_UP
        if bar_age > MARKET_DATA_MAX_AGE_SECONDS:
            return STREAM_STATUS_STALE
        if required_bars is not None and bar_count < required_bars:
            return STREAM_STATUS_WARMING_UP
        return STREAM_STATUS_LIVE

    def _needs_reconnect(self, config: BotConfig) -> bool:
        return (
            self._feed != config.data_feed
            or self._data_base_url != config.data_base_url
            or self._api_key_id != config.api_key_id
            or self._api_secret_key != config.api_secret_key
        )

    def _stop_locked(self) -> None:
        if self._stop_event:
            self._stop_event.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        self._ws = None
        self._thread = None
        self._stop_event = None
        self._connected = False
        self._authenticated = False
        self._subscribed = False

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        if payload.get("feed") != self._feed:
            return
        raw_bars = payload.get("bars")
        if not isinstance(raw_bars, dict):
            return

        with self._lock:
            for symbol in self.symbols:
                entries = raw_bars.get(symbol)
                if not isinstance(entries, list):
                    continue
                self._bars[symbol] = [
                    dict(entry)
                    for entry in entries
                    if isinstance(entry, dict) and "c" in entry and "t" in entry
                ][-self.max_bars :]
            self._prune_current_trading_day_locked()

    def _save_state_locked(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_save_monotonic < 5:
            return
        self._last_save_monotonic = now
        payload = {
            "feed": self._feed,
            "symbols": list(self.symbols),
            "saved_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "bars": self._bars,
        }
        try:
            self.state_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError as exc:
            self._last_error = f"Could not save stream state: {exc}"

    def _prune_current_trading_day_locked(self) -> None:
        today = datetime.now(NY_TZ).date()
        for symbol, bars in self._bars.items():
            self._bars[symbol] = [
                bar
                for bar in bars
                if self._bar_is_regular_session_on_date(bar, today)
            ][-self.max_bars :]

    def _regular_session_bars_locked(self, symbol: str) -> list[dict[str, Any]]:
        today = datetime.now(NY_TZ).date()
        return [
            bar
            for bar in self._bars.get(symbol, [])
            if self._bar_is_regular_session_on_date(bar, today)
        ]

    def _bar_repair_reason_locked(
        self,
        symbol: str,
        required_bars: int | None,
        max_age_seconds: int,
        now: datetime,
    ) -> str | None:
        bars = self._regular_session_bars_locked(symbol)
        latest_bar = bars[-1] if bars else None
        latest_bar_time = (
            parse_market_timestamp(latest_bar.get("t")) if latest_bar else None
        )

        if latest_bar_time is None:
            if self._regular_session_completed_minutes(now) > 0:
                return "missing_regular_session_bars"
            return None

        bar_age = bar_end_age_seconds(latest_bar_time, now)
        if bar_age is not None and bar_age > max_age_seconds:
            return "bars_stale"

        if (
            required_bars is not None
            and len(bars) < required_bars
            and self._regular_session_completed_minutes(now) >= required_bars
        ):
            return "insufficient_bars_after_warmup"

        return None

    def _fetch_previous_session_close(
        self,
        symbol: str,
        target_date: Any,
        data_base_url: str,
        feed: str,
        api_key_id: str,
        api_secret_key: str,
    ) -> Decimal | None:
        start = datetime.combine(target_date - timedelta(days=21), datetime.min.time(), NY_TZ)
        end = datetime.combine(target_date + timedelta(days=1), datetime.min.time(), NY_TZ)
        params = {
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": "1000",
            "adjustment": "raw",
            "feed": feed,
            "sort": "asc",
        }
        url = (
            f"{data_base_url}/stocks/{symbol}/bars?"
            f"{urllib.parse.urlencode(params)}"
        )
        request = urllib.request.Request(
            url,
            headers={
                "APCA-API-KEY-ID": api_key_id,
                "APCA-API-SECRET-KEY": api_secret_key,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (
            OSError,
            TimeoutError,
            urllib.error.HTTPError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            with self._lock:
                self._last_error = f"Could not fetch previous close for {symbol}: {exc}"
            return None

        bars = payload.get("bars") if isinstance(payload, dict) else None
        if isinstance(bars, dict):
            bars = bars.get(symbol) or []
        if not isinstance(bars, list):
            return None

        prior_bars: list[tuple[datetime, Decimal]] = []
        for bar in bars:
            if not isinstance(bar, dict):
                continue
            timestamp = parse_market_timestamp(bar.get("t"))
            if timestamp is None or timestamp.astimezone(NY_TZ).date() >= target_date:
                continue
            close = bar.get("c")
            if close is None:
                continue
            try:
                prior_bars.append((timestamp, Decimal(str(close))))
            except InvalidOperation:
                continue
        if not prior_bars:
            return None

        prior_bars.sort(key=lambda item: item[0])
        return prior_bars[-1][1]

    def _regular_session_completed_minutes(self, now: datetime) -> int:
        local_timestamp = now.astimezone(NY_TZ)
        seconds_since_midnight = (
            local_timestamp.hour * 60 * 60
            + local_timestamp.minute * 60
            + local_timestamp.second
        )
        if seconds_since_midnight < REGULAR_SESSION_START_SECONDS:
            return 0
        if seconds_since_midnight >= REGULAR_SESSION_END_SECONDS:
            return (
                REGULAR_SESSION_END_SECONDS - REGULAR_SESSION_START_SECONDS
            ) // 60
        return (seconds_since_midnight - REGULAR_SESSION_START_SECONDS) // 60

    def _bar_is_regular_session_on_date(self, bar: dict[str, Any], date: Any) -> bool:
        timestamp = parse_market_timestamp(bar.get("t"))
        if timestamp is None:
            return False
        local_timestamp = timestamp.astimezone(NY_TZ)
        seconds_since_midnight = (
            local_timestamp.hour * 60 * 60
            + local_timestamp.minute * 60
            + local_timestamp.second
        )
        return (
            local_timestamp.date() == date
            and REGULAR_SESSION_START_SECONDS
            <= seconds_since_midnight
            < REGULAR_SESSION_END_SECONDS
        )

    def _on_error(self, _ws: Any, error: Any) -> None:
        with self._lock:
            self._last_error = str(error)

    def _on_close(
        self,
        _ws: Any,
        _status_code: int | None,
        _message: str | None,
    ) -> None:
        with self._lock:
            self._connected = False
            self._authenticated = False
            self._subscribed = False

    def _stream_error_text(self, message: dict[str, Any]) -> str:
        code = message.get("code")
        msg = message.get("msg")
        if code is not None:
            return f"stream error {code}: {msg}"
        return f"stream error: {msg}"

    def _time_text(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00",
            "Z",
        )

    def _rounded_seconds(self, value: float | None) -> float | None:
        if value is None:
            return None
        return round(value, 3)
