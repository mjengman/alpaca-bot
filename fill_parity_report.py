from __future__ import annotations

import argparse
import csv
import json
import statistics
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from bot import (
    BotConfig,
    BotError,
    EDGEWALKER_BOTS,
    LIFECYCLE_FULL_FILL,
    LIFECYCLE_INTENDED_ENTRY,
    LIFECYCLE_INTENDED_EXIT,
    LIFECYCLE_ORDER_ACCEPTED,
    LIFECYCLE_ORDER_SUBMITTED,
    POSITION_SIZING_DYNAMIC,
    SOXL,
    SOXS,
    load_dotenv,
    parse_market_timestamp,
)
from research import (
    RESEARCH_FILL_MODEL_LIVE_AUDIT,
    RESEARCH_FILL_MODEL_NEXT_BAR_OPEN,
    RESEARCH_FILL_MODEL_STRESSED,
    ResearchFillOverride,
    ResearchRunRequest,
    fetch_historical_bars,
    run_research_backtest,
)


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_LIFECYCLE_PATH = PROJECT_ROOT / "logs" / "position_lifecycle.jsonl"
DEFAULT_LOGS_DIR = PROJECT_ROOT / "logs"
NY_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class FillAuditRow:
    date: str
    bot: str
    symbol: str
    side: str
    reason: str
    signal_at: datetime | None
    submitted_at: datetime | None
    accepted_at: datetime | None
    filled_at: datetime | None
    fill_price: Decimal | None
    filled_qty: Decimal | None
    live_price_at_signal: Decimal | None
    live_cycle_at: datetime | None
    replay_assumed_price: Decimal | None
    replay_bar_open: Decimal | None
    next_bar_open: Decimal | None
    next_bar_high: Decimal | None
    next_bar_low: Decimal | None
    next_bar_close: Decimal | None
    raw_slippage: Decimal | None
    adverse_slippage: Decimal | None
    adverse_slippage_bps: Decimal | None
    classification: str
    signal_to_submit_seconds: Decimal | None
    submit_to_accept_seconds: Decimal | None
    submit_to_fill_seconds: Decimal | None


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _date_text(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(NY_TZ).date().isoformat()


def _record_time(record: dict[str, Any]) -> datetime | None:
    return parse_market_timestamp(record.get("created_at"))


def _order(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("order")
    return value if isinstance(value, dict) else {}


def _order_id(record: dict[str, Any]) -> str | None:
    explicit = record.get("order_id")
    if explicit:
        return str(explicit)
    order = _order(record)
    value = order.get("id")
    return str(value) if value else None


def _order_time(record: dict[str, Any], field: str) -> datetime | None:
    return parse_market_timestamp(_order(record).get(field))


def _symbol(record: dict[str, Any]) -> str:
    return str(record.get("symbol") or _order(record).get("symbol") or "")


def _side(record: dict[str, Any]) -> str:
    return str(record.get("side") or _order(record).get("side") or "")


def _bot(record: dict[str, Any]) -> str:
    return str(record.get("bot") or record.get("owner") or "")


def _reason(record: dict[str, Any]) -> str:
    return str(record.get("reason") or "")


def _filled_price(record: dict[str, Any]) -> Decimal | None:
    return _decimal(record.get("filled_avg_price") or _order(record).get("filled_avg_price"))


def _filled_qty(record: dict[str, Any]) -> Decimal | None:
    return _decimal(record.get("filled_qty") or _order(record).get("filled_qty"))


def _find_signal_record(
    records: list[dict[str, Any]],
    submitted_index: int,
    submitted: dict[str, Any],
) -> dict[str, Any] | None:
    submitted_at = _record_time(submitted)
    if submitted_at is None:
        return None
    symbol = _symbol(submitted)
    side = _side(submitted)
    bot = _bot(submitted)
    allowed = {LIFECYCLE_INTENDED_ENTRY, LIFECYCLE_INTENDED_EXIT}

    for index in range(submitted_index - 1, -1, -1):
        candidate = records[index]
        if candidate.get("event_type") not in allowed:
            continue
        candidate_at = _record_time(candidate)
        if candidate_at is None:
            continue
        if submitted_at - candidate_at > timedelta(minutes=3):
            break
        if symbol and _symbol(candidate) != symbol:
            continue
        if side and _side(candidate) != side:
            continue
        candidate_bot = _bot(candidate)
        if bot and candidate_bot and candidate_bot != bot:
            continue
        return candidate
    return None


def _load_cycles(logs_dir: Path, date_text: str) -> list[dict[str, Any]]:
    rows = _read_jsonl(logs_dir / f"edgewalker-{date_text}.jsonl")
    rows.sort(
        key=lambda row: parse_market_timestamp(
            row.get("timestamp") or row.get("checked_at")
        )
        or datetime.min.replace(tzinfo=timezone.utc)
    )
    return rows


def _cycle_time(record: dict[str, Any]) -> datetime | None:
    return parse_market_timestamp(record.get("timestamp") or record.get("checked_at"))


def _cycle_price(record: dict[str, Any], symbol: str) -> Decimal | None:
    if symbol == SOXS:
        for key in ("inverse_price", "position_current_price"):
            if key == "position_current_price" and record.get("position_symbol") != SOXS:
                continue
            value = _decimal(record.get(key))
            if value is not None:
                return value
        return None

    for key in ("source_price", "price", "position_current_price"):
        if key == "position_current_price" and record.get("position_symbol") != SOXL:
            continue
        value = _decimal(record.get(key))
        if value is not None:
            return value
    return None


def _latest_cycle_at_or_before(
    cycles: list[dict[str, Any]],
    at: datetime | None,
) -> dict[str, Any] | None:
    if at is None:
        return None
    best: dict[str, Any] | None = None
    for cycle in cycles:
        cycle_at = _cycle_time(cycle)
        if cycle_at is None:
            continue
        if cycle_at <= at:
            best = cycle
            continue
        break
    return best


def _bar_decimal(bar: dict[str, Any] | None, key: str) -> Decimal | None:
    if not bar:
        return None
    return _decimal(bar.get(key))


def _next_bar_after(
    bars: list[dict[str, Any]],
    at: datetime | None,
) -> dict[str, Any] | None:
    if at is None:
        return None
    for bar in bars:
        bar_at = parse_market_timestamp(bar.get("t"))
        if bar_at is not None and bar_at > at:
            return bar
    return None


def _bar_at_or_before(
    bars: list[dict[str, Any]],
    at: datetime | None,
) -> dict[str, Any] | None:
    if at is None:
        return None
    best: dict[str, Any] | None = None
    for bar in bars:
        bar_at = parse_market_timestamp(bar.get("t"))
        if bar_at is None:
            continue
        if bar_at <= at:
            best = bar
            continue
        break
    return best


def classify_slippage(adverse_bps: Decimal | None) -> str:
    if adverse_bps is None:
        return "unknown"
    if adverse_bps < 0:
        return "favorable"
    if adverse_bps <= Decimal("10"):
        return "normal"
    if adverse_bps <= Decimal("50"):
        return "adverse"
    return "catastrophic"


def _duration_seconds(start: datetime | None, end: datetime | None) -> Decimal | None:
    if start is None or end is None:
        return None
    return Decimal(str((end - start).total_seconds())).quantize(Decimal("0.001"))


def build_fill_audit(
    *,
    lifecycle_path: Path,
    logs_dir: Path,
    config: BotConfig,
    start_date: str | None,
    end_date: str | None,
    dates: set[str] | None,
) -> list[FillAuditRow]:
    lifecycle_records = _read_jsonl(lifecycle_path)
    lifecycle_records.sort(key=lambda row: _record_time(row) or datetime.min.replace(tzinfo=timezone.utc))

    fills_by_order: dict[str, dict[str, Any]] = {}
    accepted_by_order: dict[str, dict[str, Any]] = {}
    for record in lifecycle_records:
        order_id = _order_id(record)
        if not order_id:
            continue
        event_type = record.get("event_type")
        if event_type == LIFECYCLE_ORDER_ACCEPTED:
            accepted_by_order.setdefault(order_id, record)
        if event_type == LIFECYCLE_FULL_FILL:
            fills_by_order[order_id] = record

    bars_cache: dict[str, dict[str, list[dict[str, Any]]]] = {}
    cycles_cache: dict[str, list[dict[str, Any]]] = {}
    rows: list[FillAuditRow] = []

    for index, submitted in enumerate(lifecycle_records):
        if submitted.get("event_type") != LIFECYCLE_ORDER_SUBMITTED:
            continue
        order_id = _order_id(submitted)
        fill = fills_by_order.get(order_id or "")
        if fill is None:
            continue
        submitted_at = _order_time(submitted, "submitted_at") or _record_time(submitted)
        fill_at = _order_time(fill, "filled_at") or _record_time(fill)
        date_text = _date_text(fill_at or submitted_at)
        if dates and date_text not in dates:
            continue
        if start_date and date_text < start_date:
            continue
        if end_date and date_text > end_date:
            continue

        if date_text not in bars_cache:
            bars_cache[date_text] = fetch_historical_bars(config, (SOXL, SOXS), date_text)
        if date_text not in cycles_cache:
            cycles_cache[date_text] = _load_cycles(logs_dir, date_text)

        signal = _find_signal_record(lifecycle_records, index, submitted)
        signal_at = _record_time(signal) if signal else submitted_at
        symbol = _symbol(fill or submitted)
        side = _side(fill or submitted)
        accepted = accepted_by_order.get(order_id or "")
        accepted_at = _order_time(accepted or {}, "updated_at") or _record_time(accepted or {})
        fill_price = _filled_price(fill)
        symbol_bars = bars_cache[date_text].get(symbol, [])
        replay_bar = _bar_at_or_before(symbol_bars, signal_at)
        next_bar = _next_bar_after(symbol_bars, signal_at)
        replay_price = _bar_decimal(replay_bar, "o")
        cycle = _latest_cycle_at_or_before(cycles_cache[date_text], signal_at)
        live_price = _cycle_price(cycle, symbol) if cycle else None
        cycle_at = _cycle_time(cycle) if cycle else None

        raw_slippage = None
        adverse_slippage = None
        adverse_bps = None
        if fill_price is not None and replay_price is not None:
            raw_slippage = fill_price - replay_price
            adverse_slippage = raw_slippage if side == "buy" else -raw_slippage
            if replay_price != 0:
                adverse_bps = (adverse_slippage / replay_price * Decimal("10000"))

        rows.append(
            FillAuditRow(
                date=date_text,
                bot=_bot(fill or submitted),
                symbol=symbol,
                side=side,
                reason=_reason(fill or submitted),
                signal_at=signal_at,
                submitted_at=submitted_at,
                accepted_at=accepted_at,
                filled_at=fill_at,
                fill_price=fill_price,
                filled_qty=_filled_qty(fill),
                live_price_at_signal=live_price,
                live_cycle_at=cycle_at,
                replay_assumed_price=replay_price,
                replay_bar_open=_bar_decimal(replay_bar, "o"),
                next_bar_open=_bar_decimal(next_bar, "o"),
                next_bar_high=_bar_decimal(next_bar, "h"),
                next_bar_low=_bar_decimal(next_bar, "l"),
                next_bar_close=_bar_decimal(next_bar, "c"),
                raw_slippage=raw_slippage,
                adverse_slippage=adverse_slippage,
                adverse_slippage_bps=adverse_bps,
                classification=classify_slippage(adverse_bps),
                signal_to_submit_seconds=_duration_seconds(signal_at, submitted_at),
                submit_to_accept_seconds=_duration_seconds(submitted_at, accepted_at),
                submit_to_fill_seconds=_duration_seconds(submitted_at, fill_at),
            )
        )
    return rows


def _fmt_decimal(value: Decimal | None, places: int = 2) -> str:
    if value is None:
        return "--"
    quant = Decimal("1").scaleb(-places)
    return f"{value.quantize(quant):f}"


def _fmt_time(value: datetime | None) -> str:
    if value is None:
        return "--"
    return value.astimezone(NY_TZ).strftime("%H:%M:%S")


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print(" | ".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))


def print_audit(rows: list[FillAuditRow]) -> None:
    headers = [
        "date",
        "bot",
        "sym",
        "side",
        "reason",
        "signal",
        "fill",
        "lat_s",
        "live_px",
        "replay_px",
        "next_px",
        "fill_px",
        "adv_bps",
        "class",
    ]
    table = [
        [
            row.date,
            row.bot.replace("Bot", ""),
            row.symbol,
            row.side,
            row.reason,
            _fmt_time(row.signal_at),
            _fmt_time(row.filled_at),
            _fmt_decimal(row.submit_to_fill_seconds, 3),
            _fmt_decimal(row.live_price_at_signal, 4),
            _fmt_decimal(row.replay_assumed_price, 4),
            _fmt_decimal(row.next_bar_open, 4),
            _fmt_decimal(row.fill_price, 4),
            _fmt_decimal(row.adverse_slippage_bps, 1),
            row.classification,
        ]
        for row in rows
    ]
    _print_table(headers, table)


def print_slippage_summary(rows: list[FillAuditRow]) -> None:
    values = [row.adverse_slippage_bps for row in rows if row.adverse_slippage_bps is not None]
    adverse = [value for value in values if value > 0]
    print()
    print("Slippage summary")
    print(f"- audited fills: {len(rows)}")
    print(f"- adverse fills: {len(adverse)}")
    if adverse:
        sorted_values = sorted(adverse)
        p95_index = min(len(sorted_values) - 1, round((len(sorted_values) - 1) * 0.95))
        print(f"- median adverse bps: {_fmt_decimal(Decimal(str(statistics.median(adverse))), 1)}")
        print(f"- p95 adverse bps: {_fmt_decimal(sorted_values[p95_index], 1)}")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.classification] = counts.get(row.classification, 0) + 1
    print(f"- classifications: {counts}")


