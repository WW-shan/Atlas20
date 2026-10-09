# Bitget 衍生品轨道研究：杠杆、空头、资金费与强平

| 项目 | 内容 |
|---|---|
| 日期 | 2026-10-09 |
| 状态 | 研究输入；不改变 `RESEARCH.md` 的 H5 结论，不构成上线批准 |
| 目标 | 为 `docs/superpowers/specs/2026-10-09-bitget-derivatives-track-design.md` 提供外部证据、项目旧证据、冲突和数据缺口 |
| 主样本 | 2022-01-01 至 2026-09-21 |
| 真样本外 | 2026-09-22 起，未用于本报告的任何选择 |
| 约束 | PIT CMC Top20；Bitget USDT-M；默认 gross <= 1.25x；压力 1.5x/2.0x；空头 gross <= 0.5x；isolated margin |

## 0. 结论摘要

1. **资金费 carry 是真实的经济现象，但不是单向做空策略。** 最有力的证据来自 delta-neutral 的 spot+perp carry/arbitrage，而不是“开空收资金费”。
2. **空头腿的证据明显弱于多头腿。** 项目旧研究 S4 和 S14 都显示，加密动量空腿容易被反弹和逼空打爆；S14 的一次单币 -255.28% 周收益足以主导 long-short 结果。
3. **杠杆是可行的研究方向，但必须用强平模型而不是线性缩放。** Cheng 等在 BitMEX BTC 上给出的 3x long / 5x short 最优保证金是 BTC 单资产、早期样本；Top20 altcoin 尾部更厚；结合 5.5.1 的成本敏感性，本项目把默认上限压到 1.25x，1.5x/2.0x 只做压力。
4. **Bitget 的历史 mark candle 可以覆盖 2022+，历史 funding 不行。** 已核验 `history-candles` 可返回 2022 年 BTCUSDT/NEARUSDT 的 1H mark candle；`history-fund-rate` 只覆盖最近 90 天，因此历史资金费仍需 Binance 代理。
5. **Bitget-only 做不了真正的 cash-and-carry。** 真正的 carry 需要 spot long + perp short；只有合约时，空头是方向性风险，不是市场中性套利。
6. **返佣是主账户外部现金流。** 60% 返佣不进入量化账户 NAV，不能自动复利；量化账户回测使用完整 Taker 6bps。
7. **新轨道不能修复 H5 的 DSR。** H5 的 DSR 约 0.858，低于 0.95；新增杠杆和空头试验只会增加 N，必须作为独立验收轨道。

## 1. 研究方法与证据等级

本报告把来源分为：

- **T-direct**：大市值加密资产、Top20 附近、日频或更细，可直接指导规则；
- **T-partial**：加密市场但 universe 更宽、long-short 或样本不同，只能转移机制，不能转移幅度；
- **T-mechanism**：传统资产或理论，只转移机制；
- **Project**：项目内部既有研究，作为同数据、同引擎的 ablation 证据。

本报告不把任何外部论文的数字直接当作 Bitget 可实现收益。所有外部结果都要经过：

- Top20 PIT 过滤；
- Bitget 合约可用性；
- Taker/Maker 费和滑点；
- 资金费；
- isolated margin 和强平；
- 主样本/OOS 分离；
- multiple-testing 记账。

## 2. 资金费与 carry

### 2.1 The Crypto Carry Trade

**Citation**: Christin, N., Routledge, B. R., Soska, K., and Zetlin-Jones, A. (2023). *The Crypto Carry Trade*. Carnegie Mellon University. <https://gerbil.life/papers/CarryTrade.v1.2.pdf>

**Read**: full text.

**Sample**: Binance，18 个加密货币、36 个合约，2020-08-11 至 2023-06-23，8 小时 funding 周期。

**Strategy**: long spot + short perpetual；Tether-denominated 和 coin-denominated 两种合约。

**Headline results**:

- BTC Tether carry：年化 excess mean 14.26%，std 1.63%，Sharpe 8.76；
- BTC coin carry：年化 mean 10.86%，std 2.20%，Sharpe 4.93；
- 同期 BTC buy-and-hold Sharpe 0.46，US equities 0.33；
- 论文认为收益来自 long-side 对杠杆的需求；
- 2021 年 Binance 把最高杠杆从 125x 降到 50x 后，carry 收益下降；
- 交易所破产风险可以抵消高 Sharpe：30%–40% 的年化破产概率足以抵消观测到的 carry；
- FTX 等事件后 carry 收益明显下降。

**Design implications**:

- 资金费 carry 是真实机制，但需要 spot leg。Bitget-only 无法复制。
- 不能把高 Sharpe 直接套到单向 short。
- 交易所对手方风险必须进入验收，不能用历史 Sharpe 掩盖。

**Transfer label**: T-partial（BTC/大币，spot+perp，Binance，非 Top20-only）。

### 2.2 The Risk and Return of Cryptocurrency Carry Trade

**Citation**: Fan, Z. (2024). *The Risk and Return of Cryptocurrency Carry Trade*. SSRN 4666425. <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4666425>

**Read**: abstract and secondary summary; full PDF not accessible from this network.

**Headline results**:

- Cross-sectional carry：long high-interest / short low-interest；
- 年化收益约 43.4%，Sharpe 约 0.74；另一版本摘要给出 46.71% 和 0.77；
- 报告称对 2018、2021 市场崩盘有一定抵抗，但存在未解释的负风险溢价。

**Design implications**:

- 与 Christin 等的高 Sharpe 存在明显量级冲突。
- Cross-sectional carry 的 universe 和构造与 Top20 不同，不能直接采用。
- 如果做 funding carry，必须区分 delta-neutral 和方向性 short。

**Transfer label**: T-partial。

### 2.3 Fundamentals of Perpetual Futures

**Citation**: He, S., Manela, A., Ross, O., and von Wachter, V. (2026). *Fundamentals of Perpetual Futures*. arXiv:2212.06888v7. <https://arxiv.org/html/2212.06888v7>

**Read**: full text.

**Sample**: BTC, ETH, BNB, DOGE, ADA；2020–2024 小时数据。

**Strategy**: random-maturity arbitrage；当 perpetual 高于 no-arbitrage price 时 long spot + short perp，反之 short spot + long perp。

**Zero-cost results**:

| Coin | Full-sample Sharpe | Annualized return | Max drawdown |
|---|---:|---:|---:|
| BTC | 11.65 | 52.55% | -3.82% |
| ETH | 12.77 | 62.83% | -2.62% |
| BNB | 17.66 | 134.74% | -1.96% |
| DOGE | 14.90 | 181.12% | -13.90% |
| ADA | 19.76 | 155.16% | -5.69% |

**Important caveats**:

- These are zero-cost, random-maturity arbitrage results.
- The paper explicitly discusses exchange fees, effective bid-ask spreads and interim losses.
- Maximum drawdowns can reach 13.90% for DOGE even in a delta-neutral arbitrage.
- Capital constraints and margin constraints can force liquidation before convergence.

**Design implications**:

- 这些 Sharpe 不能作为方向性 short 的预期。
- 新引擎必须建模 effective spread、margin 和 interim loss。
- 如果未来做 carry，必须同时有 spot 和 perp 两条腿。

**Transfer label**: T-partial（BTC/ETH/BNB/DOGE/ADA，spot+perp）。

### 2.4 Perpetual Futures and Basis Risk

**Citation**: Gornall, W., Rinaldi, M., and Xiao, Y. (2025). *Perpetual Futures and Basis Risk: Evidence from Cryptocurrency*. AEA 2026 program paper. <https://www.aeaweb.org/conference/2026/program/paper/ByyFEfr4>

**Read**: full preliminary PDF.

**Headline results**:

- Perpetual futures dominate volume and improve liquidity relative to quarterly futures；
- Spreads are 49–83% tighter than comparable quarterly futures；
- Perpetuals reduce extreme price dislocations；
- Perpetuals substantially reduce drawdowns of arbitrage strategies；
- Funding payments are generally small and maintain convergence；
- Arbitrage capital constraints amplify price impact when demand is high.

**Design implications**:

- 支持使用 Bitget perpetual 作为执行场所的流动性理由。
- 但“流动性好”不等于“强平时没有滑点”；资本约束和 cascade 会放大冲击。
- Funding 小是正常状态，不是收益保证。

**Transfer label**: T-direct on venue mechanism, T-partial on returns。

### 2.5 Designing Funding Rates

**Citation**: Kim, J. and Park, H. (2025). *Designing funding rates for perpetual futures in cryptocurrency markets*. arXiv:2506.08573. <https://arxiv.org/html/2506.08573v1>

**Read**: full text.

**Findings**:

- 建立 path-dependent funding rate 的定价和 replication 框架；
- 现实中的 8 小时平均 funding 是 path-dependent；
- 适当设计的 funding rate 可以让 perpetual price 锚定 target；
- 资金费不是外生常数，而是会随价格路径和 funding rule 变化。

**Design implications**:

- 回测不能用固定 0.01%/8h 代替所有币和所有时段；
- 必须使用实际 settlement timestamp 和实际 funding rate；
- Funding 压力测试必须覆盖符号反转和极端值。

**Transfer label**: T-mechanism。

## 3. 杠杆、保证金与强平

### 3.1 Liquidation, Leverage and Optimal Margin in Bitcoin Futures Markets

**Citation**: Cheng, Z., Deng, J., Wang, T., and Yu, M. (2021). *Liquidation, Leverage and Optimal Margin in Bitcoin Futures Markets*. Applied Economics 53(47), 5415–5428. arXiv:2102.04591. <https://arxiv.org/html/2102.04591v1>

**Read**: full text.

**Sample**: BitMEX BTC perpetual futures.

**Headline results**:

- 被强平交易者平均杠杆：long 约 58.13x，short 约 59.94x；
- 每日强平占未平仓量：long 3.51%，short 1.89%；
- 若目标日 margin call probability = 1%，论文估计最优 margin：
  - long 33%（约 3x）；
  - short 20%（约 5x）；
- 正态分布假设会显著低估最优保证金。

**Design implications**:

- BTC 单资产在早期 BitMEX 上就需要 3x/5x 级别的保守保证金；
- Top20 altcoin 的尾部比 BTC 更厚，不能用 3x 作为本项目默认；
- 1.25x/1.5x 比 2x/3x 更符合本项目 3% 总资金风险预算。

**Transfer label**: T-partial（BTC、早期 BitMEX）。

### 3.2 Delayed Marks, Funding Memory, and Forecasting Liquidation-Tail Risk

**Citation**: Lim, B. C. (2026). *Delayed Marks, Funding Memory, and Forecasting Liquidation-Tail Risk in Crypto Perpetual Futures*. Risks 8(5), 76. <https://www.mdpi.com/2571-9394/8/5/76>

**Read**: abstract and fetched sections; MDPI full page blocked after initial fetch.

**Findings**:

