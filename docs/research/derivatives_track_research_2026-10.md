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

### 12.1 引擎与首个口径修正

已实现并测试：

- `src/atlas20/derivatives/margin.py`：isolated-margin 强平价、强平距离、初始保证金率；
- `src/atlas20/derivatives/engine.py`：小时 mark OHLC、T+1 +3h 执行、逐结算点 funding、小时级强平、差分调仓、手续费/滑点/强平事件台账；可选 `funding_intervals_hours` 会对“持仓超过合约 funding 间隔但没有结算记录”直接 fail closed，避免缺失 funding 被静默按 0 计；
- `src/atlas20/derivatives/signals.py`：H5 long 缩放、BTC 200D MA + 30D return 熊市确认、funding filter、weakest-Top20 short；
- `src/atlas20/derivatives/data.py`：Bitget mark/funding 与 Binance funding proxy 加载。

初版 Phase 2 报告直接对 mark/funding 数据源的全量时间轴做回测，产生了两类污染：

1. 主样本开始前的预热/零收益被计入 Sharpe 和 CAGR；
2. mark 数据源在 2026-09-21 之后仍有最新批次，持仓被静默持续到数据末尾，导致 2026-09-22 起的真样本外路径进入主样本结果。

引擎现已加入可选 `start_time`/`end_time`，区间为左闭右开；窗口外的 target 不执行，窗口外的小时 mark 不进入 equity path。所有 Phase 2 结果已按 **2022-01-01 00:00 UTC 至 2026-09-21 23:00 UTC** 重跑。以下数字替代本文件此前记录的所有 Phase 2 结果。

Bitget 运行器同时加入 funding 压力接口：`--funding-stress long-adverse` 只保留对多头不利的正 funding（把负 funding 置零），`--funding-stress short-adverse` 只保留对空头不利的负 funding；`--funding-multiplier` 可把该不利 funding 放大 2x/3x。它仍是 Binance proxy 压力带，不是 Bitget 精确历史。

### 12.2 1.0x 校验的否定结果（修正窗口、+3h 对 +3h）

使用 Binance/Gate 1h mark 代理做 Phase 2 诊断（不是 Bitget 结果）；现货基准也改为同成本、同 +3h 成交的 H5，不再拿 close-fill 的 21.47x 与 +3h 衍生品路径比较：

- H5 全池现货 @20bps、+3h：19.5253x，Sharpe 1.6231，MDD -36.97%；
- 限制到代理有 mark 的同一资产池、@20bps、+3h：15.2974x，Sharpe 1.6258，MDD -26.29%；
- 原设计 30% long buffer 的 isolated-margin 1.0x：15.4917x，Sharpe 1.6312，MDD -26.20%，**4 次强平**；
- V2 50% long buffer 的 isolated-margin 1.0x：15.3380x，Sharpe 1.6267，MDD -26.20%，**0 次强平**。

强平事件说明原设计公式 `long_margin_ratio = 0.30 + MMR + fee_buffer` 在 H5 的 1–2 币集中持仓上不足；这不是收益略低，而是直接违反“1.0x 不得强平”的引擎验收。该规则被否决。

### 12.3 保证金校准（修正窗口）

预注册 8 个 calibration trials：long buffer 0.40/0.50/0.60/0.75 × leverage 1.0x/1.25x。结果显示：

| 规则 | leverage | 实际最大 gross | 强平 | 终值 | Sharpe | MDD |
|---|---:|---:|---:|---:|---:|---:|
| MB40 | 1.00x | 1.002x | 1 | 15.062x | 1.617 | -26.20% |
| MB50 | 1.00x | 1.002x | 0 | 15.338x | 1.627 | -26.20% |
| MB60 | 1.00x | 1.002x | 0 | 15.338x | 1.627 | -26.20% |
| MB75 | 1.00x | 1.002x | 0 | 15.338x | 1.627 | -26.20% |
| MB40 | 1.25x | 1.281x | 1 | 26.171x | 1.616 | -32.10% |
| MB50 | 1.25x | 1.281x | 0 | 26.782x | 1.626 | -32.10% |
| MB60 | 1.25x | 1.281x | 0 | 26.782x | 1.626 | -32.10% |
| MB75 | 1.25x | 1.124x | 0 | 26.582x | 1.636 | -30.80% |

- 40% buffer：1.0x 和 1.25x 各有 1 次强平；
- 50% buffer：两档均 0 次强平，是当前最小零强平点；
- 60% buffer：与 50% 结果相同；
- 75% buffer 在 1.25x 下受 85% 最大保证金占用约束，实际 gross 降到 1.124x，收益略低、MDD 略好。

因此 V2 默认 long buffer 修正为 50%；原 30% 的 trial 标记为 superseded，最终验收必须重新预注册 V2 并在 Bitget mark 数据上重跑。

### 12.4 V2 long-only 代理诊断（修正窗口，非最终结果）

50% long buffer、零 funding、20 bps、+3h、代理 mark：

| trial | leverage | 实际最大 gross | 强平 | 终值 | Sharpe | MDD |
|---|---:|---:|---:|---:|---:|---:|
| L125-V2 | 1.25x | 1.281x | 0 | 26.782x | 1.626 | -32.10% |
| L150-V2 | 1.50x | 1.574x | 0 | 44.674x | 1.625 | -37.70% |
| L200-V2 | 2.00x | 1.758x | 0 | 105.010x | 1.634 | -45.03% |

L125-V2 的成本压力与 **H5 同成本 +3h 现货基准**如下（`scripts/compare_derivatives_proxy_costs.py`）：

| 成本 | 终值 | Sharpe | MDD | H5 +3h 终值 | H5 Sharpe | H5 MDD | 终值比 | Sharpe 比 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 6 bps | 31.395x | 1.693 | -29.99% | 23.016x | 1.700 | -35.22% | 1.364 | 0.996 |
| 8 bps | 30.691x | 1.684 | -30.29% | 22.482x | 1.689 | -35.47% | 1.365 | 0.997 |
| 11 bps | 29.663x | 1.669 | -30.75% | 21.703x | 1.673 | -35.85% | 1.367 | 0.998 |
| 20 bps | 26.782x | 1.626 | -32.10% | 19.525x | 1.623 | -36.97% | 1.372 | 1.002 |
| 50 bps | 19.039x | 1.482 | -36.42% | 13.721x | 1.457 | -40.56% | 1.388 | 1.017 |
| 100 bps | 10.760x | 1.240 | -43.53% | 7.614x | 1.178 | -46.24% | 1.413 | 1.052 |

在修正窗口、代理 mark、零 funding、+3h 的诊断下，L125-V2 全部成本无强平，MDD < 50%，终值 >= 1.36 × H5，Sharpe 与 H5 基本持平或更高。这个改善仍不能用于上线：mark 是代理、funding 为零、Bitget 合约可用性尚未全量审计、完整 multiple-testing 和 12 个月 OOS 均未完成。

### 12.5 空头 overlay 代理诊断：仍被拒，拒绝理由修正

在 V2 50% long buffer 之上，使用代理 mark 和 Binance funding proxy 跑 SBTC25/SBTC50/SWEAK25/SWEAK50，20 bps、+3h、修正窗口：

| trial | 终值 | Sharpe | MDD | 强平 |
|---|---:|---:|---:|---:|
| SBTC25 | 26.793x | 1.624 | -32.10% | 0 |
| SBTC50 | 28.626x | 1.638 | -32.10% | 0 |
| SWEAK25 | 27.225x | 1.623 | -32.10% | 0 |
| SWEAK50 | 29.778x | 1.629 | -32.94% | 0 |

