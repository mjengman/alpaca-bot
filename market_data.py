from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from bot import (
    MARKET_DATA_MAX_AGE_SECONDS,
    BotConfig,
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
        self._api_key_id = config.api_key_id
        self._api_secret_key = config.api_secret_key
        self._connected = False
        self._authenticated = False
        self._subscribed = False
        self._last_message_at: datetime | None = None
        self._last_error: str | None = None
        self._last_save_monotonic = 0.0
        self._load_state()

    @property
    def source_name(self) -> str:
        return "stream"

    def ensure_running(self, config: BotConfig) -> None:
        with self._lock:
            if self._needs_reconnect(config):
                self._stop_locked()
                self._feed = config.data_feed
                self._api_key_id = config.api_key_id
                self._api_secret_key = config.api_secret_key
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
            bars = self._bars.get(symbol.upper(), [])
            return [dict(bar) for bar in bars[-minutes:]]

    def get_latest_trade(self, symbol: str) -> dict[str, Any] | None:
        with self._lock:
            trade = self._latest_trades.get(symbol.upper())
            return dict(trade) if trade else None

    def get_latest_quote(self, symbol: str) -> dict[str, Any] | None:
        with self._lock:
            quote = self._latest_quotes.get(symbol.upper())
            return dict(quote) if quote else None

    def status(self, symbol: str, required_bars: int | None = None) -> dict[str, Any]:
        with self._lock:
            symbol = symbol.upper()
            bars = self._bars.get(symbol, [])
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
            status = self._status_text_locked(symbol, required_bars, bar_age)

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
                self._record_bar_locked(message)
            elif message_type == "t":
                symbol = str(message.get("S", "")).upper()
                if symbol in self.symbols:
                    self._latest_trades[symbol] = dict(message)
            elif message_type == "q":
                symbol = str(message.get("S", "")).upper()
                if symbol in self.symbols:
                    self._latest_quotes[symbol] = dict(message)

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

    def _record_bar_locked(self, message: dict[str, Any]) -> None:
        symbol = str(message.get("S", "")).upper()
        timestamp = message.get("t")
        if symbol not in self.symbols or not isinstance(timestamp, str):
            return

        bar = {
            key: message[key]
            for key in ("S", "o", "h", "l", "c", "v", "n", "vw", "t")
            if key in message
        }
        bar["source"] = self.source_name
        bars = [item for item in self._bars.setdefault(symbol, []) if item.get("t") != timestamp]
        bars.append(bar)
        bars.sort(key=lambda item: self._bar_sort_key(item))
        self._bars[symbol] = bars[-self.max_bars :]

    def _bar_sort_key(self, bar: dict[str, Any]) -> str:
        timestamp = parse_market_timestamp(bar.get("t"))
        if timestamp is None:
            return str(bar.get("t", ""))
        return timestamp.isoformat()

    def _status_text_locked(
        self,
        symbol: str,
        required_bars: int | None,
        bar_age: float | None,
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
        if required_bars is not None and len(self._bars.get(symbol, [])) < required_bars:
            return STREAM_STATUS_WARMING_UP
        return STREAM_STATUS_LIVE

    def _needs_reconnect(self, config: BotConfig) -> bool:
        return (
            self._feed != config.data_feed
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
                if self._bar_trading_date(bar) == today
            ][-self.max_bars :]

    def _bar_trading_date(self, bar: dict[str, Any]) -> Any:
        timestamp = parse_market_timestamp(bar.get("t"))
        if timestamp is None:
            return None
        return timestamp.astimezone(NY_TZ).date()

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
