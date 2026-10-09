# Telegram Daily Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development.

**Goal:** Add a tested, idempotent daily Telegram push for the frozen H5 model signal.

**Architecture:** A standalone sender reads the existing live-signal JSON, formats model holdings and rebalance deltas, posts through the Telegram Bot API, and records a local sent-state file only after success. Ubuntu systemd units schedule the existing signal generator followed by the sender.

**Tech Stack:** Python 3.11, `requests`, pytest, Ubuntu systemd.

---

### Task 1: Message formatting

**Files:**
- Create: `tests/test_send_telegram_signal.py`
- Create: `scripts/send_telegram_signal.py`

- [x] Write a failing test that builds a payload with target `NEAR 62%`, current
  `NEAR 46%`, and asserts the formatted message contains the target holdings,
  current model holdings, cash, and `BUY NEAR +16.00pp`.
- [x] Run `.venv/bin/python -m pytest tests/test_send_telegram_signal.py -q` and
  confirm it fails because the module/function does not exist.
- [x] Implement `format_signal_message(payload)` with the exact text shape in the
  design spec.
- [x] Rerun the test and confirm it passes.

### Task 2: Idempotency and CLI behavior

**Files:**
- Modify: `tests/test_send_telegram_signal.py`
- Modify: `scripts/send_telegram_signal.py`

- [x] Add failing tests for: same `(trial_id, as_of)` is skipped; `--force`
  resends; `--dry-run` prints without credentials or state writes.
- [x] Run the focused tests and confirm the expected failures.
- [x] Implement signal loading, state-file read/write, argument parsing, and the
  skip/send control flow.
- [x] Rerun the focused tests and confirm they pass.

### Task 3: Telegram transport

**Files:**
- Modify: `tests/test_send_telegram_signal.py`
- Modify: `scripts/send_telegram_signal.py`

- [x] Add failing tests for successful `sendMessage`, retrying a 500 response,
  and failing without exposing the bot token.
- [x] Run the focused tests and confirm the expected failures.
- [x] Implement `send_telegram_message(...)` using `requests.post` with timeout,
  bounded retries, and token-redacted errors.
- [x] Rerun the focused tests and confirm they pass.

### Task 4: Ubuntu scheduling and operations docs

**Files:**
- Create: `ops/systemd/atlas20-telegram-signal.service`
- Create: `ops/systemd/atlas20-telegram-signal.timer`
- Create: `docs/operations/telegram_signal.md`
- Modify: `.env.example`
- Modify: `.gitignore`
- Modify: `README.md`

- [x] Add the systemd units with `/opt/atlas20` as the documented deployment
  path and 07:30 UTC daily timer.
- [x] Document BotFather setup, chat id discovery, `/etc/atlas20/telegram.env`,
  manual macOS testing, and Ubuntu installation.
- [x] Add Telegram environment variable examples and ignore the local state file.

### Task 5: Verification

- [x] Run `.venv/bin/python -m pytest tests/test_send_telegram_signal.py -q`.
- [x] Run `make lint`.
- [x] Run `make typecheck`.
- [x] Run `.venv/bin/python scripts/check_repo_health.py`.
- [x] Run the relevant live-signal tests.
- [x] Commit and push the complete change.
