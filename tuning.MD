# EdgeWalker Tuning Log

Last updated: 2026-05-28

Go-live target: 2026-06-04

This file turns after-action reviews into practical tuning candidates. The goal
is not to optimize from one day of evidence. The goal is to preserve behavioral
coherence, improve transparency, and identify the highest-value upgrades to
consider before live trading.

## Operating Bias

- Trust before aggression.
- Interpretability before cleverness.
- Policy should be explicit, logged, and testable.
- Doing nothing is valid behavior when conditions are poor.
- One session can reveal instrumentation gaps, but it should not overrule the
  strategy by itself.
- Tuning ideas should move through watch, instrument, test, accept, or reject.

## Evidence Strength

Use evidence strength to keep tuning decisions proportional to the proof behind
them.

Weak evidence:

- Single-session observation
- Low trade count
- One unusual market day
- Anecdotal operator impression
- Unstructured log pattern without supporting metrics

Moderate evidence:

- Repeated pattern across several sessions
- Pattern appears in structured events or session telemetry
- Behavior shows up across more than one regime type
- Paper-trading results and narrative debriefs agree on the issue

Strong evidence:

- Consistent behavior across many sessions and market conditions
- Replay or structured timeline confirms the causal chain
- Lifecycle ledger, telemetry, and narrative all support the same conclusion
- Proposed change has clear acceptance criteria and bounded risk

Decision standard:

- Weak evidence can justify watching or instrumenting.
- Moderate evidence can justify controlled tests or configuration changes.
- Strong evidence can justify doctrine changes or live-risk-envelope updates.

## Qualification Mode Rotation

Purpose: sample each directional posture across different market contexts before
go-live instead of clustering the same mode across adjacent, autocorrelated
market days.

Planned sequence:

- Day 1: Conservative
- Day 2: Balanced
- Day 3: Aggressive
- Day 4: Adaptive
- Day 5: Conservative
- Day 6: Balanced
- Day 7: Aggressive
- Day 8: Adaptive

Rationale:

- Consecutive market days can share volatility, sentiment, overnight
  positioning, sector momentum, and macro narrative.
- Rotating modes creates more diverse evidence than running each mode in
  back-to-back blocks.
- The comparison should evaluate behavioral stability, doctrine adherence, and
  environmental fit before P/L.
- Adaptive shadow observations become more useful when compared against varied
  manual postures across varied regimes.

Evaluation questions:

- Did the active mode create entries another mode would have blocked?
- Were those entries explainable and within doctrine?
- Did stale-data, closeout, broker, and stale-exposure policies remain dominant
  when needed?
- Did trade count, churn sensitivity, and exit quality remain acceptable?
- Did the daily narrative correctly distinguish opportunity, authorization, and
  intentional non-participation?

## 2026-05-26 After-Action Review

Session: first full paper-trading day

Cycles: 380

Result: one ChopBot SOXL trade, closed for a small profit. Account value moved
from about $99,833.86 to $99,889.79, roughly +$55.93.

Session identity:

- Regime-churn day with alternating directional and sideways classifications.
- Early strong SOXL uptrend, mid-session pullback and chop, late-session upward
  drift.
- Directional opportunities existed, but Conservative mode required fresh
  crosses and therefore blocked established-trend entries.

What worked:

- Market-open warmup behaved cleanly.
- The system armed before open, operated through the session, entered closeout
  behavior, stopped after close, and rearmed for the next market day.
- Stale-bar entry protection repeatedly blocked new entries while quotes/trades
  were live.
- Stale-exposure doctrine closed the ChopBot SOXL position when the active
  regime flipped to DOWNTREND.
- No same-cycle reversal occurred after the forced stale-position close.
- Adaptive posture shadow logs were coherent and easy to read.
- The narrative correctly identified regime churn and limited opportunity.

What needs attention:

- Repeated 90-120 second stale-bar pauses occurred despite live quote/trade
  data.