对比 L125-V2 基准（26.782x、Sharpe 1.626、MDD -32.10%），修正后空头 overlay **并没有 Sharpe 大幅下降**；SBTC50 和 SWEAK50 的 Sharpe 略高。真正的失败点是 **MDD 完全没有改善**，SWEAK50 还略差；预注册 kill criterion 要求 MDD 至少改善 5 个百分点且 Sharpe 不低于 long-only，因此四个空头仍全部被拒。

由于 funding 代理未通过 Phase 1 重叠门槛，这一结论仍只是实现层诊断，不能替代未来 Bitget 精确 funding 的独立预注册试验。

### 12.6 multiple-testing 代理诊断与尚未闭合的缺口

已新增：

- `scripts/build_derivatives_candidate_returns.py`：严格要求所有候选覆盖完全一致的日期，禁止静默内连接掉不同样本；
- `scripts/evaluate_derivatives_candidates.py`：Deflated Sharpe、White Reality Check、CSCV/PBO；
- `reports/derivatives_track_proxy_multiple_testing/`。

当前 20 bps、+3h、2022-01-01 至 2026-09-21 的 7 个可用候选矩阵：

- Deflated Sharpe（记账 N=11）：约 0.99997；
- White Reality Check p≈0.00699；
- PBO/CSCV≈0.960，最常被选中的代理候选为 SWEAK50（309/924）。

**不能据此宣布 multiple-testing 通过。** design 稿要求 PBO 矩阵覆盖 11 个预注册 trial；目前 stop20 变体仍未实现/未跑，成本档位也不是独立策略候选。7 个高度相关的 long/short 变体给出的 PBO≈0.96 是明确的选参不稳定警告，不能用 DSR 的高值覆盖。正式 gate 必须在 Bitget mark、真实 funding、完整候选矩阵和 12 个月 OOS 上重跑。

### 12.7 复现命令

```bash
# 并行下载完成后，把两个 shard 严格合并为一个回测数据目录
.venv/bin/python scripts/merge_bitget_derivatives_shards.py \
    --shard data/raw/bitget_derivatives/parallel_<stamp>/chunk_0 \
    --shard data/raw/bitget_derivatives/parallel_<stamp>/chunk_1 \
    --output-dir data/raw/bitget_derivatives/merged

# Bitget mark 上的 V2 long-only 矩阵：1.25/1.5/2.0x × zero/Binance funding 压力
.venv/bin/python scripts/run_bitget_mark_matrix.py \
    --raw-dir data/raw/bitget_derivatives/merged \
    --output-dir reports/derivatives_track_bitget_mark

# 30% buffer 的否定校验（修正窗口）与 50% buffer 的 V2 校验
.venv/bin/python scripts/validate_derivatives_engine.py \
    --long-buffer 0.30 --output-dir reports/derivatives_track_engine_validation
.venv/bin/python scripts/validate_derivatives_engine.py \
    --long-buffer 0.50 --output-dir reports/derivatives_track_engine_validation_v2

# 8 个保证金校准 trial
.venv/bin/python scripts/calibrate_derivatives_margin.py \
    --output-dir reports/derivatives_track_margin_calibration

# 6/8/11/20/50/100 bps 的 V2 成本压力
for cost in 6 8 11 20 50 100; do
  .venv/bin/python scripts/run_derivatives_proxy_trials.py --cost-bps "$cost" \
      --output-dir "reports/derivatives_track_proxy_trials_${cost}bps"
done

# 空头 overlay 与长期收益矩阵
.venv/bin/python scripts/run_derivatives_proxy_shorts.py \
    --output-dir reports/derivatives_track_proxy_shorts
.venv/bin/python scripts/build_derivatives_candidate_returns.py \
    --input reports/derivatives_track_proxy_trials_20bps/daily_returns.csv \
    --input reports/derivatives_track_proxy_shorts/daily_returns.csv \
    --output reports/derivatives_track_proxy_multiple_testing/candidate_returns.csv
.venv/bin/python scripts/evaluate_derivatives_candidates.py \
    --returns reports/derivatives_track_proxy_multiple_testing/candidate_returns.csv \
    --trial-count 11 --output-dir reports/derivatives_track_proxy_multiple_testing

# 与 H5 +3h 同成本对比
.venv/bin/python scripts/compare_derivatives_proxy_costs.py \
    --output-dir reports/derivatives_track_proxy_cost_comparison
```

### 12.8 Bitget 真实 mark 结果（2026-10-09，全量 mark）

§12.2–12.6 的结论全部建立在 Binance/Gate 1h mark **代理**上。本节用**真实 Bitget USDT-M mark 价格**重跑，是截至目前唯一可用于“Bitget mark 口径”的正式数字。代理数字不再作为该口径的证据，但作为数据源交叉验证保留。

#### 12.8.0 窗口与 funding 口径的两处修正（先于所有数字）

1. **窗口**：`run_derivatives_backtest.py` / `run_bitget_mark_matrix.py` 的 `--end-date` 之前被解释为 `end_date + 1 day` 的右端，导致 funding 结算时间戳把权益路径拖到 mark 数据之外（出现 1725 天的样本和“用 carry 价格估值”的 2026-09-21）。现在 `--end-date` 是**左闭右开的冻结窗口右端**，默认 `2026-09-21` = 样本在 2026-09-21 00:00 UTC 结束。所有 Bitget mark 结果统一为 **1724 个日收益（2022-01-01 → 2026-09-20，最后一根 mark 2026-09-20 23:00 开盘 / 09-21 00:00 收盘）**，与现货主样本一致。
2. **funding 缺失**：`skip`（把缺失结算当作 0）对多头是**乐观**口径。引擎新增两个显式政策并在结算时先判断该资产按其 `fund_interval` 是否**本就该结算**（避免在更快的结算网格上重复收费）：
   - `carry_last`：该结算缺失时沿用上一次已观测费率；无历史或超过 `funding_carry_max_hours`（默认 24h）则 fail closed；
   - `stress_median`：缺失（含该资产在持仓期完全没有 funding 历史，例如 TON 的 Binance funding 直到 2026-07 才开始）时，用**同一时刻全 funding 池的正向费率中位数**计入多头成本——这是保守上界，不是精确历史。

数据与区间：

- mark 来源 `data/raw/bitget_derivatives/merged_20261009/`（88 个映射合约，MATIC/POL 共用 `POLUSDT`），下载 0 个 error window；审计见 `reports/derivatives_track_data_audit_full/`（88/102 coin 有合约，窗口覆盖 78%，新币晚上市属设计内，最大 gap 2h）。
- 执行口径：信号 UTC 日收盘、T+1 +3h 成交、isolated margin、逐小时 mark 强平检查、funding 在每次小时检查前结算、成本 20 bps 为判定档，另跑 6/8/11/50/100 bps。
- `dropped_target_rows` 为当日目标资产没有可执行 mark 的行数（新上市/退市边缘），引擎按无 mark 不建仓处理，未静默补价。

#### 12.8.1 零 funding 上界（真实 mark）

| trial | leverage | 实际最大 gross | 强平 | 终值 | Sharpe | MDD |
|---|---:|---:|---:|---:|---:|---:|
| L125 | 1.25x | 1.281x | 0 | **44.125x** | 1.769 | -40.72% |
| L150 | 1.50x | 1.575x | 0 | **80.084x** | 1.768 | -46.88% |
| L200 | 2.00x | 1.759x | 0 | **210.175x** | 1.770 | -53.95% |

