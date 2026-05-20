ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply Batch 13 Round-2 reviewer findings. Opus 90/100 + Codex 86/100, both
REQUEST_CHANGES. All 6 round-1 originals are RESOLVED but the two reviewers
surfaced 2 Warnings + 2 Info that need follow-up.

Range in scope: `4924dec..HEAD` (the 6 round-1 fixes).

**4 atomic fixes. Each = separate commit.** Run pytest after each. Frontend must
stay 132; backend should stay 290 (only one fix below adds a regression test
worth +1).

---

## R2-W1 (Warning, Opus) — PNG tmp path still PID-only

**File:** `src/atlas20/api/services_report.py:183`.

**Problem:** Round-1 W5 fixed `_tmp_path` and `_atomic_write_json` to use
`{pid}_{uuid.uuid4().hex[:8]}`, but `_generate_png` was missed — it still
constructs its tmp filename inline:

```python
tmp_path = output_path.with_name(f"{output_path.stem}.tmp_{os.getpid()}{output_path.suffix}")
```

Two concurrent same-PID PNG regenerations on the same run_id will collide on
`equity_curve.tmp_{pid}.png`. Defeats W5's purpose.

**Decision (Claude):** Route the PNG tmp path through the existing `_tmp_path()`
helper to keep the suffix policy in one place. The helper currently produces
`{name}.tmp_{pid}_{uuid}` (no preserved extension). For PNG we want the `.png`
suffix to survive — write a small inline variant OR extend the helper.

Simplest: extend `_tmp_path` to take an optional `extension` arg so the result
is `{stem}.tmp_{pid}_{uuid}{extension}`. Or even simpler — drop the
preserved-extension requirement, since the tmp file is short-lived and not
parsed by anything before `os.replace`:

```python
tmp_path = _tmp_path(output_path)
plot_equity_curves({...}, tmp_path, ...)
os.replace(tmp_path, output_path)
```

Validate by reading `plot_equity_curves`'s contract — if it inspects the
filename suffix to choose format, switch to the extension-preserving variant.
Otherwise the simpler form is fine.

**Test:** not strictly necessary (race is timing-dependent). Skip the regression test — match the W5 round-1 decision.

**Commit:** `fix(api): batch 13 round 2 — route PNG tmp path through _tmp_path for UUID-suffix consistency`

---

## R2-W2 (Warning, Codex) — `write_report_manifest` AttributeError on non-dict JSON

**File:** `src/atlas20/api/manifest.py` around line 46-52.

**Problem:** Round-1 W1 merge logic reads the existing manifest with
`json.loads(...)`, catches `json.JSONDecodeError` and `KeyError`, but assumes
the parsed payload is a dict and calls `.get("artifacts", [])` on it. If the
existing file is a valid JSON array (`[...]`) or string (`"foo"`), the parse
succeeds but `.get` raises `AttributeError` → uncaught → 500 on the next
generate request.

**Decision (Claude):** Guard with `isinstance(existing_payload, dict)`. Also
broaden the except to log a warning when the existing manifest is malformed
(resolves R2-Info-A below in the same commit — see decision there).

```python
existing: dict[str, dict[str, Any]] = {}
if manifest_path.exists():
    try:
        existing_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(existing_payload, dict):
            for entry in existing_payload.get("artifacts", []):
                if isinstance(entry, dict) and "kind" in entry:
                    existing[entry["kind"]] = entry
        else:
            logger.warning(
                "existing manifest at %s parsed to non-dict (%s); overwriting",
                manifest_path, type(existing_payload).__name__,
            )
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("existing manifest at %s unreadable (%s); overwriting", manifest_path, exc)
```

Add `import logging; logger = logging.getLogger(__name__)` if not already
imported at module top.

