# Atlas20 策略研究记录（唯一权威版本）

> 本文取代此前所有口头结论、临时 `/tmp` 结果、旧报告和 README 里过时的策略叙述。
> 与本文冲突的旧数字一律作废。
>
> | | |
> |---|---|
> | 最后更新 | 2026-10-09（§00.13 采用 **H5**；§00.15–00.17 三族外部状态筛查全部被拒；§00.18 当前信号 = 100% NEAR / 目标 gross 0.621，全样本 22.68x @20bps（至 10-07），样本外 2026-09-22 起 17 天 **0.9689x vs BTC 0.9431x**；§00.19 资金费率 overlay（H6）**被拒**；**§00.20 上线路线：DSR 在 N=6,138 下结构性不可达，需负责人先做规则决策**；样本内结论仍以 2026-09-25 审计为准） |
> | 数据 | `data/processed/panel_daily.csv`，研究样本 2022-01-01 → **2026-09-21**；冻结规格样本外跟踪 2026-09-22 → **2026-10-07** |
> | 数据口径 | 市值与排名来自 CoinMarketCap；Gate/Binance/CoinGecko 只做独立校验；当天没有 CMC 市值的币当天不参与排名 |
> | 杠杆 | **全部无杠杆**：引擎默认并强制 gross exposure ≤ 1.0（>1 直接报错），不做空 |
> | 执行 | 信号收盘生成、T+1 执行；**实盘口径为收盘后约 3 小时成交**（02:30 UTC 刷新之后），用 Binance/Gate 1 小时 K 线模拟；缺失行情不静默填 0（短缺口按 carry 规则持有并逐条报告） |
> | 成本口径 | 基准 **2bps**（AGENTS.md），20/50/100bps 为压力测试 |
> | 主回测起点 | **2022-01-01**，剔除 2021 泡沫行情 |

> **硬约束（不可突破）**：所有策略研究、回测和实盘候选必须严格限制在 **point-in-time Top 20** 内。不得使用 Top 50、Top 100 或任何更宽股票池，包括“仅作灵敏度测试”的场景；如果某个假设需要更宽股票池，应直接否决或重新设计为 Top 20 内可验证的版本。Top 20 必须按当时真实市值重建，禁止用当前名单回填历史。

---

## 00. 2026-09-25 全面审计与修复后的权威结论（取代 §0 中与此冲突的数字和判定）

> 2026-09-23 → 09-25 对全仓库做了代码审查（数据层、回测引擎、策略、验证统计、API、前端、历史研究代码）。每个确认的缺陷都先写失败测试再修复；随后在修复后的代码上重跑了全部 phase momentum 报告。研究样本仍为 2022-01-01 → 2026-09-21，**此后的数据保留为冻结冠军的真正样本外**，不再用于任何挑选。

### 00.1 判定：冠军仍是研究候选（provisional），不是已验证策略

> **规格已被 §00.11 取代（2026-10-08）**：冻结规格现在是 H3（Top20 宽度共闸 50/50 混合，`PR2026-10-H3`），不再是本节表中的 B（单 book 冠军）。下表保留为切换前的 B 审计记录，数字仍然有效（B 依旧是基线）。

| 门槛（AGENTS.md） | 结果 | 判定 |
|---|---|---|
| ≥20x（基准成本 2bps，实盘成交时点：收盘后 3h，取两种缺 K 线假设中较差者） | **24.42x**，Sharpe 1.45，最大回撤 -43.7% | 通过 |
| 20bps 压力，同一成交时点 | **19.56x**（50bps 13.50x，100bps 7.27x） | 略低于 20x |
| 多重检验：Deflated Sharpe，按项目真实试验数 | Top20/2022 口径 N=6,132：**0.731**；全部 N=14,126：0.678；只算 30 个变体家族：0.995 | **失败**（<0.95） |
| 事后挑参数的过拟合概率 PBO | 0.526 | **失败**（>0.5）；只能用固定主规格 |
| 参数邻域 | BTC 闸门 MA100 → MA50/MA150/MA200：9.50x/11.61x/6.93x；持有排名 Top2 → Top1/Top3：14.55x/9.49x（20bps，收盘成交）；H2/H3 预注册邻域复核见 §00.6 | **失败**：结果依赖单一窄参数（AGENTS.md 明确不算稳健） |
| White Reality Check（30 变体家族） | 对零 p=0.019；对 BTC 买入持有 p=0.025 | 家族内通过；全项目无法计算（多数历史试验没有保存日收益） |
| walk-forward（预设 25 变体，365D 训练/90D 测试，2023 起，40bps 切换成本，收盘成交） | 20.78x，Sharpe 1.62 | 通过（仅收盘成交口径） |
| 去掉最佳年份 2023 | 4.83x（BTC 0.73x） | 仍优于 BTC |
| 2020-10 → 2021-12 压力 | 20bps 4.55x，Sharpe 2.39，回撤 -18.9%（BTC 4.39x） | 通过 |
| 逐条选币审计（更严格版本） | 10,308 条选币、3,436 次持有规则检查、990 条成交目标：0 违规 | 通过 |

结论：按 AGENTS.md，冠军在**基准成本下即使按真实成交时点也超过 20x**，但**多重检验（DSR 0.73、PBO 0.53）和参数窄峰两道门槛不通过**，所以只能保持 provisional。这两项都来自研究历史本身（6,132 次 Top20 试验、窄峰参数），在同一段样本上再怎么调都无法修复；唯一干净的办法是冻结规格，用 2026-09-21 之后没有任何试验见过的数据做真正的样本外检验。2026-10-08 按预注册补跑的 H2/H3 邻域（6 个新试验，见 §00.6）进一步显示：窗口集成 H2 去掉 MA50/MA100/MA150 任一窗口即失去判据，宽度共闸 H3 只在 0.55 阈值下保住判据——两者都只能作为已记录的 risk variant，不能替代或“修复”冠军。

### 00.2 修正前后对照（旧数字一律作废）

| 项目 | 旧（§0.1/§0.2） | 新（2026-09-25） | 说明 |
|---|---|---|---|
| 成交时点 @20bps | 未测，隐含“收盘价成交” | 收盘 23.09x；+1h 21.22x；**+3h 19.56x**；+6h 20.78x；+12h 21.57x；次日收盘 12.01x；延迟 2 天 5.11x | `reports/phase_momentum_execution_lag_2022/`；91.8% 的成交权重在成交时刻有可用的 Binance/Gate 小时 K 线，其余（Bitget Token 两家都没有、个别币在交易所上市前的日期、开盘价与 CMC 前收差距 >5% 的日期）分别按“次日收盘”和“信号收盘”两种假设成交，取较差者 |
| Deflated Sharpe | 0.9945（只按 32 个候选） | 家族 0.995；**Top20/2022 全部试验 0.731**（N=6,132）；全部试验 0.678（N=14,126） | `reports/research_trial_inventory/`（可复现盘点）、`reports/phase_momentum_multiple_testing_2022/` |
| White Reality Check | p=0.0150 | 家族对零 p=0.019、对 BTC p=0.025 | 旧值只对主策略单独做，没有任何多重校正 |
| PBO | 0.6288 | 0.526 | 按论文 logit 规则、去掉 2 个与主策略完全相同的候选、分块覆盖全部日期 |
| 固定主策略 CSCV | “通过”，低于中位数 7.47% | 2.06% | **不再计为证据**：训练/测试排名分布在构造上相同，只是样本内诊断 |
| 固定主策略 2023 起 | “OOS 29.91x” | 29.91x | **重标为样本内**：参数是用全样本挑的 |
| 市场状态拆分 | bull 51.83x / non-bull 0.445x | bull **25.37x**（BTC 3.27x）；non-bull **0.91x**（BTC 0.57x） | 旧版用当天收盘判定当天状态（前视），现用前一天状态 |
| 币自身趋势过滤 50/100/150/200D | 17.57/14.71/10.68/10.57x | **24.39/16.70/17.03/11.13x** | 旧版按列而不是按行取趋势，导致每天强制换仓；trend_50 事后看三项都优于主策略，但属事后发现，不能直接升级 |
| 参数等权集成 | “等权” | 按参数组真正等权：20bps **16.63x**；leave-one-parameter-out 15.81–17.65x | 旧版实为按 sleeve 等权 |
| 月度起点敏感性（54 个起点） | 沿用 2022 年起的路径 | 每个起点重新构建：中位 7.18x，最差 1.69x，最好 31.57x | 旧版切片起步空仓且继承 2022 路径 |
| 收盘成交主数字 | 20bps 23.09x、2bps 28.80x | 不变 | 各项修复没有改变冠军的实际交易 |

### 00.3 本轮修复中影响研究数字的缺陷

- **回测引擎**：权重上限按 NAV 而不是按已投资部分施加；NaN 目标/敞口直接报错；窗口外的目标日期不再静默丢弃；杠杆被默认禁止；新增收盘后 H 小时成交（`pre_fill_returns`）和短缺口 carry 规则（`gap_carries` 逐条报告）。
- **股票池/数据**：缺行情日的成交量不再填 0；缺口日收益改为缺失并由下一次报价补齐跨缺口涨跌，不再静默记 0；**当天没有 CMC 市值的币当天不参与排名**（2022-07-31 chainlink、kucoin-shares，2022-07-29/30 curve）；CoinGecko 日期错位一天（中位偏差 2.61% → 0.079%）；多源校验不再“一个源通过就忽略其他源的分歧”；CEL 别名错指到 COMP（已移除）；120 日均线预热不足（buffer 按配置最长回看推导）；数据层对 2022 年以来的面板数值**零改动**。
- **分析指标**：Sortino 改用下行偏差；回撤从初始资金起算；切片结果的总收益不再丢第一天；月末再平衡日不再把未结束月份的最后一天当月末；类别排除（稳定币等）的兜底真正生效；总市值指数改为链式计算（不再受面板进出影响）。
- **验证统计**：见 §00.2；试验盘点改为仓库内可复现脚本 `scripts/build_trial_inventory.py`，并新增预先登记台账 `reports/research_trial_inventory/preregistered_trials.csv`。

### 00.4 下一步

1. **冻结**当前主规格（`PhaseMomentumSpec` 默认值 + `PRIMARY_SIGNAL_SPECS`），以 2026-09-22 起的数据做真正样本外记录，不再调参。
2. **预先登记的新一轮假设**（依据 `docs/research/literature_review_2026-09.md` 第 4 节，参数全部来自文献或已有消融，不做网格）：H2 BTC 闸门窗口集成、H3 Top20 市场宽度共同闸门、H4 每个 sleeve 持有前五分之一（4 个币）。结果写入 `reports/phase_momentum_hypotheses_2026_10/`，每次运行先登记再执行，计入试验总数。
3. **H1（23:00 UTC 提前一小时决策、收盘成交）需要项目负责人决定**：它与“信号在收盘生成”的规则冲突，未经确认不运行。符合现行规则的替代方案是缩短数据链路：+1h 成交在 20bps 下为 21.22x（+3h 为 19.56x）。该替代方案的落地清单见 `docs/operations/execution_latency.md`。**测量已于 2026-10-08 启动**：`ops/com.atlas20.cmc-probe.plist` 已安装为 launchd 作业，在 00:05–03:50 UTC 每 15 分钟跑一次 `scripts/probe_cmc_publication.py`（每次 10 个币、160 请求/天，约为一次正常刷新的 1.5 倍），结果追加写入 `reports/provider_publication/cmc_publication_probe.csv`；首次冒烟运行成功（2026-10-07 覆盖 10/10）。用 T90（≥90% 样本拿到 D-1 的最早 UTC 时刻）决定刷新时点与成交时点。

### 00.5 2026-10-08 冻结规格样本外跟踪（16 天，仍为 provisional）

> **规格已被 §00.11 取代（2026-10-08）**：本节记录的是切换前的 B（单 book 冠军）。`reports/phase_momentum_oos_2026/` 现在跟踪 H3；在这 16 天里宽度共闸从未触发，H3 与 B 的收益逐位相同，所以本节数字对 H3 同样成立。

- **规格冻结**：`PhaseMomentumSpec` 默认值 + `PRIMARY_SIGNAL_SPECS`；没有根据 2026-09-22 之后的结果调参、换币、改成本或改执行规则。
- **样本外窗口**：2026-09-22 → 2026-10-07，共 16 个日收益。面板已刷新至 2026-10-07，且该日通过完整收盘校验（97 个资产全周数据、成交量与市值覆盖率达标）。
- **执行口径**：信号收盘生成，T+1；实盘成交按收盘后 3 小时，使用 Binance 1 小时 K 线。该窗口实际交易目标为 `NEAR`、`ZEC`，小时 K 线成交权重覆盖率为 **100%**，因此 `day_close` 与 `prior_close` 缺 K 线假设在本窗口结果相同。

| 成本 | +3h 总收益 | Sharpe | 最大回撤 | BTC 同期 |
|---:|---:|---:|---:|---:|
| 2bps | **1.0902x** | 3.316 | -10.50% | 0.9616x |
| 20bps | **1.0883x** | 3.260 | -10.57% | 0.9616x |
| 50bps | **1.0853x** | 3.166 | -10.67% | 0.9616x |
| 100bps | **1.0803x** | 3.009 | -10.84% | 0.9616x |

- **解读**：样本外开局为正，并跑赢同期 BTC；但 16 天远远不足以通过 DSR、PBO、参数邻域和多年份稳健性门槛。冠军仍然是 **provisional**，这段结果不能用来解除任何门槛，也不能反过来成为调参依据。
- **最新信号（截至 2026-10-07）**：BTC 100D 闸门开启；12 个 sleeve 的聚合目标为 `NEAR 68.37%`，生产引擎当前漂移仓位为 `NEAR 70.62%`；最近一次目标日期为 2026-10-03，因此当前 `trade_required=false`；下一次检查日期为 2026-10-08。
- **数据链修正（2026-10-08 刷新）**：EOS、HT、MKR 在迁移/退市后 CMC 仍打印 legacy 价格但 `marketCap=0`。处理器现在截断「最后一次正市值之后、超出 7 天宽限」的纯价格尾部，并把「市值 feed 已结束、当前独立缓存无法回看比对」的资产标记为 `crosscheck_historical_unverified`：历史保留（point-in-time 名单不重写），但市值结束日之后永不参与排名；审计对这类资产报 WARN 而非 FAIL，已证实的分歧仍然 FAIL。HT 的 34 行价格级损坏（已移除）在缺口检查中按文档化移除豁免为 WARN。数据链审计现为 **FAIL=0**（42 PASS / 9 WARN）。
- **对研究样本无影响（已核验）**：被截断的行全部在「最后一次正市值」之后；`build_rebalance_universe` 对 carry 来的市值明确拒绝排名（逐日记录 "no same-day market cap from CMC"）。在 2022-01-01 → 2026-10-07 的日频名单里，EOS、HT 从未进入 universe，MKR 最后一次进入是 2023-10-14（其市值 feed 结束于 2025-05-25），因此被截断的行不可能被选中或持有；冠军与 H2-H4（样本到 2026-09-21）的选币名单和组合收益不会因本次截断而改变。
- **复现**：`.venv/bin/python scripts/run_phase_momentum_oos.py --end-date 2026-10-07`；最新信号 `.venv/bin/python scripts/run_phase_momentum_live_signal.py --output-dir reports/phase_momentum_live`。报告在 `reports/phase_momentum_oos_2026/`，不包含任何参数搜索。


### 00.6 2026-10-08 H2/H3 预注册邻域结果（6 个新试验，N 6,126 → 6,132）

- **为什么现在跑**：文献综述 §4 规定邻域只在父假设通过 kill criterion 之后运行；H2（8.79x）和 H3（19.90x）在 2026-09-25 都通过了各自判据，因此按预注册先登记、后运行 6 个新试验：H2 的 4 个 leave-one-window-out 集成（分别去掉 MA50/100/150/200）与 H3 的相邻阈值 0.45/0.55。样本窗口、成本与成交口径不变（2022-01-01 → 2026-09-21；20bps 判定，2/50bps 复读；+3h 成交、两种缺 K 线假设取较差者）。每个邻域试验沿用其父假设的判据。
- **H2（BTC 闸门窗口集成）不稳健**：4 个 LOO 里只有去掉 MA200 的集成保住判据；去掉 MA50/MA150 超回撤容忍（MDD 差于 B 的 2 个百分点），去掉 MA100 低于四个单窗口变体的中位数（7.67x）。

| LOO（去掉） | 20bps +3h 总收益 | 最大回撤 | 判定 |
|---|---:|---:|---|
| MA50 | 9.93x | -51.5% | FAIL（回撤超限，阈值 -47.7%） |
| MA100 | 7.37x | -47.8% | FAIL（低于单窗口中位数 7.67x） |
| MA150 | 8.71x | -47.8% | FAIL（回撤超限） |
| MA200 | 9.91x | -42.7% | 通过 |

- **H3（Top20 宽度共同闸门）只在 0.55 阈值下稳健**：阈值 0.55 在 20/2/50bps 三个成本下都满足全部三个端点（20bps：MDD 改善 10.91pp、Sharpe 1.383 > B 1.370、1 年滚动最差 0.744 > B 0.711）；阈值 0.45 在 20bps（MDD 改善 7.00pp）与 2bps 通过，但 50bps 回撤改善降到 4.70pp（<5pp）→ 方向不一致，判为未通过。
- **判定与门槛不变**：邻域结果只用于稳健性解读，冠军仍冻结、仍为 **provisional**；新增 6 个试验使 DSR 分母从 N=6,126 升到 **N=6,132**，冠军 DSR 由 0.735 降到 **0.731**（全部试验口径 0.682 → 0.678；家族 30 口径 0.995 不变），PBO 0.526 不变，DSR/PBO/窄峰三关结论不变（仍失败）。
- **复现**：`.venv/bin/python scripts/build_trial_inventory.py` → `scripts/run_phase_momentum_hypotheses.py` → `scripts/run_phase_momentum_hypotheses.py --evaluate-only` → `scripts/run_phase_momentum_multiple_testing.py`。明细见 `reports/phase_momentum_hypotheses_2026_10/neighbourhood.csv` 与 `reports/phase_momentum_multiple_testing_2022/`。

### 00.7 2026-10-08 入场者归因：冠军收益来自在位币，不是临时入场币（直接检验 [S16]）

- **为什么做**：文献综述 §3.9 与 §4.0 要求每个假设把收益拆成「进入 Top20 不超过 29 天的入场币」与「在位币」，用来直接检验 [S16]（Grobys et al. 2026, *On survivor cryptocurrency momentum*）的幸存者批评——「加密动量收益是那些只能临时交易的币的假象」。这是一个**预声明**的归因指标，不是新试验，不计入 N。
- **口径**：用引擎实际账本按日归因（目标日按成交时刻前/后分段计收益，其余按漂移仓位），按**信号日 t-1** 的 CMC Top20 身份分类：`entrant` = 当前连续入榜区间开始 ≤29 天；`incumbent` = ≥30 天；`non_member` = 持有但当天已不在 Top20（正常应为 0）。贡献 = Σ 各币当日「权重 × 收益」；份额 = 该类贡献 / 全部贡献之和。样本 2022-01-01 → 2026-09-21，成本 20bps。
- **结果（冠军 PR2026-10-B）**：

| 成交口径 | entrant 份额 | incumbent 份额 | non_member 份额 | entrant 贡献 | incumbent 贡献 |
|---|---:|---:|---:|---:|---:|
| 收盘成交（lag 0） | **-7.81%** | 107.81% | 0.00% | -0.322 | 4.447 |
| +3h（`day_close`，较差口径） | **-9.28%** | 107.49% | 1.79% | -0.367 | 4.254 |
| +3h（`prior_close`） | **-7.97%** | 106.98% | 0.99% | -0.318 | 4.264 |
| 延迟一天（lag 1） | **-15.23%** | 110.70% | 4.53% | -0.526 | 3.821 |

- **解读**：在冠军里，入场币是**小幅负贡献**（实盘 +3h 口径 −8% 到 −9%），在位币贡献了全部收益（>100%）。也就是说冠军的收益**不是** [S16] 所说的「临时可交易币」假象，反而是这些新入榜币略微拖累收益；延迟一天时入场币的负贡献扩大到 −15%，与「入场币是最滞后、最容易被延迟吃掉的那部分」一致。H3（Top20 宽度共闸）的入场币份额约 −0.5%（风险关闭时入场币更少），方向相同。
- **对 seasoning filter（只买上市/入榜满 N 天的币）的判定**：文献综述 §5 的逻辑是「若入场币贡献收益，则 seasoning 砍掉收益来源；若不是，则 seasoning 无关紧要」。这里入场币贡献为负，所以按该逻辑 seasoning **无关紧要**；虽然事后看剔除它可能小幅提高样本内收益，但那是**在样本上事后挑选**、且会引入一个新自由参数（窗口 N）、进一步抬高 N，因此**不新增该试验**。
- **边界**：这是单一样本（2022-01-01 → 2026-09-21）的归因，不构成稳健性证据，也不改变冠军的 provisional 状态。它只回答「收益是否来自临时入场币」这一个问题。
- **复现**：`.venv/bin/python scripts/run_phase_momentum_hypotheses.py`（完整运行会在 `reports/phase_momentum_hypotheses_2026_10/` 写出 `entrant_attribution.csv`；`--evaluate-only` 只重算判定并读取该文件）；明细见同目录 `entrant_attribution.csv`（同一脚本输出 H2/H3/H4 与邻域的全部归因行）。

