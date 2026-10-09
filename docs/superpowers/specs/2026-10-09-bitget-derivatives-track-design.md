# Bitget 衍生品研究轨道设计

| 项目 | 内容 |
|---|---|
| 日期 | 2026-10-09 |
| 状态 | 设计稿，等待负责人审阅；尚未实现、尚未接入实盘 |
| 目标账户 | Bitget USDT-M 永续合约 |
| 项目资金 | 最多占总资金 3% |
| 默认最大杠杆 | 1.25x gross exposure（1.5x 仅压力） |
| 默认最大空头 | 0.5x gross exposure |
| 单币最大空头 | 0.25x gross exposure |
| 保证金模式 | isolated margin |
| 主样本 | 2022-01-01 至 2026-09-21 |
| 真样本外 | 2026-09-22 起，禁止用于选规则 |
| 关联旧轨道 | `PR2026-10-H5`，严格 point-in-time CMC Top20，long-only spot，无杠杆 |

## 0. 一句话结论

本设计新增一条与现货 H5 分离的 **Bitget 衍生品研究轨道**，用于检验三件事：

1. 在严格 point-in-time Top20 和现有 H5 选币信号不变的前提下，1.25x/1.5x/2.0x 杠杆能否在强平约束下改善终值和风险收益比；当前证据显示 1.25x 是唯一在成本压力下仍守住 50% MDD 的候选；
2. 在明确熊市确认条件下，BTC 或 Top20 最弱币的小仓位空头 overlay 是否能改善回撤，而不是单纯放大尾部风险；
3. Bitget 的真实手续费、资金费、标记价、维持保证金、强平和返佣外部现金流，能否被逐结算点建模。

这条轨道不会修改 H5 的现货结论，也不会用杠杆或做空结果去让 H5 通过原来的 DSR 门槛。新轨道必须有自己的预注册试验、强平门槛、成本压力测试和样本外验收。

## 1. 为什么必须独立于 H5

H5 的全部历史证据都基于以下约束：

- long-only spot；
- gross exposure <= 1.0；
- 无杠杆、无空头、无保证金、无强平；
- 成本口径 2/20/50/100 bps；
- 现金是唯一防守资产。

如果直接把同一份 H5 回测改成合约、杠杆和做空，会产生三个不可接受的后果：

1. **历史收益不可比**：杠杆会非线性放大路径依赖，合约存在强平、标记价、维持保证金和资金费；
2. **选择偏差失控**：杠杆倍数和空头规则都是新试验，必须计入试验数 N；
3. **验收失真**：H5 的 DSR 已经因为历史试验数过高而不通过，新增试验只会让 DSR 更差，不能反向降低门槛。

因此本设计采用双轨结构：

- `Spot Track`：原 H5，不修改；
- `Derivatives Track`：本设计，独立预注册、独立报告、独立 kill criterion。

## 2. 研究问题

### 2.1 杠杆问题

**问题 D-L1**：在 H5 目标 gross 不变的前提下，乘以固定杠杆 L 后，是否能在主样本和真样本外中：

- 提升终值；
- 不触发强平；
- 项目最大回撤不超过 50%；
- Sharpe 不低于 H5 的 90%；
- 在 6/8/11/20/50/100 bps 成本压力下仍保持方向一致。

**待检验 L**：

- 1.25x：默认主候选；
- 1.5x：压力测试，不作为默认上线候选；
- 2.0x：仅压力测试，不作为默认上线候选；
- 3.0x 及以上：不进入本轮。

### 2.2 空头问题

**问题 D-S1**：在 BTC 强空头确认下，小仓位做空 BTC，是否比现金防守更能降低组合回撤并提高 Sharpe？

**问题 D-S2**：在相同强空头确认下，做空 Top20 中动量最弱的币，是否优于做空 BTC？

**问题 D-S3**：真正的 funding carry 需要 spot long + perp short。Bitget 只有合约时，方向性空头能否仅靠资金费覆盖价格风险？

第 3 个问题的预期答案是否定的：资金费是边际收益，不能替代价格趋势和强平控制。

### 2.3 执行问题

**问题 D-X1**：Bitget 的真实 Taker/Maker 费、滑点、资金费、维持保证金、标记价和强平是否能逐结算点重建？

**问题 D-X2**：主账户收到的 60% 返佣，在量化账户之外，是否应作为外部现金流单独报告？

答案：是。量化账户 NAV 使用完整费率；返佣只进入“总财富视图”，除非负责人手动把返佣划回量化账户。

## 3. 外部证据与设计含义

本节只记录会改变设计的证据。完整来源记录见 `docs/research/derivatives_track_research_2026-10.md`。

### 3.1 资金费 carry

Christin、Routledge、Soska 和 Zetlin-Jones 的 *The Crypto Carry Trade* 使用 Binance 18 个币、36 个合约、2020-08-11 至 2023-06-23 的 8 小时资金费数据，定义“现货多 + 永续空”的 carry 交易。BTC Tether 合约的年化均值 14.26%、波动 1.63%、Sharpe 8.76；币本位合约 Sharpe 4.93。论文同时指出，30%–40% 的年化交易所破产概率就足以抵消这种 Sharpe，而且样本后期 FTX 等事件后收益显著下降。

