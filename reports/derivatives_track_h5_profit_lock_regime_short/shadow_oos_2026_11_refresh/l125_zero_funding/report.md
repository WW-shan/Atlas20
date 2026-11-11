# Derivatives Shadow OOS Tracker — PR2026-10-D-L125

- window: 2026-09-22 00:00:00+00:00 → 2026-11-10 00:00:00+00:00 (50 daily rows; 49 metric returns)
- research only: yes; live execution: **no**
- frozen long/short book: H5 1.25x baseline
- cost: 20 bps; capital reference: 1,000 units
- funding: zero (explicit upper bound; no funding charged)
- last mark: 2026-11-11 18:00:00+00:00; staleness: 1.6h
- warmup history: data/raw/bitget_derivatives/merged_20261009
- mark coverage: 0 missing hours; 88 assets checked; max gap 1.0h

## OOS metrics

| spec | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- |
| PR2026-10-D-L125 | 0.9484 | -0.3317 | -0.2771 | -0.1747 |

## Execution and risk counters

| spec | max_target_gross | max_observed_gross | gross_breach_hours | short_opens | short_stops | liquidations | funding_total | fees_total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PR2026-10-D-L125 | 0.7768 | 0.8149 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0117 |

## Latest target book

- signal date: 2026-11-06 00:00:00+00:00

| asset | side | target_weight | target_notional_per_1k | change_weight | change_notional_per_1k | action | execution_hint |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hyperliquid | flat | 0.0000 | 0.0000 | -0.1042 | -104.1667 | CLOSE | 2026-11-07 03:00:00+00:00 |
| monero | flat | 0.0000 | 0.0000 | -0.4688 | -468.7500 | CLOSE | 2026-11-07 03:00:00+00:00 |
| near | flat | 0.0000 | 0.0000 | -0.0299 | -29.9343 | CLOSE | 2026-11-07 03:00:00+00:00 |

The first daily row is the engine initialization point and is excluded from Sharpe/volatility; it remains in `oos_daily.csv`.

Research output only; not an order or a live approval.
