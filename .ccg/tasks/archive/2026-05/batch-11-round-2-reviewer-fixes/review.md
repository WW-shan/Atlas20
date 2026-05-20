# Batch 11 Round-2 Cross-Validation

Range: `5f49e01..HEAD` (11 commits, includes the round-2 self-fix).

## Reviewers

| Reviewer | Score | Verdict | Notes |
|---|---|---|---|
| Opus 4.7 (`feature-dev:code-reviewer`) | 95/100 | APPROVE | 9/9 round-1 findings RESOLVED. 0 Critical/Warning. 2 Info pre-existing or intentional. |
| Codex (`prompts/codex/reviewer.md`) | 98/100 | APPROVE | 9/9 RESOLVED. Found one new Warning and self-fixed in `5105363`. |

## Per-commit resolution

| Commit | Origin | Status |
|---|---|---|
| `efa4738` | Opus W1 + I1 — CORS prod gate + wildcard+credentials | ✅ (extended by `5105363`) |
| `abbab97` | Codex W — Retry-After on 429 | ✅ |
| `1c2c5ec` | Codex W — R7 cache settings invalidation | ✅ |
| `0175c46` | Opus I6 — Cancel route rate limit | ✅ |
| `2b64b05` | Opus I7 — Default secret prod gate | ✅ |
| `ad1de55` | Opus I2 — Per-process rate-limit docs | ✅ |
| `9108d0a` | Opus I4 — Principal id from `verify_api_key` | ✅ |
| `fa2b145` | Opus W2 — Unauthenticated GET docs | ✅ |
| `339cbdf` | Codex internal — SlowAPI response shadowing | ✅ |

## Round-2 new finding (self-fixed)

**Warning (codex):** `efa4738`'s CORS prod gate only rejected dev origins matching
`http://localhost:<port>` / `http://127.0.0.1:<port>` / `http://[::1]:<port>`.
Bare `localhost`, `https://localhost:5173`, and other loopback IP variants
slipped through.

**Fix `5105363`:** broadened the loopback detection in
`src/atlas20/api/settings.py` to cover scheme+host+optional-port variants; added
4 new regression tests in `tests/test_settings.py`. Backend pytest grew
264 → 269.

## Info follow-ups (not blocking; tracked for Batch 12)

- **I-R2-1** — `dependencies/ratelimit.py:_key_func` returns the raw `X-API-Key`
  as the SlowAPI bucket id, so the full secret lives in the in-process memory
  limiter dict. No network/log leak (access log scrubs headers). Suggested
  follow-up: hash the key before bucketing (e.g. `sha256(key)[:16]`).
- **I-R2-2** — `enforce_prod_gates` runs the wildcard+credentials check
  unconditionally (correctly — the CORS spec forbids that combo in any env).
  Function name slightly misleading; cosmetic rename suggested
  (`enforce_security_gates`).

## Test verification at HEAD (`5105363`)

- `python -m pytest tests/ -q` → **269 passed**
- `cd apps/web && npm run test -- --run` → 132 passed
- `cd apps/web && npm run lint && npm run typecheck` → clean