**设计含义**：资金费 carry 的经济机制真实存在，但它是 delta-neutral，不是方向性做空。Bitget 只有合约时，不能把“开空收资金费”等同于 carry。

### 3.2 永续 arbitrage

He、Manela、Ross 和 von Wachter 的 *Fundamentals of Perpetual Futures* 在 2020–2024 年对 BTC/ETH/BNB/DOGE/ADA 做随机到期 arbitrage。零成本下，全样本 Sharpe 分别为 11.65、12.77、17.66、14.90、19.76；BTC 最大回撤 -3.82%，DOGE -13.90%。论文强调成本、有效买卖价差和保证金会造成 interim loss，且资本约束会放大价格冲击。

**设计含义**：这些高 Sharpe 来自 spot+perp 的收敛交易和零成本假设，不能外推为单向做空。新轨道必须把有效价差、保证金和 interim loss 放入引擎。

### 3.3 多空动量

项目旧文献 S4（Han、Kang、Ryu）在 realistic assumptions 下发现：cross-sectional 动量的收益主要来自 long leg；losers 经常反弹，short leg 亏钱；shorting the market after declines 在多数情况下也亏钱。

S14（Grobys 等）使用前 30 大币，long-short quintile；普通动量不显著，一次由单一币造成的 -255.28% 周收益主导了结果；volatility-managed 版本显著，但尾部分布仍为 power law，Sharpe 的有限方差假设不可靠。

**设计含义**：空头不能只靠“资金费正”或“动量最弱”启动。必须有更强的熊市确认，且空头仓位必须远小于多头仓位。

### 3.4 杠杆与强平

Cheng、Deng、Wang 和 Yu 的 *Liquidation, Leverage and Optimal Margin in Bitcoin Futures Markets* 使用 BitMEX BTC 永续数据：

- 被强平交易者的平均杠杆约 58–60x；
- 每日强平占未平仓量的比例约 long 3.51%、short 1.89%；
- 若目标日强平概率为 1%，论文估计最优保证金约为 long 33%（3x）和 short 20%（5x）。

这仍是 BTC 单资产、早期 BitMEX 样本。对 Top20 altcoin，尾部更厚、流动性更差，因此本项目采用更保守的 1.25x 默认 gross 上限，1.5x/2.0x 只做压力测试。

### 3.5 标记价、延迟检测与流动性

Delayed Marks、Funding Memory 和 Forecasting Liquidation-Tail Risk 指出：强平风险不仅取决于杠杆和波动，还取决于标记价延迟、资金费持续扣减、维持保证金边界和可执行深度。隐藏流动性研究进一步说明，盘口显示深度在清算级联中会系统性高估可执行流动性。

**设计含义**：回测不能只用日收盘和“盘口滑点 = 0”。必须使用小时级 mark price、维持保证金、强平费、保守滑点和资金费持续扣减。

### 3.6 项目内新诊断：杠杆只放大，条件空头才是可能的 alpha

2026-10-09 在现有 H5 日收益上做了只读诊断（2022-01-01 至 2026-09-21，`day_close`；这是研究输入，不是新的预注册回测）。先用无资金费、无强平、无额外成本的线性缩放看杠杆的纯数学效果：

| 方案 | 终值 | CAGR | Sharpe | MDD | Calmar |
|---|---:|---:|---:|---:|---:|
| H5 1.0x @20bps | 19.53x | 87.6% | 1.623 | -36.97% | 2.37 |
| H5 ×1.25 @20bps | 35.85x | 113.4% | 1.623 | -44.27% | 2.56 |
| H5 ×1.50 @20bps | 62.51x | 140.0% | 1.623 | -50.88% | 2.75 |
| H5 ×2.00 @20bps | 163.44x | 194.2% | 1.623 | -62.23% | 3.12 |
| H5 ×3.00 @20bps | 621.78x | 290.4% | 1.623 | -80.56% | 3.61 |

关键结论：

1. **杠杆不改变 Sharpe**。在没有资金费和强平时，`L × return` 的 Sharpe 与 1x 完全相同；它只放大终值和回撤。
2. **杠杆不是 alpha，而是资本效率工具**。它可以把终值推过 20x，但不能单独解决 H5 的 DSR、PBO 或窄峰问题。
3. **1.5x 在 20bps 下已经越过 50% 回撤 kill switch**。按 6/8/11/20/50/100 bps 重建的成本敏感性：

| 成本 | 1.25x 终值 | 1.25x MDD | 1.50x 终值 | 1.50x MDD |
|---:|---:|---:|---:|---:|
| 6 bps | 39.87x | -43.3% | 71.00x | -49.8% |
| 8 bps | 39.27x | -43.4% | 69.72x | -50.0% |
| 11 bps | 38.38x | -43.6% | 67.85x | -50.2% |
| 20 bps | 35.85x | -44.3% | 62.51x | -50.9% |
| 50 bps | 28.55x | -46.3% | 47.57x | -53.1% |
| 100 bps | 19.53x | -49.6% | 30.16x | -56.5% |