def _load_live_summary(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return {
            row.get("date", ""): row
            for row in reader
            if row.get("date")
        }


def _starting_value_for_date(
    live_rows: dict[str, dict[str, str]],
    date_text: str,
) -> Decimal:
    current = live_rows.get(date_text) or {}
    starting_value = _decimal(current.get("starting_account_value"))
    if starting_value is not None and starting_value > 0:
        return starting_value

    prior_dates = [date for date in live_rows if date < date_text]
    for prior_date in sorted(prior_dates, reverse=True):
        prior_ending = _decimal(live_rows[prior_date].get("ending_account_value"))
        if prior_ending is not None and prior_ending > 0:
            return prior_ending

    ending_value = _decimal(current.get("ending_account_value"))
    if ending_value is not None and ending_value > 0:
        return ending_value
    return Decimal("100000")


def _fill_overrides_for_date(
    rows: list[FillAuditRow],
    date_text: str,
) -> tuple[ResearchFillOverride, ...]:
    overrides: list[ResearchFillOverride] = []
    for row in rows:
        if row.date != date_text or row.fill_price is None:
            continue
        overrides.append(
            ResearchFillOverride(
                symbol=row.symbol,
                side=row.side,
                price=row.fill_price,
                filled_at=row.filled_at,
            )
        )
    return tuple(overrides)


def print_replay_comparison(
    *,
    config: BotConfig,
    summary_path: Path,
    dates: list[str],
    audit_rows: list[FillAuditRow],
    stressed_bps: Decimal,
    stressed_cents: Decimal,
) -> None:
    live_rows = _load_live_summary(summary_path)
    table: list[list[str]] = []
    for date_text in dates:
        live = live_rows.get(date_text)
        if not live:
            continue
        starting_value = _starting_value_for_date(live_rows, date_text)
        live_pl = _decimal(live.get("realized_pl_dollars")) or Decimal("0")
        default = run_research_backtest(
            config,
            ResearchRunRequest(
                date=date_text,
                data_feed=config.data_feed,
                starting_account_value=starting_value,
                fill_model=RESEARCH_FILL_MODEL_NEXT_BAR_OPEN,
            ),
        )
        stressed = run_research_backtest(
            config,
            ResearchRunRequest(
                date=date_text,
                data_feed=config.data_feed,
                starting_account_value=starting_value,
                fill_model=RESEARCH_FILL_MODEL_STRESSED,
                slippage_bps=stressed_bps,
                slippage_cents=stressed_cents,
            ),
        )
        live_audit = run_research_backtest(
            config,
            ResearchRunRequest(
                date=date_text,
                data_feed=config.data_feed,
                starting_account_value=starting_value,
                fill_model=RESEARCH_FILL_MODEL_LIVE_AUDIT,
                fill_overrides=_fill_overrides_for_date(audit_rows, date_text),
            ),
        )
        default_pl = _decimal(default["row"].get("realized_pl_dollars")) or Decimal("0")
        stressed_pl = _decimal(stressed["row"].get("realized_pl_dollars")) or Decimal("0")
        live_audit_pl = (
            _decimal(live_audit["row"].get("realized_pl_dollars")) or Decimal("0")
        )
        table.append(
            [
                date_text,
                _fmt_decimal(live_pl),
                _fmt_decimal(default_pl),
                _fmt_decimal(stressed_pl),
                _fmt_decimal(live_audit_pl),
                _fmt_decimal(default_pl - live_pl),
                _fmt_decimal(stressed_pl - live_pl),
                _fmt_decimal(live_audit_pl - live_pl),
                str(live.get("closed_trades") or ""),
                str(default["row"].get("closed_trades") or ""),
                str(stressed["row"].get("closed_trades") or ""),
                str(live_audit["row"].get("closed_trades") or ""),
            ]
        )
    if not table:
        return
    print()
    print(
        f"Replay comparison (stressed={_fmt_decimal(stressed_bps, 1)} bps, "
        f"{_fmt_decimal(stressed_cents, 2)} cents)"
    )
    _print_table(
        [
            "date",
            "live_pl",
            "default_pl",
            "stressed_pl",
            "audit_fill_pl",
            "default_gap",
            "stressed_gap",
            "audit_gap",
            "live_tr",
            "def_tr",
            "str_tr",
            "audit_tr",
        ],
        table,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit live fills against replay next-bar assumptions.",
    )
    parser.add_argument("--lifecycle", type=Path, default=DEFAULT_LIFECYCLE_PATH)
    parser.add_argument("--logs-dir", type=Path, default=DEFAULT_LOGS_DIR)
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--dates", default=None, help="Comma-separated YYYY-MM-DD list.")
    parser.add_argument("--summary-tsv", type=Path, default=None)
    parser.add_argument("--stressed-bps", type=Decimal, default=Decimal("0"))
    parser.add_argument("--stressed-cents", type=Decimal, default=Decimal("0"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    config = replace(
        BotConfig.from_env(),
        data_feed="iex",
        enabled_bots=EDGEWALKER_BOTS,
        position_sizing_mode=POSITION_SIZING_DYNAMIC,
        position_allocation_percent=Decimal("95"),
        position_notional=Decimal("25"),
    )
    requested_dates = (
        {item.strip() for item in str(args.dates).split(",") if item.strip()}
        if args.dates
        else None
    )
    rows = build_fill_audit(
        lifecycle_path=args.lifecycle,
        logs_dir=args.logs_dir,
        config=config,
        start_date=args.start,
        end_date=args.end,
        dates=requested_dates,
    )
    print_audit(rows)
    print_slippage_summary(rows)
    if args.summary_tsv:
        comparison_dates = sorted(requested_dates or {row.date for row in rows})
        print_replay_comparison(
            config=config,
            summary_path=args.summary_tsv,
            dates=comparison_dates,
            audit_rows=rows,
            stressed_bps=args.stressed_bps,
            stressed_cents=args.stressed_cents,
        )


if __name__ == "__main__":
    try:
        main()
    except BotError as exc:
        raise SystemExit(str(exc)) from exc
