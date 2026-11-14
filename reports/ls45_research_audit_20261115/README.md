# LS45 holdings, short-budget and rerank-frequency audit

状态：**诊断性研究，不是新注册试验，不是实盘批准。**

主样本：`2022-01-01 → 2026-09-21`（UTC）；研究口径为 LS45 冻结账本、20bps、Binance funding proxy。
当前实盘/样本外窗口另见文末，不能把研究主样本结果直接当成实盘 OOS。

## 结论

- 7 天重排不是“每周只监控一次”。H5 多头按 3 天事件更新，BTC 200D regime 每日检查，20% 空头 stop 逐小时检查，gross/逐仓/对账每日执行；只有 bear weak-four 的成员重排是 7 天一次。
- 在本样本里，7D 重排优于 1D、3D、14D。日频重排的短头开仓约 1,030 次，7D 约 335 次；日频带来更高换手、更低终值和更差回撤。
- 0.25x 是冻结的保守空头请求上限，不是扫描出来的最优值。0.375x/0.50x 在 20bps 可提高部分终值，但 Sharpe 和 MDD 变差；0.50x 在 50/100bps 失守，且会逼近或越过 1.25x live gross。
- 要真正提高下跌保护，单纯抬空头上限不够；需要预注册“预留 gross 的条件对冲”或“日内/日频筛选 + 迟滞/确认”，并做 12 个月独立 OOS。

## 1. 重排频率诊断

同一 LS45 账本、同一 1.50x research gross、03:00 UTC、20bps，只改 bear weak-four 的 `rebalance_days`：

| 频率 | 终值 | Sharpe | MDD | 空头开仓 | 观测最大 gross |
|---|---:|---:|---:|---:|---:|
| 1D | 46.0364x | 1.8115 | -42.29% | 1032 | 1.3308x |
| 3D | 47.9379x | 1.8302 | -42.93% | 572 | 1.3308x |
| **7D（当前）** | 69.2088x | 1.9846 | -39.84% | 335 | 1.3308x |
| 14D | 56.4902x | 1.9055 | -39.79% | 236 | 1.3308x |

100bps 压力：1D 为 **5.4364x / 0.9378 / -58.92%**；7D 为 **15.0872x / 1.3586 / -52.28%**。
当前 live-parity 1.25x / 01:05 UTC / 20bps 对照：1D **64.6966x / 1.9630 / -35.40%**，7D **65.2592x / 1.9792 / -34.06%**。

## 2. 空头预算诊断

同样的 LS45 账本、7D 重排、03:00 UTC；只线性缩放 bear/exit 的每腿权重：

| 请求空头 gross | 20bps 终值 | 20bps Sharpe | 20bps MDD | 50bps 终值/Sharpe/MDD | 100bps 终值/Sharpe/MDD |
|---:|---:|---:|---:|---|---|
| **0.25x（当前）** | 69.2088x | 1.9846 | -39.84% | 36.4386x / 1.7208 / -44.19% | 15.0872x / 1.3586 / -52.28% |
| 0.375x | 71.3040x | 1.9577 | -41.18% | 未跑 | 未跑 |
| 0.50x | 81.1859x | 1.9558 | -43.49% | 42.2939x / 1.7048 / -49.02% | 14.1972x / 1.2837 / -57.41% |

0.50x 的 20bps 目标 gross 最高达到 **1.4786x**、观测 gross **1.4903x**；这在 1.50x research hard cap 内，但不满足当前 live **1.25x**。当前 live 1.25x 下的 0.50x 诊断达到 **109.3951x / 2.0795 / -37.49%**，但 gross breach **657 小时**，不能作为可执行结果，必须由 live risk overlay 重算。

