# Review

## Fix Commits

- `717009d` - rejected non-finite compare/options numeric validator values and added a compare NaN regression test.
- `1924768` - extracted shared CSV helpers into `data_access/_common.py` and rewired overview, universe, compare, and options.
- `2de82d6` - routed compare service settings through `_today()` and made compare data access require `anchor_date` for bounded ranges.

## Verification

- After `717009d`: `python -m pytest tests/ -x -q` -> 110 passed.
- After `1924768`: `python -m pytest tests/ -x -q` -> 110 passed.
- After `1924768`: `npm run typecheck` in `apps/web` -> passed.
- After `2de82d6`: `python -m pytest tests/ -x -q` -> 112 passed.

## Notes

- The new NaN compare regression already passed before the validator reassignment because pandas `Series.map()` is eager. The code still now reassigns the mapped series explicitly, as requested.
