from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from bot import BotConfig
from market_data import StreamingMarketDataService

NY_TZ = ZoneInfo("America/New_York")


def config() -> BotConfig:
    return BotConfig(
        trading_base_url="https://paper-api.alpaca.markets/v2",
        data_base_url="https://data.alpaca.markets/v2",
        api_key_id="key",
        api_secret_key="secret",
        symbol="SOXL",
        position_notional=Decimal("25"),
        position_sizing_mode="FIXED",
        position_allocation_percent=Decimal("25"),
        trail_percent=Decimal("1.5"),
        fast_sma_minutes=2,
        slow_sma_minutes=3,
        poll_seconds=60,
        close_liquidate_minutes=5,
        regime_gap_threshold=Decimal("0.20"),
        regime_exit_gap_threshold=Decimal("0.10"),
        chop_entry_discount_percent=Decimal("0.50"),
        directional_mode="BALANCED",
        directional_max_extension_percent=Decimal("0.50"),
        directional_strong_chase_max_extension_percent=Decimal("1.00"),
        directional_min_strength="MODERATE",
        directional_cooldown_minutes=5,
        adaptive_shadow_enabled=False,
        data_feed="iex",
        dry_run=True,
    )


def market_datetime(hour: int = 10, minute: int = 0) -> datetime:
    return datetime.now(NY_TZ).replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    ).astimezone(timezone.utc)


def market_timestamp(hour: int = 10, minute: int = 0) -> str:
    return market_datetime(hour, minute).isoformat().replace("+00:00", "Z")


