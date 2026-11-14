# Telegram Daily Signal（现货轨 · 已退役）

> **状态（2026-10-11，负责人决定）**：实盘只跑衍生品轨，**现货信号不参与实盘**。
> 本文档保留给研究/回放用；部署时不要安装 `atlas20-telegram-signal.timer`。
> 实盘入口见 `docs/operations/derivatives_live_runbook.md`。

The daily Telegram push sends one message per day from the frozen H5 signal
snapshot. It reports:

- today's `BUY`/`SELL` instructions in USDT, based on a configurable capital;
- the post-trade target holdings by coin, weight, and USDT amount, including cash;
- the as-of date, BTC gate, gross exposure, trial id, and cost assumption.

This is a notification-only path. It does not know about a real brokerage
account, does not reconcile actual holdings, and never places an order.

## Configure the bot

1. Create a bot with BotFather and copy its token.
2. Send the bot a message from the Telegram account or group that should receive
   the signal.
3. Read the chat id:

   ```bash
   curl -s "https://api.telegram.org/bot${ATLAS20_TELEGRAM_BOT_TOKEN}/getUpdates"
   ```

   Use the `message.chat.id` value from the response. A negative id is valid for
   a group. Separate multiple recipients with commas.

4. Store the credentials outside the repository:

   ```bash
   mkdir -p ~/.config/atlas20
   cat > ~/.config/atlas20/telegram.env <<'ENV'
   ATLAS20_TELEGRAM_BOT_TOKEN=123456:replace-me
   ATLAS20_TELEGRAM_CHAT_ID=123456789,987654321
   ENV
   chmod 600 ~/.config/atlas20/telegram.env
   ```

   `ATLAS20_TELEGRAM_API_BASE` is optional and defaults to
   `https://api.telegram.org`. `ATLAS20_TELEGRAM_CAPITAL` is optional and
   defaults to `1000` USDT for the amount instructions.

## Test on macOS

The sender is pure Python and works on macOS for local testing. Scheduling is
deliberately left to the Ubuntu deployment; no macOS launchd job is added.

```bash
set -a
source ~/.config/atlas20/telegram.env
set +a

.venv/bin/python scripts/run_phase_momentum_live_signal.py
.venv/bin/python scripts/send_telegram_signal.py --dry-run
.venv/bin/python scripts/send_telegram_signal.py --force
```

`--dry-run` prints the message without requiring credentials and does not write
the sent-state file. `--force` bypasses the same-day idempotency guard.

## Install on Ubuntu

The checked-in units use `/opt/atlas20` as the deployment path. Change the path
in both files if the repository lives elsewhere.

```bash
sudo mkdir -p /etc/atlas20
sudo install -m 600 /dev/null /etc/atlas20/telegram.env
sudo editor /etc/atlas20/telegram.env

sudo cp ops/systemd/atlas20-telegram-signal.service /etc/systemd/system/
sudo cp ops/systemd/atlas20-telegram-signal.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now atlas20-telegram-signal.timer

systemctl list-timers atlas20-telegram-signal.timer
journalctl -u atlas20-telegram-signal.service -n 100 --no-pager
```

The timer makes two attempts per day: 03:00 UTC (11:00 Beijing) and 07:00 UTC
(15:00 Beijing). The first attempt targets the strategy's assumed +3h execution
window; the second is a catch-up for days when the primary data refresh is late.
The same-day idempotency state means only the first successful attempt sends a
message. Both attempts assume the Ubuntu data-refresh job has completed; adjust
`OnCalendar` if that job runs at a different time. The service regenerates the
signal first, so a stale or partial panel makes the attempt fail instead of
sending a stale message.

## Derivatives track (`PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21`)

The derivatives broadcast matches the current LS45-G125 Bitget USDT-M track:
signed long/short target weights, 1.25x gross cap, isolated margin, 50% initial
buffers per leg, and a 20% mark-price stop on every short entry/increase. It
reads the frozen target book in `reports/ls45_live_g125/oos_targets.csv` and
sends one message per signal day with:

- signed `BUY`/`SELL` notional and weight changes in pp;
- long and short legs separately labelled, never hidden behind absolute values;
- reference isolated margin, total gross (`sum(abs(notional))`), and the 1.25x cap;
- the single execution time (T+1 01:05 UTC, 09:05 Beijing);
- the target ledger's `execution_hint`, which must be the same T+1 01:05 UTC clock;
- a short-risk line stating that entries carry a 20% mark-price market stop;
- a warning when the execution time has already passed.

```bash
# preview the latest LS45 message (no credentials needed)
make derivatives-signal

# refresh the live mark tree and rebuild the LS45 ledger, then send one message
make derivatives-live-data derivatives-ls45-signal derivatives-notify
```

The message is notification-only: it never places an order, does not know any
real position, and repeated runs for the same signal day are skipped by the
`(spec, signal_date)` key in `data/ls45_g125_telegram_state.json`. If the modelled
execution is more than `--max-signal-age-hours` (default 36h) in the past, the
sender refuses to send and exits non-zero. Replay an old ledger deliberately
with `--allow-stale-signal`.

On Ubuntu, install the derivatives execution timer for real trading. The signal
timer is only for a notification-only deployment and is mutually exclusive with
the execution timer:

```bash
sudo cp ops/systemd/atlas20-derivatives-signal.service /etc/systemd/system/
sudo cp ops/systemd/atlas20-derivatives-signal.timer /etc/systemd/system/
sudo cp ops/systemd/atlas20-data-refresh.service /etc/systemd/system/
sudo cp ops/systemd/atlas20-data-refresh.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now atlas20-data-refresh.timer atlas20-derivatives-signal.timer
```

The signal fallback timer fires at 03:45 and 04:15 UTC, after the 01:05 UTC
primary execution attempt, and is mutually exclusive with the execution timer.
The real execution timer fires at 01:05 / 01:35 / 03:05 / 03:35 / 04:35 /
06:35 UTC.

## Idempotency

The spot sender records the last successful `(trial_id, as_of)` pair in
`data/telegram_signal_state.json`; the derivatives sender records
`(spec, signal_date)` per chat id in `data/ls45_g125_telegram_state.json`.
A repeated timer or manual run for the same day is skipped. State is written only
after Telegram confirms `ok: true`, so a failed send can be retried safely.