更保守的“预留对冲”诊断把 H5 多头降到 0.75x、空头请求 0.50x、总 gross 上限 1.25x：20bps 为 **23.5974x / 1.9605 / -28.93%**（0 breach），100bps 为 **6.3948x / 1.2258 / -41.22%**。它显著改善了 2022 和回撤，但牺牲了 2023–2026 的收益，且 100bps 无法满足 20x 目标；这是另一个风险预算，不是当前 LS45。

## 3. 年度持仓与收益

权重为按 `trades.csv` 重放、按当日 NAV 标记的重构值；同一时点的 gross 可以超过 100%，因为是杠杆多空账本。

| 年度 | 收益 | MDD | 平均 gross | 平均 long | 平均 short | 主要多头 | 主要空头 |
|---|---:|---:|---:|---:|---:|---|---|
| 2022 | +23.71% | -11.00% | 0.273 | 0.037 | 0.236 | ADA (Cardano) 2.32% (13d) ; NEAR (NEAR Protocol) 0.85% (11d) ; SOL (Solana) 0.34% (10d) ; DOGE (Dogecoin) 0.17% (3d) | AVAX (Avalanche) 2.37% (145d) ; SOL (Solana) 2.24% (132d) ; ADA (Cardano) 2.21% (129d) ; DOGE (Dogecoin) 1.64% (98d) ; SHIB (Shiba Inu) 1.62% (96d) ; NEAR (NEAR Protocol) 1.54% (92d) |
| 2023 | +264.98% | -39.84% | 0.458 | 0.396 | 0.062 | SOL (Solana) 9.31% (70d) ; XRP (XRP) 7.00% (62d) ; AVAX (Avalanche) 4.78% (39d) ; TRX (TRON) 4.58% (37d) ; SHIB (Shiba Inu) 2.92% (22d) ; BTC (Bitcoin) 2.66% (40d) | DOGE (Dogecoin) 0.81% (66d) ; SHIB (Shiba Inu) 0.61% (49d) ; AVAX (Avalanche) 0.60% (34d) ; SOL (Solana) 0.60% (72d) ; DOT (Polkadot) 0.49% (28d) ; XRP (XRP) 0.45% (46d) |
| 2024 | +101.57% | -32.31% | 0.444 | 0.391 | 0.053 | SUI (Sui) 6.05% (60d) ; DOGE (Dogecoin) 3.85% (40d) ; ICP (Internet Computer) 3.76% (55d) ; PEPE (Pepe) 3.69% (28d) ; IMX (Immutable) 2.62% (16d) ; XRP (XRP) 2.50% (19d) | NEAR (NEAR Protocol) 0.69% (67d) ; ETH (Ethereum) 0.58% (34d) ; SOL (Solana) 0.50% (31d) ; AVAX (Avalanche) 0.47% (27d) ; PEPE (Pepe) 0.47% (29d) ; UNI (Uniswap) 0.40% (36d) |
| 2025 | +194.07% | -17.90% | 0.451 | 0.388 | 0.063 | HYPE (Hyperliquid) 10.37% (88d) ; XLM (Stellar) 3.65% (31d) ; LINK (Chainlink) 3.42% (24d) ; HBAR (Hedera) 3.30% (51d) ; SUI (Sui) 3.15% (40d) ; ETH (Ethereum) 2.48% (29d) | HBAR (Hedera) 0.97% (71d) ; LTC (Litecoin) 0.68% (65d) ; SUI (Sui) 0.63% (50d) ; ADA (Cardano) 0.51% (30d) ; LINK (Chainlink) 0.49% (42d) ; XRP (XRP) 0.48% (42d) |
| 2026 | +158.57% | -14.81% | 0.412 | 0.199 | 0.214 | ZEC (Zcash) 13.50% (74d) ; HYPE (Hyperliquid) 3.41% (33d) ; LINK (Chainlink) 1.02% (7d) ; XMR (Monero) 0.79% (12d) ; GRAM (Gram (prev. Toncoin)) 0.68% (19d) ; DOGE (Dogecoin) 0.22% (6d) | SUI (Sui) 2.10% (91d) ; ADA (Cardano) 2.03% (85d) ; BCH (Bitcoin Cash) 1.82% (77d) ; SHIB (Shiba Inu) 1.66% (70d) ; XLM (Stellar) 1.65% (70d) ; HBAR (Hedera) 1.49% (63d) |

