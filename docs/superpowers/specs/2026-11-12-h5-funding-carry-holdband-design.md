# Atlas20 候选预注册：H5 + 低换手 market-neutral funding carry（2x 持有带）

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS32-H5-FUNDING-CARRY-HOLD4-LONG60` |
| 基线 | L125（`PR2026-10-D-L125`） |
| incumbent | LS23（`PR2026-11-LS23-H5-PROFIT-LOCK-REGIME-SHORT`） |
| 多头 | 冻结 H5 1.25x；long buffer 60% |
| 中性 sleeve | LS31 完全相同的 7D funding carry，但使用 2x entry-count 持有带控制换腿 |
| 总预算 | long 1.25x + sleeve 0.25x = 1.50x hard total gross |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS31 的 20bps 路径已经解决 LS30 的 DOT long 强平，并取得 **48.9593x / 1.8168 / -40.13%**，
但 50bps 终值 **26.3191x** 低于 L125 的 27.3725x，100bps **9.3188x / 1.1491 / -56.40%**
同时低于 L125 的终值、Sharpe 和 50% MDD kill line。20bps 的优势不能抵消高成本失败。

只读换手审计显示 LS30/LS31 的 carry 目标本身不是低换手：

- 316 个周度目标，315 个发生目标变化；
- carry 目标累计 L1 变化 **70.5x NAV**；
- 多头 name changes **440**，空头 name changes **688**；
- 空头 open **381**、stop **48**。

主要问题不是 funding 方向失效，而是相近 funding 排名之间的机械换腿。LS32 因此只改变 carry
sleeve 的持仓持续性：

> 已有 carry 腿仍在当前横截面的前/后 4 名内时继续持有；跌出持有带才替换。新开仓仍只选
> 最低 2 / 最高 2；不扫描持有带宽度。

## 1. 为什么是 2x entry count

持有带宽度 `hold_count = 2 × count = 4` 不是收益扫描结果：

- entry count 已在 LS30 预注册冻结为 2；
- 2x 是项目已有的结构惯例，R7 使用过 4 名入场 / 8 名持有的同型缓冲；
- 持有带与 min_assets=8 相容：最低 4 名和最高 4 名在 8 个合格资产时仍不重叠；
- 只改变“何时替换已有腿”，不改变 funding score、方向、腿数、权重、成本或总 gross。

LS32 不扫描 hold_count 3/5/6/8，也不扫描 2x 之外的 entry/exit 缓冲。

## 2. 冻结构造

```text
H5_long = frozen H5 1.25x, long_buffer=0.60
carry_universe(D) = PIT Top20 members at D, excluding H5 holdings at D
score_i(D) = mean Binance funding settlement in [D-7D, D)
eligible_count(D) >= 8 and each score has >= 3 settlements

if no incumbent on a side:
    open lowest 2 (long) / highest 2 (short)
else:
    keep an incumbent while it remains in lowest 4 (long) or highest 4 (short)
    fill each vacancy from lowest/highest eligible names not already held
w_i = +0.0625 for two long carry legs
w_i = -0.0625 for two short carry legs
```

- 每 7 天评估，anchor = 2022-01-01；
- carry 只使用 H5 之外的资产；进入 H5 或离开 PIT Top20 时由既有 exclusions router 提前退出；
- 至少 8 个可交易、有 funding、非 H5 持仓的成员才开仓，否则 sleeve 空仓；
- funding 缺失不插值、不填零；
- short 腿使用 20% adverse mark stop；long 腿无单独 stop；
- 总 gross 按 long + |carry| 计，hard cap 1.50x；
- 其余执行规则完全继承 LS31。

## 3. 预注册门槛

研究价值门槛（20bps）：

1. 终值必须 **高于 LS23 的 61.9150x**；
2. Sharpe 必须 **不低于 LS23 的 1.9448**；
3. MDD 不得比 LS23 的 -39.84% 恶化超过 5pp，即不得差于 -44.84%。

风险与成本门槛：

4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
6. 2/20/50/100bps 终值和 Sharpe 均不低于同成本 LS23；
7. 100bps MDD <= 50%；
8. 3x short-adverse 0 强平且 MDD <= 50%；
9. observed gross <=1.50 且无 gross breach hour。

稳健性门槛：

10. 删除任一最佳年份后终值仍高于 L125；
11. 365 天滚动最差 >= L125 的 0.7325x；
12. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
13. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过 L125，12/12 MDD 5pp；
14. 单资产空头贡献 <=50%，前 3 <=80%；
15. PBO/CSCV <=0.50，White Reality Check p <=0.05；
16. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
17. 12 个月真实 OOS 未满前最高只能 provisional。

如果 LS23 的旧多重检验结果因 trial count 更新而变化，LS32 必须使用更新后的 LS23 对照值，
不能用旧 N 下的数字制造优势。

## 4. 失败后动作

如果 LS32 的 20bps 终值或 Sharpe 低于 LS23，停止该 funding-carry 持有带家族，不扫描
hold_count、lookback、rank、count、腿权重、min_assets、stop、buffer 或再平衡周期。

如果 LS32 只修复高成本但没有超过 LS23，仍判 rejected；它是研究资产而不是 promotion candidate。

不修改当前实盘 `PR2026-10-D-L125-V2`。

## 5. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS32-H5-FUNDING-CARRY-HOLD4-LONG60 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_carry_holdband
```

## 6. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
