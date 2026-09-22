# Point-in-Time Top20 Daily Momentum-Event Ensemble

## Structure

- Daily point-in-time Top20 universe; no Top50/Top100 expansion.
- Three momentum-like CTREND-lite score families: balanced, relative strength, breakout.
- Daily event rule: min hold 5 days, hold-rank band 2, 10% score gap, 1-day confirmation.
- The incumbent is exited immediately if it leaves the current Top20.
- BTC 100-day moving-average gate with 2-day confirmation.
- 60-day realized-volatility target; primary sleeves use 70% and 80% target volatility.
- Gross exposure is capped at 1.0; no shorting and no leverage.
- Signals are generated at close and executed T+1.

## Primary summary

| index | strategy | cost_bps | period | start | end | days | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | momentum3_event_ensemble | 2.0000 | full_2022_plus | 2022-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,725.0000 | 28.9161 | 1.0387 | 1.4343 | -0.4615 |
| 3 | momentum3_event_ensemble | 20.0000 | full_2022_plus | 2022-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,725.0000 | 19.6927 | 0.8794 | 1.3061 | -0.4865 |
| 6 | momentum3_event_ensemble | 50.0000 | full_2022_plus | 2022-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,725.0000 | 10.3658 | 0.6407 | 1.0902 | -0.5449 |
| 9 | momentum3_event_ensemble | 100.0000 | full_2022_plus | 2022-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,725.0000 | 3.5424 | 0.3071 | 0.7255 | -0.6351 |
| 1 | momentum3_event_ensemble | 2.0000 | post_2023 | 2023-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,360.0000 | 39.9053 | 1.6916 | 1.7506 | -0.4615 |
| 4 | momentum3_event_ensemble | 20.0000 | post_2023 | 2023-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,360.0000 | 27.6810 | 1.4397 | 1.6119 | -0.4865 |
| 7 | momentum3_event_ensemble | 50.0000 | post_2023 | 2023-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,360.0000 | 15.0250 | 1.0705 | 1.3781 | -0.5284 |
| 10 | momentum3_event_ensemble | 100.0000 | post_2023 | 2023-01-01 00:00:00 | 2026-09-21 00:00:00 | 1,360.0000 | 5.4051 | 0.5733 | 0.9830 | -0.6033 |
| 2 | momentum3_event_ensemble | 2.0000 | post_2024 | 2024-01-01 00:00:00 | 2026-09-21 00:00:00 | 995.0000 | 13.6047 | 1.6079 | 1.6963 | -0.4615 |
| 5 | momentum3_event_ensemble | 20.0000 | post_2024 | 2024-01-01 00:00:00 | 2026-09-21 00:00:00 | 995.0000 | 10.7472 | 1.3916 | 1.5751 | -0.4865 |
| 8 | momentum3_event_ensemble | 50.0000 | post_2024 | 2024-01-01 00:00:00 | 2026-09-21 00:00:00 | 995.0000 | 7.2488 | 1.0696 | 1.3708 | -0.5284 |
| 11 | momentum3_event_ensemble | 100.0000 | post_2024 | 2024-01-01 00:00:00 | 2026-09-21 00:00:00 | 995.0000 | 3.7512 | 0.6249 | 1.0249 | -0.6033 |

## Event-spec sensitivity

| index | spec | cost_bps | full_multiple | post_2024_multiple |
| --- | --- | --- | --- | --- |
| 0 | primary_mh5_hr2_g10_c1 | 2.0000 | 28.9161 | 13.6047 |
| 4 | loose_gap_mh5_hr2_g05_c1 | 2.0000 | 24.6573 | 8.8422 |
| 8 | wide_band_mh5_hr3_g05_c1 | 2.0000 | 15.7881 | 6.5678 |
| 12 | slow_mh10_hr2_g10_c1 | 2.0000 | 8.8009 | 4.5868 |
| 1 | primary_mh5_hr2_g10_c1 | 20.0000 | 19.6927 | 10.7472 |
| 5 | loose_gap_mh5_hr2_g05_c1 | 20.0000 | 16.4338 | 6.8244 |
| 9 | wide_band_mh5_hr3_g05_c1 | 20.0000 | 10.6760 | 5.1215 |
| 13 | slow_mh10_hr2_g10_c1 | 20.0000 | 6.6577 | 3.8716 |
| 2 | primary_mh5_hr2_g10_c1 | 50.0000 | 10.3658 | 7.2488 |
| 6 | loose_gap_mh5_hr2_g05_c1 | 50.0000 | 8.3439 | 4.4275 |
| 10 | wide_band_mh5_hr3_g05_c1 | 50.0000 | 5.5528 | 3.3801 |
| 14 | slow_mh10_hr2_g10_c1 | 50.0000 | 4.1773 | 2.9170 |
| 3 | primary_mh5_hr2_g10_c1 | 100.0000 | 3.5424 | 3.7512 |
| 7 | loose_gap_mh5_hr2_g05_c1 | 100.0000 | 2.6842 | 2.1470 |
| 15 | slow_mh10_hr2_g10_c1 | 100.0000 | 1.9158 | 1.8167 |
| 11 | wide_band_mh5_hr3_g05_c1 | 100.0000 | 1.8596 | 1.6865 |

