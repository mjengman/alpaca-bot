#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


TRADING_BASE_URL_DEFAULT = "https://paper-api.alpaca.markets/v2"
LIVE_TRADING_BASE_URL_DEFAULT = "https://api.alpaca.markets/v2"
DATA_BASE_URL_DEFAULT = "https://data.alpaca.markets/v2"
STATE_PATH_DEFAULT = Path(__file__).resolve().with_name(".bot_state.json")
LIFECYCLE_PATH_DEFAULT = (
    Path(__file__).resolve().with_name("logs") / "position_lifecycle.jsonl"
)
FRACTIONAL_QTY_STEP = Decimal("0.000000001")
MARKET_DATA_MAX_AGE_SECONDS = 90
SOXL = "SOXL"
SOXS = "SOXS"
WARMUP = "WARMUP"
UPTREND = "UPTREND"
SIDEWAYS = "SIDEWAYS"
DOWNTREND = "DOWNTREND"
DIRECTIONAL_MODE_CONSERVATIVE = "CONSERVATIVE"
DIRECTIONAL_MODE_BALANCED = "BALANCED"
DIRECTIONAL_MODE_AGGRESSIVE = "AGGRESSIVE"
DIRECTIONAL_MODE_ADAPTIVE = "ADAPTIVE"
DIRECTIONAL_MODES = {
    DIRECTIONAL_MODE_CONSERVATIVE,
    DIRECTIONAL_MODE_BALANCED,
    DIRECTIONAL_MODE_AGGRESSIVE,
    DIRECTIONAL_MODE_ADAPTIVE,
}
CHOP_PERMISSION_MODE_OFF = "OFF"
CHOP_PERMISSION_MODE_LOOSE = "LOOSE"
CHOP_PERMISSION_MODE_STRICT = "STRICT"
CHOP_PERMISSION_MODE_FIREWALL = "FIREWALL"
CHOP_PERMISSION_MODES = {
    CHOP_PERMISSION_MODE_OFF,
    CHOP_PERMISSION_MODE_LOOSE,
    CHOP_PERMISSION_MODE_STRICT,
    CHOP_PERMISSION_MODE_FIREWALL,
}
CHOP_PERMISSION_MAX_ABS_SOURCE_PERCENT = Decimal("2.00")
CHOP_PERMISSION_FIREWALL_MAX_DRAWDOWN_PERCENT = Decimal("-5.00")
CHOP_PERMISSION_FIREWALL_NEAR_MOMENTUM_MIN_TRUST_SCORE = 64
CHOP_PERMISSION_FIREWALL_NEAR_MOMENTUM_MIN_SOURCE_PERCENT = Decimal("2.50")
INVERSE_CASCADE_MODE_OFF = "OFF"
INVERSE_CASCADE_MODE_LOOSE = "LOOSE"
INVERSE_CASCADE_MODE_STRICT = "STRICT"
INVERSE_CASCADE_MODE_VELOCITY = "VELOCITY"
INVERSE_CASCADE_MODE_SUSTAINED = "SUSTAINED"
INVERSE_CASCADE_MODES = {
    INVERSE_CASCADE_MODE_OFF,
    INVERSE_CASCADE_MODE_LOOSE,
    INVERSE_CASCADE_MODE_STRICT,
    INVERSE_CASCADE_MODE_VELOCITY,
    INVERSE_CASCADE_MODE_SUSTAINED,
}
INVERSE_CASCADE_DEFAULTS = {
    INVERSE_CASCADE_MODE_LOOSE: {
        "source_current_max": Decimal("-1.50"),
        "source_drawdown_max": Decimal("-2.50"),
        "inverse_current_min": Decimal("1.00"),
        "source_recovery_max": Decimal("2.50"),
    },
    INVERSE_CASCADE_MODE_STRICT: {
        "source_current_max": Decimal("-2.50"),
        "source_drawdown_max": Decimal("-4.00"),
        "inverse_current_min": Decimal("2.00"),
        "source_recovery_max": Decimal("1.50"),
    },
    INVERSE_CASCADE_MODE_VELOCITY: {
        "source_current_max": Decimal("-1.50"),
        "source_drawdown_max": Decimal("-2.50"),
        "inverse_current_min": Decimal("1.00"),
        "source_recovery_max": Decimal("2.00"),
        "source_velocity_max": Decimal("-1.00"),
    },
    INVERSE_CASCADE_MODE_SUSTAINED: {
        "source_current_max": Decimal("-2.75"),
        "source_drawdown_max": Decimal("-4.00"),
        "inverse_current_min": Decimal("2.75"),
        "source_recovery_max": Decimal("1.25"),
        "source_velocity_max": Decimal("-1.25"),
        "block_source_uptrend": False,
        "sustain_source_current_max": Decimal("-2.50"),
        "sustain_source_window_start_min": Decimal("-9.00"),
        "sustain_source_prior_close_max": Decimal("-3.00"),
        "sustain_inverse_current_min": Decimal("2.25"),
        "sustain_source_deepening_min": Decimal("0.50"),
        "sustain_source_new_low_count_min": 2,
        "reset_source_current_min": Decimal("-0.50"),
    },
}
INVERSE_CASCADE_VELOCITY_WINDOW_MINUTES = 10
INVERSE_CASCADE_SUSTAIN_MINUTES = 5
INVERSE_CASCADE_TRAIL_PERCENT = Decimal("3.50")
INVERSE_CASCADE_ROUTE_INVALIDATION_GRACE_MINUTES = 5
INVERSE_CASCADE_PROVEN_MFE_PERCENT = Decimal("0.50")
INVERSE_CASCADE_PROVEN_TRAIL_PERCENT = Decimal("6.00")
INVERSE_CASCADE_PROVEN_TRAIL_TIGHTEN_MFE_PERCENT = Decimal("4.00")
INVERSE_CASCADE_PROVEN_ROUTE_RECOVERY_MIN_SOURCE_PERCENT = Decimal("0.00")
REGIME_STRENGTH_RANGE = "RANGE"
REGIME_STRENGTH_WEAK = "WEAK"
REGIME_STRENGTH_MODERATE = "MODERATE"
REGIME_STRENGTH_STRONG = "STRONG"
REGIME_STRENGTHS = {
    REGIME_STRENGTH_WEAK,
    REGIME_STRENGTH_MODERATE,
    REGIME_STRENGTH_STRONG,
}
REGIME_STRENGTH_ORDER = {
    REGIME_STRENGTH_WEAK: 1,
    REGIME_STRENGTH_MODERATE: 2,
    REGIME_STRENGTH_STRONG: 3,
}
MOMENTUM_BOT = "MomentumBot"
CHOP_BOT = "ChopBot"
INVERSE_BOT = "InverseBot"
EDGEWALKER_BOTS = (MOMENTUM_BOT, CHOP_BOT, INVERSE_BOT)
POSITION_SIZING_FIXED = "FIXED"
POSITION_SIZING_DYNAMIC = "DYNAMIC"
POSITION_SIZING_MODES = {
    POSITION_SIZING_FIXED,
    POSITION_SIZING_DYNAMIC,
}
LIFECYCLE_INTENDED_ENTRY = "INTENDED_ENTRY"
LIFECYCLE_INTENDED_EXIT = "INTENDED_EXIT"
LIFECYCLE_ORDER_SUBMITTED = "ORDER_SUBMITTED"
LIFECYCLE_ORDER_REJECTED = "ORDER_REJECTED"
LIFECYCLE_ORDER_ACCEPTED = "ORDER_ACCEPTED"
LIFECYCLE_PARTIAL_FILL = "PARTIAL_FILL"
LIFECYCLE_FULL_FILL = "FULL_FILL"
LIFECYCLE_POSITION_OPENED = "POSITION_OPENED"
LIFECYCLE_POSITION_CLOSED = "POSITION_CLOSED"
LIFECYCLE_POSITION_MANAGED = "POSITION_MANAGED"
LIFECYCLE_ADAPTIVE_POSTURE_SELECTED = "ADAPTIVE_POSTURE_SELECTED"
LIFECYCLE_SHADOW_ENTRY_SUPPRESSED = "SHADOW_ENTRY_SUPPRESSED"
POSITION_LIFECYCLE_OPENING = "OPENING"
POSITION_LIFECYCLE_OPEN = "OPEN"
POSITION_LIFECYCLE_CLOSING = "CLOSING"
POSITION_LIFECYCLE_CLOSED = "CLOSED"
BROKER_STATE_OK = "OK"
BROKER_STATE_RESTRICTED = "RESTRICTED"
BROKER_STATE_EXIT_BLOCKED = "EXIT_BLOCKED"
BROKER_STATE_BUYING_POWER_LIMITED = "BUYING_POWER_LIMITED"
BROKER_STATE_ORDER_PENDING = "ORDER_PENDING"
BROKER_CATEGORY_PDT = "PDT"
BROKER_CATEGORY_INSUFFICIENT_BUYING_POWER = "INSUFFICIENT_BUYING_POWER"
BROKER_CATEGORY_MARKET_CLOSED = "MARKET_CLOSED"
BROKER_CATEGORY_DUPLICATE_ORDER = "DUPLICATE_ORDER"
BROKER_CATEGORY_PARTIAL_FILL_CONFLICT = "PARTIAL_FILL_CONFLICT"
BROKER_CATEGORY_NOTIONAL_TOO_LARGE = "NOTIONAL_TOO_LARGE"
BROKER_CATEGORY_ASSET_NOT_TRADABLE = "ASSET_NOT_TRADABLE"
BROKER_CATEGORY_GENERIC_REJECTION = "GENERIC_BROKER_REJECTION"
BUYING_POWER_ORDER_BUFFER_PERCENT = Decimal("5")
MONEY_STEP = Decimal("0.01")
V7_DAY_BIAS_BULL = "BULL_BIAS"
V7_DAY_BIAS_BEAR = "BEAR_BIAS"
V7_DAY_BIAS_NEUTRAL = "NEUTRAL"
V7_BULL_CURRENT_MIN_PERCENT = Decimal("1.50")
V7_BULL_RUNUP_MIN_PERCENT = Decimal("4.00")
V7_BULL_FAILURE_CURRENT_PERCENT = Decimal("-2.00")
V7_BULL_FAILURE_DRAWDOWN_PERCENT = Decimal("-4.00")
V7_BEAR_CURRENT_MAX_PERCENT = Decimal("-2.00")
V7_BEAR_DRAWDOWN_MIN_PERCENT = Decimal("-4.00")
V7_ROUTE_INVALIDATION_EXIT_LIMIT = 3
V7_INVERSE_LOSS_LIMIT = 2
V7_BOT_LOSS_LIMIT = 4
V8_DIRECTIONAL_MIN_REGIME_AGE_MINUTES = Decimal("8")
V8_DIRECTIONAL_MIN_TREND_TRUST_SCORE = 45
V8_DIRECTIONAL_MAX_FLIPS_60M = 5
V9_MOMENTUM_MIN_TREND_TRUST_SCORE = 45
V9_MOMENTUM_MIN_SOURCE_PERCENT = Decimal("2.00")
V9_MOMENTUM_MAX_TRANSITIONS_PER_HOUR = Decimal("8")
V9_MOMENTUM_EARLY_WINDOW_MINUTES = 30
V9_MOMENTUM_ACTIVATION_GRACE_MINUTES = 15
V9_MOMENTUM_RECLAIM_MIN_TREND_TRUST_SCORE = 58
V9_MOMENTUM_RECLAIM_MIN_SOURCE_PERCENT = Decimal("4.00")
V9_MOMENTUM_RECLAIM_MAX_RAW_TRANSITION_COUNT = 1
V9_MOMENTUM_RECLAIM_MAX_NON_WARMUP_TRANSITION_COUNT = 0
V9_MOMENTUM_RECLAIM_START_MINUTES = 45
V9_MOMENTUM_RECLAIM_END_MINUTES = 60
V9_MOMENTUM_INVALIDATION_DRAWDOWN_FROM_HIGH_PERCENT = Decimal("-5")
V9_MOMENTUM_CONTEXT_SUPPRESSION_REASON = "v9_momentum_context_suppresses_inverse"
V9_MOMENTUM_CONTEXT_ACTIVATION_REASON = "v9_momentum_clean_tape_context"
V9_MOMENTUM_CONTEXT_RECLAIM_REASON = "v9_momentum_strict_reclaim_context"
V9_MOMENTUM_CONTEXT_INVALIDATION_REASON = "v9_momentum_context_invalidated"
V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON = "no_authority_directional_suppressed"
V10_AUTHORITY_STATE_MOMENTUM = "momentum"
V10_AUTHORITY_STATE_NONE = "none"
MOMENTUM_AUTHORITY_REQUIRED_REASON = "momentum_authority_required"
MOMENTUM_AUTHORITY_REVOKED_EXIT_REASON = "momentum_authority_revoked_exit"
CHOP_PERMISSION_SUPPRESSION_REASON = "chop_permission_gate_blocked"
NY_TZ = ZoneInfo("America/New_York")


class BotError(Exception):
    pass


