# Atlas20 研究预注册：LS57 + churn overlay 的成本与 funding 压力

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 候选 ID | `PR2026-11-LS77-LS57-CHURN-OVERLAY-STRESS` |
| 基线 | LS57 20bps 68.8077x / Sharpe 1.9819 / MDD -39.84% |
| Sleeve | LS74 churn，成本 20/50/100bps |
| 分配 | 10% / 20% / 25% residual gross，全部报告 |
| Funding | Binance proxy 正常 + 3x adverse |
| 窗口 | 2022-01-01 → 2026-09-20 |

## 0. 研究问题

LS76 在 20bps sleeve + funding proxy 下，25% 分配把 LS57 提升到 80.34x / Sharpe 2.049 /
MDD -36.80%，但 LS57 的 100bps 尾巴和 sleeve funding 仍是未闭合风险。本族冻结 LS76 的
residual-gross 规则，不重新调 allocation，只做压力矩阵：

- sleeve 成本 20 / 50 / 100bps；
- funding 正常 / **3x adverse**；
- allocation 10% / 20% / 25%；
- LS57 仍使用 20bps 日收益，因为本族只压力 sleeve；最终组合的 LS57 100bps 合并另需重跑。

3x adverse funding 的定义是：每个持仓腿都按最不利方向支付 `3 * |funding_rate|`，不是把历史
funding 简单乘以 3。若这个保守上界仍然通过，才说明 sleeve 不是靠 funding 符号侥幸获利。

## 1. 验收

每个 allocation 的 **worst case = 100bps sleeve + 3x adverse funding** 必须：

- full 终值 > LS57 20bps 基线 68.8077x；
- full Sharpe >1.9819；
- full MDD 不差于 -40.84%；
- validation 终值 > LS57 同窗口 15.2386x，且 Sharpe >2.1079；
- combined gross <=1.50x；funding coverage >=90%。

选择同时通过 worst case 的最大 allocation；不继续加 allocation。通过只进入真实 Bitget
funding/mark/fill 合并，不接实盘。

## 2. 复现

```bash
.venv/bin/python scripts/run_ls57_churn_overlay_stress.py \
  --start-date 2022-01-01 --end-date 2026-09-20 \
  --output-dir reports/ls57_churn_overlay_stress_2026
```
