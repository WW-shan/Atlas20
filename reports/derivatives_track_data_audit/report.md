# Bitget Derivatives Data Audit

- PIT Top20 coin ids in symbol map: 102
- Mapped to Bitget USDT-M: 88
- Missing Bitget contracts: 14

## Missing contracts

| coin_id | panel_symbol | reason |
|---|---|---|
| eos | EOS | no Bitget USDT-M perpetual |
| flow | FLOW | no Bitget USDT-M perpetual |
| ftx-token | FTT | no Bitget USDT-M perpetual |
| helium | HNT | no Bitget USDT-M perpetual |
| htx-dao | HTX | no Bitget USDT-M perpetual |
| huobi-token | HT | no Bitget USDT-M perpetual |
| kucoin-shares | KCS | no Bitget USDT-M perpetual |
| leo-token | LEO | no Bitget USDT-M perpetual |
| maker | MKR | no Bitget USDT-M perpetual |
| mantle | MNT | no Bitget USDT-M perpetual |
| okb | OKB | no Bitget USDT-M perpetual |
| osmosis | OSMO | no Bitget USDT-M perpetual |
| waves | WAVES | no Bitget USDT-M perpetual |
| yearn-finance | YFI | no Bitget USDT-M perpetual |

## Candle coverage

- `mark`: 6/6 windows complete (100.0%), max observed gap 2h

## Funding overlap

- Bitget funding files present: 3/88
- Contracts with overlap rows: 3
- Contracts passing all overlap gates: 0/3

| coin_id | bitget_symbol | overlap | sign | pearson | median bps | p95 bps |
|---|---|---:|---:|---:|---:|---:|
| bitcoin | BTCUSDT | 245 | 0.853 | 0.250 | 0.274 | 0.947 |
| near | NEARUSDT | 245 | 0.829 | 0.273 | 0.050 | 1.421 |
| solana | SOLUSDT | 245 | 0.694 | 0.505 | 0.378 | 1.121 |
