# Derivatives Shadow OOS Tracker — PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21

- window: 2022-01-01 00:00:00+00:00 → 2026-09-21 00:00:00+00:00 (1725 daily rows; 1724 metric returns)
- research only: yes; live execution: **no**
- frozen long/short book: H5 1.25x + LS45 stronger-21D profit-lock redistribution/regime short
- cost: 6 bps; capital reference: 1,000 units
- execution: 01:05 UTC; price model mark_1h_open_floor
- target ledger: oos_targets.csv; sha256 478a3ac190c294af551a79b01b621dd13570367c9489bd2d8f8550833ab2d38d
- funding: binance-proxy (complete for the OOS window)
- last mark: 2026-11-14 08:00:00+00:00; staleness: 2.1h
- warmup history: data/raw/bitget_derivatives/merged_20261009
- warmup provenance: sha256:77bff92b77750c483bc63041fa2b72d31f576dfaf006d167d91d9ce81121d0ad; 87 mark files; no observations in requested warmup window
- mark coverage: 25921 missing hours; 88 assets checked; 25921 gaps (25921 two-hour); max gap 2.0h
- execution-bar audit: 2477/2477 target pairs resolved; 0 missing

## OOS metrics

| spec | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- |
| PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21 | 83.9852 | 1.5564 | 2.0823 | -0.3165 |

## Execution and risk counters

| spec | max_target_gross | max_observed_gross | gross_breach_hours | short_opens | short_stops | liquidations | funding_total | fees_total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21 | 1.2500 | 1.2814 | 129.0000 | 332.0000 | 32.0000 | 1.0000 | -474.3084 | 611.6942 |

## Latest target book

- signal date: 2026-09-21 00:00:00+00:00

| asset | side | target_weight | target_notional_per_1k | change_weight | change_notional_per_1k | action | execution_hint |
| --- | --- | --- | --- | --- | --- | --- | --- |
| near | long | 0.1914 | 191.4007 | 0.0421 | 42.0761 | INCREASE | 2026-09-22 01:05:00+00:00 |
| zcash | long | 0.2494 | 249.4007 | -0.0356 | -35.6287 | DECREASE | 2026-09-22 01:05:00+00:00 |

The first daily row is the engine initialization point and is excluded from Sharpe/volatility; it remains in `oos_daily.csv`.

Research output only; not an order or a live approval.
