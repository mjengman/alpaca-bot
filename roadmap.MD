# EdgeWalker Roadmap

Last updated: 2026-05-24

EdgeWalker is becoming a proper operator-facing trading app. This roadmap keeps
the backlog ordered around one principle: make the system safer, clearer, and
more inspectable so it can grow into more aggression with confidence.

## Operating Doctrine

- Slow is smooth. Smooth is fast.
- Patience is a feature.
- Safety layers are hardcoded.
- Aggression is configurable.
- The system should always explain itself.
- Observability is a core feature, not a debugging afterthought.

## Project Spirit

EdgeWalker should remain fun, hopeful, and ambitious. Safety work should not
bury the project under procedural weight or make the UI feel timid. The point of
operational truth is to give the bot room to grow without fooling the operator.

Profitability is not assumed, but it is absolutely an aspiration. The product
should keep room for the excitement that this could become a genuinely
profitable autonomous trading runtime.

Practical implications:

- Safety should feel like confidence, not bureaucracy.
- The UI should feel alive, legible, and optimistic.
- Strategy evolution should stay exciting, but earn its freedom.
- Metrics should clarify opportunity, not only catalog risk.
- Operator experience should preserve the feeling that this is a powerful system
  becoming more capable over time.

## Safety Invariants

These should stay true as the app evolves.

- Never enter when required market data for that decision path is stale.
- Never manage exits from stale bars alone when live quote/trade data is
  unavailable.
- Never exceed the configured allocation clamp or safe buying-power threshold.
- Never reverse in the same cycle after a forced stale-position close.
- Never continue entering during stale-bar entry-block conditions.
- Never hide a broker-rejected exit behind ordinary log noise.
- Never orphan a position lifecycle state.
- Never auto-send logs, credentials, or trading records to an outside service
  without explicit user action.

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
- Position lifecycle JSONL foundation for entry/exit intent, order
  submission/rejection, broker acceptance/fill reconciliation,
  position opened/closed transitions, and trailing-risk management events
- Broker constraint classifier and dashboard state for rejected orders
- Lifecycle-derived session realized P/L summary and closed-trade count in the
  dashboard
- Bot-level realized P/L, trade count, wins/losses, and last trade result in
  the dashboard
- Daily cycle JSONL performance snapshots with session P/L, bot-level
  performance, pending-order counts, and order-flow state
- Pending-order and recent order/fill lifecycle visibility in the dashboard
- Operator Guide modal for in-app usage reference
- Settings modal foundation for paper/live broker credentials, connection tests,
  and explicit live-trading arming

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

- Foundation implemented: session realized P/L, closed-trade count, and
  bot-level realized performance are calculated from lifecycle fill records and
  shown in the dashboard.
- Foundation implemented: cycle logs now persist the same lifecycle-derived
  performance snapshot for post-session metric analysis and tuning.
- Remaining P/L work should add realized P/L per closed trade, richer history,
  and exportable journal records.
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

Notes:

- Foundation implemented: rejected orders are classified into broker constraint
  state and exposed in the API/dashboard.
- Remaining broker-state work should persist restrictions across restarts,
  classify pending orders directly from open-order state, and add rejection
  cooldown behavior.

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

- Foundation implemented: intent events, submitted/rejected order events,
  position-managed trailing-risk events, broker acceptance/fill reconciliation,
  and position opened/closed transitions are written to
  `logs/position_lifecycle.jsonl`.
- This is a prerequisite for trustworthy P/L, metrics, trade journal export,
  scale-in mode, replay, and arena work.
- Remaining lifecycle work should persist realized-result records per closed
  trade instead of deriving them only as a dashboard read model.
- Foundation implemented: pending orders and recent same-session order/fill
  lifecycle events are exposed as dashboard order flow.

### Effective Notional Visibility

Goal: make sizing behavior obvious before an order is submitted.

- Show configured notional or allocation mode
- Show current effective notional
- Show buying power clamp
- Show why a proposed entry size changed
- Log sizing decisions as structured events

### Explainability Layer

Goal: make the system's reasoning available as a first-class product surface,
not only as raw logs.

- Explain why an entry was approved or blocked
- Explain why a route changed
- Explain why a stop moved
- Explain why allocation changed
- Explain why cooldown is active
- Explain why stale data is blocking entries but not open-position risk
- Preserve concise machine-readable reason codes alongside human-readable text

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

### Operator Guide

Goal: provide a lightweight in-app reference for people who did not build the
system.

- Header info button
- Modal reference layer, not a separate manual
- Explain bot roles, core controls, status metrics, narrative summaries, and
  safety notes
- Keep copy concise and operator-facing
- Expand later with diagrams or contextual links if the UI grows more complex

### Live Trading Readiness

Goal: make real-money readiness explicit and guarded before the June 4, 2026
go-live milestone.

- Configure paper and live Alpaca credentials without hand-editing `.env`
- Test broker connection for each environment
- Show active environment clearly
- Keep dry run and paper operation as the default path
- Require explicit typed confirmation before live trading can be armed
- Require live credentials before live trading can be armed
- Provide a visible disarm control for live trading
- Block live real-order submission unless the app is armed
- Add future hard live guardrails:
  - Max live order notional
  - Max daily realized loss halt
  - Max open exposure
  - Closeout required before live start
  - Session-level kill switch

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
  - Include a cautious Analysis section with operator-facing tuning ideas
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
  - Foundation implemented for realized P/L, trade count, wins/losses, win
    rate, last trade result, and daily cycle-log snapshots.

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

### Strategy Lab / Tuning Console

Future optional workspace for turning debrief analysis into experiments, not
automatic production changes.

- Compare candidate parameter sets against replay/simulation results
- Track AI-generated tuning ideas as advisory hypotheses
- Link recommendations to supporting evidence from logs and lifecycle metrics
- Mark ideas as watch, test, accepted, rejected, or deferred
- Keep production parameter changes explicit and operator-approved

## Future Architecture

These are important, but should follow the operational truth phase.

- Persistent database layer
- Trade journal export
- Replay and simulation engine
- Session replay and timeline scrubbing
- Lab / tuning console for parameter experiments
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

1. Add realized trade detail/history from lifecycle fill records.
2. Persist realized-result lifecycle records per closed trade.
3. Add rejection cooldown behavior for repeated broker failures.
4. Add average hold duration and best/worst trade metrics.
5. Improve log styling around trade open, trade close, P/L, and rejection events.
