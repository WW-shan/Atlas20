# Atlas20 策略决策点证据审计

> 目的：逐项回答“这个参数为什么这样设”，区分外部论文支持、项目内回测支持、以及只是继承旧策略的未验证假设。
>
> 本文不把回测最优参数自动当成规律。外部证据只用于确定方向，最终仍以 point-in-time 数据和本项目成本回测为准。

## 1. 审计结论

当前固定 21 天冠军不能继续被描述为“稳健最优”。最重要的发现是：

- 只把 21D 调仓日历整体平移 0–20 天，其他规则完全不变；
- 2022-01-01 这一相位在 20bps 下得到 **22.44x**；
- 21 个相位的中位数只有 **3.94x**，最差 **0.61x**；
- 因此 22.44x 主要是日历相位运气，不是稳定的 21D 优势。

把资金平均拆成 21 个错开的 21D 子组合后，结果与起算日完全无关：

| 方案 | @2bps | @20bps | Sharpe @20bps | 最大回撤 @20bps |
|---|---:|---:|---:|---:|
| 当前单相位 21D | 25.87x | 22.44x | 1.313 | -44.0% |
| 21 相位中位数 | 4.60x | 3.94x | 0.782 | -57.7% |
| 3 份错开 | 6.71x | 5.79x | 1.022 | -45.4% |
| 7 份错开 | 5.84x | 5.06x | 1.053 | -34.3% |
| **21 份完全错开** | **6.37x** | **5.51x** | **1.111** | **-34.6%** |

**结论**：5.51x 才是当前规则下更诚实的相位不敏感基准；22.44x 是单一相位的上尾。无杠杆条件下，当前证据不支持“稳定做到 20x”。

### 1.1 决策点消融：5.51x 本身也不是稳定结果

把自身止损、BTC 闸门和重入方式拆开后，20bps 的 21 份完全错开组合为：

| 变体 | 总收益 | Sharpe | 最大回撤 |
|---|---:|---:|---:|
| 当前：75D/3 自身止损 + 11D/2 BTC 闸门 | 5.51x | 1.11 | -34.6% |
| 仅 BTC 11D/2 闸门，无自身止损 | 5.17x | 1.07 | -35.6% |
| 无自身止损、无 BTC 闸门 | 2.42x | 0.62 | -67.5% |
| 仅自身 75D/3 止损，无 BTC 闸门 | 2.37x | 0.60 | -58.0% |
| 自身止损 + BTC 闸门都立即重入 | 1.49x | 0.42 | -60.0% |

11D/2 BTC 闸门是当前最大的过拟合嫌疑：

| trailing lookback（confirm2） | 10D | 11D | 14D | 20D | 30D | 50D |
|---|---:|---:|---:|---:|---:|---:|
| 21 份组合 @20bps | 3.05x | **5.51x** | 1.98x | 2.92x | 4.47x | 4.09x |

| 11D 闸门 confirm | 1 日 | 2 日 | 3 日 | 5 日 |
|---|---:|---:|---:|---:|
| 21 份组合 @20bps | 2.20x | **5.51x** | 5.02x | 2.30x |

因此：

- **11D/2 不能被描述为已验证规律**；它更像样本内局部尖峰。
- **75D/3 自身止损处在 50–100D、confirm1–3 的宽平台内**，方向可保留，但不是唯一正确参数。
- **等待下一次调仓再重入优于立即重入**：立即重入增加了换手和 whipsaw，组合收益从 5.51x 降到 1.49x。
- 当前没有可直接上实盘的冠军；下一阶段必须先替换或独立验证 BTC 闸门。

复现实验：`reports/decision_point_ablation_2022/`。

### 1.2 波动率缩放闸门：没有解决“稳定高收益”问题

按 Moreira/Muir 和 Yang 的波动率管理方向，测试 BTC 波动率缩放的 trailing 闸门：

