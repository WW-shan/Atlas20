ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\reviewer.md
<TASK>
Round-1 review of Atlas20 Batch 10.

TARGET: commit `c20b1d3` — "feat(api+ui): R10 batch 10 — R2 disk fallback + C5 verify + U10/U11 modals"

BRIEF: `.ccg/tasks/batch-10-run-history/brief.md`

DIFF: `git show c20b1d3 --stat` then per-file dives.

REVIEW DIMENSIONS:

1. **R2 disk fallback** in `services.py`:
   - Triggered only when DB empty
   - Reads manifest.json (NOT directory names)
   - Handles missing/malformed manifest gracefully (skip + log warning)
   - Test covers: DB empty + disk present, DB present + disk ignored, both empty
   - Sort order: by mtime DESC (deterministic)

2. **C5 favorite sync test:**
   - Verifies toggle via POST → DB update → /api/runs read shows favorited
   - Verifies queue endpoint reflects same favorited state
   - No code change expected (regression test only)

3. **U10 ADD STRATEGY modal:**
   - `StrategyCompareTab.tsx` adds button + Dialog mount
   - `AddStrategyModal.tsx` (NEW): multi-select listbox from getOptions().presets
   - Search filter
   - Already-selected pre-checked
   - Submit updates compare ids (URL state?)
   - Cancel preserves prior
   - Test asserts 2 new strategies appear as columns after submit
   - Dialog component exists (NEW or reused) — verify focus trap + ESC close

4. **U11 NEW REPORT modal + stub:**
   - `NewReportModal.tsx` (NEW): type radio, formats checkboxes, optional strategy select, notes
   - `POST /api/reports/generate` stub returns 202 + job_id
   - `GenerateReportRequest` schema in schemas.py (StrictApiModel)
   - Validation: empty formats list → 422
   - Frontend submits → toast "queued"

5. **Dialog component (if new):**
   - role="dialog"
   - aria-modal="true"
   - Focus trap on mount
   - Escape closes
   - Tab/Shift-Tab cycle stays within
   - Backdrop click closes (or doesn't, document choice)

6. **Schemas:**
   - GenerateReportRequest uses StrictApiModel (rejects extra fields)
   - Formats: min_length=1 enforced
   - type literal matches brief

7. **Test coverage** — 8 backend + 8 frontend new tests, walk through.

Watch for new issues:
- Backend manifest parsing doesn't have path-traversal (we read .json files under report_root only)
- Frontend Dialog accessibility (a11y: aria-labelledby for title, focus return on close)
- StrategyCompareTab: existing selected ids are preserved on modal cancel
- NewReportModal: form validation client-side mirrors server (formats min 1)

Run yourself:
- `python -m pytest tests/ -x -q` (expect 219)
- `cd apps/web && npm run test -- --run` (expect 131)
- `cd apps/web && npm run lint && npm run typecheck` clean

AUTHORITY: apply fixes for Critical/Warning. Commit:
`fix(api): batch 10 reviewer pass — <summary>`. Each fix separate.

REPORT:
- Score X/100
- Critical / Warning / Info
- Fixes applied: commits or 'none'
- Final test count
- Verdict: APPROVE / REQUEST_CHANGES

Keep under 1000 words.
</TASK>