### 00.8 2026-10-08 逐币归因：20x 是「五个币」的故事（AGENTS.md 的「单一资产依赖」条款）

- **为什么做**：AGENTS.md 明确「结果不能依赖一个窄参数、一个相位、一年、**一个资产**或少量交易」。此前项目只做过 leave-one-sleeve（21.26x–23.91x）、leave-one-signal（20.58x–27.58x）和去掉最佳年份，**没有做过逐币归因**。这是补上这一条，不是新试验。
- **口径**：与 §00.7 入场者归因完全相同的引擎账本会计（目标日按成交时刻前/后分段，其余按漂移仓位），但保留币维度：贡献 = Σ 每日「权重 × 收益」，share = 该币贡献 / 全部贡献之和。冠军、20bps、+3h、较差缺 K 线口径（`h3_day_close`，19.5575x）。
- **结果（贡献份额，前 7 名）**：

| 排名 | 币 | 贡献 | 份额 | 累计 |
|---:|---|---:|---:|---:|
| 1 | solana | 1.216 | 30.73% | 30.73% |
| 2 | zcash | 0.708 | 17.89% | 48.62% |
| 3 | hyperliquid | 0.573 | 14.48% | 63.10% |
| 4 | avalanche-2 | 0.556 | 14.05% | 77.15% |
| 5 | bitcoin-cash | 0.521 | 13.15% | **90.31%** |
| 6 | sui | 0.362 | 9.16% | 99.46% |
| 7 | dogecoin | 0.334 | 8.45% | 107.92% |

前 5 个币合计 **90.31%**；贡献 HHI = 0.2112。共持有过 37 个币，而且**被选中的 sleeve-日分布是均匀的**（10,308 条选币里最高是 hyperliquid 8.1%、solana 7.8%、zcash 6.9%）——所以集中不是「一直满仓某个币」，而是少数几个币在被持有期间跑出了极端行情（文献 [S14]「一个币就能决定大盘动量组合」的形态）。
- **反事实（只去掉该币的每日贡献，仓位不变）**：

| 情景 | 终值 |
|---|---:|
| 完整冠军 | **19.56x** |
| 去掉 solana | **6.62x** |
| 去掉前 3（SOL/ZEC/HYPE） | **2.07x** |
| 去掉前 5（+AVAX/BCH） | **0.80x** |

去掉前 3 后只剩 2.07x（BTC 买入持有为 1.87x），去掉前 5 后直接亏损。**必须同时说明：这不是一个可交易策略**——事前不知道哪 5 个币会赢——它只回答「收益从哪来」，是集中度度量。
- **判定**：这**直接触发 AGENTS.md 的「不能依赖单一资产」条款**，是冠军必须保持 **provisional** 的又一条独立理由，且这条在样本内无法修复：唯一被预注册过的分散化方案 H4 已被证伪（3.15x）。H3（宽度共闸）也解决不了它——前 5 份额 84.1%，去掉前 5 后 1.08x，只是略好于冠军。
- **对后续的含义**：① 样本外跟踪必须同时报告这个集中度（同样的 5 个币是否还在贡献收益）；② 任何「提高稳健性」的尝试都要面对「收益就是来自少数币的大行情」这一事实，不能指望用分散化同时保住 20x。
- **现金计息敏感性（计量口径，默认不计入 headline）**：引擎给现金 0% 利息，而组合平均 gross exposure 只有 **36.0%**（64% 现金）。把闲置现金按固定年化利率计息后，冠军 20bps +3h 口径为：0% → 19.5575x；**2% → 20.7772x**；4% → 22.0729x；5% → 22.7507x。这是一个**保守假设的敏感性**，不是 alpha：它不改任何规则，也不改善 DSR/PBO/窄峰三关；是否把它计入 headline 需要项目负责人明确决定（未经决定前 §00.1/§00.5 的数字保持不变）。H3 同样口径为 19.9004x / 21.2634x / 22.7196x / 23.4847x。
### 00.10 2026-10-08 候选同口径横评：H3 全面优于冠军（含 DSR 口径修正）

- **先修一个口径错误**：此前冠军的 DSR 引的是 `reports/phase_momentum_multiple_testing_2022/` 的 **0.731**（候选 `primary`，Sharpe **1.4325**，即**收盘成交**），而 H2/H3/H4 的 DSR 来自 `reports/phase_momentum_hypotheses_2026_10/dsr.csv`（Sharpe 1.3700，即**+3h 成交**）。文献综述 §4.0 规定 DSR 用 **20bps、+3h、较差缺 K 线** 的日收益，所以在协议口径下冠军的 DSR 是 **0.679**，不是 0.731。两者都远低于 0.95，门槛结论不变；但这让"冠军 vs 变体"的比较一直不是同口径的。
- **做法**：把 5 个已注册规格放进同一个 harness、同一批成交口径重跑（`scripts/evaluate_phase_momentum_candidates.py`）。不新增试验、不做任何选择。
- **20bps、较差缺 K 线、+1h 成交（实盘目标口径）**：

| 规格 | 总收益 | Sharpe | 最大回撤 | 1年滚动最差 | 去掉最佳年 | 年换手 | 平均仓位 | DSR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B 冠军 | 21.22x | 1.398 | -46.6% | 0.753 | 4.57x | 26.0 | 36.0% | 0.703 |
| H2 闸门集成 | 10.02x | 1.177 | -47.8% | 0.749 | 2.95x | 27.8 | 36.8% | 0.501 |
| **H3 宽度共闸 (0.50)** | **23.44x** | **1.534** | **-33.4%** | **0.768** | **6.44x** | **24.6** | **29.9%** | **0.808** |
| H3 邻域 0.45 | 22.87x | 1.514 | -34.6% | 0.768 | 6.28x | 24.8 | 30.4% | 0.793 |
| H3 邻域 0.55 | 18.62x | 1.456 | -30.2% | 0.768 | 4.78x | 24.6 | 29.3% | 0.751 |

- **20bps、较差缺 K 线、+3h 成交（当前实盘口径）**：

| 规格 | 总收益 | Sharpe | 最大回撤 | DSR |
|---|---:|---:|---:|---:|
| B 冠军 | 19.56x | 1.370 | -45.7% | 0.679 |
| H3 (0.50) | 19.90x | 1.466 | -37.7% | 0.758 |
| H3 邻域 0.45 | 17.72x | 1.412 | -38.7% | 0.714 |
| H3 邻域 0.55 | 15.48x | 1.383 | -34.8% | 0.691 |

- **DSR 按成交口径**：B = 0.731（收盘）/0.703（+1h）/0.679（+3h）；H3 = 0.801/0.808/0.758。**H3 在每一个口径上 DSR 都高于冠军。**
- **评估**：在实盘目标口径（+1h）下，H3 在**收益、Sharpe、最大回撤、1 年滚动最差、去掉最佳年、换手、平均仓位、DSR 八项上全部优于冠军**，且是预注册通过判据的规格，不是事后挑的。它唯一不稳健的是**收益**：阈值 0.45/0.50/0.55 在 +1h 下为 22.87x/23.44x/18.62x（0.50 是峰值，但 0.45 只低 2.4%）；**回撤优势是单调且稳健的**（-34.6%/-33.4%/-30.2%）。
- **判定**：H3 仍是 **provisional**（DSR 0.808 < 0.95；PBO 尚未对 H3 计算；阈值邻域仍属窄峰）。按预注册 tier 规则，+3h 口径下它仍是 tier 2（19.90x < 20x），+1h 口径下 23.44x ≥ 20x。但按同口径比较，**它已经是一个严格更好的候选**。
- **本轮评估结论（我的判断，待项目负责人批准后才改写 §00.1/§00.5 的主规格）**：
  1. 如果目标函数是「在可接受风险下跑赢 BTC」（AGENTS.md 的措辞），**H3 是更好的规格，我建议采用**：它在实盘目标口径下八项全胜，回撤优势单调稳健（-30% 到 -35% vs -46.6%），且它是预注册通过的。
  2. 如果目标函数是「最大化收益上限」，则维持冠军：H3 的**收益**优势来自 0.50 这个阈值，而该阈值本身是 §0.8 早期样本内扫描选出来的（40/45/50/55/60 → 50 最优），属于二次选择，不能当作可靠优势。
  3. 无论选哪个，都仍是 **provisional**（DSR 最高 0.808 < 0.95，PBO 未对 H3 计算），且都要靠 +1h 执行才能真正站上「20bps 下 20x」。
  4. 换规格不是一行文档改动：`scripts/run_phase_momentum_live_signal.py` 目前只构造冠军的单 book 规格，采用 H3 需要同时改造它（OOS 跟踪端已支持 `--trial-id PR2026-10-H3`）。
- **复现**：`.venv/bin/python scripts/evaluate_phase_momentum_candidates.py`；明细 `reports/phase_momentum_candidate_eval/`。

### 00.9 2026-10-08 实际持仓：所谓「12 个 sleeve」其实是一个 1–2 币的组合

- **为什么做**：规格一直被描述成「12 个单币 sleeve」，听起来像 12 个独立下注、互相分散。§00.8 发现收益集中在 5 个币，于是直接测量组合**实际**持有了几个币。
- **口径**：冠军（`PhaseMomentumSpec` 默认 + `PRIMARY_SIGNAL_SPECS`），20bps、收盘成交、2022-01-01 → 2026-09-21（1725 天）；`largest_share` = 当日最大单币权重 / 当日 gross exposure。
- **结果**：

| 指标 | 数值 |
|---|---:|
| 有仓位天数（gross > 0） | 858 / 1725 |
| 平均 gross exposure（全样本） | 36.0% |
| **有仓位时平均持有的不同币数** | **1.99** |
| 最大单币占组合比的中位数 | **75.3%** |
| 最大单币占组合比的 75 分位 | **100.0%** |
| 单币 ≥50% 组合的有仓位天数 | **90.0%** |
| 单币 ≥75% 组合的有仓位天数 | 50.3% |
| 只持有一个币的有仓位天数 | 26.9% |
| 组合 HHI（等权 2 币 = 0.5） | **0.685** |

持有币数分布（有仓位天数）：1 币 231 天、2 币 439 天、3 币 151 天、4 币 36 天、5 币 1 天。

- **解读**：12 个 sleeve 的信号高度相关（都是 7–60 日 trailing return，只差检查相位），所以它们绝大多数时候指向同一个币——**这个策略实际上是一个单币（最多两币）轮动**，不是 12 币组合。这直接解释了 §00.8（5 个币贡献 90% 收益）和 -45% 的回撤：回撤就是那一个币的回撤。它也说明 §3.7「distinct coins across sleeves give partial diversification」这个设计假设**在当前规格下不成立**。
- **对「优化」的含义**（这是本轮最重要的结论）：既然实际只有一个币，那么
  - 所有分散化尝试都会**削掉收益**而不是「免费降风险」——H4（每个 sleeve 持 4 币）把 19.56x 打成 3.15x；§0.8 的宽度闸门也把 2bps 全样本从 28.92x 降到 23.10x/16.61x（换来的是回撤与 2024 起收益）。
  - 剩余的风险旋钮（vol target、闸门、止损）全都是**收益/风险权衡**，不是免费的：0.6/0.8/1.0 → 13.44x/-36.9%、23.09x/-44.9%、29.99x/-50.9%。
  - 也就是说：**样本内不存在「免费提高收益」的杠杆了**。20x 就是这个集中度的价格。
- **复现**：`.venv/bin/python scripts/analyze_phase_momentum_book.py`；明细 `reports/phase_momentum_book_concentration/daily_book.csv`。
- **已接入样本外跟踪**：`scripts/run_phase_momentum_oos.py` 现在同时输出 `oos_coin_attribution.csv` 与 `oos_concentration.csv`，report.md 增加「OOS per-coin concentration」小节（每个成本取较差缺 K 线口径），并给出同样的 drop-top1/drop-top5 反事实。当前 16 天窗口只有 `near` 一个贡献币（份额 122%，窗口太短、不构成证据）。
- **复现**：`.venv/bin/python scripts/attribute_phase_momentum_assets.py`（冠军）与 `... --trial-id PR2026-10-H3 --output-dir reports/phase_momentum_asset_attribution_h3`；报告在 `reports/phase_momentum_asset_attribution/` 与 `reports/phase_momentum_asset_attribution_h3/`。

### 00.11 2026-10-08 采用 H3 作为冻结规格（仍为 provisional；取代 §00.1/§00.5 的规格指定）

> **规格已被 §00.13 取代（2026-10-08）**：冻结规格现在是 **H5**（`PR2026-10-H5`，H3 的 50/50 结构 + 横截面离散度叠加）。本节记录 H3 的采用过程，数字仍然有效（H3 依旧是 H5 的对照规格）。

- **决定**：按 §00.10 的同口径横评，本轮把冻结规格从 **B（单 book 冠军）** 切换为 **H3（Top20 宽度共闸 50/50 混合，注册号 `PR2026-10-H3`）**。这是一次**规格指定**的切换，不是新的参数搜索：H3 在运行前已登记、通过了自己的 kill criterion，切换没有使用 2026-09-22 之后的任何数据来挑参数。
- **切换后的规格**：24 个 sleeve = 2 个 book × 12 个 sleeve，等权 1/24。
  - book A = 冠军（`PhaseMomentumSpec` 默认值 + `PRIMARY_SIGNAL_SPECS`）。
  - book B = 冠军 + Top20 宽度共闸：breadth(D) = 当日 point-in-time Top20 中收盘价高于自身 50D SMA 的占比，breadth(D) ≥ 0.50 才 risk-on（无 confirm）；不满足时 book B 的 sleeve 全部转现金。
  - 在**目标层面**做 50/50 混合，生产引擎在每次目标事件向 50/50 再平衡并按该次运行的成本计费；其余规则（信号收盘生成、T+1、2bps 基准成本、长仓现货无杠杆、gross ≤ 1.0）不变。
- **协议口径（20bps、+3h、较差缺 K 线）的头条结果**（`reports/phase_momentum_candidate_eval/`）：

| 指标 | B（切换前） | **H3（切换后）** |
| --- | ---: | ---: |
| 总收益 | 19.56x | **19.90x** |
| Sharpe | 1.370 | **1.466** |
| 最大回撤 | -45.7% | **-37.7%** |
| DSR | 0.679 | **0.758** |

- **+1h 实盘目标口径**（若 CMC 发布时间探针证明 00:30 UTC 前可拿到 D-1 收盘）：H3 **23.44x** / Sharpe 1.534 / MDD **-33.4%** / DSR 0.808；B 21.22x / 1.398 / -46.6% / 0.703。H3 在 +1h 口径下同时站上 20x。
- **仍然失败 / 未证明的门槛**（与 §00.1 相同，只是数字换成 H3；任何一条都不因切换而解除）：
  - **DSR**：协议口径 **0.758**（+1h 0.808）< 0.95 → **失败**。
  - **PBO**：已补算 → **失败**。在同一 20bps、收盘成交口径下，把 H3 三档（0.45/0.50/0.55）并入原 30 个单规格变体（去重后 33 个候选）重跑 CSCV（`scripts/run_phase_momentum_multiple_testing.py`，与 §00.1 的 B 同一方法，先复现 B 的 0.525974 再算）：**PBO = 0.558**（B 为 0.526）。只看 H3 邻域的口径更差：H3 三档 + B 共 4 个候选为 **0.658**，只看 H3 三档为 **0.775**。H3 (0.50) 在这族里的全样本收盘 Sharpe 最高（1.5233），也是被选中最多的候选（334/924），但样本外排名落在中位数以下的比例仍 >50%。结论：**PBO 门槛对 H3 同样不通过**（B 也不通过），切换规格不能解除这道门槛；这与 §00.10 的采用理由一致——采用 H3 靠的是回撤优势，不是 PBO。
  - **参数窄峰**：收益对宽度阈值敏感（+1h 下 0.45/0.50/0.55 → 22.87x/23.44x/18.62x，0.50 是峰值，0.45 只低 2.4%）；该阈值来自 §0.8 样本内 5 点网格，属**二次选择**。**回撤优势是单调且稳健的**（-34.6%/-33.4%/-30.2%），这才是采用 H3 的主要理由。
  - **单资产依赖**：§00.9 的结论（12 个 sleeve 实际是 1–2 币组合）对两个 book 都成立；H3 没有降低对单一币的依赖，只是用宽度闸门把 book B 在风险期转现金。
- **样本外**：2026-09-22 → 2026-10-07 的 16 天窗口里，宽度共闸从未触发（breadth 始终 ≥ 0.50），因此 H3 与 B 的收益逐位相同（+3h 20bps **1.0883x**，MDD -10.57%）。这段窗口原本是 B 的冻结窗口，对 H3 也是切参前数据，但**不构成 H3 的独立证据**。`reports/phase_momentum_oos_2026/` 现已切换为跟踪 H3（manifest `trial_id=PR2026-10-H3`，report.md 首行标明 tracked specification）；B 的旧快照保留在 git 历史与本文件 §00.5。
- **实盘信号工具**：`scripts/run_phase_momentum_live_signal.py` 现在默认构造 H3（模块常量 `FROZEN_TRIAL_ID = "PR2026-10-H3"`），`--trial-id champion-defaults` 可回到 B。输出新增 `trial_id` 字段，sleeve 快照新增 `book` 列（0 = book A，1 = book B），多 book 的规则描述列出两个 book 的闸门。
- **复现**：
  ```bash
  .venv/bin/python scripts/run_phase_momentum_live_signal.py --output-dir reports/phase_momentum_live
  .venv/bin/python scripts/run_phase_momentum_oos.py --trial-id PR2026-10-H3 --end-date 2026-10-07
  # H3 的 PBO（把 H3 三档并入原候选族后重跑 CSCV）
  .venv/bin/python scripts/build_phase_momentum_h3_candidates.py
  .venv/bin/python scripts/run_phase_momentum_multiple_testing.py \
      --candidate-returns reports/phase_momentum_multiple_testing_h3/candidate_returns.csv \
      --primary h3_breadth_050 --output-dir reports/phase_momentum_multiple_testing_h3
  ```
  明细：`reports/phase_momentum_candidate_eval/`、`reports/phase_momentum_oos_2026/`、`reports/phase_momentum_live/`、`reports/phase_momentum_multiple_testing_h3/`。

### 00.12 2026-10-08 新方向：横截面离散度（dispersion）风险叠加（仅筛查，未预注册、未过生产引擎）

> **状态已被 §00.13 取代（2026-10-08）**：本节当时的「仅筛查、未预注册、未过生产引擎」已推进——离散度叠加已正式预注册为 **H5**、用生产引擎（按目标事件计费）重跑并通过自己的 kill criterion，且是本项目第一个通过 PBO 的规格。下方筛查数字保留为设计依据。

> 背景：§00.11 的结论是 H3 仍过不了 DSR/PBO，而唯一干净的修复（等样本外积累）太慢。本轮回到外部文献，找 **§5「已否决」清单之外**的新机制。**本节全部是筛查，不是候选，也没有改变冻结规格。**

- **新证据（2026 年，均不在原 §2 清单内）**：
  - Makgolo & Zhang (2026), *Cross-Sectional Dispersion and the State Dependence of Cryptocurrency Momentum*, SSRN 6648082（University of Chicago Booth / Bentley）。要点：**横截面离散度比 BTC 波动率更能预测加密动量的崩溃**；极端离散度状态下动量显著走弱；按离散度缩放的策略 Sharpe **0.63 → 0.80**，最大回撤 **-42.5% → -17.1%**。来源：SSRN 摘要页 + QuantSeeker 2026-04-28 综述（SSRN 正文被反爬，未能取到全文，缩放函数的确切形式未核实）。
  - Xu & Wu (2026), *Size-Momentum Puzzle in Cryptocurrencies*, SSRN 6628860：小币（最小五分位）周度反转 4.9%，大币动量 +1.0%——**支持 Top20-only 的设定**（本项目选的都是大币）。
  - Li et al. (2026), *Taming crypto anomalies: A Lasso-type factor model*, Finance Research Letters：加密三因子模型含 **residual momentum** 因子（列在此备查，本轮未测）。
