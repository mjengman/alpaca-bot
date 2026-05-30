from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from bot import (
    AlpacaClient,
    BotError,
    BotConfig,
    BotStateStore,
    BROKER_CATEGORY_INSUFFICIENT_BUYING_POWER,
    BROKER_CATEGORY_MARKET_CLOSED,
    BROKER_CATEGORY_PARTIAL_FILL_CONFLICT,
    BROKER_STATE_BUYING_POWER_LIMITED,
    BROKER_STATE_EXIT_BLOCKED,
    BROKER_STATE_ORDER_PENDING,
    BROKER_STATE_RESTRICTED,
    EdgeWalkerBot,
    LIFECYCLE_INTENDED_ENTRY,
    LIFECYCLE_INTENDED_EXIT,
    LIFECYCLE_FULL_FILL,
    LIFECYCLE_ORDER_REJECTED,
    LIFECYCLE_ORDER_ACCEPTED,
    LIFECYCLE_ORDER_SUBMITTED,
    LIFECYCLE_PARTIAL_FILL,
    LIFECYCLE_POSITION_CLOSED,
    LIFECYCLE_POSITION_OPENED,
    LIFECYCLE_POSITION_MANAGED,
    LIFECYCLE_ADAPTIVE_POSTURE_SELECTED,
    POSITION_LIFECYCLE_CLOSED,
    POSITION_LIFECYCLE_OPEN,
    POSITION_LIFECYCLE_OPENING,
    LifecycleLedger,
    _last_completed_bar_end,
    bar_end_age_seconds,
    classify_broker_error,
    parse_market_timestamp,
)


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


def bars(
    *closes: str,
    latest_at: datetime | None = None,
) -> list[dict[str, Any]]:
    latest = latest_at or datetime.now(timezone.utc)
    start = latest - timedelta(minutes=max(len(closes) - 1, 0))
    return [
        {
            "c": close,
            "t": (start + timedelta(minutes=index))
            .isoformat()
            .replace("+00:00", "Z"),
        }
        for index, close in enumerate(closes)
    ]


