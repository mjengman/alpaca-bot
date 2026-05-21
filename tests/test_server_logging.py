from __future__ import annotations

import json
import threading
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from bot import BotConfig
from server import (
    BotRunner,
    NY_TZ,
    _append_daily_jsonl,
    _current_ny_activity,
    _cycle_log_record,
    _daily_log_path,
    _format_regime_transition,
    config_from_payload,
)


def config() -> BotConfig:
    return BotConfig(
        trading_base_url="https://paper-api.alpaca.markets/v2",
        data_base_url="https://data.alpaca.markets/v2",
        api_key_id="key",
        api_secret_key="secret",
        symbol="SOXL",
        position_notional=Decimal("25"),
        trail_percent=Decimal("1.5"),
        fast_sma_minutes=5,
        slow_sma_minutes=20,
        poll_seconds=60,
        close_liquidate_minutes=5,
        regime_gap_threshold=Decimal("0.20"),
        chop_entry_discount_percent=Decimal("0.50"),
        directional_mode="BALANCED",
        directional_max_extension_percent=Decimal("0.50"),
        directional_strong_chase_max_extension_percent=Decimal("1.00"),
        directional_min_strength="MODERATE",
        directional_cooldown_minutes=5,
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

        record = _cycle_log_record(
            config=config(),
            cycle_id=7,
            timestamp=timestamp,
            console_lines=["SOXL regime check", "entry_signal=False"],
            error=None,
            edgewalker_status=status,
            regime_transition=transition,
        )

        self.assertEqual(record["timestamp"], "2026-05-22T01:05:00Z")
        self.assertEqual(record["trading_date"], "2026-05-21")
        self.assertEqual(record["cycle_id"], 7)
        self.assertEqual(record["regime"], "UPTREND")
        self.assertEqual(record["price"], "170.42")
        self.assertEqual(record["account_value"], "50.09")
        self.assertEqual(record["console_lines"], ["SOXL regime check", "entry_signal=False"])
        self.assertEqual(record["regime_transition"], transition)
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

    def test_runner_switches_off_when_market_is_closed(self) -> None:
        runner = BotRunner.__new__(BotRunner)
        stop_event = threading.Event()
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

        runner._stop_after_market_close(
            stop_event,
            datetime(2026, 5, 22, 13, 30, 0, tzinfo=timezone.utc),
        )

        self.assertTrue(stop_event.is_set())
        self.assertFalse(runner._running)
        self.assertIsNone(runner._next_run_at)
        self.assertIsNone(runner._next_run_reason)
        self.assertIsNone(runner._market_idle_logged_for)
        self.assertIsNotNone(runner._last_stopped_at)
        self.assertEqual(
            runner._last_output[0],
            "Market closed. EdgeWalker switched off; "
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