- **本项目诊断**（`scripts/diagnose_cross_sectional_dispersion.py`；`reports/phase_momentum_dispersion_diagnostic/`）：在 2022-01-01..2026-09-21 上，把 H3 的前瞻收益按**当日 point-in-time Top20** 的横截面离散度分五档（无前视，离散度只用当日及之前的数据）：

| 离散度定义 | 前瞻窗口 | 最高档前瞻均值 | 其余四档均值 | 差 | Spearman |
|---|---|---:|---:|---:|---:|
| 近 21 日收益的横截面 std | 21 天 | **-0.17%** | +6.11% | **-6.28pp** | -0.196 |
| 近 7 日收益的横截面 std | 21 天 | +1.26% | +5.75% | -4.50pp | -0.161 |
| 当日收益的横截面 std | 21 天 | +1.90% | +5.59% | -3.70pp | -0.153 |

  外部机制在本策略上**成立**：离散度越高，未来 21 天越差。

- **可交易版本的筛查**（`scripts/backtest_dispersion_overlay.py`；`reports/phase_momentum_dispersion_overlay/`）：直接在 H3 的日收益上乘一个由**当日**离散度算出的敞口系数（**只用 t-1 的信息**）。**注意：这是筛查，按日缩放隐含每日调仓、且没有计入这部分额外换手**，所以收益被高估；真实实现只在目标事件上再平衡。

| 叠加规则 | 2bps 总收益 | 2bps Sharpe | 2bps MDD | 20bps 总收益 | 20bps Sharpe | 20bps MDD |
|---|---:|---:|---:|---:|---:|---:|
| 无（H3） | 27.77x | 1.609 | -35.6% | 22.53x | 1.524 | -37.9% |
| 二元闸：pct≥0.80 转现金 | 11.91x | 1.530 | -37.9% | — | — | — |
| 逆离散度缩放 `min(1, 252D median / disp)` | 15.69x | 1.701 | -33.8% | 13.16x | 1.605 | -36.1% |
| 逆离散度缩放 `min(1, 252D P75 / disp)` | **25.27x** | **1.755** | -35.5% | **20.82x** | **1.664** | -37.8% |

- **解读**：
  1. 二元"极端就转现金"的闸门**伤害收益**（高离散度常常伴随强趋势，砍掉的是好日子），**否决**。
  2. 连续的**逆离散度缩放**（dispersion targeting，和波动率目标同构）在 P75 目标下把 Sharpe 从 **1.52 提到 1.66（+9%）**，20bps 总收益从 22.53x 降到 20.82x（**仍 >20x**），回撤基本不变（-37.8% vs -37.9%）。
  3. 这是本轮到目前**唯一一个在 20bps 下同时保住 20x 并提高 Sharpe 的方向**；但它**没有降低回撤**（这是 H3 采用时的主要理由），也没有解决 DSR/PBO 的试验数问题。
- **状态**：**未预注册、未过生产引擎、未计入试验台账**。要成为候选必须：(1) 写进预注册台账；(2) 用生产引擎（按目标事件计费）重跑；(3) 过 H3 的 kill criterion，并补 DSR/PBO/邻域/成本压力。**尚未做任何一步**，因此**不能**据此改冻结规格。
- **复现**：
  ```bash
  .venv/bin/python scripts/diagnose_cross_sectional_dispersion.py
  .venv/bin/python scripts/backtest_dispersion_overlay.py
  ```
  明细：`reports/phase_momentum_dispersion_diagnostic/`、`reports/phase_momentum_dispersion_overlay/`。

### 00.13 2026-10-08 采用 H5 作为冻结规格（横截面离散度叠加；仍为 provisional；取代 §00.11 的规格指定与 §00.12 的「仅筛查」状态）

- **决定**：本轮把冻结规格从 **H3** 切换为 **H5**（注册号 `PR2026-10-H5`）。§00.12 的横截面离散度叠加已正式预注册、用生产引擎（按目标事件计费）重跑、并通过自己的 kill criterion；它同时是**本项目第一个通过 PBO 门槛的规格**。这是一次**规格指定**的切换：H5 在运行前登记（`scripts/run_phase_momentum_hypotheses.py` 的 `TRIALS`；台账 `reports/research_trial_inventory/preregistered_trials.csv`），切换没有使用 2026-09-22 之后的任何数据。
- **切换后的规格**：在 §00.11 的 H3 结构（2 个 book × 12 个 sleeve，目标层 50/50 混合）之上，给**两个 book 都**加同一个离散度缩放（`PhaseMomentumSpec.dispersion_target_percentile = 0.75`）：
  - `dispersion(D)` = 当日 point-in-time Top20 的**近 21 日收益横截面标准差（ddof=1）**；可用成员 < 5 → 无读数（`top20_dispersion`）。
  - `factor(D)` = `min(1, 过去 252 日离散度的 75 分位 / dispersion(D))`；无读数时 factor = 1（不做叠加，而不是强制转现金）（`dispersion_exposure`）。
  - 每个 sleeve 的（已波动率缩放、已宽度共闸的）目标权重乘以 `factor(D)`；gross ≤ 1.0 不变，因此叠加**只降风险、不抬杠杆**。其余规则（信号收盘生成、T+1、2bps 基准成本、长仓现货无杠杆）不变。
- **协议口径（20bps、+3h、较差缺 K 线）的头条结果**（`reports/phase_momentum_candidate_eval_h5/`）：

| 指标 | B（原始基线） | H3（被取代） | **H5（冻结）** |
| --- | ---: | ---: | ---: |
| 总收益 | 19.56x | 19.90x | 19.53x |
| Sharpe | 1.370 | 1.466 | **1.623** |
| 最大回撤 | -45.7% | -37.7% | **-37.0%** |
| 1 年滚动最差 | 0.711 | 0.733 | **0.806** |
| 去掉最好一年 | 4.34x | 5.90x | **6.51x** |
| 年化换手 | 26.09 | 24.65 | 24.84 |
| 平均 gross | 36.0% | 29.9% | **26.1%** |

- **+1h 实盘目标口径**：H5 **22.80x** / Sharpe 1.704 / MDD -33.3%（H3 23.44x / 1.534 / -33.4%；B 21.22x / 1.398 / -46.6%）。
- **kill criterion（预注册并已实装进评估器，20bps +3h 较差缺 K 线）**：`MDD improvement 8.71pp >= 5pp`（MDD -0.3697 vs B -0.4567）✔；`Sharpe 1.6231 > H3 1.4658` ✔；`1 年滚动最差 0.8063 > H3 0.7325` ✔。2bps（+9.02pp / 1.7223 > 1.5504 / 0.8130 > 0.7507）与 50bps（+8.21pp / 1.4570 > 1.3240 / 0.7517 > 0.6728）同判 → **通过**（`reports/phase_momentum_hypotheses_2026_10/kill.csv`）。H5 是本项目**第一个既通过 kill criterion、又通过 PBO 的规格**。
- **仍然失败 / 未证明的门槛**（任何一条都不因切换而解除；H5 仍为 **provisional**，tier 2「risk variant recorded」）：
  - **DSR**：协议口径 **0.860**（+1h 0.901，收盘 0.892）< 0.95 → **失败**（H3 0.755、B 0.675，同一口径）。DSR 用 `top20_2022_trials` 的 **N=6,135**（本轮把 3 个 H5 试验并入台账后重建的 `reports/research_trial_inventory/summary.json`，N 6,132→6,135）与家庭内 N=36 两个口径；家庭内 DSR 0.999 只是说明「在本家族里它是最强的」，不解除项目级门槛。
  - **DSR 差距有多远（新增，`scripts/analyze_dsr_gap.py`，`reports/phase_momentum_dsr_gap/`）**：保持 H5 协议日收益的分布形状（波动、偏度、峰度）不变、只把均值抬到刚好让 DSR = 0.95，需要的年化 Sharpe 是：

| DSR 口径 | N | E[max] 年化 | 现在 DSR | 现在的 Sharpe | 达到 0.95 所需 Sharpe | 差距 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| family（本族候选） | 36 | 0.398 | **0.999** ✅ | 1.623 | 1.623 | 已通过 |
| top20_2022_trials（项目口径） | 6,135 | 1.180 | 0.860 ❌ | 1.623 | **1.846** | **+13.7%** |
| all_trials | 14,129 | 1.244 | 0.822 ❌ | 1.623 | **1.908** | **+17.6%** |

    这是**反事实定价**，不是可达性声明：它说明项目级 DSR 门槛要求 Sharpe 再高约 14%，而不是「差一点」。同一份计算也说明为什么不能靠换口径过关——只有 family 口径会通过，而 family 口径不反映选择历史。
  - **PBO**：**通过**。把 H5 三档（0.60/0.75/0.90）与 H3 三档一起并入原 30 个单规格变体（去重后 **36 个候选**）重跑 CSCV（`scripts/build_phase_momentum_extended_candidates.py` + `scripts/run_phase_momentum_multiple_testing.py`；`reports/phase_momentum_multiple_testing_overlays/`）：**PBO = 0.192 < 0.5 → 通过**（H3 0.558、B 0.526，两者都是 fail）。H5(0.75) 是该族里被选中最多的候选（623/924），且全样本收盘 Sharpe 最高（1.6836）。White Reality Check：对零 p=0.019，对 BTC p=0.025。
  - **参数邻域**：**稳健**。预注册邻域 0.60/0.90 在 2/20/50bps 下都**保持** H5 的 kill criterion（H5-T60 协议口径 13.63x / Sharpe 1.540 / MDD -36.3%；H5-T90 21.68x / 1.555 / -37.0%）。收益对分位敏感（0.60 明显更低，18.16x@2bps vs 26.51x），但**风险指标（MDD、1 年滚动最差）对三档单调且稳健**——这正是采用 H5 的理由，不是收益。
  - **单资产依赖**：§00.9 的结论（12 个 sleeve 实际是 1–2 币组合）对 H5 同样成立；H5 没有降低对单一币的依赖。
  - **收益天花板**：叠加只做 de-risk（factor ≤ 1），**不抬收益上限**；协议口径下 H5 总收益（19.53x）略低于 H3（19.90x），属预注册里写明的「pass below 20x 记为 risk variant」情形。H5 在 2bps 与 +1h 口径下都 ≥ 20x，但头条（20bps +3h）低于 20x。
- **压力窗口 2020-10-03 .. 2021-12-31（20bps，收盘）**：H5 **5.177x** / Sharpe 2.553 / MDD -20.6%；H3 5.372x / 2.493 / -21.0%；B 5.129x / 2.456 / -18.9%；BTC 4.390x。
- **市场状态**（`reports/phase_momentum_regime_overlays/`，无前视标签）：H5 在 bull 20.05x / Sharpe 2.483 / MDD -37.7%，**非 bull 1.071x / Sharpe 0.255 / MDD -19.7%**，是三者里最好的非 bull（B 0.910x / -0.083 / -29.0%；H3 1.022x / 0.136 / -23.2%）。离散度叠加主要在风险期降暴露，与 §00.12 的机制一致。
- **样本外**：2026-09-22 → 2026-10-07 的 16 天里，离散度叠加**确实触发**（不像 H3 的宽度共闸从未触发）：20bps +3h 下 H5 **1.0576x** / MDD -6.39%，H3 1.0883x / -10.57%，BTC 0.9616x——H5 少赚约 2.9%，回撤小约 4.2pp。这段窗口对 H5 仍是切参前数据，**不构成独立证据**。`reports/phase_momentum_oos_2026/` 现已切换为跟踪 H5（manifest `trial_id=PR2026-10-H5`）。
- **实盘信号工具**：`scripts/run_phase_momentum_live_signal.py` 现在默认构造 H5（模块常量 `FROZEN_TRIAL_ID = "PR2026-10-H5"`），`--trial-id champion-defaults` 回到 B、`--trial-id PR2026-10-H3` 回到 H3。规则文本与 sleeve 快照现在也列出离散度叠加；`reports/phase_momentum_live/latest_signal.md` 的 Trial 字段为 `PR2026-10-H5`。
- **本轮同时修掉的两个评估器缺陷**（都会让 H5 的判定失真，记录在此以免误读）：
  1. `NEIGHBOURHOOD_IDS` 原来只有 H2/H3，H5 的 0.60/0.90 邻域虽在 `TRIALS` 里、却不在评估器的 trial 列表里，写台账时直接 `KeyError`；已补上。
  2. `_criteria` 原来只有 H2/H3/H4 三套判据，H5 会被**误用 H4 判据**评估；已实装 H5 判据（MDD 对 B、Sharpe 与 1 年滚动最差对 H3）。修正后 H5 与两个邻域都在 2/20/50bps 下通过。
- **复现**：
  ```bash
  # 1) 全量重跑预注册试验，重算判据 / DSR / Reality Check / 压力窗口
  .venv/bin/python scripts/run_phase_momentum_hypotheses.py
  # 2) 重建试验台账（把 3 个 H5 试验计入 DSR 分母 N=6,135）
  .venv/bin/python scripts/build_trial_inventory.py
  # 3) H5 与 B/H3 及各自邻域的同口径横评（含 DSR）
  .venv/bin/python scripts/evaluate_phase_momentum_candidates.py \
      --trial-ids PR2026-10-B,PR2026-10-H3,PR2026-10-H5,PR2026-10-H5-T60,PR2026-10-H5-T90 \
      --output-dir reports/phase_momentum_candidate_eval_h5
  # 4) 把 H3+H5 六档并入原候选族后重算 PBO / DSR / Reality Check
  .venv/bin/python scripts/build_phase_momentum_extended_candidates.py
  .venv/bin/python scripts/run_phase_momentum_multiple_testing.py \
      --candidate-returns reports/phase_momentum_multiple_testing_overlays/candidate_returns.csv \
      --primary h5_disp_p75 --output-dir reports/phase_momentum_multiple_testing_overlays
  # 5) 市场状态拆分
  .venv/bin/python scripts/run_phase_momentum_regime_breakdown.py \
      --returns-file reports/phase_momentum_multiple_testing_overlays/candidate_returns.csv \
      --candidates primary,h3_breadth_050,h5_disp_p75 \
      --output-dir reports/phase_momentum_regime_overlays
  # 6) DSR 差距定价（达到 0.95 所需的年化 Sharpe）
  .venv/bin/python scripts/analyze_dsr_gap.py --output-dir reports/phase_momentum_dsr_gap
  # 6f) 追高进场诊断（§00.18）
  .venv/bin/python scripts/analyze_momentum_chase_risk.py --output-dir reports/phase_momentum_chase_risk

  # 6e) 永续资金费率筛查（§00.17，全部被拒）
  .venv/bin/python scripts/download_funding_rates.py --start-month 2020-09 --end-month 2026-09
  .venv/bin/python scripts/analyze_momentum_funding_states.py --output-dir reports/phase_momentum_funding_states

  # 6d) 小时线日内状态筛查（§00.16，全部被拒）
  .venv/bin/python scripts/analyze_momentum_hourly_states.py --output-dir reports/phase_momentum_hourly_states

  # 6c) 量能/换手/集中度状态筛查（§00.15，全部被拒）
  .venv/bin/python scripts/analyze_momentum_flow_states.py --output-dir reports/phase_momentum_flow_states

  # 6b) 崩溃月归因：有没有状态变量能标记最差月份（§00.14，表格已被 §00.15 勘误）
  .venv/bin/python scripts/analyze_momentum_crash_states.py --output-dir reports/phase_momentum_crash_states
  # 7) 实盘信号与样本外跟踪
  .venv/bin/python scripts/run_phase_momentum_live_signal.py --output-dir reports/phase_momentum_live
  .venv/bin/python scripts/run_phase_momentum_oos.py --trial-id PR2026-10-H5 --end-date 2026-10-07
  ```
  明细：`reports/phase_momentum_candidate_eval_h5/`、`reports/phase_momentum_multiple_testing_overlays/`、`reports/phase_momentum_regime_overlays/`、`reports/phase_momentum_dsr_gap/`、`reports/phase_momentum_hypotheses_2026_10/`、`reports/phase_momentum_oos_2026/`、`reports/phase_momentum_live/`。

### 00.14 2026-10-08 诊断：DSR 差距不能靠「再加一层市场状态 overlay」补上（否定性结果）

> 背景：§00.13 把 H5 的 DSR 差距定价为「年化 Sharpe 还需再高 **13.7%**」。本节先做归因，回答「这 13.7% 到底亏在哪、能不能靠再叠一层状态变量补上」，再决定要不要开新试验。**本节只做诊断：不预注册、不新增试验、不改变冻结规格。**

- **亏损集中度**：H5 协议口径（20bps、+3h）57 个日历月里 17 个月为负（29.8%；同期 BTC 为 25/57）。回撤主要由**少数几个月**贡献。最扎眼的是「大盘上涨、策略却大跌」的月份：2023-04（H5 **-19.3%** vs BTC +2.8%）、2024-01（-10.6% vs +0.8%）、2023-07（-11.4% vs -4.1%），以及 2024-04（-19.0% vs -15.0%，这一类主要是市场型）。
- **这些月份叠加层在干什么**（`scripts/analyze_momentum_crash_states.py`；`reports/phase_momentum_crash_states/`）：

| 月份 | H5（净） | BTC | BTC 闸门开 | disp_ratio | gross |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2023-04 | **-19.3%** | +2.8% | 100% | **0.59** | **0.90** |
| 2024-04 | -19.0% | -15.0% | 100% | 0.69 | 0.34 |
| 2023-07 | -11.4% | -4.1% | 100% | 1.66 | 0.34 |
| 2024-01 | -10.6% | +0.8% | 100% | 0.70 | 0.41 |

  （`disp_ratio` = 当日离散度 / 其自身 252 日 75 分位；< 1 表示叠加层认为「离散度不高」，factor 保持 1。）

- **关键观察**：2023-04 的 disp_ratio 全月均值 **0.59** —— 离散度一直低于 75 分位，**factor 全程 = 1.000，叠加层根本没触发**，而 gross 高达 **90%**。也就是说，除了市场型下跌之外，最伤人的「大盘没事、动量自己反转」月份恰好落在叠加层的**盲区**里（低离散度，按 Makgolo–Zhang 的机制本该对动量*有利*）。当月亏损来自 OKB（-7.7pp）、cardano（-2.8pp）、ripple（-2.3pp）、dogecoin（-1.1pp）；2024-01 来自 internet-computer（-6.4pp）、ethereum-classic（-3.0pp）。
- **状态变量筛查（否定性结果）**：把 9 个崩溃月（≤ -8%）与其余 44 个月对比 6 个**当日可观测**的状态变量：

| 状态变量 | 崩溃月均值 | 其余月均值 | 差值 / 其余月标准差 |
| --- | ---: | ---: | ---: |
| BTC 闸门开 | 0.650 | 0.499 | +0.35 |
| breadth | 0.370 | 0.480 | -0.37 |
| disp_ratio | 0.751 | 0.943 | -0.38 |
| 市场 60D 已实现波动 | 0.718 | 0.705 | +0.06 |
| 策略自身过去 63 日收益 | 0.217 | 0.122 | +0.36 |
| gross | 0.310 | 0.266 | +0.18 |

  **没有一个变量的区分度超过 0.4σ。** 换句话：在这一族状态变量里找不到能标记崩溃月的变量，因此**再加一层同族 overlay 更可能只是增加试验数**（分母变大、所需 Sharpe 反而更高），而不是补上 13.7%。
- **结论（方向性）**：
  1. H5 的 Sharpe 增益（1.466 → 1.623）来自**整体降波动**，不是靠躲过崩溃月 —— 崩溃月不在它的状态空间里。
  2. 要补上 13.7% 的 Sharpe，需要**这一族（价格动量 / 波动 / 宽度 / 离散度）之外的新信息源**，而不是继续微调现有状态变量。
  3. 本节是**样本内假设生成**：即便将来某个变量能区分崩溃月，也必须在预注册后由样本外数据确认，才可能改规则。**当前冻结规格不变。**
- **复现**：
  ```bash
  .venv/bin/python scripts/analyze_momentum_crash_states.py
  ```
  明细：`reports/phase_momentum_crash_states/monthly_state.csv`、`state_separation.csv`、`report.md`。
- **勘误（2026-10-09，§00.15 给出）**：上表是在 **53/57** 个月上算的 —— 该脚本按行 dropna，而 `disp_ratio` 需要 126 个可用离散度读数、`own63` 需要 63 日收益序列预热，于是**整行丢掉了 2022-01..04**，其中 2022-04（-10.5%）正是一个崩溃月。按「逐状态丢缺失值 + 原口径」重算后结论不变（见 §00.15 表二），但样本应为 **57 个月、10 个崩溃月**。

---

### 00.15 2026-10-09 诊断：量能/换手状态变量筛查 —— 全部被拒（否定性结果，仍不开新试验）

