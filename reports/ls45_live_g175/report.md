# Derivatives Shadow OOS Tracker — PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090

- window: 2026-09-22 00:00:00+00:00 → 2026-11-24 00:00:00+00:00 (64 daily rows; 64 metric returns)
- research only: yes; live execution: **no**
- frozen long/short book: H5 1.25x + LS45 stronger-21D profit-lock redistribution/regime short
- execution profile: short_scale 2x, gross cap 1.75x, margin cap 90%, venue leverage 4x
- cost: 20 bps; capital reference: 1,000 units
- execution: 01:05 UTC; price model market_1h_open_floor
- scheduled fills: bitget_market_1h_open across 102 asset(s); downgrades 0
- engine end: 2026-11-25 01:05:01+00:00 (includes the final T+1 execution; daily metrics end 2026-11-24)
- target ledger: oos_targets.csv; sha256 e04b17f3f82071f6b272616b14407348486f73e14dd40e67673bf7d2e26dd1dc
- funding: bitget-exact (complete for the OOS window)
- last mark: 2026-11-24 23:00:00+00:00; staleness: 1.7h
- warmup history: data/raw/bitget_derivatives/merged_20261009
- warmup provenance: sha256:42c89558ab364cd031533deb7b30b693d44eb6ce306a8a63dbe735c2a630a2f0; 95 mark files; 0 missing hours; 0 gaps (0 two-hour); max gap 1.0h
- mark coverage: 0 missing hours; 102 assets checked; 0 gaps (0 two-hour); max gap 1.0h
- execution-bar audit: 78/78 target pairs resolved; 0 missing

## OOS metrics

| spec | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- |
| PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21 | 1.0322 | 0.1978 | 0.6071 | -0.1930 |

## Execution and risk counters

| spec | max_target_gross | max_observed_gross | gross_breach_hours | short_opens | short_stop_exits | liquidations | funding_total | fees_total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21 | 0.7768 | 0.8163 | 0.0000 | 6.0000 | 0.0000 | 0.0000 | -2.1407 | 7.2283 |

## Latest target book

- signal date: 2026-11-20 00:00:00+00:00

| asset | side | target_weight | target_notional_per_1k | change_weight | change_notional_per_1k | action | execution_hint |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bitcoin-cash | short | -0.1250 | -125.0000 | 0.0000 | 0.0000 | HOLD | 2026-11-21 01:05:00+00:00 |
| ethereum | short | -0.1250 | -125.0000 | -0.1250 | -125.0000 | OPEN | 2026-11-21 01:05:00+00:00 |
| hyperliquid | flat | 0.0000 | 0.0000 | 0.1250 | 125.0000 | CLOSE | 2026-11-21 01:05:00+00:00 |
| near | flat | 0.0000 | 0.0000 | 0.1250 | 125.0000 | CLOSE | 2026-11-21 01:05:00+00:00 |
| uniswap | short | -0.1250 | -125.0000 | -0.1250 | -125.0000 | OPEN | 2026-11-21 01:05:00+00:00 |
| zcash | short | -0.1250 | -125.0000 | 0.0000 | 0.0000 | HOLD | 2026-11-21 01:05:00+00:00 |

The first daily row is measured against the engine's initial capital; it is included in the reported metrics.

Research output only; not an order or a live approval.
