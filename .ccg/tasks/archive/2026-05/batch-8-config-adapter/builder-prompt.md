ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Implement Atlas20 Batch 8 — E1 BacktestConfig → ResearchConfig adapter +
E7 resource validation + C1 drop view param + C2 chip semantics regression.

Brief: `.ccg/tasks/batch-8-config-adapter/brief.md` (read fully first).

Hard requirements:
1. Follow brief Scope exactly — no creep.
2. New file `src/atlas20/api/config_adapter.py` with `to_research_config`
   function. Map BacktestConfig → ResearchConfig per the brief table.
3. Extend BacktestConfig pydantic validators per E7 (window span ≤ 10y,
   end ≤ today via _time.today(), topN ≤ 50, slots ≤ topN, costs ≤ 1000).
4. Wire Idempotency-Key header on POST /backtests/run using existing
   IdempotencyRepo from Batch 7.
5. Remove `view` field/param everywhere (schemas, services, routes, FE
   api.ts and any feature/history/*.tsx that sends it).
6. Add C2 regression tests but DO NOT change `_matches_chip` logic — it's
   already correct.
7. Run `python -m pytest tests/ -x -q` after each major chunk.
8. Frontend: `cd apps/web && npm run test -- --run` + `npm run typecheck` +
   `npm run lint --max-warnings=0` all must stay green.
9. Final commit: `feat(api): R8 batch 8 — config adapter + resource validation + idempotency + C1/C2`

Apply your own internal review before final commit.

Report:
- ✅/❌ PASS or FAIL
- Files created / modified counts
- Backend test count (was 139)
- Frontend test count (was 122; expect 121 if grid toggle test removed, else 122)
- Final commit hash
- Any deviations
</TASK>
