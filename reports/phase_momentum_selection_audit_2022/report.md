# Phase-Momentum Selection Audit

Every check uses the point-in-time Top20 snapshot the strategy ranked from and
the provider's own print for the day (a carried, forward-filled price counts
as missing):

- every non-empty sleeve selection is in that date's snapshot, has a print, and
  is not Rain, a configured stablecoin (`universe.stablecoin_ids`) or a
  configured excluded id (`universe.excluded_ids`);
- every evaluated date has a snapshot of exactly 20 coins;
- on each sleeve's scheduled check the asset it holds ranks within the hold rank;
- every positive weight of every traded aggregate target is in that date's
  snapshot and has a print.

Result: PASS: every violation count is zero.

## Summary

| check | count |
| --- | --- |
| selection_rows | 10308 |
| violations | 0 |
| missing_price_rows | 0 |
| outside_top20_rows | 0 |
| rain_rows | 0 |
| stablecoin_rows | 0 |
| excluded_id_rows | 0 |
| dates_evaluated | 1725 |
| dates_without_snapshot | 0 |
| dates_with_wrong_size | 0 |
| max_universe_size | 20 |
| min_universe_size | 20 |
| hold_rule_checked_rows | 3436 |
| hold_rule_violations | 0 |
| traded_rows | 990 |
| traded_outside_top20 | 0 |
| traded_without_price | 0 |

## Selection violations

| index | signal_date | signal_name | phase_offset | selected_asset | selected_rank | in_point_in_time_top20 | has_price | snapshot_size | is_rain | is_stablecoin | is_excluded_id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Snapshot violations

| index | date | universe_size | has_snapshot | wrong_size |
| --- | --- | --- | --- | --- |

## Hold-rule violations

| index | signal_date | signal_name | phase_offset | selected_asset | selected_rank | hold_rule_ok |
| --- | --- | --- | --- | --- | --- | --- |

## Traded-target violations

| index | target_date | asset | weight | in_point_in_time_top20 | has_price |
| --- | --- | --- | --- | --- | --- |