> 背景：§00.14 的结论是「要补上 13.7% 的 Sharpe，需要价格动量 / 波动 / 宽度 / 离散度这一族之外的**新信息源**」。在不新增数据拉取的前提下，面板里唯一没被用过的信息就是**成交量与市值**。本节对该族做**只筛查、不预注册、不新增试验、不改规则**的诊断；筛选门槛在跑数之前写死在脚本 docstring 里。外部证据见 `docs/research/literature_review_2026-09.md` §7（S37–S43，逐条 fetch 验证）。

**外部机制（与筛查变量的对应）**

| 机制 | 来源 | 对应状态变量 |
| --- | --- | --- |
| 流动性/换手率作为情绪指标：换手率越高，随后收益越低（卖空约束下的过度反应） | Baker & Stein (2004), JFM, doi:10.1016/j.finmar.2003.11.005（NBER w8816 摘要已 fetch） | `turnover`、`turnover_ratio`、`volume_ratio` |
| 过去换手率同时预测动量的幅度与持续性；高换手赢家长期反转 | Lee & Swaminathan (2000), JF, doi:10.1111/0022-1082.00280 | `holdings_turnover_ratio` |
| 动量集中在**流动性最好**的币（羊群机制） | Begušić & Kostanjčar (2019), arXiv:1904.00890（arXiv API 摘要已 fetch） | `turnover_disp_ratio` |
| 日频数据可构造有效加密流动性指标；流动性波动被定价 | Brauneis et al. (2021), JBF, doi:10.1016/j.jbankfin.2020.106041；FRL 2021, doi:10.1016/j.frl.2021.102031 | `amihud_ratio` |
| 集中度/羊群：Top20 内部市值与成交量集中度 | 本项目内机制（`mcap_hhi`、`btc_share`、`volume_top3_share`）；外部证据仅部分支持 | 3 个集中度变量 |

**预设门槛（先写后跑）**：同时满足三条才允许升级为 H6 —— ① `|Spearman(状态, 次月 H5−BTC)| ≥ 0.25`；② `H5−BTC` 的三分位均值单调；③ `|崩溃月−其余月| / 其余月标准差 ≥ 0.50`。对照量取**超额收益**（H5 − BTC），因为 §00.14 的失败模式是「大盘涨、策略跌」。

**结果：9 个状态变量全部未通过**（`reports/phase_momentum_flow_states/`）

| 状态变量 | Spearman（对超额） | 崩溃−其余（σ） | 三分位单调 | 升级 H6 |
| --- | ---: | ---: | :--: | :--: |
| `turnover` | -0.069 | +0.04 | 否 | 否 |
| `turnover_ratio` | +0.083 | -0.22 | 是 | 否 |
| `volume_ratio` | +0.090 | +0.21 | 是 | 否 |
| `turnover_disp_ratio` | +0.126 | +0.68 | 否 | 否 |
| `amihud_ratio` | -0.109 | -0.15 | 否 | 否 |
| `mcap_hhi` | +0.166 | **-0.53**（t≈-2.1） | 否 | 否 |
| `btc_share` | +0.158 | **-0.52**（t≈-2.0） | 否 | 否 |
| `volume_top3_share` | -0.171 | -0.42 | 否 | 否 |
| `holdings_turnover_ratio` | -0.175 | **+2.09**（仅 28/57 个月可用） | 否 | 否 |

- **唯一接近的方向**是市值集中度：崩溃月之前的 Top20 **更分散**（HHI 0.412 vs 0.448、BTC 占比 0.599 vs 0.635），但它的秩相关只有 0.166（p≈0.21），且三分位不单调 —— **未达预设门槛，不升级**。`holdings_turnover_ratio` 的 2.09σ 不可用：它只在持仓月有定义（28/57，崩溃月只剩 7 个），是典型的选择性样本，且极端值（2023-07 达 11.9）主导。
- **§00.14 勘误与「可执行口径」重算**：按同样的**月内均值**口径、逐状态丢缺失值、全 57 个月重算，结论不变（σ：`gate_open` +0.36、`breadth` -0.31、`disp_ratio` -0.38、`mkt_vol` +0.05、`gross` +0.22）。但换成**月初读数**（overlay 真正能用的口径）后，同一个变量族其实**是能区分**的：

| 月初可执行状态 | 崩溃月均值 | 其余月均值 | 差值/σ | Welch t |
| --- | ---: | ---: | ---: | ---: |
| BTC 闸门开 | **0.900** | 0.447 | +0.90 | 3.66 |
| breadth | **0.690** | 0.372 | +0.95 | 3.94 |
| 月初 gross | **0.455** | 0.226 | +0.72 | 2.27 |

  即：**H5 进入最差月份时并不是防守状态，而是「闸门开、宽度高、仓位接近半仓」的满风险状态**，而这些状态在牛市中同样长期为真 —— 用它们做减仓过滤器，等于砍掉大部分收益。这正是 §00.14 否定性结论的可执行表述，也是为什么这条线**不值得再开 H6**。
- **结论**：
  1. 量能/换手/集中度这一族**不能**补 DSR 缺口：最强的候选也达不到预设的样本内门槛。
  2. 已记录的**被拒假设**：Top20 换手率择时（Baker–Stein 方向）、持仓拥挤度、Amihud 非流动性、集中度择时。除非有**新的样本外数据**，不再从这一族派生新试验。
  3. 若要继续追 DSR，剩下三条诚实路径：(a) 接受 H5 为「冻结但未通过 DSR」的当前最优；(b) 用 2026-09-22 起的**真实样本外**累积来正当地降低试验数权重（慢，且不能调参）；(c) 引入**面板之外**的新数据源（链上/资金费率等），需要先解决数据获取。
  4. **冻结规格不变**；本节不新增试验，台账计数不变。
- **复现**：
  ```bash
  .venv/bin/python scripts/analyze_momentum_flow_states.py --output-dir reports/phase_momentum_flow_states
  ```
  明细：`reports/phase_momentum_flow_states/{monthly_state.csv,daily_flow_state.csv,state_separation.csv,state_separation_legacy_corrected.csv,state_separation_legacy_actionable.csv,state_information.csv,state_terciles.csv,state_redundancy.csv,state_verdicts.csv,report.md,manifest.json}`。

---

### 00.16 2026-10-09 诊断：小时线（日内）状态变量筛查 —— 同样全部被拒（否定性结果）

> 背景：§00.15 关闭了面板里的**日频**量能/换手/集中度信息。仓库里还剩最后一块策略看不到的信息：**Binance 小时线**（`data/raw/binance_1h`，56 个交易对，2021-12-25 起；它本来只被用于 +1h/+3h 成交协议）。本节对它做同样的「只筛查、不预注册、不新增试验」诊断；门槛在跑之前写死。外部证据见 `docs/research/literature_review_2026-09.md` §8（S44–S48）。

**覆盖度**：评价窗口内出现过的 **53 个 PIT Top20 成员**中，只有 `bitget-token` 没有小时线；成员-日覆盖 **34,381 / 34,500 = 99.66%**（最低单日 95%）。

**7 个候选状态**（全部按「月初前一收盘」读数，截面只取 PIT Top20 成员，单日不足 5 个成员记缺失，小时数不足 20 的残日整日丢弃）：

| 状态变量 | 机制与来源 |
| --- | --- |
| `rv_ratio` | 24 小时已实现方差（小时对数收益平方和）7 日均值 ÷ 自身 252 日中位数；Andersen–Bollerslev–Diebold–Labys (2003) 证明已实现方差比日频平方收益噪声小得多 |
| `range_ratio` | 日均 (high−low)/close 的 7 日均值 ÷ 自身中位数；Parkinson (1980) 极值波动率估计 |
| `rvs_down_share` | 下行半方差占已实现方差的比例（「坏波动」）；Barndorff-Nielsen–Kinnebrock–Shephard（已实现半方差） |
| `hour_share_ratio` | 单小时最大成交额占当日比重 ÷ 自身中位数；Cong–Li–Tang–Yang「Crypto Wash Trading」：不受监管交易所的刷量平均占报告量 **70%+** |
| `venue_share_ratio` | Binance 成交额 ÷ 成员 CMC 报告成交额（7 日均值）÷ 自身中位数：报告量中可被单一场所验证的比例 |
| `hourly_autocorr` | 各成员小时收益 30 日一阶自相关的截面中位数：日内趋势 vs 日内反转 |
| `night_minus_day` | 等权 Top20 组合 00:00–08:00 UTC 收益减 08:00–24:00 UTC 收益的 7 日和；Hansen–Kim–Kimbrough 记录加密波动与成交量的**小时效应** |

**预设门槛（比 §00.15 更严）**：这是同一样本上的**第二个**筛查，因此信息门槛按 18 个候选做族错误率校正：`|Spearman(状态, 次月 H5−BTC)| ≥ 0.38`（n≈57 时双侧 5% 除以 18），加三分位单调，加 `|崩溃−其余| / 其余σ ≥ 0.50`。

**结果：7 个状态全部未通过**

| 状态变量 | Spearman（对超额） | 崩溃−其余（σ） | 三分位单调 | 升级 H6 |
| --- | ---: | ---: | :--: | :--: |
| `rv_ratio` | +0.036 | +0.25 | 否 | 否 |
| `range_ratio` | +0.081 | +0.23 | 是 | 否 |
| `rvs_down_share` | -0.183 | -0.35 | 否 | 否 |
| `hour_share_ratio` | **+0.262** | -0.33 | 是 | 否 |
| `venue_share_ratio` | -0.177 | -0.04 | 是 | 否 |
| `hourly_autocorr` | -0.043 | -0.03 | 是 | 否 |
| `night_minus_day` | +0.123 | +0.23 | 是 | 否 |

- `hour_share_ratio` 是**日频+小时线共 16 个候选里最强的**：三分位单调，秩相关 +0.262 甚至能过 §00.15 的未校正门槛 0.25 —— 但它连 0.50σ 的区分度门槛都没到（-0.33），因此**不升级**，只登记为被拒假设。
- **已实现波动率（教科书式的崩溃条件变量）对次月超额收益的秩相关只有 +0.036**。这与 §00.14 的结论一致：H5 的问题不在「波动率状态」里。
- **结论**：项目现有的**全部信息源**（日频价格/成交量/市值 + 小时线）都已被筛过；在三类面板内派生状态里都找不到能补 DSR 缺口的新信息。要么接受 H5 为「冻结但未过 DSR」的当前最优，要么等 **2026-09-22 起的真实样本外** 累积，要么引入**面板之外**的数据（需要先解决获取，且必须重新走预注册流程）。**冻结规格与试验计数不变。**
- **复现**：
  ```bash
  .venv/bin/python scripts/analyze_momentum_hourly_states.py --output-dir reports/phase_momentum_hourly_states
  ```
  明细：`reports/phase_momentum_hourly_states/{monthly_state.csv,daily_hourly_state.csv,hourly_coverage.csv,state_separation.csv,state_information.csv,state_terciles.csv,state_redundancy.csv,state_verdicts.csv,report.md,manifest.json}`。

---

### 00.17 2026-10-09 诊断：永续合约资金费率筛查 —— 被拒，但它是目前最强的崩溃月区分变量（否定性结果）

> 背景：§00.15（日频现货量能）与 §00.16（小时线）都在**现货**信息里，且都被拒。项目从未用过的最后一块信息是**衍生品持仓**：多头为持有仓位支付的资金费率。`data.binance.vision` 按月归档每个 Binance USDT 永续的完整资金费率历史，`scripts/download_funding_rates.py` 已把 57 个币中的 **52 个**落到 `data/raw/binance_funding/`（`fapi.binance.com` 在本网络不可达，故走公开归档）。本节同样是**只筛查、不预注册、不新增试验**。外部证据见 `docs/research/literature_review_2026-09.md` §9（S49–S51）。

**外部机制**：*Management Science* (2026) 的 "Crypto Carry" 证明期货-现货 carry 可达年化 40%+，来源是「**追趋势的小投资者加杠杆的需求** + 套利资本受限」——资金费率因此是"杠杆拥挤度"的直接读数；另一篇 2026 年 Binance 永续面板研究显示「累计资金费率」显著预测 8 小时内 ≥5% 的暴跌（样本外 AUROC 0.76）。

**4 个候选状态**（月初前一收盘读数，截面只取有资金费率的 PIT Top20 成员，单日不足 5 个记缺失）：`funding_level`（成员日均资金费率的 7 日均值，单位 bps/日）、`funding_pct`（该序列在自身 252 日窗口内的分位）、`funding_positive_share`（正费率成员占比的 7 日均值）、`funding_disp_ratio`（截面离散度 ÷ 自身 252 日中位数）。

**覆盖度**：53 个 PIT 成员中 5 个没有资金费率历史（4 个 Gate 专属 + bitget-token），成员-日覆盖 **33,043 / 34,500 = 95.78%**，**没有任何一天低于 5 成员下限**。

**预设门槛**（同一样本上的第三个筛查，20 个候选族错误率校正）：`|Spearman(状态, 次月 H5−BTC)| ≥ 0.38` + 三分位单调 + `|崩溃−其余| ≥ 0.50σ`。

**结果：4 个状态全部未通过 —— 但 `funding_level` 是目前全部 20 个候选里崩溃月区分度最强的**

| 状态变量 | Spearman（对超额） | 崩溃−其余（σ） | Welch t | 三分位单调 | 升级 H6 |
| --- | ---: | ---: | ---: | :--: | :--: |
| `funding_level` | +0.162 | **+1.12** | 1.99 | 是 | 否 |
| `funding_positive_share` | +0.168 | **+0.76** | **3.57** | 否 | 否 |
| `funding_pct` | +0.088 | +0.51 | 1.52 | 否 | 否 |
| `funding_disp_ratio` | +0.067 | -0.12 | -0.27 | 否 | 否 |

- **崩溃月之前的多头杠杆明显更贵**：崩溃月月初的日均资金费率 **3.19 bps**，其余月份只有 **0.70 bps**（差 1.12σ，t≈2.0），方向与「杠杆拥挤 → 崩塌」机制一致。这是三次筛查里唯一超过 1σ 的区分度。
- **但它不是方向性过滤器**：同样是这个高费率三分位，也是**平均最好的月份**（H5 均值 **+12.7%** vs 低三分位 +3.1%；超额 +6.3% vs +1.6%）。按崩溃月区分度去「高费率就减仓」，会砍掉最好的月份 —— 这正是它的超额秩相关只有 +0.162（远低于 0.38 门槛）的原因。
- **而且它并不新**：`funding_level` 与规格已看到的状态高度重合 —— 与 breadth 相关 0.66、与 BTC 闸门 0.65、与 gross 0.61、与 mkt_vol −0.40。也就是说，拥挤杠杆主要是**波动率/风险偏好放大器**，而 H5 已经通过 gross 和 breadth 看到其中大部分。
- **结论**：资金费率族**不升级为 H6**，登记为被拒假设。三次筛查（日频量能、小时线、资金费率，共 20 个候选）合起来说明：**在项目可低成本获得的信息里，找不到能补 DSR 缺口的定向信号**。
- **落地限制（必须记录）**：Binance 只按月归档资金费率（没有日档），且 `fapi.binance.com` 在本网络不可达 —— 因此即便将来某个资金费率状态被预注册并验证，也**无法直接驱动实盘**，需要另找数据通道。
- **复现**：
  ```bash
  .venv/bin/python scripts/download_funding_rates.py --start-month 2020-09 --end-month 2026-09
  .venv/bin/python scripts/analyze_momentum_funding_states.py --output-dir reports/phase_momentum_funding_states
  ```
  明细：`reports/phase_momentum_funding_states/{monthly_state.csv,daily_funding_state.csv,funding_coverage.csv,state_separation.csv,state_information.csv,state_terciles.csv,state_redundancy.csv,state_verdicts.csv,report.md,manifest.json}`。

---

### 00.18 2026-10-09 现状与诊断：当前信号、样本外进度，以及「追高进场」的历史表现

**一、当前信号（数据截至 2026-10-07，UTC 日已收完）**

| 项目 | 值 |
| --- | --- |
| 目标 | **100% `near`**，gross **0.505**（其余为现金） |
| 当前持仓 | `near` 0.5048 |
| BTC 闸门 | 开 |
| 需要交易 | 是（目标 0.5057 vs 当前 0.5048，仅漂移补仓） |
| 建仓过程 | 2026-09-18 之前是 100% `zcash`；09-19 起 `near`+`zcash`；**10-04 起 100% `near`** |

单币集中不是异常：本规格由 **24 个单币 sleeve**（2 本账 × 4 信号 × 3 相位）叠加而成，历史上有 26.9% 的持仓日为单一币种、最大持仓占比中位数 75.3%（`reports/phase_momentum_book_concentration/`）。真正约束风险的是**波动率目标**：`near` 60 日已实现波动 **120% 年化**，因此目标仓位只给到 50.5%，其余留现金。

**二、业绩（20bps、引擎收盘成交口径）**

| 区间 | 策略 | BTC |
| --- | ---: | ---: |
| 全样本 2022-01-01 .. 2026-10-07 | **22.68x** | 2026 YTD -6% |
| 2022 | -16.34% | — |
| 2023 | +215.81% | — |
| 2024 | +90.17% | — |
| 2025 | +102.13% | — |
| 2026 YTD（至 10-07） | **+123.26%** | **-6%** |
| 样本外 2026-09-22 .. 2026-10-07（16 天） | **+5.61%**（+3h 口径 +5.76%） | **-3.84%** |
| 样本外回撤 | -6.5% | -3.8% |

- 研究截止（2026-09-21）时的注册结论是 **19.53x**；样本外这两周把它推到 **22.68x**（至 10-07），同期 BTC 下跌。样本外窗口太短，**不构成验证**，只记录。
- **2026-10-08 数据推进一天后的更新**：样本外窗口延长到 **17 天**，H5 在 10-08 单日回吐，20bps +3h 较差口径从 1.0576x 降到 **0.9689x（−3.11%）**，同期 BTC **0.9431x（−5.69%）**；最大回撤 H5 -8.6% vs BTC -5.7%。也就是说，**样本外绝对收益转为小幅为负，但相对 BTC 仍然领先**。当前信号（10-08 收盘）仍是 100% `near`，目标 gross 从 0.505 升到 **0.621**（`near` 波动率回落，波动率目标允许更大仓位），需要加仓。`reports/phase_momentum_oos_2026/` 与 `reports/phase_momentum_live/` 已同步刷新到 10-08。
- 2026 年的收益高度依赖 `zcash`（YTD +153%）与 `near`（9 月以来 +183%）两段行情 —— 这正是动量设计要抓的东西，但也意味着**当前这仓是本轮行情后段进场**。
- 换手随行情下降：2023 年累计成交 42.5x gross，2026 年至今只有 9.6x（长期持有领涨币）。

**三、新诊断：追高进场之后会怎样（`scripts/analyze_momentum_chase_risk.py`）**

对每个持仓日，取**最大持仓币的过去 21 日涨幅**（动量 sleeve 正在追的东西），再看策略自己随后的 5/10/21 日收益：

| 分位（按追涨幅度） | 天数 | 中位涨幅 | 21 日前瞻均值 | 21 日胜率 | 21 日最差回撤 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1（最低） | 175 | +4.9% | +5.33% | 56.0% | -21.8% |
| 2 | 175 | +22.3% | +6.70% | 46.9% | -21.0% |
| 3 | 174 | +40.8% | +8.33% | 51.7% | -20.1% |
| 4 | 175 | +67.9% | **+10.71%** | **61.7%** | -19.3% |
| 5（最极端） | 175 | **+113.7%** | **+1.78%** | **42.9%** | -19.4% |

- **最强的一档（前 20%，门槛 21 日 +87%）之后，21 日前瞻收益只有 +1.78%，约为第 4 档（+10.71%）的 1/6**；5 日/10 日差异较小，说明是**约三周尺度**的边际衰减，不是立刻崩。
- **不是波动率目标造成的假象**：按前瞻期平均 gross 归一后，极端档 **+6.55%** vs 其余 **+14.86%**（Welch t **-2.83**）；原始口径差 -5.97pp（t **-4.99**）。极端档 gross 确实更低（0.36 vs 0.49），但归一后差距仍在。
- **当前这仓正好落在这一档**：`near` 过去 21 日 **+104.3%**（第 **87** 分位）。
- **外部证据存在冲突，已如实记录**：股票 MAX 效应（Bali–Cakici–Whitelaw 2011）说极端涨幅后收益更低；加密 MAX 动量研究（Li–Urquhart 等 2021，本综述 S6）结论相反。本项目用**最大单日涨幅**复现该构造时，对策略前瞻收益**没有显著影响**（21 日 t=-1.17，按 gross 归一 t=+0.37），因此两者都不能直接支持或否定本节的「21 日累计涨幅」结果。
- **结论与边界**：极端追涨档**仍然是正收益**（+1.78% / 21 日），所以这不是「不能买」的信号，而是「边际更薄、胜率更低」的状态；且本结果是**样本内、且以策略自己选择持有为条件**。**不改规则**：任何「追涨就减仓/不买」的改动都属于新的预注册试验，在当前 DSR 已因试验数过多而失败的前提下，加试验只会让门槛更高。本节只做记录与风险披露。
- **复现**：
  ```bash
  .venv/bin/python scripts/analyze_momentum_chase_risk.py --output-dir reports/phase_momentum_chase_risk
  ```
  明细：`reports/phase_momentum_chase_risk/{daily_chase.csv,chase_buckets.csv,chase_extreme_vs_rest.csv,max_daily_buckets.csv,max_daily_extreme_vs_rest.csv,report.md,manifest.json}`。

