# Pre-2022 proxy-mark stress (2020-10-03 → 2022-01-01)

Goal: close the coverage caveat of §12.8.9 — the Bitget-only run dropped 199 target rows
to cash, so "no liquidation" covered only 32 contracts.  This run splices Binance 1-hour
spot candles (proxy mark path) in front of each contract's first Bitget mark hour, or uses
the proxy alone when Bitget has no row.  It is a kill-criterion stress, not performance.

## Coverage upgrade

- coins with a usable path: **63**, loaded as 64 series (matic-network and polygon-ecosystem-token share the POLUSDT file): bitget-only 14, spliced 18, proxy-only 31; still no data: 39
- splice seams: 18, median |basis| 0.502%, worst 2.040%
- carried marks: 65 hourly bars, max carry 3h (engine `carry` policy, max 3h)

## Matrix (zero funding, 20 bps, +3h fills)

| index | leverage | assets | dropped_target_rows | liquidations | max_gross | multiple | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1.2500 | 64.0000 | 0.0000 | 0.0000 | 0.9532 | 4.2956 | 2.0754 | -0.2776 |
| 1 | 1.5000 | 64.0000 | 0.0000 | 0.0000 | 1.1372 | 5.2757 | 2.0600 | -0.3286 |
| 2 | 2.0000 | 64.0000 | 0.0000 | 0.0000 | 1.5230 | 7.3930 | 2.0291 | -0.4252 |

## Per-leg adverse excursion vs the -51.01% liquidation distance

| index | price_source | legs | worst_mae | median_mae |
| --- | --- | --- | --- | --- |
| 0 | bitget | 15.0000 | -0.2650 | -0.1284 |
| 1 | proxy | 28.0000 | -0.4435 | -0.1943 |
| 2 | spliced | 2.0000 | -0.3656 | -0.2582 |

By Bitget tradability (synthetic-symbol coins were never listed on Bitget):

| index | bitget_listed | legs | worst_mae | median_mae |
| --- | --- | --- | --- | --- |
| 0 | 0.0000 | 3.0000 | -0.2817 | -0.1347 |
| 1 | 1.0000 | 42.0000 | -0.4435 | -0.1787 |

Worst legs:

| index | asset | price_source | entry_time | exit_time | max_adverse_excursion | liquidation_distance |
| --- | --- | --- | --- | --- | --- | --- |
| 19 | dogecoin | proxy | 2021-01-30 03:00:00+00:00 | 2021-03-03 03:00:00+00:00 | -0.4435 | -0.5101 |
| 30 | dogecoin | proxy | 2021-04-16 03:00:00+00:00 | 2021-05-14 03:00:00+00:00 | -0.4164 | -0.5101 |
| 35 | avalanche-2 | proxy | 2021-08-25 03:00:00+00:00 | 2021-09-11 03:00:00+00:00 | -0.3965 | -0.5101 |
| 42 | shiba-inu | spliced | 2021-10-07 03:00:00+00:00 | 2021-11-28 03:00:00+00:00 | -0.3656 | -0.5101 |
| 5 | stellar | proxy | 2020-12-22 03:00:00+00:00 | 2020-12-24 03:00:00+00:00 | -0.3172 | -0.5101 |
| 10 | maker | proxy | 2021-01-10 03:00:00+00:00 | 2021-01-11 03:00:00+00:00 | -0.2817 | -0.5101 |
| 36 | algorand | proxy | 2021-09-17 03:00:00+00:00 | 2021-09-27 03:00:00+00:00 | -0.2772 | -0.5101 |
| 13 | stellar | proxy | 2021-01-09 03:00:00+00:00 | 2021-01-17 03:00:00+00:00 | -0.2743 | -0.5101 |

## Bitget-only baseline for comparison (§12.8.9)

| index | leverage | available_mark_assets | dropped_target_rows | liquidation_count | multiple | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 1.2500 | 32.0000 | 199.0000 | 0.0000 | 0.9694 | -0.2062 |
| 1 | 1.5000 | 32.0000 | 199.0000 | 0.0000 | 0.9525 | -0.2465 |
| 2 | 2.0000 | 32.0000 | 199.0000 | 0.0000 | 0.9087 | -0.3254 |

## Reading

- Zero liquidations across all leverage levels on 64 series; worst leg MAE -44.35% vs liquidation distance -51.01% — headroom 6.66pp.
- The worst legs (DOGE Jan/Feb 2021) are proxy-priced; their drawdown is a real Binance
  path, but the venue that would have liquidated is Bitget, so this remains a modelled
  stress, not a measured Bitget mark event.
- 3 of 45 legs sit on coins Bitget never listed
  (synthetic symbols): the realizable book would have been in cash there, so the proxy run
  deliberately overstates participation to bound liquidation risk.
- Residual limits: coins that did not exist in the window cannot appear; funding is zero;
  the proxy is a competitor's spot tape.  The gate stays *partial-with-bounding*.
