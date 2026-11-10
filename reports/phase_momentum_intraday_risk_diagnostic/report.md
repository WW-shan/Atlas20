# Intraday Risk Overlay Diagnostic

**Diagnostic only.** No rule is promoted, no trial is registered, and the live H5 book is unchanged.

This screen uses the frozen H5 target schedule and Binance hourly closes. A target from signal day D executes at 01:00 UTC on D+1; any hourly risk signal executes on the next hourly close. Missing hourly asset-days are geometrically interpolated from the daily return and explicitly counted.

Coverage: 84.71% of target-asset-days have all 24 hourly returns. The production +1h H5 anchor is shown separately because the hourly simulator is an approximation.

## Production anchor versus simulated baseline

| index | book | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- |
| 0 | production +1h | 22.8004 | 0.9387 | 1.7036 | -0.3327 |
| 1 | hourly simulator baseline | 21.5644 | 0.9159 | 1.6687 | -0.3745 |

## Summary

| index | overlay | multiple | cagr | sharpe | max_drawdown | events | turnover |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | baseline | 21.5644 | 0.9159 | 1.6687 | -0.3745 | 541.0000 | 117.4105 |
| 1 | fast_gate_roundtrip | 16.2994 | 0.8057 | 1.5606 | -0.3816 | 634.0000 | 137.9951 |
| 2 | fast_gate_slow_reentry | 18.4954 | 0.8546 | 1.6283 | -0.3967 | 622.0000 | 154.3881 |
| 3 | fixed_stop_5 | 16.6936 | 0.8148 | 1.5639 | -0.4254 | 572.0000 | 151.4572 |
| 4 | fixed_stop_8 | 20.4288 | 0.8941 | 1.6412 | -0.3951 | 545.0000 | 120.4570 |
| 5 | fixed_stop_10 | 21.5210 | 0.9151 | 1.6718 | -0.3690 | 543.0000 | 119.5632 |
| 6 | trailing_stop_5 | 10.4127 | 0.6422 | 1.4287 | -0.4224 | 596.0000 | 175.8482 |
| 7 | trailing_stop_8 | 21.0815 | 0.9067 | 1.6526 | -0.4023 | 550.0000 | 125.5711 |
| 8 | trailing_stop_10 | 21.5210 | 0.9151 | 1.6718 | -0.3690 | 543.0000 | 119.5632 |

## Yearly returns

| index | year | baseline | fast_gate_roundtrip | fast_gate_slow_reentry | fixed_stop_5 | fixed_stop_8 | fixed_stop_10 | trailing_stop_5 | trailing_stop_8 | trailing_stop_10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2022-12-31 00:00:00 | -0.1713 | -0.0780 | -0.1104 | -0.1680 | -0.1664 | -0.1713 | -0.1727 | -0.1664 | -0.1713 |
| 1 | 2023-12-31 00:00:00 | 2.0426 | 2.1073 | 2.0578 | 1.3735 | 1.9111 | 2.0365 | 0.9304 | 2.0089 | 2.0365 |
| 2 | 2024-12-31 00:00:00 | 1.0512 | 0.9303 | 1.0538 | 1.0809 | 1.0512 | 1.0512 | 0.5106 | 1.0512 | 1.0512 |
| 3 | 2025-12-31 00:00:00 | 1.0629 | 0.4774 | 0.6418 | 1.0102 | 1.0307 | 1.0629 | 1.1855 | 1.0275 | 1.0629 |
| 4 | 2026-12-31 00:00:00 | 1.0210 | 0.9950 | 1.0163 | 1.0210 | 1.0210 | 1.0210 | 0.9749 | 1.0210 | 1.0210 |

## Decision

None of the intraday overlays is promoted. The diagnostic must be treated as a rejected hypothesis generator, not as evidence for live intraday trading.
