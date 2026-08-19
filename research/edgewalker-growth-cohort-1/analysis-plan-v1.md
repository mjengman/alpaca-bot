# Edgewalker Growth Cohort 1 — Prospective Analysis Plan

Frozen: 2026-08-19

## Objective

Maximize long-run compounded account return while preserving positive expectancy. The aspirational operating target is 1% per regular trading session. Drawdown is measured and reported, but it is not a promotion veto for this experimental account.

## Prospective cohort

- Environment: Alpaca live trading.
- Market data: IEX.
- Production strategy: the current Full Roster Edgewalker build at launch.
- Sizing: the operator-selected production sizing at launch; the complete effective notional and account equity are recorded every cycle.
- Duration: 60 completed regular-session observations.
- Interim readouts: after sessions 20 and 40. These are descriptive only and do not authorize tuning or early promotion.
- Freeze: no production strategy, risk-doctrine, execution, data-feed, or sizing change during the cohort. Runtime provenance drift blocks new entries while existing-position risk management remains active.
- Human intervention: any operator entry, exit, or Bank Day event is retained and marks that session as operator-affected. It is never silently removed.

## Session denominator

Every session admitted by Edgewalker's first live, market-open cycle is counted, including no-trade and operational-error sessions. A session is finalized after the regular close. Complete server absence is an operational availability gap and must be disclosed separately; it must not be relabeled as a no-trade strategy session.

## Frozen outcomes

Primary outcome:

- Geometric mean daily account return across completed cohort sessions.

Supporting outcomes:

- Total compounded return.
- Positive-session rate.
- Count and rate of sessions at or above +1%.
- Maximum peak-to-trough drawdown.
- Trade count, no-trade count, error-cycle count, and operator-affected session count.
- Starting and ending equity in dollars.

At session 60, Edgewalker applies a circular moving-block bootstrap to log daily returns using block length 5, 50,000 resamples, and seed 20260819. A one-sided 95% lower bound above zero is labeled strong positive support. The +1% aspiration is supported only when both that lower bound is above zero and geometric mean daily return is at least +1%.

All daily account returns use the broker-reported day P/L percentage captured by Edgewalker. Capital level is therefore normalized in the primary return statistics while actual dollars, buying power, requested notional, and effective notional remain in the decision ledger for capacity and slippage analysis.

## Interpretation

The cohort is successful only if the frozen strategy has positive total compounding and positive geometric mean daily return after all 60 sessions. Reaching or exceeding 1% geometric mean daily return is the aspirational result. Drawdown informs the quality and repeatability of growth but does not independently fail the cohort.

No inference is made from a single best day, only traded days, or a backfilled subset. Any post-launch rule change creates a new version and a new prospective cohort.

## Challenger policy

Alternative strategies may run in shadow only. A challenger must consume the same timestamped market state, produce a decision without live order authority, and write its version, features, action, counterfactual fill assumptions, and outcome to the experiment database. Promotion requires a separately frozen comparison rule and a new live cohort.

The first frozen challenger is an entry-anchored exit-doctrine lab. It starts 1.0%, 1.5%, 2.0%, 3.5%, and 6.0% trailing-stop shadows from each autonomous live buy fill. It uses only same-cycle cached SOXL/SOXS marks, runs after live processing, makes no broker or network call, and has no promotion authority. These are per-trade comparisons, not overlapping-capital portfolio simulations.