class FakeClient:
    def __init__(
        self,
        bar_map: dict[str, list[dict[str, Any]]],
        positions: dict[str, dict[str, Any] | None] | None = None,
        latest_trades: dict[str, dict[str, Any] | None] | None = None,
        latest_quotes: dict[str, dict[str, Any] | None] | None = None,
        buy_error: BotError | None = None,
        sell_error: BotError | None = None,
        buy_order_response: dict[str, Any] | None = None,
        sell_order_response: dict[str, Any] | None = None,
        open_orders: list[dict[str, Any]] | None = None,
        order_lookup: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.bar_map = bar_map
        self.positions = positions or {}
        self.latest_trades = latest_trades or {}
        self.latest_quotes = latest_quotes or {}
        self.buy_error = buy_error
        self.sell_error = sell_error
        self.buy_order_response = buy_order_response
        self.sell_order_response = sell_order_response
        self.open_orders = open_orders or []
        self.order_lookup = order_lookup or {}
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

    def get_latest_trade(self, symbol: str) -> dict[str, Any] | None:
        return self.latest_trades.get(symbol)

    def get_latest_quote(self, symbol: str) -> dict[str, Any] | None:
        return self.latest_quotes.get(symbol)

    def list_open_orders(self) -> list[dict[str, Any]]:
        return list(self.open_orders)

    def get_position(self, symbol: str) -> dict[str, Any] | None:
        return self.positions.get(symbol)

    def get_asset(self, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol, "fractionable": True}

    def get_order(self, order_id: str) -> dict[str, Any]:
        if order_id not in self.order_lookup:
            raise BotError(f"order not found: {order_id}")
        return self.order_lookup[order_id]

    def submit_market_buy(self, symbol: str, notional: Decimal) -> dict[str, Any]:
        if self.buy_error:
            raise self.buy_error
        self.buys.append((symbol, notional))
        order = dict(self.buy_order_response or {})
        order.setdefault("id", f"buy-{len(self.buys)}")
        order.setdefault("symbol", symbol)
        order.setdefault("side", "buy")
        return order

    def submit_market_sell_qty(self, symbol: str, qty: Decimal) -> dict[str, Any]:
        if self.sell_error:
            raise self.sell_error
        self.sells.append((symbol, qty))
        order = dict(self.sell_order_response or {})
        order.setdefault("id", f"sell-{len(self.sells)}")
        order.setdefault("symbol", symbol)
        order.setdefault("side", "sell")
        return order


class FakeMarketData:
    source_name = "stream"

    def __init__(
        self,
        bar_map: dict[str, list[dict[str, Any]]],
        data_status: str = "LIVE",
        latest_trades: dict[str, dict[str, Any] | None] | None = None,
        latest_quotes: dict[str, dict[str, Any] | None] | None = None,
    ) -> None:
        self.bar_map = bar_map
        self.data_status = data_status
        self.latest_trades = latest_trades or {}
        self.latest_quotes = latest_quotes or {}

    def get_recent_bars(self, symbol: str, minutes: int) -> list[dict[str, Any]]:
        return self.bar_map[symbol][-minutes:]

    def get_latest_trade(self, symbol: str) -> dict[str, Any] | None:
        return self.latest_trades.get(symbol)

    def get_latest_quote(self, symbol: str) -> dict[str, Any] | None:
        return self.latest_quotes.get(symbol)

    def status(self, symbol: str, required_bars: int | None = None) -> dict[str, Any]:
        symbol_bars = self.bar_map.get(symbol, [])
        latest_bar_time = (
            parse_market_timestamp(symbol_bars[-1].get("t")) if symbol_bars else None
        )
        return {
            "data_source": "stream",
            "data_feed": "iex",
            "data_status": self.data_status,
            "stream_connected": self.data_status == "LIVE",
            "stream_authenticated": self.data_status == "LIVE",
            "stream_subscribed": self.data_status == "LIVE",
            "stream_error": None,
            "stream_bar_count": len(symbol_bars),
            "stream_last_message_at": None,
            "latest_bar_time": (
                latest_bar_time.isoformat().replace("+00:00", "Z")
                if latest_bar_time
                else None
            ),
            "bar_age_seconds": bar_end_age_seconds(latest_bar_time),
            "latest_trade_time": None,
            "trade_age_seconds": None,
            "latest_quote_time": None,
            "quote_age_seconds": None,
        }


class RepairingMarketData(FakeMarketData):
    def __init__(
        self,
        bar_map: dict[str, list[dict[str, Any]]],
        repaired_bar_map: dict[str, list[dict[str, Any]]],
    ) -> None:
        super().__init__(bar_map)
        self.repaired_bar_map = repaired_bar_map
        self.repair_calls: list[dict[str, Any]] = []

    def repair_stale_bars(
        self,
        client: FakeClient,
        symbols: tuple[str, ...],
        required_bars: int,
    ) -> dict[str, Any]:
        self.repair_calls.append(
            {"symbols": symbols, "required_bars": required_bars}
        )
        self.bar_map.update(self.repaired_bar_map)
        return {
            "attempted": True,
            "candidate_symbols": ["SOXL"],
            "repaired_symbols": ["SOXL"],
            "unchanged_symbols": [],
            "errors": [],
            "reasons": {"SOXL": "bars_stale"},
        }


class EdgeWalkerBotTest(unittest.TestCase):
    def run_bot(
        self,
        client: FakeClient,
        setup_state: Any | None = None,
        bot_config: BotConfig | None = None,
        market_data: FakeMarketData | None = None,
    ) -> tuple[str, Any]:
        output, status, _records = self.run_bot_with_lifecycle(
            client,
            setup_state,
            bot_config,
            market_data,
        )
        return output, status

    def run_bot_with_lifecycle(
        self,
        client: FakeClient,
        setup_state: Any | None = None,
        bot_config: BotConfig | None = None,
        market_data: FakeMarketData | None = None,
    ) -> tuple[str, Any, list[dict[str, Any]]]:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            lifecycle_ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            if setup_state:
                setup_state(state_store)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = EdgeWalkerBot(
                    bot_config or config(),
                    client,
                    state_store,
                    market_data,
                    lifecycle_ledger,
                ).run_once()
            return output.getvalue(), status, lifecycle_ledger.read_all()

    def test_warmup_blocks_regime_routing_until_slow_sma_history_exists(self) -> None:
        client = FakeClient({"SOXL": bars("100", "99")})

        output, status = self.run_bot(client)

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [])
        self.assertIn("regime=WARMUP active_bot=NONE routed_symbol=NONE", output)
        self.assertEqual(status.regime, "WARMUP")
        self.assertIsNone(status.active_bot)
        self.assertIsNone(status.routed_symbol)
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "collecting_data")

    def test_warmup_persists_regime_state_to_clear_old_hysteresis_memory(self) -> None:
        client = FakeClient({"SOXL": bars("100", "99")})

        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            lifecycle_ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            state_store.set_regime_state("UPTREND", Decimal("0.30"))

            with contextlib.redirect_stdout(io.StringIO()):
                EdgeWalkerBot(
                    config(),
                    client,
                    state_store,
                    None,
                    lifecycle_ledger,
                ).run_once()

            regime_state = state_store.get_regime_state()

        self.assertEqual(regime_state["regime"], "WARMUP")
        self.assertEqual(regime_state["gap_percent"], "0")

    def test_regime_state_tracks_regime_age_and_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")

            state_store.set_regime_state("UPTREND", Decimal("0.30"))
            first_state = state_store.get_regime_state()
            first_since = first_state["regime_since"]

            state_store.set_regime_state("UPTREND", Decimal("0.35"))
            same_state = state_store.get_regime_state()

            state_store.set_regime_state("SIDEWAYS", Decimal("0.05"))
            changed_state = state_store.get_regime_state()

        self.assertEqual(same_state["regime_since"], first_since)
        self.assertEqual(changed_state["transitions"][-1]["from"], "UPTREND")
        self.assertEqual(changed_state["transitions"][-1]["to"], "SIDEWAYS")

    def test_market_timestamp_accepts_alpaca_nanosecond_precision(self) -> None:
        parsed = parse_market_timestamp("2026-05-21T14:56:53.123456789Z")

        self.assertEqual(
            parsed,
            datetime(2026, 5, 21, 14, 56, 53, 123456, tzinfo=timezone.utc),
        )

    def test_exact_slow_sma_history_allows_chop_routing(self) -> None:
        client = FakeClient({"SOXL": bars("100", "101", "99")})

        output, status = self.run_bot(client)

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [("SOXL", Decimal("25"))])
        self.assertIn("regime=SIDEWAYS active_bot=ChopBot", output)
        self.assertIn("[TREND] TRUST", output)
        self.assertEqual(status.regime, "SIDEWAYS")
        self.assertIsNotNone(status.trend_trust)
        self.assertIn("score", status.trend_trust)
        self.assertEqual(status.active_bot, "ChopBot")
        self.assertEqual(status.routed_symbol, "SOXL")
        self.assertEqual(status.action_taken, "market_buy")

    def test_lifecycle_ledger_records_edgewalker_entry_order(self) -> None:
        client = FakeClient({"SOXL": bars("100", "101", "99")})

        _output, status, records = self.run_bot_with_lifecycle(client)

        self.assertEqual(status.action_taken, "market_buy")
        self.assertEqual(
            [record["event_type"] for record in records],
            [LIFECYCLE_INTENDED_ENTRY, LIFECYCLE_ORDER_SUBMITTED],
        )
        intended = records[0]
        submitted = records[1]
        self.assertEqual(intended["runtime"], "EdgeWalker")
        self.assertEqual(intended["bot"], "ChopBot")
        self.assertEqual(intended["symbol"], "SOXL")
        self.assertEqual(intended["side"], "buy")
        self.assertEqual(intended["notional"], "25")
        self.assertEqual(intended["reason"], "discount_confirmed")
        self.assertEqual(submitted["order"]["id"], "buy-1")

    def test_lifecycle_ledger_records_filled_entry_order(self) -> None:
        client = FakeClient(
            {"SOXL": bars("100", "101", "99")},
            buy_order_response={
                "id": "buy-1",
                "symbol": "SOXL",
                "side": "buy",
                "status": "filled",
                "filled_qty": "0.25",
                "filled_avg_price": "99.50",
            },
        )

        _output, status, records = self.run_bot_with_lifecycle(client)

        self.assertEqual(status.action_taken, "market_buy")
        self.assertEqual(
            [record["event_type"] for record in records],
            [
                LIFECYCLE_INTENDED_ENTRY,
                LIFECYCLE_ORDER_SUBMITTED,
                LIFECYCLE_ORDER_ACCEPTED,
                LIFECYCLE_FULL_FILL,
                LIFECYCLE_POSITION_OPENED,
            ],
        )
        self.assertEqual(records[2]["order_id"], "buy-1")
        self.assertEqual(records[3]["filled_qty"], "0.25")
        self.assertEqual(records[3]["filled_avg_price"], "99.5")
        self.assertEqual(
            records[3]["position_lifecycle_state"],
            POSITION_LIFECYCLE_OPEN,
        )
        self.assertEqual(records[4]["qty"], "0.25")
        self.assertEqual(records[4]["avg_entry_price"], "99.5")
        self.assertEqual(
            records[4]["position_lifecycle_state"],
            POSITION_LIFECYCLE_OPEN,
        )

    def test_lifecycle_ledger_reconciles_partial_fill_for_pending_order(self) -> None:
        def setup_state(state_store: BotStateStore) -> None:
            state_store.track_order(
                "buy-1",
                {
                    "bot": "ChopBot",
                    "reason": "discount_confirmed",
                    "symbol": "SOXL",
                    "side": "buy",
                    "last_status": "new",
                    "last_filled_qty": "0",
                    "accepted_recorded": True,
                },
            )

        client = FakeClient(
            {"SOXL": bars("100", "100", "100")},
            order_lookup={
                "buy-1": {
                    "id": "buy-1",
                    "symbol": "SOXL",
                    "side": "buy",
                    "status": "partially_filled",
                    "filled_qty": "0.10",
                    "filled_avg_price": "100",
                }
            },
        )

        _output, status, records = self.run_bot_with_lifecycle(client, setup_state)

        self.assertEqual(status.action_taken, "no_entry_signal")
        self.assertEqual(
            [record["event_type"] for record in records],
            [LIFECYCLE_PARTIAL_FILL, LIFECYCLE_POSITION_OPENED],
        )
        self.assertEqual(records[0]["order_id"], "buy-1")
        self.assertEqual(records[0]["fill_delta_qty"], "0.1")
        self.assertEqual(
            records[0]["position_lifecycle_state"],
            POSITION_LIFECYCLE_OPENING,
        )
        self.assertEqual(records[1]["qty"], "0.1")
        self.assertEqual(
            records[1]["position_lifecycle_state"],
            POSITION_LIFECYCLE_OPENING,
        )

    def test_lifecycle_ledger_reconciles_pending_sell_fill_as_position_closed(self) -> None:
        def setup_state(state_store: BotStateStore) -> None:
            state_store.track_order(
                "sell-1",
                {
                    "bot": "MomentumBot",
                    "reason": "trailing_stop_breached",
                    "symbol": "SOXL",
                    "side": "sell",
                    "last_status": "new",
                    "last_filled_qty": "0",
                    "accepted_recorded": True,
                },
            )

        client = FakeClient(
            {"SOXL": bars("100", "100", "100")},
            order_lookup={
                "sell-1": {
                    "id": "sell-1",
                    "symbol": "SOXL",
                    "side": "sell",
                    "status": "filled",
                    "filled_qty": "1",
                    "filled_avg_price": "98",
                }
            },
        )

        _output, status, records = self.run_bot_with_lifecycle(client, setup_state)

        self.assertEqual(status.action_taken, "no_entry_signal")
        self.assertEqual(
            [record["event_type"] for record in records],
            [LIFECYCLE_FULL_FILL, LIFECYCLE_POSITION_CLOSED],
        )
        self.assertEqual(records[0]["order_id"], "sell-1")
        self.assertEqual(records[0]["filled_qty"], "1")
        self.assertEqual(
            records[0]["position_lifecycle_state"],
            POSITION_LIFECYCLE_CLOSED,
        )
        self.assertEqual(records[1]["qty"], "1")
        self.assertEqual(records[1]["exit_price"], "98")
        self.assertEqual(
            records[1]["position_lifecycle_state"],
            POSITION_LIFECYCLE_CLOSED,
        )

    def test_stale_market_data_blocks_strategy_actions(self) -> None:
        stale_latest_at = datetime.now(timezone.utc) - timedelta(minutes=15)
        client = FakeClient({"SOXL": bars("100", "101", "99", latest_at=stale_latest_at)})

        output, status = self.run_bot(client)

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [])
        self.assertIn("market_data_freshness=", output)
        self.assertIn('"isStale": true', output)
        self.assertIn("action_taken=wait_stale_market_data", output)
        self.assertEqual(status.regime, "SIDEWAYS")
        self.assertEqual(status.active_bot, "ChopBot")
        self.assertEqual(status.routed_symbol, "SOXL")
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "wait_stale_market_data")

    def test_stale_market_data_still_persists_hysteresis_adjusted_regime(self) -> None:
        stale_latest_at = datetime.now(timezone.utc) - timedelta(minutes=15)
        client = FakeClient(
            {"SOXL": bars("100", "100", "101", latest_at=stale_latest_at)}
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            lifecycle_ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            state_store.set_regime_state("UPTREND", Decimal("0.30"))

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = EdgeWalkerBot(
                    config(),
                    client,
                    state_store,
                    None,
                    lifecycle_ledger,
                ).run_once()

            regime_state = state_store.get_regime_state()

        self.assertIn("hysteresis hold", output.getvalue())
        self.assertEqual(status.action_taken, "wait_stale_market_data")
        self.assertEqual(status.regime, "UPTREND")
        self.assertEqual(regime_state["regime"], "UPTREND")
        self.assertEqual(regime_state["gap_percent"], status.gap_percent)

    def test_stale_market_data_still_manages_open_position_with_live_marks(self) -> None:
        stale_latest_at = datetime.now(timezone.utc) - timedelta(minutes=15)
        now_text = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        client = FakeClient(
            {"SOXL": bars("100", "101", "99", latest_at=stale_latest_at)},
            {"SOXL": {"symbol": "SOXL", "qty": "1", "avg_entry_price": "100"}},
            latest_quotes={"SOXL": {"bp": "99", "ap": "99", "t": now_text}},
        )

        output, status = self.run_bot(client)

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [])
        self.assertIn("live risk management remains active", output)
        self.assertIn("[RISK] SOXL: trailing stop holding", output)
        self.assertNotIn("action_taken=wait_stale_market_data", output)
        self.assertEqual(status.action_taken, "manage_open_position_stale_bars")

    def test_lifecycle_ledger_records_live_risk_exit_during_stale_bars(self) -> None:
        stale_latest_at = datetime.now(timezone.utc) - timedelta(minutes=15)
        now_text = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        client = FakeClient(
            {"SOXL": bars("100", "101", "99", latest_at=stale_latest_at)},
            {"SOXL": {"symbol": "SOXL", "qty": "1", "avg_entry_price": "100"}},
            latest_quotes={"SOXL": {"bp": "98", "ap": "98", "t": now_text}},
        )

        output, status, records = self.run_bot_with_lifecycle(client)

        self.assertEqual(client.sells, [("SOXL", Decimal("1.000000000"))])
        self.assertIn("live risk management remains active", output)
        self.assertEqual(status.action_taken, "manage_open_position_stale_bars")
        self.assertEqual(
            [record["event_type"] for record in records],
            [
                LIFECYCLE_POSITION_MANAGED,
                LIFECYCLE_INTENDED_EXIT,
                LIFECYCLE_ORDER_SUBMITTED,
            ],
        )
        managed = records[0]
        submitted = records[2]
        self.assertEqual(managed["runtime"], "TrailingStopBot")
        self.assertEqual(managed["symbol"], "SOXL")
        self.assertEqual(managed["stop_breached"], True)
        self.assertEqual(managed["require_live_mark"], True)
        self.assertEqual(submitted["reason"], "trailing_stop_breached")
        self.assertEqual(submitted["order"]["id"], "sell-1")

    def test_lifecycle_ledger_records_broker_rejected_entry(self) -> None:
        client = FakeClient(
            {"SOXL": bars("100", "101", "99")},
            buy_error=BotError("broker rejected buy"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            lifecycle_ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            output = io.StringIO()
            with self.assertRaises(BotError):
                with contextlib.redirect_stdout(output):
                    EdgeWalkerBot(
                        config(),
                        client,
                        state_store,
                        lifecycle_ledger=lifecycle_ledger,
                    ).run_once()

            records = lifecycle_ledger.read_all()

        self.assertEqual(client.buys, [])
        self.assertEqual(
            [record["event_type"] for record in records],
            [LIFECYCLE_INTENDED_ENTRY, LIFECYCLE_ORDER_REJECTED],
        )
        self.assertEqual(records[1]["side"], "buy")
        self.assertEqual(records[1]["error"], "broker rejected buy")
        self.assertEqual(
            records[1]["broker_constraint"]["category"],
            "GENERIC_BROKER_REJECTION",
        )

    def test_broker_error_classifier_maps_buying_power_rejection(self) -> None:
        error = (
            'HTTP 403 from https://paper-api.alpaca.markets/v2/orders: '
            '{"buying_power":"99860.01","code":40310000,'
            '"cost_basis":"100000.18","message":"insufficient buying power"}'
        )

        constraint = classify_broker_error(error, side="buy", symbol="SOXL")

        self.assertEqual(constraint.state, BROKER_STATE_BUYING_POWER_LIMITED)
        self.assertEqual(
            constraint.category,
            BROKER_CATEGORY_INSUFFICIENT_BUYING_POWER,
        )
        self.assertEqual(constraint.code, "40310000")
        self.assertEqual(constraint.symbol, "SOXL")

    def test_broker_error_classifier_maps_wash_trade_to_partial_fill_conflict(self) -> None:
        error = (
            'HTTP 403 from https://paper-api.alpaca.markets/v2/orders: '
            '{"code":40310000,'
            '"existing_order_id":"813de39f-0e2c-45f6-84df-fcb64b88f3fc",'
            '"message":"potential wash trade detected. use complex orders",'
            '"reject_reason":"opposite side market/stop order exists"}'
        )

        constraint = classify_broker_error(error, side="sell", symbol="SOXL")

        self.assertEqual(constraint.state, BROKER_STATE_ORDER_PENDING)
        self.assertEqual(
            constraint.category,
            BROKER_CATEGORY_PARTIAL_FILL_CONFLICT,
        )
        self.assertEqual(constraint.code, "40310000")
        self.assertEqual(constraint.symbol, "SOXL")

    def test_broker_error_classifier_marks_failed_exit_as_exit_blocked(self) -> None:
        constraint = classify_broker_error(
            "HTTP 403: market is closed",
            side="sell",
            symbol="SOXL",
        )

        self.assertEqual(constraint.state, BROKER_STATE_EXIT_BLOCKED)
        self.assertEqual(constraint.category, BROKER_CATEGORY_MARKET_CLOSED)

    def test_broker_error_classifier_marks_market_closed_entry_restricted(self) -> None:
        constraint = classify_broker_error(
            "HTTP 403: market is closed",
            side="buy",
            symbol="SOXL",
        )

        self.assertEqual(constraint.state, BROKER_STATE_RESTRICTED)
        self.assertEqual(constraint.category, BROKER_CATEGORY_MARKET_CLOSED)

    def test_streaming_market_data_replaces_rest_bars_for_regime(self) -> None:
        stale_latest_at = datetime.now(timezone.utc) - timedelta(minutes=15)
        client = FakeClient({"SOXL": bars("100", "101", "99", latest_at=stale_latest_at)})
        stream = FakeMarketData({"SOXL": bars("100", "101", "99")})

        output, status = self.run_bot(client, market_data=stream)

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [("SOXL", Decimal("25"))])
        self.assertIn("regime=SIDEWAYS active_bot=ChopBot", output)
        self.assertEqual(status.data_source, "stream")
        self.assertEqual(status.data_status, "LIVE")
        self.assertEqual(status.action_taken, "market_buy")

    def test_streaming_market_data_repairs_stale_bars_before_regime_detection(self) -> None:
        stale_latest_at = datetime.now(timezone.utc) - timedelta(minutes=15)
        client = FakeClient({"SOXL": bars("100", "100", "100")})
        stream = RepairingMarketData(
            {"SOXL": bars("100", "101", latest_at=stale_latest_at)},
            {"SOXL": bars("100", "101", "99")},
        )

        output, status = self.run_bot(client, market_data=stream)

        self.assertEqual(
            stream.repair_calls,
            [{"symbols": ("SOXL", "SOXS"), "required_bars": 4}],
        )
        self.assertIn("[DATA] BAR BACKFILL repaired symbols=SOXL", output)
        self.assertEqual(status.action_taken, "market_buy")

    def test_stream_status_must_be_live_before_strategy_actions(self) -> None:
        client = FakeClient({"SOXL": bars("100", "101", "99")})
        stream = FakeMarketData(
            {"SOXL": bars("100", "101", "99")},
            data_status="CONNECTING",
        )

        output, status = self.run_bot(client, market_data=stream)

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [])
        self.assertIn("action_taken=wait_stream_market_data", output)
        self.assertEqual(status.data_source, "stream")
        self.assertEqual(status.data_status, "CONNECTING")
        self.assertEqual(status.action_taken, "wait_stream_market_data")

    def test_downtrend_closes_soxl_without_same_cycle_soxs_buy(self) -> None:
        client = FakeClient(
            {"SOXL": bars("100", "99", "98", "97")},
            {"SOXL": {"qty": "0.25", "avg_entry_price": "100"}},
        )

        output, status = self.run_bot(client)

        self.assertEqual(client.sells, [("SOXL", Decimal("0.250000000"))])
        self.assertEqual(client.buys, [])
        self.assertIn("regime=DOWNTREND active_bot=InverseBot", output)
        self.assertIn("close_route_invalidated_position_no_same_cycle_reversal", output)
        self.assertEqual(status.regime, "DOWNTREND")
        self.assertEqual(status.active_bot, "InverseBot")
        self.assertEqual(status.routed_symbol, "SOXS")
        self.assertEqual(status.action_taken, "close_route_invalidated_position_no_same_cycle_reversal")
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

    def test_balanced_inverse_buys_valid_soxs_continuation_without_fresh_cross(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("103", "102", "101"),
                "SOXS": bars("8.00", "8.10", "8.14"),
            }
        )

        output, status = self.run_bot(client)

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [("SOXS", Decimal("25"))])
        self.assertIn("regime=DOWNTREND active_bot=InverseBot", output)
        self.assertIn("source_strength=MODERATE", output)
        self.assertIn("reason=trend_continuation_allowed", output)
        self.assertEqual(status.regime, "DOWNTREND")
        self.assertEqual(status.active_bot, "InverseBot")
        self.assertEqual(status.routed_symbol, "SOXS")
        self.assertEqual(status.entry_signal, True)
        self.assertEqual(status.action_taken, "market_buy")

    def test_conservative_inverse_still_requires_fresh_cross(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("103", "102", "101"),
                "SOXS": bars("8.00", "8.10", "8.14"),
            }
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(config(), directional_mode="CONSERVATIVE"),
        )

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [])
        self.assertIn("regime=DOWNTREND active_bot=InverseBot", output)
        self.assertIn("mode=CONSERVATIVE", output)
        self.assertIn("reason=mode_requires_fresh_cross", output)
        self.assertEqual(status.regime, "DOWNTREND")
        self.assertEqual(status.active_bot, "InverseBot")
        self.assertEqual(status.routed_symbol, "SOXS")
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_directional_min_strength_blocks_weak_downtrend_even_when_aggressive(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "99.5", "99.2"),
                "SOXS": bars("8.00", "8.10", "8.14"),
            }
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(config(), directional_mode="AGGRESSIVE"),
        )

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [])
        self.assertIn("regime=DOWNTREND active_bot=InverseBot", output)
        self.assertIn("source_strength=WEAK", output)
        self.assertIn("reason=directional_strength_below_minimum", output)
        self.assertEqual(status.regime, "DOWNTREND")
        self.assertEqual(status.active_bot, "InverseBot")
        self.assertEqual(status.routed_symbol, "SOXS")
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")

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
        self.assertEqual(status.action_taken, "close_route_invalidated_position_no_same_cycle_reversal")

    def test_stale_position_waits_when_same_symbol_buy_order_is_open(self) -> None:
        client = FakeClient(
            {"SOXL": bars("100", "100", "101", "99")},
            {"SOXL": {"qty": "75", "avg_entry_price": "219.87"}},
            open_orders=[
                {
                    "id": "buy-open",
                    "symbol": "SOXL",
                    "side": "buy",
                    "status": "accepted",
                }
            ],
        )

        output, status = self.run_bot(
            client,
            lambda state: state.set_position_owner("SOXL", "MomentumBot"),
        )

        self.assertEqual(client.sells, [])
        self.assertIn("route invalidated, buy order still open", output)
        self.assertEqual(status.regime, "SIDEWAYS")
        self.assertEqual(status.active_bot, "ChopBot")
        self.assertEqual(status.action_taken, "wait_for_route_invalidated_close_order")

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
        self.assertEqual(status.action_taken, "close_route_invalidated_position_no_same_cycle_reversal")

    def test_regime_hysteresis_holds_prior_trend_above_exit_threshold(self) -> None:
        client = FakeClient({"SOXL": bars("100", "100", "100.7")})

        output, status = self.run_bot(
            client,
            lambda state: state.set_regime_state("UPTREND", Decimal("0.30")),
        )

        self.assertIn("hysteresis hold", output)
        self.assertEqual(status.regime, "UPTREND")
        self.assertEqual(status.active_bot, "MomentumBot")

    def test_balanced_directional_buys_valid_soxl_continuation_without_fresh_cross(self) -> None:
        client = FakeClient({"SOXL": bars("100", "101", "102")})

        output, status = self.run_bot(client)

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [("SOXL", Decimal("25"))])
        self.assertIn("regime=UPTREND active_bot=MomentumBot", output)
        self.assertIn("mode=BALANCED", output)
        self.assertIn("reason=trend_continuation_allowed", output)
        self.assertEqual(status.regime, "UPTREND")
        self.assertEqual(status.active_bot, "MomentumBot")
        self.assertEqual(status.entry_signal, True)
        self.assertEqual(status.action_taken, "market_buy")

    def test_conservative_directional_soxl_still_requires_fresh_cross(self) -> None:
        client = FakeClient({"SOXL": bars("100", "101", "102")})

        output, status = self.run_bot(
            client,
            bot_config=replace(config(), directional_mode="CONSERVATIVE"),
        )

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [])
        self.assertIn("mode=CONSERVATIVE", output)
        self.assertIn("reason=mode_requires_fresh_cross", output)
        self.assertEqual(status.regime, "UPTREND")
        self.assertEqual(status.active_bot, "MomentumBot")
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_balanced_directional_blocks_absurd_soxl_extension(self) -> None:
        client = FakeClient({"SOXL": bars("100", "102", "103.2")})

        output, status = self.run_bot(client)

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [])
        self.assertIn("reason=already_extended_above_fast_sma", output)
        self.assertEqual(status.regime, "UPTREND")
        self.assertEqual(status.active_bot, "MomentumBot")
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_aggressive_directional_allows_strong_soxl_trend_chase(self) -> None:
        client = FakeClient({"SOXL": bars("100", "102", "103.2")})

        output, status = self.run_bot(
            client,
            bot_config=replace(config(), directional_mode="AGGRESSIVE"),
        )

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [("SOXL", Decimal("25"))])
        self.assertIn("mode=AGGRESSIVE", output)
        self.assertIn("strength=STRONG", output)
        self.assertIn("reason=strong_trend_chase_allowed", output)
        self.assertEqual(status.regime, "UPTREND")
        self.assertEqual(status.active_bot, "MomentumBot")
        self.assertEqual(status.entry_signal, True)
        self.assertEqual(status.action_taken, "market_buy")

    def test_adaptive_directional_selects_aggressive_for_strong_clean_trend(self) -> None:
        client = FakeClient({"SOXL": bars("100", "102", "103.2")})

        output, status, records = self.run_bot_with_lifecycle(
            client,
            bot_config=replace(config(), directional_mode="ADAPTIVE"),
        )

        self.assertEqual(client.buys, [("SOXL", Decimal("25"))])
        self.assertIn("[ADAPTIVE] posture=AGGRESSIVE", output)
        self.assertIn("scope=ACTIVE", output)
        self.assertIn("mode=AGGRESSIVE", output)
        self.assertEqual(status.directional_mode, "ADAPTIVE")
        self.assertEqual(status.effective_directional_mode, "AGGRESSIVE")
        self.assertEqual(status.adaptive_posture, "AGGRESSIVE")
        self.assertEqual(status.adaptive_confidence, "HIGH")
        adaptive_events = [
            record
            for record in records
            if record["event_type"] == LIFECYCLE_ADAPTIVE_POSTURE_SELECTED
        ]
        self.assertEqual(len(adaptive_events), 1)
        self.assertEqual(adaptive_events[0]["selected_posture"], "AGGRESSIVE")
        self.assertEqual(adaptive_events[0]["active"], True)

    def test_adaptive_shadow_does_not_override_manual_directional_mode(self) -> None:
        client = FakeClient({"SOXL": bars("100", "101", "102")})

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                directional_mode="CONSERVATIVE",
                adaptive_shadow_enabled=True,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("[ADAPTIVE] posture=BALANCED", output)
        self.assertIn("scope=SHADOW", output)
        self.assertIn("mode=CONSERVATIVE", output)
        self.assertEqual(status.directional_mode, "CONSERVATIVE")
        self.assertEqual(status.effective_directional_mode, "CONSERVATIVE")
        self.assertEqual(status.adaptive_posture, "BALANCED")
        self.assertEqual(status.adaptive_shadow, True)

    def test_adaptive_posture_pauses_entry_choice_while_position_is_open(self) -> None:
        client = FakeClient(
            {"SOXL": bars("100", "101", "102")},
            {"SOXL": {"qty": "0.25", "avg_entry_price": "100"}},
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(config(), directional_mode="ADAPTIVE"),
        )

        self.assertIn("constraints=position_open", output)
        self.assertIn("reasons=adaptive_entry_posture_paused", output)
        self.assertEqual(status.adaptive_posture, "BALANCED")
        self.assertEqual(status.adaptive_confidence, "HIGH")
        self.assertIn("position_open", status.adaptive_constraints)
        self.assertIn("adaptive_entry_posture_paused", status.adaptive_reasons)

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

    def test_fixed_position_sizing_clamps_to_buying_power_buffer(self) -> None:
        client = FakeClient({"SOXL": bars("100", "101", "99")})

        output, status = self.run_bot(
            client,
            bot_config=replace(config(), position_notional=Decimal("100000")),
        )

        self.assertEqual(client.buys, [("SOXL", Decimal("950.00"))])
        self.assertIn("mode=FIXED", output)
        self.assertIn("effective=$950", output)
        self.assertEqual(status.effective_position_notional, "950")

    def test_dynamic_full_deployment_uses_allocation_percent(self) -> None:
        client = FakeClient({"SOXL": bars("100", "101", "99")})

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                position_sizing_mode="DYNAMIC",
                position_allocation_percent=Decimal("95"),
            ),
        )

        self.assertEqual(client.buys, [("SOXL", Decimal("950.00"))])
        self.assertIn("mode=DYNAMIC allocation=95%", output)
        self.assertIn("effective=$950", output)
        self.assertEqual(status.effective_position_notional, "950")

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
    def test_last_completed_bar_end_excludes_in_progress_minute(self) -> None:
        now = datetime(2026, 5, 21, 13, 50, 12, 345678, tzinfo=timezone.utc)

        self.assertEqual(
            _last_completed_bar_end(now),
            datetime(2026, 5, 21, 13, 49, 59, 999999, tzinfo=timezone.utc),
        )

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
