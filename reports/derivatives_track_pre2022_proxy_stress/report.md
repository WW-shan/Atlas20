# Pre-2022 proxy-mark stress (2020-10-03 → 2022-01-01)

Goal: close the coverage caveat of §12.8.9 — the Bitget-only run dropped 199 target rows
to cash, so "no liquidation" covered only 32 contracts.  This run splices Binance 1-hour
spot candles (proxy mark path) in front of each contract's first Bitget mark hour, or uses
the proxy alone when Bitget has no row.  It is a kill-criterion stress, not performance.

## Coverage upgrade

- coins with a usable path: **61** (bitget-only 14, spliced 18, proxy-only 29); still no data: 41
- splice seams: 18, median |basis| 0.502%, worst 2.040%
- carried marks: 62 hourly bars, max carry 3h (engine `carry` policy, max 3h)

## Matrix (zero funding, 20 bps, +3h fills)

| index | leverage | assets | dropped_target_rows | liquidations | max_gross | multiple | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1.2500 | 55.0000 | 52.0000 | 0.0000 | 0.9532 | 2.8117 | 1.6824 | -0.2754 |
| 1 | 1.5000 | 55.0000 | 52.0000 | 0.0000 | 1.1372 | 3.2153 | 1.6641 | -0.3264 |
| 2 | 2.0000 | 55.0000 | 52.0000 | 0.0000 | 1.5230 | 3.9544 | 1.6275 | -0.4272 |

## Per-leg adverse excursion vs the -51.01% liquidation distance

| index | price_source | legs | worst_mae | median_mae |
| --- | --- | --- | --- | --- |
| 0 | bitget | 15.0000 | -0.2650 | -0.1284 |
| 1 | proxy | 19.0000 | -0.4435 | -0.2136 |
| 2 | spliced | 2.0000 | -0.3656 | -0.2582 |

Worst legs:

| index | asset | price_source | entry_time | exit_time | max_adverse_excursion | liquidation_distance |
| --- | --- | --- | --- | --- | --- | --- |
| 16 | dogecoin | proxy | 2021-01-30 03:00:00+00:00 | 2021-03-03 03:00:00+00:00 | -0.4435 | -0.5101 |
| 25 | dogecoin | proxy | 2021-04-16 03:00:00+00:00 | 2021-05-14 03:00:00+00:00 | -0.4164 | -0.5101 |
| 27 | avalanche-2 | proxy | 2021-08-25 03:00:00+00:00 | 2021-09-11 03:00:00+00:00 | -0.3965 | -0.5101 |
| 34 | shiba-inu | spliced | 2021-10-07 03:00:00+00:00 | 2021-11-28 03:00:00+00:00 | -0.3656 | -0.5101 |
| 4 | stellar | proxy | 2020-12-22 03:00:00+00:00 | 2020-12-24 03:00:00+00:00 | -0.3172 | -0.5101 |
| 28 | algorand | proxy | 2021-09-17 03:00:00+00:00 | 2021-09-27 03:00:00+00:00 | -0.2772 | -0.5101 |
| 10 | stellar | proxy | 2021-01-09 03:00:00+00:00 | 2021-01-17 03:00:00+00:00 | -0.2743 | -0.5101 |
| 18 | chiliz | proxy | 2021-03-13 03:00:00+00:00 | 2021-03-14 03:00:00+00:00 | -0.2660 | -0.5101 |

## Bitget-only baseline for comparison (§12.8.9)

| index | leverage | available_mark_assets | dropped_target_rows | liquidation_count | multiple | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 1.2500 | 32.0000 | 199.0000 | 0.0000 | 0.9694 | -0.2062 |
| 1 | 1.5000 | 32.0000 | 199.0000 | 0.0000 | 0.9525 | -0.2465 |
| 2 | 2.0000 | 32.0000 | 199.0000 | 0.0000 | 0.9087 | -0.3254 |

## Reading

- Zero liquidations across all leverage levels on 61 assets; worst leg MAE -44.35% vs liquidation distance -51.01% — headroom 6.66pp.
- The worst legs (DOGE Jan/Feb 2021) are proxy-priced; their drawdown is a real Binance
  path, but the venue that would have liquidated is Bitget, so this remains a modelled
  stress, not a measured Bitget mark event.
- Residual limits: 41 coins simply did not exist in the window; funding is zero; proxy is a
  competitor's spot tape.  The gate stays *partial-with-bounding* rather than fully closed.
