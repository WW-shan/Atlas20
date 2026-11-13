# Atlas20 预注册：LS82 carry-core 独立稳健性审计

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；research-only；不接实盘 |
| Trial ID | `PR2026-11-LS94-LS82-ROBUSTNESS` |
| 候选 | LS82：LS57 + core8 PIT funding carry，25% residual，60% long buffer，1.45x target gross |
| 基准 | 同成本、同共同交易日的 LS57 |
| 成本场景 | 13.0164bps maker-shadow；20bps 基准成本 |
| 窗口 | 2022-01-01 → 2026-09-20 |
| 输入 | 已保存的真实引擎日收益；不重新拟合、不扫描 allocation/参数 |

## 0. 研究问题

LS93 发现 LS92 core-satellite 的改善不稳健，但 LS82 standalone 在同一两个成本档的 full 终值、
Sharpe 和 MDD 都优于 LS92。LS94 只问：LS82 相对 LS57 的优势本身是否稳健，还是同样集中在
2023/2024 和少数路径？这不是新策略，也不改变 LS82 的规则、allocation、funding 或执行假设。

## 1. 冻结输入

```text
LS82_13 = reports/ls92_ls82_maker13_2026/daily_normal_13.0164_0.25.csv
LS57_13 = reports/ls92_ls57_maker13_2026/daily_base_normal_13.0164.csv
LS82_20 = reports/ls82_core8_carry_risk_2026/daily_normal_20_0.25.csv
LS57_20 = reports/ls89_asset_ma21_exit_2026/daily_base_normal_20.csv
```

两个场景分别取共同有效日期；缺失、重复或非有限收益直接失败，不填充。13.0164bps 与 20bps 不混合。

## 2. 必做诊断

1. full 与 2024-01-01→2026-09-20 validation 的终值、Sharpe、MDD。
2. 逐年收益/Sharpe/MDD、leave-one-year-out、365D rolling 最差和为正比例。
3. 日 log excess 的 Newey-West t(63)，以及 63 日 circular block bootstrap 5,000 次的 2.5%/97.5%
   总 log excess 区间。
4. 两个成本档分别做 LS57、LS82 两候选 CSCV/PBO；White Reality Check 对零和对 LS57 超额。
5. 当前 `reports/research_trial_inventory/summary.json` 的项目级 Deflated Sharpe 诊断。
6. 不用 LS92 的 50/25/25 组合结果替代 LS82 standalone；不因为 LS82 全样本更高就跳过年度/路径检查。

## 3. 结论标签

- `robust-shadow`：两个成本档 full 终值和 Sharpe 高于 LS57、MDD 不差超过 1pp，bootstrap 2.5%
  总 log excess 为正，leave-one-year-out 最差为正，PBO <=0.50，且 Reality Check 对 LS57 超额 p<0.05。
- `cost-fragile`：13.0164bps 改善但 20bps 不能同时改善终值和 Sharpe。
- `year-concentrated`：两个成本档点估计改善，但 bootstrap 或 leave-one-year-out 显示依赖少数年份。
- `inconclusive`：其他情况或关键统计量不可计算。

标签只描述冻结证据；不构成 live promotion，也不阻止下一组研究。

## 4. 复现

```bash
.venv/bin/python scripts/run_ls94_ls82_robustness.py \
  --output-dir reports/ls94_ls82_robustness_2026
```

输出：`scenario_summary.csv`、`yearly.csv`、`leave_one_year_out.csv`、
`rolling_365_summary.csv`、`daily_excess.csv`、`pbo.csv`、`deflated_sharpe.csv`、
`reality_check.csv`、`manifest.json` 和 `report.md`。
