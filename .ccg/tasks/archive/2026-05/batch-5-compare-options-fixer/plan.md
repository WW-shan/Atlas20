# Plan

1. Add a regression test for the compare NaN leak, then fix the validator mapping in `compare.py` and `options.py`.
2. Extract shared data-access CSV helpers into `_common.py` and update `overview.py`, `universe.py`, `compare.py`, and `options.py` to import from it.
3. Route compare anchor handling through `_today()` in `services.py`, remove the datetime fallback in `compare.py`, and clean up imports.
4. Run the requested test and typecheck commands after each commit, then archive the task record.