| 参数 | 21 份错开组合 @20bps | 相位中位数 | 最差相位 | Sharpe | 最大回撤 |
|---|---:|---:|---:|---:|---:|
| 30D / vol30 / 1.5σ / confirm2 | 3.22x | 1.89x | 0.20x | 0.70 | -56.0% |
| 50D / vol30 / 1.5σ / confirm2 | 3.08x | 1.68x | 0.16x | 0.69 | -56.9% |

这个方向比 11D/2 的邻域更连续，但绝对收益和相位稳定性仍不足，不能把策略恢复到“稳定 20x”。很多更宽的波动率倍数几乎不触发退出，退化回无闸门版本。当前不替换冠军规则。

复现实验：`reports/volatility_gate_validation_2022/`。

### 1.3 相位不敏感波动率目标：目前最稳的领先候选，但因子族敏感

新的候选把固定 21D 和 11D/2 闸门替换为：

- 14D balanced top1，排除 BTC；
- 75D/3 自身止损，下一次调仓重入；
- BTC 100D MA，confirm2；
- 60D 已实现波动率缩放仓位，目标波动 50%–80%，最大 gross exposure = 1.0。

> 2026-09-23 修正：早期快速模拟器会在非调仓日无成本地把权重重置回目标值，和生产引擎不一致。现已改为持仓权重随价格漂移，并与生产引擎对拍；本节全部数字为重跑结果。

20bps 相位不敏感结果：

| 目标波动 | 全样本总收益 | Sharpe | 最大回撤 | 2025–2026 测试段 | 测试 Sharpe | 测试最大回撤 |
|---|---:|---:|---:|---:|---:|---:|
| 50% | 4.14x | 1.091 | -33.5% | 1.65x | 1.121 | -16.1% |
| 60% | 4.75x | 1.070 | -38.1% | 1.75x | 1.117 | -18.2% |
| 70% | 5.21x | 1.049 | -42.1% | 1.82x | 1.107 | -20.8% |
| 80% | 5.22x | 1.006 | -45.4% | 1.85x | 1.074 | -23.3% |

成本和滚动窗口：以 14D、目标波动 50%、60D 波动窗口、own75、BTC MA100 为例：

| 成本 | 全样本 | Sharpe | 最大回撤 | 2025–2026 | 1 年滚动最差 |
|---|---:|---:|---:|---:|---:|
| 2bps | 4.69x | 1.174 | -32.7% | 1.72x | 0.821x |
| 20bps | 4.14x | 1.091 | -33.5% | 1.65x | 0.812x |
| 100bps | 2.37x | 0.724 | -38.1% | 1.37x | 0.765x |

选币分数族邻域（14D、60D 波动率目标、own75、BTC MA100、20bps）：

| 分数族 | 50% 总收益 | 50% Sharpe | 50% 最大回撤 | 60% 总收益 | 60% Sharpe | 60% 最大回撤 |
|---|---:|---:|---:|---:|---:|---:|
| balanced | **4.14x** | 1.091 | -33.5% | **4.75x** | 1.070 | -38.1% |
| relative_strength | 3.92x | **1.091** | **-30.1%** | 4.54x | **1.070** | **-34.9%** |
| breakout | 3.67x | 1.028 | -34.3% | 4.12x | 1.010 | -39.0% |
| acceleration | 3.20x | 0.949 | -35.3% | 3.44x | 0.921 | -40.2% |
| vol_adjusted | 1.92x | 0.632 | -31.2% | 1.86x | 0.597 | -33.3% |

这个候选在 2023 年明显跑输 BTC，但在 2022、2025、2026 胜出；它不是无风险策略。`balanced`、`relative_strength`、`breakout` 同一量级，但 `acceleration` 和 `vol_adjusted` 明显更差，所以当前收益不能归因于一个已经验证的选币因子。

当前状态：单个参数版本；固定等权集成和 walk-forward 结果见 1.4。仍缺多重检验和独立样本验证。

复现实验：

- `reports/phase_invariant_vol_target_gates_2022/`
- `reports/vol_target_neighborhood_2022/`
- `reports/vol_target_frontier_2022/`
- `reports/vol_target_cost_rolling_2022/`
- `reports/vol_target_score_family_*_2022/`

