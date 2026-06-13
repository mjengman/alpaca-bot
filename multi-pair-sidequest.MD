# EdgeWalker Multi-Pair Sidequest

Date captured: 2026-06-13

This note preserves a research-only curiosity run against several leveraged ETF
pairs outside EdgeWalker's native SOXL/SOXS habitat. The goal was not to tune,
promote, or change production behavior. It was to see how the current locked
full-roster strategy behaves when pointed at other long/inverse pairs.

## Research Protocol

- Harness: current EdgeWalker research backtest engine
- Production code changes: none
- Symbol changes: in-memory only for each throwaway run
- Date range: 2026-01-02 through 2026-06-09
- Sessions: 109
- Starting balance: `$350`
- Sizing: dynamic `25% BP`
- Roster: full locked roster
  - Momentum Surge
  - Chop Reversion
  - Inverse Cascade
- Data/feed assumptions: same as current research harness
- Fill model: research replay / next-bar style fills already used by the
  harness

Important caveat: these are out-of-domain curiosity runs. The specialists were
calibrated on SOXL/SOXS behavior, including volatility profile, route behavior,
prior-close dynamics, extension thresholds, trail behavior, and cascade shape.
The sidequest results should be treated as behavioral fingerprints, not
production evidence.

## Scoreboard

| Pair | P/L | Return | Max DD | Green / Red / Flat | Trades | Read |
|---|---:|---:|---:|---:|---:|---|
| SOXL/SOXS | `+$32.79` | `+9.37%` | `-2.34%` | `56 / 37 / 16` | `252` | Home turf, full roster matters |
| LABU/LABD | `+$2.97` | `+0.85%` | `-0.55%` | `7 / 6 / 96` | `14` | Quiet with one clean Inverse strike |
| FAS/FAZ | `+$2.75` | `+0.79%` | `-0.19%` | `7 / 3 / 99` | `12` | Clean Chop-friendly behavior |
| TQQQ/SQQQ | `+$2.67` | `+0.76%` | `-0.89%` | `42 / 35 / 32` | `164` | Active Chop grinder |
| UPRO/SPXU | `+$0.70` | `+0.20%` | `-0.69%` | `17 / 15 / 77` | `38` | Broad-market Chop nibble |
| GUSH/DRIP | `-$1.05` | `-0.30%` | `-1.41%` | `27 / 18 / 64` | `75` | Active but messy |
| SSO/SDS | `-$2.21` | `-0.63%` | `-0.63%` | `6 / 13 / 90` | `20` | Too quiet for current gates |
| UVXY/SVXY | `-$3.54` | `-1.01%` | `-1.98%` | `24 / 41 / 44` | `128` | Volatility mismatch |

Note: the user-requested `SPXU/UPRO` run was executed as `UPRO/SPXU` so the
semantic orientation stayed consistent with the harness: primary long ETF first,
inverse/bear ETF second.

## Native Habitat Result

SOXL/SOXS remains the clear native habitat.

Specialist attribution:

| Specialist | P/L | Active Days | Trades |
|---|---:|---:|---:|
| Momentum Surge | `+$1.58` | `8` | `21` |
| Chop Reversion | `+$10.12` | `78` | `214` |
| Inverse Cascade | `+$21.11` | `17` | `17` |

The key distinction is not just higher total return. SOXL/SOXS is the only pair
where the full roster acted like an ecosystem. Chop carried persistent small
edge, Inverse delivered asymmetric rescue/strike days, and Momentum contributed
selectively. The sidequest pairs mostly reduced to Chop-only behavior, one-off
Inverse hits, or noisy churn.

## Pair Notes

### LABU/LABD

LABU/LABD was the most interesting non-SOXL result. It stayed mostly flat, then
benefited from one clean Inverse Cascade strike.

Specialist attribution:

- Momentum Surge: `$0.00`, no trades
- Chop Reversion: `-$0.10`, 13 trades
- Inverse Cascade: `+$3.07`, 1 trade

Read: this pair may have occasional cascade-like conditions, but the sample does
not show enough breadth to treat it as a candidate without a full recalibration
cycle.

### FAS/FAZ

FAS/FAZ was clean but modest.

Specialist attribution:

- Momentum Surge: `-$0.64`, 2 trades
- Chop Reversion: `+$3.39`, 10 trades
- Inverse Cascade: `$0.00`, no trades

Read: the current stack mostly sees this as a Chop Reversion instrument. It did
not show meaningful Momentum or Inverse behavior under SOXL-tuned gates.

### TQQQ/SQQQ

TQQQ/SQQQ was the most plausible adjacent habitat, but not a SOXL replacement.

Specialist attribution:

- Momentum Surge: `-$0.11`, 1 trade
- Chop Reversion: `+$2.75`, 159 trades
- Inverse Cascade: `+$0.03`, 4 trades

Read: there is enough activity for the system to trade, but most of the result
comes from many small Chop trades. The current Momentum and Inverse gates do not
find the same payoff profile they find in SOXL/SOXS.

### UPRO/SPXU

UPRO/SPXU was polite and contained.

Specialist attribution:

- Momentum Surge: `$0.00`, no trades
- Chop Reversion: `+$0.72`, 37 trades
- Inverse Cascade: `-$0.02`, 1 trade

Read: broad-market 3x behavior produced a small Chop edge but no specialist
fireworks. It is safer-looking than some pairs, but not especially compelling.

### GUSH/DRIP

GUSH/DRIP was active and messy.