与代理 mark 相比，Bitget mark 的 Sharpe 更高（1.63 → 1.77），MDD 更差（-32.10% → -40.72%）。零 funding 是**上界**，不是可上线假设。

#### 12.8.2 funding 口径：Bitget 精确历史不存在

- Bitget 官方 funding 历史只回溯约 90 天（`reports/derivatives_track_data_audit_full/funding_overlap.csv`：0/88 通过 2022 起的重叠门槛）；2022 起的精确 funding 在公开源上未找到。
- 因此 funding 只能用 **Binance funding proxy**（覆盖 88 个合约中的 49 个），并把结果标为压力带，不能标为“真实 funding 已计”。
- 限制到这 49 个资产后，零 funding 上界：L125 38.260x / Sharpe 1.730 / MDD -40.72%；L150 67.977x / 1.730 / -46.88%；L200 172.267x / 1.734 / -53.95%。

#### 12.8.3 funding 压力带（真实 mark，49 资产 funding 池）

`--funding-stress long-adverse` 只保留对多头不利的正 funding（负 funding 置零）再放大：

| trial | 缺失口径 | proxy 1x | 2x adverse | 3x adverse |
|---|---|---:|---:|---:|
| L125 | `skip`（乐观） | 34.874x | 28.921x | 25.140x |
| L125 | `stress_median`（保守） | **34.477x** | **28.266x** | **24.290x** |
| L150 | `skip`（乐观） | 60.843x | 48.625x | 41.113x |
| L150 | `stress_median`（保守） | **60.015x** | **47.311x** | **39.457x** |
| L200 | `skip`（乐观） | 149.251x | 111.488x | 89.643x |
| L200 | `stress_median`（保守） | **146.567x** | **107.511x** | **84.888x** |

`stress_median` 的 Sharpe：L125 1.689 / 1.609 / 1.548；L150 1.688 / 1.608 / 1.547；L200 1.692 / 1.610 / 1.548。全部 0 次强平。乐观口径相对保守口径的偏高为 **1.1%–5.3%**（杠杆越高、压力越大，偏得越多），这是 `skip` 被替换的直接理由。

#### 12.8.4 成本压力（L125，真实 mark，`skip` 口径，与 §12.4 同表）

| 成本 | 零 funding | 3x adverse funding | H5 +3h 同成本 | 零 funding / H5 | 3x adverse / H5 |
|---:|---:|---:|---:|---:|---:|
| 6 bps | 52.782x | 29.891x | 23.016x | 2.29 | 1.30 |
| 8 bps | 51.449x | 29.162x | 22.482x | 2.29 | 1.30 |
| 11 bps | 49.512x | 28.100x | 21.703x | 2.28 | 1.29 |
| 20 bps | 44.125x | 25.140x | 19.525x | 2.26 | 1.29 |
| 50 bps | 30.036x | 17.336x | 13.721x | 2.19 | 1.26 |
| 100 bps | 15.784x | 9.310x | 7.614x | 2.07 | 1.22 |

最保守的 (100 bps, 3x adverse) 组合仍有 9.310x，优于现货 H5 在 100 bps 的 7.614x。方向在全部成本档一致，无强平。该表用 `skip`；换成 `stress_median` 后同档位再低约 1%–5%。

#### 12.8.5 保证金校准在真实 mark 上复跑（取代 §12.3 的代理校准）

| buffer | leverage | 实际最大 gross | 强平 | 终值 | Sharpe | MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 0.40 | 1.00x | 1.002x | **1** | 22.691x | 1.761 | -33.96% |
| 0.40 | 1.25x | 1.281x | **1** | 43.107x | 1.760 | -40.72% |
| 0.50 | 1.00x | 1.002x | 0 | 23.111x | 1.770 | -33.96% |
| 0.50 | 1.25x | 1.281x | 0 | **44.125x** | 1.769 | -40.72% |
| 0.60 | 1.00x | 1.002x | 0 | 23.111x | 1.770 | -33.96% |
| 0.60 | 1.25x | 1.281x | 0 | 44.125x | 1.769 | -40.72% |
| 0.75 | 1.25x | 1.124x | 0 | 43.313x | 1.776 | -38.98% |

- 40% buffer 在真实 mark 上同样各档 1 次强平 → 拒绝；
- **50% 是最小的零强平点**，与代理校准的结论一致；
- 60% 与 50% 相同；75% 受 85% 最大保证金占用约束，实际 gross 降到 1.124x，收益略低、MDD 略好（更保守，可留作实盘选项）。

#### 12.8.6 multiple-testing（Bitget mark 候选族，取代代理 PBO）

`reports/derivatives_track_bitget_mark_multiple_testing/`：15 个真实 mark 候选（3 杠杆 × {零 funding、49 资产限制、Binance proxy、2x、3x adverse}），严格同日期 1724 天，记账 N=22（`preregistered_trials.csv` 中全部 `PR2026-10-D-*`）：

| 指标 | 结果 | 门槛 | 判定 |
|---|---:|---|---|
| Deflated Sharpe | 0.99974–0.99997（全候选） | ≥0.95 | 通过 |
| White Reality Check p | 0.0050 | ≤0.05 | 通过 |
| PBO / CSCV | **0.229**（最常选中 L200-zero，332/924；候选族已换成 stress_median funding 口径） | ≤0.50 | 通过 |

§12.6/§9.7 的代理 PBO≈0.960 来自一个把**已被拒绝的空头 overlay**计入的候选族；真实 mark 上这些空头不是候选，候选族是上线时真正要在其中做选择的杠杆 × funding 处理族。两次 PBO 度量的是不同问题，**不能**用 0.229 覆盖 0.960 的历史，只能记录为：在“已定 long-only 结构、只在杠杆与 funding 假设间选择”的决策上，选参不稳定警告消失；只要重新引入结构变化（空头/止损/其他规则），PBO 必须重算。

#### 12.8.7 仍未闭合的 gate（按 AGENTS.md，本轨道保持 provisional）

1. **真实 funding 缺失**：只有 Binance proxy + 放大压力带（`skip` 上界 / `stress_median` 保守），没有 2022 起的 Bitget 精确历史。
2. **pre-2022 压力窗口（已用代理 mark 扩展到 61 条路径，仍有残留）**：kill criterion 要求 2020-10..2021-12 无强平；Bitget mark 该区间只有 32 个合约，因此另用 Binance 1h 代理 mark 补齐（§12.8.9 更新）：64 条价格序列（63 个币，含 Binance+Gate 代理）、dropped rows 归零、0 次强平、最坏单腿 MAE -44.35% vs 强平距离 -51.01%（余量 6.66pp）。但代理是竞对现货盘、其中 3 条腿落在 Bitget 当年根本没上架的币上，门槛保持 partial-with-bounding。
3. **成交价口径**：全部用 mark 结算，尚未用 Bitget market（last）K 线做执行价敏感性；market 数据下载进行中（`data/raw/bitget_derivatives/market_20261009/`）。
4. **年度/滚动/最优年剔除**：尚未在真实 mark 上跑。
5. **12 个月真 OOS**：2026-09-22 起才起算，目前不足。

#### 12.8.8 日历稳健性（真实 mark，`reports/derivatives_track_bitget_mark_robustness/`）

同一 1724 天样本上的逐年收益（%，复利）：