### 1.4 Walk-forward 和参数集成

为避免把 2022–2026 全样本挑出的参数当作样本外结果，新增：

- 365 天训练窗口、90 天测试窗口、每 90 天重新选参数；
- 只在过去数据上选择 7D/14D × 50%–80% 的 8 个版本；
- 20bps，策略切换额外计 40bps；
- 样本外从 2023-01-01 开始。

| 2023-01-01 → 2026-09-21 | 总收益 | Sharpe | 最大回撤 |
|---|---:|---:|---:|
| trailing Sharpe 动态选参数 | 4.12x | 1.166 | -37.0% |
| trailing 收益动态选参数 | 5.43x | 1.159 | -48.5% |
| 8 个参数版本固定等权集成 | **6.17x** | **1.287** | **-42.0%** |
| BTC 买入持有 | 5.23x | 1.183 | -53.1% |

固定等权集成的成本压力（全样本 / 2023 起样本外）：

| 成本 | 全样本 | 样本外 |
|---|---:|---:|
| 2bps | 6.22x | 7.54x |
| 20bps | 5.05x | 6.17x |
| 100bps | 2.00x | 2.52x |

结论：动态挑参数没有稳定超额；固定等权集成更简单，并且在样本外收益、Sharpe、最大回撤三项都优于 BTC。但 20bps 下 1 年滚动最差窗口仍是 0.72x，且集成的只是参数，不是底层单币风险。

复现实验：`reports/vol_target_walk_forward_2022/`、`reports/vol_target_walk_forward_multiple_2022/`、`reports/vol_target_ensemble_2022/`。

## 2. 决策点逐项审计

| 决策点 | 当前做法 | 来源 | 外部证据 | 项目内结果 | 判定 |
|---|---|---|---|---|---|
| 股票池 | 历史 point-in-time Top20 | 初始策略/旧项目 | 大市值加密资产确实有较强动量；幸存者偏差和退市偏差会严重高估等权组合收益 | 已从 CMC 原始 payload 重建 Top20 并审计 | **方向支持，必须继续保持 point-in-time** |
| 排除 BTC | Top20 内排除 BTC 选币 | 初始策略 | 没有论文支持必须排除 BTC | 样本内排除 BTC 明显提高收益 | **项目内经验，不是外部规律** |
| 选币因子 | CTREND-lite balanced 综合分 | 项目自建 | 加密横截面动量在真实成本下证据弱；时间序列动量证据更强 | 5 个分数族同口径测试：balanced/relative/breakout 为 3.67x–4.14x，acceleration/vol_adjusted 降至 1.92x–3.20x | **可作为候选，不能称为已验证因子** |
| 调仓周期 | 固定 21D | 初始策略 | 论文最优持有期不统一；有 5D、周频、月频；换仓日/星期几本身会显著影响结果 | 21D 相位扫描：中位 3.94x，最差 0.61x，最好 22.44x | **被推翻为“稳定最优”；必须做相位不变或事件驱动** |
| 持仓数量 | 单版本只持有第 1 名；8 版本集成最多分散到 8 个币 | 初始策略 + 参数集成 | Man Group 研究显示风险调整后峰值约 10–15 个币；单个币可以毁掉动量组合 | 单版本 Top1 仍是高波动；8 版本集成在 2023 起样本外收益、Sharpe、回撤三项优于 BTC | **单版本是高风险赌注；集成只分散参数/相位，不是充分分散化** |
| 入场过滤 | 只有自身趋势向上才买 | 项目新增 | 时间序列/绝对趋势过滤有较强证据 | 能降低部分回撤，但和 21D 相位交互很大 | **方向支持，具体 MA 周期未验证** |
| 止损 | 75D MA + 连续 3 日确认 | 项目调参 | 加密止损有正面证据；但论文没有规定 75D/3 日 | 21 份错开组合中，50–100D、confirm1–3 是宽平台，约 4.9–5.7x；75D/3 不是唯一最优 | **止损方向支持；75D/3 是可接受但非唯一参数** |
| BTC 风控 | 11 日前收盘 + 2 日确认 | 初始策略 | 未找到直接支持 11D/2 的论文；常见做法是 20/65/150/200D MA 或波动率缩放 | 11D/2 组合 5.51x，但 10D/14D、confirm1/5 明显崩落 | **已推翻为稳定规律；高过拟合嫌疑，禁止直接上线** |
| 风险资产 | 转现金 | 初始策略 | 加密压力期下行相关性极高，现金有合理性 | 现金比 BTC 停车在样本内更稳 | **方向支持，具体触发未验证** |
| 再入场 | 等下一次 21D 调仓 | 项目设计 | 有研究使用“回升阈值后重新买入”，结果混合 | 立即重入的 21 份组合只有 1.49x，低于下一次调仓的 5.51x | **项目内实证支持“下一次调仓重入”** |
| 成本 | 2/20bps 压力测试 | 项目设计 | 交易成本会显著侵蚀动量收益 | 已覆盖到 100bps | **正确，但不能替代实盘成交验证** |
| 执行 | 收盘信号，T+1 | 项目设计 | 防未来函数的标准要求 | 引擎已显式建模 | **工程正确，不是 alpha 来源** |

