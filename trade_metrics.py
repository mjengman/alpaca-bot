from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from bot import (
    LIFECYCLE_FULL_FILL,
    LIFECYCLE_PARTIAL_FILL,
    LIFECYCLE_POSITION_MANAGED,
    format_decimal,
    parse_market_timestamp,
)


NY_TZ = ZoneInfo("America/New_York")


def analyze_lifecycle_trades(
    records: list[dict[str, Any]],
    session_date: str,
    *,
    session_tz: ZoneInfo = NY_TZ,
) -> dict[str, Any]:
    lots_by_symbol: dict[str, list[dict[str, Any]]] = {}
    realized_trades: list[dict[str, Any]] = []
    unmatched_exit_qty = Decimal("0")
    ignored_fill_count = 0

    for record in records:
        if record.get("event_type") not in {
            LIFECYCLE_PARTIAL_FILL,
            LIFECYCLE_FULL_FILL,
        }:
            continue
        created_at = record_created_at(record)
        if created_at is None or ny_date_text(created_at, session_tz) != session_date:
            continue

        symbol = record.get("symbol")
        side = str(record.get("side") or "").lower()
        fill_qty = record_decimal(record, "fill_delta_qty") or record_decimal(
            record,
            "filled_qty",
        )
        fill_price = record_decimal(record, "filled_avg_price")
        if not isinstance(symbol, str) or side not in {"buy", "sell"}:
            ignored_fill_count += 1
            continue
        if fill_qty is None or fill_qty <= 0 or fill_price is None:
            ignored_fill_count += 1
            continue

        if side == "buy":
            lots_by_symbol.setdefault(symbol, []).append(
                {
                    "qty": fill_qty,
                    "price": fill_price,
                    "bot": record.get("bot"),
                    "created_at": created_at,
                    "order_id": record.get("order_id"),
                }
            )
            continue

        remaining = fill_qty
        matched_qty = Decimal("0")
        cost_basis = Decimal("0")
        matched_lot_bots: list[tuple[str | None, Decimal]] = []
        matched_entry_times: list[datetime] = []
        matched_entry_order_ids: list[str] = []
        lots = lots_by_symbol.setdefault(symbol, [])
        while remaining > 0 and lots:
            lot = lots[0]
            lot_qty = lot["qty"]
            consumed_qty = min(remaining, lot_qty)
            matched_qty += consumed_qty
            cost_basis += consumed_qty * lot["price"]
            matched_lot_bots.append((optional_text(lot.get("bot")), consumed_qty))
            created_at_value = lot.get("created_at")
            if isinstance(created_at_value, datetime):
                matched_entry_times.append(created_at_value)
            order_id = optional_text(lot.get("order_id"))
            if order_id:
                matched_entry_order_ids.append(order_id)
            remaining -= consumed_qty
            lot["qty"] = lot_qty - consumed_qty
            if lot["qty"] <= 0:
                lots.pop(0)

        if matched_qty <= 0:
            unmatched_exit_qty += remaining
            continue

        unmatched_exit_qty += max(remaining, Decimal("0"))
        proceeds = matched_qty * fill_price
        realized_pl = proceeds - cost_basis
        avg_entry_price = cost_basis / matched_qty
        realized_pl_percent = (
            realized_pl / cost_basis * Decimal("100")
            if cost_basis > 0
            else None
        )
        entry_at = min(matched_entry_times) if matched_entry_times else created_at
        trade = {
            "symbol": symbol,
            "bot": optional_text(record.get("bot")) or dominant_bot(matched_lot_bots),
            "qty": format_decimal(matched_qty),
            "avg_entry_price": format_decimal(avg_entry_price),
            "exit_price": format_decimal(fill_price),
            "realized_pl": format_decimal(realized_pl),
            "realized_pl_percent": (
                format_decimal(realized_pl_percent)
                if realized_pl_percent is not None
                else None
            ),
            "entry_order_id": matched_entry_order_ids[0]
            if matched_entry_order_ids
            else None,
            "entry_order_ids": matched_entry_order_ids,
            "exit_reason": record.get("reason"),
            "exit_order_id": record.get("order_id"),
            "opened_at": entry_at.isoformat(timespec="seconds"),
            "closed_at": created_at.isoformat(timespec="seconds"),
        }
        enrich_trade_with_price_points(
            trade,
            price_points_for_trade(
                records,
                symbol=symbol,
                entry_at=entry_at,
                exit_at=created_at,
            ),
            source="managed_mark",
        )
        realized_trades.append(trade)

    open_qty = sum(
        (lot["qty"] for lots in lots_by_symbol.values() for lot in lots),
        Decimal("0"),
    )
    open_cost_basis = sum(
        (lot["qty"] * lot["price"] for lots in lots_by_symbol.values() for lot in lots),
        Decimal("0"),
    )

    return {
        "realized_trades": realized_trades,
        "open_qty": open_qty,
        "open_cost_basis": open_cost_basis,
        "unmatched_exit_qty": unmatched_exit_qty,
        "ignored_fill_count": ignored_fill_count,
    }