- 强平风险由 leverage、funding、mark price delay、maintenance boundary 和 executable depth 共同决定；
- delayed or smoothed mark 会隐藏实际价格穿越，造成 catch-up overshoot 和 bad debt；
- funding 是 persistent collateral drain，应按 position direction 和 horizon 评估，而不是只看无条件均值；
- 建议更快价格检测、更大 maintenance cushion、限制 leverage，并用 average execution price 而不是 last level 评估 liquidation size。

**Design implications**:

- 引擎必须用 mark price，不是 last price；
- 必须逐结算点扣 funding；
- 强平必须允许 worst-case slippage 和 liquidation fee；
- 回测应报告 liquidation event、强平价、实际执行价和坏账风险。

**Transfer label**: T-mechanism/T-direct for liquidation modeling。

### 3.3 Hidden Liquidity During a Bitcoin Perpetual Futures Liquidation Cascade

**Citation**: Lim, B. C. (2026). *Hidden Liquidity, Displayed Depth, and Execution Risk During a Bitcoin Perpetual Futures Liquidation Cascade*. SSRN 6891658. <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6891658>

**Read**: abstract.

**Findings**:

- 使用 Bybit BTCUSDT 完整 trade tape 和 50-level order book；
- 在 liquidation cascade 中，hidden liquidity 被检测到的频率更高，hidden-depth ratio 更大；
- displayed depth 在 execution risk 最高时是有偏且不完整的可执行流动性代理。

**Design implications**:

- 当前 Bitget 盘口显示深度只能用于小仓位估滑点；
- 强平级联中不能用显示深度线性外推；
- 压力测试必须使用高于正常盘口的滑点。

**Transfer label**: T-direct for execution risk。

### 3.4 Anatomy of a Crypto Cascade

**Citation**: Lim, B. C. (2026). *Anatomy of a Crypto Cascade: Minute-Level Evidence from the October 2025 Crash*. SSRN 6579278. <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6579278>

**Read**: abstract and secondary summaries.

**Findings**:

- 2025-10-10，Binance BTC 在 10 分钟内下跌约 12.6%；
- 市场级联，主要 venue BTC 低点相差仅约 0.3%；
- 报道约 $19B 杠杆仓位在短时间内被清算；
- intra-minute spread 可达 6.79%。

**Design implications**:

- 小时级 mark price 仍可能低估秒级 cascade；
- 强平压力测试需要加入跳空、滑点和 ADL/liquidation fee；
- 空头在上涨 cascade 中同样会遭遇逼空。

**Transfer label**: T-direct for tail risk。

### 3.5 Early-Warning Signals Across Seven Liquidation Cascades

**Citation**: arXiv:2607.27070. *Where does the criticality live? Early-warning signals are event-heterogeneous across seven crypto-perpetual liquidation cascades*. <https://arxiv.org/abs/2607.27070>

**Read**: abstract.

**Findings**:

- 研究 2022–2025 七次 BTC liquidation cascade；
- 没有任何变量在所有事件中都是 event-invariant；
- price critical-slowing-down 在 5/7 事件中出现，但在两次 sudden-news 冲击中失效；
- 结果支持“内生 buildup”与“外生 news shock”两类结构。

**Design implications**:

- 不存在一个可靠的“提前逃顶”指标；
- 熊市确认只能降低风险，不能保证避开 cascade；
- 强平缓冲和仓位上限比预测强平更重要。

**Transfer label**: T-direct for regime uncertainty。

## 4. 多空动量与空头腿

### 4.1 Time-Series and Cross-Sectional Momentum under Realistic Assumptions

**Citation**: Han, C., Kang, B., and Ryu, J. (2024). *Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market: A Comprehensive Analysis under Realistic Assumptions*. SSRN 4675565; conference PDF: <https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>

**Read**: full text (also project S4).

**Sample**: CMC coins with market cap >= $1M and daily volume >= $1M, December 2013–August 2023; 15 bps per trade; daily mark-to-market; liquidation modelling.

**Findings**:

- Time-series long-only trend is strong: best (28, 5) Sharpe 1.51 vs market 0.84；cumulative 36,686% vs 2,696%；invested 48% of time；
- Time-series momentum is concentrated in bullish markets；
- Shorting the market after declines loses money in most cases；
- Cross-sectional momentum is weak: 5 of 21 portfolios liquidated；only 6 beat market；
- Profits come from long leg and large coins；
- Losers often rebound and hurt the short leg.

**Design implications**:

- 空头不能是 H5 的默认防守；
- 只有强熊市确认和很小 gross 才值得测试；
- 必须建模 liquidation，因为 5/21 cross-sectional portfolios 被强平。

**Transfer label**: T-partial/T-direct for short-leg warning。

### 4.2 Cryptocurrency Momentum Has (Not) Its Moments

**Citation**: Grobys, K., Kolari, J. W., Sandretto, D., Shahzad, S. J. H., and Äijö, J. (2025). *Cryptocurrency momentum has (not) its moments*. Financial Markets and Portfolio Management 39(4). <https://osuva.uwasa.fi/bitstreams/994474fd-8d6c-4669-9f43-98836145cad6/download>

**Read**: full text (project S14).

**Sample**: 30 largest coins by prior year-end market cap, stablecoins excluded, January 2016–December 2023; weekly quintile long-short.

**Findings**:

- Plain momentum insignificant；
- One crash driven by a single coin produced -255.28% weekly return；
- Volatility-managed versions earn 1.86–2.40% per week and remain significant after factor adjustment；
- Power-law tail exponents < 3，so variance is undefined；
- Volatility management does not remove tail risk.

**Design implications**:

