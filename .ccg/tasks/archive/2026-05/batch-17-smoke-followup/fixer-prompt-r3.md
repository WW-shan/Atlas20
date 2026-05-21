ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
You are the **codex fixer** for Atlas20 Batch 17 round-4 follow-up. Round-3 cross-validation by Opus 4.7 (78/100) and fresh codex reviewer (79/100) BOTH said REQUEST_CHANGES. All round-2 findings (C1/W1-W4) resolved; all round-1 findings (A/B/C) confirmed still resolved; codex deviation (worker/__init__.py lazy exports) justified by both reviewers. But round-3 surfaced 1 NEW Critical + 3 NEW Warning. Fix all 4 in separate commits. Info-level findings are deferred per Opus ("acceptable for MVP").

Branch: `redesign/r3-premium`. Start from current HEAD `a420f20`.

Each finding = independent atomic commit. Run pytest + verify_release after each. Commit messages use `fix(api|infra|docs): batch 17 r3 — <one-line summary>`.

---

## C1 — Multiproc dir mmap files accumulate unboundedly (Opus Critical)

**Files:**
- `src/atlas20/api/worker/__main__.py`
- `src/atlas20/api/worker/spawn.py`
- `docs/operations/logging.md`
- `tests/test_worker_metrics_multiproc.py` (extend) or new `tests/test_worker_multiproc_lifecycle.py`

