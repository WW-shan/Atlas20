# Atlas20 预注册：LS92 core-satellite 稳健性归因

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；research-only；不接实盘 |
| Trial ID | `PR2026-11-LS93-LS92-ROBUSTNESS` |
| 候选 | LS92：50% LS57 + 25% LS82 carry + 25% LS88 long-only carry，初始资本权重，不再平衡 |
| 基准 | 同一成本、同一共同交易日的 LS57 |
| 成本场景 | 13.0164bps maker-shadow；20bps 基准成本 |
| 窗口 | 2022-01-01 → 2026-09-20，严格取四个 sleeve 的共同有效日期 |
| 输入 | 已保存的真实引擎日收益；不重新拟合、不扫描权重、不改变规则 |

## 0. 研究问题

LS92 相对同成本 LS57 的改善很小：13.0164bps 下终值约 +4.65%，Sharpe 约 +0.016。这个差异可能
来自真实的组合分散收益，也可能只是某个 sleeve、某一年、某段行情或 maker-shadow 成本假设造成。
LS93 只做稳健性和归因，不寻找新的权重，也不把结果当作 live promotion。

无论结论是 robust、cost-fragile、sleeve-concentrated 还是 inconclusive，都继续进入下一组研究，
不把一次失败解释成策略形式本身不可研究。

## 1. 冻结输入和样本规则

```text
LS92 = reports/ls92_core_satellite_maker_shadow_2026/portfolio_daily_returns.csv
LS57_13 = reports/ls92_ls57_maker13_2026/daily_base_normal_13.0164.csv
LS91 = reports/ls91_core_satellite_ensemble_2026/portfolio_daily_returns.csv
LS57_20 = reports/ls89_asset_ma21_exit_2026/daily_base_normal_20.csv
```

每个场景分别取 LS57、LS82、LS88、LS89 和组合的共同日期。任一日收益缺失、重复或非有限值即停止，
不用 0、前值或另一成本曲线补齐。13.0164bps 和 20bps 不混合，组合收益必须来自对应成本的真实引擎输出。

## 2. 必做诊断

1. full、2024-01-01→2026-09-20 validation、逐年收益/Sharpe/MDD。
2. 逐年 leave-one-year-out；365 个日收益滚动窗口的最差和超额为正比例。
3. 日 log excess 的 Newey-West t（63 lag），以及 63 日 circular block bootstrap 5,000 次的总 log
   excess 中位数、2.5%/97.5% 区间和为正概率。
4. 每个 sleeve 的最终财富贡献：`weight × sleeve terminal multiple / portfolio terminal multiple`，
   并报告相对 LS57 的增量归因。
5. 子账户相关矩阵。
6. 以同一场景的 LS57、LS82、LS88、LS89、组合为候选集，做 12-block CSCV/PBO；同时报告当前
   `reports/research_trial_inventory/summary.json` 的 project-wide Deflated Sharpe 诊断。
7. 同一组诊断在 13.0164bps 和 20bps 各跑一次，禁止只在有利成本档下结论。

## 3. 结论标签

- `robust-shadow`：两个成本档的终值和 Sharpe 都高于同成本 LS57，MDD 不差超过 1pp，bootstrap
  总 log excess 的 2.5% 分位为正，且多数年份和 leave-one-year-out 仍为正。
- `cost-fragile`：13.0164bps 档改善，但 20bps 档不能同时满足终值和 Sharpe 改善。
- `sleeve-concentrated`：组合改善主要来自单一 sleeve，或该 sleeve 的增量贡献超过总增量的大部分。
- `inconclusive`：其他情况，或关键统计量无法在完整共同样本上计算。

这些标签只描述证据，不构成对后续研究的禁令。任何标签都保留当前 live track
`PR2026-10-D-L125-V2` 不变；实盘晋级仍需要 owner 明确批准和独立的执行验证。

## 4. 复现

```bash
.venv/bin/python scripts/run_ls93_core_satellite_robustness.py \
  --output-dir reports/ls93_core_satellite_robustness_2026
```

输出应包含 `scenario_summary.csv`、`yearly.csv`、`leave_one_year_out.csv`、
`rolling_365_summary.csv`、`daily_excess.csv`、`sleeve_contributions.csv`、
`correlations.csv`、`pbo.csv`、`deflated_sharpe.csv`、`manifest.json` 和 `report.md`。
