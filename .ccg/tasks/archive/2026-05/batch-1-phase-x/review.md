# Batch 1 Phase X Review

## Files changed
- `src/atlas20/reporting/report.py`
- `tests/test_report_export.py`

## Tests added
- 6 report export tests covering per-strategy weights, selection history schema/sort order, manifest shape, write failure rollback, partial publish rollback, and `reports/latest.txt`.

## Validation
- `pytest -q tests/test_report_export.py` -> pass
- `pytest -q tests/` -> pass
- `pytest -q` -> pass
- `python -m compileall -q src/atlas20/reporting/report.py` -> pass
- `git diff --check -- src/atlas20/reporting/report.py tests/test_report_export.py` -> pass

## Manual smoke
- Synthetic export smoke is covered by `tests/test_report_export.py` using temporary report directories.
- Verified generated artifacts in the smoke path include:
  - `weights/BTC_BH__always_on.csv`
  - `weights/TOP20_EQ__always_on.csv`
  - `selection_history.csv`
  - `manifest.json`
  - `latest.txt`

## Review
- Claude reviewer found rollback and duplicate-index hardening issues; fixed before commit.
- Gemini reviewer could not run because `gemini` was not available on PATH.

## Deviations
- Full `python -m atlas20.pipeline --config config/base.yaml` was not run because `reports/latest` contains tracked generated artifacts and the smaller synthetic smoke covers the changed exporter behavior without overwriting them.
