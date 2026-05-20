ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\reviewer.md
<TASK>
Round-2 validation of Atlas20 Batch 8 reviewer fixes.

7 commits in scope, range `2382a00..HEAD`:

```
3fd5afb docs(api): batch 8 reviewer pass — document positionPct precision contract
0f7272a fix(api): batch 8 reviewer pass — reject unknown query params on /runs
5d57b44 test(api): batch 8 reviewer pass — ATLAS chip excludes non-family decoy
97be8c9 test(api): batch 8 reviewer pass — idempotency-key boundary regression
dc4a23c feat(ui): batch 8 reviewer pass — restore list/grid toggle as client-side state
727ca92 fix(api): batch 8 reviewer pass — robust project_root + missing base.yaml ValueError
363a460 fix(api): batch 8 reviewer pass — name offending fields in validation errors
```

These address round-1 reviewer findings:
- Codex W1/W2/W3 (3 Warning)
- Opus + Codex Info items (6 total)

For each commit, verify the original finding is genuinely resolved (code +
test coverage), and look for new regressions.

VALIDATION DIMENSIONS:

1. **363a460 W1 validator field names** — error messages on `costs`,
   `slots > topN` violations include the offending field names.

2. **727ca92 W2 project_root + base.yaml** —
   - `settings.project_root` defaults via `Path(__file__).resolve().parents[N]`
     pointing to repo root
   - `config_adapter` raises ValueError when base.yaml missing
   - `routes/backtests.py` try/except converts ValueError → HTTPException 422
   - Tests: settings default points to "Atlas20" dir; adapter raises with
     clear message; route returns 422

3. **dc4a23c W3 list/grid toggle restored** —
   - Toolbar has segmented control with role="radiogroup" + aria-label
   - RunHistoryTab has local viewMode state
   - "Grid" view renders cards (not table)
   - getRuns API call does NOT carry `view` param (verify in test)
   - Frontend test count went 121 → 122 (one toggle test added)

4. **97be8c9 idempotency boundary** —
   - 64-char key: 200/202 accepted
   - 65-char key: 422 rejected
   - `!!!` key: 422 rejected

5. **5d57b44 ATLAS chip decoy** —
   - Test creates decoy row family="Other" + strategy contains "ATLAS"
   - Asserts chip="ATLAS" filter excludes decoy

6. **0f7272a /api/runs strict** —
   - `HistoryFilter` uses StrictApiModel (extra="forbid") OR
     route uses explicit Pydantic Query model with forbid
   - `GET /api/runs?view=list` returns 422 with mention of "view"
   - Existing tests passing `dateRange`, `chips`, etc. still work

7. **3fd5afb positionPct docstring** — docstring added in
   `config_adapter.py` near positionPct mapping. No code change.

Look for NEW issues:
- StrictApiModel on HistoryFilter — does it accept the existing query
  params correctly? Specifically `chips` as list, `q` as string default ""?
- W2 try/except in route may swallow other ValueErrors. Verify the scope
  is narrow.
- Grid view UI — does it have proper test-id and accessibility attrs?

Run yourself:
- `python -m pytest tests/ -x -q` (expect 166 passed)
- `cd apps/web && npm run test -- --run` (expect 122)
- `cd apps/web && npm run lint` (clean)
- `cd apps/web && npm run typecheck` (clean)

AUTHORITY: apply additional fixes ONLY for new Critical/Warning. Commit:
`fix(api): batch 8 round 2 — <one-line summary>`.

REPORT FORMAT:
- Score X/100
- Per-commit verification: ✅ / ❌
- New findings: Critical/Warning/Info
- Fixes applied: commits or 'none'
- Final test count
- Verdict: APPROVE / REQUEST_CHANGES

If no new findings → APPROVE.

Keep under 1000 words.
</TASK>
