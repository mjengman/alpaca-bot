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
The browser UI also has a Settings modal for paper/live Alpaca credentials,
connection tests, active environment selection, live-trading
arming/disarming, notification settings, and operator spreadsheet settings.
The local activity log is kept for 24 hours in `.bot_activity.json`, which is also ignored by git.

### Operator Overrides

While the repeating bot is running, the dashboard exposes three non-halting
operator controls. They remain visible but disabled outside regular market hours:

- `Buy SOXL Now` and `Buy SOXS Now` submit an immediate market buy for the
  selected ticker without requiring an autonomous route, warmup, ORB, authority,
  setup, or confirmation gate. They use the active fixed/dynamic size selection,
  start a fresh dedicated `0.75%` manual trail, and do not inherit specialist
  proven-state, route-grace, profit-lock, or cooldown state. Autonomous route
  changes do not close an operator-entered position; the manual trail, `Exit Now`,
  Auto Bank, and closeout protection remain authoritative.
- `Exit Now` cancels a pending entry or flattens the current position, then
  automatically returns control to Edgewalker. It does not bank the session or
  add a manual cooldown, so the bot may enter again on a later qualified cycle.

Operator actions and autonomous cycles share one execution lock so they cannot
submit conflicting orders concurrently. Entry and exit fills record independent
`bot`/`operator` initiators. Account P/L includes every fill, while specialist
expectancy cards and archaeology include only `bot/bot` trades. Operator-affected
records retain action IDs and counterfactual replay hooks.

### Bank Day

While the repeating bot is running and the market is open, `Bank Day` is an
operator safety control that cancels pending entry orders, flattens any SOXL or
SOXS position, and blocks new entries for the rest of that New York trading
session. If an order is still resolving, the runner keeps enforcing the bank on
subsequent cycles until the account is flat. Bot-managed risk remains active
until the flattening exit actually fills.

The status distinguishes an exit request from a completed fill. Before a fill,
any displayed P/L is labeled as the press-time dashboard snapshot. After the
lifecycle ledger reconciles the fill, the UI displays the realized trade result.
The bank event also records its route, position, MFE, and timestamp as an anchor
for later counterfactual replay; it does not claim that replay is automatic.

When `AUTO_BANK_DAY_ENABLED=true`, Edgewalker applies the same flatten-and-halt
contract automatically after Alpaca account equity reaches
`AUTO_BANK_DAY_TARGET_PERCENT` above prior-close equity. The target is checked
before a new autonomous decision and again after each cycle. Automatic banks
use the separate `AUTO_BANK_DAY` lifecycle event and
`auto_bank_day_target` exit reason, remain bot/bot expectancy, and display as
`Auto Bank` rather than an operator intervention. Market-order movement means
the realized close can finish slightly above or below the trigger snapshot.

## Strategy

Current production posture: full-roster EdgeWalker Router.

- MomentumBot trades SOXL only when upside continuation has earned permission.
  The legacy StrictAuthority/BalancedTight path remains available, and the
  default production upside edge is the high-conviction Momentum Surge lane
  (`MOMENTUM_SURGE_MODE=SUSTAINED`). When `OPENING_ORB_ENABLED=true`, a separate
  bullish opening lane builds the first 15-minute SOXL range, waits for a
  completed confirmation bar, and enters only when SOXL clears the range high
  by the configured buffer, is at least 1% above its session open, and paired
  SOXS weakness confirms. The lane rejects excessive extension, gets one
  attempt per session, uses a dedicated 1% trailing stop, and exits at 9:55 ET
  if neither its trail nor Auto Bank has already ended the trade. Normal routing
  resumes after that handoff.
- ChopBot trades SOXL mean reversion through `Chop_Gap020` with
  `CHOP_PERMISSION_MODE=FIREWALL`, primarily when directional authority is
  absent and the runtime observer does not flag dirty tape or deep source
  drawdown.
- InverseBot trades SOXS through the sustained cascade specialist
  (`INVERSE_CASCADE_MODE=SUSTAINED`). It requires downside/cascade confirmation,
  prior-close context, and cascade-specific exit handling before it can execute.
  When `OPENING_IMPULSE_ENABLED=true`, a separate first-20-minute lane can route
  SOXS before the 20-bar SMA warmup completes, but only after SOXL decline,
  drawdown, velocity, low-making pressure, and SOXS strength all confirm. It then
  uses the same autonomous allocation, cascade trailing stop, lifecycle ledger,
  one-entry lockout, and Auto Bank handling as the mature-session specialist.
  The final five minutes demand stronger SOXS confirmation, and an excessively
  fast selloff is rejected to avoid chasing the exhaustion end of a waterfall.
- The two opening lanes are intentionally asymmetric. Bearish openings qualify
  through fast impulse/path evidence; bullish openings qualify through an
  opening-range breakout. If both ever appear qualified in the same cycle,
  opening authority fails closed instead of guessing a direction.
- BalancedPure is a runtime observer/probe only. It supplies authority context
  through `BALANCEDPURE_RUNTIME_OBSERVER_ENABLED=true` and has no execution
  rights in the live router.