---

### 00.19 2026-10-09 预注册试验 H6：永续资金费率 overlay —— **被拒**（负结果）

**一、为什么做 H6**

`§00.17` 的资金费率筛查发现：point-in-time Top20 成员日均永续资金费率的 7 日均值（`funding_level`）是全部 20 个候选状态里**最强的崩溃月区分变量**（崩溃月 3.19 bps/日 vs 其余 0.70，差 +1.12 个 rest-std），只是**月频 Spearman 不达标**（+0.162 < 0.38 门槛）。筛查本身不构成规则，因此把它升级为一个**预注册**（`PR2026-10-H6`，登记在 `reports/research_trial_inventory/preregistered_trials.csv` 后才运行）的生产引擎试验：机制沿用 H5 的「反向分位缩放」形式，把分散度换成资金费率水平。

**二、规则（登记原文）**

在冻结的 **H5** 账本（champion + H3 breadth 共闸，50/50 目标层混合，已含 dispersion overlay）之上，再乘一个 point-in-time 拥挤因子：

- `state(D)` = point-in-time Top20 中有 Binance USDT 永续的成员，其**当日资金费率截面均值**的 **7 日均值**（bps/日；可用成员 < 5 → 无读数）。
- `f(D) = min(1, 过去 252 日的 P80(state) / state)`，**下限 0.25**，取**信号收盘前一日**的值；缺失/非正读数 → `f(D)=1`。
- 两个账本统一乘 `f(D)`（拥挤是市场级状态）；gross 仍 ≤ 1，overlay 只能减仓。

预注册的 kill criterion（20bps、+3h、更差缺失K线策略，且 2/50bps 同向）：`MDD(H6) >= MDD(H5)-0.05`、`Sharpe(H6) > Sharpe(H5)`、`rolling 1y worst(H6) > H5`、且 `M(H6) >= 0.85 x M(H5)`；否则拒绝。

**三、结果：被拒（2022-01-01 .. 2026-09-21，20bps，+3h 更差策略）**

| 指标 | H5（冻结） | **H6** | 判定 |
| --- | ---: | ---: | --- |
| 总收益 | **19.53x** | **12.02x** | `12.02 < 0.85×19.53=16.60` → **FAIL** |
| Sharpe | **1.623** | **1.537** | 未提升 → **FAIL** |
| 最大回撤 | -36.97% | **-27.58%** | 改善 9.4pp（达标） |
| rolling 1y worst | 0.806 | 0.806 | 未提升 → **FAIL** |
| 年均 gross | 0.261 | 0.226 | 减仓确实发生 |
| 年换手 | 24.84 | 22.47 | — |

- 三个成本档方向一致：2bps 24.12x→14.55x、20bps 19.53x→12.02x、50bps 13.72x→8.74x、100bps 7.61x→5.13x；Sharpe 全部下降（1.72→1.64 / 1.62→1.54 / 1.46→1.36 / 1.18→1.08）。
- 预注册邻域同样不达标：P70 → 10.09x / Sharpe 1.518 / MDD -27.1%；P90 → 14.18x / Sharpe 1.556 / MDD -35.3%。三档 P80/P70/P90 都是「降回撤、更降收益」。
- 分年看，损失集中在趋势最强的年份：2023 1.998→1.307、2024 0.949→0.678、2026 1.064→0.949；2022 熊市两者完全相同（2022-01 起才有资金费率覆盖，且当时组合基本空仓）。也就是说，**高资金费率状态同时包含「崩溃前」和「动量最强」两类时段**，减仓把两者一起削掉。

**四、结论与不变量**

- **H6 被拒，冻结规格仍为 H5。** 资金费率的崩溃区分度真实存在，但作为**减仓规则**它净损失收益与 Sharpe，达不到任何一条提升要求；这解释了为什么 `§00.17` 的筛查结论不能直接变成规则。
- **H5 的 DSR 因新试验数上升而进一步变差**：把 H6 与其预注册邻域（P70/P90）计入后，Top20/2022 试验数由 6,135 升至 **6,138**，H5 的 Deflated Sharpe 由 0.860 微降到 **0.858**（`reports/phase_momentum_hypotheses_2026_10/dsr.csv`，`top20_2022_trials` scope）。这是选择偏差的诚实记账，**不通过放宽门槛来掩盖**。
- **部署约束（登记时已声明）**：项目目前没有日频资金费率实时源（`data/raw/binance_funding` 来自 Binance 月度归档），即使 H6 通过也只能回测、不能上实盘；这一点写进了 `docs/research/literature_review_2026-09.md` §H6 的 deviation。
- **复现**：
  ```bash
  .venv/bin/python scripts/run_phase_momentum_hypotheses.py --register
  .venv/bin/python scripts/run_phase_momentum_hypotheses.py
  ```
  明细：`reports/phase_momentum_hypotheses_2026_10/{runs.csv,decision.csv,kill.csv,neighbourhood.csv,dsr.csv,yearly.csv,returns_20bps.csv,report.md}`。

---

### 00.20 2026-10-09 上线路线：DSR 在当前试验数下结构性不可达，必须先做规则决策

**一、问题被量化了**

`AGENTS.md` 要求多重检验/选择偏差门槛。H5 唯一没过的就是它（DSR 0.858 < 0.95）。
新增工具 `scripts/analyze_dsr_horizon.py`（`reports/phase_momentum_dsr_horizon/`）回答
「还需要多少新数据」：保持 H5 日收益的波动/偏度/峰度不变、只改新数据均值，
以项目真实试验数 N=6,138（期望最大年化 Sharpe 1.184）重算合并样本 DSR。

| 假设的新样本外年化 Sharpe | 达到 DSR 0.95 所需新数据 |
| ---: | ---: |
| 1.40 | > 10,000 天（≈27 年，实质不可达） |
| **1.623（＝样本内水平）** | **2,340 天（6.4 年）** |
| 1.80 | 1,232 天（3.4 年） |
| 2.00 | 776 天（2.1 年） |

**结论：DSR 把「从 6,138 个候选里挑出最好的」这个选择惩罚再收一次费，且收在整个样本上。
只要新数据 Sharpe 不超过样本内水平，合并 Sharpe 会被拉低，DSR 上升极慢。**
这不是「差一点」，是**在当前 N 下的结构性不可达**。

**二、对比：只用样本外的检验便宜约 6 倍**

样本外窗口没有参与选规格，其 Sharpe 是无偏估计，不需要再付选择惩罚。假设 Sharpe≈1.6：
单侧 t 检验 95% 需要 **386 天（1.06 年）**，99% 需要 **772 天（2.11 年）**。

**三、这必须先由项目负责人决策，不能自行改规则**

`AGENTS.md` 原文允许「an equivalent documented method」和「genuinely out-of-sample splits」，
但也明确「Never weaken, reinterpret, or remove a constraint after seeing a backtest result」。
因此这里**不能由我自行把 DSR 换成 t 检验**。两条路：

- **A. 维持 DSR ≥ 0.95 为硬门槛** → H5 在本项目试验数下实际上**永远无法上线**，
  只能长期保持 provisional 的样本外记录。
- **B. 负责人现在（在样本外仍无信息量时）批准一套预声明的样本外验收协议** →
  DSR 继续报告但不再作为唯一门槛，用 12–18 个月的真实样本外按事先写死的判据决定。

**我的建议是 B**，但**必须由负责人批准，且必须现在批准**；等样本外攒到能看出结论再定规则
就是事后挑口径，规则本身不允许。

**三之二、推论：继续「优化策略规则」现在是负收益动作**

DSR 的分母 N 统计所有在 Top20/2022 上回测过的配置。**每加一条规则、每扫一个参数，
N 就变大、期望最大 Sharpe 就变高、DSR 就更远。** 在规则决策（§三）解决之前，
任何新的策略试验都在把上线推远；而 §00.14–00.19 已连续证明没有免费杠杆
（再加 overlay 无效、H4/H6 被拒、三族状态筛查全被拒）。
**策略层面已经到顶**——不是「暂时没找到更好的」，而是「再找会变差」。
剩余可做且有效的只有：执行（+1h）、数据链路与告警、预声明验收协议 + 攒样本外、资金分层与熔断。

**四、上线路线图**

完整方案写入 `docs/operations/go_live_plan.md`：预声明样本外验收协议（§3）、
+1h 执行杠杆（§4，20bps 下 19.53x → **22.80x**、Sharpe 1.623 → 1.704、MDD -37.0% → -33.3%，
纯运营、不改规则、不抬高 N）、运营就绪清单（§5）、资金分层（§6）、gate 表（§7）、
时间线（§8）。**最早可上线 ≈ 2027 年 9 月之后**（样本外满 365 天 + 影子/小额期）。

**五、复现**

```bash
.venv/bin/python scripts/analyze_dsr_horizon.py --output-dir reports/phase_momentum_dsr_horizon
```

明细：`reports/phase_momentum_dsr_horizon/{dsr_by_horizon.csv,required_oos_sharpe.csv,required_oos_days.csv,oos_only_significance.csv,report.md,manifest.json}`。

---

## 0. 2026-09-23 新主候选：相位错开多周期动量（生产引擎已验收）

> 本节是新主候选的权威结论，取代旧 21D、11D/2 BTC 闸门和此前“无稳定 20x 策略”的叙述。旧章节仅保留为历史审计记录。

### 0.0 策略规则

- 股票池：严格 point-in-time **Top 20**，包含 BTC；CMC 决定成员，缺失 CMC 的币不参与排名。
- 信号：四条透明 trailing-return 动量，等权：
  1. `weighted_multi_horizon`：7/14/21/28/42/60D = 10/15/20/25/15/15%；
  2. `ret21`；
  3. `equal_7_14_28_60`；
  4. `equal_14_21_28`。
- 每条信号做 3 个相位错开，共 12 个 sleeve；每 sleeve 每 3 天检查一次，合起来每天都有 sleeve 在检查。
- 持仓只要仍在当前 sleeve 的 Top2 就继续持有；跌出 Top2 才换到当前第 1 名；跌出当天 Top20 立即退出。
- 风控：BTC 100D MA + confirm2；单 sleeve 按 60D 已实现波动率缩放到 80% 目标波动；gross exposure 硬上限 1.0，无杠杆、无做空。
- 执行：收盘信号，T+1；所有成本按 2/20/50/100bps 分别重跑生产引擎 `run_backtest`。

### 0.1 主结果

2022-01-01 → 2026-09-21，严格 Top20、无杠杆：

| 往返总成本 | 总收益 | CAGR | Sharpe | 最大回撤 |
|---|---:|---:|---:|---:|
| **2bps** | **28.80x** | 103.69% | 1.514 | -42.61% |
| **20bps** | **23.09x** | 94.38% | 1.433 | -44.92% |
| 50bps | 15.97x | 79.78% | 1.297 | -48.72% |
| 100bps | 8.62x | 57.79% | 1.069 | -54.49% |
| BTC 买入持有 | 1.87x | 14.17% | 0.515 | -66.89% |

逐年收益（20bps 主策略 vs BTC）：

| 年份 | 主策略 | BTC |
|---|---:|---:|
| 2022 | -22.8% | -64.3% |
| 2023 | +378.4% | +155.4% |
| 2024 | +78.5% | +121.1% |
| 2025 | +65.5% | -6.3% |
| 2026 YTD | +111.7% | -1.0% |

### 0.2 过拟合与稳健性门槛

| 检验 | 结果 | 判定 |
|---|---:|---|
| 参数邻域（25 个固定变体 @20bps） | 除“去掉 BTC 闸门”为 2.88x 外，其余约 9.5x–30.0x；主策略 23.09x | 通过；BTC 闸门是必要风险开关 |
| ~~固定主策略 Deflated Sharpe~~ | ~~0.9945~~ | **作废**：只按 32 个候选计算；按真实试验数为 0.731（2026-10-08，N=6,132），失败（见 §00） |
| ~~固定主策略 White Reality Check~~ | ~~p=0.0150~~ | **作废**：只对主策略单独做；家族内对零 p=0.019、对 BTC p=0.025（见 §00） |
| 动态 walk-forward（365D 训练/90D 测试，2023 起，含 40bps 切换成本） | 20.78x，Sharpe 1.621 | 通过（>20x） |
| 固定主策略 2023 起（~~OOS~~ 样本内） | 29.91x，Sharpe 1.734 | **重标**：参数用全样本挑选，不是样本外（见 §00） |
| ~~固定主策略 CSCV（12 块、924 折）~~ | ~~低于中位数比例 7.47%~~ | **不计为证据**：训练/测试分布构造上相同，只是样本内诊断（见 §00） |
| 参数等权集成 CSCV | OOS 排名中位数 0.438；低于中位数比例 85.71% | 拒绝作为冠军 |
| 去掉最佳年份 2023 | 主策略 4.83x、Sharpe 1.112；BTC 同期 0.73x | 通过；收益不依赖单一年份 |
| 去掉任意一条信号 @20bps | 20.58x–27.58x | 通过；不依赖单一信号 |
| 去掉任意一个相位 @20bps | 21.26x–23.91x | 通过；不依赖单一相位 |
| 市场状态拆分（bull / non-bull）@20bps | ~~bull 51.83x vs BTC 13.65x；non-bull 0.445x vs BTC 0.137x~~ | **作废**（同日标签前视）；前一日标签：bull 25.37x vs BTC 3.27x，non-bull 0.91x vs BTC 0.57x（见 §00） |
| 参数等权集成 leave-one-parameter-out @20bps | 15.11x–16.93x | 集成低于 20x，仅保留为风险分散参考，不替代固定主策略 |
| 2020-10-03 → 2021-12-31 压力 | 20bps 4.55x，Sharpe 2.394，最大回撤 -18.9% | 通过 |
| 逐条选币审计 | 10,308 条选币记录，0 条不在当天 Top20、0 条无价格、0 条 Rain/稳定币；所有快照恰好 20 个币 | 通过 |
| 事后挑最佳参数 PBO | ~~0.6288~~ 0.526（修正后） | 失败；因此禁止动态挑选全样本最佳参数，使用固定主策略 |

解释：

- ~~PBO 0.63 否定的不是固定主策略……固定主策略的 CSCV OOS 排名稳定性为 7.47% 低于中位数，反而是通过的。~~ **作废（2026-09-25）**：固定主策略 CSCV 在构造上无法提供样本外证据；PBO 修正后为 0.526，仍失败（见 §00）。
- 参数等权集成 2bps 为 20.06x，但 20bps 只有 15.97x，且 CSCV 不稳定，因此只保留为风险分散参考，不替代主策略。
- 止损、移动止损和币自身均线过滤都跑过：固定 20% 止损 20bps 为 24.54x 但回撤略差；移动 20% 止损为 22.00x、回撤 -43.32%；币自身 50D/100D/150D/200D 趋势过滤 ~~仅 17.57x/14.71x/10.68x/10.57x~~（列查找 bug，作废）修正后为 24.39x/16.70x/17.03x/11.13x；trend_50 在三项上都优于主策略，但这是修复后事后看到的，不能据此升级规格（见 §00）。
- 市场状态拆分（修正后，前一日状态标签）：bull 阶段主策略 25.37x、BTC 3.27x；non-bull 阶段主策略 0.91x、BTC 0.57x。两种状态下都优于 BTC，但 non-bull 阶段仍是小幅负收益，不能把整体 23.09x 理解成全天候绝对收益。
- ~~这已经是可上实盘测试的研究冠军~~ **（2026-09-25 修正）**：多重检验和参数窄峰两道门槛未通过，冠军只能保持 provisional，按 §00.4 冻结规格做样本外记录；容量、真实滑点、交易所退市、数据延迟和监控仍需验证。

### 0.3 复现实验

按依赖顺序（默认参数即权威口径，样本 2022-01-01 → 2026-09-21；2026-09-25 全部重跑过）：

```bash
# 1) 主报告、候选矩阵、成交时点（Binance/Gate 小时 K 线见 scripts/download_hourly_prices.py）
.venv/bin/python scripts/run_phase_momentum.py
.venv/bin/python scripts/run_phase_momentum_candidates.py
.venv/bin/python scripts/run_phase_momentum_execution_lag.py --lags 0,1,2 --fill-hours 1,3,6,12 --cost-bps 2,20,50,100

# 2) 试验盘点（多重检验的试验数来源）
.venv/bin/python scripts/build_trial_inventory.py

# 3) 读取候选矩阵的验证
.venv/bin/python scripts/run_phase_momentum_multiple_testing.py
.venv/bin/python scripts/run_phase_momentum_walk_forward.py
.venv/bin/python scripts/run_phase_momentum_fixed_cscv.py
.venv/bin/python scripts/run_phase_momentum_regime_breakdown.py
.venv/bin/python scripts/run_phase_momentum_robustness.py
.venv/bin/python scripts/run_phase_momentum_parameter_ensemble.py

# 4) 其余独立研究与审计
.venv/bin/python scripts/run_phase_momentum_leave_one_out.py
.venv/bin/python scripts/run_phase_momentum_parameter_leave_one_out.py
.venv/bin/python scripts/audit_phase_momentum_selections.py

# 5) 实盘信号（最新已完成的 UTC 日；拒绝过期或未收完的最后一天，见 --max-staleness-days / --allow-partial-day）
.venv/bin/python scripts/run_phase_momentum_live_signal.py
```

权威报告：

- `reports/phase_momentum_2022/`（含 `gap_carries.csv`：缺口 carry 记录）
- `reports/phase_momentum_execution_lag_2022/`（`fill_timing.csv`：收盘后 1/3/6/12 小时成交）
- `reports/research_trial_inventory/`（全项目试验盘点与预先登记台账）
- `reports/phase_momentum_walk_forward_2022/`
- `reports/phase_momentum_multiple_testing_2022/`
- `reports/phase_momentum_fixed_cscv_2022/`
- `reports/phase_momentum_leave_one_out_2022/`
- `reports/phase_momentum_parameter_leave_one_out_2022/`
- `reports/phase_momentum_regime_2022/`
- `reports/phase_momentum_robustness_2022/`
- `reports/phase_momentum_selection_audit_2022/`
- `reports/phase_momentum_live/`

---

## 0.4 历史相位审计：旧 21D 冠军不能直接上线

固定 21D 的 25.87x/22.44x 结果对调仓日历起算日极其敏感。保持所有规则不变，只把 21D 日历平移 0–20 天：

| 指标 @20bps | 数值 |
|---|---:|
| 当前 2022-01-01 相位 | **22.44x** |
| 21 个相位中位数 | **3.94x** |
| 21 个相位最差 | **0.61x** |
| 21 份完全错开组合 | **5.51x** |
| 21 份错开 Sharpe / 最大回撤 | **1.11 / -34.6%** |

因此：

- 22.44x 是相位上尾，不是稳定预期；
- 无杠杆条件下，当前证据不支持稳定做到 20x；
- 旧冠军标记为 **phase-sensitive / provisional**；
- 逐决策点外部证据见 `docs/research/strategy_evidence_audit.md`；
- 复现实验见 `reports/strategy_evidence_audit_2022/`。

### 0.1 决策点消融：11D BTC 闸门是局部尖峰，不能直接上线

第二阶段审计保持 Top20、CTREND-breakout、无杠杆、T+1 不变，分别开关自身止损、BTC 闸门和重入规则，并在 21 个调仓相位及 21 份完全错开组合上评估。20bps 下：

| 变体 | 21 份错开组合总收益 | CAGR | Sharpe | 最大回撤 |
|---|---:|---:|---:|---:|
| 当前组合：75D/3 止损 + 11D/2 BTC 闸门 | **5.51x** | 43.5% | 1.11 | -34.6% |
| 仅 BTC 11D/2 闸门，无自身止损 | 5.17x | 41.6% | 1.07 | -35.6% |
| 无自身止损、无 BTC 闸门 | 2.42x | 20.6% | 0.62 | -67.5% |
| 仅自身 75D/3 止损，无 BTC 闸门 | 2.37x | 20.1% | 0.60 | -58.0% |
| 止损后立即重入，无 BTC 闸门 | 2.22x | 18.4% | 0.58 | -62.7% |
| 自身止损 + BTC 闸门都立即重入 | 1.49x | 8.8% | 0.42 | -60.0% |
| 仅 BTC 闸门，立即重入 | 1.37x | 6.9% | 0.39 | -61.2% |

