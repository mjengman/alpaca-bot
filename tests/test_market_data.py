from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
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


def market_timestamp(hour: int = 10, minute: int = 0) -> str:
    timestamp = datetime.now(NY_TZ).replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )
    return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


if __name__ == "__main__":
    unittest.main()
