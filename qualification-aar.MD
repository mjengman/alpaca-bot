# EdgeWalker Qualification AAR

Last updated: 2026-06-05

This file captures qualification and early-live observations before they become
tuning decisions. During the first full rotation through Conservative,
Balanced, Aggressive, and Adaptive, the goal was to let each mode show its tape
without moving the target. In live trading, the same evidence discipline
applies: prove lifecycle truth first, then tune from repeated evidence.

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

## Emerging Themes

These are recurring observations, not tuning decisions.

- Trend Trust appears more important than raw trend strength.
- Regime age may be underrepresented in current confidence logic.
- Churn count alone is insufficient to explain tradeability.
- Fresh regime transitions can be low-trust but high-opportunity; Trend Trust
  should measure environmental reliability while fresh-cross doctrine measures
  timing opportunity.
- Directional persistence may explain outcomes better than raw churn count,
  trend strength, or regime classification alone.
- Environmental classification may become the next layer above regime
  detection. Regime answers local direction; environment should eventually
  describe whether the current reward structure favors continuation, reversal,
  or patience.
- Profitable Persistence is emerging as a key concept: many regimes appear real,
  but not all produce enough favorable post-entry movement to reward
  participation.
- Live operational success is distinct from strategy edge. The first real-money
  day should be judged primarily on lifecycle truth, order correctness,
  reconciliation, and operator control.
- Route invalidation exits dominate realized outcomes on churny sessions.
- Route invalidation P/L is now a first-class validation metric. On June 2,
  route invalidation exits were net positive, suggesting the doctrine may be
  protecting gains rather than merely interrupting trades.
- Upside continuation quality and downside continuation quality may be
  asymmetric. MomentumBot and InverseBot should not be assumed to be equally
  effective mirror images across all market environments.
- Adaptive appears disciplined, but may need stronger regime-maturity awareness.
- Adaptive shadow should be evaluated primarily while flat; posture counts while
  a position is open can mostly reflect paused entry-posture judgment.
- `POLL_SEC` may be more important for exit precision than entry quality while
  regime logic remains one-minute-bar based.
- Live/research comparisons must account for cadence differences. A 20-second
  live poll loop can produce a different behavioral fingerprint than a
  one-minute `next_bar_open` replay even with the same controls.
- Regular-session warmup integrity is a doctrine question: what market world is
  EdgeWalker modeling at the open?
- Human-facing label: route invalidation exit. Current internal code:
  `stale_position_regime_mismatch`.

## Daily AAR Template

- Date:
- Qualification day:
- Mode:
- Cycles:
- Account result:
- Closed trades:
- Regime transitions:
- Market character:
- Session difficulty:
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
- Market character: `CHURNY / MIXED`
- Session difficulty: `MODERATE-HIGH`
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
- Market character: `CHURNY / HOSTILE`
- Session difficulty: `HIGH`
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
- Market character: `CHURNY / DIRECTIONAL / TRADEABLE`
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

## 2026-05-29 AAR: Adaptive Mode

Qualification day: Day 4

Mode: Adaptive

Session files:

- `logs/edgewalker-2026-05-29.jsonl`
- `logs/position_lifecycle.jsonl`

Result:

- Final lifecycle realized P/L: `-$25.03`
- Approximate account impact: `-$25.02`, about `-0.03%` on a roughly `$99k`
  paper account
- Cycles: `385`
- Closed trades: `16`
- Wins/losses: `3W / 13L`
- Regime transitions: `34`
- Market character: `CHURNY / BOUNDARY-DRIVEN / MICRO-TREND`
- Data health: `353 / 385` cycles were `LIVE`; `25` stale cycles and `7`
  warming-up cycles were recorded
- Broker state: `OK` all day
- Broker/order errors: `0`
- End state: flat into close, no pending orders
- Session difficulty: `HIGH / CHURNY AND BOUNDARY-DRIVEN`
- Interpretation confidence: `HIGH` for operational behavior, `MEDIUM` for
  strategy conclusions because this is Adaptive's first active qualification
  day

Bot performance:

