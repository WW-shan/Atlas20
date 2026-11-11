# H5 Exit Forward-Return Diagnostic

Date: 2026-11-11  
Status: diagnostic only; no portfolio backtest and no new trial configuration.

## Question

When frozen H5 fully exits an asset while that asset is still in the point-in-time CMC Top20, does it
continue to underperform the contemporaneous Top20 equal-weight basket?

## Method

- H5 target events use `PR2026-10-H5`.
- An exit is an asset held at the previous H5 target event and absent at the current event.
- Eligibility requires membership in the latest point-in-time CMC Top20 snapshot at the signal date.
- Entry uses the next daily close after the signal to avoid same-close look-ahead.
- Forward horizons are 7/14/21/30/60 calendar days.
- Relative return is asset return minus the equal-weight return of all eligible Top20 members with
  finite prices at both endpoints.

## Results

| Horizon | Observations | Mean relative | Median relative | Underperform rate | iid t |
|---:|---:|---:|---:|---:|---:|
| 7D | 117 | -1.10% | -1.36% | 61.5% | -1.30 |
| 14D | 117 | -2.44% | -1.94% | 61.5% | -2.23 |
| **21D** | **117** | **-4.18%** | **-4.97%** | **66.7%** | **-3.18** |
| 30D | 117 | -4.66% | -4.05% | 63.2% | -2.89 |
| 60D | 117 | -5.46% | -6.70% | 65.0% | -2.61 |

21D by year:

| Year | Observations | Mean relative | Underperform rate |
|---|---:|---:|---:|
| 2022 | 6 | -0.61% | 66.7% |
| 2023 | 35 | +0.93% | 57.1% |
| 2024 | 36 | -9.50% | 72.2% |
| 2025 | 29 | -5.98% | 72.4% |
| 2026 | 11 | -0.18% | 63.6% |

## Interpretation

The exit effect is directionally consistent across 7/14/21/30/60 days and is not concentrated in
2022. It motivated the pre-registered LS3 production-engine test.

This diagnostic does **not** include:

- short stop-loss execution;
- isolated-margin liquidation;
- funding;
- Bitget mark path;
- fees and slippage;
- gross exposure or next-tick guard;
- portfolio compounding.

The LS3 production result is therefore authoritative. Its return improved strongly, but it was
rejected because of drawdown, gross breaches, 100bps cost failure, PBO, DSR, rolling worst and asset
concentration.

Files:

- `exit_forward_returns.csv`
- `exit_short_summary.csv`