## 3. 外部证据摘要

### 3.1 动量与调仓频率

- Han, Kang, Ryu, *Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market*：
  - 计入交易成本和持仓期间价格波动后，很多横截面组合会被清算；
  - 时间序列动量证据强于横截面动量；
  - 最优组合之一是 28 日回看、5 日持有；
  - 换仓日选择会显著改变结论。
  - <https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>
- Gbadebo, *Momentum Trading in Cryptocurrencies: A Comparative Study of Time-Series and Cross-Sectional Strategies*：
  - 时间序列动量在风险调整后优于横截面动量；
  - 横截面版本最大回撤约 55%，且加密资产高相关削弱分散化。
  - <https://www.journals.vu.lt/BATP/en/article/download/44540/42590/138419>
- Clare, Seaton, Smith, Thomas, *Breaking into the Blackbox: Trend Following, Stop Losses, and the Frequency of Trading*：
  - 在 S&P 500 上，月末决策优于更高频交易；
  - 常用止损规则没有增加价值；
  - 说明“检查更频繁”不等于“交易更频繁”。
  - <https://openaccess.city.ac.uk/id/eprint/17842/8/BLACKBOX%20%20%20SSRN-id2126476.pdf>

### 3.2 止损

- Białkowski, *Cryptocurrencies in institutional investors’ portfolios: Evidence from industry stop-loss rules*：
  - 止损可显著降低波动和收益，但长期多头存活率不超过 35%；
  - 结论是止损有助于风险管理，不是保证收益。
  - <https://ideas.repec.org/a/eee/ecolet/v191y2020ics0165176519304227.html>
- Sadaqat, Butt, *Stop-loss rules and momentum payoffs in cryptocurrencies*：
  - 147 个加密资产，2015-01 至 2022-06；
  - 止损版动量在收益、Sharpe 和 alpha 上优于传统动量；
  - 在不同市场状态下都更好。
  - <https://ideas.repec.org/a/eee/beexfi/v39y2023ics2214635023000473.html>
- Kaminski, Lo, *When do stop-loss rules stop losses?*：
  - 在较长采样频率下，某些止损规则可以提高期望收益并显著降低波动。
  - <https://ideas.repec.org/a/eee/finmar/v18y2014icp234-254.html>
- Kaya, Mostowfi, *Low-volatility strategies for highly liquid cryptocurrencies*：
  - 低波动组合配合简单止损可改善下行风险和 Sharpe。
  - <https://doi.org/10.1016/j.frl.2021.102422>
- Duarte, *Trailing Stop-Loss and Re-Entry Strategies in Europe*：
  - 使用 3% trailing stop，并在回升 3% 后重入；
  - 结果混合，但在高波动市场能减少损失；
  - 说明“止损后的重入规则”本身是独立决策点。
  - <https://eu-opensci.org/index.php/ejbmr/article/view/51426>

