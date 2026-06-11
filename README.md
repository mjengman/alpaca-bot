# EdgeWalker Alpaca Bot

An operator-facing Alpaca trading app for SOXL/SOXS specialist routing. EdgeWalker
streams one-minute semiconductor tape, waits for validated specialist conditions,
routes to the appropriate bot, and protects any open position with bot-managed
exit doctrine.

## Quick Start

Browser UI:

```bash
python3 -m pip install -r requirements.txt
python3 server.py
```

Then open `http://127.0.0.1:8765`.

Do not open `web/index.html` directly unless the server is also running. The page can load from disk, but the buttons still need `server.py` for the local API.

CLI:

```bash
python3 bot.py --once --edgewalker
```

That runs one dry-run cycle using the credentials in `.env`. To run continuously:

```bash
python3 bot.py --edgewalker
```

Omit `--edgewalker` to run the original single-symbol trailing stop bot.
For live EdgeWalker testing, prefer the browser server because it owns the WebSocket stream and warmup cache. The CLI path is still useful for manual order tests and diagnostics.

The checked-in `.env.example` shows the settings. The local `.env` file is ignored by git.
The browser UI also has a Settings modal for paper/live Alpaca credentials, connection tests, active environment selection, and live-trading arming/disarming.
The local activity log is kept for 24 hours in `.bot_activity.json`, which is also ignored by git.

## Strategy

Current production posture: full-roster EdgeWalker Router.

- MomentumBot trades SOXL only when upside continuation has earned permission.
  The legacy StrictAuthority/BalancedTight path remains available, and the
  default production upside edge is the high-conviction Momentum Surge lane
  (`MOMENTUM_SURGE_MODE=SUSTAINED`).
- ChopBot trades SOXL mean reversion through `Chop_Gap020` with
  `CHOP_PERMISSION_MODE=FIREWALL`, primarily when directional authority is
  absent and the runtime observer does not flag dirty tape or deep source
  drawdown.
- InverseBot trades SOXS through the sustained cascade specialist
  (`INVERSE_CASCADE_MODE=SUSTAINED`). It requires downside/cascade confirmation,
  prior-close context, and cascade-specific exit handling before it can execute.
- BalancedPure is a runtime observer/probe only. It supplies authority context
  through `BALANCEDPURE_RUNTIME_OBSERVER_ENABLED=true` and has no execution
  rights in the live router.
- The browser Strategy Controls are intentionally simplified for live operation:
  most strategy inputs are locked, while position sizing, `Check now`, and
  `Turn On` / `Turn Off` remain operator-facing.

The live philosophy is "PatienceBot": no specialist is expected to trade every
day. EdgeWalker should stay flat until the tape rotates into one of the
validated habitats.

- Regime source: `SOXL`
- Regimes: `UPTREND`, `SIDEWAYS`, `DOWNTREND` from fast/slow SMA separation
- Router: `MomentumBot` trades `SOXL`, `InverseBot` trades `SOXS`, `ChopBot` trades SOXL mean reversion
- Directional mode: `CONSERVATIVE` requires a fresh cross, `BALANCED` also allows reasonable continuation entries, `AGGRESSIVE` can chase strong trends within the configured extension cap, and `ADAPTIVE` transparently selects one of those postures from runtime conditions without changing sizing
- Adaptive shadow: when `ADAPTIVE_SHADOW_ENABLED=true`, EdgeWalker logs the posture Adaptive would choose while the manually selected directional mode remains in control
- Entry: MomentumBot and InverseBot use the effective directional mode; ChopBot buys SOXL when SIDEWAYS price is discounted below the slow SMA
- Position size: fixed notional or dynamic allocation modes, clamped to the safe buying-power threshold and submitted through Alpaca notional orders
- Exit protection: track the high-water mark locally and submit a fractional market sell if price falls by `TRAIL_PERCENT`
- Regime flip guard: stale opposite exposure is sold first, with no same-cycle reversal
- Poll interval: `POLL_SECONDS`, default 60 seconds
- Closeout guard: sell the full open position inside `CLOSE_LIQUIDATE_MINUTES`, default 5, before Alpaca's reported market close
- Market data feed: `DATA_FEED=iex`, suitable for free Alpaca market data plans; use `sip` only if the account has SIP entitlement
- Live data source: the local server keeps an Alpaca WebSocket stream warm for SOXL/SOXS trades, quotes, and one-minute bars
- Prior-close context: Momentum Surge and Inverse Cascade gates lazily request
  the previous regular-session close through the active market data source. If
  that value is unavailable, those gates fail closed rather than guessing.
