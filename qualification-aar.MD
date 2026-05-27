# EdgeWalker Qualification AAR

Last updated: 2026-05-27

This file captures paper-trading qualification observations before they become
tuning decisions. During the first full rotation through Conservative,
Balanced, Aggressive, and Adaptive, the goal is to let each mode show its tape
without moving the target.

## Qualification Doctrine

- Do not change strategy configuration during the first mode cycle except for
  the planned daily mode rotation.
- Treat one session as evidence, not proof.
- Separate market difficulty from runtime correctness.
- Separate P/L outcomes from operational coherence.
- Capture hypotheses without turning them into immediate changes.
- Promote repeated patterns into `tuning.MD` only after enough evidence exists.

## Review Questions

- Did the runtime remain coherent?
- Did data health, broker state, order flow, and closeout behavior stay clean?
- Did the active mode authorize trades that were explainable under doctrine?
- Which bot carried the session outcome?
- Which exit reasons drove realized P/L?
- Did the narrative summarize scale, risk, and behavior accurately?
- How confident are we in the interpretation, separate from profitability?
- Which notable events should be remembered when reviewing the tape later?
- Did Adaptive shadow reveal useful posture, confidence, or stability signals?
- What should be watched in the next mode before changing anything?

## Daily AAR Template

- Date:
- Qualification day:
- Mode:
- Cycles:
- Account result:
- Closed trades:
- Regime transitions:
- Data / broker health:
- Interpretation confidence:
- Bot performance:
- Notable events:
- Main behavioral fingerprint:
- Adaptive shadow observations:
- What worked:
- What needs attention:
- Parked hypotheses:
- Do not change yet:

## 2026-05-26 AAR: Conservative Mode

Qualification day: Day 1

Mode: Conservative

Session files:

- `logs/edgewalker-2026-05-26.jsonl`
- `logs/position_lifecycle.jsonl`

Result:

- Final realized P/L: `+$55.93`
- Approximate account impact: `+0.06%` on a roughly `$100k` paper account
- Cycles: `380`
- Closed trades: `1`
- Wins/losses: `1W / 0L`
- Regime transitions: `30`
- Data health: `353 / 380` cycles were `LIVE`; `15` warmup cycles and `12`
  stale-data wait cycles were recorded
- Broker state: `OK`
- End state: flat into close, no pending orders
- Interpretation confidence: `MEDIUM`
  - Operational interpretation is high-confidence.
  - Strategy interpretation is lower-confidence because Conservative produced
    only one closed trade.

Mode note:

- Regular-market qualification behavior was Conservative.
- The raw log contains one pre-market/early record marked `BALANCED`; the
  remaining `379` cycles were `CONSERVATIVE`.

Bot performance:

- MomentumBot: `$0.00`, `0 trades`
- ChopBot: `+$55.93`, `1 trade`, `1W / 0L`
- InverseBot: `$0.00`, `0 trades`

Exit reason contribution:

- Stale-position regime mismatch: `1 exit`, `+$55.93`

Entry reason contribution:

- Discount confirmed: `1 trade`, `+$55.93`

Notable events:

- Only closed trade: ChopBot SOXL, `+$55.93`, held about `2m 04s`
  from roughly `10:50` to `10:52 ET`.
- Most regime churn in a 15-minute window: `4` flips, roughly
  `10:04-10:13 ET`.
- Cleanest behavior: stale-position regime mismatch closed the only position
  profitably and did not trigger a same-cycle reversal.

Session identity:

- Regime-churn day with alternating directional and sideways classifications.
- Early strong SOXL uptrend, mid-session pullback/chop, and late-session upward
  drift.
- Conservative mode blocked most established-trend continuation entries because
  it required fresh directional crosses.
- The only trade was a ChopBot SOXL entry that closed profitably when ownership
  no longer matched the active route.

Adaptive shadow observations:

- Adaptive shadow evaluated on `359` cycles.
- On entry-posture cycles it selected: `BALANCED 199`, `CONSERVATIVE 88`,
  `AGGRESSIVE 70`.
- The posture stream was readable and did not appear operationally noisy, but
  this was observation only. Conservative mode remained in control.

What worked:

- Market-open warmup behaved cleanly.
- The system armed before open, operated through the session, entered closeout
  behavior, stopped after close, and rearmed for the next market day.
- Stale-bar entry protection repeatedly blocked new entries while quote/trade
  data continued to update.
- Stale-position doctrine closed the ChopBot SOXL position when the active
  regime flipped to DOWNTREND.
- No same-cycle reversal occurred after the forced stale-position close.
- Adaptive posture shadow logs were coherent and easy to read.
- The narrative correctly identified regime churn and limited opportunity.

What needs attention:

- Repeated 90-120 second stale-bar pauses occurred despite live quote/trade
  data.
- Regime routing changed frequently near threshold boundaries.
- Daily narrative should distinguish "no trend existed" from "trend existed but
  entry doctrine blocked continuation entries."
- Directional fresh-cross-only behavior may be too restrictive after warmup, but
  this should be studied across more Conservative samples before changing.
- The system needs a first-class event vocabulary so AARs can rely on structured
  facts instead of loose log interpretation.

Parked hypotheses:

- Conservative may be operationally stable but too restrictive for already
  established trends.
- Stale-data entry blocks should be tracked as a first-class daily metric.
- Regime churn may be common enough in semiconductor ETFs that every mode needs
  explicit churn telemetry.
- Narrative V2 should report intentional non-participation as a distinct
  behavior, not as missed opportunity.

Do not change yet:

- Do not loosen Conservative mode based on one low-trade day.
- Do not change stale-data thresholds from this single session.
- Do not change regime thresholds before every mode gets a full qualification
  day.

Next session:

- Qualification Day 2 should run Balanced mode.
- Preserve all other configuration unless a fire-fix is required.

## 2026-05-27 AAR: Balanced Mode

Qualification day: Day 2

Mode: Balanced

Session files:

- `logs/edgewalker-2026-05-27.jsonl`
- `logs/position_lifecycle.jsonl`

Result:

- Final realized P/L: `-$763.19`
- Approximate account impact: `-0.76%` on a roughly `$100k` paper account
- Cycles: `385`
- Closed trades: `25`
- Wins/losses: `8W / 17L`
- Regime transitions: `42`
- Data health: `383 / 385` cycles were `LIVE`
- Broker state: `OK`
- End state: flat into close, no pending orders
- Interpretation confidence: `HIGH` for the runtime/churn diagnosis, `MEDIUM`
  for any future tuning implication because this is still one session.

Bot performance:

- MomentumBot: `-$1,001.51`, `11 trades`, `3W / 8L`
- ChopBot: `+$50.76`, `4 trades`, `2W / 2L`
- InverseBot: `+$187.57`, `10 trades`, `3W / 7L`

Exit reason contribution:

- Stale-position regime mismatch: `17 exits`, `-$597.47`
- Trailing-stop breached: `7 exits`, `-$177.81`
- Market-close liquidation: `1 exit`, `+$12.09`

Entry reason contribution:

- Trend continuation allowed: `17 trades`, `-$876.66`
- Discount confirmed: `4 trades`, `+$50.76`
- Fresh cross confirmed: `4 trades`, `+$62.71`

Notable events:

- Highest realized gain: InverseBot SOXS, `+$1,029.46`, roughly
  `9:37-9:50 ET`, exited by trailing-stop breach.
- Largest realized loss: InverseBot SOXS, `-$433.82`, roughly
  `9:51-9:53 ET`, exited by trailing-stop breach.
- Longest hold: MomentumBot SOXL, about `29m 21s`, roughly
  `12:02-12:31 ET`, closed by stale-position regime mismatch for `+$491.94`.
- Fastest closed trade: ChopBot SOXL, about `1m 01s`, roughly
  `11:41-11:42 ET`, stale-position regime mismatch for `+$4.79`.
- Most regime churn in a 15-minute window: `5` flips, roughly
  `9:54-10:08 ET`.

Session identity:

- Hostile churn day in semiconductor ETFs.
- The market rotated frequently between uptrend, downtrend, and sideways
  classifications.
- Balanced mode did not appear reckless; it appeared under-protected against
  regime churn.
- MomentumBot was the main casualty. ChopBot and InverseBot both ended green,
  which supports the specialist-bot architecture.

Adaptive shadow observations:

- Adaptive shadow evaluated on `379` cycles.
- It paused entry posture while a position was open on `248` cycles, selecting
  Balanced as a holding/default posture while manual Balanced stayed in control.
- On true entry-posture cycles it selected: `BALANCED 96`, `CONSERVATIVE 23`,
  `AGGRESSIVE 12`.
- Grouping actual entries by Adaptive's shadow posture at entry time:
  `AGGRESSIVE 4 trades, +$429.59`; `BALANCED 20 trades, -$1,602.39`;
  `CONSERVATIVE 1 trade, +$409.61`. This is observational grouping, not a
  counterfactual Adaptive P/L.
- The largest weakness bucket was `moderate_directional_regime`: `16 trades`,
  `-$1,653.15`, `3W / 13L`.
- Adaptive appeared observationally stable under stress. The bigger future
  lesson is environmental coherence: recent regime flip rate, regime age, and
  churn pressure may need to affect confidence before Adaptive receives control
  authority.

What worked:

- Runtime stayed coherent through a difficult market structure.
- No runaway orders, duplicate entries, conflicting positions, broker chaos, or
  recursive reversal behavior were observed.
- Data health was strong for nearly the entire session.
- Broker state stayed clean.
- Stale-position regime-mismatch exits flattened exposure when the current
  route no longer matched the open position's owner.
- Closeout behavior flattened the final position before the bell.
- Dashboard hierarchy and order-flow visibility were useful for session review.
- Audio cues were useful enough to notice important closes without requiring
  constant visual focus.

What needs attention:

- The daily narrative was emotionally too negative. It should scale language by
  account impact, not only by churn, trade count, or red P/L.
- The phrase "stale position regime mismatch" is easy to misread as stale data.
  It actually means route/owner mismatch after regime change.
- MomentumBot continuation entries were vulnerable to churn.
- Regime transitions were expensive, especially when they forced ownership
  exits soon after entry.
- The dashboard can briefly show an open position with `Trail exit --` while a
  bot-managed exit order is resolving because the trailing state has already
  been cleared.

Parked hypotheses:

- Regime sensitivity may be too high for volatile semiconductor sessions.
- Recent regime churn should eventually reduce directional confidence or
  continuation-entry willingness.
- Regime age, confirmation count, or churn penalty may be safer future tools
  than simply widening thresholds.
- MomentumBot may need more protection from fake breakouts and low-followthrough
  continuation entries.
- Narrative V2 should include P/L percent, account context, volatility context,
  and operational-health assessment.
- Timeline/replay views should make route changes, owner mismatch exits, and
  realized P/L by exit reason first-class.

Do not change yet:

- Do not change regime thresholds from this single session.
- Do not change trail percent from this single session.
- Do not change Balanced mode doctrine before every mode gets a full
  qualification day.
- Do not treat the narrative's tuning suggestion as an approved adjustment.

Next session:

- Qualification Day 3 should run Aggressive mode.
- Preserve all other configuration unless a fire-fix is required.
- Compare Aggressive mode's behavior under whatever tape the market gives us,
  especially trade count, churn sensitivity, and MomentumBot exposure.