- MomentumBot: `-$369.28`, `7 trades`, `2W / 5L`
- ChopBot: `-$23.21`, `2 trades`, `0W / 2L`
- InverseBot: `+$367.46`, `7 trades`, `1W / 6L`

Exit reason contribution:

- Stale-position regime mismatch: `15 exits`, about `-$1,050.77`
- Trailing-stop breached: `1 exit`, about `+$1,025.75`

Entry reason contribution:

- Trend continuation allowed: `12 trades`, about `+$59.04`
- Strong trend chase allowed: `1 trade`, about `+$192.28`
- Fresh cross confirmed: `1 trade`, about `-$253.14`
- Discount confirmed: `2 trades`, about `-$23.21`

Notable events:

- Highest realized gain: InverseBot SOXS, about `+$1,025.75`, roughly
  `10:08-10:52 ET`, exited by trailing-stop breach.
- Largest realized loss: InverseBot SOXS, about `-$253.14`, roughly
  `11:09-11:15 ET`, exited by stale-position regime mismatch.
- Longest hold: InverseBot SOXS, about `43m 33s`, the same high-gain trade.
- Only one trailing-stop exit nearly offset fifteen route-invalidation exits.
- No partial-fill opposite-side rejection repeated after the open-buy sell
  guard was added.
- The first cycle showed `12 / 20` warmup bars at `09:30:01 ET`; the latest bar
  was from `09:24 ET`, implying persisted same-day premarket bars were included
  in the opening warmup cache.

Session identity:

- Micro-trend/chop day where the market repeatedly changed its mind.
- SOXL opened with a strong early move, moved into a sharp downtrend, then spent
  much of the day alternating between short-lived directional regimes and
  sideways classifications.
- Adaptive finished essentially flat despite `34` regime transitions and a
  `3W / 13L` trade distribution.
- The day's P/L was carried by one persistent InverseBot thesis and eroded by
  many small route-invalidation losses.

Behavioral fingerprint:

- Adaptive mostly selected Balanced, but this should not be read as simple
  indecision. Most Balanced/HIGH cycles happened while a position was already
  open and entry posture was paused.
- Adaptive escalated to Aggressive only twice, suggesting the confidence model
  did not overreact to strength.
- Adaptive used Conservative during stale-bar entry-block conditions and weak
  directional regimes.
- The system remained operationally disciplined: no broker errors, no runaway
  entries, clean P/L reconciliation, and flat closeout.

Adaptive active observations:

- Posture counts: `BALANCED 336`, `CONSERVATIVE 34`, `AGGRESSIVE 2`, no
  posture on `13` warmup/closeout cycles.
- Entry grouping by active Adaptive posture:
  - `AGGRESSIVE`: `2 trades`, about `+$35.13`
  - `BALANCED`: `12 directional trades`, about `-$36.94`
  - ChopBot/sideways entries: `2 trades`, about `-$23.21`
- Of `16` entries, `14` occurred within about `3` minutes of the active regime
  beginning, and all `16` occurred within `10` minutes.
- Median regime age at entry was about `1` minute.
- This suggests Adaptive evaluated signal strength coherently but did not yet
  fully price regime maturity or environmental trustworthiness.

What worked:

- Adaptive behaved coherently and stayed disciplined under a difficult tape.
- The system did not overtrade: `16` buys across `385` cycles.
- Aggressive posture was rare and controlled.
- Extension protection and entry checks continued to block weak or overextended
  setups.
- The high-gain InverseBot trade showed the architecture can benefit from a
  real persistence window.
- Account P/L and lifecycle P/L reconciled cleanly.
- Broker state stayed clean all day.

What needs attention:

- Adaptive needs better visibility into regime age, recent churn, and trend
  trustworthiness. Strength alone is not enough.
- Route-invalidation exits dominated realized outcomes. They need outcome
  classification before the doctrine can be judged.
- The opening warmup cache included current-day bars from before regular-market
  open. If EdgeWalker is modeling regular-session behavior, warmup should
  either explicitly include or explicitly exclude premarket bars.
- Logs exposed a recurring state where quotes/trades were live while bars were
  stale. This means the market was moving while the regime interpretation
  pipeline was temporarily frozen.
