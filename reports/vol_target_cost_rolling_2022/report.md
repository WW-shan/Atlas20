# Phase-Invariant Volatility-Target Validation

This study keeps CTREND-lite balanced top-1 selection and replaces the
binary BTC gate with a capped volatility-target exposure. Every cycle is
evaluated as an equal-weight basket of all calendar phases, so the result
does not depend on a fixed start date. No leverage is allowed.

## External evidence

- Moreira and Muir, *Volatility-Managed Portfolios*: scaling exposure by
  realized volatility can improve risk-adjusted outcomes.
  <https://doi.org/10.1111/jofi.12467>
- Yang, *Cryptocurrency market risk-managed momentum strategies*:
  volatility scaling improved crypto momentum Sharpe and returns.
  <https://doi.org/10.1016/j.frl.2025.107879>
- Man Group, *In Crypto We Trend*: volatility scaling can reduce
  pressure-period turnover while preserving trend exposure.
  <https://www.man.com/insights/in-crypto-we-trend>

## Top candidates by full-period basket multiple at 20bps

| index | cycle_days | target_volatility | vol_window | stop_mode | gate_mode | cost_bps | basket_multiple | basket_cagr | basket_sharpe | basket_max_drawdown | train_multiple | train_sharpe | test_multiple | test_sharpe | test_max_drawdown | rolling_1y_median_multiple | rolling_1y_worst_multiple | rolling_1y_median_sharpe | rolling_1y_worst_sharpe | rolling_1y_worst_drawdown | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_exposure | phase_median_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21 | 7.0000 | 0.8000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.5908 | 0.4396 | 0.9548 | -0.5028 | 3.1019 | 0.9594 | 1.8024 | 0.9504 | -0.2937 | 1.3246 | 0.6273 | 0.8464 | -1.6397 | -0.5028 | 4.4205 | 0.6451 | 21.9028 | 0.8094 | -0.7610 | 0.3900 | 35.1036 |
| 15 | 7.0000 | 0.7000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.4090 | 0.4296 | 0.9807 | -0.4735 | 2.9762 | 0.9721 | 1.8174 | 1.0017 | -0.2635 | 1.3373 | 0.6474 | 0.8943 | -1.6750 | -0.4735 | 4.2964 | 0.7402 | 18.2185 | 0.8260 | -0.7091 | 0.3654 | 32.9143 |
| 45 | 14.0000 | 0.8000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.1745 | 0.4162 | 1.0043 | -0.4571 | 2.7914 | 0.9682 | 1.8537 | 1.0805 | -0.2331 | 1.3653 | 0.7384 | 0.8683 | -1.4712 | -0.4571 | 4.4826 | 0.9105 | 16.1997 | 0.8169 | -0.7115 | 0.3623 | 19.4144 |
| 39 | 14.0000 | 0.7000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.1056 | 0.4122 | 1.0431 | -0.4247 | 2.7983 | 1.0113 | 1.8245 | 1.1112 | -0.2085 | 1.3865 | 0.7594 | 0.9278 | -1.5000 | -0.4247 | 4.5410 | 1.0603 | 13.9836 | 0.8488 | -0.6646 | 0.3404 | 18.2936 |
| 9 | 7.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.7549 | 0.3911 | 0.9838 | -0.4330 | 2.6917 | 0.9637 | 1.7665 | 1.0257 | -0.2320 | 1.3453 | 0.6676 | 0.9089 | -1.7086 | -0.4330 | 3.8623 | 0.8046 | 14.4316 | 0.8256 | -0.6483 | 0.3328 | 30.0942 |
| 33 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.5652 | 0.3792 | 1.0565 | -0.3853 | 2.6156 | 1.0277 | 1.7454 | 1.1170 | -0.1829 | 1.3621 | 0.7822 | 0.9475 | -1.5328 | -0.3853 | 3.9784 | 1.1967 | 10.8396 | 0.8475 | -0.6172 | 0.3109 | 16.7837 |
| 3 | 7.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 3.9829 | 0.3399 | 0.9840 | -0.3871 | 2.3544 | 0.9451 | 1.6917 | 1.0605 | -0.1975 | 1.3217 | 0.7021 | 0.9202 | -1.7144 | -0.3871 | 3.4686 | 0.8724 | 11.0304 | 0.8413 | -0.5837 | 0.2914 | 26.3772 |
| 27 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 3.9066 | 0.3344 | 1.0692 | -0.3395 | 2.3879 | 1.0456 | 1.6360 | 1.1195 | -0.1598 | 1.3255 | 0.8122 | 0.9740 | -1.5355 | -0.3395 | 3.5197 | 1.3010 | 8.2853 | 0.8223 | -0.5562 | 0.2724 | 14.7501 |

