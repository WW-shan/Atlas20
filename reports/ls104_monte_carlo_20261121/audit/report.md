# Atlas20 derivatives conditional Monte Carlo path audit

> Conditional stationary-block bootstrap of already-produced daily returns.
> This is not a new OOS run, not a parameter choice, and not a guarantee of future returns.

- source: `ls104_20bps_daily.csv`
- sample: 2022-01-01 00:00:00+00:00 → 2026-09-21 00:00:00+00:00 (1725 daily returns)
- primary draws: 10000 per block length
- block lengths (days): 5, 20, 40, 80
- seed: 20261121
- observed terminal multiple: 77.952x
- observed Sharpe: 1.9621
- observed maximum drawdown: -40.5217%

## Path distribution

| block | terminal p01 | p05 | p50 | p95 | p99 | P(<1x) | P(<2x) | Sharpe p05 | Sharpe p50 | P(Sharpe<0) | MDD p05 | MDD p50 | P(MDD<-50%) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 4.254x | 9.91x | 74.42x | 660.6x | 1628x | 0.00% | 0.09% | 1.208 | 1.950 | 0.00% | -55.98% | -38.64% | 12.84% |
| 20 | 3.531x | 8.222x | 75.06x | 852.7x | 2592x | 0.02% | 0.29% | 1.141 | 1.958 | 0.00% | -58.02% | -39.50% | 15.09% |
| 40 | 3.307x | 7.892x | 75.02x | 887.4x | 2768x | 0.03% | 0.31% | 1.133 | 1.949 | 0.01% | -56.41% | -39.33% | 13.88% |
| 80 | 3.663x | 8.506x | 74.72x | 755.8x | 2048x | 0.01% | 0.13% | 1.149 | 1.949 | 0.00% | -54.87% | -38.86% | 11.35% |

## Paired benchmark

- benchmark: `btc_buy_and_hold_daily.csv`; same resampled daily indices as the candidate

| block | observed ratio | p05 | p50 | p95 | P(ratio<1) |
|---:|---:|---:|---:|---:|---:|
| 5 | 41.68x | 3.086x | 41.58x | 636.1x | 0.90% |
| 20 | 41.68x | 3.506x | 42.54x | 558.6x | 0.69% |
| 40 | 41.68x | 3.829x | 42.32x | 521.6x | 0.53% |
| 80 | 41.68x | 3.678x | 42.54x | 470x | 0.38% |

## Interpretation limits

- Blocks preserve short-range autocorrelation but destroy longer calendar regimes and event clustering.
- The input is a single realized path; bootstrap uncertainty is not selection-bias correction.
- Four block lengths (5/20/40/80) probe short-range dependence; they are not a complete model of regime shifts.
- A terminal below 1x in the tail is a path-risk warning, not a claim that the live account will hit it.