- The label `stale_position_regime_mismatch` remains semantically muddy because
  it describes route/owner invalidation, not stale market data.

Parked hypotheses:

- Trend Trust may need to become a first-class telemetry concept, separate from
  raw regime strength.
- A one-minute-old regime should not receive the same confidence treatment as a
  thirty-minute-old regime with similar SMA gap.
- Recent flips over `15`, `30`, and `60` minutes may be more useful to Adaptive
  than total daily transition count.
- Directional efficiency and post-signal follow-through may better explain mode
  performance than churn count alone.
- `POLL_SEC` may become an exit-precision and perception setting, especially
  while a position is open, but should be instrumented before active tuning.
- A subtle audio cue when trailing exit crosses entry price could help the
  operator perceive when a position becomes protected without celebrating P/L.
- The dashboard should eventually show entry price and trail exit together for
  easier visual comparison.

Do not change yet:

- Do not demote Adaptive because the first active day was near-flat.
- Do not change regime thresholds from this single boundary-driven session.
- Do not loosen ChopBot based on two small losing trades.
- Do not tighten trail percent from this session alone.
- Do not make active Dynamic Controls changes before shadow evidence exists.

Next session:

- Continue the qualification rotation without strategy-threshold changes.
- Promote documentation and observability items: Trend Trust telemetry,
  regular-session warmup integrity, stale-bar repair/backfill investigation,
  and route-invalidation exit classification.
- Judge the next Conservative sample against Day 1 to see whether separated
  time slices reveal consistent behavior.

## Qualification Round 2 Readiness Note

Date: 2026-05-31

Status:

- Weekend observability sprint completed and pushed before qualification round
  2.
- No strategy thresholds, sizing doctrine, trail percent, ChopBot discount,
  cooldown, or Adaptive posture rules were changed.
- Implemented changes are primarily operational-truth and operator-confidence
  improvements: regular-session-only warmup, stale-bar REST backfill, lifecycle
  visibility, partial-fill conflict classification, P/L reconciliation
  confidence, Trend Trust shadow telemetry, route-invalidation context, session
  metrics, and dashboard risk-state polish.

What may affect observed behavior:

- Opening behavior may change because premarket bars no longer satisfy
  regular-session warmup.
- Stale-bar recovery may improve because the runtime now attempts bounded REST
  bar backfill before regime detection.

What should not change:

- Entry doctrine.
- Exit doctrine.
- Same-cycle reversal policy.
- Adaptive decision rules.
- Position sizing.
- Strategy thresholds.

Round 2 instruction:

- Run Conservative, Balanced, Aggressive, and Adaptive again without strategy
  retuning.
- Treat Trend Trust and session metrics as shadow evidence only.
- Use the second Conservative sample to compare separated time slices against
  Day 1 rather than to declare a winner.

## 2026-06-01 AAR: Round 2 Conservative Mode

Qualification day: Round 2 Day 1

Mode: Conservative

Session files:

- `logs/edgewalker-2026-06-01.jsonl`
- `logs/position_lifecycle.jsonl`

Result:

- Final realized P/L: `+$911.33`
- Approximate account impact: `+0.92%` on a roughly `$100k` paper account
- Cycles: `383`
- Closed trades: `2`
- Wins/losses: `2W / 0L`
- Regime transitions: `23`
- Market character: `CHURNY BUT TRADEABLE / DIRECTIONAL`
- Session difficulty: `MODERATE-HIGH`
- Interpretation confidence: `HIGH` for operational behavior; `MEDIUM` for
  strategy conclusions because this is one separated Conservative sample.

Bot performance:

- MomentumBot: `+$718.53`, `1 trade`, `1W / 0L`
- ChopBot: `$0.00`, `0 trades`
- InverseBot: `+$192.80`, `1 trade`, `1W / 0L`

Weekend-change validation:

- Regular-session-only warmup passed. At the regular open, EdgeWalker started at
  `0 / 20` bars and warmed up on regular-session bars instead of inheriting
  premarket context.
- Route invalidation behaved as intended. MomentumBot owned a profitable `SOXL`
  position, the regime moved `UPTREND -> SIDEWAYS`, active ownership shifted to
  ChopBot, and the runtime exited via
  `close_route_invalidated_position_no_same_cycle_reversal`.
