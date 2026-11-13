# Atlas20 候选预注册：LS57 逐资产 200D 趋势过滤

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；研究输出不接实盘 |
| 候选 ID | `PR2026-11-LS85-LS57-ASSET-TREND-200D` |
| 基线 | LS57（H5 1.25x + LS23 profit-lock + BTC-regime short router） |
| 新增规则 | 信号日 D 的 long leg 收盘低于自身 200D SMA 时，该 leg 目标降为 0；不重分配 |
| 空头 | 保持 LS57 router 完全不变 |
| 窗口 | 2022-01-01 → 2026-09-20；warmup 2021-01-01 |
| 执行 | T+1 UTC +3h；Bitget mark/liquidation，Bitget market fill；missing mark carry 3h |
| 成本 | 20 / 50 / 100bps；正常与 3x two-sided adverse funding |

## 0. 研究问题

LS57 的多头仍可能在单个资产进入长期下行趋势时继续持有；利润保护只处理“已经涨了很多”的
leader，不处理“已经跌破长期趋势”的普通 long leg。这个 trial 检验一个简单、低频且可解释的
防守规则：

> H5 选中的 long asset，如果信号日收盘低于自己的 200D SMA，则该腿转为现金；不把释放的
> 权重分给其他资产，不改 short router。

200D 是项目已有的长期趋势窗口，不扫描 50/100/150/200/250D，也不按年份或资产手工筛选。
缺失 MA 或价格时保留该腿并记录，不静默变成现金。

## 1. 冻结构造

```text
base_long = LS57 long targets
for each signal date D and long asset i:
  if close_i(D) < SMA200_i(D):
      target_i(D) = 0
  otherwise:
      target_i(D) unchanged
short_targets = LS57 short router unchanged
combined = base long + short, total gross cap 1.50x
```

- 只用 D 收盘及之前数据；T+1 执行。
- 不重分配、不改变 LS23 profit-lock、不改变 short router、不改变 20% short stop。
- 每个事件记录 filtered weight、cash weight、缺失 MA 数量。
- 20/50/100bps 和 3x two-sided adverse funding 必报。

## 2. 预注册判定

1. 20bps full multiple >= LS57 baseline，Sharpe >= baseline，MDD 至少改善 2pp；
2. 20bps validation multiple/Sharpe 均不差于 baseline；
3. 50bps 和 100bps 不得低于同成本 baseline 的终值/Sharpe；
4. 3x two-sided adverse funding 下不得出现强平或 gross breach；
5. 过滤不能依赖单一资产或单一年份；必须报告 filtered weight 和资产贡献；
6. 如果只是降风险但收益明显下降，标记为 risk-only rejected，不晋级；
7. 任何失败都不通过调整 MA window、重分配比例或只对某些资产生效来救结果。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls85_asset_trend_filter.py \
  --warmup-start 2021-01-01 --start-date 2022-01-01 --end-date 2026-09-21 \
  --costs-bps 20,50,100 --output-dir reports/ls85_asset_trend_filter_2026
```