- 空头腿的尾部风险不能被 Sharpe 或波动率目标完全描述；
- 必须报告 best-trade removal、tail loss 和 terminal-wealth bootstrap；
- 单币风险是真实风险，H5 已经高度集中，杠杆会放大。

**Transfer label**: T-direct on large caps, T-partial on long-short construction。

### 4.3 Catching Crypto Trends

**Citation**: Zarattini, C., Pagani, A., and Barbon, A. (2025). *Catching Crypto Trends: A Tactical Approach for Bitcoin and Altcoins*. Swiss Finance Institute Research Paper 25-80. <https://concretumgroup.com/wp-content/uploads/2026/02/Catching-Crypto-Trends.pdf>

**Read**: full text (project S17).

**Findings**:

- Long-only top-20 liquid portfolio, net 10 bps: Sharpe 1.57, CAGR 18%, volatility 9%, max drawdown 11%, alpha 10.8%；
- BTC ensemble Sharpe 1.58, max drawdown 19%；
- 50 bps cost cuts 5-day model CAGR from 34% to 18%；
- 200% weight cap implies leverage；
- Zero-delay fills make results an upper bound.

**Design implications**:

- 前二十长仓趋势在更分散、更低波动构造下可以很稳；
- 但该策略的收益远低于 H5，H5 的高收益来自集中度和选币；
- 杠杆不能解决集中度问题，只会放大单币尾部。

**Transfer label**: T-direct on universe, T-partial on design。

### 4.4 Cross-Sectional Momentum in Cryptocurrency Markets

**Citation**: Drogen, L. (2023). *Cross-Sectional Momentum in Cryptocurrency Markets*. SSRN 4322637. <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4322637>

**Read**: abstract.

**Findings**:

- 综述价格动量证据并构造多种策略；
- 与 S4/S14 一致，cross-sectional 构造对样本和成本敏感。

**Design implications**:

- 不把 cross-sectional long-short 作为第一轮候选；
- 先做 long-only leverage，再做小仓位 BTC short，最后才考虑 weakest-Top20。

**Transfer label**: T-partial。

## 5. 项目旧研究

### 5.1 H5 现货结论

- H5 在 2022-01-01 至 2026-09-21、20bps、+3h worse policy 下：19.53x，Sharpe 1.623，MDD -36.97%；
- PBO 0.192 PASS；
- DSR 0.858 < 0.95 FAIL；
- 当前信号为 NEAR 62.14% / CASH 37.86%；
- 2026-09-22 起为真样本外，截至 2026-10-08 约 0.9689x vs BTC 0.9431x。

来源：`RESEARCH.md` §00.13、§00.18、§00.20；`reports/phase_momentum_candidate_eval_h5/`。

### 5.2 资金费 overlay H6 被拒

`PR2026-10-H6` 用 point-in-time Top20 mean funding level 的 7 日均值做 de-risking overlay。结果：

- MDD 从 -36.97% 改善到 -27.58%；
- terminal multiple 从 19.53x 降到 12.02x；
- Sharpe 从 1.623 降到 1.537；
- 一年滚动最差 multiple 不变；
- 两个邻域 P70/P90 也失败。

结论：资金费状态有 crash separation，但作为减仓规则净损失收益。不能把 H6 的失败直接解释为“应该反向做空”。

来源：`RESEARCH.md` §00.19；`reports/phase_momentum_hypotheses_2026_10/`。

### 5.3 无杠杆消融

项目已经做过 400 组跨家族无杠杆消融。结论是：在没有杠杆约束下，现有候选的高收益来自选币、集中度和波动率目标，而不是一个免费的杠杆来源。`reports/no_leverage_ablation_2022/`。

### 5.4 执行延迟

H5 在 20bps 下：

- close fill：21.47x；
- +1h：22.80x；
- +3h：19.53x；
- lag 1 day：10.55x。

执行延迟本身已经是重要成本。衍生品轨道继续使用 T+1 +3h，不能假设 close fill。

来源：`reports/phase_momentum_execution_lag_2022/`；`reports/phase_momentum_candidate_eval_h5/`。

### 5.5 项目内新分析（2026-10-09）

本节是对现有 H5 日收益和现有 Binance funding 数据的**只读诊断**，不是新的预注册回测，也不改变 `RESEARCH.md` 的任何结论。它的作用是把设计稿里的几个直觉问题量化：杠杆到底改善了什么、空头到底收不收 funding、条件空头值不值得进入 Phase 3。

#### 5.5.1 杠杆缩放：Sharpe 不变，MDD 放大

使用 H5 `day_close` 日收益（2022-01-01 至 2026-09-21，20bps）做线性缩放，不含资金费、强平和额外成本：

| 方案 | 终值 | CAGR | Sharpe | MDD | Calmar |
|---|---:|---:|---:|---:|---:|
| H5 1.0x | 19.53x | 87.6% | 1.623 | -36.97% | 2.37 |
| H5 ×1.25 | 35.85x | 113.4% | 1.623 | -44.27% | 2.56 |
| H5 ×1.50 | 62.51x | 140.0% | 1.623 | -50.88% | 2.75 |
| H5 ×2.00 | 163.44x | 194.2% | 1.623 | -62.23% | 3.12 |
| H5 ×3.00 | 621.78x | 290.4% | 1.623 | -80.56% | 3.61 |

结论：在没有资金费和强平时，杠杆不改变 Sharpe；它只放大终值和回撤。Calmar 看似提高，是因为回撤没有完全按 L 线性放大，但这不能替代资金费、强平和尾部风险的建模。

按 6/8/11/20/50/100 bps 重建成本敏感性后：