因此 **1.25x 是唯一在全部成本档位下仍低于 50% MDD 的杠杆候选；1.5x 只有在最乐观的 6bps 假设下才勉强通过，不能作为默认上线档位。** 这直接推翻了“1.5x 是默认安全上限”的直觉。

条件空头诊断（仅研究输入，不是预注册结果）：在 `BTC < 200D MA` 且 `BTC 30D return < 0` 时，做空 PIT Top20 中 30D 收益最弱的币；用 Binance funding 代理和 16bps 单边切换成本，日频 close-to-close，未做完整强平引擎：

| 空头 | 空头 gross | 组合终值 | Sharpe | MDD |
|---|---:|---:|---:|---:|
| 空 BTC | 0.25x | 33.99x | 1.872 | -36.97% |
| 空 BTC | 0.50x | 57.35x | 2.052 | -36.97% |
| 空最弱币 | 0.25x | 90.34x | 2.245 | -36.97% |
| 空最弱币 | 0.50x | 364.86x | 2.525 | -36.97% |

这个诊断有两个相反的含义：

- 它支持“条件空头可能改善收益和 Sharpe”，值得进入 Phase 3；
- 它没有改善 H5 的 MDD，而且使用 close-to-close、日频、无完整强平/ADL 的简化模型，因此**按本设计现有的空头 kill criterion（相比同杠杆 long-only 的 MDD 改善至少 5 个百分点）并不通过**。它不能作为上线依据，也不能用来降低任何门槛。

资金费诊断（Binance 2022-01-01 至 2026-09-21，52 个有历史的币）：全样本中位年化 funding 约 4.65%，正 funding 时间占比中位约 75.0%。BTC 年化均值约 6.61%，正 funding 占比 84.6%；NEAR 约 4.54%，正占比 74.7%；SOL 约 -4.93%，正占比 66.1%。因此“开空大部分时候能收资金费”对 BTC/NEAR 近似成立，但对 SOL 等币不成立；每个空头标的必须使用自己的 funding 历史，不能统一用 BTC funding。


## 4. Derivatives Track 硬约束

### 4.1 保留的约束

- 币种池仍是严格 point-in-time CMC Top20；
- 信号仍在 UTC 日线收盘生成；
- 执行仍为 T+1；
- 不使用 Top20 之外资产；
- 缺失数据不得静默填零；
- 所有试验必须预先登记；
- 真样本外从 2026-09-22 起，禁止调参。

### 4.2 新增约束

- 交易所：Bitget USDT-M perpetual；
- 方向：long/short；
- 默认 gross exposure 上限：1.25x；
- 压力 gross 上限：1.5x/2.0x，仅研究；
- 空头总 gross 上限：0.5x；
- 单币空头 gross 上限：0.25x；
- 保证金模式：isolated；
- 强平门槛：主样本内不得出现强平事件；
- 项目最大回撤 kill switch：50%；
- 量化账户返佣：不计入 NAV；
- 主账户返佣：单独报告为外部现金流；
- 成本压力：6/8/11/20/50/100 bps。

### 4.3 不进入本轮的规则

- 3x 及以上杠杆；
- cross margin；
- 无趋势确认的裸空；
- 只凭资金费正就做空；
- 用 Top20 之外资产替代 Bitget 缺失合约；
- 用杠杆或做空结果重新定义 H5 的 DSR 门槛。

### 4.4 账户杠杆、仓位杠杆和强平距离

衍生品轨道最容易混淆的三个量必须分开定义：

| 概念 | 定义 | 本设计默认 |
|---|---|---:|
| 账户 gross | `Σ|notional_i| / account_equity` | long 1.25x；压力 1.5x/2.0x |
| 仓位杠杆 | `|notional_i| / isolated_margin_i` | 由强平距离反推，不直接固定 |
| 强平距离 | 价格从入场到强平价的不利变动 | long ≥30%；short ≥50% |

不能用“账户 gross = 1.5x”推断“每个仓位 1.5x”。例如：1.25x gross 的 long book，如果每个 long 仓位的 `margin / notional = 30% + MMR + fee_buffer`，总初始保证金约为 `1.25 × 0.31 ≈ 38.8%` equity；再叠加 0.5x short 的 50% 保证金，总保证金约 `38.8% + 25% = 63.8%`，仍保留约 36% 的未占用现金作为缓冲。这个结构才是 isolated margin 下可执行的。

仓位保证金规则：

```text
margin_ratio_long  = max(0.30 + MMR_i + fee_buffer, min_margin_ratio)
margin_ratio_short = max(0.50 + MMR_i + fee_buffer, min_margin_ratio)
isolated_margin_i  = margin_ratio_i × |notional_i|
```

其中 `fee_buffer` 默认 0.5%，用于强平费、滑点和标记价跳空；`MMR_i` 使用 Bitget 对应 position tier 的 maintenance margin rate。若所有仓位的 `isolated_margin` 之和超过账户 equity，则按比例缩小所有 notional，直到保证金占用不超过 equity 的 85%，不允许用“账户还有现金”作为提高单仓杠杆的理由。


## 5. 数据与数据质量

### 5.1 价格和标记价

主回测使用：

