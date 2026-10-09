# Phase-Momentum Market Regime Breakdown

The bull/non-bull split uses the project regime frame from `config/base.yaml`:
- BTC 120D moving-average state
- tracked total market-cap 120D moving-average state
- combine method: `all`

Each day's return is labelled with the regime known at the previous close;
the same-day state would already contain that day's return.

Bull days: 806; non-bull days: 918.

## Summary

| index | strategy | regime | days | total_multiple | annualized_return | annualized_volatility | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | L125-zero | bull | 806.0000 | 39.7337 | 4.2989 | 0.7420 | 2.6029 | -0.4072 |
| 1 | L125-zero | non_bull | 918.0000 | 1.1105 | 0.0426 | 0.1904 | 0.3126 | -0.2409 |
| 2 | L125-zero-funding-universe | bull | 806.0000 | 34.0512 | 3.9412 | 0.7304 | 2.5372 | -0.4072 |
| 3 | L125-zero-funding-universe | non_bull | 918.0000 | 1.1236 | 0.0474 | 0.1904 | 0.3371 | -0.2409 |
| 4 | L125-binance-proxy | bull | 806.0000 | 31.0858 | 3.7415 | 0.7299 | 2.4818 | -0.4065 |
| 5 | L125-binance-proxy | non_bull | 918.0000 | 1.1218 | 0.0468 | 0.1904 | 0.3338 | -0.2399 |
| 6 | L125-binance-long-adverse-3x | bull | 806.0000 | 22.8511 | 3.1246 | 0.7290 | 2.2922 | -0.4249 |
| 7 | L125-binance-long-adverse-3x | non_bull | 918.0000 | 1.1002 | 0.0387 | 0.1904 | 0.2931 | -0.2452 |
| 8 | L200-zero | bull | 806.0000 | 186.7349 | 9.6791 | 1.1371 | 2.6131 | -0.5395 |
| 9 | L200-zero | non_bull | 918.0000 | 1.1255 | 0.0481 | 0.3073 | 0.3033 | -0.3720 |
| 10 | BTC | bull | 806.0000 | 3.0599 | 0.6594 | 0.4528 | 1.3433 | -0.2693 |
| 11 | BTC | non_bull | 918.0000 | 0.5727 | -0.1988 | 0.5504 | -0.1257 | -0.6212 |

This is a diagnostic slice of the same saved production returns. It does
not select a new parameter and it does not repair capacity, execution, or
data-quality risks.
