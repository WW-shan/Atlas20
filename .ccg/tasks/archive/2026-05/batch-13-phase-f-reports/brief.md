# Batch 13 — Phase F: Report Generation & Authenticated Download

## Goal

Implement Phase F from `docs/redesign/ROADMAP.md`: real report generation
(markdown/PDF/PNG/ZIP) wired to `POST /api/reports/generate`, plus authenticated
streaming download routes that replace the current URL-stub responses with
`FileResponse`. Add a per-run `report_manifest.json` that drives a sha256-based
download whitelist, and an APScheduler-driven weekly featured digest job.

Phase F unblocks U11 (NEW REPORT modal already wired in Batch 10) for real
backend traffic.

## Scope (~550 LOC + ~20 tests)

### F1 — Authenticated streaming download (replace URL stubs)

**Files:** `src/atlas20/api/routes/reports.py`, `src/atlas20/api/services.py`,
new `src/atlas20/api/services_download.py`.

Current `routes/reports.py:25-29 (digest/download)` and `52-60
({report_id}/download)` return `{url: "/static/..."}` JSON. Replace with
streaming `FileResponse`:

1. Resolve the requested artifact path through the DB `report_files` table
   (or fallback to disk scan when DB row missing).
2. **Path safety:** `path.resolve().relative_to(settings.report_root.resolve())`
   — anything outside `report_root` returns 403.
3. **Manifest check (F7):** if `{run_dir}/report_manifest.json` exists, the
   resolved path must appear in the manifest's `artifacts[*].path` and the
   sha256 of the file content must match. Mismatch → 403.
4. Keep `verify_api_key` dependency for the existing GET endpoints
   (compatible with the empty-keys "anonymous" branch).
5. Set `Content-Disposition: attachment; filename="<sanitized>"` and the
   proper `Content-Type` per format (md → `text/markdown`, pdf →
   `application/pdf`, png → `image/png`, csv → `text/csv`, zip →
   `application/zip`).

Drop `build_digest_download_url` / `build_report_download_url` from
`services.py` (only used by the URL-stub routes). Replace with
`resolve_download(report_id|"featured", format)` returning a
`(absolute_path, content_type, suggested_filename)` tuple. Raise
`HTTPException(404)` for unknown report; `HTTPException(403)` for path
traversal / manifest mismatch.

### F2 — Markdown generation

**File:** `src/atlas20/api/services_report.py` (new).

Implement `generate_run_report(run_id, formats: set[ReportFormat]) -> list[ReportFile]`:

1. Load the run from `RunsRepo`; resolve `{report_root}/app_runs/{run_id}`.
2. Read `summary.csv`, `yearly_returns.csv`, `regime_performance.csv` from
   the run dir (these are written by the worker per Batch 9).
3. Build a `ResearchConfig` via the existing `config_adapter` + the run's
   stored `params` JSON.
4. Call `atlas20.reporting.report.build_markdown_report(...)`, writing to
   `{run_dir}/digest.md` (atomic via `.tmp` + `os.replace`).
5. Compute sha256, insert a `ReportFile` row (`kind="markdown"`,
   `path=str(relative_to_report_root)`, `sha256=...`, `size_bytes=...`,
   `run_id=run_id`).

`POST /api/reports/generate` (currently a stub) must:
- Accept `GenerateReportRequest { run_id, formats: list[ReportFormat] }`.
- Validate `run_id` matches `^btk_\d{4,6}$` (already enforced via `RunId`).
- 404 if run missing.
- Enqueue the generation: synchronous for MVP (formats expected to take
  &lt; 30s combined). Return `202 { job_id, status: "completed", files: [ReportEntry, ...] }`.
- Use the existing `verify_api_key` + `5/minute` rate limit.

### F3 — PDF generation

Add `weasyprint` to `pyproject.toml` and `requirements*.txt`. Implement
`generate_pdf(markdown_path, output_path)` that converts via:

```python
from markdown import markdown as md_to_html
from weasyprint import HTML
html = md_to_html(markdown_path.read_text(encoding="utf-8"))
HTML(string=html).write_pdf(output_path)
```

(Install `markdown` too — it's already in `pyproject.toml`? verify; add if
missing.)

If weasyprint import fails at runtime (system GTK deps missing on Windows
dev boxes), the route falls back to: skip PDF format, return only the
formats that succeeded, log a warning. **Do NOT crash the whole generate
request.**

### F4 — PNG generation (matplotlib)

Reuse `src/atlas20/reporting/charts.py` (`plot_equity_curves`,
`plot_drawdowns`, etc). For a per-run PNG, render `equity_curve.png` from
the run's `equity_curve.csv` if not already on disk. Output:
`{run_dir}/equity_curve.png` (atomic).

### F5 — ZIP bundle

`generate_bundle(run_id) -> Path`. Uses `zipfile.ZipFile(out_path, "w",
zipfile.ZIP_DEFLATED)`. Includes: `digest.md`, `equity_curve.png`,
`summary.csv`, `equity_curve.csv`, `manifest.json`, `report_manifest.json`,
plus any other `*.csv` under `{run_dir}/weights/`.

Bundle is written to `{run_dir}/bundle.zip` (atomic) and registered in
`report_files` with `kind="bundle"`.

### F6 — APScheduler weekly featured digest

**File:** new `src/atlas20/api/scheduler.py`; wire into `app.py` lifespan.

Use `apscheduler.schedulers.asyncio.AsyncIOScheduler`. Job:
`generate_featured_digest()` runs every Monday 00:00 UTC.

The job:
1. Pick the most recent run by `created_at` (DB) with `status="completed"`.
2. Call `generate_run_report(run_id, {markdown, pdf, png, bundle})`.
3. Insert a `KvSetting` row `featured_digest_run_id = <run_id>` so
   `get_featured_digest()` can read it.
4. Update `services.get_featured_digest()` to consult `kv_settings` first;
   fall back to current "newest markdown" heuristic.

Add a CLI command `python -m atlas20.api.scripts.generate_digest --week N`
that triggers the job out-of-schedule (uses `--week N` to pick the run from
N weeks ago for replay).

**Test fixture:** disable the scheduler in pytest via
`ATLAS20_DISABLE_SCHEDULER=1` env; test the job function directly without
APScheduler.

### F7 — Per-run report_manifest.json

**File:** extend `src/atlas20/reporting/report.py` (or new
`src/atlas20/api/manifest.py`).

After every successful generation, write `{run_dir}/report_manifest.json`:

```json
{
  "run_id": "btk_0142",
  "generated_at": "2026-05-20T00:00:00Z",
  "artifacts": [
    {"kind": "markdown", "path": "digest.md", "sha256": "...", "size": 4321},
    {"kind": "pdf",      "path": "digest.pdf", "sha256": "...", "size": 73210},
    {"kind": "png",      "path": "equity_curve.png", "sha256": "...", "size": 18432},
    {"kind": "bundle",   "path": "bundle.zip", "sha256": "...", "size": 95113}
  ]
}
```

F1's download handler reads this manifest to whitelist artifact access.

### Algorithm decisions

- **Synchronous generation in MVP** — single-format ≤ 30s; 5/min rate
  cap is enough. Long-running jobs can move to the Batch 9 worker pool
  later (track for Batch 14 if a real run shows multi-minute generation).
- **No idempotency key for `/reports/generate`** in this batch — the run_id
  is the natural key, and overwriting a previously generated digest is the
  desired behavior (regeneration after a worker re-run is a use case).
- **No streaming Range support** — files are ≤ 1MB typical; full
  `FileResponse` is fine. Track for Batch 14 if PDF/bundle grows large.
- **Path safety > performance** — manifest sha256 verification is done on
  every download (re-hash the file). For typical ≤ 1MB sizes this is sub-ms
  on modern hardware; if it becomes a hotspot the cached `report_files.sha256`
  column can be trusted instead.
