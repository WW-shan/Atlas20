# Atlas20 研究预注册：Top20 churn short with alt-weak regime gate

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 候选族 ID | `PR2026-11-LS73-TOP20-CHURN-ALT-WEAK` |
| 来源 | LS72 的 m=7/h=28 churn short 在 2022–2026 为正，但 2021 alt bull 为负 |
| 状态 | 组合级研究回测；不连接实盘、不修改 live target |
| 数据 | strict PIT CMC Top20 + `data/processed/panel_daily.csv` |
| Discovery | 2022-01-01 → 2023-12-31 |
| Validation | 2024-01-01 → 2026-11-12 |
| 独立负控 | 2021-01-01 → 2021-12-31（LS72 的全期失败年份） |
| 冻结交易规则 | LS72 `m=7, h=28`，entry+exit churn，等权空头 + BTC 多头对冲 |
| 执行 | 事件确认日 close 后，下一 close 起持有 28 日 |
| 成本 | 2 / 20 / 50 / 100bps 每边；初步筛查不计 funding |

## 0. 研究问题

LS72 的未经门控结果在 2022-01-01 → 2026-11-12 为 **1.2114x / Sharpe 1.3027 / MDD -3.18%**，
但 2021 为 **0.7604x / -2.6950 / -26.02%**。这说明事件空头不是无条件 alpha，而是可能在
alt bull 中反向。本轮不重新挑 m/h，只检验三个冻结的状态闸门：

1. `alt_rel_60`：Top20 equal-weight 60D log return <= BTC 60D log return；
2. `btc_ma200`：BTC close < BTC 200D SMA；
3. `both`：上述两个条件同时成立。

闸门只在新事件确认日读取；事件一旦开出，就按 LS72 持满 28 日。2021 是负控/压力年，不用它
挑闸门；三个闸门全部报告，不能只保留最好结果。

## 1. 冻结构造

- 事件定义、30 日冷却、entry+exit 合并、空头等权和 BTC 对冲全部沿用 LS72；
- 每个事件日组合 gross 1.0，其中空头 0.5、BTC 多头 0.5；
- 每个事件日按 `1/h` tranche 分散，组合总 gross <=1；
- 每个闸门只决定事件是否允许开仓，不在持有期间每日缩放；
- 缺失收益、成本、窗口和 LS72 一致。

## 2. 验收

按 discovery 20bps Sharpe 选最好闸门，要求 discovery 20/50bps Sharpe >0。候选必须：

- validation 20bps 与 50bps Sharpe >0；
- 2021 负控终值 >=0.92x（允许小幅负收益，但不能重现 LS72 的 -24%）；
- full 20bps 终值 >1.0、Sharpe >0.5、MDD 不差于 -30%；
- full 20bps/50bps 终值均高于 1.0；
- 报告每个闸门的完整指标、事件数和 LS57 overlay；不能只报通过者。

通过只进入 funding、Bitget mark/fill 和 live shadow；不直接接实盘。

## 3. 失败后动作

若三个闸门都没有同时改善 2021 和 2022–2026，停止 Top20 churn 家族，不再扫 MA 窗口、
60D 阈值、持有期、冷却期、空头比例或 entry/exit 拆分。保留 LS72/LS73 的负结果作为研究资产。

## 4. 复现

```bash
.venv/bin/python scripts/run_top20_churn_gated.py \
  --start-date 2021-01-01 --end-date 2026-11-12 \
  --output-dir reports/top20_churn_gated_2026
```
