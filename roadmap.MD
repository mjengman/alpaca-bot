# EdgeWalker Roadmap

Last updated: 2026-05-30

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
- Never let stale interpretation masquerade as fresh conviction.
- Never make regular-session strategy behavior depend on accidental premarket
  warmup context.
- Never auto-send logs, credentials, or trading records to an outside service
  without explicit user action.

## Current Baseline

These are implemented in the current app and should be treated as the
foundation for future work.

- Activity log copy button
- Directional mode system: Conservative, Balanced, Aggressive, Adaptive
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
  explicit live-trading arming, and live-trading disarming
- Adaptive posture selector v1 with active mode support, shadow-mode support,
  status exposure, explainable reasons/constraints, and lifecycle posture events
- Qualification-hardening pass for paper/live connection tests, non-overlapping
  dashboard polling, and lower-noise stream bar persistence
- Initial same-symbol open-buy sell guard to avoid broker-rejected
  opposite-side exits while an entry order is still resolving

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

### Runtime State Summary

Goal: make the bot's current operating state explicit, inspectable, and
eventually replayable without forcing all runtime conditions into one brittle
enum.

EdgeWalker already has several state models emerging across app lifecycle,
market/data state, position lifecycle, broker constraints, and live-readiness.
These should gradually converge into a read-only runtime state summary before
any major state-machine refactor.

Model runtime state as:

- Primary state: what the system is mainly doing
- Guards/flags: conditions that allow, block, or modify action
- Interrupts: urgent abnormal states that require operator attention

Initial primary states may include:

- DISARMED
- ARMED
- WAITING_FOR_MARKET
- ENTRY_READY
- ENTRY_PENDING
- POSITION_OPEN
- EXIT_PENDING
- COOLDOWN
- CLOSEOUT
- STOPPED

Initial guards may include:

- Bars stale
- Stream disconnected
- Market closed
- Buying power limited
- Live trading blocked
- Entry blocked
- Exit blocked

Initial interrupts may include:

- BROKER_RESTRICTED
- STALE_DATA
- FATAL_ERROR

Notes:

- Begin as a derived summary, not a giant refactor.
- Some runtime conditions are not mutually exclusive; for example, a position
  can be open while bars are stale.
- Stale data should be a guard when entries are blocked but live risk
  management can continue; it should become an interrupt only when essential
  management data is unavailable.
- The summary should eventually support dashboard display, replay, metrics,
  live guardrails, multi-symbol routing, and arena work.

### Market Data Interpretation Integrity

Goal: make the difference between live market state and market interpretation
explicit. Quotes and trades may be live while one-minute bars are stale; in
that state, price/risk visibility exists but regime interpretation is degraded.

Name this state clearly:

- Live market, stale interpretation

Key behaviors:

- Block fresh entries while bar-based interpretation is stale.
- Continue open-position risk management from live quote/trade marks when those
  marks are fresh.
- Distinguish stream disconnects from bar aggregation lag.
- Attempt bounded recent-bar repair/backfill when quote/trade data is live but
  bars are stale.
- Record whether backfill repaired the stream cache, partially repaired it, or
  failed.

Regular-session warmup integrity:

- Decide explicitly whether regular-session trading includes premarket bars in
  warmup.
- If not, filter warmup bars to regular-session time before producing the first
  actionable regime.
- If premarket context is useful, expose it separately instead of silently
  mixing it into the regular-session SMA context.

Notes:

- A bot pre-armed before open can have same-day premarket bars cached at
  `09:30 ET`. That is a partially formed opinion, not a clean regular-session
  blank slate.
- This is an observability and doctrine issue before it is a strategy issue.

### Foundational Replay / Timeline Reconstruction

Goal: reconstruct what happened during a session from lifecycle events,
decision logs, broker events, and market/data state without relying on fragile
UI state or loose log interpretation.

This is not backtesting or strategy optimization. Foundational replay is an
operational truth feature: show the session as it unfolded, explain what state
the system believed it was in, and make debugging and postmortems trustworthy.

Initial scope:

- Reconstruct session timeline from lifecycle JSONL and daily decision logs
- Show position lifecycle events in chronological order
- Reconstruct primary runtime state, guards, and interrupts over time
- Show when entries were approved, blocked, submitted, rejected, filled, or
  skipped
- Show when exits were submitted, rejected, filled, or blocked
- Show realized-result events once persisted
- Support operator-facing postmortems after unusual sessions

Initial UX direction:

