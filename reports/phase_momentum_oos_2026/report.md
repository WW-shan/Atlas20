# Phase-Momentum Frozen-Spec Out-of-Sample Tracking

Research sample: `2022-01-01` .. `2026-09-21`. 
Out-of-sample window: `2026-09-22` .. `2026-10-06` (15 daily observations).

The champion specification was frozen before this window. This report does not
tune parameters, universe membership, costs, or execution timing. The window is
too short to validate the strategy; it records whether the frozen rules continue
to behave as expected after the research cutoff.

## OOS summary

| index | fill_policy | cost_bps | start | end | days | observed_weight_share | turnover | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | close | 2.0000 | 2026-09-22 00:00:00 | 2026-10-06 00:00:00 | 15.0000 | 1.0000 | 0.9063 | 1.0561 | 3.1476 | 2.3376 | -0.1009 |
| 1 | h3_day_close | 2.0000 | 2026-09-22 00:00:00 | 2026-10-06 00:00:00 | 15.0000 | 1.0000 | 0.9218 | 1.0504 | 2.5993 | 2.1380 | -0.1050 |
| 2 | h3_prior_close | 2.0000 | 2026-09-22 00:00:00 | 2026-10-06 00:00:00 | 15.0000 | 1.0000 | 0.9218 | 1.0504 | 2.5993 | 2.1380 | -0.1050 |
| 3 | close | 20.0000 | 2026-09-22 00:00:00 | 2026-10-06 00:00:00 | 15.0000 | 1.0000 | 0.9063 | 1.0544 | 2.9748 | 2.2787 | -0.1015 |
| 4 | h3_day_close | 20.0000 | 2026-09-22 00:00:00 | 2026-10-06 00:00:00 | 15.0000 | 1.0000 | 0.9218 | 1.0486 | 2.4469 | 2.0780 | -0.1057 |
| 5 | h3_prior_close | 20.0000 | 2026-09-22 00:00:00 | 2026-10-06 00:00:00 | 15.0000 | 1.0000 | 0.9218 | 1.0486 | 2.4469 | 2.0780 | -0.1057 |
| 6 | close | 50.0000 | 2026-09-22 00:00:00 | 2026-10-06 00:00:00 | 15.0000 | 1.0000 | 0.9063 | 1.0515 | 2.7027 | 2.1803 | -0.1026 |
| 7 | h3_day_close | 50.0000 | 2026-09-22 00:00:00 | 2026-10-06 00:00:00 | 15.0000 | 1.0000 | 0.9218 | 1.0457 | 2.2070 | 1.9777 | -0.1067 |
| 8 | h3_prior_close | 50.0000 | 2026-09-22 00:00:00 | 2026-10-06 00:00:00 | 15.0000 | 1.0000 | 0.9218 | 1.0457 | 2.2070 | 1.9777 | -0.1067 |
| 9 | close | 100.0000 | 2026-09-22 00:00:00 | 2026-10-06 00:00:00 | 15.0000 | 1.0000 | 0.9063 | 1.0467 | 2.2897 | 2.0157 | -0.1043 |
| 10 | h3_day_close | 100.0000 | 2026-09-22 00:00:00 | 2026-10-06 00:00:00 | 15.0000 | 1.0000 | 0.9218 | 1.0409 | 1.8435 | 1.8099 | -0.1084 |
| 11 | h3_prior_close | 100.0000 | 2026-09-22 00:00:00 | 2026-10-06 00:00:00 | 15.0000 | 1.0000 | 0.9218 | 1.0409 | 1.8435 | 1.8099 | -0.1084 |

`close` is the production engine's signal-close fill. `h3_day_close` and
`h3_prior_close` fill three hours after the signal close and bracket coins without
usable hourly candles. `observed_weight_share` is the share of OOS traded target
weight with a usable hourly fill; 1.0 means every traded target is observed.
Sharpe and CAGR are annualized diagnostics over a very short window and are not
used as validation evidence.

## BTC benchmark

| index | fill_policy | cost_bps | start | end | days | observed_weight_share | turnover | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | btc_close | 0.0000 | 2026-09-22 00:00:00 | 2026-10-06 00:00:00 | 15.0000 | 1.0000 | 0.0000 | 0.9879 | -0.2714 | -1.5295 | -0.0358 |

## Data and scope

- Panel end date: `2026-10-06` (latest verified data at report time).
- OOS starts on the first daily close after the research cutoff: `2026-09-22`.
- Strict point-in-time Top20, long-only spot, no leverage, gross exposure <= 1.0.
- No parameter, universe, or execution rule was changed after seeing this window.

This file is a research tracking report only. It does not place orders.