- Position ownership and no-same-cycle-reversal doctrine held. The route
  invalidation exit locked profit without immediately flipping into a new
  position.
- Trend Trust worked as telemetry, not authority. The Momentum entry had
  `LOW` Trend Trust with a newborn regime and became the largest winner; the
  Inverse entry had `MODERATE` Trend Trust and also won.
- Adaptive shadow stayed non-invasive. Adaptive generated posture opinions but
  did not mutate the active Conservative behavior.
- Stale-bar handling remained safe under degraded data conditions. Stale data
  appeared during the session, but stale-entry protections and live risk
  management behaved coherently.

Main behavioral fingerprint:

- EdgeWalker stayed selective under churn: `23` regime transitions, `383`
  cycles, and only `2` entries.
- The day validated that safety and observability improvements did not neuter
  participation.
- The strongest lesson was not "nothing went wrong." It was that when data and
  regimes became imperfect, the system degraded safely instead of acting
  chaotically.

Parked hypotheses:

- Fresh regime transitions can be low-trust but high-opportunity.
- Trend Trust should continue measuring environmental reliability, while
  fresh-cross doctrine measures timing opportunity.
- Trend Trust may become useful later for sizing, risk envelope, or operating
  tempo, but this session argues against using it as a hard entry veto.
- Stale-bar REST backfill improved visibility and safety, but did not eliminate
  stale-bar episodes.

Do not change yet:

- Do not change strategy thresholds after this green Conservative sample.
- Do not feed Trend Trust into active entry/exit decisions yet.
- Do not loosen or tighten stale-bar behavior from one session.
- Run Balanced tomorrow unchanged so Round 2 remains a clean comparison.

## 2026-06-02 AAR: Round 2 Balanced Mode

Qualification day: Round 2 Day 2

Mode: Balanced

Session files:

- `logs/edgewalker-2026-06-02.jsonl`
- `logs/position_lifecycle.jsonl`

Result:

- Final realized P/L: `+$1,291.63`
- Approximate account impact: `+1.29%` on a roughly `$100k` paper account
- Cycles: `383`
- Closed trades: `15`
- Wins/losses: `9W / 6L`
- Regime transitions: `26`
- Market character: `HIGH-TRANSITION / TRADEABLE UPSIDE CONTINUATION`
- Session difficulty: `HIGH`
- Data / broker health: no broker or stream errors; `356` live cycles, `21`
  warmup cycles, and `6` stale-bar cycles
- End state: flat into close, no pending orders
- Interpretation confidence: `HIGH` for operational behavior; `MEDIUM` for
  strategy conclusions because this is one separated Balanced sample.

Bot performance:

- MomentumBot: `+$2,142.17`, `8 trades`, `7W / 1L`
- ChopBot: `-$59.18`, `1 trade`, `0W / 1L`
- InverseBot: `-$791.36`, `6 trades`, `2W / 4L`

Exit reason contribution:

- Route invalidation exits: `13`, `+$813.71`
- Trailing stop exits: `1`, `-$51.44`
- Market close liquidation: `1`, `+$529.35`

Main behavioral fingerprint:

- This was not simply a "Balanced worked" day. It was a "MomentumBot worked"
  day inside Balanced doctrine.
- Balanced allowed participation, but the session outcome was carried by
  persistent upside continuation captured by MomentumBot.
- InverseBot struggled in the same high-transition environment, which suggests
  upside continuation and downside continuation quality may be asymmetric.
- EdgeWalker stayed selective enough to avoid re-entry chaos despite `26`
  regime transitions.
- The runtime spent most of the day managing open positions, not searching for
  new entries.

Adaptive shadow observations:

- Adaptive selected `BALANCED` for `344` cycles, `CONSERVATIVE` for `12`, and
  `AGGRESSIVE` for `1`.
- The more meaningful flat/evaluable sample was `85` Balanced, `12`
  Conservative, and `1` Aggressive. Open-position cycles mostly reflected
  paused entry-posture judgment.
- Adaptive largely agreed that Balanced doctrine fit the environment.
- Conservative shadow calls clustered around weak/new regime transitions and
  stale-bar constraints.