- Regime routing changed frequently near the threshold boundaries.
- Daily narrative should distinguish "no trend existed" from "trend existed but
  entry doctrine blocked continuation entries."
- Directional fresh-cross-only behavior may be too restrictive after warmup, but
  this should be studied before changing.
- The system needs a first-class event vocabulary so after-action reviews are
  built from structured facts instead of loose log interpretation.

## 2026-05-28 After-Action Review

Session: qualification day 3, Aggressive mode

Cycles: 386

Result: 20 completed trades. Account value moved from about $99,121.35 to
$99,408.60, roughly +$287.25. Lifecycle summary reported +$297.86, which should
be reconciled against fill-paired/account movement.

Session identity:

- Directional participation day with persistent regime churn.
- SOXL ranged from about $219.87 at first actionable cycle, down to $207.59,
  up to $231.60, and closed the session near $224.91.
- Regime transitions remained high at 38, but the tape rewarded directional
  persistence more than Balanced day did.
- Aggressive mode acted more continuation-friendly than reckless; it approved
  many continuation entries while still blocking weak or sideways setups.

Bot behavior:

- MomentumBot was the primary winner, with 11 trades and strong positive P/L.
- InverseBot struggled, with 8 trades and negative P/L.
- ChopBot was mostly irrelevant, with one small losing trade.
- Only one entry used `strong_trend_chase_allowed`; most approved directional
  entries were ordinary `trend_continuation_allowed`.

What worked:

- Aggressive increased participation without obviously collapsing discipline.
- The bot spent more time managing open positions than entering new ones.
- Stale-data, closeout, sizing, and route-invalidation policies remained active.
- MomentumBot captured a major persistence window that Conservative would have
  avoided and Balanced may have handled differently.
- The comparison with Balanced day suggests churn count alone is not enough to
  explain tradeability.

What needs attention:

- Two exit attempts were rejected during a partial-fill opening state because
  Alpaca detected an opposite-side/wash-trade conflict.
- Broker rejection classification labeled those rejections as insufficient
  buying power, which was misleading.
- P/L reconciliation differed by about $10 between lifecycle summary and
  account/fill-paired movement.
- `stale_position_regime_mismatch` is behaviorally useful but semantically
  muddy; future naming should distinguish route invalidation from stale data.
- Regime-mismatch exits need outcome classification before the doctrine can be
  judged.

Behavioral assessment:

Aggressive mode expanded participation and captured directional persistence
without behaving like a churn-seeking mode. The session increased confidence in
the continuation-entry architecture, but the most actionable findings were
execution and telemetry issues rather than strategy-threshold defects.

Evidence strength:

- Strong evidence for preserving the open-buy sell guard and improving
  opening/closing lifecycle visibility before live trading.
- Strong evidence for improving broker rejection classification.
- Moderate evidence that directional persistence quality matters more than
  transition count alone.
- Moderate evidence that regime-mismatch exits need richer outcome telemetry.
- Weak evidence for changing directional thresholds, cooldowns, stops, or
  InverseBot filters.

Adaptive note:

Adaptive shadow mostly displayed Balanced posture, but most of those cycles
were `adaptive_entry_posture_paused` while a position was already open. This
should not be read as a simple rejection of Aggressive mode. Adaptive day should
be judged on doctrine selection quality: whether it avoids churn traps,
participates when persistence emerges, and makes confidence changes that remain
explainable in hindsight.

## P0 Candidates Before Go-Live

### 1. Add First-Class Event Classification

Status: strongly consider

Impact: high

Why:

The logs already contain meaningful behavior, but the meaning is embedded in
text. Event classification would make decision history, narrative summaries,
health metrics, and future timeline work more trustworthy.

Candidate event types:

