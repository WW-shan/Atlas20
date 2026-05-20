ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply Batch 9 round-2 Critical/Warning findings. Two race windows remain in
the cancel path:

1. **Codex C2-residual (Critical)**: cancel-after-claim-before-spawn. After
   `claim_one` commits status='running', before `subprocess.Popen`, if a
   cancel lands, the subprocess still spawns and runs side effects until
   the next heartbeat tick (~2s).

2. **Opus W-1 (Warning)**: failed+cancel race. If subprocess crashes AND
   cancel was requested, status becomes 'failed' instead of 'cancelled'.
   Cancel-wins contract from `update_metrics_from_completion` is not
   honored in the failure path.

## Fix A (Critical) — Pre-spawn cancel guard

File: `src/atlas20/api/worker/main.py:_execute_run`

**Decision (Claude):** before calling `subprocess.Popen`, re-fetch run from
DB and check `requested_cancel`. If True → mark status='cancelled' with
error='cancelled before execution', skip subprocess.

```python
def _execute_run(self, claimed_run: Run) -> None:
    # Re-check cancel flag in a fresh session — claim_one may have committed
    # status='running' before the user's cancel request landed at the route
    # handler.
    with session_scope() as session:
        repo = RunsRepo(session)
        run = repo.get(claimed_run.run_id)
        if run is None:
            return  # disappeared somehow
        if run.requested_cancel:
            repo.update(
                claimed_run.run_id,
                status="cancelled",
                error="cancelled before execution",
                heartbeat_at=None,
            )
            return
    # ... existing subprocess spawn ...
```

**Test in `tests/test_worker_queue.py`:**
- `test_execute_run_skips_subprocess_when_cancel_arrives_after_claim`:
  Mock subprocess.Popen. Seed a running run (post-claim state) with
  requested_cancel=True. Invoke _execute_run. Assert Popen NOT called.
  Assert status='cancelled'.

**Commit:** `fix(api): batch 9 round 2 — pre-spawn cancel guard closes claim/spawn race window`

## Fix B (Warning) — Cancel wins on failed path too

Files:
- `src/atlas20/api/worker/main.py:_mark_failed`
- `src/atlas20/api/worker/run_one.py` exception handler (around line 190-198)
- `src/atlas20/api/repositories/runs_repo.py:update_metrics_from_completion`

**Decision (Claude):** extend `update_metrics_from_completion` to honor
`requested_cancel` for ANY terminal-status transition (completed, failed),
not just completed. Then use `update_metrics_from_completion` everywhere
that writes a terminal status.

```python
# runs_repo.py
def update_metrics_from_completion(self, run_id: str, **fields) -> Run | None:
    run = self.get(run_id)
    if run is None: return None
    # Cancel-wins: if user requested cancel before terminal write lands,
    # promote any terminal status to 'cancelled'.
    if run.requested_cancel and fields.get("status") in {"completed", "failed"}:
        original_status = fields["status"]
        fields["status"] = "cancelled"
        fields["error"] = f"cancelled during execution (would have been {original_status})"
    for key, value in fields.items():
        setattr(run, key, value)
    self._s.add(run)
    self._s.commit()
    self._s.refresh(run)
    return run
```

Refactor:
- `main.py:_mark_failed` → call `update_metrics_from_completion(status="failed", error=...)`
- `run_one.py` exception block → use `update_metrics_from_completion`
- Audit any other `repo.update(status="failed")` direct calls and route them through `update_metrics_from_completion`

**Tests:**
- `test_failed_with_cancel_flag_becomes_cancelled` in test_worker_queue.py:
  set requested_cancel=True on a running run; call
  update_metrics_from_completion(status="failed", error="pipeline crash");
  assert final status='cancelled', error mentions both cancel and crash.
- Update any existing `_mark_failed` tests that asserted status='failed'
  to also cover the requested_cancel=True case.

**Commit:** `fix(api): batch 9 round 2 — cancel-wins contract extends to failed path`

## Procedure

2 atomic commits in order Fix A → Fix B. After each:
- `python -m pytest tests/ -x -q` green
- After Fix B: confirm 207 → 209 passed (2 new regression tests)

Frontend untouched, expect 123 unchanged.

## Report

- 2 commit hashes
- Final backend test count
- Frontend test count (should stay 123)
- Any deviations
</TASK>
