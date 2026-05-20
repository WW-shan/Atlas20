# Sanity Audit Post-B15

End-to-end full-repo audit triggered by user after B15 archived. Joint
parallel audit: Claude full sweep + codex full sweep. Codex caught 6 items
Claude missed (1 Critical + 5 Warning/Info); reviewer pattern paid off.

## Cycle summary

| Stage | Commits | Backend | Frontend |
|---|---|---|---|
| Round-1 fixes (7 atomic) | 7 | 327 → 329 (+2 W1/W2 tests) | 156 → 157 (+1 W3 nested-main axe regression) |
| Round-2 Info cleanup (3 atomic) | 3 | 329 → 332 (+3 hygiene tests) | unchanged |
| **Total** | **10** | **327 → 332 (+5 tests)** | **156 → 157 (+1 test)** |

## Audit scorecard

| Round | Opus | Codex |
|---|---|---|
| 1 (audit on HEAD) | full sweep, all gates green | 80/100 NEEDS_FIXES (1 Critical / 4 Warning / 2 Info) |
| 2 (post round-1 fixes) | 96/100 APPROVE (4 Info) | 96/100 APPROVE (1 Info) |
| Post round-2 Info cleanup | not re-reviewed (3 trivial defensive fixes verified by tests) |

Claude's pre-dispatch full sweep showed all gates green but missed 4 of
Codex's 6 findings. Lesson: per-batch reviewer chain prevents regressions
but full-repo cross-cutting audit catches a different class of issues
(release-gate scripts, route policy uniformity, landmark composition, dev
UX vs CI alignment, test perf).

## Round-1 fix commits (7)

| Commit | Finding |
|---|---|
| `e30c076` | C1 (Codex) — `scripts/verify_release.py` exit 1; `check_repo_health.py` flagged archived `.md` + `tests/test_settings.py` intentional dummies; `git diff --check` complained about archive whitespace |
| `c97fedb` | W1 (Codex) — `POST /runs/{id}/favorite` missing rate limit (cancel had one, favorite didn't) |
| `69d7df4` | W2 (Codex) — `/api/reports/generate` no-completed-run path returned `status="completed"` without emitting `atlas20_report_generations_total` |
| `544ff77` | W3 (Codex) — nested `<main>` in `AppShell.tsx:30` AND `ResearchConsolePage.tsx:65` (WCAG landmark-no-duplicate-main) |
| `8ab18dd` | W4 (Codex) — `make typecheck` ran broad `mypy --strict src/atlas20/api` (145 errors) while CI only checked 3 leaf files |
| `46488d6` | W5 (Codex Info→W) — React act() warnings in axe tests for several tabs + RunTable header a11y fix (legitimate, not paper-over) |
| `c847a50` | I1 (Codex) — `time.sleep(1.1)` in test_generate_report.py:179 (replaced with `os.utime` for instant mtime delta) |

## Round-2 Info cleanup (3)

| Commit | Finding |
|---|---|
| `0374edf` | Opus R2-Info2 — `record_report_generation` validated format but not status against `REPORT_STATUSES` allow-list (symmetric guard added) |
| `5025ead` | Opus R2-Info1 — `check_repo_health.py` EXCLUDE_PATHS had no regression test (added test asserting archive/ + tests/ skipped but src/ flagged) |
| `2ff9801` | Codex R2-Info — `/api/reports/generate` HTTPException-fallback path emitted skipped metric but no direct regression test (monkeypatched test added) |

## Outstanding (informational, not blocking v1 tag)

- `app-shell-main` class has no CSS rule — purely structural wrapper, no styling break (Opus R2-Info3).
- Favorite 60/min rate could throttle hypothetical bulk-select UI (Opus R2-Info4); raise if needed when feature ships.
- `.context/` directory not present — codex noted this is a project context dir it expects; not Atlas20 convention (Codex R2-Info).

## Final verification at HEAD (`2ff9801`)

- `python -m pytest tests/ -q` → **332 passed, 2 skipped** (was 327 + 2; +5 from 5 hygiene/regression tests)
- `cd apps/web && npm run test -- --run` → 157 passed
- `cd apps/web && npm run typecheck && npm run lint && npm run build` → clean
- `python scripts/verify_release.py` → **exit 0**
- `ruff check src tests` → clean
- `mypy --strict src/atlas20/api/schemas.py src/atlas20/api/settings.py src/atlas20/api/_metrics.py` → clean
- `git diff --check d73ce8f~30..HEAD` → clean

**MS-3 production-readiness fully verified. Repo ready for v1 tag.**
