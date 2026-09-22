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

## 2. 决策点逐项审计

| 决策点 | 当前做法 | 来源 | 外部证据 | 项目内结果 | 判定 |
|---|---|---|---|---|---|
| 股票池 | 历史 point-in-time Top20 | 初始策略/旧项目 | 大市值加密资产确实有较强动量；幸存者偏差和退市偏差会严重高估等权组合收益 | 已从 CMC 原始 payload 重建 Top20 并审计 | **方向支持，必须继续保持 point-in-time** |
| 排除 BTC | Top20 内排除 BTC 选币 | 初始策略 | 没有论文支持必须排除 BTC | 样本内排除 BTC 明显提高收益 | **项目内经验，不是外部规律** |
| 选币因子 | CTREND-breakout 综合分 | 项目自建 | 加密横截面动量在真实成本下证据弱；时间序列动量证据更强 | 样本内 breakout 最好，但换其他分数族和相位后仍不稳定 | **可作为候选，不能称为已验证因子** |
| 调仓周期 | 固定 21D | 初始策略 | 论文最优持有期不统一；有 5D、周频、月频；换仓日/星期几本身会显著影响结果 | 21D 相位扫描：中位 3.94x，最差 0.61x，最好 22.44x | **被推翻为“稳定最优”；必须做相位不变或事件驱动** |
| 持仓数量 | 只持有第 1 名 | 初始策略 | Man Group 研究显示风险调整后峰值约 10–15 个币；单个币可以毁掉动量组合 | Top1 22.44x，Top2 6.60x，Top3 6.40x，Top5 2.58x，Top10 2.14x @20bps | **这是高收益/高风险赌注，不是分散化上更合理的方案** |
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

1. **替换或独立验证 BTC 闸门。**
   候选方向：波动率缩放 trailing、BTC 与市场宽度组合、风险预算/波动率目标，而不是继续搜索 10–14 日之间的离散参数。

2. **做多重检验修正。**
   当前已经试了数千组参数。最终候选必须做：
   - walk-forward / 滚动起点；
   - 参数邻域；
   - 子区间；
   - 成本压力；
   - White Reality Check / Deflated Sharpe 或等价的多重检验。

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

## 6. 证据等级说明

- **外部论文支持**：有论文方向支持，但仍需本项目数据验证。
- **项目内实证支持**：当前数据和成本口径下成立，不代表未来。
- **未验证继承假设**：来自旧策略或用户初始规则，尚未完成独立研究。
- **已推翻**：被相位、邻域、滚动起点或成本测试否定。
