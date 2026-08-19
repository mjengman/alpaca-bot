from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from experiment_ledger import (
    COHORT_STATUS_COMPLETE,
    COHORT_STATUS_ACTIVE,
    GitProvenance,
    GrowthCohortCoordinator,
    GrowthCohortLedger,
    circular_block_bootstrap_analysis,
    payload_hash,
)


class GrowthCohortLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.ledger = GrowthCohortLedger(
            root / "experiment.sqlite3",
            root / "audit.jsonl",
        )
        self.config = {
            "strategy_version": "v1",
            "dry_run": False,
            "position_allocation_percent": "95",
            "data_feed": "iex",
        }
        self.provenance = GitProvenance("abc123", False)

    def tearDown(self) -> None:
        self.ledger.close()
        self.temporary_directory.cleanup()

    def start(self) -> None:
        self.ledger.start(
            launched_at=datetime(2026, 8, 19, 13, 30, tzinfo=timezone.utc),
            environment="live",
            data_feed="iex",
            provenance=self.provenance,
            config_payload=self.config,
            manifest_hash="manifest-hash",
        )

    def test_launch_freezes_build_and_configuration(self) -> None:
        self.start()
        run = self.ledger.run()

        self.assertIsNotNone(run)
        self.assertEqual(run["status"], COHORT_STATUS_ACTIVE)
        self.assertEqual(run["launch_git_sha"], "abc123")
        self.assertEqual(run["config_hash"], payload_hash(self.config))
        self.assertEqual(
            self.ledger.integrity_issues(
                config_payload={**self.config, "position_allocation_percent": "50"},
                provenance=GitProvenance("def456", True),
                environment="paper",
                data_feed="sip",
            ),
            [
                "frozen_config_changed",
                "production_build_changed",
                "production_worktree_dirty",
                "alpaca_environment_changed",
                "market_data_feed_changed",
            ],
        )

    def test_frozen_block_bootstrap_is_deterministic(self) -> None:
        first = circular_block_bootstrap_analysis(
            [Decimal("0.01")] * 20,
            block_length=5,
            resamples=500,
            seed=20260819,
        )
        second = circular_block_bootstrap_analysis(
            [Decimal("0.01")] * 20,
            block_length=5,
            resamples=500,
            seed=20260819,
        )

        self.assertEqual(first, second)
        self.assertGreater(
            Decimal(first["one_sided_95_lower_bound"]),
            Decimal("0"),
        )

    def test_no_trade_sessions_count_and_returns_compound(self) -> None:
        self.start()
        first = datetime(2026, 8, 19, 19, 59, tzinfo=timezone.utc)
        second = datetime(2026, 8, 20, 19, 59, tzinfo=timezone.utc)

        self.ledger.record_cycle(
            cycle_id=1,
            observed_at=first,
            provenance=self.provenance,
            config_payload=self.config,
            edgewalker_status={
                "portfolio_value": "1010",
                "day_pl_percent": "1.0",
                "regime": "SIDEWAYS",
                "action_taken": "no_entry",
            },
            performance={"session_trade_count": 0},
            broker_state={"state": "OK"},
            error=None,
        )
        self.assertTrue(
            self.ledger.finalize_latest_session(
                datetime(2026, 8, 19, 20, 5, tzinfo=timezone.utc)
            )
        )
        self.ledger.record_cycle(
            cycle_id=2,
            observed_at=second,
            provenance=self.provenance,
            config_payload=self.config,
            edgewalker_status={
                "portfolio_value": "1004.95",
                "day_pl_percent": "-0.5",
                "regime": "UPTREND",
                "action_taken": "managed_position",
            },
            performance={"session_trade_count": 1},
            broker_state={"state": "OK"},
            error=None,
        )
        self.ledger.finalize_latest_session(
            datetime(2026, 8, 20, 20, 5, tzinfo=timezone.utc)
        )

        metrics = self.ledger.metrics()
        sessions = self.ledger.session_rows(completed_only=True)
        self.assertEqual(metrics["completed_sessions"], 2)
        self.assertEqual(metrics["positive_sessions"], 1)
        self.assertEqual(metrics["one_percent_sessions"], 1)
        self.assertEqual(metrics["compounded_return"], "0.00495")
        self.assertEqual(sessions[0]["trade_count"], 0)

    def test_operator_lifecycle_event_marks_session(self) -> None:
        self.start()
        observed_at = datetime(2026, 8, 19, 15, 0, tzinfo=timezone.utc)
        self.ledger.record_cycle(
            cycle_id=1,
            observed_at=observed_at,
            provenance=self.provenance,
            config_payload=self.config,
            edgewalker_status={"portfolio_value": "1000", "day_pl_percent": "0"},
            performance={"session_trade_count": 0},
            broker_state={"state": "OK"},
            error=None,
        )
        inserted = self.ledger.sync_lifecycle_records(
            [
                {
                    "event_type": "OPERATOR_ENTER_NOW",
                    "created_at": "2026-08-19T15:01:00+00:00",
                    "symbol": "SOXL",
                }
            ]
        )
        self.ledger.finalize_latest_session(
            datetime(2026, 8, 19, 20, 1, tzinfo=timezone.utc)
        )

        self.assertEqual(inserted, 1)
        self.assertEqual(self.ledger.metrics()["manual_intervention_sessions"], 1)

    def test_shadow_trail_lab_is_local_and_uses_autonomous_fill_anchor(self) -> None:
        self.start()
        fill = {
            "event_type": "FULL_FILL",
            "created_at": "2026-08-19T14:00:00+00:00",
            "side": "buy",
            "symbol": "SOXL",
            "bot": "MomentumBot",
            "filled_avg_price": "100",
            "order_id": "entry-1",
            "dry_run": False,
            "lifecycle_context": {
                "entry_initiator": "bot",
                "operator_affected": False,
            },
        }
        self.ledger.observe_shadow_trails(
            records=[fill],
            edgewalker_status={"source_price": "100", "inverse_price": "40"},
            observed_at=datetime(2026, 8, 19, 14, 0, tzinfo=timezone.utc),
        )
        self.ledger.observe_shadow_trails(
            records=[fill],
            edgewalker_status={"source_price": "102", "inverse_price": "40"},
            observed_at=datetime(2026, 8, 19, 14, 1, tzinfo=timezone.utc),
        )
        self.ledger.observe_shadow_trails(
            records=[fill],
            edgewalker_status={"source_price": "100.8", "inverse_price": "40"},
            observed_at=datetime(2026, 8, 19, 14, 2, tzinfo=timezone.utc),
        )

        metrics = {
            row["variant_id"]: row for row in self.ledger.shadow_trail_metrics()
        }
        self.assertEqual(metrics["trail-1.00"]["closed_trades"], 1)
        self.assertEqual(metrics["trail-1.00"]["average_return"], "0.008")
        self.assertEqual(metrics["trail-1.50"]["open_trades"], 1)

        self.assertEqual(
            self.ledger.finalize_shadow_trails(
                datetime(2026, 8, 19, 20, 1, tzinfo=timezone.utc)
            ),
            4,
        )
        self.assertTrue(
            all(row["closed_trades"] == 1 for row in self.ledger.shadow_trail_metrics())
        )

    def test_sixtieth_completed_session_closes_cohort(self) -> None:
        self.start()
        with self.ledger._lock, self.ledger._connection:
            for day in range(1, 61):
                session_date = f"2026-10-{day:02d}"
                self.ledger._connection.execute(
                    """
                    INSERT INTO cohort_sessions (
                        cohort_id, session_date, first_observed_at, last_observed_at,
                        completed, config_hash, git_sha
                    ) VALUES (?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        "edgewalker-growth-cohort-1",
                        session_date,
                        "2026-10-01T14:00:00Z",
                        "2026-10-01T20:00:00Z",
                        payload_hash(self.config),
                        "abc123",
                    ),
                )
            self.ledger._connection.execute(
                """
                UPDATE cohort_sessions SET completed = 0
                WHERE cohort_id = ? AND session_date = ?
                """,
                ("edgewalker-growth-cohort-1", "2026-10-60"),
            )

        self.assertTrue(
            self.ledger.finalize_latest_session(
                datetime(2026, 12, 1, 21, 0, tzinfo=timezone.utc)
            )
        )
        self.assertEqual(self.ledger.run()["status"], COHORT_STATUS_COMPLETE)


class GrowthCohortCoordinatorTest(unittest.TestCase):
    def test_dirty_worktree_blocks_authorized_live_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = root / "manifest.json"
            artifact = root / "analysis.md"
            artifact.write_text("frozen", encoding="utf-8")
            manifest.write_text(
                json.dumps(
                    {
                        "launch_authorized": True,
                        "frozen_artifacts": {
                            "analysis.md": hashlib.sha256(b"frozen").hexdigest()
                        },
                    }
                ),
                encoding="utf-8",
            )
            ledger = GrowthCohortLedger(root / "db.sqlite3", root / "audit.jsonl")
            coordinator = GrowthCohortCoordinator(
                ledger,
                project_root=root,
                manifest_path=manifest,
            )
            config = {"dry_run": False, "data_feed": "iex"}
            try:
                with patch(
                    "experiment_ledger.git_provenance",
                    return_value=GitProvenance("abc123", True),
                ):
                    halt = coordinator.entry_halt(
                        config_payload=config,
                        environment="live",
                        live_trading_armed=True,
                        observed_at=datetime.now(timezone.utc),
                    )
                self.assertEqual(
                    halt["reason"],
                    "experiment_launch_provenance_blocked",
                )
                self.assertIsNone(ledger.run())
            finally:
                ledger.close()


if __name__ == "__main__":
    unittest.main()