## 4. 分季度时间线

表中“主要多头/空头”是该季度按持仓天数累计暴露的前几名，不是某一天的完整持仓。

| 季度 | 收益 | MDD | 平均 gross | 主要多头 | 主要空头 |
|---|---:|---:|---:|---|---|
| 2022Q1 | +3.73% | -9.40% | 0.304 | ADA (Cardano) 7.02% (8d) | SHIB (Shiba Inu) 3.11% (45d) ; SOL (Solana) 2.85% (42d) ; ATOM (Cosmos Hub) 2.28% (33d) ; AVAX (Avalanche) 2.26% (33d) ; UNI (Uniswap) 2.10% (30d) ; LINK (Chainlink) 2.02% (28d) |
| 2022Q2 | +20.44% | -4.66% | 0.297 | NEAR (NEAR Protocol) 3.43% (11d) ; ADA (Cardano) 2.35% (5d) ; SOL (Solana) 1.36% (10d) | AVAX (Avalanche) 4.00% (63d) ; SOL (Solana) 2.36% (35d) ; NEAR (NEAR Protocol) 1.93% (31d) ; ATOM (Cosmos Hub) 1.88% (30d) ; ADA (Cardano) 1.75% (26d) ; BCH (Bitcoin Cash) 1.55% (21d) |
| 2022Q3 | -3.66% | -9.05% | 0.241 |  | DOGE (Dogecoin) 2.86% (42d) ; XLM (Stellar) 2.38% (35d) ; UNI (Uniswap) 2.25% (35d) ; DOT (Polkadot) 2.20% (33d) ; SOL (Solana) 1.87% (27d) ; XRP (XRP) 1.42% (21d) |
| 2022Q4 | +2.79% | -8.52% | 0.250 | DOGE (Dogecoin) 0.68% (3d) | ADA (Cardano) 3.76% (56d) ; SOL (Solana) 1.88% (28d) ; ETC (Ethereum Classic) 1.85% (28d) ; AVAX (Avalanche) 1.85% (28d) ; DOGE (Dogecoin) 1.79% (28d) ; ATOM (Cosmos Hub) 1.42% (21d) |
| 2023Q1 | +3.56% | -25.97% | 0.345 | BTC (Bitcoin) 7.79% (16d) ; SOL (Solana) 7.75% (28d) ; SHIB (Shiba Inu) 5.58% (7d) ; XRP (XRP) 2.63% (13d) ; FIL (Filecoin) 1.85% (8d) ; ETH (Ethereum) 1.23% (9d) | DOGE (Dogecoin) 0.95% (13d) ; SHIB (Shiba Inu) 0.59% (21d) ; SOL (Solana) 0.56% (20d) ; ADA (Cardano) 0.53% (7d) ; AVAX (Avalanche) 0.53% (7d) ; DOT (Polkadot) 0.53% (7d) |
| 2023Q2 | +17.25% | -17.51% | 0.612 | XRP (XRP) 21.74% (32d) ; TRX (TRON) 17.51% (31d) ; ICP (Internet Computer) 6.41% (11d) ; BCH (Bitcoin Cash) 3.25% (9d) ; BNB (BNB) 2.98% (8d) ; BTC (Bitcoin) 2.98% (24d) | LTC (Litecoin) 0.64% (25d) ; ADA (Cardano) 0.58% (21d) ; DOGE (Dogecoin) 0.58% (21d) ; BTC (Bitcoin) 0.57% (21d) ; XRP (XRP) 0.55% (21d) ; ETH (Ethereum) 0.31% (11d) |
| 2023Q3 | -20.84% | -22.36% | 0.333 | SHIB (Shiba Inu) 6.11% (15d) ; BCH (Bitcoin Cash) 4.80% (30d) ; XLM (Stellar) 4.62% (23d) ; XRP (XRP) 3.69% (17d) ; SOL (Solana) 2.44% (9d) ; DOGE (Dogecoin) 0.17% (3d) | DOGE (Dogecoin) 1.71% (32d) ; UNI (Uniswap) 1.62% (24d) ; AVAX (Avalanche) 1.42% (21d) ; SOL (Solana) 1.27% (31d) ; ATOM (Cosmos Hub) 0.95% (14d) ; SHIB (Shiba Inu) 0.94% (14d) |
| 2023Q4 | +279.69% | -7.41% | 0.542 | SOL (Solana) 26.93% (33d) ; AVAX (Avalanche) 18.95% (39d) ; NEAR (NEAR Protocol) 1.72% (6d) ; ICP (Internet Computer) 0.89% (13d) ; ADA (Cardano) 0.88% (9d) | XLM (Stellar) 0.92% (14d) ; SHIB (Shiba Inu) 0.92% (14d) ; ATOM (Cosmos Hub) 0.59% (9d) ; SOL (Solana) 0.55% (21d) ; DOT (Polkadot) 0.48% (7d) ; HBAR (Hedera) 0.46% (7d) |
| 2024Q1 | +18.35% | -19.14% | 0.530 | ICP (Internet Computer) 11.52% (46d) ; IMX (Immutable) 10.56% (16d) ; SHIB (Shiba Inu) 5.77% (30d) ; UNI (Uniswap) 5.46% (10d) ; ETC (Ethereum Classic) 5.37% (22d) ; LINK (Chainlink) 5.23% (19d) | ETC (Ethereum Classic) 0.57% (21d) ; ICP (Internet Computer) 0.48% (18d) |
| 2024Q2 | -16.30% | -22.49% | 0.379 | PEPE (Pepe) 14.85% (28d) ; BCH (Bitcoin Cash) 6.93% (20d) ; GRAM (Gram (prev. Toncoin)) 5.91% (28d) ; NEAR (NEAR Protocol) 3.37% (16d) ; SOL (Solana) 1.51% (8d) ; SHIB (Shiba Inu) 1.50% (15d) | NEAR (NEAR Protocol) 0.78% (28d) ; DOGE (Dogecoin) 0.58% (21d) ; UNI (Uniswap) 0.35% (15d) |
| 2024Q3 | -6.01% | -20.55% | 0.381 | XRP (XRP) 9.82% (16d) ; SUI (Sui) 5.22% (11d) ; ICP (Internet Computer) 3.55% (9d) ; TRX (TRON) 2.61% (3d) ; SOL (Solana) 2.30% (10d) ; KAS (Kaspa) 0.41% (5d) | AVAX (Avalanche) 1.88% (27d) ; NEAR (NEAR Protocol) 1.84% (37d) ; ETH (Ethereum) 1.82% (27d) ; PEPE (Pepe) 1.73% (27d) ; SOL (Solana) 1.52% (24d) ; UNI (Uniswap) 1.25% (21d) |
| 2024Q4 | +116.53% | -23.95% | 0.488 | SUI (Sui) 18.83% (49d) ; DOGE (Dogecoin) 14.91% (37d) ; HBAR (Hedera) 4.78% (24d) ; TAO (Bittensor) 2.14% (5d) ; APT (Aptos) 1.77% (10d) ; XLM (Stellar) 1.57% (21d) | DOGE (Dogecoin) 0.71% (23d) ; XLM (Stellar) 0.54% (20d) ; SUI (Sui) 0.51% (19d) ; SOL (Solana) 0.48% (7d) ; DOT (Polkadot) 0.47% (7d) ; ETH (Ethereum) 0.47% (7d) |
| 2025Q1 | -12.31% | -17.07% | 0.261 | BGB (Bitget Token) 7.37% (38d) ; XRP (XRP) 5.97% (24d) ; SUI (Sui) 2.87% (12d) ; HBAR (Hedera) 2.53% (20d) ; LTC (Litecoin) 2.04% (7d) ; SOL (Solana) 0.74% (5d) | HBAR (Hedera) 0.79% (24d) ; XRP (XRP) 0.71% (23d) ; BTC (Bitcoin) 0.59% (21d) ; LINK (Chainlink) 0.56% (21d) ; LTC (Litecoin) 0.55% (20d) ; BCH (Bitcoin Cash) 0.21% (3d) |
| 2025Q2 | +48.06% | -13.96% | 0.544 | HYPE (Hyperliquid) 35.62% (68d) ; SUI (Sui) 9.81% (28d) ; ETH (Ethereum) 1.84% (9d) ; BCH (Bitcoin Cash) 0.74% (5d) | DOT (Polkadot) 0.91% (14d) ; HBAR (Hedera) 0.79% (12d) ; XRP (XRP) 0.77% (12d) ; LTC (Litecoin) 0.68% (10d) ; ETH (Ethereum) 0.68% (10d) ; SUI (Sui) 0.56% (21d) |
| 2025Q3 | +77.10% | -17.90% | 0.756 | XLM (Stellar) 14.47% (31d) ; LINK (Chainlink) 13.46% (21d) ; HBAR (Hedera) 10.62% (31d) ; ETH (Ethereum) 8.01% (20d) ; AVAX (Avalanche) 6.66% (7d) ; HYPE (Hyperliquid) 5.90% (20d) | LTC (Litecoin) 0.55% (21d) ; AVAX (Avalanche) 0.17% (7d) |
| 2025Q4 | +27.90% | -9.29% | 0.240 | BNB (BNB) 8.58% (11d) ; AVAX (Avalanche) 1.18% (5d) | HBAR (Hedera) 2.31% (35d) ; SUI (Sui) 1.94% (29d) ; HYPE (Hyperliquid) 1.78% (26d) ; ADA (Cardano) 1.31% (19d) ; DOGE (Dogecoin) 1.18% (18d) ; LINK (Chainlink) 0.94% (14d) |
| 2026Q1 | +1.96% | -5.76% | 0.241 |  | SUI (Sui) 2.49% (38d) ; ADA (Cardano) 2.22% (31d) ; DOGE (Dogecoin) 2.09% (31d) ; LTC (Litecoin) 1.87% (28d) ; ZEC (Zcash) 1.48% (20d) ; HBAR (Hedera) 1.47% (21d) |
| 2026Q2 | +52.11% | -11.79% | 0.575 | ZEC (Zcash) 23.42% (44d) ; HYPE (Hyperliquid) 4.14% (19d) ; XMR (Monero) 2.28% (12d) ; GRAM (Gram (prev. Toncoin)) 1.97% (19d) ; DOGE (Dogecoin) 0.65% (6d) ; NEAR (NEAR Protocol) 0.36% (4d) | BCH (Bitcoin Cash) 3.34% (49d) ; SUI (Sui) 3.14% (46d) ; ADA (Cardano) 3.04% (45d) ; AVAX (Avalanche) 2.19% (32d) ; XLM (Stellar) 1.93% (28d) ; ETH (Ethereum) 1.87% (28d) |
| 2026Q3 | +66.73% | -6.27% | 0.421 | ZEC (Zcash) 17.30% (30d) ; HYPE (Hyperliquid) 6.33% (14d) ; LINK (Chainlink) 3.26% (7d) ; NEAR (NEAR Protocol) 0.23% (2d) | XLM (Stellar) 2.58% (35d) ; SHIB (Shiba Inu) 2.19% (29d) ; HBAR (Hedera) 1.58% (21d) ; HYPE (Hyperliquid) 1.58% (21d) ; DOGE (Dogecoin) 1.36% (18d) ; NEAR (NEAR Protocol) 1.16% (15d) |