## Strict Top20 membership sensitivity

| index | strict_top20_exit | cost_bps | full_multiple | post_2024_multiple |
| --- | --- | --- | --- | --- |
| 4 | 0.0000 | 2.0000 | 41.5230 | 17.8141 |
| 0 | 1.0000 | 2.0000 | 28.9161 | 13.6047 |
| 5 | 0.0000 | 20.0000 | 28.4345 | 14.0744 |
| 1 | 1.0000 | 20.0000 | 19.6927 | 10.7472 |
| 6 | 0.0000 | 50.0000 | 15.1054 | 9.4951 |
| 2 | 1.0000 | 50.0000 | 10.3658 | 7.2488 |
| 7 | 0.0000 | 100.0000 | 5.2417 | 4.9153 |
| 3 | 1.0000 | 100.0000 | 3.5424 | 3.7512 |

## Pre-2022 stress check

| index | strategy | cost_bps | period | start | end | days | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | momentum3_event_ensemble | 2.0000 | stress_2020_10_to_2021_12 | 2020-10-03 00:00:00 | 2021-12-31 00:00:00 | 455.0000 | 6.6200 | 3.5703 | 2.5904 | -0.2838 |
| 1 | momentum3_event_ensemble | 20.0000 | stress_2020_10_to_2021_12 | 2020-10-03 00:00:00 | 2021-12-31 00:00:00 | 455.0000 | 6.1327 | 3.2978 | 2.4996 | -0.2889 |
| 2 | momentum3_event_ensemble | 50.0000 | stress_2020_10_to_2021_12 | 2020-10-03 00:00:00 | 2021-12-31 00:00:00 | 455.0000 | 5.3981 | 2.8788 | 2.3473 | -0.2981 |
| 3 | momentum3_event_ensemble | 100.0000 | stress_2020_10_to_2021_12 | 2020-10-03 00:00:00 | 2021-12-31 00:00:00 | 455.0000 | 4.3619 | 2.2680 | 2.0917 | -0.3133 |

## Yearly returns

| year_end | 2bps | 20bps | 50bps | 100bps |
| --- | --- | --- | --- | --- |
| 2022-12-31 00:00:00 | -0.2754 | -0.2886 | -0.3101 | -0.3446 |
| 2023-12-31 00:00:00 | 1.9332 | 1.5756 | 1.0728 | 0.4409 |
| 2024-12-31 00:00:00 | 2.8756 | 2.4554 | 1.8528 | 1.0705 |
| 2025-12-31 00:00:00 | 0.8176 | 0.6868 | 0.4888 | 0.2081 |
| 2026-12-31 00:00:00 | 0.9313 | 0.8439 | 0.7067 | 0.4996 |

## External evidence

- Han, Kang, Ryu, *Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market*:
  cross-sectional momentum is weak after realistic costs, while time-series momentum
  is stronger and profits concentrate in large winners.
  <https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>
- Yang, *Cryptocurrency market risk-managed momentum strategies*: volatility scaling
  improved crypto momentum returns and Sharpe.
  <https://doi.org/10.1016/j.frl.2025.107879>
- Alpha Architect, *Destabilizing Rebalancing*: reviewing more often is not the same as
  trading more often; no-trade bands reduce unnecessary turnover.
  <https://alphaarchitect.com/destabilizing-rebalancing>
- Man Group, *In Crypto We Trend*: volatility scaling can reduce pressure-period turnover
  while preserving trend exposure.
  <https://www.man.com/insights/in-crypto-we-trend>
- Grobys et al., *Cryptocurrency momentum has (not) its moments*: large-cap momentum
  can crash severely, and volatility management helps mitigate the crash risk.
  <https://osuva.uwasa.fi/bitstream/handle/10024/20018/Osuva_Grobys_Kolari_Sandretto_Shahzad_%C3%84ij%C3%B6_2025.pdf?sequence=2>

## Guardrails

- The event-spec parameters were selected after a broad research sweep. The high
  full-sample return is therefore not proof of a stable live edge.
- The neighboring-spec table is mandatory: if only one exact parameter survives,
  the candidate remains research-only.
- The 100bps cost column is a stress test, not the user's expected cost.
- Capacity, exchange outage, delisting, and regime-change risks remain.
