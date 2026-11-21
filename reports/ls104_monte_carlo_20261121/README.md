# LS104 conditional Monte Carlo path audit — 2026-11-21

This directory preserves the full-sample inputs and the reproducible path audit
that were used after the 2026-11-21 live-chain incident.  It is a **conditional**
diagnostic on an already-produced live-parity path.  It is not new OOS, not a
parameter search, and not a live-promotion decision.

## Reproduction provenance

The two LS104 files were rebuilt from the same command family that produced the
2026-11-15 candidate report:

- signal trial: `PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21`
- execution profile: `short_scale=2.0`, `max_total_gross=1.75`,
  `max_margin_utilization=0.90`, `venue_leverage=4.0`
- fills: Bitget market 1H open floor at 01:05 UTC
- capital: 1,000 reference / 500 engine
- contract quantization: frozen Bitget symbol map
- funding: Binance proxy with missing policy `skip`
- window: 2022-01-01 → 2026-09-21 UTC

The original 2026-11-15 report describes the same family as Bitget-exact
funding.  The exact Bitget funding cache only starts in 2026-07, so a full-sample
exact rerun correctly fails at the first historical held asset.  The Binance
proxy is therefore used here to reproduce the historical path, with `skip`
explicitly recorded; this is weaker funding evidence than exact Bitget history
and is not silently treated as equivalent.

## Reproduced full-sample metrics

| cost | terminal | CAGR | Sharpe | MDD | max observed gross | gross breaches | liquidations |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 bps | 77.9520x | 151.36% | 1.9621 | -40.52% | 1.4980x | 0 | 1 |
| 50 bps | 41.4935x | 119.97% | 1.7155 | -46.49% | 1.4958x | 0 | 1 |

These are essentially identical to the recorded 2026-11-15 results in
`reports/ls104_g175_m090_20261115/README.md` (77.8524x / 1.9637 / -40.77% and
41.4492x / 1.7174 / -46.55%).  The small differences are from the current raw
tree and the explicitly labelled proxy funding input, not from a changed
strategy or execution profile.

## Monte Carlo result

Command:

```sh
.venv/bin/python scripts/audit_derivatives_monte_carlo.py \
  --returns reports/ls104_monte_carlo_20261121/ls104_20bps_daily.csv \
  --benchmark-returns reports/ls104_monte_carlo_20261121/btc_buy_and_hold_daily.csv \
  --output-dir reports/ls104_monte_carlo_20261121/audit \
  --draws 10000 --block-lengths 5,20,40,80 --seed 20261121
```

- stationary circular block bootstrap, 10,000 paths per block length
- block lengths: 5 / 20 / 40 / 80 days
- paired BTC buy-and-hold uses the same resampled daily indices

| block | terminal p01 | p05 | p50 | p95 | p99 | P(<1x) | P(<2x) | Sharpe p05 | P(Sharpe<0) | MDD p05 | P(MDD<-50%) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 4.254x | 9.91x | 74.42x | 660.6x | 1628x | 0.00% | 0.09% | 1.208 | 0.00% | -55.98% | 12.84% |
| 20 | 3.531x | 8.222x | 75.06x | 852.7x | 2592x | 0.02% | 0.29% | 1.141 | 0.00% | -58.02% | 15.09% |
| 40 | 3.307x | 7.892x | 75.02x | 887.4x | 2768x | 0.03% | 0.31% | 1.133 | 0.01% | -56.41% | 13.88% |
| 80 | 3.663x | 8.506x | 74.72x | 755.8x | 2048x | 0.01% | 0.13% | 1.149 | 0.00% | -54.87% | 11.35% |

Paired versus BTC:

| block | observed terminal ratio | p05 | p50 | p95 | P(ratio<1) |
|---:|---:|---:|---:|---:|---:|
| 5 | 41.68x | 3.086x | 41.58x | 636.1x | 0.90% |
| 20 | 41.68x | 3.506x | 42.54x | 558.6x | 0.69% |
| 40 | 41.68x | 3.829x | 42.32x | 521.6x | 0.53% |
| 80 | 41.68x | 3.678x | 42.54x | 470x | 0.38% |

## What the audit says

- The central path distribution is strong across all four block lengths; the
  median terminal multiple is about 74–75x and the median Sharpe is about 1.95.
- The **left-tail drawdown risk is material**: 11–15% of resampled paths exceed
  a 50% drawdown, and the 5th-percentile MDD is roughly -55% to -58%.  The
  single observed -40.52% path understates this conditional tail.
- `P(terminal < 1x)` is only 0–0.03%, so the sample does not support a claim of
  near-certain ruin, but a bootstrap is not a guarantee and is not an OOS test.
- Against BTC, the paired lower-tail is still positive: the 5th-percentile
  terminal ratio is about 3.1–3.8x, with `P(ratio < 1)` below 1%.  This measures
  path ordering conditional on the realized return distribution, not future
  alpha.

## Limitations

- The input is one realized path.  Resampling it does not correct selection bias,
  multiple testing or the fact that the strategy was chosen on the same history.
- Blocks preserve short-range serial dependence but destroy multi-month regime
  structure and event clustering.
- Binance funding is a proxy for the historical full sample; exact Bitget funding
  is only available from 2026-07 in the current raw tree.
- The 2025-02-03 XRP liquidation is inherited from the path and appears in both
  20bps and 50bps runs.  The bootstrap does not simulate a new liquidation engine.
- The live track still has no completed 12-month independent OOS.  This audit is
  not a substitute for that requirement.

## Files

- `ls104_20bps_daily.csv`, `ls104_50bps_daily.csv`: reproduced full-sample daily returns.
- `btc_buy_and_hold_daily.csv`: aligned BTC buy-and-hold daily returns.
- `audit/summary.json`: complete quantiles and paired statistics.
- `audit/report.md`: human-readable audit.
- `audit/paths_block_*.csv`: every simulated path metric for reproducibility.