- `data/processed/panel_daily.csv`：H5 选币和每日信号；
- Binance 1h K 线：现有执行延迟和小时路径；
- Bitget `/api/v3/market/history-candles` 的 `type=mark` 1H K 线：强平路径主数据；
- Bitget `/api/v3/market/history-candles` 的 `type=market` 和 `type=index` 1H K 线：成交和标记校验；
- Bitget `/api/v2/mix/market/history-fund-rate` 的最近约 90 天精确 funding：与 Binance 历史 funding 代理做重叠校验。

已核验：Bitget 历史 K 线接口可返回 2022 年 BTCUSDT 和 NEARUSDT 的 1H mark candle；单次 `limit<=100`、单窗口<=90 天，且返回 `endTime` 之前最近 100 条，因此必须从 `endTime` 向前分页。仍需对所有 PIT Top20 成员逐币做全量覆盖审计，因为新上市、下架、迁移和 rebrand 会造成缺口。

限制：

- Bitget v2 历史 funding 接口只覆盖最近约 90 天，2022–2026 的资金费历史仍使用 Binance funding 代理并做重叠误差报告；
- Bitget 历史 mark candle 是交易所事后提供的 K 线，仍可能缺少极端秒级插针、部分下架合约和部分新币早期数据；
- 真样本外阶段必须切换到 Bitget 实时 mark price 和实际成交记录；
- 所有缺口必须显式报告，不能静默回填。

### 5.2 资金费

- Bitget `/api/v2/mix/market/history-fund-rate`：精确最近约 90 天，8 小时间隔；`pageNo` 分页有效；
- Bitget `/api/v3/market/history-fund-rate`：忽略 `pageNo`，只返回最近 20 条，不能用于历史下载；
- Binance `data.binance.vision` fundingRate 月度归档：2022 起历史代理；
- 每个币按实际结算时间计费，不能假设所有币都是 8 小时；
- 正资金费：long 支付 short；负资金费：short 支付 long；
- 资金费压力：1x、2x、3x 和最近一年最差窗口；
- 缺失资金费：fail closed 或使用当日可执行标的的保守上界，不填零。

### 5.2.1 资金费代理验证协议

Bitget 公开历史 funding 只有最近约 90 天，因此 2022–2026 的主历史必须用 Binance funding 归档代理。代理不能默认可信，必须先通过以下重叠窗口验证：

| 指标 | 通过阈值 | 不通过处理 |
|---|---:|---|
| settlement timestamp 对齐率 | ≥99% | 逐币报告缺口；缺口币不进入空头候选 |
| funding 符号一致率 | ≥95% | 逐币降级或排除 |
| Pearson/Spearman 相关 | ≥0.95 | 逐币降级或排除 |
| 中位绝对误差 | ≤1 bp/settlement | 逐币降级或排除 |
| 95 分位绝对误差 | ≤5 bp/settlement | 逐币降级或排除 |
| 极端值方向一致 | 最差 1% 窗口同号 | 逐币降级或排除 |

通过后仍要报告每个币的重叠误差表。未通过重叠验证的币，在历史回测中只能使用 fail-closed 处理：不开仓、平仓或使用明确上界，不能把缺失 funding 填零。资金费压力测试固定为：

- 1x：实际/代理 funding；
- 2x：全部 settlement 乘以 2；
- 3x：全部 settlement 乘以 3；
- 符号反转：把正 funding 改为负、负 funding 改为正；
- 最近一年最差 30 天窗口：把该窗口的 funding 重复到全样本做压力。

任何空头候选必须通过 2x/3x 压力后才允许进入下一阶段。


### 5.2.2 Phase 1 funding 重叠审计结果

2026-10-09 用 Bitget v2 最近 245 个 settlement 与 Binance 归档代理做重叠验证，BTC/NEAR/SOL 的结果如下：

| 币 | overlap | 符号一致率 | Pearson | 中位绝对误差 | 95 分位绝对误差 | 累计差 | 7 日最大绝对差 | 判定 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| BTC | 245 | 0.853 | 0.250 | 0.274 bps | 0.947 bps | -19.7 bps | 11.7 bps | 失败 |
| NEAR | 245 | 0.829 | 0.273 | 0.050 bps | 1.421 bps | +55.0 bps | 12.6 bps | 失败 |
| SOL | 245 | 0.694 | 0.505 | 0.378 bps | 1.121 bps | +36.2 bps | 12.6 bps | 失败 |

失败原因是**符号一致率和相关性**不达 §5.2.1 的预注册阈值，而不是误差量级：中位/95 分位误差都很小，但符号一致率只有 0.69–0.85，Pearson 只有 0.25–0.51。累计差在 245 个 settlement（约 82 天）为 -19.7 bps 到 +55.0 bps，年化约 -88 bps 到 +245 bps，足以影响年 funding drag 约 150 bps 的策略。

结论：

- Binance funding **不能**被称为 Bitget 精确历史；
- 预注册门槛不因本次结果放宽；
- 如果 2022–2026 回测依赖精确 funding，当前数据质量门不通过；
- 可选的合规路径只有：寻找更好的 Bitget 历史 funding 来源；或把 2022–2026 funding 明确降级为 proxy/uncertain 压力带；或只用最近 90 天 Bitget 精确 funding + 未来 OOS；
- Phase 2 引擎可以继续实现，但 funding attribution 必须带 `funding_source=proxy` 标签，且在找到更好来源前不能作为上线依据。


