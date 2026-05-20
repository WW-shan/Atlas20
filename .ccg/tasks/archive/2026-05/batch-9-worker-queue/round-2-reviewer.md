ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\reviewer.md
<TASK>
Round-2 validation of Atlas20 Batch 9 reviewer fixes.

10 commits in scope, range `12567f5..HEAD`:

```
5ec1596 docs(ops): worker deployment guide
0bf5b71 chore(api): remove dead fallback_runs_queue
598a919 docs(api): publish_report_dir backup-rename semantics
053d3f0 fix(api): heartbeat DB error resilience
af7647c fix(api): configurable heartbeat interval, cancel ≤5s
3ac3634 fix(api): preserve tmp dir contents on mock runs
1f80760 fix(api): PID-scoped worker startup recovery
1a91627 fix(api): clearer cancel 409 messages
45088c6 fix(api): close queued-cancel race in claim + completion
758e7a9 fix(ui): add cancelled status to frontend RunStatusEnum
```

These address round-1 findings from BOTH Opus 4.7 and codex CCG.

Critical fixes to verify:
- 758e7a9 C1: `apps/web/src/components/ui/types.ts` adds "cancelled" to RunStatusEnum; RunQueue/RunTable/RunHistoryTab render a "CANCELLED" pill with rose tone; test asserts it
- 45088c6 C2: `worker/queue.py:claim_one` checks `requested_cancel` before claiming; on True marks status='cancelled' and returns None; `runs_repo.update_metrics_from_completion` forces 'cancelled' when run.requested_cancel is True; 3 new regression tests

Warning fixes:
- 1a91627 W1: routes/runs.py cancel endpoint branches 409 message per terminal status
- 1f80760 W2: worker/recovery.py exports recover_my_own_stale_runs(pid); worker/main.py startup uses it
- 3ac3634 W3: worker/run_one.py mock path no longer unconditionally wipes tmp
- af7647c W4: settings.py adds worker_heartbeat_interval_seconds (default 2.0) and worker_cancel_grace_seconds (default 3.0); worker/main.py uses them; test parametrize with small heartbeat
- 053d3f0 W5: heartbeat loop catches exception per iteration and continues
- 598a919 W6: docstring at publish_report_dir call site

Info fixes:
- 0bf5b71 I2: fallback_runs_queue removed from mock_data.py
- 5ec1596 I3: docs/operations/worker.md added

VALIDATION:
For each commit verify the original finding is fully resolved with code +
regression test, no new regressions.

Run yourself:
- `python -m pytest tests/ -x -q` (expect 207)
- `cd apps/web && npm run test -- --run` (expect 123)
- `cd apps/web && npm run lint` clean
- `cd apps/web && npm run typecheck` clean

WATCH FOR:
- C2: Is the queued-cancel race truly closed? Read claim_one and update_metrics_from_completion side-by-side. Could the race still occur if cancel arrives BETWEEN claim_one's BEGIN IMMEDIATE and the subprocess spawn?
- W4: cancel default config: heartbeat=2 + grace=3 = ~5s. Test asserts under 6s.
- W2: PID-scoped vs lifespan-scoped recovery — both still wired and not redundant?
- 758e7a9: TS type drift — is "cancelled" used everywhere RunStatusEnum is consumed (filtering, switch statements, pill rendering)?

AUTHORITY: apply additional fixes ONLY for new Critical/Warning.
Commit: `fix(api): batch 9 round 2 — <summary>`

REPORT FORMAT:
- Score X/100
- Per-commit: ✅ RESOLVED / ❌ STILL OPEN
- New findings: Critical/Warning/Info
- Fixes applied: commits or 'none'
- Final test count
- Verdict: APPROVE / REQUEST_CHANGES

If no new findings → APPROVE.

Keep under 1000 words.
</TASK>
