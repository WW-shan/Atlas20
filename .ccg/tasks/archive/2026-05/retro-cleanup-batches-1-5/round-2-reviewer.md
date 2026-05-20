ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\reviewer.md
<TASK>
Round-2 independent cross-validation of Atlas20 commits since `a4238fd`.

13 commits in scope (mix of Batch 6 reviewer/Info fixes + retro cleanup of
Batches 1-5):

```
fe10dd6 fix(api): retro — align fallback universe tokens with real-adapter ranking
6f9e689 fix(api): retro — align featured digest subtitle separator to middle dot
da3784d refactor(tests): retro — extract CSV-building fixtures into conftest
9fd26c6 chore(ui): batch 6 reviewer pass — wire real ESLint with TS/React/a11y plugins
a25ee65 refactor(api): retro — extract _time module; single datetime.now() entry
41d8aae docs(ui): batch 6 reviewer pass — document useRunQueue pairing
ef30d46 feat(api): retro — _latest_report_dir honors reports/latest.txt pointer
6fdf996 fix(ui): batch 6 reviewer pass — skeleton replaces sidebar only on initial load
2dc27eb refactor(api): retro — drop redundant to_numeric in NaN-guarded loaders
7aa4bdc refactor(api): retro — consolidate _as_* helpers, rename universe _as_text_or_default
4121279 fix(ui): batch 6 reviewer pass — stale-data pill instead of full ErrorBanner on overview refetch
e26d7a4 fix(ui): batch 6 reviewer pass — disable pending report downloads
dcb1d8d fix(ui): batch 6 reviewer pass — lock favorite controls during mutation
```

Diff range: `git diff a4238fd..HEAD`

NOTE: while you review, a fixer is concurrently applying 2 round-2 Opus
findings (path-traversal guard in _latest_report_dir + featured digest title
em-dash). Re-check HEAD before running pytest so you include any new fix
commits.

VALIDATION DIMENSIONS:

1. Each commit does what its message claims, no scope creep.
2. No import cycles after `_time.py` extraction (services -> _time -> settings).
3. `_as_float`'s new optional `column` parameter is backward-compatible —
   verify all call sites in overview.py / compare.py / options.py / universe.py.
4. `latest.txt` pointer reader is safe — does it handle:
   - empty file
   - file with whitespace
   - file with newline
   - path-traversal `../../etc` (NEW: fixer is adding guard)
   - absolute path
5. ESLint config (`apps/web/eslint.config.js`) doesn't suppress real bugs.
   `--max-warnings=0` is honest.
6. Conftest fixtures (`tests/conftest.py`) are imported by all 5 consumer
   test files. Verify no duplicate-definition leftovers.
7. Featured digest separator (`·` in subtitle, `—` in title after fixer).
   Verify consistency with mock_data fallback.
8. `mock_data.fallback_universe_timeline.tokens` order matches a frequency-
   ranked output.

Run yourself:
- `python -m pytest tests/ -x -q` (expect 119+ passed)
- `cd apps/web && npm run test -- --run` (expect 122 passed)
- `cd apps/web && npm run lint` (expect 0 warnings)
- `cd apps/web && npm run typecheck` (clean)

AUTHORITY: You CAN apply additional fixes if you find any Critical/Warning
that the Opus reviewer or fixer missed. Each fix = separate commit:
`fix(api): round 2 — <one-line summary>`

DO NOT touch the unrelated `.ccg/tasks/review-r3-premium-redesign/.turns.json`.

REPORT FORMAT:
- Each of the 13 commits: ✅ verified / ❌ issue found
- The 2 fixer commits (when they land): ✅ resolves Opus I-1/I-2
- New findings: Critical / Warning / Info (must list each with file:line)
- Fixes applied: list of commits or 'none'
- Final test counts (backend / frontend)
- Verdict: APPROVE / REQUEST_CHANGES

If you find no new findings AND all original findings resolved → APPROVE.

Keep report under 1000 words.
</TASK>
