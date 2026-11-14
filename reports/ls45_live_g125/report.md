# Derivatives Shadow OOS Tracker — PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21

- window: 2026-09-22 00:00:00+00:00 → 2026-11-13 00:00:00+00:00 (53 daily rows; 52 metric returns)
- research only: yes; live execution: **no**
- frozen long/short book: H5 1.25x + LS45 stronger-21D profit-lock redistribution/regime short
- cost: 20 bps; capital reference: 1,000 units
- execution: 01:05 UTC; price model mark_1h_open_floor
- target ledger: oos_targets.csv; sha256 e7049b2dda6bc7e6338939cb7d763e09341eb71d6845f54b91c12587b4dfc871
- funding: bitget-exact (complete for the OOS window)
- last mark: 2026-11-14 13:00:00+00:00; staleness: 1.2h
- warmup history: data/raw/bitget_derivatives/merged_20261009
- warmup provenance: sha256:77bff92b77750c483bc63041fa2b72d31f576dfaf006d167d91d9ce81121d0ad; 87 mark files; 28371 missing hours; 26265 gaps (26265 two-hour); max gap 2.0h
- mark coverage: 0 missing hours; 88 assets checked; 0 gaps (0 two-hour); max gap 1.0h
- execution-bar audit: 72/72 target pairs resolved; 0 missing

## OOS metrics

| spec | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- |
| PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21 | 0.9385 | -0.3650 | -0.5415 | -0.1932 |

## Execution and risk counters

| spec | max_target_gross | max_observed_gross | gross_breach_hours | short_opens | short_stops | liquidations | funding_total | fees_total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21 | 0.7768 | 0.8163 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -2.0320 | 6.2422 |

## Latest target book

- signal date: 2026-11-13 00:00:00+00:00

| asset | side | target_weight | target_notional_per_1k | change_weight | change_notional_per_1k | action | execution_hint |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bitcoin-cash | short | -0.0625 | -62.5000 | -0.0625 | -62.5000 | OPEN | 2026-11-14 01:05:00+00:00 |
| hyperliquid | short | -0.0625 | -62.5000 | -0.0625 | -62.5000 | OPEN | 2026-11-14 01:05:00+00:00 |
| near | short | -0.0625 | -62.5000 | -0.0625 | -62.5000 | OPEN | 2026-11-14 01:05:00+00:00 |
| zcash | short | -0.0625 | -62.5000 | -0.0625 | -62.5000 | OPEN | 2026-11-14 01:05:00+00:00 |

The first daily row is the engine initialization point and is excluded from Sharpe/volatility; it remains in `oos_daily.csv`.

Research output only; not an order or a live approval.
