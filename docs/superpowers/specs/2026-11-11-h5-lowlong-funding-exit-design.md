# Atlas20 候选预注册：H5 低多头仓位下的 funding 拥挤退出空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS8-H5-LOWLONG-FUNDING-EXIT` |
| 基线 ID | `PR2026-11-LS8-H5-BASELINE` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 多头 | 冻结 H5 `PR2026-10-H5`，1.0x 目标 gross |
| 空头信号 | H5 完全退出，且退出资产满足 LS6 的 7D funding 上三分之一 |
| 新增条件 | 退出后的 H5 目标 long gross ≤ 0.50 才允许开空 |
| 持有期 | 21 个日历日；H5 重新买入时提前关闭 |
| 单腿 | 2.5% NAV；20% adverse mark stop |
| gross | target 0.95，hard observed 1.00，仅使用未使用 gross |
| 执行/成本 | T+1 UTC +3h；2/20/50/100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS6 已经证明 funding 拥挤退出空头在四个成本档都提高 H5 的终值和 Sharpe，但 365 天滚动最差仍从 H5 的 0.7970x 降到 0.7923x。LS7 通过降低多头仓位换取更低回撤，却牺牲了终值并且 gross guard 失败。

> 2026-11-11 执行后记：首轮 LS8 由于 H5 gross 的 naive datetime 与 UTC schedule 日期不一致，错误显示“从未触发”。修复后 LS8 实际产生 37 个空头，20bps 为 22.8336x / Sharpe 1.7744 / MDD -33.52%，但滚动最差 0.7909x 仍低于基线，故仍为 rejected。

失败诊断显示：LS6 的空头在 H5 仍高度持仓时平均贡献为负；在 H5 已经减仓后，空头更像风险对冲。LS8 因此不改 funding 定义，只新增一个风险预算条件：

> 如果 H5 的新目标 long gross 仍高于 50%，不做空；只有 H5 已经进入低仓位状态，才启动已通过的 funding 拥挤退出空头。

50% 是「半仓」的事前风险预算分界，不是从多个阈值中扫描出来的最优点。

## 1. 冻结构造

### 1.1 H5 long gross

对每个信号日 `D`：

1. 用冻结 H5 在 `D` 的最新目标权重计算正权重之和；
2. 不使用未来目标，缺失目标沿用最近一个已生成目标；
3. 若 `long_gross(D) > 0.50`，任何 H5 退出资产都不得新开空头；
4. 该条件只作用于**新开仓**，不会强制平掉已存在的空头。

### 1.2 Funding 与退出信号

完全沿用 LS6：

- H5 前一目标持有、当前目标完全退出；
- 退出资产仍在当日 PIT Top20；
- 7D funding 横截面排名不低于 2/3；
- 有效 funding 资产少于 5 个时 fail closed；
- 固定 21 日持有；
- H5 重新买入时提前平仓；
- 单腿 2.5% NAV；
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

LS8 只能在以下全部满足时升级：

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

如果 LS8 失败：

- 不扫描 0.30/0.40/0.50/0.60/0.70 的 long-gross 分界；
- 不扫描 funding lookback、rank、min_assets、持有期、stop、单腿或 gross；
- 必须提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现接口

```bash
.venv/bin/python scripts/run_h5_lowlong_funding_exit_short.py --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_lowlong_funding_exit

.venv/bin/python scripts/run_h5_lowlong_funding_exit_short.py --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_lowlong_funding_exit
```

## 5. 状态

- 预注册：是；
- 正式运行：是（2/20/50/100bps + 3x short-adverse funding）；
- 结果：rejected（365 天滚动最差 0.7909x < 0.7970x；DSR 失败）；
- 实盘：否；
- 修改当前实盘：否。