| 成本 | 1.25x 终值 | 1.25x MDD | 1.50x 终值 | 1.50x MDD |
|---:|---:|---:|---:|---:|
| 6 bps | 39.87x | -43.3% | 71.00x | -49.8% |
| 8 bps | 39.27x | -43.4% | 69.72x | -50.0% |
| 11 bps | 38.38x | -43.6% | 67.85x | -50.2% |
| 20 bps | 35.85x | -44.3% | 62.51x | -50.9% |
| 50 bps | 28.55x | -46.3% | 47.57x | -53.1% |
| 100 bps | 19.53x | -49.6% | 30.16x | -56.5% |

**1.25x 是唯一在全部成本档位下仍低于 50% MDD 的杠杆候选；1.5x 从 8bps 起就触及或越过 50% kill switch。** 这支持把设计稿默认从 1.5x 下调到 1.25x，把 1.5x/2.0x 降级为压力测试。

#### 5.5.2 Funding 分布：不是所有空头都在收 funding

使用 Binance 2022-01-01 至 2026-09-21 的 funding 归档，52 个有历史的币：

| 指标 | 中位数 | BTC | NEAR | SOL |
|---|---:|---:|---:|---:|
| 年化 funding 均值 | 4.65% | 6.61% | 4.54% | -4.93% |
| 正 funding 占比 | 75.0% | 84.6% | 74.7% | 66.1% |
| 1% 分位（8h） | -0.042% | -0.0093% | -0.0447% | -0.1506% |
| 95% 分位（8h） | 0.0154% | 0.0118% | 0.0160% | 0.0172% |

含义：

- BTC/NEAR 的 funding 历史上多数时间为正，空头持有这些币更可能收到 funding；
- SOL 的年化 funding 均值为负，空头平均要支付 funding；
- 空头标的必须使用自己的 funding 历史，不能用 BTC funding 代理所有 altcoin；
- funding 分布有厚尾，1% 分位可以达到 -0.15%/8h 甚至更低，必须做 2x/3x 和符号反转压力。

#### 5.5.3 条件空头诊断：有收益改善，但没有通过 MDD 门槛

规则：`bear_t = BTC < 200D MA 且 BTC 30D return < 0`；在 `bear_t` 时做空 PIT Top20 中 30D 收益最弱的币，或做空 BTC。使用 Binance funding 代理、16bps 单边切换成本、日频 close-to-close，未做完整强平/ADL：

| 空头 | 空头 gross | 组合终值 | Sharpe | MDD | 空头年化贡献 |
|---|---:|---:|---:|---:|---:|
| 空 BTC | 0.25x | 33.99x | 1.872 | -36.97% | 12.0% |
| 空 BTC | 0.50x | 57.35x | 2.052 | -36.97% | 23.9% |
| 空最弱币 | 0.25x | 90.34x | 2.245 | -36.97% | 33.7% |
| 空最弱币 | 0.50x | 364.86x | 2.525 | -36.97% | 67.4% |

这个结果看起来很强，但必须同时看到四个警告：

1. **MDD 没有改善**。H5 的最大回撤发生在空头 overlay 未激活的时期，所以组合 MDD 与 H5 完全相同。按设计稿现有的空头 kill criterion（相比同杠杆 long-only 的 MDD 改善至少 5 个百分点），它**不通过**。
2. **2022 贡献过大**。空最弱币 0.25x 的空头年度收益中，2022 年约贡献 106% 的累计空头 PnL；去掉 2022 年后组合约 41.2x，仍高于 H5，但优势显著缩小。
3. **少数极端日驱动**。空最弱币 0.25x 去掉最好的 20 个空头交易日后，组合约 44.2x，仍高于 H5 的 19.5x，说明不是只靠 1–3 天；但去掉最好 1 天就从 114.4x 降到 101.7x，尾部贡献集中度仍然高。
4. **反向尾部真实存在**。空头最差单日是 2022-11-10 做空 SOL，SOL 当日 +26.8%，1x 空头亏损 -26.8%；0.5x 空头单日拖累约 -13.4% equity。完整引擎必须检查这类逼空是否会触发强平或 ADL。

#### 5.5.4 设计含义

- **默认杠杆从 1.5x 下调到 1.25x**，1.5x/2.0x 只做压力；
- **杠杆不是 alpha**，不能把它当成改善 Sharpe 的手段；
- **空头 overlay 仍有研究价值**，但只能作为 long-only 杠杆候选通过后的独立 overlay；
- **空头 MDD 门槛不能因为这次诊断而放宽**，否则就是看到结果后改规则；
- **每个空头币必须有自己的 funding 历史**，不能统一用 BTC funding；
- **在完整 isolated margin + mark price + funding + 强平引擎跑完之前，任何空头结论都只能是 provisional**。


### 5.6 Phase 1 数据审计（2026-10-09）

本轮已经实现并跑通 Phase 1 的最小数据层：

- Bitget 公共 USDT-M 客户端：合约、历史 mark/index/market K 线、funding history；
- PIT Top20 coin id → Bitget 合约映射；
- 可恢复下载器：`scripts/download_bitget_derivatives_data.py`；
- 覆盖与 funding 重叠审计：`scripts/audit_bitget_derivatives_data.py`；
- 单元测试：`tests/test_bitget_derivatives.py`。

#### 5.6.1 合约映射

当前 PIT Top20 历史池共 102 个 coin id，其中 **88 个映射到 Bitget USDT-M**，**14 个没有 Bitget 合约**：

```text
EOS, FLOW, FTT, HNT, HTX, HT, KCS, LEO, MKR, MNT, OKB, OSMO, WAVES, YFI
```