## 5. 最大回撤阶段

| 峰值 → 谷底 | 恢复/结束 | MDD | 谷底持仓 |
|---|---|---:|---|
| 2023-01-29 → 2023-05-11 | 2023-10-30 | -39.84% | TRX (TRON) 51.72% ; BTC (Bitcoin) 10.31%; ADA (Cardano) -2.51% |
| 2024-03-31 → 2024-10-25 | 2024-11-09 | -32.31% | DOGE (Dogecoin) 53.36% ; SUI (Sui) 46.92% ; APT (Aptos) 8.67% |
| 2024-01-02 → 2024-01-22 | 2024-02-19 | -19.14% | ETC (Ethereum Classic) 26.17% ; ICP (Internet Computer) 15.27% |
| 2024-12-24 → 2025-04-23 | 2025-05-07 | -18.52% |  |
| 2025-07-27 → 2025-08-02 | 2025-08-16 | -17.90% | HBAR (Hedera) 61.70% ; XLM (Stellar) 33.48% |
| 2024-02-20 → 2024-02-26 | 2024-03-03 | -16.77% | UNI (Uniswap) 58.90% ; FIL (Filecoin) 8.37%; ICP (Internet Computer) -2.73% |
| 2026-02-05 → 2026-04-19 | 2026-05-03 | -14.81% | ZEC (Zcash) 58.48% ; HYPE (Hyperliquid) 29.70%; HBAR (Hedera) -6.55% ; SHIB (Shiba Inu) -6.48% ; BCH (Bitcoin Cash) -6.47% ; ADA (Cardano) -6.47% |
| 2025-05-25 → 2025-05-29 | 2025-06-09 | -13.96% | HYPE (Hyperliquid) 71.84%; SUI (Sui) -2.62% |

