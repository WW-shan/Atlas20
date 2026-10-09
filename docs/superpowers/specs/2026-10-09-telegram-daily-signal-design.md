# Telegram Daily Signal Push Design

**Date:** 2026-10-09
**Status:** approved in conversation

## Goal

Push one Telegram message per day containing the frozen phase-momentum H5 model's
target holdings and rebalance instructions. The user executes trades manually.

## Requirements

- The message is generated from `reports/phase_momentum_live/latest_signal.json`.
- It always reports, once per day:
  - as-of date, target date, BTC gate, gross exposure, trial id, cost assumption;
  - target holdings by coin and weight, plus cash;
  - current model holdings by coin and weight, plus cash;
  - model rebalance actions (`BUY`, `SELL`, `HOLD`) in percentage points;
  - `今日无需调仓` when the target and current model book match.
- "Current model holdings" means the production engine's drifted book, not a real
  brokerage account. No real-account ledger is added.
- Delivery is idempotent per `(trial_id, as_of)` so reruns do not duplicate a
  daily message.
- The script fails closed when the signal file is missing or malformed and does
  not write the sent state until Telegram confirms success.
- Telegram credentials come from environment variables:
  `ATLAS20_TELEGRAM_BOT_TOKEN`, `ATLAS20_TELEGRAM_CHAT_ID`.
- Optional `ATLAS20_TELEGRAM_API_BASE` supports proxies and tests.
- Ubuntu scheduling uses `systemd` service and timer units. No macOS launchd
  dependency is added.

## Non-Goals

- No order placement or exchange integration.
- No real-account position reconciliation.
- No strategy rule, parameter, or backtest changes.
- No new research trials.

## Message Shape

```text
Atlas20 H5 每日信号
As of: 2026-10-08
Target date: 2026-10-08
Trade required: YES
BTC gate: OPEN
Gross target: 62.14%

今日目标持仓:
  NEAR 62.14%
  CASH 37.86%

模型当前持仓:
  NEAR 46.05%
  CASH 53.95%

模型调仓:
  BUY NEAR +16.09pp

Trial: PR2026-10-H5
Cost: 20 bps
信号仅供参考，请手动执行。
```

## Scheduling

The checked-in units target a deployment path of `/opt/atlas20` and run once
daily at 07:30 UTC. The service first regenerates the frozen H5 signal, then
sends it. Operators must adjust the path and timer to match the Ubuntu host.