## Top candidates by 2025-2026 test multiple at 20bps

| index | cycle_days | target_volatility | vol_window | stop_mode | gate_mode | cost_bps | basket_multiple | basket_cagr | basket_sharpe | basket_max_drawdown | train_multiple | train_sharpe | test_multiple | test_sharpe | test_max_drawdown | rolling_1y_median_multiple | rolling_1y_worst_multiple | rolling_1y_median_sharpe | rolling_1y_worst_sharpe | rolling_1y_worst_drawdown | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_exposure | phase_median_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 45 | 14.0000 | 0.8000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.1745 | 0.4162 | 1.0043 | -0.4571 | 2.7914 | 0.9682 | 1.8537 | 1.0805 | -0.2331 | 1.3653 | 0.7384 | 0.8683 | -1.4712 | -0.4571 | 4.4826 | 0.9105 | 16.1997 | 0.8169 | -0.7115 | 0.3623 | 19.4144 |
| 39 | 14.0000 | 0.7000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.1056 | 0.4122 | 1.0431 | -0.4247 | 2.7983 | 1.0113 | 1.8245 | 1.1112 | -0.2085 | 1.3865 | 0.7594 | 0.9278 | -1.5000 | -0.4247 | 4.5410 | 1.0603 | 13.9836 | 0.8488 | -0.6646 | 0.3404 | 18.2936 |
| 15 | 7.0000 | 0.7000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.4090 | 0.4296 | 0.9807 | -0.4735 | 2.9762 | 0.9721 | 1.8174 | 1.0017 | -0.2635 | 1.3373 | 0.6474 | 0.8943 | -1.6750 | -0.4735 | 4.2964 | 0.7402 | 18.2185 | 0.8260 | -0.7091 | 0.3654 | 32.9143 |
| 21 | 7.0000 | 0.8000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.5908 | 0.4396 | 0.9548 | -0.5028 | 3.1019 | 0.9594 | 1.8024 | 0.9504 | -0.2937 | 1.3246 | 0.6273 | 0.8464 | -1.6397 | -0.5028 | 4.4205 | 0.6451 | 21.9028 | 0.8094 | -0.7610 | 0.3900 | 35.1036 |
| 9 | 7.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.7549 | 0.3911 | 0.9838 | -0.4330 | 2.6917 | 0.9637 | 1.7665 | 1.0257 | -0.2320 | 1.3453 | 0.6676 | 0.9089 | -1.7086 | -0.4330 | 3.8623 | 0.8046 | 14.4316 | 0.8256 | -0.6483 | 0.3328 | 30.0942 |
| 33 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.5652 | 0.3792 | 1.0565 | -0.3853 | 2.6156 | 1.0277 | 1.7454 | 1.1170 | -0.1829 | 1.3621 | 0.7822 | 0.9475 | -1.5328 | -0.3853 | 3.9784 | 1.1967 | 10.8396 | 0.8475 | -0.6172 | 0.3109 | 16.7837 |
| 3 | 7.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 3.9829 | 0.3399 | 0.9840 | -0.3871 | 2.3544 | 0.9451 | 1.6917 | 1.0605 | -0.1975 | 1.3217 | 0.7021 | 0.9202 | -1.7144 | -0.3871 | 3.4686 | 0.8724 | 11.0304 | 0.8413 | -0.5837 | 0.2914 | 26.3772 |
| 27 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 3.9066 | 0.3344 | 1.0692 | -0.3395 | 2.3879 | 1.0456 | 1.6360 | 1.1195 | -0.1598 | 1.3255 | 0.8122 | 0.9740 | -1.5355 | -0.3395 | 3.5197 | 1.3010 | 8.2853 | 0.8223 | -0.5562 | 0.2724 | 14.7501 |

## Interpretation guardrail

A candidate is not promoted because of one phase or one full-sample
maximum. The basket, train/test split, exposure level, and neighboring
volatility windows must all be economically consistent.