- Add a third log panel tab: Activity | Narrative | Timeline
- Treat Timeline as a structured forensic view, not a simulator
- Provide date/timeframe selection, bot filters, event filters, and a "show
  important only" toggle
- Render chronological cycle groups with regime, primary state, guards,
  decision rationale, sizing, order events, broker outcomes, and P/L moments
- Render open-position segments that summarize entry, management, exit, and
  realized result
- Add a compact session rail or mini-map later for regime changes, stale-data
  spans, broker errors, open-position spans, and closeout windows

Notes:

- Replay is for truth first, optimization later.
- Begin as deterministic timeline reconstruction, not alternate-parameter
  simulation.
- Activity remains the raw operational stream.
- Narrative remains the AI/operator debrief.
- Timeline becomes the structured flight recorder for "what happened, in what
  order, and what did EdgeWalker believe at the time?"
- Advanced simulation, backtesting, arena evaluation, and mutation testing
  should remain future architecture until clean replay primitives exist.

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

### Audioscape

Goal: add a calm situational-awareness layer that makes EdgeWalker feel alive,
trustworthy, and operator-facing without turning the app into a casino or a
game.

Core principle:

The audioscape should quietly answer three questions:

1. Is the system alive?
2. Did something materially change?
3. Do I need to care right now?

Design identity:

- Calm cockpit, not dopamine casino
- Machine dignity: disciplined, procedural, restrained
- Textural, tactile, semi-mechanical, and cinematic-realistic
- More submarine, spacecraft, aviation cockpit, industrial control room, or
  high-end lab equipment than synthwave, game UI, or phone notifications
- Silence is part of the design; long stable stretches should feel calm, not
  dead

Initial implementation posture:

- Optional app preference in the settings menu
- Disabled by default until the cue set feels useful
- Start mostly event-driven, then consider an optional ambient layer later
- Critical operational cues should eventually be able to remain audible even if
  ambience is disabled
- Avoid strategy or trading-logic changes while adding audio

Tier 1: Operationally critical state transitions

- Bot started
- Bot stopped
- Order submitted
- Order filled
- Order rejected
- Error / disconnect
- Live trading armed
- Human intervention required

Notes:

- These sounds create trust by confirming important state transitions.
- Live trading armed should be unmistakable, deeper, slower, restrained, and
  procedural. It marks the transition from simulation to consequence.
- Human intervention required should be separate from generic errors for states
  like insufficient buying power, conflicting position state, API desync,
  authentication expiry, broker approval requirements, or blocked exits. It
  should interrupt ambience, recur gently until acknowledged, and stop when the
  operator has handled it.

Tier 2: Ambient awareness

- UI taps and menu interactions
- Audioscape enabled / disabled
- Optional low-level idle ambience while the bot is online
- Optional poll-cycle tick or soft heartbeat

Notes:

- These should nearly disappear from conscious awareness after long use.
- If the operator notices them constantly, they are too loud or too frequent.
- Poll-cycle ticks should be used carefully, especially at short polling
  intervals.

Tier 3: Strategic intelligence

- Regime changed
- Active bot shifted
- Trailing exit updated
- Trailing exit crossed entry price
- Position closed

Notes:

- Regime audio could become a signature EdgeWalker feature: uptrend, sideways,
  and downtrend should become subconsciously recognizable without implying that
  one is inherently "good" or "bad."
- Uptrend may use airy upward motion; sideways may use dry, stable, percussive
  texture; downtrend may use denser, lower, slower motion.
- Active bot shifts should use subtle identity motifs for MomentumBot, ChopBot,
  and InverseBot, with timbre doing more work than melody.
- Trailing exit updated should feel like a tiny mechanical ratchet or lock-in
  tick: progress, protection, and tightening control without celebrating money.
- Trailing exit crossed entry should be a once-per-position cue that the
  position has entered a more protected state. It should be calm and procedural,
  not celebratory.

Future sound profiles:

- Silent
- Minimal
- Tactical
- Cinematic
- Streamer Mode

### Operator Guide

Goal: provide a lightweight in-app reference for people who did not build the
system.

- Header info button
- Modal reference layer, not a separate manual
- Explain bot roles, core controls, status metrics, narrative summaries, and
  safety notes
- Keep copy concise and operator-facing
- Expand later with diagrams or contextual links if the UI grows more complex

### Position Risk Display

Goal: make the open-position risk picture legible at a glance.

- Split the current Trail exit block into a compact comparison:
  - Entry price
  - Trail exit