Specialist attribution:

- Momentum Surge: `$0.00`, no trades
- Chop Reversion: `-$0.23`, 70 trades
- Inverse Cascade: `-$0.82`, 5 trades

Read: this pair has enough volatility to wake the system up, but the current
gates do not convert that activity into reliable edge.

### SSO/SDS

SSO/SDS was mostly too quiet.

Specialist attribution:

- Momentum Surge: `$0.00`, no trades
- Chop Reversion: `-$2.21`, 20 trades
- Inverse Cascade: `$0.00`, no trades

Read: the 2x S&P pair did not move enough to qualify the SOXL-calibrated
Momentum or Inverse gates. Chop fired occasionally, but all recorded exits were
route invalidations.

### UVXY/SVXY

UVXY/SVXY was the least compatible instrument family.

Specialist attribution:

- Momentum Surge: `-$0.73`, 1 trade
- Chop Reversion: `-$2.80`, 127 trades
- Inverse Cascade: `$0.00`, no trades

Read: volatility products do not behave like ordinary long/inverse equity ETF
pairs. The current route semantics do not map cleanly to UVXY/SVXY structure,
decay, or spike behavior.

## Main Findings

1. SOXL/SOXS is not accidentally profitable in this harness.

   The control result was an order of magnitude stronger than every sidequest
   pair. This supports the thesis that EdgeWalker is currently specialized, not
   generic.

2. The sidequest pairs mostly became Chop studies.

   FAS/FAZ, TQQQ/SQQQ, UPRO/SPXU, GUSH/DRIP, SSO/SDS, and UVXY/SVXY all leaned
   heavily on Chop Reversion when they traded at all. Momentum and Inverse rarely
   activated outside SOXL/SOXS.

3. Low drawdown on unfamiliar pairs is a good sign.

   The system generally did not overtrade catastrophically when pointed at
   mismatched instruments. This suggests the gates are selective enough to fail
   closed or trade lightly outside their validated habitat.

4. Positive sidequest results are not promotion cases.

   LABU/LABD, FAS/FAZ, TQQQ/SQQQ, and UPRO/SPXU were positive, but their
   profiles were small, narrow, or one-off. None should be treated as production
   candidates without pair-specific calibration.

5. Instrument personality matters.

   SOXL/SOXS has a volatility and behavioral profile that the current roster was
   built around. Other pairs need their own thresholds, route rules, prior-close
   interpretation, and exit doctrine.

## Future Idea: Asymmetric Upside Optimizer

The sidequest suggests a possible long-term direction:

```text
EdgeWalker as an Asymmetric Upside Optimizer across multiple calibrated
long/inverse ETF pairs.
```

In that future version, EdgeWalker would not simply trade every pair with the
same settings. Instead, it would maintain calibrated strategy lanes per pair and
compare current opportunities across the universe.

Conceptual workflow:

1. Observe multiple candidate pairs.
2. Compute pair-specific specialist gate states.
3. Estimate opportunity quality / expectancy for each eligible lane.
4. Rank opportunities across sectors.
5. Route capital only to the best qualified opportunity.
6. Stay flat when no opportunity clears the required expectancy threshold.

This preserves the current doctrine:

- Specialists must earn their habitat.
- Patience remains a feature.
- Flat is a valid result.
- The system should explain why it chose one opportunity over another.

## Required Research Before Multi-Pair Promotion

A real multi-pair EdgeWalker would need a full research program, not a quick
symbol swap.

Minimum requirements:

- Per-pair calibration packs
- Per-pair volatility normalization
- Per-pair prior-close diagnostics
- Per-pair trail width and proven/route-hold sensitivity
- Per-pair regime-gap calibration
- Per-pair false-positive and false-negative audits
- Pair-level expectancy estimates
- Cross-pair capital allocation policy
- Collision policy when multiple pairs qualify at once
- Sector exposure / correlation controls
- Live data preload for every watched pair
- UI support for multi-pair opportunity ranking
- Spreadsheet/reporting fields for pair attribution

## Possible Future Architecture

```text
Market Universe
  -> Pair Adapters
      -> Pair-specific gates
      -> Pair-specific specialist configs
      -> Pair-specific risk model
  -> Opportunity Scorer
      -> Expected value
      -> Confidence
      -> Drawdown/risk impact
      -> Correlation/capital constraints
  -> Router
      -> Best qualified opportunity
      -> No trade if no edge clears threshold
```

This would keep EdgeWalker as one autonomous strategy engine while allowing it
to specialize across several instrument personalities.

## Open Questions

- Does each pair need a fully separate config, or can some thresholds be
  volatility-normalized?
- Should Chop Reversion be a universal specialist while Momentum and Inverse
  remain pair-specific?
- How should EdgeWalker rank one large Inverse opportunity versus several small
  Chop opportunities?
- What is the right capital policy when multiple uncorrelated sectors qualify?
- Should the system ever hold more than one pair at once, or should it remain
  single-position for simplicity and operator trust?
- What sample size is required before adding a new pair to the candidate
  universe?

## Conclusion

The sidequest strengthened the main thesis: EdgeWalker currently has a real
SOXL/SOXS specialty. The side pairs did not disprove the architecture; they
showed that the current roster is selective, relatively contained, and not yet
generic.

The promising future is not "run SOXL settings everywhere." The promising
future is a calibrated multi-pair engine that can scan several asymmetric
opportunity habitats and choose the best one when, and only when, the evidence
is strong enough.

