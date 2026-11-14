# LS45-G125 execution-clock and cost comparison

Generated: 2026-11-14. Research evidence only; this is not an order or a live approval.

## Headline comparison

| Scenario | Window | Multiple | CAGR | Sharpe | MDD |
| --- | --- | ---: | ---: | ---: | ---: |
| Legacy OOS · 03:00 ideal | 2026-09-22 → 2026-11-12 | 0.936549x | -38.03% | -0.6064 | -17.65% |
| OOS · 01:05 ideal | 2026-09-22 → 2026-11-13 | 0.943766x | -34.46% | -0.4727 | -18.99% |
| OOS · 01:05 live-parity | 2026-09-22 → 2026-11-13 | 0.938508x | -36.50% | -0.5415 | -19.32% |
| Full · 01:05 live-parity · 20bps | 2022-01-01 → 2026-09-21 | 65.259203x | 142.33% | 1.9792 | -34.06% |
| Full · 01:05 live-parity · 6bps diagnostic | 2022-01-01 → 2026-09-21 | 83.985152x | 155.64% | 2.0823 | -31.65% |

The 6bps row is a diagnostic sensitivity only. Current live accounting uses 20bps taker cost.

## Execution and risk counters

| Scenario | Days / metric days | Skips | Quantizations | Margin events | Liquidation | Gross breaches | Max observed gross | Fees | Funding |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| OOS · 01:05 live-parity | 53 / 52 | 11 | 49 | 52 | 0 | 0 | 0.8163x | 6.24 | -2.03 |
| Full · 01:05 live-parity · 20bps | 1725 / 1724 | 508 | 1538 | 1569 | 1 | 156 | 1.2821x | 1662.47 | -395.51 |
| Full · 01:05 live-parity · 6bps diagnostic | 1725 / 1724 | 494 | 1552 | 1569 | 1 | 129 | 1.2814x | 611.69 | -474.31 |

## Data and clock evidence

- Canonical execution clock: **01:05 UTC / 09:05 Beijing**, `mark_1h_open_floor`.
- Current live/OOS data fingerprint: `sha256:9ccd2bac1ca17aa9c6c9e4b57d5ff3ab52e9d246b5567a4a734ff64f5428c08f`.
- Warmup data fingerprint: `sha256:77bff92b77750c483bc63041fa2b72d31f576dfaf006d167d91d9ce81121d0ad`.
- Target ledger SHA-256: `e7049b2dda6bc7e6338939cb7d763e09341eb71d6845f54b91c12587b4dfc871`; the executor and `audit-live` verify it against manifest.
- OOS mark coverage: 0 missing hours; max gap 1.0h.
- OOS target execution audit: 72/72 pairs resolved; 0 missing.
- Full target execution audit: 2477/2477 pairs resolved; 0 missing.
- Full historical mark coverage: 25921 isolated 2-hour gaps across 86/88 assets; max gap 2.0h. `allow_incomplete_marks=true`, carry <=3h, `allow_data_audit_failures=false`.
- Full mark carries: 1222 held-asset hours; fill downgrades: 0.
- Full funding source: `binance-proxy` (Binance proxy); live/OOS uses `bitget-exact` through `2026-11-14 08:00:00+00:00`.

## Interpretation

- The 01:05 live-parity OOS is below both the legacy 03:00 OOS and the 01:05 ideal book. The difference is material and is not hidden by replacing the legacy result.
- The full-sample 20bps result remains above the 20x research objective, but it includes one real engine liquidation (XRP on 2025-02-03), 156 observed gross-breach hours, 508 order skips and 1538 quantity quantizations.
- A 6bps cost assumption improves the full result to 83.9852x and MDD to -31.65%, but that is not the current live cost model and therefore cannot be used as the live expectation.
- Signal, target book and execution clock are aligned. Actual venue fills, latency, slippage, partial fills, funding and venue rule changes remain execution differences; this report does not claim 1:1 realized fills.

## Current operational state

- The 2026-11-13 target book contains four 0.0625-weight shorts: bitcoin-cash, hyperliquid, near and zcash.
- The 2026-11-14 09:05 Beijing run was generated against stale cache state and wrote a 0-order cash journal. The cache/funding gates are now repaired, but the venue still has zero positions and the journal still says signal 2026-11-06.
- The four-short target is therefore **not executed**. Starting it after the six-hour catch-up window would be a deliberate late trade, not the frozen 01:05 strategy fill; no such late order was placed.

## Source identities

| Source | SHA-256 |
| --- | --- |
| `reports/ls45_live_g125_legacy_0300/summary.json` | `47ed83635d0373b868590c5b148f14627c6b158512fbaf313ac6e74a017f797e` |
| `reports/ls45_live_g125_0105_ideal/summary.json` | `a80c4b98d690663250eedc0b14c5e0f728242faeb70b92100e8f7b565c491d98` |
| `reports/ls45_live_g125/summary.json` | `a19cd9229788ea29a8eeb2fec697391ee7efab44531022586969959c4948b275` |
| `reports/ls45_live_g125_full_0105/summary.json` | `e5fa91d90de18322ee147e9be099d514e47dfc15dd283c97b4b3c1ec02bf91c2` |
| `reports/ls45_live_g125_full_0105_6bps/summary.json` | `3e508472c2f6c3d0f9679a13300b7db4088c9f26b8b6d97c5bff420837eca9a1` |
