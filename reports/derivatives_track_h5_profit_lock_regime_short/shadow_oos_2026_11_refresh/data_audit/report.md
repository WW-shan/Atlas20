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

- `mark`: 88/88 windows complete (100.0%), 0 partial, max observed gap 1h

## Funding overlap

- Bitget funding files present: 88/88
- Contracts with overlap rows: 48
- Contracts passing all overlap gates: 0/88

| coin_id | bitget_symbol | overlap | sign | pearson | median bps | p95 bps |
|---|---|---:|---:|---:|---:|---:|
| kaspa | KASUSDT | 289 | 0.972 | nan | 0.000 | 0.164 |
| world-liberty-financial | WLFIUSDT | 289 | 0.889 | 0.009 | 0.000 | 0.868 |
| immutable-x | IMXUSDT | 289 | 0.934 | 0.603 | 0.000 | 0.625 |
| hyperliquid | HYPEUSDT | 289 | 0.747 | 0.621 | 0.122 | 0.892 |
| the-open-network | GRAMUSDT | 289 | 0.931 | 0.441 | 0.000 | 0.731 |
| celestia | TIAUSDT | 289 | 0.782 | 0.058 | 0.005 | 0.883 |
| canton-network | CCUSDT | 289 | 0.907 | 0.794 | 0.000 | 1.003 |
| bittensor | TAOUSDT | 289 | 0.862 | 0.032 | 0.000 | 0.948 |
| ethena | ENAUSDT | 289 | 0.768 | 0.002 | 0.000 | 1.153 |
| axie-infinity | AXSUSDT | 289 | 0.958 | 0.028 | 0.000 | 0.401 |
| render-token | RENDERUSDT | 289 | 0.903 | 0.436 | 0.000 | 0.748 |
| bitcoin | BTCUSDT | 144 | 0.896 | 0.207 | 0.253 | 0.866 |
| binancecoin | BNBUSDT | 144 | 0.583 | 0.325 | 0.638 | 1.000 |
| terra-luna | LUNCUSDT | 144 | 0.924 | -0.043 | 0.000 | 1.427 |
| hedera-hashgraph | HBARUSDT | 144 | 0.868 | 0.255 | 0.266 | 1.195 |
| apecoin | APEUSDT | 144 | 0.854 | 0.164 | 0.000 | 1.896 |
| algorand | ALGOUSDT | 144 | 0.826 | 0.280 | 0.000 | 1.790 |
| injective-protocol | INJUSDT | 144 | 0.771 | 0.701 | 0.306 | 2.933 |
| internet-computer | ICPUSDT | 144 | 0.882 | 0.344 | 0.000 | 1.287 |
| sui | SUIUSDT | 144 | 0.778 | 0.368 | 0.281 | 1.329 |
| lido-dao | LDOUSDT | 144 | 0.826 | 0.035 | 0.000 | 1.376 |
| litecoin | LTCUSDT | 144 | 0.896 | 0.350 | 0.137 | 1.165 |
| matic-network | POLUSDT | 144 | 0.812 | nan | 0.500 | 1.680 |
| monero | XMRUSDT | 144 | 1.000 | 0.857 | 0.000 | 4.120 |
| stellar | XLMUSDT | 144 | 0.910 | 0.805 | 0.000 | 1.008 |
| near | NEARUSDT | 144 | 0.812 | 0.190 | 0.041 | 1.443 |
| solana | SOLUSDT | 144 | 0.660 | 0.536 | 0.326 | 1.124 |
| optimism | OPUSDT | 144 | 0.715 | 0.237 | 0.120 | 2.050 |
| shiba-inu | SHIBUSDT | 144 | 0.854 | 0.646 | 0.000 | 1.533 |
| pepe | PEPEUSDT | 144 | 0.840 | 0.552 | 0.089 | 1.911 |
