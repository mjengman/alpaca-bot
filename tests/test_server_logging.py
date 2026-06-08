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
    LIFECYCLE_POSITION_MANAGED,
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
    _ground_narrative_sections,
    _is_allowed_ui_origin,
    _most_recent_log_date,
    _parse_narrative_response,
    _research_compare_date_summary,
    _research_compare_preset_summaries,
    _research_fingerprint,
    _research_specialist_audit,
    _runtime_source_price_path,
    _shadow_router_allows_persistence_override,
    _shadow_router_authority_decision,
    _shadow_router_authority_summary,
    _shadow_router_checkpoint_summaries,
    _shadow_router_decision,
    _shadow_router_persist_decision,
    _shadow_router_pick,
    alpaca_environment_settings,
    build_operator_spreadsheet_daily_row,
    build_summary_prompt,
    config_from_payload,
    generate_session_summary,
    lifecycle_performance_summary,
    OPERATOR_SPREADSHEET_COLUMNS,
    order_visibility_summary,
    save_alpaca_environment_settings,
    set_live_trading_armed,
    set_live_trading_disarmed,
)
from research import _session_metrics
from trade_metrics import enrich_trades_with_bar_extremes
from trade_metrics import bot_archaeology_report


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
            "reconciliation_confidence": "HIGH",
            "reconciliation_notes": ["all_fills_matched"],
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
        self.assertEqual(record["pl_reconciliation_confidence"], "HIGH")
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
                "event_type": LIFECYCLE_POSITION_MANAGED,
                "created_at": "2026-05-22T14:45:00+00:00",
                "symbol": "SOXL",
                "qty": "2",
                "current_price": "104",
                "avg_entry_price": "100",
            },
            {
                "event_type": LIFECYCLE_POSITION_MANAGED,
                "created_at": "2026-05-22T15:00:00+00:00",
                "symbol": "SOXL",
                "qty": "2",
                "current_price": "98",
                "avg_entry_price": "100",
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
        self.assertEqual(summary["last_trade"]["mfe_pl"], "8")
        self.assertEqual(summary["last_trade"]["mae_pl"], "-4")
        self.assertEqual(summary["last_trade"]["mfe_percent"], "4")
        self.assertEqual(summary["last_trade"]["mae_percent"], "-2")
        self.assertEqual(summary["last_trade"]["capture_ratio_percent"], "75")
        self.assertEqual(summary["last_trade"]["hold_seconds"], 3600.0)
        self.assertEqual(summary["last_trade"]["mfe_mae_source"], "managed_mark")
        self.assertEqual(summary["trade_quality"]["avg_mfe_percent"], "4")
        self.assertEqual(summary["trade_quality"]["avg_capture_ratio_percent"], "75")
        self.assertEqual(summary["reconciliation_confidence"], "HIGH")
        self.assertEqual(summary["reconciliation_notes"], ["all_fills_matched"])
        self.assertEqual(summary["open_lot_qty"], "0")
        self.assertEqual(summary["unmatched_exit_qty"], "0")

    def test_lifecycle_performance_summary_handles_empty_session(self) -> None:
        now = datetime(2026, 5, 22, 15, 0, 0, tzinfo=NY_TZ)

        summary = lifecycle_performance_summary([], now)

        self.assertEqual(summary["session_realized_pl"], "0")
        self.assertEqual(summary["session_trade_count"], 0)
        self.assertEqual(summary["last_trade"], None)
        self.assertEqual(summary["reconciliation_confidence"], "HIGH")
        self.assertEqual(summary["open_lot_qty"], "0")

    def test_research_bar_excursion_ignores_bars_after_exit(self) -> None:
        trades = [
            {
                "symbol": "SOXS",
                "qty": "10",
                "avg_entry_price": "10",
                "exit_price": "9.50",
                "realized_pl": "-5",
                "opened_at": "2026-06-05T14:00:00+00:00",
                "closed_at": "2026-06-05T14:02:00+00:00",
            }
        ]
        bars_by_symbol = {
            "SOXS": [
                {
                    "t": "2026-06-05T14:00:00Z",
                    "h": "11",
                    "l": "9.8",
                },
                {
                    "t": "2026-06-05T14:01:00Z",
                    "h": "10.5",
                    "l": "9.4",
                },
                {
                    "t": "2026-06-05T14:02:00Z",
                    "h": "30",
                    "l": "1",
                },
            ]
        }

        enriched = enrich_trades_with_bar_extremes(trades, bars_by_symbol)

        self.assertEqual(enriched[0]["mfe_price"], "11")
        self.assertEqual(enriched[0]["mae_price"], "9.4")
        self.assertEqual(enriched[0]["mfe_pl"], "10")
        self.assertEqual(enriched[0]["mae_pl"], "-6")
        self.assertEqual(enriched[0]["capture_ratio_percent"], "-50")
        self.assertEqual(
            enriched[0]["mfe_mae_source"],
            "research_completed_bar_high_low",
        )

    def test_research_fingerprint_summarizes_full_and_early_windows(self) -> None:
        records = []
        for minute in range(60):
            if minute < 10:
                regime = "WARMUP"
            elif minute < 30:
                regime = "UPTREND"
            else:
                regime = "DOWNTREND"
            records.append(
                {
                    "timestamp": f"2026-06-05T14:{minute:02d}:00Z",
                    "regime": regime,
                    "regime_transition": (
                        {"from": "WARMUP", "to": "UPTREND"}
                        if minute == 10
                        else {"from": "UPTREND", "to": "DOWNTREND"}
                        if minute == 30
                        else None
                    ),
                    "trend_trust": {"score": "50"},
                    "source_price": str(100 + minute),
                    "source_bar_open": str(100 + minute),
                    "source_bar_high": str(101 + minute),
                    "source_bar_low": str(99 + minute),
                    "source_bar_close": str(100.5 + minute),
                    "inverse_price": str(50 - minute / 10),
                    "inverse_bar_open": str(50 - minute / 10),
                    "inverse_bar_high": str(50.1 - minute / 10),
                    "inverse_bar_low": str(49.8 - minute / 10),
                    "inverse_bar_close": str(49.9 - minute / 10),
                }
            )
        trades = [
            {
                "closed_at": "2026-06-05T14:20:00Z",
                "realized_pl": "1",
                "exit_reason": "route_invalidated_exit",
                "mfe_percent": "2",
                "mae_percent": "-0.5",
                "capture_ratio_percent": "50",
                "hold_seconds": "600",
            },
            {
                "closed_at": "2026-06-05T14:50:00Z",
                "realized_pl": "-2",
                "exit_reason": "trailing_stop_breached",
                "mfe_percent": "1",
                "mae_percent": "-1",
                "capture_ratio_percent": "-200",
                "hold_seconds": "300",
            },
        ]

        full = _research_fingerprint(records, trades)
        early = _research_fingerprint(records, trades, window_minutes=30)

        self.assertEqual(full["cycles"], 60)
        self.assertEqual(full["regime_transitions"], 2)
        self.assertEqual(full["transitions_per_hour"], 2)
        self.assertEqual(full["avg_regime_duration_minutes"], 25)
        self.assertEqual(full["closed_trades"], 2)
        self.assertEqual(full["route_invalidation_rate"], 50)
        self.assertEqual(full["trailing_stop_rate"], 50)
        self.assertEqual(full["avg_mfe_percent"], 1.5)
        self.assertEqual(full["source_open_to_current_percent"], 59.5)
        self.assertEqual(full["source_max_drawdown_from_open_percent"], -1)
        self.assertEqual(full["source_max_runup_from_open_percent"], 60)
        self.assertEqual(full["inverse_open_to_current_percent"], -12)
        self.assertEqual(full["inverse_max_drawdown_from_open_percent"], -12.2)
        self.assertEqual(full["current_regime"], "DOWNTREND")
        self.assertEqual(full["uptrend_minutes"], 20)
        self.assertEqual(full["downtrend_minutes"], 30)
        self.assertEqual(early["cycles"], 30)
        self.assertEqual(early["closed_trades"], 1)
        self.assertEqual(early["route_invalidation_rate"], 100)

    def test_research_comparison_reports_winner_margin_and_wrong_cost(self) -> None:
        def result(name: str, realized_pl: str, change_percent: str) -> dict[str, object]:
            return {
                "date": "2026-06-05",
                "preset_id": f"{name}::v1",
                "preset_name": name,
                "preset_version": "v1",
                "row": {
                    "realized_pl_dollars": realized_pl,
                    "account_change_percent": change_percent,
                },
                "fingerprint": {"transitions_per_hour": 12},
                "early_windows": {"30": {}, "60": {}},
            }

        rows = [
            result("Lead_Generalist", "-2", "-0.57"),
            result("Lead_Inverse_Specialist", "3", "0.86"),
            result("Lead_Momentum_Specialist", "1", "0.29"),
        ]

        summary = _research_compare_date_summary("2026-06-05", rows)
        preset_summaries = _research_compare_preset_summaries(rows, [summary])

        self.assertEqual(summary["winner"], "Lead_Inverse_Specialist")
        self.assertEqual(summary["runner_up"], "Lead_Momentum_Specialist")
        self.assertEqual(summary["margin_dollars"], 2.0)
        self.assertEqual(summary["margin_percent"], 0.57)
        self.assertEqual(summary["winner_confidence"], "MODERATE")
        self.assertEqual(summary["worst_misclassification_cost_dollars"], 5.0)
        self.assertEqual(summary["misclassification_costs"][0]["preset_name"], "Lead_Momentum_Specialist")
        self.assertEqual(preset_summaries[0]["preset_name"], "Lead_Inverse_Specialist")
        self.assertEqual(preset_summaries[0]["date_wins"], 1)

    def test_research_specialist_audit_scores_target_purity_and_home_turf_capture(self) -> None:
        def result(
            date: str,
            total_pl: str,
            momentum_pl: str,
            chop_pl: str,
            inverse_pl: str,
            runup: str,
            momentum_trades: int,
            closed_trades: int,
        ) -> dict[str, object]:
            return {
                "date": date,
                "preset_id": "Lead_Momentum_Specialist::v1",
                "preset_name": "Lead_Momentum_Specialist",
                "preset_version": "v1",
                "row": {
                    "realized_pl_dollars": total_pl,
                    "starting_account_value": "100",
                    "position_sizing_mode": "DYNAMIC",
                    "position_allocation_percent": "25",
                    "position_notional": "25",
                    "closed_trades": closed_trades,
                    "momentum_pl": momentum_pl,
                    "chop_pl": chop_pl,
                    "inverse_pl": inverse_pl,
                },
                "bot_performance": [
                    {"bot": MOMENTUM_BOT, "trade_count": momentum_trades},
                    {"bot": CHOP_BOT, "trade_count": 0},
                    {"bot": INVERSE_BOT, "trade_count": 0},
                ],
                "fingerprint": {
                    "source_max_runup_from_open_percent": runup,
                    "inverse_max_runup_from_open_percent": "0",
                },
            }

        audit = _research_specialist_audit(
            [
                result("2026-06-01", "2", "1.5", "0.2", "0.3", "10", 2, 3),
                result("2026-06-02", "1", "1", "-0.1", "0.1", "8", 1, 2),
                result("2026-06-03", "-0.5", "-0.2", "0", "-0.3", "1", 0, 1),
            ]
        )

        row = audit[0]

        self.assertEqual(row["preset_name"], "Lead_Momentum_Specialist")
        self.assertEqual(row["target_bot"], MOMENTUM_BOT)
        self.assertEqual(row["total_pl"], 2.5)
        self.assertEqual(row["target_bot_pl"], 2.3)
        self.assertEqual(row["non_target_damage"], 0.4)
        self.assertEqual(row["target_purity_percent"], 62.16)
        self.assertEqual(row["target_trade_share_percent"], 50.0)
        self.assertEqual(row["home_turf_capture_efficiency_percent"], 48.42)
        self.assertEqual(row["home_turf_missed_opportunity"], 2.45)
        self.assertEqual(row["home_turf_target_share_percent"], 92.0)
        self.assertEqual(row["diagnosis"], "SPECIALIST_CONFIRMED")

    def test_research_specialist_audit_does_not_confirm_negative_target_engine(self) -> None:
        def result(
            date: str,
            total_pl: str,
            momentum_pl: str,
            chop_pl: str,
            inverse_pl: str,
            runup: str,
        ) -> dict[str, object]:
            return {
                "date": date,
                "preset_id": "Lead_Momentum_Specialist::v1",
                "preset_name": "Lead_Momentum_Specialist",
                "preset_version": "v1",
                "row": {
                    "realized_pl_dollars": total_pl,
                    "starting_account_value": "100",
                    "position_sizing_mode": "DYNAMIC",
                    "position_allocation_percent": "25",
                    "position_notional": "25",
                    "closed_trades": 3,
                    "momentum_pl": momentum_pl,
                    "chop_pl": chop_pl,
                    "inverse_pl": inverse_pl,
                },
                "bot_performance": [
                    {"bot": MOMENTUM_BOT, "trade_count": 1},
                    {"bot": CHOP_BOT, "trade_count": 1},
                    {"bot": INVERSE_BOT, "trade_count": 1},
                ],
                "fingerprint": {
                    "source_max_runup_from_open_percent": runup,
                    "inverse_max_runup_from_open_percent": "0",
                },
            }

        audit = _research_specialist_audit(
            [
                result("2026-03-09", "1.59", "1.59", "0", "0", "70"),
                result("2026-03-10", "0.69", "0.63", "0.06", "0", "55"),
                result("2026-03-02", "-0.96", "-0.72", "-0.24", "0", "45"),
                result("2026-03-19", "-0.35", "-0.48", "0.13", "0", "60"),
                result("2026-03-06", "0.14", "0.19", "-0.05", "0", "40"),
                result("2026-03-11", "-3.00", "-3.00", "0", "0", "1"),
            ]
        )

        row = audit[0]

        self.assertLess(row["target_bot_pl"], 0)
        self.assertLess(row["home_turf_capture_efficiency_percent"], 10)
        self.assertEqual(row["diagnosis"], "WEAK_TARGET_ENGINE")

    def test_shadow_router_pick_uses_transparent_fingerprint_rules(self) -> None:
        momentum = _shadow_router_pick(
            {
                "transitions_per_hour": 2.5,
                "avg_regime_duration_minutes": 20,
                "trend_trust_avg": 55,
                "source_open_to_current_percent": 3.2,
                "source_max_drawdown_from_open_percent": -0.5,
                "source_max_runup_from_open_percent": 2.2,
                "current_regime": "UPTREND",
            }
        )
        inverse = _shadow_router_pick(
            {
                "transitions_per_hour": 6,
                "avg_regime_duration_minutes": 10,
                "trend_trust_avg": 40,
                "source_open_to_current_percent": -3.2,
                "source_max_drawdown_from_open_percent": -3,
                "current_regime": "DOWNTREND",
            }
        )
        generalist = _shadow_router_pick(
            {
                "transitions_per_hour": 6,
                "avg_regime_duration_minutes": 9,
                "trend_trust_avg": 55,
                "source_open_to_current_percent": 0.2,
                "source_max_drawdown_from_open_percent": -0.5,
                "current_regime": "SIDEWAYS",
            }
        )
        early_momentum = _shadow_router_pick(
            {
                "transitions_per_hour": 0,
                "avg_regime_duration_minutes": 15,
                "source_open_to_current_percent": 3,
                "source_max_drawdown_from_open_percent": -0.5,
                "source_max_runup_from_open_percent": 3.2,
                "current_regime": "WARMUP",
            }
        )
        shallow_early_selloff = _shadow_router_pick(
            {
                "transitions_per_hour": 0,
                "avg_regime_duration_minutes": 15,
                "source_open_to_current_percent": -2.8,
                "source_max_drawdown_from_open_percent": -3,
                "current_regime": "WARMUP",
            }
        )
        rebound_momentum = _shadow_router_pick(
            {
                "transitions_per_hour": 2,
                "avg_regime_duration_minutes": 19.5,
                "trend_trust_avg": 66,
                "source_open_to_current_percent": 2.6,
                "source_max_drawdown_from_open_percent": -5.4,
                "source_max_runup_from_open_percent": 2.8,
                "current_regime": "UPTREND",
            }
        )

        self.assertEqual(momentum["role"], "momentum")
        self.assertEqual(momentum["confidence"], "HIGH")
        self.assertEqual(inverse["role"], "inverse")
        self.assertEqual(inverse["confidence"], "HIGH")
        self.assertEqual(generalist["role"], "generalist")
        self.assertEqual(early_momentum["role"], "momentum")
        self.assertEqual(shallow_early_selloff["role"], "generalist")
        self.assertEqual(rebound_momentum["role"], "momentum")

    def test_shadow_router_decision_scores_against_eventual_winner(self) -> None:
        role_presets = {
            "generalist": {
                "id": "Lead_Generalist::v1",
                "name": "Lead_Generalist",
                "version": "v1",
            },
            "momentum": {
                "id": "Lead_Momentum_Specialist::v1",
                "name": "Lead_Momentum_Specialist",
                "version": "v1",
            },
            "inverse": {
                "id": "Lead_Inverse_Specialist::v1",
                "name": "Lead_Inverse_Specialist",
                "version": "v1",
            },
        }
        observer = {
            "date": "2026-06-05",
            "preset_id": "Lead_Generalist::v1",
            "preset_name": "Lead_Generalist",
            "preset_version": "v1",
            "early_windows": {
                "60": {
                    "transitions_per_hour": 6,
                    "avg_regime_duration_minutes": 10,
                    "trend_trust_avg": 40,
                    "source_open_to_current_percent": -2,
                    "source_max_drawdown_from_open_percent": -3,
                    "current_regime": "DOWNTREND",
                }
            },
            "checkpoint_trade_windows": {
                "60": {
                    "pre_pl": "1",
                    "post_pl": "-3",
                    "post_trade_count": 2,
                }
            },
        }
        results = [
            {
                "date": "2026-06-05",
                "preset_id": "Lead_Generalist::v1",
                "preset_name": "Lead_Generalist",
                "row": {
                    "realized_pl_dollars": "-2",
                    "account_change_percent": "-2",
                },
                "checkpoint_trade_windows": {
                    "60": {
                        "pre_pl": "1",
                        "post_pl": "-3",
                        "post_trade_count": 2,
                    }
                },
            },
            {
                "date": "2026-06-05",
                "preset_id": "Lead_Inverse_Specialist::v1",
                "preset_name": "Lead_Inverse_Specialist",
                "row": {
                    "realized_pl_dollars": "3",
                    "account_change_percent": "3",
                },
                "checkpoint_trade_windows": {
                    "60": {
                        "pre_pl": "-1",
                        "post_pl": "4",
                        "post_trade_count": 3,
                    }
                },
            },
        ]
        date_summary = {
            "date": "2026-06-05",
            "winner": "Lead_Inverse_Specialist",
            "winner_version": "v1",
            "winner_pl": 3,
            "winner_account_change_percent": 3,
            "winner_confidence": "HIGH",
        }

        decision = _shadow_router_decision(
            date_summary=date_summary,
            checkpoint={"label": "10:30", "window_minutes": 60},
            observer_result=observer,
            role_presets=role_presets,
            results=results,
        )
        summary = _shadow_router_checkpoint_summaries([decision])[2]

        self.assertEqual(decision["selected_preset"], "Lead_Inverse_Specialist")
        self.assertTrue(decision["correct"])
        self.assertEqual(decision["cost_dollars"], 0.0)
        self.assertTrue(decision["switch_correct"])
        self.assertEqual(decision["generalist_pre_pl"], 1.0)
        self.assertEqual(decision["selected_post_pl"], 4.0)
        self.assertEqual(decision["switch_pl"], 5.0)
        self.assertEqual(decision["switch_delta_vs_generalist"], 7.0)
        self.assertEqual(summary["checkpoint"], "10:30")
        self.assertEqual(summary["accuracy_percent"], 100)
        self.assertEqual(summary["switch_accuracy_percent"], 100)
        self.assertEqual(summary["selected_total_pl"], 3.0)
        self.assertEqual(summary["switch_total_pl"], 5.0)
        self.assertEqual(summary["switch_delta_vs_generalist_total"], 7.0)

    def test_shadow_router_persists_high_confidence_early_specialist(self) -> None:
        role_presets = {
            "generalist": {
                "id": "Lead_Generalist::v1",
                "name": "Lead_Generalist",
                "version": "v1",
            },
            "momentum": {
                "id": "Lead_Momentum_Specialist::v1",
                "name": "Lead_Momentum_Specialist",
                "version": "v1",
            },
            "inverse": {
                "id": "Lead_Inverse_Specialist::v1",
                "name": "Lead_Inverse_Specialist",
                "version": "v1",
            },
        }
        persisted = {
            "date": "2026-05-19",
            "selected_role": "momentum",
            "selected_preset": "Lead_Momentum_Specialist",
            "router_confidence": "HIGH",
        }
        current = {
            "date": "2026-05-19",
            "selected_role": "generalist",
            "selected_preset": "Lead_Generalist",
            "selected_version": "v1",
            "router_confidence": "LOW",
            "winner": "Lead_Momentum_Specialist",
            "winner_version": "v1",
            "winner_pl": 2,
            "winner_account_change_percent": 2,
            "reasons": ["No specialist threshold cleared."],
        }
        results = [
            {
                "date": "2026-05-19",
                "preset_id": "Lead_Generalist::v1",
                "row": {
                    "realized_pl_dollars": "0",
                    "account_change_percent": "0",
                },
            },
            {
                "date": "2026-05-19",
                "preset_id": "Lead_Momentum_Specialist::v1",
                "row": {
                    "realized_pl_dollars": "2",
                    "account_change_percent": "2",
                },
            },
        ]

        self.assertFalse(
            _shadow_router_allows_persistence_override(persisted, current)
        )
        persisted_current = _shadow_router_persist_decision(
            current_decision=current,
            persisted_decision=persisted,
            role_presets=role_presets,
            results=results,
        )

        self.assertEqual(
            persisted_current["selected_preset"],
            "Lead_Momentum_Specialist",
        )
        self.assertTrue(persisted_current["correct"])
        self.assertEqual(persisted_current["cost_dollars"], 0.0)
        self.assertTrue(persisted_current["persistence_applied"])

    def test_shadow_router_v6_authority_gates_early_inverse(self) -> None:
        role_presets = {
            "generalist": {
                "id": "Lead_Generalist::v1",
                "name": "Lead_Generalist",
                "version": "v1",
            },
            "momentum": {
                "id": "Lead_Momentum_Specialist::v1",
                "name": "Lead_Momentum_Specialist",
                "version": "v1",
            },
            "inverse": {
                "id": "Lead_Inverse_Specialist::v1",
                "name": "Lead_Inverse_Specialist",
                "version": "v1",
            },
        }
        observer = {
            "date": "2026-06-05",
            "preset_id": "Lead_Generalist::v1",
            "preset_name": "Lead_Generalist",
            "checkpoint_trade_windows": {
                "15": {"pre_pl": "0", "post_pl": "-2", "post_trade_count": 1}
            },
        }
        results = [
            observer,
            {
                "date": "2026-06-05",
                "preset_id": "Lead_Inverse_Specialist::v1",
                "preset_name": "Lead_Inverse_Specialist",
                "checkpoint_trade_windows": {
                    "15": {"pre_pl": "0", "post_pl": "1", "post_trade_count": 1}
                },
            },
        ]
        base_decision = {
            "date": "2026-06-05",
            "checkpoint": "09:45",
            "window_minutes": 15,
            "selected_role": "inverse",
            "selected_preset": "Lead_Inverse_Specialist",
            "router_confidence": "HIGH",
            "generalist_pre_pl": 0,
            "generalist_post_pl": -2,
            "generalist_checkpoint_pl": -2,
            "checkpoint_best_preset": "Lead_Inverse_Specialist",
            "checkpoint_best_preset_id": "Lead_Inverse_Specialist::v1",
            "checkpoint_best_switch_pl": 1,
            "fingerprint": {
                "source_open_to_current_percent": -4.5,
                "source_max_drawdown_from_open_percent": -4.5,
                "transitions_per_hour": 0,
                "current_regime": "WARMUP",
            },
        }

        routed = {
            **base_decision,
            **_shadow_router_authority_decision(
                decision=base_decision,
                observer_result=observer,
                role_presets=role_presets,
                results=results,
            ),
        }
        blocked_decision = {
            **base_decision,
            "date": "2026-05-18",
            "fingerprint": {
                **base_decision["fingerprint"],
                "source_open_to_current_percent": -8,
                "source_max_drawdown_from_open_percent": -8,
            },
        }
        blocked = {
            **blocked_decision,
            **_shadow_router_authority_decision(
                decision=blocked_decision,
                observer_result=observer,
                role_presets=role_presets,
                results=results,
            ),
        }
        flush_rebound_decision = {
            **base_decision,
            "date": "2026-03-30",
            "fingerprint": {
                **base_decision["fingerprint"],
                "source_open_to_current_percent": -4.86,
                "source_max_drawdown_from_open_percent": -6.6,
            },
        }
        flush_rebound_blocked = {
            **flush_rebound_decision,
            **_shadow_router_authority_decision(
                decision=flush_rebound_decision,
                observer_result=observer,
                role_presets=role_presets,
                results=results,
            ),
        }
        summary = _shadow_router_authority_summary(
            [routed, blocked, flush_rebound_blocked]
        )

        self.assertEqual(routed["authority_action"], "ROUTE")
        self.assertEqual(
            routed["authority_model"],
            "v6_0945_high_confidence_with_rebound_block",
        )
        self.assertEqual(routed["authority_preset"], "Lead_Inverse_Specialist")
        self.assertEqual(routed["authority_pl"], 1.0)
        self.assertEqual(blocked["authority_action"], "BLOCKED_REVIEW")
        self.assertEqual(blocked["authority_preset"], "Lead_Generalist")
        self.assertEqual(flush_rebound_blocked["authority_action"], "BLOCKED_REVIEW")
        self.assertEqual(
            flush_rebound_blocked["authority_preset"],
            "Lead_Generalist",
        )
        self.assertIn("bounced materially", flush_rebound_blocked["authority_reason"])
        self.assertEqual(summary["routes"], 1)
        self.assertEqual(summary["blocked"], 2)

    def test_runtime_source_price_path_tracks_flush_rebound(self) -> None:
        path = _runtime_source_price_path(
            [
                {"o": 100, "h": 101, "l": 96, "c": 97},
                {"o": 97, "h": 98, "l": 93.4, "c": 95.14},
            ]
        )

        self.assertEqual(path["source_open_to_current_percent"], -4.86)
        self.assertEqual(path["source_max_drawdown_from_open_percent"], -6.6)
        self.assertEqual(path["source_max_runup_from_open_percent"], 1.0)

    def test_inversebot_archaeology_returns_ranked_hypotheses(self) -> None:
        report = bot_archaeology_report(
            [
                {
                    "bot": INVERSE_BOT,
                    "realized_pl": "-5",
                    "exit_reason": "trailing_stop_breached",
                    "mfe_percent": "10",
                    "mae_percent": "-1",
                    "capture_ratio_percent": "-50",
                    "hold_seconds": "120",
                },
                {
                    "bot": INVERSE_BOT,
                    "realized_pl": "-2",
                    "exit_reason": "route_invalidated_exit",
                    "mfe_percent": "0",
                    "mae_percent": "-3",
                    "capture_ratio_percent": None,
                    "hold_seconds": "60",
                },
            ],
            INVERSE_BOT,
        )

        self.assertEqual(report["bot"], INVERSE_BOT)
        self.assertEqual(report["trade_count"], 2)
        self.assertEqual(report["near_zero_mfe_count"], 1)
        self.assertEqual(report["meaningful_mfe_low_capture_count"], 1)
        self.assertIn("trailing_stop_breached", report["exit_reasons"])
        self.assertIn("hypothesis", report["hypotheses"][0])
        self.assertNotIn("change", report["hypotheses"][0]["hypothesis"].lower())

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
        self.assertEqual(summary["reconciliation_confidence"], "MEDIUM")
        self.assertEqual(summary["reconciliation_notes"], ["open_lot_qty=2"])

    def test_lifecycle_performance_summary_marks_unmatched_exit_low_confidence(self) -> None:
        now = datetime(2026, 5, 22, 15, 0, 0, tzinfo=NY_TZ)
        records = [
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-05-22T15:30:00+00:00",
                "symbol": "SOXL",
                "side": "sell",
                "order_id": "sell-1",
                "fill_delta_qty": "1",
                "filled_avg_price": "9",
            },
        ]

        summary = lifecycle_performance_summary(records, now)

        self.assertEqual(summary["session_realized_pl"], "0")
        self.assertEqual(summary["session_trade_count"], 0)
        self.assertEqual(summary["unmatched_exit_qty"], "1")
        self.assertEqual(summary["reconciliation_confidence"], "LOW")
        self.assertEqual(summary["reconciliation_notes"], ["unmatched_exit_qty=1"])

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
        self.assertEqual(by_bot[MOMENTUM_BOT]["avg_capture_ratio_percent"], "100")
        self.assertEqual(by_bot[MOMENTUM_BOT]["avg_hold_seconds"], "600")
        self.assertEqual(by_bot[INVERSE_BOT]["realized_pl"], "-2")
        self.assertEqual(by_bot[INVERSE_BOT]["losses"], 1)
        self.assertEqual(by_bot[CHOP_BOT]["realized_pl"], "0")
        self.assertEqual(by_bot[CHOP_BOT]["trade_count"], 0)

    def test_operator_spreadsheet_daily_row_builds_exit_reason_columns(self) -> None:
        lifecycle_records = [
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-06-01T13:40:00+00:00",
                "symbol": "SOXL",
                "side": "buy",
                "bot": MOMENTUM_BOT,
                "order_id": "buy-1",
                "fill_delta_qty": "10",
                "filled_avg_price": "100",
            },
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-06-01T14:10:00+00:00",
                "symbol": "SOXL",
                "side": "sell",
                "bot": MOMENTUM_BOT,
                "order_id": "sell-1",
                "fill_delta_qty": "10",
                "filled_avg_price": "110",
                "reason": "route_invalidated_exit",
            },
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-06-01T15:00:00+00:00",
                "symbol": "SOXS",
                "side": "buy",
                "bot": INVERSE_BOT,
                "order_id": "buy-2",
                "fill_delta_qty": "20",
                "filled_avg_price": "10",
            },
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-06-01T20:00:00+00:00",
                "symbol": "SOXS",
                "side": "sell",
                "bot": INVERSE_BOT,
                "order_id": "sell-2",
                "fill_delta_qty": "20",
                "filled_avg_price": "12",
                "reason": "market_close_liquidation",
            },
        ]
        log_records = [
            {
                "timestamp": "2026-06-01T13:30:00+00:00",
                "market_open": True,
                "portfolio_value": "1000",
                "config": {"directional_mode": "BALANCED"},
                "regime": "UPTREND",
                "trend_trust": {"score": 40, "regime_age_minutes": 0},
                "console_lines": [],
            },
            {
                "timestamp": "2026-06-01T20:00:00+00:00",
                "market_open": True,
                "portfolio_value": "1140",
                "config": {
                    "config_version": "v-test-config",
                    "strategy_version": "v-test-strategy",
                    "symbol": "SOXL",
                    "position_sizing_mode": "DYNAMIC",
                    "position_notional": "25",
                    "position_allocation_percent": "50",
                    "poll_seconds": 30,
                    "trail_percent": "1.25",
                    "fast_sma_minutes": 5,
                    "slow_sma_minutes": 20,
                    "regime_gap_threshold": "0.20",
                    "regime_exit_gap_threshold": "0.10",
                    "chop_entry_discount_percent": "0.50",
                    "close_liquidate_minutes": 5,
                    "directional_mode": "BALANCED",
                    "directional_max_extension_percent": "0.50",
                    "directional_strong_chase_max_extension_percent": "1.00",
                    "directional_min_strength": "MODERATE",
                    "directional_cooldown_minutes": 4,
                    "adaptive_shadow_enabled": True,
                    "dry_run": False,
                    "active_environment": "paper",
                    "data_feed": "iex",
                },
                "regime": "SIDEWAYS",
                "regime_transition": {"from": "UPTREND", "to": "SIDEWAYS"},
                "data_status": "STALE",
                "stream_error": True,
                "trend_trust": {"score": 60, "regime_age_minutes": 30},
                "console_lines": ["[DATA] HEALTH bars=STALE (93s)"],
            },
        ]

        class FakeLifecycleLedger:
            def read_all(self) -> list[dict[str, object]]:
                return lifecycle_records

        with tempfile.TemporaryDirectory() as tmpdir:
            logs_root = Path(tmpdir)
            log_path = logs_root / "edgewalker-2026-06-01.jsonl"
            log_path.write_text(
                "\n".join(json.dumps(record) for record in log_records),
                encoding="utf-8",
            )
            with patch("server.LOGS_ROOT", logs_root), patch(
                "server.LifecycleLedger",
                FakeLifecycleLedger,
            ):
                payload = build_operator_spreadsheet_daily_row(
                    "2026-06-01",
                    operator_notes="round 2 conservative",
                    include_daily_narrative=False,
                )

        row = payload["row"]

        self.assertEqual(payload["columns"], OPERATOR_SPREADSHEET_COLUMNS)
        self.assertEqual(len(payload["values"]), len(OPERATOR_SPREADSHEET_COLUMNS))
        self.assertEqual(
            payload["columns"].index("win_rate"),
            payload["columns"].index("losses") + 1,
        )
        self.assertEqual(
            payload["columns"].index("momentum_pl"),
            payload["columns"].index("win_rate") + 1,
        )
        self.assertEqual(row["date"], "2026-06-01")
        self.assertEqual(row["mode"], "BALANCED")
        self.assertEqual(row["starting_account_value"], 1000.0)
        self.assertEqual(row["ending_account_value"], 1140.0)
        self.assertEqual(row["realized_pl_dollars"], 140.0)
        self.assertEqual(row["account_change_percent"], 14.0)
        self.assertEqual(row["account_result_status"], "GREEN")
        self.assertEqual(row["closed_trades"], 2)
        self.assertEqual(row["wins"], 2)
        self.assertEqual(row["losses"], 0)
        self.assertEqual(row["win_rate"], 100.0)
        self.assertEqual(row["momentum_pl"], 100.0)
        self.assertEqual(row["inverse_pl"], 40.0)
        self.assertEqual(row["top_pl_bot"], MOMENTUM_BOT)
        self.assertEqual(row["bottom_pl_bot"], "")
        self.assertEqual(row["regime_transitions"], 1)
        self.assertEqual(row["cycles"], 2)
        self.assertEqual(row["stale_cycles"], 1)
        self.assertEqual(row["stream_error_cycles"], 1)
        self.assertEqual(row["session_trend_trust_avg"], 50.0)
        self.assertEqual(row["route_invalidation_exits"], 1)
        self.assertEqual(row["route_invalidation_pl"], 100.0)
        self.assertEqual(row["market_close_exits"], 1)
        self.assertEqual(row["market_close_pl"], 40.0)
        self.assertEqual(row["session_avg_mfe_percent"], 15.0)
        self.assertEqual(row["session_avg_mae_percent"], 0.0)
        self.assertEqual(row["session_avg_capture_ratio_percent"], 100.0)
        self.assertEqual(row["session_avg_hold_seconds"], 9900.0)
        self.assertEqual(row["momentum_avg_mfe_percent"], 10.0)
        self.assertEqual(row["momentum_avg_mae_percent"], 0.0)
        self.assertEqual(row["momentum_avg_capture_ratio_percent"], 100.0)
        self.assertEqual(row["momentum_avg_hold_seconds"], 1800.0)
        self.assertEqual(row["chop_avg_mfe_percent"], "")
        self.assertEqual(row["chop_avg_mae_percent"], "")
        self.assertEqual(row["chop_avg_capture_ratio_percent"], "")
        self.assertEqual(row["chop_avg_hold_seconds"], "")
        self.assertEqual(row["inverse_avg_mfe_percent"], 20.0)
        self.assertEqual(row["inverse_avg_mae_percent"], 0.0)
        self.assertEqual(row["inverse_avg_capture_ratio_percent"], 100.0)
        self.assertEqual(row["inverse_avg_hold_seconds"], 18000.0)
        self.assertEqual(row["inverse_near_zero_mfe_count"], 0)
        self.assertEqual(row["inverse_meaningful_mfe_low_capture_count"], 0)
        self.assertEqual(row["inverse_adverse_gt_favorable_count"], 0)
        self.assertEqual(row["mfe_mae_source"], "fill_prices_only")
        self.assertEqual(row["reconciliation_confidence"], "HIGH")
        self.assertEqual(row["config_version"], "v-test-config")
        self.assertEqual(row["strategy_version"], "v-test-strategy")
        self.assertEqual(row["symbol_primary"], "SOXL")
        self.assertEqual(row["symbol_inverse"], "SOXS")
        self.assertEqual(row["position_sizing_mode"], "DYNAMIC")
        self.assertEqual(row["position_notional"], 25.0)
        self.assertEqual(row["position_allocation_percent"], 50.0)
        self.assertEqual(row["poll_seconds"], 30)
        self.assertEqual(row["trail_percent"], 1.25)
        self.assertEqual(row["fast_sma_minutes"], 5)
        self.assertEqual(row["slow_sma_minutes"], 20)
        self.assertEqual(row["regime_gap_percent"], 0.2)
        self.assertEqual(row["regime_exit_gap_percent"], 0.1)
        self.assertEqual(row["chop_discount_percent"], 0.5)
        self.assertEqual(row["close_liquidate_minutes"], 5)
        self.assertEqual(row["directional_max_extension_percent"], 0.5)
        self.assertEqual(row["directional_strong_chase_max_extension_percent"], 1.0)
        self.assertEqual(row["directional_min_strength"], "MODERATE")
        self.assertEqual(row["directional_cooldown_minutes"], 4)
        self.assertTrue(row["adaptive_shadow_enabled"])
        self.assertFalse(row["dry_run"])
        self.assertEqual(row["active_environment"], "paper")
        self.assertEqual(row["data_feed"], "iex")
        self.assertEqual(row["operator_notes"], "round 2 conservative")

    def test_operator_spreadsheet_daily_row_uses_final_environment(self) -> None:
        lifecycle_records = [
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-06-04T12:45:00+00:00",
                "symbol": "SOXL",
                "side": "buy",
                "bot": MOMENTUM_BOT,
                "order_id": "paper-buy",
                "fill_delta_qty": "1",
                "filled_avg_price": "100",
            },
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-06-04T12:46:00+00:00",
                "symbol": "SOXL",
                "side": "sell",
                "bot": MOMENTUM_BOT,
                "order_id": "paper-sell",
                "fill_delta_qty": "1",
                "filled_avg_price": "200",
                "reason": "trailing_stop_breached",
            },
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-06-04T13:40:00+00:00",
                "symbol": "SOXL",
                "side": "buy",
                "bot": MOMENTUM_BOT,
                "order_id": "live-buy",
                "fill_delta_qty": "1",
                "filled_avg_price": "10",
            },
            {
                "event_type": LIFECYCLE_FULL_FILL,
                "created_at": "2026-06-04T14:00:00+00:00",
                "symbol": "SOXL",
                "side": "sell",
                "bot": MOMENTUM_BOT,
                "order_id": "live-sell",
                "fill_delta_qty": "1",
                "filled_avg_price": "10.08",
                "reason": "route_invalidated_exit",
            },
        ]
        log_records = [
            {
                "timestamp": "2026-06-04T12:44:13Z",
                "market_open": False,
                "portfolio_value": "92119.38",
                "config": {
                    "directional_mode": "ADAPTIVE",
                    "active_environment": "paper",
                    "dry_run": False,
                },
                "stream_error": True,
                "trend_trust": {"score": 10},
                "console_lines": ["[DATA] HEALTH bars=STALE (120s)"],
            },
            {
                "timestamp": "2026-06-04T12:51:36Z",
                "market_open": False,
                "portfolio_value": "100",
                "config": {
                    "directional_mode": "ADAPTIVE",
                    "active_environment": "live",
                    "dry_run": False,
                },
                "trend_trust": {"score": 40},
                "console_lines": [],
            },
            {
                "timestamp": "2026-06-04T20:00:00Z",
                "market_open": True,
                "portfolio_value": "100.02",
                "config": {
                    "directional_mode": "ADAPTIVE",
                    "active_environment": "live",
                    "dry_run": False,
                },
                "regime_transition": {"from": "UPTREND", "to": "DOWNTREND"},
                "trend_trust": {"score": 60},
                "console_lines": [],
            },
        ]

        class FakeLifecycleLedger:
            def read_all(self) -> list[dict[str, object]]:
                return lifecycle_records

        with tempfile.TemporaryDirectory() as tmpdir:
            logs_root = Path(tmpdir)
            log_path = logs_root / "edgewalker-2026-06-04.jsonl"
            log_path.write_text(
                "\n".join(json.dumps(record) for record in log_records),
                encoding="utf-8",
            )
            with patch("server.LOGS_ROOT", logs_root), patch(
                "server.LifecycleLedger",
                FakeLifecycleLedger,
            ):
                payload = build_operator_spreadsheet_daily_row("2026-06-04")

        row = payload["row"]

        self.assertEqual(row["starting_account_value"], 100.0)
        self.assertEqual(row["ending_account_value"], 100.02)
        self.assertEqual(row["realized_pl_dollars"], 0.08)
        self.assertEqual(row["account_change_percent"], 0.08)
        self.assertEqual(row["closed_trades"], 1)
        self.assertEqual(row["route_invalidation_exits"], 1)
        self.assertEqual(row["route_invalidation_pl"], 0.08)
        self.assertEqual(row["trailing_stop_exits"], 0)
        self.assertEqual(row["cycles"], 2)
        self.assertEqual(row["stale_cycles"], 0)
        self.assertEqual(row["stream_error_cycles"], 0)
        self.assertEqual(row["session_trend_trust_avg"], 50.0)
        self.assertEqual(row["active_environment"], "live")

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

    def test_research_session_metrics_include_v8_blocks_and_bot_early_entries(self) -> None:
        records = [
            {
                "action_taken": "no_entry_signal",
                "console_lines": [
                    "[ENTRY] MomentumBot check: entry_signal=False reason=v8_regime_too_young",
                    "[ENTRY] BLOCKED bot=MomentumBot reason=v8_regime_too_young",
                ],
            },
            {
                "action_taken": "no_entry_signal",
                "console_lines": [
                    "[ENTRY] InverseBot check: entry_signal=False reason=v8_trend_trust_below_minimum",
                ],
            },
            {
                "action_taken": "no_entry_signal",
                "console_lines": [
                    "[ENTRY] InverseBot check: entry_signal=False reason=v8_noisy_water_filter",
                ],
            },
            {
                "action_taken": "no_entry_signal",
                "console_lines": [
                    "[ENTRY] InverseBot check: entry_signal=False reason=v9_momentum_context_suppresses_inverse",
                ],
                "v9_momentum_context": {
                    "active": True,
                    "activated_at": "2026-06-08T14:00:00Z",
                },
            },
            {
                "action_taken": "no_entry_signal",
                "console_lines": [],
                "v9_momentum_context": {
                    "active": False,
                    "activated_at": "2026-06-08T14:00:00Z",
                    "invalidated_at": "2026-06-08T15:00:00Z",
                },
            },
            {
                "action_taken": "market_buy",
                "active_bot": MOMENTUM_BOT,
                "trend_trust": {"regime_age_minutes": 2},
            },
            {
                "action_taken": "market_buy",
                "active_bot": CHOP_BOT,
                "trend_trust": {"regime_age_minutes": 1},
            },
            {
                "action_taken": "market_buy",
                "active_bot": INVERSE_BOT,
                "trend_trust": {"regime_age_minutes": 3},
            },
            {
                "action_taken": "market_buy",
                "active_bot": INVERSE_BOT,
                "trend_trust": {"regime_age_minutes": 8},
            },
        ]

        metrics = _session_metrics(records, [])

        self.assertEqual(metrics["v8_young_regime_blocks"], 1)
        self.assertEqual(metrics["v8_low_trust_blocks"], 1)
        self.assertEqual(metrics["v8_noisy_water_blocks"], 1)
        self.assertEqual(metrics["v9_momentum_context_activations"], 1)
        self.assertEqual(metrics["v9_inverse_suppression_blocks"], 1)
        self.assertEqual(metrics["v9_momentum_context_invalidations"], 1)
        self.assertEqual(metrics["early_entry_count"], 3)
        self.assertEqual(metrics["momentum_early_entry_count"], 1)
        self.assertEqual(metrics["chop_early_entry_count"], 1)
        self.assertEqual(metrics["inverse_early_entry_count"], 1)
        self.assertEqual(metrics["entry_regime_age_median"], Decimal("3"))

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
                "action_taken": "close_route_invalidated_position_no_same_cycle_reversal",
                "position_owner": MOMENTUM_BOT,
                "position_symbol": "SOXL",
                "position_qty": "1",
                "position_current_price": "99",
                "config": {"dry_run": False},
                "console_lines": [
                    "[RISK] SOXL: route invalidated under regime=SIDEWAYS; "
                    "owner=MomentumBot active_bot=ChopBot; selling qty=1.",
                ],
            },
        ]

        context = _extract_session_context(records, "2026-05-22", [])

        self.assertEqual([trade["action"] for trade in context["trades"]], ["BUY", "SELL"])
        self.assertEqual(context["trades"][1]["bot"], MOMENTUM_BOT)

    def test_session_context_includes_structured_session_metrics(self) -> None:
        records = [
            {
                "timestamp": "2026-05-22T14:30:00Z",
                "market_open": True,
                "regime": "UPTREND",
                "regime_transition": {"from": "WARMUP", "to": "UPTREND"},
                "action_taken": "no_entry_signal",
                "adaptive_posture": "BALANCED",
                "trend_trust": {
                    "score": 50,
                    "label": "LOW",
                    "regime_age_minutes": 1,
                    "recent_flip_count_60m": 3,
                },
                "console_lines": [
                    "[ENTRY] BLOCKED bot=MomentumBot symbol=SOXL reason=mode_requires_fresh_cross",
                    "[DATA] BAR BACKFILL repaired symbols=SOXL",
                ],
                "config": {"dry_run": False},
            },
            {
                "timestamp": "2026-05-22T14:31:00Z",
                "market_open": True,
                "regime": "UPTREND",
                "action_taken": "wait_stale_market_data",
                "adaptive_posture": "CONSERVATIVE",
                "data_status": "STALE",
                "trend_trust": {
                    "score": 60,
                    "label": "MODERATE",
                    "regime_age_minutes": 3,
                    "recent_flip_count_60m": 4,
                },
                "console_lines": [
                    "[DATA] HEALTH bars=STALE (111s) quotes=LIVE (<1s)",
                ],
                "config": {"dry_run": False},
            },
        ]
        lifecycle_records = [
            {
                "event_type": LIFECYCLE_ORDER_SUBMITTED,
                "created_at": "2026-05-22T14:35:00+00:00",
                "symbol": "SOXL",
                "side": "sell",
                "reason": "route_invalidated_exit",
                "lifecycle_context": {"kind": "route_invalidation_exit"},
            },
            {
                "event_type": LIFECYCLE_ORDER_SUBMITTED,
                "created_at": "2026-05-22T14:40:00+00:00",
                "symbol": "SOXL",
                "side": "sell",
                "reason": "trailing_stop_breached",
            },
        ]

        context = _extract_session_context(records, "2026-05-22", lifecycle_records)
        prompt = _build_summary_prompt(context)
        metrics = context["session_metrics"]

        self.assertEqual(metrics["regime_transition_count"], 1)
        self.assertEqual(metrics["stale_bar_cycles"], 1)
        self.assertEqual(metrics["backfill_repair_cycles"], 1)
        self.assertEqual(metrics["route_invalidation_exit_count"], 1)
        self.assertEqual(metrics["route_invalidation_scaffold_count"], 1)
        self.assertEqual(metrics["trailing_stop_exit_count"], 1)
        self.assertEqual(metrics["trend_trust"]["average_score"], "55.0")
        self.assertIn("SESSION METRICS:", prompt)
        self.assertIn("route_invalidated=1", prompt)
        self.assertIn("avg_score=55.0", prompt)
        self.assertIn("mode_requires_fresh_cross=1", prompt)

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

    def test_ground_narrative_sections_uses_lifecycle_bot_stats(self) -> None:
        sections = _parse_narrative_response(
            json.dumps(
                {
                    "tldr": "Brief read.",
                    "bot_performance": {
                        "MomentumBot": "Executed 10 trades with 5 wins and 5 losses.",
                        "ChopBot": "Engaged in 2 trades, both losses.",
                        "InverseBot": "Traded 5 times with 4 wins and 1 loss.",
                    },
                }
            )
        )
        performance = {
            "bot_performance": [
                {
                    "bot": MOMENTUM_BOT,
                    "realized_pl": "2142.171078",
                    "trade_count": 8,
                    "wins": 7,
                    "losses": 1,
                    "win_rate_percent": "87.5",
                    "last_trade_realized_pl": "529.351248",
                    "last_trade_symbol": "SOXL",
                },
                {
                    "bot": CHOP_BOT,
                    "realized_pl": "-59.181182",
                    "trade_count": 1,
                    "wins": 0,
                    "losses": 1,
                    "win_rate_percent": "0",
                    "last_trade_realized_pl": "-59.181182",
                    "last_trade_symbol": "SOXL",
                },
                {
                    "bot": INVERSE_BOT,
                    "realized_pl": "-791.362640",
                    "trade_count": 6,
                    "wins": 2,
                    "losses": 4,
                    "win_rate_percent": "33.33333333333333333333333333",
                    "last_trade_realized_pl": "-285.716729",
                    "last_trade_symbol": "SOXS",
                },
            ]
        }

        grounded = _ground_narrative_sections(sections, {"performance": performance})

        self.assertIn("8 closed trades, 7W/1L", grounded["bot_performance"][MOMENTUM_BOT])
        self.assertIn("realized P/L $2,142.17", grounded["bot_performance"][MOMENTUM_BOT])
        self.assertIn("1 closed trade, 0W/1L", grounded["bot_performance"][CHOP_BOT])
        self.assertIn("6 closed trades, 2W/4L", grounded["bot_performance"][INVERSE_BOT])

    def test_generate_session_summary_reuses_matching_cache(self) -> None:
        log_records = [
            {
                "timestamp": "2026-06-02T13:30:00+00:00",
                "market_open": True,
                "portfolio_value": "1000",
                "config": {"directional_mode": "BALANCED", "dry_run": False},
                "regime": "UPTREND",
                "source_price": "250",
                "console_lines": [],
            },
            {
                "timestamp": "2026-06-02T20:00:00+00:00",
                "market_open": True,
                "portfolio_value": "1010",
                "config": {"directional_mode": "BALANCED", "dry_run": False},
                "regime": "SIDEWAYS",
                "cycle_id": 382,
                "source_price": "260",
                "console_lines": [],
            },
        ]

        class FakeLifecycleLedger:
            def read_all(self) -> list[dict[str, object]]:
                return []

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            log_path = root / "edgewalker-2026-06-02.jsonl"
            log_path.write_text(
                "\n".join(json.dumps(record) for record in log_records),
                encoding="utf-8",
            )
            cache_path = root / ".narrative_cache.json"
            with (
                patch("server.LOGS_ROOT", root),
                patch("server.NARRATIVE_CACHE_PATH", cache_path),
                patch("server.LifecycleLedger", FakeLifecycleLedger),
                patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
                patch(
                    "server._call_openai",
                    return_value='{"tldr": "Cached read.", "bottom_line": "Done."}',
                ) as call_openai,
            ):
                first = generate_session_summary("2026-06-02", "1D")
                second = generate_session_summary("2026-06-02", "1D")
                cache_only = generate_session_summary(
                    "2026-06-02",
                    "1D",
                    cache_only=True,
                )

        self.assertEqual(call_openai.call_count, 1)
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertTrue(cache_only["cached"])
        self.assertEqual(second["narrative"]["tldr"], "Cached read.")

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
                "operator_spreadsheet": {
                    "spreadsheet_url": "https://docs.google.com/spreadsheets/d/example",
                    "post_endpoint_url": "https://script.google.com/macros/s/example/exec",
                    "auto_post_enabled": True,
                    "include_daily_narrative": True,
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
        self.assertTrue(settings["operator_spreadsheet"]["auto_post_enabled"])
        self.assertNotIn("paper-secret-5678", json.dumps(settings))
        self.assertIn("ALPACA_LIVE_API_KEY_ID=live-key-1234", env_text)
        self.assertIn("OPERATOR_SPREADSHEET_AUTO_POST=true", env_text)

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
                parsed = config_from_payload({"dryRun": True})
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

        with patch.object(
            BotRunner,
            "_operator_spreadsheet_auto_post_date",
            return_value=None,
        ):
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

    def test_runner_auto_posts_operator_spreadsheet_once_after_close(self) -> None:
        runner = BotRunner.__new__(BotRunner)
        stop_event = threading.Event()
        runner._config = config()
        runner._lock = threading.Lock()
        runner._stop_event = stop_event
        runner._running = True
        runner._next_run_at = None
        runner._next_run_reason = None
        runner._market_idle_logged_for = "old"
        runner._last_stopped_at = None
        runner._last_output = ["previous"]
        runner._last_error = None
        runner._activity_log = []
        runner._spreadsheet_auto_posted_dates = set()
        runner._spreadsheet_auto_post_attempted_dates = set()
        runner._save_activity_log = lambda: None
        runner._save_spreadsheet_posted_dates = lambda: None
        fast_config = replace(config(), poll_seconds=0)
        next_open = datetime(2026, 6, 3, 13, 30, 0, tzinfo=timezone.utc)

        with (
            patch.object(
                BotRunner,
                "_operator_spreadsheet_auto_post_date",
                return_value="2026-06-02",
            ),
            patch(
                "server.post_operator_spreadsheet_daily_row",
                return_value={"narrative_error": None},
            ) as post_daily_row,
        ):
            runner._arm_until_market_open(fast_config, stop_event, next_open)
            runner._arm_until_market_open(fast_config, stop_event, next_open)

        self.assertEqual(post_daily_row.call_count, 1)
        post_daily_row.assert_called_once_with({"date": "2026-06-02"})
        self.assertIn("2026-06-02", runner._spreadsheet_auto_posted_dates)
        self.assertIn(
            "[SPREADSHEET] Auto-posted daily row for 2026-06-02.",
            [line for _, line in runner._activity_log],
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