MATIC → POL 的 rebrand 映射有效；BGB、SHIB、PEPE、LUNC 等直接映射有效。缺失合约必须按设计中的 `CASH / unavailable` 处理，不能用排名更低的币替代。

#### 5.6.2 API 事实修正

这轮实测修正了此前设计稿中的两个 API 细节：

| 端点 | 实测行为 | 设计含义 |
|---|---|---|
| `/api/v2/mix/market/history-fund-rate` | `pageNo` 有效，约 90 天历史；BTC 约 270 条 8h 记录 | **历史 funding 主端点** |
| `/api/v3/market/history-fund-rate` | 忽略 `pageNo`，每次只返回最近 20 条 | 不能用于历史 funding 下载 |
| `/api/v3/market/history-candles` | `type=mark/index/market` 可用；单次 `limit<=100`；窗口<=90 天；返回 `endTime` 之前最近 100 条 | 必须从 `endTime` 向前分页，再按 `[start, end)` 过滤 |
| `/api/v2/mix/market/contracts?productType=USDT-FUTURES` | 返回 816 个合约 | 合约规格主端点 |

#### 5.6.3 K 线覆盖抽样

本轮对 BTC、NEAR、SOL 的 `mark` 1H 数据做了两个抽样窗口（2022-01-01 附近和 2026-09-14 附近）：

- 6/6 抽样窗口完整；
- 每个币 334 行；
- 窗口内最大 gap 2 小时。

这证明 Bitget 历史 mark K 线可以覆盖 2022 和 2026，但**不是全量覆盖审计**。全量下载仍需要遍历 88 个映射合约 × `mark/index/market`，下载器已按 89 天窗口和断点状态设计。

#### 5.6.4 Funding 重叠验证：严格门槛失败

Bitget v2 funding 与 Binance funding 在最近 245 个 settlement 上重叠：

| 币 | overlap | 符号一致率 | Pearson | 中位绝对误差 | 95 分位绝对误差 | 累计差 | 7 日最大绝对差 | 判定 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| BTC | 245 | 0.853 | 0.250 | 0.274 bps | 0.947 bps | -19.7 bps | 11.7 bps | 失败 |
| NEAR | 245 | 0.829 | 0.273 | 0.050 bps | 1.421 bps | +55.0 bps | 12.6 bps | 失败 |
| SOL | 245 | 0.694 | 0.505 | 0.378 bps | 1.121 bps | +36.2 bps | 12.6 bps | 失败 |

失败原因不是量级，而是**结算点符号一致率和相关性**：中位误差和 95 分位误差都低于设计阈值，但符号一致率只有 0.69–0.85，Pearson 只有 0.25–0.51，远低于 0.95。按设计稿 §5.2.1 的预注册阈值，Binance funding **不能作为 Bitget funding 的精确历史代理**。

累计误差在 245 个结算点（约 82 天）为 -19.7 bps 到 +55.0 bps，年化约 -88 bps 到 +245 bps。这个量级足以影响一个年 funding drag 约 150 bps 的策略，不能被当成零。

#### 5.6.5 结论与处理

1. **不要把 Binance funding 称为 Bitget 精确历史。** 它只能作为不确定性/压力带。
2. **严格数据质量门槛不因为本次结果放宽。** 预注册阈值仍为符号一致率 ≥0.95、Pearson ≥0.95、中位误差 ≤1bp、95 分位 ≤5bp。
3. **历史衍生品回测如果依赖精确 funding，当前不能通过。** 三个可选项：
   - 找到更好的 Bitget 历史 funding 数据源（交易所数据、付费供应商或数据请求）；
   - 明确把 2022–2026 的 funding 结果标为“proxy/uncertain”，用 0x/1x/2x/3x 压力带而不是精确值；
   - 只用最近 90 天 Bitget 精确 funding + 未来 OOS，历史段只做不含 funding 的价格/强平研究。
4. **Phase 2 引擎可以继续实现，但 funding attribution 必须带 `funding_source=proxy` 标签**，且在找到更好来源前不能作为上线依据。
5. **全量 K 线下载尚未完成。** 本轮只抽样验证了 BTC/NEAR/SOL 的 mark 数据；88 个合约 × 3 种类型仍需后台跑完。


## 6. Bitget 官方机制

### 6.1 Funding

Bitget 官方支持文档：

- <https://www.bitget.com/support/articles/12560603817108>
- <https://www.bitget.com/support/articles/12560603837210>

机制：

- 大多数 USDT-M、Coin-M、USDC-M 永续每 8 小时结算一次；
- 部分交易对 interval 不同；
- 正 funding：longs pay shorts；
- 负 funding：shorts pay longs；
- 历史 funding 页面支持时间筛选，但公开 API 只返回最近 90 天。

API:

- `GET /api/v3/market/history-fund-rate`
- 文档：<https://www.bitget.com/docs/catalog/market/derivatives>

### 6.2 Mark price 和 liquidation

Bitget 官方文档：

- <https://www.bitget.com/amp/academy/how-does-bitgets-futures-liquidation-mechanism-work>
- <https://www.bitget.com/support/articles/12560603839176>

关键点：

- Futures liquidation 基于 maintenance-margin risk，使用 mark price 和 position-tier rules；
- Derivatives maintenance margin = position size × (maintenance margin rate + taker fee rate) × mark price；
- Isolated margin 只影响同一 token 的 orders/positions；
- Liquidation fee 不退还；
- 强平可能通过 IOC 部分减仓，而不是一次全部平掉。

