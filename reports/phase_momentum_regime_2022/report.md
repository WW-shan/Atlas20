# Phase-Momentum Market Regime Breakdown

The bull/non-bull split uses the project regime frame from `config/base.yaml`:
- BTC 120D moving-average state
- tracked total market-cap 120D moving-average state
- combine method: `all`

Bull days: 809; non-bull days: 916.

## Summary

| index | strategy | regime | days | total_multiple | annualized_return | annualized_volatility | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | primary | bull | 809.0000 | 51.8331 | 4.9373 | 0.8003 | 2.6091 | -0.3983 |
| 1 | primary | non_bull | 916.0000 | 0.4454 | -0.2755 | 0.2113 | -1.4141 | -0.5597 |
| 2 | parameter_ensemble_20bps | bull | 809.0000 | 40.4135 | 4.3067 | 0.7695 | 2.5391 | -0.3934 |
| 3 | parameter_ensemble_20bps | non_bull | 916.0000 | 0.3951 | -0.3093 | 0.1972 | -1.7719 | -0.6059 |
| 4 | BTC | bull | 809.0000 | 13.6472 | 2.2516 | 0.4593 | 2.7979 | -0.2029 |
| 5 | BTC | non_bull | 916.0000 | 0.1370 | -0.5470 | 0.5433 | -1.1824 | -0.8795 |

This is a diagnostic slice of the same saved production returns. It does
not select a new parameter and it does not repair capacity, execution, or
data-quality risks.