## 6. 最好/最差单日

| 日期 | 收益 | 主要持仓 |
|---|---:|---|
| 2023-01-14 | +31.19% | SOL (Solana) 97.89% |
| 2024-11-10 | +25.13% | DOGE (Dogecoin) 86.48% ; SUI (Sui) 19.97% |
| 2023-06-23 | +22.15% | BCH (Bitcoin Cash) 68.27%; LTC (Litecoin) -2.17% ; XRP (XRP) -2.03% |
| 2024-11-11 | +17.34% | DOGE (Dogecoin) 58.96% ; SUI (Sui) 14.50% |
| 2025-08-28 | +15.99% | LINK (Chainlink) 23.05% ; CRO (Cronos) 9.14% ; ETH (Ethereum) 3.81%; LTC (Litecoin) -2.51% |
| 2025-07-13 | +15.67% | XLM (Stellar) 41.80% ; HYPE (Hyperliquid) 37.29% ; HBAR (Hedera) 33.10% |
| 2026-09-16 | +15.56% | ZEC (Zcash) 79.38% |
| 2023-11-10 | +15.46% | SOL (Solana) 66.59% |
| 2023-12-08 | +15.20% | AVAX (Avalanche) 88.05% ; ADA (Cardano) 10.73%; SOL (Solana) -2.33% |
| 2023-12-10 | +14.67% | AVAX (Avalanche) 88.58% ; ADA (Cardano) 9.71%; SOL (Solana) -1.93% |
| 2025-05-08 | +14.13% | SUI (Sui) 50.97% ; HYPE (Hyperliquid) 32.71% |
| 2023-02-09 | -12.54% | SHIB (Shiba Inu) 93.40% |
| 2025-08-25 | -9.91% | LINK (Chainlink) 67.99% ; ETH (Ethereum) 43.82%; LTC (Litecoin) -2.43% |
| 2024-10-25 | -9.41% | DOGE (Dogecoin) 53.36% ; SUI (Sui) 46.92% ; APT (Aptos) 8.67% |
| 2025-08-19 | -8.67% | LINK (Chainlink) 75.54% ; ETH (Ethereum) 41.84%; LTC (Litecoin) -2.58% |
| 2023-03-22 | -7.82% | XRP (XRP) 72.66% ; BTC (Bitcoin) 38.50% ; BNB (BNB) 16.31%; ETH (Ethereum) -2.63% ; SOL (Solana) -2.62% |
| 2024-10-15 | -7.63% | SUI (Sui) 86.42% |
| 2024-06-07 | -7.21% | PEPE (Pepe) 59.64% ; UNI (Uniswap) 6.38%; NEAR (NEAR Protocol) -2.51% |
| 2023-10-24 | -6.89% | SOL (Solana) 124.80% |
| 2023-05-01 | -6.86% | ICP (Internet Computer) 52.01% ; BTC (Bitcoin) 5.36%; ADA (Cardano) -2.59% |