def normalize_enabled_bots(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return EDGEWALKER_BOTS

    if isinstance(value, str):
        raw_items = value.replace(",", " ").split()
    elif isinstance(value, (list, tuple, set)):
        raw_items = [str(item) for item in value]
    else:
        raise BotError("enabledBots must be a list or comma-separated string")

    aliases = {
        "momentum": MOMENTUM_BOT,
        "momentumbot": MOMENTUM_BOT,
        "chop": CHOP_BOT,
        "chopbot": CHOP_BOT,
        "inverse": INVERSE_BOT,
        "inversebot": INVERSE_BOT,
    }
    enabled: list[str] = []
    for item in raw_items:
        normalized = item.strip().replace("_", "").replace("-", "").lower()
        if not normalized:
            continue
        bot_name = aliases.get(normalized)
        if bot_name is None:
            raise BotError(
                "enabledBots may only contain MomentumBot, ChopBot, or InverseBot"
            )
        if bot_name not in enabled:
            enabled.append(bot_name)
    if not enabled:
        raise BotError("enabledBots must contain at least one bot")
    return tuple(enabled)


def _last_completed_bar_end(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    return current.replace(second=0, microsecond=0) - timedelta(microseconds=1)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def normalize_alpaca_base_url(value: str) -> str:
    normalized = str(value).strip().rstrip("/")
    if not normalized:
        return normalized

    parsed = urllib.parse.urlparse(normalized)
    alpaca_hosts = {
        "api.alpaca.markets",
        "paper-api.alpaca.markets",
        "data.alpaca.markets",
    }
    if parsed.scheme in {"http", "https"} and parsed.netloc.lower() in alpaca_hosts:
        if parsed.path.rstrip("/") in {"", "/"}:
            return urllib.parse.urlunparse(
                (parsed.scheme, parsed.netloc, "/v2", "", "", "")
            )

    return normalized


def env_decimal(name: str, default: str) -> Decimal:
    value = os.environ.get(name, default)
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise BotError(f"{name} must be a valid number, got {value!r}") from exc


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise BotError(f"{name} must be an integer, got {value!r}") from exc


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BotConfig:
    trading_base_url: str
    data_base_url: str
    api_key_id: str
    api_secret_key: str
    symbol: str
    position_notional: Decimal
    position_sizing_mode: str
    position_allocation_percent: Decimal
    trail_percent: Decimal
    fast_sma_minutes: int
    slow_sma_minutes: int
    poll_seconds: int
    close_liquidate_minutes: int
    regime_gap_threshold: Decimal
    regime_exit_gap_threshold: Decimal
    chop_entry_discount_percent: Decimal
    directional_mode: str
    directional_max_extension_percent: Decimal
    directional_strong_chase_max_extension_percent: Decimal
    directional_min_strength: str
    directional_cooldown_minutes: int
    adaptive_shadow_enabled: bool
    data_feed: str
    dry_run: bool
    enabled_bots: tuple[str, ...] = EDGEWALKER_BOTS
    chop_permission_mode: str = CHOP_PERMISSION_MODE_OFF
    chop_permission_max_abs_source_percent: Decimal = (
        CHOP_PERMISSION_MAX_ABS_SOURCE_PERCENT
    )
    inverse_cascade_mode: str = INVERSE_CASCADE_MODE_SUSTAINED
    inverse_cascade_velocity_window_minutes: int = (
        INVERSE_CASCADE_VELOCITY_WINDOW_MINUTES
    )
    inverse_cascade_sustain_minutes: int = INVERSE_CASCADE_SUSTAIN_MINUTES
    inverse_cascade_trail_percent: Decimal = INVERSE_CASCADE_TRAIL_PERCENT
    inverse_cascade_route_invalidation_grace_minutes: int = (
        INVERSE_CASCADE_ROUTE_INVALIDATION_GRACE_MINUTES
    )
    inverse_cascade_proven_mfe_percent: Decimal = INVERSE_CASCADE_PROVEN_MFE_PERCENT
    inverse_cascade_proven_trail_percent: Decimal = INVERSE_CASCADE_PROVEN_TRAIL_PERCENT
    inverse_cascade_proven_trail_tighten_mfe_percent: Decimal = (
        INVERSE_CASCADE_PROVEN_TRAIL_TIGHTEN_MFE_PERCENT
    )
    inverse_cascade_proven_route_recovery_min_source_percent: Decimal = (
        INVERSE_CASCADE_PROVEN_ROUTE_RECOVERY_MIN_SOURCE_PERCENT
    )
    momentum_authority_required: bool = False
    momentum_authority_revoke_exits: bool = False
    momentum_authority_latch_once_active: bool = False
    momentum_authority_min_trust_score: int = V9_MOMENTUM_MIN_TREND_TRUST_SCORE
    momentum_authority_min_source_percent: Decimal = V9_MOMENTUM_MIN_SOURCE_PERCENT
    momentum_authority_max_transitions_per_hour: Decimal = (
        V9_MOMENTUM_MAX_TRANSITIONS_PER_HOUR
    )
    momentum_authority_reclaim_enabled: bool = False
    momentum_authority_reclaim_min_trust_score: int = (
        V9_MOMENTUM_RECLAIM_MIN_TREND_TRUST_SCORE
    )
    momentum_authority_reclaim_min_source_percent: Decimal = (
        V9_MOMENTUM_RECLAIM_MIN_SOURCE_PERCENT
    )
    momentum_authority_reclaim_max_raw_transition_count: int = (
        V9_MOMENTUM_RECLAIM_MAX_RAW_TRANSITION_COUNT
    )
    momentum_authority_reclaim_max_non_warmup_transition_count: int = (
        V9_MOMENTUM_RECLAIM_MAX_NON_WARMUP_TRANSITION_COUNT
    )
    momentum_authority_reclaim_start_minutes: int = V9_MOMENTUM_RECLAIM_START_MINUTES
    momentum_authority_reclaim_end_minutes: int = V9_MOMENTUM_RECLAIM_END_MINUTES
    preset_name: str | None = None
    v9_observer_context: dict[str, Any] | None = None
    v10_force_no_authority: bool = False

    @classmethod
    def from_env(cls, environment_override: str | None = None) -> "BotConfig":
        alpaca_environment = (
            environment_override
            if environment_override is not None
            else os.environ.get("ALPACA_ENVIRONMENT", "paper")
        ).strip().lower()
        if alpaca_environment not in {"paper", "live"}:
            raise BotError("ALPACA_ENVIRONMENT must be paper or live")

        if alpaca_environment == "live":
            api_key_id = os.environ.get("ALPACA_LIVE_API_KEY_ID", "").strip()
            api_secret_key = os.environ.get("ALPACA_LIVE_API_SECRET_KEY", "").strip()
            trading_base_url = os.environ.get(
                "ALPACA_LIVE_TRADING_BASE_URL",
                LIVE_TRADING_BASE_URL_DEFAULT,
            )
        else:
            api_key_id = (
                os.environ.get("ALPACA_PAPER_API_KEY_ID")
                or os.environ.get("ALPACA_API_KEY_ID", "")
            ).strip()
            api_secret_key = (
                os.environ.get("ALPACA_PAPER_API_SECRET_KEY")
                or os.environ.get("ALPACA_API_SECRET_KEY", "")
            ).strip()
            trading_base_url = (
                os.environ.get("ALPACA_PAPER_TRADING_BASE_URL")
                or os.environ.get("ALPACA_TRADING_BASE_URL")
                or TRADING_BASE_URL_DEFAULT
            )
        if not api_key_id or not api_secret_key:
            raise BotError(
                "Set Alpaca API key and secret for the selected environment in .env"
            )

        fast_sma = env_int("FAST_SMA_MINUTES", 5)
        slow_sma = env_int("SLOW_SMA_MINUTES", 20)
        if fast_sma < 2:
            raise BotError("FAST_SMA_MINUTES must be at least 2")
        if slow_sma <= fast_sma:
            raise BotError("SLOW_SMA_MINUTES must be greater than FAST_SMA_MINUTES")

        trail_percent = env_decimal("TRAIL_PERCENT", "1.5")
        if trail_percent <= 0:
            raise BotError("TRAIL_PERCENT must be greater than 0")

        position_notional = env_decimal("POSITION_NOTIONAL", "25")
        if position_notional <= 0:
            raise BotError("POSITION_NOTIONAL must be greater than 0")

        position_sizing_mode = os.environ.get(
            "POSITION_SIZING_MODE",
            POSITION_SIZING_FIXED,
        ).strip().upper()
        if position_sizing_mode not in POSITION_SIZING_MODES:
            raise BotError("POSITION_SIZING_MODE must be FIXED or DYNAMIC")

        position_allocation_percent = env_decimal("POSITION_ALLOCATION_PERCENT", "25")
        if position_allocation_percent <= 0 or position_allocation_percent > 100:
            raise BotError("POSITION_ALLOCATION_PERCENT must be between 0 and 100")

        poll_seconds = env_int("POLL_SECONDS", 60)
        if poll_seconds < 5:
            raise BotError("POLL_SECONDS must be at least 5")

        close_liquidate_minutes = env_int("CLOSE_LIQUIDATE_MINUTES", 5)
        if close_liquidate_minutes < 1:
            raise BotError("CLOSE_LIQUIDATE_MINUTES must be at least 1")

        regime_gap_threshold = env_decimal("REGIME_GAP_THRESHOLD", "0.20")
        if regime_gap_threshold < 0:
            raise BotError("REGIME_GAP_THRESHOLD must be at least 0")

        regime_exit_gap_threshold = env_decimal("REGIME_EXIT_GAP_THRESHOLD", "0.10")
        if regime_exit_gap_threshold < 0:
            raise BotError("REGIME_EXIT_GAP_THRESHOLD must be at least 0")

        chop_entry_discount_percent = env_decimal("CHOP_ENTRY_DISCOUNT_PERCENT", "0.50")
        if chop_entry_discount_percent < 0:
            raise BotError("CHOP_ENTRY_DISCOUNT_PERCENT must be at least 0")

        directional_mode = os.environ.get(
            "DIRECTIONAL_MODE",
            os.environ.get("MOMENTUM_MODE", DIRECTIONAL_MODE_BALANCED),
        ).strip().upper()
        if directional_mode not in DIRECTIONAL_MODES:
            raise BotError(
                "DIRECTIONAL_MODE must be CONSERVATIVE, BALANCED, AGGRESSIVE, or ADAPTIVE"
            )

        directional_max_extension_percent = env_decimal(
            "DIRECTIONAL_MAX_EXTENSION_PERCENT",
            os.environ.get("MOMENTUM_MAX_EXTENSION_PERCENT", "0.50"),
        )
        if directional_max_extension_percent < 0:
            raise BotError("DIRECTIONAL_MAX_EXTENSION_PERCENT must be at least 0")

        directional_strong_chase_max_extension_percent = env_decimal(
            "DIRECTIONAL_STRONG_CHASE_MAX_EXTENSION_PERCENT",
            os.environ.get("MOMENTUM_STRONG_CHASE_MAX_EXTENSION_PERCENT", "1.00"),
        )
        if directional_strong_chase_max_extension_percent < 0:
            raise BotError(
                "DIRECTIONAL_STRONG_CHASE_MAX_EXTENSION_PERCENT must be at least 0"
            )

        directional_min_strength = os.environ.get(
            "DIRECTIONAL_MIN_STRENGTH",
            os.environ.get("MOMENTUM_MIN_STRENGTH", REGIME_STRENGTH_MODERATE),
        ).strip().upper()
        if directional_min_strength not in REGIME_STRENGTHS:
            raise BotError("DIRECTIONAL_MIN_STRENGTH must be WEAK, MODERATE, or STRONG")

        directional_cooldown_minutes = env_int(
            "DIRECTIONAL_COOLDOWN_MINUTES",
            env_int("MOMENTUM_COOLDOWN_MINUTES", 5),
        )
        if directional_cooldown_minutes < 0:
            raise BotError("DIRECTIONAL_COOLDOWN_MINUTES must be at least 0")

        chop_permission_mode = os.environ.get(
            "CHOP_PERMISSION_MODE",
            CHOP_PERMISSION_MODE_OFF,
        ).strip().upper()
        if chop_permission_mode not in CHOP_PERMISSION_MODES:
            raise BotError(
                "CHOP_PERMISSION_MODE must be OFF, LOOSE, STRICT, or FIREWALL"
            )
        chop_permission_max_abs_source_percent = env_decimal(
            "CHOP_PERMISSION_MAX_ABS_SOURCE_PERCENT",
            CHOP_PERMISSION_MAX_ABS_SOURCE_PERCENT,
        )
        if chop_permission_max_abs_source_percent < 0:
            raise BotError("CHOP_PERMISSION_MAX_ABS_SOURCE_PERCENT must be at least 0")

        inverse_cascade_mode = os.environ.get(
            "INVERSE_CASCADE_MODE",
            INVERSE_CASCADE_MODE_SUSTAINED,
        ).strip().upper()
        if inverse_cascade_mode not in INVERSE_CASCADE_MODES:
            raise BotError(
                "INVERSE_CASCADE_MODE must be OFF, LOOSE, STRICT, VELOCITY, or SUSTAINED"
            )
        inverse_cascade_velocity_window_minutes = env_int(
            "INVERSE_CASCADE_VELOCITY_WINDOW_MINUTES",
            INVERSE_CASCADE_VELOCITY_WINDOW_MINUTES,
        )
        if inverse_cascade_velocity_window_minutes < 1:
            raise BotError(
                "INVERSE_CASCADE_VELOCITY_WINDOW_MINUTES must be at least 1"
            )
        inverse_cascade_sustain_minutes = env_int(
            "INVERSE_CASCADE_SUSTAIN_MINUTES",
            INVERSE_CASCADE_SUSTAIN_MINUTES,
        )
        if inverse_cascade_sustain_minutes < 1:
            raise BotError("INVERSE_CASCADE_SUSTAIN_MINUTES must be at least 1")
        inverse_cascade_trail_percent = env_decimal(
            "INVERSE_CASCADE_TRAIL_PERCENT",
            str(INVERSE_CASCADE_TRAIL_PERCENT),
        )
        if inverse_cascade_trail_percent <= 0:
            raise BotError("INVERSE_CASCADE_TRAIL_PERCENT must be greater than 0")
        inverse_cascade_route_invalidation_grace_minutes = env_int(
            "INVERSE_CASCADE_ROUTE_INVALIDATION_GRACE_MINUTES",
            INVERSE_CASCADE_ROUTE_INVALIDATION_GRACE_MINUTES,
        )
        if inverse_cascade_route_invalidation_grace_minutes < 0:
            raise BotError(
                "INVERSE_CASCADE_ROUTE_INVALIDATION_GRACE_MINUTES must be at least 0"
            )
        inverse_cascade_proven_mfe_percent = env_decimal(
            "INVERSE_CASCADE_PROVEN_MFE_PERCENT",
            str(INVERSE_CASCADE_PROVEN_MFE_PERCENT),
        )
        if inverse_cascade_proven_mfe_percent < 0:
            raise BotError("INVERSE_CASCADE_PROVEN_MFE_PERCENT must be at least 0")
        inverse_cascade_proven_trail_percent = env_decimal(
            "INVERSE_CASCADE_PROVEN_TRAIL_PERCENT",
            str(INVERSE_CASCADE_PROVEN_TRAIL_PERCENT),
        )
        if inverse_cascade_proven_trail_percent <= 0:
            raise BotError("INVERSE_CASCADE_PROVEN_TRAIL_PERCENT must be greater than 0")
        inverse_cascade_proven_trail_tighten_mfe_percent = env_decimal(
            "INVERSE_CASCADE_PROVEN_TRAIL_TIGHTEN_MFE_PERCENT",
            str(INVERSE_CASCADE_PROVEN_TRAIL_TIGHTEN_MFE_PERCENT),
        )
        if inverse_cascade_proven_trail_tighten_mfe_percent < 0:
            raise BotError(
                "INVERSE_CASCADE_PROVEN_TRAIL_TIGHTEN_MFE_PERCENT must be at least 0"
            )
        inverse_cascade_proven_route_recovery_min_source_percent = env_decimal(
            "INVERSE_CASCADE_PROVEN_ROUTE_RECOVERY_MIN_SOURCE_PERCENT",
            str(INVERSE_CASCADE_PROVEN_ROUTE_RECOVERY_MIN_SOURCE_PERCENT),
        )

        runtime_observer_context = None
        if env_bool("BALANCEDPURE_RUNTIME_OBSERVER_ENABLED", False):
            runtime_observer_context = {
                "observer_preset": "BalancedPure_LiveObserver",
                "runtime_observer": True,
                "execution_rights": "none",
            }

        return cls(
            trading_base_url=normalize_alpaca_base_url(trading_base_url),
            data_base_url=normalize_alpaca_base_url(
                os.environ.get("ALPACA_DATA_BASE_URL", DATA_BASE_URL_DEFAULT)
            ),
            api_key_id=api_key_id,
            api_secret_key=api_secret_key,
            symbol=os.environ.get("SYMBOL", SOXL).strip().upper(),
            position_notional=position_notional,
            position_sizing_mode=position_sizing_mode,
            position_allocation_percent=position_allocation_percent,
            trail_percent=trail_percent,
            fast_sma_minutes=fast_sma,
            slow_sma_minutes=slow_sma,
            poll_seconds=poll_seconds,
            close_liquidate_minutes=close_liquidate_minutes,
            regime_gap_threshold=regime_gap_threshold,
            regime_exit_gap_threshold=regime_exit_gap_threshold,
            chop_entry_discount_percent=chop_entry_discount_percent,
            directional_mode=directional_mode,
            directional_max_extension_percent=directional_max_extension_percent,
            directional_strong_chase_max_extension_percent=(
                directional_strong_chase_max_extension_percent
            ),
            directional_min_strength=directional_min_strength,
            directional_cooldown_minutes=directional_cooldown_minutes,
            adaptive_shadow_enabled=env_bool("ADAPTIVE_SHADOW_ENABLED", True),
            data_feed=os.environ.get("DATA_FEED", "iex").strip(),
            dry_run=env_bool("DRY_RUN", False),
            enabled_bots=normalize_enabled_bots(os.environ.get("ENABLED_BOTS")),
            chop_permission_mode=chop_permission_mode,
            chop_permission_max_abs_source_percent=(
                chop_permission_max_abs_source_percent
            ),
            inverse_cascade_mode=inverse_cascade_mode,
            inverse_cascade_velocity_window_minutes=(
                inverse_cascade_velocity_window_minutes
            ),
            inverse_cascade_sustain_minutes=inverse_cascade_sustain_minutes,
            inverse_cascade_trail_percent=inverse_cascade_trail_percent,
            inverse_cascade_route_invalidation_grace_minutes=(
                inverse_cascade_route_invalidation_grace_minutes
            ),
            inverse_cascade_proven_mfe_percent=inverse_cascade_proven_mfe_percent,
            inverse_cascade_proven_trail_percent=inverse_cascade_proven_trail_percent,
            inverse_cascade_proven_trail_tighten_mfe_percent=(
                inverse_cascade_proven_trail_tighten_mfe_percent
            ),
            inverse_cascade_proven_route_recovery_min_source_percent=(
                inverse_cascade_proven_route_recovery_min_source_percent
            ),
            momentum_authority_required=env_bool("MOMENTUM_AUTHORITY_REQUIRED", False),
            momentum_authority_revoke_exits=env_bool(
                "MOMENTUM_AUTHORITY_REVOKE_EXITS",
                False,
            ),
            momentum_authority_latch_once_active=env_bool(
                "MOMENTUM_AUTHORITY_LATCH_ONCE_ACTIVE",
                False,
            ),
            momentum_authority_min_trust_score=env_int(
                "MOMENTUM_AUTHORITY_MIN_TRUST_SCORE",
                V9_MOMENTUM_MIN_TREND_TRUST_SCORE,
            ),
            momentum_authority_min_source_percent=env_decimal(
                "MOMENTUM_AUTHORITY_MIN_SOURCE_PERCENT",
                V9_MOMENTUM_MIN_SOURCE_PERCENT,
            ),
            momentum_authority_max_transitions_per_hour=env_decimal(
                "MOMENTUM_AUTHORITY_MAX_TRANSITIONS_PER_HOUR",
                V9_MOMENTUM_MAX_TRANSITIONS_PER_HOUR,
            ),
            momentum_authority_reclaim_enabled=env_bool(
                "MOMENTUM_AUTHORITY_RECLAIM_ENABLED",
                False,
            ),
            momentum_authority_reclaim_min_trust_score=env_int(
                "MOMENTUM_AUTHORITY_RECLAIM_MIN_TRUST_SCORE",
                V9_MOMENTUM_RECLAIM_MIN_TREND_TRUST_SCORE,
            ),
            momentum_authority_reclaim_min_source_percent=env_decimal(
                "MOMENTUM_AUTHORITY_RECLAIM_MIN_SOURCE_PERCENT",
                V9_MOMENTUM_RECLAIM_MIN_SOURCE_PERCENT,
            ),
            momentum_authority_reclaim_max_raw_transition_count=env_int(
                "MOMENTUM_AUTHORITY_RECLAIM_MAX_RAW_TRANSITION_COUNT",
                V9_MOMENTUM_RECLAIM_MAX_RAW_TRANSITION_COUNT,
            ),
            momentum_authority_reclaim_max_non_warmup_transition_count=env_int(
                "MOMENTUM_AUTHORITY_RECLAIM_MAX_NON_WARMUP_TRANSITION_COUNT",
                V9_MOMENTUM_RECLAIM_MAX_NON_WARMUP_TRANSITION_COUNT,
            ),
            momentum_authority_reclaim_start_minutes=env_int(
                "MOMENTUM_AUTHORITY_RECLAIM_START_MINUTES",
                V9_MOMENTUM_RECLAIM_START_MINUTES,
            ),
            momentum_authority_reclaim_end_minutes=env_int(
                "MOMENTUM_AUTHORITY_RECLAIM_END_MINUTES",
                V9_MOMENTUM_RECLAIM_END_MINUTES,
            ),
            preset_name=os.environ.get("PRESET_NAME") or None,
            v9_observer_context=runtime_observer_context,
            v10_force_no_authority=False,
        )


class AlpacaClient:
    def __init__(self, config: BotConfig) -> None:
        self.config = config

    def get_account(self) -> dict[str, Any]:
        return self._trading_request("GET", "/account")

    def get_clock(self) -> dict[str, Any]:
        return self._trading_request("GET", "/clock")

    def get_position(self, symbol: str) -> dict[str, Any] | None:
        try:
            return self._trading_request("GET", f"/positions/{symbol}")
        except BotError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise

    def get_asset(self, symbol: str) -> dict[str, Any]:
        return self._trading_request("GET", f"/assets/{symbol}")

    def list_open_orders(self) -> list[dict[str, Any]]:
        orders = self._trading_request(
            "GET",
            "/orders",
            {"status": "open", "limit": "100", "direction": "desc", "nested": "false"},
        )
        if not isinstance(orders, list):
            raise BotError(f"Unexpected orders response: {orders!r}")
        return orders

    def get_recent_bars(self, symbol: str, minutes: int) -> list[dict[str, Any]]:
        end = _last_completed_bar_end()
        start = end - timedelta(minutes=max(minutes * 3, minutes + 15))
        params = {
            "timeframe": "1Min",
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "limit": str(minutes),
            "adjustment": "raw",
            "feed": self.config.data_feed,
            "sort": "asc",
        }

        data = self._data_request("GET", f"/stocks/{symbol}/bars", params)
        bars = data.get("bars") or []

        if isinstance(bars, dict):
            bars = bars.get(symbol) or []
        if not isinstance(bars, list):
            raise BotError(f"Unexpected bars response: {data!r}")

        return bars

    def get_previous_session_close(self, symbol: str) -> Decimal | None:
        target_date = datetime.now(NY_TZ).date()
        start = datetime.combine(
            target_date - timedelta(days=21),
            datetime.min.time(),
            NY_TZ,
        )
        end = datetime.combine(target_date + timedelta(days=1), datetime.min.time(), NY_TZ)
        params = {
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": "1000",
            "adjustment": "raw",
            "feed": self.config.data_feed,
            "sort": "asc",
        }

        data = self._data_request("GET", f"/stocks/{symbol}/bars", params)
        bars = data.get("bars") or []
        if isinstance(bars, dict):
            bars = bars.get(symbol) or []
        if not isinstance(bars, list):
            raise BotError(f"Unexpected previous close bars response: {data!r}")

        prior_bars: list[tuple[datetime, Decimal]] = []
        for bar in bars:
            if not isinstance(bar, dict):
                continue
            timestamp = parse_market_timestamp(bar.get("t"))
            if timestamp is None or timestamp.astimezone(NY_TZ).date() >= target_date:
                continue
            close = bar.get("c")
            if close is None:
                continue
            try:
                prior_bars.append((timestamp, Decimal(str(close))))
            except InvalidOperation:
                continue
        if not prior_bars:
            return None

        prior_bars.sort(key=lambda item: item[0])
        return prior_bars[-1][1]

    def get_latest_trade(self, symbol: str) -> dict[str, Any] | None:
        data = self._data_request(
            "GET",
            f"/stocks/{symbol}/trades/latest",
            {"feed": self.config.data_feed},
        )
        trade = data.get("trade")
        if trade is None:
            return None
        if not isinstance(trade, dict):
            raise BotError(f"Unexpected latest trade response: {data!r}")
        return trade

    def get_latest_quote(self, symbol: str) -> dict[str, Any] | None:
        data = self._data_request(
            "GET",
            f"/stocks/{symbol}/quotes/latest",
            {"feed": self.config.data_feed},
        )
        quote = data.get("quote")
        if quote is None:
            return None
        if not isinstance(quote, dict):
            raise BotError(f"Unexpected latest quote response: {data!r}")
        return quote

    def submit_market_buy(self, symbol: str, notional: Decimal) -> dict[str, Any] | None:
        payload = {
            "symbol": symbol,
            "notional": str(notional),
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
        }
        if self.config.dry_run:
            print(f"[dry-run] Would submit market buy: {json.dumps(payload)}")
            return None
        return self._trading_request("POST", "/orders", payload=payload)

    def submit_market_buy_qty(self, symbol: str, qty: Decimal) -> dict[str, Any] | None:
        payload = {
            "symbol": symbol,
            "qty": format_decimal(qty),
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
        }
        if self.config.dry_run:
            print(f"[dry-run] Would submit market buy: {json.dumps(payload)}")
            return None
        return self._trading_request("POST", "/orders", payload=payload)

    def submit_market_sell_qty(self, symbol: str, qty: Decimal) -> dict[str, Any] | None:
        payload = {
            "symbol": symbol,
            "qty": format_decimal(qty),
            "side": "sell",
            "type": "market",
            "time_in_force": "day",
        }
        if self.config.dry_run:
            print(f"[dry-run] Would submit market sell: {json.dumps(payload)}")
            return None
        return self._trading_request("POST", "/orders", payload=payload)

    def get_order(self, order_id: str) -> dict[str, Any]:
        order = self._trading_request("GET", f"/orders/{order_id}")
        if not isinstance(order, dict):
            raise BotError(f"Unexpected order response: {order!r}")
        return order

    def submit_trailing_stop_sell(
        self, symbol: str, qty: Decimal, trail_percent: Decimal
    ) -> dict[str, Any] | None:
        payload = {
            "symbol": symbol,
            "qty": format_decimal(qty),
            "side": "sell",
            "type": "trailing_stop",
            "time_in_force": "gtc",
            "trail_percent": str(trail_percent),
        }
        if self.config.dry_run:
            print(f"[dry-run] Would submit trailing stop sell: {json.dumps(payload)}")
            return None
        return self._trading_request("POST", "/orders", payload=payload)

    def _trading_request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return self._request(
            method,
            f"{self.config.trading_base_url}{path}",
            params=params,
            payload=payload,
        )

    def _data_request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        return self._request(
            method,
            f"{self.config.data_base_url}{path}",
            params=params,
        )

    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        body = None
        headers = {
            "APCA-API-KEY-ID": self.config.api_key_id,
            "APCA-API-SECRET-KEY": self.config.api_secret_key,
            "Accept": "application/json",
        }

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise BotError(f"HTTP {exc.code} from {url}: {details}") from exc
        except urllib.error.URLError as exc:
            raise BotError(f"Network error calling {url}: {exc.reason}") from exc

        if not raw:
            return None

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BotError(f"Invalid JSON from {url}: {raw[:250]}") from exc


def format_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f")


def decimal_from_api(value: Any, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise BotError(f"Could not parse {field_name} value {value!r}") from exc


def optional_decimal_from_api(value: Any, field_name: str) -> Decimal | None:
    if value in (None, ""):
        return None
    return decimal_from_api(value, field_name)


def lifecycle_json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format_decimal(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): lifecycle_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [lifecycle_json_value(item) for item in value]
    return value


@dataclass(frozen=True)
class BrokerConstraint:
    state: str
    category: str | None
    message: str | None
    side: str | None = None
    symbol: str | None = None
    code: str | None = None


def broker_constraint_ok() -> BrokerConstraint:
    return BrokerConstraint(
        state=BROKER_STATE_OK,
        category=None,
        message=None,
    )


def broker_constraint_payload(constraint: BrokerConstraint) -> dict[str, Any]:
    return {
        "state": constraint.state,
        "category": constraint.category,
        "message": constraint.message,
        "side": constraint.side,
        "symbol": constraint.symbol,
        "code": constraint.code,
    }


def classify_broker_error(
    message: str,
    side: str | None = None,
    symbol: str | None = None,
) -> BrokerConstraint:
    payload = broker_error_payload(message)
    payload_message = str(payload.get("message") or "") if payload else ""
    code = str(payload.get("code")) if payload and payload.get("code") else None
    text = f"{message} {payload_message}".lower()
    normalized_side = side.lower() if isinstance(side, str) else None

    category = BROKER_CATEGORY_GENERIC_REJECTION
    state = BROKER_STATE_RESTRICTED
    if "pattern day" in text or "pdt" in text:
        category = BROKER_CATEGORY_PDT
    elif (
        "potential wash trade" in text
        or "opposite side market/stop order exists" in text
        or ("existing_order_id" in text and "opposite side" in text)
    ):
        category = BROKER_CATEGORY_PARTIAL_FILL_CONFLICT
        state = BROKER_STATE_ORDER_PENDING
    elif "insufficient buying power" in text or code == "40310000":
        category = BROKER_CATEGORY_INSUFFICIENT_BUYING_POWER
        state = BROKER_STATE_BUYING_POWER_LIMITED
    elif (
        "market closed" in text
        or "market is closed" in text
        or "market is not open" in text
        or "outside of trading" in text
    ):
        category = BROKER_CATEGORY_MARKET_CLOSED
    elif "duplicate" in text or "already open" in text:
        category = BROKER_CATEGORY_DUPLICATE_ORDER
        state = BROKER_STATE_ORDER_PENDING
    elif "notional" in text and (
        "too large" in text
        or "exceed" in text
        or "greater" in text
    ):
        category = BROKER_CATEGORY_NOTIONAL_TOO_LARGE
    elif (
        "not tradable" in text
        or "not fractionable" in text
        or "asset" in text
        and "tradable" in text
    ):
        category = BROKER_CATEGORY_ASSET_NOT_TRADABLE

    if normalized_side == "sell" and state != BROKER_STATE_ORDER_PENDING:
        state = BROKER_STATE_EXIT_BLOCKED

    return BrokerConstraint(
        state=state,
        category=category,
        message=payload_message or message,
        side=normalized_side,
        symbol=symbol,
        code=code,
    )


def broker_error_payload(message: str) -> dict[str, Any] | None:
    start = message.find("{")
    if start == -1:
        return None
    try:
        payload = json.loads(message[start:])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def sma(values: list[Decimal]) -> Decimal:
    return sum(values) / Decimal(len(values))


def crossed_above(
    fast_now_values: list[Decimal],
    fast_prev_values: list[Decimal],
    slow_now_values: list[Decimal],
    slow_prev_values: list[Decimal],
) -> bool:
    fast_now = sma(fast_now_values)
    fast_prev = sma(fast_prev_values)
    slow_now = sma(slow_now_values)
    slow_prev = sma(slow_prev_values)
    return fast_prev <= slow_prev and fast_now > slow_now


def latest_close_prices(bars: list[dict[str, Any]]) -> list[Decimal]:
    prices: list[Decimal] = []
    for bar in bars:
        if "c" not in bar:
            continue
        prices.append(decimal_from_api(bar["c"], "bar close"))
    return prices


def latest_complete_bar(bars: list[dict[str, Any]]) -> dict[str, Any] | None:
    for bar in reversed(bars):
        if "c" in bar:
            return bar
    return None


def parse_market_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = trim_timestamp_fraction(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def trim_timestamp_fraction(value: str) -> str:
    dot_index = value.find(".")
    if dot_index == -1:
        return value

    suffix_index = len(value)
    for index in range(dot_index + 1, len(value)):
        if not value[index].isdigit():
            suffix_index = index
            break

    fraction = value[dot_index + 1 : suffix_index]
    if len(fraction) <= 6:
        return value
    return f"{value[: dot_index + 1]}{fraction[:6]}{value[suffix_index:]}"


def age_seconds(
    timestamp: datetime | None,
    now: datetime | None = None,
) -> float | None:
    if timestamp is None:
        return None
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return max((current.astimezone(timezone.utc) - timestamp).total_seconds(), 0.0)


def bar_end_age_seconds(
    bar_start: datetime | None,
    now: datetime | None = None,
) -> float | None:
    if bar_start is None:
        return None
    return age_seconds(bar_start + timedelta(minutes=1), now)


@dataclass(frozen=True)
class SmaSnapshot:
    symbol: str
    price: Decimal
    fast_sma: Decimal
    slow_sma: Decimal
    fast_now_values: list[Decimal]
    fast_prev_values: list[Decimal]
    slow_now_values: list[Decimal]
    slow_prev_values: list[Decimal]
    latest_bar_time: datetime | None

    @property
    def gap_percent(self) -> Decimal:
        if self.slow_sma == 0:
            return Decimal("0")
        return abs(self.fast_sma - self.slow_sma) / self.slow_sma * Decimal("100")

    @property
    def has_cross_context(self) -> bool:
        return (
            len(self.fast_now_values) == len(self.fast_prev_values)
            and len(self.slow_now_values) == len(self.slow_prev_values)
        )

    @property
    def crossed_above(self) -> bool:
        if not self.has_cross_context:
            return False
        return crossed_above(
            self.fast_now_values,
            self.fast_prev_values,
            self.slow_now_values,
            self.slow_prev_values,
        )


@dataclass(frozen=True)
class MarketDataFreshness:
    symbol: str
    latest_bar_time: datetime | None
    latest_bar_close: Decimal | None
    latest_trade_time: datetime | None
    latest_trade_price: Decimal | None
    latest_quote_time: datetime | None
    latest_quote_bid: Decimal | None
    latest_quote_ask: Decimal | None
    bar_age_seconds: float | None
    trade_age_seconds: float | None
    quote_age_seconds: float | None
    trade_error: str | None = None
    quote_error: str | None = None

    @property
    def is_stale(self) -> bool:
        return (
            self.bar_age_seconds is None
            or self.bar_age_seconds > MARKET_DATA_MAX_AGE_SECONDS
        )

    @property
    def has_live_trade_or_quote(self) -> bool:
        return any(
            age is not None and age <= MARKET_DATA_MAX_AGE_SECONDS
            for age in (self.trade_age_seconds, self.quote_age_seconds)
        )


@dataclass(frozen=True)
class RegimeSignal:
    source_symbol: str
    price: Decimal
    fast_sma: Decimal
    slow_sma: Decimal
    gap_percent: Decimal
    regime: str


@dataclass(frozen=True)
class BotRoute:
    active_bot: str
    routed_symbol: str | None
    allows_entry: bool


@dataclass(frozen=True)
class EntryDecision:
    signal: bool
    reason: str


@dataclass(frozen=True)
class SourcePricePath:
    open_price: Decimal
    current_price: Decimal
    high_price: Decimal
    low_price: Decimal
    current_percent: Decimal
    runup_percent: Decimal
    drawdown_percent: Decimal


@dataclass(frozen=True)
class AdaptivePosture:
    selected_mode: str
    confidence: str
    reasons: tuple[str, ...]
    constraints: tuple[str, ...]
    active: bool
    shadow: bool


@dataclass(frozen=True)
class EdgeWalkerStatus:
    checked_at: str
    market_open: bool
    next_open: str | None
    next_close: str | None
    buying_power: str | None
    portfolio_value: str | None
    cash: str | None
    position_sizing_mode: str
    position_allocation_percent: str
    effective_position_notional: str | None
    directional_mode: str
    effective_directional_mode: str | None
    adaptive_posture: str | None
    adaptive_confidence: str | None
    adaptive_reasons: list[str]
    adaptive_constraints: list[str]
    adaptive_shadow: bool
    day_pl: str | None
    day_pl_percent: str | None
    source_symbol: str
    source_price: str | None
    inverse_price: str | None
    fast_sma: str | None
    slow_sma: str | None
    gap_percent: str | None
    regime: str | None
    trend_trust: dict[str, Any] | None
    active_bot: str | None
    routed_symbol: str | None
    entry_signal: bool | None
    action_taken: str
    position_symbol: str | None
    position_qty: str | None
    position_market_value: str | None
    position_avg_entry_price: str | None
    position_unrealized_pl: str | None
    position_unrealized_pl_percent: str | None
    position_current_price: str | None
    position_owner: str | None
    high_water_mark: str | None
    trailing_exit_price: str | None
    data_source: str | None
    data_feed: str | None
    data_status: str | None
    stream_connected: bool | None
    stream_authenticated: bool | None
    stream_subscribed: bool | None
    stream_error: str | None
    stream_bar_count: int | None
    stream_last_message_at: str | None
    latest_bar_time: str | None
    bar_age_seconds: float | None
    latest_trade_time: str | None
    trade_age_seconds: float | None
    latest_quote_time: str | None
    quote_age_seconds: float | None
    v9_momentum_context: dict[str, Any] | None


def parse_clock_time(value: Any, field_name: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise BotError(f"Could not parse Alpaca clock {field_name}: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def closeout_status(
    clock: dict[str, Any],
    close_liquidate_minutes: int,
) -> tuple[datetime | None, float | None, bool]:
    next_close = parse_clock_time(clock.get("next_close"), "next_close")
    if next_close is None:
        return None, None, False

    seconds_to_close = (next_close - datetime.now(timezone.utc)).total_seconds()
    closeout_due = 0 <= seconds_to_close <= close_liquidate_minutes * 60
    return next_close, seconds_to_close, closeout_due


def config_for_symbol(config: BotConfig, symbol: str) -> BotConfig:
    return BotConfig(**{**config.__dict__, "symbol": symbol})


class BotStateStore:
    def __init__(self, path: Path = STATE_PATH_DEFAULT) -> None:
        self.path = path

    def get_high_water_mark(self, symbol: str) -> Decimal | None:
        data = self._read()
        raw = data.get("trailing", {}).get(symbol, {}).get("high_water_mark")
        if raw is None:
            return None
        return decimal_from_api(raw, f"{symbol} high water mark")

    def set_high_water_mark(self, symbol: str, value: Decimal) -> None:
        data = self._read()
        trailing = data.setdefault("trailing", {})
        symbol_state = trailing.setdefault(symbol, {})
        symbol_state["high_water_mark"] = format_decimal(value)
        symbol_state["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(data)

    def get_position_owner(self, symbol: str) -> str | None:
        data = self._read()
        owner = data.get("trailing", {}).get(symbol, {}).get("owner")
        if not owner:
            return None
        return str(owner)

    def set_position_owner(self, symbol: str, owner: str) -> None:
        data = self._read()
        trailing = data.setdefault("trailing", {})
        symbol_state = trailing.setdefault(symbol, {})
        symbol_state["owner"] = owner
        symbol_state["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(data)

    def clear_symbol(self, symbol: str) -> None:
        data = self._read()
        trailing = data.get("trailing", {})
        if symbol in trailing:
            del trailing[symbol]
            self._write(data)

    def get_inverse_cascade_state(self) -> dict[str, Any]:
        data = self._read()
        state = data.get("inverse_cascade", {})
        return state if isinstance(state, dict) else {}

    def set_inverse_cascade_state(self, state: dict[str, Any]) -> None:
        data = self._read()
        data["inverse_cascade"] = lifecycle_json_value(state)
        self._write(data)

    def update_inverse_cascade_state(self, **fields: Any) -> dict[str, Any]:
        state = self.get_inverse_cascade_state()
        state.update(lifecycle_json_value(fields))
        self.set_inverse_cascade_state(state)
        return state

    def clear_inverse_cascade_state(self) -> None:
        data = self._read()
        if "inverse_cascade" in data:
            data["inverse_cascade"] = {}
            self._write(data)

    def get_last_entry_at(self, bot_name: str, symbol: str) -> datetime | None:
        data = self._read()
        raw = data.get("entries", {}).get(bot_name, {}).get(symbol)
        return parse_market_timestamp(raw)

    def set_last_entry_at(
        self,
        bot_name: str,
        symbol: str,
        value: datetime | None = None,
    ) -> None:
        data = self._read()
        entries = data.setdefault("entries", {})
        bot_entries = entries.setdefault(bot_name, {})
        timestamp = value or datetime.now(timezone.utc)
        bot_entries[symbol] = timestamp.astimezone(timezone.utc).isoformat()
        self._write(data)

    def get_regime_state(self) -> dict[str, Any]:
        data = self._read()
        regime_state = data.get("regime", {})
        return regime_state if isinstance(regime_state, dict) else {}

    def get_v9_momentum_context(self) -> dict[str, Any]:
        data = self._read()
        v9_state = data.get("v9", {})
        if not isinstance(v9_state, dict):
            return {}
        context = v9_state.get("momentum_context", {})
        return context if isinstance(context, dict) else {}

    def set_v9_momentum_context(self, context: dict[str, Any]) -> None:
        data = self._read()
        v9_state = data.setdefault("v9", {})
        if not isinstance(v9_state, dict):
            v9_state = {}
            data["v9"] = v9_state
        v9_state["momentum_context"] = lifecycle_json_value(context)
        self._write(data)

    def set_regime_state(self, regime: str, gap_percent: Decimal) -> None:
        data = self._read()
        existing = data.get("regime", {})
        existing = existing if isinstance(existing, dict) else {}
        previous_regime = existing.get("regime")
        now = datetime.now(timezone.utc)
        transitions = existing.get("transitions")
        transitions = transitions if isinstance(transitions, list) else []
        regime_since = existing.get("regime_since")
        if previous_regime != regime:
            if previous_regime:
                transitions.append(
                    {
                        "from": previous_regime,
                        "to": regime,
                        "at": now.isoformat(),
                    }
                )
            regime_since = now.isoformat()
        elif not regime_since:
            regime_since = now.isoformat()
        data["regime"] = {
            "regime": regime,
            "gap_percent": format_decimal(gap_percent),
            "updated_at": now.isoformat(),
            "regime_since": regime_since,
            "transitions": transitions[-100:],
        }
        self._write(data)

    def get_pending_orders(self) -> dict[str, dict[str, Any]]:
        data = self._read()
        orders = data.get("orders", {})
        return orders if isinstance(orders, dict) else {}

    def get_pending_order(self, order_id: str) -> dict[str, Any] | None:
        order = self.get_pending_orders().get(order_id)
        return order if isinstance(order, dict) else None

    def track_order(self, order_id: str, metadata: dict[str, Any]) -> None:
        data = self._read()
        orders = data.setdefault("orders", {})
        existing_order = orders.get(order_id)
        existing = existing_order if isinstance(existing_order, dict) else {}
        existing.update(lifecycle_json_value(metadata))
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        orders[order_id] = existing
        self._write(data)

    def clear_order(self, order_id: str) -> None:
        data = self._read()
        orders = data.get("orders", {})
        if order_id in orders:
            del orders[order_id]
            self._write(data)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "trailing": {},
                "entries": {},
                "regime": {},
                "orders": {},
                "v9": {},
                "inverse_cascade": {},
            }
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BotError(f"Invalid bot state file {self.path}") from exc
        if not isinstance(data, dict):
            raise BotError(f"Invalid bot state file {self.path}")
        data.setdefault("trailing", {})
        data.setdefault("entries", {})
        data.setdefault("regime", {})
        data.setdefault("orders", {})
        data.setdefault("inverse_cascade", {})
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


class LifecycleLedger:
    def __init__(self, path: Path = LIFECYCLE_PATH_DEFAULT) -> None:
        self.path = path

    def record(self, event_type: str, **fields: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "event_type": event_type,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **{key: lifecycle_json_value(value) for key, value in fields.items()},
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records


class OrderLifecycleTracker:
    ACCEPTED_STATUSES = {
        "accepted",
        "accepted_for_bidding",
        "new",
        "pending_new",
        "partially_filled",
        "filled",
        "done_for_day",
    }
    TERMINAL_STATUSES = {"filled", "canceled", "expired", "rejected"}

    def __init__(
        self,
        client: AlpacaClient,
        state_store: BotStateStore,
        lifecycle_ledger: LifecycleLedger,
        runtime: str,
        dry_run: bool,
    ) -> None:
        self.client = client
        self.state_store = state_store
        self.lifecycle_ledger = lifecycle_ledger
        self.runtime = runtime
        self.dry_run = dry_run

    def track_submitted_order(
        self,
        order: dict[str, Any] | None,
        bot_name: str | None,
        reason: str,
        lifecycle_context: dict[str, Any] | None = None,
    ) -> None:
        order_id = self._order_id(order)
        if order_id is None or order is None:
            return

        metadata = {
            "bot": bot_name,
            "reason": reason,
            "symbol": order.get("symbol"),
            "side": order.get("side"),
            "last_status": None,
            "last_filled_qty": "0",
            "position_lifecycle_state": self._position_lifecycle_state(
                self._order_side(order, {}),
                "submitted",
                Decimal("0"),
            ),
            "position_opened_recorded": False,
            "position_closed_recorded": False,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        if lifecycle_context:
            metadata["lifecycle_context"] = lifecycle_context
        self.state_store.track_order(order_id, metadata)
        self.reconcile_order(order_id, order)

    def reconcile_pending_orders(self) -> None:
        for order_id in list(self.state_store.get_pending_orders().keys()):
            try:
                order = self.client.get_order(order_id)
            except BotError as exc:
                print(f"[ORDER] {order_id}: reconciliation failed: {exc}")
                continue
            self.reconcile_order(order_id, order)

    def reconcile_order(
        self,
        order_id: str,
        order: dict[str, Any],
    ) -> None:
        pending = self.state_store.get_pending_order(order_id) or {}
        status = self._order_status(order)
        side = self._order_side(order, pending)
        symbol = self._order_symbol(order, pending)
        filled_qty = self._filled_qty(order)
        previous_status = pending.get("last_status")
        previous_filled_qty = optional_decimal_from_api(
            pending.get("last_filled_qty"),
            "last filled qty",
        ) or Decimal("0")
        filled_avg_price = optional_decimal_from_api(
            order.get("filled_avg_price"),
            "filled avg price",
        )
        bot_name = self._field(order, pending, "bot")
        reason = self._field(order, pending, "reason")
        context_fields = self._context_fields(pending)
        position_lifecycle_state = self._position_lifecycle_state(
            side,
            status,
            filled_qty,
        )

        if (
            status in self.ACCEPTED_STATUSES
            and status != previous_status
            and not pending.get("accepted_recorded")
        ):
            self._record(
                LIFECYCLE_ORDER_ACCEPTED,
                order_id=order_id,
                bot=bot_name,
                symbol=symbol,
                side=side,
                status=status,
                reason=reason,
                position_lifecycle_state=position_lifecycle_state,
                order=order,
                **context_fields,
            )
            pending["accepted_recorded"] = True

        if (
            status == "rejected"
            and status != previous_status
            and not pending.get("rejected_recorded")
        ):
            self._record(
                LIFECYCLE_ORDER_REJECTED,
                order_id=order_id,
                bot=bot_name,
                symbol=symbol,
                side=side,
                status=status,
                reason=reason,
                error=str(order.get("reject_reason") or "order rejected"),
                position_lifecycle_state=position_lifecycle_state,
                order=order,
                **context_fields,
            )
            pending["rejected_recorded"] = True

        if filled_qty > previous_filled_qty:
            fill_event = (
                LIFECYCLE_FULL_FILL
                if status == "filled"
                else LIFECYCLE_PARTIAL_FILL
            )
            fill_delta = filled_qty - previous_filled_qty
            self._record(
                fill_event,
                order_id=order_id,
                bot=bot_name,
                symbol=symbol,
                side=side,
                status=status,
                filled_qty=filled_qty,
                fill_delta_qty=fill_delta,
                filled_avg_price=filled_avg_price,
                reason=reason,
                position_lifecycle_state=position_lifecycle_state,
                order=order,
                **context_fields,
            )
            if side == "buy" and not pending.get("position_opened_recorded"):
                self._record(
                    LIFECYCLE_POSITION_OPENED,
                    order_id=order_id,
                    bot=bot_name,
                    symbol=symbol,
                    side=side,
                    qty=filled_qty,
                    avg_entry_price=filled_avg_price,
                    reason=reason,
                    position_lifecycle_state=position_lifecycle_state,
                    **context_fields,
                )
                pending["position_opened_recorded"] = True
            if (
                side == "sell"
                and status == "filled"
                and not pending.get("position_closed_recorded")
            ):
                self._record(
                    LIFECYCLE_POSITION_CLOSED,
                    order_id=order_id,
                    bot=bot_name,
                    symbol=symbol,
                    side=side,
                    qty=filled_qty,
                    exit_price=filled_avg_price,
                    reason=reason,
                    position_lifecycle_state=position_lifecycle_state,
                    **context_fields,
                )
                pending["position_closed_recorded"] = True

        pending.update(
            {
                "bot": bot_name,
                "reason": reason,
                "symbol": symbol,
                "side": side,
                "last_status": status,
                "last_filled_qty": format_decimal(filled_qty),
                "position_lifecycle_state": position_lifecycle_state,
                "accepted_recorded": pending.get("accepted_recorded", False),
                "position_opened_recorded": pending.get(
                    "position_opened_recorded",
                    False,
                ),
                "position_closed_recorded": pending.get(
                    "position_closed_recorded",
                    False,
                ),
                "rejected_recorded": pending.get("rejected_recorded", False),
            }
        )
        if context_fields:
            pending["lifecycle_context"] = context_fields["lifecycle_context"]

        if status in self.TERMINAL_STATUSES:
            self.state_store.clear_order(order_id)
        else:
            self.state_store.track_order(order_id, pending)

    def _record(self, event_type: str, **fields: Any) -> None:
        payload = {
            "runtime": self.runtime,
            "dry_run": self.dry_run,
        }
        payload.update(fields)
        self.lifecycle_ledger.record(event_type, **payload)

    def _field(
        self,
        order: dict[str, Any],
        pending: dict[str, Any],
        key: str,
    ) -> str | None:
        value = order.get(key) or pending.get(key)
        return str(value) if value not in (None, "") else None

    def _context_fields(self, pending: dict[str, Any]) -> dict[str, Any]:
        context = pending.get("lifecycle_context")
        if isinstance(context, dict):
            return {"lifecycle_context": context}
        return {}

    def _position_lifecycle_state(
        self,
        side: str | None,
        status: str,
        filled_qty: Decimal,
    ) -> str | None:
        if side == "buy":
            if status == "filled":
                return POSITION_LIFECYCLE_OPEN
            if status in {"canceled", "expired", "rejected"} and filled_qty <= 0:
                return POSITION_LIFECYCLE_CLOSED
            return POSITION_LIFECYCLE_OPENING
        if side == "sell":
            if status == "filled":
                return POSITION_LIFECYCLE_CLOSED
            return POSITION_LIFECYCLE_CLOSING
        return None

    def _order_id(self, order: dict[str, Any] | None) -> str | None:
        if not order:
            return None
        value = order.get("id")
        return str(value) if value else None

    def _order_status(self, order: dict[str, Any]) -> str:
        return str(order.get("status") or "unknown").lower()

    def _order_side(
        self,
        order: dict[str, Any],
        pending: dict[str, Any],
    ) -> str | None:
        value = order.get("side") or pending.get("side")
        return str(value).lower() if value else None

    def _order_symbol(
        self,
        order: dict[str, Any],
        pending: dict[str, Any],
    ) -> str | None:
        value = order.get("symbol") or pending.get("symbol")
        return str(value) if value else None

    def _filled_qty(self, order: dict[str, Any]) -> Decimal:
        filled_qty = optional_decimal_from_api(order.get("filled_qty"), "filled qty")
        if filled_qty is not None:
            return filled_qty
        if self._order_status(order) == "filled":
            return optional_decimal_from_api(order.get("qty"), "order qty") or Decimal(
                "0"
            )
        return Decimal("0")


class TrailingStopBot:
    def __init__(
        self,
        config: BotConfig,
        client: AlpacaClient,
        state_store: BotStateStore | None = None,
        market_data: Any | None = None,
        lifecycle_ledger: LifecycleLedger | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.state_store = state_store or BotStateStore()
        self.market_data = market_data
        self.lifecycle_ledger = lifecycle_ledger or LifecycleLedger()
        self.order_tracker = OrderLifecycleTracker(
            self.client,
            self.state_store,
            self.lifecycle_ledger,
            "TrailingStopBot",
            self.config.dry_run,
        )

    def _record_lifecycle(self, event_type: str, **fields: Any) -> None:
        payload = {
            "runtime": "TrailingStopBot",
            "dry_run": self.config.dry_run,
        }
        payload.update(fields)
        self.lifecycle_ledger.record(event_type, **payload)

    def _broker_rejection_payload(
        self,
        exc: BotError,
        side: str,
        symbol: str,
    ) -> dict[str, Any]:
        return broker_constraint_payload(
            classify_broker_error(str(exc), side=side, symbol=symbol)
        )

    def run_forever(self) -> None:
        print(
            f"Starting {self.config.symbol} bot. "
            f"dry_run={self.config.dry_run}, poll_seconds={self.config.poll_seconds}"
        )
        while True:
            try:
                self.run_once()
            except BotError as exc:
                print(f"[error] {exc}", file=sys.stderr)
            time.sleep(self.config.poll_seconds)

    def run_once(self) -> None:
        clock = self.client.get_clock()
        account = self.client.get_account()
        market_open = bool(clock.get("is_open"))
        next_close, seconds_to_close, closeout_due = closeout_status(
            clock,
            self.config.close_liquidate_minutes,
        )
        next_close_text = next_close.isoformat(timespec="seconds") if next_close else "unknown"
        print(
            f"[{datetime.now().isoformat(timespec='seconds')}] "
            f"market_open={market_open} "
            f"next_close={next_close_text} "
            f"buying_power={account.get('buying_power')} "
            f"portfolio_value={account.get('portfolio_value')}"
        )
        self.order_tracker.reconcile_pending_orders()

        symbol = self.config.symbol
        orders = self.client.list_open_orders()
        symbol_orders = [order for order in orders if order.get("symbol") == symbol]
        position = self.client.get_position(symbol)

        if position:
            if closeout_due:
                self._liquidate_before_close(
                    symbol,
                    position,
                    symbol_orders,
                    seconds_to_close,
                )
                return
            self._manage_trailing_stop(symbol, position, symbol_orders)
            return

        self.state_store.clear_symbol(symbol)

        if closeout_due:
            print(
                f"{symbol}: inside final {self.config.close_liquidate_minutes} "
                "minutes before close; no new entry orders will be submitted."
            )
            return

        if not market_open:
            print(f"{symbol}: market is closed; no new entry orders will be submitted.")
            return

        if any(order.get("side") == "buy" for order in symbol_orders):
            print(f"{symbol}: buy order already open; waiting.")
            return

        self._maybe_enter(symbol)

    def _liquidate_before_close(
        self,
        symbol: str,
        position: dict[str, Any],
        symbol_orders: list[dict[str, Any]],
        seconds_to_close: float | None,
    ) -> None:
        if any(order.get("side") == "sell" for order in symbol_orders):
            print(f"{symbol}: closeout window active, sell order already open.")
            return
        if any(order.get("side") == "buy" for order in symbol_orders):
            print(f"{symbol}: closeout window active, buy order still open; waiting.")
            return

        qty = decimal_from_api(position.get("qty"), "position qty")
        if qty <= 0:
            print(f"{symbol}: closeout window active, no long position to sell.")
            return

        qty = qty.quantize(FRACTIONAL_QTY_STEP, rounding=ROUND_DOWN)
        minutes_text = "unknown"
        if seconds_to_close is not None:
            minutes_text = f"{max(seconds_to_close, 0) / 60:.1f}"
        print(
            f"{symbol}: market closes in {minutes_text} minutes; "
            f"selling all shares qty={format_decimal(qty)}."
        )
        self._record_lifecycle(
            LIFECYCLE_INTENDED_EXIT,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason="closeout_window",
            seconds_to_close=seconds_to_close,
        )
        try:
            order = self.client.submit_market_sell_qty(symbol, qty)
        except BotError as exc:
            self._record_lifecycle(
                LIFECYCLE_ORDER_REJECTED,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="closeout_window",
                error=str(exc),
                broker_constraint=self._broker_rejection_payload(exc, "sell", symbol),
            )
            raise
        self._record_lifecycle(
            LIFECYCLE_ORDER_SUBMITTED,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason="closeout_window",
            order=order,
        )
        self.order_tracker.track_submitted_order(order, None, "closeout_window")
        self.state_store.clear_symbol(symbol)

    def _manage_trailing_stop(
        self,
        symbol: str,
        position: dict[str, Any],
        symbol_orders: list[dict[str, Any]],
        require_live_mark: bool = False,
    ) -> None:
        if any(order.get("side") == "sell" for order in symbol_orders):
            print(f"{symbol}: sell order already open; waiting for it to resolve.")
            return
        if any(order.get("side") == "buy" for order in symbol_orders):
            print(f"{symbol}: buy order still open; trailing stop waiting for it to resolve.")
            return

        qty = decimal_from_api(position.get("qty"), "position qty")
        if qty <= 0:
            print(f"{symbol}: non-long position qty={qty}; no trailing stop submitted.")
            return

        current_price = self._latest_price(symbol, require_live_mark=require_live_mark)
        if current_price is None:
            print(f"{symbol}: no recent price available; trailing stop not evaluated.")
            return

        avg_entry_price = decimal_from_api(
            position.get("avg_entry_price", current_price), "avg entry price"
        )
        self._maybe_update_inverse_cascade_proven_state(symbol, avg_entry_price)
        high_water_mark = self.state_store.get_high_water_mark(symbol)
        reference_price = max(current_price, avg_entry_price)

        if high_water_mark is None or reference_price > high_water_mark:
            high_water_mark = reference_price
            self.state_store.set_high_water_mark(symbol, high_water_mark)

        trail_percent = self._effective_trail_percent(symbol)
        stop_price = high_water_mark * (
            Decimal("1") - (trail_percent / Decimal("100"))
        )
        qty = qty.quantize(FRACTIONAL_QTY_STEP, rounding=ROUND_DOWN)

        print(
            f"[RISK] {symbol}: position qty={format_decimal(qty)} current={current_price:.4f} "
            f"hwm={high_water_mark:.4f} trail={trail_percent}% bot_stop={stop_price:.4f}"
        )
        stop_breached = current_price <= stop_price
        self._record_lifecycle(
            LIFECYCLE_POSITION_MANAGED,
            symbol=symbol,
            side="long",
            qty=qty,
            current_price=current_price,
            avg_entry_price=avg_entry_price,
            high_water_mark=high_water_mark,
            stop_price=stop_price,
            trail_percent=trail_percent,
            stop_breached=stop_breached,
            require_live_mark=require_live_mark,
        )

        if stop_breached:
            print(f"[RISK] {symbol}: trailing stop breached; submitting fractional market sell.")
            self._mark_inverse_cascade_trailing_stop_lockout(symbol)
            self._record_lifecycle(
                LIFECYCLE_INTENDED_EXIT,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="trailing_stop_breached",
                current_price=current_price,
                stop_price=stop_price,
                trail_percent=trail_percent,
                high_water_mark=high_water_mark,
            )
            try:
                order = self.client.submit_market_sell_qty(symbol, qty)
            except BotError as exc:
                self._record_lifecycle(
                    LIFECYCLE_ORDER_REJECTED,
                    symbol=symbol,
                    side="sell",
                    qty=qty,
                    reason="trailing_stop_breached",
                    error=str(exc),
                    broker_constraint=self._broker_rejection_payload(exc, "sell", symbol),
                )
                raise
            self._record_lifecycle(
                LIFECYCLE_ORDER_SUBMITTED,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="trailing_stop_breached",
                order=order,
            )
            self.order_tracker.track_submitted_order(
                order,
                None,
                "trailing_stop_breached",
            )
            self.state_store.clear_symbol(symbol)
        else:
            print(f"[RISK] {symbol}: trailing stop holding.")

    def _mark_inverse_cascade_trailing_stop_lockout(self, symbol: str) -> None:
        if (
            symbol != SOXS
            or self.config.inverse_cascade_mode != INVERSE_CASCADE_MODE_SUSTAINED
        ):
            return
        state = self.state_store.get_inverse_cascade_state()
        session_date = datetime.now(timezone.utc).astimezone(NY_TZ).date().isoformat()
        if (
            state.get("mode") != INVERSE_CASCADE_MODE_SUSTAINED
            or state.get("session_date") != session_date
            or not state.get("entered_at")
        ):
            return
        state["lockout_active"] = True
        state["stopped_out_at"] = datetime.now(timezone.utc).isoformat()
        state["stopped_out_reason"] = "trailing_stop_breached"
        state["invalidation_started_at"] = None
        self.state_store.set_inverse_cascade_state(state)

    def _effective_trail_percent(self, symbol: str) -> Decimal:
        if (
            symbol == SOXS
            and self.config.inverse_cascade_mode == INVERSE_CASCADE_MODE_SUSTAINED
        ):
            state = self.state_store.get_inverse_cascade_state()
            session_date = datetime.now(timezone.utc).astimezone(NY_TZ).date().isoformat()
            if (
                state.get("mode") == INVERSE_CASCADE_MODE_SUSTAINED
                and state.get("session_date") == session_date
                and state.get("entered_at")
            ):
                if state.get("proven_at"):
                    max_mfe = optional_decimal_from_api(
                        state.get("max_favorable_excursion_percent"),
                        "inverse cascade max favorable excursion",
                    )
                    if (
                        max_mfe is None
                        or max_mfe
                        < self.config.inverse_cascade_proven_trail_tighten_mfe_percent
                    ):
                        return self.config.inverse_cascade_proven_trail_percent
                return self.config.inverse_cascade_trail_percent
        return self.config.trail_percent

    def _latest_price(
        self,
        symbol: str,
        require_live_mark: bool = False,
    ) -> Decimal | None:
        max_age_seconds = MARKET_DATA_MAX_AGE_SECONDS if require_live_mark else None
        current_mark = self._latest_market_mark(symbol, max_age_seconds=max_age_seconds)
        if current_mark is not None:
            return current_mark

        if require_live_mark:
            return None

        bars = self._recent_bars(symbol, 1)
        prices = latest_close_prices(bars)
        if not prices:
            return None
        return prices[-1]

    def _sma_snapshot(
        self,
        symbol: str,
        require_cross_context: bool = True,
    ) -> SmaSnapshot | None:
        bars_needed = self.config.slow_sma_minutes + (1 if require_cross_context else 0)
        bars = self._recent_bars(symbol, bars_needed)
        prices = latest_close_prices(bars)
        latest_bar = latest_complete_bar(bars)
        latest_bar_time = (
            parse_market_timestamp(latest_bar.get("t")) if latest_bar else None
        )
        if len(prices) < bars_needed:
            reason = "warming up." if not require_cross_context else "waiting for more data."
            print(
                f"{symbol}: need {bars_needed} one-minute bars, got {len(prices)}; "
                f"{reason}"
            )
            return None

        fast_now_values = prices[-self.config.fast_sma_minutes :]
        fast_prev_values = prices[-(self.config.fast_sma_minutes + 1) : -1]
        slow_now_values = prices[-self.config.slow_sma_minutes :]
        slow_prev_values = prices[-(self.config.slow_sma_minutes + 1) : -1]

        return SmaSnapshot(
            symbol=symbol,
            price=prices[-1],
            fast_sma=sma(fast_now_values),
            slow_sma=sma(slow_now_values),
            fast_now_values=fast_now_values,
            fast_prev_values=fast_prev_values,
            slow_now_values=slow_now_values,
            slow_prev_values=slow_prev_values,
            latest_bar_time=latest_bar_time,
        )

    def _recent_bars(self, symbol: str, minutes: int) -> list[dict[str, Any]]:
        if self.market_data is not None:
            return self.market_data.get_recent_bars(symbol, minutes)
        return self.client.get_recent_bars(symbol, minutes)

    def _maybe_update_inverse_cascade_proven_state(
        self,
        symbol: str,
        avg_entry_price: Decimal,
    ) -> dict[str, Any]:
        if (
            self.config.inverse_cascade_mode != INVERSE_CASCADE_MODE_SUSTAINED
            or symbol != SOXS
            or avg_entry_price <= 0
        ):
            return {}
        state = self.state_store.get_inverse_cascade_state()
        session_date = datetime.now(timezone.utc).astimezone(NY_TZ).date().isoformat()
        if (
            state.get("mode") != INVERSE_CASCADE_MODE_SUSTAINED
            or state.get("session_date") != session_date
            or not state.get("entered_at")
        ):
            return state

        highs = [
            value
            for bar in self._session_bars(symbol)
            if (value := self._bar_decimal(bar, "h", "c", "o")) is not None
        ]
        if not highs:
            return state

        high_price = max(highs)
        mfe_percent = (
            (high_price - avg_entry_price) / avg_entry_price * Decimal("100")
        )
        previous_mfe = optional_decimal_from_api(
            state.get("max_favorable_excursion_percent"),
            "inverse cascade max favorable excursion",
        )
        changed = False
        if previous_mfe is None or mfe_percent > previous_mfe:
            state["max_favorable_excursion_percent"] = format_decimal(mfe_percent)
            state["max_favorable_price"] = format_decimal(high_price)
            changed = True

        if (
            not state.get("proven_at")
            and mfe_percent >= self.config.inverse_cascade_proven_mfe_percent
        ):
            state["proven_at"] = datetime.now(timezone.utc).isoformat()
            state["proven_mfe_percent"] = format_decimal(mfe_percent)
            state["proven_threshold_percent"] = format_decimal(
                self.config.inverse_cascade_proven_mfe_percent
            )
            changed = True

        if changed:
            self.state_store.set_inverse_cascade_state(state)
        return state

    def _session_bars(self, symbol: str) -> list[dict[str, Any]]:
        session_date = datetime.now(timezone.utc).astimezone(NY_TZ).date().isoformat()
        return [
            bar
            for bar in self._recent_bars(symbol, 420)
            if self._record_date(bar.get("t")) == session_date
        ]

    def _record_date(self, value: Any) -> str | None:
        parsed = parse_market_timestamp(value)
        if parsed is None:
            return None
        return parsed.astimezone(NY_TZ).date().isoformat()

    def _bar_decimal(
        self,
        bar: dict[str, Any],
        *field_names: str,
    ) -> Decimal | None:
        for field_name in field_names:
            value = optional_decimal_from_api(bar.get(field_name), field_name)
            if value is not None:
                return value
        return None

    def _latest_market_mark(
        self,
        symbol: str,
        max_age_seconds: int | None = None,
    ) -> Decimal | None:
        data_source = self.market_data or self.client

        quote = data_source.get_latest_quote(symbol)
        if quote and self._market_timestamp_is_recent(quote.get("t"), max_age_seconds):
            bid = optional_decimal_from_api(quote.get("bp"), "latest quote bid")
            ask = optional_decimal_from_api(quote.get("ap"), "latest quote ask")
            if bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid:
                return (bid + ask) / Decimal("2")

        trade = data_source.get_latest_trade(symbol)
        if trade and self._market_timestamp_is_recent(trade.get("t"), max_age_seconds):
            return optional_decimal_from_api(trade.get("p"), "latest trade price")

        return None

    def _market_timestamp_is_recent(
        self,
        value: Any,
        max_age_seconds: int | None,
    ) -> bool:
        if max_age_seconds is None:
            return True
        timestamp = parse_market_timestamp(value)
        current_age = age_seconds(timestamp)
        return current_age is not None and current_age <= max_age_seconds

    def _maybe_enter(self, symbol: str) -> None:
        asset = self.client.get_asset(symbol)
        if not asset.get("fractionable"):
            print(f"{symbol}: asset is not fractionable; no notional entry submitted.")
            return

        snapshot = self._sma_snapshot(symbol)
        if snapshot is None:
            return

        has_entry_signal = snapshot.crossed_above

        print(
            f"{symbol}: last={snapshot.price:.4f} "
            f"fast_sma={snapshot.fast_sma:.4f} slow_sma={snapshot.slow_sma:.4f} "
            f"entry_signal={has_entry_signal}"
        )

        if not has_entry_signal:
            print(f"{symbol}: no entry signal.")
            return

        print(
            f"{symbol}: entry signal detected; "
            f"submitting ${self.config.position_notional} market buy."
        )
        self._record_lifecycle(
            LIFECYCLE_INTENDED_ENTRY,
            symbol=symbol,
            side="buy",
            notional=self.config.position_notional,
            reason="sma_crossed_above",
        )
        try:
            order = self.client.submit_market_buy(symbol, self.config.position_notional)
        except BotError as exc:
            self._record_lifecycle(
                LIFECYCLE_ORDER_REJECTED,
                symbol=symbol,
                side="buy",
                notional=self.config.position_notional,
                reason="sma_crossed_above",
                error=str(exc),
                broker_constraint=self._broker_rejection_payload(exc, "buy", symbol),
            )
            raise
        self._record_lifecycle(
            LIFECYCLE_ORDER_SUBMITTED,
            symbol=symbol,
            side="buy",
            notional=self.config.position_notional,
            reason="sma_crossed_above",
            order=order,
        )
        self.order_tracker.track_submitted_order(order, None, "sma_crossed_above")


class RegimeDetector:
    def __init__(
        self,
        config: BotConfig,
        client: AlpacaClient,
        market_data: Any | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.market_data = market_data

    def detect(self) -> tuple[RegimeSignal | None, SmaSnapshot | None]:
        probe = TrailingStopBot(
            config_for_symbol(self.config, SOXL),
            self.client,
            market_data=self.market_data,
        )
        snapshot = probe._sma_snapshot(SOXL, require_cross_context=False)
        if snapshot is None:
            return None, None

        gap_percent = snapshot.gap_percent
        if gap_percent < self.config.regime_gap_threshold:
            regime = SIDEWAYS
        elif snapshot.fast_sma > snapshot.slow_sma:
            regime = UPTREND
        else:
            regime = DOWNTREND

        return (
            RegimeSignal(
                source_symbol=SOXL,
                price=snapshot.price,
                fast_sma=snapshot.fast_sma,
                slow_sma=snapshot.slow_sma,
                gap_percent=gap_percent,
                regime=regime,
            ),
            snapshot,
        )


class RegimeRouter:
    def route(self, regime: str) -> BotRoute:
        if regime == UPTREND:
            return BotRoute(MOMENTUM_BOT, SOXL, True)
        if regime == DOWNTREND:
            return BotRoute(INVERSE_BOT, SOXS, True)
        return BotRoute(CHOP_BOT, SOXL, True)


class EdgeWalkerBot:
    basket_symbols = (SOXL, SOXS)

    def __init__(
        self,
        config: BotConfig,
        client: AlpacaClient,
        state_store: BotStateStore | None = None,
        market_data: Any | None = None,
        lifecycle_ledger: LifecycleLedger | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.state_store = state_store or BotStateStore()
        self.market_data = market_data
        self.lifecycle_ledger = lifecycle_ledger or LifecycleLedger()
        self.order_tracker = OrderLifecycleTracker(
            self.client,
            self.state_store,
            self.lifecycle_ledger,
            "EdgeWalker",
            self.config.dry_run,
        )
        self._latest_freshness: MarketDataFreshness | None = None
        self._adaptive_posture: AdaptivePosture | None = None
        self._trend_trust: dict[str, Any] | None = None
        self._inverse_cascade_context: dict[str, Any] | None = None

    def _record_lifecycle(self, event_type: str, **fields: Any) -> None:
        payload = {
            "runtime": "EdgeWalker",
            "dry_run": self.config.dry_run,
        }
        payload.update(fields)
        self.lifecycle_ledger.record(event_type, **payload)

    def _broker_rejection_payload(
        self,
        exc: BotError,
        side: str,
        symbol: str,
    ) -> dict[str, Any]:
        return broker_constraint_payload(
            classify_broker_error(str(exc), side=side, symbol=symbol)
        )

    def _route_invalidation_context(
        self,
        symbol: str,
        position: dict[str, Any] | None,
        qty: Decimal,
        regime: str,
        active_bot: str,
        owner: str | None,
    ) -> dict[str, Any]:
        return {
            "kind": "route_invalidation_exit",
            "outcome_status": "PENDING_FOLLOW_THROUGH",
            "outcome_classification": None,
            "outcome_candidates": [
                "DEFENSIVE_SAVE",
                "PREMATURE_CUT",
                "PROFITABLE_HANDOFF",
                "NEUTRAL_EXIT",
            ],
            "invalidated_symbol": symbol,
            "owner_bot": owner or "UNKNOWN",
            "active_bot": active_bot,
            "regime_at_invalidation": regime,
            "qty": qty,
            "avg_entry_price": self._position_optional_decimal(
                position,
                "avg_entry_price",
            ),
            "current_price": self._position_optional_decimal(position, "current_price"),
            "market_value": self._position_optional_decimal(position, "market_value"),
            "unrealized_pl": self._position_optional_decimal(
                position,
                "unrealized_pl",
            ),
            "unrealized_pl_percent": self._position_optional_decimal(
                position,
                "unrealized_plpc",
            ),
            "high_water_mark": self.state_store.get_high_water_mark(symbol),
            "captured_at": datetime.now(timezone.utc),
        }

    def _position_optional_decimal(
        self,
        position: dict[str, Any] | None,
        field_name: str,
    ) -> Decimal | None:
        if not position:
            return None
        return optional_decimal_from_api(position.get(field_name), field_name)

    def run_once(self) -> EdgeWalkerStatus:
        self._latest_freshness = None
        self._adaptive_posture = None
        self._trend_trust = None
        self._inverse_cascade_context = None
        clock = self.client.get_clock()
        account = self.client.get_account()
        market_open = bool(clock.get("is_open"))
        next_open = parse_clock_time(clock.get("next_open"), "next_open")
        next_close, seconds_to_close, closeout_due = closeout_status(
            clock,
            self.config.close_liquidate_minutes,
        )
        next_close_text = next_close.isoformat(timespec="seconds") if next_close else "unknown"
        checked_at = datetime.now().isoformat(timespec="seconds")
        print(
            f"[SYSTEM] [{checked_at}] "
            f"edgewalker=True market_open={market_open} "
            f"next_close={next_close_text} "
            f"buying_power={account.get('buying_power')} "
            f"portfolio_value={account.get('portfolio_value')}"
        )
        self.order_tracker.reconcile_pending_orders()
        if market_open:
            self._repair_stale_market_bars()

        detector = RegimeDetector(self.config, self.client, self.market_data)
        signal, soxl_snapshot = detector.detect()
        if signal is None or soxl_snapshot is None:
            self.state_store.set_regime_state(WARMUP, Decimal("0"))
            self._print_market_data_status(SOXL)
            print(
                "[REGIME] regime=WARMUP active_bot=NONE routed_symbol=NONE "
                "entry_signal=False action_taken=collecting_data"
            )
            positions = {
                symbol: self.client.get_position(symbol)
                for symbol in self.basket_symbols
            }
            if closeout_due:
                orders = self.client.list_open_orders()
                action_taken = self._liquidate_all_before_close(
                    positions,
                    orders,
                    seconds_to_close,
                )
                return self._build_status(
                    checked_at,
                    market_open,
                    next_open,
                    next_close,
                    account,
                    None,
                    None,
                    positions,
                    False,
                    action_taken,
                    regime_override=WARMUP,
                )

            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                None,
                None,
                positions,
                False,
                "collecting_data",
                regime_override=WARMUP,
            )

        previous_regime_state = self.state_store.get_regime_state()
        signal = self._apply_regime_hysteresis(signal, previous_regime_state)
        self.state_store.set_regime_state(signal.regime, signal.gap_percent)
        current_regime_state = self.state_store.get_regime_state()
        self._trend_trust = self._trend_trust_telemetry(
            signal,
            soxl_snapshot,
            current_regime_state,
        )
        route = RegimeRouter().route(signal.regime)
        self._v9_update_momentum_context(self._v9_authority_evaluation_route(route))
        route = self._inverse_cascade_route_override(route)
        route = self._apply_enabled_bot_mask(route)
        routed_symbol = route.routed_symbol or "NONE"
        strength = self._regime_strength(signal)
        print(
            f"[REGIME] {SOXL} regime check: price={signal.price:.4f} "
            f"fast_sma={signal.fast_sma:.4f} slow_sma={signal.slow_sma:.4f} "
            f"gap={signal.gap_percent:.2f}% threshold={self.config.regime_gap_threshold}% "
            f"exit_threshold={self._regime_exit_threshold()}% "
            f"strength={strength}"
        )
        print(
            f"[ROUTER] regime={signal.regime} active_bot={route.active_bot} "
            f"routed_symbol={routed_symbol}"
        )
        self._print_trend_trust()

        orders = self.client.list_open_orders()
        positions = {symbol: self.client.get_position(symbol) for symbol in self.basket_symbols}
        freshness = self._market_data_freshness(SOXL, soxl_snapshot)
        self._latest_freshness = freshness

        if closeout_due:
            action_taken = self._liquidate_all_before_close(positions, orders, seconds_to_close)
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                action_taken,
            )

        if not market_open:
            print(
                "[SYSTEM] market is closed; "
                "entry_signal=False action_taken=no_entry"
            )
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                "no_entry",
            )

        self._maybe_update_adaptive_posture(
            signal,
            route,
            freshness,
            positions,
            account,
            previous_regime_state,
        )

        market_data_blocks_entries = freshness.is_stale or self._market_data_blocks_trading(
            SOXL
        )
        if market_data_blocks_entries:
            active_symbol, active_position = self._active_position(positions)
            if active_symbol and active_position:
                symbol_orders = [
                    order for order in orders if order.get("symbol") == active_symbol
                ]
                print(
                    "[DATA] bar data is not fresh enough for entries; "
                    "regime exits paused, live risk management remains active."
                )
                risk_bot = TrailingStopBot(
                    config_for_symbol(self.config, active_symbol),
                    self.client,
                    self.state_store,
                    self.market_data,
                    self.lifecycle_ledger,
                )
                risk_bot._manage_trailing_stop(
                    active_symbol,
                    active_position,
                    symbol_orders,
                    require_live_mark=True,
                )
                print("entry_signal=False action_taken=manage_open_position_stale_bars")
                return self._build_status(
                    checked_at,
                    market_open,
                    next_open,
                    next_close,
                    account,
                    signal,
                    route,
                    positions,
                    False,
                    "manage_open_position_stale_bars",
                )

        if freshness.is_stale:
            print(
                "[DATA] stale market data; "
                "entry_signal=False action_taken=wait_stale_market_data"
            )
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                "wait_stale_market_data",
            )

        if self._market_data_blocks_trading(SOXL):
            status = self._market_data_status(SOXL)
            print(
                "[DATA] stream market data is not live; "
                f"data_status={status.get('data_status')} "
                "entry_signal=False action_taken=wait_stream_market_data"
            )
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                "wait_stream_market_data",
            )

        stale_symbol = self._stale_symbol(route, positions)
        if stale_symbol:
            stale_owner = self.state_store.get_position_owner(stale_symbol)
            grace_action = self._maybe_hold_inverse_cascade_route_invalidated_position(
                stale_symbol,
                positions[stale_symbol],
                orders,
                signal.regime,
                route.active_bot,
                stale_owner,
            )
            if grace_action:
                return self._build_status(
                    checked_at,
                    market_open,
                    next_open,
                    next_close,
                    account,
                    signal,
                    route,
                    positions,
                    False,
                    grace_action,
                )
            action_taken = self._close_stale_position(
                stale_symbol,
                positions[stale_symbol],
                orders,
                signal.regime,
                route.active_bot,
                stale_owner,
            )
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                action_taken,
            )

        self._clear_inverse_cascade_invalidation_when_route_valid(route, positions)

        authority_exit = self._maybe_exit_momentum_authority_revoked_position(
            route,
            positions,
            orders,
            signal.regime,
        )
        if authority_exit:
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                authority_exit,
            )

        if not route.allows_entry or route.routed_symbol is None:
            print("[ENTRY] BLOCKED reason=route_disallows_entry")
            print("entry_signal=False action_taken=chop_no_trade_placeholder")
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                "chop_no_trade_placeholder",
            )

        routed_position = positions.get(route.routed_symbol)
        routed_orders = [
            order for order in orders if order.get("symbol") == route.routed_symbol
        ]
        routed_bot = TrailingStopBot(
            config_for_symbol(self.config, route.routed_symbol),
            self.client,
            self.state_store,
            self.market_data,
            self.lifecycle_ledger,
        )

        if routed_position:
            if route.active_bot == CHOP_BOT:
                action_taken = self._maybe_exit_chop_position(
                    route.routed_symbol,
                    routed_position,
                    routed_orders,
                    soxl_snapshot,
                )
                if action_taken:
                    return self._build_status(
                        checked_at,
                        market_open,
                        next_open,
                        next_close,
                        account,
                        signal,
                        route,
                        positions,
                        False,
                        action_taken,
                    )

            routed_bot._manage_trailing_stop(route.routed_symbol, routed_position, routed_orders)
            print("entry_signal=False action_taken=manage_open_position")
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                "manage_open_position",
            )

        if any(order.get("side") == "buy" for order in routed_orders):
            print(
                f"[ENTRY] {route.routed_symbol}: buy order already open; "
                "entry_signal=False action_taken=wait_for_open_order"
            )
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                "wait_for_open_order",
            )

        entry_decision = self._entry_decision_for_route(route, soxl_snapshot)
        if entry_decision.signal:
            policy_decision = self._momentum_authority_entry_policy_decision(
                route,
                soxl_snapshot,
            )
            if policy_decision is None:
                policy_decision = self._chop_permission_entry_policy_decision(
                    route,
                    soxl_snapshot,
                )
            if policy_decision is None:
                policy_decision = self._v9_entry_policy_decision(
                    route,
                    soxl_snapshot,
                )
            if policy_decision is None:
                policy_decision = self._v10_entry_policy_decision(
                    route,
                    soxl_snapshot,
                )
            if policy_decision is None:
                policy_decision = self._v8_entry_policy_decision(route, soxl_snapshot)
            if policy_decision is not None:
                entry_decision = policy_decision
        entry_signal = entry_decision.signal
        print(
            f"[ENTRY] {route.active_bot} check: "
            f"entry_signal={entry_signal} reason={entry_decision.reason} "
            f"mode={self._directional_mode_for_route(route)}"
        )
        print(f"entry_signal={entry_signal}")
        if not entry_signal:
            print(
                f"[ENTRY] BLOCKED bot={route.active_bot} "
                f"symbol={route.routed_symbol} reason={entry_decision.reason} "
                f"mode={self._directional_mode_for_route(route)}"
            )
            print("action_taken=no_entry_signal")
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                "no_entry_signal",
            )

        asset = self.client.get_asset(route.routed_symbol)
        if not asset.get("fractionable"):
            print(
                f"[ENTRY] {route.routed_symbol}: asset is not fractionable; "
                "action_taken=no_entry"
            )
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                True,
                "no_entry",
            )

        print(
            f"[ENTRY] APPROVED bot={route.active_bot} "
            f"symbol={route.routed_symbol} reason={entry_decision.reason} "
            f"mode={self._directional_mode_for_route(route)}"
        )
        effective_notional, requested_notional, buying_power = (
            self._effective_position_notional(account)
        )
        if effective_notional is None or effective_notional <= 0:
            print(
                "[ENTRY] BLOCKED reason=insufficient_buying_power "
                f"buying_power={format_decimal(buying_power) if buying_power is not None else 'unknown'}"
            )
            print("entry_signal=False action_taken=insufficient_buying_power")
            return self._build_status(
                checked_at,
                market_open,
                next_open,
                next_close,
                account,
                signal,
                route,
                positions,
                False,
                "insufficient_buying_power",
            )

        allocation_text = (
            f" allocation={format_decimal(self.config.position_allocation_percent)}%"
            if self.config.position_sizing_mode == POSITION_SIZING_DYNAMIC
            else ""
        )
        requested_text = (
            format_decimal(requested_notional) if requested_notional is not None else "unknown"
        )
        buying_power_text = format_decimal(buying_power) if buying_power is not None else "unknown"
        print(
            "[RISK] position sizing: "
            f"mode={self.config.position_sizing_mode}{allocation_text} "
            f"buying_power={buying_power_text} requested=${requested_text} "
            f"effective=${format_decimal(effective_notional)}"
        )
        print(
            f"[TRADE] {route.active_bot}: submitting ${format_decimal(effective_notional)} "
            f"market buy for {route.routed_symbol}."
        )
        lifecycle_context = self._entry_lifecycle_context(
            route,
            entry_decision.reason,
        )
        self._record_lifecycle(
            LIFECYCLE_INTENDED_ENTRY,
            bot=route.active_bot,
            symbol=route.routed_symbol,
            side="buy",
            notional=effective_notional,
            requested_notional=requested_notional,
            buying_power=buying_power,
            position_sizing_mode=self.config.position_sizing_mode,
            position_allocation_percent=self.config.position_allocation_percent,
            regime=signal.regime,
            reason=entry_decision.reason,
            mode=self._directional_mode_for_route(route),
            lifecycle_context=lifecycle_context,
        )
        try:
            order = self.client.submit_market_buy(route.routed_symbol, effective_notional)
        except BotError as exc:
            self._record_lifecycle(
                LIFECYCLE_ORDER_REJECTED,
                bot=route.active_bot,
                symbol=route.routed_symbol,
                side="buy",
                notional=effective_notional,
                requested_notional=requested_notional,
                buying_power=buying_power,
                regime=signal.regime,
                reason=entry_decision.reason,
                mode=self._directional_mode_for_route(route),
                lifecycle_context=lifecycle_context,
                error=str(exc),
                broker_constraint=self._broker_rejection_payload(
                    exc,
                    "buy",
                    route.routed_symbol,
                ),
            )
            raise
        self._record_lifecycle(
            LIFECYCLE_ORDER_SUBMITTED,
            bot=route.active_bot,
            symbol=route.routed_symbol,
            side="buy",
            notional=effective_notional,
            requested_notional=requested_notional,
            buying_power=buying_power,
            regime=signal.regime,
            reason=entry_decision.reason,
            mode=self._directional_mode_for_route(route),
            lifecycle_context=lifecycle_context,
            order=order,
        )
        self.order_tracker.track_submitted_order(
            order,
            route.active_bot,
            entry_decision.reason,
            lifecycle_context,
        )
        self._mark_inverse_cascade_entry(route, entry_decision.reason)
        if not self.config.dry_run:
            self.state_store.set_position_owner(route.routed_symbol, route.active_bot)
            self.state_store.set_last_entry_at(route.active_bot, route.routed_symbol)
        print("action_taken=market_buy")
        return self._build_status(
            checked_at,
            market_open,
            next_open,
            next_close,
            account,
            signal,
            route,
            positions,
            True,
            "market_buy",
        )

    def _build_status(
        self,
        checked_at: str,
        market_open: bool,
        next_open: datetime | None,
        next_close: datetime | None,
        account: dict[str, Any],
        signal: RegimeSignal | None,
        route: BotRoute | None,
        positions: dict[str, dict[str, Any] | None],
        entry_signal: bool | None,
        action_taken: str,
        regime_override: str | None = None,
    ) -> EdgeWalkerStatus:
        position_symbol, position = self._active_position(positions)
        position_owner = None
        high_water_mark = None
        trailing_exit_price = None

        if position_symbol:
            position_owner = self.state_store.get_position_owner(position_symbol)
            high_water_mark = self.state_store.get_high_water_mark(position_symbol)
            if high_water_mark is not None:
                trailing_exit_price = high_water_mark * (
                    Decimal("1") - (self.config.trail_percent / Decimal("100"))
                )

        day_pl, day_pl_percent = self._account_day_pl(account)
        data_status = self._market_data_status(SOXL)
        freshness = self._latest_freshness
        effective_notional, _, _ = self._effective_position_notional(account)
        adaptive = self._adaptive_posture
        effective_directional_mode = self._current_effective_directional_mode()
        inverse_price = self._latest_status_price(SOXS)

        return EdgeWalkerStatus(
            checked_at=checked_at,
            market_open=market_open,
            next_open=next_open.isoformat(timespec="seconds") if next_open else None,
            next_close=next_close.isoformat(timespec="seconds") if next_close else None,
            buying_power=self._raw_text(account.get("buying_power")),
            portfolio_value=self._raw_text(account.get("portfolio_value") or account.get("equity")),
            cash=self._raw_text(account.get("cash")),
            position_sizing_mode=self.config.position_sizing_mode,
            position_allocation_percent=format_decimal(
                self.config.position_allocation_percent
            ),
            effective_position_notional=self._decimal_text(effective_notional),
            directional_mode=self.config.directional_mode,
            effective_directional_mode=effective_directional_mode,
            adaptive_posture=adaptive.selected_mode if adaptive else None,
            adaptive_confidence=adaptive.confidence if adaptive else None,
            adaptive_reasons=list(adaptive.reasons) if adaptive else [],
            adaptive_constraints=list(adaptive.constraints) if adaptive else [],
            adaptive_shadow=bool(adaptive and adaptive.shadow),
            day_pl=self._decimal_text(day_pl),
            day_pl_percent=self._decimal_text(day_pl_percent),
            source_symbol=SOXL,
            source_price=self._decimal_text(signal.price if signal else None),
            inverse_price=self._decimal_text(inverse_price),
            fast_sma=self._decimal_text(signal.fast_sma if signal else None),
            slow_sma=self._decimal_text(signal.slow_sma if signal else None),
            gap_percent=self._decimal_text(signal.gap_percent if signal else None),
            regime=regime_override or (signal.regime if signal else None),
            trend_trust=self._trend_trust,
            active_bot=route.active_bot if route else None,
            routed_symbol=route.routed_symbol if route and route.routed_symbol else None,
            entry_signal=entry_signal,
            action_taken=action_taken,
            position_symbol=position_symbol,
            position_qty=self._raw_text(position.get("qty")) if position else None,
            position_market_value=self._raw_text(position.get("market_value")) if position else None,
            position_avg_entry_price=(
                self._raw_text(position.get("avg_entry_price")) if position else None
            ),
            position_unrealized_pl=(
                self._raw_text(position.get("unrealized_pl")) if position else None
            ),
            position_unrealized_pl_percent=(
                self._raw_text(position.get("unrealized_plpc")) if position else None
            ),
            position_current_price=(
                self._raw_text(position.get("current_price")) if position else None
            ),
            position_owner=position_owner,
            high_water_mark=self._decimal_text(high_water_mark),
            trailing_exit_price=self._decimal_text(trailing_exit_price),
            data_source=data_status.get("data_source"),
            data_feed=data_status.get("data_feed"),
            data_status=data_status.get("data_status"),
            stream_connected=data_status.get("stream_connected"),
            stream_authenticated=data_status.get("stream_authenticated"),
            stream_subscribed=data_status.get("stream_subscribed"),
            stream_error=data_status.get("stream_error"),
            stream_bar_count=data_status.get("stream_bar_count"),
            stream_last_message_at=data_status.get("stream_last_message_at"),
            latest_bar_time=(
                self._time_text(freshness.latest_bar_time)
                if freshness
                else data_status.get("latest_bar_time")
            ),
            bar_age_seconds=(
                self._rounded_seconds(freshness.bar_age_seconds)
                if freshness
                else data_status.get("bar_age_seconds")
            ),
            latest_trade_time=(
                self._time_text(freshness.latest_trade_time)
                if freshness
                else data_status.get("latest_trade_time")
            ),
            trade_age_seconds=(
                self._rounded_seconds(freshness.trade_age_seconds)
                if freshness
                else data_status.get("trade_age_seconds")
            ),
            latest_quote_time=(
                self._time_text(freshness.latest_quote_time)
                if freshness
                else data_status.get("latest_quote_time")
            ),
            quote_age_seconds=(
                self._rounded_seconds(freshness.quote_age_seconds)
                if freshness
                else data_status.get("quote_age_seconds")
            ),
            v9_momentum_context=self._v9_momentum_context_for_status(),
        )

    def _current_effective_directional_mode(self) -> str | None:
        if self.config.directional_mode == DIRECTIONAL_MODE_ADAPTIVE:
            if self._adaptive_posture is None:
                return None
            return self._adaptive_posture.selected_mode
        return self.config.directional_mode

    def _active_position(
        self,
        positions: dict[str, dict[str, Any] | None],
    ) -> tuple[str | None, dict[str, Any] | None]:
        for symbol in self.basket_symbols:
            position = positions.get(symbol)
            if self._position_qty(position) > 0:
                return str(position.get("symbol") or symbol), position
        return None, None

    def _latest_status_price(self, symbol: str) -> Decimal | None:
        try:
            current_mark = self._latest_status_market_mark(symbol)
            if current_mark is not None:
                return current_mark

            data_source = self.market_data or self.client
            bars = data_source.get_recent_bars(symbol, 1)
            prices = latest_close_prices(bars)
            if not prices:
                return None
            return prices[-1]
        except (BotError, KeyError):
            return None

    def _latest_status_market_mark(self, symbol: str) -> Decimal | None:
        data_source = self.market_data or self.client

        quote = data_source.get_latest_quote(symbol)
        if quote:
            bid = optional_decimal_from_api(quote.get("bp"), "latest quote bid")
            ask = optional_decimal_from_api(quote.get("ap"), "latest quote ask")
            if bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid:
                return (bid + ask) / Decimal("2")

        trade = data_source.get_latest_trade(symbol)
        if trade:
            return optional_decimal_from_api(trade.get("p"), "latest trade price")

        return None

    def _effective_position_notional(
        self,
        account: dict[str, Any],
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        buying_power = optional_decimal_from_api(
            account.get("buying_power"),
            "buying power",
        )
        if self.config.position_sizing_mode == POSITION_SIZING_DYNAMIC:
            if buying_power is None:
                return None, None, buying_power
            requested = buying_power * (
                self.config.position_allocation_percent / Decimal("100")
            )
        else:
            requested = self.config.position_notional

        effective = requested
        if buying_power is not None:
            max_notional = buying_power * (
                (Decimal("100") - BUYING_POWER_ORDER_BUFFER_PERCENT) / Decimal("100")
            )
            effective = min(requested, max_notional)

        return (
            effective.quantize(MONEY_STEP, rounding=ROUND_DOWN),
            requested.quantize(MONEY_STEP, rounding=ROUND_DOWN),
            buying_power,
        )

    def _maybe_update_adaptive_posture(
        self,
        signal: RegimeSignal,
        route: BotRoute,
        freshness: MarketDataFreshness,
        positions: dict[str, dict[str, Any] | None],
        account: dict[str, Any],
        previous_regime_state: dict[str, Any] | None = None,
    ) -> None:
        if not self._adaptive_should_evaluate():
            return

        posture = self._select_adaptive_posture(
            signal,
            route,
            freshness,
            positions,
            account,
            previous_regime_state,
        )
        self._adaptive_posture = posture
        scope = "ACTIVE" if posture.active else "SHADOW"
        reasons = ",".join(posture.reasons) if posture.reasons else "none"
        constraints = ",".join(posture.constraints) if posture.constraints else "none"
        print(
            f"[ADAPTIVE] posture={posture.selected_mode} "
            f"confidence={posture.confidence} scope={scope} "
            f"reasons={reasons} constraints={constraints}"
        )
        self._record_lifecycle(
            LIFECYCLE_ADAPTIVE_POSTURE_SELECTED,
            selected_posture=posture.selected_mode,
            confidence=posture.confidence,
            active=posture.active,
            shadow=posture.shadow,
            configured_directional_mode=self.config.directional_mode,
            reasons=posture.reasons,
            constraints=posture.constraints,
            regime=signal.regime,
            regime_strength=self._regime_strength(signal),
            gap_percent=signal.gap_percent,
            active_bot=route.active_bot,
            routed_symbol=route.routed_symbol,
            position_symbol=self._active_position(positions)[0],
        )

    def _adaptive_should_evaluate(self) -> bool:
        return (
            self.config.directional_mode == DIRECTIONAL_MODE_ADAPTIVE
            or self.config.adaptive_shadow_enabled
        )

    def _select_adaptive_posture(
        self,
        signal: RegimeSignal,
        route: BotRoute,
        freshness: MarketDataFreshness,
        positions: dict[str, dict[str, Any] | None],
        account: dict[str, Any],
        previous_regime_state: dict[str, Any] | None = None,
    ) -> AdaptivePosture:
        active = self.config.directional_mode == DIRECTIONAL_MODE_ADAPTIVE
        shadow = not active
        reasons: list[str] = []
        constraints: list[str] = []
        selected_mode = DIRECTIONAL_MODE_BALANCED
        confidence = "MODERATE"

        active_position_symbol, _active_position = self._active_position(positions)
        stream_not_live = self._market_data_blocks_trading(SOXL)
        effective_notional, _requested_notional, buying_power = (
            self._effective_position_notional(account)
        )

        if active_position_symbol:
            constraints.append("position_open")
            reasons.append("adaptive_entry_posture_paused")
            selected_mode = DIRECTIONAL_MODE_BALANCED
            confidence = "HIGH"
        elif freshness.is_stale:
            constraints.append("bars_stale")
            reasons.append("entries_require_fresh_bars")
            selected_mode = DIRECTIONAL_MODE_CONSERVATIVE
            confidence = "HIGH"
        elif stream_not_live:
            constraints.append("stream_not_live")
            reasons.append("entries_require_live_stream")
            selected_mode = DIRECTIONAL_MODE_CONSERVATIVE
            confidence = "HIGH"
        elif effective_notional is None or effective_notional <= 0:
            constraints.append("buying_power_limited")
            reasons.append("effective_notional_unavailable")
            selected_mode = DIRECTIONAL_MODE_CONSERVATIVE
            confidence = "HIGH"
        elif route.active_bot == CHOP_BOT:
            reasons.append("sideways_route_chopbot")
            reasons.append("directional_posture_standby")
            selected_mode = DIRECTIONAL_MODE_BALANCED
            confidence = "LOW"
        else:
            strength = self._regime_strength(signal)
            if strength == REGIME_STRENGTH_STRONG:
                reasons.append("strong_directional_regime")
                selected_mode = DIRECTIONAL_MODE_AGGRESSIVE
                confidence = "HIGH"
            elif strength == REGIME_STRENGTH_MODERATE:
                reasons.append("moderate_directional_regime")
                selected_mode = DIRECTIONAL_MODE_BALANCED
                confidence = "MODERATE"
            else:
                reasons.append("weak_directional_regime")
                selected_mode = DIRECTIONAL_MODE_CONSERVATIVE
                confidence = "LOW"

        previous_regime_source = (
            previous_regime_state or self.state_store.get_regime_state()
        )
        previous_regime = str(previous_regime_source.get("regime") or "").upper()
        if previous_regime and previous_regime != signal.regime:
            constraints.append("regime_shift_detected")
            if selected_mode == DIRECTIONAL_MODE_AGGRESSIVE:
                selected_mode = DIRECTIONAL_MODE_BALANCED
                reasons.append("fresh_regime_shift_tempers_aggression")

        if buying_power is None:
            constraints.append("buying_power_unknown")

        if not reasons:
            reasons.append("default_balanced_posture")

        return AdaptivePosture(
            selected_mode=selected_mode,
            confidence=confidence,
            reasons=tuple(reasons),
            constraints=tuple(constraints),
            active=active,
            shadow=shadow,
        )

    def _apply_regime_hysteresis(
        self,
        signal: RegimeSignal,
        previous_regime_state: dict[str, Any] | None = None,
    ) -> RegimeSignal:
        raw_regime = signal.regime
        previous_regime_source = (
            previous_regime_state or self.state_store.get_regime_state()
        )
        previous_regime = str(previous_regime_source.get("regime") or "").upper()
        directional_regime = self._directional_regime_for_signal(signal)
        exit_threshold = self._regime_exit_threshold()

        if (
            raw_regime == SIDEWAYS
            and previous_regime in {UPTREND, DOWNTREND}
            and directional_regime == previous_regime
            and signal.gap_percent >= exit_threshold
        ):
            print(
                "[REGIME] hysteresis hold: "
                f"raw={raw_regime} previous={previous_regime} "
                f"gap={signal.gap_percent:.2f}% "
                f"exit_threshold={exit_threshold}%"
            )
            return RegimeSignal(
                source_symbol=signal.source_symbol,
                price=signal.price,
                fast_sma=signal.fast_sma,
                slow_sma=signal.slow_sma,
                gap_percent=signal.gap_percent,
                regime=previous_regime,
            )

        return signal

    def _directional_regime_for_signal(self, signal: RegimeSignal) -> str:
        if signal.fast_sma > signal.slow_sma:
            return UPTREND
        if signal.fast_sma < signal.slow_sma:
            return DOWNTREND
        return SIDEWAYS

    def _regime_exit_threshold(self) -> Decimal:
        return min(self.config.regime_exit_gap_threshold, self.config.regime_gap_threshold)

    def _account_day_pl(self, account: dict[str, Any]) -> tuple[Decimal | None, Decimal | None]:
        equity = optional_decimal_from_api(
            account.get("equity") or account.get("portfolio_value"),
            "account equity",
        )
        last_equity = optional_decimal_from_api(account.get("last_equity"), "last equity")
        if equity is None or last_equity is None:
            return None, None

        day_pl = equity - last_equity
        if last_equity == 0:
            return day_pl, None
        return day_pl, day_pl / last_equity * Decimal("100")

    def _raw_text(self, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value)

    def _decimal_text(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return format_decimal(value)

    def _regime_strength(self, signal: RegimeSignal) -> str:
        return self._strength_for_gap(signal.regime, signal.gap_percent)

    def _trend_trust_telemetry(
        self,
        signal: RegimeSignal,
        snapshot: SmaSnapshot,
        regime_state: dict[str, Any],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        regime_since = parse_market_timestamp(regime_state.get("regime_since"))
        regime_age = age_seconds(regime_since, now)
        age_minutes = (regime_age or 0.0) / 60
        recent_flips = self._recent_regime_flip_count(regime_state, now)
        efficiency = self._directional_efficiency(snapshot.slow_now_values)
        efficiency_value = float(efficiency) if efficiency is not None else 0.0

        threshold = self.config.regime_gap_threshold
        if threshold <= 0:
            strength_component = 0.0
        elif signal.regime == SIDEWAYS:
            strength_component = min(float(signal.gap_percent / threshold) * 25, 40.0)
        else:
            strength_component = min(
                float(signal.gap_percent / threshold) / 3 * 100,
                100.0,
            )
        age_component = min(age_minutes / 30 * 100, 100.0)
        stability_component = max(0.0, 100.0 - recent_flips * 15.0)
        efficiency_component = min(max(efficiency_value, 0.0), 100.0)
        score = int(
            round(
                strength_component * 0.35
                + age_component * 0.25
                + stability_component * 0.25
                + efficiency_component * 0.15
            )
        )
        if score >= 70:
            label = "HIGH"
        elif score >= 45:
            label = "MODERATE"
        else:
            label = "LOW"

        return {
            "score": score,
            "label": label,
            "regime": signal.regime,
            "strength": self._regime_strength(signal),
            "regime_age_seconds": self._rounded_seconds(regime_age),
            "regime_age_minutes": round(age_minutes, 2),
            "recent_flip_count_60m": recent_flips,
            "directional_efficiency": self._decimal_text(efficiency),
            "components": {
                "strength": round(strength_component, 1),
                "age": round(age_component, 1),
                "stability": round(stability_component, 1),
                "efficiency": round(efficiency_component, 1),
            },
        }

    def _recent_regime_flip_count(
        self,
        regime_state: dict[str, Any],
        now: datetime,
    ) -> int:
        transitions = regime_state.get("transitions")
        if not isinstance(transitions, list):
            return 0
        cutoff = now - timedelta(minutes=60)
        count = 0
        for transition in transitions:
            if not isinstance(transition, dict):
                continue
            transition_at = parse_market_timestamp(transition.get("at"))
            if transition_at is not None and transition_at >= cutoff:
                count += 1
        return count

    def _directional_efficiency(
        self,
        values: list[Decimal],
    ) -> Decimal | None:
        if len(values) < 2:
            return None
        net_move = abs(values[-1] - values[0])
        gross_move = sum(
            abs(values[index] - values[index - 1])
            for index in range(1, len(values))
        )
        if gross_move == 0:
            return Decimal("0")
        return net_move / gross_move * Decimal("100")

    def _print_trend_trust(self) -> None:
        telemetry = self._trend_trust
        if not telemetry:
            return
        efficiency = telemetry.get("directional_efficiency") or "--"
        print(
            "[TREND] TRUST "
            f"score={telemetry.get('score')} "
            f"label={telemetry.get('label')} "
            f"age={telemetry.get('regime_age_minutes')}m "
            f"flips_60m={telemetry.get('recent_flip_count_60m')} "
            f"efficiency={efficiency}% "
            f"strength={telemetry.get('strength')}"
        )

    def _strength_for_gap(self, regime: str, gap_percent: Decimal) -> str:
        threshold = self.config.regime_gap_threshold
        if regime == SIDEWAYS or threshold <= 0:
            return REGIME_STRENGTH_RANGE
        if gap_percent < threshold * Decimal("1.5"):
            return REGIME_STRENGTH_WEAK
        if gap_percent < threshold * Decimal("3"):
            return REGIME_STRENGTH_MODERATE
        return REGIME_STRENGTH_STRONG

    def _strength_meets_minimum(self, strength: str) -> bool:
        return REGIME_STRENGTH_ORDER.get(strength, 0) >= REGIME_STRENGTH_ORDER.get(
            self.config.directional_min_strength,
            REGIME_STRENGTH_ORDER[REGIME_STRENGTH_MODERATE],
        )

    def _market_data_status(self, symbol: str) -> dict[str, Any]:
        if self.market_data is None:
            status = "LIVE" if self._latest_freshness and not self._latest_freshness.is_stale else "REST"
            return {
                "data_source": "rest",
                "data_feed": self.config.data_feed,
                "data_status": status,
                "stream_connected": None,
                "stream_authenticated": None,
                "stream_subscribed": None,
                "stream_error": None,
                "stream_bar_count": None,
                "stream_last_message_at": None,
                "latest_bar_time": None,
                "bar_age_seconds": None,
                "latest_trade_time": None,
                "trade_age_seconds": None,
                "latest_quote_time": None,
                "quote_age_seconds": None,
            }

        return self.market_data.status(
            symbol,
            required_bars=self.config.slow_sma_minutes,
        )

    def _repair_stale_market_bars(self) -> None:
        if self.market_data is None:
            return
        repair = getattr(self.market_data, "repair_stale_bars", None)
        if not callable(repair):
            return

        result = repair(
            self.client,
            self.basket_symbols,
            required_bars=self.config.slow_sma_minutes + 1,
        )
        if not result.get("attempted"):
            return

        reasons = result.get("reasons") or {}
        reason_text = ",".join(
            f"{symbol}:{reason}" for symbol, reason in sorted(reasons.items())
        )
        repaired = result.get("repaired_symbols") or []
        unchanged = result.get("unchanged_symbols") or []
        errors = result.get("errors") or []

        if repaired:
            print(
                "[DATA] BAR BACKFILL repaired "
                f"symbols={','.join(repaired)} reasons={reason_text}"
            )
        if unchanged:
            print(
                "[DATA] BAR BACKFILL unchanged "
                f"symbols={','.join(unchanged)} reasons={reason_text}"
            )
        for error in errors:
            print(
                "[DATA] BAR BACKFILL error "
                f"symbol={error.get('symbol')} error={error.get('error')}"
            )

    def _print_market_data_status(self, symbol: str) -> None:
        status = self._market_data_status(symbol)
        print(f"[DATA] HEALTH {self._status_summary(status)}")
        if status.get("stream_error"):
            print(f"[DATA] ERROR stream_error={status.get('stream_error')}")

    def _market_data_blocks_trading(self, symbol: str) -> bool:
        if self.market_data is None:
            return False
        return self._market_data_status(symbol).get("data_status") != "LIVE"

    def _market_data_freshness(
        self,
        symbol: str,
        snapshot: SmaSnapshot,
    ) -> MarketDataFreshness:
        now = datetime.now(timezone.utc)
        trade = None
        quote = None
        trade_error = None
        quote_error = None

        data_source = self.market_data or self.client

        try:
            trade = data_source.get_latest_trade(symbol)
        except BotError as exc:
            trade_error = str(exc)

        try:
            quote = data_source.get_latest_quote(symbol)
        except BotError as exc:
            quote_error = str(exc)

        latest_trade_time = parse_market_timestamp(trade.get("t")) if trade else None
        latest_quote_time = parse_market_timestamp(quote.get("t")) if quote else None
        freshness = MarketDataFreshness(
            symbol=symbol,
            latest_bar_time=snapshot.latest_bar_time,
            latest_bar_close=snapshot.price,
            latest_trade_time=latest_trade_time,
            latest_trade_price=(
                optional_decimal_from_api(trade.get("p"), "latest trade price")
                if trade
                else None
            ),
            latest_quote_time=latest_quote_time,
            latest_quote_bid=(
                optional_decimal_from_api(quote.get("bp"), "latest quote bid")
                if quote
                else None
            ),
            latest_quote_ask=(
                optional_decimal_from_api(quote.get("ap"), "latest quote ask")
                if quote
                else None
            ),
            bar_age_seconds=bar_end_age_seconds(snapshot.latest_bar_time, now),
            trade_age_seconds=age_seconds(latest_trade_time, now),
            quote_age_seconds=age_seconds(latest_quote_time, now),
            trade_error=trade_error,
            quote_error=quote_error,
        )
        print(f"[DATA] HEALTH {self._freshness_summary(freshness)}")
        if freshness.is_stale or freshness.trade_error or freshness.quote_error:
            print(f"[DATA] DETAILS market_data_freshness={self._freshness_payload(freshness)}")
        return freshness

    def _freshness_payload(self, freshness: MarketDataFreshness) -> str:
        payload = {
            "symbol": freshness.symbol,
            "now": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "latestBarTime": self._time_text(freshness.latest_bar_time),
            "latestBarClose": self._float_value(freshness.latest_bar_close),
            "latestTradeTime": self._time_text(freshness.latest_trade_time),
            "latestTradePrice": self._float_value(freshness.latest_trade_price),
            "latestQuoteTime": self._time_text(freshness.latest_quote_time),
            "latestQuoteBid": self._float_value(freshness.latest_quote_bid),
            "latestQuoteAsk": self._float_value(freshness.latest_quote_ask),
            "barAgeSeconds": self._rounded_seconds(freshness.bar_age_seconds),
            "tradeAgeSeconds": self._rounded_seconds(freshness.trade_age_seconds),
            "quoteAgeSeconds": self._rounded_seconds(freshness.quote_age_seconds),
            "maxAgeSeconds": MARKET_DATA_MAX_AGE_SECONDS,
            "isStale": freshness.is_stale,
        }
        if freshness.trade_error:
            payload["latestTradeError"] = freshness.trade_error
        if freshness.quote_error:
            payload["latestQuoteError"] = freshness.quote_error
        return json.dumps(payload, sort_keys=True)

    def _time_text(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00",
            "Z",
        )

    def _float_value(self, value: Decimal | None) -> float | None:
        if value is None:
            return None
        return float(value)

    def _rounded_seconds(self, value: float | None) -> float | None:
        if value is None:
            return None
        return round(value, 3)

    def _freshness_summary(self, freshness: MarketDataFreshness) -> str:
        status = self._market_data_status(freshness.symbol)
        stream_state = "CONNECTED" if status.get("stream_connected") else "DISCONNECTED"
        if status.get("data_status") and status.get("data_status") not in {"LIVE", "REST"}:
            stream_state = str(status.get("data_status"))
        return (
            f"bars={self._health_piece(freshness.bar_age_seconds)} "
            f"quotes={self._health_piece(freshness.quote_age_seconds)} "
            f"trades={self._health_piece(freshness.trade_age_seconds)} "
            f"stream={stream_state}"
        )

    def _status_summary(self, status: dict[str, Any]) -> str:
        stream_state = "CONNECTED" if status.get("stream_connected") else "DISCONNECTED"
        if status.get("data_status") and status.get("data_status") not in {"LIVE", "REST"}:
            stream_state = str(status.get("data_status"))
        bar_count = status.get("stream_bar_count")
        bars = status.get("data_status") or "UNKNOWN"
        if bar_count is not None:
            bars = f"{bars} bars={bar_count}/{self.config.slow_sma_minutes}"
        return (
            f"bars={bars} ({self._age_label(status.get('bar_age_seconds'))}) "
            f"quotes={self._health_piece(status.get('quote_age_seconds'))} "
            f"trades={self._health_piece(status.get('trade_age_seconds'))} "
            f"stream={stream_state}"
        )

    def _health_piece(self, age: float | None) -> str:
        if age is None:
            return "WAITING"
        if age > MARKET_DATA_MAX_AGE_SECONDS:
            return f"STALE ({self._age_label(age)})"
        return f"LIVE ({self._age_label(age)})"

    def _age_label(self, value: Any) -> str:
        if value is None:
            return "--"
        seconds = float(value)
        if seconds < 1:
            return "<1s"
        return f"{round(seconds)}s"

    def _directional_mode_for_route(self, route: BotRoute) -> str:
        if route.active_bot in {MOMENTUM_BOT, INVERSE_BOT}:
            return self._effective_directional_mode_for_bot(route.active_bot)
        return "NA"

    def _apply_enabled_bot_mask(self, route: BotRoute) -> BotRoute:
        if route.active_bot in self.config.enabled_bots:
            return route

        enabled_text = ",".join(self.config.enabled_bots)
        print(
            "[ROUTER] entries disabled for routed bot: "
            f"bot={route.active_bot} enabled_bots={enabled_text}"
        )
        return BotRoute(route.active_bot, route.routed_symbol, False)

    def _v9_authority_evaluation_route(self, route: BotRoute) -> BotRoute:
        if (
            route.active_bot == CHOP_BOT
            and self.config.chop_permission_mode != CHOP_PERMISSION_MODE_OFF
        ):
            return BotRoute(MOMENTUM_BOT, SOXL, True)
        return route

    def _inverse_cascade_route_override(self, route: BotRoute) -> BotRoute:
        self._inverse_cascade_context = None
        if self.config.inverse_cascade_mode == INVERSE_CASCADE_MODE_OFF:
            return route
        if INVERSE_BOT not in self.config.enabled_bots:
            return route

        context = self._inverse_cascade_context_for_mode()
        self._inverse_cascade_maybe_reset_state(context)
        context["base_route_bot"] = route.active_bot
        context["base_route_symbol"] = route.routed_symbol
        reasons = context.get("reasons") or []
        thresholds = context.get("thresholds") or {}
        if (
            context.get("mode") == INVERSE_CASCADE_MODE_SUSTAINED
            and thresholds.get("block_source_uptrend")
            and route.active_bot == MOMENTUM_BOT
            and route.routed_symbol == SOXL
        ):
            reasons.append("source_uptrend_route_blocks_sustained_cascade")
        if reasons:
            print(
                "[INVERSE] Cascade candidate blocked: "
                f"mode={context.get('mode')} reason={','.join(reasons)} "
                f"base={context.get('base_route_bot')}/{context.get('base_route_symbol') or 'NONE'} "
                f"soxl={self._decimal_text(context.get('source_current_percent'))}% "
                f"dd={self._decimal_text(context.get('source_drawdown_percent'))}% "
                f"recovery={self._decimal_text(context.get('source_recovery_percent'))}% "
                f"soxs={self._decimal_text(context.get('inverse_current_percent'))}% "
                f"velocity={self._decimal_text(context.get('source_velocity_percent'))}% "
                f"deepening={self._decimal_text(context.get('sustain_source_deepening_percent'))}% "
                f"new_lows={context.get('sustain_source_new_low_count', '--')} "
                f"sustain={context.get('sustained_window_minutes', '--')}m"
            )
            return route

        self._inverse_cascade_context = context
        self._inverse_cascade_clear_invalidation_state()
        print(
            "[INVERSE] Cascade candidate qualified: "
            f"mode={context.get('mode')} "
            f"base={context.get('base_route_bot')}/{context.get('base_route_symbol') or 'NONE'} "
            f"soxl={self._decimal_text(context.get('source_current_percent'))}% "
            f"dd={self._decimal_text(context.get('source_drawdown_percent'))}% "
            f"recovery={self._decimal_text(context.get('source_recovery_percent'))}% "
            f"soxs={self._decimal_text(context.get('inverse_current_percent'))}% "
            f"velocity={self._decimal_text(context.get('source_velocity_percent'))}% "
            f"deepening={self._decimal_text(context.get('sustain_source_deepening_percent'))}% "
            f"new_lows={context.get('sustain_source_new_low_count', '--')} "
            f"sustain={context.get('sustained_window_minutes', '--')}m"
        )
        if route.active_bot != INVERSE_BOT or route.routed_symbol != SOXS:
            print(
                "[ROUTER] inverse cascade override: "
                f"from_bot={route.active_bot} from_symbol={route.routed_symbol or 'NONE'} "
                f"to_bot={INVERSE_BOT} to_symbol={SOXS}"
            )
        return BotRoute(INVERSE_BOT, SOXS, True)

    def _inverse_cascade_context_for_mode(self) -> dict[str, Any]:
        mode = self.config.inverse_cascade_mode
        thresholds = INVERSE_CASCADE_DEFAULTS.get(mode, {})
        context: dict[str, Any] = {
            "mode": mode,
            "reasons": [],
            "thresholds": thresholds,
        }
        reasons: list[str] = context["reasons"]

        source_path = self._symbol_session_price_path(SOXL)
        inverse_path = self._symbol_session_price_path(SOXS)
        if source_path is None:
            reasons.append("source_path_unavailable")
        if inverse_path is None:
            reasons.append("inverse_path_unavailable")
        if source_path is None or inverse_path is None:
            return context

        source_recovery = source_path.current_percent - source_path.drawdown_percent
        source_velocity = None
        if mode in {INVERSE_CASCADE_MODE_VELOCITY, INVERSE_CASCADE_MODE_SUSTAINED}:
            source_velocity = self._recent_session_return_percent(
                SOXL,
                self.config.inverse_cascade_velocity_window_minutes,
            )

        context.update(
            {
                "source_current_percent": source_path.current_percent,
                "source_runup_percent": source_path.runup_percent,
                "source_drawdown_percent": source_path.drawdown_percent,
                "source_recovery_percent": source_recovery,
                "inverse_current_percent": inverse_path.current_percent,
                "inverse_runup_percent": inverse_path.runup_percent,
                "source_velocity_percent": source_velocity,
            }
        )

        source_current_max = thresholds.get("source_current_max")
        if (
            isinstance(source_current_max, Decimal)
            and source_path.current_percent > source_current_max
        ):
            reasons.append("source_current_above_cascade_max")

        source_drawdown_max = thresholds.get("source_drawdown_max")
        if (
            isinstance(source_drawdown_max, Decimal)
            and source_path.drawdown_percent > source_drawdown_max
        ):
            reasons.append("source_drawdown_above_cascade_max")

        inverse_current_min = thresholds.get("inverse_current_min")
        if (
            isinstance(inverse_current_min, Decimal)
            and inverse_path.current_percent < inverse_current_min
        ):
            reasons.append("inverse_current_below_cascade_min")

        source_recovery_max = thresholds.get("source_recovery_max")
        if (
            isinstance(source_recovery_max, Decimal)
            and source_recovery > source_recovery_max
        ):
            reasons.append("source_recovery_above_cascade_max")

        source_velocity_max = thresholds.get("source_velocity_max")
        if mode in {INVERSE_CASCADE_MODE_VELOCITY, INVERSE_CASCADE_MODE_SUSTAINED}:
            if source_velocity is None:
                reasons.append("source_velocity_unavailable")
            elif (
                isinstance(source_velocity_max, Decimal)
                and source_velocity > source_velocity_max
            ):
                reasons.append("source_velocity_above_cascade_max")

        if mode == INVERSE_CASCADE_MODE_SUSTAINED:
            context.update(self._inverse_cascade_sustained_window_context(thresholds))
            reasons.extend(context.get("sustained_reasons") or [])

        return context

    def _inverse_cascade_sustained_window_context(
        self,
        thresholds: dict[str, Any],
    ) -> dict[str, Any]:
        context: dict[str, Any] = {
            "sustained_reasons": [],
            "sustained_window_minutes": self.config.inverse_cascade_sustain_minutes,
        }
        reasons: list[str] = context["sustained_reasons"]
        window_minutes = self.config.inverse_cascade_sustain_minutes
        source_bars = self._symbol_session_bars(SOXL)
        inverse_bars = self._symbol_session_bars(SOXS)
        if len(source_bars) < window_minutes or len(inverse_bars) < window_minutes:
            reasons.append("sustained_window_insufficient_bars")
            return context

        source_open = self._v7_bar_decimal(source_bars[0], "o", "c")
        inverse_open = self._v7_bar_decimal(inverse_bars[0], "o", "c")
        if (
            source_open is None
            or inverse_open is None
            or source_open <= 0
            or inverse_open <= 0
        ):
            reasons.append("sustained_window_open_unavailable")
            return context

        source_recent = source_bars[-window_minutes:]
        inverse_recent = inverse_bars[-window_minutes:]
        source_threshold = thresholds.get("sustain_source_current_max")
        inverse_threshold = thresholds.get("sustain_inverse_current_min")
        source_percents: list[Decimal] = []
        inverse_percents: list[Decimal] = []
        for bar in source_recent:
            price = self._v7_bar_decimal(bar, "c", "o")
            if price is None:
                reasons.append("sustained_source_price_unavailable")
                break
            source_percents.append((price - source_open) / source_open * Decimal("100"))
        for bar in inverse_recent:
            price = self._v7_bar_decimal(bar, "c", "o")
            if price is None:
                reasons.append("sustained_inverse_price_unavailable")
                break
            inverse_percents.append((price - inverse_open) / inverse_open * Decimal("100"))

        if source_percents:
            context["soxl_pct_from_open_at_cascade_window_start"] = source_percents[0]
            source_prior_close = self._symbol_previous_session_close(SOXL)
            source_window_start_price = self._v7_bar_decimal(source_recent[0], "c", "o")
            if (
                source_prior_close is not None
                and source_prior_close > 0
                and source_window_start_price is not None
            ):
                context["soxl_pct_vs_prior_close_at_cascade_window_start"] = (
                    (source_window_start_price - source_prior_close)
                    / source_prior_close
                    * Decimal("100")
                )
            source_window_start_min = thresholds.get("sustain_source_window_start_min")
            if (
                isinstance(source_window_start_min, Decimal)
                and source_percents[0] < source_window_start_min
            ):
                reasons.append("source_window_start_below_cascade_min")
            source_prior_close_max = thresholds.get("sustain_source_prior_close_max")
            source_prior_close_percent = context.get(
                "soxl_pct_vs_prior_close_at_cascade_window_start"
            )
            if isinstance(source_prior_close_max, Decimal):
                if not isinstance(source_prior_close_percent, Decimal):
                    reasons.append("source_prior_close_unavailable")
                elif source_prior_close_percent > source_prior_close_max:
                    reasons.append("source_prior_close_above_cascade_max")
            context["sustain_source_worst_percent"] = max(source_percents)
            context["sustain_source_latest_percent"] = source_percents[-1]
            source_deepening = source_percents[0] - source_percents[-1]
            context["sustain_source_deepening_percent"] = source_deepening
            (
                direction_changes,
                down_path_ratio,
                path_length,
                down_distance,
            ) = self._inverse_cascade_window_quality(source_percents)
            context["sustain_source_direction_changes"] = direction_changes
            context["sustain_source_down_path_ratio"] = down_path_ratio
            context["sustain_source_path_length_percent"] = path_length
            context["sustain_source_down_distance_percent"] = down_distance
            context.update(
                self._inverse_cascade_entry_bar_momentum_context(
                    source_recent,
                    "soxl",
                )
            )
        if inverse_percents:
            context["sustain_inverse_worst_percent"] = min(inverse_percents)
            context["sustain_inverse_latest_percent"] = inverse_percents[-1]
            context.update(
                self._inverse_cascade_entry_bar_momentum_context(
                    inverse_recent,
                    "soxs",
                )
            )
            if context.get("entry_bar_soxs_direction") == "DOWN":
                reasons.append("inverse_entry_bar_down")

        source_new_low_count = self._inverse_cascade_recent_new_low_count(
            source_bars,
            window_minutes,
        )
        context["sustain_source_new_low_count"] = source_new_low_count

        if (
            isinstance(source_threshold, Decimal)
            and source_percents
            and any(percent > source_threshold for percent in source_percents)
        ):
            reasons.append("source_not_sustained_below_cascade_max")
        if (
            isinstance(inverse_threshold, Decimal)
            and inverse_percents
            and any(percent < inverse_threshold for percent in inverse_percents)
        ):
            reasons.append("inverse_not_sustained_above_cascade_min")

        source_deepening_min = thresholds.get("sustain_source_deepening_min")
        source_deepening = context.get("sustain_source_deepening_percent")
        if (
            isinstance(source_deepening_min, Decimal)
            and isinstance(source_deepening, Decimal)
            and source_deepening < source_deepening_min
        ):
            reasons.append("source_not_deepening_during_sustain")

        source_new_low_count_min = thresholds.get("sustain_source_new_low_count_min")
        if (
            isinstance(source_new_low_count_min, int)
            and source_new_low_count < source_new_low_count_min
        ):
            reasons.append("source_new_low_pressure_below_min")
        return context

    def _inverse_cascade_entry_bar_momentum_context(
        self,
        bars: list[dict[str, Any]],
        symbol_key: str,
    ) -> dict[str, Any]:
        if len(bars) < 2:
            return {}

        prices: list[Decimal] = []
        for bar in bars:
            price = self._v7_bar_decimal(bar, "c", "o")
            if price is None or price <= 0:
                return {}
            prices.append(price)

        bar_moves: list[Decimal] = []
        for index in range(1, len(prices)):
            previous_price = prices[index - 1]
            latest_price = prices[index]
            if previous_price <= 0:
                return {}
            bar_moves.append(
                (latest_price - previous_price) / previous_price * Decimal("100")
            )

        if not bar_moves:
            return {}

        bar_percent = bar_moves[-1]
        if bar_percent > 0:
            direction = "UP"
        elif bar_percent < 0:
            direction = "DOWN"
        else:
            direction = "FLAT"
        context: dict[str, Any] = {
            f"entry_bar_{symbol_key}_pct": bar_percent,
            f"entry_bar_{symbol_key}_direction": direction,
        }
        prior_moves = bar_moves[:-1]
        if prior_moves:
            prior_avg_abs = sum(
                (abs(move) for move in prior_moves),
                Decimal("0"),
            ) / Decimal(len(prior_moves))
            context[f"entry_bar_{symbol_key}_prior_avg_abs_pct"] = prior_avg_abs
            if prior_avg_abs > 0:
                context[f"entry_bar_{symbol_key}_velocity_ratio"] = (
                    abs(bar_percent) / prior_avg_abs
                )
        return context

    def _inverse_cascade_window_quality(
        self,
        source_percents: list[Decimal],
    ) -> tuple[int, Decimal | None, Decimal, Decimal]:
        direction_changes = 0
        previous_direction = 0
        path_length = Decimal("0")
        down_distance = Decimal("0")
        for index in range(1, len(source_percents)):
            delta = source_percents[index] - source_percents[index - 1]
            if delta == 0:
                continue
            path_length += abs(delta)
            if delta < 0:
                down_distance += abs(delta)
            direction = 1 if delta > 0 else -1
            if previous_direction and direction != previous_direction:
                direction_changes += 1
            previous_direction = direction
        down_path_ratio = (
            down_distance / path_length if path_length > 0 else None
        )
        return direction_changes, down_path_ratio, path_length, down_distance

    def _inverse_cascade_recent_new_low_count(
        self,
        source_bars: list[dict[str, Any]],
        window_minutes: int,
    ) -> int:
        if len(source_bars) < window_minutes:
            return 0

        recent_start = len(source_bars) - window_minutes
        running_low: Decimal | None = None
        count = 0
        for index, bar in enumerate(source_bars):
            low_price = self._v7_bar_decimal(bar, "l", "c", "o")
            if low_price is None:
                continue
            if running_low is None or low_price < running_low:
                if index >= recent_start:
                    count += 1
                running_low = low_price
        return count

    def _inverse_cascade_session_date(self) -> str:
        return datetime.now(timezone.utc).astimezone(NY_TZ).date().isoformat()

    def _inverse_cascade_same_session_state(self) -> dict[str, Any]:
        state = self.state_store.get_inverse_cascade_state()
        if state.get("session_date") != self._inverse_cascade_session_date():
            if state:
                self.state_store.clear_inverse_cascade_state()
            return {}
        return state

    def _maybe_update_inverse_cascade_proven_state(
        self,
        symbol: str,
        avg_entry_price: Decimal,
    ) -> dict[str, Any]:
        if (
            self.config.inverse_cascade_mode != INVERSE_CASCADE_MODE_SUSTAINED
            or symbol != SOXS
            or avg_entry_price <= 0
        ):
            return {}
        state = self._inverse_cascade_same_session_state()
        if (
            state.get("mode") != INVERSE_CASCADE_MODE_SUSTAINED
            or not state.get("entered_at")
        ):
            return state

        session_bars = self._symbol_session_bars(symbol)
        highs = [
            value
            for bar in session_bars
            if (value := self._v7_bar_decimal(bar, "h", "c", "o")) is not None
        ]
        if not highs:
            return state

        high_price = max(highs)
        mfe_percent = (
            (high_price - avg_entry_price) / avg_entry_price * Decimal("100")
        )
        previous_mfe = optional_decimal_from_api(
            state.get("max_favorable_excursion_percent"),
            "inverse cascade max favorable excursion",
        )
        changed = False
        if previous_mfe is None or mfe_percent > previous_mfe:
            state["max_favorable_excursion_percent"] = format_decimal(mfe_percent)
            state["max_favorable_price"] = format_decimal(high_price)
            changed = True

        if (
            not state.get("proven_at")
            and mfe_percent >= self.config.inverse_cascade_proven_mfe_percent
        ):
            state["proven_at"] = datetime.now(timezone.utc).isoformat()
            state["proven_mfe_percent"] = format_decimal(mfe_percent)
            state["proven_threshold_percent"] = format_decimal(
                self.config.inverse_cascade_proven_mfe_percent
            )
            changed = True

        if changed:
            self.state_store.set_inverse_cascade_state(state)
        return state

    def _inverse_cascade_source_current_percent(self) -> Decimal | None:
        source_path = self._symbol_session_price_path(SOXL)
        if source_path is None:
            return None
        return source_path.current_percent

    def _inverse_cascade_maybe_reset_state(self, context: dict[str, Any]) -> None:
        if self.config.inverse_cascade_mode != INVERSE_CASCADE_MODE_SUSTAINED:
            return
        state = self._inverse_cascade_same_session_state()
        if not state.get("entered_at"):
            return
        if state.get("stopped_out_at"):
            return
        if self._position_qty(self.client.get_position(SOXS)) > 0:
            return
        thresholds = context.get("thresholds") or {}
        reset_current_min = thresholds.get("reset_source_current_min")
        source_current = context.get("source_current_percent")
        if (
            isinstance(reset_current_min, Decimal)
            and isinstance(source_current, Decimal)
            and source_current >= reset_current_min
        ):
            print(
                "[INVERSE] Sustained cascade lockout reset: "
                f"soxl={self._decimal_text(source_current)}% "
                f"threshold={reset_current_min}%"
            )
            self.state_store.clear_inverse_cascade_state()

    def _inverse_cascade_reentry_locked(self) -> bool:
        if self.config.inverse_cascade_mode != INVERSE_CASCADE_MODE_SUSTAINED:
            return False
        state = self._inverse_cascade_same_session_state()
        return bool(state.get("entered_at") and state.get("lockout_active", True))

    def _inverse_cascade_stopped_out_session_locked(self) -> bool:
        if self.config.inverse_cascade_mode != INVERSE_CASCADE_MODE_SUSTAINED:
            return False
        state = self._inverse_cascade_same_session_state()
        return bool(state.get("stopped_out_at"))

    def _inverse_cascade_clear_invalidation_state(self) -> None:
        if self.config.inverse_cascade_mode != INVERSE_CASCADE_MODE_SUSTAINED:
            return
        state = self._inverse_cascade_same_session_state()
        if state.get("invalidation_started_at"):
            state["invalidation_started_at"] = None
            self.state_store.set_inverse_cascade_state(state)

    def _inverse_cascade_context_active(self, route: BotRoute) -> bool:
        context = self._inverse_cascade_context
        return bool(
            context
            and not context.get("reasons")
            and route.active_bot == INVERSE_BOT
            and route.routed_symbol == SOXS
        )

    def _effective_directional_mode_for_bot(self, bot_name: str) -> str:
        if (
            bot_name in {MOMENTUM_BOT, INVERSE_BOT}
            and self.config.directional_mode == DIRECTIONAL_MODE_ADAPTIVE
            and self._adaptive_posture is not None
        ):
            return self._adaptive_posture.selected_mode
        if self.config.directional_mode == DIRECTIONAL_MODE_ADAPTIVE:
            return DIRECTIONAL_MODE_BALANCED
        return self.config.directional_mode

    def _chop_permission_entry_policy_decision(
        self,
        route: BotRoute,
        soxl_snapshot: SmaSnapshot,
    ) -> EntryDecision | None:
        del soxl_snapshot
        mode = self.config.chop_permission_mode
        if route.active_bot != CHOP_BOT or mode == CHOP_PERMISSION_MODE_OFF:
            return None

        reasons: list[str] = []
        if self._v10_authority_state() == V10_AUTHORITY_STATE_MOMENTUM:
            reasons.append("chop_momentum_authority_active")

        invalidation_reason = self._v9_momentum_context_invalidation_reason()
        if invalidation_reason == "momentum_drawdown_with_dirty_tape":
            reasons.append(invalidation_reason)
        if (
            mode == CHOP_PERMISSION_MODE_FIREWALL
            and invalidation_reason == "soxl_below_open_after_1030"
        ):
            reasons.append(invalidation_reason)

        observer_context = self._v9_observer_context()
        if mode == CHOP_PERMISSION_MODE_STRICT:
            transition_count = self._v9_observer_int(
                observer_context,
                "early_transition_count",
            )
            if transition_count is None or transition_count != 0:
                reasons.append("chop_early_transition_count_not_zero")

            path = self._v7_source_price_path()
            source_percent = path.current_percent if path is not None else None
            if (
                source_percent is None
                or abs(source_percent)
                > self.config.chop_permission_max_abs_source_percent
            ):
                reasons.append("chop_source_directional_state_too_large")
        elif mode == CHOP_PERMISSION_MODE_FIREWALL:
            path = self._v7_source_price_path()
            source_percent = path.current_percent if path is not None else None
            drawdown_percent = path.drawdown_percent if path is not None else None
            non_warmup_transition_count = self._v9_observer_int(
                observer_context,
                "early_non_warmup_transition_count",
            )
            trust_score = self._v9_observer_int(
                observer_context,
                "trend_trust_score",
            )

            if (
                source_percent is None
                or non_warmup_transition_count is None
                or drawdown_percent is None
            ):
                reasons.append("chop_firewall_context_unavailable")
            else:
                if source_percent <= 0 and non_warmup_transition_count > 0:
                    reasons.append("chop_negative_noisy_tape")
                if (
                    drawdown_percent
                    <= CHOP_PERMISSION_FIREWALL_MAX_DRAWDOWN_PERCENT
                ):
                    reasons.append("chop_source_drawdown_firewall")
                if (
                    trust_score is not None
                    and trust_score
                    >= CHOP_PERMISSION_FIREWALL_NEAR_MOMENTUM_MIN_TRUST_SCORE
                    and source_percent
                    >= CHOP_PERMISSION_FIREWALL_NEAR_MOMENTUM_MIN_SOURCE_PERCENT
                    and non_warmup_transition_count == 0
                ):
                    reasons.append("chop_near_momentum_authority")

        if not reasons:
            return None

        reason = ",".join(reasons)
        print(
            "[V10] Chop permission suppresses entry: "
            f"mode={mode} reason={reason}"
        )
        return EntryDecision(False, CHOP_PERMISSION_SUPPRESSION_REASON)

    def _momentum_authority_entry_policy_decision(
        self,
        route: BotRoute,
        soxl_snapshot: SmaSnapshot,
    ) -> EntryDecision | None:
        del soxl_snapshot
        if route.active_bot != MOMENTUM_BOT:
            return None
        if not self.config.momentum_authority_required:
            return None

        block_reason = self._momentum_authority_block_reason()
        if block_reason is None:
            return None

        context = self._v10_no_authority_context(
            route,
            activation_reason=block_reason,
            authority_gate="momentum_permission",
        )
        routed_symbol = route.routed_symbol or SOXL
        print(
            "[V10] Momentum authority suppresses entry: "
            f"bot={route.active_bot} symbol={routed_symbol} "
            f"reason={V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON} "
            f"gate_reason={block_reason}"
        )
        self._record_lifecycle(
            LIFECYCLE_SHADOW_ENTRY_SUPPRESSED,
            bot=route.active_bot,
            symbol=routed_symbol,
            side="buy",
            reason=V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON,
            authority_state=V10_AUTHORITY_STATE_NONE,
            v10_no_authority_context=context,
            shadow_pl_status="natural_exit_shadow_not_computed",
        )
        return EntryDecision(False, V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON)

    def _momentum_authority_block_reason(self) -> str | None:
        if self._momentum_authority_latched():
            return None

        if self.config.momentum_authority_latch_once_active:
            context = self._v9_session_context()
            if context.get("active") and not context.get("invalidated"):
                self._latch_momentum_authority(context)
                return None

        hard_veto_reason = self._v9_momentum_context_hard_veto_reason()
        if hard_veto_reason:
            self._v9_invalidate_active_momentum_context(hard_veto_reason)
            return hard_veto_reason
        if self._v9_active_momentum_context() is None:
            return MOMENTUM_AUTHORITY_REQUIRED_REASON
        return None

    def _v9_momentum_context_hard_veto_reason(self) -> str | None:
        context = self._v9_session_context()
        if context.get("invalidated") and context.get("invalidation_reason"):
            return str(context.get("invalidation_reason"))
        return self._v9_momentum_context_invalidation_reason()

    def _v9_invalidate_active_momentum_context(self, reason: str) -> None:
        context = self._v9_session_context()
        if context.get("active") and not context.get("invalidated"):
            self._v9_invalidate_momentum_context(context, reason)

    def _v9_entry_policy_decision(
        self,
        route: BotRoute,
        soxl_snapshot: SmaSnapshot,
    ) -> EntryDecision | None:
        del soxl_snapshot
        if route.active_bot != INVERSE_BOT:
            return None

        context = self._v9_active_momentum_context()
        if context is None:
            return None

        invalidation_reason = self._v9_momentum_context_invalidation_reason()
        if invalidation_reason:
            self._v9_invalidate_momentum_context(context, invalidation_reason)
            print(
                "[V9] Momentum context invalidated before suppression: "
                f"reason={invalidation_reason}"
            )
            return None

        path = self._v7_source_price_path()
        current_percent = path.current_percent if path is not None else None
        routed_symbol = route.routed_symbol or SOXS
        print(
            "[V9] Momentum context suppresses InverseBot: "
            f"symbol={routed_symbol} "
            f"reason={V9_MOMENTUM_CONTEXT_SUPPRESSION_REASON} "
            f"source_current={self._decimal_text(current_percent)}% "
            f"activated_at={context.get('activated_at') or '--'}"
        )
        self._record_lifecycle(
            LIFECYCLE_SHADOW_ENTRY_SUPPRESSED,
            bot=route.active_bot,
            symbol=routed_symbol,
            side="buy",
            reason=V9_MOMENTUM_CONTEXT_SUPPRESSION_REASON,
            v9_momentum_context=context,
            source_open_to_current_percent=current_percent,
        )
        return EntryDecision(False, V9_MOMENTUM_CONTEXT_SUPPRESSION_REASON)

    def _v10_entry_policy_decision(
        self,
        route: BotRoute,
        soxl_snapshot: SmaSnapshot,
    ) -> EntryDecision | None:
        del soxl_snapshot
        if route.active_bot not in {MOMENTUM_BOT, INVERSE_BOT}:
            return None
        if self._inverse_cascade_context_active(route):
            return None
        if self._v10_authority_state() != V10_AUTHORITY_STATE_NONE:
            return None

        context = self._v10_no_authority_context(route)
        routed_symbol = route.routed_symbol or (
            SOXL if route.active_bot == MOMENTUM_BOT else SOXS
        )
        print(
            "[V10] No-authority suppresses directional entry: "
            f"bot={route.active_bot} symbol={routed_symbol} "
            f"reason={V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON} "
            f"trust={context.get('trend_trust_score') or '--'} "
            f"soxl={context.get('source_open_to_current_percent') or '--'}% "
            f"raw30={context.get('early_transition_count')}/"
            f"{context.get('early_transitions_per_hour')} "
            f"nw30={context.get('early_non_warmup_transition_count')}/"
            f"{context.get('early_non_warmup_transitions_per_hour')}"
        )
        self._record_lifecycle(
            LIFECYCLE_SHADOW_ENTRY_SUPPRESSED,
            bot=route.active_bot,
            symbol=routed_symbol,
            side="buy",
            reason=V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON,
            authority_state=V10_AUTHORITY_STATE_NONE,
            v10_no_authority_context=context,
            shadow_pl_status="natural_exit_shadow_not_computed",
        )
        return EntryDecision(False, V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON)

    def _v10_authority_state(self) -> str | None:
        if self.config.v10_force_no_authority:
            return V10_AUTHORITY_STATE_NONE

        if self._momentum_authority_latched():
            return V10_AUTHORITY_STATE_MOMENTUM

        if self._v9_active_momentum_context() is not None:
            return V10_AUTHORITY_STATE_MOMENTUM

        if self._v9_observer_context() is None:
            return None

        context = self._v9_session_context()
        if context.get("evaluated") or context.get("invalidated"):
            return V10_AUTHORITY_STATE_NONE
        return None

    def _v10_no_authority_context(
        self,
        route: BotRoute,
        *,
        activation_reason: str | None = None,
        authority_gate: str | None = None,
    ) -> dict[str, Any]:
        observer_context = self._v9_observer_context() or {}
        v9_context = self._v9_session_context()
        trend_trust = self._trend_trust or {}
        regime_state = self.state_store.get_regime_state()
        path = self._v7_source_price_path()
        return {
            "authority_state": V10_AUTHORITY_STATE_NONE,
            "suppression_reason": V10_NO_AUTHORITY_DIRECTIONAL_SUPPRESSION_REASON,
            "authority_gate": authority_gate,
            "observer_preset": observer_context.get("observer_preset"),
            "activation_reason": (
                activation_reason
                or v9_context.get("invalidation_reason")
                or v9_context.get("activation_reason")
            ),
            "route_bot": route.active_bot,
            "route_symbol": route.routed_symbol,
            "regime": regime_state.get("regime"),
            "trend_trust_score": trend_trust.get("score"),
            "trend_trust_label": trend_trust.get("label"),
            "regime_age_minutes": trend_trust.get("regime_age_minutes"),
            "recent_flip_count_60m": trend_trust.get("recent_flip_count_60m"),
            "early_transition_count": observer_context.get("early_transition_count"),
            "early_transitions_per_hour": observer_context.get(
                "early_transitions_per_hour"
            ),
            "early_non_warmup_transition_count": observer_context.get(
                "early_non_warmup_transition_count"
            ),
            "early_non_warmup_transitions_per_hour": observer_context.get(
                "early_non_warmup_transitions_per_hour"
            ),
            "early_transition_window_minutes": observer_context.get(
                "early_transition_window_minutes"
            )
            or V9_MOMENTUM_EARLY_WINDOW_MINUTES,
            "source_open_to_current_percent": self._v10_path_percent(
                path.current_percent if path is not None else None
            ),
            "source_runup_percent": self._v10_path_percent(
                path.runup_percent if path is not None else None
            ),
            "source_drawdown_percent": self._v10_path_percent(
                path.drawdown_percent if path is not None else None
            ),
        }

    def _v10_path_percent(self, value: Decimal | None) -> float | None:
        if value is None:
            return None
        return float(value.quantize(Decimal("0.01")))

    def _v8_entry_policy_decision(
        self,
        route: BotRoute,
        soxl_snapshot: SmaSnapshot,
    ) -> EntryDecision | None:
        v7_decision = self._v7_entry_policy_decision(route, soxl_snapshot)
        if v7_decision is not None:
            return v7_decision
        if self._inverse_cascade_context_active(route):
            print(
                "[V8] Inverse cascade bypasses regime survivability: "
                f"mode={self.config.inverse_cascade_mode}"
            )
            return None
        return self._v8_regime_survivability_decision(route)

    def _v8_regime_survivability_decision(
        self,
        route: BotRoute,
    ) -> EntryDecision | None:
        if route.active_bot not in {MOMENTUM_BOT, INVERSE_BOT}:
            return None

        telemetry = self._trend_trust or {}
        age_minutes = Decimal(str(telemetry.get("regime_age_minutes") or 0))
        score = int(telemetry.get("score") or 0)
        flips = int(telemetry.get("recent_flip_count_60m") or 0)
        print(
            "[V8] Directional survivability: "
            f"bot={route.active_bot} age={age_minutes}m "
            f"min_age={V8_DIRECTIONAL_MIN_REGIME_AGE_MINUTES}m "
            f"trust={score} min_trust={V8_DIRECTIONAL_MIN_TREND_TRUST_SCORE} "
            f"flips_60m={flips} max_flips={V8_DIRECTIONAL_MAX_FLIPS_60M}"
        )

        if age_minutes < V8_DIRECTIONAL_MIN_REGIME_AGE_MINUTES:
            return EntryDecision(False, "v8_regime_too_young")
        if score < V8_DIRECTIONAL_MIN_TREND_TRUST_SCORE:
            return EntryDecision(False, "v8_trend_trust_below_minimum")
        if flips > V8_DIRECTIONAL_MAX_FLIPS_60M:
            return EntryDecision(False, "v8_noisy_water_filter")
        return None

    def _v9_update_momentum_context(self, route: BotRoute) -> None:
        context = self._v9_session_context()
        active_context = context if context.get("active") else None
        if active_context and not context.get("invalidated"):
            invalidation_reason = self._v9_momentum_context_invalidation_reason()
            if invalidation_reason:
                self._v9_invalidate_momentum_context(context, invalidation_reason)
                print(
                    "[V9] Momentum context invalidated: "
                    f"reason={invalidation_reason}"
                )
            return

        if context.get("evaluated"):
            if not self._v9_can_retry_momentum_reclaim(context):
                return
        elif not self._v9_in_activation_window():
            return

        decision = self._v9_momentum_context_activation_decision(route)
        context.update(decision)
        context["evaluated"] = True
        context["evaluated_at"] = self._time_text(datetime.now(timezone.utc))
        if context.get("active") and self.config.momentum_authority_latch_once_active:
            self._latch_momentum_authority(context, persist=False)
        self.state_store.set_v9_momentum_context(context)
        if context.get("active"):
            print(
                "[V9] Momentum context activated: "
                f"reason={context.get('activation_reason')} "
                f"transitions={context.get('early_transition_count')} "
                f"trans_per_hour={context.get('early_transitions_per_hour')} "
                f"non_warmup={context.get('early_non_warmup_transition_count')} "
                f"trust={context.get('trend_trust_score')} "
                f"soxl={context.get('source_open_to_current_percent')}% "
                f"observer={context.get('observer_preset') or '--'}"
            )
        else:
            print(
                "[V9] Momentum context inactive: "
                f"reason={context.get('activation_reason')} "
                f"preset={self.config.preset_name or '--'}"
            )

    def _v9_can_retry_momentum_reclaim(self, context: dict[str, Any]) -> bool:
        if not self.config.momentum_authority_reclaim_enabled:
            return False
        if context.get("active") or context.get("invalidated"):
            return False
        if not self._v9_in_reclaim_window():
            return False

        reason = str(context.get("activation_reason") or "")
        retryable_reasons = {
            "soxl_below_v9_momentum_floor",
            "trend_trust_below_v9_minimum",
            "soxl_below_reclaim_floor",
        }
        hard_blockers = {
            "v10_forced_no_authority_fallback",
            "not_momentum_context",
            "observer_context_unavailable",
            "first_30m_non_warmup_transition_count_not_zero",
            "early_non_warmup_transition_pressure_too_high",
            "early_transition_count_above_reclaim_limit",
            "reclaim_session_non_warmup_transition_count_not_zero",
            "trend_trust_below_reclaim_minimum",
            "soxl_below_open_after_1030",
            "momentum_drawdown_with_dirty_tape",
        }
        if any(blocker in reason for blocker in hard_blockers):
            return False
        return any(blocker in reason for blocker in retryable_reasons)

    def _v9_invalidate_momentum_context(
        self,
        context: dict[str, Any],
        reason: str,
    ) -> None:
        context.update(
            {
                "active": False,
                "invalidated": True,
                "invalidated_at": self._time_text(datetime.now(timezone.utc)),
                "invalidation_reason": reason,
            }
        )
        self.state_store.set_v9_momentum_context(context)

    def _v9_session_context(self) -> dict[str, Any]:
        current_session = self._v9_session_date()
        context = self.state_store.get_v9_momentum_context()
        if context.get("session_date") == current_session:
            return context
        return {
            "session_date": current_session,
            "active": False,
            "invalidated": False,
            "evaluated": False,
        }

    def _momentum_authority_latched(self) -> bool:
        if not self.config.momentum_authority_latch_once_active:
            return False
        return bool(self._v9_session_context().get("momentum_authority_latched"))

    def _latch_momentum_authority(
        self,
        context: dict[str, Any],
        *,
        persist: bool = True,
    ) -> None:
        if context.get("momentum_authority_latched"):
            return
        context.update(
            {
                "momentum_authority_latched": True,
                "momentum_authority_latched_at": self._time_text(
                    datetime.now(timezone.utc)
                ),
            }
        )
        if persist:
            self.state_store.set_v9_momentum_context(context)

    def _v9_observer_context(self) -> dict[str, Any] | None:
        context = self.config.v9_observer_context
        if not isinstance(context, dict):
            return None
        if context.get("runtime_observer"):
            runtime_context = self._v9_runtime_observer_context()
            return {
                **context,
                **runtime_context,
                "observer_preset": (
                    context.get("observer_preset")
                    or runtime_context.get("observer_preset")
                ),
            }
        return context

    def _v9_runtime_observer_context(self) -> dict[str, Any]:
        window_minutes = V9_MOMENTUM_EARLY_WINDOW_MINUTES
        session_open = self._v9_session_open()
        session_window_close = self._v9_session_window_close(window_minutes)
        transition_count = self._v9_transition_count_between(
            session_open,
            session_window_close,
            include_warmup=True,
        )
        non_warmup_transition_count = self._v9_transition_count_between(
            session_open,
            session_window_close,
            include_warmup=False,
        )
        transitions_per_hour = (
            Decimal(transition_count)
            / Decimal(str(window_minutes))
            * Decimal("60")
        )
        non_warmup_transitions_per_hour = (
            Decimal(non_warmup_transition_count)
            / Decimal(str(window_minutes))
            * Decimal("60")
        )
        trend_score = self._trend_trust.get("score") if self._trend_trust else None
        path = self._v7_source_price_path()
        source_percent = path.current_percent if path is not None else None
        return {
            "observer_preset": "BalancedPure_LiveObserver",
            "early_transition_count": transition_count,
            "early_transitions_per_hour": float(
                transitions_per_hour.quantize(Decimal("0.01"))
            ),
            "early_non_warmup_transition_count": non_warmup_transition_count,
            "early_non_warmup_transitions_per_hour": float(
                non_warmup_transitions_per_hour.quantize(Decimal("0.01"))
            ),
            "trend_trust_score": int(trend_score)
            if isinstance(trend_score, (int, float))
            else None,
            "source_open_to_current_percent": self._v10_path_percent(
                source_percent,
            ),
            "early_transition_window_minutes": window_minutes,
        }

    def _v9_observer_decimal(
        self,
        context: dict[str, Any] | None,
        key: str,
    ) -> Decimal | None:
        if context is None:
            return None
        value = context.get(key)
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _v9_observer_int(
        self,
        context: dict[str, Any] | None,
        key: str,
    ) -> int | None:
        value = self._v9_observer_decimal(context, key)
        if value is None:
            return None
        return int(value)

    def _v9_momentum_context_activation_decision(
        self,
        route: BotRoute,
    ) -> dict[str, Any]:
        observer_context = self._v9_observer_context()
        transition_count = self._v9_observer_int(
            observer_context,
            "early_transition_count",
        )
        transitions_per_hour = self._v9_observer_decimal(
            observer_context,
            "early_transitions_per_hour",
        )
        non_warmup_transition_count = self._v9_observer_int(
            observer_context,
            "early_non_warmup_transition_count",
        )
        non_warmup_transitions_per_hour = self._v9_observer_decimal(
            observer_context,
            "early_non_warmup_transitions_per_hour",
        )
        trust_score = self._v9_observer_int(observer_context, "trend_trust_score")
        source_percent = self._v9_observer_decimal(
            observer_context,
            "source_open_to_current_percent",
        )
        window_minutes = self._v9_observer_int(
            observer_context,
            "early_transition_window_minutes",
        ) or V9_MOMENTUM_EARLY_WINDOW_MINUTES
        if transitions_per_hour is None and transition_count is not None:
            transitions_per_hour = (
                Decimal(transition_count)
                / Decimal(str(window_minutes))
                * Decimal("60")
            )
        if (
            non_warmup_transitions_per_hour is None
            and non_warmup_transition_count is not None
        ):
            non_warmup_transitions_per_hour = (
                Decimal(non_warmup_transition_count)
                / Decimal(str(window_minutes))
                * Decimal("60")
            )
        reasons: list[str] = []
        pre_activation_invalidation_reason = (
            self._v9_momentum_context_invalidation_reason()
        )

        if self.config.v10_force_no_authority:
            reasons.append("v10_forced_no_authority_fallback")
        if not self._v9_is_momentum_context_candidate(route):
            reasons.append("not_momentum_context")
        if observer_context is None:
            reasons.append("observer_context_unavailable")
        if (
            source_percent is None
            or source_percent < self.config.momentum_authority_min_source_percent
        ):
            reasons.append("soxl_below_v9_momentum_floor")
        if non_warmup_transition_count is None or non_warmup_transition_count != 0:
            reasons.append("first_30m_non_warmup_transition_count_not_zero")
        if (
            non_warmup_transitions_per_hour is None
            or non_warmup_transitions_per_hour
            >= self.config.momentum_authority_max_transitions_per_hour
        ):
            reasons.append("early_non_warmup_transition_pressure_too_high")
        if (
            trust_score is None
            or trust_score < self.config.momentum_authority_min_trust_score
        ):
            reasons.append("trend_trust_below_v9_minimum")
        if pre_activation_invalidation_reason:
            reasons.append(pre_activation_invalidation_reason)

        reclaim = self._v9_momentum_reclaim_activation_decision(
            observer_context=observer_context,
            route=route,
            transition_count=transition_count,
            non_warmup_transition_count=non_warmup_transition_count,
            trust_score=trust_score,
            pre_activation_invalidation_reason=pre_activation_invalidation_reason,
        )
        active = not reasons
        reclaim_active = bool(reclaim.get("active")) if reclaim is not None else False
        if reasons and reclaim_active:
            active = True
            reason = V9_MOMENTUM_CONTEXT_RECLAIM_REASON
            source_percent = reclaim.get("source_percent")
        elif reasons and reclaim is not None and self._v9_in_reclaim_window():
            reason = str(reclaim.get("reason") or "v9_momentum_reclaim_not_qualified")
        else:
            reason = (
                V9_MOMENTUM_CONTEXT_ACTIVATION_REASON
                if active
                else ",".join(reasons) or "v9_momentum_context_not_qualified"
            )

        return {
            "active": active,
            "invalidated": False,
            "activation_reason": reason,
            "preset_name": self.config.preset_name,
            "observer_preset": (
                observer_context.get("observer_preset")
                if observer_context is not None
                else None
            ),
            "route_bot": route.active_bot,
            "route_symbol": route.routed_symbol,
            "early_transition_count": transition_count,
            "early_transition_window_minutes": window_minutes,
            "early_transitions_per_hour": (
                float(transitions_per_hour.quantize(Decimal("0.01")))
                if transitions_per_hour is not None
                else None
            ),
            "early_non_warmup_transition_count": non_warmup_transition_count,
            "early_non_warmup_transitions_per_hour": (
                float(non_warmup_transitions_per_hour.quantize(Decimal("0.01")))
                if non_warmup_transitions_per_hour is not None
                else None
            ),
            "trend_trust_score": trust_score,
            "source_open_to_current_percent": (
                float(source_percent.quantize(Decimal("0.01")))
                if isinstance(source_percent, Decimal)
                else None
            ),
            "reclaim_enabled": self.config.momentum_authority_reclaim_enabled,
            "reclaim_reason": reclaim.get("reason") if reclaim is not None else None,
            "reclaim_session_non_warmup_transition_count": (
                reclaim.get("session_non_warmup_transition_count")
                if reclaim is not None
                else None
            ),
            "activated_at": (
                self._time_text(datetime.now(timezone.utc)) if active else None
            ),
        }

    def _v9_momentum_reclaim_activation_decision(
        self,
        *,
        observer_context: dict[str, Any] | None,
        route: BotRoute,
        transition_count: int | None,
        non_warmup_transition_count: int | None,
        trust_score: int | None,
        pre_activation_invalidation_reason: str | None,
    ) -> dict[str, Any] | None:
        if not self.config.momentum_authority_reclaim_enabled:
            return None

        reasons: list[str] = []
        path = self._v7_source_price_path()
        source_percent = path.current_percent if path is not None else None
        session_non_warmup_transition_count = self._v9_non_warmup_flip_count_since(
            self._v9_session_open(),
        )

        if self.config.v10_force_no_authority:
            reasons.append("v10_forced_no_authority_fallback")
        if not self._v9_is_momentum_context_candidate(route):
            reasons.append("not_momentum_context")
        if observer_context is None:
            reasons.append("observer_context_unavailable")
        if not self._v9_in_reclaim_window():
            reasons.append("outside_momentum_reclaim_window")
        if (
            source_percent is None
            or source_percent
            < self.config.momentum_authority_reclaim_min_source_percent
        ):
            reasons.append("soxl_below_reclaim_floor")
        if (
            transition_count is None
            or transition_count
            > self.config.momentum_authority_reclaim_max_raw_transition_count
        ):
            reasons.append("early_transition_count_above_reclaim_limit")
        if (
            non_warmup_transition_count is None
            or non_warmup_transition_count
            > self.config.momentum_authority_reclaim_max_non_warmup_transition_count
        ):
            reasons.append("first_30m_non_warmup_transition_count_not_zero")
        if (
            session_non_warmup_transition_count
            > self.config.momentum_authority_reclaim_max_non_warmup_transition_count
        ):
            reasons.append("reclaim_session_non_warmup_transition_count_not_zero")
        if (
            trust_score is None
            or trust_score < self.config.momentum_authority_reclaim_min_trust_score
        ):
            reasons.append("trend_trust_below_reclaim_minimum")
        if pre_activation_invalidation_reason:
            reasons.append(pre_activation_invalidation_reason)

        return {
            "active": not reasons,
            "reason": (
                V9_MOMENTUM_CONTEXT_RECLAIM_REASON
                if not reasons
                else ",".join(reasons)
            ),
            "source_percent": source_percent,
            "session_non_warmup_transition_count": (
                session_non_warmup_transition_count
            ),
        }

    def _v9_momentum_context_invalidation_reason(self) -> str | None:
        path = self._v7_source_price_path()
        if path is None:
            return None

        now_ny = datetime.now(timezone.utc).astimezone(NY_TZ)
        if now_ny.hour > 10 or (now_ny.hour == 10 and now_ny.minute >= 30):
            if path.current_percent < 0:
                return "soxl_below_open_after_1030"

        drawdown_from_high = path.current_percent - path.runup_percent
        recent_flips = self._v9_non_warmup_flip_count_since(
            datetime.now(timezone.utc) - timedelta(minutes=30),
        )
        if (
            drawdown_from_high <= V9_MOMENTUM_INVALIDATION_DRAWDOWN_FROM_HIGH_PERCENT
            and recent_flips > 0
        ):
            return "momentum_drawdown_with_dirty_tape"
        return None

    def _v9_active_momentum_context(self) -> dict[str, Any] | None:
        context = self._v9_session_context()
        if context.get("active") and not context.get("invalidated"):
            return context
        return None

    def _v9_momentum_context_for_status(self) -> dict[str, Any] | None:
        context = self._v9_session_context()
        if context.get("evaluated") or context.get("active"):
            return context
        return None

    def _v9_is_momentum_context_candidate(self, route: BotRoute) -> bool:
        preset_name = (self.config.preset_name or "").lower()
        if "momentum" in preset_name:
            return True
        if route.active_bot == MOMENTUM_BOT and route.routed_symbol == SOXL:
            return True
        return False

    def _v9_in_activation_window(self) -> bool:
        now_ny = datetime.now(timezone.utc).astimezone(NY_TZ)
        minutes = now_ny.hour * 60 + now_ny.minute
        first_30_close = 9 * 60 + 30 + V9_MOMENTUM_EARLY_WINDOW_MINUTES
        activation_close = first_30_close + V9_MOMENTUM_ACTIVATION_GRACE_MINUTES
        return first_30_close <= minutes <= activation_close

    def _v9_in_reclaim_window(self) -> bool:
        now_ny = datetime.now(timezone.utc).astimezone(NY_TZ)
        minutes = (now_ny.hour * 60 + now_ny.minute) - (9 * 60 + 30)
        return (
            self.config.momentum_authority_reclaim_start_minutes
            <= minutes
            <= self.config.momentum_authority_reclaim_end_minutes
        )

    def _v9_session_date(self) -> str:
        return datetime.now(timezone.utc).astimezone(NY_TZ).date().isoformat()

    def _v9_session_open(self) -> datetime:
        now_ny = datetime.now(timezone.utc).astimezone(NY_TZ)
        open_ny = now_ny.replace(hour=9, minute=30, second=0, microsecond=0)
        return open_ny.astimezone(timezone.utc)

    def _v9_session_window_close(self, minutes: int) -> datetime:
        return self._v9_session_open() + timedelta(minutes=minutes)

    def _v9_elapsed_session_minutes(self) -> Decimal:
        elapsed_seconds = max(
            (datetime.now(timezone.utc) - self._v9_session_open()).total_seconds(),
            0,
        )
        return Decimal(str(elapsed_seconds)) / Decimal("60")

    def _v9_non_warmup_flip_count_since(self, cutoff: datetime) -> int:
        return self._v9_non_warmup_flip_count_between(cutoff, None)

    def _v9_non_warmup_flip_count_between(
        self,
        start: datetime,
        end: datetime | None,
    ) -> int:
        return self._v9_transition_count_between(
            start,
            end,
            include_warmup=False,
        )

    def _v9_transition_count_between(
        self,
        start: datetime,
        end: datetime | None,
        *,
        include_warmup: bool,
    ) -> int:
        regime_state = self.state_store.get_regime_state()
        transitions = regime_state.get("transitions")
        if not isinstance(transitions, list):
            return 0
        count = 0
        for transition in transitions:
            if not isinstance(transition, dict):
                continue
            from_regime = str(transition.get("from") or "").upper()
            to_regime = str(transition.get("to") or "").upper()
            if not include_warmup and (from_regime == WARMUP or to_regime == WARMUP):
                continue
            transition_at = parse_market_timestamp(transition.get("at"))
            if transition_at is None or transition_at < start:
                continue
            if end is not None and transition_at >= end:
                continue
            if transition_at is not None:
                count += 1
        return count

    def _v7_entry_policy_decision(
        self,
        route: BotRoute,
        soxl_snapshot: SmaSnapshot,
    ) -> EntryDecision | None:
        del soxl_snapshot
        stats = self._v7_session_stats()
        route_invalidated = stats["route_invalidated_exits"]
        if route_invalidated >= V7_ROUTE_INVALIDATION_EXIT_LIMIT:
            print(
                "[V7] Fresh entries paused: "
                f"route_invalidated_exits={route_invalidated} "
                f"limit={V7_ROUTE_INVALIDATION_EXIT_LIMIT}."
            )
            return EntryDecision(False, "v7_route_invalidation_breaker")

        if route.active_bot == INVERSE_BOT:
            path = self._v7_source_price_path()
            if path is not None:
                bias = self._v7_day_bias(path)
                bull_failed = self._v7_bull_bias_failed(path)
                print(
                    "[V7] Day path: "
                    f"bias={bias} current={path.current_percent:.2f}% "
                    f"runup={path.runup_percent:.2f}% "
                    f"drawdown={path.drawdown_percent:.2f}% "
                    f"bull_failed={bull_failed}"
                )
                if bias == V7_DAY_BIAS_BULL and not bull_failed:
                    return EntryDecision(False, "v7_bull_bias_blocks_inverse")

        losses_by_bot = stats["losses_by_bot"]
        pl_by_bot = stats["pl_by_bot"]
        bot_losses = losses_by_bot.get(route.active_bot, 0)
        bot_pl = pl_by_bot.get(route.active_bot, Decimal("0"))
        if (
            route.active_bot == INVERSE_BOT
            and bot_losses >= V7_INVERSE_LOSS_LIMIT
            and bot_pl < 0
        ):
            print(
                "[V7] InverseBot fresh entries paused: "
                f"losses={bot_losses} realized_pl={format_decimal(bot_pl)}."
            )
            return EntryDecision(False, "v7_inverse_loss_breaker")
        if bot_losses >= V7_BOT_LOSS_LIMIT and bot_pl < 0:
            print(
                "[V7] Bot fresh entries paused: "
                f"bot={route.active_bot} losses={bot_losses} "
                f"realized_pl={format_decimal(bot_pl)}."
            )
            return EntryDecision(False, "v7_bot_loss_breaker")
        return None

    def _v7_source_price_path(self) -> SourcePricePath | None:
        return self._symbol_session_price_path(SOXL)

    def _symbol_session_price_path(self, symbol: str) -> SourcePricePath | None:
        session_bars = self._symbol_session_bars(symbol)
        if len(session_bars) < 2:
            return None

        open_price = self._v7_bar_decimal(session_bars[0], "o", "c")
        current_price = self._v7_bar_decimal(session_bars[-1], "c", "o")
        highs = [
            value
            for bar in session_bars
            if (value := self._v7_bar_decimal(bar, "h", "c", "o")) is not None
        ]
        lows = [
            value
            for bar in session_bars
            if (value := self._v7_bar_decimal(bar, "l", "c", "o")) is not None
        ]
        if open_price is None or current_price is None or open_price <= 0:
            return None
        high_price = max(highs or [open_price, current_price])
        low_price = min(lows or [open_price, current_price])
        return SourcePricePath(
            open_price=open_price,
            current_price=current_price,
            high_price=high_price,
            low_price=low_price,
            current_percent=(current_price - open_price) / open_price * Decimal("100"),
            runup_percent=(high_price - open_price) / open_price * Decimal("100"),
            drawdown_percent=(low_price - open_price) / open_price * Decimal("100"),
        )

    def _symbol_session_bars(self, symbol: str) -> list[dict[str, Any]]:
        try:
            data_source = self.market_data or self.client
            bars = data_source.get_recent_bars(symbol, 420)
        except (BotError, KeyError):
            return []

        session_date = self._v7_session_date()
        return [
            bar
            for bar in bars
            if self._v7_record_date(bar.get("t")) == session_date
        ]

    def _symbol_previous_session_close(self, symbol: str) -> Decimal | None:
        data_source = self.market_data or self.client
        getter = getattr(data_source, "get_previous_session_close", None)
        if not callable(getter):
            return None
        try:
            value = getter(symbol)
        except (BotError, KeyError):
            return None
        return optional_decimal_from_api(value, f"{symbol} previous session close")

    def _recent_session_return_percent(
        self,
        symbol: str,
        window_minutes: int,
    ) -> Decimal | None:
        session_bars = self._symbol_session_bars(symbol)
        if len(session_bars) < 2:
            return None

        latest_bar = session_bars[-1]
        latest_time = parse_market_timestamp(latest_bar.get("t"))
        current_price = self._v7_bar_decimal(latest_bar, "c", "o")
        if latest_time is None or current_price is None or current_price <= 0:
            return None

        cutoff = latest_time - timedelta(minutes=window_minutes)
        reference_bar = session_bars[0]
        for bar in session_bars:
            bar_time = parse_market_timestamp(bar.get("t"))
            if bar_time is None or bar_time > cutoff:
                break
            reference_bar = bar
        reference_price = self._v7_bar_decimal(reference_bar, "c", "o")
        if reference_price is None or reference_price <= 0:
            return None
        return (current_price - reference_price) / reference_price * Decimal("100")

    def _v7_bar_decimal(
        self,
        bar: dict[str, Any],
        *field_names: str,
    ) -> Decimal | None:
        for field_name in field_names:
            value = optional_decimal_from_api(bar.get(field_name), field_name)
            if value is not None:
                return value
        return None

    def _v7_day_bias(self, path: SourcePricePath) -> str:
        if (
            path.current_percent >= V7_BULL_CURRENT_MIN_PERCENT
            or (
                path.runup_percent >= V7_BULL_RUNUP_MIN_PERCENT
                and path.current_percent >= Decimal("-0.50")
            )
        ):
            return V7_DAY_BIAS_BULL
        if (
            path.current_percent <= V7_BEAR_CURRENT_MAX_PERCENT
            and path.drawdown_percent <= V7_BEAR_DRAWDOWN_MIN_PERCENT
        ):
            return V7_DAY_BIAS_BEAR
        return V7_DAY_BIAS_NEUTRAL

    def _v7_bull_bias_failed(self, path: SourcePricePath) -> bool:
        return (
            path.current_percent <= V7_BULL_FAILURE_CURRENT_PERCENT
            and path.drawdown_percent <= V7_BULL_FAILURE_DRAWDOWN_PERCENT
        )

    def _v7_session_stats(self) -> dict[str, Any]:
        records = self.lifecycle_ledger.read_all()
        session_date = self._v7_session_date()
        session_records = [
            record
            for record in records
            if self._v7_record_date(record.get("created_at")) == session_date
        ]
        route_invalidated_exits = sum(
            1
            for record in session_records
            if record.get("event_type") == LIFECYCLE_POSITION_CLOSED
            and record.get("reason") == "route_invalidated_exit"
        )
        trade_health = self._v7_trade_health(session_records)
        return {
            "route_invalidated_exits": route_invalidated_exits,
            "losses_by_bot": trade_health["losses_by_bot"],
            "pl_by_bot": trade_health["pl_by_bot"],
        }

    def _v7_session_date(self) -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def _v7_record_date(self, value: Any) -> str | None:
        parsed = parse_market_timestamp(value)
        if parsed is None:
            return None
        return parsed.astimezone(timezone.utc).date().isoformat()

    def _v7_trade_health(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        lots_by_symbol: dict[str, list[dict[str, Any]]] = {}
        losses_by_bot: dict[str, int] = {
            MOMENTUM_BOT: 0,
            CHOP_BOT: 0,
            INVERSE_BOT: 0,
        }
        pl_by_bot: dict[str, Decimal] = {
            MOMENTUM_BOT: Decimal("0"),
            CHOP_BOT: Decimal("0"),
            INVERSE_BOT: Decimal("0"),
        }

        for record in records:
            if record.get("event_type") not in {
                LIFECYCLE_PARTIAL_FILL,
                LIFECYCLE_FULL_FILL,
            }:
                continue
            side = str(record.get("side") or "").lower()
            symbol = record.get("symbol")
            if not isinstance(symbol, str) or side not in {"buy", "sell"}:
                continue
            qty = optional_decimal_from_api(
                record.get("fill_delta_qty") or record.get("filled_qty"),
                "filled qty",
            )
            price = optional_decimal_from_api(
                record.get("filled_avg_price"),
                "filled avg price",
            )
            if qty is None or qty <= 0 or price is None:
                continue

            bot_name = self._v7_bot_name(record.get("bot"))
            if side == "buy":
                lots_by_symbol.setdefault(symbol, []).append(
                    {"qty": qty, "price": price, "bot": bot_name}
                )
                continue

            remaining = qty
            matched_pl_by_bot: dict[str, Decimal] = {}
            lots = lots_by_symbol.setdefault(symbol, [])
            while remaining > 0 and lots:
                lot = lots[0]
                lot_qty = Decimal(str(lot["qty"]))
                consumed = min(remaining, lot_qty)
                lot_bot = bot_name or self._v7_bot_name(lot.get("bot"))
                if lot_bot in pl_by_bot:
                    matched_pl_by_bot[lot_bot] = matched_pl_by_bot.get(
                        lot_bot,
                        Decimal("0"),
                    ) + consumed * (price - Decimal(str(lot["price"])))
                remaining -= consumed
                lot["qty"] = lot_qty - consumed
                if lot["qty"] <= 0:
                    lots.pop(0)

            for matched_bot, matched_pl in matched_pl_by_bot.items():
                pl_by_bot[matched_bot] += matched_pl
                if matched_pl < 0:
                    losses_by_bot[matched_bot] += 1

        return {"losses_by_bot": losses_by_bot, "pl_by_bot": pl_by_bot}

    def _v7_bot_name(self, value: Any) -> str | None:
        text = str(value) if value not in (None, "") else None
        if text in {MOMENTUM_BOT, CHOP_BOT, INVERSE_BOT}:
            return text
        return None

    def _entry_decision_for_route(
        self,
        route: BotRoute,
        soxl_snapshot: SmaSnapshot,
    ) -> EntryDecision:
        if route.active_bot == MOMENTUM_BOT:
            snapshot = self._directional_entry_snapshot(SOXL, soxl_snapshot)
            return self._directional_entry_decision(
                bot_name=MOMENTUM_BOT,
                symbol=SOXL,
                snapshot=snapshot,
                source_strength=self._strength_for_gap(UPTREND, soxl_snapshot.gap_percent),
            )

        if route.active_bot == CHOP_BOT:
            if soxl_snapshot.slow_sma == 0:
                print(
                    "[ENTRY] ChopBot entry check: slow_sma=0.0000 "
                    "entry_signal=False"
                )
                return EntryDecision(False, "invalid_mean")
            discount_percent = (
                (soxl_snapshot.slow_sma - soxl_snapshot.price)
                / soxl_snapshot.slow_sma
                * Decimal("100")
            )
            entry_signal = soxl_snapshot.price <= soxl_snapshot.slow_sma * (
                Decimal("1")
                - (self.config.chop_entry_discount_percent / Decimal("100"))
            )
            if entry_signal:
                reason = "discount_confirmed"
            elif discount_percent <= 0:
                reason = "price_above_mean"
            else:
                reason = "discount_insufficient"
            print(
                f"[ENTRY] ChopBot entry check: price={soxl_snapshot.price:.4f} "
                f"slow_sma={soxl_snapshot.slow_sma:.4f} "
                f"discount={discount_percent:.2f}% "
                f"threshold={self.config.chop_entry_discount_percent}% "
                f"reason={reason}"
            )
            return EntryDecision(entry_signal, reason)

        if route.active_bot == INVERSE_BOT and route.routed_symbol:
            cascade_decision = self._inverse_cascade_entry_decision(route)
            if cascade_decision is not None:
                return cascade_decision
            if self._inverse_cascade_stopped_out_session_locked():
                return EntryDecision(False, "inverse_cascade_stopped_out_session_locked")
            if self.config.inverse_cascade_mode == INVERSE_CASCADE_MODE_SUSTAINED:
                return EntryDecision(False, "inverse_cascade_required")
            snapshot = self._directional_entry_snapshot(route.routed_symbol)
            if snapshot is None:
                return EntryDecision(False, "inverse_confirmation_missing")
            return self._directional_entry_decision(
                bot_name=INVERSE_BOT,
                symbol=route.routed_symbol,
                snapshot=snapshot,
                source_strength=self._strength_for_gap(
                    DOWNTREND,
                    soxl_snapshot.gap_percent,
                ),
            )

        return EntryDecision(False, "route_not_supported")

    def _inverse_cascade_entry_decision(self, route: BotRoute) -> EntryDecision | None:
        if not self._inverse_cascade_context_active(route):
            return None

        routed_symbol = route.routed_symbol or SOXS
        cooldown_active, cooldown_remaining = self._directional_cooldown_status(
            INVERSE_BOT,
            routed_symbol,
        )
        if cooldown_active:
            return EntryDecision(
                False,
                f"directional_cooldown_active_{cooldown_remaining}m",
            )

        context = self._inverse_cascade_context or {}
        if self._inverse_cascade_reentry_locked():
            return EntryDecision(False, "inverse_cascade_reentry_locked")
        print(
            "[ENTRY] InverseBot cascade check: "
            f"mode={context.get('mode')} symbol={routed_symbol} "
            f"soxl={self._decimal_text(context.get('source_current_percent'))}% "
            f"soxl_dd={self._decimal_text(context.get('source_drawdown_percent'))}% "
            f"soxl_recovery={self._decimal_text(context.get('source_recovery_percent'))}% "
            f"soxs={self._decimal_text(context.get('inverse_current_percent'))}% "
            f"velocity={self._decimal_text(context.get('source_velocity_percent'))}%"
        )
        return EntryDecision(
            True,
            f"inverse_cascade_{str(context.get('mode')).lower()}_confirmed",
        )

    def _entry_lifecycle_context(
        self,
        route: BotRoute,
        reason: str,
    ) -> dict[str, Any] | None:
        if route.active_bot != INVERSE_BOT or route.routed_symbol != SOXS:
            return None

        context: dict[str, Any] = {
            "entry_family": "inverse_legacy",
            "inverse_entry_family": "legacy",
            "inverse_cascade_confirmed": False,
        }
        if not reason.startswith("inverse_cascade_"):
            return context

        cascade_context = self._inverse_cascade_context or {}
        context.update(
            {
                "entry_family": "inverse_cascade",
                "inverse_entry_family": "cascade",
                "inverse_cascade_confirmed": True,
                "inverse_cascade_mode": cascade_context.get("mode"),
                "base_route_bot": cascade_context.get("base_route_bot"),
                "base_route_symbol": cascade_context.get("base_route_symbol"),
                "source_current_percent": cascade_context.get("source_current_percent"),
                "source_drawdown_percent": cascade_context.get(
                    "source_drawdown_percent"
                ),
                "source_recovery_percent": cascade_context.get(
                    "source_recovery_percent"
                ),
                "source_velocity_percent": cascade_context.get(
                    "source_velocity_percent"
                ),
                "inverse_current_percent": cascade_context.get(
                    "inverse_current_percent"
                ),
                "sustain_source_deepening_percent": cascade_context.get(
                    "sustain_source_deepening_percent"
                ),
                "sustain_source_new_low_count": cascade_context.get(
                    "sustain_source_new_low_count"
                ),
                "soxl_pct_from_open_at_cascade_window_start": cascade_context.get(
                    "soxl_pct_from_open_at_cascade_window_start"
                ),
                "soxl_pct_vs_prior_close_at_cascade_window_start": cascade_context.get(
                    "soxl_pct_vs_prior_close_at_cascade_window_start"
                ),
                "sustain_source_direction_changes": cascade_context.get(
                    "sustain_source_direction_changes"
                ),
                "sustain_source_down_path_ratio": cascade_context.get(
                    "sustain_source_down_path_ratio"
                ),
                "sustain_source_path_length_percent": cascade_context.get(
                    "sustain_source_path_length_percent"
                ),
                "sustain_source_down_distance_percent": cascade_context.get(
                    "sustain_source_down_distance_percent"
                ),
                "entry_bar_soxl_pct": cascade_context.get("entry_bar_soxl_pct"),
                "entry_bar_soxl_direction": cascade_context.get(
                    "entry_bar_soxl_direction"
                ),
                "entry_bar_soxl_prior_avg_abs_pct": cascade_context.get(
                    "entry_bar_soxl_prior_avg_abs_pct"
                ),
                "entry_bar_soxl_velocity_ratio": cascade_context.get(
                    "entry_bar_soxl_velocity_ratio"
                ),
                "entry_bar_soxs_pct": cascade_context.get("entry_bar_soxs_pct"),
                "entry_bar_soxs_direction": cascade_context.get(
                    "entry_bar_soxs_direction"
                ),
                "entry_bar_soxs_prior_avg_abs_pct": cascade_context.get(
                    "entry_bar_soxs_prior_avg_abs_pct"
                ),
                "entry_bar_soxs_velocity_ratio": cascade_context.get(
                    "entry_bar_soxs_velocity_ratio"
                ),
                "sustained_window_minutes": cascade_context.get(
                    "sustained_window_minutes"
                ),
            }
        )
        return context

    def _mark_inverse_cascade_entry(self, route: BotRoute, reason: str) -> None:
        if (
            self.config.inverse_cascade_mode != INVERSE_CASCADE_MODE_SUSTAINED
            or route.active_bot != INVERSE_BOT
            or route.routed_symbol != SOXS
            or not reason.startswith("inverse_cascade_sustained_")
        ):
            return
        context = self._inverse_cascade_context or {}
        self.state_store.set_inverse_cascade_state(
            {
                "mode": INVERSE_CASCADE_MODE_SUSTAINED,
                "session_date": self._inverse_cascade_session_date(),
                "entered_at": datetime.now(timezone.utc).isoformat(),
                "lockout_active": True,
                "entry_reason": reason,
                "source_current_percent": context.get("source_current_percent"),
                "source_drawdown_percent": context.get("source_drawdown_percent"),
                "source_velocity_percent": context.get("source_velocity_percent"),
                "inverse_current_percent": context.get("inverse_current_percent"),
                "sustain_source_deepening_percent": context.get(
                    "sustain_source_deepening_percent"
                ),
                "sustain_source_new_low_count": context.get(
                    "sustain_source_new_low_count"
                ),
                "sustained_window_minutes": context.get("sustained_window_minutes"),
                "invalidation_started_at": None,
                "max_favorable_excursion_percent": None,
                "max_favorable_price": None,
                "proven_at": None,
                "proven_mfe_percent": None,
                "proven_threshold_percent": format_decimal(
                    self.config.inverse_cascade_proven_mfe_percent
                ),
            }
        )

    def _directional_entry_decision(
        self,
        bot_name: str,
        symbol: str,
        snapshot: SmaSnapshot,
        source_strength: str,
    ) -> EntryDecision:
        cooldown_active, cooldown_remaining = self._directional_cooldown_status(
            bot_name,
            symbol,
        )
        directional_mode = self._effective_directional_mode_for_bot(bot_name)
        extension_percent = self._extension_above_fast_sma(snapshot)
        symbol_strength = self._strength_for_gap(UPTREND, snapshot.gap_percent)
        print(
            f"[ENTRY] {bot_name} entry check: symbol={symbol} "
            f"price={snapshot.price:.4f} fast_sma={snapshot.fast_sma:.4f} "
            f"slow_sma={snapshot.slow_sma:.4f} "
            f"source_strength={source_strength} symbol_strength={symbol_strength} "
            f"extension={extension_percent:.2f}% "
            f"max_extension={self.config.directional_max_extension_percent}% "
            f"chase_max={self.config.directional_strong_chase_max_extension_percent}% "
            f"min_strength={self.config.directional_min_strength} "
            f"mode={directional_mode} "
            f"crossed_above={snapshot.crossed_above}"
        )

        if cooldown_active:
            return EntryDecision(
                False,
                f"directional_cooldown_active_{cooldown_remaining}m",
            )
        if snapshot.crossed_above:
            return EntryDecision(True, "fresh_cross_confirmed")
        if directional_mode == DIRECTIONAL_MODE_CONSERVATIVE:
            return EntryDecision(False, "mode_requires_fresh_cross")
        if not self._strength_meets_minimum(source_strength):
            return EntryDecision(False, "directional_strength_below_minimum")
        if snapshot.fast_sma <= snapshot.slow_sma:
            return EntryDecision(False, self._directional_weak_reason(bot_name))
        if snapshot.price < snapshot.slow_sma:
            return EntryDecision(False, self._directional_weak_reason(bot_name))
        if extension_percent <= self.config.directional_max_extension_percent:
            return EntryDecision(True, "trend_continuation_allowed")
        if (
            directional_mode == DIRECTIONAL_MODE_AGGRESSIVE
            and source_strength == REGIME_STRENGTH_STRONG
            and extension_percent
            <= self.config.directional_strong_chase_max_extension_percent
        ):
            return EntryDecision(True, "strong_trend_chase_allowed")
        return EntryDecision(False, "already_extended_above_fast_sma")

    def _directional_weak_reason(self, bot_name: str) -> str:
        if bot_name == INVERSE_BOT:
            return "soxs_momentum_weak"
        return "trend_strength_weakening"

    def _directional_entry_snapshot(
        self,
        symbol: str,
        fallback: SmaSnapshot | None = None,
    ) -> SmaSnapshot | None:
        probe = TrailingStopBot(
            config_for_symbol(self.config, symbol),
            self.client,
            self.state_store,
            self.market_data,
            self.lifecycle_ledger,
        )
        snapshot = probe._sma_snapshot(symbol, require_cross_context=True)
        if snapshot is not None:
            return snapshot
        if fallback is not None:
            return fallback
        return probe._sma_snapshot(symbol, require_cross_context=False)

    def _extension_above_fast_sma(self, snapshot: SmaSnapshot) -> Decimal:
        if snapshot.fast_sma == 0:
            return Decimal("0")
        return (snapshot.price - snapshot.fast_sma) / snapshot.fast_sma * Decimal("100")

    def _directional_cooldown_status(self, bot_name: str, symbol: str) -> tuple[bool, int]:
        cooldown_minutes = self.config.directional_cooldown_minutes
        if cooldown_minutes <= 0:
            return False, 0

        last_entry_at = self.state_store.get_last_entry_at(bot_name, symbol)
        if last_entry_at is None:
            return False, 0

        elapsed_seconds = age_seconds(last_entry_at)
        if elapsed_seconds is None:
            return False, 0

        cooldown_seconds = cooldown_minutes * 60
        if elapsed_seconds >= cooldown_seconds:
            return False, 0

        remaining = int((cooldown_seconds - elapsed_seconds + 59) // 60)
        return True, max(remaining, 1)

    def _stale_symbol(
        self,
        route: BotRoute,
        positions: dict[str, dict[str, Any] | None],
    ) -> str | None:
        for symbol in self.basket_symbols:
            position = positions.get(symbol)
            if self._position_qty(position) <= 0:
                continue
            owner = self.state_store.get_position_owner(symbol)
            if symbol != route.routed_symbol or owner != route.active_bot:
                return symbol
        return None

    def _position_qty(self, position: dict[str, Any] | None) -> Decimal:
        if not position:
            return Decimal("0")
        return decimal_from_api(position.get("qty"), "position qty")

    def _maybe_hold_inverse_cascade_route_invalidated_position(
        self,
        symbol: str,
        position: dict[str, Any] | None,
        orders: list[dict[str, Any]],
        regime: str,
        active_bot: str,
        owner: str | None,
    ) -> str | None:
        del regime, active_bot
        if (
            self.config.inverse_cascade_mode != INVERSE_CASCADE_MODE_SUSTAINED
            or symbol != SOXS
            or owner not in {INVERSE_BOT, None}
        ):
            return None
        state = self._inverse_cascade_same_session_state()
        if (
            state.get("mode") != INVERSE_CASCADE_MODE_SUSTAINED
            or not state.get("entered_at")
        ):
            return None
        avg_entry_price = optional_decimal_from_api(
            (position or {}).get("avg_entry_price"),
            "avg entry price",
        )
        if avg_entry_price is not None:
            state = self._maybe_update_inverse_cascade_proven_state(
                symbol,
                avg_entry_price,
            )

        now = datetime.now(timezone.utc)
        symbol_orders = [order for order in orders if order.get("symbol") == symbol]
        source_current_percent = self._inverse_cascade_source_current_percent()
        if (
            state.get("proven_at")
            and source_current_percent is not None
            and source_current_percent
            < self.config.inverse_cascade_proven_route_recovery_min_source_percent
        ):
            state["invalidation_started_at"] = None
            self.state_store.set_inverse_cascade_state(state)
            print(
                "[INVERSE] Proven cascade route invalidation suppressed: "
                f"symbol={symbol} source_current={source_current_percent:.2f}% "
                "state=proven"
            )
            risk_bot = TrailingStopBot(
                config_for_symbol(self.config, symbol),
                self.client,
                self.state_store,
                self.market_data,
                self.lifecycle_ledger,
            )
            risk_bot._manage_trailing_stop(symbol, position or {}, symbol_orders)
            return "hold_inverse_cascade_proven_route_suppressed"

        grace_minutes = self.config.inverse_cascade_route_invalidation_grace_minutes
        if grace_minutes <= 0:
            return None

        started_at = parse_market_timestamp(state.get("invalidation_started_at"))
        if started_at is None:
            started_at = now
            state["invalidation_started_at"] = started_at.isoformat()
            self.state_store.set_inverse_cascade_state(state)
        elapsed = age_seconds(started_at, now) or 0
        if elapsed >= grace_minutes * 60:
            print(
                "[INVERSE] Sustained cascade route invalidation grace expired: "
                f"symbol={symbol} elapsed={self._rounded_seconds(elapsed)}s"
            )
            return None

        print(
            "[INVERSE] Sustained cascade route invalidation grace active: "
            f"symbol={symbol} elapsed={self._rounded_seconds(elapsed)}s "
            f"grace={grace_minutes}m"
        )
        risk_bot = TrailingStopBot(
            config_for_symbol(self.config, symbol),
            self.client,
            self.state_store,
            self.market_data,
            self.lifecycle_ledger,
        )
        risk_bot._manage_trailing_stop(symbol, position or {}, symbol_orders)
        return "hold_inverse_cascade_route_invalidation_grace"

    def _clear_inverse_cascade_invalidation_when_route_valid(
        self,
        route: BotRoute,
        positions: dict[str, dict[str, Any] | None],
    ) -> None:
        if (
            self.config.inverse_cascade_mode != INVERSE_CASCADE_MODE_SUSTAINED
            or route.active_bot != INVERSE_BOT
            or route.routed_symbol != SOXS
            or self._position_qty(positions.get(SOXS)) <= 0
        ):
            return
        owner = self.state_store.get_position_owner(SOXS)
        if owner not in {INVERSE_BOT, None}:
            return
        self._inverse_cascade_clear_invalidation_state()

    def _maybe_exit_momentum_authority_revoked_position(
        self,
        route: BotRoute,
        positions: dict[str, dict[str, Any] | None],
        orders: list[dict[str, Any]],
        regime: str,
    ) -> str | None:
        if not (
            self.config.momentum_authority_required
            and self.config.momentum_authority_revoke_exits
        ):
            return None

        position = positions.get(SOXL)
        if self._position_qty(position) <= 0:
            return None

        owner = self.state_store.get_position_owner(SOXL)
        if owner != MOMENTUM_BOT:
            return None

        block_reason = self._momentum_authority_block_reason()
        if block_reason is None:
            return None

        return self._close_momentum_authority_revoked_position(
            SOXL,
            position,
            orders,
            regime,
            route.active_bot,
            block_reason,
        )

    def _close_momentum_authority_revoked_position(
        self,
        symbol: str,
        position: dict[str, Any] | None,
        orders: list[dict[str, Any]],
        regime: str,
        active_bot: str,
        revoke_reason: str,
    ) -> str:
        symbol_orders = [order for order in orders if order.get("symbol") == symbol]
        if any(order.get("side") == "sell" for order in symbol_orders):
            print(
                f"[RISK] {symbol}: Momentum authority revoked, sell order already open; "
                "entry_signal=False action_taken=wait_for_momentum_authority_revoked_close"
            )
            return "wait_for_momentum_authority_revoked_close"
        if any(order.get("side") == "buy" for order in symbol_orders):
            print(
                f"[RISK] {symbol}: Momentum authority revoked, buy order still open; "
                "entry_signal=False action_taken=wait_for_momentum_authority_revoked_close_order"
            )
            return "wait_for_momentum_authority_revoked_close_order"

        qty = self._position_qty(position).quantize(
            FRACTIONAL_QTY_STEP,
            rounding=ROUND_DOWN,
        )
        if qty <= 0:
            print(
                f"[RISK] {symbol}: authority-revoked Momentum position not found; "
                "entry_signal=False action_taken=noop"
            )
            return "noop"

        lifecycle_context = self._route_invalidation_context(
            symbol,
            position,
            qty,
            regime,
            active_bot,
            MOMENTUM_BOT,
        )
        lifecycle_context["authority_revoke_reason"] = revoke_reason
        print(
            f"[RISK] {symbol}: Momentum authority revoked; "
            f"reason={revoke_reason}; selling qty={format_decimal(qty)}."
        )
        self._record_lifecycle(
            LIFECYCLE_INTENDED_EXIT,
            bot=MOMENTUM_BOT,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason=MOMENTUM_AUTHORITY_REVOKED_EXIT_REASON,
            regime=regime,
            active_bot=active_bot,
            owner=MOMENTUM_BOT,
            authority_revoke_reason=revoke_reason,
            lifecycle_context=lifecycle_context,
        )
        try:
            order = self.client.submit_market_sell_qty(symbol, qty)
        except BotError as exc:
            self._record_lifecycle(
                LIFECYCLE_ORDER_REJECTED,
                bot=MOMENTUM_BOT,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason=MOMENTUM_AUTHORITY_REVOKED_EXIT_REASON,
                regime=regime,
                active_bot=active_bot,
                owner=MOMENTUM_BOT,
                authority_revoke_reason=revoke_reason,
                error=str(exc),
                broker_constraint=self._broker_rejection_payload(exc, "sell", symbol),
                lifecycle_context=lifecycle_context,
            )
            raise
        self._record_lifecycle(
            LIFECYCLE_ORDER_SUBMITTED,
            bot=MOMENTUM_BOT,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason=MOMENTUM_AUTHORITY_REVOKED_EXIT_REASON,
            regime=regime,
            active_bot=active_bot,
            owner=MOMENTUM_BOT,
            authority_revoke_reason=revoke_reason,
            order=order,
            lifecycle_context=lifecycle_context,
        )
        self.order_tracker.track_submitted_order(
            order,
            MOMENTUM_BOT,
            MOMENTUM_AUTHORITY_REVOKED_EXIT_REASON,
            lifecycle_context,
        )
        self.state_store.clear_symbol(symbol)
        print(
            "entry_signal=False "
            "action_taken=close_momentum_authority_revoked_position_no_same_cycle_reversal"
        )
        return "close_momentum_authority_revoked_position_no_same_cycle_reversal"

    def _close_stale_position(
        self,
        symbol: str,
        position: dict[str, Any] | None,
        orders: list[dict[str, Any]],
        regime: str,
        active_bot: str,
        owner: str | None,
    ) -> str:
        owner_text = owner or "UNKNOWN"
        symbol_orders = [order for order in orders if order.get("symbol") == symbol]
        if any(order.get("side") == "sell" for order in symbol_orders):
            print(
                f"[RISK] {symbol}: regime={regime} owner={owner_text} "
                f"active_bot={active_bot} route invalidated, sell order already open; "
                "entry_signal=False action_taken=wait_for_route_invalidated_close"
            )
            return "wait_for_route_invalidated_close"
        if any(order.get("side") == "buy" for order in symbol_orders):
            print(
                f"[RISK] {symbol}: regime={regime} owner={owner_text} "
                f"active_bot={active_bot} route invalidated, buy order still open; "
                "entry_signal=False action_taken=wait_for_route_invalidated_close_order"
            )
            return "wait_for_route_invalidated_close_order"

        qty = self._position_qty(position).quantize(
            FRACTIONAL_QTY_STEP,
            rounding=ROUND_DOWN,
        )
        if qty <= 0:
            print(
                f"[RISK] {symbol}: route-invalidated position not found; "
                "entry_signal=False action_taken=noop"
            )
            return "noop"

        lifecycle_context = self._route_invalidation_context(
            symbol,
            position,
            qty,
            regime,
            active_bot,
            owner,
        )
        print(
            f"[RISK] {symbol}: route invalidated under regime={regime}; "
            f"owner={owner_text} active_bot={active_bot}; "
            f"selling qty={format_decimal(qty)}."
        )
        self._record_lifecycle(
            LIFECYCLE_INTENDED_EXIT,
            bot=owner_text,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason="route_invalidated_exit",
            regime=regime,
            active_bot=active_bot,
            owner=owner_text,
            lifecycle_context=lifecycle_context,
        )
        try:
            order = self.client.submit_market_sell_qty(symbol, qty)
        except BotError as exc:
            self._record_lifecycle(
                LIFECYCLE_ORDER_REJECTED,
                bot=owner_text,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="route_invalidated_exit",
                regime=regime,
                active_bot=active_bot,
                owner=owner_text,
                error=str(exc),
                broker_constraint=self._broker_rejection_payload(exc, "sell", symbol),
                lifecycle_context=lifecycle_context,
            )
            raise
        self._record_lifecycle(
            LIFECYCLE_ORDER_SUBMITTED,
            bot=owner_text,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason="route_invalidated_exit",
            regime=regime,
            active_bot=active_bot,
            owner=owner_text,
            order=order,
            lifecycle_context=lifecycle_context,
        )
        self.order_tracker.track_submitted_order(
            order,
            owner_text,
            "route_invalidated_exit",
            lifecycle_context,
        )
        self.state_store.clear_symbol(symbol)
        print(
            "entry_signal=False "
            "action_taken=close_route_invalidated_position_no_same_cycle_reversal"
        )
        return "close_route_invalidated_position_no_same_cycle_reversal"

    def _maybe_exit_chop_position(
        self,
        symbol: str,
        position: dict[str, Any],
        symbol_orders: list[dict[str, Any]],
        soxl_snapshot: SmaSnapshot,
    ) -> str | None:
        reclaim = soxl_snapshot.price >= soxl_snapshot.slow_sma
        print(
            f"[RISK] ChopBot exit check: price={soxl_snapshot.price:.4f} "
            f"slow_sma={soxl_snapshot.slow_sma:.4f} reclaim={reclaim}"
        )
        if not reclaim:
            return None

        if any(order.get("side") == "sell" for order in symbol_orders):
            print(
                f"[RISK] {symbol}: ChopBot slow SMA reclaim, sell order already open; "
                "entry_signal=False action_taken=wait_for_chop_exit_order"
            )
            return "wait_for_chop_exit_order"
        if any(order.get("side") == "buy" for order in symbol_orders):
            print(
                f"[RISK] {symbol}: ChopBot slow SMA reclaim, buy order still open; "
                "entry_signal=False action_taken=wait_for_chop_exit_order"
            )
            return "wait_for_chop_exit_order"

        qty = self._position_qty(position).quantize(
            FRACTIONAL_QTY_STEP,
            rounding=ROUND_DOWN,
        )
        if qty <= 0:
            print(f"[RISK] {symbol}: ChopBot exit found no long position; action_taken=noop")
            return "noop"

        print(
            f"[TRADE] {symbol}: ChopBot slow SMA reclaim; "
            f"selling qty={format_decimal(qty)}."
        )
        self._record_lifecycle(
            LIFECYCLE_INTENDED_EXIT,
            bot=CHOP_BOT,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason="chop_reclaim_slow_sma",
            price=soxl_snapshot.price,
            slow_sma=soxl_snapshot.slow_sma,
        )
        try:
            order = self.client.submit_market_sell_qty(symbol, qty)
        except BotError as exc:
            self._record_lifecycle(
                LIFECYCLE_ORDER_REJECTED,
                bot=CHOP_BOT,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="chop_reclaim_slow_sma",
                error=str(exc),
                broker_constraint=self._broker_rejection_payload(exc, "sell", symbol),
            )
            raise
        self._record_lifecycle(
            LIFECYCLE_ORDER_SUBMITTED,
            bot=CHOP_BOT,
            symbol=symbol,
            side="sell",
            qty=qty,
            reason="chop_reclaim_slow_sma",
            price=soxl_snapshot.price,
            slow_sma=soxl_snapshot.slow_sma,
            order=order,
        )
        self.order_tracker.track_submitted_order(
            order,
            CHOP_BOT,
            "chop_reclaim_slow_sma",
        )
        self.state_store.clear_symbol(symbol)
        print("entry_signal=False action_taken=chop_exit_reclaim_slow_sma")
        return "chop_exit_reclaim_slow_sma"

    def _liquidate_all_before_close(
        self,
        positions: dict[str, dict[str, Any] | None],
        orders: list[dict[str, Any]],
        seconds_to_close: float | None,
    ) -> str:
        minutes_text = "unknown"
        if seconds_to_close is not None:
            minutes_text = f"{max(seconds_to_close, 0) / 60:.1f}"

        sold_any = False
        sell_pending = False
        for symbol in self.basket_symbols:
            position = positions.get(symbol)
            qty = self._position_qty(position)
            if qty <= 0:
                continue

            symbol_orders = [order for order in orders if order.get("symbol") == symbol]
            if any(order.get("side") == "sell" for order in symbol_orders):
                print(f"[RISK] {symbol}: closeout window active, sell order already open.")
                sell_pending = True
                continue
            if any(order.get("side") == "buy" for order in symbol_orders):
                print(f"[RISK] {symbol}: closeout window active, buy order still open.")
                sell_pending = True
                continue

            qty = qty.quantize(FRACTIONAL_QTY_STEP, rounding=ROUND_DOWN)
            print(
                f"[TRADE] {symbol}: market closes in {minutes_text} minutes; "
                f"selling all shares qty={format_decimal(qty)}."
            )
            owner = self.state_store.get_position_owner(symbol) or "UNKNOWN"
            self._record_lifecycle(
                LIFECYCLE_INTENDED_EXIT,
                bot=owner,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="market_close_liquidation",
                seconds_to_close=seconds_to_close,
            )
            try:
                order = self.client.submit_market_sell_qty(symbol, qty)
            except BotError as exc:
                self._record_lifecycle(
                    LIFECYCLE_ORDER_REJECTED,
                    bot=owner,
                    symbol=symbol,
                    side="sell",
                    qty=qty,
                    reason="market_close_liquidation",
                    error=str(exc),
                    broker_constraint=self._broker_rejection_payload(exc, "sell", symbol),
                )
                raise
            self._record_lifecycle(
                LIFECYCLE_ORDER_SUBMITTED,
                bot=owner,
                symbol=symbol,
                side="sell",
                qty=qty,
                reason="market_close_liquidation",
                seconds_to_close=seconds_to_close,
                order=order,
            )
            self.order_tracker.track_submitted_order(
                order,
                owner,
                "market_close_liquidation",
            )
            self.state_store.clear_symbol(symbol)
            sold_any = True

        if sold_any:
            print("entry_signal=False action_taken=market_close_liquidation")
            return "market_close_liquidation"
        elif sell_pending:
            print("entry_signal=False action_taken=wait_for_closeout_order")
            return "wait_for_closeout_order"
        else:
            print("entry_signal=False action_taken=closeout_window_no_position")
            return "closeout_window_no_position"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Alpaca trailing stop bot POC")
    parser.add_argument("--once", action="store_true", help="Run one polling cycle")
    parser.add_argument("--edgewalker", action="store_true", help="Run EdgeWalker router")
    parser.add_argument("--symbol", help="Override SYMBOL")
    parser.add_argument("--notional", type=Decimal, help="Override POSITION_NOTIONAL")
    parser.add_argument("--trail-percent", type=Decimal, help="Override TRAIL_PERCENT")
    parser.add_argument(
        "--close-liquidate-minutes",
        type=int,
        help="Override CLOSE_LIQUIDATE_MINUTES",
    )
    parser.add_argument(
        "--regime-gap-threshold",
        type=Decimal,
        help="Override REGIME_GAP_THRESHOLD",
    )
    parser.add_argument("--buy-qty", type=Decimal, help="Submit a manual market buy")
    parser.add_argument("--sell-qty", type=Decimal, help="Submit a manual market sell")
    run_mode = parser.add_mutually_exclusive_group()
    run_mode.add_argument("--dry-run", action="store_true", help="Do not place orders")
    run_mode.add_argument("--live", action="store_true", help="Place paper orders")
    return parser.parse_args()


def apply_arg_overrides(config: BotConfig, args: argparse.Namespace) -> BotConfig:
    updates: dict[str, Any] = {}
    if args.symbol:
        updates["symbol"] = args.symbol.strip().upper()
    if args.notional is not None:
        if args.notional <= 0:
            raise BotError("POSITION_NOTIONAL must be greater than 0")
        updates["position_notional"] = args.notional
    if args.trail_percent is not None:
        if args.trail_percent <= 0:
            raise BotError("TRAIL_PERCENT must be greater than 0")
        updates["trail_percent"] = args.trail_percent
    if args.close_liquidate_minutes is not None:
        if args.close_liquidate_minutes < 1:
            raise BotError("CLOSE_LIQUIDATE_MINUTES must be at least 1")
        updates["close_liquidate_minutes"] = args.close_liquidate_minutes
    if args.dry_run:
        updates["dry_run"] = True
    if args.live:
        updates["dry_run"] = False
    if args.regime_gap_threshold is not None:
        if args.regime_gap_threshold < 0:
            raise BotError("REGIME_GAP_THRESHOLD must be at least 0")
        updates["regime_gap_threshold"] = args.regime_gap_threshold

    if not updates:
        return config

    return BotConfig(**{**config.__dict__, **updates})


def main() -> int:
    load_dotenv(Path(".env"))
    args = parse_args()
    config = apply_arg_overrides(BotConfig.from_env(), args)
    client = AlpacaClient(config)
    bot = TrailingStopBot(config, client)

    if args.buy_qty and args.sell_qty:
        raise BotError("Use either --buy-qty or --sell-qty, not both")

    if args.buy_qty:
        result = bot.client.submit_market_buy_qty(config.symbol, args.buy_qty)
        if result:
            print(
                f"Submitted buy order id={result.get('id')} "
                f"symbol={result.get('symbol')} qty={result.get('qty')} "
                f"status={result.get('status')}"
            )
    elif args.sell_qty:
        result = bot.client.submit_market_sell_qty(config.symbol, args.sell_qty)
        if result:
            print(
                f"Submitted sell order id={result.get('id')} "
                f"symbol={result.get('symbol')} qty={result.get('qty')} "
                f"status={result.get('status')}"
            )
    elif args.once:
        if args.edgewalker:
            EdgeWalkerBot(config, client).run_once()
        else:
            bot.run_once()
    else:
        if args.edgewalker:
            print(
                f"Starting EdgeWalker. dry_run={config.dry_run}, "
                f"poll_seconds={config.poll_seconds}"
            )
            while True:
                EdgeWalkerBot(config, client).run_once()
                time.sleep(config.poll_seconds)
        else:
            bot.run_forever()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
        raise SystemExit(130)
    except BotError as exc:
        print(f"[fatal] {exc}", file=sys.stderr)
        raise SystemExit(1)