### 5.3 手续费与返佣

- Taker：6 bps/边；
- Maker：2 bps/边；
- 滑点：小仓位 1–3 bps/边；压力 5/10 bps/边；
- 60% 返佣：主账户外部现金流，量化账户不抵扣；
- 若负责人手动划回返佣，必须作为显式 cash injection 建模，不能自动复利。

### 5.4 合约规格

每个 PIT Top20 币必须维护：

- Bitget symbol；
- baseCoin；
- launchTime；
- symbolStatus；
- fundInterval；
- maker/taker fee；
- minTradeNum/minTradeUSDT；
- sizeMultiplier；
- position tier 和 maintenance margin rate；
- liquidation fee；
- 是否发生过 rebrand/delist。

当前已知缺口（2026-10-09 Phase 1 审计）：102 个 PIT Top20 coin id 中 88 个有 Bitget USDT-M 合约，14 个缺失：

```text
EOS, FLOW, FTT, HNT, HTX, HT, KCS, LEO, MKR, MNT, OKB, OSMO, WAVES, YFI
```

MATIC 已迁移到 POL，映射为 POLUSDT；`bitget-token` 映射为 BGBUSDT。缺失合约不得用排名更低的币替代。

主规则：若 H5 选中的币没有可用 Bitget 永续，该 sleeve 进入现金。不得自动用排名更低的币替代。替代规则只能作为单独的预注册变体。

## 6. 引擎架构

新增模块建议：

```text
src/atlas20/derivatives/
  __init__.py
  instruments.py      # Bitget instrument map, contract specs, availability
  funding.py          # Bitget 90d exact feed + Binance historical proxy
  margin.py           # isolated margin, maintenance margin, liquidation
  engine.py           # hourly/8h event-driven long-short backtest
  signals.py          # leverage, BTC short, weakest-Top20 short
  reporting.py        # metrics, liquidation events, funding attribution
```

脚本建议：

```text
scripts/download_bitget_derivatives_data.py
scripts/run_derivatives_backtest.py
scripts/evaluate_derivatives_candidates.py
scripts/run_derivatives_oos.py
```

### 6.1 引擎事件顺序

每个 UTC 日按以下顺序处理：

1. 读取上一日收盘生成的 target；
2. 在 T+1 的 +3h 执行 fill；
3. 应用 Taker/Maker 费和滑点；
4. 更新每个 isolated position 的 margin；
5. 在 00:00 / 08:00 / 16:00 UTC（或实际 fundInterval）结算资金费；
6. 用 1H mark price 检查维持保证金和强平；
7. 强平时收取强平费，并按保守执行价扣滑点；
8. 记录 position、equity、gross、net、funding、fees、liquidation event。

### 6.2 账户模型

- 账户 equity = cash + unrealized PnL - accrued funding - fees；
- 每个 isolated position 有独立 margin；
- long liquidation 由 mark price 下跌触发；
- short liquidation 由 mark price 上涨触发；
- 强平后该 position 归零，剩余 margin 进入 cash；
- 不使用 cross margin，避免一个 altcoin 的尖刺拖垮整个账户；
- 强平检查必须在小时级别完成，不能只看日收盘。

### 6.2.1 强平价公式与路径规则

强平必须用 mark price，不允许用 last price 或日收盘。对 isolated margin 的单一仓位，设：

- `P0`：入场 mark price；
- `r_margin = isolated_margin / |notional|`：保证金率；
- `m`：该 position tier 的 maintenance margin rate；
- `fee_buffer`：强平费、滑点和 ADL 缓冲。

则初始强平价近似为：

```text
long:  P_liq = P0 × (1 - r_margin) / (1 - m)
short: P_liq = P0 × (1 + r_margin) / (1 + m)
```

如果 `r_margin = 31%`、`m = 1%`，long 的强平距离约 `1 - 0.69/0.99 ≈ 30.3%`；如果 `r_margin = 51%`、`m = 1%`，short 的强平距离约 `1.51/1.01 - 1 ≈ 49.5%`。这与 4.4 的 30%/50% 目标一致。

路径规则：

1. 每个 1H mark candle 先检查 funding settlement，再检查 high/low 是否穿越强平价；
2. 如果同一根 1H candle 内既触发 funding 又触发强平，按“先扣 funding、后强平”处理；
3. 如果 1H open 已经在强平价之外，按 open（或更差的可执行价）成交，不能按理论强平价成交；
4. 强平成交价再加 `fee_buffer` 和压力滑点（正常 1–3bps，cascade 5–10bps，极端 20bps）；
5. 记录 `liquidation_event`、触发 mark price、理论强平价、实际成交价、剩余 margin、强平费和坏账风险；
6. 日收盘只用于报告，不能用于触发强平；
7. ADL 不在 base case 中假设发生，但必须作为尾部场景单独报告：如果仓位 notional 超过对应合约 open interest 的 1%，需要额外压力测试。