| 年份 | L125-zero | L125 proxy | L125 3x adverse | L200-zero | BTC 买入持有 |
|---|---:|---:|---:|---:|---:|
| 2022 | -19.4 | -19.6 | -20.3 | -30.7 | **-65.3** |
| 2023 | 278.8 | 277.2 | 239.4 | 607.3 | 154.7 |
| 2024 | 131.6 | 119.4 | 93.0 | 212.0 | 111.6 |
| 2025 | 157.4 | 117.5 | 104.2 | 263.8 | -7.3 |
| 2026（至 09-20） | 142.3 | 141.0 | 135.7 | 277.7 | 约 -2 |

- **2022 是亏损年**（-19.4% 到 -30.7%，杠杆越高越差），不是靠“每一年都赚”堆出来的曲线；剔除 2022 后终值反而上升（L125 44.125x → 54.725x）。
- **最优年剔除**：去掉 2023 后 L125-zero 仍有 **11.648x**（Sharpe 1.591），3x adverse 口径 **7.407x**（Sharpe 1.364），L200-zero 29.717x。即“没有最好的一年”仍显著跑赢 BTC 的 1.74x。
- **一年滚动最坏**：全部候选的最差 365 天窗口都从 **2022-05-12** 开始；L125-zero 0.733x（约 -27%），3x adverse 0.705x，L200 0.610x。也就是说最坏的一整年仍然只是回撤三分之一左右，没有年度级别的本金毁灭。
- **同窗口 BTC 基准**：1.740x，Sharpe 0.099，MDD **-67.38%**；L125 即使在最保守的 3x adverse funding 档也是 24.290x / Sharpe 1.548 / MDD -42.49%。收益、Sharpe、回撤三项同时优于买入持有。

#### 12.8.9 pre-2022 压力窗口（2020-10-03 → 2022-01-01）：部分通过，覆盖率是限制

kill criterion 要求 2020-10..2021-12 无强平。Bitget mark 该区间的下载已完成（`data/raw/bitget_derivatives/merged_pre2022_20261009/`），但**合约历史本身就是限制**：

- 32 个合约有该区间数据，其中只有 14 个覆盖完整 2020-10-01 → 2021-12-31（BTC/ETH/ADA/BNB/BCH/DOT/ETC/LINK/LTC/SUSHI/TRX/UNI/XRP/XTZ）；其余按 Bitget 实际上线时间分批出现（如 SOL 2021-07-22、AXS/AVAX/THETA 2021-09-23、SHIB 2021-11-26、NEAR/EGLD 2021-12-22）。
- 结果（零 funding、20 bps、+3h、`--min-mark-assets 10`）：

| trial | 强平 | 实际最大 gross | 终值 | Sharpe | MDD |
|---|---:|---:|---:|---:|---:|
| L125 | 0 | 0.726x | 0.969x | 0.015 | -20.62% |
| L150 | 0 | 0.869x | 0.953x | 0.008 | -24.65% |
| L200 | 0 | 1.207x | 0.909x | -0.008 | -32.54% |

- **通过的部分**：在能被交易的资产上，整段牛市里 gross 从未超过 1.21x，没有任何强平，最大回撤 -20.6% ~ -32.5%（对应 2021-05 与 2021-11 之后的熊段）。
- **不通过的部分（诚实标注）**：`dropped_target_rows=199`，即策略当年想持有的很多 Top20 币（LUNA、MANA、SAND、GALA、CRV、EGLD、ICP 等）在 Bitget 上没有该区间的 mark，被强制降为现金。所以“没有强平”是**在受限资产池上的结论**，不能外推成“策略在该区间的最坏情况没有强平风险”。该门槛记为 **partial**，不是 pass。
**2026-10-09 更新：用代理 mark 把覆盖率从 32 扩到 64 条序列（`reports/derivatives_track_pre2022_proxy_stress/`）**

Binance 1h 预 2022 数据（`data/raw/binance_1h_pre2022/`，62 个币）加上 Gate 归档补下的 CRO/WAVES（`data/raw/gate_1h_pre2022/`）就绪后，`scripts/build_pre2022_proxy_marks.py` 构建了一棵**带标注的代理树**：Bitget mark 行永不被覆盖，代理行只接在合约首个 Bitget mark 之前（或在该币 Bitget 完全没有数据时单独使用）。18 个拼接缝的 |基差| 中位 0.502%、最差 2.040%（NEAR -2.04%），不足以制造假强平；Bitget 从未上架的 14 个币用合成 symbol 写入（其中 7 个有代理数据）；缺失小时用引擎 `carry` 策略（上限 3h），共 65 根小时线被 carry。

| 口径 | 可用资产 | dropped rows | 强平 | L125 终值 | L125 MDD | 最坏单腿 MAE |
|---|---:|---:|---:|---:|---:|---:|
| Bitget-only（上表） | 32 | 199 | 0 | 0.969x | -20.62% | — |
| + 代理 mark | **64 序列 / 63 币**（14 纯 Bitget / 18 拼接 / 31 纯代理） | **0** | **0**（L125/L150/L200） | 4.296x | -27.76% | **-44.35%** |

- 45 条腿按价格来源分类：纯 Bitget 15 腿（最坏 MAE -26.50%）、拼接 2 腿（-36.56%）、纯代理 28 腿（最坏 **-44.35%**）；其中 3 条腿落在 Bitget 当年没上架的币上（合成 symbol），实盘口径应为现金。最坏腿是 DOGE 2021-01-30 → 2021-03-03（代理价），距 -51.01% 强平线还有 **6.66pp**——比 2022–2026 主样本最坏腿（XRP -41.14%）更紧，但依然未击穿。
- 该窗口是 2021 牛市（AGENTS.md 明确：2020-10..2021-12 只作压力检查、不是 headline 业绩），终值仅作 kill-criterion 记录；盈亏集中在 SHIB（31.4%）与 DOGE（16.4%），L125/L150/L200 全部零强平。
- **诚实边界**：代理是 Binance/Gate 现货 tape，不是 Bitget mark；真正会强平的是 Bitget。39 个币在该窗口尚未存在（天然无数据），funding 按零计。因此这条门槛记为 **partial-with-bounding**（在可用路径上 0 强平、最坏余量 6.66pp），而不是完全 pass。

#### 12.8.10 逐 legs 的强平余量（`reports/derivatives_track_bitget_mark_leg_risk/`）

“0 次强平”本身不是证据，问题是**离强平有多远**。`scripts/analyze_derivatives_leg_risk.py` 把每一笔已开仓 legs 的 mark low 路径与它自己的强平价对齐：

- isolated margin 下多头的强平价距入场价恒为 **-51.01%**（= long buffer 0.50 + fee buffer 0.005 + MMR 0.01 对应的保证金耗尽点），与实际杠杆无关——这是隔离保证金的关键性质：放大 gross 不改变单腿的强平阈值，只改变同时爆掉的腿数。
- 2022-01-01 → 2026-09-21 共 **137 笔 legs**：最强不利偏移（MAE）**-41.14%**（XRP，2025-01-16 → 2025-02-06），中位数 **-7.51%**；只有 1 笔超过 -40%，4 笔超过 -35%。即最坏历史 legs 距离强平还有 **约 9.9 个百分点**。
- **交叉验证 40% buffer 的失败原因**：把 buffer 降到 0.40，强平距离变成 **-40.91%**，而那条 XRP legs 的 -41.14% 正好击穿它——脚本独立复现出“1 次强平”，与 §12.8.5 的校准结果完全一致。这解释了 50% buffer 不是拍的：它就是历史最坏 legs 加上约 10pp 余量。
- 同一 MAE 在 1.25x/1.5x/2.0x 下完全相同，进一步说明三个杠杆档的差异只来自收益放大与多腿同时爆仓的尾部，而不是单腿风险变差。