- Trading block: EdgeWalker will not enter trades unless the stream is live and the latest completed one-minute bar is fresh
- Market-hours guard: no fresh entry orders are submitted while Alpaca reports the market is closed
- Market-close behavior: the repeating browser runner switches itself off after Alpaca reports the regular market is closed

The bot defaults to `ALPACA_ENVIRONMENT=paper` and `DRY_RUN=false`, so the paper account places paper orders by default. Set `DRY_RUN=true` in `.env` only when you explicitly want the bot to print intended orders without sending them to Alpaca.

Live trading uses separate live credentials and the live Alpaca trading URL. Real live-order submission is blocked unless `LIVE_TRADING_ARMED=true`, which the Settings modal only enables after live credentials are configured and a typed `LIVE` confirmation is entered. The same modal can disarm live trading. Keep paper trading as the default workflow until live-readiness checks are complete.

## Qualification Notes

Current review is focused on preserving operational truth while running the
full specialist roster. A few concepts are now part of the project vocabulary:

- Regime strength is not the same as Trend Trust. Shadow telemetry now tracks
  regime age, recent flips, directional efficiency, and a score/label before
  any threshold or Adaptive-logic changes.
- Quotes/trades can be live while one-minute bars are stale. In that state the
  market is visible for risk management, but regime interpretation is degraded;
  entries remain blocked. The stream service can attempt bounded REST backfill
  to repair stale bars before regime detection.
- Regular-session trading now uses regular-session warmup bars only, so
  premarket bars do not accidentally satisfy the first actionable SMA context.
- Route-invalidation exits are treated as policy events. Lifecycle records store
  enough context to classify them later as defensive saves, premature cuts,
  neutral exits, or profitable handoffs.
- Dynamic Controls are a future shadow-first idea for bounded runtime
  adaptation inside operator-approved rails, not autonomous strategy mutation.
- Previous-session close is currently fetched lazily during gate evaluation.
  A planned hardening item is to preload the required prior-close anchors during
  EdgeWalker startup/warmup so the first actionable evaluation does not depend
  on a just-in-time fetch.
- Recent rolling YTD research on the current production candidate showed the
  specialist stack improving return and drawdown versus the prior baseline:
  25% sizing ended at about `$390.01` from `$350` (`+11.43%`, max drawdown
  `1.72%`), while 95% sizing ended at about `$522.71` (`+49.35%`, max drawdown
  `6.51%`). These are research results, not promises.

## Research Mode

Research Mode is the in-app backtest lab. It replays historical one-minute
SOXL/SOXS bars against the current Strategy Controls configuration while using a
simulated broker instead of the live or paper Alpaca trading path.

Use it for evidence, not doctrine:

- Enable Research Mode from the App Settings menu.
- Research controls appear inside Strategy Controls only while Research Mode is
  enabled.
- Choose a backtest date, data feed, fill model, slippage, and preset labels.
- Click `Run Backtest` to replay the selected regular session and post a
  research row if a spreadsheet endpoint is configured.

V1 assumptions:

- Historical bars come from Alpaca one-minute bars.
- Strategy perception uses completed prior bars.
- Simulated fills use `next_bar_open`.
- Slippage is explicit and recorded in the research row.
- Research rows do not generate a daily narrative.
- Research runs are blocked while the live/paper loop is running.

Spreadsheet setup:

- `Sheet URL` and `Post Endpoint` remain the primary spreadsheet settings.
- `Research Sheet URL` is used by the `Open Research` button.
- `Research Endpoint Override` is optional. When blank, Research Mode reuses the
  normal `Post Endpoint`.
- The Apps Script should route rows with `is_backtest=true` into the research
  tab and live/paper rows into the daily session tab.

## Useful Commands

```bash
python3 bot.py --once --edgewalker --dry-run
python3 bot.py --once --edgewalker --live
python3 bot.py --once --dry-run
python3 bot.py --symbol AAPL --notional 50 --trail-percent 2
python3 bot.py --symbol F --buy-qty 1 --live
python3 bot.py --symbol F --sell-qty 1 --live
```

Market sells triggered by the bot-managed trailing stop do not guarantee a specific fill price. Keep this POC on paper trading until the behavior has been reviewed carefully.
