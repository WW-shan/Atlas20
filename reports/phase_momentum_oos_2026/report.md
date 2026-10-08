# Phase-Momentum Frozen-Spec Out-of-Sample Tracking

Tracked specification: `PR2026-10-H3` (registered trial PR2026-10-H3).

Research sample: `2022-01-01` .. `2026-09-21`. 
Out-of-sample window: `2026-09-22` .. `2026-10-07` (16 daily observations).

The champion specification was frozen before this window. This report does not
tune parameters, universe membership, costs, or execution timing. The window is
too short to validate the strategy; it records whether the frozen rules continue
to behave as expected after the research cutoff.

## OOS summary

| index | fill_policy | cost_bps | start | end | days | observed_weight_share | turnover | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | close | 2.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.9063 | 1.0961 | 8.3159 | 3.5049 | -0.1009 |
| 1 | h3_day_close | 2.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.9218 | 1.0902 | 7.1694 | 3.3164 | -0.1050 |
| 2 | h3_prior_close | 2.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.9218 | 1.0902 | 7.1694 | 3.3164 | -0.1050 |
| 3 | close | 20.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.9063 | 1.0943 | 7.9533 | 3.4497 | -0.1015 |
| 4 | h3_day_close | 20.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.9218 | 1.0883 | 6.8461 | 3.2601 | -0.1057 |
| 5 | h3_prior_close | 20.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.9218 | 1.0883 | 6.8461 | 3.2601 | -0.1057 |
| 6 | close | 50.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.9063 | 1.0913 | 7.3798 | 3.3573 | -0.1026 |
| 7 | h3_day_close | 50.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.9218 | 1.0853 | 6.3353 | 3.1661 | -0.1067 |
| 8 | h3_prior_close | 50.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.9218 | 1.0853 | 6.3353 | 3.1661 | -0.1067 |
| 9 | close | 100.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.9063 | 1.0864 | 6.5040 | 3.2028 | -0.1043 |
| 10 | h3_day_close | 100.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.9218 | 1.0803 | 5.5563 | 3.0088 | -0.1084 |
| 11 | h3_prior_close | 100.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.9218 | 1.0803 | 5.5563 | 3.0088 | -0.1084 |

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
| 0 | 2.0000 | h3_day_close | 1.0902 | near | 1.2240 | 1.2240 | 1.2240 | 1.5483 | 0.9758 | 0.9758 |
| 1 | 20.0000 | h3_day_close | 1.0883 | near | 1.2240 | 1.2240 | 1.2240 | 1.5483 | 0.9742 | 0.9742 |
| 2 | 50.0000 | h3_day_close | 1.0853 | near | 1.2240 | 1.2240 | 1.2240 | 1.5483 | 0.9715 | 0.9715 |
| 3 | 100.0000 | h3_day_close | 1.0803 | near | 1.2240 | 1.2240 | 1.2240 | 1.5483 | 0.9670 | 0.9670 |

`drop_top5_multiple` is the attribution counterfactual "the five largest
contributors earned nothing, every position unchanged"; it is a concentration
measure, not a tradable strategy.

## BTC benchmark

| index | fill_policy | cost_bps | start | end | days | observed_weight_share | turnover | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | btc_close | 0.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.0000 | 0.9616 | -0.6145 | -4.0774 | -0.0384 |

## Data and scope

- Panel end date: `2026-10-07` (latest verified data at report time).
- OOS starts on the first daily close after the research cutoff: `2026-09-22`.
- Strict point-in-time Top20, long-only spot, no leverage, gross exposure <= 1.0.
- No parameter, universe, or execution rule was changed after seeing this window.

This file is a research tracking report only. It does not place orders.