**Test:** in `tests/test_report_manifest.py`, add `test_write_manifest_recovers_from_non_dict_payload`:
- Write `report_manifest.json` containing `"[1, 2, 3]"` (raw JSON array).
- Call `write_report_manifest(run_id, run_dir, [markdown_artifact])`.
- Assert no exception; resulting manifest is the new payload (markdown only,
  since the array can't contribute valid kinds).

**Commit:** `fix(api): batch 13 round 2 — guard write_report_manifest against non-dict existing payloads`

---

## R2-Info-A (Opus) — corrupt manifest silently overwrites

**File:** `src/atlas20/api/manifest.py` same block as R2-W2.

**Problem:** Round-1 W1 catches `JSONDecodeError` and `KeyError` with `pass`, so
data loss (old kinds dropped) is silent.

**Decision (Claude):** ALREADY ADDRESSED by R2-W2 — the same code change adds
`logger.warning(...)` for both the parse-error and non-dict cases. Do NOT make
a separate commit; bundle into R2-W2.

---

## R2-Info-B (Codex) — `_resolve_featured_file` rglob fallback can serve unrelated artifacts

**File:** `src/atlas20/api/services_download.py:128-137`.

**Problem:** When `KvRepo.get("featured_digest_run_id")` returns nothing OR the
indicated run has no `ReportFile` row of the requested kind, the code calls
`_fallback_featured_path(fmt, settings)` which does `report_root.rglob(pattern)`
and returns the newest match anywhere under `report_root`. This can serve
arbitrary artifacts (e.g., the markdown from a totally different run/config
config that happens to be named `digest.md`) — surprising and inconsistent with
the W4 security stance.

**Decision (Claude):** Drop the `_fallback_featured_path` rglob path. When
KV-pointer is absent or the DB row is missing, raise `HTTPException(404,
"featured digest not yet generated; trigger via POST /api/reports/generate or
the weekly scheduler")`. This matches the W4 tightening philosophy.

```python
def _resolve_featured_file(fmt: str, session: Session, settings: Settings) -> tuple[Path, str | None, str | None]:
    run_id = KvRepo(session).get("featured_digest_run_id")
    if run_id:
        row = ReportsRepo(session).by_run_kind(run_id, FORMAT_KIND[fmt])
        if row is not None:
            return Path(settings.report_root) / row.path, row.run_id, row.sha256
    raise HTTPException(
        status_code=404,
        detail="featured digest not yet generated; trigger via POST /api/reports/generate or the weekly scheduler",
    )
```

Delete `_fallback_featured_path` if unused after this change.

**Note:** This MAY break an existing test (`test_download_streaming.py` or
`test_generate_report.py`) that depends on the rglob fallback returning 200.
Update those tests to plant a `KvSetting` row + a `ReportFile` row first
(consistent with the post-fix happy path).

**Test:** in `tests/test_download_streaming.py` or `test_download_path_safety.py`:
- KV pointer absent → GET `/api/reports/featured/download?format=markdown` → 404.
- KV pointer present but no `ReportFile` of that kind → 404.
- KV pointer + `ReportFile` row → 200 (existing happy path still works).

**Commit:** `fix(api): batch 13 round 2 — drop rglob featured-digest fallback, require KV pointer + DB row`

---

## R2-Bonus — Add a regression for symlink-escape on Linux CI

**File:** `tests/test_download_path_safety.py` — the symlink-escape test that's
currently skipped on Windows.

**Decision (Claude):** Leave the skip in place (correct on Windows without
elevation), but add a docstring comment explaining the test SHOULD run on
Linux CI to actually exercise the path. One-line code change; not really a
fix, more a documentation note.

**SKIP this — it's just a comment in a test docstring. Codex: SKIP unless
already in scope of another commit.**

---

## Procedure

3 atomic commits in order R2-W1 → R2-W2 (also covers R2-Info-A) → R2-Info-B.

After each:
- `python -m pytest tests/ -x -q` green
- Frontend test count must stay 132 (no UI changes expected in any of these 3)

Expect final pytest: 290 + 2 new (R2-W2 + R2-Info-B each add ≥1 test) =
**~292 passing**, 2 skipped unchanged.

## Report

- 3 commit hashes
- Final backend test count
- Frontend test count (must be 132)
- Any deviations (Claude triages)
</TASK>
