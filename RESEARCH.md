# Atlas20 策略研究记录（唯一权威版本）

> 本文取代此前所有口头结论、临时 `/tmp` 结果、旧报告和 README 里过时的策略叙述。
> 与本文冲突的旧数字一律作废。
>
> | | |
> |---|---|
> | 最后更新 | 2026-09-23 |
> | 数据 | `data/processed/panel_daily.csv`，101 个币，2020-10-03 → **2026-09-21** |
> | 数据口径 | 市值与排名来自 CoinMarketCap；Gate/Binance 只做独立校验 |
> | 杠杆 | **全部无杠杆**，gross exposure 硬上限 1.0，不做空 |
> | 执行 | 信号收盘生成，**T+1** 执行；缺失行情不会静默填 0 |
> | 主回测起点 | **2022-01-01**，剔除 2021 泡沫行情 |

---

## 0. 一句话结论

在 **真实 point-in-time Top20 + 无杠杆 + 现货** 约束下，当前最强可复现策略是：

**CTREND-breakout 单币集中轮动 + 每日自身趋势止损**
= 历史 Top20 内排除 BTC → 21 天调仓选 CTREND-breakout 第 1 名 → 每日检查持仓是否连续 3 个交易日收盘低于自身 75 日均线 → 若是则转现金，下一次 21 天调仓才允许重入 → BTC 跌破 11 日前收盘连续 2 天则全部转现金。

| 2022-01-01 → 2026-09-21 | 新策略 @2bps | 新策略 @10bps | 新策略 @20bps | BTC |
|---|---:|---:|---:|---:|
| 总收益 | **25.87x** | **24.28x** | **22.44x** | 1.82x |
| CAGR | 99.1% | 96.5% | 93.2% | 13.5% |
| Sharpe | 1.360 | 1.339 | 1.313 | 0.502 |
| 最大回撤 | -41.8% | -42.6% | -44.0% | -67.0% |
| 年换手 | 16.7x | 16.7x | 16.7x | ~0.2x |

**为什么不是每天重新选币**：每天检查数据是对的，但“每天重新选第一名”会显著放大噪声和换手。项目实测了 176 组每日事件驱动/ hysteresis 变体：固定起点最高的一组在 20bps 下到 **76.48x**，但参数邻域中位数只有 **2.20x**、邻域最差 **0.11x**，属于明显的参数尖峰，拒绝采用。把每日检查用于“持仓自身趋势退出”，而不是每日轮动，才得到稳健改善。

**结论不是“可以稳定每年翻倍”**：25.87x 仍是 2022-01-01 固定起点的结果。45 个月度起点滚动回测中，@2bps 中位数 **3.80x**、最差 **0.62x**；@20bps 中位数 **3.51x**、最差 **0.585x**。策略比旧冠军更稳，但起点敏感性和单币集中风险仍然存在。

---

## 1. 定义（完全可复现）

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

## 2. 权威结果

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

## 3. 候选对比与为什么没有选更高倍数

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

**结论**：每日检查有价值，但价值主要在风险退出、确认和 hysteresis，而不是每天重新排序换仓。固定 21 天选币日历是换手和过拟合控制，不是拒绝每日数据的理由。

---

## 4. 数据与选币审计

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

- 数据链审计：`scripts/audit_data_chain.py`，**43 PASS / 6 WARN / 0 FAIL**；
- 被独立源拒绝的标的：CEL、HT（价格不一致），不进入排名/策略；
- RAIN 被流动性门槛排除；
- 缺失行情策略为 `error`，不会把停牌/下架误当 0% 收益；
- 买入后行情终止：按最后一个有效收盘价强制退出并计成本，不继续假装能交易；
- 研究脚本使用 `persist=False` 在内存中构建面板，不会覆盖 canonical `data/processed/panel_daily.csv`；
- 每日刷新写盘前有回归闸门：如果新面板会让已有资产消失、或把面板起止日期往内/往回移动，直接报错并保留旧面板。

### 4.3 外部研究参考

已查阅并保留原始结果：