- The single Aggressive shadow call did not imply broad aggression; Adaptive
  remained restrained.

What worked:

- Route invalidation doctrine was materially validated. The `13`
  route-invalidated exits were net positive by about `+$813.71`.
- MomentumBot captured repeated upside continuation opportunities.
- Entry filters remained active. The day included many blocked marginal setups,
  especially ChopBot `price_above_mean` and `discount_insufficient` blocks.
- Trend Trust remained useful telemetry without becoming a hard gatekeeper.
- The operator spreadsheet auto-post workflow and config snapshot worked.

What needs attention:

- InverseBot underperformed. Do not tune from one day, but watch whether
  downside continuation remains less reliable than upside continuation.
- Route invalidation P/L should be tracked across sessions, not just exit
  counts. Today suggests it may protect gains, but repeated evidence is needed.
- Persistence telemetry remains the clearest next diagnostic frontier: how long
  did the market continue rewarding the thesis after entry?
- Narrative output must remain ledger-grounded. Bot-level counts and P/L should
  come from lifecycle metrics, not model inference.

Parked hypotheses:

- Route invalidation may be one of EdgeWalker's strongest architectural edges
  because it protects gains when thesis ownership changes.
- Balanced is effective when the market rewards upside continuation, but the
  mode label alone does not explain the result.
- MomentumBot and InverseBot may need separate persistence-quality telemetry
  rather than being treated as perfect mirror strategies.
- Future Adaptive value may show up when it disagrees with the manual mode and
  that disagreement proves correct in hindsight.

Do not change yet:

- Do not promote Balanced or alter thresholds from this green sample.
- Do not change InverseBot filters after one weak downside-continuation day.
- Do not feed Trend Trust into active entry/exit decisions yet.
- Continue Round 2 unchanged; run Aggressive tomorrow as planned.

## 2026-06-04 AAR: Live Day 1 Adaptive Mode

Qualification day: first live real-money trading day

Mode: Adaptive

Session files:

- `logs/edgewalker-2026-06-04.jsonl`
- `logs/position_lifecycle.jsonl`

Result:

- Starting account value: `$100.00`
- Ending account value: `$100.02`
- Final realized P/L: `+$0.08`
- Account impact: `+0.08%`
- Cycles: `1100` log cycles
- Closed trades: `21`
- Wins/losses: `8W / 13L`
- Win rate: `38.10%`
- Regime transitions: `32`
- Market character: `HIGH-CHURN / MIXED / TRADEABLE BUT FRAGMENTED`
- Session difficulty: `HIGH`
- Data / broker health: `28` stale cycles, `4` stream-error cycles, broker
  state remained operational, reconciliation confidence `HIGH`
- End state: flat after closeout
- Interpretation confidence: `HIGH` for live lifecycle behavior; `MEDIUM` for
  strategy conclusions because position size was intentionally tiny.

Configuration:

- Active environment: `live`
- Sizing mode: `DYNAMIC`
- Allocation: `25%` of buying power, about `$25` notional per position
- `POLL_SEC`: `20`
- Trail: `1.5%`
- Regime gap / exit gap: `0.20% / 0.10%`
- Data feed: `iex`

Bot performance:

- MomentumBot: `+$1.69`
- ChopBot: `-$0.42`
- InverseBot: `-$1.18`
- Top P/L bot: MomentumBot
- Bottom P/L bot: InverseBot

Exit reason contribution:

- Route invalidation exits: `13`, `+$0.50`
- Trailing stop exits: `7`, `-$0.63`
- Market close liquidation: `1`, `+$0.22`

Adaptive observations:

- Adaptive did not behave as a single fixed posture. After warmup, posture
  telemetry was mostly `BALANCED`, with short `CONSERVATIVE` and `AGGRESSIVE`
  windows.
- The posture distribution was coherent with the tape: frequent churn, several
  real but fragmented opportunities, and no sustained reason to remain
  Aggressive for long.
- Adaptive's first live test should be graded on whether it selected and
  executed doctrine coherently, not whether it maximized dollars on a `$100`
  account.

Main behavioral fingerprint:

- This was a live-pipe validation day more than a strategy-proof day.
- EdgeWalker placed and closed real-money trades, maintained lifecycle
  visibility, preserved reconciliation confidence, and auto-posted the daily
  row.
- The system was active enough to generate meaningful live data, but the small
  account and `25%` allocation kept mistakes bounded.
- MomentumBot again carried the net result while InverseBot remained the main
  drag, reinforcing the watch item around upside/downside continuation
  asymmetry.
- Route invalidation was net positive again, while trailing stops were net
  negative. That does not prove one doctrine is better than the other, but it
  makes exit-reason P/L one of the most valuable ongoing measurements.

Operational findings:

- The first live run exposed a spreadsheet attribution issue: a pre-open paper
  status snapshot could contaminate live daily-row account fields. This was
  fixed after the session so spreadsheet rows prefer the relevant active
  environment.
- The first live run also confirmed the need for explicit `win_rate` in the
  spreadsheet row and for a research starting-account control so live and
  replay rows can be compared at the same scale.
- `POLL_SEC=20` gave the operator a more responsive live loop than the older
  `60` second cadence. Future research comparisons should account for this
  because Research Mode currently replays one-minute bars with `next_bar_open`
  fills.

What worked:

- Live account connection, arming, order submission, fills, exits, closeout,
  reconciliation, and dashboard visibility all operated.
- Real-money exposure stayed appropriately tiny for Day 1.
- Route invalidation remained disciplined and positive on the day.
- The operator spreadsheet captured the live session, config snapshot, exit
  reason attribution, and daily narrative path.
- Research Mode is now available to compare configuration behavior on the same
  historical tape without touching the live broker path.

What needs attention:

- InverseBot remains the weakest repeated contributor and should stay on the
  watchlist. Do not remove or nerf it from one live day, but continue comparing
  downside continuation quality against MomentumBot.
- Trailing stop exits were net negative. This should be studied with MFE/MAE
  and backtest/live comparisons before changing `trail_percent`.
- The live-vs-research gap is expected in V1, but should be documented whenever
  a replay is used as evidence. Live uses real fills and a 20-second polling
  loop; Research Mode uses completed bars and `next_bar_open`.
- Win rate alone is not a sufficient score. This green day had a `38.10%` win
  rate because winners and exit reasons carried more meaning than hit rate.

Parked hypotheses:

- Route invalidation may be doing more useful work than trailing stops in
  high-churn conditions, but this needs multi-session exit-reason P/L evidence.
- Downside continuation may require different trust or persistence telemetry
  than upside continuation, even if the current bots remain doctrinal mirrors.
- `POLL_SEC=20` may improve exit awareness, but may also expose the runtime to
  more micro-churn. Compare behavior before treating lower polling cadence as
  broadly better.
- Research Mode should become the main place to test whether trail, regime gap,
  and extension controls improve persistence capture.

Do not change yet:

- Do not change core strategy thresholds from the first live day.
- Do not make Trend Trust an active gate yet.
- Do not infer Adaptive profitability from a `$0.08` live result.
- Continue using the live account primarily to prove lifecycle correctness
  while Research Mode begins measuring strategy ability.

## 2026-06-05 AAR: Live Day 2 Adaptive Mode

Qualification day: second live real-money trading day

Mode: Adaptive

Session files:

- `logs/edgewalker-2026-06-05.jsonl`

Result:

- Starting account value: `$350.02`
- Ending account value: `$334.37`
- Final realized P/L: `-$15.53`
- Account impact: `-4.44%`
- Cycles: `384`
- Closed trades: `27`
- Wins/losses: `5W / 22L`
- Win rate: `18.52%`
- Regime transitions: `28`
- Average Trend Trust: `56`
- Market character: `BEARISH CASCADE / SOXL COLLAPSE`
- Session difficulty: `EXTREME`
- Data / broker health: `0` stale cycles, `0` stream-error cycles in the
  session row; reconciliation confidence `HIGH`
- Operational note: a transient Alpaca HTTPS/TLS handshake timeout occurred
  against the open-orders endpoint. Treat as broker/API connectivity
  degradation, not a strategy or broker-rejection event.