- The browser live-control surface is intentionally simplified for live
  operation. The former strategy-control block is now an Edgewalker Status
  panel with the locked build, account vitals, position sizing, `Check now`,
  and `Turn On` / `Turn Off`.
- Strategy Gates show the live state of Momentum Surge, Chop Reversion, and
  Inverse Cascade. Gate tiles are structured telemetry, not console-log
  scraping, and remain visible for all strategies so the operator can see what
  is passing, waiting, or vetoing before a strategy fires.

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
- Scan cadence: `POLL_SECONDS`, default 60 seconds while flat; open positions
  or pending orders are checked every 5 seconds for tighter bot-managed exits.
  Daily accounting separates signal cycles from faster active-position risk
  scans so reports do not dilute regime-transition math.
- Closeout guard: sell the full open position inside `CLOSE_LIQUIDATE_MINUTES`, default 5, before Alpaca's reported market close
- Market data feed: `DATA_FEED=iex`, suitable for free Alpaca market data plans; use `sip` only if the account has SIP entitlement
- Live data source: the local server keeps an Alpaca WebSocket stream warm for SOXL/SOXS trades, quotes, and one-minute bars
- Prior-close context: Momentum Surge and Inverse Cascade gates require the
  previous regular-session close. Edgewalker preloads the value during
  startup/warmup, reports explicit telemetry states (`Loaded`, `Pending`, or
  `Unavailable`), and fails the dependent gates closed rather than guessing.
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
- Previous-session close is preloaded during startup/warmup for the specialist
  gates that require it. The UI reports whether that anchor is loaded, pending,
  or unavailable.
- Recent rolling YTD research on the current production candidate remains
  constructive after the harness honesty pass. With corrected timestamp
  alignment and live-parity fixes, the 95% sizing replay from a simulated
  `$350` starting balance ended at about `$517.37` through 2026-06-09
  (`+47.82%`, max drawdown about `9.66%`). This does not include outside
  account deposits. It is research evidence, not a promise.
- Earlier pre-harness-correction research showed about `$522.71` (`+49.35%`).
  The corrected replay shaved roughly `$5.34` / `1.53` return points from the
  old result, which suggests the replay became more realistic without erasing
  the broad YTD edge.

### Live Observation Watchlist

The current operating posture is to collect live data without changing strategy
code. The latest parity work supports patience: the live sample remains small,
the corrected YTD replay is still positive, and one-week pain has not justified
strategy mutation. Keep these observations as review items for the next
research/hardening cycle:

- 2026-06-23: Momentum Surge entered SOXL and closed eight seconds later via
  `momentum_authority_revoked_exit`. Snapshot: entry `$252.5999`, exit
  `$252.0718`, quantity `2.154078049`, realized P/L `-$1.14`, MFE `0%`, MAE
  `-0.2091%`. Working hypothesis: Surge can correctly qualify through its own
  sustained-confirmation override while the legacy Momentum authority state is
  still closed, then the open-position authority-revoke guard treats the Surge
  position like a regular authority-based Momentum entry. This may be a policy
  mismatch, but it should be confirmed with more live evidence before changing
  strategy code.

## Research Mode

Research Mode is the in-app backtest lab. It replays historical one-minute
SOXL/SOXS bars against the current EdgeWalker configuration while using a
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
- Simulated fills use `next_bar_open` by default. Parity research can also use
  live-audit fill overrides from broker lifecycle records.
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

## Notifications

Edgewalker can send low-volume operator emails through the same Google Apps
Script surface used for spreadsheet logging. The app posts notification payloads
to the configured Apps Script endpoint, and the script delivers them with
`MailApp.sendEmail`.

Use the Notifications modal to configure:

- Notification email address
- Apps Script endpoint URL
- Optional shared secret
- Trade, P/L, warmup, daily-summary, and error-notification toggles
- Error-notification cooldown
- Delivery-state visibility for last sent event, last failure, and active
  cooldown
- Manual `Send EOD Summary` recovery action

The notification sender keeps a local dedupe/cooldown ledger in
`.notification_events.json`, so restarts do not repeatedly resend the same trade
or error event. Daily-summary emails use the deterministic narrative sections
already computed for the in-app Narrative tab rather than recomputing a separate
interpretation.

## Narratives And Reports

The Narrative tab uses deterministic, locally generated story beats by default.
No trading logs are sent to OpenAI for the current local narrative path.

Current report behavior:

- 1D, 1W, 1M, YTD, and MAX summaries can be generated from structured session
  rows.
- The narrative header includes a source indicator such as `Source: Local`.
- Daily summaries distinguish signal cycles from active-position risk scans.
- Partial-week and partial-period language is included when a selected range is
  incomplete.
- Narrative phrasing varies deterministically so repeated reports do not become
  completely canned, while the underlying facts and anti-overfitting guardrails
  remain stable.

Narratives are operator debriefs, not strategy doctrine. They should explain
what the data supports, preserve no-trade days as valid behavior, and avoid
parameter-change recommendations from one session.

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
