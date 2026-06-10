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

import bot as bot_module
from bot import (
    AlpacaClient,
    BotError,
    BotConfig,
    BotRoute,
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
    LIFECYCLE_SHADOW_ENTRY_SUPPRESSED,
    CHOP_BOT,
    INVERSE_CASCADE_MODE_LOOSE,
    INVERSE_CASCADE_MODE_STRICT,
    INVERSE_CASCADE_MODE_SUSTAINED,
    INVERSE_CASCADE_MODE_VELOCITY,
    INVERSE_BOT,
    MOMENTUM_AUTHORITY_REVOKED_EXIT_REASON,
    MOMENTUM_BOT,
    POSITION_LIFECYCLE_CLOSED,
    POSITION_LIFECYCLE_OPEN,
    POSITION_LIFECYCLE_OPENING,
    SOXL,
    SOXS,
    V10_AUTHORITY_STATE_MOMENTUM,
    V10_AUTHORITY_STATE_NONE,
    V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON,
    LifecycleLedger,
    NY_TZ,
    _last_completed_bar_end,
    bar_end_age_seconds,
    classify_broker_error,
    parse_market_timestamp,
)


class FrozenDateTime(datetime):
    current: datetime = datetime.now(timezone.utc)

    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        value = cls.current
        if tz is not None:
            value = value.astimezone(tz)
        else:
            value = value.replace(tzinfo=None)
        return cls(
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
            tzinfo=value.tzinfo,
            fold=getattr(value, "fold", 0),
        )


@contextlib.contextmanager
def patched_bot_time(current: datetime):
    previous = bot_module.datetime
    FrozenDateTime.current = current.astimezone(timezone.utc)
    bot_module.datetime = FrozenDateTime
    try:
        yield
    finally:
        bot_module.datetime = previous


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


