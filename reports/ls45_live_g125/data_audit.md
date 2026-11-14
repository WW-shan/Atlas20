# Atlas20 derivatives data audit

- passed: **True**
- fingerprint: `sha256:082b19c79ab9ad2f0bbe4e4ab58f09e211fb9f1ae4d34d1dc8704661009af462`
- hard failures: 0
- warnings: 89

## Hard failures

- none

## Warnings

- panel.valid_market_cap: 32 negative/non-finite market-cap row(s)
- funding.1inch.fresh: funding is stale but no short is required
- funding.aave.fresh: funding is stale but no short is required
- funding.algorand.fresh: funding is stale but no short is required
- funding.apecoin.fresh: funding is stale but no short is required
- funding.aptos.fresh: funding is stale but no short is required
- funding.arbitrum.fresh: funding is stale but no short is required
- funding.aster-2.fresh: funding is stale but no short is required
- funding.avalanche-2.fresh: funding is stale but no short is required
- funding.axie-infinity.fresh: funding is stale but no short is required
- funding.basic-attention-token.fresh: funding is stale but no short is required
- funding.binancecoin.fresh: funding is stale but no short is required
- funding.bitcoin.fresh: funding is stale but no short is required
- funding.bitcoin-cash.fresh: funding is stale but no short is required
- funding.bitget-token.fresh: funding is stale but no short is required
- funding.bittensor.fresh: funding is stale but no short is required
- funding.bitway.fresh: funding is stale but no short is required
- funding.canton-network.fresh: funding is stale but no short is required
- funding.cardano.fresh: funding is stale but no short is required
- funding.celestia.fresh: funding is stale but no short is required
- funding.chainlink.fresh: funding is stale but no short is required
- funding.chiliz.fresh: funding is stale but no short is required
- funding.compound-governance-token.fresh: funding is stale but no short is required
- funding.cosmos.fresh: funding is stale but no short is required
- funding.crypto-com-chain.fresh: funding is stale but no short is required
- funding.curve-dao-token.fresh: funding is stale but no short is required
- funding.decentraland.fresh: funding is stale but no short is required
- funding.dogecoin.fresh: funding is stale but no short is required
- funding.dydx-chain.fresh: funding is stale but no short is required
- funding.elrond-erd-2.fresh: funding is stale but no short is required
- funding.enjincoin.fresh: funding is stale but no short is required
- funding.ethena.fresh: funding is stale but no short is required
- funding.ethereum.fresh: funding is stale but no short is required
- funding.ethereum-classic.fresh: funding is stale but no short is required
- funding.ethereum-name-service.fresh: funding is stale but no short is required
- funding.fantom.fresh: funding is stale but no short is required
- funding.filecoin.fresh: funding is stale but no short is required
- funding.gala.fresh: funding is stale but no short is required
- funding.havven.fresh: funding is stale but no short is required
- funding.hedera-hashgraph.fresh: funding is stale but no short is required
- funding.hyperliquid.fresh: funding is stale but no short is required
- funding.immutable-x.fresh: funding is stale but no short is required
- funding.injective-protocol.fresh: funding is stale but no short is required
- funding.internet-computer.fresh: funding is stale but no short is required
- funding.jupiter-exchange-solana.fresh: funding is stale but no short is required
- funding.kaspa.fresh: funding is stale but no short is required
- funding.lido-dao.fresh: funding is stale but no short is required
- funding.litecoin.fresh: funding is stale but no short is required
- funding.matic-network.fresh: funding is stale but no short is required
- funding.memecore.fresh: funding is stale but no short is required
- funding.monero.fresh: funding is stale but no short is required
- funding.morpho.fresh: funding is stale but no short is required
- funding.near.fresh: funding is stale but no short is required
- funding.neo.fresh: funding is stale but no short is required
- funding.ondo-finance.fresh: funding is stale but no short is required
- funding.optimism.fresh: funding is stale but no short is required
- funding.pancakeswap-token.fresh: funding is stale but no short is required
- funding.pepe.fresh: funding is stale but no short is required
- funding.pi-network.fresh: funding is stale but no short is required
- funding.polkadot.fresh: funding is stale but no short is required
- funding.polygon-ecosystem-token.fresh: funding is stale but no short is required
- funding.pump-fun.fresh: funding is stale but no short is required
- funding.quant-network.fresh: funding is stale but no short is required
- funding.render-token.fresh: funding is stale but no short is required
- funding.ripple.fresh: funding is stale but no short is required
- funding.sei-network.fresh: funding is stale but no short is required
- funding.shiba-inu.fresh: funding is stale but no short is required
- funding.sky.fresh: funding is stale but no short is required
- funding.solana.fresh: funding is stale but no short is required
- funding.stellar.fresh: funding is stale but no short is required
- funding.stepn.fresh: funding is stale but no short is required
- funding.sui.fresh: funding is stale but no short is required
- funding.sushi.fresh: funding is stale but no short is required
- funding.terra-luna.fresh: funding is stale but no short is required
- funding.terra-luna-2.fresh: funding is stale but no short is required
- funding.tezos.fresh: funding is stale but no short is required
- funding.the-graph.fresh: funding is stale but no short is required
- funding.the-open-network.fresh: funding is stale but no short is required
- funding.the-sandbox.fresh: funding is stale but no short is required
- funding.theta-token.fresh: funding is stale but no short is required
- funding.thorchain.fresh: funding is stale but no short is required
- funding.tron.fresh: funding is stale but no short is required
- funding.uniswap.fresh: funding is stale but no short is required
- funding.vechain.fresh: funding is stale but no short is required
- funding.venice-token.fresh: funding is stale but no short is required
- funding.world-liberty-financial.fresh: funding is stale but no short is required
- funding.worldcoin-wld.fresh: funding is stale but no short is required
- funding.zcash.fresh: funding is stale but no short is required
- funding.zilliqa.fresh: funding is stale but no short is required

