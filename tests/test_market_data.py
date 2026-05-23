from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from bot import BotConfig
from market_data import StreamingMarketDataService


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
        data_feed="iex",
        dry_run=True,
    )


class StreamingMarketDataServiceTest(unittest.TestCase):
    def test_stream_messages_cache_bars_trades_and_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StreamingMarketDataService(
                config(),
                symbols=("SOXL", "SOXS"),
                state_path=Path(tmpdir) / "stream-state.json",
            )
            timestamp = (
                datetime.now(timezone.utc)
                .replace(second=0, microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )

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
            timestamp = (
                datetime.now(timezone.utc)
                .replace(second=0, microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )

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


if __name__ == "__main__":
    unittest.main()
