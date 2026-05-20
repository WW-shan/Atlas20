ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\reviewer.md
<TASK>
Round-3 spot validation of Batch 9 round-2 race fixes.

2 commits in scope, range `5ec1596..HEAD`:

- `13d4a96 fix(api): batch 9 round 2 — pre-spawn cancel guard closes claim/spawn race window`
- `eec80ff fix(api): batch 9 round 2 — cancel-wins contract extends to failed path`

PRIOR CRITICAL FINDING (codex round-2): cancel-after-claim-before-spawn race
window left subprocess running side effects.

PRIOR WARNING FINDING (Opus round-2): failed+cancel race — status='failed'
overrode user's cancel intent.

VERIFY:

1. **13d4a96**: read `src/atlas20/api/worker/main.py:_execute_run`.
   Confirm there's a fresh DB read of `requested_cancel` AFTER claim_one
   commits and BEFORE `subprocess.Popen`. If True → status='cancelled',
   `error='cancelled before execution'`, return without spawning.
   Regression test exercises this path with Popen mocked.

2. **eec80ff**: read `src/atlas20/api/repositories/runs_repo.py`
   `update_metrics_from_completion`. Confirm the cancel-wins clause now
   triggers for BOTH `status="completed"` AND `status="failed"`. Verify
   error message includes the original status (e.g., "would have been failed").
   Verify `_mark_failed` in main.py and the exception block in run_one.py
   both route through this function (not direct `repo.update(status="failed")`).
   Regression test asserts requested_cancel=True + status=failed → final cancelled.

3. NEW RACE WINDOWS to look for:
   - What if `requested_cancel` arrives AFTER `update_metrics_from_completion`
     committed? (Acceptable — user sees completed/failed run; they should
     not have been able to cancel after the fact since cancel returns 409
     for terminal status.)
   - What about the heartbeat thread vs pre-spawn guard? They both might
     try to mark cancelled concurrently. Should be idempotent.
   - What about `_mark_failed` vs heartbeat-driven cancellation?

4. **Test coverage**:
   - 209 - 207 = 2 new tests for these 2 fixes
   - The pre-spawn race test uses `mock_subprocess.Popen` and asserts
     not_called
   - The failed+cancel test creates a running run with requested_cancel=True
     and calls update_metrics_from_completion(status="failed")

Run yourself:
- `python -m pytest tests/ -x -q` (expect 209)
- `cd apps/web && npm run test -- --run` (expect 123)
- `cd apps/web && npm run lint && npm run typecheck` clean

AUTHORITY: apply fixes ONLY for new Critical/Warning. Commit as
`fix(api): batch 9 round 3 — <summary>`. Each fix separate.

OUTPUT:
- Score X/100
- Each of 2 commits: ✅ RESOLVED / ❌ STILL OPEN
- New findings: Critical / Warning / Info
- Fixes applied: commits or 'none'
- Final test count
- Verdict: APPROVE / REQUEST_CHANGES

If no new findings AND both originals resolved → APPROVE.

Keep under 800 words.
</TASK>