def price_points_for_trade(
    records: list[dict[str, Any]],
    *,
    symbol: str,
    entry_at: datetime,
    exit_at: datetime,
) -> list[Decimal]:
    points: list[Decimal] = []
    for record in records:
        if record.get("event_type") != LIFECYCLE_POSITION_MANAGED:
            continue
        if record.get("symbol") != symbol:
            continue
        created_at = record_created_at(record)
        if created_at is None or created_at < entry_at or created_at > exit_at:
            continue
        current_price = record_decimal(record, "current_price")
        if current_price is not None:
            points.append(current_price)
    return points


def enrich_trade_with_price_points(
    trade: dict[str, Any],
    price_points: list[Decimal],
    *,
    source: str,
) -> dict[str, Any]:
    qty = Decimal(str(trade.get("qty") or 0))
    entry_price = Decimal(str(trade.get("avg_entry_price") or 0))
    exit_price = Decimal(str(trade.get("exit_price") or 0))
    realized_pl = Decimal(str(trade.get("realized_pl") or 0))
    points = [entry_price, exit_price, *price_points]
    high_price = max(points) if points else entry_price
    low_price = min(points) if points else entry_price
    mfe_pl = max(high_price - entry_price, Decimal("0")) * qty
    mae_pl = min(low_price - entry_price, Decimal("0")) * qty
    mfe_percent = (
        max(high_price - entry_price, Decimal("0")) / entry_price * Decimal("100")
        if entry_price > 0
        else None
    )
    mae_percent = (
        min(low_price - entry_price, Decimal("0")) / entry_price * Decimal("100")
        if entry_price > 0
        else None
    )
    capture_ratio = (
        realized_pl / mfe_pl * Decimal("100")
        if mfe_pl > 0
        else None
    )
    opened_at = parse_market_timestamp(trade.get("opened_at"))
    closed_at = parse_market_timestamp(trade.get("closed_at"))
    hold_seconds = None
    if opened_at is not None and closed_at is not None:
        hold_seconds = max((closed_at - opened_at).total_seconds(), 0)

    trade.update(
        {
            "mfe_price": format_decimal(high_price),
            "mae_price": format_decimal(low_price),
            "mfe_pl": format_decimal(mfe_pl),
            "mae_pl": format_decimal(mae_pl),
            "mfe_percent": (
                format_decimal(mfe_percent) if mfe_percent is not None else None
            ),
            "mae_percent": (
                format_decimal(mae_percent) if mae_percent is not None else None
            ),
            "capture_ratio_percent": (
                format_decimal(capture_ratio) if capture_ratio is not None else None
            ),
            "hold_seconds": hold_seconds,
            "mfe_mae_source": source if price_points else "fill_prices_only",
        }
    )
    return trade