### 6.3 历史 K 线

Bitget `GET /api/v3/market/history-candles` 支持：

- `type=market`, `mark`, `index`, `premium`；
- `interval=1H`；
- 可返回 90 天以前的历史。

已核验：

- BTCUSDT 2022-01-01 1H mark candle 可返回；
- NEARUSDT 2022-01-01 1H mark candle 可返回；
- 仍需逐币做覆盖审计。

### 6.4 手续费

Bitget 当前 USDT-M 基础费率：

- Maker 0.02% = 2 bps/边；
- Taker 0.06% = 6 bps/边。

60% 返佣：

- 有效 Taker：2.4 bps/边；
- 有效 Maker：0.8 bps/边；
- 但返佣进入主账户，不是量化账户；
- 量化账户 NAV 必须按 6 bps/边记账。

## 7. 冲突证据

| 主题 | 支持 | 反对 | 本项目处理 |
|---|---|---|---|
| Funding carry | Christin 等 Sharpe 8.76；He 等 random-maturity Sharpe 11.65+ | Fan 等 Sharpe 0.74；FTX 后收益下降；exchange risk | 只作为 delta-neutral 研究；Bitget-only 不复制 |
| 空头动量 | S2 大币 long-short 有收益；Man Group 使用 long-short | S4 short leg 亏钱；S14 单币 -255% 周收益 | 只做 0.25x/0.5x 条件性 overlay |
| 杠杆 | Cheng 等 BTC 3x long/5x short 最优保证金 | Altcoin 尾部更厚；cascade 和 hidden liquidity；1.5x 在 8bps 起越过 50% MDD | 默认 1.25x；1.5x/2x 仅压力 |
| 波动率管理 | Barroso/Santa-Clara；Yang 2025；S14 | Cederburg 等 OOS 失败 | 保留 de-risking，不把 Sharpe 当唯一指标 |
| 流动性 | Gornall 等 perp 改善流动性 | Hidden liquidity 显示 cascade 中显示深度失真 | 小仓位正常滑点 1–3bps；压力 5–10bps |

## 8. 设计修正

基于本报告，设计稿采用以下修正：

1. 默认最大 gross 从“未定”改为 **1.25x**（2026-10-09 项目内诊断后从 1.5x 下调）；
2. 2.0x 只作为压力测试，不作为默认上线；
3. 空头总 gross 上限 **0.5x**，单币 **0.25x**；
4. 第一轮空头只做 BTC short，weakest-Top20 short 作为第二轮；
5. 真正 funding carry 需要 spot+perp，Bitget-only 不进入第一轮；
6. 强平路径使用 Bitget 历史 mark candle，不再完全依赖 Binance mark price；
7. 历史 funding 使用 Binance 代理 + Bitget 90 天重叠校验；
8. 量化账户使用完整 6bps Taker，返佣只做主账户外部现金流；
9. 所有新试验进入独立 trial scope，不修改 H5 DSR；
10. 空头 overlay 必须同时改善回撤和 Sharpe，不能只看收益；
11. 默认杠杆从 1.5x 下调到 **1.25x**；1.5x/2.0x 只做压力（与第 1 条一致）；
12. 明确区分账户 gross、仓位杠杆和强平距离，新增保证金率公式；
13. 资金费代理增加符号一致率、相关性、中位/95 分位误差阈值；
14. 项目内空头诊断没有通过 MDD kill criterion，只作为 Phase 3 的动机，不作为上线依据；
15. 新增 shadow → micro-live → scale 的上线阶梯，micro-live 不能绕过 robustness gate。

## 9. 数据缺口

| 缺口 | 影响 | 当前处理 |
|---|---|---|
| Bitget 历史 funding 只有约 90 天 | 2022–2026 funding 不精确 | v2 funding 取精确 90 天；Binance 代理未通过重叠验证（§5.6.4），只能作压力带 |
| Bitget mark candle 需要逐币覆盖审计 | 新币/下架/迁移可能缺口 | Phase 1 逐币审计 |
| 秒级 mark 和 liquidation tape 不易获得 | 小时级可能低估 cascade | 强平滑点压力 + 5/10bps |
| 历史 position tier 可能变化 | maintenance margin 不精确 | 当前 tier + 保守 buffer |
| 历史 funding interval 可能变化 | 8h 假设会错 | 使用 contract fundInterval + 实际 timestamp |
| 60% 返佣到账延迟 | 量化账户不享受复利 | 主账户外部现金流 |

## 10. 试验预算

主试验：

- `PR2026-10-D-L125`
- `PR2026-10-D-L150`
- `PR2026-10-D-L200`
- `PR2026-10-D-SBTC25`
- `PR2026-10-D-SBTC50`
- `PR2026-10-D-SWEAK25`
- `PR2026-10-D-SWEAK50`

本轮预注册 **7 个主试验 + 4 个邻域，共 11 个**：4 个邻域包括 BTC/weakest 的 20% stop 变体，以及 1.25x 在 50bps/100bps 成本下的压力变体。所有 trials 必须进入 append-only ledger；任何事后新增变体都会增加 N，不能只报告胜者。

## 11. 推荐下一步

1. 负责人审阅设计稿和本研究报告；
2. 把 11 个 pre-registered trials 写入 trial ledger；
3. 增加独立 `Derivatives Track` AGENTS 章节（仅在负责人批准后）；
4. 全量下载 Bitget 2022+ mark/index/market 1H candles 并做覆盖审计；
5. 解决 historical funding 数据源：继续寻找更可靠的 Bitget 历史 funding，或把 proxy 明确降级为压力带；
6. 实现 isolated margin + funding + liquidation 引擎，funding attribution 必须标注来源；
7. 先跑 1.25x long-only，1.5x/2.0x 只做压力；
8. long-only 通过后再跑 BTC short overlay；
9. 最后才考虑 weakest-Top20 short；
10. 通过 Phase 5 的 shadow/micro-live/scale 阶梯后才考虑真实资金。

