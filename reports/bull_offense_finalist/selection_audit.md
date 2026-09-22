# Finalist selection and universe audit

- Window: 2021-01-01 .. 2026-09-18
- Weekly rebalances replayed: 299
- BTC gate open on 156 of them (52.2%); flat otherwise
- Picks outside that date's Top-N: 0

## Independent point-in-time ranking check

The ranking was rebuilt straight from the cached CoinMarketCap payload (`data/raw/coinmarketcap/history`) and compared with the universe the strategy used. Same eligibility gates (price, dollar volume, history) are applied to both sides so the comparison isolates the market-cap ranking itself.

- Dates compared: 299
- Identical membership: 299 / 299
- Identical order: 299 / 299
- Market-cap value mismatches beyond 1e-6 relative: 0
- Members absent from the raw cache: 0

## Recent rebalances

| rebalance_date | btc_gate_open | picked_symbol | pipeline_rank | independent_rank | target_vol_exposure |
| --- | --- | --- | --- | --- | --- |
| 2026-07-03 | 0.0000 |  |  |  | 0.0000 |
| 2026-07-10 | 0.0000 |  |  |  | 0.0000 |
| 2026-07-17 | 1.0000 | ZEC | 9.0000 | 9.0000 | 0.8160 |
| 2026-07-24 | 1.0000 | ZEC | 9.0000 | 9.0000 | 0.8792 |
| 2026-07-31 | 0.0000 |  |  |  | 0.0000 |
| 2026-08-07 | 1.0000 | UNI | 20.0000 | 20.0000 | 1.0000 |
| 2026-08-14 | 0.0000 |  |  |  | 0.0000 |
| 2026-08-21 | 1.0000 | ZEC | 9.0000 | 9.0000 | 0.6739 |
| 2026-08-28 | 1.0000 | ZEC | 8.0000 | 8.0000 | 0.6480 |
| 2026-09-04 | 1.0000 | ZEC | 8.0000 | 8.0000 | 0.5928 |
| 2026-09-11 | 1.0000 | ZEC | 8.0000 | 8.0000 | 0.5006 |
| 2026-09-18 | 1.0000 | ZEC | 7.0000 | 7.0000 | 0.4557 |

## How often each coin was picked

| symbol | picks |
| --- | --- |
| DOGE | 13.0000 |
| ZEC | 13.0000 |
| SOL | 9.0000 |
| SHIB | 9.0000 |
| XLM | 8.0000 |
| HYPE | 8.0000 |
| LUNC | 7.0000 |
| AVAX | 7.0000 |
| BCH | 7.0000 |
| SUI | 7.0000 |
| XRP | 6.0000 |
| ICP | 6.0000 |
| LINK | 6.0000 |
| GRAM | 4.0000 |
| PEPE | 4.0000 |
| THETA | 3.0000 |
| ETC | 3.0000 |
| OKB | 3.0000 |
| KAS | 3.0000 |
| UNI | 3.0000 |
| HBAR | 3.0000 |
| BNB | 2.0000 |
| FIL | 2.0000 |
| NEAR | 2.0000 |
| APT | 2.0000 |
| BTC | 2.0000 |
| XMR | 2.0000 |
| SNX | 1.0000 |
| DOT | 1.0000 |
| CHZ | 1.0000 |
| CRO | 1.0000 |
| MATIC | 1.0000 |
| ATOM | 1.0000 |
|  | 1.0000 |
| IMX | 1.0000 |
| TRX | 1.0000 |
| TAO | 1.0000 |
| ETH | 1.0000 |
| MNT | 1.0000 |

Full per-date trace (including the entire Top-N on every date) is in `selections.csv`; the per-date universe comparison is in `universe_audit.csv`.