关键参数邻域：

| BTC trailing lookback（confirm2） | 10D | 11D | 14D | 20D | 30D | 50D |
|---|---:|---:|---:|---:|---:|---:|
| 21 份组合 @20bps | 3.05x | **5.51x** | 1.98x | 2.92x | 4.47x | 4.09x |

| BTC 11D 闸门 confirm | 1 日 | 2 日 | 3 日 | 5 日 |
|---|---:|---:|---:|---:|
| 21 份组合 @20bps | 2.20x | **5.51x** | 5.02x | 2.30x |

自身止损网格（20/50/65/75/100/150/200 × confirm1/2/3）在 20bps 下的 21 份组合约为 3.75x–5.66x；50–100D、confirm1–3 是宽平台，75D/3 不是唯一最优，但也没有被邻域否定。

结论：

- **11D/2 BTC 闸门目前是过拟合嫌疑最大的继承规则**；它把 2.4x 基准提高到 5.5x，但 10D/14D 和 confirm1/5 都显著崩落，不能把它当成已验证规律。
- **“止损后等下一次调仓再重入”得到项目内实证支持**：立即重入因来回打脸和换手，21 份组合明显更差。
- **75D/3 自身止损处在宽参数平台内**，方向上可保留；但它不是论文规定的唯一参数。
- 当前没有可直接上实盘的冠军。11D/2 必须替换为参数不敏感的市场闸门，或通过独立样本重新验证。
- 复现实验见 `reports/decision_point_ablation_2022/`。

### 0.2 波动率缩放 BTC 闸门：方向合理，但还不足以替代

按 Moreira/Muir 和 Yang 的波动率管理方向，把固定 11D 阈值换成 BTC 自身波动率缩放的 trailing 闸门（Chandelier 风格），并保持 75D/3 自身止损、下一次调仓重入、无杠杆和 T+1 不变。20bps 下最佳参数邻域：

| 参数 | 21 份错开组合 | 相位中位数 | 最差相位 | Sharpe | 最大回撤 |
|---|---:|---:|---:|---:|---:|
| lookback 30D / vol30 / 1.5σ / confirm2 | 3.22x | 1.89x | 0.20x | 0.70 | -56.0% |
| lookback 50D / vol30 / 1.5σ / confirm2 | 3.08x | 1.68x | 0.16x | 0.69 | -56.9% |

结论：

- 波动率缩放闸门比 11D/2 的参数邻域更连续，但绝对收益和相位稳定性仍不足；它不能把策略恢复到“稳定 20x”。
- 很多更宽的波动率倍数几乎不触发退出，退化回“无 BTC 闸门”版本。
- 该方向可以继续研究，但当前不替换冠军规则。
- 复现实验见 `reports/volatility_gate_validation_2022/`。

---

### 0.3 相位不敏感 + 波动率目标：新的领先候选（仍为研究态）

> 2026-09-23 修正：早期快速模拟器会在非调仓日无成本地把权重重置回目标值，和生产引擎不一致。现已改为“目标事件生效后持仓权重随价格漂移”，并与 `run_backtest` 对拍。下表的数字均为修正后结果；旧报告中的 3.91x/4.57x 等数字作废。

这轮不再固定 21D，也不再用 11D/2 BTC 闸门，而是：

- 选币改为 **14D balanced top1，排除 BTC**；
- 持仓仍用 **75D/3 自身趋势止损，下一次调仓重入**；
- 市场闸门改为 **BTC 100D MA，confirm2**；
- 仓位按 **60D 已实现波动率** 缩放到目标波动，**只能降仓，最大 gross exposure = 1.0，不加杠杆**；
- 所有相位等权错开，报告相位不敏感组合，而不是固定起点上尾。

2022-01-01 → 2026-09-21，20bps，相位不敏感 14 份组合：

| 目标波动 | 总收益 | Sharpe | 最大回撤 | 2025–2026 测试段 | 测试 Sharpe | 测试最大回撤 |
|---|---:|---:|---:|---:|---:|---:|
| 50% | 4.14x | 1.091 | -33.5% | 1.65x | 1.121 | -16.1% |
| 60% | 4.75x | 1.070 | -38.1% | 1.75x | 1.117 | -18.2% |
| 70% | 5.21x | 1.049 | -42.1% | 1.82x | 1.107 | -20.8% |
| 80% | 5.22x | 1.006 | -45.4% | 1.85x | 1.074 | -23.3% |

同期 BTC 约 1.87x；2025–2026 测试段 BTC 约 0.93x。这个候选的参数邻域是连续的：50%–80% 目标波动、60D 波动窗口、7D/14D 调仓周期都能得到相近结论，不像 11D/2 那样一跳就崩。

但结论仍然不能夸大：

- 全样本约 4x–5x，不是 20x；
- 最大回撤仍有 34%–45%；
- 单币集中和 2024/2026 行情依赖仍然存在；
- 这只是一个更稳健的领先候选，尚未完成成本、滚动窗口、因子家族和多重检验。

复现实验：

- `reports/vol_target_neighborhood_2022/`：7/14/21/28D × 目标波动 50%–80% × 20/30/60D 波动窗口。
- `reports/vol_target_frontier_2022/`：目标波动 80%–200% 的收益/回撤边界。
- `reports/phase_invariant_vol_target_gates_2022/`：BTC 100D/200D 闸门和止损开关对照。

### 0.4 领先候选的成本和滚动窗口压力测试

以更保守的 **14D balanced top1 ex-BTC + 75D/3 自身止损 + BTC 100D MA confirm2 + 60D 波动率目标 50%** 为例（修正漂移口径后重跑）：

| 往返总成本 | 全样本 | Sharpe | 最大回撤 | 2025–2026 测试段 | 1 年滚动最差窗口 |
|---|---:|---:|---:|---:|---:|
| 2bps | 4.69x | 1.174 | -32.7% | 1.72x | 0.821x |
| 20bps | 4.14x | 1.091 | -33.5% | 1.65x | 0.812x |
| 100bps | 2.37x | 0.724 | -38.1% | 1.37x | 0.765x |

逐年收益（20bps）：

| 年份 | 策略 | BTC |
|---|---:|---:|
| 2022 | -13.6% | -64.3% |
| 2023 | +58.0% | +155.4% |
| 2024 | +84.2% | +121.1% |
| 2025 | +8.3% | -6.3% |
| 2026 YTD | +51.9% | -1.0% |

解释：

- 这个版本在 2023 年明显跑输 BTC，但在 2022、2025、2026 胜出；
- 100bps 压力下仍约为 BTC 的 1.27 倍，但 1 年滚动最差窗口约 0.77x，不是无风险；
- 最大回撤主要来自 2024 年末的震荡回撤，不是旧策略的单次 -80% 崩盘；
- 这是目前“收益、回撤、成本、滚动窗口”四项最平衡的候选。

复现实验见 `reports/vol_target_cost_rolling_2022/`。

### 0.5 选币分数族邻域：收益并非来自一个已验证的因子

为了确认领先候选不是只依赖 `balanced` 这一组自建权重，保持 **14D、60D 波动率目标、own75、BTC MA100、20bps、全部相位错开** 不变，只替换 CTREND-lite 的分数族：

| 分数族 | 50% 目标波动总收益 | 50% Sharpe | 50% 最大回撤 | 60% 目标波动总收益 | 60% Sharpe | 60% 最大回撤 |
|---|---:|---:|---:|---:|---:|---:|
| balanced | **4.14x** | 1.091 | -33.5% | **4.75x** | 1.070 | -38.1% |
| relative_strength | 3.92x | **1.091** | **-30.1%** | 4.54x | **1.070** | **-34.9%** |
| breakout | 3.67x | 1.028 | -34.3% | 4.12x | 1.010 | -39.0% |
| acceleration | 3.20x | 0.949 | -35.3% | 3.44x | 0.921 | -40.2% |
| vol_adjusted | 1.92x | 0.632 | -31.2% | 1.86x | 0.597 | -33.3% |

结论：

- `balanced`、`relative_strength`、`breakout` 处在同一量级，说明结果不完全依赖某一个分数族；
- 但 `acceleration` 和 `vol_adjusted` 明显更差，说明“因子族不敏感”并不成立；
- 因此当前候选的收益不能被表述为“已验证的选币 alpha”，它仍然混合了波动率控制、BTC 闸门、单币集中和样本内分数选择；
- 更保守的研究对照是 `relative_strength` 50%：全样本略低，但 Sharpe 相同、最大回撤更低；
- 下一步必须做滚动 walk-forward 和多重检验修正，而不是继续在完整样本上挑最高分。

复现实验：`reports/vol_target_score_family_*_2022/`。

### 0.6 Walk-forward 与参数集成：不要动态挑参数，固定等权集成更稳

为了回答“2022–2026 全样本挑出来的 50%/60%/70%/80% 参数是不是事后有效”，新增了真正的 walk-forward：

- 训练窗口：过去 365 天；
- 测试窗口：接下来 90 天；
- 每 90 天只用过去数据重新选择 7D/14D × 50%–80% 中的 8 个版本；
- 20bps，策略切换额外按 40bps 计；
- 样本外起点：2023-01-01。

结果：

| 方案（2023-01-01 → 2026-09-21） | 总收益 | Sharpe | 最大回撤 |
|---|---:|---:|---:|
| trailing Sharpe 动态选参数 | 4.12x | 1.166 | -37.0% |
| trailing 收益动态选参数 | 5.43x | 1.159 | -48.5% |
| **8 个参数版本固定等权集成** | **6.17x** | **1.287** | **-42.0%** |
| BTC 买入持有 | 5.23x | 1.183 | -53.1% |

结论：

- 动态挑参数没有创造稳定超额；按 trailing Sharpe 选甚至跑不过 BTC；
- 固定等权集成反而在收益、Sharpe、最大回撤三项都优于 BTC；
- 原因是它不押注某个精确周期/目标波动，而是把 7D/14D × 50%/60%/70%/80% 全部纳入，降低了单参数风险；
- 这仍然是单币集中轮动，等权集成只分散参数，不分散底层单币风险。

等权集成的成本和全样本表现：

| 往返成本 | 全样本 2022–2026 | 全样本 Sharpe | 全样本最大回撤 | 2023 起样本外 | 样本外 Sharpe |
|---|---:|---:|---:|---:|---:|
| 2bps | 6.22x | 1.139 | -40.4% | 7.54x | 1.403 |
| 20bps | 5.05x | 1.033 | -42.0% | 6.17x | 1.287 |
| 100bps | 2.00x | 0.559 | -49.1% | 2.52x | 0.765 |

风险提示：

- 20bps 下 1 年滚动最差窗口仍为 **0.72x**，不是无风险；
- 100bps 下样本外仍有 2.52x，但 Sharpe 只有 0.765；
- 等权集成的优势来自参数分散，不代表 CTREND 选币因子已经被验证；
- 下一步应该做多重检验修正、容量/滑点和退市场景，而不是继续加参数。

复现实验：

- `reports/vol_target_walk_forward_2022/`
- `reports/vol_target_walk_forward_multiple_2022/`
- `reports/vol_target_ensemble_2022/`

### 0.7 新的高收益候选：Top20 内三族动量事件组合（仍为研究态）

在严格 Top20、无杠杆、T+1、2bps 真实成本口径下，新增了一组比波动率目标集成收益更高、但参数更敏感的候选：

- 每天在 point-in-time Top20 内计算 `balanced`、`relative_strength`、`breakout` 三族 CTREND-lite 分数；
- 每族使用同一事件规则：最少持有 5 天、持仓排名带 2、挑战者分数领先 10% 才切换、1 天确认；
- 持仓一旦跌出当天 Top20，立即退出，不再等待最少持有期；
- BTC 低于 100 日均线且连续确认 2 天时全部转现金；
- 60 日已实现波动率目标，主候选等权组合 70% 和 80% 两个目标波动版本；
- 总敞口硬上限 1.0，不做空、不加杠杆、不使用 Top20 以外资产。

严格 Top20 版本结果：

| 2022-01-01 → 2026-09-21 | @2bps | @20bps | @50bps | @100bps |
|---|---:|---:|---:|---:|
| 总收益 | **28.92x** | **19.69x** | **10.37x** | **3.54x** |
| CAGR | 103.9% | 87.9% | 64.1% | 30.7% |
| Sharpe | 1.434 | 1.306 | 1.090 | 0.725 |
| 最大回撤 | -46.2% | -48.7% | -54.5% | -63.5% |

分段结果（2bps / 20bps）：

| 区间 | 总收益 | Sharpe | 最大回撤 |
|---|---:|---:|---:|
| 2023 起 | **39.91x / 27.68x** | 1.751 / 1.612 | -46.2% / -48.7% |
| 2024 起 | **13.60x / 10.75x** | 1.696 / 1.575 | -46.2% / -48.7% |

年度收益（2bps）：2022 **-27.5%**、2023 **+193.3%**、2024 **+287.6%**、2025 **+81.8%**、2026 至 9 月 **+93.1%**。2020-10 至 2021-12 的固定规则压力检查为 **6.62x @2bps**，说明它不是只在 2024 年单点有效；但这仍不是实盘授权。

事件规则邻域敏感性（全样本 2022–2026，2bps）：

| 事件规则 | 总收益 | 2024 起 |
|---|---:|---:|
| 主候选：mh5 / hr2 / gap10% / confirm1 | **28.92x** | **13.60x** |
| gap 降到 5% | 24.66x | 8.84x |
| hold-rank 放宽到 3 | 15.79x | 6.57x |
| 最少持有放宽到 10 天 | 8.80x | 4.59x |

严格 Top20 退出的代价也很大：如果不要求跌出 Top20 后立即退出，全样本 2bps 为 41.52x、20bps 为 28.43x；严格版本分别降到 28.92x 和 19.69x。由于用户硬约束是“不能超过 Top20”，报告只把严格版本作为主口径。

闸门和目标波动邻域也做了低维审计。2bps 下：无 BTC 闸门只有 10.80x；MA50/confirm1–3 为 12.15x–13.79x；MA100/confirm1–3 为 23.62x–28.95x；MA200/confirm1–3 为 16.32x–18.19x。MA100 的 confirm1 和 confirm2 几乎相同（28.95x / 28.92x），是当前闸门平台；目标波动从 70%/80% 提高到 90%/100% 后全样本反而降到 28.05x、2024 起仅 13.70x，因此没有采用更高目标波动。

结论：

- 这是本轮新增的**高收益严格 Top20 研究候选**：在 2022–2026 全样本、2bps 实际成本口径下超过 20x；
- 但它的收益高度依赖一个事件规则尖峰，邻近参数虽然仍为正，却从 28.9x 掉到 8.8x–24.7x，不能据此宣称稳定 alpha；
- 2024 起子区间只有 13.6x @2bps，说明 20x 目标主要由 2023 年贡献，未来不能外推；
- 因此新候选标记为 **高收益研究候选 / provisional**，不能覆盖更稳健但收益较低的波动率目标集成，也不能直接上实盘；
- 下一步必须做真正的嵌套 walk-forward、多重检验修正、换手/容量压力和不同市场阶段的独立验证。

复现实验：

- `reports/momentum_event_ensemble_2022/`
- `scripts/run_momentum_event_ensemble.py`


### 0.8 Top20 市场宽度闸门：风险明显下降，2024 起收益改善

前一轮三族动量事件组合的弱点是 2024 起只有 13.60x @2bps，且最大回撤 -46.2%。新增一个只用 **当前 Top20 成员**计算的市场宽度信号：

- 宽度 = 当前 Top20 中收盘价高于自身 50 日均线的币占比；
- 基础闸门仍是 BTC 100 日均线、确认 2 天；
- 宽度闸门版本再要求宽度 ≥ 50%；
- 混合版本 = 50% 基础版本 + 50% 宽度版本，每天等权再平衡。

结果（严格 Top20、无杠杆、T+1、60D 波动率目标 70%/80%）：

| 策略 | 成本 | 全样本 2022–2026 | 2023 起 | 2024 起 | Sharpe | 最大回撤 |
|---|---:|---:|---:|---:|---:|---:|
| 基础：BTC MA100 | 2bps | **28.92x** | **39.91x** | 13.60x | 1.434 | -46.2% |
| 宽度 ≥50% | 2bps | 16.61x | 22.45x | **17.66x** | **1.962** | **-32.7%** |
| 50/50 混合 | 2bps | **23.10x** | **31.54x** | **15.95x** | **1.867** | **-36.0%** |
| 基础：BTC MA100 | 20bps | **19.69x** | **27.68x** | 10.75x | 1.306 | -48.7% |
| 宽度 ≥50% | 20bps | 11.51x | 15.82x | **14.09x** | **1.833** | **-34.8%** |
| 50/50 混合 | 20bps | 15.87x | 22.04x | **12.66x** | **1.739** | **-37.2%** |

阈值邻域（全样本 / 2024 起，2bps）：

| 宽度阈值 | 全样本 | 2024 起 | 最大回撤 |
|---|---:|---:|---:|
| 40% | 11.55x | 11.08x | -55.5% |
| 45% | 13.99x | 14.81x | -55.3% |
| **50%** | **16.61x** | **17.66x** | **-54.7%** |
| 55% | 13.83x | 13.71x | -51.4% |
| 60% | 10.42x | 10.55x | -52.3% |

50% 是当前最优阈值，但 45% 和 55% 仍然有效，说明它不是单点尖峰；40% 和 60% 明显更差。混合权重邻域也连续：基础权重 25%/50%/75% 时，2bps 全样本为 19.85x/23.10x/26.18x，2024 起为 16.91x/15.95x/14.83x。

年度收益（2bps）：

| 策略 | 2022 | 2023 | 2024 | 2025 | 2026 至 9 月 |
|---|---:|---:|---:|---:|---:|
| 基础 | -27.5% | +193.3% | +287.6% | +81.8% | +93.1% |
| 宽度 ≥50% | -26.0% | +27.1% | **+457.0%** | +69.0% | +87.7% |
| 50/50 混合 | -26.8% | +97.8% | +368.4% | +76.7% | +92.7% |

2020-10 至 2021-12 压力检查（2bps）：基础 **6.62x**、宽度 50% **5.07x**、50/50 混合 **5.83x**。宽度闸门牺牲了部分 2021 和 2023 收益，但显著改善了 2024 起收益和回撤。

结论：

- 宽度 50% 是目前**风险调整后最干净**的新版本：2024 起 17.66x @2bps，Sharpe 1.962，最大回撤 -32.7%；
- 50/50 混合是收益/风险折中：全样本 23.10x、2023 起 31.54x、2024 起 15.95x @2bps，最大回撤 -36.0%；
- 但它仍然没有在 2024 起单独超过 20x，且宽度阈值仍是项目内选择的参数；
- 外部研究支持“大市值/高流动性币的动量和趋势更稳”，但宽度信号本身还没有同等强度的学术证据，因此该版本标记为**高收益研究候选 / provisional**，不能直接上实盘。

复现实验：

- `reports/momentum_event_breadth_overlay_2022/`
- `scripts/run_momentum_event_breadth_overlay.py`


---

## 1. 一句话结论（有领先研究候选，但仍不可直接上实盘）

在 **真实 point-in-time Top20 + 无杠杆 + 现货** 约束下，当前有两条不同定位的研究路线：**最稳健路线**仍是 **7D/14D × 50%/60%/70%/80% 共 8 个波动率目标版本的固定等权集成**（balanced top1、75D/3 自身止损、BTC 100D MA 闸门）；**最高收益但更参数敏感路线**是第 0.7 节的三族动量事件组合（严格 Top20、2bps 全样本 28.92x，但 2024 起只有 13.60x）。两者都不能直接上实盘。旧的固定起点高收益组合仍保留作上尾对照：

**旧上尾候选：CTREND-breakout 单币集中轮动 + 每日自身趋势止损**
= 历史 Top20 内排除 BTC → 21 天调仓选 CTREND-breakout 第 1 名 → 每日检查持仓是否连续 3 个交易日收盘低于自身 75 日均线 → 若是则转现金，下一次 21 天调仓才允许重入 → BTC 跌破 11 日前收盘连续 2 天则全部转现金。

| 2022-01-01 → 2026-09-21 | 旧上尾候选 @2bps | 旧上尾候选 @10bps | 旧上尾候选 @20bps | BTC |
|---|---:|---:|---:|---:|
| 总收益 | **25.87x** | **24.28x** | **22.44x** | 1.87x |
| CAGR | 99.1% | 96.5% | 93.2% | 13.5% |
| Sharpe | 1.360 | 1.339 | 1.313 | 0.502 |
| 最大回撤 | -41.8% | -42.6% | -44.0% | -67.0% |
| 年换手 | 16.7x | 16.7x | 16.7x | ~0.2x |