- `SESSION_STARTED`
- `SESSION_STOPPED`
- `MARKET_ARMED`
- `MARKET_OPENED`
- `MARKET_CLOSED`
- `WARMUP_STARTED`
- `WARMUP_COMPLETED`
- `DATA_HEALTH_CHANGED`
- `STALE_DATA_WAIT`
- `REGIME_CHECK`
- `REGIME_CHANGE`
- `HYSTERESIS_HOLD`
- `ROUTE_SELECTED`
- `ADAPTIVE_POSTURE_SELECTED`
- `ENTRY_CHECK`
- `ENTRY_BLOCKED`
- `ENTRY_APPROVED`
- `SIZING_DECISION`
- `ORDER_SUBMITTED`
- `POSITION_OPENED`
- `POSITION_MANAGED`
- `STALE_EXPOSURE_EXIT`
- `SAME_CYCLE_REVERSAL_BLOCKED`
- `POSITION_CLOSED`
- `CLOSEOUT_WINDOW`
- `BROKER_REJECTION`

Acceptance criteria:

- Important runtime decisions have stable event codes.
- Each event includes timestamp, bot, symbol, regime, action, reason code, and
  constraints when applicable.
- Narrative generation can prefer structured events over raw log text.

### 2. Upgrade Daily Narrative V2

Status: strongly consider

Impact: high

Why:

The 1D narrative is useful, but it is still mostly descriptive. Before live
trading, the debrief should assess whether the system behaved correctly, not
only whether it made money.

Add sections:

- `Session Identity`
- `Behavioral Assessment`
- `Narrative Confidence`
- `Key Policy Decisions`
- `Top Constraints`
- `Tuning Candidates`

Example behavioral assessment:

```text
The system behaved conservatively and coherently under unstable market
conditions. It avoided overtrading, honored stale-data entry protection, and
closed stale exposure when regime ownership no longer matched the open position.
```

Acceptance criteria:

- Narrative distinguishes market opportunity from system authorization.
- Narrative identifies intentional inactivity.
- Narrative confidence explains uncertainty, especially on low-trade days.

### 3. Make Fresh-Cross Doctrine Explicit

Status: decide before go-live

Impact: high

Why:

MomentumBot and InverseBot did not trade because Conservative mode required a
fresh cross. This is coherent, but it is a major participation policy.

Open decision:

- Keep live go-live in Conservative fresh-cross-only mode.
- Or allow Balanced/Adaptive continuation entries when a trend is already
  established after warmup.

Recommended near-term action:

- Do not change the rule from one day of evidence.
- Add better logs for "established trend rejected by fresh-cross doctrine."
- Track how often continuation entries would have been eligible under Balanced
  or Aggressive modes.

Acceptance criteria:

- The operator can tell whether no trade happened because no setup existed or
  because doctrine intentionally rejected the setup.
- Fresh-cross-only behavior is an explicit go-live choice, not an accidental
  default.

### 4. Add Data Freshness Session Telemetry

Status: strongly consider

Impact: high

Why:

Stale-bar protection worked, but repeated bar staleness should be summarized.
The system should quantify data quality without requiring manual log review.

Metrics:

- Stale-bar event count
- Total stale-bar duration
- Max bar age
- Average bar age
- Quote/trade live while bars stale count
- Entries blocked by stale bars
- Open-position risk cycles during stale bars

Acceptance criteria:

- End-of-day summary shows whether data quality was clean, degraded, or
  concerning.
- Stale data is reported as a handled guardrail, not as silent non-trading.

### 5. Add Regime Churn Metrics

Status: strongly consider

Impact: medium-high

Why:

The session had frequent boundary crossings. We need to know whether the regime
engine is appropriately sensitive or too twitchy for live use.

Metrics:

- Regime changes per hour
- Average regime hold time
- Short-lived regime count, such as holds under 3 minutes
- Hysteresis hold count
- Route changes per hour
- Entries blocked immediately after regime shifts
- Positions closed due to stale ownership mismatch

Acceptance criteria:

- Daily narrative can call a day `trend`, `chop`, `regime churn`, or
  `compression` based on metrics.
