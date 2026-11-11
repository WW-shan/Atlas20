# Atlas20 候选预注册：H5 相对动量确认 + 连续风险预算 funding 退出空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS10-H5-RELMOM14-RISKBUDGET-FUNDING-EXIT` |
| 基线 ID | `PR2026-11-LS10-H5-BASELINE` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 多头 | 冻结 H5 `PR2026-10-H5`，1.0x 目标 gross |
| 空头信号 | H5 完全退出、7D funding 上三分之一、且信号日资产 14D 回报低于 BTC |
| 空头单腿权重 | `5% × max(0, 1 - 退出后的 H5 target long gross)`，开仓时固定 |
| 持有期 | 21 个日历日；H5 重新买入时提前关闭 |
| stop | 20% adverse mark |
| gross | target 0.95，hard observed 1.00，仅使用未使用 gross |
| 执行/成本 | T+1 UTC +3h；2/20/50/100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS9 通过连续未使用风险预算提高了 H5 的终值和 Sharpe，但 365 天滚动最差仍低于 H5。最差
2022-05→2023-05 窗口中的主要损伤来自两个 episode：

- Dogecoin 2022-11-09：-1.0140% NAV，14D 相对 BTC 为 **+48.33%**；
- Solana 2023-03-08：-0.5455% NAV，14D 相对 BTC 为 -9.78%。

失败诊断显示：LS9 的 49 个 episode 中，信号日 14D 相对 BTC 为负的 15 个 episode 合计
+5.5448%，平均 +0.3697%；相对 BTC 为正的 34 个 episode 合计 +5.7916%，平均 +0.1703%。
最差窗口中，未过滤空头合计 -1.30698%，仅保留 14D 相对 BTC 为负的空头后为 -0.29798%。

7D/14D/30D/60D 相对动量都被检查过用于失败归因，但只有 14D 被选为规则，原因是：

1. 14D 已经是冻结 H5 的已有信号窗口，不引入新的时间尺度搜索；
2. 14D 在该诊断中同时减少最差窗口损伤并保留正贡献；
3. 规则只使用一个零阈值，不扫描阈值、分位数或持有期。

这是一个机制不同的新候选：LS10 不是继续调整 LS9 的风险预算大小，而是增加相对动量确认，
避免在资产已经强于 BTC 时继续做空。

## 1. 冻结构造

### 1.1 相对动量

对每个 H5 退出资产 `a` 和信号日 `D`：

- `r_a(D,14) = P_a(D) / P_a(D-14) - 1`
- `r_btc(D,14) = P_btc(D) / P_btc(D-14) - 1`
- 仅当 `r_a(D,14) < r_btc(D,14)` 时允许新开空头；
- 使用不晚于 `D-14` 的最后一个有效价格；
- 资产或 BTC 历史不足时 fail closed；
- 不使用未来价格，不填充缺失收益。

### 1.2 Funding、退出与风险预算

完全沿用 LS9：

- H5 前一目标持有、当前目标完全退出；
- 退出资产仍在当日 PIT Top20；
- 7D funding 横截面排名不低于 2/3；
- 有效 funding 资产少于 5 个时 fail closed；
- 单腿权重 `5% × max(0, 1 - post-exit H5 target long gross)`，开仓时固定；
- 固定 21 日持有；
- H5 重新买入时提前平仓；
- 20% adverse mark stop。

### 1.3 资金与执行

- H5 1.0x；target total gross 0.95；hard observed gross 1.00；
- 空头只使用未使用 gross；
- long buffer 0.75、short buffer 0.50；
- T+1 UTC +3h；
- missing mark carry 最多 3 小时；
- funding 主口径 Binance proxy/skip；另跑 3x short-adverse。

## 2. 预注册评估门槛

LS10 只能在以下全部满足时升级：

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

如果 LS10 失败：

- 不扫描相对动量 lookback、阈值、分位数或方向；
- 不扫描 base weight、指数、H5 gross 阈值、funding lookback、rank、min_assets、持有期、stop 或 gross；
- 必须提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现接口

```bash
.venv/bin/python scripts/run_h5_relmom_riskbudget_funding_exit_short.py --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_relmom_riskbudget_funding_exit

.venv/bin/python scripts/run_h5_relmom_riskbudget_funding_exit_short.py --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_relmom_riskbudget_funding_exit
```

## 5. 状态

- 预注册：是；
- 正式运行：是（2/20/50/100bps + 3x short-adverse funding）；
- 结果：rejected（滚动最差 0.7946x；单资产空头贡献 67.62%；Top20 DSR 0.9237、全项目 DSR 0.8974）；
- 真实引擎冷启动：硬失败后未继续执行；
- 实盘：否；
- 修改当前实盘：否。
