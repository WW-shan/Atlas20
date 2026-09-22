# Daily Own-Trend Stop Validation

## Question

The fixed 21-day strategy already checks the BTC market gate every day. This study asks
whether daily monitoring of the *selected coin's own trend* can improve the strategy
without turning the leader selection into a noisy daily rotation.

## Rule

- Point-in-time Top-20, exclude BTC, CTREND-breakout top-1 on a 21-day calendar.
- Monitor the holding against its own moving average every day.
- After a confirmed close below the moving average, sell to cash.
- Re-enter only on the next scheduled selection date when the base strategy still
  chooses that coin and it is back above the trend filter.
- Keep the BTC 11-day trailing gate with two-day confirmation.
- No leverage and no shorting; T+1 execution.

## External evidence

- Han et al. find stronger evidence for time-series momentum than cross-sectional
  momentum once realistic costs and daily fluctuations are included.
  <https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>
- Kaya and Mostowfi find that a simple stop-loss rule materially reduces downside risk
  and improves Sharpe for concentrated crypto portfolios.
  <https://doi.org/10.1016/j.frl.2021.102422>
- Yang finds risk-managed crypto momentum improves returns and Sharpe after costs.
  <https://doi.org/10.1016/j.frl.2025.107879>

## Results

| index | variant_id | full_multiple_2bps | full_multiple_20bps | full_cagr_20bps | full_sharpe_20bps | full_max_drawdown_20bps | full_annualized_turnover | rolling_1y_median_multiple | rolling_1y_worst_multiple | rolling20_median_multiple | rolling20_worst_multiple |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 17 | ma75_confirm3 | 25.8685 | 22.4353 | 0.9320 | 1.3134 | -0.4399 | 16.7256 | 1.5989 | 0.6221 | 3.5128 | 0.5853 |
| 16 | ma75_confirm2 | 25.6004 | 22.2028 | 0.9278 | 1.3151 | -0.4399 | 16.7256 | 1.5989 | 0.6221 | 3.5128 | 0.6336 |
| 15 | ma75_confirm1 | 25.1841 | 21.8419 | 0.9211 | 1.3099 | -0.4436 | 16.7256 | 1.5969 | 0.6179 |  |  |
| 9 | ma50_confirm1 | 25.2501 | 21.8203 | 0.9207 | 1.3039 | -0.4328 | 17.1491 | 1.5507 | 0.6309 |  |  |
| 12 | ma60_confirm1 | 25.0445 | 21.6426 | 0.9174 | 1.3069 | -0.4436 | 17.1491 | 1.5969 | 0.6179 |  |  |
| 10 | ma50_confirm2 | 24.8370 | 21.4632 | 0.9140 | 1.2984 | -0.4399 | 17.1491 | 1.5471 | 0.6221 |  |  |
| 14 | ma60_confirm3 | 24.9236 | 21.4606 | 0.9140 | 1.2984 | -0.4399 | 17.5725 | 1.5471 | 0.6221 |  |  |
| 7 | ma40_confirm2 | 24.8867 | 21.4289 | 0.9134 | 1.2976 | -0.4408 | 17.5725 | 1.5471 | 0.6150 |  |  |
| 13 | ma60_confirm2 | 24.6371 | 21.2905 | 0.9107 | 1.3008 | -0.4399 | 17.1491 | 1.5507 | 0.6221 |  |  |
| 3 | ma30_confirm1 | 24.5964 | 21.1790 | 0.9086 | 1.2968 | -0.4929 | 17.5725 | 1.5471 | 0.6881 |  |  |
| 4 | ma30_confirm2 | 24.4137 | 21.0216 | 0.9056 | 1.2919 | -0.4570 | 17.5725 | 1.5471 | 0.6287 |  |  |
| 2 | ma20_confirm3 | 22.9907 | 19.7964 | 0.8815 | 1.2756 | -0.4570 | 17.5725 | 1.4768 | 0.6417 |  |  |
| 6 | ma40_confirm1 | 22.3249 | 19.2231 | 0.8699 | 1.2635 | -0.4917 | 17.5725 | 1.5507 | 0.6214 |  |  |
| 22 | ma150_confirm2 | 21.5115 | 18.8596 | 0.8623 | 1.2903 | -0.4792 | 15.4553 | 1.5989 | 0.6221 |  |  |
| 23 | ma150_confirm3 | 21.5010 | 18.8503 | 0.8621 | 1.2901 | -0.4792 | 15.4553 | 1.5989 | 0.6221 |  |  |
| 8 | ma40_confirm3 | 21.5635 | 18.5674 | 0.8562 | 1.2491 | -0.5154 | 17.5725 | 1.5471 | 0.5227 |  |  |
| 11 | ma50_confirm3 | 21.5635 | 18.5674 | 0.8562 | 1.2491 | -0.5154 | 17.5725 | 1.5471 | 0.5227 |  |  |
| 20 | ma100_confirm3 | 20.4826 | 17.8928 | 0.8417 | 1.2708 | -0.4792 | 15.8788 | 1.5989 | 0.6221 |  |  |
| 18 | ma100_confirm1 | 20.1013 | 17.5597 | 0.8344 | 1.2646 | -0.4792 | 15.8788 | 1.5989 | 0.6221 |  |  |
| 5 | ma30_confirm3 | 20.2455 | 17.4325 | 0.8315 | 1.2289 | -0.5154 | 17.5725 | 1.5471 | 0.5227 |  |  |
| 19 | ma100_confirm2 | 19.8139 | 17.3087 | 0.8288 | 1.2597 | -0.4792 | 15.8788 | 1.5989 | 0.6221 |  |  |
| 1 | ma20_confirm2 | 15.0623 | 13.0164 | 0.7217 | 1.1550 | -0.4929 | 17.1491 | 1.4412 | 0.7361 |  |  |
| 21 | ma150_confirm1 | 13.5487 | 11.8784 | 0.6887 | 1.1482 | -0.4792 | 15.4553 | 1.4545 | 0.6221 |  |  |
| 24 | ma200_confirm1 | 11.1788 | 9.8715 | 0.6238 | 1.0999 | -0.5526 | 14.6085 | 1.6166 | 0.5684 | 2.4511 | 0.6248 |
| 25 | ma200_confirm2 | 9.5519 | 8.4046 | 0.5694 | 1.0393 | -0.6059 | 15.0319 | 1.4233 | 0.4949 |  |  |
| 0 | ma20_confirm1 | 9.4833 | 8.1953 | 0.5610 | 1.0232 | -0.4142 | 17.1491 | 1.1330 | 0.7531 |  |  |
| 26 | ma200_confirm3 | 8.9626 | 7.8860 | 0.5484 | 1.0140 | -0.6428 | 15.0319 | 1.4233 | 0.4486 |  |  |

## BTC benchmark at 2bps

- Multiple: 1.82x
- CAGR: 13.46%
- Sharpe: 0.502
- Max drawdown: -66.90%

## Selected candidate yearly returns (2bps)

| index | year | strategy | btc |
| --- | --- | --- | --- |
| 0 | 2,022.0000 | -0.0585 | -0.6531 |
| 1 | 2,023.0000 | 0.6667 | 1.5542 |
| 2 | 2,024.0000 | 3.4722 | 1.2105 |
| 3 | 2,025.0000 | 0.4272 | -0.0634 |
| 4 | 2,026.0000 | 1.5828 | -0.0104 |

## Guardrail

A daily stop is useful only if it improves the rolling-start distribution and cost
survival, not merely the fixed 2022-start multiple. The parameter neighborhood and
out-of-sample subperiods are therefore part of the decision.
