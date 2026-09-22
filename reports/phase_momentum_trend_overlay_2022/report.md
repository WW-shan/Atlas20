# Phase-Momentum Absolute Trend Overlay

Absolute-trend variants require the selected coin to trade above its own trailing moving average.
This is a direct test of the time-series-momentum evidence in Han et al. and related crypto trend research.

## Summary

| index | strategy | cost_bps | period | start | end | days | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | param_trend_50 | 20.0000 | full_2022_plus | 2022-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,725.0000 | 17.5659 | 0.8345 | 1.2343 | -0.5336 |
| 4 | param_trend_100_trailing_stop_20 | 20.0000 | full_2022_plus | 2022-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,725.0000 | 15.2185 | 0.7796 | 1.1967 | -0.5586 |
| 1 | param_trend_100 | 20.0000 | full_2022_plus | 2022-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,725.0000 | 14.7099 | 0.7669 | 1.1854 | -0.5586 |
| 5 | param_trend_100_target_vol_0.7 | 20.0000 | full_2022_plus | 2022-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,725.0000 | 12.4473 | 0.7055 | 1.1925 | -0.5134 |
| 2 | param_trend_150 | 20.0000 | full_2022_plus | 2022-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,725.0000 | 10.6758 | 0.6509 | 1.0827 | -0.5670 |
| 3 | param_trend_200 | 20.0000 | full_2022_plus | 2022-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,725.0000 | 10.5672 | 0.6474 | 1.0757 | -0.5251 |

## Interpretation

- The overlay is adopted only if it improves the risk/return trade-off without creating a narrow parameter spike.
- The primary no-overlay specification remains the benchmark until this table is combined with walk-forward and multiple-testing results.