### 3.3 均线与趋势跟随

- Le, Ruthbah, *Trend-following Strategies for Crypto Investors*：
  - 测试 20/65/150/200 日均线；
  - BTC 上 65 日最好，ETH 和大型非 BTC 指数上 20 日最好；
  - 交易成本显著侵蚀收益。
  - <https://www.monash.edu/__data/assets/pdf_file/0011/3744821/Trend-following-Strategies-for-Crypto-Investors.pdf>
- Grobys, Ahmed, Sapkota, *Technical trading rules in the cryptocurrency market*：
  - 2016–2018，11 个高成交加密资产；
  - 20 日均线策略在样本内表现较好；
  - 但样本短，不能外推为固定最优周期。
  - <https://osuva.uwasa.fi/server/api/core/bitstreams/6d20e4ef-7741-419e-b2ea-0cb103bfa1dd/content>

### 3.4 风险管理和集中度

- Yang, *Cryptocurrency market risk-managed momentum strategies*：
  - 风险缩放把平均周收益从 3.18% 提到 3.47%，Sharpe 从 1.12 提到 1.42；
  - 在加密市场中改善主要来自收益增强，而不是仅降低下行。
  - <https://doi.org/10.1016/j.frl.2025.107879>
- Man Group, *In Crypto We Trend*：
  - 趋势跟随适合加密资产，但币数要平衡分散化和成本；
  - 风险调整后收益峰值大约在 10–15 个币；
  - 波动率缩放可降低压力期交易成本。
  - <https://www.man.com/insights/in-crypto-we-trend>
- Platanakis, Sutcliffe, Urquhart, *Optimal vs naïve diversification in cryptocurrencies*：
  - 四个主流币的周度组合中，1/N 等权和 Markowitz 优化差别很小；
  - 估计误差抵消了优化的理论收益。
  - <https://centaur.reading.ac.uk/78105/3/Optimal%20vs%20Naive%20Diversificationin%20Cryptocurrencies%20-%20Final%20Version.pdf>
- Grobys et al., *Cryptocurrency momentum has (not) its moments*：
  - 大市值币的等权动量仍会严重崩溃；
  - 单个币可以导致整个动量组合收益不显著；
  - 波动率管理有助于缓解动量崩溃。
  - <https://osuva.uwasa.fi/bitstream/handle/10024/20018/Osuva_Grobys_Kolari_Sandretto_Shahzad_%C3%84ij%C3%B6_2025.pdf?sequence=2>

### 3.5 数据偏差

- Ammann, Burdorf, Liebi, Stöckl, *Survivorship and Delisting Bias in Cryptocurrency Markets*：
  - 3,904 个加密资产，2014–2021；
  - 等权买入持有组合的幸存者偏差可高达 62.19%；
  - 纳入退市收益后，动量和市场 beta 不再显示正向关系。
  - <https://alexandria.unisg.ch/server/api/core/bitstreams/2bc8397d-47dd-4f66-8467-9004b2c9d212/content>
- CoinMarketCap 官方市值定义：
  - 市值基于流通供应量，而不是总供应量或完全稀释供应量。
  - <https://support.coinmarketcap.com/hc/en-us/articles/360043836811-Market-Capitalization-Cryptoasset-Aggregate>

## 4. 当前策略应该怎么改

### 已经完成的修正

1. **停止把 22.44x 当作稳健结果。**
   现在同时报告 21 个相位的分布和 21 份完全错开组合。

2. **把固定单相位 21D 改成相位不敏感评估。**
   21 份完全错开的 21D 组合已经成为决策基准；固定起点只作为上尾参考。

3. **BTC 11D 闸门已经完成独立对照。**
   无闸门、20/50/65/100/200D MA、10/11/14/20/30/50/100/200D trailing、confirm1/2/3/5 都已跑过。结论是 11D/2 是局部尖峰，不是稳定规律，不能直接上线。

4. **止损周期已经完成分布审计。**
   MA20/50/65/75/100/150/200 × confirm1/2/3 已跑完；50–100D、confirm1–3 是宽平台，75D/3 不是唯一最优。

