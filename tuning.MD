# EdgeWalker Tuning Log

Last updated: 2026-06-10

Initial go-live: 2026-06-04

This file turns after-action reviews into practical tuning candidates. The goal
is not to optimize from one day of evidence. The goal is to preserve behavioral
coherence, improve transparency, and identify the highest-value upgrades to
consider before and after initial live trading.

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
- Research replay reproduces the broad behavioral fingerprint of known sessions
- Lifecycle ledger, telemetry, and narrative all support the same conclusion
- Proposed change has clear acceptance criteria and bounded risk

Decision standard:

- Weak evidence can justify watching or instrumenting.
- Moderate evidence can justify controlled tests or configuration changes.
- Strong evidence can justify doctrine changes or live-risk-envelope updates.

## Research Track

Research Mode creates a parallel evidence track for comparing configurations on
the same historical tape. It should accelerate hypothesis testing without
becoming an optimizer.

Operating rules:

- Run the exact EdgeWalker bot/router/doctrine stack against historical bars.
- Use the simulated broker only; Research Mode must not call the live or paper
  order path.
- Treat research rows as experiment evidence, not trading truth.
- Compare behavioral fingerprints before trusting P/L differences.
- Do not toggle specialist bots on/off as a shortcut; compare strategy-control
  configurations first.
- Do not promote a configuration from one backtest day alone.

Validation standard:

- Baseline replay should broadly match known sessions in trade count, dominant
  bot, dominant exit reasons, regime-transition shape, and P/L direction.
- Exact P/L matching is not required in V1 because live fills, spreads, partial
  fills, and stream timing differ from bar replay.
- Research evidence becomes stronger when replay, lifecycle logs, sheet rows,
  and operator AARs tell the same story.

## Current Production Stack

As of 2026-06-10, the live candidate is no longer a single generalist preset.
It is a full-roster specialist stack:

- MomentumBot: legacy StrictAuthority remains, with the promoted Momentum Surge
  lane enabled through `MOMENTUM_SURGE_MODE=SUSTAINED`.
- ChopBot: mean-reversion specialist, guarded by
  `CHOP_PERMISSION_MODE=FIREWALL`.
- InverseBot: sustained cascade specialist enabled through
  `INVERSE_CASCADE_MODE=SUSTAINED`.
- BalancedPure: observer/probe only, no execution rights.

Working doctrine:

- A specialist must earn its habitat before it can trade.
- Failing closed is acceptable when a required data anchor is missing.
- No-trade behavior is a success case when the tape does not match a validated
  lane.
- Specialist improvements should be judged by roster-level impact, not by
  isolated bot P/L alone.

Latest rolling YTD reference from a `$350` starting balance:

- Candidate at `25%`: ending equity about `$390.01`, `+11.43%`, max drawdown
  about `1.72%`.
- Prior baseline at `25%`: ending equity about `$379.96`, `+8.56%`, max
  drawdown about `2.35%`.
- Candidate at `95%`: ending equity about `$522.71`, `+49.35%`, max drawdown
  about `6.51%`.
- Prior baseline at `95%`: ending equity about `$473.78`, `+35.37%`, max
  drawdown about `8.77%`.

Research caveat: these are replay results, not expected live returns. They are
evidence that the specialist stack improved the historical fingerprint without
raising drawdown in the tested YTD window.

Current V1 assumptions:

- Historical data source: Alpaca one-minute bars.
- Perception model: completed prior bars.
- Fill model: `next_bar_open`.
- Slippage: explicit basis-point field.
- Output: research spreadsheet rows without daily narrative generation.
- Research rows should be compared to live rows by behavioral fingerprint
  before P/L, especially when live `POLL_SEC` is below `60` and replay cadence
  remains one-minute bars.
- Research rows should capture an explicit starting account so P/L, bot P/L,
  and exit-reason P/L can be scaled consistently against live rows.

## Environmental Classification Research

Working concept:

```text
Regime = local direction
Environment = reward structure around regimes
Posture = willingness to participate
Config = how the system expresses that willingness
```

The regime engine should remain the first sensor. It answers whether the local
structure is UPTREND, DOWNTREND, or SIDEWAYS. Environmental classification is a
layer above that sensor. It should interpret regime history, exit behavior,
post-entry movement, and data quality to answer a different question:

```text
Is this market currently rewarding continuation, reversal, or patience?
```

Do not start by inventing hard labels like bull, bear, or sideways. Build
fingerprints first, collect them across live and research sessions, then name
recurring clusters only after the data earns those names.

Candidate fingerprint fields:

- `regime_transitions`
- `avg_regime_duration_minutes`
- `median_regime_duration_minutes`
- `max_regime_duration_minutes`
- `transitions_per_hour`
- `session_trend_trust_avg`
- `route_invalidation_rate`
- `route_invalidation_pl`
- `early_entry_percent`
- `regime_age_at_entry_avg`
- `avg_mfe_percent`
- `avg_mae_percent`
- `momentum_avg_mfe`
- `momentum_avg_mae`
- `inverse_avg_mfe`
- `inverse_avg_mae`
- `chop_avg_mfe`
- `chop_avg_mae`
- `trade_count`
- `win_rate`

Rolling scopes:

- Session fingerprint
- 60-minute fingerprint
- 30-minute fingerprint
- Open-position context

The goal is to avoid treating a full day as one static state. A session can
begin hostile, become tradeable, and deteriorate again. Environmental telemetry
should eventually be able to detect those shifts.

Profitable Persistence:

```text
Profitable Persistence =
post-entry favorable movement before invalidation or exit
```

Recent evidence suggests EdgeWalker often enters real regimes. The harder
question is whether those real regimes produce enough favorable continuation to
pay for participation, noise, spread, trail behavior, and route invalidation.
MFE/MAE telemetry is the next required instrument for this question.

Implementation order:

1. MFE/MAE tracking
2. Capture ratio
3. Closed-trade record enrichment
4. InverseBot trade archaeology
5. Strategy preset save/load
6. Lightweight preset comparison matrix
7. Environmental Fingerprint Telemetry
8. Manual labels in AAR and spreadsheet notes
9. Research Mode cluster comparison
10. Shadow environment classification
11. Shadow config selector
12. Active config routing later

Manual labels should be observational, not predictive. Useful starting labels
may include `TRADEABLE_TREND`, `HOSTILE_CHURN`, `TRADEABLE_CHURN`,
`RANGE_REVERSION`, and `DIRECTIONAL_TRAP`, but those names should remain
provisional until repeated fingerprints support them.

Authority boundary:

- Environmental classification is research-only for now.
- It should not mutate live strategy controls.
- It should not override hard safety doctrine.
- It should not promote a configuration from one session or one replay.
- It can inform AARs, spreadsheet notes, Research Mode comparisons, and future
  shadow recommendations.
- No AI/LLM layer is part of the current environment-classification plan.
  Keep the near-term classifier deterministic and evidence-based.

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

## Emerging Themes

These are recurring observations that have graduated beyond single-session
notes, but have not yet become approved tuning decisions.

- Trend Trust appears more predictive than raw trend strength.
- Regime age may be underrepresented in current confidence calculations.
- Churn count alone is insufficient to explain performance.
- The next conceptual layer is environmental classification: not whether the
  market is up/down/sideways, but whether it is rewarding continuation,
  reversal, or patience.
- Profitable Persistence may be the missing link between real regimes and
  profitable regimes.
- Route invalidation exits dominate realized outcomes on churny sessions.
- Route invalidation P/L may be more important than route invalidation count.
  June 2 showed `13` route-invalidated exits with about `+$813.71` net P/L,
  suggesting the doctrine may protect gains when thesis ownership changes.
- MomentumBot and InverseBot should not be assumed to be perfect mirror
  strategies. Upside continuation quality and downside continuation quality may
  differ materially across sessions.
- Adaptive appears disciplined, but may lack regime-maturity awareness.
- Adaptive shadow should be interpreted on flat/evaluable cycles first. While a
  position is open, posture telemetry often reflects paused entry-posture
  judgment rather than an independent mode-selection opinion.
- `POLL_SEC` may be an exit-quality and perception lever rather than an
  entry-quality lever.
- `POLL_SEC=20` produced a clean first live run and much higher cycle count, but
  should be treated as a measurement/timing variable until replay/live
  comparisons show whether faster polling improves exits or increases
  micro-churn sensitivity.
- Live operational success is not the same as strategy edge. The first live day
  proved real-money lifecycle capability; Research Mode and future sessions
  still need to measure repeatable ability.
- Exit-reason P/L is more diagnostic than exit counts. June 4 showed route
  invalidation net positive and trailing stops net negative on the same live
  tape, making MFE/MAE and exit-quality telemetry higher-value than raw win
  rate.
- June 5 Research Mode produced the first materially useful detector candidate:
  `8/30`, `0.30/0.05`, `STRONG`, with `0.50/1.00` extension discipline. It
  reduced crash-day drawdown without breaking the June 1-4 replay set.
- The global detector is no longer the only suspect. Once detector eagerness is
  reduced, InverseBot participation quality becomes the visible bottleneck.
- Shared controls may be too blunt for collapse environments. A setting can
  help InverseBot while harming MomentumBot or ChopBot, which points toward
  future environment-specific or bot-specific doctrine.
- Research Mode now provides evidence against a single universal best
  configuration. `Lead_Generalist`, `Lead_Momentum_Specialist`, and
  `Lead_Inverse_Specialist` each fit different tapes, while
  `Bear_Capture_Trail_075` looked promising in-sample and then failed the May
  out-of-sample batch.
- The first 20-date preset comparison matrix found
  `Lead_Momentum_Specialist` as the aggregate leader, but not as a universal
  replacement. `Lead_Generalist` remains the default anchor and
  `Lead_Inverse_Specialist` remains the high-cost downside specialist candidate.
- Candidate labels should remain role-based and provisional. The current
  research roles are Generalist, Momentum specialist, and Inverse specialist.
  A Chop/range specialist has not yet earned a slot.
- InverseBot is no longer merely an archaeology subject. The sustained cascade
  lane earned promotion by separating true SOXL cascade days from gap-down
  recovery fakes and by fixing cascade-specific exit behavior.
- MomentumBot was not fixed by simply loosening the old bot. It needed a new
  surge lane with its own proof conditions, mutual isolation from InverseBot,
  and YTD/rolling-equity validation.
- Previous-session close has become a core specialist anchor. The current live
  path fetches it lazily and fails closed when unavailable; preloading it during
  startup/warmup is the next operational hardening item.
- "PatienceBot" is the correct operator framing for the default system: the
  roster should wait for qualified lanes rather than manufacture activity.
- Specialist discovery and environment fingerprinting should inform each other.
  Do not force a four-lane taxonomy before same-date preset comparisons show
  that all four lanes are materially distinct.
- Win rate is contextual. June 4 finished green with a `38.10%` win rate
  because bot-level and exit-reason P/L mattered more than hit rate.
- Live and research rows must preserve their assumptions. Live rows include
  broker fills, stream/data imperfections, and poll cadence; research rows use
  completed bars and the configured fill model.
- Regular-session warmup integrity is a doctrine question, not just a data
  hygiene issue.
- Human-facing label: route invalidation exit. Current internal code:
  `stale_position_regime_mismatch`.

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

## 2026-05-29 After-Action Review

Session: qualification day 4, Adaptive mode

Cycles: 385

Result: 16 completed trades. Account value moved from about $99,404.27 to
$99,379.25, roughly -$25.02. Lifecycle summary reported -$25.03, so account and
lifecycle movement reconciled cleanly.

Session identity:

- Micro-trend/chop day with frequent boundary-driven regime changes.
- Regime transitions remained high at 34, roughly one change every 11 minutes.
- Adaptive finished essentially flat despite a `3W / 13L` trade distribution.
- One persistent InverseBot thesis nearly offset fifteen route-invalidation
  exits.