class FakeBarsClient:
    def __init__(self, bars_by_symbol: dict[str, list[dict[str, object]]]) -> None:
        self.bars_by_symbol = bars_by_symbol
        self.calls: list[tuple[str, int]] = []

    def get_recent_bars(self, symbol: str, minutes: int) -> list[dict[str, object]]:
        self.calls.append((symbol, minutes))
        return self.bars_by_symbol.get(symbol, [])[-minutes:]


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class StreamingMarketDataServiceTest(unittest.TestCase):
    def test_stream_messages_cache_bars_trades_and_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StreamingMarketDataService(
                config(),
                symbols=("SOXL", "SOXS"),
                state_path=Path(tmpdir) / "stream-state.json",
            )
            timestamp = market_timestamp()

            with service._lock:
                service._handle_messages_locked(
                    [
                        {
                            "T": "b",
                            "S": "SOXL",
                            "o": 100,
                            "h": 101,
                            "l": 99,
                            "c": 100.5,
                            "v": 1000,
                            "t": timestamp,
                        },
                        {
                            "T": "t",
                            "S": "SOXL",
                            "p": 100.75,
                            "t": timestamp,
                        },
                        {
                            "T": "q",
                            "S": "SOXL",
                            "bp": 100.7,
                            "ap": 100.8,
                            "t": timestamp,
                        },
                    ]
                )

            self.assertEqual(service.get_recent_bars("SOXL", 1)[0]["c"], 100.5)
            self.assertEqual(service.get_latest_trade("SOXL")["p"], 100.75)
            self.assertEqual(service.get_latest_quote("SOXL")["bp"], 100.7)

    def test_updated_bar_replaces_existing_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StreamingMarketDataService(
                config(),
                symbols=("SOXL",),
                state_path=Path(tmpdir) / "stream-state.json",
            )
            timestamp = market_timestamp()

            with service._lock:
                service._handle_messages_locked(
                    [
                        {"T": "b", "S": "SOXL", "c": 100, "t": timestamp},
                        {"T": "u", "S": "SOXL", "c": 101, "t": timestamp},
                    ]
                )

            bars = service.get_recent_bars("SOXL", 5)
            self.assertEqual(len(bars), 1)
            self.assertEqual(bars[0]["c"], 101)

    def test_trade_quote_messages_do_not_persist_bar_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StreamingMarketDataService(
                config(),
                symbols=("SOXL",),
                state_path=Path(tmpdir) / "stream-state.json",
            )
            timestamp = market_timestamp()
            prune_calls: list[bool] = []
            save_calls: list[bool] = []
            service._prune_current_trading_day_locked = lambda: prune_calls.append(True)
            service._save_state_locked = lambda force=False: save_calls.append(force)

            with service._lock:
                service._handle_messages_locked(
                    [
                        {"T": "t", "S": "SOXL", "p": 100.75, "t": timestamp},
                        {"T": "q", "S": "SOXL", "bp": 100.7, "ap": 100.8, "t": timestamp},
                    ]
                )

            self.assertEqual(prune_calls, [])
            self.assertEqual(save_calls, [])
            self.assertEqual(service.get_latest_trade("SOXL")["p"], 100.75)
            self.assertEqual(service.get_latest_quote("SOXL")["bp"], 100.7)

    def test_premarket_bars_do_not_satisfy_regular_session_warmup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StreamingMarketDataService(
                config(),
                symbols=("SOXL",),
                state_path=Path(tmpdir) / "stream-state.json",
            )
            premarket_timestamp = market_timestamp(9, 24)
            regular_timestamp = market_timestamp(9, 30)

            with service._lock:
                service._handle_messages_locked(
                    [
                        {"T": "b", "S": "SOXL", "c": 99, "t": premarket_timestamp},
                        {"T": "b", "S": "SOXL", "c": 100, "t": regular_timestamp},
                    ]
                )

            bars = service.get_recent_bars("SOXL", 20)
            self.assertEqual(len(bars), 1)
            self.assertEqual(bars[0]["t"], regular_timestamp)
            self.assertEqual(bars[0]["c"], 100)
            self.assertEqual(
                service.status("SOXL", required_bars=2)["stream_bar_count"],
                1,
            )

    def test_cached_premarket_bars_are_pruned_on_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "stream-state.json"
            premarket_timestamp = market_timestamp(9, 24)
            regular_timestamp = market_timestamp(9, 30)
            state_path.write_text(
                json.dumps(
                    {
                        "feed": "iex",
                        "symbols": ["SOXL"],
                        "bars": {
                            "SOXL": [
                                {"S": "SOXL", "c": 99, "t": premarket_timestamp},
                                {"S": "SOXL", "c": 100, "t": regular_timestamp},
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            service = StreamingMarketDataService(
                config(),
                symbols=("SOXL",),
                state_path=state_path,
            )

            bars = service.get_recent_bars("SOXL", 20)
            self.assertEqual(len(bars), 1)
            self.assertEqual(bars[0]["t"], regular_timestamp)

    def test_repair_stale_bars_backfills_regular_session_bars(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StreamingMarketDataService(
                config(),
                symbols=("SOXL",),
                state_path=Path(tmpdir) / "stream-state.json",
            )
            stale_timestamp = market_timestamp(9, 30)
            repaired_timestamp = market_timestamp(10, 5)
            client = FakeBarsClient(
                {
                    "SOXL": [
                        {"S": "SOXL", "c": 99, "t": stale_timestamp},
                        {"S": "SOXL", "c": 101, "t": repaired_timestamp},
                    ]
                }
            )

            with service._lock:
                service._handle_messages_locked(
                    [{"T": "b", "S": "SOXL", "c": 99, "t": stale_timestamp}]
                )

            result = service.repair_stale_bars(
                client,
                symbols=("SOXL",),
                required_bars=1,
                now=market_datetime(10, 7),
                min_interval_seconds=0,
            )

            bars = service.get_recent_bars("SOXL", 5)
            self.assertEqual(client.calls, [("SOXL", 1)])
            self.assertEqual(result["repaired_symbols"], ["SOXL"])
            self.assertEqual(bars[-1]["t"], repaired_timestamp)
            self.assertEqual(bars[-1]["source"], "rest_backfill")

    def test_repair_stale_bars_ignores_normal_opening_warmup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StreamingMarketDataService(
                config(),
                symbols=("SOXL",),
                state_path=Path(tmpdir) / "stream-state.json",
            )
            regular_timestamp = market_timestamp(9, 30)
            client = FakeBarsClient(
                {"SOXL": [{"S": "SOXL", "c": 100, "t": regular_timestamp}]}
            )

            with service._lock:
                service._handle_messages_locked(
                    [{"T": "b", "S": "SOXL", "c": 100, "t": regular_timestamp}]
                )

            result = service.repair_stale_bars(
                client,
                symbols=("SOXL",),
                required_bars=20,
                now=market_datetime(9, 31),
                min_interval_seconds=0,
            )

            self.assertEqual(client.calls, [])
            self.assertFalse(result["attempted"])

    def test_previous_session_close_fetches_and_caches_daily_bar(self) -> None:
        today = datetime.now(NY_TZ).date()
        prior_day = today - timedelta(days=1)
        current_day = today
        prior_timestamp = datetime.combine(
            prior_day,
            datetime.min.time(),
            NY_TZ,
        ).astimezone(timezone.utc)
        current_timestamp = datetime.combine(
            current_day,
            datetime.min.time(),
            NY_TZ,
        ).astimezone(timezone.utc)
        calls: list[str] = []

        def fake_urlopen(request: object, timeout: int) -> FakeHTTPResponse:
            calls.append(getattr(request, "full_url"))
            self.assertEqual(timeout, 20)
            return FakeHTTPResponse(
                {
                    "bars": [
                        {
                            "t": prior_timestamp.isoformat().replace("+00:00", "Z"),
                            "c": "101.25",
                        },
                        {
                            "t": current_timestamp.isoformat().replace("+00:00", "Z"),
                            "c": "102.75",
                        },
                    ],
                    "symbol": "SOXL",
                }
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            service = StreamingMarketDataService(
                config(),
                symbols=("SOXL",),
                state_path=Path(tmpdir) / "stream-state.json",
            )

            with patch("market_data.urllib.request.urlopen", fake_urlopen):
                self.assertEqual(
                    service.get_previous_session_close("SOXL"),
                    Decimal("101.25"),
                )
                self.assertEqual(
                    service.get_previous_session_close("SOXL"),
                    Decimal("101.25"),
                )

        self.assertEqual(len(calls), 1)
        self.assertIn("timeframe=1Day", calls[0])
        self.assertIn("feed=iex", calls[0])

    def test_previous_session_close_status_reports_cache_state(self) -> None:
        today = datetime.now(NY_TZ).date()
        prior_day = today - timedelta(days=1)
        prior_timestamp = datetime.combine(
            prior_day,
            datetime.min.time(),
            NY_TZ,
        ).astimezone(timezone.utc)

        def fake_urlopen(request: object, timeout: int) -> FakeHTTPResponse:
            del request, timeout
            return FakeHTTPResponse(
                {
                    "bars": [
                        {
                            "t": prior_timestamp.isoformat().replace("+00:00", "Z"),
                            "c": "101.25",
                        }
                    ],
                    "symbol": "SOXL",
                }
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            service = StreamingMarketDataService(
                config(),
                symbols=("SOXL",),
                state_path=Path(tmpdir) / "stream-state.json",
            )

            self.assertEqual(
                service.previous_session_close_status("SOXL")["status"],
                "Pending",
            )
            with patch("market_data.urllib.request.urlopen", fake_urlopen):
                self.assertEqual(
                    service.get_previous_session_close("SOXL"),
                    Decimal("101.25"),
                )
            self.assertEqual(
                service.previous_session_close_status("SOXL"),
                {
                    "status": "Loaded",
                    "symbol": "SOXL",
                    "value": "101.25",
                    "feed": "iex",
                },
            )

    def test_previous_session_close_status_reports_unavailable_after_failed_fetch(
        self,
    ) -> None:
        def fake_urlopen(request: object, timeout: int) -> FakeHTTPResponse:
            del request, timeout
            return FakeHTTPResponse({"bars": [], "symbol": "SOXL"})

        with tempfile.TemporaryDirectory() as tmpdir:
            service = StreamingMarketDataService(
                config(),
                symbols=("SOXL",),
                state_path=Path(tmpdir) / "stream-state.json",
            )

            with patch("market_data.urllib.request.urlopen", fake_urlopen):
                self.assertIsNone(service.get_previous_session_close("SOXL"))

            self.assertEqual(
                service.previous_session_close_status("SOXL")["status"],
                "Unavailable",
            )


if __name__ == "__main__":
    unittest.main()
