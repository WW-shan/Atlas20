# Phase-Momentum Market Regime Breakdown

The bull/non-bull split uses the project regime frame from `config/base.yaml`:
- BTC 120D moving-average state
- tracked total market-cap 120D moving-average state
- combine method: `all`

Each day's return is labelled with the regime known at the previous close;
the same-day state would already contain that day's return.

Bull days: 807; non-bull days: 918.

## Summary

| index | strategy | regime | days | total_multiple | annualized_return | annualized_volatility | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | primary | bull | 807.0000 | 25.3661 | 3.3165 | 0.8061 | 2.1996 | -0.4020 |
| 1 | primary | non_bull | 918.0000 | 0.9102 | -0.0367 | 0.2024 | -0.0826 | -0.2895 |
| 2 | h3_breadth_050 | bull | 807.0000 | 22.0367 | 3.0504 | 0.7308 | 2.2653 | -0.3787 |
| 3 | h3_breadth_050 | non_bull | 918.0000 | 1.0224 | 0.0088 | 0.1666 | 0.1361 | -0.2324 |
| 4 | h5_disp_p75 | bull | 807.0000 | 20.0534 | 2.8812 | 0.6217 | 2.4832 | -0.3775 |
| 5 | h5_disp_p75 | non_bull | 918.0000 | 1.0707 | 0.0275 | 0.1508 | 0.2546 | -0.1965 |
| 6 | BTC | bull | 807.0000 | 3.2658 | 0.7079 | 0.4546 | 1.4031 | -0.2693 |
| 7 | BTC | non_bull | 918.0000 | 0.5727 | -0.1988 | 0.5504 | -0.1257 | -0.6212 |

This is a diagnostic slice of the same saved production returns. It does
not select a new parameter and it does not repair capacity, execution, or
data-quality risks.