#### 12.8.11 样本外跟踪已启动（`reports/derivatives_track_oos_2026/`）

- 冻结规格 `PR2026-10-D-L125-V2`（H5 long book × 1.25、isolated margin、50% long buffer、20 bps、T+1 +3h 成交）在 **2026-09-22 起**进入样本外记录。脚本 `scripts/run_derivatives_oos.py` 只做三件事：用完整历史重建信号（保留相位锚点）、把冻结规格换成每日目标仓位、把目标仓位换算成人类可读的下单说明；**没有任何参数在样本外被选择或调整**。
- 数据：`data/raw/bitget_derivatives/merged_oos_20261009/`（88 个合约，2026-09-21 00:00 → 2026-10-09 09:00，逐小时 mark，438 根/合约）。
- 结果（17 个完整日，2026-09-22 → 2026-10-08，零 funding 上界）：**0.9598x**（-4.02%），MDD -10.81%，Sharpe -0.86（17 天样本，Sharpe 无统计意义，只作记录）。同期现货 H5 +3h/20bps **0.9692x**，BTC 约 **0.9431x**。衍生品路径的日收益约为现货路径的 1.20–1.32 倍，与 1.25x 杠杆一致。
- funding 在该窗口同样没有 Bitget 精确历史，因此上界为“零 funding”；方向对多头偏乐观。样本外尚未出现强平。
- 该段窗口**不足以**满足 12 个月 OOS 门槛，只是把计时器启动起来；后续每新增一个完整 day 都要用同一命令追加。
- **2026-10-09 代码审计发现并修复：样本外时钟曾静默停摆。** 每日下载脚本按「窗口起点」缓存（`state.json` 里该窗口被标记 complete 后永久跳过），而 Makefile 用的是固定起点 `2026-09-21`，于是 2026-10-09 之后 mark 数据不再向后延伸（审计时数据停在 09:00 UTC、实际已 16:00 UTC），样本外账本与 Telegram 信号都会冻结在旧日期。修复：① Makefile 改用滚动起点（今天 −3 天 → 明天）；② `run_derivatives_oos.py` 增加 staleness 守卫（默认 30h，超时失败，`--allow-stale` 可回放）；③ 信号日封顶在最近一个已收盘 UTC 日，避免用到未收盘的当日 bar。修复后数据恢复到 1.1h 内新鲜。

#### 12.8.12 funding 压力到多少才吃掉优势（`stress_median`，真实 mark，L125）

把 Binance proxy 的“对多头不利”费率整体放大，看优势在哪个倍数消失（同一候选的敏感性档，不是新 trial，记法与成本档位相同）：

| funding 倍数 | 终值 | Sharpe | MDD | 累计 funding | 强平 |
|---:|---:|---:|---:|---:|---:|
| 1x（历史） | 34.477x | 1.689 | -40.65% | -0.66 | 0 |
| 2x | 28.266x | 1.609 | -41.91% | -1.44 | 0 |
| 3x | 24.290x | 1.548 | -42.49% | -1.95 | 0 |
| 4x | 20.870x | 1.487 | -43.08% | -2.33 | 0 |
| 5x | 17.929x | 1.426 | -43.79% | -2.63 | 0 |
| 6x | 15.400x | 1.364 | -44.49% | -2.85 | 0 |
| 8x | 11.357x | 1.241 | -45.86% | -3.12 | 0 |

- 同成本现货 H5 +3h @20bps 为 **19.525x / Sharpe 1.623 / MDD -36.97%**。
- **收益优势的盈亏平衡点在 4x–5x 之间（约 4.3x）**：只有当 Bitget 的历史多头 funding 比 Binance 记录还要差 4 倍以上时，1.25x 衍生品路径才会输给现货路径。
- Sharpe 优势的平衡点更低（约 1.5x），MDD 则从一开始就更差（-40.7% vs -37.0%），这与 1.25x 杠杆的预期一致。
- 全程零强平；资金费累计成本即使在 8x 压力下也只有约 3.1 个 NAV 单位（起点 1.0），说明单币集中持仓的 funding 拖累是渐进的，不是断崖式的。

#### 12.8.13 市场状态分解（`reports/derivatives_track_bitget_mark_regime/`）

用项目既有的 regime 框架（`config/base.yaml` 的 bull 定义，且**收益日使用前一收盘的状态标签**，避免把当天下跌归到当天标记的 non-bull）：

| 策略 | 状态 | 天数 | 区间终值 | 年化 | Sharpe | MDD |
|---|---|---:|---:|---:|---:|---:|
| L125-zero | bull | 806 | 39.734x | 429.9% | 2.603 | -40.72% |
| L125-zero | non_bull | 918 | 1.111x | 4.3% | 0.313 | -24.13% |
| L125 3x adverse | bull | 806 | 22.851x | 312.5% | 2.292 | -42.49% |
| L125 3x adverse | non_bull | 918 | 1.100x | 3.9% | 0.293 | -24.50% |
| L200-zero | bull | 806 | 186.735x | 967.9% | 2.613 | -53.95% |
| L200-zero | non_bull | 918 | 1.126x | 4.8% | 0.303 | -37.20% |
| BTC 买入持有 | bull | 806 | 3.060x | 65.9% | 1.343 | -26.93% |
| BTC 买入持有 | non_bull | 918 | **0.573x** | -19.9% | -0.126 | **-62.12%** |

- 收益几乎全部来自 bull 状态，这部分是预期内的（策略本质是动量多头）。
- 真正有价值的一条：**non_bull 的 918 天里策略基本走平（+11.1%）而 BTC 亏 42.7%**，且 MDD 只有 -24.1% 对 BTC 的 -62.1%。也就是说这套东西在熊市里的作用是“防守 + 微幅正收益”，而不是靠熊市赚钱。
- 三条杠杆档在 non_bull 表现几乎一样（1.10x–1.13x），因为熊市里 gross 通常很低；杠杆只在 bull 状态放大结果。

#### 12.8.14 资产集中度：44x 里有多少是 ZEC（触发 AGENTS.md 的单一资产条款）

`reports/derivatives_track_bitget_mark_leg_risk/asset_pnl.csv` 按资产归因已实现盈亏（平均成本、含手续费），再用“把该资产从可交易集合中移除、权重降为现金（不换仓）”做反事实：

| 口径 | L125 | L150 | L200 | Sharpe（L125） |
|---|---:|---:|---:|---:|
| 全样本 | 44.125x | 80.084x | 210.175x | 1.769 |
| 去掉 `zcash` | **20.295x** | 31.995x | 63.485x | 1.511 |
| 去掉 `zcash` + `hyperliquid` | **12.429x** | 17.951x | 32.205x | 1.333 |