- Threshold changes are based on measured churn, not vibes.

### 6. Preserve Stale-Exposure Doctrine

Status: preserve

Impact: high

Why:

The `close_stale_position_no_same_cycle_reversal` behavior is a constitutional
safety rule. It prevents immediate reversal chaos when ownership no longer
matches the active regime.

Recommended action:

- Keep the rule.
- Promote it to a named policy event.
- Include it in the daily behavioral assessment whenever it triggers.

Acceptance criteria:

- Forced stale-position exits are easy to distinguish from strategy exits.
- Same-cycle reversal blocks are visible as policy, not as missing trades.

### 7. Add Go-Live Risk Envelope Settings

Status: strongly consider

Impact: high

Why:

Live trading should have explicit hard limits even if the strategy behaves
well in paper trading.

Candidate limits:

- Max live order notional
- Max live allocation percent
- Max daily realized loss
- Max closed trades per day
- Max broker rejections per day
- Max consecutive failed exits
- Manual kill switch
- Require flat state before live arming

Acceptance criteria:

- Live mode cannot submit orders outside the configured envelope.
- The UI exposes the active live envelope clearly.
- Breaching a limit halts entries and explains why.

### 8. Harden Partial-Fill Exit Handling

Status: partially implemented; continue hardening

Impact: high

Why:

Aggressive day produced two broker-rejected exit attempts while an opening buy
order was still partially filling. The initial open-buy sell guard has been
implemented so same-symbol exits wait while a buy order is still open. The
remaining live-readiness work is to make `OPENING`, `OPEN`, `CLOSING`, and
`CLOSED` materially visible position lifecycle states.

Candidate behavior:

- Preserve the implemented guard that avoids opposite-side market exits while a
  same-symbol buy order is still open.
- Surface an `OPENING` state when entry fill reconciliation is incomplete.
- Keep risk logic aware that a partially filled position exists, but avoid
  broker-rejected opposite-side orders.
- Escalate repeated partial-fill exit blockage as an operator-visible
  interrupt.

Acceptance criteria:

- Partial entry fills do not create repeated rejected exit attempts.
- The dashboard shows when a position is opening, open, closing, or closed.
- Risk logs explain whether the bot is waiting for fill completion or taking an
  allowed protective action.

### 9. Tighten Broker Rejection And P/L Truth

Status: strongly consider

Impact: high

Why:

The partial-fill exit rejections were classified as insufficient buying power
even though Alpaca reported an opposite-side/wash-trade conflict. Aggressive day
also showed a small P/L difference between lifecycle summary and account/fill
movement.

Recommended action:

- Add a distinct rejection category for opposite-side order conflict or
  wash-trade risk.
- Preserve broker-provided rejection text in operator-visible state.
- Reconcile lifecycle P/L, fill-paired P/L, and account day P/L around partial
  fills.

Acceptance criteria:

- Broker rejection categories match the actual failure cause.
- P/L summaries can explain any gap between account movement and lifecycle
  realized P/L.
- Partial fills are not double-counted or mispaired in trade summaries.

## P1 Candidates After More Sessions

### 1. ChopBot Threshold Review

Status: watch

Why:

ChopBot correctly entered a discounted sideways setup and exited profitably
when regime ownership changed. One successful trade is not enough to tune the
discount threshold.

Watch:

- ChopBot entry frequency
- Average hold time
- Mean-reversion follow-through
- Exits caused by route mismatch
- Missed opportunities where discount was close but insufficient

### 2. Regime Threshold And Hysteresis Review

Status: watch

Why:

The regime engine had frequent transitions near threshold boundaries. This may
be appropriate market sensitivity, or it may be churn.

Watch:

- Whether short-lived regime flips produce bad trades
- Whether hysteresis prevents enough false flips
- Whether separate uptrend/downtrend thresholds are needed
- Whether volatility-adjusted thresholds would improve stability

### 3. Adaptive Active Mode Decision

Status: defer until more evidence

