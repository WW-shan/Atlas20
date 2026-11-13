# PR2026-11-LS98-CROSS-VENUE-BASIS

LS98 is a research proxy for a long-spot / short-perp BTC/ETH basis sleeve. It is not a
live signal and does not prove same-venue Bitget execution.

- Common sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily observations)
- Per asset: spot long 0.50x NAV + perp short 0.50x NAV; total gross 1.00x
- Primary cost: 10bps per leg per side; 5/20bps shown as a band
- Funding is a Binance proxy; perp mark is Bitget; spot is a CMC/Binance daily proxy

## Variant summary

| index | variant | cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | mean_gross | turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | always-on | 5.0000 | 1.3378 | 2.0925 | -0.0250 | 1.2146 | 2.8538 | 1.0000 | 2.0000 |
| 1 | always-on | 10.0000 | 1.3365 | 2.0850 | -0.0250 | 1.2140 | 2.8458 | 1.0000 | 2.0000 |
| 2 | always-on | 20.0000 | 1.3338 | 2.0692 | -0.0250 | 1.2128 | 2.8284 | 1.0000 | 2.0000 |
| 3 | positive-funding | 5.0000 | 1.3212 | 2.3128 | -0.0164 | 1.2044 | 2.8273 | 0.8762 | 34.0000 |
| 4 | positive-funding | 10.0000 | 1.2990 | 2.1626 | -0.0185 | 1.1942 | 2.6840 | 0.8762 | 34.0000 |
| 5 | positive-funding | 20.0000 | 1.2555 | 1.8557 | -0.0261 | 1.1741 | 2.3889 | 0.8762 | 34.0000 |
| 6 | btc-only | 5.0000 | 1.1672 | 2.6047 | -0.0065 | 1.1027 | 3.3358 | 0.5000 | 1.0000 |
| 7 | btc-only | 10.0000 | 1.1666 | 2.5957 | -0.0065 | 1.1024 | 3.3265 | 0.5000 | 1.0000 |
| 8 | btc-only | 20.0000 | 1.1654 | 2.5766 | -0.0065 | 1.1019 | 3.3058 | 0.5000 | 1.0000 |
| 9 | eth-only | 5.0000 | 1.1471 | 1.4981 | -0.0246 | 1.1019 | 2.2433 | 0.5000 | 1.0000 |
| 10 | eth-only | 10.0000 | 1.1465 | 1.4925 | -0.0246 | 1.1016 | 2.2371 | 0.5000 | 1.0000 |
| 11 | eth-only | 20.0000 | 1.1454 | 1.4809 | -0.0246 | 1.1011 | 2.2240 | 0.5000 | 1.0000 |

## Yearly returns

| index | year | return | net_pnl |
| --- | --- | --- | --- |
| 0 | 2,022.0000 | 0.0192 | 0.0201 |
| 1 | 2,023.0000 | 0.0801 | 0.0772 |
| 2 | 2,024.0000 | 0.1339 | 0.1259 |
| 3 | 2,025.0000 | 0.0524 | 0.0513 |
| 4 | 2,026.0000 | 0.0174 | 0.0176 |

## Asset attribution (always-on, 10bps)

| index | asset | basis_pnl | funding_pnl | costs | net_pnl |
| --- | --- | --- | --- | --- | --- |
| 0 | bitcoin | -0.0006 | 0.1561 | 0.0010 | 0.1545 |
| 1 | ethereum | -0.0026 | 0.1412 | 0.0010 | 0.1377 |

## Evidence classification

**funding-dominated**

The label is a research diagnostic. It does not promote the sleeve or change the live track.
A positive result only earns a same-venue spot/perp data and execution study.

Research output only; no orders sent.