- L200 口径下 `zcash` 一家占已实现盈亏的 **59.6%**，`hyperliquid` 占 15.4%；MDD 在去掉它们后**完全不变**（-40.72%），说明集中发生在收益端而不是风险端。
- 这与现货轨 §00.8 的结论是同一件事：动量组合的收益本来就来少数币的极端行情（§00.8 记录现货口径前 5 个币贡献 90.31%、去掉前 3 只剩 2.07x）。衍生品轨只是把同样的集中度乘上了杠杆，**因此同样触发 AGENTS.md 的「不能依赖单一资产」条款**，是本轨道必须保持 provisional 的又一条独立理由。
- 去掉 ZEC+HYPE 后 1.25x 仍有 12.429x（BTC 同窗口 1.740x），说明“策略完全靠一个币”不成立；但它也说明：**44x 这个头条数字的一半来自一个币的行情**，任何上线决策都必须按“去掉 ZEC 后约 20x / 去掉 ZEC+HYPE 后约 12x”的预期来规划风险。
- 该反事实只回答“收益从哪来”，不是可交易策略（事前不知道哪个币会赢），也不能作为挑选资产的依据。

#### 12.8.15 风险尺度与“3% 资金”口径（L125，真实 mark）

用户计划只投入总资金的 3%，且衍生品用 isolated margin（单腿最多亏掉该腿保证金）。把 L125 的历史尾部换算成总资金口径：

| 口径 | 零 funding | 3x adverse funding | 折算到 3% 资金 |
|---|---:|---:|---:|
| 最大回撤 | -40.72% | -42.49% | 总资金的 **-1.27%** |
| 最差 7 天 | -18.77% | -19.08% | -0.57% |
| 最差 30 天 | -22.41% | -23.10% | -0.69% |
| 最差 90 天 | -38.57% | -40.24% | -1.21% |
| 最差 365 天 | -26.66% | -29.51% | -0.89% |

- 也就是说：按 3% 资金、1.25x、50% long buffer 运行，**历史上最深的一段亏损约占总资金 1.3%**；即使假设整个量化账户归零（隔离保证金下需要极端连环强平），损失上限是总资金 3%。
- 与之对照，同一窗口 BTC 买入持有的最大回撤是 -67.38%——若把 3% 全部买 BTC，对应总资金 -2.0%。
- 这个尺度是"可以上线试一试"的依据之一，但它**不能**替代真实 funding、成交价口径与 12 个月 OOS 三道未闭合的门槛。

## 13. 上线路线（2026-10-09 状态）

按 AGENTS.md，衍生品轨**不是** live-ready。这一节把“还差什么”列成可执行清单，任何一项不通过都不能上真钱。规范永远冻结在 `PR2026-10-D-L125-V2`（= H5 long book × 1.25、isolated margin、50% long buffer、T+1 +3h、20 bps、60% 返佣不计入量化 NAV）。

| # | 门槛 | 状态 | 当前证据 | 还差什么 |
|---|---|---|---|---|
| 1 | 20x 以上收益、显著跑赢 BTC | **通过（头条口径）** | 44.125x（零 funding）/ 24.290x（3x adverse）/ 12.429x（去掉 ZEC+HYPE）；BTC 1.740x | —（但见 #5、#6） |
| 2 | 无强平 | **通过** | 1.25x/1.5x/2.0x 全样本 0 次强平；137 腿最坏 MAE -41.14% vs 强平距离 -51.01% | — |
| 3 | 成本压力 6/8/11/20/50/100 bps | **通过** | 各档方向一致、无强平，最保守组合 9.310x > 现货 H5 100bps 的 7.614x | — |
| 4 | multiple-testing（DSR/RC/PBO） | **通过（该口径）** | DSR 0.9997+、RC p=0.0050、PBO 0.229（结构已定的 long-only 候选族） | 任何新增结构变化都必须重算 |
| 5 | 单一资产依赖 | **设计属性（负责人确认）** | 轮动重仓最强币是策略本体；机制有正超额（+0.343%/日、前 20% 命中率 33.1% vs 随机 20%）、但 t=1.81 不显著且 74.4% 盈亏来自前 5 条腿（§12.8.18–19） | 残差风险=右尾依赖；用仓位规模（3%）与 50% buffer 控制，不用分散化（H4 已证伪） |
| 6 | 参数邻域 / 年度 / 滚动 / 状态 | **通过（除 #5）** | buffer 0.40 强平、0.50 起零强平；去最优年仍有 11.648x；最差滚动年 0.733x；non_bull 1.111x vs BTC 0.573x | — |
| 7 | 真实 funding | **部分闭合** | 90 天重叠窗口实测 Bitget/Binance 总 funding 比 1.59x（§12.8.16）；按实测水平 L125 = 30.078x；压力 24.290x（3x）；盈亏平衡约 4.3x | 需要 Bitget 2022 起 funding 归档才能完全闭合，否则永久标注 proxy 水平校准 |
| 8 | 成交价口径（market vs mark） | **通过** | 87 合约 market K 线；9 个组合下 market 成交与 mark 成交差 0.14%–0.29%，MDD 不变，0 次 downgrade（§12.8.17） | — |
| 9 | pre-2022 压力窗口 | **partial-with-bounding** | Bitget-only：32 合约/199 行降现金；代理 mark 扩展后 64 序列、dropped 归零、0 强平、最坏腿 MAE -44.35%（余量 6.66pp，§12.8.9） | 代理为竞对现货 tape；3 腿落在 Bitget 未上架币；39 币当时不存在；funding=0 |
| 10 | 12 个月真样本外 | **进行中（17/365 天）** | 2026-09-22 → 10-08：0.9598x，MDD -10.81%，日波动为现货的 1.20–1.32 倍 | 继续按日追加约 11 个月 |

**上线前的最小可执行动作**（执行细节见 `docs/operations/derivatives_live_runbook.md`）：

1. 等 market K 线下载完成 → 跑 `--fill-price-source market`，确认成交价口径不改变结论（或量化差异）。
2. （已完成）成交价敏感性已闭合；用同一个冻结规格继续每日样本外记录（`scripts/run_derivatives_oos.py`），并在 Telegram 日报里同时报“目标持仓 + 调仓 + 去 ZEC/HYPE 的集中度提示”。
3. 资金规模按 3% 总资金、1.25x、单腿 isolated、50% buffer 执行；预期最深一段亏损约总资金 -1.27%，理论上限 -3%。
4. 若 market 口径与 mark 口径差异 > 20% 终值，或 funding 压力超过 4.3x 才保本，则不上线，回到研究。

#### 12.8.16 funding proxy 的水平校准：Bitget 实际约为 Binance 的 1.59 倍

§12.8.2 只能证明"Bitget 精确历史不存在"，但不能说明代理**偏多少**。Bitget 的公开 funding 端点能回溯约 90 天，因此可以在两者都有的窗口上直接测：

`scripts/compare_bitget_binance_funding.py` / `reports/derivatives_track_funding_calibration/`：

- 窗口 2026-07-11 → 2026-10-10，48 个两者都有历史的资产；
- **总 funding 之比（Bitget / Binance）中位数 1.590、均值 1.631**；单次结算费率之比中位数 1.449；
- 结算次数中位数：Bitget 270 次 vs Binance 246 次（Bitget 该窗口多为 8h 节奏，部分资产 4h）；
- 结构上 BTC 基本持平（0.97x，proxy 可信），**山寨币普遍 1.3x–5.6x**（如 BCH 5.58x、Canton 3.92x、APT 2.86x）——也就是说 Binance proxy 在集中持仓山寨币时会系统性低估 Bitget 的资金费。

据此把"实测水平"作为中心情形（Binance proxy 不利 funding × **1.59**），在真实 mark 上重跑：

