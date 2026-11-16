# Derivatives Shadow OOS Tracker — PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090

- window: 2026-09-22 00:00:00+00:00 → 2026-11-15 00:00:00+00:00 (55 daily rows; 55 metric returns)
- research only: yes; live execution: **no**
- frozen long/short book: H5 1.25x + LS45 stronger-21D profit-lock redistribution/regime short
- execution profile: short_scale 2x, gross cap 1.75x, margin cap 90%, venue leverage 4x
- cost: 20 bps; capital reference: 1,000 units
- execution: 01:05 UTC; price model market_1h_open_floor
- scheduled fills: bitget_market_1h_open across 88 asset(s); downgrades 0
- engine end: 2026-11-16 01:05:01+00:00 (includes the final T+1 execution; daily metrics end 2026-11-15)
- target ledger: oos_targets.csv; sha256 2ef4e701d29376ec0073bd589424dbcf30525914f7eb587459de88a263863930
- funding: bitget-exact (complete for the OOS window)
- last mark: 2026-11-16 16:00:00+00:00; staleness: 1.2h
- warmup history: data/raw/bitget_derivatives/merged_20261009
- warmup provenance: sha256:d5f571ce686a2dd62b96f4c9e155ff03c2039dd4d4d7c79b7b46fd0f1dcb1e3b; 87 mark files; 0 missing hours; 0 gaps (0 two-hour); max gap 1.0h
- mark coverage: 0 missing hours; 88 assets checked; 0 gaps (0 two-hour); max gap 1.0h
- execution-bar audit: 72/72 target pairs resolved; 0 missing

## OOS metrics

| spec | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- |
| PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21 | 0.9885 | -0.0737 | 0.1402 | -0.1930 |

## Execution and risk counters

| spec | max_target_gross | max_observed_gross | gross_breach_hours | short_opens | short_stop_exits | liquidations | funding_total | fees_total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21 | 0.7768 | 0.8163 | 0.0000 | 4.0000 | 0.0000 | 0.0000 | -2.0668 | 6.7190 |

## Latest target book

- signal date: 2026-11-13 00:00:00+00:00

| asset | side | target_weight | target_notional_per_1k | change_weight | change_notional_per_1k | action | execution_hint |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bitcoin-cash | short | -0.1250 | -125.0000 | -0.1250 | -125.0000 | OPEN | 2026-11-14 01:05:00+00:00 |
| hyperliquid | short | -0.1250 | -125.0000 | -0.1250 | -125.0000 | OPEN | 2026-11-14 01:05:00+00:00 |
| near | short | -0.1250 | -125.0000 | -0.1250 | -125.0000 | OPEN | 2026-11-14 01:05:00+00:00 |
| zcash | short | -0.1250 | -125.0000 | -0.1250 | -125.0000 | OPEN | 2026-11-14 01:05:00+00:00 |

The first daily row is measured against the engine's initial capital; it is included in the reported metrics.

Research output only; not an order or a live approval.