- Visually indicate when trail exit is at or above entry price.
- Keep the display stable when an exit order is pending.
- Preserve the current Position P/L readout as account/position mark context,
  not as a substitute for risk-state clarity.

### Icon Polish

Goal: keep high-frequency controls visually quiet and cohesive.

- Replace the Activity/Narrative `Copy` text button with a copy icon.
- Preserve accessible label text and hover tooltip.
- Preserve state feedback for copied, empty, or failed copy attempts through a
  tooltip, temporary icon state, or small toast.

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
- Live-market/stale-interpretation frequency
- Stale-bar repair/backfill attempts and outcomes
- Broker rejection counts
- Average data latency
- Trade execution timing
- Order acceptance latency
- Time spent armed, active, closeout, and flat

### Trend Trust Telemetry

Goal: measure whether a trend deserves trust, not only whether a trend exists.

Initial components:

- Strength: fast/slow SMA gap and regime strength bucket
- Age: how long the current regime has persisted
- Stability: regime flips over the last 15, 30, and 60 minutes
- Persistence: post-signal follow-through over 5, 15, and 30 minutes
- Efficiency: net directional movement divided by total movement
- Excursion: max favorable and max adverse excursion after entry

Notes:

- A strong one-minute-old regime should not be treated the same as a strong
  thirty-minute-old regime.
- Adaptive should eventually distinguish strong-but-immature signals from
  moderate-but-stable signals.
- Begin as telemetry and narrative context before feeding it into active
  decision logic.

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

### Adaptive Posture Selector

Goal: let EdgeWalker choose its current directional posture from observable
runtime conditions instead of relying only on a globally fixed aggression mode.

Adaptive should be a transparent selector/modulator that consumes operational
truth. It should answer: what posture has the system earned right now?

Adaptive v1 should choose among existing directional modes:

- Conservative
- Balanced
- Aggressive

Adaptive v1 should not change capital allocation, leverage, or hidden sizing
math. Keep behavioral adaptation separate from capital amplification until the
posture logic has earned trust through logs, replay, and operator review.

Potential input signals:

- Trend strength
- Trend Trust telemetry
- Regime age
- Regime stability and recent regime churn
- Data freshness and stream health
- Broker state and recent order rejections
- Session drawdown or realized P/L pressure
- Time until closeout
- Current runtime guards and interrupts

Operator-facing readout:

- Adaptive Posture
- Confidence
- Reasons
- Active constraints
- Recent posture shifts

Notes:

- Adaptive is a posture selector, not a new strategy.
- Adaptive should answer not only "what posture fits?" but "how much should I
  believe what I am seeing?"
- Adaptive decisions should become first-class timeline/decision events.
- Every posture selection or posture shift should be explainable and replayable.
- Operator-defined envelopes should bound all adaptive behavior.
- Sizing modulation may be a future version, but should not be part of v1.
- Dependencies: Runtime State Summary, Broker Constraint State, Data Health,
  Explainability Layer, Telemetry, and Foundational Replay.

### Dynamic Controls

Future optional companion to Adaptive. Not enabled by default.

Goal: let EdgeWalker adjust selected operating controls inside
operator-approved rails when environmental conditions call for a tighter or
looser runtime envelope.

Adaptive answers:

- What doctrine fits this environment?

Dynamic Controls answers:

- How tightly should the system operate right now?

Initial doctrine:

- Manual settings define the envelope.
- Dynamic Controls may move only within explicit min/max rails.
- Safety doctrine remains hardcoded and cannot be weakened dynamically.
- Shadow mode comes first, using `would_set` recommendations before any active
  runtime changes.
- The first active version should control one or two low-risk knobs only.

Early candidate controls:

- Poll cadence while flat, opening, open, closing, or near closeout.
- Trail sensitivity or trail ratchet behavior.
- Cooldown duration after churn, route invalidation, or reversal clusters.
- Position sizing cap inside the existing allocation and live-risk envelope.

Higher-risk controls that require stronger evidence:

- Continuation-entry strictness.
- Strong-trend chase allowance.
- ChopBot discount threshold.
- Regime threshold or hysteresis behavior.

Operator-facing readout:

- Dynamic Controls status: Off, Shadow, or Active.
- Current recommended values and active values.
- Reasons, confidence, and constraints.
- Operator rail ranges for each dynamic value.

Notes:

- This is bounded runtime adaptation, not autonomous optimization.
- `POLL_SEC` may be especially important as an exit-precision and perception
  setting, but faster polling should be tested for noise sensitivity before
  active use.
