# PR2026-11-LS101-LS57-SAME-VENUE-BASIS

LS101 integrates the LS100 Bitget same-venue price proxy into LS57 residual gross.
Full-history funding remains a Binance proxy and exact Bitget funding is only a recent
reconciliation window. It is a research result, not a live signal.

- Sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily observations)
- LS57 baseline: 68.8077x / Sharpe 1.9819 / MDD -39.8350%
- LS100 sleeve actual gross: 1.00x; combined hard cap: 1.45x
- LS100 has no position on 2022-01-01; its first complete return is 2022-01-02
- Costs are charged on LS100 scale entry, changes and final exit at 10bps or 20bps per leg per side

## Results

| index | allocation | basis_cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | mean_combined_gross | max_combined_gross | mean_scale | scale_change_days | total_scale_cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0.2500 | 10.0000 | 71.2144 | 1.9960 | -0.3973 | 15.5923 | 2.1235 | 0.6610 | 1.4500 | 0.2489 | 45.0000 | 0.0019 |
| 1 | 0.5000 | 10.0000 | 72.7796 | 2.0050 | -0.3982 | 15.8314 | 2.1341 | 0.8937 | 1.4500 | 0.4817 | 132.0000 | 0.0146 |
| 2 | 1.0000 | 10.0000 | 73.7400 | 2.0110 | -0.3995 | 15.9684 | 2.1406 | 1.2971 | 1.4500 | 0.8851 | 387.0000 | 0.0605 |
| 3 | 0.2500 | 20.0000 | 71.0777 | 1.9952 | -0.3977 | 15.5790 | 2.1230 | 0.6610 | 1.4500 | 0.2489 | 45.0000 | 0.0039 |
| 4 | 0.5000 | 20.0000 | 71.7329 | 1.9992 | -0.4008 | 15.7047 | 2.1288 | 0.8937 | 1.4500 | 0.4817 | 132.0000 | 0.0292 |
| 5 | 1.0000 | 20.0000 | 69.4617 | 1.9873 | -0.4053 | 15.3762 | 2.1159 | 1.2971 | 1.4500 | 0.8851 | 387.0000 | 0.1209 |

## Decision

**PASS (research integration only; not live approval)**

A pass only earns same-venue execution, funding settlement, margin and small-order
research. It does not change `PR2026-10-D-L125-V2`.

Research output only; no orders sent.
