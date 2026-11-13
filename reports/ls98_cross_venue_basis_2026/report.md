# PR2026-11-LS98-CROSS-VENUE-BASIS

LS98 is a research proxy for a long-spot / short-perp BTC/ETH basis sleeve. It is not a
live signal and does not prove same-venue Bitget execution.

- Common sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily observations)
- Per asset: spot long 0.25x NAV + perp short 0.25x NAV; portfolio gross 1.00x
- Primary cost: 10bps per leg per side; 5/20bps shown as a band
- Funding is a Binance proxy; perp mark is Bitget; spot is a CMC/Binance daily proxy
- Gross counts both legs; costs are charged on each leg per side

## Variant summary

| index | variant | cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | mean_gross | turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | always-on | 5.0000 | 1.1567 | 2.0850 | -0.0125 | 1.1021 | 2.8458 | 1.0000 | 1.0000 |
| 1 | always-on | 10.0000 | 1.1555 | 2.0692 | -0.0125 | 1.1015 | 2.8284 | 1.0000 | 1.0000 |
| 2 | always-on | 20.0000 | 1.1532 | 2.0348 | -0.0125 | 1.1004 | 2.7890 | 1.0000 | 1.0000 |
| 3 | positive-funding | 5.0000 | 1.1402 | 2.1626 | -0.0092 | 1.0930 | 2.6840 | 0.8762 | 17.0000 |
| 4 | positive-funding | 10.0000 | 1.1209 | 1.8557 | -0.0131 | 1.0838 | 2.3889 | 0.8762 | 17.0000 |
| 5 | positive-funding | 20.0000 | 1.0834 | 1.2425 | -0.0221 | 1.0655 | 1.7914 | 0.8762 | 17.0000 |
| 6 | btc-only | 5.0000 | 1.0802 | 2.5957 | -0.0033 | 1.0500 | 3.3265 | 0.5000 | 0.5000 |
| 7 | btc-only | 10.0000 | 1.0797 | 2.5766 | -0.0033 | 1.0498 | 3.3058 | 0.5000 | 0.5000 |
| 8 | btc-only | 20.0000 | 1.0786 | 2.5333 | -0.0033 | 1.0492 | 3.2570 | 0.5000 | 0.5000 |
| 9 | eth-only | 5.0000 | 1.0710 | 1.4925 | -0.0123 | 1.0497 | 2.2371 | 0.5000 | 0.5000 |
| 10 | eth-only | 10.0000 | 1.0705 | 1.4809 | -0.0123 | 1.0494 | 2.2240 | 0.5000 | 0.5000 |
| 11 | eth-only | 20.0000 | 1.0694 | 1.4567 | -0.0123 | 1.0489 | 2.1956 | 0.5000 | 0.5000 |

## Yearly returns

| index | year | return | net_pnl |
| --- | --- | --- | --- |
| 0 | 2,022.0000 | 0.0093 | 0.0095 |
| 1 | 2,023.0000 | 0.0393 | 0.0386 |
| 2 | 2,024.0000 | 0.0649 | 0.0630 |
| 3 | 2,025.0000 | 0.0259 | 0.0256 |
| 4 | 2,026.0000 | 0.0082 | 0.0083 |

## Asset attribution (always-on, 10bps)

| index | asset | basis_pnl | funding_pnl | costs | net_pnl |
| --- | --- | --- | --- | --- | --- |
| 0 | bitcoin | -0.0003 | 0.0780 | 0.0010 | 0.0767 |
| 1 | ethereum | -0.0013 | 0.0706 | 0.0010 | 0.0683 |

## Evidence classification

**funding-dominated**

The label is a research diagnostic. It does not promote the sleeve or change the live track.
A positive result only earns a same-venue spot/perp data and execution study.

Research output only; no orders sent.
