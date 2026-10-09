# Execution-price sensitivity: mark vs market fills

- mark matrix: `reports/derivatives_track_bitget_mark_funding_stress_median/bitget_mark_matrix.csv`
- market matrix: `reports/derivatives_track_bitget_market_fills_funding/bitget_mark_matrix.csv`
- worst market/mark terminal-multiple ratio: **1.001**
- median ratio: 1.002
- max-drawdown deterioration (worst row): -0.00%

| index | scenario | leverage | multiple_mark | multiple_market | multiple_ratio | sharpe_mark | sharpe_market | sharpe_delta | max_drawdown_mark | max_drawdown_market | mdd_delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | binance-long-adverse-2x | 1.2500 | 28.2662 | 28.3079 | 1.0015 | 1.6089 | 1.6097 | 0.0007 | -0.4191 | -0.4191 | -0.0000 |
| 4 | binance-long-adverse-2x | 1.5000 | 47.3107 | 47.3996 | 1.0019 | 1.6080 | 1.6088 | 0.0008 | -0.4816 | -0.4816 | 0.0000 |
| 7 | binance-long-adverse-2x | 2.0000 | 107.5114 | 107.8080 | 1.0028 | 1.6103 | 1.6111 | 0.0008 | -0.5533 | -0.5534 | -0.0000 |
| 2 | binance-long-adverse-3x | 1.2500 | 24.2902 | 24.3265 | 1.0015 | 1.5480 | 1.5487 | 0.0007 | -0.4249 | -0.4249 | -0.0000 |
| 5 | binance-long-adverse-3x | 1.5000 | 39.4566 | 39.5319 | 1.0019 | 1.5469 | 1.5476 | 0.0008 | -0.4879 | -0.4878 | 0.0000 |
| 8 | binance-long-adverse-3x | 2.0000 | 84.8876 | 85.1254 | 1.0028 | 1.5483 | 1.5491 | 0.0008 | -0.5601 | -0.5601 | -0.0000 |
| 0 | binance-proxy | 1.2500 | 34.4766 | 34.5264 | 1.0014 | 1.6889 | 1.6896 | 0.0007 | -0.4065 | -0.4065 | -0.0000 |
| 3 | binance-proxy | 1.5000 | 60.0154 | 60.1260 | 1.0018 | 1.6883 | 1.6890 | 0.0008 | -0.4681 | -0.4681 | 0.0000 |
| 6 | binance-proxy | 2.0000 | 146.5672 | 146.9634 | 1.0027 | 1.6917 | 1.6925 | 0.0008 | -0.5387 | -0.5387 | -0.0000 |
