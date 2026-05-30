from __future__ import annotations

import json
import os
import threading
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from bot import (
    BotConfig,
    BotError,
    CHOP_BOT,
    INVERSE_BOT,
    LIFECYCLE_FULL_FILL,
    LIFECYCLE_ORDER_ACCEPTED,
    LIFECYCLE_ORDER_SUBMITTED,
    LIFECYCLE_PARTIAL_FILL,
    MOMENTUM_BOT,
    POSITION_LIFECYCLE_CLOSED,
    POSITION_LIFECYCLE_CLOSING,
    POSITION_LIFECYCLE_OPEN,
    POSITION_LIFECYCLE_OPENING,
    broker_constraint_ok,
    broker_constraint_payload,
)
from server import (
    BotRunner,
    NY_TZ,
    _append_daily_jsonl,
    _build_summary_prompt,
    _current_ny_activity,
    _cycle_log_record,
    _daily_log_path,
    _display_date_label,
    _extract_session_context,
    _format_regime_transition,
    _config_for_alpaca_environment,
    _is_allowed_ui_origin,
    _most_recent_log_date,
    _parse_narrative_response,
    alpaca_environment_settings,
    build_summary_prompt,
    config_from_payload,
    lifecycle_performance_summary,
    order_visibility_summary,
    save_alpaca_environment_settings,
    set_live_trading_armed,
    set_live_trading_disarmed,
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
        fast_sma_minutes=5,
        slow_sma_minutes=20,
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


class ServerLoggingTest(unittest.TestCase):
    def test_daily_jsonl_uses_new_york_local_date_and_writes_record(self) -> None:
        timestamp = datetime(2026, 5, 22, 1, 5, 0, tzinfo=timezone.utc)
        status = {
            "regime": "UPTREND",
            "active_bot": "MomentumBot",
            "routed_symbol": "SOXL",
            "source_price": "170.42",
            "portfolio_value": "50.09",
            "action_taken": "no_entry_signal",
        }
        transition = {"from": "SIDEWAYS", "to": "UPTREND", "gap_percent": "0.28"}
        performance = {
            "source": "position_lifecycle",
            "session_date": "2026-05-21",
            "session_realized_pl": "5",
            "session_trade_count": 1,
            "bot_performance": [
                {
                    "bot": MOMENTUM_BOT,
                    "realized_pl": "5",
                    "trade_count": 1,
                    "wins": 1,
                    "losses": 0,
                    "win_rate_percent": "100",
                    "last_trade_realized_pl": "5",
                    "last_trade_symbol": "SOXL",
                    "last_trade_closed_at": "2026-05-22T01:00:00+00:00",
                }
            ],
        }
        order_state = {
            "source": "position_lifecycle",
            "session_date": "2026-05-21",
            "pending_count": 1,
            "pending_orders": [{"order_id": "order-1"}],
            "recent_events": [],
            "latest_fill": None,
        }

        record = _cycle_log_record(
            config=config(),
            cycle_id=7,
            timestamp=timestamp,
            console_lines=["SOXL regime check", "entry_signal=False"],
            error=None,
            edgewalker_status=status,
            broker_state=broker_constraint_payload(broker_constraint_ok()),
            regime_transition=transition,
            performance=performance,
            order_state=order_state,
        )

        self.assertEqual(record["timestamp"], "2026-05-22T01:05:00Z")
        self.assertEqual(record["trading_date"], "2026-05-21")
        self.assertEqual(record["cycle_id"], 7)
        self.assertEqual(record["regime"], "UPTREND")
        self.assertEqual(record["price"], "170.42")
        self.assertEqual(record["account_value"], "50.09")
        self.assertEqual(record["broker_state"]["state"], "OK")
        self.assertEqual(record["console_lines"], ["SOXL regime check", "entry_signal=False"])
        self.assertEqual(record["regime_transition"], transition)
        self.assertEqual(record["performance"], performance)
        self.assertEqual(record["bot_performance"], performance["bot_performance"])
        self.assertEqual(record["session_realized_pl"], "5")
        self.assertEqual(record["session_trade_count"], 1)
        self.assertEqual(record["order_state"], order_state)
        self.assertEqual(record["pending_order_count"], 1)
        self.assertNotIn("api_secret_key", record["config"])
        self.assertNotIn("api_key_id", record["config"])

        with tempfile.TemporaryDirectory() as tmpdir:
            logs_root = Path(tmpdir) / "logs"
            self.assertEqual(
                _daily_log_path(timestamp, logs_root).name,
                "edgewalker-2026-05-21.jsonl",
            )

            _append_daily_jsonl(record, timestamp, logs_root)

            payload = (_daily_log_path(timestamp, logs_root)).read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(payload), 1)
            self.assertEqual(json.loads(payload[0]), record)

    def test_activity_log_filters_to_current_new_york_date(self) -> None:
        now = datetime(2026, 5, 21, 15, 0, 0, tzinfo=NY_TZ)
        entries = [
            (datetime(2026, 5, 20, 23, 59, 0, tzinfo=NY_TZ), "old"),
            (datetime(2026, 5, 21, 9, 30, 0, tzinfo=NY_TZ), "today"),
            (datetime(2026, 5, 22, 1, 0, 0, tzinfo=timezone.utc), "also today"),
        ]

        self.assertEqual(
            [line for _, line in _current_ny_activity(entries, now)],
            ["today", "also today"],
        )

    def test_regime_transition_is_detected_after_initial_regime(self) -> None:
        runner = BotRunner.__new__(BotRunner)
        runner._last_regime = None

        self.assertIsNone(runner._regime_transition_locked({"regime": "SIDEWAYS"}))
        transition = runner._regime_transition_locked(
            {"regime": "DOWNTREND", "gap_percent": "0.28"}
        )

        self.assertEqual(
            transition,
            {"from": "SIDEWAYS", "to": "DOWNTREND", "gap_percent": "0.28"},
        )
        self.assertEqual(
            _format_regime_transition(transition),
            "[REGIME] REGIME CHANGE: SIDEWAYS -> DOWNTREND gap=0.28%",
        )

    def test_lifecycle_performance_summary_calculates_realized_pl(self) -> None:
        now = datetime(2026, 5, 22, 15, 0, 0, tzinfo=NY_TZ)
        records = [
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-05-22T14:30:00+00:00",
                "symbol": "SOXL",
                "side": "buy",
                "bot": "MomentumBot",
                "order_id": "buy-1",
                "fill_delta_qty": "2",
                "filled_avg_price": "100",
            },
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-05-22T15:30:00+00:00",
                "symbol": "SOXL",
                "side": "sell",
                "bot": "MomentumBot",
                "order_id": "sell-1",
                "reason": "trailing_stop_breached",
                "fill_delta_qty": "2",
                "filled_avg_price": "103",
            },
        ]

        summary = lifecycle_performance_summary(records, now)

        self.assertEqual(summary["session_date"], "2026-05-22")
        self.assertEqual(summary["session_realized_pl"], "6")
        self.assertEqual(summary["session_trade_count"], 1)
        self.assertEqual(summary["session_wins"], 1)
        self.assertEqual(summary["session_losses"], 0)
        self.assertEqual(summary["last_trade_realized_pl"], "6")
        self.assertEqual(summary["last_trade"]["realized_pl_percent"], "3")
        self.assertEqual(summary["open_lot_qty"], "0")
        self.assertEqual(summary["unmatched_exit_qty"], "0")

    def test_lifecycle_performance_summary_handles_empty_session(self) -> None:
        now = datetime(2026, 5, 22, 15, 0, 0, tzinfo=NY_TZ)

        summary = lifecycle_performance_summary([], now)

        self.assertEqual(summary["session_realized_pl"], "0")
        self.assertEqual(summary["session_trade_count"], 0)
        self.assertEqual(summary["last_trade"], None)
        self.assertEqual(summary["open_lot_qty"], "0")

    def test_lifecycle_performance_summary_handles_partial_open_lot(self) -> None:
        now = datetime(2026, 5, 22, 15, 0, 0, tzinfo=NY_TZ)
        records = [
            {
                "event_type": LIFECYCLE_PARTIAL_FILL,
                "created_at": "2026-05-22T14:30:00+00:00",
                "symbol": "SOXL",
                "side": "buy",
                "bot": "ChopBot",
                "order_id": "buy-1",
                "fill_delta_qty": "3",
                "filled_avg_price": "10",
            },
            {
                "event_type": LIFECYCLE_PARTIAL_FILL,
                "created_at": "2026-05-22T15:30:00+00:00",
                "symbol": "SOXL",
                "side": "sell",
                "bot": "ChopBot",
                "order_id": "sell-1",
                "fill_delta_qty": "1",
                "filled_avg_price": "9",
            },
        ]

        summary = lifecycle_performance_summary(records, now)

        self.assertEqual(summary["session_realized_pl"], "-1")
        self.assertEqual(summary["session_trade_count"], 1)
        self.assertEqual(summary["session_wins"], 0)
        self.assertEqual(summary["session_losses"], 1)
        self.assertEqual(summary["open_lot_qty"], "2")
        self.assertEqual(summary["open_lot_cost_basis"], "20")

    def test_lifecycle_performance_summary_groups_realized_pl_by_bot(self) -> None:
        now = datetime(2026, 5, 22, 15, 0, 0, tzinfo=NY_TZ)
        records = [
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-05-22T14:30:00+00:00",
                "symbol": "SOXL",
                "side": "buy",
                "bot": MOMENTUM_BOT,
                "order_id": "buy-1",
                "fill_delta_qty": "1",
                "filled_avg_price": "100",
            },
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-05-22T14:40:00+00:00",
                "symbol": "SOXL",
                "side": "sell",
                "bot": MOMENTUM_BOT,
                "order_id": "sell-1",
                "fill_delta_qty": "1",
                "filled_avg_price": "105",
            },
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-05-22T15:00:00+00:00",
                "symbol": "SOXS",
                "side": "buy",
                "bot": INVERSE_BOT,
                "order_id": "buy-2",
                "fill_delta_qty": "2",
                "filled_avg_price": "10",
            },
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-05-22T15:30:00+00:00",
                "symbol": "SOXS",
                "side": "sell",
                "bot": INVERSE_BOT,
                "order_id": "sell-2",
                "fill_delta_qty": "2",
                "filled_avg_price": "9",
            },
        ]

        summary = lifecycle_performance_summary(records, now)
        by_bot = {item["bot"]: item for item in summary["bot_performance"]}

        self.assertEqual(by_bot[MOMENTUM_BOT]["realized_pl"], "5")
        self.assertEqual(by_bot[MOMENTUM_BOT]["trade_count"], 1)
        self.assertEqual(by_bot[MOMENTUM_BOT]["wins"], 1)
        self.assertEqual(by_bot[MOMENTUM_BOT]["win_rate_percent"], "100")
        self.assertEqual(by_bot[INVERSE_BOT]["realized_pl"], "-2")
        self.assertEqual(by_bot[INVERSE_BOT]["losses"], 1)
        self.assertEqual(by_bot[CHOP_BOT]["realized_pl"], "0")
        self.assertEqual(by_bot[CHOP_BOT]["trade_count"], 0)

    def test_order_visibility_summary_lists_pending_and_recent_events(self) -> None:
        now = datetime(2026, 5, 22, 15, 0, 0, tzinfo=NY_TZ)
        pending_orders = {
            "buy-1": {
                "bot": "ChopBot",
                "reason": "discount_confirmed",
                "symbol": "SOXL",
                "side": "buy",
                "last_status": "partially_filled",
                "last_filled_qty": "0.25",
                "position_lifecycle_state": POSITION_LIFECYCLE_OPENING,
                "submitted_at": "2026-05-22T14:30:00+00:00",
                "updated_at": "2026-05-22T14:31:00+00:00",
            }
        }
        records = [
            {
                "event_type": LIFECYCLE_ORDER_ACCEPTED,
                "created_at": "2026-05-22T14:30:00+00:00",
                "symbol": "SOXL",
                "side": "buy",
                "bot": "ChopBot",
                "order_id": "buy-1",
                "status": "new",
                "reason": "discount_confirmed",
                "position_lifecycle_state": POSITION_LIFECYCLE_OPENING,
            },
            {
                "event_type": LIFECYCLE_PARTIAL_FILL,
                "created_at": "2026-05-22T14:31:00+00:00",
                "symbol": "SOXL",
                "side": "buy",
                "bot": "ChopBot",
                "order_id": "buy-1",
                "status": "partially_filled",
                "fill_delta_qty": "0.25",
                "filled_qty": "0.25",
                "filled_avg_price": "99.5",
                "reason": "discount_confirmed",
                "position_lifecycle_state": POSITION_LIFECYCLE_OPENING,
            },
        ]

        summary = order_visibility_summary(records, pending_orders, now)

        self.assertEqual(
            summary["position_lifecycle_state"],
            POSITION_LIFECYCLE_OPENING,
        )
        self.assertEqual(summary["pending_count"], 1)
        self.assertEqual(summary["pending_orders"][0]["order_id"], "buy-1")
        self.assertEqual(summary["pending_orders"][0]["status"], "partially_filled")
        self.assertEqual(summary["pending_orders"][0]["filled_qty"], "0.25")
        self.assertEqual(
            summary["pending_orders"][0]["position_lifecycle_state"],
            POSITION_LIFECYCLE_OPENING,
        )
        self.assertEqual(summary["recent_events"][0]["event_type"], LIFECYCLE_PARTIAL_FILL)
        self.assertEqual(
            summary["recent_events"][0]["position_lifecycle_state"],
            POSITION_LIFECYCLE_OPENING,
        )
        self.assertEqual(summary["latest_fill"]["filled_avg_price"], "99.5")

    def test_order_visibility_summary_prefers_closing_state_for_pending_sell(self) -> None:
        now = datetime(2026, 5, 22, 15, 0, 0, tzinfo=NY_TZ)
        pending_orders = {
            "sell-1": {
                "symbol": "SOXL",
                "side": "sell",
                "last_status": "new",
                "last_filled_qty": "0",
                "position_lifecycle_state": POSITION_LIFECYCLE_CLOSING,
            },
        }

        summary = order_visibility_summary([], pending_orders, now)

        self.assertEqual(
            summary["position_lifecycle_state"],
            POSITION_LIFECYCLE_CLOSING,
        )

    def test_order_visibility_summary_uses_latest_closed_or_open_fill_state(self) -> None:
        now = datetime(2026, 5, 22, 15, 0, 0, tzinfo=NY_TZ)
        records = [
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-05-22T14:30:00+00:00",
                "symbol": "SOXL",
                "side": "buy",
                "status": "filled",
                "filled_qty": "1",
                "position_lifecycle_state": POSITION_LIFECYCLE_OPEN,
            },
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-05-22T14:40:00+00:00",
                "symbol": "SOXL",
                "side": "sell",
                "status": "filled",
                "filled_qty": "1",
                "position_lifecycle_state": POSITION_LIFECYCLE_CLOSED,
            },
        ]

        summary = order_visibility_summary(records, {}, now)

        self.assertEqual(
            summary["position_lifecycle_state"],
            POSITION_LIFECYCLE_CLOSED,
        )

    def test_summary_default_prefers_recent_market_open_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_root = Path(tmpdir) / "logs"
            logs_root.mkdir()
            (logs_root / "edgewalker-2026-05-22.jsonl").write_text(
                json.dumps(
                    {
                        "timestamp": "2026-05-22T14:30:00Z",
                        "market_open": True,
                        "regime": "UPTREND",
                        "source_price": "101",
                        "config": {"dry_run": False},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (logs_root / "edgewalker-2026-05-23.jsonl").write_text(
                json.dumps(
                    {
                        "timestamp": "2026-05-23T14:30:00Z",
                        "market_open": False,
                        "regime": "WARMUP",
                        "config": {"dry_run": False},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            self.assertEqual(
                _most_recent_log_date(logs_root=logs_root),
                "2026-05-23",
            )
            self.assertEqual(
                _most_recent_log_date(logs_root=logs_root, market_open_only=True),
                "2026-05-22",
            )
            with patch("server.LOGS_ROOT", logs_root):
                prompt = build_summary_prompt()

        self.assertEqual(prompt["date"], "2026-05-22")
        self.assertEqual(prompt["display_date"], "May 22 2026")
        self.assertIn("MARKET: OPEN", prompt["prompt"])
        self.assertIn('"tldr"', prompt["prompt"])

    def test_custom_summary_prompt_uses_inclusive_log_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_root = Path(tmpdir) / "logs"
            logs_root.mkdir()
            for day in ("2026-05-22", "2026-05-24"):
                (logs_root / f"edgewalker-{day}.jsonl").write_text(
                    json.dumps(
                        {
                            "timestamp": f"{day}T14:30:00Z",
                            "market_open": True,
                            "regime": "SIDEWAYS",
                            "source_price": "101",
                            "config": {"dry_run": False},
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

            with patch("server.LOGS_ROOT", logs_root):
                prompt = build_summary_prompt(
                    timeframe="CUSTOM",
                    start_date="2026-05-22",
                    end_date="2026-05-24",
                )

        self.assertEqual(prompt["date"], "2026-05-22 to 2026-05-24")
        self.assertEqual(prompt["display_date"], "May 22 2026 to May 24 2026")
        self.assertIn("PERIOD: 2026-05-22 to 2026-05-24 (CUSTOM)", prompt["prompt"])
        self.assertIn("2026-05-22 [PAPER LIVE]", prompt["prompt"])
        self.assertIn("2026-05-24 [PAPER LIVE]", prompt["prompt"])

    def test_session_context_uses_lifecycle_order_actions(self) -> None:
        records = [
            {
                "timestamp": "2026-05-22T14:30:00Z",
                "market_open": True,
                "regime": "UPTREND",
                "action_taken": "no_entry_signal",
                "source_price": "100",
                "config": {"dry_run": False},
            }
        ]
        lifecycle_records = [
            {
                "event_type": LIFECYCLE_ORDER_SUBMITTED,
                "created_at": "2026-05-22T14:35:00+00:00",
                "bot": MOMENTUM_BOT,
                "symbol": "SOXL",
                "side": "buy",
                "notional": "100",
                "reason": "trend_continuation_allowed",
            },
            {
                "event_type": LIFECYCLE_ORDER_SUBMITTED,
                "created_at": "2026-05-22T15:10:00+00:00",
                "bot": MOMENTUM_BOT,
                "symbol": "SOXL",
                "side": "sell",
                "qty": "1",
                "reason": "trailing_stop_breached",
            },
        ]

        context = _extract_session_context(records, "2026-05-22", lifecycle_records)
        prompt = _build_summary_prompt(context)

        self.assertEqual([trade["action"] for trade in context["trades"]], ["BUY", "SELL"])
        self.assertIn("TRADE ACTIONS — 1 entries, 1 exits:", prompt)
        self.assertIn("reason=trailing_stop_breached", prompt)

    def test_session_context_falls_back_to_cycle_exit_actions(self) -> None:
        records = [
            {
                "timestamp": "2026-05-22T14:30:00Z",
                "market_open": True,
                "regime": "UPTREND",
                "action_taken": "market_buy",
                "active_bot": MOMENTUM_BOT,
                "routed_symbol": "SOXL",
                "source_price": "100",
                "effective_position_notional": "100",
                "config": {"dry_run": False},
            },
            {
                "timestamp": "2026-05-22T15:10:00Z",
                "market_open": True,
                "regime": "SIDEWAYS",
                "action_taken": "close_stale_position_no_same_cycle_reversal",
                "position_owner": MOMENTUM_BOT,
                "position_symbol": "SOXL",
                "position_qty": "1",
                "position_current_price": "99",
                "config": {"dry_run": False},
                "console_lines": [
                    "[RISK] SOXL: stale exposure under regime=SIDEWAYS; "
                    "owner=MomentumBot active_bot=ChopBot; selling qty=1.",
                ],
            },
        ]

        context = _extract_session_context(records, "2026-05-22", [])

        self.assertEqual([trade["action"] for trade in context["trades"]], ["BUY", "SELL"])
        self.assertEqual(context["trades"][1]["bot"], MOMENTUM_BOT)

    def test_ai_origin_guard_allows_only_local_ui_origins(self) -> None:
        self.assertTrue(_is_allowed_ui_origin("http://127.0.0.1:8765"))
        self.assertTrue(_is_allowed_ui_origin("http://localhost:8765"))
        self.assertFalse(_is_allowed_ui_origin("https://example.com"))

    def test_display_date_label_formats_period_dates(self) -> None:
        self.assertEqual(_display_date_label("2026-05-22"), "May 22 2026")
        self.assertEqual(
            _display_date_label("2026-05-22 to 2026-05-24"),
            "May 22 2026 to May 24 2026",
        )

    def test_parse_narrative_response_normalizes_json(self) -> None:
        parsed = _parse_narrative_response(
            json.dumps(
                {
                    "tldr": "Brief read.",
                    "highlight": "Churn stood out.",
                    "bot_performance": {
                        "MomentumBot": "Caught uptrends.",
                        "ChopBot": "Handled ranges.",
                    },
                    "market_conditions": "Mixed.",
                    "operational_issues": "One rejection.",
                    "analysis": "Watch hysteresis before changing thresholds.",
                    "bottom_line": "Useful session.",
                }
            )
        )

        self.assertEqual(parsed["tldr"], "Brief read.")
        self.assertEqual(parsed["bot_performance"][MOMENTUM_BOT], "Caught uptrends.")
        self.assertEqual(parsed["bot_performance"][INVERSE_BOT], "")
        self.assertEqual(parsed["analysis"], "Watch hysteresis before changing thresholds.")
        self.assertEqual(parsed["bottom_line"], "Useful session.")

    def test_parse_narrative_response_preserves_plain_text_as_bottom_line(self) -> None:
        parsed = _parse_narrative_response("Plain debrief text.")

        self.assertEqual(parsed["tldr"], "")
        self.assertEqual(parsed["bottom_line"], "Plain debrief text.")

    def test_parse_narrative_response_accepts_fenced_json(self) -> None:
        parsed = _parse_narrative_response(
            '```json\n{"tldr": "Brief read.", "bottom_line": "Useful session."}\n```'
        )

        self.assertEqual(parsed["tldr"], "Brief read.")
        self.assertEqual(parsed["bottom_line"], "Useful session.")

    def test_environment_settings_round_trip_masks_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            payload = {
                "active_environment": "live",
                "data_base_url": "https://data.alpaca.markets/v2",
                "data_feed": "iex",
                "paper": {
                    "trading_base_url": "https://paper-api.alpaca.markets/v2",
                    "api_key_id": "paper-key-1234",
                    "api_secret_key": "paper-secret-5678",
                },
                "live": {
                    "trading_base_url": "https://api.alpaca.markets/v2",
                    "api_key_id": "live-key-1234",
                    "api_secret_key": "live-secret-5678",
                },
            }

            with patch("server.ENV_PATH", env_path), patch.dict(os.environ, {}, clear=True):
                settings = save_alpaca_environment_settings(payload)
                loaded = alpaca_environment_settings()
                env_text = env_path.read_text()

        self.assertEqual(settings["active_environment"], "live")
        self.assertEqual(loaded["active_environment"], "live")
        self.assertEqual(settings["paper"]["api_key_id_masked"], "********1234")
        self.assertEqual(settings["live"]["api_secret_key_masked"], "********5678")
        self.assertNotIn("paper-secret-5678", json.dumps(settings))
        self.assertIn("ALPACA_LIVE_API_KEY_ID=live-key-1234", env_text)

    def test_environment_settings_normalizes_bare_alpaca_hosts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            payload = {
                "active_environment": "live",
                "data_base_url": "https://data.alpaca.markets",
                "data_feed": "iex",
                "paper": {
                    "trading_base_url": "https://paper-api.alpaca.markets",
                    "api_key_id": "paper-key",
                    "api_secret_key": "paper-secret",
                },
                "live": {
                    "trading_base_url": "https://api.alpaca.markets",
                    "api_key_id": "live-key",
                    "api_secret_key": "live-secret",
                },
            }

            with patch("server.ENV_PATH", env_path), patch.dict(os.environ, {}, clear=True):
                settings = save_alpaca_environment_settings(payload)
                parsed = config_from_payload({})
                env_text = env_path.read_text()

        self.assertEqual(settings["data_base_url"], "https://data.alpaca.markets/v2")
        self.assertEqual(
            settings["paper"]["trading_base_url"],
            "https://paper-api.alpaca.markets/v2",
        )
        self.assertEqual(
            settings["live"]["trading_base_url"],
            "https://api.alpaca.markets/v2",
        )
        self.assertEqual(parsed.trading_base_url, "https://api.alpaca.markets/v2")
        self.assertIn("ALPACA_LIVE_TRADING_BASE_URL=https://api.alpaca.markets/v2", env_text)

    def test_live_trading_arm_and_disarm_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            payload = {
                "active_environment": "paper",
                "data_base_url": "https://data.alpaca.markets/v2",
                "data_feed": "iex",
                "live": {
                    "trading_base_url": "https://api.alpaca.markets/v2",
                    "api_key_id": "live-key-1234",
                    "api_secret_key": "live-secret-5678",
                },
            }

            with patch("server.ENV_PATH", env_path), patch.dict(os.environ, {}, clear=True):
                save_alpaca_environment_settings(payload)
                armed = set_live_trading_armed("LIVE")
                disarmed = set_live_trading_disarmed()

        self.assertTrue(armed["live_trading_armed"])
        self.assertFalse(disarmed["live_trading_armed"])

    def test_live_trading_arm_requires_live_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            with patch("server.ENV_PATH", env_path), patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(BotError):
                    set_live_trading_armed("LIVE")

    def test_live_trading_armed_is_ignored_without_live_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("LIVE_TRADING_ARMED=true\n", encoding="utf-8")
            with patch("server.ENV_PATH", env_path), patch.dict(os.environ, {}, clear=True):
                settings = alpaca_environment_settings()

        self.assertFalse(settings["live_trading_armed"])

    def test_config_payload_blocks_unarmed_live_orders(self) -> None:
        payload = {"dryRun": False}
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            with patch("server.ENV_PATH", env_path), patch.dict(
                os.environ,
                {
                    "ALPACA_ENVIRONMENT": "live",
                    "ALPACA_LIVE_API_KEY_ID": "key",
                    "ALPACA_LIVE_API_SECRET_KEY": "secret",
                    "LIVE_TRADING_ARMED": "false",
                },
                clear=True,
            ):
                with self.assertRaises(BotError):
                    config_from_payload(payload)

    def test_runner_initial_config_falls_back_to_paper_when_live_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            with patch("server.ENV_PATH", env_path), patch.dict(
                os.environ,
                {
                    "ALPACA_ENVIRONMENT": "live",
                    "ALPACA_PAPER_API_KEY_ID": "paper-key",
                    "ALPACA_PAPER_API_SECRET_KEY": "paper-secret",
                },
                clear=True,
            ):
                config_value, error = BotRunner.__new__(BotRunner)._initial_config()
                environment_after = os.environ.get("ALPACA_ENVIRONMENT")

        self.assertEqual(config_value.api_key_id, "paper-key")
        self.assertIn("Live environment incomplete", error or "")
        self.assertEqual(environment_after, "live")

    def test_connection_config_environment_override_does_not_mutate_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            with patch("server.ENV_PATH", env_path), patch.dict(
                os.environ,
                {
                    "ALPACA_ENVIRONMENT": "paper",
                    "ALPACA_PAPER_API_KEY_ID": "paper-key",
                    "ALPACA_PAPER_API_SECRET_KEY": "paper-secret",
                    "ALPACA_LIVE_API_KEY_ID": "live-key",
                    "ALPACA_LIVE_API_SECRET_KEY": "live-secret",
                },
                clear=True,
            ):
                config_value = _config_for_alpaca_environment("live")
                environment_after = os.environ.get("ALPACA_ENVIRONMENT")

        self.assertEqual(config_value.api_key_id, "live-key")
        self.assertTrue(config_value.dry_run)
        self.assertEqual(environment_after, "paper")

    def test_runner_arms_until_market_open_when_market_is_closed(self) -> None:
        runner = BotRunner.__new__(BotRunner)
        stop_event = threading.Event()
        runner._config = config()
        runner._lock = threading.Lock()
        runner._stop_event = stop_event
        runner._running = True
        runner._next_run_at = "2026-05-21T20:01:00"
        runner._next_run_reason = "poll"
        runner._market_idle_logged_for = "old"
        runner._last_stopped_at = None
        runner._last_output = ["previous"]
        runner._activity_log = []
        runner._save_activity_log = lambda: None
        fast_config = replace(config(), poll_seconds=0)

        runner._arm_until_market_open(
            fast_config,
            stop_event,
            datetime(2026, 5, 22, 13, 30, 0, tzinfo=timezone.utc),
        )

        self.assertFalse(stop_event.is_set())
        self.assertTrue(runner._running)
        self.assertEqual(runner._next_run_at, "2026-05-22T13:30:00+00:00")
        self.assertEqual(runner._next_run_reason, "market_open")
        self.assertEqual(runner._market_idle_logged_for, runner._next_run_at)
        self.assertIsNone(runner._last_stopped_at)
        self.assertEqual(
            runner._last_output[0],
            "Market closed. EdgeWalker armed; "
            "next market open at 2026-05-22T13:30:00+00:00.",
        )
        self.assertEqual(
            [line for _, line in runner._activity_log],
            [runner._last_output[0]],
        )

    def test_config_payload_accepts_directional_controls(self) -> None:
        payload = {
            "directionalMode": "aggressive",
            "directionalMaxExtensionPercent": "0.75",
            "directionalStrongChaseMaxExtensionPercent": "1.25",
            "directionalMinStrength": "strong",
            "directionalCooldownMinutes": "3",
        }

        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY_ID": "key",
                "ALPACA_API_SECRET_KEY": "secret",
            },
            clear=True,
        ):
            parsed = config_from_payload(payload)

        self.assertEqual(parsed.directional_mode, "AGGRESSIVE")
        self.assertEqual(parsed.directional_max_extension_percent, Decimal("0.75"))
        self.assertEqual(
            parsed.directional_strong_chase_max_extension_percent,
            Decimal("1.25"),
        )
        self.assertEqual(parsed.directional_min_strength, "STRONG")
        self.assertEqual(parsed.directional_cooldown_minutes, 3)

    def test_config_payload_accepts_dynamic_sizing_and_hysteresis(self) -> None:
        payload = {
            "positionSizingMode": "dynamic",
            "positionAllocationPercent": "95",
            "regimeExitGapThreshold": "0.10",
        }

        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY_ID": "key",
                "ALPACA_API_SECRET_KEY": "secret",
            },
            clear=True,
        ):
            parsed = config_from_payload(payload)

        self.assertEqual(parsed.position_sizing_mode, "DYNAMIC")
        self.assertEqual(parsed.position_allocation_percent, Decimal("95"))
        self.assertEqual(parsed.regime_exit_gap_threshold, Decimal("0.10"))

    def test_config_payload_keeps_legacy_momentum_aliases(self) -> None:
        payload = {
            "momentumMode": "balanced",
            "momentumMaxExtensionPercent": "0.65",
            "momentumStrongChaseMaxExtensionPercent": "1.10",
            "momentumMinStrength": "weak",
            "momentumCooldownMinutes": "2",
        }

        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY_ID": "key",
                "ALPACA_API_SECRET_KEY": "secret",
            },
            clear=True,
        ):
            parsed = config_from_payload(payload)

        self.assertEqual(parsed.directional_mode, "BALANCED")
        self.assertEqual(parsed.directional_max_extension_percent, Decimal("0.65"))
        self.assertEqual(
            parsed.directional_strong_chase_max_extension_percent,
            Decimal("1.10"),
        )
        self.assertEqual(parsed.directional_min_strength, "WEAK")
        self.assertEqual(parsed.directional_cooldown_minutes, 2)


if __name__ == "__main__":
    unittest.main()
