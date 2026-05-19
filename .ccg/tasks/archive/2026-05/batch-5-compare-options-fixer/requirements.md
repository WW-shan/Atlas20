# Requirements

- Reject non-finite numeric values in compare/options CSV loaders.
- Extract shared CSV helpers into `src/atlas20/api/data_access/_common.py`.
- Route compare anchor handling through `_today()` and remove the direct `datetime.now()` fallback from compare data access.
- Keep public payloads and fallback behavior unchanged.
- Verify each fix with `python -m pytest tests/ -x -q`, and run `cd apps/web && npm run typecheck` after the refactor.
