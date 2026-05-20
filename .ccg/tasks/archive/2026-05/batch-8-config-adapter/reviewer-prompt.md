ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\reviewer.md
<TASK>
Round-1 review of Atlas20 Batch 8.

TARGET: commit `2382a00` — "feat(api): R8 batch 8 — config adapter + resource validation + idempotency + C1/C2"

BRIEF: `.ccg/tasks/batch-8-config-adapter/brief.md` (codex archived may be under .ccg/tasks/archive/2026-05/)

DIFF: `git diff HEAD~1 HEAD --stat` then per-file:
- `src/atlas20/api/config_adapter.py` (NEW)
- `src/atlas20/api/schemas.py` (validators)
- `src/atlas20/api/services.py` (drop view + idempotency)
- `src/atlas20/api/routes/runs.py` (drop view)
- `src/atlas20/api/routes/backtests.py` (Idempotency-Key header)
- `src/atlas20/api/settings.py` (project_root)
- `apps/web/src/lib/api.ts` (drop view)
- `apps/web/src/features/history/*.tsx` (drop view UI)

REVIEW DIMENSIONS:

1. **E1 adapter correctness vs brief table:**
   - preset → config/{slug}.yaml or base fallback (case-insensitive? slug normalization?)
   - universe.topN → UniverseConfig.universe_size
   - universe.excludeStable → stablecoin_ids set to [] when False
   - universe.excludeWrapped → exclude_wrapped_assets
   - window.start/end → start_date / end_date as "YYYY-MM-DD"
   - window.rebalance → SINGLE-entry frequencies dict (Weekly=7D, Biweekly=14D, Monthly=month_end)
   - allocation.positionPct → frictions.max_weight_per_coin / 100
   - allocation.slots → stored in params JSON (NOT in ResearchConfig)
   - costs.feeBps/slippageBps → frictions.fee_bps / slippage_bps
   - project_root set from settings

2. **E7 validators correctness:**
   - window span ≤ 10 years
   - end ≤ today via atlas20.api._time.today() (NOT date.today())
   - topN ≤ 50 (via Field(le=50))
   - slots ≤ topN
   - feeBps + slippageBps ≤ 1000
   - Each gives a 422 with the offending field in detail
   - Validators are AFTER model construction (model_validator(mode="after"))

3. **Idempotency:**
   - POST /backtests/run reads Idempotency-Key header
   - Validation regex (brief said 8-64 alphanumeric/dash/underscore)
   - **DEVIATION FROM BRIEF**: codex noted the 8-char floor was NOT enforced.
     Verify the actual regex used and decide if it's acceptable for MVP.
     My (Claude) call: accept 1-64 chars is fine for MVP; the 8-char minimum
     was a brief-specified guard rail not a hard requirement.
   - Stored response has `Run` summary serialized
   - 24h TTL via existing IdempotencyRepo
   - Repeat call returns cached without inserting new run
   - Invalid key → 422

4. **C1 view removal:**
   - schemas.HistoryFilter: no `view` field
   - services.list_runs: no view param
   - routes/runs.py: no view query param
   - apps/web/src/lib/api.ts: no view in getRuns params type
   - History tab no longer sends view (grid/list toggle is local state only)
   - Any test still using view is updated

5. **C2 chip regression tests:**
   - chip="ATLAS" → family match only, not substring
   - chip="MOMENTUM_LEAD" → substring match
   - chip="favorited" → favorited filter
   - chip="completed" → status filter
   - Logic NOT changed, only tests added

6. **New issues to look for:**
   - `project_root` in settings — does it have a sensible default?
   - YAML load errors handled gracefully (FileNotFoundError → fallback, ParserError → ValueError)?
   - Rebalance dict ALWAYS has exactly one entry (engine may assume more)?
   - Strategy preset slug normalization — special chars stripped?
   - Frontend grid/list toggle still works locally without backend?

7. **Test coverage check:**
   - 20 new tests claimed. Walk through:
     * test_config_adapter.py — 10 tests covering all 8 mapping cases + 2 error paths
     * test_backtest_config_validation.py — 7 tests covering all 5 validators + happy + 1 boundary
     * test_idempotency_route.py — 4 tests covering all 4 brief cases
     * test_api_services.py — at least 4 C2 chip tests

Run yourself:
- `python -m pytest tests/ -x -q` (expect 159 passed)
- `cd apps/web && npm run test -- --run` (expect 121)
- `cd apps/web && npm run lint` (clean)
- `cd apps/web && npm run typecheck` (clean)

AUTHORITY: Apply fixes for Critical/Warning. Commit:
`fix(api): batch 8 reviewer pass — <one-line summary>`

REPORT FORMAT:
- Score X/100
- Critical: [...] or 'none'
- Warning: [...] or 'none'
- Info: [...]
- Fixes applied: commits or 'none'
- Final test counts
- Verdict: APPROVE / REQUEST_CHANGES

Keep under 1000 words.
</TASK>