5. **重入规则已经完成独立对照。**
   当前样本支持“止损后等到下一次调仓再重入”；立即重入的换手和 whipsaw 明显更差。

### 仍需完成

1. **验证新的高收益候选。**
   BTC 100D MA + 60D 波动率目标 + 三族每日动量事件组合已经完成严格 Top20、成本、事件规则邻域、因子族和 2020–2021 压力检查；但事件规则仍是参数尖峰，2024 起子区间只有 13.60x @2bps，不能直接上线。

2. **做多重检验修正。**
   当前已经试了数千组参数。最终候选必须做：
   - 真正的嵌套 walk-forward；
   - White Reality Check / Deflated Sharpe 或等价的多重检验；
   - 换手、容量、滑点和退市场景；
   - 不同市场阶段的独立验证。

### 暂不改

- 不增加杠杆；
- 不放弃 point-in-time Top20；
- 不放弃 T+1；
- 不放弃 2/20/50/100bps 成本压力测试；
- 不把纯 TSMOM 当作当前 Top20 轮动的替代，除非它在相位不敏感测试中胜出。

## 5. 可复现实验

本次相位审计由以下脚本生成：

```bash
.venv/bin/python scripts/run_strategy_evidence_audit.py \
  --config config/base.yaml \
  --start-date 2022-01-01 \
  --cost-bps 2,20 \
  --tranche-counts 1,3,7,21 \
  --output-dir reports/strategy_evidence_audit_2022
```

输出：

- `reports/strategy_evidence_audit_2022/phase_scan.csv`
- `reports/strategy_evidence_audit_2022/staggered_robustness.csv`
- `reports/strategy_evidence_audit_2022/report.md`
- `reports/strategy_evidence_audit_2022/manifest.json`

决策点消融：

```bash
.venv/bin/python scripts/run_decision_point_ablation.py \
  --config config/base.yaml \
  --start-date 2022-01-01 \
  --cost-bps 2,20 \
  --output-dir reports/decision_point_ablation_2022
```

输出：

- `reports/decision_point_ablation_2022/phase_metrics.csv`
- `reports/decision_point_ablation_2022/variant_summary.csv`
- `reports/decision_point_ablation_2022/staggered_basket.csv`
- `reports/decision_point_ablation_2022/report.md`
- `reports/decision_point_ablation_2022/manifest.json`

相位不敏感波动率目标：

```bash
.venv/bin/python scripts/run_phase_invariant_vol_target.py \
  --config config/base.yaml \
  --start-date 2022-01-01 \
  --cycles 7,14,21,28 \
  --target-vols 0.5,0.6,0.7,0.8 \
  --vol-windows 20,30,60 \
  --stop-modes own75 \
  --gate-modes btc_ma100 \
  --cost-bps 2,20 \
  --output-dir reports/vol_target_neighborhood_2022
```

三族每日动量事件组合（严格 Top20）：

```bash
.venv/bin/python scripts/run_momentum_event_ensemble.py \
  --config config/base.yaml \
  --start-date 2022-01-01 \
  --target-vols 0.7,0.8 \
  --vol-window 60 \
  --cost-bps 2,20,50,100 \
  --output-dir reports/momentum_event_ensemble_2022
```

输出：

- `reports/momentum_event_ensemble_2022/summary.csv`
- `reports/momentum_event_ensemble_2022/spec_sensitivity.csv`
- `reports/momentum_event_ensemble_2022/membership_sensitivity.csv`
- `reports/momentum_event_ensemble_2022/stress_test.csv`
- `reports/momentum_event_ensemble_2022/report.md`

## 6. 证据等级说明

- **外部论文支持**：有论文方向支持，但仍需本项目数据验证。
- **项目内实证支持**：当前数据和成本口径下成立，不代表未来。
- **未验证继承假设**：来自旧策略或用户初始规则，尚未完成独立研究。
- **已推翻**：被相位、邻域、滚动起点或成本测试否定。