Why:

Adaptive shadow looked coherent, but shadow mode should earn trust over several
sessions before it is given control.

Watch:

- How often Adaptive would choose a different posture than the manual mode
- Whether those choices align with later market behavior
- Whether Adaptive reacts too quickly to churn
- Whether Adaptive correctly reduces aggression near closeout and stale-data
  conditions

### 4. Regime-Mismatch Exit Outcome Classification

Status: watch

Why:

Route-invalidation exits are doctrine, not automatically success or failure.
Aggressive day had many exits under the current `stale_position_regime_mismatch`
reason, but the outcome quality likely varied.

Potential classifications:

- Defensive save: exit prevented meaningful adverse continuation.
- Premature cut: exit was followed by favorable continuation in the exited
  direction.
- Profitable handoff: exit cleared exposure before a different bot captured the
  new regime.
- Neutral exit: little meaningful movement followed.

Watch:

- Post-exit price path over 5, 15, and 30 minutes.
- Whether a new routed bot entered after the exit.
- Whether the exit protected capital or mostly increased churn.

### 5. Directional Persistence And Session Difficulty Telemetry

Status: watch

Why:

Balanced day and Aggressive day had similar regime-transition counts but very
different outcomes. Churn count alone is not the causal explanation.

Potential metrics:

- Regime age at entry.
- Regime flips over the last 15, 30, and 60 minutes.
- Post-entry follow-through over 5, 15, and 30 minutes.
- Max favorable excursion and max adverse excursion per trade.
- Session difficulty score based on churn, volatility, persistence, and
  reversal frequency.

Watch:

- Whether continuation entries work only after regimes have proven enough age.
- Whether high local churn should lower Adaptive confidence.
- Whether session difficulty explains mode performance better than raw churn.

## Go-Live Readiness Checklist

- [ ] Fresh-cross doctrine explicitly accepted or revised.
- [ ] Stale-bar telemetry summarized per session.
- [ ] Regime churn metrics summarized per session.
- [ ] Daily narrative includes behavioral assessment.
- [ ] Daily narrative includes narrative confidence.
- [ ] Stale-exposure exits are named policy events.
- [x] Initial open-buy sell guard prevents repeated opposite-side sell attempts
  while a same-symbol buy order is still open.
- [ ] Opening, open, closing, and closed lifecycle states are visible to the
  operator.
- [ ] Broker rejection classification distinguishes buying-power limits from
  opposite-side or wash-trade conflicts.
- [ ] Lifecycle P/L, fill-paired P/L, and account movement can be reconciled.
- [ ] Live risk envelope is configured and visible.
- [ ] Live trading remains explicitly armed, typed-confirmation gated, and easy
  to disarm.
- [ ] Final closeout state is clear: flat, stopped, and rearmed for next day.

## Non-Goals For Now

- Replay UI.
- Multi-day strategy optimization.
- Automatic parameter mutation.
- Increasing aggression based on one profitable day.
- Replacing raw logs with narrative summaries.

## Decision Log

2026-05-26:

- Created this tuning log after the first full paper-trading day.
- Chose to prioritize event classification, daily behavioral assessment, data
  freshness telemetry, and explicit fresh-cross doctrine before any major
  strategy parameter changes.
- Added evidence-strength standards so tuning decisions stay proportional to
  the quality of supporting proof.
- Added the qualification mode rotation plan:
  Conservative -> Balanced -> Aggressive -> Adaptive, repeated across separated
  market contexts.

2026-05-28:

- Added the Aggressive qualification day AAR.
- Recorded that Aggressive increased continuation participation without
  appearing reckless, but surfaced execution and telemetry findings.
- Recorded the implemented open-buy sell guard and promoted remaining lifecycle
  visibility, broker rejection classification, and P/L reconciliation as
  pre-live correctness candidates.
- Added regime-mismatch outcome classification and directional-persistence
  telemetry as watch items before any strategy-threshold changes.
