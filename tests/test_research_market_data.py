from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from bot import SOXL, SOXS
from research import ReplayMarketData


class ReplayMarketDataTest(unittest.TestCase):
    def test_symbol_lookups_are_timestamp_aligned(self) -> None:
        market_data = ReplayMarketData(
            {
                SOXL: [
                    {"t": "2026-06-24T10:00:00Z", "o": "100", "c": "101"},
                    {"t": "2026-06-24T10:02:00Z", "o": "102", "c": "103"},
                ],
                SOXS: [
                    {"t": "2026-06-24T09:59:00Z", "o": "9.90", "c": "9.95"},
                    {"t": "2026-06-24T10:00:00Z", "o": "10.00", "c": "10.05"},
                    {"t": "2026-06-24T10:02:00Z", "o": "10.20", "c": "10.25"},
                ],
            },
            "iex",
        )

        market_data.set_time(datetime(2026, 6, 24, 10, 2, tzinfo=timezone.utc))

        self.assertEqual(market_data.current_bar(SOXL)["t"], "2026-06-24T10:02:00Z")
        self.assertEqual(market_data.current_bar(SOXS)["t"], "2026-06-24T10:02:00Z")
        self.assertEqual(market_data.current_price(SOXS), Decimal("10.20"))

    def test_set_index_uses_source_symbol_time(self) -> None:
        market_data = ReplayMarketData(
            {
                SOXL: [
                    {"t": "2026-06-24T10:00:00Z", "o": "100", "c": "101"},
                    {"t": "2026-06-24T10:02:00Z", "o": "102", "c": "103"},
                ],
                SOXS: [
                    {"t": "2026-06-24T09:59:00Z", "o": "9.90", "c": "9.95"},
                    {"t": "2026-06-24T10:00:00Z", "o": "10.00", "c": "10.05"},
                    {"t": "2026-06-24T10:02:00Z", "o": "10.20", "c": "10.25"},
                ],
            },
            "iex",
        )

        market_data.set_index(1)

        self.assertEqual(market_data.current_bar(SOXL)["t"], "2026-06-24T10:02:00Z")
        self.assertEqual(market_data.current_bar(SOXS)["t"], "2026-06-24T10:02:00Z")

    def test_missing_exact_bar_uses_latest_known_past_bar(self) -> None:
        market_data = ReplayMarketData(
            {
                SOXL: [{"t": "2026-06-24T10:01:00Z", "o": "101", "c": "102"}],
                SOXS: [{"t": "2026-06-24T10:00:00Z", "o": "10.00", "c": "10.05"}],
            },
            "iex",
        )

        market_data.set_time(datetime(2026, 6, 24, 10, 1, tzinfo=timezone.utc))

        self.assertEqual(market_data.current_bar(SOXS)["t"], "2026-06-24T10:00:00Z")
        self.assertEqual(market_data.current_price(SOXS), Decimal("10.00"))

    def test_proven_state_bars_include_current_bar_without_changing_signal_bars(self) -> None:
        market_data = ReplayMarketData(
            {
                SOXL: [
                    {"t": "2026-06-24T10:00:00Z", "o": "100", "h": "101", "c": "100.5"},
                    {"t": "2026-06-24T10:01:00Z", "o": "101", "h": "102", "c": "101.5"},
                ],
                SOXS: [
                    {"t": "2026-06-24T10:00:00Z", "o": "10.00", "h": "10.10", "c": "10.05"},
                    {"t": "2026-06-24T10:01:00Z", "o": "10.10", "h": "10.30", "c": "10.15"},
                ],
            },
            "iex",
        )

        market_data.set_time(datetime(2026, 6, 24, 10, 1, tzinfo=timezone.utc))

        signal_bars = market_data.get_recent_bars(SOXS, 10)
        proven_bars = market_data.get_recent_bars_for_proven_state(SOXS, 10)

        self.assertEqual([bar["t"] for bar in signal_bars], ["2026-06-24T10:00:00Z"])
        self.assertEqual(
            [bar["t"] for bar in proven_bars],
            ["2026-06-24T10:00:00Z", "2026-06-24T10:01:00Z"],
        )
        self.assertEqual(market_data.proven_state_source(), "replay_intrabar_high")


if __name__ == "__main__":
    unittest.main()
