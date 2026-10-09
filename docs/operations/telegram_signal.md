# Telegram Daily Signal

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
   a group.

4. Store the credentials outside the repository:

   ```bash
   mkdir -p ~/.config/atlas20
   cat > ~/.config/atlas20/telegram.env <<'ENV'
   ATLAS20_TELEGRAM_BOT_TOKEN=123456:replace-me
   ATLAS20_TELEGRAM_CHAT_ID=123456789
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

## Idempotency

The sender records the last successful `(trial_id, as_of)` pair in
`data/telegram_signal_state.json`. A repeated timer or manual run for the same
day is skipped. The state is written only after Telegram confirms `ok: true`, so
a failed send can be retried safely.
