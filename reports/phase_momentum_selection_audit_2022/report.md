# Phase-Momentum Selection Audit

Every non-empty selection is checked against the point-in-time Top20 snapshot
used by the strategy. A violation means the selected asset was absent from that
snapshot, had no price, was Rain, or was a stablecoin.

## Summary

| index | selection_rows | violations | missing_price_rows | outside_top20_rows | rain_rows | stablecoin_rows | max_universe_size | min_universe_size |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 10,308.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 20.0000 | 20.0000 |

## Violations

| index | signal_date | signal_name | phase_offset | selected_asset | in_point_in_time_top20 | has_price | snapshot_size | is_rain | is_stablecoin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Universe size

| index | rebalance_date | universe_size |
| --- | --- | --- |
| count | 1725 | 1,725.0000 |
| mean | 2024-05-12 00:00:00 | 20.0000 |
| min | 2022-01-01 00:00:00 | 20.0000 |
| 25% | 2023-03-08 00:00:00 | 20.0000 |
| 50% | 2024-05-12 00:00:00 | 20.0000 |
| 75% | 2025-07-17 00:00:00 | 20.0000 |
| max | 2026-09-21 00:00:00 | 20.0000 |
| std | nan | 0.0000 |