- Han, Kang, Ryu, *Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market: A Comprehensive Analysis under Realistic Assumptions*：<https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>。核心结论：考虑真实成本和日间波动后，很多横截面组合会被清算；时间序列动量证据相对更强，动量集中在大赢家；换仓日选择本身会显著影响结论。
- Yang, *Cryptocurrency market risk-managed momentum strategies*：<https://doi.org/10.1016/j.frl.2025.107879>。风险缩放把周均收益从 3.18% 提升到 3.47%，年化 Sharpe 从 1.12 提升到 1.42，且在交易成本下仍有稳健性。
- Kaya, Mostowfi, *Low-volatility strategies for highly liquid cryptocurrencies*：<https://doi.org/10.1016/j.frl.2021.102422>。低波动组合加简单止损能显著降低下行风险并改善 Sharpe。
- Alpha Architect, *Portfolio Rebalancing Research: Momentum and Tolerance Bands*：<https://alphaarchitect.com/destabilizing-rebalancing>。更频繁地“检查”不等于更频繁地交易；no-trade band 能减少无效换手。
- Aligrithm, *Percentile-Rank Momentum With Hysteresis*：<https://aligrithm.com/percentile-rank-momentum-with-hysteresis-low-churn-signals>。用高低阈值之间的 hysteresis band 抑制排名噪声；该文也明确指出其 crypto 回测缺少成本和基准，因此本项目只采用方法方向，不采用其收益结论。
- Vilnius University, *Momentum strategies in cryptocurrency markets* (2026)：8 个大币样本，TSMOM 风险调整后优于 XSMOM：<https://www.journals.vu.lt/BATP/en/article/view/44540>。
- Starkiller Capital, cross-sectional momentum in crypto：<https://www.starkiller.capital/post/cross-sectional-momentum-in-cryptocurrency-markets>。

外部论文只能提供方向，不能代替本项目的 point-in-time 数据和成本回测；本文所有结论以项目实跑为准。

---

## 5. 已知局限（上实盘前必须知道）

1. **起点敏感**：固定 2022-01-01 的 25.87x 不是任意起点可达；@2bps 滚动中位数 3.80x、最差 0.62x。
2. **收益集中**：2024 年 +347%，2026 YTD +158%；如果未来没有类似的单币大行情，收益会显著下降。
3. **单币集中**：同一时间只持 1 个币，存在跳空、下架、流动性枯竭和单币黑天鹅风险。
4. **每日止损会误伤**：75 日均线 + 3 日确认降低了回撤，但趋势震荡期仍可能卖在低点；不能用更高频的每日轮动替代确认机制。
5. **成本假设**：2bps 依赖你实际成交和返佣；20bps 下为 22.44x，50bps 下为 17.68x，100bps 下为 11.87x。
6. **容量**：Top20 虽比 Top50 好，但单币满仓时规模受币种深度限制；大额资金需要重新做冲击成本测试。
7. **过拟合风险**：每日事件驱动最高固定起点 76.48x 已被邻域测试拒绝；新策略仍需持续做 walk-forward、参数邻域和成本压力测试。
8. **未建模**：税务、返佣到账延迟、交易所限价/滑点、借贷/资金费（当前无杠杆不适用）。

---

## 6. 复现命令

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

# 数据链审计
.venv/bin/python scripts/audit_data_chain.py --config config/base.yaml
```

---

## 7. 文件索引（权威性）

| 路径 | 内容 | 状态 |
|---|---|---|
| `RESEARCH.md` | **本文，唯一权威结论** | ✅ 权威 |
| `reports/trend_stop_champion_2022/` | **新冠军** 2/5/10/20/50/100bps、逐年、子区间、目标历史、最新信号、基础选币审计 | ✅ 权威 |
| `reports/trend_stop_validation_2022/` | MA20-200 × confirm1-3 每日自身趋势止损全扫 + fresh rolling | ✅ 权威研究 |
| `reports/event_driven_validation_2022/` | 176 组每日事件/hysteresis + 36 组每日 rank-stop 混合；用于证明每日轮动未采用 | ✅ 权威研究 |
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
