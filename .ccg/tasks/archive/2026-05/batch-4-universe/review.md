# Batch 4 Universe Review

## Automated Verification

- Focused tests after TDD implementation: `10 passed in 0.59s`
- Full suite: `python -m pytest tests/ -x -q` -> `98 passed in 2.45s`
- Uvicorn smoke: `/api/universe/timeline` -> 200, `/api/universe/alerts` -> 200 on port 8000

## CCG External Review

Gemini review could not run because the local `gemini` CLI is not on PATH:

```text
gemini command not found in PATH
```

Claude reviewer returned no Critical findings.

### Addressed

- Changed the validation-failure alert title to use the brief's em dash.
- Added tests for the emitted alert titles.
- Removed unused `median_price_gap` from required alert columns because the brief's alert rules do not read it.
- Hardened rotation detection to only compare rebalance dates with top-20 rows.
- Wrapped the universe data-access import in `services.py` and documented deterministic timeline choices.

### Not Changed

- Claude suggested tolerating malformed non-alert `data_quality.csv` rows. This was not adopted because the brief explicitly says contract violations should raise `ValueError`, and the service layer catches that to fall back to mock data.

## Result

No Critical findings remain. The only deviation is the unavailable Gemini reviewer backend.
