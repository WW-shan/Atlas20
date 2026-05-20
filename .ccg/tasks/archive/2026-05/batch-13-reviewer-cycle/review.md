# Batch 13 Reviewer Cycle (Phase F Report Generation)

Builder commit: `4924dec feat(api): R13 batch 13 — phase F reports`
(archived separately under `batch-13-phase-f-reports/`).

Cycle range: `4924dec..HEAD` — 15 fix commits across 4 fixer rounds, validated
by 3 pairs of parallel Opus + codex reviewers per
`.ccg/process/batch-execution-protocol.md` Step 6.

## Final reviewer verdicts

| Round | Opus | Codex |
|---|---|---|
| 1 | 72/100 REQUEST_CHANGES (1 Critical, 3 Warnings, 8 Info) | 72/100 REQUEST_CHANGES (1 Critical, 5 Warnings, 2 Info) |
| 2 | 90/100 REQUEST_CHANGES (1 Warning, 1 Info) | 86/100 REQUEST_CHANGES (1 Warning, 2 Info) |
| 3 | 96/100 APPROVE | 96/100 APPROVE (1 self-fix `e63f928`) |
| 4 (Info cleanup per user directive) | — | — |
| 5 | 96/100 APPROVE | **100/100 APPROVE** |

## Fix commits by round

### Round 1 (6 commits — Critical + Warnings from combined Opus + Codex round-1 review)

| Commit | Finding |
|---|---|
| `c354a15` | C1 (both) — frontend `requestJson<{url}>` vs backend `FileResponse` contract; window.open can't send X-API-Key on GET downloads |
| `31c175e` | W1 (Opus+Codex) — bundle ZIP includes stale manifest; partial regen orphans DB rows for older kinds |
| `5f439b6` | W2 (Opus) — `_first_existing` raises `FileNotFoundError` → 500 (now 404) |
| `ddb32d9` | W3 (Opus) — `_generate_png` early-returns when file exists; stale PNG vs CSV |
| `4d706fc` | W4 (Codex) — disk-fallback download bypasses sha256 whitelist |
| `905cd5c` | W5 (Codex) — PID-only tmp names race on concurrent same-process generation |

### Round 2 (3 commits — round-2 reviewer findings)

| Commit | Finding |
|---|---|
| `bf543f7` | R2-W1 (Opus) — `_generate_png` was missed by W5 round-1 sweep; route through `_tmp_path` helper |
| `04a5a4d` | R2-W2 (Codex) + R2-Info-A (Opus) — guard `write_report_manifest` against non-dict JSON; emit `logger.warning` on corrupt manifest |
| `1a1d0e4` | R2-Info-B (Codex) — drop `_fallback_featured_path` rglob; require KV pointer + DB row |

### Round 3 (1 commit — codex self-fix during validation)

| Commit | Finding |
|---|---|
| `e63f928` | R3-W (Codex self-fix) — dict manifest with non-list `artifacts` (e.g. `{"artifacts": 1}`) raised TypeError; added isinstance(list) guard |

### Round 4 (5 commits — Info cleanup per user directive "info 也都改完")

| Commit | Finding |
|---|---|
| `929464b` | R1-Opus-I1 — bundle double-hash perf (cache `row.sha256` in manifest writer) |
| `41a5136` | R1-Opus-I3 — symlink test docstring documents Windows-skip + CI-Linux requirement |
| `ea449ca` | R1-Codex-Info — CLI `--week` `--help` clarifies "run offset, NOT ISO calendar week" |
| `8628ae3` | R3-Opus-I1 — added test coverage for OSError branch of `write_report_manifest` |
| `5e925f3` | R3-Opus-I2 — extracted `_tmp_name` helper in `reporting/report.py`; routed inline tmp patterns through it |

## Deferred to Batch 14 (Phase O observability)

- **R1-Opus-I6** — Multi-worker scheduler dedup. Currently each uvicorn worker
  boots its own `AsyncIOScheduler` → digest generates N× per Monday. Needs
  file-lock or leader-elect (architectural change, not polish).

## Test trajectory

| Round | Backend | Frontend |
|---|---|---|
| Builder (`4924dec`) | 286 + 2 skipped | 132 |
| After round 1 (6 fixes) | 290 + 2 skipped | 132 |
| After round 2 (3 fixes) | 292 + 2 skipped | 132 |
| After round 3 self-fix | 293 + 2 skipped | 132 |
| After round 4 (5 fixes) | **295 + 2 skipped** | **132** |

Net regression coverage added across the cycle: **+9 backend tests**
(security path safety, manifest merge, OSError fallback, double-hash perf,
malformed payload guard, featured rejection without KV+DB).

## Cycle verification at final HEAD (`5e925f3`)

- `python -m pytest tests/ -q` → 295 passed, 2 skipped
- `cd apps/web && npm run test -- --run` → 132 passed
- `cd apps/web && npm run typecheck && npm run lint` → clean
- `git diff --check 4924dec..HEAD` → clean