def enrich_trades_with_bar_extremes(
    trades: list[dict[str, Any]],
    bars_by_symbol: dict[str, list[dict[str, Any]]],
    *,
    source: str = "research_completed_bar_high_low",
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for trade in trades:
        trade_copy = dict(trade)
        symbol = optional_text(trade_copy.get("symbol"))
        opened_at = parse_market_timestamp(trade_copy.get("opened_at"))
        closed_at = parse_market_timestamp(trade_copy.get("closed_at"))
        if not symbol or opened_at is None or closed_at is None:
            enriched.append(trade_copy)
            continue
        points: list[Decimal] = []
        for bar in bars_by_symbol.get(symbol, []):
            bar_at = parse_market_timestamp(bar.get("t"))
            if bar_at is None or bar_at < opened_at or bar_at >= closed_at:
                continue
            high = decimal_from_bar(bar, "h")
            low = decimal_from_bar(bar, "l")
            if high is not None:
                points.append(high)
            if low is not None:
                points.append(low)
        enrich_trade_with_price_points(trade_copy, points, source=source)
        enriched.append(trade_copy)
    return enriched


def decimal_from_bar(bar: dict[str, Any], key: str) -> Decimal | None:
    raw = bar.get(key)
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except Exception:
        return None


def trade_quality_averages(trades: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "avg_mfe_percent": average_decimal_field(trades, "mfe_percent"),
        "avg_mae_percent": average_decimal_field(trades, "mae_percent"),
        "avg_capture_ratio_percent": average_decimal_field(
            trades,
            "capture_ratio_percent",
        ),
        "avg_hold_seconds": average_decimal_field(trades, "hold_seconds"),
    }


def bot_archaeology_report(
    trades: list[dict[str, Any]],
    bot_name: str,
) -> dict[str, Any]:
    bot_trades = [trade for trade in trades if optional_text(trade.get("bot")) == bot_name]
    exit_reasons: dict[str, dict[str, Any]] = {}
    near_zero_mfe = 0
    meaningful_mfe_low_capture = 0
    larger_adverse_than_favorable = 0
    for trade in bot_trades:
        reason = optional_text(trade.get("exit_reason")) or "UNKNOWN"
        bucket = exit_reasons.setdefault(
            reason,
            {
                "count": 0,
                "realized_pl": Decimal("0"),
            },
        )
        bucket["count"] += 1
        bucket["realized_pl"] += Decimal(str(trade.get("realized_pl") or 0))
        mfe_percent = decimal_from_value(trade.get("mfe_percent"))
        mae_percent = decimal_from_value(trade.get("mae_percent"))
        capture_ratio = decimal_from_value(trade.get("capture_ratio_percent"))
        if mfe_percent is not None and mfe_percent <= Decimal("0.10"):
            near_zero_mfe += 1
        if (
            mfe_percent is not None
            and mfe_percent > Decimal("0.10")
            and capture_ratio is not None
            and capture_ratio < Decimal("25")
        ):
            meaningful_mfe_low_capture += 1
        if (
            mfe_percent is not None
            and mae_percent is not None
            and abs(mae_percent) > mfe_percent
        ):
            larger_adverse_than_favorable += 1

    hypotheses = ranked_archaeology_hypotheses(
        bot_name,
        len(bot_trades),
        near_zero_mfe,
        meaningful_mfe_low_capture,
        larger_adverse_than_favorable,
    )
    return {
        "bot": bot_name,
        "trade_count": len(bot_trades),
        "quality": trade_quality_averages(bot_trades),
        "near_zero_mfe_count": near_zero_mfe,
        "meaningful_mfe_low_capture_count": meaningful_mfe_low_capture,
        "larger_adverse_than_favorable_count": larger_adverse_than_favorable,
        "exit_reasons": {
            reason: {
                "count": value["count"],
                "realized_pl": format_decimal(value["realized_pl"]),
            }
            for reason, value in sorted(exit_reasons.items())
        },
        "hypotheses": hypotheses,
    }


def ranked_archaeology_hypotheses(
    bot_name: str,
    trade_count: int,
    near_zero_mfe: int,
    meaningful_mfe_low_capture: int,
    larger_adverse_than_favorable: int,
) -> list[dict[str, Any]]:
    if trade_count <= 0:
        return [
            {
                "rank": 1,
                "hypothesis": f"{bot_name} had no closed trades to evaluate.",
                "evidence": "trade_count=0",
            }
        ]

    candidates = [
        (
            near_zero_mfe,
            f"{bot_name} entries may be failing because the thesis never develops.",
            f"near_zero_mfe_count={near_zero_mfe}/{trade_count}",
        ),
        (
            meaningful_mfe_low_capture,
            f"{bot_name} entries may find favorable movement but fail to capture it.",
            (
                "meaningful_mfe_low_capture_count="
                f"{meaningful_mfe_low_capture}/{trade_count}"
            ),
        ),
        (
            larger_adverse_than_favorable,
            (
                f"{bot_name} entries may experience adverse movement that is larger "
                "than their favorable excursion."
            ),
            (
                "larger_adverse_than_favorable_count="
                f"{larger_adverse_than_favorable}/{trade_count}"
            ),
        ),
    ]
    ranked = [
        {
            "rank": rank,
            "hypothesis": hypothesis,
            "evidence": evidence,
        }
        for rank, (_score, hypothesis, evidence) in enumerate(
            sorted(candidates, key=lambda item: item[0], reverse=True),
            start=1,
        )
    ]
    return ranked


def average_decimal_field(
    rows: list[dict[str, Any]],
    field_name: str,
) -> str | None:
    values: list[Decimal] = []
    for row in rows:
        value = row.get(field_name)
        if value in (None, ""):
            continue
        try:
            values.append(Decimal(str(value)))
        except Exception:
            continue
    if not values:
        return None
    return format_decimal(sum(values, Decimal("0")) / Decimal(len(values)))


def decimal_from_value(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def record_created_at(record: dict[str, Any]) -> datetime | None:
    return parse_market_timestamp(record.get("created_at"))


def ny_date_text(value: datetime, tz: ZoneInfo = NY_TZ) -> str:
    return value.astimezone(tz).date().isoformat()


def record_decimal(record: dict[str, Any], field_name: str) -> Decimal | None:
    raw = record.get(field_name)
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except Exception:
        return None


def optional_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def dominant_bot(items: list[tuple[str | None, Decimal]]) -> str | None:
    totals: dict[str, Decimal] = {}
    for bot, qty in items:
        if not bot:
            continue
        totals[bot] = totals.get(bot, Decimal("0")) + qty
    if not totals:
        return None
    return max(totals.items(), key=lambda item: item[1])[0]
