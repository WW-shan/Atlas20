ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply Batch 13 Round-4 cleanup of remaining Info-level findings from rounds 1
and 3. Per protocol "Info 级别 finding 也要修" (batch-execution-protocol.md
lesson 9). 5 atomic fixes. **Each = separate commit.** Run pytest after each.
Frontend must stay 132; backend grows 293 → ~295 (only the OSError test adds a
case).

Range: starts from current HEAD `e63f928`.

---

## R4-I1 — Bundle double-hash perf

**Files:** `src/atlas20/api/services_report.py` (around line 280),
`src/atlas20/api/manifest.py:_artifacts_from_rows` (or wherever the helper
lives — grep for it).

**Problem (Opus R1-I1):** After generating the bundle, `write_report_manifest`
re-hashes every artifact via `_artifacts_from_rows(settings, files)`. The
`ReportFile` row already carries `sha256` (computed at registration time at
services_report.py:112). For a 100MB bundle, that's a second full-file read.

**Decision:** Make `_artifacts_from_rows` (or the equivalent transformer)
use `row.sha256` directly. Only fall back to `sha256_file(path)` when the row
lacks a sha (shouldn't happen in normal flow). Also have `write_report_manifest`
NOT re-hash files already present in artifact entries.

Verify: grep `sha256_file(` across services_report.py + manifest.py to see all
call sites. The only legitimate call should be in the artifact REGISTRATION
path (when first computing sha for `ReportFile.sha256`), not in the manifest
WRITE path.

**Test:** add a perf-leaning assertion or simply assert correctness:
`tests/test_report_manifest.py` already covers manifest content correctness;
add `test_artifacts_from_rows_uses_row_sha256` that monkeypatches `sha256_file`
to raise (to prove the manifest-writer path doesn't call it). Or simpler: count
file `open()` calls during a generate cycle.

**Commit:** `perf(api): batch 13 round 4 — avoid double-hashing artifacts when row.sha256 is known`

---

## R4-I2 — Symlink test docstring (CI Linux note)

**File:** `tests/test_download_path_safety.py:64` (`test_download_rejects_symlink_escape`).

**Problem:** Test silently `pytest.skip(...)` on Windows without elevation
(line 75). Future readers don't know this case is critical-but-skipped → CI
must run Linux.

**Decision:** Add a clear docstring at the top of the test:

```python
def test_download_rejects_symlink_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    """Reject downloads when a symlink points outside report_root.

    NOTE: this test will pytest.skip() on Windows hosts without symlink
    creation privilege (common dev case). The symlink-escape attack
    surface is real and this test MUST run on Linux CI to actually
    exercise the rejection path. Do not interpret a green run on a
    Windows dev box as coverage of this case.
    """
```

**Test:** the test itself is unchanged. Pure docstring update.

**Commit:** `docs(test): batch 13 round 4 — document Windows-skip semantics on symlink-escape test`

---

## R4-I3 — CLI `--week` `--help` documentation

**File:** `src/atlas20/api/scripts/generate_digest.py`.

**Problem (Codex R1-Info):** `--week N` is implemented as "Nth most recent
completed run" (offset), not as calendar-week-based replay. Existing
`--help` says "Completed-run offset to replay, newest is 0" — accurate but
could mislead users who expect ISO-week semantics.

**Decision:** Expand the help text to be explicit and rename the parser
description to match:

```python
parser = argparse.ArgumentParser(
    description=(
        "Generate the featured Atlas20 digest from a recently-completed run. "
        "Use --week N to replay the Nth most recent completed run (counter, "
        "NOT an ISO calendar week)."
    ),
)
parser.add_argument(
    "--week",
    type=int,
    default=0,
    help=(
        "Completed-run offset to replay (0 = newest completed run, 1 = the "
        "one before, etc). This is a run counter, not an ISO calendar week."
    ),
)
```

**Test:** if there's a CLI test, update its expected stderr/help output. If
not, no test needed (pure copy change).

**Commit:** `docs(api): batch 13 round 4 — clarify generate_digest --week is run offset, not ISO week`

---

## R4-I4 — OSError branch test coverage

**Files:** `tests/test_report_manifest.py`.

**Problem (Opus R3-I1):** `manifest.py:_atomic_write_json`'s caller path
catches `(json.JSONDecodeError, OSError)` and emits `logger.warning(...)`. The
JSONDecodeError branch is tested (`test_write_manifest_recovers_from_non_dict_payload`,
the malformed-artifacts case). The OSError branch (e.g., permission denied on
read) has no coverage.

**Decision:** Add a test using `monkeypatch.setattr(Path, "read_text", ...)`
to inject a `PermissionError` (subclass of `OSError`), assert the
generation still succeeds, the manifest is overwritten with the new payload,
and a warning was logged (use the `caplog` pytest fixture, asserting
`("WARNING", ".*unreadable.*")` or similar).

```python
def test_write_manifest_recovers_from_unreadable_existing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "report_manifest.json").write_text('{"artifacts": []}', encoding="utf-8")

    original_read_text = Path.read_text
    def _boom(self: Path, *args, **kwargs):
        if self.name == "report_manifest.json":
            raise PermissionError("denied")
        return original_read_text(self, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", _boom)

    artifact = ReportArtifact(kind="markdown", path="digest.md", sha256="abc", size=1)
    with caplog.at_level("WARNING", logger="atlas20.api.manifest"):
        write_report_manifest("btk_0001", run_dir, [artifact])

    assert any("unreadable" in rec.message for rec in caplog.records)
    payload = json.loads((run_dir / "report_manifest.json").read_text(encoding="utf-8"))
    assert [a["kind"] for a in payload["artifacts"]] == ["markdown"]
```

**Commit:** `test(api): batch 13 round 4 — cover OSError branch of write_report_manifest`

---

## R4-I5 — `reporting/report.py` inline tmp pattern → helper

**File:** `src/atlas20/reporting/report.py`. 3 inline `f"{name}.tmp_{os.getpid()}_{time.time_ns()}"`
patterns at lines 287, 302, 333.

**Problem (Opus R3-I2):** Three inline copies of the same tmp-naming pattern;
hard to evolve (e.g., if we later want to add a UUID component or a `.tmp/`
subdirectory).

**Decision:** Add a module-private helper at the top of `report.py` (DO NOT
import from `atlas20.api.*` — that would create a wrong dependency direction
from `reporting/` to `api/`; reporting is the lower-level pipeline module).

```python
def _tmp_name(base: Path) -> Path:
    """Return a sibling path with a tmp suffix unique per PID + monotonic ns.

    Used for atomic writes inside the pipeline (publish-via-rename pattern).
    """
    return base.with_name(f"{base.name}.tmp_{os.getpid()}_{time.time_ns()}")
```

Replace all 3 sites:
- Line 287 (`_temporary_report_dir`): `return _tmp_name(report_dir)`
- Line 302 (`_publish_report_dir`): use `_tmp_name(report_dir).with_name(f"{report_dir.name}.bak_{os.getpid()}_{time.time_ns()}")` — wait, this is the BACKUP path, not a tmp. It uses `.bak_` prefix. Keep it inline OR factor out a `_bak_name` mirror helper. Simpler: just leave `_publish_report_dir`'s `.bak_` line as-is (since it's semantically different — a backup, not a write-tmp). Document in code that the bak path mirrors the tmp pattern.
- Line 333 (`_atomic_write_pointer`): `tmp_pointer_path = _tmp_name(pointer_path)`

So only 2 of the 3 sites get the helper. The `.bak_` site at line 302 stays
inline with a comment.

**Test:** existing pipeline tests should cover (atomic-write behavior is
verified end-to-end via `test_pipeline_*` / `test_report_publish*`). No new
test needed unless there's an existing test that grepped for the exact tmp
suffix shape.

**Commit:** `refactor(reporting): batch 13 round 4 — extract _tmp_name helper for atomic publish paths`

---

## Deferred (NOT in this round-4)

- **R1-Opus-I6 multi-worker scheduler dedup** — needs file-lock / leader-elect
  architecture; legitimate Batch 14 (Phase O observability) scope.
- **R3-Codex-Info `.context/` directory** — meta about codex's project-context
  discovery, not an Atlas20 code fix. No-op.

---

## Procedure

5 atomic commits in order R4-I1 → R4-I2 → R4-I3 → R4-I4 → R4-I5.

After each:
- `python -m pytest tests/ -x -q` green
- Frontend test count must stay 132

Expect final pytest: 293 + ~2 = **~295 passing**, 2 skipped unchanged.

## Report

- 5 commit hashes
- Final backend test count
- Frontend test count (must be 132)
- Any deviations (Claude triages)
</TASK>
