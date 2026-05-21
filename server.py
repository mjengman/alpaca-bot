#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import mimetypes
import threading
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from bot import (
    AlpacaClient,
    BotConfig,
    BotError,
    EdgeWalkerBot,
    load_dotenv,
    parse_clock_time,
)


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_ROOT = PROJECT_ROOT / "web"
HOST = "127.0.0.1"
PORT = 8765
ACTIVITY_PATH = PROJECT_ROOT / ".bot_activity.json"
ACTIVITY_RETENTION = timedelta(days=1)


@dataclass
class RunnerSnapshot:
    running: bool
    symbol: str
    dry_run: bool
    poll_seconds: int
    close_liquidate_minutes: int
    regime_gap_threshold: str
    chop_entry_discount_percent: str
    position_notional: str
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
    last_error: str | None


class BotRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._config = BotConfig.from_env()
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
        self._last_error: str | None = None
        self._market_idle_logged_for: str | None = None

    def snapshot(self) -> RunnerSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def start(self, config: BotConfig) -> RunnerSnapshot:
        with self._lock:
            if self._running:
                return self._snapshot_locked()

            self._config = config
            self._running = True
            self._last_started_at = now_iso()
            self._last_stopped_at = None
            self._last_error = None
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

    def run_once(self, config: BotConfig) -> RunnerSnapshot:
        with self._lock:
            self._config = config
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

        now_utc = datetime.now(timezone.utc)
        next_open_text = None
        wait_seconds = config.poll_seconds
        reason = "poll"
        has_next_open = False
        if next_open and next_open > now_utc:
            next_open_text = next_open.isoformat(timespec="seconds")
            wait_seconds = max((next_open - now_utc).total_seconds(), 1)
            reason = "market_open"
            has_next_open = True

        if not next_open_text:
            next_run = datetime.now() + timedelta(seconds=config.poll_seconds)
            next_open_text = next_run.isoformat(timespec="seconds")

        with self._lock:
            if self._stop_event is stop_event and self._running:
                self._next_run_at = next_open_text
                self._next_run_reason = reason
                if self._market_idle_logged_for != next_open_text:
                    if has_next_open:
                        line = (
                            "Market closed. EdgeWalker armed; "
                            f"next market open at {next_open_text}."
                        )
                    else:
                        line = (
                            "Market closed. EdgeWalker armed; "
                            f"next clock check at {next_open_text}."
                        )
                    self._last_output = [line]
                    self._append_activity_locked(self._last_output)
                    self._market_idle_logged_for = next_open_text

        stop_event.wait(wait_seconds)
        return True

    def _record_scheduler_error(self, config: BotConfig, exc: BotError) -> None:
        next_run = datetime.now() + timedelta(seconds=config.poll_seconds)
        lines = [f"[error] Could not check market clock: {exc}"]
        with self._lock:
            self._last_error = str(exc)
            self._last_output = lines
            self._next_run_at = next_run.isoformat(timespec="seconds")
            self._next_run_reason = "poll"
            self._append_activity_locked(lines)

    def _run_cycle(self, config: BotConfig) -> None:
        output = io.StringIO()
        error: str | None = None
        edgewalker_status: dict[str, Any] | None = None
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                status = EdgeWalkerBot(config, AlpacaClient(config)).run_once()
                edgewalker_status = asdict(status)
        except BotError as exc:
            error = str(exc)
        except Exception as exc:  # Keep the local control server alive on surprises.
            error = f"{type(exc).__name__}: {exc}"

        lines = [line for line in output.getvalue().splitlines() if line.strip()]
        if error:
            lines.append(f"[error] {error}")

        with self._lock:
            self._config = config
            self._cycle_count += 1
            self._last_run_at = now_iso()
            self._last_error = error
            if edgewalker_status:
                self._edgewalker_status = edgewalker_status
            self._last_output = lines[-40:] if lines else ["Cycle complete."]
            self._append_activity_locked(self._last_output)

    def _append_activity_locked(self, lines: list[str]) -> None:
        now = datetime.now()
        cutoff = now - ACTIVITY_RETENTION
        for line in lines:
            self._activity_log.append((now, line))
        self._activity_log = [
            (created_at, line)
            for created_at, line in self._activity_log
            if created_at >= cutoff
        ]
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

        cutoff = datetime.now() - ACTIVITY_RETENTION
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
            if created_at >= cutoff:
                entries.append((created_at, line))
        return entries

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
        return RunnerSnapshot(
            running=self._running,
            symbol=self._config.symbol,
            dry_run=self._config.dry_run,
            poll_seconds=self._config.poll_seconds,
            close_liquidate_minutes=self._config.close_liquidate_minutes,
            regime_gap_threshold=str(self._config.regime_gap_threshold),
            chop_entry_discount_percent=str(self._config.chop_entry_discount_percent),
            position_notional=str(self._config.position_notional),
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
            last_error=self._last_error,
        )


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def decimal_from_payload(
    payload: dict[str, Any],
    key: str,
    fallback: Decimal,
    allow_zero: bool = False,
) -> Decimal:
    raw = payload.get(key, str(fallback))
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


def int_from_payload(payload: dict[str, Any], key: str, fallback: int, minimum: int) -> int:
    raw = payload.get(key, fallback)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise BotError(f"{key} must be an integer") from exc
    if value < minimum:
        raise BotError(f"{key} must be at least {minimum}")
    return value


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
    chop_entry_discount_percent = decimal_from_payload(
        payload,
        "chopEntryDiscountPercent",
        base.chop_entry_discount_percent,
        allow_zero=True,
    )
    dry_run = bool(payload.get("dryRun", base.dry_run))

    return replace(
        base,
        symbol=symbol,
        dry_run=dry_run,
        poll_seconds=poll_seconds,
        close_liquidate_minutes=close_liquidate_minutes,
        regime_gap_threshold=regime_gap_threshold,
        chop_entry_discount_percent=chop_entry_discount_percent,
        position_notional=decimal_from_payload(
            payload, "positionNotional", base.position_notional
        ),
        trail_percent=decimal_from_payload(payload, "trailPercent", base.trail_percent),
        fast_sma_minutes=fast_sma,
        slow_sma_minutes=slow_sma,
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
        self.send_header("Access-Control-Allow-Origin", "*")
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
        AppHandler.runner.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
