# Alpaca Trailing Stop Bot

A small local proof of concept for Alpaca paper trading. It polls one-minute market data, enters a long position when a fast moving average crosses above a slow moving average, and protects any open position with a bot-managed trailing stop that can sell fractional shares.

## Quick Start

Browser UI:

```bash
python3 server.py
```

Then open `http://127.0.0.1:8765`.

Do not open `web/index.html` directly unless the server is also running. The page can load from disk, but the buttons still need `server.py` for the local API.

CLI:

```bash
python3 bot.py --once
```

That runs one dry-run cycle using the credentials in `.env`. To run continuously:

```bash
python3 bot.py
```

The checked-in `.env.example` shows the settings. The local `.env` file is ignored by git.

## Strategy

- Symbol: `SYMBOL`, default `F`
- Entry: buy when the fast SMA crosses above the slow SMA
- Position size: market buy by `POSITION_NOTIONAL`, which supports fractional shares through Alpaca notional orders
- Exit protection: track the high-water mark locally and submit a fractional market sell if price falls by `TRAIL_PERCENT`
- Poll interval: `POLL_SECONDS`, default 60 seconds
- Closeout guard: sell the full open position inside `CLOSE_LIQUIDATE_MINUTES`, default 5, before Alpaca's reported market close
- Market data feed: `DATA_FEED=iex`, suitable for free Alpaca market data plans
- Market-hours guard: no fresh entry orders are submitted while Alpaca reports the market is closed

The bot defaults to `DRY_RUN=true`, so it will show what it would do without placing orders. Set `DRY_RUN=false` in `.env` when you want the paper account to place orders.

## Useful Commands

```bash
python3 bot.py --once --dry-run
python3 bot.py --once --live
python3 bot.py --symbol AAPL --notional 50 --trail-percent 2
python3 bot.py --symbol F --buy-qty 1 --live
python3 bot.py --symbol F --sell-qty 1 --live
```

Market sells triggered by the bot-managed trailing stop do not guarantee a specific fill price. Keep this POC on paper trading until the behavior has been reviewed carefully.
