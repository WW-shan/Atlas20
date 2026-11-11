# Phase-Momentum Frozen-Spec Out-of-Sample Tracking

Tracked specification: `PR2026-10-H5` (registered trial PR2026-10-H5).

Research sample: `2022-01-01` .. `2026-09-21`. 
Out-of-sample window: `2026-09-22` .. `2026-11-10` (50 daily observations).

The champion specification was frozen before this window. This report does not
tune parameters, universe membership, costs, or execution timing. The window is
too short to validate the strategy; it records whether the frozen rules continue
to behave as expected after the research cutoff.

## OOS summary

| index | fill_policy | cost_bps | start | end | days | observed_weight_share | turnover | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | close | 20.0000 | 2026-09-22 00:00:00 | 2026-11-10 00:00:00 | 50.0000 | 1.0000 | 4.3003 | 0.9894 | -0.0765 | 0.1226 | -0.1455 |
| 1 | h3_day_close | 20.0000 | 2026-09-22 00:00:00 | 2026-11-10 00:00:00 | 50.0000 | 0.8447 | 4.2550 | 0.9524 | -0.3048 | -0.4247 | -0.1706 |
| 2 | h3_prior_close | 20.0000 | 2026-09-22 00:00:00 | 2026-11-10 00:00:00 | 50.0000 | 0.8447 | 4.3117 | 0.9981 | -0.0140 | 0.2386 | -0.1310 |

`close` is the production engine's signal-close fill. `h3_day_close` and
`h3_prior_close` fill three hours after the signal close and bracket coins without
usable hourly candles. `observed_weight_share` is the share of OOS traded target
weight with a usable hourly fill; 1.0 means every traded target is observed.
Sharpe and CAGR are annualized diagnostics over a very short window and are not
used as validation evidence.

## OOS per-coin concentration

RESEARCH.md section 00.8 shows the in-sample return is concentrated in a few
coins; this tracks the same measure after the research cutoff. The +3h rows use
the worse missing-candle policy at each cost. A short window makes these shares
noisy - they are recorded, not interpreted as validation.

| index | cost_bps | fill_policy | multiple | top1_coin | top1_share | top3_share | top5_share | contribution_hhi | drop_top1_multiple | drop_top5_multiple |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 20.0000 | h3_day_close | 0.9524 | near | -2.0630 | -2.3227 | -2.3227 | 7.1971 | 0.9288 | 0.9239 |

`drop_top5_multiple` is the attribution counterfactual "the five largest
contributors earned nothing, every position unchanged"; it is a concentration
measure, not a tradable strategy.

## BTC benchmark

| index | fill_policy | cost_bps | start | end | days | observed_weight_share | turnover | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | btc_close | 0.0000 | 2026-09-22 00:00:00 | 2026-11-10 00:00:00 | 50.0000 | 1.0000 | 0.0000 | 0.8512 | -0.6987 | -3.6565 | -0.1488 |

## Data and scope

- Panel end date: `2026-11-10` (latest verified data at report time).
- OOS starts on the first daily close after the research cutoff: `2026-09-22`.
- Strict point-in-time Top20, long-only spot, no leverage, gross exposure <= 1.0.
- No parameter, universe, or execution rule was changed after seeing this window.

This file is a research tracking report only. It does not place orders.
