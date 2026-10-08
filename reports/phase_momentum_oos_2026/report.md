# Phase-Momentum Frozen-Spec Out-of-Sample Tracking

Tracked specification: `PR2026-10-H5` (registered trial PR2026-10-H5).

Research sample: `2022-01-01` .. `2026-09-21`. 
Out-of-sample window: `2026-09-22` .. `2026-10-07` (16 daily observations).

The champion specification was frozen before this window. This report does not
tune parameters, universe membership, costs, or execution timing. The window is
too short to validate the strategy; it records whether the frozen rules continue
to behave as expected after the research cutoff.

## OOS summary

| index | fill_policy | cost_bps | start | end | days | observed_weight_share | turnover | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | close | 2.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.6794 | 1.0574 | 2.8924 | 3.2239 | -0.0647 |
| 1 | h3_day_close | 2.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.7033 | 1.0589 | 3.0245 | 3.3044 | -0.0634 |
| 2 | h3_prior_close | 2.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.7033 | 1.0589 | 3.0245 | 3.3044 | -0.0634 |
| 3 | close | 20.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.6794 | 1.0561 | 2.7782 | 3.1598 | -0.0652 |
| 4 | h3_day_close | 20.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.7033 | 1.0576 | 2.9024 | 3.2379 | -0.0639 |
| 5 | h3_prior_close | 20.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.7033 | 1.0576 | 2.9024 | 3.2379 | -0.0639 |
| 6 | close | 50.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.6794 | 1.0540 | 2.5953 | 3.0526 | -0.0661 |
| 7 | h3_day_close | 50.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.7033 | 1.0553 | 2.7070 | 3.1269 | -0.0648 |
| 8 | h3_prior_close | 50.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.7033 | 1.0553 | 2.7070 | 3.1269 | -0.0648 |
| 9 | close | 100.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.6794 | 1.0504 | 2.3099 | 2.8730 | -0.0675 |
| 10 | h3_day_close | 100.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.7033 | 1.0516 | 2.4028 | 2.9408 | -0.0662 |
| 11 | h3_prior_close | 100.0000 | 2026-09-22 00:00:00 | 2026-10-07 00:00:00 | 16.0000 | 1.0000 | 0.7033 | 1.0516 | 2.4028 | 2.9408 | -0.0662 |

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
| 0 | 2.0000 | h3_day_close | 1.0589 | near | 1.2306 | 1.2306 | 1.2306 | 1.5675 | 0.9848 | 0.9848 |
| 1 | 20.0000 | h3_day_close | 1.0576 | near | 1.2306 | 1.2306 | 1.2306 | 1.5675 | 0.9835 | 0.9835 |
| 2 | 50.0000 | h3_day_close | 1.0553 | near | 1.2306 | 1.2306 | 1.2306 | 1.5675 | 0.9814 | 0.9814 |
| 3 | 100.0000 | h3_day_close | 1.0516 | near | 1.2306 | 1.2306 | 1.2306 | 1.5675 | 0.9780 | 0.9780 |

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
