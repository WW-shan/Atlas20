ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply Batch 13 Round-1 reviewer findings. Combined Opus + codex review on commit
`4924dec` (Phase F). 6 atomic fixes. **Each = separate commit.** Run pytest after
each. Frontend test count must stay 132; backend climbs 286 → ~290.

---

## C1 (Critical) — Frontend download contract break

**Files:** `apps/web/src/lib/api.ts`, `apps/web/src/features/reports/ReportsExportsTab.tsx`, `apps/web/src/features/reports/ReportsExportsTab.test.tsx`, `apps/web/src/lib/api.test.ts` (if it covers downloadDigest), `src/atlas20/api/routes/reports.py`, `src/atlas20/api/schemas.py`.

**Problem:**
- Backend `GET /api/reports/digest/download` and `GET /api/reports/{report_id}/download` now stream `FileResponse` (binary).
- Frontend `apps/web/src/lib/api.ts:645-652` still calls `requestJson<{ url: string }>(...)` → parses binary as JSON → throws → swallowed by `.catch(() => {})` in `ReportsExportsTab.tsx:86-99`. Real downloads silently fail.
- Also: `routes/reports.py` decorates GET download routes with `Depends(verify_api_key)` — but `window.open(url)` cannot send custom `X-API-Key` header. Per `docs/operations/security.md` (Batch 11), GET routes are documented unauth in MVP.

**Decision (Claude):**

1. **Drop `verify_api_key` from the two GET download routes** in `routes/reports.py`. Keep it on `POST /reports/generate`. The security boundary for downloads is path-safety + manifest sha256 (already in place + tightened by W4 below), not API key. Comment near the routes referencing `docs/operations/security.md` MVP gate.

2. **Convert frontend to URL builders** (no fetch). In `apps/web/src/lib/api.ts`:

```ts
// Replace existing downloadDigest / downloadReport:
export function downloadDigestUrl(format: ReportFormat | "bundle"): string {
  return buildApiUrl(`/reports/digest/download?format=${encodeURIComponent(format)}`);
}

export function downloadReportUrl(id: string, fmt?: ReportFormat | "bundle"): string {
  const q = fmt ? `?format=${encodeURIComponent(fmt)}` : "";
  return buildApiUrl(`/reports/${encodeURIComponent(id)}/download${q}`);
}
```