**Problem (Opus reviewer, sourced from prometheus_client docs + GH#275, #566, #121):**
`__main__.py:14-17` creates `data/.prom-multiproc-worker/` with
`exist_ok=True` but NEVER wipes. Each `run_one` subprocess writes
`counter_<pid>.db` + `histogram_<pid>.db` (~1MB each). `mark_process_dead`
at run_one atexit only deletes Gauge files (atlas20 has no Gauges, so
it's effectively a no-op for atlas20). Files accumulate per run_one pid
across the worker's lifetime. /metrics scrape time is O(file count). At
~1000 backtests over a month: ~2GB; over a year: ~24GB.

Upstream guidance (https://prometheus.github.io/client_python/multiprocess/):
"The PROMETHEUS_MULTIPROC_DIR directory must be wiped between Prometheus
processes runs."

**Decision (Claude):** Wipe the dir on parent worker startup. Coordinate with
`spawn.py` multi-worker case so children don't race-wipe each other's files.

### `__main__.py` — wipe-by-default

```python
"""Bootstrap entry for ``python -m atlas20.api.worker``.

Sets ``PROMETHEUS_MULTIPROC_DIR`` before importing atlas20 worker modules so
per-process Counter writes land in shared mmap files that the parent
``/metrics`` endpoint aggregates. Required because ``run_one`` runs in a
subprocess; without this, its counter increments vanish on subprocess exit.

The multiproc directory is wiped on startup to prevent unbounded growth
of dead-pid mmap files (per prometheus_client multiprocess guidance).
spawn.py sets ATLAS20_WORKER_MULTIPROC_SKIP_WIPE=1 on its children so only
the spawn-time owner wipes once before any worker starts.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _initialize_multiproc_dir() -> Path:
    explicit = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if explicit:
        multiproc_dir = Path(explicit)
    else:
        data_root = Path(os.environ.get("ATLAS20_DATA_ROOT", "data"))
        multiproc_dir = data_root / ".prom-multiproc-worker"
    if os.environ.get("ATLAS20_WORKER_MULTIPROC_SKIP_WIPE") != "1" and multiproc_dir.exists():
        # Best-effort wipe — if a file is still mmap'd by an in-flight subprocess
        # (rare during a clean restart), let the leftover stay rather than crash.
        shutil.rmtree(multiproc_dir, ignore_errors=True)
    multiproc_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", str(multiproc_dir))
    return multiproc_dir


_initialize_multiproc_dir()

from atlas20.api.worker.main import main  # noqa: E402

if __name__ == "__main__":
    main()
```

### `spawn.py` — wipe once, then signal children to skip

```python
"""Utility for launching multiple local worker child processes."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _wipe_multiproc_dir() -> None:
    explicit = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if explicit:
        multiproc_dir = Path(explicit)
    else:
        data_root = Path(os.environ.get("ATLAS20_DATA_ROOT", "data"))
        multiproc_dir = data_root / ".prom-multiproc-worker"
    if multiproc_dir.exists():
        shutil.rmtree(multiproc_dir, ignore_errors=True)
    multiproc_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", str(multiproc_dir))


def spawn_workers(count: int | None = None) -> list[subprocess.Popen]:
    worker_count = count if count is not None else int(os.environ.get("ATLAS20_WORKERS", "2"))
    _wipe_multiproc_dir()
    processes: list[subprocess.Popen] = []
    for _ in range(worker_count):
        env = os.environ.copy()
        env["ATLAS20_WORKERS"] = "1"
        env["ATLAS20_WORKER_MULTIPROC_SKIP_WIPE"] = "1"
        processes.append(subprocess.Popen([sys.executable, "-m", "atlas20.api.worker"], env=env))
    return processes


def main() -> None:
    # ... existing
```

### Tests

Add `tests/test_worker_multiproc_lifecycle.py`:

1. `test_initialize_multiproc_dir_wipes_existing_files(tmp_path, monkeypatch)`:
   - Set `ATLAS20_DATA_ROOT=tmp_path`
   - Create `tmp_path / ".prom-multiproc-worker" / "stale_counter_999.db"` (zero-byte stub)
   - Call `_initialize_multiproc_dir`
   - Assert file gone, dir still exists, env var set

2. `test_initialize_multiproc_dir_skips_wipe_when_env_set(tmp_path, monkeypatch)`:
   - Same setup as #1, but `ATLAS20_WORKER_MULTIPROC_SKIP_WIPE=1`
   - Assert stale file still present after init

3. `test_spawn_workers_wipes_once_and_signals_children(tmp_path, monkeypatch)`:
   - Mock `subprocess.Popen` to capture env
   - Pre-seed a stale file in the multiproc dir
   - Call `spawn_workers(count=2)`
   - Assert stale file is gone; both children have `ATLAS20_WORKER_MULTIPROC_SKIP_WIPE=1` in env

### Docs

Update `docs/operations/logging.md` Prometheus section — add subsection:

```markdown
### Multiprocess metric file lifecycle

The worker's `PROMETHEUS_MULTIPROC_DIR` (default
`{ATLAS20_DATA_ROOT}/.prom-multiproc-worker`) accumulates per-pid mmap
files for every `run_one` subprocess. The bootstrap shim
(`src/atlas20/api/worker/__main__.py`) wipes the directory on every
worker startup to prevent unbounded growth, per upstream
`prometheus_client` guidance.

For the multi-worker local helper (`atlas20.api.worker.spawn`), the
parent process wipes the directory once and sets
`ATLAS20_WORKER_MULTIPROC_SKIP_WIPE=1` on each spawned child so the
children do not race-wipe each other's mmap files.

On Windows, a wipe that races with an in-flight subprocess's open mmap
will fail to delete the locked file; this is acceptable — the wipe is
`ignore_errors=True` and the leftover is bounded by the number of
in-flight subprocesses at restart time (typically 1).
```

**Commit:** `fix(api): batch 17 r3 — wipe PROMETHEUS_MULTIPROC_DIR on worker startup; spawn.py coordinates once-only wipe`

---

## W1 — Narrow OSError to EADDRINUSE + correct misleading fallback log

**Files:**
- `src/atlas20/api/worker/main.py`
- `tests/test_worker_metrics.py`

**Problem (Opus + codex):**
Two issues in `worker/main.py:54-63`:

1. `except OSError as exc:` catches every OSError. PermissionError (port
   < 1024 without privs), network-unreachable, address-family errors are
   misclassified as "port already bound", swallowed silently, and the
   real failure is hidden.

2. When `PROMETHEUS_MULTIPROC_DIR` is unset and another worker already
   bound the port, the current log says counters "will be aggregated by
   the bound process via PROMETHEUS_MULTIPROC_DIR=None" — FALSE. Without
   multiproc, the collision-loser's counters are silently DROPPED.

**Decision (Claude):**

```python
import errno

# ... inside start_metrics_server, replace except clause:
except OSError as exc:
    addr_in_use_codes = {errno.EADDRINUSE}
    win_code = getattr(errno, "WSAEADDRINUSE", None)
    if win_code is not None:
        addr_in_use_codes.add(win_code)
    if exc.errno not in addr_in_use_codes:
        # Not a port collision — propagate so operators see the real failure.
        raise
    _metrics_server_started = True
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if multiproc_dir:
        logger.info(
            "worker prometheus /metrics port %d already bound; this worker's "
            "counters will be aggregated by the bound process via "
            "PROMETHEUS_MULTIPROC_DIR=%s",
            port, multiproc_dir,
        )
    else:
        logger.warning(
            "worker prometheus /metrics port %d already bound and "
            "PROMETHEUS_MULTIPROC_DIR is not configured; this worker's "
            "counter increments will be DROPPED (not visible in any /metrics "
            "scrape). Set PROMETHEUS_MULTIPROC_DIR to enable cross-worker "
            "aggregation.",
            port,
        )
```

**Tests:**
- Extend `tests/test_worker_metrics.py::test_start_metrics_server_tolerates_port_in_use`:
  monkeypatch start_http_server to raise `OSError(errno.EADDRINUSE, ...)`, assert
  swallow + INFO log when multiproc set.
- Add `test_start_metrics_server_reraises_unrelated_oserror`:
  monkeypatch start_http_server to raise `PermissionError(13, "denied")`,
  assert it re-raises (not swallowed).
- Add `test_start_metrics_server_warns_when_collision_without_multiproc`:
  monkeypatch start_http_server to raise EADDRINUSE, ensure no
  PROMETHEUS_MULTIPROC_DIR env, assert WARNING log fires with "DROPPED".

**Commit:** `fix(api): batch 17 r3 — start_metrics_server narrows to EADDRINUSE and warns when counters will be dropped`

---

## W2 — docs/operations/worker.md still documents old entrypoint

**Files:** `docs/operations/worker.md`

**Problem (codex):** Line 8 still says
`python -m atlas20.api.worker.main`. That bypasses
`__main__.py` so manual operators following this doc lose run_one
subprocess counters silently.

**Decision (Claude):** Replace the old invocation with the new one, plus
PYTHONPATH=src guidance to align with README + `__main__.py` bootstrap.
Run a Grep across `docs/` for any other occurrences of `worker.main` and
update if found.

**Commit:** `docs(infra): batch 17 r3 — worker.md uses new python -m atlas20.api.worker entrypoint`

---

## W3 — logging.md table inaccuracy on atlas20_backtests_total

**Files:** `docs/operations/logging.md`

**Problem (Opus):** Table at `logging.md:28` labels
`atlas20_backtests_total{status}` as Worker-only. The API process ALSO
emits it: `src/atlas20/api/app.py:125` calls `recover_stale_runs` in
lifespan startup, which transitively calls `_record_terminal_transition`
in the API process and increments BACKTESTS_TOTAL there.

**Decision (Claude):** Update the table row to clarify dual emission.
Also add an INFO note that, since the API emits this counter only during
lifespan startup recovery, the API contribution is bounded and small —
no PromQL adjustment needed beyond the existing `sum without (instance,
job)` example.

```markdown
| `atlas20_backtests_total{status}`       | Worker (main path) + API (lifespan recovery only) | Incremented per terminal transition. The API process emits this only during lifespan startup when `recover_stale_runs` reclassifies orphaned runs as failed; the dominant emitter is the worker subprocess via multiproc aggregation. |
```

**Commit:** `docs(infra): batch 17 r3 — clarify atlas20_backtests_total is also emitted by API lifespan recovery`

---

## Info findings — deferred

Per Opus reviewer, all info-level items are acceptable for MVP:
- Worker imports app.py top-level (could be a small standalone module)
- `__main__.py` always creates default path even when env supplied
- Healthcheck only probes HTTP listener thread, not queue loop
- Multiproc test uses `python -c`, not real run_one

**Do NOT spend commits on these.** Note them in your final report so the
follow-up batch knows what's pending.

---

## Procedure

4 atomic commits in order: C1 → W1 → W2 → W3. After each:
`PYTHONPATH=src python -m pytest tests/ -x -q` green.
After all 4: `python scripts/verify_release.py` exit 0,
`git diff --check a420f20..HEAD` clean.

**Final acceptance:**
- pytest: 356 → ~360+ (C1 adds 3 tests, W1 adds 2 tests, W2/W3 docs-only)
- vitest: 161 unchanged
- verify_release exit 0

## Report back

- 4 commit hashes in order
- Final backend test count
- Any deviations + Claude-decision justification
- Confirmation each round-3 finding is actually addressed by the corresponding commit (file:line evidence)
- List of deferred Info findings preserved for next batch
</TASK>