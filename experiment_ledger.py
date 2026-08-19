from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


COHORT_ID = "edgewalker-growth-cohort-3"
COHORT_NAME = "Edgewalker Growth Cohort 3"
COHORT_STATUS_ACTIVE = "ACTIVE"
COHORT_STATUS_COMPLETE = "COMPLETE"
COHORT_STATUS_WAITING = "WAITING"
COHORT_STATUS_BLOCKED = "BLOCKED"
PLANNED_SESSION_COUNT = 60
INTERIM_SESSION_COUNTS = (20, 40)
TARGET_DAILY_RETURN = Decimal("0.01")
BOOTSTRAP_BLOCK_LENGTH = 5
BOOTSTRAP_RESAMPLES = 50_000
BOOTSTRAP_SEED = 20260819
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "logs" / "edgewalker-experiments.sqlite3"
DEFAULT_AUDIT_PATH = PROJECT_ROOT / "logs" / "edgewalker-experiment-events.jsonl"
DEFAULT_MANIFEST_PATH = (
    PROJECT_ROOT
    / "research"
    / COHORT_ID
    / "launch-readiness-manifest-v3.json"
)
NY_TZ = ZoneInfo("America/New_York")
OPERATOR_EVENT_TYPES = {
    "OPERATOR_BANK_DAY",
    "OPERATOR_ENTER_NOW",
    "OPERATOR_EXIT_NOW",
}
SHADOW_TRAIL_VARIANTS = {
    "trail-1.00": Decimal("1.00"),
    "trail-1.50": Decimal("1.50"),
    "trail-2.00": Decimal("2.00"),
    "trail-3.50": Decimal("3.50"),
    "trail-6.00": Decimal("6.00"),
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def payload_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def lifecycle_event_hash(record: dict[str, Any]) -> str:
    return payload_hash(record)


def utc_text(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def session_date_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(NY_TZ).date().isoformat()


def decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _operator_affected(record: dict[str, Any]) -> bool:
    if record.get("event_type") in OPERATOR_EVENT_TYPES:
        return True
    context = record.get("lifecycle_context")
    if not isinstance(context, dict):
        context = {}
    values = (
        record.get("entry_initiator"),
        record.get("exit_initiator"),
        record.get("operator_affected"),
        context.get("entry_initiator"),
        context.get("exit_initiator"),
        context.get("operator_affected"),
    )
    return any(value is True or str(value).lower() == "operator" for value in values)


def circular_block_bootstrap_analysis(
    returns: list[Decimal],
    *,
    block_length: int = BOOTSTRAP_BLOCK_LENGTH,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    if not returns or any(value <= Decimal("-1") for value in returns):
        return {
            "method": "circular_moving_block_bootstrap",
            "available": False,
            "reason": "valid_returns_unavailable",
        }
    log_returns = [math.log1p(float(value)) for value in returns]
    rng = random.Random(seed)
    estimates: list[float] = []
    sample_count = len(log_returns)
    effective_block_length = min(max(1, block_length), sample_count)
    for _ in range(resamples):
        sample: list[float] = []
        while len(sample) < sample_count:
            start = rng.randrange(sample_count)
            sample.extend(
                log_returns[(start + offset) % sample_count]
                for offset in range(effective_block_length)
            )
        estimates.append(math.expm1(sum(sample[:sample_count]) / sample_count))
    estimates.sort()
    lower_index = max(0, math.ceil(0.05 * resamples) - 1)
    observed = math.expm1(sum(log_returns) / sample_count)
    return {
        "method": "circular_moving_block_bootstrap",
        "available": True,
        "block_length": effective_block_length,
        "resamples": resamples,
        "seed": seed,
        "geometric_mean_daily_return": str(Decimal(str(observed))),
        "one_sided_95_lower_bound": str(Decimal(str(estimates[lower_index]))),
    }


@dataclass(frozen=True)
class GitProvenance:
    commit_sha: str
    dirty: bool


def git_provenance(project_root: Path = PROJECT_ROOT) -> GitProvenance:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=project_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return GitProvenance(commit_sha="unknown", dirty=True)
    return GitProvenance(commit_sha=commit or "unknown", dirty=dirty)


class GrowthCohortLedger:
    """Append-oriented, queryable source of truth for the prospective cohort."""

    def __init__(
        self,
        database_path: Path = DEFAULT_DATABASE_PATH,
        audit_path: Path = DEFAULT_AUDIT_PATH,
    ) -> None:
        self.database_path = database_path
        self.audit_path = audit_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.database_path,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._initialize_schema()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _initialize_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cohort_runs (
                    cohort_id TEXT PRIMARY KEY,
                    cohort_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    launched_at TEXT NOT NULL,
                    completed_at TEXT,
                    planned_sessions INTEGER NOT NULL,
                    environment TEXT NOT NULL,
                    data_feed TEXT NOT NULL,
                    launch_git_sha TEXT NOT NULL,
                    launch_git_dirty INTEGER NOT NULL,
                    config_hash TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    manifest_hash TEXT NOT NULL,
                    starting_equity TEXT,
                    last_equity TEXT,
                    integrity_state TEXT NOT NULL DEFAULT 'PASS',
                    integrity_detail TEXT,
                    analysis_json TEXT
                );

                CREATE TABLE IF NOT EXISTS cohort_sessions (
                    cohort_id TEXT NOT NULL,
                    session_date TEXT NOT NULL,
                    first_observed_at TEXT NOT NULL,
                    last_observed_at TEXT NOT NULL,
                    completed_at TEXT,
                    completed INTEGER NOT NULL DEFAULT 0,
                    cycle_count INTEGER NOT NULL DEFAULT 0,
                    error_cycle_count INTEGER NOT NULL DEFAULT 0,
                    trade_count INTEGER NOT NULL DEFAULT 0,
                    operator_intervention INTEGER NOT NULL DEFAULT 0,
                    opening_equity TEXT,
                    closing_equity TEXT,
                    day_return TEXT,
                    config_hash TEXT NOT NULL,
                    git_sha TEXT NOT NULL,
                    PRIMARY KEY (cohort_id, session_date),
                    FOREIGN KEY (cohort_id) REFERENCES cohort_runs(cohort_id)
                );

                CREATE TABLE IF NOT EXISTS decision_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cohort_id TEXT NOT NULL,
                    session_date TEXT NOT NULL,
                    cycle_id INTEGER NOT NULL,
                    cycle_key TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    git_sha TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    regime TEXT,
                    active_bot TEXT,
                    routed_symbol TEXT,
                    action_taken TEXT,
                    entry_signal INTEGER,
                    entry_block_reason TEXT,
                    day_return TEXT,
                    account_equity TEXT,
                    error TEXT,
                    status_json TEXT,
                    performance_json TEXT,
                    broker_json TEXT,
                    UNIQUE (cohort_id, cycle_key),
                    FOREIGN KEY (cohort_id, session_date)
                        REFERENCES cohort_sessions(cohort_id, session_date)
                );

                CREATE TABLE IF NOT EXISTS lifecycle_events (
                    event_hash TEXT PRIMARY KEY,
                    cohort_id TEXT NOT NULL,
                    session_date TEXT NOT NULL,
                    created_at TEXT,
                    event_type TEXT,
                    symbol TEXT,
                    bot TEXT,
                    operator_affected INTEGER NOT NULL DEFAULT 0,
                    event_json TEXT NOT NULL,
                    FOREIGN KEY (cohort_id) REFERENCES cohort_runs(cohort_id)
                );

                CREATE TABLE IF NOT EXISTS experiment_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cohort_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    FOREIGN KEY (cohort_id) REFERENCES cohort_runs(cohort_id)
                );

                CREATE TABLE IF NOT EXISTS shadow_trail_trades (
                    cohort_id TEXT NOT NULL,
                    entry_event_hash TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    session_date TEXT NOT NULL,
                    bot TEXT,
                    symbol TEXT NOT NULL,
                    entry_at TEXT NOT NULL,
                    entry_price TEXT NOT NULL,
                    trail_percent TEXT NOT NULL,
                    high_water_mark TEXT NOT NULL,
                    latest_mark TEXT NOT NULL,
                    mfe_return TEXT NOT NULL DEFAULT '0',
                    mae_return TEXT NOT NULL DEFAULT '0',
                    exit_at TEXT,
                    exit_price TEXT,
                    exit_reason TEXT,
                    realized_return TEXT,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    PRIMARY KEY (cohort_id, entry_event_hash, variant_id),
                    FOREIGN KEY (cohort_id) REFERENCES cohort_runs(cohort_id)
                );

                CREATE INDEX IF NOT EXISTS idx_decisions_session
                    ON decision_snapshots(cohort_id, session_date);
                CREATE INDEX IF NOT EXISTS idx_lifecycle_session
                    ON lifecycle_events(cohort_id, session_date);
                CREATE INDEX IF NOT EXISTS idx_shadow_trails_variant
                    ON shadow_trail_trades(cohort_id, variant_id, status);
                """
            )
            columns = {
                row[1]
                for row in self._connection.execute(
                    "PRAGMA table_info(cohort_runs)"
                ).fetchall()
            }
            if "analysis_json" not in columns:
                self._connection.execute(
                    "ALTER TABLE cohort_runs ADD COLUMN analysis_json TEXT"
                )

    def run(self, cohort_id: str = COHORT_ID) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM cohort_runs WHERE cohort_id = ?",
                (cohort_id,),
            ).fetchone()
        return dict(row) if row else None

    def start(
        self,
        *,
        launched_at: datetime,
        environment: str,
        data_feed: str,
        provenance: GitProvenance,
        config_payload: dict[str, Any],
        manifest_hash: str,
    ) -> dict[str, Any]:
        config_hash = payload_hash(config_payload)
        existing = self.run()
        if existing:
            return existing
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO cohort_runs (
                    cohort_id, cohort_name, status, launched_at,
                    planned_sessions, environment, data_feed,
                    launch_git_sha, launch_git_dirty, config_hash,
                    config_json, manifest_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    COHORT_ID,
                    COHORT_NAME,
                    COHORT_STATUS_ACTIVE,
                    utc_text(launched_at),
                    PLANNED_SESSION_COUNT,
                    environment,
                    data_feed,
                    provenance.commit_sha,
                    int(provenance.dirty),
                    config_hash,
                    canonical_json(config_payload),
                    manifest_hash,
                ),
            )
            self._append_event_locked(
                "COHORT_LAUNCHED",
                {
                    "environment": environment,
                    "data_feed": data_feed,
                    "git_sha": provenance.commit_sha,
                    "git_dirty": provenance.dirty,
                    "config_hash": config_hash,
                    "planned_sessions": PLANNED_SESSION_COUNT,
                    "interim_sessions": list(INTERIM_SESSION_COUNTS),
                },
                launched_at,
            )
        return self.run() or {}

    def integrity_issues(
        self,
        *,
        config_payload: dict[str, Any],
        provenance: GitProvenance,
        environment: str,
        data_feed: str,
    ) -> list[str]:
        run = self.run()
        if not run:
            return []
        issues: list[str] = []
        if payload_hash(config_payload) != run["config_hash"]:
            issues.append("frozen_config_changed")
        if provenance.commit_sha != run["launch_git_sha"]:
            issues.append("production_build_changed")
        if provenance.dirty:
            issues.append("production_worktree_dirty")
        if environment != run["environment"]:
            issues.append("alpaca_environment_changed")
        if data_feed != run["data_feed"]:
            issues.append("market_data_feed_changed")
        return issues

    def record_integrity(self, issues: list[str], observed_at: datetime) -> None:
        run = self.run()
        if not run:
            return
        state = "BLOCKED" if issues else "PASS"
        detail = ",".join(issues) if issues else None
        if run.get("integrity_state") == state and run.get("integrity_detail") == detail:
            return
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE cohort_runs
                SET integrity_state = ?, integrity_detail = ?
                WHERE cohort_id = ?
                """,
                (state, detail, COHORT_ID),
            )
            self._append_event_locked(
                "INTEGRITY_BLOCKED" if issues else "INTEGRITY_RESTORED",
                {"issues": issues},
                observed_at,
            )

    def record_cycle(
        self,
        *,
        cycle_id: int,
        observed_at: datetime,
        provenance: GitProvenance,
        config_payload: dict[str, Any],
        edgewalker_status: dict[str, Any] | None,
        performance: dict[str, Any] | None,
        broker_state: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        run = self.run()
        if not run or run["status"] != COHORT_STATUS_ACTIVE:
            return
        status = edgewalker_status or {}
        session_date = session_date_text(observed_at)
        equity = decimal_or_none(status.get("portfolio_value"))
        day_percent = decimal_or_none(status.get("day_pl_percent"))
        day_return = day_percent / Decimal("100") if day_percent is not None else None
        observed_text = utc_text(observed_at)
        config_hash = payload_hash(config_payload)
        performance = performance or {}
        trade_count = int(performance.get("session_trade_count") or 0)

        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO cohort_sessions (
                    cohort_id, session_date, first_observed_at, last_observed_at,
                    cycle_count, error_cycle_count, trade_count,
                    opening_equity, closing_equity, day_return,
                    config_hash, git_sha
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cohort_id, session_date) DO UPDATE SET
                    last_observed_at = excluded.last_observed_at,
                    cycle_count = cohort_sessions.cycle_count + 1,
                    error_cycle_count = cohort_sessions.error_cycle_count + excluded.error_cycle_count,
                    trade_count = MAX(cohort_sessions.trade_count, excluded.trade_count),
                    closing_equity = COALESCE(excluded.closing_equity, cohort_sessions.closing_equity),
                    day_return = COALESCE(excluded.day_return, cohort_sessions.day_return)
                """,
                (
                    COHORT_ID,
                    session_date,
                    observed_text,
                    observed_text,
                    int(bool(error)),
                    trade_count,
                    str(equity) if equity is not None else None,
                    str(equity) if equity is not None else None,
                    str(day_return) if day_return is not None else None,
                    config_hash,
                    provenance.commit_sha,
                ),
            )
            self._connection.execute(
                """
                INSERT OR IGNORE INTO decision_snapshots (
                    cohort_id, session_date, cycle_id, cycle_key, observed_at,
                    git_sha, config_hash, regime, active_bot, routed_symbol,
                    action_taken, entry_signal, entry_block_reason, day_return,
                    account_equity, error, status_json, performance_json, broker_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    COHORT_ID,
                    session_date,
                    cycle_id,
                    f"{observed_text}:{cycle_id}",
                    observed_text,
                    provenance.commit_sha,
                    config_hash,
                    status.get("regime"),
                    status.get("active_bot"),
                    status.get("routed_symbol"),
                    status.get("action_taken"),
                    int(bool(status.get("entry_signal")))
                    if status.get("entry_signal") is not None
                    else None,
                    status.get("entry_block_reason"),
                    str(day_return) if day_return is not None else None,
                    str(equity) if equity is not None else None,
                    error,
                    canonical_json(status) if status else None,
                    canonical_json(performance) if performance else None,
                    canonical_json(broker_state) if broker_state else None,
                ),
            )
            if equity is not None:
                self._connection.execute(
                    """
                    UPDATE cohort_runs
                    SET starting_equity = COALESCE(starting_equity, ?), last_equity = ?
                    WHERE cohort_id = ?
                    """,
                    (str(equity), str(equity), COHORT_ID),
                )

    def sync_lifecycle_records(self, records: Iterable[dict[str, Any]]) -> int:
        run = self.run()
        if not run:
            return 0
        try:
            launched_at = datetime.fromisoformat(
                str(run["launched_at"]).replace("Z", "+00:00")
            )
        except ValueError:
            launched_at = datetime.min.replace(tzinfo=timezone.utc)
        inserted = 0
        with self._lock, self._connection:
            for record in records:
                created_at = str(record.get("created_at") or "")
                try:
                    parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                if parsed.astimezone(timezone.utc) < launched_at.astimezone(timezone.utc):
                    continue
                event_date = session_date_text(parsed)
                event_hash = lifecycle_event_hash(record)
                operator_affected = _operator_affected(record)
                cursor = self._connection.execute(
                    """
                    INSERT OR IGNORE INTO lifecycle_events (
                        event_hash, cohort_id, session_date, created_at,
                        event_type, symbol, bot, operator_affected, event_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_hash,
                        COHORT_ID,
                        event_date,
                        created_at,
                        record.get("event_type"),
                        record.get("symbol"),
                        record.get("bot"),
                        int(operator_affected),
                        canonical_json(record),
                    ),
                )
                if cursor.rowcount:
                    inserted += 1
                    if operator_affected:
                        self._connection.execute(
                            """
                            UPDATE cohort_sessions
                            SET operator_intervention = 1
                            WHERE cohort_id = ? AND session_date = ?
                            """,
                            (COHORT_ID, event_date),
                        )
        return inserted

    def observe_shadow_trails(
        self,
        *,
        records: Iterable[dict[str, Any]],
        edgewalker_status: dict[str, Any] | None,
        observed_at: datetime,
    ) -> None:
        """Run local-only exit-doctrine shadows anchored to real autonomous fills."""
        run = self.run()
        if not run or run["status"] != COHORT_STATUS_ACTIVE:
            return
        try:
            launched_at = datetime.fromisoformat(
                str(run["launched_at"]).replace("Z", "+00:00")
            )
        except ValueError:
            return
        status = edgewalker_status or {}
        with self._lock, self._connection:
            for record in records:
                if (
                    record.get("event_type") != "FULL_FILL"
                    or str(record.get("side") or "").lower() != "buy"
                    or _operator_affected(record)
                    or record.get("dry_run") is True
                ):
                    continue
                created_at = str(record.get("created_at") or "")
                try:
                    parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                if parsed.astimezone(timezone.utc) < launched_at.astimezone(timezone.utc):
                    continue
                entry_price = decimal_or_none(record.get("filled_avg_price"))
                symbol = str(record.get("symbol") or "")
                if entry_price is None or entry_price <= 0 or not symbol:
                    continue
                entry_hash = lifecycle_event_hash(record)
                for variant_id, trail_percent in SHADOW_TRAIL_VARIANTS.items():
                    self._connection.execute(
                        """
                        INSERT OR IGNORE INTO shadow_trail_trades (
                            cohort_id, entry_event_hash, variant_id, session_date,
                            bot, symbol, entry_at, entry_price, trail_percent,
                            high_water_mark, latest_mark
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            COHORT_ID,
                            entry_hash,
                            variant_id,
                            session_date_text(parsed),
                            record.get("bot"),
                            symbol,
                            utc_text(parsed),
                            str(entry_price),
                            str(trail_percent),
                            str(entry_price),
                            str(entry_price),
                        ),
                    )

            marks = {
                "SOXL": decimal_or_none(status.get("source_price")),
                "SOXS": decimal_or_none(status.get("inverse_price")),
            }
            open_rows = self._connection.execute(
                """
                SELECT * FROM shadow_trail_trades
                WHERE cohort_id = ? AND status = 'OPEN'
                """,
                (COHORT_ID,),
            ).fetchall()
            for row in open_rows:
                mark = marks.get(row["symbol"])
                entry_price = decimal_or_none(row["entry_price"])
                prior_high = decimal_or_none(row["high_water_mark"])
                trail_percent = decimal_or_none(row["trail_percent"])
                if (
                    mark is None
                    or mark <= 0
                    or entry_price is None
                    or entry_price <= 0
                    or prior_high is None
                    or trail_percent is None
                ):
                    continue
                high_water = max(prior_high, mark)
                current_return = mark / entry_price - Decimal("1")
                mfe = max(decimal_or_none(row["mfe_return"]) or Decimal("0"), current_return)
                mae = min(decimal_or_none(row["mae_return"]) or Decimal("0"), current_return)
                stop_price = high_water * (
                    Decimal("1") - trail_percent / Decimal("100")
                )
                if mark <= stop_price:
                    self._connection.execute(
                        """
                        UPDATE shadow_trail_trades
                        SET high_water_mark = ?, latest_mark = ?,
                            mfe_return = ?, mae_return = ?, status = 'CLOSED',
                            exit_at = ?, exit_price = ?, exit_reason = 'trailing_stop',
                            realized_return = ?
                        WHERE cohort_id = ? AND entry_event_hash = ? AND variant_id = ?
                        """,
                        (
                            str(high_water),
                            str(mark),
                            str(mfe),
                            str(mae),
                            utc_text(observed_at),
                            str(mark),
                            str(current_return),
                            COHORT_ID,
                            row["entry_event_hash"],
                            row["variant_id"],
                        ),
                    )
                else:
                    self._connection.execute(
                        """
                        UPDATE shadow_trail_trades
                        SET high_water_mark = ?, latest_mark = ?,
                            mfe_return = ?, mae_return = ?
                        WHERE cohort_id = ? AND entry_event_hash = ? AND variant_id = ?
                        """,
                        (
                            str(high_water),
                            str(mark),
                            str(mfe),
                            str(mae),
                            COHORT_ID,
                            row["entry_event_hash"],
                            row["variant_id"],
                        ),
                    )

    def finalize_shadow_trails(self, completed_at: datetime) -> int:
        completed_date = session_date_text(completed_at)
        closed = 0
        with self._lock, self._connection:
            rows = self._connection.execute(
                """
                SELECT * FROM shadow_trail_trades
                WHERE cohort_id = ? AND status = 'OPEN' AND session_date <= ?
                """,
                (COHORT_ID, completed_date),
            ).fetchall()
            for row in rows:
                entry_price = decimal_or_none(row["entry_price"])
                exit_price = decimal_or_none(row["latest_mark"])
                if entry_price is None or entry_price <= 0 or exit_price is None:
                    continue
                realized_return = exit_price / entry_price - Decimal("1")
                self._connection.execute(
                    """
                    UPDATE shadow_trail_trades
                    SET status = 'CLOSED', exit_at = ?, exit_price = ?,
                        exit_reason = 'session_close', realized_return = ?
                    WHERE cohort_id = ? AND entry_event_hash = ? AND variant_id = ?
                    """,
                    (
                        utc_text(completed_at),
                        str(exit_price),
                        str(realized_return),
                        COHORT_ID,
                        row["entry_event_hash"],
                        row["variant_id"],
                    ),
                )
                closed += 1
        return closed

    def shadow_trail_metrics(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM shadow_trail_trades
                WHERE cohort_id = ? ORDER BY variant_id, entry_at
                """,
                (COHORT_ID,),
            ).fetchall()
        grouped: dict[str, list[Decimal]] = {
            variant_id: [] for variant_id in SHADOW_TRAIL_VARIANTS
        }
        open_counts = {variant_id: 0 for variant_id in SHADOW_TRAIL_VARIANTS}
        for row in rows:
            variant_id = row["variant_id"]
            if row["status"] == "OPEN":
                open_counts[variant_id] = open_counts.get(variant_id, 0) + 1
                continue
            realized = decimal_or_none(row["realized_return"])
            if realized is not None:
                grouped.setdefault(variant_id, []).append(realized)
        metrics: list[dict[str, Any]] = []
        for variant_id, trail_percent in SHADOW_TRAIL_VARIANTS.items():
            returns = grouped.get(variant_id, [])
            average = sum(returns, Decimal("0")) / len(returns) if returns else None
            metrics.append(
                {
                    "variant_id": variant_id,
                    "trail_percent": str(trail_percent),
                    "closed_trades": len(returns),
                    "open_trades": open_counts.get(variant_id, 0),
                    "wins": sum(int(value > 0) for value in returns),
                    "average_return": str(average) if average is not None else None,
                    "total_return": str(sum(returns, Decimal("0"))),
                }
            )
        return sorted(
            metrics,
            key=lambda row: decimal_or_none(row["average_return"])
            if row["average_return"] is not None
            else Decimal("-Infinity"),
            reverse=True,
        )

    def finalize_latest_session(self, completed_at: datetime) -> bool:
        run = self.run()
        if not run or run["status"] != COHORT_STATUS_ACTIVE:
            return False
        completed_date = session_date_text(completed_at)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT session_date FROM cohort_sessions
                WHERE cohort_id = ? AND completed = 0 AND session_date <= ?
                ORDER BY session_date DESC LIMIT 1
                """,
                (COHORT_ID, completed_date),
            ).fetchone()
        if not row:
            return False
        session_date = row["session_date"]
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE cohort_sessions
                SET completed = 1, completed_at = ?
                WHERE cohort_id = ? AND session_date = ?
                """,
                (utc_text(completed_at), COHORT_ID, session_date),
            )
            count = self._connection.execute(
                """
                SELECT COUNT(*) FROM cohort_sessions
                WHERE cohort_id = ? AND completed = 1
                """,
                (COHORT_ID,),
            ).fetchone()[0]
            self._append_event_locked(
                "SESSION_FINALIZED",
                {"session_date": session_date, "completed_sessions": count},
                completed_at,
            )
            if count >= PLANNED_SESSION_COUNT:
                analysis = self._formal_analysis_locked()
                self._connection.execute(
                    """
                    UPDATE cohort_runs
                    SET status = ?, completed_at = ?, analysis_json = ?
                    WHERE cohort_id = ?
                    """,
                    (
                        COHORT_STATUS_COMPLETE,
                        utc_text(completed_at),
                        canonical_json(analysis),
                        COHORT_ID,
                    ),
                )
                self._append_event_locked(
                    "COHORT_COMPLETED",
                    {"completed_sessions": count, "analysis": analysis},
                    completed_at,
                )
        return True

    def session_rows(self, *, completed_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM cohort_sessions WHERE cohort_id = ?"
        if completed_only:
            query += " AND completed = 1"
        query += " ORDER BY session_date"
        with self._lock:
            rows = self._connection.execute(query, (COHORT_ID,)).fetchall()
        return [dict(row) for row in rows]

    def _formal_analysis_locked(self) -> dict[str, Any]:
        rows = self._connection.execute(
            """
            SELECT * FROM cohort_sessions
            WHERE cohort_id = ? AND completed = 1
            ORDER BY session_date
            """,
            (COHORT_ID,),
        ).fetchall()
        returns = [
            value
            for value in (decimal_or_none(row["day_return"]) for row in rows)
            if value is not None
        ]
        bootstrap = circular_block_bootstrap_analysis(returns)
        missing_returns = len(rows) - len(returns)
        manual_sessions = sum(int(bool(row["operator_intervention"])) for row in rows)
        lower_bound = decimal_or_none(bootstrap.get("one_sided_95_lower_bound"))
        geometric = decimal_or_none(bootstrap.get("geometric_mean_daily_return"))
        run = self.run() or {}
        compromised = bool(
            missing_returns
            or manual_sessions
            or run.get("integrity_state") == "BLOCKED"
        )
        if compromised:
            conclusion = "operationally_compromised"
        elif geometric is None or geometric <= 0:
            conclusion = "failed_positive_expectancy"
        elif lower_bound is not None and lower_bound > 0:
            conclusion = (
                "aspirational_target_supported"
                if geometric >= TARGET_DAILY_RETURN
                else "strong_positive_support"
            )
        else:
            conclusion = "positive_but_inconclusive"
        return {
            "conclusion": conclusion,
            "completed_sessions": len(rows),
            "missing_return_sessions": missing_returns,
            "manual_intervention_sessions": manual_sessions,
            "bootstrap": bootstrap,
        }

    def metrics(self) -> dict[str, Any]:
        run = self.run()
        if not run:
            return {
                "cohort_id": COHORT_ID,
                "state": COHORT_STATUS_WAITING,
                "planned_sessions": PLANNED_SESSION_COUNT,
                "completed_sessions": 0,
            }
        sessions = self.session_rows(completed_only=True)
        returns = [
            value
            for value in (decimal_or_none(row.get("day_return")) for row in sessions)
            if value is not None and value > Decimal("-1")
        ]
        wealth = Decimal("1")
        peak = Decimal("1")
        max_drawdown = Decimal("0")
        positive = 0
        target_hits = 0
        for daily_return in returns:
            wealth *= Decimal("1") + daily_return
            peak = max(peak, wealth)
            if peak > 0:
                max_drawdown = min(max_drawdown, wealth / peak - Decimal("1"))
            positive += int(daily_return > 0)
            target_hits += int(daily_return >= TARGET_DAILY_RETURN)
        geometric_daily = None
        if returns and wealth > 0:
            geometric_daily = Decimal(str(math.exp(math.log(float(wealth)) / len(returns)) - 1))
        return {
            "cohort_id": COHORT_ID,
            "cohort_name": COHORT_NAME,
            "state": run["status"],
            "integrity_state": run["integrity_state"],
            "integrity_detail": run["integrity_detail"],
            "planned_sessions": run["planned_sessions"],
            "completed_sessions": len(sessions),
            "observed_sessions": len(self.session_rows()),
            "interim_sessions": list(INTERIM_SESSION_COUNTS),
            "compounded_return": str(wealth - Decimal("1")),
            "geometric_mean_daily_return": (
                str(geometric_daily) if geometric_daily is not None else None
            ),
            "max_drawdown": str(max_drawdown),
            "positive_sessions": positive,
            "one_percent_sessions": target_hits,
            "manual_intervention_sessions": sum(
                int(bool(row["operator_intervention"])) for row in sessions
            ),
            "starting_equity": run["starting_equity"],
            "last_equity": run["last_equity"],
            "launch_git_sha": run["launch_git_sha"],
            "config_hash": run["config_hash"],
            "shadow_trail_leaderboard": self.shadow_trail_metrics(),
            "formal_analysis": (
                json.loads(run["analysis_json"])
                if run.get("analysis_json")
                else None
            ),
        }

    def _append_event_locked(
        self,
        event_type: str,
        payload: dict[str, Any],
        created_at: datetime,
    ) -> None:
        record = {
            "cohort_id": COHORT_ID,
            "created_at": utc_text(created_at),
            "event_type": event_type,
            **payload,
        }
        self._connection.execute(
            """
            INSERT INTO experiment_events (
                cohort_id, created_at, event_type, event_json
            ) VALUES (?, ?, ?, ?)
            """,
            (COHORT_ID, record["created_at"], event_type, canonical_json(record)),
        )
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")


class GrowthCohortCoordinator:
    """Runtime bridge that freezes live entry eligibility without changing exits."""

    def __init__(
        self,
        ledger: GrowthCohortLedger | None = None,
        *,
        project_root: Path = PROJECT_ROOT,
        manifest_path: Path = DEFAULT_MANIFEST_PATH,
    ) -> None:
        self.ledger = ledger or GrowthCohortLedger()
        self.project_root = project_root
        self.manifest_path = manifest_path

    def _manifest(self) -> dict[str, Any] | None:
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _artifact_issues(self, manifest: dict[str, Any] | None) -> list[str]:
        if not manifest:
            return ["launch_manifest_unavailable"]
        artifacts = manifest.get("frozen_artifacts")
        if not isinstance(artifacts, dict) or not artifacts:
            return ["frozen_artifact_hashes_unavailable"]
        issues: list[str] = []
        for relative_path, expected_hash in artifacts.items():
            path = self.manifest_path.parent / str(relative_path)
            try:
                actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                issues.append(f"frozen_artifact_missing:{relative_path}")
                continue
            if actual_hash != str(expected_hash):
                issues.append(f"frozen_artifact_changed:{relative_path}")
        return issues

    def eligible(
        self,
        *,
        config_payload: dict[str, Any],
        environment: str,
        live_trading_armed: bool,
    ) -> bool:
        manifest = self._manifest()
        return bool(
            manifest
            and manifest.get("launch_authorized") is True
            and environment == "live"
            and live_trading_armed
            and config_payload.get("dry_run") is False
            and str(config_payload.get("data_feed") or "").lower() == "iex"
        )

    def entry_halt(
        self,
        *,
        config_payload: dict[str, Any],
        environment: str,
        live_trading_armed: bool,
        observed_at: datetime,
    ) -> dict[str, Any] | None:
        run = self.ledger.run()
        eligible = self.eligible(
            config_payload=config_payload,
            environment=environment,
            live_trading_armed=live_trading_armed,
        )
        if not run and not eligible:
            return None
        manifest = self._manifest()
        artifact_issues = self._artifact_issues(manifest)
        if artifact_issues and not run:
            return {
                "active": True,
                "reason": "experiment_artifact_integrity_blocked",
                "issues": artifact_issues,
            }
        provenance = git_provenance(self.project_root)
        if not run:
            manifest = manifest or {}
            if provenance.dirty or provenance.commit_sha == "unknown":
                return {
                    "active": True,
                    "reason": "experiment_launch_provenance_blocked",
                    "issues": ["production_worktree_dirty_or_unknown"],
                }
            self.ledger.start(
                launched_at=observed_at,
                environment=environment,
                data_feed=str(config_payload.get("data_feed") or ""),
                provenance=provenance,
                config_payload=config_payload,
                manifest_hash=payload_hash(manifest),
            )
            run = self.ledger.run()
        if run and run["status"] == COHORT_STATUS_COMPLETE:
            return {
                "active": True,
                "reason": "experiment_complete_entries_frozen",
            }
        issues = self.ledger.integrity_issues(
            config_payload=config_payload,
            provenance=provenance,
            environment=environment,
            data_feed=str(config_payload.get("data_feed") or ""),
        )
        issues.extend(artifact_issues)
        self.ledger.record_integrity(issues, observed_at)
        if issues:
            return {
                "active": True,
                "reason": "experiment_integrity_blocked",
                "issues": issues,
            }
        return None

    def observe_cycle(
        self,
        *,
        cycle_id: int,
        observed_at: datetime,
        config_payload: dict[str, Any],
        edgewalker_status: dict[str, Any] | None,
        performance: dict[str, Any] | None,
        broker_state: dict[str, Any] | None,
        error: str | None,
        lifecycle_records: Iterable[dict[str, Any]],
    ) -> None:
        run = self.ledger.run()
        if not run:
            return
        provenance = git_provenance(self.project_root)
        self.ledger.record_cycle(
            cycle_id=cycle_id,
            observed_at=observed_at,
            provenance=provenance,
            config_payload=config_payload,
            edgewalker_status=edgewalker_status,
            performance=performance,
            broker_state=broker_state,
            error=error,
        )
        self.ledger.sync_lifecycle_records(lifecycle_records)
        self.ledger.observe_shadow_trails(
            records=lifecycle_records,
            edgewalker_status=edgewalker_status,
            observed_at=observed_at,
        )

    def finalize_session(self, completed_at: datetime) -> bool:
        self.ledger.finalize_shadow_trails(completed_at)
        return self.ledger.finalize_latest_session(completed_at)

    def status(
        self,
        *,
        config_payload: dict[str, Any],
        environment: str,
        live_trading_armed: bool,
    ) -> dict[str, Any]:
        metrics = self.ledger.metrics()
        run = self.ledger.run()
        if not run:
            eligible = self.eligible(
                config_payload=config_payload,
                environment=environment,
                live_trading_armed=live_trading_armed,
            )
            artifact_issues = self._artifact_issues(self._manifest()) if eligible else []
            metrics["state"] = (
                COHORT_STATUS_BLOCKED
                if artifact_issues
                else "READY"
                if eligible
                else COHORT_STATUS_WAITING
            )
            metrics["integrity_state"] = "BLOCKED" if artifact_issues else "PENDING"
            metrics["integrity_detail"] = ",".join(artifact_issues) or None
        metrics["environment_required"] = "live"
        metrics["data_feed_required"] = "iex"
        metrics["target_daily_return"] = str(TARGET_DAILY_RETURN)
        metrics["objective"] = "maximum_compounded_return"
        return metrics
