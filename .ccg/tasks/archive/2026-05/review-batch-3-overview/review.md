# Review: Batch 3 Overview + Featured Digest

## Scope
- Commit reviewed: `6d5683d`
- Brief: `.ccg/tasks/archive/2026-05/batch-3-overview/brief.md`
- Code scope: `src/atlas20/api/data_access/*`, `src/atlas20/api/services.py`, and Batch 3 tests

## Validation Results
- Champion selection: `reports/latest/strategy_summary.csv` Sharpe top-1 is `ETH_BH__bull_only` (`0.573728367229925`), and `get_overview()` returns the same champion.
- YTD computation: current-year return for `ETH_BH__bull_only` is `0.0`; full-window return is `1.2868666971969986`, confirming the payload is not using the full window.
- Equity overlay: returns percentage series for champion vs `BTC_BH__always_on`; current payload has four YTD monthly points and does not expose raw equity values.
- Monthly resample: `equity_curve` length is `6`; `daily_returns` length is `6`.
- Frontend contract: `OverviewPayload.model_validate` succeeds, and strict JSON serialization with `allow_nan=False` succeeds for the real payload.
- Fallback paths: missing, empty, and malformed CSV cases are covered by tests and smoke validation.
- Featured digest: newest markdown by mtime is `reports/bear_bottom_to_current_2022_11_21_2026_04_22/profit_max_refine/champion_all_1m_14d_stop11_confirm2/champion_report.md`; API returns `champion_report` with `generated_at=2026-04-22T06:27:32Z`.

## Fix Applied
- Hardened `src/atlas20/api/data_access/overview.py` so `_as_float` rejects invalid, `NaN`, and infinite numeric values before they can reach the JSON payload.
- Added a regression test in `tests/test_overview_data_access.py` for blank numeric CSV cells that pandas parses as `NaN`.

## Verification
- `pytest -q tests/test_overview_data_access.py tests/test_services_overview_fallback.py tests/test_featured_digest.py`: 13 passed
- `pytest -q tests/`: 88 passed
- `npm test --prefix apps/web -- --run`: 106 passed
- Smoke: `python -c "from atlas20.api.services import get_overview; p = get_overview(); print(p.champion.strategy, p.hero_kpi.ytdReturn)"` printed `ETH_BH__bull_only 0.0`

## External Review
- Claude reviewer: PASS; only minor suggestions around more contextual error messages and broader non-finite test parameterization.
- Gemini reviewer: unavailable; `codeagent-wrapper` failed because `gemini` is not in PATH.

## Deferred
- CSV caching / mtime-based cache invalidation is deferred to the next batch as requested.
- No dependency, repository-pattern, or broader architectural changes were made.