### 6.3 信号层

H5 的多头选币和 gross 目标保持不变。衍生品层只做三件事：

- 对 H5 多头 gross 乘以杠杆 L；
- 可选地在熊市确认下加入负权重空头；
- 把总 gross 限制在 `max_gross`。

默认不改变 H5 的 3 日相位、Top2 hold band、BTC 100D gate 和 dispersion overlay。

## 7. 预注册试验

本轮登记以下 7 个主试验和 4 个预注册邻域。除此之外，任何新邻域只有在主试验通过 kill criterion 后才登记；所有登记项都进入 trial ledger，不能只报告胜者。

| ID | 方向 | 规则 | 默认 gross 上限 |
|---|---|---|---:|
| `PR2026-10-D-L125` | long | H5 gross × 1.25 | 1.25x |
| `PR2026-10-D-L150` | long | H5 gross × 1.50 | 1.50x |
| `PR2026-10-D-L200` | long | H5 gross × 2.00，仅压力测试 | 2.00x |
| `PR2026-10-D-SBTC25` | long + short BTC | BTC < 200D MA 且 30D return < 0 且 funding 不为深度负，short 0.25x | 1.25x long + 0.25x short |
| `PR2026-10-D-SBTC50` | long + short BTC | 同上，short 0.50x | 1.25x long + 0.50x short |
| `PR2026-10-D-SWEAK25` | long + short weakest | 同熊市确认，short Top20 最弱 1 币 0.25x | 1.25x long + 0.25x short |
| `PR2026-10-D-SWEAK50` | long + short weakest | 同上，short 0.50x | 1.25x long + 0.50x short |

所有试验必须登记到：

```text
reports/research_trial_inventory/preregistered_trials.csv
```

试验数必须进入新的 multiple-testing scope。禁止只报告胜者。

### 7.1 规则的精确预注册

**Long book**

```text
w_long_i,t = L × w_H5_i,t
if Σ|w_long_i,t| > max_gross:
    w_long_i,t = w_long_i,t × max_gross / Σ|w_long_i,t|
```

`L ∈ {1.25, 1.50, 2.00}`。H5 的选币、3 日相位、Top2 hold band、BTC 100D gate 和 dispersion overlay 全部不变。H5 未持有的币不允许因为“Bitget 有合约”而临时加入。

**Bear regime**

```text
bear_t = (BTC_close_t < SMA_200(BTC)_t) AND (BTC_close_t / BTC_close_{t-30} - 1 < 0)
```

**Funding filter**

```text
btc_funding_3d_t = mean(最近 3 个 BTC funding settlement)
weak_funding_3d_t = mean(最近 3 个目标空头币 funding settlement)
funding_filter_t = (btc_funding_3d_t > -0.0001) AND (weak_funding_3d_t > -0.0002)
```

`-0.0001` 和 `-0.0002` 是每 8 小时 funding rate，不是年化。缺失 funding 时 `funding_filter_t = False`，该日不开新空头；已有空头按下一可执行时点平仓。

**Weakest Top20**

```text
eligible_t = {i ∈ PIT_CMC_Top20_t : Bitget USDT-M contract exists and passes data audit}
weakest_t = argmin_{i ∈ eligible_t} (price_i,t / price_i,t-30 - 1)
```

**Short overlay**

```text
target_short_t = w_short × weakest_t   if bear_t and funding_filter_t
target_short_t = 0                     otherwise
w_short ∈ {0.25, 0.50}
```

执行：信号在 UTC 日线收盘生成，T+1 的 +3h 执行。若 `weakest_t` 改变，先平旧空、再开新空；若离开 PIT Top20、失去 Bitget 合约或 funding filter 失效，下一可执行时点平仓。base case 不加额外止损；`D-S-BTC25-STOP20` 和 `D-S-WEAK25-STOP20` 作为预注册邻域，分别测试“空头浮亏达到 20% 时平仓”的规则。

**Margin**

```text
long_margin_ratio  = max(0.30 + MMR_i + 0.005, 0.25)
short_margin_ratio = max(0.50 + MMR_i + 0.005, 0.50)
```

初始保证金不足时按比例缩小 notional，不提高单仓杠杆。

### 7.2 试验记账与多重检验 scope

主试验共 7 个：

```text
PR2026-10-D-L125
PR2026-10-D-L150
PR2026-10-D-L200
PR2026-10-D-SBTC25
PR2026-10-D-SBTC50
PR2026-10-D-SWEAK25
PR2026-10-D-SWEAK50
```

预注册邻域共 4 个：

```text
PR2026-10-D-S-BTC25-STOP20
PR2026-10-D-S-WEAK25-STOP20
PR2026-10-D-L125-COST50
PR2026-10-D-L125-COST100
```

Derivatives Track 的 multiple-testing scope 以这 11 个为初始 N。任何新增杠杆、空头阈值、stop、funding 阈值或执行变体都必须 append 到 `reports/research_trial_inventory/preregistered_trials.csv`，并同步增加 N。H5 的 N=6,138 继续独立报告，不能用来替代或放宽本 scope 的 DSR/PBO。


