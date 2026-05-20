# Batch 14 — Phase O Observability + Scheduler File-Lock

Scope: Roadmap Phase O (O3 Prometheus + O4 Sentry + O5 /healthz+/readyz +
O6 log redaction & rotation) plus B13-deferred R1-Opus-I6 (multi-worker
scheduler dedup via filelock).

Pre-existing from prior batches: O1 structlog JSON
(`src/atlas20/api/logging_config.py`), O2 X-Request-ID middleware
(`src/atlas20/api/middleware/request_id.py`).

## Cycle summary

| Stage | Commits | Backend tests |
|---|---|---|
| Builder (squashed) `4d075be` | 1 | 295 → 316 (+21) |
| Round-1 reviewer fixes | 10 | 316 → 325 (+9) |
| Round-2 Info cleanup | 4 | 325 → 327 (+2) |
| **Total** | **15** | **295 → 327 (+32)** |

Frontend held at 132 throughout (no UI work in Phase O).

## Reviewer scorecard

| Round | Opus | Codex |
|---|---|---|
| 1 | 86/100 REQUEST_CHANGES (2 Critical / 3 Warning / 6 Info) | 77/100 REQUEST_CHANGES (1 Critical / 2 Warning / 0 scoped Info) |
| 2 (post round-1 fixes) | 92/100 APPROVE (4 Info) | 98/100 APPROVE (1 Info) |
| 3 (post round-2 Info cleanup) | 98/100 APPROVE (1 Info — backlog note) | **100/100 APPROVE** |

## Builder commit (1 squashed)

- `4d075be` — `feat(api): R14 batch 14 — phase O observability`

New files: `_metrics.py`, `_log_redact.py`, `middleware/metrics.py`,
`routes/health.py`. Modified: `app.py`, `logging_config.py`, `scheduler.py`,
`settings.py`, `repositories/runs_repo.py`, `dependencies/ratelimit.py`,
`services_report.py`, `middleware/access_log.py`. New tests: `test_metrics.py`,
`test_sentry.py`, `test_health.py`, `test_log_redact.py`, `test_log_rotation.py`,
`test_scheduler_lock.py` (21 tests).

## Round-1 fix commits (10) — Critical + Warning + Info

| Commit | Finding |
|---|---|
| `60bb6fd` | W1 (Codex-Crit + Opus-multi) — centralize metric error handling in `_metrics.py` recorders (try/except + logger.warning) |
| `8b32ec5` | C1 (Opus-I1 + Codex-Crit) — clamp report metric labels to known formats; move 422 validation OUT of try block |
| `ea939e2` | C2 (Opus-I2 + Codex-Crit) — drop raw-path rate-limit fallback; pre-warm `route="unmatched"` |
| `172ded5` | W2 (Codex) — emit `atlas20_backtests_total` on queue cancel + worker recovery paths |
| `6f0f753` | W3 (Codex) — duration histogram: return None / skip observe when neither `duration_s` nor `started_at` known |
| `ac60716` | W4 (Opus-W1) — Sentry hub isolation autouse fixture in conftest.py |
| `001e67a` | W5 (Opus-W2) — drop duplicate `redact_sensitive` from ProcessorFormatter chain |
| `f6fc3e6` | I1 (Opus-N1) — anchor `excluded_handlers` regex (`^/healthz$`, `^/readyz$`) |
| `913b20f` | I3 (Opus-W3) — document `/readyz` exclusion from Prometheus |
| `558bb7a` | I4 (Opus-N3) — cross-reference `/healthz` `/readyz` `/metrics` in `security.md` |

(I2 — pre-warm `route="unmatched"` — was bundled into C2.)

## Round-2 Info cleanup (4) — per user directive "info 也都改完"

| Commit | Finding |
|---|---|
| `86e3fa0` | R3-I1 (Opus) — document metric-before-commit timing trade-off in `_metrics.py` module docstring + `logging.md` |
| `b8dab71` | R3-I2 (Opus) — defensive allow-list clamp inside `record_report_generation` (belt-and-braces) |
| `31ad1ef` | R3-I3 (Opus) — symmetric `requested & REPORT_FORMATS` clamp in report success path |
| `dc7a44e` | R3-I4 (Codex) — direct counter assertion test for `recover_my_own_stale_runs` |

## Outstanding (backlog only)

- `tests/test_metrics.py` uses `Counter._value.get()` (prometheus_client private
  API). Idiomatic in the codebase; backlog note for if prometheus_client ever
  changes internals. Not blocking.

## Cycle verification at HEAD (`dc7a44e`)

- `python -m pytest tests/ -q` → **327 passed, 2 skipped**
- `cd apps/web && npm run test -- --run` → 132 passed
- `cd apps/web && npm run typecheck && npm run lint` → clean
- `git diff --check 4ae8b29..HEAD` → clean
