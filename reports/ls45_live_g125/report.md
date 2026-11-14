# Derivatives Shadow OOS Tracker — PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21

- window: 2026-09-22 00:00:00+00:00 → 2026-11-13 00:00:00+00:00 (53 daily rows; 52 metric returns)
- research only: yes; live execution: **no**
- frozen long/short book: H5 1.25x + LS45 stronger-21D profit-lock redistribution/regime short
- cost: 20 bps; capital reference: 1,000 units
- execution: 01:05 UTC; price model mark_1h_open_floor
- funding: bitget-exact (available through 2026-11-11 16:00:00+00:00; stale shorts flattened)
- last mark: 2026-11-14 00:00:00+00:00; staleness: 1.2h
- warmup history: data/raw/bitget_derivatives/merged_20261009
- mark coverage: 0 missing hours; 88 assets checked; max gap 1.0h

## OOS metrics

| spec | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- |
| PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21 | 0.9385 | -0.3650 | -0.5415 | -0.1932 |

## Execution and risk counters

| spec | max_target_gross | max_observed_gross | gross_breach_hours | short_opens | short_stops | liquidations | funding_total | fees_total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21 | 0.7768 | 0.8163 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -2.0320 | 6.2422 |

## Latest target book

- signal date: 2026-11-06 00:00:00+00:00

| asset | side | target_weight | target_notional_per_1k | change_weight | change_notional_per_1k | action | execution_hint |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hyperliquid | flat | 0.0000 | 0.0000 | -0.1042 | -104.1667 | CLOSE | 2026-11-07 01:05:00+00:00 |
| monero | flat | 0.0000 | 0.0000 | -0.4688 | -468.7500 | CLOSE | 2026-11-07 01:05:00+00:00 |
| near | flat | 0.0000 | 0.0000 | -0.0299 | -29.9343 | CLOSE | 2026-11-07 01:05:00+00:00 |

The first daily row is the engine initialization point and is excluded from Sharpe/volatility; it remains in `oos_daily.csv`.

Research output only; not an order or a live approval.