def ohlc_bars(
    *rows: tuple[str, str, str, str],
    latest_at: datetime | None = None,
) -> list[dict[str, Any]]:
    latest = latest_at or datetime.now(timezone.utc)
    start = latest - timedelta(minutes=max(len(rows) - 1, 0))
    return [
        {
            "o": open_price,
            "h": high_price,
            "l": low_price,
            "c": close_price,
            "t": (start + timedelta(minutes=index))
            .isoformat()
            .replace("+00:00", "Z"),
        }
        for index, (open_price, high_price, low_price, close_price) in enumerate(rows)
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
        previous_session_closes: dict[str, Decimal] | None = None,
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
        self.previous_session_closes = previous_session_closes or {}
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

    def get_previous_session_close(self, symbol: str) -> Decimal | None:
        return self.previous_session_closes.get(symbol)

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
        setup_lifecycle: Any | None = None,
    ) -> tuple[str, Any]:
        output, status, _records = self.run_bot_with_lifecycle(
            client,
            setup_state,
            bot_config,
            market_data,
            setup_lifecycle,
        )
        return output, status

    def run_bot_with_lifecycle(
        self,
        client: FakeClient,
        setup_state: Any | None = None,
        bot_config: BotConfig | None = None,
        market_data: FakeMarketData | None = None,
        setup_lifecycle: Any | None = None,
    ) -> tuple[str, Any, list[dict[str, Any]]]:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            lifecycle_ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            if setup_state:
                setup_state(state_store)
            if setup_lifecycle:
                setup_lifecycle(lifecycle_ledger)
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

    def survived_regime(
        self,
        regime: str,
        *,
        gap_percent: str = "0.30",
        minutes: int = 12,
        recent_flips: int = 0,
    ) -> Any:
        def setup_state(state_store: BotStateStore) -> None:
            state_store.set_regime_state(regime, Decimal(gap_percent))
            data = state_store._read()
            regime_state = data["regime"]
            now = datetime.now(timezone.utc)
            regime_state["regime_since"] = (
                now - timedelta(minutes=minutes)
            ).isoformat()
            regime_state["transitions"] = [
                {
                    "from": "SIDEWAYS",
                    "to": regime,
                    "at": (now - timedelta(minutes=index + 1)).isoformat(),
                }
                for index in range(recent_flips)
            ]
            state_store._write(data)

        return setup_state

    def test_warmup_blocks_regime_routing_until_slow_sma_history_exists(self) -> None:
        client = FakeClient({"SOXL": bars("100", "99")})

        output, status = self.run_bot(
            client,
            setup_state=self.survived_regime("DOWNTREND"),
            bot_config=replace(
                config(),
                inverse_cascade_mode=bot_module.INVERSE_CASCADE_MODE_OFF,
            ),
        )

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

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=bot_module.INVERSE_CASCADE_MODE_OFF,
            ),
        )

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

    def test_enabled_bot_mask_blocks_non_target_route_entries(self) -> None:
        client = FakeClient({"SOXL": bars("100", "101", "99")})

        output, status = self.run_bot(
            client,
            bot_config=replace(config(), enabled_bots=(MOMENTUM_BOT,)),
        )

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [])
        self.assertIn("regime=SIDEWAYS active_bot=ChopBot", output)
        self.assertIn(
            "entries disabled for routed bot: bot=ChopBot enabled_bots=MomentumBot",
            output,
        )
        self.assertIn("reason=route_disallows_entry", output)
        self.assertEqual(status.regime, "SIDEWAYS")
        self.assertEqual(status.active_bot, CHOP_BOT)
        self.assertEqual(status.routed_symbol, SOXL)
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "chop_no_trade_placeholder")

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

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=bot_module.INVERSE_CASCADE_MODE_OFF,
            ),
        )

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

        output, status = self.run_bot(
            client,
            setup_state=self.survived_regime("DOWNTREND"),
            bot_config=replace(
                config(),
                inverse_cascade_mode=bot_module.INVERSE_CASCADE_MODE_OFF,
            ),
        )

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

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=bot_module.INVERSE_CASCADE_MODE_OFF,
            ),
        )

        self.assertEqual(client.sells, [("SOXL", Decimal("0.250000000"))])
        self.assertEqual(client.buys, [])
        self.assertIn("regime=DOWNTREND active_bot=InverseBot", output)
        self.assertIn("close_route_invalidated_position_no_same_cycle_reversal", output)
        self.assertEqual(status.regime, "DOWNTREND")
        self.assertEqual(status.active_bot, "InverseBot")
        self.assertEqual(status.routed_symbol, "SOXS")
        self.assertEqual(status.action_taken, "close_route_invalidated_position_no_same_cycle_reversal")
        self.assertEqual(status.position_symbol, "SOXL")

    def test_route_invalidation_exit_records_outcome_scaffold(self) -> None:
        client = FakeClient(
            {"SOXL": bars("100", "99", "98", "97")},
            {
                "SOXL": {
                    "qty": "0.25",
                    "avg_entry_price": "100",
                    "current_price": "98.75",
                    "market_value": "24.69",
                    "unrealized_pl": "-0.31",
                    "unrealized_plpc": "-0.0124",
                }
            },
            sell_order_response={
                "id": "sell-route",
                "status": "filled",
                "filled_qty": "0.25",
                "filled_avg_price": "98.75",
            },
        )

        def setup_state(state: BotStateStore) -> None:
            state.set_position_owner("SOXL", "MomentumBot")
            state.set_high_water_mark("SOXL", Decimal("101"))

        _output, _status, records = self.run_bot_with_lifecycle(
            client,
            setup_state,
        )

        exit_records = [
            record
            for record in records
            if record.get("reason") == "route_invalidated_exit"
        ]
        self.assertTrue(exit_records)
        for record in exit_records:
            context = record.get("lifecycle_context")
            self.assertIsInstance(context, dict)
            self.assertEqual(context["kind"], "route_invalidation_exit")
            self.assertEqual(context["outcome_status"], "PENDING_FOLLOW_THROUGH")
            self.assertIsNone(context["outcome_classification"])
            self.assertEqual(context["owner_bot"], "MomentumBot")
            self.assertEqual(context["active_bot"], "InverseBot")
            self.assertEqual(context["regime_at_invalidation"], "DOWNTREND")
            self.assertEqual(context["avg_entry_price"], "100")
            self.assertEqual(context["current_price"], "98.75")
            self.assertEqual(context["high_water_mark"], "101")
        self.assertIn(
            LIFECYCLE_POSITION_CLOSED,
            [record["event_type"] for record in exit_records],
        )

    def test_confirmed_downtrend_routes_next_cycle_to_soxs(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "99", "98", "97"),
                "SOXS": bars("100", "99", "100", "102"),
            }
        )

        output, status = self.run_bot(
            client,
            setup_state=self.survived_regime("DOWNTREND"),
            bot_config=replace(
                config(),
                inverse_cascade_mode=bot_module.INVERSE_CASCADE_MODE_OFF,
            ),
        )

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

        output, status = self.run_bot(
            client,
            setup_state=self.survived_regime("DOWNTREND"),
            bot_config=replace(
                config(),
                inverse_cascade_mode=bot_module.INVERSE_CASCADE_MODE_OFF,
            ),
        )

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

    def test_v7_bull_day_bias_blocks_fresh_inverse_entry(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "106", "105", "104"),
                "SOXS": bars("8.00", "8.05", "8.10", "8.13"),
            }
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=bot_module.INVERSE_CASCADE_MODE_OFF,
            ),
        )

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [])
        self.assertIn("[V7] Day path: bias=BULL_BIAS", output)
        self.assertIn("reason=v7_bull_bias_blocks_inverse", output)
        self.assertEqual(status.regime, "DOWNTREND")
        self.assertEqual(status.active_bot, "InverseBot")
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_inverse_cascade_off_preserves_sideways_chop_route(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "98", "97.4", "97.6", "97.5"),
                "SOXS": bars("10.00", "10.15", "10.25", "10.30", "10.35"),
            }
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=bot_module.INVERSE_CASCADE_MODE_OFF,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertNotIn("Cascade candidate", output)
        self.assertEqual(status.regime, "SIDEWAYS")
        self.assertEqual(status.active_bot, CHOP_BOT)
        self.assertEqual(status.routed_symbol, SOXL)

    def test_inverse_cascade_loose_routes_sideways_cascade_to_soxs(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "98", "97.4", "97.6", "97.5"),
                "SOXS": bars("10.00", "10.15", "10.25", "10.30", "10.35"),
            }
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_LOOSE,
            ),
        )

        self.assertEqual(client.buys, [(SOXS, Decimal("25"))])
        self.assertIn("[INVERSE] Cascade candidate qualified: mode=LOOSE", output)
        self.assertIn("[ROUTER] inverse cascade override", output)
        self.assertIn("reason=inverse_cascade_loose_confirmed", output)
        self.assertIn("[V8] Inverse cascade bypasses regime survivability", output)
        self.assertEqual(status.regime, "SIDEWAYS")
        self.assertEqual(status.active_bot, INVERSE_BOT)
        self.assertEqual(status.routed_symbol, SOXS)
        self.assertEqual(status.entry_signal, True)

    def test_inverse_cascade_strict_rejects_recovered_drop(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "94", "96.8", "97.1", "97.0"),
                "SOXS": bars("10.00", "10.15", "10.25", "10.30", "10.35"),
            }
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_STRICT,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("[INVERSE] Cascade candidate blocked: mode=STRICT", output)
        self.assertIn("source_recovery_above_cascade_max", output)
        self.assertEqual(status.regime, "SIDEWAYS")
        self.assertEqual(status.active_bot, CHOP_BOT)

    def test_inverse_cascade_velocity_requires_recent_source_drop(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "96", "97.2", "97.4", "97.5"),
                "SOXS": bars("10.00", "10.15", "10.20", "10.25", "10.30"),
            }
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_VELOCITY,
                inverse_cascade_velocity_window_minutes=2,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("[INVERSE] Cascade candidate blocked: mode=VELOCITY", output)
        self.assertIn("source_velocity_above_cascade_max", output)
        self.assertEqual(status.regime, "SIDEWAYS")
        self.assertEqual(status.active_bot, CHOP_BOT)

    def test_inverse_cascade_sustained_requires_held_source_drop(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "96", "95.8", "98.0", "95.6"),
                "SOXS": bars("10.00", "10.20", "10.30", "10.35", "10.40"),
            }
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                inverse_cascade_sustain_minutes=3,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("[INVERSE] Cascade candidate blocked: mode=SUSTAINED", output)
        self.assertIn("source_not_sustained_below_cascade_max", output)

    def test_inverse_cascade_sustained_routes_after_held_confirmation(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "96.5", "96.0", "95.7", "95.4"),
                "SOXS": bars("10.00", "10.20", "10.30", "10.35", "10.40"),
            },
            previous_session_closes={SOXL: Decimal("100")},
        )

        output, status, records = self.run_bot_with_lifecycle(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                inverse_cascade_sustain_minutes=3,
            ),
        )

        self.assertEqual(client.buys, [(SOXS, Decimal("25"))])
        self.assertIn("[INVERSE] Cascade candidate qualified: mode=SUSTAINED", output)
        self.assertIn("reason=inverse_cascade_sustained_confirmed", output)
        self.assertEqual(status.active_bot, INVERSE_BOT)
        self.assertEqual(status.routed_symbol, SOXS)
        submitted = next(
            record
            for record in records
            if record["event_type"] == LIFECYCLE_ORDER_SUBMITTED
            and record["side"] == "buy"
        )
        context = submitted["lifecycle_context"]
        self.assertEqual(context["entry_family"], "inverse_cascade")
        self.assertEqual(context["inverse_entry_family"], "cascade")
        self.assertEqual(context["inverse_cascade_mode"], INVERSE_CASCADE_MODE_SUSTAINED)
        self.assertEqual(context["base_route_bot"], CHOP_BOT)
        self.assertEqual(context["base_route_symbol"], SOXL)
        self.assertEqual(context["soxl_pct_from_open_at_cascade_window_start"], "-4")
        self.assertEqual(
            Decimal(context["soxl_pct_vs_prior_close_at_cascade_window_start"]),
            Decimal("-4"),
        )
        self.assertEqual(context["sustain_source_direction_changes"], 0)
        self.assertEqual(context["sustain_source_down_path_ratio"], "1")
        self.assertEqual(context["sustain_source_path_length_percent"], "0.6")
        self.assertEqual(context["sustain_source_down_distance_percent"], "0.6")
        self.assertLess(Decimal(context["entry_bar_soxl_pct"]), Decimal("0"))
        self.assertEqual(context["entry_bar_soxl_direction"], "DOWN")
        self.assertGreater(
            Decimal(context["entry_bar_soxl_prior_avg_abs_pct"]),
            Decimal("0"),
        )
        self.assertGreater(
            Decimal(context["entry_bar_soxl_velocity_ratio"]),
            Decimal("0"),
        )
        self.assertGreater(Decimal(context["entry_bar_soxs_pct"]), Decimal("0"))
        self.assertEqual(context["entry_bar_soxs_direction"], "UP")
        self.assertGreater(
            Decimal(context["entry_bar_soxs_prior_avg_abs_pct"]),
            Decimal("0"),
        )
        self.assertGreater(
            Decimal(context["entry_bar_soxs_velocity_ratio"]),
            Decimal("0"),
        )

    def test_inverse_cascade_sustained_blocks_prior_close_support_floor(
        self,
    ) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "96.5", "96.0", "95.7", "95.4"),
                "SOXS": bars("10.00", "10.20", "10.30", "10.35", "10.40"),
            },
            previous_session_closes={SOXL: Decimal("98")},
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                inverse_cascade_sustain_minutes=3,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("source_prior_close_above_cascade_max", output)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_inverse_cascade_sustained_blocks_missing_prior_close(
        self,
    ) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "96.5", "96.0", "95.7", "95.4"),
                "SOXS": bars("10.00", "10.20", "10.30", "10.35", "10.40"),
            }
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                inverse_cascade_sustain_minutes=3,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("source_prior_close_unavailable", output)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_inverse_cascade_sustained_blocks_extreme_window_extension(
        self,
    ) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "90.5", "90.0", "89.7", "89.4"),
                "SOXS": bars("10.00", "10.80", "10.90", "11.00", "11.10"),
            },
            previous_session_closes={SOXL: Decimal("100")},
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                inverse_cascade_sustain_minutes=3,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("source_window_start_below_cascade_min", output)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_inverse_cascade_sustained_blocks_soxs_down_entry_bar(
        self,
    ) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "96.5", "96.0", "95.7", "95.4"),
                "SOXS": bars("10.00", "10.60", "10.50", "10.40", "10.30"),
            },
            previous_session_closes={SOXL: Decimal("100")},
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                inverse_cascade_sustain_minutes=3,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("inverse_entry_bar_down", output)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_inverse_cascade_sustained_blocks_uptrend_base_route(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "96.5", "96.0", "95.7", "95.4"),
                "SOXS": bars("10.00", "10.20", "10.30", "10.35", "10.40"),
            },
            previous_session_closes={SOXL: Decimal("100")},
        )

        original = bot_module.INVERSE_CASCADE_DEFAULTS[
            INVERSE_CASCADE_MODE_SUSTAINED
        ]["block_source_uptrend"]
        bot_module.INVERSE_CASCADE_DEFAULTS[INVERSE_CASCADE_MODE_SUSTAINED][
            "block_source_uptrend"
        ] = True
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                edgewalker = EdgeWalkerBot(
                    replace(
                        config(),
                        inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                        inverse_cascade_sustain_minutes=3,
                    ),
                    client,
                    BotStateStore(Path(tmpdir) / "state.json"),
                    None,
                    LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl"),
                )
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    route = edgewalker._inverse_cascade_route_override(
                        BotRoute(MOMENTUM_BOT, SOXL, True)
                    )
        finally:
            bot_module.INVERSE_CASCADE_DEFAULTS[INVERSE_CASCADE_MODE_SUSTAINED][
                "block_source_uptrend"
            ] = original

        self.assertEqual(route.active_bot, MOMENTUM_BOT)
        self.assertEqual(route.routed_symbol, SOXL)
        self.assertIn("source_uptrend_route_blocks_sustained_cascade", output.getvalue())
        self.assertIn("base=MomentumBot/SOXL", output.getvalue())

    def test_inverse_cascade_sustained_allows_sideways_base_route(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "96.5", "96.0", "95.7", "95.4"),
                "SOXS": bars("10.00", "10.20", "10.30", "10.35", "10.40"),
            },
            previous_session_closes={SOXL: Decimal("100")},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            edgewalker = EdgeWalkerBot(
                replace(
                    config(),
                    inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                    inverse_cascade_sustain_minutes=3,
                ),
                client,
                BotStateStore(Path(tmpdir) / "state.json"),
                None,
                LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl"),
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                route = edgewalker._inverse_cascade_route_override(
                    BotRoute(CHOP_BOT, SOXL, True)
                )

        self.assertEqual(route.active_bot, INVERSE_BOT)
        self.assertEqual(route.routed_symbol, SOXS)
        self.assertIn("[INVERSE] Cascade candidate qualified", output.getvalue())
        self.assertIn("base=ChopBot/SOXL", output.getvalue())

    def test_inverse_cascade_sustained_rejects_stalling_drop(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "96.5", "96.0", "95.9", "95.8"),
                "SOXS": bars("10.00", "10.20", "10.30", "10.35", "10.40"),
            }
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                inverse_cascade_sustain_minutes=3,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("[INVERSE] Cascade candidate blocked: mode=SUSTAINED", output)
        self.assertIn("source_not_deepening_during_sustain", output)
        self.assertEqual(status.active_bot, CHOP_BOT)

    def test_inverse_cascade_sustained_blocks_same_session_reentry(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "96.5", "96.0", "95.7", "95.4"),
                "SOXS": bars("10.00", "10.20", "10.30", "10.35", "10.40"),
            },
            previous_session_closes={SOXL: Decimal("100")},
        )

        def setup_state(state_store: BotStateStore) -> None:
            state_store.set_inverse_cascade_state(
                {
                    "mode": INVERSE_CASCADE_MODE_SUSTAINED,
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(bot_module.NY_TZ)
                    .date()
                    .isoformat(),
                    "entered_at": datetime.now(timezone.utc).isoformat(),
                    "lockout_active": True,
                }
            )

        output, status = self.run_bot(
            client,
            setup_state=setup_state,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                inverse_cascade_sustain_minutes=3,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("reason=inverse_cascade_reentry_locked", output)
        self.assertEqual(status.active_bot, INVERSE_BOT)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_inverse_cascade_stopout_blocks_same_session_legacy_inverse(
        self,
    ) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "99", "98", "97"),
                "SOXS": bars("10.00", "10.20", "10.40", "10.60"),
            }
        )

        def setup_state(state_store: BotStateStore) -> None:
            state_store.set_inverse_cascade_state(
                {
                    "mode": INVERSE_CASCADE_MODE_SUSTAINED,
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(bot_module.NY_TZ)
                    .date()
                    .isoformat(),
                    "entered_at": (
                        datetime.now(timezone.utc) - timedelta(minutes=10)
                    ).isoformat(),
                    "lockout_active": True,
                    "stopped_out_at": datetime.now(timezone.utc).isoformat(),
                    "stopped_out_reason": "trailing_stop_breached",
                }
            )

        output, status = self.run_bot(
            client,
            setup_state=setup_state,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("reason=inverse_cascade_stopped_out_session_locked", output)
        self.assertEqual(status.active_bot, INVERSE_BOT)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_inverse_cascade_sustained_uses_wider_trailing_stop(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "99", "98", "97", "96"),
                "SOXS": bars("10.00", "10.05", "10.04", "10.05", "10.05"),
            },
            positions={
                SOXS: {
                    "symbol": SOXS,
                    "qty": "1",
                    "avg_entry_price": "10.00",
                }
            },
        )

        def setup_state(state_store: BotStateStore) -> None:
            state_store.set_position_owner(SOXS, INVERSE_BOT)
            state_store.set_high_water_mark(SOXS, Decimal("10.20"))
            state_store.set_inverse_cascade_state(
                {
                    "mode": INVERSE_CASCADE_MODE_SUSTAINED,
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(bot_module.NY_TZ)
                    .date()
                    .isoformat(),
                    "entered_at": datetime.now(timezone.utc).isoformat(),
                    "lockout_active": True,
                }
            )

        output, status = self.run_bot(
            client,
            setup_state=setup_state,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                inverse_cascade_sustain_minutes=3,
                inverse_cascade_trail_percent=Decimal("3.50"),
                inverse_cascade_proven_mfe_percent=Decimal("0.75"),
            ),
        )

        self.assertEqual(client.sells, [])
        self.assertIn("trail=3.50%", output)
        self.assertEqual(status.action_taken, "manage_open_position")

    def test_inverse_cascade_intrabar_mfe_marks_proven_state(self) -> None:
        current_time = datetime(2026, 6, 5, 14, 0, tzinfo=timezone.utc)
        client = FakeClient(
            {
                "SOXL": bars("100", "99", "98", latest_at=current_time),
                "SOXS": ohlc_bars(
                    ("10.00", "10.00", "9.95", "9.98"),
                    ("9.98", "10.08", "9.97", "10.01"),
                    latest_at=current_time,
                ),
            },
            positions={
                SOXS: {
                    "symbol": SOXS,
                    "qty": "1",
                    "avg_entry_price": "10.00",
                }
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            lifecycle_ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            state_store.set_position_owner(SOXS, INVERSE_BOT)
            state_store.set_inverse_cascade_state(
                {
                    "mode": INVERSE_CASCADE_MODE_SUSTAINED,
                    "session_date": current_time.astimezone(bot_module.NY_TZ)
                    .date()
                    .isoformat(),
                    "entered_at": (current_time - timedelta(minutes=10)).isoformat(),
                    "lockout_active": True,
                    "invalidation_started_at": None,
                }
            )

            output = io.StringIO()
            with patched_bot_time(current_time), contextlib.redirect_stdout(output):
                status = EdgeWalkerBot(
                    replace(
                        config(),
                        inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                        inverse_cascade_proven_mfe_percent=Decimal("0.75"),
                    ),
                    client,
                    state_store,
                    None,
                    lifecycle_ledger,
                ).run_once()

            state = state_store.get_inverse_cascade_state()
            self.assertEqual(status.action_taken, "manage_open_position")
            self.assertIsNotNone(state.get("proven_at"))
            self.assertEqual(state.get("proven_threshold_percent"), "0.75")
            self.assertEqual(state.get("max_favorable_excursion_percent"), "0.8")

    def test_inverse_cascade_proven_suppresses_route_invalidation_and_widens_trail(
        self,
    ) -> None:
        current_time = datetime.now(timezone.utc)
        client = FakeClient(
            {
                "SOXL": bars("100", "96", "97", "98", latest_at=current_time),
                "SOXS": ohlc_bars(
                    ("10.00", "10.00", "9.95", "9.98"),
                    ("9.98", "10.08", "9.97", "10.01"),
                    ("10.01", "10.03", "9.94", "9.96"),
                    latest_at=current_time,
                ),
            },
            positions={
                SOXS: {
                    "symbol": SOXS,
                    "qty": "1",
                    "avg_entry_price": "10.00",
                }
            },
        )

        def setup_state(state_store: BotStateStore) -> None:
            state_store.set_position_owner(SOXS, INVERSE_BOT)
            state_store.set_inverse_cascade_state(
                {
                    "mode": INVERSE_CASCADE_MODE_SUSTAINED,
                    "session_date": current_time.astimezone(bot_module.NY_TZ)
                    .date()
                    .isoformat(),
                    "entered_at": (current_time - timedelta(minutes=20)).isoformat(),
                    "lockout_active": True,
                    "invalidation_started_at": (
                        current_time - timedelta(minutes=20)
                    ).isoformat(),
                }
            )

        output, status = self.run_bot(
            client,
            setup_state=setup_state,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                inverse_cascade_proven_mfe_percent=Decimal("0.75"),
                inverse_cascade_proven_trail_percent=Decimal("6.00"),
                inverse_cascade_proven_route_recovery_min_source_percent=Decimal("0.00"),
            ),
        )

        self.assertEqual(client.sells, [])
        self.assertIn("Proven cascade route invalidation suppressed", output)
        self.assertIn("trail=6.00%", output)
        self.assertEqual(
            status.action_taken,
            "hold_inverse_cascade_proven_route_suppressed",
        )

    def test_inverse_cascade_unproven_route_invalidates_normally(self) -> None:
        current_time = datetime.now(timezone.utc)
        client = FakeClient(
            {
                "SOXL": bars("100", "96", "97", "98", latest_at=current_time),
                "SOXS": ohlc_bars(
                    ("10.00", "10.02", "9.95", "9.98"),
                    ("9.98", "10.01", "9.90", "9.94"),
                    ("9.94", "9.98", "9.88", "9.90"),
                    latest_at=current_time,
                ),
            },
            positions={
                SOXS: {
                    "symbol": SOXS,
                    "qty": "1",
                    "avg_entry_price": "10.00",
                }
            },
        )

        def setup_state(state_store: BotStateStore) -> None:
            state_store.set_position_owner(SOXS, INVERSE_BOT)
            state_store.set_inverse_cascade_state(
                {
                    "mode": INVERSE_CASCADE_MODE_SUSTAINED,
                    "session_date": current_time.astimezone(bot_module.NY_TZ)
                    .date()
                    .isoformat(),
                    "entered_at": (current_time - timedelta(minutes=20)).isoformat(),
                    "lockout_active": True,
                    "invalidation_started_at": (
                        current_time - timedelta(minutes=10)
                    ).isoformat(),
                }
            )

        output, status = self.run_bot(
            client,
            setup_state=setup_state,
            bot_config=replace(
                config(),
                inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                inverse_cascade_proven_mfe_percent=Decimal("0.75"),
                inverse_cascade_route_invalidation_grace_minutes=5,
            ),
        )

        self.assertEqual(len(client.sells), 1)
        self.assertIn("route invalidated", output)
        self.assertEqual(
            status.action_taken,
            "close_route_invalidated_position_no_same_cycle_reversal",
        )

    def test_inverse_cascade_reset_keeps_state_while_position_open(self) -> None:
        current_time = datetime.now(timezone.utc)
        client = FakeClient(
            {"SOXL": bars("100", "99", "100", latest_at=current_time)},
            positions={
                SOXS: {
                    "symbol": SOXS,
                    "qty": "1",
                    "avg_entry_price": "10.00",
                }
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            lifecycle_ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            state_store.set_inverse_cascade_state(
                {
                    "mode": INVERSE_CASCADE_MODE_SUSTAINED,
                    "session_date": current_time.astimezone(bot_module.NY_TZ)
                    .date()
                    .isoformat(),
                    "entered_at": (current_time - timedelta(minutes=20)).isoformat(),
                    "lockout_active": True,
                }
            )

            edgewalker = EdgeWalkerBot(
                replace(
                    config(),
                    inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                ),
                client,
                state_store,
                None,
                lifecycle_ledger,
            )
            edgewalker._inverse_cascade_maybe_reset_state(
                {
                    "thresholds": {"reset_source_current_min": Decimal("-0.50")},
                    "source_current_percent": Decimal("0.00"),
                }
            )

            self.assertTrue(
                state_store.get_inverse_cascade_state().get("lockout_active")
            )

    def test_inverse_cascade_route_valid_clears_invalidation_timer(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "99", "98"),
                "SOXS": bars("10.00", "10.10", "10.20"),
            },
            positions={
                SOXS: {
                    "symbol": SOXS,
                    "qty": "1",
                    "avg_entry_price": "10.00",
                }
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            lifecycle_ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            state_store.set_position_owner(SOXS, INVERSE_BOT)
            state_store.set_inverse_cascade_state(
                {
                    "mode": INVERSE_CASCADE_MODE_SUSTAINED,
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(bot_module.NY_TZ)
                    .date()
                    .isoformat(),
                    "entered_at": datetime.now(timezone.utc).isoformat(),
                    "lockout_active": True,
                    "invalidation_started_at": (
                        datetime.now(timezone.utc) - timedelta(minutes=3)
                    ).isoformat(),
                }
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = EdgeWalkerBot(
                    replace(
                        config(),
                        inverse_cascade_mode=INVERSE_CASCADE_MODE_SUSTAINED,
                    ),
                    client,
                    state_store,
                    None,
                    lifecycle_ledger,
                ).run_once()

            self.assertEqual(status.action_taken, "manage_open_position")
            self.assertIsNone(
                state_store.get_inverse_cascade_state().get(
                    "invalidation_started_at"
                )
            )

    def test_v8_fresh_directional_regime_blocks_entry_until_survives(self) -> None:
        client = FakeClient({"SOXL": bars("100", "101", "102")})

        output, status = self.run_bot(client)

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [])
        self.assertIn("[V8] Directional survivability", output)
        self.assertIn("reason=v8_regime_too_young", output)
        self.assertEqual(status.regime, "UPTREND")
        self.assertEqual(status.active_bot, "MomentumBot")
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_v8_noisy_water_filter_blocks_survived_directional_entry(self) -> None:
        client = FakeClient({"SOXL": bars("100", "101", "102")})

        output, status = self.run_bot(
            client,
            setup_state=self.survived_regime("UPTREND", recent_flips=6),
        )

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [])
        self.assertIn("[V8] Directional survivability", output)
        self.assertIn("reason=v8_noisy_water_filter", output)
        self.assertEqual(status.regime, "UPTREND")
        self.assertEqual(status.active_bot, "MomentumBot")
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_v9_active_momentum_context_suppresses_inverse_entry(self) -> None:
        def setup_state(state_store: BotStateStore) -> None:
            self.survived_regime("DOWNTREND")(state_store)
            state_store.set_v9_momentum_context(
                {
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(NY_TZ)
                    .date()
                    .isoformat(),
                    "active": True,
                    "invalidated": False,
                    "evaluated": True,
                    "activation_reason": "v9_momentum_clean_tape_context",
                    "activated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        client = FakeClient(
            {
                "SOXL": bars("100", "101.4", "101.2", "101.0"),
                "SOXS": bars("8.00", "8.05", "8.10", "8.12"),
            }
        )

        output, status, records = self.run_bot_with_lifecycle(
            client,
            setup_state=setup_state,
            bot_config=replace(
                config(),
                preset_name="Lead_Momentum_Specialist",
                regime_gap_threshold=Decimal("0.05"),
                inverse_cascade_mode=bot_module.INVERSE_CASCADE_MODE_OFF,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("reason=v9_momentum_context_suppresses_inverse", output)
        self.assertEqual(status.active_bot, "InverseBot")
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")
        self.assertEqual(records[-1]["event_type"], LIFECYCLE_SHADOW_ENTRY_SUPPRESSED)
        self.assertEqual(records[-1]["bot"], "InverseBot")

    def test_v9_authority_precedes_v8_directional_blocks(self) -> None:
        def setup_state(state_store: BotStateStore) -> None:
            state_store.set_v9_momentum_context(
                {
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(NY_TZ)
                    .date()
                    .isoformat(),
                    "active": True,
                    "invalidated": False,
                    "evaluated": True,
                    "activation_reason": "v9_momentum_clean_tape_context",
                    "activated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        client = FakeClient(
            {
                "SOXL": bars("100", "102", "98", "101"),
                "SOXS": bars("8.00", "8.05", "8.10", "8.12"),
            }
        )

        output, status, records = self.run_bot_with_lifecycle(
            client,
            setup_state=setup_state,
            bot_config=replace(
                config(),
                preset_name="Lead_Momentum_Specialist",
                regime_gap_threshold=Decimal("0.05"),
                inverse_cascade_mode=bot_module.INVERSE_CASCADE_MODE_OFF,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("reason=v9_momentum_context_suppresses_inverse", output)
        self.assertNotIn("reason=v8_regime_too_young", output)
        self.assertEqual(status.active_bot, "InverseBot")
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(records[-1]["reason"], "v9_momentum_context_suppresses_inverse")

    def test_v9_dirty_active_context_releases_inverse_entry_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            state_store.set_v9_momentum_context(
                {
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(NY_TZ)
                    .date()
                    .isoformat(),
                    "active": True,
                    "invalidated": False,
                    "evaluated": True,
                    "activation_reason": "v9_momentum_clean_tape_context",
                    "activated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            data = state_store._read()
            data["regime"] = {
                "regime": "DOWNTREND",
                "transitions": [
                    {
                        "from": "UPTREND",
                        "to": "DOWNTREND",
                        "at": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            }
            state_store._write(data)
            bot = EdgeWalkerBot(
                replace(config(), preset_name="Lead_Momentum_Specialist"),
                FakeClient({"SOXL": bars("100", "106", "100")}),
                state_store,
            )

            decision = bot._v9_entry_policy_decision(
                BotRoute(INVERSE_BOT, SOXS, True),
                None,
            )
            context = state_store.get_v9_momentum_context()

        self.assertIsNone(decision)
        self.assertFalse(context["active"])
        self.assertTrue(context["invalidated"])
        self.assertEqual(
            context["invalidation_reason"],
            "momentum_drawdown_with_dirty_tape",
        )

    def test_momentum_authority_required_blocks_entry_without_active_context(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("100", "101", "102", "103"),
            }
        )

        output, status, records = self.run_bot_with_lifecycle(
            client,
            setup_state=self.survived_regime("UPTREND", minutes=20),
            bot_config=replace(
                config(),
                preset_name="Momentum_BalancedTight_Permission",
                regime_gap_threshold=Decimal("0.05"),
                momentum_authority_required=True,
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn("gate_reason=momentum_authority_required", output)
        self.assertEqual(status.active_bot, MOMENTUM_BOT)
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")
        self.assertEqual(records[-1]["event_type"], LIFECYCLE_SHADOW_ENTRY_SUPPRESSED)
        self.assertEqual(
            records[-1]["reason"],
            V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON,
        )
        self.assertEqual(
            records[-1]["v10_no_authority_context"]["activation_reason"],
            "momentum_authority_required",
        )

    def test_momentum_authority_hard_veto_blocks_active_context_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            state_store.set_v9_momentum_context(
                {
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(NY_TZ)
                    .date()
                    .isoformat(),
                    "active": True,
                    "invalidated": False,
                    "evaluated": True,
                    "activation_reason": "v9_momentum_clean_tape_context",
                    "activated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            data = state_store._read()
            data["regime"] = {
                "regime": "UPTREND",
                "transitions": [
                    {
                        "from": "SIDEWAYS",
                        "to": "UPTREND",
                        "at": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            }
            state_store._write(data)
            lifecycle_ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Momentum_BalancedTight_Permission",
                    momentum_authority_required=True,
                ),
                FakeClient({"SOXL": bars("100", "106", "100")}),
                state_store,
                lifecycle_ledger=lifecycle_ledger,
            )

            decision = bot._momentum_authority_entry_policy_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True),
                None,
            )
            context = state_store.get_v9_momentum_context()
            records = lifecycle_ledger.read_all()

        self.assertIsNotNone(decision)
        self.assertFalse(decision.signal)
        self.assertEqual(
            decision.reason,
            V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON,
        )
        self.assertFalse(context["active"])
        self.assertTrue(context["invalidated"])
        self.assertEqual(
            context["invalidation_reason"],
            "momentum_drawdown_with_dirty_tape",
        )
        self.assertEqual(
            records[-1]["v10_no_authority_context"]["activation_reason"],
            "momentum_drawdown_with_dirty_tape",
        )

    def test_momentum_authority_latch_allows_later_entry_after_active_context(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            state_store.set_v9_momentum_context(
                {
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(NY_TZ)
                    .date()
                    .isoformat(),
                    "active": True,
                    "invalidated": False,
                    "evaluated": True,
                    "activation_reason": "v9_momentum_clean_tape_context",
                    "activated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            data = state_store._read()
            data["regime"] = {
                "regime": "UPTREND",
                "transitions": [
                    {
                        "from": "SIDEWAYS",
                        "to": "UPTREND",
                        "at": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            }
            state_store._write(data)
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Momentum_BalancedTight_StrictLatch",
                    momentum_authority_required=True,
                    momentum_authority_latch_once_active=True,
                ),
                FakeClient({"SOXL": bars("100", "106", "100")}),
                state_store,
            )

            decision = bot._momentum_authority_entry_policy_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True),
                None,
            )
            context = state_store.get_v9_momentum_context()

        self.assertIsNone(decision)
        self.assertTrue(context["momentum_authority_latched"])
        self.assertTrue(context["active"])
        self.assertFalse(context["invalidated"])

    def test_momentum_authority_latch_still_blocks_before_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            lifecycle_ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Momentum_BalancedTight_StrictLatch",
                    momentum_authority_required=True,
                    momentum_authority_latch_once_active=True,
                ),
                FakeClient({"SOXL": bars("100", "101", "102")}),
                state_store,
                lifecycle_ledger=lifecycle_ledger,
            )

            decision = bot._momentum_authority_entry_policy_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True),
                None,
            )
            context = state_store.get_v9_momentum_context()
            records = lifecycle_ledger.read_all()

        self.assertIsNotNone(decision)
        self.assertFalse(decision.signal)
        self.assertEqual(
            decision.reason,
            V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON,
        )
        self.assertFalse(context.get("momentum_authority_latched", False))
        self.assertEqual(
            records[-1]["v10_no_authority_context"]["activation_reason"],
            "momentum_authority_required",
        )

    def test_v10_authority_state_treats_latched_context_as_momentum(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            state_store.set_v9_momentum_context(
                {
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(NY_TZ)
                    .date()
                    .isoformat(),
                    "active": False,
                    "invalidated": True,
                    "evaluated": True,
                    "invalidation_reason": "momentum_drawdown_with_dirty_tape",
                    "momentum_authority_latched": True,
                }
            )
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Momentum_BalancedTight_StrictLatch",
                    momentum_authority_latch_once_active=True,
                ),
                FakeClient({"SOXL": bars("100", "101")}),
                state_store,
            )

            authority_state = bot._v10_authority_state()

        self.assertEqual(authority_state, V10_AUTHORITY_STATE_MOMENTUM)

    def test_momentum_authority_revoke_exits_owned_position(self) -> None:
        def setup_state(state_store: BotStateStore) -> None:
            self.survived_regime("UPTREND", minutes=20)(state_store)
            state_store.set_position_owner(SOXL, MOMENTUM_BOT)
            state_store.set_v9_momentum_context(
                {
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(NY_TZ)
                    .date()
                    .isoformat(),
                    "active": False,
                    "invalidated": True,
                    "evaluated": True,
                    "activation_reason": "v9_momentum_clean_tape_context",
                    "invalidation_reason": "momentum_drawdown_with_dirty_tape",
                    "invalidated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        client = FakeClient(
            {"SOXL": bars("100", "101", "102", "103")},
            positions={SOXL: {"qty": "1.25", "avg_entry_price": "101"}},
        )

        output, status, records = self.run_bot_with_lifecycle(
            client,
            setup_state=setup_state,
            bot_config=replace(
                config(),
                preset_name="Momentum_BalancedTight_Permission",
                regime_gap_threshold=Decimal("0.05"),
                momentum_authority_required=True,
                momentum_authority_revoke_exits=True,
            ),
        )

        self.assertEqual(client.sells, [(SOXL, Decimal("1.25"))])
        self.assertIn("Momentum authority revoked", output)
        self.assertEqual(
            status.action_taken,
            "close_momentum_authority_revoked_position_no_same_cycle_reversal",
        )
        self.assertEqual(records[-1]["reason"], MOMENTUM_AUTHORITY_REVOKED_EXIT_REASON)
        self.assertEqual(
            records[-1]["authority_revoke_reason"],
            "momentum_drawdown_with_dirty_tape",
        )

    def test_v9_first_30m_non_warmup_transition_blocks_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Lead_Momentum_Specialist",
                    v9_observer_context={
                        "observer_preset": "Lead_Generalist",
                        "early_transition_count": 1,
                        "early_transitions_per_hour": 2,
                        "early_non_warmup_transition_count": 1,
                        "early_non_warmup_transitions_per_hour": 2,
                        "trend_trust_score": 60,
                        "source_open_to_current_percent": 1,
                        "early_transition_window_minutes": 30,
                    },
                ),
                FakeClient({"SOXL": bars("100", "101")}),
                state_store,
            )

            decision = bot._v9_momentum_context_activation_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True)
            )

        self.assertEqual(decision["early_transition_count"], 1)
        self.assertEqual(decision["early_non_warmup_transition_count"], 1)
        self.assertEqual(decision["observer_preset"], "Lead_Generalist")
        self.assertFalse(decision["active"])
        self.assertIn(
            "first_30m_non_warmup_transition_count_not_zero",
            decision["activation_reason"],
        )

    def test_v9_observer_warmup_exit_only_activates_momentum_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Lead_Momentum_Specialist",
                    v9_observer_context={
                        "observer_preset": "Lead_Generalist",
                        "early_transition_count": 1,
                        "early_transitions_per_hour": 2,
                        "early_non_warmup_transition_count": 0,
                        "early_non_warmup_transitions_per_hour": 0,
                        "trend_trust_score": 60,
                        "source_open_to_current_percent": 2.5,
                        "early_transition_window_minutes": 30,
                    },
                ),
                FakeClient({"SOXL": bars("100", "101")}),
                state_store,
            )
            session_open = bot._v9_session_open()
            data = state_store._read()
            data["regime"] = {
                "regime": "UPTREND",
                "transitions": [
                    {
                        "from": "UPTREND",
                        "to": "DOWNTREND",
                        "at": (session_open + timedelta(minutes=31)).isoformat(),
                    }
                ],
            }
            state_store._write(data)

            decision = bot._v9_momentum_context_activation_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True)
            )

        self.assertEqual(decision["early_transition_count"], 1)
        self.assertEqual(decision["early_non_warmup_transition_count"], 0)
        self.assertEqual(decision["observer_preset"], "Lead_Generalist")
        self.assertTrue(decision["active"])
        self.assertEqual(decision["activation_reason"], "v9_momentum_clean_tape_context")

    def test_v9_strict_momentum_authority_threshold_blocks_weak_reclaim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Momentum_BalancedTight_StrictAuthority",
                    momentum_authority_min_trust_score=66,
                    momentum_authority_min_source_percent=Decimal("4.00"),
                    v9_observer_context={
                        "observer_preset": "Lead_Generalist",
                        "early_transition_count": 1,
                        "early_transitions_per_hour": 2,
                        "early_non_warmup_transition_count": 0,
                        "early_non_warmup_transitions_per_hour": 0,
                        "trend_trust_score": 60,
                        "source_open_to_current_percent": 3.5,
                        "early_transition_window_minutes": 30,
                    },
                ),
                FakeClient({"SOXL": bars("100", "101")}),
                state_store,
            )

            decision = bot._v9_momentum_context_activation_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True)
            )

        self.assertFalse(decision["active"])
        self.assertIn("soxl_below_v9_momentum_floor", decision["activation_reason"])
        self.assertIn("trend_trust_below_v9_minimum", decision["activation_reason"])

    def test_v9_strict_reclaim_allows_clean_secondary_checkpoint(self) -> None:
        current_time = datetime(2026, 3, 23, 10, 20, tzinfo=NY_TZ).astimezone(
            timezone.utc
        )
        with tempfile.TemporaryDirectory() as tmpdir, patched_bot_time(current_time):
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Momentum_BalancedTight_StrictReclaim",
                    momentum_authority_min_trust_score=66,
                    momentum_authority_min_source_percent=Decimal("4.00"),
                    momentum_authority_reclaim_enabled=True,
                    v9_observer_context={
                        "observer_preset": "Lead_Generalist",
                        "early_transition_count": 1,
                        "early_transitions_per_hour": 2,
                        "early_non_warmup_transition_count": 0,
                        "early_non_warmup_transitions_per_hour": 0,
                        "trend_trust_score": 59,
                        "source_open_to_current_percent": 2.38,
                        "early_transition_window_minutes": 30,
                    },
                ),
                FakeClient({"SOXL": bars("100", "104.50", latest_at=current_time)}),
                state_store,
            )

            decision = bot._v9_momentum_context_activation_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True)
            )

        self.assertTrue(decision["active"])
        self.assertEqual(
            decision["activation_reason"],
            "v9_momentum_strict_reclaim_context",
        )
        self.assertEqual(decision["source_open_to_current_percent"], 4.5)
        self.assertEqual(decision["reclaim_session_non_warmup_transition_count"], 0)

    def test_v9_strict_reclaim_blocks_session_non_warmup_flip(self) -> None:
        current_time = datetime(2026, 3, 23, 10, 20, tzinfo=NY_TZ).astimezone(
            timezone.utc
        )
        with tempfile.TemporaryDirectory() as tmpdir, patched_bot_time(current_time):
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            data = state_store._read()
            data["regime"] = {
                "regime": "DOWNTREND",
                "transitions": [
                    {
                        "from": "UPTREND",
                        "to": "DOWNTREND",
                        "at": (current_time - timedelta(minutes=5)).isoformat(),
                    }
                ],
            }
            state_store._write(data)
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Momentum_BalancedTight_StrictReclaim",
                    momentum_authority_min_trust_score=66,
                    momentum_authority_min_source_percent=Decimal("4.00"),
                    momentum_authority_reclaim_enabled=True,
                    v9_observer_context={
                        "observer_preset": "Lead_Generalist",
                        "early_transition_count": 1,
                        "early_transitions_per_hour": 2,
                        "early_non_warmup_transition_count": 0,
                        "early_non_warmup_transitions_per_hour": 0,
                        "trend_trust_score": 59,
                        "source_open_to_current_percent": 2.38,
                        "early_transition_window_minutes": 30,
                    },
                ),
                FakeClient({"SOXL": bars("100", "104.50", latest_at=current_time)}),
                state_store,
            )

            decision = bot._v9_momentum_context_activation_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True)
            )

        self.assertFalse(decision["active"])
        self.assertIn(
            "reclaim_session_non_warmup_transition_count_not_zero",
            decision["activation_reason"],
        )

    def test_v9_requires_material_soxl_reclaim_at_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Lead_Momentum_Specialist",
                    v9_observer_context={
                        "observer_preset": "Lead_Generalist",
                        "early_transition_count": 1,
                        "early_transitions_per_hour": 2,
                        "early_non_warmup_transition_count": 0,
                        "early_non_warmup_transitions_per_hour": 0,
                        "trend_trust_score": 60,
                        "source_open_to_current_percent": 1.5,
                        "early_transition_window_minutes": 30,
                    },
                ),
                FakeClient({"SOXL": bars("100", "101")}),
                state_store,
            )

            decision = bot._v9_momentum_context_activation_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True)
            )

        self.assertFalse(decision["active"])
        self.assertIn(
            "soxl_below_v9_momentum_floor",
            decision["activation_reason"],
        )

    def test_v9_dirty_drawdown_blocks_momentum_context_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Lead_Momentum_Specialist",
                    v9_observer_context={
                        "observer_preset": "Lead_Generalist",
                        "early_transition_count": 1,
                        "early_transitions_per_hour": 2,
                        "early_non_warmup_transition_count": 0,
                        "early_non_warmup_transitions_per_hour": 0,
                        "trend_trust_score": 60,
                        "source_open_to_current_percent": 2,
                        "early_transition_window_minutes": 30,
                    },
                ),
                FakeClient({"SOXL": bars("100", "106", "100")}),
                state_store,
            )
            data = state_store._read()
            data["regime"] = {
                "regime": "DOWNTREND",
                "transitions": [
                    {
                        "from": "UPTREND",
                        "to": "DOWNTREND",
                        "at": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            }
            state_store._write(data)

            decision = bot._v9_momentum_context_activation_decision(
                BotRoute(INVERSE_BOT, SOXS, True)
            )

        self.assertFalse(decision["active"])
        self.assertIn(
            "momentum_drawdown_with_dirty_tape",
            decision["activation_reason"],
        )

    def test_v9_missing_observer_context_blocks_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            bot = EdgeWalkerBot(
                replace(config(), preset_name="Lead_Momentum_Specialist"),
                FakeClient({"SOXL": bars("100", "101")}),
                state_store,
            )

            decision = bot._v9_momentum_context_activation_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True)
            )

        self.assertFalse(decision["active"])
        self.assertIn("observer_context_unavailable", decision["activation_reason"])

    def test_v9_runtime_observer_context_uses_live_first_30m_telemetry(self) -> None:
        current_time = datetime(2026, 6, 9, 10, 0, tzinfo=NY_TZ)
        session_open = current_time.replace(hour=9, minute=30).astimezone(timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir, patched_bot_time(current_time):
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            state_store._write(
                {
                    "regime": {
                        "regime": "UPTREND",
                        "regime_since": session_open.isoformat(),
                        "transitions": [
                            {
                                "from": "WARMUP",
                                "to": "SIDEWAYS",
                                "at": (session_open + timedelta(minutes=2)).isoformat(),
                            },
                            {
                                "from": "SIDEWAYS",
                                "to": "UPTREND",
                                "at": (session_open + timedelta(minutes=10)).isoformat(),
                            },
                            {
                                "from": "UPTREND",
                                "to": "SIDEWAYS",
                                "at": (session_open + timedelta(minutes=35)).isoformat(),
                            },
                        ],
                    },
                }
            )
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Router_StrictAuthority_ChopFirewall",
                    v9_observer_context={
                        "observer_preset": "BalancedPure_LiveObserver",
                        "runtime_observer": True,
                        "execution_rights": "none",
                    },
                ),
                FakeClient(
                    {
                        "SOXL": bars(
                            "100",
                            "101",
                            "104.50",
                            latest_at=current_time,
                        )
                    }
                ),
                state_store,
            )
            bot._trend_trust = {"score": 67}

            observer_context = bot._v9_observer_context()

        self.assertEqual(observer_context["observer_preset"], "BalancedPure_LiveObserver")
        self.assertEqual(observer_context["early_transition_count"], 2)
        self.assertEqual(observer_context["early_non_warmup_transition_count"], 1)
        self.assertEqual(observer_context["early_transitions_per_hour"], 4.0)
        self.assertEqual(observer_context["early_non_warmup_transitions_per_hour"], 2.0)
        self.assertEqual(observer_context["trend_trust_score"], 67)
        self.assertEqual(observer_context["source_open_to_current_percent"], 4.5)
        self.assertEqual(observer_context["execution_rights"], "none")

    def test_v9_force_no_authority_blocks_research_fallback_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Lead_Momentum_Specialist",
                    v10_force_no_authority=True,
                    v9_observer_context={
                        "observer_preset": "Lead_Generalist",
                        "early_transition_count": 1,
                        "early_transitions_per_hour": 2,
                        "early_non_warmup_transition_count": 0,
                        "early_non_warmup_transitions_per_hour": 0,
                        "trend_trust_score": 63,
                        "source_open_to_current_percent": 3.5,
                        "early_transition_window_minutes": 30,
                    },
                ),
                FakeClient({"SOXL": bars("100", "103")}),
                state_store,
            )

            decision = bot._v9_momentum_context_activation_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True)
            )

        self.assertFalse(decision["active"])
        self.assertIn("v10_forced_no_authority_fallback", decision["activation_reason"])

    def test_v10_force_no_authority_suppresses_before_v9_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Router_v1_NoAuthority",
                    v10_force_no_authority=True,
                    v9_observer_context={
                        "observer_preset": "Lead_Generalist",
                        "early_transition_count": 1,
                        "early_transitions_per_hour": 2,
                        "early_non_warmup_transition_count": 0,
                        "early_non_warmup_transitions_per_hour": 0,
                        "trend_trust_score": 63,
                        "source_open_to_current_percent": 3.5,
                        "early_transition_window_minutes": 30,
                    },
                ),
                FakeClient({"SOXL": bars("100", "103")}),
                state_store,
                lifecycle_ledger=ledger,
            )

            decision = bot._v10_entry_policy_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True),
                None,
            )
            records = ledger.read_all()

        self.assertIsNotNone(decision)
        self.assertFalse(decision.signal)
        self.assertEqual(
            decision.reason,
            V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON,
        )
        self.assertEqual(records[-1]["event_type"], LIFECYCLE_SHADOW_ENTRY_SUPPRESSED)
        self.assertEqual(records[-1]["authority_state"], V10_AUTHORITY_STATE_NONE)

    def test_v10_force_no_authority_works_without_observer_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Chop_BaselineClean",
                    v10_force_no_authority=True,
                ),
                FakeClient({"SOXL": bars("100", "103")}),
                state_store,
                lifecycle_ledger=ledger,
            )

            decision = bot._v10_entry_policy_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True),
                None,
            )
            records = ledger.read_all()

        self.assertIsNotNone(decision)
        self.assertFalse(decision.signal)
        self.assertEqual(
            decision.reason,
            V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON,
        )
        self.assertEqual(records[-1]["event_type"], LIFECYCLE_SHADOW_ENTRY_SUPPRESSED)
        self.assertEqual(records[-1]["authority_state"], V10_AUTHORITY_STATE_NONE)

    def test_v10_no_authority_suppresses_directional_entry_with_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            state_store.set_regime_state("UPTREND", Decimal("0.50"))
            state_store.set_v9_momentum_context(
                {
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(NY_TZ)
                    .date()
                    .isoformat(),
                    "active": False,
                    "invalidated": False,
                    "evaluated": True,
                    "activation_reason": "soxl_below_v9_momentum_floor",
                }
            )
            ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            bot = EdgeWalkerBot(
                replace(
                    config(),
                    preset_name="Lead_Momentum_Specialist",
                    v9_observer_context={
                        "observer_preset": "Lead_Generalist",
                        "early_transition_count": 1,
                        "early_transitions_per_hour": 2,
                        "early_non_warmup_transition_count": 0,
                        "early_non_warmup_transitions_per_hour": 0,
                        "trend_trust_score": 63,
                        "source_open_to_current_percent": 1.5,
                        "early_transition_window_minutes": 30,
                    },
                ),
                FakeClient({"SOXL": bars("100", "103")}),
                state_store,
                lifecycle_ledger=ledger,
            )
            bot._trend_trust = {
                "score": 61,
                "label": "MODERATE",
                "regime_age_minutes": 12.5,
                "recent_flip_count_60m": 1,
            }

            decision = bot._v10_entry_policy_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True),
                None,
            )
            records = ledger.read_all()

        self.assertIsNotNone(decision)
        self.assertFalse(decision.signal)
        self.assertEqual(
            decision.reason,
            V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON,
        )
        self.assertEqual(records[-1]["event_type"], LIFECYCLE_SHADOW_ENTRY_SUPPRESSED)
        self.assertEqual(records[-1]["reason"], V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON)
        self.assertEqual(records[-1]["authority_state"], V10_AUTHORITY_STATE_NONE)
        context = records[-1]["v10_no_authority_context"]
        self.assertEqual(context["observer_preset"], "Lead_Generalist")
        self.assertEqual(context["route_bot"], MOMENTUM_BOT)
        self.assertEqual(context["trend_trust_score"], 61)
        self.assertEqual(context["early_non_warmup_transition_count"], 0)
        self.assertEqual(context["source_open_to_current_percent"], 3.0)

    def test_v10_no_authority_precedes_v8_directional_blocks(self) -> None:
        def setup_state(state_store: BotStateStore) -> None:
            state_store.set_v9_momentum_context(
                {
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(NY_TZ)
                    .date()
                    .isoformat(),
                    "active": False,
                    "invalidated": False,
                    "evaluated": True,
                    "activation_reason": "soxl_below_v9_momentum_floor",
                }
            )

        client = FakeClient({"SOXL": bars("100", "101", "102")})

        output, status, records = self.run_bot_with_lifecycle(
            client,
            setup_state=setup_state,
            bot_config=replace(
                config(),
                preset_name="Lead_Momentum_Specialist",
                v9_observer_context={
                    "observer_preset": "Lead_Generalist",
                    "early_transition_count": 1,
                    "early_transitions_per_hour": 2,
                    "early_non_warmup_transition_count": 0,
                    "early_non_warmup_transitions_per_hour": 0,
                    "trend_trust_score": 63,
                    "source_open_to_current_percent": 1.5,
                    "early_transition_window_minutes": 30,
                },
            ),
        )

        self.assertEqual(client.buys, [])
        self.assertIn(f"reason={V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON}", output)
        self.assertNotIn("reason=v8_regime_too_young", output)
        self.assertEqual(status.active_bot, MOMENTUM_BOT)
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(records[-1]["event_type"], LIFECYCLE_SHADOW_ENTRY_SUPPRESSED)
        self.assertEqual(records[-1]["reason"], V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON)

    def test_v10_waits_for_v9_context_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            bot = EdgeWalkerBot(
                replace(config(), preset_name="Lead_Momentum_Specialist"),
                FakeClient({"SOXL": bars("100", "103")}),
                state_store,
            )

            decision = bot._v10_entry_policy_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True),
                None,
            )

        self.assertIsNone(decision)

    def test_v10_requires_observer_context_before_no_authority_suppression(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            state_store.set_v9_momentum_context(
                {
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(NY_TZ)
                    .date()
                    .isoformat(),
                    "active": False,
                    "invalidated": False,
                    "evaluated": True,
                    "activation_reason": "observer_context_unavailable",
                }
            )
            ledger = LifecycleLedger(Path(tmpdir) / "lifecycle.jsonl")
            bot = EdgeWalkerBot(
                replace(config(), preset_name="Lead_Generalist"),
                FakeClient({"SOXL": bars("100", "103")}),
                state_store,
                lifecycle_ledger=ledger,
            )

            decision = bot._v10_entry_policy_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True),
                None,
            )

        self.assertIsNone(decision)
        self.assertEqual(ledger.read_all(), [])

    def test_v10_no_authority_preserves_chopbot_exemption(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            state_store.set_v9_momentum_context(
                {
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(NY_TZ)
                    .date()
                    .isoformat(),
                    "active": False,
                    "invalidated": False,
                    "evaluated": True,
                    "activation_reason": "soxl_below_v9_momentum_floor",
                }
            )
            bot = EdgeWalkerBot(
                replace(config(), preset_name="Lead_Momentum_Specialist"),
                FakeClient({"SOXL": bars("100", "101")}),
                state_store,
            )

            decision = bot._v10_entry_policy_decision(
                BotRoute("ChopBot", SOXL, True),
                None,
            )

        self.assertIsNone(decision)

    def test_v10_does_not_suppress_while_momentum_authority_is_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = BotStateStore(Path(tmpdir) / "state.json")
            state_store.set_v9_momentum_context(
                {
                    "session_date": datetime.now(timezone.utc)
                    .astimezone(NY_TZ)
                    .date()
                    .isoformat(),
                    "active": True,
                    "invalidated": False,
                    "evaluated": True,
                    "activation_reason": "v9_momentum_clean_tape_context",
                    "activated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            bot = EdgeWalkerBot(
                replace(config(), preset_name="Lead_Momentum_Specialist"),
                FakeClient({"SOXL": bars("100", "103")}),
                state_store,
            )

            decision = bot._v10_entry_policy_decision(
                BotRoute(MOMENTUM_BOT, SOXL, True),
                None,
            )

        self.assertIsNone(decision)

    def test_v7_route_invalidation_breaker_pauses_fresh_entries(self) -> None:
        def setup_lifecycle(ledger: LifecycleLedger) -> None:
            for index in range(3):
                ledger.record(
                    LIFECYCLE_POSITION_CLOSED,
                    bot="MomentumBot",
                    symbol="SOXL",
                    side="sell",
                    qty="0.1",
                    reason="route_invalidated_exit",
                    order_id=f"sell-{index}",
                )

        client = FakeClient({"SOXL": bars("100", "101", "102")})

        output, status = self.run_bot(
            client,
            setup_lifecycle=setup_lifecycle,
        )

        self.assertEqual(client.sells, [])
        self.assertEqual(client.buys, [])
        self.assertIn("[V7] Fresh entries paused", output)
        self.assertIn("reason=v7_route_invalidation_breaker", output)
        self.assertEqual(status.regime, "UPTREND")
        self.assertEqual(status.active_bot, "MomentumBot")
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_conservative_inverse_still_requires_fresh_cross(self) -> None:
        client = FakeClient(
            {
                "SOXL": bars("103", "102", "101"),
                "SOXS": bars("8.00", "8.10", "8.14"),
            }
        )

        output, status = self.run_bot(
            client,
            bot_config=replace(
                config(),
                directional_mode="CONSERVATIVE",
                inverse_cascade_mode=bot_module.INVERSE_CASCADE_MODE_OFF,
            ),
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
            bot_config=replace(
                config(),
                directional_mode="AGGRESSIVE",
                inverse_cascade_mode=bot_module.INVERSE_CASCADE_MODE_OFF,
            ),
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

        output, status = self.run_bot(
            client,
            setup_state=self.survived_regime("UPTREND"),
        )

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
            setup_state=self.survived_regime("UPTREND"),
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
            setup_state=self.survived_regime("UPTREND"),
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

    def test_chop_loose_permission_blocks_when_momentum_authority_active(self) -> None:
        current_time = datetime(2026, 4, 1, 10, 5, tzinfo=NY_TZ).astimezone(
            timezone.utc
        )
        client = FakeClient(
            {"SOXL": bars("100", "101", "99", latest_at=current_time)}
        )

        with patched_bot_time(current_time):
            output, status = self.run_bot(
                client,
                bot_config=replace(
                    config(),
                    enabled_bots=(CHOP_BOT,),
                    chop_permission_mode="LOOSE",
                    v9_observer_context={
                        "observer_preset": "Chop_Ungated",
                        "early_transition_count": 0,
                        "early_transitions_per_hour": 0,
                        "early_non_warmup_transition_count": 0,
                        "early_non_warmup_transitions_per_hour": 0,
                        "trend_trust_score": 70,
                        "source_open_to_current_percent": 4.5,
                        "early_transition_window_minutes": 30,
                    },
                ),
            )

        self.assertEqual(client.buys, [])
        self.assertIn("Chop permission suppresses entry", output)
        self.assertIn("reason=chop_momentum_authority_active", output)
        self.assertEqual(status.active_bot, CHOP_BOT)
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_chop_strict_permission_blocks_noisy_early_transition(self) -> None:
        current_time = datetime(2026, 4, 1, 10, 5, tzinfo=NY_TZ).astimezone(
            timezone.utc
        )
        client = FakeClient(
            {"SOXL": bars("100", "101", "99", latest_at=current_time)}
        )

        with patched_bot_time(current_time):
            output, status = self.run_bot(
                client,
                bot_config=replace(
                    config(),
                    enabled_bots=(CHOP_BOT,),
                    chop_permission_mode="STRICT",
                    v9_observer_context={
                        "observer_preset": "Chop_Ungated",
                        "early_transition_count": 1,
                        "early_transitions_per_hour": 2,
                        "early_non_warmup_transition_count": 0,
                        "early_non_warmup_transitions_per_hour": 0,
                        "trend_trust_score": 40,
                        "source_open_to_current_percent": 0.5,
                        "early_transition_window_minutes": 30,
                    },
                ),
            )

        self.assertEqual(client.buys, [])
        self.assertIn("Chop permission suppresses entry", output)
        self.assertIn("reason=chop_early_transition_count_not_zero", output)
        self.assertEqual(status.active_bot, CHOP_BOT)
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_chop_firewall_permission_blocks_negative_noisy_tape(self) -> None:
        current_time = datetime(2026, 6, 8, 10, 5, tzinfo=NY_TZ).astimezone(
            timezone.utc
        )
        client = FakeClient(
            {"SOXL": bars("100", "100", "99", latest_at=current_time)}
        )

        with patched_bot_time(current_time):
            output, status = self.run_bot(
                client,
                bot_config=replace(
                    config(),
                    enabled_bots=(CHOP_BOT,),
                    chop_permission_mode="FIREWALL",
                    v9_observer_context={
                        "observer_preset": "Generalist_BalancedPure_Observer",
                        "early_transition_count": 3,
                        "early_transitions_per_hour": 6,
                        "early_non_warmup_transition_count": 2,
                        "early_non_warmup_transitions_per_hour": 4,
                        "trend_trust_score": 57,
                        "source_open_to_current_percent": -0.36,
                        "early_transition_window_minutes": 30,
                    },
                ),
            )

        self.assertEqual(client.buys, [])
        self.assertIn("Chop permission suppresses entry", output)
        self.assertIn("reason=chop_negative_noisy_tape", output)
        self.assertEqual(status.active_bot, CHOP_BOT)
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")

    def test_chop_firewall_permission_blocks_deep_source_drawdown(self) -> None:
        current_time = datetime(2026, 6, 4, 10, 5, tzinfo=NY_TZ).astimezone(
            timezone.utc
        )
        soxl_bars = bars("100", "100", "99", latest_at=current_time)
        soxl_bars[1]["l"] = "94"
        client = FakeClient({"SOXL": soxl_bars})

        with patched_bot_time(current_time):
            output, status = self.run_bot(
                client,
                bot_config=replace(
                    config(),
                    enabled_bots=(CHOP_BOT,),
                    chop_permission_mode="FIREWALL",
                    v9_observer_context={
                        "observer_preset": "Generalist_BalancedPure_Observer",
                        "early_transition_count": 1,
                        "early_transitions_per_hour": 2,
                        "early_non_warmup_transition_count": 0,
                        "early_non_warmup_transitions_per_hour": 0,
                        "trend_trust_score": 40,
                        "source_open_to_current_percent": -1.24,
                        "early_transition_window_minutes": 30,
                    },
                ),
            )

        self.assertEqual(client.buys, [])
        self.assertIn("Chop permission suppresses entry", output)
        self.assertIn("reason=chop_source_drawdown_firewall", output)
        self.assertEqual(status.active_bot, CHOP_BOT)
        self.assertEqual(status.entry_signal, False)
        self.assertEqual(status.action_taken, "no_entry_signal")

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

    def test_previous_session_close_uses_latest_bar_before_current_session(
        self,
    ) -> None:
        client = AlpacaClient(config())
        calls: list[tuple[str, str, dict[str, str] | None]] = []

        def fake_data_request(
            method: str,
            path: str,
            params: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            calls.append((method, path, params))
            return {
                "bars": [
                    {"t": "2026-06-08T04:00:00Z", "c": "99.50"},
                    {"t": "2026-06-09T04:00:00Z", "c": "101.25"},
                    {"t": "2026-06-10T04:00:00Z", "c": "102.75"},
                ],
                "next_page_token": None,
                "symbol": "SOXL",
            }

        client._data_request = fake_data_request

        with patched_bot_time(datetime(2026, 6, 10, 14, 0, tzinfo=timezone.utc)):
            previous_close = client.get_previous_session_close("SOXL")

        self.assertEqual(previous_close, Decimal("101.25"))
        self.assertEqual(calls[0][0], "GET")
        self.assertEqual(calls[0][1], "/stocks/SOXL/bars")
        self.assertEqual(calls[0][2]["timeframe"], "1Day")


if __name__ == "__main__":
    unittest.main()
