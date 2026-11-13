# PR2026-11-LS100-SAME-VENUE-BASIS

LS100 is a Bitget same-venue price proxy for a long-spot / short-perp BTC/ETH basis
sleeve. Full-history funding is still a Binance proxy; exact Bitget funding is only
reconciled on the recent overlap. It is not a live signal and sends no orders.

- Sample: 2022-01-02 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1723 usable daily observations)
- Structure: per asset spot 0.25x NAV + perp short 0.25x NAV; portfolio gross 1.00x
- Cost: 10bps per leg per side primary; 20bps stress
- Mark coverage: 100.00%; max staleness 1.00h
- Spot coverage continuous: True
- Exact Bitget funding reconciliation: 2026-07-13 00:00:00+00:00 → 2026-09-20 00:00:00+00:00

## Variant summary

| index | variant | cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | mean_gross | turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | always-on | 10.0000 | 1.1550 | 3.6300 | -0.0082 | 1.0992 | 3.3544 | 1.0000 | 1.0000 |
| 1 | always-on | 20.0000 | 1.1527 | 3.5486 | -0.0082 | 1.0981 | 3.3019 | 1.0000 | 1.0000 |
| 2 | btc-only | 10.0000 | 1.0790 | 4.9221 | -0.0028 | 1.0487 | 4.5405 | 0.5000 | 0.5000 |
| 3 | btc-only | 20.0000 | 1.0779 | 4.7879 | -0.0028 | 1.0481 | 4.4507 | 0.5000 | 0.5000 |
| 4 | eth-only | 10.0000 | 1.0705 | 2.5959 | -0.0071 | 1.0483 | 2.5492 | 0.5000 | 0.5000 |
| 5 | eth-only | 20.0000 | 1.0694 | 2.5451 | -0.0071 | 1.0477 | 2.5146 | 0.5000 | 0.5000 |

## Yearly returns (always-on, 10bps)

| index | year | return | net_pnl |
| --- | --- | --- | --- |
| 0 | 2,022.0000 | 0.0104 | 0.0104 |
| 1 | 2,023.0000 | 0.0399 | 0.0392 |
| 2 | 2,024.0000 | 0.0648 | 0.0628 |
| 3 | 2,025.0000 | 0.0250 | 0.0247 |
| 4 | 2,026.0000 | 0.0072 | 0.0072 |

## Asset attribution (always-on, 10bps)

| index | asset | basis_pnl | funding_pnl | costs | net_pnl |
| --- | --- | --- | --- | --- | --- |
| 0 | bitcoin | -0.0009 | 0.0780 | 0.0010 | 0.0761 |
| 1 | ethereum | -0.0014 | 0.0706 | 0.0010 | 0.0682 |

## Funding reconciliation

| index | asset | proxy_funding_pnl | exact_funding_pnl | relative_difference | match |
| --- | --- | --- | --- | --- | --- |
| 0 | bitcoin | 0.0128 | 0.0101 | 0.2102 | 1.0000 |
| 1 | ethereum | 0.0086 | 0.0112 | 0.2964 | 1.0000 |

## Decision

**PASS (research proxy only; not live approval)**

The exact-Bitget funding window is too short to backfill full history. A pass only
earns a same-venue execution, funding, margin and small-order study; it does not
change `PR2026-10-D-L125-V2`.

Research output only; no orders sent.
