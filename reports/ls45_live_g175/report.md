# Derivatives Shadow OOS Tracker — PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090

- window: 2026-09-22 00:00:00+00:00 → 2026-11-27 00:00:00+00:00 (67 daily rows; 67 metric returns)
- research only: yes; live execution: **no**
- frozen long/short book: H5 1.25x + LS45 stronger-21D profit-lock redistribution/regime short
- execution profile: short_scale 2x, gross cap 1.75x, margin cap 90%, venue leverage 4x
- cost: 20 bps; capital reference: 1,000 units
- execution: 01:05 UTC; price model market_1h_open_floor
- scheduled fills: bitget_market_1h_open across 102 asset(s); downgrades 0
- engine end: 2026-11-28 01:05:01+00:00 (includes the final T+1 execution; daily metrics end 2026-11-27)
- target ledger: oos_targets.csv; sha256 ea13cf9259083d8e3d3fb31ea0a91dce2472b348af318f38d555d6f4447da33e
- funding: bitget-exact (complete for the OOS window)
- last mark: 2026-11-27 23:00:00+00:00; staleness: 2.9h
- warmup history: data/raw/bitget_derivatives/merged_20261009
- warmup provenance: sha256:3a3c631139e0e96906becdf4c9c7da1526694e783a79075823cb578b127ab813; 96 mark files; 0 missing hours; 0 gaps (0 two-hour); max gap 1.0h
- mark coverage: 0 missing hours; 102 assets checked; 0 gaps (0 two-hour); max gap 1.0h
- execution-bar audit: 78/82 target pairs resolved; 0 missing

## OOS metrics

| spec | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- |
| PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21 | 1.0250 | 0.1437 | 0.5197 | -0.1930 |

## Execution and risk counters

| spec | max_target_gross | max_observed_gross | gross_breach_hours | short_opens | short_stop_exits | liquidations | funding_total | fees_total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21 | 0.7768 | 0.8163 | 0.0000 | 6.0000 | 0.0000 | 0.0000 | -2.0825 | 7.7571 |

## Latest target book

- signal date: 2026-11-27 00:00:00+00:00

| asset | side | target_weight | target_notional_per_1k | change_weight | change_notional_per_1k | action | execution_hint |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bitcoin-cash | flat | 0.0000 | 0.0000 | 0.1250 | 125.0000 | CLOSE | 2026-11-28 01:05:00+00:00 |
| ethereum | flat | 0.0000 | 0.0000 | 0.1250 | 125.0000 | CLOSE | 2026-11-28 01:05:00+00:00 |
| uniswap | flat | 0.0000 | 0.0000 | 0.1250 | 125.0000 | CLOSE | 2026-11-28 01:05:00+00:00 |
| zcash | flat | 0.0000 | 0.0000 | 0.1250 | 125.0000 | CLOSE | 2026-11-28 01:05:00+00:00 |

The first daily row is measured against the engine's initial capital; it is included in the reported metrics.

Research output only; not an order or a live approval.