- **APScheduler disabled in tests** — see F6 fixture note.

### Tests (~20 new)

1. `tests/test_download_path_safety.py`:
   - Symlink/`..` traversal → 403
   - Path outside `report_root` → 403
   - Path not in manifest → 403
   - Path in manifest but file content sha256 mismatch → 403
   - Valid path + valid sha256 → 200 streaming bytes
2. `tests/test_download_streaming.py`:
   - GET `/api/reports/{report_id}/download?format=markdown` → 200 + 
     `Content-Type: text/markdown` + `Content-Disposition: attachment`
   - GET `/api/reports/digest/download?format=bundle` → 200 + ZIP body
3. `tests/test_generate_report.py`:
   - POST with unknown run_id → 404
   - POST with valid run_id + `formats=["markdown"]` → 202, files contains
     `kind=markdown`, file exists on disk, sha256 in DB matches file hash
   - POST with `formats=["markdown","png","bundle"]` → 202, all 3 files
     present
   - POST with `formats=["pdf"]` when weasyprint unavailable → 202 with
     `files=[]` and a warning in the response payload (or in a separate
     `errors` list)
4. `tests/test_report_manifest.py`:
   - Manifest written with correct schema after generate
   - Manifest sha256 matches file content
5. `tests/test_scheduler.py`:
   - Job picks most recent completed run
   - Job writes `KvSetting(featured_digest_run_id=...)`
   - `get_featured_digest()` reads from `kv_settings` first

Frontend tests unchanged (132); the U11 modal already POSTs to
`/reports/generate` and surfaces errors per Batch 10's `3f03bec`.

## Out of scope

- Asynchronous generation (worker queue for reports) — defer to Batch 14
  if needed.
- Email/webhook notification when scheduled digest completes.
- PDF templating (custom CSS, header/footer) — use plain markdown→HTML.
- Versioned report retention beyond what `report_files` already provides.

## Acceptance

- `python -m pytest tests/ -x -q` → 269 → ~289 (+20)
- `cd apps/web && npm run test -- --run` → 132 unchanged
- `cd apps/web && npm run lint && npm run typecheck` → clean
- Manual: `POST /api/reports/generate { run_id: "btk_0142", formats: ["markdown"] }`
  with valid API key → 202; `GET /api/reports/btk_0142/download?format=markdown`
  → 200 streaming the generated digest.
- Path traversal attempt: `GET /api/reports/btk_0142/download?format=../../etc/passwd`
  → 422 (format enum rejects) OR 403 (path resolve rejects).

## Files expected to change

| File | Action | Est LOC |
|---|---|---|
| `src/atlas20/api/routes/reports.py` | Replace 3 stub routes with streaming + real generate | +60 -20 |
| `src/atlas20/api/services.py` | Drop `build_*_download_url`; add `resolve_download` | +50 -30 |
| `src/atlas20/api/services_report.py` | New: `generate_run_report`, `generate_bundle`, etc | +200 |
| `src/atlas20/api/manifest.py` | New: report_manifest read/write/verify | +80 |
| `src/atlas20/api/scheduler.py` | New: APScheduler wiring + job | +60 |
| `src/atlas20/api/scripts/generate_digest.py` | New CLI | +30 |
| `src/atlas20/api/app.py` | Lifespan: start/stop scheduler | +10 |
| `src/atlas20/api/repositories/reports_repo.py` | Add `upsert(file)` helper | +15 |
| `pyproject.toml` + requirements | Add `weasyprint`, `apscheduler`, `markdown` (if missing) | +5 |
| `tests/test_download_path_safety.py` | New | +60 |
| `tests/test_download_streaming.py` | New | +40 |
| `tests/test_generate_report.py` | New | +80 |
| `tests/test_report_manifest.py` | New | +30 |
| `tests/test_scheduler.py` | New | +40 |
| `tests/conftest.py` | Add `ATLAS20_DISABLE_SCHEDULER` autouse | +5 |
| **Total** | | **~770 (550 source + 220 tests)** |