| trial | 终值 | Sharpe | MDD | 累计 funding | 强平 |
|---|---:|---:|---:|---:|---:|
| L125 | **30.078x** | 1.634 | -41.66% | -1.198 | 0 |
| L150 | 50.963x | 1.633 | -47.90% | -1.903 | 0 |
| L200 | 118.435x | 1.636 | -55.05% | -4.019 | 0 |

对照同成本现货 H5 +3h（19.525x / 1.623 / -36.97%）：**按实测 Bitget funding 水平，1.25x 衍生品路径仍高 54%，Sharpe 略优，MDD 差 4.7pp**。加上 §12.8.12 的盈亏平衡约 4.3x，说明距离"资金费吃掉优势"还有约 2.7 倍的安全边际。

这仍不是完整闭合：90 天的水平校准不能保证 2022–2025 的相对水平不变，且该窗口恰好是 funding 偏高的阶段（行情热）。因此 #7 门槛从"未闭合"升级为**部分闭合（有实测水平 + 上方压力带）**，记录口径为：中心情形 30.1x、压力情形 24.3x（3x）、上界 44.1x（零 funding）。

#### 12.8.17 成交价口径闭合：mark 成交 vs market(last) 成交

此前的所有 Bitget mark 结果都用 **mark 开盘价** 成交。真实下单会成交在 **market(last) 价**。引擎现在把两者分开（mark 负责估值、强平与 funding；market 负责调仓成交），并下载了 87 个合约的 market K 线（`data/raw/bitget_derivatives/merged_market_20261009/`，2022-01-01 → 2026-09-21 23:00，各 40,993 根小时线）。

`scripts/compare_derivatives_fills.py` 对同一冻结规格的两套结果做对比（**`fill_downgrades=0`，即每一笔成交都用了真实 market K 线，没有任何回退到 mark**）：

| 情形 | mark 成交 | market 成交 | 比值 |
|---|---:|---:|---:|
| 零 funding L125 | 44.125x | **44.197x** | 1.0016 |
| 零 funding L150 | 80.084x | 80.248x | 1.0020 |
| 零 funding L200 | 210.175x | 210.794x | 1.0029 |
| proxy funding L125 | 34.477x | 34.526x | 1.0014 |
| 2x adverse L125 | 28.266x | 28.308x | 1.0015 |
| **3x adverse L125** | 24.290x | **24.327x** | 1.0015 |
| 3x adverse L200 | 84.888x | 85.125x | 1.0028 |

- 9 个（funding × leverage）组合里，market 成交的终值比 mark 成交高 **0.14%–0.29%**，Sharpe 略升，MDD 完全不变或微好。
- 结论：**成交价假设不是这套策略的实质风险**。原因是它 4.7 年只开 137 条腿、且都在 Bitget 深度最好的前 20 币上，T+1 +3h 的 market 开盘与 mark 开盘几乎一致。此前的 mark 成交口径因此不需要重跑全部结果，但两者都在报告里留档。
- 门槛 #8 由「进行中」改为 **通过**。

#### 12.8.18 轮动机制的直接证据：选出来的币到底有没有跑赢篮子

重仓最强币本身是策略设计，不是缺陷。真正要验证的是**「选出来的币是否系统性地跑赢 PIT Top20 篮子」**——如果只是 ZEC 一次运气，机制就不成立。`scripts/analyze_rotation_skill.py` / `reports/phase_momentum_rotation_skill_2022/`：

口径：t 日信号 → 记为 t+1 交易日的收益（不使用当天信息）；`book = Σ w_i · r_i / Σ|w_i|`，`basket =` 当日 PIT Top20 等权，520 个有仓位的信号日。

| 指标 | 数值 |
|---|---:|
| 组合日均收益 | +0.560% |
| 篮子日均收益 | +0.217% |
| **日均超额** | **+0.343%**（年化 +125%） |
| 超额中位数 | -0.126% |
| 超额为正的比例 | 47.3% |
| Newey-West t（lag 5） | **1.81**（5% 不显著） |
| 选中的币进入篮子前 20%（前 4 名） | **33.1%**（随机为 20%） |

逐年：

| 年份 | 天数 | 日均超额 | 超额为正 | 选中币进前 20% |
|---|---:|---:|---:|---:|
| 2022 | 16 | -0.71% | 25.0% | 25.0% |
| 2023 | 166 | +0.09% | 46.4% | 30.1% |
| 2024 | 165 | +0.55% | 46.7% | 31.5% |
| 2025 | 124 | +0.34% | 47.6% | 30.7% |
| 2026 | 49 | +0.87% | 59.2% | 57.1% |

**结论**：机制方向正确——选中的币有 33% 概率落在篮子前 20%（随机 20%），四年里有三年超额为正，2026 年尤其强。但它是**典型动量形态**：胜率不到 50%、中位数略微为负、均值靠右尾拉动，且 t=1.81 达不到 5% 显著。这意味着「集中」不是执行失误，而是这类边缘收益的正确表达方式；反过来，任何分散化都会同时砍掉右尾（现货轨 H4 分散化只得到 3.15x，已被证伪）。

#### 12.8.19 逐 legs 收益分布（L125，129 条腿）

| 指标 | 数值 |
|---|---:|
| 盈利腿占比 | **45.0%** |
| 腿收益中位数 | +0.2% |
| 腿收益分位 | p10 -15.0% / p90 +36.9% |
| 单腿最大 / 最小 | +187.1%（DOGE 2024-10）/ -35.4% |
| 最大单腿占总盈亏 | 25.5% |
| 前 3 / 前 5 条腿占比 | 57.0% / 74.4% |

盈利最多的 5 条腿：ZEC ×2（+77%、+72%）、HYPE（+159%）、DOGE（+187%）、BNB（+11%）。**即使落到单腿粒度，也是「多数小输小赢 + 少数巨大赢」**——这是动量策略的统计指纹，也解释了为什么按资产归因会看到 ZEC 占 59.6%（§12.8.14）。

**因此对 AGENTS.md「不能依赖单一资产」条款的处理**：这是一条**负责人确认的设计属性**（2026-10-09：板块轮动、重仓最强币是策略本体），而不是待修 bug。记录保留两点残差风险，不做粉饰：① 机制的超额在 5% 水平不显著（t=1.81）；② 若未来 12 个月里没有出现类似 ZEC/HYPE 的右尾，策略会表现为「低胜率 + 小幅亏损」，而不是回撤。对应的控制手段只有**仓位规模**（3% 总资金）与隔离保证金缓冲，而不是分散化。

#### 12.8.20 跨所 funding 偏差有多大：Bybit 五年历史告诉我们什么

Bitget 只有 90 天历史，无法证明 1.59x 这个溢价在 2022–2025 是否稳定。改用**有完整历史的 Bybit** 做旁证（`scripts/analyze_funding_venue_premia.py` / `reports/derivatives_track_funding_venue_premia/`），口径为「该所总 funding / 同期 Binance 总 funding」，49 个两者都有历史的币：

**Bybit / Binance，逐年中位数**

| 年份 | 2022 | 2023 | 2024 | 2025 | 2026(至 09-20) |
|---|---:|---:|---:|---:|---:|
| Bybit / Binance | 0.897 | 1.129 | 1.020 | 0.989 | **0.673** |

**同一个 91 天窗口（2026-07-11 → 2026-10-10）三所对比**

| 场所 | 相对 Binance |
|---|---:|
| Bitget | **1.590x** |
| Bybit | **0.761x** |

结论与它对 funding 门槛的含义：

