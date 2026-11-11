# Atlas20 候选预注册：H5 多头内部 funding 拥挤去权重

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS18-H5-FUNDING-TILT` |
| 基线 ID | `PR2026-10-D-L125` |
| 基础 alpha | 冻结 LS12：H5 1.25x + BTC 200D 双空头 router |
| 新机制 | 将 H5 多头中 funding 拥挤的正 funding 腿减半，并在同一 H5 书内再分配 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | long 1.25x 上限；short <=0.25x；hard total 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

H6 的 book-level funding state 按整个 H5 账本缩放，无法区分“某一个持仓拥挤”与“整个组合拥挤”；
它在主成本上净损失收益和 Sharpe。LS18 改为 **持仓内部横截面**：

> 只对 H5 当前持有的、7D funding 位于 PIT Top20 上三分之一且为正的腿减半；把释放的权重分配给
> 同一 H5 书内未被标记的其他持仓。若无人能接收，剩余权重保留现金。

外部依据仍是 Crypto Carry（S49）和 funding-crash（S50）：高 funding 表示多头杠杆需求拥挤，
正 funding 也有直接 carry 含义。与 H6 的区别是：

- H6：组合层面一个 factor，所有 sleeve 同比例缩放；
- LS18：资产层面 cross-sectional tilt，仍保留 H5 的选择和总 gross 目标。

## 1. 可行性审计

- 1,053 个 H5 holding-events，511 个目标事件日；
- 325 个 crowded holding-events，覆盖 256 个事件日；
- 触发日释放的 gross 中位数为 **31.25%**，90 分位为 50%；
- 触发并不集中于单一资产。

这说明机制有足够横截面变化，不是无效的空操作。

## 2. 冻结构造

对于每个 H5 long 目标日 `D`：

```text
state_i = funding_rank_i(D) >= 2/3 and mean_funding_7d_i(D) > 0
w_i' = 0.5 * w_i                    if state_i
w_i' = w_i                          otherwise

freed = sum(w_i - w_i')
recipients = {i: state_i is false and w_i > 0}
allocate freed pro rata to recipient original weights
cap each recipient at 0.60 * NAV
unallocated = cash
```

约束：

- 只在 H5 当前选中的资产集合内重分配，不新增币；
- `max_asset_weight = 0.60` 沿用衍生品设计的单币上限；
- funding rank / mean 只用 `D` 之前或当天的 settlements；
- 空头 router、H5 选币、BTC 200D、20% short stop、short buffer 和 gross cap 不变；
- T+1 UTC +3h；
- funding 主口径为 Binance proxy/skip，不能声称 Bitget 精确历史已闭合。

## 3. 预注册门槛

1. 20bps 终值 > L125；
2. 20bps Sharpe >= L125；
3. 20bps MDD <= L125 +5pp；
4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
6. 100bps MDD <=50%；
7. 3x short-adverse 0 强平且 MDD <=50%；
8. 删除任一最佳年份后终值仍高于同成本 L125；
9. 365 天滚动最差 >= L125；
10. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
11. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过基线，12/12 MDD 5pp；
12. 单资产空头贡献 <=50%，前 3 <=80%；
13. observed gross <=1.50 且无 gross breach hour；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月真实 OOS 未满前最高只能 provisional。

## 4. 失败后动作

如果 LS18 失败：

- 不扫描 funding lookback、rank、减半比例、单币 cap、再分配规则或触发方向；
- 停止 long-leg funding tilt 家族；
- 提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 5. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS18-H5-FUNDING-TILT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_tilt
```

## 6. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
