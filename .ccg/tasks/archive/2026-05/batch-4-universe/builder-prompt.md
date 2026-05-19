You are the codex builder for Atlas20 Batch 4.

Read the brief at `.ccg/tasks/batch-4-universe/brief.md` and implement
EVERYTHING in the "Scope" section.

Hard requirements:
1. Follow the same data-access + service fallback pattern used in Batch 3 —
   look at `src/atlas20/api/data_access/overview.py` and the
   `_load_overview_payload` helper in `src/atlas20/api/services.py`.
2. New module `src/atlas20/api/data_access/universe.py` exports two
   functions: `load_universe_timeline_from_processed(settings) -> dict` and
   `load_data_alerts_from_processed(settings) -> list[dict]`. Raise
   `FileNotFoundError` or `ValueError` only — service layer catches both.
3. Schemas live in `src/atlas20/api/schemas.py` already (`UniverseTimelinePayload`,
   `DataAlert`). Do NOT add new schema fields.
4. Tests must use `tmp_path` and synthetic CSVs — do NOT depend on real
   `data/processed/*.csv` files (they may not exist in CI).
5. All tests must pass: `python -m pytest tests/ -x -q`.
6. Run `python -m pytest tests/ -x -q` yourself before reporting PASS;
   include the output in your final report.
7. Stage and commit when green with message:
   `feat(api): R6/R8 real universe timeline + data alerts with mock fallback`

Report format at the end:
- ✅/❌ PASS or FAIL
- Files changed
- Test count delta
- Any deviations from brief