## 8. Kill Criteria

### 8.1 杠杆多头

候选必须同时满足：

- 主样本内无强平事件；
- 项目最大回撤 <= 50%；
- 终值 >= 1.20 × 同成本 H5 终值；
- Sharpe >= 0.90 × 同成本 H5 Sharpe；
- 在 6/8/11/20/50/100 bps 成本下方向一致；
- 在 2020-10 至 2021-12 stress window 不出现强平；
- 真样本外 2026-09-22 起不出现强平，且回撤不超过主样本最差一档。

### 8.2 空头 overlay

候选必须同时满足：

- 主样本内无强平事件；
- 相比同杠杆 long-only，最大回撤改善至少 5 个百分点；
- Sharpe 不低于同杠杆 long-only；
- 空头年化贡献不能只来自少数几个事件；必须做 best-trade removal；
- 资金费压力 2x/3x 后仍不改变结论；
- 真样本外不允许为了通过而修改熊市阈值。

### 8.3 数据质量

以下任一情况直接判定无效：

- 资金费缺失被填零；
- 使用当前 Top20 回填历史成员；
- 用 Top20 之外资产替代缺失合约；
- 强平只用日收盘；
- 返佣被静默计入量化账户 NAV；
- 把 Binance funding 称为 Bitget 精确历史；
- 在 funding 代理未通过重叠门槛时仍把它用于精确 funding attribution；
- 只报告 best parameter，不报告全部 trial。

### 8.4 决策树

```text
先跑 L125/L150/L200 long-only
  ├─ 无候选通过：不启用杠杆，保留 H5 现货轨道
  ├─ L125 通过：以 L125 为主候选，L150/L200 只作为压力
  └─ L125/L150 都通过：优先 L125，除非 L150 在全部成本和 OOS 上都不触碰 50% MDD

在通过的 long-only 上再跑 BTC short
  ├─ 不通过 MDD/Sharpe kill criterion：不启用空头
  └─ 通过：再跑 weakest-Top20 short，且必须先通过 funding 2x/3x 压力

所有候选都必须先通过数据质量、强平、成本、多重检验和 OOS
  └─ 任一失败：保持 provisional，不上线
```

空头 overlay 不允许用来“救活”失败的 long-only 杠杆候选；它只能作为通过 long-only 之后的独立 overlay 测试。


## 9. 稳健性与多重检验

新轨道必须沿用并扩展旧项目的稳健性工具：

- 参数邻域：杠杆 1.25/1.5/2.0；空头 0.25/0.5；
- 多个起始日：2022 年起所有月度起点；
- 滚动一年最差结果；
- 分年、分市场 regime、bull/non-bull；
- best year removal；
- best trade removal；
- entrant/incumbent attribution；
- White Reality Check；
- Deflated Sharpe；
- PBO/CSCV；
- terminal-wealth bootstrap；
- liquidation-event bootstrap。

新轨道不继承 H5 的 DSR 通过状态。H5 的 DSR 仍是 0.858，低于 0.95；新增试验只会让原 scope 的 N 更大。

### 9.1 Derivatives Track 的多重检验 scope

H5 的 DSR 在 N=6,138 下为 0.858，结构性不可达。Derivatives Track 不能继承这个结论，也不能用它来放宽 H5。新轨道必须单独计算：

- White Reality Check / stepwise；
- Deflated Sharpe Ratio，scope = 上述 11 个 pre-registered trials；
- PBO/CSCV，候选矩阵覆盖 11 个 trials；
- terminal-wealth bootstrap；
- liquidation-event bootstrap；
- best-year removal、best-trade removal、best-coin removal；
- 月度起始、逐年、bull/non-bull、entrant/incumbent 拆分。

Derivatives Track 的 DSR 门槛仍为 0.95。若 11 个 trials 的 DSR < 0.95，候选保持 provisional，不得上线。若通过，仍需 12 个月真样本外和 Phase 5 的上线阶梯。


## 10. 风险控制

### 10.1 账户级

- 量化账户最多使用总资金 3%；
- 项目最大回撤 25%：告警并人工复核；
- 项目最大回撤 50%：停止新开仓，转入纸面交易；
- 交易所对手方风险：不在 Bitget 存放超过项目资金上限的资产；
- 不把主账户返佣自动当作量化账户保证金。

### 10.2 仓位级

- 默认 gross <= 1.25x；1.5x/2.0x 仅压力；
- 空头 gross <= 0.5x；
- 单币空头 <= 0.25x；
- 入场时 long 到强平距离 >= 30%；
- 入场时 short 到强平距离 >= 50%；
- 24h 预期资金费 > 0.5% equity 时降仓；
- 资金费连续 3 个结算点逆风时复核；
- 单币持仓不超过账户 equity 的 60%，除非 H5 原始信号和波动率目标同时允许。

### 10.3 运营级

- 每日 Telegram 推送必须包含：目标持仓、调仓、预估资金费、强平价和保证金缓冲；
- 没有 Bitget 合约的标的必须显示 `CASH / unavailable`；
- 所有订单执行后回写实际成交价和手续费；
- 每日对账：策略账户、主账户返佣、资金费、手续费分开。