- Dynamic recommendations should become first-class events so debriefs can
  compare manual behavior against the suggested dynamic envelope.

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
- Lab / tuning console for parameter experiments
- Advanced simulation and backtesting engine
- Alternate-parameter replay
- Arena season evaluation
- Mutation testing / strategy fitness replay
- Multi-position support
- Multi-symbol routing
- Arena / competing bots
- Strategy lineage tracking
- Mobile dashboard / remote monitoring
- Autonomous overnight reporting
- AI-generated strategy tuning suggestions

Notes:

- AI-generated tuning should be advisory only until foundational replay and
  clean simulation primitives exist.
- Arena work depends on clean lifecycle and metrics primitives.
- Multi-symbol support depends on broker-state and allocation controls.

## Suggested Next Sprint

During the eight paper-trading qualification days before planned go-live, limit
code changes to fire-fixes and low-risk observability/documentation updates.
The goal is to collect clean behavior data across Conservative, Balanced,
Aggressive, and Adaptive qualification days without moving the target every
session.

Qualification protocol:

- Day 1: Conservative
- Day 2: Balanced
- Day 3: Aggressive
- Day 4: Adaptive
- Day 5: Conservative
- Day 6: Balanced
- Day 7: Aggressive
- Day 8: Adaptive

Operating rules:

1. Fire-fix only during market sessions.
2. Keep non-critical strategy and UI changes parked until after the daily
   session review.
3. Capture daily logs, lifecycle files, screenshots, and operator notes.
4. After enough clean logs exist, add realized trade detail/history from
   lifecycle fill records.
5. Persist realized-result lifecycle records per closed trade.
6. Add average hold duration and best/worst trade metrics.
7. Start Foundational Replay / Timeline Reconstruction once the event stream is
   representative enough to design against.
8. Add Trend Trust telemetry before changing Adaptive's posture rules.

## Weekend Sprint Before Qualification Round 2

Objective: improve operational truth and operator confidence before the second
qualification rotation. Do not retune strategy behavior in this sprint.

Guiding rule:

```text
Improve truth and operator confidence.
Do not retune strategy behavior.
```

### P0: Before Qualification Round 2

1. Regular-session warmup integrity
   - Ensure regular-session trading does not accidentally use premarket bars
     for the first actionable SMA context.
   - Decide what market world EdgeWalker is modeling at the open.

2. Stale-bar repair / backfill
   - If quotes/trades are live but bars are stale, attempt bounded recent-bar
     REST backfill.
   - Keep entries blocked until bar freshness is restored.

3. Opening/open/closing/closed lifecycle visibility
   - Make position/order lifecycle state visible enough that live-money
     operation feels sane, especially while orders are pending or partially
     filled.

4. Broker rejection classification cleanup
   - Add distinct classification for opposite-side or wash-trade conflicts
     instead of mislabeling them as buying-power issues.

5. P/L reconciliation confidence
   - Tighten or expose lifecycle P/L versus fill-paired P/L versus account
     movement so discrepancies are explainable.

### P1: Highest-Value Telemetry

6. Trend Trust telemetry, shadow-only
   - Log regime age, recent flip counts, regime hold time, and post-entry
     MFE/MAE where feasible.
   - Do not feed these metrics into decisions yet.

7. Route invalidation exit labeling
   - Keep the internal code compatible.
   - Surface the human label `route_invalidation_exit` in logs, narrative, or
     UI where practical.

8. Route invalidation outcome scaffolding
   - Start storing enough context to later classify defensive save, premature
     cut, neutral exit, and profitable handoff.

9. Session metrics summary
   - Summarize stale-bar count, max bar age, regime transitions, average regime
     age, short-lived regime count, and trade count by bot/mode.

### P2: UI / Operator Polish

10. Entry price + Trail exit comparison
    - Show entry price and trail exit together so risk state is easier to scan.

11. Protected-position state
    - Show when trail exit is at or above entry price.
    - This should feel like "risk improved," not a profit celebration.

12. Audio cue for trail at or above entry
    - Trigger once per position.
    - Keep it subtle and procedural.

13. Copy icon
    - Replace the `Copy` text button with a copy icon while preserving
      tooltip and state feedback.

### P3: Parked Until After More Evidence

14. Dynamic Controls shadow
    - Documented and promising, but not required before Thursday unless higher
      priorities are already clean.

15. Adaptive logic changes
    - Do not feed Trend Trust into active decisions yet.

16. Strategy threshold changes
    - Do not change regime thresholds, trail percent, ChopBot discount,
      cooldown, or mode rules in this sprint.
