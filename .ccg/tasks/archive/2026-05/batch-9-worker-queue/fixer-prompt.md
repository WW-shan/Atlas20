ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply Atlas20 Batch 9 round-1 reviewer fixes. 2 Critical + 6 Warning + 2
actionable Info from combined Opus 4.7 + codex CCG review.

Each fix = separate commit. Run pytest after each.

## C1 — Frontend `RunStatusEnum` missing `"cancelled"`

**Files:**
- `apps/web/src/components/ui/types.ts:7` — add `"cancelled"` to the union
- Any TS switch on status: `RunQueue.tsx:10`, `RunTable.tsx:15`,
  `RunHistoryTab.tsx:185` — add `cancelled` case (display "CANCELLED" pill,
  tone `"muted"` or `"rose"`, icon similar to failed but distinct)
- `apps/web/src/lib/api.ts` — same union if defined there

**Decision (Claude):** display `cancelled` with rose tone + label "CANCELLED".

**Test:** add Vitest case asserting `RunTable` renders "CANCELLED" pill for
a row with `status="cancelled"`. Update existing exhaustive-switch tests
if any.

**Commit:** `fix(ui): batch 9 reviewer pass — add cancelled status to frontend RunStatusEnum`

## C2 — Queued-cancel race condition

**Problem chain:**
1. User POSTs cancel on a queued run → `requested_cancel=True`, status stays `queued`
2. Worker `claim_one` picks it up (claim doesn't check `requested_cancel`) → status becomes `running`
3. Subprocess starts; before heartbeat tick checks `requested_cancel`, subprocess may complete
4. `update_metrics_from_completion` overwrites status to `completed` AND (per codex finding) clears `requested_cancel=False`

**Fix decision (Claude):** TWO changes:

**Fix 2a** — in `src/atlas20/api/worker/queue.py:claim_one`:
After locking with BEGIN IMMEDIATE, check `requested_cancel`. If True:
- Mark status='cancelled', error='cancelled before execution', started_at=utc_now(), heartbeat_at=None
- Commit and return None (so worker proceeds to next iteration without spawning subprocess)

```python
def claim_one(self) -> Run | None:
    self._begin_immediate_for_sqlite()
    candidate = self._s.exec(
        select(Run).where(Run.status == "queued").order_by(Run.created_at.asc()).limit(1)
    ).first()
    if candidate is None:
        return None
    if candidate.requested_cancel:
        candidate.status = "cancelled"
        candidate.error = "cancelled before execution"
        candidate.started_at = utc_now()
        self._s.add(candidate)
        self._s.commit()
        return None
    # ... existing claim logic ...
```

**Fix 2b** — in `src/atlas20/api/repositories/runs_repo.py:update_metrics_from_completion`:
DO NOT clear `requested_cancel`. Audit any other repo method that mutates it.
Also: if `requested_cancel=True` is set when worker calls
`update_metrics_from_completion(status="completed")`, refuse to overwrite:
either keep as `running` (worker will mark cancelled next tick) OR set to
`cancelled` directly. Decision: set to `cancelled`.

```python
def update_metrics_from_completion(self, run_id: str, **fields) -> Run | None:
    run = self.get(run_id)
    if run is None: return None
    # If cancel was requested concurrently, force cancelled regardless of completion
    if run.requested_cancel and fields.get("status") == "completed":
        fields["status"] = "cancelled"
        fields.setdefault("error", "cancelled during execution")
    for key, value in fields.items():
        setattr(run, key, value)
    self._s.add(run)
    self._s.commit()
    self._s.refresh(run)
    return run
```

**Tests:** add to `tests/test_worker_queue.py`:
- `test_claim_one_skips_queued_with_requested_cancel` — seed a queued run
  with requested_cancel=True; call claim_one; assert returns None and
  status='cancelled'.
- `test_update_metrics_respects_concurrent_cancel` — set
  requested_cancel=True on a running run, then call update_metrics_from_completion
  with status='completed'; assert final status='cancelled'.
- `test_cancel_queued_run_never_executes_subprocess` (integration) — POST
  cancel on a queued run; start worker; assert subprocess NOT invoked
  (mock `subprocess.Popen` and assert no call).

**Commit:** `fix(api): batch 9 reviewer pass — close queued-cancel race in claim + completion`

## W1 — Cancel 409 message phrasing

File: `src/atlas20/api/routes/runs.py:81-82`

**Fix:**
```python
if run.status == "cancelled":
    raise HTTPException(409, "run is already cancelled")
if run.status == "completed":
    raise HTTPException(409, "run already completed; cannot cancel")
if run.status == "failed":
    raise HTTPException(409, "run already failed; cannot cancel")
# else: queued or running → accept
```

**Test:** assert each 409 message text in test_cancel_route.py.

**Commit:** `fix(api): batch 9 reviewer pass — clearer cancel 409 messages per terminal status`

## W2 — Worker-startup recovery not PID-scoped

File: `src/atlas20/api/worker/main.py:_recover_on_startup` (or similar)

**Current:** calls `recover_stale_runs(stale_after=60)` which marks ANY
stale running run failed — including sibling workers' active runs.

**Fix decision (Claude):** add PID-scoped variant.

In `src/atlas20/api/worker/recovery.py`:
```python
def recover_my_own_stale_runs(session: Session, my_pid: int) -> int:
    """Mark runs failed that are stuck on a dead PID (the current worker's PID before crash).

    On worker startup, only recovers runs that claim THIS worker's PID, since
    sibling workers may still be alive with valid heartbeats.
    """
    runs = session.exec(
        select(Run).where(Run.status == "running", Run.worker_pid == my_pid)
    ).all()
    count = 0
    for run in runs:
        run.status = "failed"
        run.error = "worker died — restart recovery"
        session.add(run)
        count += 1
    session.commit()
    return count
```

In worker/main.py startup:
```python
def _recover_on_startup(session):
    return recover_my_own_stale_runs(session, my_pid=os.getpid())
```

Lifespan in app.py keeps using the broad `recover_stale_runs(60)` (FastAPI
process is the central coordinator; OK to broadly recover).

**Test:** add to test_restart_recovery.py:
- `test_worker_startup_recovery_skips_other_workers_runs` — seed two
  running runs with different worker_pid; call recover_my_own_stale_runs
  for one pid; assert only that one becomes failed.

**Commit:** `fix(api): batch 9 reviewer pass — PID-scoped worker startup recovery`

## W3 — Mock tmp dir wipe destroys debug artifacts

File: `src/atlas20/api/worker/run_one.py:_prepare_tmp_dir` (lines ~132-135)

**Current:** unconditionally `shutil.rmtree(path)` before mock writes.

**Fix decision (Claude):** remove the unconditional wipe in mock path. Mock
artifacts can overwrite individual files (use `path.mkdir(exist_ok=True)`
and individual file writes). If a previous failed run left a tmp dir, it
gets overwritten file-by-file; nothing else is destroyed.

Same semantics as real pipeline path (which doesn't wipe).

**Test:** update existing mock test to verify pre-existing junk files in
tmp dir remain after mock run (or are overwritten only if same filename).

**Commit:** `fix(api): batch 9 reviewer pass — preserve tmp dir contents on mock-mode runs`

## W4 — Heartbeat interval hardcoded; cancel latency > 5s

Files:
- `src/atlas20/api/settings.py` — add `worker_heartbeat_interval_seconds: float = 2.0`
  and `worker_cancel_grace_seconds: float = 3.0`
- `src/atlas20/api/worker/main.py` — replace hardcoded `10.0` and `5.0` with
  these settings

**Decision (Claude):** defaults give worst-case cancel ≈ 5s (2s heartbeat
tick + 3s grace = 5s). Tests can override via env or fixture.

**Test:** parametrize cancel test with heartbeat=0.1 to assert ≤1s cancel.

**Commit:** `fix(api): batch 9 reviewer pass — configurable heartbeat interval, cancel ≤5s default`

## W5 — Heartbeat DB errors uncaught

File: `src/atlas20/api/worker/main.py:_heartbeat_loop`

**Fix:** wrap each iteration in try/except. Log + continue.

```python
def _heartbeat_loop(self, run_id, stop_event):
    while not stop_event.is_set():
        try:
            with Session(engine) as session:
                repo = RunsRepo(session)
                run = repo.get(run_id)
                if run and run.requested_cancel:
                    return "cancel_requested"
                if run:
                    repo.update(run_id, heartbeat_at=utc_now())
        except Exception as exc:
            logger.warning("heartbeat tick failed: %s", exc)
        stop_event.wait(self._heartbeat_interval)
    return None
```

**Test:** mock Session to raise OperationalError on first call, second call
succeeds; assert heartbeat thread doesn't die.

**Commit:** `fix(api): batch 9 reviewer pass — heartbeat resilience under DB errors`

## W6 — `_publish_report_dir` not pure `os.replace`

File: `src/atlas20/api/worker/run_one.py:_publish_report_dir`

**Decision (Claude):** the brief's reuse of Batch 1's
`_publish_report_dir` (which uses shutil.move + backup) is intentional —
backup-rename is safer than raw os.replace under partial failure. Keep as
is. Add a docstring near the call site explaining why.

```python
# Uses Batch 1's _publish_report_dir which performs backup-rename
# (move existing → .backup, move tmp → final, delete .backup on success).
# This is intentionally NOT a single os.replace because we want crash-safe
# rollback of a partial publish.
report.publish_report_dir(tmp_dir, final_dir)
```

**No test, no behavior change.**

**Commit:** `docs(api): batch 9 reviewer pass — document publish_report_dir backup-rename semantics`

## I2 — Remove dead `fallback_runs_queue` constant

File: `src/atlas20/api/mock_data.py:131` (or wherever)

After Batch 7 + Batch 9, no API code reads or mutates this constant.

**Fix:** `grep -rn "fallback_runs_queue" src/ tests/` and remove if truly
unused. Keep `fallback_runs_list` (still used as seed source).

**Commit:** `chore(api): batch 9 reviewer pass — remove dead fallback_runs_queue mock constant`

## I3 — Worker deployment docs

**Fix:** add `docs/operations/worker.md` covering:
- How to launch workers (`python -m atlas20.api.worker.main`)
- `ATLAS20_WORKERS` env var
- `ATLAS20_WORKER_MOCK` testing flag
- Behavior under packaged install (works via stdlib, no extra steps)
- Cancellation latency expectation (~5s worst case)
- Restart recovery semantics

**No test.**

**Commit:** `docs(ops): batch 9 reviewer pass — worker deployment guide`

## Procedure

10 atomic commits in order C1, C2, W1-W6, I2, I3. After EACH:
- `python -m pytest tests/ -x -q` green
- After C1: `cd apps/web && npm run test -- --run` green (122 → 123 with
  cancelled pill test)
- After C1: `npm run typecheck` clean (RunStatusEnum union now exhaustive)
- After C1: `npm run lint` clean

## Report

- 10 commit hashes
- Final backend test count (was 198 → expect ~205)
- Final frontend test count (was 122 → expect 123)
- Any deviations
</TASK>