## Summary

```json
{
  "checks": 1517,
  "funding": {
    "1inch": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "aave": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "algorand": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "apecoin": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "aptos": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "arbitrum": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "aster-2": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "avalanche-2": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "axie-infinity": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "basic-attention-token": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "binancecoin": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "bitcoin": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "bitcoin-cash": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "bitget-token": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "bittensor": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "bitway": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "canton-network": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "cardano": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "celestia": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "chainlink": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "chiliz": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "compound-governance-token": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "cosmos": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "crypto-com-chain": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "curve-dao-token": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "decentraland": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "dogecoin": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "dydx-chain": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "elrond-erd-2": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "enjincoin": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "ethena": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "ethereum": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "ethereum-classic": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "ethereum-name-service": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "fantom": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "filecoin": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "gala": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "havven": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "hedera-hashgraph": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "hyperliquid": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "immutable-x": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "injective-protocol": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "internet-computer": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "jupiter-exchange-solana": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "kaspa": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "lido-dao": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "litecoin": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "matic-network": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "memecore": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "monero": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "morpho": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "near": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "neo": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "ondo-finance": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "optimism": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "pancakeswap-token": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "pepe": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "pi-network": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "polkadot": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "polygon-ecosystem-token": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "pump-fun": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "quant-network": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "render-token": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "ripple": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "sei-network": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "shiba-inu": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "sky": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "solana": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "stellar": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "stepn": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "sui": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "sushi": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "terra-luna": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "terra-luna-2": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "tezos": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "the-graph": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "the-open-network": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "the-sandbox": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "theta-token": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "thorchain": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "tron": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "uniswap": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "vechain": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "venice-token": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "world-liberty-financial": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    },
    "worldcoin-wld": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "zcash": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 270,
      "stale": true
    },
    "zilliqa": {
      "last": "2026-11-11 16:00:00+00:00",
      "rows": 540,
      "stale": true
    }
  },
  "funding_assets": 88,
  "hard_failures": 0,
  "last_mark": "2026-11-13 23:00:00+00:00",
  "mark_assets": 88,
  "now": "2026-11-14T00:31:11.223185+00:00",
  "panel_latest": "2026-11-13",
  "panel_latest_assets": 97,
  "warnings": 89
}
```
