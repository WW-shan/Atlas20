# Atlas20 候选预注册：H5 利润保护 + 动态多空预算

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS27-H5-PROFIT-LOCK-DYNAMIC-SHORT` |
| 基线 ID | `PR2026-11-LS23-H5-PROFIT-LOCK-REGIME-SHORT`（当前最强研究候选）；同时报告 L125 |
| 多头 | 冻结 H5 1.25x + LS22 单龙头极端涨幅减半 |
| 空头组件 A | 冻结 LS12 BTC-200D 双空头 router（bear weak4 / non-bear funding-exit），名义 0.25x |
| 空头组件 B | 冻结 R6 14D bottom-quintile 4 币周频空头，名义 0.25x；20% 单腿 stop |
| 组合预算 | 两个空头组件等名义权重合并，请求短 gross 最多 0.50x；只使用多头未使用 gross，目标 total gross 1.48x，hard total gross 1.50x |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS23 已把 LS22 的利润保护和 LS12 的双空头 router 组合起来，但空头始终被限制在 0.25x。
LS22 触发利润保护时会把多头腿减半并释放现金；LS23 只用其中一部分转换为空头，而且空头只来自
LS12 一个信号族。LS27 检验两个已冻结、且收益来源不同的空头信号能否：

1. 在正常满多头时把 0.25x 空头预算分散到 LS12 和 R6 两条正交信号；
2. 在 LS22 释放现金时，把新增的未使用 gross 动态分配给空头，而不是一直留现金；
3. 在不提高 1.50x hard gross、不增加杠杆的条件下提高收益，同时不把回撤放大超过 5pp。

这不是对 stop、bottom-N、lookback 或空头权重的扫描。A、B 两个组件的规则都来自已经冻结的
试验；唯一新规则是“等名义权重合并 + 只用未使用 gross + 最多 0.50x 请求短 gross”。

## 1. 冻结构造

```text
long = LS22(H5 1.25x)
short_A = frozen LS12 router (bear weak4 / non-bear funding exit), requested 0.25x
short_B = frozen R6 weekly 14D weakest-four PIT Top20 short, requested 0.25x
short_requested = 1.0 * short_A + 1.0 * short_B
combined = cash-budget(long, short_requested, max_total_gross=1.50)
```

- 多头和两个空头组件都不得改写原始信号；
- `short_A` 和 `short_B` 等名义权重合并；同资产重叠时按目标权重相加；
- 合并后的空头请求不超过 0.50x；
- `combine_long_with_cash_budgeted_short` 只使用 `1.50 - long_gross` 的未使用 gross；
- 因 LS22 减半释放的现金，可在同一目标事件转换为额外空头；
- 空头仍使用 20% adverse mark stop、50% short buffer、T+1 +3h 和 missing-mark carry 3h；
- 不在空头组件之间做方向性择时，不按近期表现切换组件，不增加第三空头信号。

### 1.1 执行缓冲修订（在查看最终结果前固定）

第一轮实现审计发现：目标 total gross 直接贴住 1.50x 时，单资产 mark 在一小时内上涨会造成
组合 gross 短暂超过 1.50x。为避免把“目标层合规”误写成“逐小时合规”，LS27 使用 1.48x 目标
上限，并启用 1.50x 的逐小时 hard gross guard；1.48x 是执行缓冲，不是收益参数。缓冲区固定为
target 的约 1.35%，不使用近期表现、资产类别或 regime 调整。

## 2. 预注册门槛

以 LS23 为 incumbent；L125 作为历史基线一并报告。

1. 20bps 终值 > LS23 的 61.9150x；
2. 20bps Sharpe >= LS23 的 1.9448；
3. 20bps MDD <= LS23 的 -39.84% + 5pp；
4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 LS23；
6. 100bps MDD <= 50%；
7. 3x short-adverse 0 强平且 MDD <= 50%；
8. 删除任一最佳年份后终值仍高于同成本 LS23；
9. 365 天滚动最差 >= LS23 的 0.8551x；
10. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
11. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过 LS23，12/12 MDD 5pp；
12. 单资产空头贡献 <= 50%，前 3 <= 80%；
13. observed gross <=1.50 且无 gross breach hour；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月真实 OOS 未满前最高只能 provisional。

## 3. 失败后动作

如果 LS27 在 20bps 三项主门槛中失败，停止该组合，不扫描等权比例、空头预算、bottom-N、stop、
regime 或再分配规则；保留组件结果和失败证据，继续提出新的独立信息源或风险层。

不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS27-H5-PROFIT-LOCK-DYNAMIC-SHORT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_profit_lock_dynamic_short
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
