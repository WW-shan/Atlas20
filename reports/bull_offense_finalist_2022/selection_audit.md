# Finalist selection and universe audit

- Window: 2022-01-01 .. 2026-09-19
- Weekly rebalances replayed: 247
- BTC gate open on 123 of them (49.8%); flat otherwise
- Picks outside that date's Top-N: 0

## Independent point-in-time ranking check

The ranking was rebuilt straight from the cached CoinMarketCap payload (`data/raw/coinmarketcap/history`) and compared with the universe the strategy used. Same eligibility gates (price, dollar volume, history) are applied to both sides so the comparison isolates the market-cap ranking itself.

- Dates compared: 247
- Identical membership: 247 / 247
- Identical order: 247 / 247
- Market-cap value mismatches beyond 1e-6 relative: 0
- Members absent from the raw cache: 0

## Recent rebalances

| rebalance_date | btc_gate_open | picked_symbol | pipeline_rank | independent_rank | target_vol_exposure |
| --- | --- | --- | --- | --- | --- |
| 2026-07-04 | 0.0000 |  |  |  | 0.0000 |
| 2026-07-11 | 0.0000 |  |  |  | 0.0000 |
| 2026-07-18 | 1.0000 | ZEC | 9.0000 | 9.0000 | 0.8290 |
| 2026-07-25 | 1.0000 | ETH | 2.0000 | 2.0000 | 1.0000 |
| 2026-08-01 | 0.0000 |  |  |  | 0.0000 |
| 2026-08-08 | 1.0000 | XMR | 10.0000 | 10.0000 | 1.0000 |
| 2026-08-15 | 0.0000 |  |  |  | 0.0000 |
| 2026-08-22 | 1.0000 | ZEC | 9.0000 | 9.0000 | 0.6580 |
| 2026-08-29 | 1.0000 | ZEC | 9.0000 | 9.0000 | 0.6459 |
| 2026-09-05 | 1.0000 | ZEC | 8.0000 | 8.0000 | 0.5957 |
| 2026-09-12 | 1.0000 | ZEC | 8.0000 | 8.0000 | 0.4966 |
| 2026-09-19 | 1.0000 | ZEC | 7.0000 | 7.0000 | 0.4484 |

## How often each coin was picked

| symbol | picks |
| --- | --- |
| ZEC | 13.0000 |
| SOL | 8.0000 |
| BCH | 8.0000 |
| XLM | 8.0000 |
| DOGE | 7.0000 |
| HYPE | 7.0000 |
| ICP | 6.0000 |
| SUI | 6.0000 |
| XRP | 5.0000 |
| SHIB | 5.0000 |
| OKB | 4.0000 |
| AVAX | 4.0000 |
| HBAR | 4.0000 |
| NEAR | 3.0000 |
| ETC | 3.0000 |
| BTC | 3.0000 |
| LINK | 3.0000 |
| KAS | 3.0000 |
| PEPE | 3.0000 |
| TAO | 3.0000 |
| GRAM | 2.0000 |
| APT | 2.0000 |
| UNI | 2.0000 |
| ETH | 2.0000 |
| XMR | 2.0000 |
| LUNC | 1.0000 |
| MKR | 1.0000 |
| IMX | 1.0000 |
| TRX | 1.0000 |
| BGB | 1.0000 |
| MNT | 1.0000 |
| WLFI | 1.0000 |

Full per-date trace (including the entire Top-N on every date) is in `selections.csv`; the per-date universe comparison is in `universe_audit.csv`.