## 7. 当前 live-parity OOS（2026-09-22 → 2026-11-13）

53 个日行；整体 **0.938508x / Sharpe -0.5415 / MDD -19.32%**。这段窗口在 11-13 之前没有空头成交，弱势来自多头集中，而不是空头亏损。

| 月份 | 收益 | MDD | 平均 gross | 平均 long | 平均 short | 主要多头 | 主要空头 |
|---|---:|---:|---:|---:|---:|---|---|
| 2026-09 | -0.50% | -3.79% | 0.384 | 0.383 | 0.000 | ZEC (Zcash) 22.99% (9d) ; NEAR (NEAR Protocol) 15.35% (9d) |  |
| 2026-10 | +0.60% | -14.80% | 0.453 | 0.452 | 0.000 | NEAR (NEAR Protocol) 35.03% (31d) ; XMR (Monero) 4.71% (11d) ; TRX (TRON) 3.71% (6d) ; ZEC (Zcash) 1.34% (3d) ; BTW 0.41% (1d) |  |
| 2026-11 | -6.24% | -5.73% | 0.247 | 0.247 | 0.000 | HYPE (Hyperliquid) 10.76% (6d) ; XMR (Monero) 8.19% (4d) ; NEAR (NEAR Protocol) 5.72% (6d) |  |