## 12. Phase 2 项目内更新（2026-10-09）

### 12.1 引擎

已实现并测试：

- `src/atlas20/derivatives/margin.py`：isolated-margin 强平价、强平距离、初始保证金率；
- `src/atlas20/derivatives/engine.py`：小时 mark OHLC、T+1 +3h 执行、逐结算点 funding、小时级强平、差分调仓、手续费/滑点/强平事件台账；
- `src/atlas20/derivatives/signals.py`：H5 long 缩放、BTC 200D MA + 30D return 熊市确认、funding filter、weakest-Top20 short；
- `src/atlas20/derivatives/data.py`：Bitget mark/funding 与 Binance funding proxy 加载。

### 12.2 1.0x 校验的否定结果

使用 Binance/Gate 1h mark 代理做 Phase 2 诊断（不是 Bitget 结果）：

- H5 全池现货 @20bps：21.47x，Sharpe 1.684，MDD -37.75%；
- 限制到代理有 mark 的同一资产池：18.22x，Sharpe 1.723，MDD -25.31%；
- 原设计 30% long buffer 的 isolated-margin 1.0x：15.67x，Sharpe 1.623，MDD -26.20%，**4 次强平**。

强平事件说明原设计公式 `long_margin_ratio = 0.30 + MMR + fee_buffer` 在 H5 的 1–2 币集中持仓上不足；这不是收益略低，而是直接违反“1.0x 不得强平”的引擎验收。该规则被否决。

### 12.3 保证金校准

预注册 8 个 calibration trials：long buffer 0.40/0.50/0.60/0.75 × leverage 1.0x/1.25x。结果显示：

- 40% buffer：1.0x 和 1.25x 各有 1 次强平；
- 50% buffer：两档均 0 次强平，是当前最小零强平点；
- 60% buffer：与 50% 结果相同；
- 75% buffer：1.25x 下受 85% 最大保证金占用约束，实际 gross 降到 1.124x，收益略低、MDD 略好。

因此 V2 默认 long buffer 修正为 50%；原 30% 的 11 个 trial 标记为 superseded，最终验收必须重新预注册 V2 并在 Bitget mark 数据上重跑。

### 12.4 V2 long-only 代理诊断（非最终结果）

50% long buffer、零 funding、20 bps、代理 mark：

| trial | leverage | 实际最大 gross | 强平 | 终值 | Sharpe | MDD |
|---|---:|---:|---:|---:|---:|---:|
| L125-V2 | 1.25x | 1.281x | 0 | 27.16x | 1.618 | -32.10% |
| L150-V2 | 1.50x | 1.574x | 0 | 45.43x | 1.617 | -37.70% |
| L200-V2 | 2.00x | 1.758x | 0 | 107.38x | 1.627 | -45.03% |

L125-V2 的成本压力（代理 mark、零 funding）如下：

| 成本 | 终值 | Sharpe | MDD | H5 同成本终值 | 终值比 | Sharpe 比 |
|---:|---:|---:|---:|---:|---:|---:|
| 6 bps | 31.84x | 1.685 | -29.99% | 25.30x | 1.258 | 0.956 |
| 8 bps | 31.12x | 1.675 | -30.29% | 24.71x | 1.259 | 0.957 |
| 11 bps | 30.08x | 1.661 | -30.75% | 23.86x | 1.261 | 0.958 |
| 20 bps | 27.16x | 1.618 | -32.10% | 21.47x | 1.265 | 0.961 |
| 50 bps | 19.30x | 1.475 | -36.42% | 15.10x | 1.278 | 0.973 |
| 100 bps | 10.91x | 1.236 | -43.53% | 8.39x | 1.300 | 1.001 |

代理诊断下，L125-V2 全部成本无强平，MDD < 50%，终值 >= 1.20 × H5，Sharpe >= 0.90 × H5；但这不是 Bitget 结果，不能用于上线。

这些数字仅证明保证金规则修正方向；它们使用代理 mark、零 funding、尚未做 Bitget mark、真实 funding、short overlay、multiple-testing 和 OOS。任何上线结论都不成立。

### 12.5 空头 overlay 代理诊断：被拒

在 V2 50% long buffer 之上，使用代理 mark 和 Binance funding proxy 跑 SBTC25/SBTC50/SWEAK25/SWEAK50，20 bps：

| trial | 终值 | Sharpe | MDD | 强平 |
|---|---:|---:|---:|---:|
| SBTC25 | 27.14x | 1.430 | -32.10% | 0 |
| SBTC50 | 29.00x | 1.442 | -32.10% | 0 |
| SWEAK25 | 27.58x | 1.429 | -32.10% | 0 |
| SWEAK50 | 30.16x | 1.434 | -32.94% | 0 |

对比 L125-V2 基准（27.16x、Sharpe 1.618、MDD -32.10%），四个空头 overlay 都显著降低 Sharpe，且没有达到“MDD 改善至少 5 个百分点”的门槛。因此 Phase 3 空头 overlay 在当前代理诊断下被拒绝。由于 funding 代理未通过 Phase 1 重叠门槛，这一结论仍只是实现层诊断，不能替代未来 Bitget 精确 funding 的独立预注册试验。
