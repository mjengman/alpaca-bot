from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from bot import BotConfig
from fill_parity_report import classify_slippage
from research import (
    RESEARCH_FILL_MODEL_LIVE_AUDIT,
    RESEARCH_FILL_MODEL_STRESSED,
    RESEARCH_FILL_MODELS,
    ResearchFillOverride,
    SimulatedBroker,
)


class FakeMarketData:
    def current_price(self, _symbol: str) -> Decimal:
        return Decimal("100")


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
        fast_sma_minutes=5,
        slow_sma_minutes=20,
        poll_seconds=60,
        close_liquidate_minutes=5,
        regime_gap_threshold=Decimal("0.20"),
        regime_exit_gap_threshold=Decimal("0.10"),
        chop_entry_discount_percent=Decimal("0.35"),
        directional_mode="BALANCED",
        directional_max_extension_percent=Decimal("0.40"),
        directional_strong_chase_max_extension_percent=Decimal("1.00"),
        directional_min_strength="MODERATE",
        directional_cooldown_minutes=4,
        adaptive_shadow_enabled=False,
        data_feed="iex",
        dry_run=True,
    )


class FillParityReportTest(unittest.TestCase):
    def test_classifies_slippage(self) -> None:
        self.assertEqual(classify_slippage(Decimal("-1")), "favorable")
        self.assertEqual(classify_slippage(Decimal("5")), "normal")
        self.assertEqual(classify_slippage(Decimal("25")), "adverse")
        self.assertEqual(classify_slippage(Decimal("75")), "catastrophic")

    def test_stressed_fill_model_is_supported(self) -> None:
        self.assertIn(RESEARCH_FILL_MODEL_STRESSED, RESEARCH_FILL_MODELS)

    def test_live_audit_fill_model_is_supported(self) -> None:
        self.assertIn(RESEARCH_FILL_MODEL_LIVE_AUDIT, RESEARCH_FILL_MODELS)

    def test_stressed_fill_offsets_are_adverse_by_side(self) -> None:
        broker = SimulatedBroker(
            config(),
            FakeMarketData(),  # type: ignore[arg-type]
            start=datetime(2026, 6, 1, 13, 30, tzinfo=timezone.utc),
            end=datetime(2026, 6, 1, 20, 0, tzinfo=timezone.utc),
            starting_account_value=Decimal("350"),
            fill_model=RESEARCH_FILL_MODEL_STRESSED,
            slippage_bps=Decimal("10"),
            slippage_cents=Decimal("5"),
        )

        self.assertEqual(broker._fill_price("SOXL", "buy"), Decimal("100.150"))
        self.assertEqual(broker._fill_price("SOXL", "sell"), Decimal("99.850"))

    def test_live_audit_fill_override_is_used_near_current_time(self) -> None:
        filled_at = datetime(2026, 6, 1, 13, 31, tzinfo=timezone.utc)
        broker = SimulatedBroker(
            config(),
            FakeMarketData(),  # type: ignore[arg-type]
            start=datetime(2026, 6, 1, 13, 30, tzinfo=timezone.utc),
            end=datetime(2026, 6, 1, 20, 0, tzinfo=timezone.utc),
            starting_account_value=Decimal("350"),
            fill_model=RESEARCH_FILL_MODEL_LIVE_AUDIT,
            slippage_bps=Decimal("0"),
            slippage_cents=Decimal("0"),
            fill_overrides=(
                ResearchFillOverride(
                    symbol="SOXL",
                    side="buy",
                    price=Decimal("99.25"),
                    filled_at=filled_at,
                ),
            ),
        )

        broker.set_time(datetime(2026, 6, 1, 13, 31, 30, tzinfo=timezone.utc))

        self.assertEqual(broker._fill_price("SOXL", "buy"), Decimal("99.25"))
        self.assertEqual(broker._fill_price("SOXL", "buy"), Decimal("100"))

    def test_live_audit_fill_override_ignores_stale_timestamp(self) -> None:
        broker = SimulatedBroker(
            config(),
            FakeMarketData(),  # type: ignore[arg-type]
            start=datetime(2026, 6, 1, 13, 30, tzinfo=timezone.utc),
            end=datetime(2026, 6, 1, 20, 0, tzinfo=timezone.utc),
            starting_account_value=Decimal("350"),
            fill_model=RESEARCH_FILL_MODEL_LIVE_AUDIT,
            slippage_bps=Decimal("0"),
            slippage_cents=Decimal("0"),
            fill_overrides=(
                ResearchFillOverride(
                    symbol="SOXL",
                    side="buy",
                    price=Decimal("99.25"),
                    filled_at=datetime(2026, 6, 1, 13, 31, tzinfo=timezone.utc),
                    max_time_delta_seconds=Decimal("10"),
                ),
            ),
        )

        broker.set_time(datetime(2026, 6, 1, 13, 32, tzinfo=timezone.utc))

        self.assertEqual(broker._fill_price("SOXL", "buy"), Decimal("100"))


if __name__ == "__main__":
    unittest.main()
