ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Implement Atlas20 Batch 10 — R2 disk fallback + C5 verify + U10 ADD STRATEGY modal + U11 NEW REPORT stub.

Brief: `.ccg/tasks/batch-10-run-history/brief.md` (read fully first).

Scope:
- R2 backend disk fallback when DB empty (read manifest.json files, not directory names)
- C5 favorite sync verification (no code change expected, just regression test)
- U10 ADD STRATEGY modal in Compare tab — real multi-select using getOptions().presets
- U11 NEW REPORT modal in Reports tab — UI complete + stub backend endpoint
  (actual report generation is Batch 12)

Hard requirements:
1. Read brief Scope exactly, no creep.
2. R7/R10 are EXPLICITLY out of scope (Batch 11).
3. `Dialog` component: check if exists in `apps/web/src/components/ui/`; if
   not, create a minimal one (overlay + focus trap + Escape close + role=dialog).
4. `POST /api/reports/generate` is a STUB — returns 202 with hardcoded
   job_id. Real generation in Batch 12.
5. After each major chunk, run pytest + npm test.
6. Final commit: `feat(api+ui): R10 batch 10 — R2 disk fallback + C5 verify + U10/U11 modals`

Apply your own internal review before final commit.

Report:
- ✅/❌ PASS or FAIL
- Files created (count) / modified (count)
- Backend test count (was 211, expect ~219)
- Frontend test count (was 123, expect ~131)
- Final commit hash
- Any deviations
</TASK>