2026-11-13 的最新信号在 2026-11-14 01:05 UTC 执行，开出 BCH/HYPE/NEAR/ZEC 四条 6.25% NAV 弱四空头；这是日频执行器根据 7D 账本执行，不是“每天重新选一遍”。

## 8. 方法与边界

- `full_daily_holdings.csv` 是从 LS45 `trades.csv` 和日线 mark 重放得到的研究重构，不是引擎原生的逐日 positions 文件；用于解释持仓，不能替代正式账本。
- 主样本 1.50x 是研究 hard cap；当前 live 是 1.25x target/hard cap，二者不能混用。
- 频率/预算变体均通过隔离进程临时改 `FROZEN_CONFIG`，没有改源码、没有改 live 参数，也没有预注册，因此只能作为诊断，不是 promotion evidence。
- 当前 live 的最后一次完整审计（2026-11-14 20:15 UTC）为 0 hard failure，账户约 505.3 USDT、115.7 USDT gross（约 0.229x），四条空头均有交易所可见的 20% mark stop；这是本地持久化审计快照，不是本报告的实时 API 刷新。

## 文件

- `frequency/summary.csv`：所有频率、成本和空头预算诊断数值。
- `holdings/full_daily_holdings.csv`：逐日持仓与 NAV 权重。
- `holdings/full_monthly.csv` / `full_quarterly.csv` / `full_yearly.csv`：聚合持仓与收益。
- `holdings/oos_daily_holdings.csv` / `oos_monthly.csv`：当前 live-parity 窗口。
- `holdings/full_drawdown_episodes.csv`、`full_best_days.csv`、`full_worst_days.csv`：回撤与单日事件。
