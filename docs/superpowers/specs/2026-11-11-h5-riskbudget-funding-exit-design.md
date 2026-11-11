# Atlas20 候选预注册：H5 连续未使用风险预算下的 funding 退出空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS9-H5-RISKBUDGET-FUNDING-EXIT` |
| 基线 ID | `PR2026-11-LS9-H5-BASELINE` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 多头 | 冻结 H5 `PR2026-10-H5`，1.0x 目标 gross |
| 空头信号 | H5 完全退出，且退出资产满足 LS6 的 7D funding 上三分之一 |
| 空头单腿权重 | `5% × max(0, 1 - 退出后的 H5 目标 long gross)` |
| 持有期 | 21 个日历日；H5 重新买入时提前关闭 |
| stop | 20% adverse mark |
| gross | target 0.95，hard observed 1.00，仅使用未使用 gross |
| 执行/成本 | T+1 UTC +3h；2/20/50/100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS8 首轮曾因 H5 gross 的 naive datetime 与 UTC schedule 日期不一致而错误显示“从未触发”。修复后
LS8 实际产生 37 个空头，20bps 为 22.8336x / Sharpe 1.7744 / MDD -33.52%，但 365 天滚动最差
0.7909x 仍低于 H5 的 0.7970x，DSR 也失败，因此 LS8 rejected。继续扫 0.50 附近的硬阈值没有依据。

LS9 改为连续风险预算：

- H5 满仓时，空头单腿权重为 0；
- H5 半仓时，空头单腿权重为 2.5% NAV；
- H5 空仓时，空头单腿权重为 5% NAV；
- 公式固定为 `5% × max(0, 1 - H5_long_gross)`，不扫描系数或指数。

这样不是在“高多头时关闭空头”，而是让空头规模随未使用的多头风险预算变化。

## 1. 冻结构造

### 1.1 H5 long gross

对每个信号日 `D`：

1. 用冻结 H5 在 `D` 的最新目标权重计算正权重之和；
2. 不使用未来目标，缺失目标沿用最近一个已生成目标；
3. 空头新仓的单腿权重在该仓开仓日计算一次，之后持有期内不随 H5 gross 改变；
4. 已存在的空头不会因为 H5 之后加仓而强制改变大小。

### 1.2 Funding 与退出信号

完全沿用 LS6：

- H5 前一目标持有、当前目标完全退出；
- 退出资产仍在当日 PIT Top20；
- 7D funding 横截面排名不低于 2/3；
- 有效 funding 资产少于 5 个时 fail closed；
- 固定 21 日持有；
- H5 重新买入时提前平仓；
- 20% adverse mark stop。

### 1.3 资金与执行

- H5 1.0x；target total gross 0.95；hard observed gross 1.00；
- 空头只使用 `max(0, 0.95 - scaled_H5_long_gross)`；
- next-tick gross guard；
- long buffer 0.75、short buffer 0.50；
- T+1 UTC +3h；
- missing mark carry 最多 3 小时；
- funding 主口径 Binance proxy/skip；另跑 3x short-adverse。

## 2. 预注册评估门槛

LS9 只能在以下全部满足时升级：

1. 20bps 终值和 Sharpe 都严格高于 H5 基线；
2. 20bps MDD 不比 H5 差超过 5 个百分点；
3. 365 天滚动最差不低于 H5 基线；
4. 2/20/50/100bps 终值和 Sharpe 都高于同成本 H5；
5. 100bps MDD ≤ 50%；
6. 3x short-adverse funding 下 0 强平且 MDD ≤ 50%；
7. 所有成本档最大 observed gross ≤ 1.00，target gross ≤ 0.95；
8. 删除最佳年份后不低于 H5；
9. 12 个真实月初引擎启动中至少 8/12 终值和 Sharpe 胜过基线，MDD 5pp 门槛 12/12；
10. 单资产空头贡献 ≤ 50%，前 3 ≤ 80%；
11. PBO/CSCV ≤ 0.50，White Reality Check p ≤ 0.05；
12. Top20/2022 与全项目 DSR ≥ 0.95 才可 promotion；
13. 12 个月真实 OOS 未满前最高只能 provisional。

## 3. 失败后动作

如果 LS9 失败：

- 不扫描 base weight 2.5%/5%/7.5%/10%；
- 不扫描公式指数、除数或 H5 gross 阈值；
- 不扫描 funding lookback、rank、min_assets、持有期、stop、单腿或 gross；
- 必须提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现接口

```bash
.venv/bin/python scripts/run_h5_riskbudget_funding_exit_short.py --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_riskbudget_funding_exit

.venv/bin/python scripts/run_h5_riskbudget_funding_exit_short.py --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_riskbudget_funding_exit
```

## 5. 状态

- 预注册：是；
- 正式运行：是（2/20/50/100bps + 3x short-adverse funding）；
- 结果：rejected（365 天滚动最差 0.7865x < 0.7970x；Top20 DSR 0.9382、全项目 DSR 0.9156）；
- 实盘：否；
- 修改当前实盘：否。