- Interpretation confidence: `HIGH` for the loss attribution; `MEDIUM` for
  tuning conclusions until MFE/MAE and per-trade archaeology are available.

Configuration:

- Active environment: `live`
- Sizing mode: `DYNAMIC`
- Allocation: `25%` of buying power
- `POLL_SEC`: `60`
- Trail: `1.5%`
- Fast/slow SMA: `8 / 21`
- Regime gap / exit gap: `0.10% / 0.05%`
- Chop discount: `0.33%`
- Directional max extension / chase extension: `1.0% / 2.0%`
- Directional minimum strength: `STRONG`
- Adaptive shadow: `false`
- Data feed: `iex`

Bot performance:

- MomentumBot: `-$12.47`
- ChopBot: `-$0.40`
- InverseBot: `-$2.67`
- Top P/L bot: ChopBot, by losing least
- Bottom P/L bot: MomentumBot

Exit reason contribution:

- Route invalidation exits: `8`, `-$5.69`
- Trailing stop exits: `19`, `-$9.84`
- Market close liquidation: `0`, `$0.00`

Main behavioral fingerprint:

- SOXL suffered an extreme selloff, but EdgeWalker did not turn the downside
  into an InverseBot payday.
- The live loss was dominated by MomentumBot attempting upside participation
  during a broader bearish collapse and by trailing-stop losses across many
  short-lived trades.
- InverseBot was active and did participate, but its contribution remained
  negative despite the environment appearing ideal for inverse exposure.
- This was not a lifecycle failure. Orders, fills, P/L reconciliation, and
  closeout remained coherent. The failure was strategy expression inside a
  bearish-cascade environment.

Research Mode findings from the same tape:

- The live configuration produced `-4.44%` account impact.
- A more selective detector profile reduced the June 5 replay drawdown to about
  `-0.24%`:
  - Fast/slow SMA: `8 / 30`
  - Regime gap / exit gap: `0.30% / 0.05%`
  - Trail: `1.5%`
  - Chop discount: `0.33%`
  - Directional max extension / chase extension: `0.50% / 1.00%`
  - Directional minimum strength: `STRONG`
  - Cooldown: `5m`
- The same candidate stayed broadly stable across the June 1-5 replay set,
  finishing near breakeven overall rather than improving one day while breaking
  the others.
- The research result suggests the detector was too eager, but the detector is
  not the only bottleneck.

What worked:

- Live exposure was bounded enough that an extreme SOXL collapse produced a
  painful but survivable account drawdown.
- The spreadsheet row, bot attribution, exit attribution, and reconciliation
  confidence produced a usable research record.
- Research Mode quickly eliminated several hypotheses:
  - Widening the shared trail did not solve the problem.
  - Increasing exit hysteresis did not solve the problem.
  - Extension discipline materially reduced damage.

What needs attention:

- InverseBot failed its most important audition: it did not monetize a major
  SOXL collapse.
- MomentumBot needs stronger suppression or reversal proof during bearish
  cascade environments. Local upside bounces should not be treated as equal
  continuation opportunities while the broader tape is collapsing.
- Shared controls are proving blunt. A setting that helps InverseBot can damage
  MomentumBot or ChopBot, and vice versa.
- MFE/MAE and capture ratio are now the highest-value instrumentation gaps.

Parked hypotheses:

- `BigMove_v2_Candidate` / `Stability_8_30_Gap30_Ext05` may be a better
  defensive detector profile than the current live configuration, but it is not
  yet proven enough for live promotion.
- Bear Cascade may need a future environment-specific doctrine:
  suppress MomentumBot, prioritize InverseBot, require stronger bullish
  reversal proof, and let inverse continuation prove whether it can pay.
- The detector can find the avalanche. The trader layer still does not monetize
  the avalanche.

Do not change yet:

- Do not promote the candidate configuration from one evening of research.
- Do not remove or nerf InverseBot without per-trade archaeology.
- Do not change trail percent globally based on June 5; shared wider trail made
  several research variants worse.
- Next research focus: InverseBot trade archaeology, including entry timing,
  exit timing, exit reason, regime age, Trend Trust, MFE, MAE, and capture
  ratio.
