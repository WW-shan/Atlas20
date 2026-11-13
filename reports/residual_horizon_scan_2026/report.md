# PIT Top20 residual momentum horizon / sign scan

- status: factor screen only; no funding; no leverage; no orders
- sample: 2022-01-01 → 2026-11-12
- discovery: 2022-01-01 → 2023-12-31; validation: 2024-01-01 → 2026-09-21
- latest: 2026-09-22 → 2026-11-12 (descriptive only)
- beta: 120D rolling BTC beta, minimum 90 observations
- grid: lookback 63/126/252 x skip 0/21 x direction momentum/reversal = 12

## Discovery-ranked configurations

The table is displayed in discovery-sharpe order only. Validation and latest columns were not used to choose the order or the parameters.

| index | variant_id | full_multiple_20 | full_sharpe_20 | full_mdd_20 | discovery_multiple_20 | discovery_sharpe_20 | validation_multiple_20 | validation_sharpe_20 | latest_multiple_20 | tier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | residual_L126_S21_reversal | 1.3373 | 0.3690 | -0.4625 | 1.6710 | 0.8713 | 0.7717 | -0.2061 | 1.0370 | rejected-now |
| 1 | residual_L252_S0_reversal | 0.6982 | -0.0295 | -0.6413 | 1.4484 | 0.7065 | 0.4624 | -0.8926 | 1.0424 | rejected-now |
| 2 | residual_L252_S21_reversal | 0.8212 | 0.0698 | -0.5585 | 1.1592 | 0.4378 | 0.6809 | -0.4184 | 1.0403 | rejected-now |
| 3 | residual_L63_S21_reversal | 0.8789 | 0.1039 | -0.4526 | 1.0949 | 0.3651 | 0.7889 | -0.2363 | 1.0175 | rejected-now |
| 4 | residual_L126_S0_momentum | 1.0184 | 0.1701 | -0.4384 | 0.9387 | 0.1094 | 1.1648 | 0.3422 | 0.9314 | rejected-now |
| 5 | residual_L63_S0_momentum | 0.5223 | -0.2483 | -0.6001 | 0.8181 | -0.0626 | 0.6930 | -0.3771 | 0.9212 | rejected-now |
| 6 | residual_L63_S0_reversal | 0.8305 | 0.0758 | -0.5062 | 0.7598 | -0.0800 | 1.0233 | 0.1637 | 1.0682 | rejected-now |
| 7 | residual_L126_S0_reversal | 0.4442 | -0.2990 | -0.7296 | 0.6753 | -0.2190 | 0.6208 | -0.4954 | 1.0595 | rejected-now |
| 8 | residual_L63_S21_momentum | 0.5058 | -0.2884 | -0.6231 | 0.5639 | -0.5193 | 0.9261 | 0.0053 | 0.9686 | rejected-now |
| 9 | residual_L252_S21_momentum | 0.5815 | -0.1827 | -0.6834 | 0.5442 | -0.5484 | 1.1252 | 0.2978 | 0.9497 | rejected-now |
| 10 | residual_L252_S0_momentum | 0.6823 | -0.0787 | -0.6505 | 0.4439 | -0.8138 | 1.6184 | 0.7815 | 0.9498 | rejected-now |
| 11 | residual_L126_S21_momentum | 0.3329 | -0.5046 | -0.7570 | 0.3759 | -0.9849 | 0.9324 | 0.0456 | 0.9500 | rejected-now |

## Best discovery variant by sample

Selected by discovery Sharpe only: `residual_L126_S21_reversal`. The 20bps metrics below are shown for transparency; the latest window is far too short to validate the strategy.

| index | sample | days | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | full | 1,777.0000 | 1.3373 | 0.0616 | 0.3690 | -0.4625 |
| 1 | discovery | 730.0000 | 1.6710 | 0.2931 | 0.8713 | -0.4354 |
| 2 | validation | 995.0000 | 0.7717 | -0.0908 | -0.2061 | -0.4625 |
| 3 | latest | 52.0000 | 1.0370 | 0.2971 | 1.2642 | -0.0981 |

## Asset concentration

Every asset contribution is in `asset_contributions.csv`. The ranking table lists the three largest positive and negative full-sample contributions for each variant.

## Interpretation guardrail

This is a monthly dollar-neutral residual-factor screen using daily panel returns and turnover costs. It does not include funding, Bitget fills, queue position, stop-losses or live routing. A label is descriptive evidence, not an order or a permanent ban on later hypotheses. A candidate-for-integration label still requires independent execution, funding and robustness checks before it can affect a live track.