Bot behavior:

- MomentumBot: `-$369.28`, 7 trades, 2 wins and 5 losses.
- ChopBot: `-$23.21`, 2 trades, 0 wins and 2 losses.
- InverseBot: `+$367.46`, 7 trades, 1 win and 6 losses.
- The highest-impact exit was one trailing-stop breach for about `+$1,025.75`.
- Fifteen route-invalidation exits totaled about `-$1,050.77`.

What worked:

- Adaptive stayed disciplined and did not over-escalate aggression.
- Aggressive posture appeared only twice.
- Conservative posture appeared during stale-bar entry-block conditions and
  weak directional regimes.
- Broker state stayed clean and the partial-fill opposite-side rejection did
  not repeat.
- Lifecycle P/L and account movement reconciled cleanly.

What needs attention:

- Adaptive selected reasonable posture from current regime strength, but most
  entries occurred in very young regimes.
- Of 16 entries, 14 occurred within about 3 minutes of the active regime
  beginning, and all 16 occurred within 10 minutes.
- Median regime age at entry was about 1 minute.
- Current-day premarket bars appeared in the opening warmup cache, creating a
  partially formed opening opinion before enough regular-session bars existed.
- Logs repeatedly showed live quotes/trades while bars were stale: live market,
  stale interpretation.

Behavioral assessment:

Adaptive mode passed its first active qualification day operationally. It did
not prove profitability, but it showed coherent posture selection, clean broker
behavior, and controlled participation. The major diagnostic lesson is that
regime strength and regime trustworthiness are separate dimensions.

Evidence strength:

- Strong evidence for keeping Adaptive under observation rather than judging it
  by one near-flat day.
- Strong evidence that Trend Trust telemetry should include regime age and
  recent churn pressure.
- Moderate evidence that route-invalidation exits need outcome classification.
- Moderate evidence that regular-session warmup integrity should be explicit.
- Weak evidence for changing regime thresholds, trail percent, ChopBot
  discount, or Adaptive posture rules.

## June 5 Research Findings

Research Mode produced two distinct findings after the June 5 SOXL collapse.

Discovery 1: the detector was too eager.

The live June 5 configuration was:

- Fast/slow SMA: `8 / 21`
- Regime gap / exit gap: `0.10% / 0.05%`
- Trail: `1.5%`
- Chop discount: `0.33%`
- Directional max extension / chase extension: `1.0% / 2.0%`
- Directional minimum strength: `STRONG`

Live result:

- Account impact: `-4.44%`
- Closed trades: `27`
- Win rate: `18.52%`
- MomentumBot: `-$12.47`
- ChopBot: `-$0.40`
- InverseBot: `-$2.67`

First materially useful detector candidate found at that point:

```text
Name: BigMove_v2_Candidate / Stability_8_30_Gap30_Ext05
Mode: ADAPTIVE
Trail: 1.5%
Fast SMA: 8
Slow SMA: 30
Regime Gap: 0.30%
Regime Exit Gap: 0.05%
Chop Discount: 0.33%
Max Extension: 0.50%
Strong Chase Extension: 1.00%
Min Strength: STRONG
Cooldown: 5 minutes
```

June 5 replay result:

- Account impact: about `-0.24%`
- Closed trades: `23`
- Win rate: `43.48%`
- MomentumBot: `-$1.59`
- ChopBot: `+$0.58`
- InverseBot: `+$0.18`

June 1-5 replay smoke test:

- June 1: `+0.41%`
- June 2: `-0.29%`
- June 3: `-0.32%`
- June 4: `+0.10%`
- June 5: `-0.24%`
- Aggregate: roughly `-0.34%`

Observed effects:

- Reduced trade frequency.
- Reduced MomentumBot losses during the collapse tape.
- Improved June 5 crash-day behavior materially.
- Preserved broadly similar behavior across June 1-4.
- Did not turn the collapse into an InverseBot payday.

Discovery 2: InverseBot is now the visible bottleneck.

Research Mode made the detector calmer. Once the detector improved, the
remaining limitation became clearer: InverseBot still did not monetize a major
SOXL collapse.

Key conclusion:

```text
The detector can find the avalanche.
The trader layer does not yet monetize the avalanche.
```

Next research focus:

- InverseBot trade archaeology.
- Participation-quality analysis.
- MFE/MAE and capture ratio.
- Bear Cascade environmental fingerprinting.

Research question:

```text
Does InverseBot fail because it enters poorly, exits poorly,
or because downside continuation requires different participation doctrine
than upside continuation?
```

Authority boundary:

- Save the candidate configuration as a research preset.
- Do not promote it directly to live from one evening of research.
- Do not remove or nerf InverseBot before per-trade evidence exists.
- Do not widen trail globally from June 5; shared wider-trail variants worsened
  the whole-system result.

## June 7 Research Findings

Research Mode moved from single-tape tuning into same-date candidate comparison.
The main lesson was that EdgeWalker is unlikely to have one universally best
configuration across the sampled tapes.

### Retired Stepping Stone: Bear_Capture_Trail_075

The `Bear_Capture_Trail_075` candidate used the calmer `8/30`,
`0.30% / 0.05%`, `STRONG`, `0.50% / 1.00%` detector with a `0.75%` trail.

It was useful because it:

- Reduced June 5 damage materially.
- Helped reveal that a lower trail could improve capture on a crash tape.
- Led to the discovery of a better bear/strong-move detector shape.

It should not be promoted because:

- It failed the fresh May 18-28 out-of-sample batch.
- It remained weak for InverseBot across broader samples.
- It appears to be a research stepping stone, not a durable specialist.

### Generalist Anchor: Lead_Generalist

Current role:

```text
Generalist / lower-variance anchor
```

Configuration identity:

- Trail: `1.5%`
- Fast/slow SMA: `8 / 21`
- Regime gap / exit gap: `0.10% / 0.05%`
- Chop discount: `0.33%`
- Directional max extension / chase extension: `1.0% / 2.0%`
- Directional minimum strength: `STRONG`

Research read:

- Survived the May 18-28 out-of-sample batch better than
  `Bear_Capture_Trail_075` and the pre-rename inverse specialist candidate.
- Still has tail-risk days, especially hostile churn and crash tapes.
- Remains the current default/generalist control unless a candidate beats it
  across broader same-date comparisons.

### Inverse Specialist Candidate: Lead_Inverse_Specialist

Current role:

```text
Inverse / downside-damage specialist candidate
```

Configuration identity:

- Trail: `0.75%`
- Fast/slow SMA: `8 / 24`
- Regime gap / exit gap: `0.25% / 0.05%`
- Chop discount: `0.33%`
- Directional max extension / chase extension: `0.50% / 1.00%`
- Directional minimum strength: `STRONG`

Research read:

- First candidate that made June 5's SOXL collapse become an InverseBot payday
  in replay.
- Made InverseBot net positive across the initial control set.
- Failed the May 18-28 out-of-sample batch as a general replacement.
- Should be treated as an environment-specific specialist candidate, not a live
  default.

### Momentum Specialist Candidate: Lead_Momentum_Specialist

Current role:

```text
Momentum / upside-trend participation specialist candidate
```

Configuration identity:

- Trail: `1.5%`
- Fast/slow SMA: `8 / 30`
- Regime gap / exit gap: `0.20% / 0.05%`
- Chop discount: `0.33%`
- Directional max extension / chase extension: `0.75% / 1.50%`
- Directional minimum strength: `MODERATE`

Research read:

- Beat `Lead_Generalist` on the May 18-28 batch.
- Produced large wins on clean trend/upside participation days.
- Failed hard on hostile or bearish tapes such as June 3, June 5, and May 18.
- Should be treated as a high-upside specialist, not a safe generalist.

### Chop / Range Specialist Status

`Range_CHOP_v1` did not earn a specialist slot.

Research read:

- It improved some ChopBot contribution but did not prove a distinct range
  doctrine.
- Some of its better days were still driven mostly by MomentumBot or
  InverseBot.
- The Chop/range lane remains unknown. It may become a true ChopBot specialist,
  a defensive low-participation preset, or no separate lane at all.

### First Preset Comparison Matrix

The first full comparison matrix ran `60` replay runs: `3` saved presets across
`20` dates, using `Next Bar Open` fills and `0 bps` slippage.

Aggregate result:

| Preset | Total P/L | Avg % | Date Wins | Green/Red | Momentum | Chop | Inverse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Lead_Momentum_Specialist` | `$2.83` | `+0.14%` | `8` | `10/8` | `$3.29` | `$1.66` | `-$2.10` |
| `Lead_Generalist` | `-$0.16` | `-0.01%` | `7` | `11/9` | `$0.24` | `-$0.71` | `$0.31` |
| `Lead_Inverse_Specialist` | `-$2.57` | `-0.13%` | `5` | `9/10` | `-$1.77` | `-$0.51` | `-$0.24` |

Research read:

- `Lead_Momentum_Specialist` led the aggregate batch, but still failed hard on
  June 3 and June 5. It is a specialist candidate, not a live default.
- `Lead_Generalist` did not win the aggregate, but remained a viable default
  anchor and won important mixed tapes such as June 1 and June 2.
- `Lead_Inverse_Specialist` did not win the aggregate, but won the highest
  misclassification-cost downside tapes: June 3 and June 5.
- Every `Lead_Momentum_Specialist` date win in this batch had `30m Trans/hr = 0`.
  That is the first concrete early-window routing clue, not a routing rule.
- The highest wrong-choice cost was June 5: choosing the wrong preset instead
  of `Lead_Inverse_Specialist` cost up to `$3.25` on a `$100` replay account.

Current research hypothesis:

```text
Quiet first 30 minutes / low early transition pressure
=> Momentum specialist may fit.

Mixed or ambiguous tape
=> Generalist remains the safer anchor.

