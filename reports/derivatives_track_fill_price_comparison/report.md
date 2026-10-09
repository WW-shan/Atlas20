# Execution-price sensitivity: mark vs market fills

- mark matrix: `reports/derivatives_track_bitget_mark_zero/bitget_mark_matrix.csv`
- market matrix: `reports/derivatives_track_bitget_market_fills/bitget_mark_matrix.csv`
- worst market/mark terminal-multiple ratio: **1.002**
- median ratio: 1.002
- max-drawdown deterioration (worst row): -0.00%

| index | scenario | leverage | multiple_mark | multiple_market | multiple_ratio | sharpe_mark | sharpe_market | sharpe_delta | max_drawdown_mark | max_drawdown_market | mdd_delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | zero | 1.2500 | 44.1253 | 44.1971 | 1.0016 | 1.7691 | 1.7698 | 0.0007 | -0.4072 | -0.4072 | -0.0000 |
| 1 | zero | 1.5000 | 80.0840 | 80.2480 | 1.0020 | 1.7680 | 1.7688 | 0.0008 | -0.4688 | -0.4688 | 0.0000 |
| 2 | zero | 2.0000 | 210.1750 | 210.7938 | 1.0029 | 1.7704 | 1.7712 | 0.0008 | -0.5395 | -0.5396 | -0.0000 |
