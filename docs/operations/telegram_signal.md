# Telegram Daily Signal

> **状态**：现货 Telegram 定时任务已退役；实盘只跑衍生品轨。
> 本文档只保留通知格式、凭据和手工回放说明，不再包含现货生产定时器。
> 实盘四节点入口见 `docs/operations/derivatives_live_runbook.md`。

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

## Scheduling

There is no spot notification timer in the production topology. The derivatives
executor sends its own daily report after a real execution attempt, and the
19:00 Beijing monitor is alert-only. Use the manual commands above for research
replay; do not reinstall the retired spot timer.

## Derivatives track (`PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090`)

The derivatives broadcast matches the current LS104-G175-M090 Bitget USDT-M
track: signed long/short target weights, 1.75x gross cap, isolated margin, 50%
initial buffers per leg, and a 20% mark-price stop on every short
entry/increase. It reads the frozen target book in
`reports/ls45_live_g175/oos_targets.csv` and
sends one message per signal day with:

- signed `BUY`/`SELL` notional and weight changes in pp;
- long and short legs separately labelled, never hidden behind absolute values;
- reference isolated margin, total gross (`sum(abs(notional))`), and the 1.75x cap;
- the single execution time (T+1 01:05 UTC, 09:05 Beijing);
- the target ledger's `execution_hint`, which must be the same T+1 01:05 UTC clock;
- a short-risk line stating that entries carry a 20% mark-price market stop;
- a warning when the execution time has already passed.

```bash
# preview the latest LS104 message (no credentials needed)
.venv/bin/python scripts/send_derivatives_signal.py \
  --targets-file reports/ls45_live_g175/oos_targets.csv \
  --spec PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090 \
  --state-file data/ls45_g175_telegram_state.json \
  --execution-state-file data/ls45_g175_execution_state.json --dry-run

# refresh the live mark tree and rebuild the LS104 ledger, then send one message
make derivatives-live-data derivatives-ls104-signal derivatives-notify-ls104
```

The message is notification-only: it never places an order, does not know any
real exchange position, and repeated runs for the same signal day are skipped by the
`(spec, signal_date)` key in `data/ls45_g175_telegram_state.json`. If the modelled
execution is more than `--max-signal-age-hours` (default 36h) in the past, the
sender refuses to send and exits non-zero. Replay an old ledger deliberately
with `--allow-stale-signal`.

When `--execution-state-file` is supplied (the LS104 Makefile target always
does), the sender uses the matching active event's `equity_at_execution` as the
notional reference. If the state is missing, belongs to another track, or does
not match the target signal/weights, it fails closed instead of silently
falling back to the 1,000 USDT reference book.

The executor records `telegram_sent_key` only after its Telegram send succeeds.
The fallback sender compares that marker with `last_key` and skips when the
same successful execution report was already delivered; `--force` is the
explicit override for a deliberate resend. If the executor notification fails,
the marker is not written, so the later fallback attempt remains active.

On Ubuntu, install the same four production nodes documented in the live
runbook: data (00:30 UTC), signal (00:35 UTC), execution (01:05 UTC) and the
read-only monitor. Do not install a separate notification or retry timer; the
executor sends the execution report, and a failed node is surfaced by the
monitor for an operator decision.

## Idempotency

The spot sender records the last successful `(trial_id, as_of)` pair in
`data/telegram_signal_state.json`; the derivatives sender records
`(spec, signal_date)` per chat id in `data/ls45_g175_telegram_state.json`.
A repeated timer or manual run for the same day is skipped. State is written only
after Telegram confirms `ok: true`, so a failed send can be retried safely.
