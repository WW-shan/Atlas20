# Batch 17 Smoke Follow-up — Final Cross-Validation Matrix

**Branch:** `redesign/r3-premium`
**Final HEAD:** `c543d7a` (r13)
**Termination criterion:** Both reviewers (Opus 4.7 + codex) return zero in-scope findings.

## Round-by-round outcomes

| Round | Claude (Opus 4.7) | Codex | New in-scope findings | Action |
| --- | --- | --- | --- | --- |
| r1 (originals) | — | — | 3 Critical (A/B/C) from smoke | builder commits b4b9ed8 / 89a8b71 / 4f7c9f0 |
| r2 | 80/100 REQUEST_CHANGES (1C/4W) | 75/100 REQUEST_CHANGES (1C/3W+codex-deviation justified) | Critical C1 (counters dropped in subprocess), W1–W4 | fixer commits e283558 / 020353e / 7ce2947 / 970929f / a420f20 |
| r3 | 78/100 REQUEST_CHANGES | 79/100 REQUEST_CHANGES | 1 Critical (multiproc dir wipe) + 3 Warning | fixer commits d47754c / 6363106 / 57e81ef / f485ddd |
| r5 | 90/100 REQUEST_CHANGES | 87/100 REQUEST_CHANGES | 2 doc inconsistencies | c54b776 |
| r7 | 92/100 REQUEST_CHANGES | 88/100 REQUEST_CHANGES | 3 doc contradictions | e5c3968 |
| r9 | 94/100 APPROVE | 86/100 REQUEST_CHANGES | 2 doc gaps (codex paranoia) | 9339ebf |
| r11 | 95/100 APPROVE | 88/100 REQUEST_CHANGES | 3 pre-existing doc bugs surfaced by codex paranoia | db6cfea |
| r12 | 91/100 REQUEST_CHANGES (1 Critical) | 92/100 REQUEST_CHANGES (1 Warning) | L37/L40 hostnames + L27 description | c543d7a (r13) |
| **r14** | **96/100 APPROVE** | **100/100 APPROVE** | **0** | **— ship —** |

## Commits landed (B17 cycle, ordered)

1. `b4b9ed8` fix(reporting): graceful N/A fallback when benchmark strategies absent
2. `89a8b71` fix(api): worker exposes /metrics on dedicated port
3. `4f7c9f0` fix(infra): Makefile PYTHONPATH=src + README editable install + lifespan shadow warning
4. `e283558` fix(api): r2 — worker /metrics aggregates run_one subprocess counters via PROMETHEUS_MULTIPROC_DIR
5. `020353e` fix(infra): r2 — worker compose service overrides image HEALTHCHECK to scrape :8001/metrics
6. `7ce2947` fix(api): r2 — start_metrics_server tolerates EADDRINUSE under spawn.py multi-worker
7. `970929f` docs(infra): r2 — corrected Prometheus scrape doc lists API vs worker counters and histogram PromQL
8. `a420f20` fix(api): r2 — worker startup also emits shadow-install warning
9. `d47754c` fix(api): r3 — wipe PROMETHEUS_MULTIPROC_DIR on worker startup; spawn.py coordinates once-only wipe
10. `6363106` fix(api): r3 — start_metrics_server narrows to EADDRINUSE and warns when counters will be dropped
11. `57e81ef` docs(infra): r3 — worker.md uses new python -m atlas20.api.worker entrypoint
12. `f485ddd` docs(infra): r3 — clarify atlas20_backtests_total is also emitted by API lifespan recovery
13. `c54b776` docs(infra): r5 — close two cross-validation gaps in logging.md
14. `e5c3968` docs(infra): r7 — fix three internal contradictions in logging.md
15. `9339ebf` docs(infra): r9 — close codex final-review doc gaps in logging.md
16. `db6cfea` docs(infra): r11 — fix pre-existing logging.md inaccuracies surfaced by codex paranoia scan
17. `c543d7a` docs(infra): r13 — close r12 dual-reviewer doc gaps in logging.md

## Test verification at HEAD

- `PYTHONPATH=src python -m pytest tests/ -q` → **361 passed, 2 skipped**
- vitest → 161 (unchanged across cycle)
- `python scripts/verify_release.py` → exit 0

## Deferred Info findings (B18 candidates)

Per Opus reviewer "acceptable for MVP" and out-of-scope at r12+:

- `docs/operations/worker.md:35` mildly overstates PID-recovery scope
- `docs/redesign/ROADMAP.md:413` lists implemented O3/O5 items as unchecked
- `__main__.py` always creates default multiproc path even when env supplied
- Worker imports app.py top-level (could be a small standalone module)
- Healthcheck only probes HTTP listener thread, not queue loop
- Multiproc test uses `python -c`, not real run_one subprocess

## Observed asymmetry

Across r2–r12, **codex's paranoia mode surfaced 5 findings Opus missed** (mostly pre-existing doc bugs uncovered when its scan scope expanded). **Opus surfaced 2 Criticals codex missed** (r2 C1 multiproc, r12 docker-compose hostname). Conclusion: alternating cycles paid off — neither reviewer alone would have terminated at zero findings.
