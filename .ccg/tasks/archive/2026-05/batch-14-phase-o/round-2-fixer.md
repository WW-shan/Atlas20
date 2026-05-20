ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply Batch 14 Round-2 reviewer Info-cleanup findings per user directive and
protocol Lesson 9 ("Info 级别 finding 也要修"). Opus 92/100 + Codex 98/100 both
APPROVED with the 10 round-1 fixes; this round addresses the 4 outstanding Info
items so 0 tech debt carries forward.

4 atomic fixes. **Each = separate commit.** Run pytest after each. Frontend
stays 132. Backend climbs 325 → 326 (only R3-I4 adds a test case).

Range: starts from current HEAD `558bb7a`.

---

## R3-I1 — Document metric-before-commit ordering trade-off

**Files:** `src/atlas20/api/_metrics.py` (add module docstring section) AND
`docs/operations/logging.md` (add a short note).

**Problem (Opus-Round2-Info1):** `record_backtest_terminal` is called BEFORE
the surrounding DB commit in `worker/queue.py`, `worker/recovery.py`, and
`runs_repo._record_terminal_transition` callers. If the DB commit rolls back,
the Prometheus counter has already been incremented → permanent overcount.
Likelihood is low (commits rarely fail post-flush) and Prometheus counters
are monotonic anyway, but it's worth documenting.

**Decision (Claude):** No code change — refactoring to after-commit hooks
adds complexity disproportionate to the risk. Instead document the trade-off
in two places:

1. Add a module-level comment block at the top of `src/atlas20/api/_metrics.py`:

```python
"""Atlas20 Prometheus metric recorders.

Recorder timing trade-off
-------------------------
All counters/histograms here are emitted BEFORE the surrounding DB transaction
commits (see worker/queue.py, worker/recovery.py, repositories/runs_repo.py).
A rollback after a recorder call leaves Prometheus permanently over-counted
versus the DB. We accept this trade-off because (a) post-flush commits
rarely fail in this codebase, (b) Prometheus counters are monotonic so
"slightly high" is operationally tolerable, and (c) an after-commit hook
would couple metric emission to ORM lifecycle events in ways that hurt
testability. Track for future hardening if the divergence ever becomes
operationally visible.
"""
```

2. Add a short paragraph in `docs/operations/logging.md` (in a new "Metrics
correctness caveats" section near the existing `/readyz` exclusion note):

> **Counters may slightly over-count on rollback.** Backtest terminal counters
> and report-generation counters are incremented before the surrounding DB
> transaction commits. A commit failure leaves Prometheus over-reporting by 1.
> We accept this as Prometheus counters are monotonic and commit failures are
> rare in this codebase. Track via the existing 5xx alert if the divergence
> ever becomes visible.

**Test:** docs/comments only — no regression test.

**Commit:** `docs(api): batch 14 round 2 info — document metric-before-commit timing trade-off`

---

## R3-I2 — Defensive label clamp inside `record_report_generation`

**File:** `src/atlas20/api/_metrics.py`.

**Problem (Opus-Round2-Info2):** `record_report_generation(format_name, status)`
accepts arbitrary `format_name` strings. The single caller in `services_report.py`
clamps to `requested & REPORT_FORMATS` but a future caller could bypass it.

**Decision:** Add a defensive guard inside the recorder so misuse can't blow
up cardinality:

```python
from atlas20.api.schemas import REPORT_FORMATS

def record_report_generation(format_name: str, status: str) -> None:
    if format_name not in REPORT_FORMATS:
        logger.warning("ignoring metric for unknown report format: %s", format_name)
        return
    try:
        REPORT_GENERATIONS_TOTAL.labels(format=format_name, status=status).inc()
    except Exception:
        logger.warning("failed to record report generation metric", exc_info=True)
```

If `REPORT_FORMATS` import creates a circular dependency, hard-code the
allow-list as `_ALLOWED_REPORT_FORMATS = frozenset({"markdown", "pdf", "png",
"csv", "bundle"})` inside `_metrics.py` and add a comment pointing to
`schemas.py:ReportFormat` as the source of truth.

**Test:** in `tests/test_metrics.py`:
- Call `record_report_generation("__not_a_format__", "completed")` directly →
  counter NOT incremented (no new label series); caplog has the warning.

**Commit:** `fix(api): batch 14 round 2 info — defensive label clamp inside record_report_generation`

---

## R3-I3 — Symmetry: success path also uses intersection

**File:** `src/atlas20/api/services_report.py` line ~298.

**Problem (Opus-Round2-Info3):** Success path iterates `for format_name in requested`,
failure path iterates `for format_name in requested & REPORT_FORMATS`. Both are
functionally equivalent (the `unknown` check at :245 rejected anything else),
but symmetric clamp is clearer.

**Decision:** Change success-path iteration to use the same intersection:

```python
for format_name in requested & REPORT_FORMATS:
    _safe_record_report_generation(format_name, "completed")
```

(Or whatever the actual call signature is — match the existing failure-path
pattern exactly.)

**Test:** no new test; existing C1 cardinality test at `tests/test_metrics.py`
exercises both paths.

**Commit:** `refactor(api): batch 14 round 2 info — symmetric label clamp in report success path`

---

## R3-I4 — Direct counter assertion for recover_my_own_stale_runs

**File:** `tests/test_metrics.py`.

**Problem (Codex-Round2-Info):** `recover_my_own_stale_runs` now emits the
terminal counter (added in R2-W2 commit 172ded5), but the test suite only
asserts the recovery BEHAVIOR (run state transitions), not the metric
increment.

**Decision:** Add a direct counter-assertion test mirroring the existing
`recover_stale_runs` test pattern.

```python
def test_recover_my_own_stale_runs_emits_backtests_total(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify recover_my_own_stale_runs increments atlas20_backtests_total{status=failed}."""
    from atlas20.api.worker.recovery import recover_my_own_stale_runs
    from atlas20.api._metrics import BACKTESTS_TOTAL
    import time

    # Seed a stale running run owned by this PID
    my_pid = 99999  # synthetic
    seed_run(
        db_session,
        run_id="btk_9999",
        status="running",
        worker_pid=my_pid,
        heartbeat_at=utc_now() - timedelta(seconds=600),  # ancient
        started_at=utc_now() - timedelta(seconds=900),
    )
    db_session.commit()

    before = BACKTESTS_TOTAL.labels(status="failed")._value.get()
    recovered = recover_my_own_stale_runs(db_session, my_pid)
    after = BACKTESTS_TOTAL.labels(status="failed")._value.get()

    assert recovered == 1
    assert after == before + 1
```

(Match the existing `recover_stale_runs` test signature; adapt seed helpers
to whatever exists in `tests/conftest.py` or `tests/_seeders.py`.)

**Commit:** `test(api): batch 14 round 2 info — direct counter assertion for recover_my_own_stale_runs`

---

## Procedure

4 atomic commits in order R3-I1 → R3-I2 → R3-I3 → R3-I4.

After each: `python -m pytest tests/ -x -q` green. Frontend untouched (132).

Expect final pytest: 325 + 2 new (R3-I2 + R3-I4) = **327 passing**, 2 skipped.

## Report

- 4 commit hashes
- Final backend test count
- Frontend test count (must be 132)
- Any deviations (Claude triages)
</TASK>
