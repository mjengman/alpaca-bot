# EdgeWalker Roadmap

Last updated: 2026-05-23

EdgeWalker is becoming a proper operator-facing trading app. This roadmap keeps
the backlog ordered around one principle: make the system safer, clearer, and
more inspectable before adding more aggression.

## Operating Doctrine

- Slow is smooth. Smooth is fast.
- Patience is a feature.
- Safety layers are hardcoded.
- Aggression is configurable.
- The system should always explain itself.
- Observability is a core feature, not a debugging afterthought.

## Current Baseline

These are implemented in the current app and should be treated as the
foundation for future work.

- Activity log copy button
- Directional mode system: Conservative, Balanced, Aggressive
- Dynamic allocation sizing
- Full Deployment mode using about 95% of buying power
- Position sizing safety clamp at 95% of current buying power
- Regime hysteresis with entry and exit thresholds
- Auto-arm and market-hours lifecycle
- Streaming data architecture
- Stale-bar entry protection
- Open-position live risk management during stale-bar conditions
- Structured decision logs and daily JSONL records

## Priority 0: Operational Truth

This is the next main phase. The app should make financial state and operational
constraints impossible to miss.

### P/L Visibility

Goal: make realized and unrealized performance painfully obvious.

- Session realized P/L
- Realized P/L per closed trade
- Unrealized P/L for the open position
- Color-coded gain and loss indicators
- Last trade result
- Cumulative bot-level performance
- Bot-by-bot P/L breakdown

Notes:

- Realized P/L should come from fills/trade lifecycle records, not inferred only
  from account-level equity changes.
- UI should separate account-level daily P/L from strategy/session P/L.

### Broker Constraint State

Goal: broker failures should be first-class operational state, not just log text.

- Broker state pill:
  - OK
  - Restricted
  - Exit Blocked
  - Buying Power Limited
  - Order Pending
- Classify order rejections:
  - PDT
  - Insufficient buying power
  - Market closed
  - Duplicate order
  - Notional too large
  - Asset not tradable/fractionable
  - Generic broker rejection
- Failed exits should become high-priority state.
- Repeated rejected entries should cool down until account or broker state changes.

### Position Lifecycle Ledger

Goal: define one canonical lifecycle model that every metric and UI surface can
trust.

- Intended entry
- Order submitted
- Order accepted/rejected
- Partial fill
- Full fill
- Position opened
- Position managed
- Exit submitted
- Exit accepted/rejected
- Position closed
- Realized result calculated

Notes:

- This is a prerequisite for trustworthy P/L, metrics, trade journal export,
  scale-in mode, replay, and arena work.

### Effective Notional Visibility

Goal: make sizing behavior obvious before an order is submitted.

- Show configured notional or allocation mode
- Show current effective notional
- Show buying power clamp
- Show why a proposed entry size changed
- Log sizing decisions as structured events

## Priority 1: Operator Experience

These make the app easier to operate once financial state and broker state are
clear.

### Richer Log Styling

- Stronger event color identity
- Clearer visual hierarchy
- Grouped cycle/event blocks
- Prominent realized profit/loss moments
- Clear distinction between:
  - Entry blocked
  - Risk managed
  - Broker rejected
  - Position opened
  - Position closed

### Audio Cues

Optional toggle. Disabled by default until the cue set feels useful.

- Position opened
- Position closed
- Regime change
- Broker rejection
- Trailing stop hit
- Exit blocked

### Narrative Panel

Goal: turn logs into readable operating summaries without replacing raw logs.

- Activity / Narrative tabs
- Timeframe selectors:
  - 1D
  - 1W
  - 1M
  - 3M
  - YTD
  - MAX
- MVP:
  - User-triggered log summary request
  - Structured prompt over selected logs
  - Render returned narrative in-app
- Later:
  - Archived debrief history
  - Notable event extraction
  - Autonomous daily battle report

Notes:

- Do not auto-send logs anywhere without explicit user action.
- Redact secrets and avoid including API credentials.

## Priority 2: Metrics And Telemetry

Metrics should be built from the lifecycle ledger, not from loose log scraping.

### Bot Metrics

- Active duration
- Trade count
- Realized P/L
- Unrealized P/L
- Average hold duration
- Win/loss rate
- Best trade
- Worst trade
- Regime participation breakdown
- Bot-level performance by MomentumBot, ChopBot, and InverseBot

### System Health Telemetry

- Stream uptime
- Stale-bar frequency
- Broker rejection counts
- Average data latency
- Trade execution timing
- Order acceptance latency
- Time spent armed, active, closeout, and flat

## Priority 3: Strategy Evolution

Strategy complexity should wait until operational truth is solid.

### Position Lifecycle Rules

Current doctrine:

- Single-entry
- Manage until flat
- No same-cycle reversal after forced close
- Cooldown after directional entries

Open questions:

- Should cooldown apply after all exits or only directional entries?
- Should stale-regime exits remain paused when bars are stale, even if quotes are
  live?
- Should closeout behavior create a distinct terminal session state?

### Scale-In Mode

Future optional feature. Not enabled by default.

Requirements before implementation:

- Position lifecycle ledger
- Realized and unrealized P/L visibility
- Broker constraint state
- Max total allocation control

Rules to define:

- Max adds per position
- Max total allocation percent
- Unrealized gain threshold before adding
- Cooldown between adds
- No adding below fast SMA
- No adding during stale-bar conditions

### Regime Memory Tuning

Basic hysteresis exists. Future controls may include:

- Directional memory duration
- Regime confirmation count
- Separate uptrend and downtrend thresholds
- Volatility-adjusted thresholds

## Future Architecture

These are important, but should follow the operational truth phase.

- Persistent database layer
- Trade journal export
- Replay and simulation engine
- Multi-position support
- Multi-symbol routing
- Arena / competing bots
- Strategy lineage tracking
- Mobile dashboard / remote monitoring
- Autonomous overnight reporting
- AI-generated strategy tuning suggestions

Notes:

- AI-generated tuning should be advisory only until replay/simulation exists.
- Arena work depends on clean lifecycle and metrics primitives.
- Multi-symbol support depends on broker-state and allocation controls.

## Suggested Next Sprint

1. Build the position lifecycle ledger.
2. Add realized and unrealized P/L cards to the UI.
3. Add broker constraint state and rejection classification.
4. Expose effective notional and buying-power clamp in the UI.
5. Improve log styling around trade open, trade close, P/L, and rejection events.
