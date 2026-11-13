# Atlas20 预注册：LS82 carry sleeve 独立归因

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；research-only；不接实盘 |
| Trial ID | `PR2026-11-LS95-LS82-CARRY-ATTRIBUTION` |
| 输入 | LS82 已保存的 `carry_schedule.csv`，以及同一 Bitget mark/market、Binance funding 数据 |
| 组合 | 只运行 carry sleeve：25% residual allocation，不包含 LS57 base |
| 成本 | 20bps；与 LS82 主报告一致 |
| 窗口 | 2022-01-01 → 2026-09-20 |

## 0. 研究问题

LS94 发现 LS82 相对 LS57 的增量收益集中在少数年份。LS95 只做归因：carry sleeve 独立运行时，
收益来自哪些年份、资产和多空腿？它不重新选资产、不扫描 funding lookback、不改变 7D rebalance、
不改变 2 low + 2 high、不改变 25% allocation，也不把归因结果直接变成新策略。

## 1. 冻结构造

- 从 `reports/ls82_core8_carry_risk_2026/carry_schedule.csv` 读取每周目标权重；
- 权重乘以 0.25，作为独立 carry sleeve 的 NAV 权重；
- 使用与 LS82 相同的 Bitget mark、Bitget market fill、Binance funding proxy、T+1 UTC +3h、
  missing-mark carry 3h 和 20bps 成本；
- base targets 为空；因此本 trial 的收益不是 LS82 相对 LS57 的复合差额，而是 carry sleeve 本身的
  price/funding/fee PnL。

## 2. 归因方法

1. 重放独立 sleeve 的 trades，得到每小时 signed quantity；
2. 用同一 mark close 计算每小时 price PnL；
3. 从 funding ledger 汇总 funding PnL，从 trades ledger 汇总 fee；
4. 按 year、asset、long/short 汇总 price/funding/fee/net；
5. 用 engine `daily_returns` 校验归因：日净 PnL / 前一日权益与 engine 日收益的相关性必须 >0.95，
   否则标记 `inconclusive`，不把归因表当结论；
6. 输出 `carry_daily.csv`、`asset_summary.csv`、`asset_year_net.csv`、`side_year_net.csv`、
   `year_summary.csv`、`manifest.json` 和 `report.md`。

## 3. 结论标签

- `asset-concentrated`：单一资产贡献超过正 net PnL 的 50%，或单一资产造成超过总正贡献的 50% 回吐；
- `year-concentrated`：单一日历年份贡献超过总 net PnL 的 70%；
- `side-concentrated`：long 或 short 单侧贡献超过总 net PnL 的 80%；
- `diversified`：以上均不触发，且归因校验通过；
- `inconclusive`：归因与 engine 日收益不匹配，或关键 ledger 缺失。

标签只描述 carry sleeve 的历史来源，不构成 live promotion。若出现集中，下一步只允许预注册
机制假设（例如 regime 或风险预算），不允许按资产/年份事后删数据救结果。

## 4. 复现

```bash
.venv/bin/python scripts/run_ls95_carry_attribution.py \
  --output-dir reports/ls95_carry_attribution_2026
```
