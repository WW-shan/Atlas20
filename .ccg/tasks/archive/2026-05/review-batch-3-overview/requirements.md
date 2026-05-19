# Requirements

Cross-validate commit `6d5683d` against `.ccg/tasks/archive/2026-05/batch-3-overview/brief.md`.

Review scope:
- `src/atlas20/api/data_access/*`
- `src/atlas20/api/services.py`
- New and updated tests from the commit

Validation focus:
- Champion is selected by top Sharpe using `reports/latest/strategy_summary.csv`.
- YTD is computed as product of current-year daily returns minus one.
- Equity overlay compares champion and `BTC_BH__always_on` cumulative return percentages.
- Missing, empty, and malformed CSV inputs fall back without crashing at the service layer.
- Monthly equity curve resampling returns at most six points.
- `OverviewPayload.model_validate` continues to pass.
- Featured digest picks newest markdown by mtime.
- Note CSV caching opportunity without implementing it.
- Confirm pandas scalar/date/null values are JSON-safe.
