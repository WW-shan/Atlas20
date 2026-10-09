# Phase-Momentum Frozen-Spec Out-of-Sample Tracking

Tracked specification: `PR2026-10-H5` (registered trial PR2026-10-H5).

Research sample: `2022-01-01` .. `2026-09-21`. 
Out-of-sample window: `2026-09-22` .. `2026-10-08` (17 daily observations).

The champion specification was frozen before this window. This report does not
tune parameters, universe membership, costs, or execution timing. The window is
too short to validate the strategy; it records whether the frozen rules continue
to behave as expected after the research cutoff.

## OOS summary

| index | fill_policy | cost_bps | start | end | days | observed_weight_share | turnover | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | close | 2.0000 | 2026-09-22 00:00:00 | 2026-10-08 00:00:00 | 17.0000 | 1.0000 | 0.6803 | 0.9688 | -0.5143 | -0.9008 | -0.0874 |
| 1 | h3_day_close | 2.0000 | 2026-09-22 00:00:00 | 2026-10-08 00:00:00 | 17.0000 | 0.8959 | 0.7502 | 0.9705 | -0.4953 | -0.8406 | -0.0848 |
| 2 | h3_prior_close | 2.0000 | 2026-09-22 00:00:00 | 2026-10-08 00:00:00 | 17.0000 | 0.8959 | 0.7051 | 0.9702 | -0.4989 | -0.8500 | -0.0850 |
| 3 | close | 20.0000 | 2026-09-22 00:00:00 | 2026-10-08 00:00:00 | 17.0000 | 1.0000 | 0.6803 | 0.9677 | -0.5277 | -0.9481 | -0.0883 |
| 4 | h3_day_close | 20.0000 | 2026-09-22 00:00:00 | 2026-10-08 00:00:00 | 17.0000 | 0.8959 | 0.7502 | 0.9692 | -0.5106 | -0.8921 | -0.0858 |
| 5 | h3_prior_close | 20.0000 | 2026-09-22 00:00:00 | 2026-10-08 00:00:00 | 17.0000 | 0.8959 | 0.7051 | 0.9689 | -0.5132 | -0.8990 | -0.0860 |
| 6 | close | 50.0000 | 2026-09-22 00:00:00 | 2026-10-08 00:00:00 | 17.0000 | 1.0000 | 0.6803 | 0.9657 | -0.5492 | -1.0270 | -0.0898 |
| 7 | h3_day_close | 50.0000 | 2026-09-22 00:00:00 | 2026-10-08 00:00:00 | 17.0000 | 0.8959 | 0.7502 | 0.9670 | -0.5351 | -0.9781 | -0.0875 |
| 8 | h3_prior_close | 50.0000 | 2026-09-22 00:00:00 | 2026-10-08 00:00:00 | 17.0000 | 0.8959 | 0.7051 | 0.9669 | -0.5361 | -0.9809 | -0.0876 |
| 9 | close | 100.0000 | 2026-09-22 00:00:00 | 2026-10-08 00:00:00 | 17.0000 | 1.0000 | 0.6803 | 0.9624 | -0.5829 | -1.1590 | -0.0924 |
| 10 | h3_day_close | 100.0000 | 2026-09-22 00:00:00 | 2026-10-08 00:00:00 | 17.0000 | 0.8959 | 0.7502 | 0.9634 | -0.5733 | -1.1216 | -0.0903 |
| 11 | h3_prior_close | 100.0000 | 2026-09-22 00:00:00 | 2026-10-08 00:00:00 | 17.0000 | 0.8959 | 0.7051 | 0.9635 | -0.5720 | -1.1177 | -0.0902 |

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
| 0 | 2.0000 | h3_prior_close | 0.9702 | 1inch | -0.0000 | 0.0000 | 0.0000 | 0.5424 | 0.9702 | 0.9702 |
| 1 | 20.0000 | h3_prior_close | 0.9689 | 1inch | -0.0000 | 0.0000 | 0.0000 | 0.5424 | 0.9689 | 0.9689 |
| 2 | 50.0000 | h3_prior_close | 0.9669 | 1inch | -0.0000 | 0.0000 | 0.0000 | 0.5424 | 0.9669 | 0.9669 |
| 3 | 100.0000 | h3_day_close | 0.9634 | 1inch | -0.0000 | 0.0000 | 0.0000 | 0.5477 | 0.9634 | 0.9634 |

`drop_top5_multiple` is the attribution counterfactual "the five largest
contributors earned nothing, every position unchanged"; it is a concentration
measure, not a tradable strategy.

## BTC benchmark

| index | fill_policy | cost_bps | start | end | days | observed_weight_share | turnover | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | btc_close | 0.0000 | 2026-09-22 00:00:00 | 2026-10-08 00:00:00 | 17.0000 | 1.0000 | 0.0000 | 0.9431 | -0.7371 | -5.5871 | -0.0569 |

## Data and scope

- Panel end date: `2026-10-08` (latest verified data at report time).
- OOS starts on the first daily close after the research cutoff: `2026-09-22`.
- Strict point-in-time Top20, long-only spot, no leverage, gross exposure <= 1.0.
- No parameter, universe, or execution rule was changed after seeing this window.

This file is a research tracking report only. It does not place orders.