High downside damage risk / hostile continuation
=> Inverse specialist may be the needed defensive lane.
```

This remains research-only. The comparison matrix is evidence for future shadow
routing, not live routing authority.

### Next Research Priority

Use the preset comparison and environment-fingerprint frame to evaluate more
date batches before active routing.

Required comparison fields:

- Date
- Preset
- Total P/L
- Bot P/L
- Trade count
- Win rate
- Route invalidation P/L
- Trailing stop P/L
- Session and bot-level MFE/MAE/capture
- Winner per date
- Full-session versus partial-session marker

Required early-window questions:

- What did the first 30 minutes look like?
- What did the first 60 minutes look like?
- How early could a deterministic fingerprint have selected the winning preset?
- What would misclassification have cost?

Authority boundary:

- Do not build active routing yet.
- Do not force the final taxonomy to be UP / DOWN / CHOP / GENERAL until the
  data proves those lanes are real.
- Do not promote a specialist from one in-sample cluster.
- Use same-date preset comparison as the guardrail before naming environments
  or giving any selector live authority.

## Measurement Sprint: Trade Behavior Analyzer

Goal:

```text
Turn EdgeWalker from trade result logger
into trade behavior analyzer.
```

This sprint should not make EdgeWalker smarter yet. It should make each trade
more inspectable so future tuning can distinguish bad entries, bad exits,
missed capture, and unsuitable doctrine.

Hard rule:

- No live behavior changes.
- No strategy-threshold changes.
- No InverseBot doctrine changes.
- No active environment classifier.
- No AI/LLM selector layer.

Build order:

### P0 - MFE/MAE Per Trade

Record maximum favorable excursion and maximum adverse excursion for every
open position from entry through exit.

Definition:

- MFE is the highest favorable price reached during the position lifetime.
- MAE is the worst adverse price reached during the position lifetime.
- Both are measured from the actual fill price, not the entry-intent price.
- The position lifetime begins at fill and ends at exit.
- Research Mode must only use bars visible during the simulated position
  lifetime. It must not inspect bars after the exit.
- V1 should record the excursion source explicitly. Research Mode starts with
  completed-bar MFE/MAE for replay honesty and live/research parity. Live
  quote/trade-based excursion can be added later as a separate metric if useful.

Why:

- Reveals whether a trade ever found opportunity.
- Distinguishes immediate bad entries from good entries with poor capture.
- Gives InverseBot analysis the missing facts from June 5.

### P0 - Capture Ratio

Derive capture quality from realized P/L versus available favorable excursion.

Priority:

- Bot-level capture ratio is more diagnostic than session-level capture ratio.
- Session-level capture ratio can be summarized later, but the first consumers
  should be MomentumBot, InverseBot, ChopBot, and exit-reason groupings.

Diagnostic reads:

- If MFE is near zero, the thesis never developed.
- If MFE is meaningful but capture ratio is low, the trade found opportunity
  but exit/capture behavior failed to preserve enough of it.
- If MFE is meaningful, capture ratio is reasonable, and P/L is still negative,
  MAE may be too large relative to MFE.

Why:

- Converts raw MFE into an exit-quality judgment metric.
- Helps separate "no opportunity existed" from "opportunity existed but was
  not captured."

### P1 - Closed-Trade Record Enrichment

Persist trade-quality facts with every closed trade, including bot owner, entry
context, exit context, regime age, Trend Trust, MFE, MAE, capture ratio, and
exit reason.

Include hold duration while the lifecycle ledger is being enriched. Hold
duration by bot and exit reason helps distinguish fast reversals from slow
bleeds, especially for InverseBot.

Why:

- Makes the daily row and AAR less dependent on ad hoc log archaeology.
- Lets Research Mode compare candidates by behavior, not just P/L.

### P1 - InverseBot Archaeology Report

Use enriched closed trades to answer whether InverseBot fails from poor entry,
poor exit/capture, or downside-continuation doctrine mismatch.

Output discipline:

- The report should end with ranked hypotheses to test in Research Mode, not
  immediate live changes.
- Example output shape: "Hypothesis: InverseBot bearish-continuation entries
  show meaningful MFE but poor capture during Bear Cascade tapes."

Why:

- June 5 showed that detecting a bearish cascade is not the same as monetizing
  it.
- InverseBot should be evaluated separately from MomentumBot rather than
  treated as a perfect mirror.

### P2 - Strategy Preset Save/Load

Preserve discovered configurations such as
`BigMove_v2_Candidate / Stability_8_30_Gap30_Ext05`.

Preset records should preserve context, not just numeric controls:

- Name
- Status
- Created/discovery date
- Config snapshot
- Discovery context
- Tested dates
- Aggregate result / cross-date P/L summary
- Evidence summary
- Operator notes

Why:

- Presets preserve knowledge.
- MFE/MAE creates knowledge.
- If sprint bandwidth gets tight, ship MFE/MAE and capture ratio cleanly before
  shipping presets.

Success criteria:

- Every closed trade can say whether it found favorable excursion.
- Every closed trade can say how much of that excursion was captured.
- Every closed trade records hold duration.
- InverseBot can be analyzed without manually reading every lifecycle line.
- InverseBot archaeology returns testable hypotheses rather than doctrine
  changes.
- Research rows and AARs can discuss trade quality, not only trade result.

## P0 Candidates Before / After Initial Go-Live

### 0. InverseBot Trade Archaeology And MFE/MAE

Observation:

- June 5 was an extreme bearish SOXL session, yet InverseBot finished negative
  live and only slightly positive in the best same-day research variant.
- Research Mode made the detector calmer, but did not turn the bearish cascade
  into an inverse payday.

Need:

- Entry time
- Entry price
- Exit time
- Exit reason
- Exit price
- Regime age at entry
- Trend Trust at entry
- MFE
- MAE
- Capture ratio
- Bot owner
- Environment fingerprint

Acceptance criteria:

- For each closed trade, EdgeWalker can say whether the trade failed because it
  never moved favorably, moved favorably but was not captured, or was
  invalidated before continuation could pay.
- InverseBot can be evaluated separately from MomentumBot instead of being
  treated as a perfect mirror.
- Research Mode can compare detector candidates by participation quality, not
  only final P/L.

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
- `Scorecard`
- `What The Logs Support`
- `Bot Behavior`
- `Operational Health`
- `Behavioral Assessment`
- `Interpretation`
- `Watchlist`
- `Bottom Line`
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

- Narrative separates facts, interpretation, operational health, watchlist, and
  confidence instead of blending them into a generic prose recap.
- Narrative explicitly states the active mode and whether Adaptive was active or
  shadow-only.
- Narrative distinguishes execution health from data health, especially when
  stale bars were observed but safely handled.
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

Status: initial implementation complete; continue measuring

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

- [x] End-of-day summary shows whether stale-bar cycles occurred.
- [x] Stale data is reported as a handled guardrail, not as silent non-trading.
- [ ] Future enrichment: total stale duration, max bar age, and average bar age.

### 5. Add Regime Churn Metrics

Status: initial implementation complete; continue measuring

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

- [x] Daily summary includes regime-transition count and Trend Trust averages.
- [ ] Future enrichment: average regime hold time, short-lived regime count,
  hysteresis hold count, and route changes per hour.
- [ ] Threshold changes are based on measured churn, not vibes.

### 6. Preserve Stale-Exposure Doctrine

Status: preserve

Impact: high

Why:

The `close_stale_position_no_same_cycle_reversal` behavior is a constitutional
safety rule. It prevents immediate reversal chaos when ownership no longer
matches the active regime.

Implemented / recommended action:

- Keep the rule.
- Promote it to a named policy event. Initial human-facing label:
  `route_invalidated_exit`.
- Include it in the daily behavioral assessment whenever it triggers.

Acceptance criteria:

- [x] Route-invalidation exits are easy to distinguish from strategy exits.
- [x] Same-cycle reversal blocks are visible as policy, not as missing trades.
- [ ] Future enrichment: classify whether each exit became a defensive save,
  premature cut, profitable handoff, or neutral exit.

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

Status: implemented for current qualification needs; continue watching

Impact: high

Why:

Aggressive day produced two broker-rejected exit attempts while an opening buy
order was still partially filling. The initial open-buy sell guard has been
implemented so same-symbol exits wait while a buy order is still open.
`OPENING`, `OPEN`, `CLOSING`, and `CLOSED` are now materially visible in the
order-flow lifecycle state.

Candidate behavior:

- Preserve the implemented guard that avoids opposite-side market exits while a
  same-symbol buy order is still open.
- Surface an `OPENING` state when entry fill reconciliation is incomplete.
- Keep risk logic aware that a partially filled position exists, but avoid
  broker-rejected opposite-side orders.
- Escalate repeated partial-fill exit blockage as an operator-visible
  interrupt.

Acceptance criteria:

- [x] Partial entry fills do not create repeated rejected exit attempts.
- [x] The dashboard shows when a position is opening, open, closing, or closed.
- [ ] Continue watching whether repeated partial-fill blockage needs an
  operator interrupt.

### 9. Tighten Broker Rejection And P/L Truth

Status: initial implementation complete; continue reconciling

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

- [x] Broker rejection categories distinguish partial-fill/opposite-side
  conflicts from buying-power limits.
- [x] P/L summaries expose reconciliation confidence and notes.
- [ ] Continue watching account movement versus lifecycle realized P/L around
  partial fills.

### 10. Regular-Session Warmup Integrity

Status: implemented

Impact: medium-high

Why:

Adaptive day opened with `12 / 20` bars already present at `09:30:01 ET`; the
latest bar was from `09:24 ET`. That implies same-day premarket bars can enter
the warmup cache. This is not necessarily wrong, but it should be explicit. If
EdgeWalker is modeling regular-session behavior, the first actionable regime
should be based on regular-session bars.

Candidate behavior:

- Add an explicit setting or doctrine for whether warmup includes premarket
  bars.
- Default regular-session trading to regular-session warmup bars only.
- Keep premarket context available as separate telemetry if useful.
- Log the warmup source: `regular_session`, `premarket_included`, or `mixed`.

Acceptance criteria:

- [x] Regular-session trading uses regular-session warmup bars only.
- [x] A regular-session strategy does not accidentally start from a mixed
  premarket/regular opinion.
- [ ] Future enrichment: expose warmup source explicitly in the UI/log summary.

### 11. Stale-Bar Repair / Backfill Investigation

Status: initial implementation complete; continue watching

Impact: high

Why:

The logs show a recurring state where quotes and trades are live while bars are
stale. That means the live market is visible for mark/risk purposes, but the
bar-based interpretation pipeline is temporarily frozen. Current behavior
correctly blocks entries, but repeated stale-bar pauses reduce decision quality
and operator trust.

Candidate behavior:

- Add session metrics for "live market, stale interpretation" cycles.
- When bars are stale but quote/trade data is live, attempt a bounded REST
  backfill of recent one-minute bars.
- Record whether backfill repaired the stream cache or failed.
- Keep entries blocked until bar freshness is restored.
- Preserve live quote/trade marks for open-position risk management.

Acceptance criteria:

- [x] Stale-bar episodes are summarized by count and backfill repair path.
- [x] The system distinguishes stream disconnect from bar aggregation lag.
- [x] Entry decisions remain blocked during stale interpretation.
- [x] Open-position risk management can continue from live quote/trade marks.
- [ ] Future enrichment: stale duration and max/average bar age.

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

Naming note:

- Human-facing label: route invalidation exit.
- Current internal code: `stale_position_regime_mismatch`.
- Do not rename the internal code until logs, tests, docs, and narrative
  prompts can move together.

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

### 5. Trend Trust, Directional Persistence, And Session Difficulty Telemetry

Status: watch

Why:

Balanced day and Aggressive day had similar regime-transition counts but very
different outcomes. Adaptive day added a stronger clue: most entries occurred
in regimes that were only about one minute old. Churn count alone is not the
causal explanation. The system needs to measure whether a trend deserves trust,
not only whether a trend appears to exist.

Potential metrics:

- Regime age at entry.
- Regime flips over the last 15, 30, and 60 minutes.
- Post-entry follow-through over 5, 15, and 30 minutes.
- Max favorable excursion and max adverse excursion per trade.
- Directional efficiency, such as net movement divided by total movement.
- Time spent in current regime versus time spent near boundary thresholds.
- Session difficulty score based on churn, volatility, persistence, and
  reversal frequency.

Watch:

- Whether continuation entries work only after regimes have proven enough age.
- Whether high local churn should lower Adaptive confidence.
- Whether session difficulty explains mode performance better than raw churn.
- Whether Adaptive should distinguish strong-but-immature signals from
  moderate-but-stable signals.
- Whether Trend Trust should become a visible operator metric or remain a
  behind-the-scenes confidence input.

### 6. Dynamic Controls Within Operator Rails

Status: watch / instrument first

Why:

Adaptive posture selection answers which doctrine fits the environment.
Dynamic Controls would answer how tightly the runtime should operate inside the
operator-approved envelope. This should not mean automatic strategy mutation or
unbounded self-optimization. It should mean bounded runtime adaptation for
tempo, risk, and exit precision.

Doctrine:

- Operator settings define the allowed rails.
- Dynamic Controls may move selected values within those rails.
- Constitutional safety rules remain hardcoded and non-negotiable.
- All dynamic recommendations should run in shadow before active use.
- Every recommendation should include the proposed value, prior value, reason,
  confidence, and active constraints.

Best early candidates:

- `POLL_SEC`, especially while a position is open.
- Trail sensitivity or trail ratchet behavior.
- Cooldown duration.
- Position sizing cap inside the existing max allocation.

Handle carefully:

- Continuation strictness.
- Chase allowance.
- ChopBot discount threshold.
- Regime hysteresis or confirmation windows.

Do not dynamically mutate for now:

- Stale-exposure flattening doctrine.
- No same-cycle reversal policy.
- Broker and lifecycle guards.
- Live max allocation hard caps.
- Closeout safety requirements.

Potential shadow logs:

```text
[DYNAMIC] would_set poll_sec=15 previous=60 reason=position_open_profit_expanding confidence=HIGH constraints=within_operator_rails
[DYNAMIC] would_set trail_pct=1.4 previous=1.8 reason=high_churn_short_regime_age confidence=MODERATE constraints=within_operator_rails
[DYNAMIC] would_set cooldown=8m previous=5m reason=recent_reversal_cluster confidence=LOW constraints=shadow_only
```

Watch:

- Whether faster polling would have ratcheted trailing exits sooner.
- Whether delayed exit checks gave back meaningful max favorable excursion.
- Whether lower `POLL_SEC` improves exit precision without creating noise-driven
  churn.
- Whether dynamic recommendations remain stable and explainable across
  sessions.
- Whether `POLL_SEC` is better treated as an exit-precision setting than an
  entry-logic setting while regimes remain one-minute-bar based.

## Deferred Architecture Candidate: Event-Driven Signal/Risk Split

Status: defer until the current live build has about a week of evidence.

Current bridge:

- Flat / no pending order: scan on the configured bar-aligned cadence.
- Open position or pending order: scan every `5s` for tighter bot-managed exit
  handling and broker reconciliation.

Concept:

- Completed one-minute bars should trigger signal evaluation.
- Live quote/trade ticks should trigger open-position risk checks.
- Broker fills and lifecycle records should remain the source of truth for
  whether an entry, pending order, open position, or exit is active.

Why this waits:

- It is architecturally sound, but it changes the control model from one simple
  loop into coordinated entry, risk, and reconciliation loops.
- The first live-session fire was latency around bot-managed exits; the active
  `5s` scan directly addresses that without changing entry doctrine.
- We need live evidence before deciding whether event-driven risk checks are
  necessary, and what exact failure modes they must solve.

Watch:

- Trail-trigger overshoot after active scan deployment.
- Capture ratio on live trailing-stop exits.
- Duplicate-order or pending-order edge cases during fast risk scans.
- Whether 5-second active scans are sufficient in normal live volatility.

## Go-Live Readiness Checklist

- [ ] Fresh-cross doctrine explicitly accepted or revised.
- [x] Stale-bar telemetry summarized per session.
- [x] Regime churn metrics summarized per session.
- [ ] Daily narrative includes behavioral assessment.
- [ ] Daily narrative includes narrative confidence.
- [x] Stale-exposure exits are named policy events.
- [x] Initial open-buy sell guard prevents repeated opposite-side sell attempts
  while a same-symbol buy order is still open.
- [x] Opening, open, closing, and closed lifecycle states are visible to the
  operator.
- [x] Broker rejection classification distinguishes buying-power limits from
  opposite-side or wash-trade conflicts.
- [x] Lifecycle P/L reconciliation confidence is visible.
- [ ] Continue comparing lifecycle P/L, fill-paired P/L, and account movement
  around partial fills.
- [x] Opening warmup policy explicitly includes or excludes premarket bars.
- [x] Stale-bar episodes distinguish stream failure from
  live-market/stale-interpretation lag.
- [ ] Live risk envelope is configured and visible.
- [x] Live trading remains explicitly armed, typed-confirmation gated, and easy
  to disarm.
- [ ] Final closeout state is clear: flat, stopped, and rearmed for next day.
- [x] First live-money lifecycle proof completed with `HIGH` reconciliation on
  2026-06-04.
- [x] Operator spreadsheet environment attribution hardened after the first
  live row exposed a mixed paper/live snapshot issue.
- [x] Spreadsheet rows include `win_rate` plus full config snapshot for live
  and research comparison.
- [x] Add MFE/MAE telemetry so route invalidation, trailing stops, and market
  close exits can be evaluated against missed or protected excursion.

## Non-Goals For Now

- Replay UI.
- Multi-day strategy optimization.
- Unbounded automatic parameter mutation.
- Active Dynamic Controls before shadow evidence exists.
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

2026-05-29:

- Added Dynamic Controls as a future bounded-adaptation concept.
- Recorded that `POLL_SEC` may be a perception and exit-precision setting, but
  should be instrumented before active tuning.
- Clarified that any dynamic values should stay inside operator-approved rails
  and run in shadow before production use.

2026-05-30:

- Added the Adaptive qualification day AAR.
- Promoted regime age and Trend Trust telemetry as the main diagnostic lesson
  from Adaptive day.
- Added regular-session warmup integrity as a pre-live observability/doctrine
  candidate.
- Added stale-bar repair/backfill investigation around the "live market, stale
  interpretation" state.

2026-05-31:

- Completed the weekend observability sprint before qualification round 2.
- Implemented regular-session-only warmup, bounded stale-bar REST backfill,
  visible position lifecycle states, partial-fill conflict classification, and
  P/L reconciliation confidence.
- Added shadow Trend Trust telemetry and structured session metrics without
  feeding them into active decisions.
- Added route-invalidation exit labeling and lifecycle context for later
  defensive-save / premature-cut / profitable-handoff classification.
- Added dashboard operator polish: entry price plus trail exit comparison,
  protected-position state, one-time `Position_secured.wav` cue, and copy icon.
- Strategy thresholds, Adaptive logic changes, and active Dynamic Controls
  remain intentionally parked until more evidence exists.

2026-06-04:

- Completed first live real-money trading day with Adaptive mode, tiny
  notional exposure, and `HIGH` reconciliation.
- Treated the result as live-pipe validation rather than strategy proof:
  arming, live orders, fills, exits, closeout, dashboard state, and spreadsheet
  export all produced usable evidence.
- Fixed spreadsheet environment attribution after a pre-open paper snapshot
  polluted the first live daily row.
- Added `win_rate` to session rows and explicit research starting-account
  control so live and research outputs can be compared at the same scale.
- Preserved strategy thresholds after the live day; promoted MFE/MAE and
  exit-quality telemetry as the next evidence upgrades.

2026-06-06:

- Completed the measurement, reporting, and memory scope of the Trade Behavior
  Analyzer sprint.
- Added closed-trade MFE/MAE, capture ratio, hold duration, and source-labeled
  excursion telemetry without changing live strategy behavior.
- Research Mode enriches closed trades with completed-bar high/low excursion
  inside the simulated position lifetime.
- Live/session summaries enrich closed trades from lifecycle managed marks and
  fill prices.
- Added a structured InverseBot archaeology report that returns ranked
  hypotheses for Research Mode testing, not live doctrine changes.
- Added a Research Mode result surface for overall replay outcome, bot-quality
  averages, InverseBot archaeology, and closed-trade MFE/MAE/capture review.
- Added live and research spreadsheet row fields for session-level and bot-level
  MFE/MAE, capture ratio, hold duration, InverseBot diagnostic counts, and the
  MFE/MAE source label.
- Added local strategy preset save/load with name, version, notes, saved
  timestamp, and strategy-control snapshot. Presets are research memory only;
  they do not select live configurations or alter strategy behavior
  automatically.

2026-06-07:

- Compared `live_preset`, `Bear_Capture_Trail_075`,
  `Lead_Adaptive_8_24_25`, `Momentum_UP_v1`, and `Range_CHOP_v1` across
  same-date research batches.
- Renamed the surviving preset candidates:
  - `Lead_Generalist`
  - `Lead_Momentum_Specialist`
  - `Lead_Inverse_Specialist`
- Preserved `Lead_Generalist` as the current generalist anchor.
- Promoted `Lead_Momentum_Specialist` to momentum/upside-trend specialist
  candidate status.
- Promoted `Lead_Inverse_Specialist` to inverse/downside-damage specialist
  candidate status, not general replacement status.
- Retired `Bear_Capture_Trail_075` as a research stepping stone after
  out-of-sample failure.
- Left the Chop/range specialist slot open; `Range_CHOP_v1` did not prove a
  distinct range doctrine.
- Built the same-date preset comparison matrix and environment-fingerprint
  frame.
- Added an interactive no-sheet-post comparison UI, elapsed progress indicator,
  and copyable markdown output.
- Ran a `60` replay comparison across `20` dates and the three lead presets.
  `Lead_Momentum_Specialist` led the aggregate result at `$2.83`, while
  `Lead_Generalist` remained the default anchor and `Lead_Inverse_Specialist`
  won the highest wrong-choice-cost downside dates.
- First deterministic fingerprint clue: every `Lead_Momentum_Specialist` win in
  the batch had `30m Trans/hr = 0`. Treat this as a hypothesis for shadow
  routing, not a live rule.
- Keep active config routing parked until broader batches and shadow selector
  evidence prove that the routing decision is better than simply staying with
  `Lead_Generalist`.

2026-06-08:

- Froze v9.1 as the validated Momentum permission layer after three 20-date
  packs showed zero Pack 1 / Pack 2 regression and a `+$0.35` Pack 3
  improvement versus v8.5.
- v9.1 authority is intentionally conservative: it reads the
  `Lead_Generalist` observer fingerprint, requires zero first-30 non-warmup
  transitions, sufficient trend trust, and a material SOXL reclaim before
  suppressing InverseBot inside Momentum Specialist.
- Known limitation: v9.1 catches May 19-style authority, where SOXL has
  materially reclaimed by checkpoint, but it can miss March 9-style delayed
  breakouts where momentum develops after SOXL is still recovering at the
  checkpoint.
- Treat delayed-breakout misses in later v10 shadow output as authority-gate
  calibration misses, not ChopBot fallback failures.
- Next research step is v10 No-Authority Mode: after v9 evaluates inactive or
  invalidated, suppress directional fresh entries, let ChopBot run clean, and
  shadow-log suppressed MomentumBot/InverseBot entries with observer
  fingerprints.

2026-06-10:

- Promoted the full-roster specialist router after separate research cycles for
  InverseBot and MomentumBot.
- InverseBot research started from weak/negative downside participation and
  graduated into `INVERSE_CASCADE_MODE=SUSTAINED`.
- The Inverse research arc identified and fixed distinct failure modes:
  cascade confirmation quality, gap-down recovery pollution, stale
  route-invalidation timer state, proven-state route suppression, wider
  proven-state trailing behavior, SOXS-down entry rejection, prior-close
  gating, and second-entry/lockout discipline.
- MomentumBot research confirmed that the old upside path was structurally too
  late/selective for many SOXL surge days. The promoted response was not a
  broad loosened bot, but a separate sustained surge lane with its own proof
  conditions.
- Momentum Surge validation showed low-frequency, high-conviction behavior:
  `8` surge trades in the YTD reference, about `+$8.17` at `25%` sizing and
  about `+$36.68` at `95%` sizing.
- Roster validation showed the Momentum surge lane did not cannibalize
  InverseBot's home turf; in fixed-notional comparison, Inverse P/L remained
  unchanged while Momentum moved from drag to contributor.
- Rolling YTD equity validation showed the current candidate improving both
  return and max drawdown versus the prior baseline at `25%` and `95%` sizing.
- Accepted residuals for now: occasional failed surge scratches such as
  2025-04-30, residual Inverse/Chop edge cases, and the general reality that a
  real trading system will have red days.
- Added a live-ops follow-up: preload previous-session close during
  startup/warmup. Today the value is available through the live data path and
  gates fail closed if missing, but the first actionable evaluation should not
  depend on just-in-time prior-close retrieval.
