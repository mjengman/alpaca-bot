from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from bot import AlpacaClient, BotConfig, BotStateStore, EdgeWalkerBot


def config() -> BotConfig:
    return BotConfig(
        trading_base_url="https://paper-api.alpaca.markets/v2",
        data_base_url="https://data.alpaca.markets/v2",
        api_key_id="key",
        api_secret_key="secret",
        symbol="SOXL",
        position_notional=Decimal("25"),
        trail_percent=Decimal("1.5"),
        fast_sma_minutes=2,
        slow_sma_minutes=3,
        poll_seconds=60,
        close_liquidate_minutes=5,
        regime_gap_threshold=Decimal("0.20"),
        chop_entry_discount_percent=Decimal("0.50"),
        data_feed="iex",
        dry_run=True,
    )


def bars(*closes: str) -> list[dict[str, Any]]:
    return [{"c": close} for close in closes]


class FakeClient:
    def __init__(
        self,
        bar_map: dict[str, list[dict[str, Any]]],
        positions: dict[str, dict[str, Any] | None] | None = None,
    ) -> None:
        self.bar_map = bar_map
        self.positions = positions or {}
        self.buys: list[tuple[str, Decimal]] = []
        self.sells: list[tuple[str, Decimal]] = []

    def get_clock(self) -> dict[str, Any]:
        return {
            "is_open": True,
            "next_close": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
        }

    def get_account(self) -> dict[str, Any]:
        return {"buying_power": "1000", "portfolio_value": "1000"}

    def get_recent_bars(self, symbol: str, minutes: int) -> list[dict[str, Any]]:
        return self.bar_map[symbol][-minutes:]

    def list_open_orders(self) -> list[dict[str, Any]]:
        return []

    def get_position(self, symbol: str) -> dict[str, Any] | None:
        return self.positions.get(symbol)

    def get_asset(self, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol, "fractionable": True}

    def submit_market_buy(self, symbol: str, notional: Decimal) -> None:
        self.buys.append((symbol, notional))

    def submit_market_sell_qty(self, symbol: str, qty: Decimal) -> None:
        self.sells.append((symbol, qty))


