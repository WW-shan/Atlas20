# PIT Top20 membership event diagnostic

- status: event study only; no strategy, no orders, no live changes
- entry: coin has been continuously in PIT Top20 for m days
- exit: coin has been continuously outside PIT Top20 for m days; only after it was previously a member
- forward return starts at next close; horizons 7/14/28/56 trading days
- cell means require at least 3 same-day events; events are equally weighted within a day

## Summary

| index | confirmation_days | event_type | horizon_days | sample | event_count | event_day_count | mean_raw_return | mean_btc_excess | mean_top20_excess | positive_btc_share | positive_top20_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 3.0000 | exit | 7.0000 | discovery | 70.0000 | 1.0000 | -0.0602 | 0.0462 | 0.0073 | 0.4000 | 0.4429 |
| 1 | 3.0000 | exit | 14.0000 | discovery | 70.0000 | 1.0000 | -0.0775 | 0.1593 | 0.0685 | 0.2571 | 0.3571 |
| 2 | 3.0000 | exit | 28.0000 | discovery | 70.0000 | 1.0000 | -0.1050 | 0.0711 | 0.1019 | 0.2143 | 0.3571 |
| 3 | 3.0000 | exit | 56.0000 | discovery | 70.0000 | 1.0000 | -0.1386 | 0.1817 | 0.1921 | 0.2857 | 0.3714 |

## Verdict

**rejected**

- no m/h cell has stable entry-positive and exit-negative BTC excess

## Guardrail

This diagnostic does not establish a tradeable strategy. It ignores costs, funding, execution, capacity and overlapping event risk.
