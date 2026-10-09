# Live Execution Replay

- window: 2022-01-01 -> 2026-09-21 (leverage 1.25, 20 bps)
- rebalances replayed: 534
- engine orders: 1185, matched: 1185, mismatched: 0
- engine final multiple: 44.1253

## Stateful plan-driven account (rounding + venue minimums compound)

- final engine multiple 42.555918x vs plan-driven 42.720619x
- relative drag: +0.3870%
- hourly liquidation events: 0

## Venue quantization (real Bitget specs)

- reference equity: 1,000 USDT; orders compared: 1185, below venue minimum: 73
- |notional error| mean 1.2905%, p95 6.1574%, max 49.8363%