> 注意：上表是 2022-01-01 单一相位的上尾结果。相位中位数和错开组合见第 0 节。

**为什么不是每天重新选币**：每天检查数据是对的，但“每天重新选第一名”会显著放大噪声和换手。项目实测了 176 组每日事件驱动/hysteresis 变体：固定起点最高的一组在 20bps 下到 **76.48x**，但参数邻域中位数只有 **2.20x**、邻域最差 **0.11x**，属于明显的参数尖峰，不能作为稳健冠军。第 0.7 节进一步加入了严格 Top20 退出、BTC MA100 闸门和波动率目标，三族动量事件组合在 2bps 全样本达到 **28.92x**，但事件规则邻域从 8.8x 到 24.7x、2024 起只有 13.60x，因此它被记录为高收益研究候选，而不是实盘冠军。把每日检查用于“持仓自身趋势退出”和严格 Top20 风险控制，比每日裸选第一名更可解释。

**止损后为什么不立即重入**：这不是凭直觉保留的规则。逐决策点审计把“下一次调仓重入”和“信号恢复后立即重入”分开比较；立即重入的换手显著上升，21 份错开组合从 5.51x 降到 1.49x，因此当前样本支持等待下一次调仓。

**为什么 11D/2 闸门仍标记为高风险**：它虽然在当前数据上把 21 份组合从 2.37x 提到 5.51x，但 10D/14D、confirm1/5 的邻域都明显更差。没有外部研究直接支持 11D/2；它更像样本内挑出来的参数尖峰，而不是稳定规律。

**结论不是“可以稳定每年翻倍”**：25.87x 仍是 2022-01-01 固定起点的结果。45 个月度起点滚动回测中，@2bps 中位数 **3.80x**、最差 **0.62x**；@20bps 中位数 **3.51x**、最差 **0.585x**。即使改成 21 份错开组合，当前完整规则也只有 5.51x，而且依赖 11D/2 闸门；无闸门版本只有 2.42x。对于旧上尾候选，当前证据不支持稳定 20x；第 0.7 节新候选虽然在 2bps 全样本超过 20x，但 2024 起只有 13.60x，且事件规则邻域敏感，因此同样不支持直接上实盘。

---

## 2. 定义（完全可复现）

| 步骤 | 规则 |
|---|---|
| ① 股票池 | 每个调仓日按 CMC 市值重建 **当时 Top20**；严格流动性门槛：历史 ≥90 天、日成交额 ≥$25M、CMC 市值 >0、价格 >0，并应用项目流动性/包装资产过滤 |
| ② 基础策略 | `ctrend_lite_breakout`：趋势 7/14/21/28/42/60 日收益、短期加速度、90 日高点突破、相对 BTC/ETH 强度、成交量扩张、波动率和过热惩罚的加权排名 |
| ③ 选币 | Top20 内排除 BTC，取分数第 1 名，单币 100% |
| ④ 持仓趋势止损 | 每日检查当前持仓；连续 3 个交易日收盘低于自身 75 日均线 → 目标改为 100% 现金，下一次 21 天调仓日才允许重入 |
| ⑤ 市场风控 | BTC 收盘跌破其 11 日前收盘 → 状态为 risk-off；连续 2 天确认后，目标改为 100% 现金；下一次 21 天调仓日若已恢复 risk-on，才允许重新买币 |
| ⑥ 调仓 | 选币 21 天一次；信号在收盘生成，T+1 执行；持仓趋势和市场风控每日检查，退出可在两次调仓之间发生 |
| ⑦ 成本 | 2bps/10bps/20bps 分别报告；表内均为**往返总成本**（例如 2bps = 每边 1bps 手续费+滑点），2bps 对应你声明的实际成本+返佣口径，20bps 是保守压力测试 |
| ⑧ 无杠杆 | 目标权重之和 ≤1.0，engine 的 `max_gross_exposure=1.0` 会拒绝超限 |

**主动排除 BTC 选币**：加入 BTC 后同一策略 @2bps 只有约 15x，因为 BTC 会在部分高弹性阶段取代真正上涨的币。这里的“排除 BTC”只针对选币，风控仍然使用 BTC 作为大盘闸门。

---

## 3. 权威结果

### 2.1 成本与总收益

| 往返总成本（脚本拆成每边一半） | 总收益 | CAGR | Sharpe | 最大回撤 |
|---|---:|---:|---:|---:|
| 2bps | **25.87x** | 99.1% | 1.360 | -41.8% |
| 5bps | 25.26x | 98.1% | 1.352 | -41.9% |
| 10bps | **24.28x** | 96.5% | 1.339 | -42.6% |
| 20bps | **22.44x** | 93.2% | 1.313 | -44.0% |
| 50bps | 17.68x | 83.7% | 1.236 | -47.9% |
| 100bps | 11.87x | 68.8% | 1.105 | -53.8% |
| BTC @2bps | 1.82x | 13.5% | 0.502 | -67.0% |

### 2.2 逐年表现（策略 @2bps vs BTC）

| 年份 | 策略 | BTC |
|---|---:|---:|
| 2022 | -5.9% | -65.3% |
| 2023 | +66.7% | +155.4% |
| 2024 | **+347.2%** | +121.1% |
| 2025 | +42.7% | -6.3% |
| 2026 YTD | **+158.3%** | -1.0% |

2023 仍然明显输给 BTC；2024 和 2026 是超额收益的主要来源。不要只看 CAGR 或累计倍数。

### 2.3 滚动起点（45 个月度起点）

| 指标 | @2bps | @20bps |
|---|---:|---:|
| 中位数倍数 | 3.80x | 3.51x |
| 最差起点 | 0.62x | 0.585x |
| 最好起点 | 25.87x | 22.44x |
| 中位数最大回撤 | -47.4% | -49.4% |
| 最差最大回撤 | -74.7% | -76.3% |

这张表比 25.87x 更重要：**从 2022-01-01 起跑很好，不代表任意时点开始都很好。**

---

## 4. 候选对比与为什么没有选更高倍数

### 3.1 同一 Top20 面板上的近距离候选

| 基准/候选 | @2bps | @20bps | 滚动起点中位数 | 最差起点 | 最大回撤 |
|---|---:|---:|---:|---:|---:|
| BTC 50/100/120 日均线等 | — | 通常 2–8x | — | — | 高 |
| CTREND-breakout top1 21D + BTC trailing11 confirm2 + BTC停车 | 24.00x | 18.27x | **4.05x** | 0.57x | -64.6% |
| CTREND-breakout top1 21D + BTC trailing11 confirm2 + cash（旧冠军） | 21.56x | 18.57x | 3.48x | **0.67x** | -49.2% |
| **CTREND-breakout top1 21D + 每日自身75日MA confirm3止损 + BTC trailing11 + cash（新冠军）** | **25.87x** | **22.44x** | 3.80x | 0.62x | **-41.8%** |
| 每日事件驱动最高固定起点尖峰（mh5/hr2/gap10/c1） | 137.43x | 76.48x | 邻域中位仅 2.20x | 邻域最差 0.11x | -61.1% |

**取舍**：
- 每日事件驱动最高固定起点看似远超新策略，但参数邻域塌陷，不能采用。
- 新冠军用同一 21 天选币频率，把每日数据只用于持仓自身趋势退出；它提高了固定起点收益、Sharpe 和回撤，同时换手没有上升。
- 新策略在 2022-2023、2022-2024 和 2025-2026 都优于旧冠军；在 2024-2026 基本持平（20bps 下约 1.62x vs 1.63x）。

### 3.2 Top50 灵敏度（不是你的 Top20 规则）

Top50 + strict 流动性 + CTREND relative-strength top1 14D + BTC MA150 在 2022 起 @20bps 达到 **23.54x**。但它不是生产规则：

- 滚动起点中位数 **2.15x**，最差 **0.096x**，最好 59.7x；
- 中位数回撤 -70.8%，最差 -94.9%；
- 收益几乎全部来自 2024 年 11–12 月的 DOGE/XRP 行情；
- Top50 的流动性、冲击成本和容量都不如 Top20。

**结论：Top50 版本可以作为研究线索，不能当作“你的 Top20 策略”上线。**

### 3.3 纯时间序列动量（TSMOM）

基于 Han/Kang/Ryu 的论文，另外实现了并全跑 **1,440 组 TSMOM**（Top20/Top50 × 30/90/180 日回看 × 7/14/28 日调仓 × top1/top3/all × equal/inverse-vol × 8 种 overlay）：

| 宇宙 | 最佳总收益 | 最佳 Sharpe | ≥5x 候选数 |
|---|---:|---:|---:|
| Top50 灵敏度 | 4.95x | 0.90 | 0 |
| Top20 | 2.72x | 0.82 | 0 |

结论：在这批数据上，**“每币自身趋势闸门 + 广泛风险平价”远弱于“Top20 内集中选最强币”**。论文说 TSMOM 证据较强，是在不同的资产池、权重和样本定义下；本项目的真实数据在这一段没有支持纯 TSMOM 达到 20x。

### 3.4 多策略集成

对 Top50 的 5 种 CTREND 家族做 2/3/5/10 组件等权集成：

- 2 组件：13.65x，DD -49.8%；
- 3 组件：12.75x，DD -52.6%；
- 5/10 组件：更低。

集成确实降低了单币和单参数风险，但达不到 20x，所以没有取代冠军。

### 3.5 每日重检/事件驱动调仓研究（2026-09-23 新增）

问题不是“能不能每天看数据”，而是“每天看到变化后该不该交易”。当前旧策略本来就已经每日检查 BTC 风控；固定的是选币日历。为了验证每日选币是否更好，项目跑了：

- 176 组固定频率 + daily event/hysteresis 变体（最小持有、hold-rank band、score gap、确认天数）；
- 36 组“21 天选币 + 每日 rank-stop 退出”混合变体；
- 27 组“21 天选币 + 每日自身均线止损”变体（MA 20–200 日 × 1–3 日确认）。

结果：

| 方向 | 最佳固定起点 @20bps | 稳健性结论 |
|---|---:|---|
| 每日事件驱动轮动 | 76.48x（mh5/hr2/gap0.10/c1） | 参数邻域中位数仅 2.20x，邻域最差 0.11x；拒绝 |
| 21 天选币 + 每日 rank-stop | 25.33x（hr5/c3/mh10） | 2024-2026 仅 1.16x，低于旧冠军 1.63x；拒绝 |
| 21 天选币 + 每日自身 MA75 confirm3 止损 | **22.44x** | 滚动中位数 3.51x、最差 0.585x；MA 50–100 日邻域均约 21–24x；采用 |

**结论**：每日检查有价值，但价值主要在风险退出、确认和 hysteresis，而不是每天重新排序换仓。固定 21 天选币日历是换手和过拟合控制，不是拒绝每日数据的理由。自身趋势止损方向可以保留，但整体候选仍受第 0.1 节的 BTC 闸门参数脆弱性约束。

---

## 5. 数据与选币审计

### 4.1 Point-in-time Top20 独立审计

`scripts/audit_ctrend_selections.py` 不经过 processed 市值矩阵，而是直接从 `data/raw/coinmarketcap/history` 的原始 CMC payload 重建每个 21 天调仓日的 Top20，再和策略实际使用的 universe 逐日比较：

| 项目 | 结果 |
|---|---:|
| 比较调仓日 | **83** |
| Top20 集合一致 | **83 / 83** |
| Top20 顺序一致 | **83 / 83** |
| 市值数值不符 | **0** |
| 选中的币不在当日 Top20 | **0** |
| 实际有持仓的调仓日 | 42 |

完整逐日明细：
- `reports/trend_stop_champion_2022/audit/selections.csv`
- `reports/trend_stop_champion_2022/audit/universe_audit.csv`
- `reports/trend_stop_champion_2022/audit/selection_audit.md`

### 4.2 数据质量

- 数据链审计：`scripts/audit_data_chain.py`，**43 PASS / 6 WARN / 0 FAIL**（2026-09-23 时点；**已被 §00.5 的 2026-10-08 结果取代：42 PASS / 9 WARN / 0 FAIL**）；
- 被独立源拒绝的标的：CEL、HT（价格不一致），不进入排名/策略（**2026-10-08 更新：CEL 仍被拒绝；HT 的市值 feed 已结束、当前缓存无可比对区间，改为 historical-only——保留历史、市值结束后永不参与排名。见 §00.5**）；
- RAIN 被流动性门槛排除；
- 缺失行情策略为 `error`（2026-10-08 现状：`carry`，单次缺口 ≤3 天且逐条记入 `gap_carries`，更长即中止；结束的 feed 按最后价格卖出），不会把停牌/下架误当 0% 收益；
- 买入后行情终止：按最后一个有效收盘价强制退出并计成本，不继续假装能交易；
- 研究脚本使用 `persist=False` 在内存中构建面板，不会覆盖 canonical `data/processed/panel_daily.csv`；
- 每日刷新写盘前有回归闸门：如果新面板会让已有资产消失、或把面板起止日期往内/往回移动，直接报错并保留旧面板。

### 4.3 外部研究参考

已查阅并保留原始结果：

- Han, Kang, Ryu, *Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market: A Comprehensive Analysis under Realistic Assumptions*：<https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>。核心结论：考虑真实成本和日间波动后，很多横截面组合会被清算；时间序列动量证据相对更强，动量集中在大赢家；换仓日选择本身会显著影响结论。
- Yang, *Cryptocurrency market risk-managed momentum strategies*：<https://doi.org/10.1016/j.frl.2025.107879>。风险缩放把周均收益从 3.18% 提升到 3.47%，年化 Sharpe 从 1.12 提升到 1.42，且在交易成本下仍有稳健性。
- Kaya, Mostowfi, *Low-volatility strategies for highly liquid cryptocurrencies*：<https://doi.org/10.1016/j.frl.2021.102422>。低波动组合加简单止损能显著降低下行风险并改善 Sharpe。
- Kaminski, Lo, *When do stop-loss rules stop losses?*：<https://doi.org/10.1016/j.finmar.2013.07.001>。止损是否增加收益取决于采样频率和市场状态；论文支持“止损可以降低波动”，但不支持任意固定参数。
- Sadaqat, Butt, *Stop-loss rules and momentum payoffs in cryptocurrencies*：<https://doi.org/10.1016/j.jbef.2023.100833>。147 个币、2015-01 至 2022-06 的样本中，止损版动量在收益、Sharpe 和 alpha 上优于普通动量；这支持“止损方向”，不支持直接照搬某个均线周期。
- Le, Ruthbah, *Trend-following Strategies for Crypto Investors*：<https://www.monash.edu/__data/assets/pdf_file/0011/3744821/Trend-following-Strategies-for-Crypto-Investors.pdf>。测试 20/65/150/200 日均线；BTC 上 65D 较好，ETH 和大型非 BTC 指数上 20D 较好；交易成本显著侵蚀收益。
- Duarte, *Trailing Stop-Loss and Re-Entry Strategies in Europe*：<https://doi.org/10.24018/ejbmr.2022.7.3.1426>。止损后的重入规则是独立决策点；文章使用 3% 回撤止损和 3% 回升重入，结果显示重入规则有场景依赖，不能默认“一回升就买”。
- Alpha Architect, *Portfolio Rebalancing Research: Momentum and Tolerance Bands*：<https://alphaarchitect.com/destabilizing-rebalancing>。更频繁地“检查”不等于更频繁地交易；no-trade band 能减少无效换手。
- Aligrithm, *Percentile-Rank Momentum With Hysteresis*：<https://aligrithm.com/percentile-rank-momentum-with-hysteresis-low-churn-signals>。用高低阈值之间的 hysteresis band 抑制排名噪声；该文也明确指出其 crypto 回测缺少成本和基准，因此本项目只采用方法方向，不采用其收益结论。
- Vilnius University, *Momentum strategies in cryptocurrency markets* (2026)：8 个大币样本，TSMOM 风险调整后优于 XSMOM：<https://www.journals.vu.lt/BATP/en/article/view/44540>。
- Starkiller Capital, cross-sectional momentum in crypto：<https://www.starkiller.capital/post/cross-sectional-momentum-in-cryptocurrency-markets>。

外部论文只能提供方向，不能代替本项目的 point-in-time 数据和成本回测；本文所有结论以项目实跑为准。

---

## 6. 已知局限（上实盘前必须知道）

1. **起点敏感**：固定 2022-01-01 的 25.87x 不是任意起点可达；@2bps 滚动中位数 3.80x、最差 0.62x。完全错开 21 份组合也只有 5.51x。
2. **市场闸门参数尖峰**：11D/2 BTC trailing 闸门把 21 份组合从 2.37x 提到 5.51x，但 10D/14D、confirm1/5 都显著崩落；当前不能把它当成稳定规律，更不能直接上实盘。
3. **收益集中**：2024 年 +347%，2026 YTD +158%；如果未来没有类似的单币大行情，收益会显著下降。
4. **单币集中**：同一时间只持 1 个币，存在跳空、下架、流动性枯竭和单币黑天鹅风险。
5. **每日止损会误伤**：75 日均线 + 3 日确认处在 50–100D/confirm1–3 的宽平台内，但趋势震荡期仍可能卖在低点；不能用更高频的每日轮动替代确认机制。
6. **重入规则**：当前样本支持“止损后等到下一次调仓再重入”，立即重入的 21 份组合只有 1.49x；这条结论仍需独立样本验证。
7. **成本假设**：2bps 依赖你实际成交和返佣；20bps 下为 22.44x，50bps 下为 17.68x，100bps 下为 11.87x。
8. **容量**：Top20 虽比 Top50 好，但单币满仓时规模受币种深度限制；大额资金需要重新做冲击成本测试。
9. **过拟合风险**：每日事件驱动最高固定起点 76.48x 和 11D/2 BTC 闸门都已暴露为参数尖峰；新策略仍需持续做 walk-forward、参数邻域和成本压力测试。
10. **未建模**：税务、返佣到账延迟、交易所限价/滑点、借贷/资金费（当前无杠杆不适用）。

---

## 7. 复现命令

```bash
# 新冠军：21D 选币 + 每日自身75日MA confirm3止损，2/5/10/20/50/100bps
.venv/bin/python scripts/run_trend_stop_champion.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --cost-bps 2,5,10,20,50,100 \
  --output-dir reports/trend_stop_champion_2022

# 每日自身趋势止损全参数扫描（MA20-200 × confirm1-3 + fresh rolling）
.venv/bin/python scripts/run_trend_stop_validation.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --output-dir reports/trend_stop_validation_2022

# 每日事件驱动/hysteresis/rank-stop 全参数扫描
.venv/bin/python scripts/run_event_driven_validation.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --output-dir reports/event_driven_validation_2022

# 独立 CMC Top20 + 选币审计（新冠军基础选币）
.venv/bin/python scripts/audit_ctrend_selections.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --output-dir reports/trend_stop_champion_2022/audit

# 旧冠军（保留作对照）
.venv/bin/python scripts/run_ctrend_champion.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --cost-bps 2,5,10,20,50,100 \
  --output-dir reports/ctrend_champion_top20_2022

# 2218 组 Top20 全量筛选（2022 起，screen-only）
.venv/bin/python scripts/run_top20_convex_validation.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --universe-size 20 --screen-only --workers 8 \
  --output-dir reports/convex_validation_2022_top20

# 1440 组 TSMOM 对照筛
.venv/bin/python scripts/run_tsmom_validation.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --workers 8 --screen-only --output-dir reports/tsmom_validation_2022

# 相位敏感性 + 错开组合审计（判断 21D 冠军是否只是日历运气）
.venv/bin/python scripts/run_strategy_evidence_audit.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --cost-bps 2,20 --tranche-counts 1,3,7,21 \
  --output-dir reports/strategy_evidence_audit_2022

# 逐决策点消融：自身止损、BTC 闸门、重入方式（21 相位 + 错开组合）
.venv/bin/python scripts/run_decision_point_ablation.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --cost-bps 2,20 --output-dir reports/decision_point_ablation_2022

# BTC 波动率缩放 trailing 闸门验证
.venv/bin/python scripts/run_volatility_gate_validation.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --cost-bps 2,20 --output-dir reports/volatility_gate_validation_2022

# 相位不敏感 + 波动率目标仓位：主候选邻域
.venv/bin/python scripts/run_phase_invariant_vol_target.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --cycles 7,14,21,28 --target-vols 0.5,0.6,0.7,0.8 \
  --vol-windows 20,30,60 --stop-modes own75 --gate-modes btc_ma100 \
  --cost-bps 2,20 --output-dir reports/vol_target_neighborhood_2022

# 数据链审计
.venv/bin/python scripts/audit_data_chain.py --config config/base.yaml
```

---

## 8. 文件索引（权威性）