### 10.4 保证金与资金操作

- 衍生品账户总资金不超过总财富的 3%；初始实盘 pilot 不超过总财富的 0.1%。
- 账户内最大 gross 1.25x；1.5x 只作为压力，2.0x 只作为研究。
- 任何时点至少保留 30% 账户 equity 为未占用现金；初始保证金占用不超过 equity 的 85%。
- 主账户 60% 返佣是外部现金流；量化账户 NAV 使用完整 6bps Taker。返佣单独记录为 `rebate_external_cashflow`，只有实际划回量化账户时才作为 `cash_injection` 建模。
- 每日对账必须分开：策略账户权益、未实现 PnL、funding、手续费、强平费、返佣外部现金流。
- 资金费、手续费、返佣、强平费任何一项缺失，当日信号标记 `UNVERIFIED`，不允许自动加仓。


## 11. AGENTS.md 拟修订

在负责人批准本设计后，建议在 `AGENTS.md` 增加独立的 `Derivatives Research Track` 章节，明确：

- 原 `Spot Track` 的 long-only、无杠杆约束不变；
- `Derivatives Track` 允许 long/short、默认 gross 1.25x、压力 1.5x/2.0x、空头 0.5x；
- 主样本、OOS、成本、数据质量、强平和多重检验要求；
- 返佣不计入量化账户 NAV；
- 新轨道不能用来重定义 H5 的验收结果。

## 12. 分阶段实施

### Phase 0：设计审阅与预注册

- 负责人审阅本设计稿和 `docs/research/derivatives_track_research_2026-10.md`；
- 明确是否接受 1.25x 作为默认上限、1.5x 仅压力；
- 明确空头 overlay 的 MDD 改善门槛是否保持不变；
- 把 11 个 trials 写入 `reports/research_trial_inventory/preregistered_trials.csv`；
- 只有在负责人批准后，才修改 `AGENTS.md` 增加独立的 `Derivatives Research Track` 章节。


### Phase 1：数据和仪器（数据层已实现，审计未全通过）

- 已实现 Bitget 合约、mark/index/market K 线、funding history 客户端；
- 已实现 PIT Top20 → Bitget symbol 映射、可恢复下载器和覆盖审计脚本；
- 已下载 BTC/NEAR/SOL 的 90 天 Bitget funding，并完成与 Binance 的重叠验证；
- **审计结论：funding 代理未通过 §5.2.1 的预注册门槛**；
- 仍需全量下载 88 个映射合约 × `mark/index/market`，并解决 historical funding 数据源问题。

### Phase 2：引擎

- 实现 isolated margin、funding、fees、liquidation；
- 用单元测试覆盖 long/short 强平边界；
- 用现有 H5 日权重做 1.0x 校验，确认与现货结果一致；
- 再用 1.25x/1.5x/2.0x 跑预注册试验。

### Phase 3：空头 overlay

- 先只做 BTC short；
- 再做 weakest-Top20 short；
- 每一步都做资金费 1x/2x/3x 压力；
- 空头 overlay 只有同时改善回撤和 Sharpe 才继续。

### Phase 4：真样本外

- 从 2026-09-22 起冻结规则；
- 每日记录实际 signal、order、fill、funding、fee、margin；
- 至少累积 12 个月 OOS 后才评估是否上线。

### Phase 5：上线阶梯

任何真实资金上线都不能跳过以下阶梯：

1. **Shadow**：只记录信号、订单和模拟成交，至少 30 天；
2. **Micro-live**：最多总财富 0.1%，验证真实 funding、手续费、返佣、标记价和强平接口，至少 30 天；
3. **Scale**：只有 12 个月真样本外 + DSR/PBO/Reality Check + 无强平 + 最大回撤门槛全部通过后，才允许把资金提升到总财富 3%。

Micro-live 是运营验证，不是“策略已通过验证”的声明；它不能用来绕过任何 robustness gate。


## 13. 当前不做的决定与负责人签核清单

- 不决定是否在 1.25x 默认档位之上启用 1.5x/2.0x；
- 不决定 BTC short 还是 weakest short 最终上线；
- 不决定是否把返佣划回量化账户；
- 不决定是否购买 Bitget 历史数据供应商；
- 不决定是否接受 funding-uncertain 的 proxy/压力带回测口径；
- 不决定是否使用 cross margin。

这些都必须由 Phase 1–3 的结果决定，不能在看结果前写死。

负责人签核清单：

- [ ] 接受 `Spot Track` 不变，`Derivatives Track` 独立预注册、独立验收；
- [ ] 接受 1.25x 为默认候选上限，1.5x 仅压力，2.0x 仅研究；
- [ ] 接受空头 gross ≤0.5x、单币 short ≤0.25x、long/short 强平距离 ≥30%/≥50%；
- [ ] 接受主账户 60% 返佣不计入量化账户 NAV；
- [ ] 接受 11 个预注册 trials 和独立 multiple-testing scope；
- [ ] 接受 Phase 0–5 的实施顺序和 12 个月真样本外门槛；
- [ ] 明确是否允许 Bitget 现货 leg 进入未来的独立 carry 研究（本设计不包含）。
