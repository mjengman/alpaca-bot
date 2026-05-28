# EdgeWalker Qualification AAR

Last updated: 2026-05-28

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

## 2026-05-28 AAR: Aggressive Mode

Qualification day: Day 3

Mode: Aggressive

Session files:

- `logs/edgewalker-2026-05-28.jsonl`
- `logs/position_lifecycle.jsonl`

Result:

- Final lifecycle realized P/L: `+$297.86`
- Approximate account impact: `+$287.25`, about `+0.29%` on a roughly `$99k`
  paper account
- Fill-paired P/L: `+$287.24`
- Cycles: `386`
- Closed trades: `20`
- Wins/losses: `8W / 12L`
- Regime transitions: `38`
- Data health: `368 / 386` cycles were `LIVE`; `13` stale cycles and `3`
  warming-up cycles were recorded
- Broker state: mostly `OK`, with `2` exit-blocked cycles from partial-fill
  opposite-side order conflicts
- End state: flat into close, no pending orders
- Session difficulty: `HIGH / CHURNY BUT TRADEABLE`
- Interpretation confidence: `HIGH` for operational findings, `MEDIUM` for
  strategy conclusions because Adaptive has not yet had control

Bot performance:

- MomentumBot: lifecycle `+$636.48`, `11 trades`, `6W / 5L`
- ChopBot: `-$23.83`, `1 trade`, `0W / 1L`
- InverseBot: `-$314.79`, `8 trades`, `2W / 6L`

Fill-paired contribution note:

- Fill-paired MomentumBot P/L was about `+$625.86`, about `$10.62` below the
  lifecycle bot summary. This appears tied to the opening partial-fill sequence
  and should be reconciled before live trading.

Exit reason contribution, fill-paired:

- Stale-position regime mismatch: `17 exits`, about `-$91.80`
- Trailing-stop breached: `3 exits`, about `+$379.04`

Entry reason contribution, fill-paired:

- Trend continuation allowed: `18 trades`, about `+$8.48`
- Strong trend chase allowed: `1 trade`, about `+$302.59`
- Discount confirmed: `1 trade`, about `-$23.83`

Notable events:

- Highest realized gain: MomentumBot SOXL, about `+$650.36`, roughly
  `10:55-11:45 ET`, exited by stale-position regime mismatch after a major
  persistence window.
- Largest realized loss: MomentumBot SOXL, about `-$242.82`, roughly
  `15:09-15:17 ET`, exited by stale-position regime mismatch.
- Longest hold: MomentumBot SOXL, about `50m 36s`, roughly `10:55-11:45 ET`.
- First trade opened during partial fills; attempted route-invalidation exits
  at roughly `9:36` and `9:37 ET` were rejected by Alpaca as opposite-side /
  wash-trade conflicts until the entry finished filling.
- Only one trade used `strong_trend_chase_allowed`; Aggressive did not behave
  like uncontrolled chase mode.

Session identity:

- Directional participation day with persistent regime churn.
- SOXL moved from about `$219.87` at the first actionable cycle, down to
  `$207.59`, up to `$231.60`, and ended near `$224.91`.
- Regime churn remained high, but the tape rewarded directional persistence
  more than Balanced day did.
- Aggressive mode acted more continuation-friendly than reckless.

Behavioral fingerprint:

- Aggressive increased participation and captured persistence without obviously
  collapsing discipline.
- The system spent most of the day managing open positions rather than firing
  constant new entries.
- Continuation participation was materially higher than Conservative and more
  successful than Balanced under this tape.
- MomentumBot appears environment-sensitive rather than intrinsically weak:
  nearly absent in Conservative, heavily negative in Balanced, strongly
  positive in Aggressive.
- InverseBot was the casualty of this session, which contrasts with its
  positive contribution on Balanced day.

Adaptive shadow observations:

- Adaptive posture counts: `BALANCED/HIGH 241`, `BALANCED/LOW 77`,
  `CONSERVATIVE/LOW 27`, `BALANCED/MODERATE 18`, `CONSERVATIVE/HIGH 8`,
  `AGGRESSIVE/HIGH 4`.
- Most `BALANCED/HIGH` cycles were `adaptive_entry_posture_paused` while a
  position was already open, so the raw Balanced count should not be read as a
  simple rejection of Aggressive mode.
- Grouping actual entries by Adaptive's shadow posture at entry time:
  `AGGRESSIVE/HIGH 4 trades, +$519.53`; `BALANCED/MODERATE 14 trades,
  -$173.57`; `BALANCED/HIGH 1 trade, -$34.89`; `BALANCED/LOW 1 trade,
  -$23.83`. This is observational grouping, not counterfactual Adaptive P/L.
- Tomorrow's Adaptive day should be judged on doctrine-selection quality, not
  just P/L.

What worked:

- Aggressive traded less than Balanced while producing better session results:
  `20` trades versus Balanced's `25`.
- The runtime still blocked many weak setups: ChopBot discount/mean checks and
  directional strength checks remained active.
- Stale-data, closeout, sizing, and route-invalidation policies remained active.
- The strongest MomentumBot trade showed that continuation entries can work
  when directional persistence quality is favorable.
- Churn count alone was shown to be insufficient: Balanced lost money with
  `42` transitions, while Aggressive made money with `38`.

What needs attention:

- Initial open-buy sell guards have been implemented; remaining work is
  lifecycle visibility around opening/closing states.
- Broker rejection classification mislabeled opposite-side/wash-trade conflict
  as insufficient buying power.
- Lifecycle P/L, fill-paired P/L, and account movement should reconcile cleanly,
  especially around partial fills.
- The phrase `stale_position_regime_mismatch` is behaviorally useful but
  semantically muddy; it reads like stale data even when the real issue is
  route/owner invalidation.
- Regime-mismatch exits need outcome classification before the doctrine can be
  evaluated. Potential buckets: defensive save, premature cut, profitable
  handoff, neutral exit.

Parked hypotheses:

- The key hidden variable may be directional persistence quality, not raw
  regime-transition count.
- Regime age at entry and recent churn pressure may eventually improve Adaptive
  confidence.
- Continuation entries may need confidence scoring that distinguishes fresh
  cross, ordinary continuation, and strong-trend chase.
- Session difficulty should eventually capture churn, volatility, persistence,
  and reversal frequency.
- Aggressive may be better understood by operators as continuation-friendly or
  participation-oriented, not reckless.

Do not change yet:

- Do not change directional thresholds from this single profitable session.
- Do not change InverseBot filters from one bad day.
- Do not change trail percent or cooldown from this session.
- Do not promote Aggressive live behavior just because it ended green.
- Do not interrupt the qualification rotation before Adaptive has a full day in
  control.

Next session:

- Qualification Day 4 should run Adaptive mode.
- Judge Adaptive on doctrine-selection quality before profitability.
- Watch whether Adaptive avoids churn traps, participates when persistence
  emerges, and exposes confidence changes that are explainable in hindsight.
- After Adaptive day, promote operational fixes that now have enough evidence
  into implementation backlog: opening/closing lifecycle visibility, broker
  rejection classification, and P/L reconciliation.