- **交易所之间的资金费差异是真实且双向的**：同一窗口里 Bybit 比 Binance 低 24%，Bitget 比 Binance 高 59%，两者相差 **2.09 倍**。所以不能假设「Bitget 溢价 1.59x 在 2022–2025 也一定是 1.59x」。
- 但这也给出了**上界的使用方式**：即便假设 Bitget 历史溢价达到本次观测到的跨所最大离散度（≈2x Binance），对应终值 28.266x，仍高于同成本现货 H5 的 19.525x；距离 4.3x 盈亏平衡还有约 2.15 倍。
- 因此 funding 门槛的口径定为：**中心情形 = 实测 Bitget 水平（proxy × 1.59，30.078x）；上界情形 = 跨所最大离散度（×2，28.266x）；压力情形 = ×3（24.290x）；break-even = ×4.3**。仍不能声称"精确资金费已计"，但"代理偏多少"已经从未知变成有实测、有上界、有安全边际。
- 顺带一个重要观察：2026 年 Bybit 的 funding 显著低于 Binance（0.67x），说明**当前是 funding 偏高的阶段**（§12.8.16 的 90 天窗口是高位），把它当作长期水平反而偏保守。

#### 12.8.21 全链路实测与负路径审计（2026-10-09/10）

用户要求"信号、代码全链路实测一遍"，因此对上线路径做了一次逐段演练，并把**失败路径**也当作被测对象。全部证据如下（本机 macOS，UTC 时钟）：

**正向链路（全部通过）**

1. 面板刷新 `scripts/download_data.py`：PIT CMC Top20 面板更新到 2026-10-08，97 个完整行，无缺失填充。
2. OOS 追踪 `make derivatives-oos`：17 天，最新 mark 2026-10-09 15:00 UTC，staleness 1.46h（< 30h 闸门），0 次强平，dropped_target_rows=0，signal day 自动停在 2026-10-08（未收盘的 UTC 日不进信号）。
3. 信号 dry-run 与**独立重算**对拍：账本重算出 NEAR 名义 776.78 / 变化 +144.67 / 隔离保证金 400.04（=776.78×51.5%），与 `send_derivatives_signal.py --dry-run` 逐字一致。
4. 真实 Telegram 发送：`getMe` 正常，两个 chat id（1231093599、5582320122）都收到 2026-10-08 信号；随后再跑一次 `derivatives-notify` 命中幂等（"Already sent … skipping"，exit 0，未重复发送）。
5. 冻结结果复现（审计后重跑，与已提交证据**逐位一致**）：zero funding L125 = 44.12529343989681x（daily_returns 序列 bit-identical）；实测 funding（proxy×1.59、stress_median）= 30.07751281087659x，Sharpe 1.6338534307862165，MDD −41.66%，0 强平，funding_total −1.1982。

**负路径（fail loudly，全部 exit≠0 且带可操作提示）**

| 场景 | 结果 |
|---|---|
| 缺 bot token | exit 1，`ATLAS20_TELEGRAM_BOT_TOKEN is not set` |
| 信号超过 36h | exit 1，拒绝发送并提示刷新 pipeline / `--allow-stale-signal` |
| targets 文件不存在 | exit 1，`targets file not found: …` |
| 缺 chat id | exit 1，`ATLAS20_TELEGRAM_CHAT_ID is not set` |
| mark 数据过期（>30h） | exit 1，提示 `make derivatives-oos-data` 或 `--allow-stale` |
| mark 目录不存在 | 修复前是 `FileNotFoundError` 堆栈；现为 exit 1 + 可操作提示 |

**本轮新修 1 个真 bug**：`run_derivatives_oos.py` 对缺失的 mark 目录会抛出原始 traceback（其他闸门都是可读的 SystemExit）。改为 `load_symbol_map()` 显式检查 `symbol_map.csv` 并给出下载指引，新增 2 个回归测试。

**回归状态**：`pytest -q` 1359 passed / 1 skipped；`make lint`、`make typecheck`、`check_repo_health.py` 全绿（本轮仅 scripts/ 与 tests/ 改动，未触碰冻结策略参数）。

#### 12.8.22 实盘执行层与 live-fire 回放（2026-10-10）

用户要求"实战全链路、要有逻辑测试"，并且"程序每天按余额动态计算"。为此把执行层从"研究账本"
推进到"可直接对账户下发的计划"，并用引擎 4.7 年的真实成交账本做逐笔回放验证。

**新增模块**

- `atlas20.derivatives.account` — Bitget **UTA v3** 私有客户端（签名、重试、`paptrading` 演示盘头）。
  端点用线上 API 逐一验证存在性（鉴权错误 40006 = 存在；404 = 不存在）：
  `GET /api/v3/account/assets`、`GET /api/v3/position/current-position`、
  `POST /api/v3/trade/place-order`、`POST /api/v3/account/set-leverage`、
  `POST /api/v3/account/set-margin`、`POST /api/v3/account/set-hold-mode`。
  **重要修正**：流传的 `POST /api/v2/mix/position/adjust-position-margin` **不存在（404）**；
  逐仓保证金调整的真实端点是 v3 `set-margin`（`operation=add|remove`，`amount` 为保证金币种）。
- `atlas20.derivatives.execution` — 实盘订单规划器：从**真实权益**出发算目标名义，逐仓保证金按
  51.5% 计算差额，先减后加（与引擎同序），按合约 `quantityMultiplier`/`minOrderQty`/
  `minOrderAmount` 向下取整，可用保证金不足时缩减而不是硬下（镜像引擎口径）。
- `scripts/plan_live_execution.py` / `make execution-plan[-live]` — 每日执行计划：支持
  `--live`（UTA API）、`--account-file`（JSON 快照）、`--equity`（手填），输出"买/卖多少枚、
  名义多少、保证金加/减多少"，`--notify` 可发 Telegram（同日幂等）。
- `scripts/replay_live_execution.py` — live-fire 回放（下述）。

**一等证据：逐笔回放（2022-01-01 → 2026-09-21，L125、20 bps）**

| 检查 | 结果 |
|---|---|
| 引擎调仓次数 / 订单数 | 534 / 1185 |
| 实盘规划器复现引擎订单 | **1185/1185 匹配，0 不匹配** |
| 账户完全按规划器自己的订单演化（含真实合约步长/最小下单量） | 42.7206x vs 引擎 42.5559x（同一时点）→ **+0.387%** |
| 逐小时强平检查（plan-driven 账户） | **0 次** |
| 低于交易所最小下单量的订单 | 73 / 1185 = 6.2%（多为零头再平衡；次日计划从真实持仓重算，自我修正） |
| 其余订单名义误差（真实合约量化） | 均值 1.29% / p95 6.16% / max 49.8%（全部向下取整，不会超仓） |

报告：`reports/derivatives_track_live_replay/`。

**合约细节（公开 API 实测）**：USDT-M 的 `qty` 是**币数量**（如 NEAR 步长 1 枚、min 名义 5 USDT、
taker 6 bps）。逐仓保证金由杠杆自动划入（2x ≈ 50%），要达到模型的 51.5% 需成交后
`set-margin(add)` 补 1.5pp；减仓日按交易所真实 `positionBalance` 算"撤出"。计划器每日重读账户，
不依赖缓存，误差最多持续一天。

**尚未闭合**：① 真实账户/真实下单未测试（没有 API key；演示盘 key 建好后可全链路跑通）；
② funding 精确历史仍为 proxy；③ 12 个月样本外继续计时。