Use the existing `buildApiUrl` helper (or whatever the codebase's API base resolver is named — grep `lib/api.ts` for `API_BASE` / `apiBase`).

3. **Call-site change in `ReportsExportsTab.tsx`:**

```ts
const handleDownloadAll = () => {
  if (digestDownloadPending) return;
  setDigestDownloadPending(true);
  try { window.open(downloadDigestUrl("bundle"), "_blank", "noopener,noreferrer"); }
  finally { setDigestDownloadPending(false); }
};

const handleDownloadOne = (id: string, fmt?: ReportFormat) => {
  if (reportDownloadPendingId) return;
  setReportDownloadPendingId(id);
  try { window.open(downloadReportUrl(id, fmt ?? format), "_blank", "noopener,noreferrer"); }
  finally { setReportDownloadPendingId(undefined); }
};
```

Note: drop the `.then((r) => openDownload(r.url))` pattern entirely. `openDownload` helper at line 78 can also be deleted if no other call sites remain.

4. **Type fix:** `ReportFormat` union currently excludes `"bundle"`. Either (a) add `"bundle"` to `ReportFormat` (preferred — consolidate), updating the Literal in `schemas.py` and TypeScript type accordingly; OR (b) keep separate `ReportFormat | "bundle"` in download signatures. Pick (a) — single source of truth.

5. **`GenerateReportResponse` consistency:** backend returns `status="completed"`; frontend type expected `"queued"`. Update the TS literal to `"completed" | "queued"` (union) and let backend stay `"completed"`. Update NewReportModal's toast / success-message handling if it conditions on the literal.

6. **Update vitest mocks** in `ReportsExportsTab.test.tsx`: replace `vi.mocked(api.downloadDigest).mockResolvedValue({ url: "stub" })` with a stub for `downloadDigestUrl` that returns a deterministic URL string. Replace the click-assertion at line 75 to assert `window.open` (use `vi.spyOn(window, "open")`).

7. **Acceptance:** `cd apps/web && npm run test -- --run` → 132 still passing; manual `window.open` returns a real URL pointing to the streaming route.

**Commit:** `fix(api+ui): batch 13 reviewer pass — wire frontend downloads to streaming routes, drop verify_api_key on GET downloads`

---

## W1 (Warning) — Bundle/manifest ordering + partial-regen orphans DB rows

**Files:** `src/atlas20/api/services_report.py`, `src/atlas20/api/manifest.py`.

**Problem A (Opus):** `generate_bundle` includes `report_manifest.json` in the ZIP, but the manifest written before bundling lacks the `bundle` entry. The on-disk manifest later includes `bundle`. → manifest-in-zip diverges from manifest-on-disk.

**Problem B (Codex):** `write_report_manifest` is called with only the current request's formats. A subsequent `formats=["markdown"]` regenerate overwrites manifest with only `markdown`, but the DB still has rows for older `pdf`/`png`/`bundle`. After W4 (below), those rows return 403 because their paths aren't in the new manifest.

**Decision (Claude):** Combined fix.

1. **Drop `report_manifest.json` from the bundle include list.** In `services_report.py:generate_bundle`, remove `"report_manifest.json"` from the `include_names` list (around line 196-203). The on-disk manifest is the single source of truth; the bundle ships actual data only.

2. **Merge semantics in `write_report_manifest`.** In `manifest.py`, change the function to:
   - Read existing `report_manifest.json` if present.
   - Keep entries whose `kind` is NOT in the new artifacts.
   - Overlay the new artifacts.
   - Write atomically.

```python
def write_report_manifest(run_id: str, run_dir: Path, artifacts: list[ReportArtifact]) -> Path:
    run_dir = Path(run_dir)
    manifest_path = run_dir / "report_manifest.json"
    # Merge with existing entries so partial regens don't orphan DB rows
    existing: dict[str, dict[str, Any]] = {}
    if manifest_path.exists():
        try:
            existing_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in existing_payload.get("artifacts", []):
                existing[entry["kind"]] = entry
        except (json.JSONDecodeError, KeyError):
            pass  # corrupt manifest → start fresh
    new_kinds = {a.kind for a in artifacts}
    rows = [existing[k] for k in existing if k not in new_kinds]
    for artifact in artifacts:
        rows.append({...})  # keep existing schema
    payload = {"run_id": run_id, "generated_at": ..., "artifacts": rows}
    _atomic_write_json(manifest_path, payload)
    return manifest_path
```

3. **Bundle write order:** call `write_report_manifest(...)` ONCE after the bundle is on disk, with the full list including the bundle artifact. Drop the pre-bundle manifest write at services_report.py:273. Single write at the end.

**Test:** in `tests/test_report_manifest.py`:
- Generate markdown for run X → manifest has [markdown].
- Generate png for run X → manifest has [markdown, png] (NOT [png] only).
- Verify on disk + verify_manifest_artifact returns True for both kinds.

**Commit:** `fix(api): batch 13 reviewer pass — merge report_manifest on partial regen, drop manifest-in-bundle`

---

## W2 (Warning) — FileNotFoundError → 500

**Files:** `src/atlas20/api/services_report.py`, `tests/test_generate_report.py`.

**Problem:** `_first_existing` (services_report.py:47-52) raises `FileNotFoundError` when a run's `summary.csv` / `equity_curve.csv` is missing. The route handler in `routes/reports.py:65-75` only catches `HTTPException`, so this bubbles as 500.

**Decision:** Raise `HTTPException(404, ...)` directly from `_first_existing`. Cleaner than wrapping at the route level.

```python
def _first_existing(run_dir: Path, names: list[str]) -> Path:
    for name in names:
        candidate = run_dir / name
        if candidate.exists():
            return candidate
    raise HTTPException(
        status_code=404,
        detail=f"run output missing: expected one of {names} under {run_dir.name}",
    )
```

**Test:** seed a run with no `summary.csv` → POST /reports/generate → expect 404 (not 500). Add to test_generate_report.py.

**Commit:** `fix(api): batch 13 reviewer pass — return 404 (not 500) when run artifacts are missing`

---

## W3 (Warning) — PNG silently skipped on re-generation

**File:** `src/atlas20/api/services_report.py` lines 177-179.

**Problem:**

```python
def _generate_png(run_dir: Path) -> Path:
    output_path = run_dir / "equity_curve.png"
    if output_path.exists():
        return output_path  # ← stale if equity_curve.csv was updated
```

**Decision:** Drop the early return. Always regenerate. Consistency with markdown/pdf/bundle which always overwrite. Perf is fine (single chart, ms-scale).

**Test:** existing PNG generation test should cover. Add a regression in `test_generate_report.py`:
- Generate png → record mtime.
- Re-generate png (1 second later) → assert mtime > first.

**Commit:** `fix(api): batch 13 reviewer pass — always regenerate PNG, never skip on file present`

---

## W4 (Warning) — Disk-fallback download bypasses sha256 whitelist

**File:** `src/atlas20/api/services_download.py` lines 71-78.

**Problem:** `_validate_manifest_and_hash` allows downloads when both manifest is absent AND `expected_sha is None` (the disk-fallback path). This means a file planted in `report_root/app_runs/btk_0001/digest.md` without going through `generate_run_report` can be downloaded, bypassing the sha whitelist story.

**Decision (Claude):** Tighten — require EITHER manifest verification OR DB-row sha. If neither, raise 403. This forces all downloadable artifacts to be registered through the generation flow.

```python
def _validate_manifest_and_hash(path: Path, settings: Settings, *, run_id: str | None, expected_sha: str | None) -> None:
    run_dir = _run_dir_for_path(path, settings, run_id)
    manifest_path = (run_dir / "report_manifest.json") if run_dir else None
    if manifest_path and manifest_path.exists():
        if not verify_manifest_artifact(run_dir, path):
            raise HTTPException(status_code=403, detail="report artifact failed manifest verification")
        return
    if expected_sha is not None:
        if expected_sha != sha256_file(path):
            raise HTTPException(status_code=403, detail="report artifact sha256 mismatch")
        return
    # Neither manifest nor DB sha — refuse the download
    raise HTTPException(
        status_code=403,
        detail="report artifact has no manifest or registered sha256; regenerate via POST /api/reports/generate",
    )
```

**Test:** in `tests/test_download_path_safety.py`:
- Plant a file in `report_root/app_runs/btk_0001/digest.md` without manifest or DB row.
- GET `/api/reports/btk_0001/download?format=markdown` → 403 (not 200).

Note: this MAY break an existing test that depends on the disk-fallback path returning 200. Update that test to register the report file via the proper flow (call `generate_run_report` first), or assert 403 if the test intent was to verify the legacy fallback.

**Commit:** `fix(api): batch 13 reviewer pass — require manifest or DB sha for download, refuse bare disk fallback`

---

## W5 (Warning) — PID-only tmp names race on concurrent same-process generation

**Files:** `src/atlas20/api/services_report.py:43`, `src/atlas20/api/manifest.py:36`.

**Problem:** `_tmp_path` and `_atomic_write_json` use `{name}.tmp_{pid}`. Two concurrent threadpool requests in the same process (FastAPI runs `def` routes in threadpool) hit the same tmp filename → race on `os.replace`.

**Decision:** Add UUID component.

```python
import uuid
def _tmp_path(path: Path, suffix: str = ".tmp") -> Path:
    return path.with_name(f"{path.name}{suffix}_{os.getpid()}_{uuid.uuid4().hex[:8]}")

def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)
```

**Test:** not strictly necessary (race is timing-dependent). Skip the regression test — just fix.

**Commit:** `fix(api): batch 13 reviewer pass — UUID-suffix tmp names to avoid concurrent same-process collisions`

---

## Info items intentionally deferred to Batch 14

- **Multi-worker scheduler duplicate jobs** (Opus I6 / Codex W note) — needs file-lock or leader-elect. Will be in Batch 14 (Phase O) brief.
- **Symlink-escape test skipped on Windows** (Opus I3) — CI runs on Linux already; document in test docstring as a comment.
- **Bundle double-hash perf** (Opus I1) — micro-optimization, skip.
- **`--week N` CLI calendar semantics** (Codex info) — current "Nth most recent completed" interpretation is fine for MVP; document in CLI `--help`.

---

## Procedure

6 atomic commits in order C1 → W1 → W2 → W3 → W4 → W5.

After each:
- `python -m pytest tests/ -x -q` green
- Frontend `npm run test` only re-run if C1 (or any UI touch) — must stay 132

Expect final pytest: 286 + 3 new (W1, W2, W4 each add ≥1 test) = **~289-291 passing**, 2 skipped unchanged.

## Report

- 6 commit hashes
- Final backend test count
- Frontend test count (must be 132)
- Any deviations from the decisions above (with justification — Claude triages)
</TASK>
