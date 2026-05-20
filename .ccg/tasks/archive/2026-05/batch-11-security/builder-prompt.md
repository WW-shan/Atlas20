ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Implement Atlas20 Batch 11 — Security S2-S9 + R7/R10 + C3.

Brief: `.ccg/tasks/batch-11-security/brief.md` (read fully first).

Scope: S2 CORS gate, S3 docs gate, S4 API key auth, S6 slowapi rate limit,
S7 typed Path params, S8 secret scan, S9 docs (no static mount), R7 Data
Sources real (mtime-based with 5min TTL cache), R10 Universe Refresh real
(enqueue as worker job kind), C3 verify _time.today() exhaustive.

S5 JWT deferred.

Hard requirements:
1. Read brief Scope exactly. No creep.
2. Add `slowapi>=0.1.9` to pyproject.toml.
3. Auth Depends + rate limit applied to MUTATING routes only (GET unauth'd).
4. API keys optional — empty set means auth disabled (back-compat).
5. Use pydantic v2 `Annotated[str, StringConstraints(pattern=...)]` syntax.
6. Worker run_one.py handles new `strategy="universe_refresh"` kind by
   calling `download_and_cache_raw_data` instead of `run_research_pipeline`.
7. R7 caches data source status for 5min (in-memory).
8. After each major chunk: pytest + npm test.
9. Final commit: `feat(api): R11 batch 11 — security S2-S9 + R7/R10 + C3`

Apply internal review before final commit.

Report:
- ✅/❌ PASS or FAIL
- Files created (count) / modified (count)
- Backend test count (was 220, expect ~250)
- Frontend test count (was 132)
- Any deviations
- Final commit hash
</TASK>