class EdgeWalkerBotTest(unittest.TestCase):
    def run_bot(
        self,
        client: FakeClient,
        setup_state: Any | None = None,
        bot_config: BotConfig | None = None,
    ) -> tuple[str, Any]:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            if setup_state:
                setup_state(state_store)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = EdgeWalkerBot(
                    bot_config or config(),
                    client,
                    state_store,
                ).run_once()
            return output.getvalue(), status

    def test_downtrend_closes_soxl_without_same_cycle_soxs_buy(self) -> None:
        client = FakeClient(
            {"SOXL": bars("100", "99", "98", "97")},
            {"SOXL": {"qty": "0.25", "avg_entry_price": "100"}},
        )

        output, status = self.run_bot(client)

        self.assertEqual(client.sells, [("SOXL", Decimal("0.250000000"))])
        self.assertEqual(client.buys, [])
        self.assertIn("regime=DOWNTREND active_bot=InverseBot", output)
        self.assertIn("close_stale_position_no_same_cycle_reversal", output)
        self.assertEqual(status.regime, "DOWNTREND")
        self.assertEqual(status.active_bot, "InverseBot")
        self.assertEqual(status.routed_symbol, "SOXS")
        self.assertEqual(status.action_taken, "close_stale_position_no_same_cycle_reversal")
        self.assertEqual(status.position_symbol, "SOXL")

    def test_confirmed_downtrend_routes_next_cycle_to_soxs(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "99", "98", "97"),
                "SOXS": bars("100", "99", "100", "102"),
            }
        )

        output, status = self.run_bot(client)

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [("SOXS", Decimal("25"))])
        self.assertIn("regime=DOWNTREND active_bot=InverseBot", output)
        self.assertIn("action_taken=market_buy", output)
        self.assertEqual(status.regime, "DOWNTREND")
        self.assertEqual(status.active_bot, "InverseBot")
        self.assertEqual(status.routed_symbol, "SOXS")
        self.assertEqual(status.entry_signal, True)
        self.assertEqual(status.action_taken, "market_buy")

    def test_sideways_closes_momentum_owned_soxl_before_chop_entry(self) -> None:
        client = FakeClient(
            {"SOXL": bars("100", "100", "101", "99")},
            {"SOXL": {"qty": "0.25", "avg_entry_price": "100"}},
        )

        output, status = self.run_bot(
            client,
            lambda state: state.set_position_owner("SOXL", "MomentumBot"),
        )

        self.assertEqual(client.sells, [("SOXL", Decimal("0.250000000"))])
        self.assertEqual(client.buys, [])
        self.assertIn("regime=SIDEWAYS active_bot=ChopBot", output)
        self.assertIn("owner=MomentumBot active_bot=ChopBot", output)
        self.assertEqual(status.regime, "SIDEWAYS")
        self.assertEqual(status.active_bot, "ChopBot")
        self.assertEqual(status.routed_symbol, "SOXL")
        self.assertEqual(status.action_taken, "close_stale_position_no_same_cycle_reversal")

    def test_uptrend_closes_chop_owned_soxl_before_momentum_entry(self) -> None:
        client = FakeClient(
            {"SOXL": bars("100", "101", "102", "103")},
            {"SOXL": {"qty": "0.25", "avg_entry_price": "100"}},
        )

        output, status = self.run_bot(
            client,
            lambda state: state.set_position_owner("SOXL", "ChopBot"),
        )

        self.assertEqual(client.sells, [("SOXL", Decimal("0.250000000"))])
        self.assertEqual(client.buys, [])
        self.assertIn("regime=UPTREND active_bot=MomentumBot", output)
        self.assertIn("owner=ChopBot active_bot=MomentumBot", output)
        self.assertEqual(status.regime, "UPTREND")
        self.assertEqual(status.active_bot, "MomentumBot")
        self.assertEqual(status.action_taken, "close_stale_position_no_same_cycle_reversal")

    def test_chop_entry_buys_soxl_when_discounted_below_slow_sma(self) -> None:
        client = FakeClient({"SOXL": bars("100", "100", "101", "99")})

        output, status = self.run_bot(client)

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [("SOXL", Decimal("25"))])
        self.assertIn("regime=SIDEWAYS active_bot=ChopBot", output)
        self.assertIn("ChopBot entry check:", output)
        self.assertIn("entry_signal=True", output)
        self.assertEqual(status.regime, "SIDEWAYS")
        self.assertEqual(status.active_bot, "ChopBot")
        self.assertEqual(status.routed_symbol, "SOXL")
        self.assertEqual(status.entry_signal, True)
        self.assertEqual(status.action_taken, "market_buy")

    def test_chop_exit_sells_when_price_reclaims_slow_sma(self) -> None:
        client = FakeClient(
            {"SOXL": bars("100", "100", "99", "101")},
            {"SOXL": {"qty": "0.25", "avg_entry_price": "100"}},
        )

        output, status = self.run_bot(
            client,
            lambda state: state.set_position_owner("SOXL", "ChopBot"),
        )

        self.assertEqual(client.sells, [("SOXL", Decimal("0.250000000"))])
        self.assertEqual(client.buys, [])
        self.assertIn("ChopBot exit check:", output)
        self.assertIn("reclaim=True", output)
        self.assertEqual(status.regime, "SIDEWAYS")
        self.assertEqual(status.active_bot, "ChopBot")
        self.assertEqual(status.routed_symbol, "SOXL")
        self.assertEqual(status.action_taken, "chop_exit_reclaim_slow_sma")


class AlpacaClientTest(unittest.TestCase):
    def test_recent_bars_handles_null_after_hours_response(self) -> None:
        client = AlpacaClient(config())
        client._data_request = lambda *_args, **_kwargs: {
            "bars": None,
            "next_page_token": None,
            "symbol": "SOXL",
        }

        self.assertEqual(client.get_recent_bars("SOXL", 3), [])


if __name__ == "__main__":
    unittest.main()