| 路径 | 内容 | 状态 |
|---|---|---|
| `RESEARCH.md` | **本文，唯一权威结论** | ✅ 权威 |
| `docs/research/literature_review_2026-09.md` | H1–H5 的预注册规则、参数来源与 kill criterion（H5 于 2026-10-08 追加） | ✅ 权威预注册 |
| `reports/phase_momentum_hypotheses_2026_10/` | H2–H5 预注册试验：判据、DSR、Reality Check、压力窗口、逐年、逐币归因 | ✅ 当前权威 |
| `reports/phase_momentum_candidate_eval_h5/` | B / H3 / H5 与两族邻域的同口径横评（含 DSR） | ✅ 当前权威 |
| `reports/phase_momentum_multiple_testing_overlays/` | 36 候选族的 CSCV/PBO（H5 = 0.192，首个通过）、DSR、Reality Check | ✅ 当前权威 |
| `reports/phase_momentum_regime_overlays/` | B / H3 / H5 的 bull 与 non-bull 拆分 | ✅ 当前权威 |
| `reports/phase_momentum_dsr_gap/` | DSR 差距定价：达到 0.95 所需的年化 Sharpe（family / top20 / all_trials） | ✅ 当前权威 |
| `reports/phase_momentum_dsr_horizon/` | DSR 的时间维度定价：保持样本内 Sharpe 需 6.4 年新数据；只用样本外的 t 检验需 1.06 年（§00.20） | ✅ 当前权威 |
| `reports/phase_momentum_crash_states/` | 崩溃月与可观测状态变量的对照（否定性结果：无变量区分度 > 0.4σ） | ✅ 当前权威 |
| `reports/phase_momentum_flow_states/` | 量能/换手/集中度状态筛查（9 个变量全部被拒）；含 §00.14 表格的全样本勘误 | ✅ 当前权威 |
| `reports/phase_momentum_hourly_states/` | 小时线日内状态筛查（已实现方差/半方差/小时成交集中度/场所占比/日内自相关/时段效应；7 个变量全部被拒） | ✅ 当前权威 |
| `reports/phase_momentum_funding_states/` | 永续资金费率状态筛查（4 个变量全部被拒；`funding_level` 崩溃月区分度 +1.12σ 为三次筛查最强，但方向与冗余度决定不可用） | ✅ 当前权威 |
| `reports/phase_momentum_chase_risk/` | 追高进场诊断：极端 21 日涨幅后策略前瞻收益衰减（21 日 +1.78% vs +7.74%，按 gross 归一 t=-2.83）；含 MAX 构造的对照 | ✅ 当前权威 |
| `reports/phase_momentum_dispersion_diagnostic/` | 离散度机制的项目内诊断（五档前瞻 + Spearman） | ✅ 筛查证据 |
| `reports/phase_momentum_dispersion_overlay/` | 离散度叠加的日频筛查（**未计**额外换手，收益偏高） | ⚠️ 仅筛查，非候选 |
| `reports/phase_momentum_live/` | 冻结规格（H5）的最新目标快照；信号工具，不下单 | ✅ 当前 |
| `reports/phase_momentum_oos_2026/` | 冻结规格自 2026-09-22 起的样本外跟踪 | ✅ 当前 |
| `reports/phase_momentum_multiple_testing_2022/` | 30 个单规格变体的 CSCV/PBO（B = 0.526） | ✅ 历史基线 |
| `reports/phase_momentum_candidate_eval/` | H3 采用时的横评快照 | ⚠️ 已被 §00.13 取代 |
| `reports/phase_momentum_multiple_testing_h3/` | H3 的 PBO（0.558，fail） | ⚠️ 历史 |
| `reports/research_trial_inventory/` | 试验台账、DSR 分母（Top20/2022 = 6,135）与 manifest | ✅ 权威计数 |
| `reports/trend_stop_champion_2022/` | 固定 21D 冠军结果、逐年、子区间、目标历史、最新信号、基础选币审计 | ⚠️ 相位敏感，只能作为上尾参考 |
| `reports/trend_stop_validation_2022/` | MA20-200 × confirm1-3 每日自身趋势止损全扫 + fresh rolling | ✅ 权威研究 |
| `reports/event_driven_validation_2022/` | 176 组每日事件/hysteresis + 36 组每日 rank-stop 混合；用于证明每日轮动未采用 | ✅ 权威研究 |
| `reports/strategy_evidence_audit_2022/` | 21D 相位扫描 + 1/3/7/21 份错开组合稳健性审计 | ✅ 权威审计 |
| `reports/decision_point_ablation_2022/` | 自身止损、BTC 闸门、重入方式的 21 相位/错开组合消融 | ✅ 权威审计，否定 11D/2 为稳定规律 |
| `reports/volatility_gate_validation_2022/` | BTC 波动率缩放 trailing 闸门参数邻域验证 | ✅ 方向合理，但当前不足以替代 |
| `reports/phase_invariant_vol_target_gates_2022/` | 相位不敏感 + 波动率目标 + BTC MA 闸门对照 | ✅ 新领先候选研究 |
| `reports/vol_target_neighborhood_2022/` | 7/14/21/28D × 目标波动 × 波动窗口参数平台 | ✅ 当前最完整稳健性证据 |
| `reports/vol_target_frontier_2022/` | 目标波动 80%–200% 收益/回撤边界 | ✅ 边界研究 |
| `reports/vol_target_cost_rolling_2022/` | 领先候选 2–100bps 成本压力 + 1 年滚动窗口 | ✅ 当前最关键稳健性报告 |
| `docs/research/strategy_evidence_audit.md` | 逐决策点外部证据矩阵和未验证假设 | ✅ 权威审计 |
| `docs/superpowers/specs/2026-10-09-bitget-derivatives-track-design.md` | Bitget 衍生品独立轨道设计稿（long/short、杠杆、保证金、funding、强平、预注册 trials） | ⚠️ 设计稿，待负责人审阅 |
| `docs/research/derivatives_track_research_2026-10.md` | 衍生品外部研究、项目内诊断、Bitget API 事实和 Phase 1 数据审计 | ⚠️ 研究输入，不构成上线批准 |
| `reports/derivatives_track_data_audit/` | Phase 1 合约映射、K 线抽样覆盖和 funding 重叠审计 | ⚠️ funding 代理未通过预注册门槛 |
| `reports/derivatives_track_engine_validation/` | Phase 2 isolated-margin 1.0x 对 H5 的代理 mark 校验 | ⚠️ 代理诊断，非 Bitget 结果 |
| `reports/derivatives_track_margin_calibration/` | 8 个预注册保证金 buffer 校准 trial | ⚠️ 代理诊断；50% buffer 当前最小零强平点 |
| `reports/derivatives_track_proxy_trials*/` | V2 long-only 代理试验与成本压力 | ⚠️ 代理诊断，待 Bitget mark 重跑 |
| `reports/ctrend_champion_top20_2022/` | 旧冠军（固定21D，无每日自身趋势止损） | ⚠️ 已被新冠军取代 |
| `reports/convex_validation_2022_top20/` | 2218 组 Top20 2022 起点全量筛选 | ✅ 权威研究 |
| `reports/convex_validation_2022_top50/` | Top50 灵敏度全量筛选 | ⚠️ 只做灵敏度，不是生产规则 |
| `reports/tsmom_validation_2022/` | 1440 组纯 TSMOM 对照 | ✅ 对照结论 |
| `reports/no_leverage_ablation_2022/` | 400 组跨家族无杠杆消融 | ✅ 保守基准 |
| `reports/convex_overlay_sweep_2022_top20/` | 1584 组 BTC 风控/停车资产参数扫描 | ✅ 冠军选择依据 |
| `reports/ctrend_focus_2022_top50/`、`reports/ctrend_focus_2022_top20/` | Top50/Top20 小范围 overlay 聚焦 | ⚠️ 已被更完整的 overlay sweep 取代 |
| `reports/bull_offense_finalist*` | 旧冠军 bull-offense | ❌ 已被本文取代 |
| `reports/top20_convex_validation/` | 旧面板 2218 筛选 | ❌ 旧面板，仅历史参考 |
| `reports/latest/` | 主流水线 32 个策略（含 BTC/ETH 基准） | ✅ 仍可用于基准对比 |

**数据更新方案**：`ops/com.atlas20.daily-refresh.plist` 已安装到用户 `launchd`，每日 02:30/06:30 UTC 执行；CoinGecko 独立校验缓存有 3 小时 TTL，避免 Gate 不上市资产长期使用旧缓存后被错误排除。

---

## 9. Derivatives Track（独立研究轨道）

> 本节不修改 H5 Spot Track 的任何结论，也不构成衍生品上线批准。它只记录 Bitget USDT-M 独立轨道的研究、设计和 Phase 1 数据审计状态。

### 9.1 文档与数据

- 设计稿：`docs/superpowers/specs/2026-10-09-bitget-derivatives-track-design.md`
- 外部研究：`docs/research/derivatives_track_research_2026-10.md`
- Phase 1 审计报告：`reports/derivatives_track_data_audit/report.md`
- 下载器：`scripts/download_bitget_derivatives_data.py`
- 并行下载分片合并器：`scripts/merge_bitget_derivatives_shards.py`
- 审计器：`scripts/audit_bitget_derivatives_data.py`
- 客户端与映射：`src/atlas20/derivatives/`

### 9.2 2026-10-09 Phase 1 结论

- PIT Top20 历史池 102 个 coin id，其中 **88 个映射到 Bitget USDT-M**，14 个缺失：EOS、FLOW、FTT、HNT、HTX、HT、KCS、LEO、MKR、MNT、OKB、OSMO、WAVES、YFI。
- Bitget 历史 funding 主端点是 `/api/v2/mix/market/history-fund-rate`，`pageNo` 有效，覆盖最近约 90 天；v3 端点忽略 `pageNo`，每次只返回最近 20 条。
- BTC/NEAR/SOL 的 Bitget vs Binance funding 重叠验证均**未通过**设计稿 §5.2.1 的预注册门槛：符号一致率 0.694–0.853，Pearson 0.250–0.505；中位误差 0.050–0.378 bps、95 分位 0.947–1.421 bps。
- Binance funding 只能作为 **proxy/uncertain 压力带**，不能称为 Bitget 精确历史；在找到更好的 Bitget 历史 funding 来源前，依赖精确 funding 的 2022–2026 衍生品回测不能作为上线依据。
- Bitget 历史 mark K 线 API 可用，但单次 `limit<=100`、窗口<=90 天，且返回 `endTime` 之前最近 100 条；下载器必须从 `endTime` 向前分页。BTC/NEAR/SOL 的抽样 mark 覆盖为 6/6 窗口完整，但全量 88 合约 × 3 类型下载尚未完成。

### 9.3 当前判定

- **H5 Spot Track 不变，仍为 provisional；DSR/PBO/窄峰门槛不因衍生品轨道放宽。**
- **Derivatives Track 仍为 provisional，Phase 1 数据质量门未全通过。**
- 在 full candle coverage、historical funding 数据源、isolated margin/强平引擎、multiple-testing 和 12 个月 OOS 全部通过前，不启用杠杆、不做空、不接实盘。

### 9.4 2026-10-09 Phase 2：isolated-margin 引擎与 1.0x 校验（**重大设计修正**）

> **口径修正（同日）**：初版 Phase 2 直接对 mark/funding 全量时间轴做回测，结果被两类污染放大：一是 2022 前的预热/零收益；二是数据源在 2026-09-21 之后的最新批次。前者会人为压低 Sharpe/CAGR，后者会把主样本之后的价格路径计入结果。引擎现已支持左闭右开的 `start_time`/`end_time` 评估窗口，所有下表结果均为 **2022-01-01 00:00 至 2026-09-21 23:00 UTC**；旧数字全部废止。

- 已实现独立衍生品引擎 `src/atlas20/derivatives/engine.py`：小时 mark OHLC、T+1 +3h 执行、逐结算点 funding、isolated margin、小时级强平、差分调仓（不再每次全平全开）、手续费/滑点分开记录；缺失 mark 默认 fail closed，诊断模式可显式 `exit_last`/`carry`。传入每币 `funding_intervals_hours` 后，持仓若超过合约 funding 间隔仍没有结算记录会直接报错，不再把缺失 funding 静默当作 0。
- 已实现保证金/强平数学 `src/atlas20/derivatives/margin.py`、信号构造 `src/atlas20/derivatives/signals.py`、Bitget/Binance 数据加载 `src/atlas20/derivatives/data.py`，以及 Phase 2 验证/校准/代理试验脚本。
- 先用 Binance/Gate 1h K 线作为 **mark 代理** 做 1.0x 对 H5 的引擎校验；这不是 Bitget 结果，不能作为上线依据。比较基准必须是 **H5 同成本的 +3h 成交**，不能拿 close-fill 的 21.47x 与 +3h 衍生品路径对比。
- 2022-01-01 至 2026-09-21、20 bps、+3h、代理 mark 的结果：
  - H5 全池现货：19.5253x，Sharpe 1.6231，MDD -36.97%；
  - 同一 H5 选币但仅保留代理中有小时 mark 的资产：15.2974x，Sharpe 1.6258，MDD -26.29%；
  - 30% long buffer + isolated margin 的 1.0x 衍生品：15.4917x，Sharpe 1.6312，MDD -26.20%，**4 次强平**；
  - 50% long buffer（V2）的 1.0x 衍生品：15.3380x，Sharpe 1.6267，MDD -26.20%，**0 次强平**。
- 强平事件仍出现在 2022-11-08 DOGE、2023-08-17 SHIB、2024-03-05 SHIB、2024-04-25 HEDERA 等历史回撤段，说明原设计 `long_margin_ratio = 0.30 + MMR + 0.005` 在 H5 这种 1–2 币集中持仓上**不能通过“1.0x 不得强平”的门槛**；这不是参数小修，而是原规则被 Phase 2 校验否决。
- 30% buffer 的原始 11 个衍生品 trial 因此不能直接进入最终验收；已追加 8 个 margin calibration trials，并把 V2 规则单独记录为 Phase 2 diagnostic。所有结果仍需在 Bitget mark 数据上重跑。

### 9.5 2026-10-09 保证金校准：50% long buffer 是当前最小可行点

预注册的 calibration grid 为 long buffer 0.40/0.50/0.60/0.75 × leverage 1.0x/1.25x，固定 fee_buffer 0.005、MMR 0.01、最大保证金占用 85%、20 bps、+3h、零 funding，使用代理 mark：

| 规则 | leverage | 实际最大 gross | 强平次数 | 终值 | Sharpe | MDD |
|---|---:|---:|---:|---:|---:|---:|
| MB40 | 1.00x | 1.002x | 1 | 15.062x | 1.617 | -26.20% |
| MB50 | 1.00x | 1.002x | **0** | 15.338x | 1.627 | -26.20% |
| MB60 | 1.00x | 1.002x | **0** | 15.338x | 1.627 | -26.20% |
| MB75 | 1.00x | 1.002x | **0** | 15.338x | 1.627 | -26.20% |
| MB40 | 1.25x | 1.281x | 1 | 26.171x | 1.616 | -32.10% |
| MB50 | 1.25x | 1.281x | **0** | 26.782x | 1.626 | -32.10% |
| MB60 | 1.25x | 1.281x | **0** | 26.782x | 1.626 | -32.10% |
| MB75 | 1.25x | 1.124x | **0** | 26.582x | 1.636 | -30.80% |

- 40% buffer 仍各有 1 次强平；50% buffer 是两个 leverage 档位下最小的零强平点。
- 75% buffer 在 1.25x 下因为 85% 最大保证金占用而把实际 gross 压到 1.124x，收益略低、MDD 略好；当前不优先。
- 因此，**Provisional V2 默认改为 long buffer 50%**；short buffer 仍保持 50% 或更高，具体由后续空头试验决定。
- V2 long-only 代理诊断（50% buffer、零 funding、20 bps、+3h）：

  | trial | leverage | 实际最大 gross | 强平 | 终值 | Sharpe | MDD |
  |---|---:|---:|---:|---:|---:|---:|
  | L125-V2 | 1.25x | 1.281x | 0 | 26.782x | 1.626 | -32.10% |
  | L150-V2 | 1.50x | 1.574x | 0 | 44.674x | 1.625 | -37.70% |
  | L200-V2 | 2.00x | 1.758x | 0 | 105.010x | 1.634 | -45.03% |

- L125-V2 的成本压力（代理 mark、零 funding、+3h）与 **H5 同成本 +3h 基准**比较：

  | 成本 | 衍生品终值 | 衍生品 Sharpe | 衍生品 MDD | H5 +3h 终值 | H5 Sharpe | H5 MDD | 终值比 | Sharpe 比 |
  |---:|---:|---:|---:|---:|---:|---:|---:|---:|
  | 6 bps | 31.395x | 1.693 | -29.99% | 23.016x | 1.700 | -35.22% | 1.364 | 0.996 |
  | 8 bps | 30.691x | 1.684 | -30.29% | 22.482x | 1.689 | -35.47% | 1.365 | 0.997 |
  | 11 bps | 29.663x | 1.669 | -30.75% | 21.703x | 1.673 | -35.85% | 1.367 | 0.998 |
  | 20 bps | 26.782x | 1.626 | -32.10% | 19.525x | 1.623 | -36.97% | 1.372 | 1.002 |
  | 50 bps | 19.039x | 1.482 | -36.42% | 13.721x | 1.457 | -40.56% | 1.388 | 1.017 |
  | 100 bps | 10.760x | 1.240 | -43.53% | 7.614x | 1.178 | -46.24% | 1.413 | 1.052 |

- 在代理 mark、零 funding、+3h 的诊断下，L125-V2 全部成本无强平、MDD < 50%、终值 >= 1.36 × H5、Sharpe 与 H5 基本持平或更高；这比旧口径看起来更强，但仍是 **proxy diagnostic**，不能用于上线。
- 这些数字只证明保证金规则修正和窗口修正方向；**Bitget mark、真实 funding、Bitget 合约可用性、完整 multiple-testing、12 个月 OOS 全部未完成**，不能作为上线或最终收益结论。

### 9.6 2026-10-09 空头 overlay 代理诊断：仍被拒，但拒绝理由修正

在 V2 50% long buffer 之上，使用代理 mark 和 **未通过 Phase 1 重叠门槛的 Binance funding proxy** 跑 4 个空头 overlay（20 bps、+3h、已修正窗口）：

| trial | 终值 | Sharpe | MDD | 强平 | 相对 L125-V2 |
|---|---:|---:|---:|---:|---|
| SBTC25 | 26.793x | 1.624 | -32.10% | 0 | 收益基本持平；Sharpe 略低；MDD 不改善 |
| SBTC50 | 28.626x | 1.638 | -32.10% | 0 | 收益略高；Sharpe 略高；MDD 不改善 |
| SWEAK25 | 27.225x | 1.623 | -32.10% | 0 | 收益略高；Sharpe 略低；MDD 不改善 |
| SWEAK50 | 29.778x | 1.629 | -32.94% | 0 | 收益略高；Sharpe 略高；MDD 反而变差 |

- L125-V2 基准：26.782x，Sharpe 1.626，MDD -32.10%，0 次强平。
- 修正窗口后，空头 overlay 并没有“Sharpe 大幅下降”；真正的未通过点是 **MDD 完全没有改善**，SWEAK50 还略差。预注册 kill criterion 要求 MDD 至少改善 5 个百分点且 Sharpe 不低于 long-only 基准，因此 4 个空头仍全部被拒。
- 该结论是代理诊断，且 funding 代理本身未通过 Phase 1 重叠门槛；即使未来 Bitget 精确 funding 改变结果，也必须重新预注册并重新跑完整门槛，不能把本次结论当作最终上线依据。

### 9.7 2026-10-09 multiple-testing 代理诊断（仍需补全正式 scope）

- `reports/derivatives_track_proxy_multiple_testing/` 已加入长期收益矩阵、DSR、White Reality Check 和 PBO/CSCV；输入是当前已跑出的 7 个 20 bps、+3h 代理候选（3 个 long-only leverage + 4 个 short overlay），日期严格为 2022-01-01 至 2026-09-21。
- 结果：Deflated Sharpe（N=11 的预注册 scope 记账，7 个可用候选的波动率）约 0.99997；White Reality Check p≈0.00699；**PBO/CSCV≈0.960**，最常被选中为 SWEAK50（309/924）。
- 这 **不能** 宣布 multiple-testing 通过：design 稿要求候选矩阵覆盖 11 个 trial，目前 stop20 变体仍未实现/未跑，成本档位也不是独立策略候选；7 个高度相关的 long/short 变体给出的 PBO≈0.96 是明确的选参不稳定警告。DSR 的高值不能覆盖 PBO 失败。
- 该报告仍标注为 **proxy diagnostic**；正式 gate 必须在 Bitget mark、真实 funding、完整候选矩阵和 12 个月 OOS 上重跑。固定规格与试验计数不变。
