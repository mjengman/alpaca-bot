# Alpaca Trailing Stop Bot

A small local proof of concept for Alpaca paper trading. EdgeWalker polls one-minute SOXL market data, classifies the semiconductor regime, routes to one specialist bot, and protects any open position with a bot-managed trailing stop that can sell fractional shares.

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

- Regime source: `SOXL`
- Regimes: `UPTREND`, `SIDEWAYS`, `DOWNTREND` from fast/slow SMA separation
- Router: `MomentumBot` trades `SOXL`, `InverseBot` trades `SOXS`, `ChopBot` trades SOXL mean reversion
- Directional mode: `CONSERVATIVE` requires a fresh cross, `BALANCED` also allows reasonable continuation entries, and `AGGRESSIVE` can chase strong trends within the configured extension cap
- Entry: MomentumBot and InverseBot use the configured directional mode; ChopBot buys SOXL when SIDEWAYS price is discounted below the slow SMA
- Position size: fixed notional or dynamic allocation modes, clamped to the safe buying-power threshold and submitted through Alpaca notional orders
- Exit protection: track the high-water mark locally and submit a fractional market sell if price falls by `TRAIL_PERCENT`
- Regime flip guard: stale opposite exposure is sold first, with no same-cycle reversal
- Poll interval: `POLL_SECONDS`, default 60 seconds
- Closeout guard: sell the full open position inside `CLOSE_LIQUIDATE_MINUTES`, default 5, before Alpaca's reported market close
- Market data feed: `DATA_FEED=iex`, suitable for free Alpaca market data plans; use `sip` only if the account has SIP entitlement
- Live data source: the local server keeps an Alpaca WebSocket stream warm for SOXL/SOXS trades, quotes, and one-minute bars
- Trading block: EdgeWalker will not enter trades unless the stream is live and the latest completed one-minute bar is fresh
- Market-hours guard: no fresh entry orders are submitted while Alpaca reports the market is closed
- Market-close behavior: the repeating browser runner switches itself off after Alpaca reports the regular market is closed

The bot defaults to `ALPACA_ENVIRONMENT=paper` and `DRY_RUN=true`, so it will show what it would do without placing orders. Turn off Dry run in the UI when you want the paper account to place orders.

Live trading uses separate live credentials and the live Alpaca trading URL. Real live-order submission is blocked unless `LIVE_TRADING_ARMED=true`, which the Settings modal only enables after live credentials are configured and a typed `LIVE` confirmation is entered. The same modal can disarm live trading. Keep paper trading as the default workflow until live-readiness checks are complete.

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
