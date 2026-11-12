# Atlas20 候选预注册：LS23 优先 + 剩余 gross funding carry

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS33-H5-LS23-RESIDUAL-CARRY-LONG60` |
| 对照 ID | `PR2026-11-LS33C-H5-LS23-LONG60-CONTROL` |
| 基线 | L125；LS23 为当前最强 candidate |
| 多头 | 冻结 H5 1.25x + LS22 单一龙头利润保护 |
| 基础空头 | 冻结 LS12 BTC-200D 双空头 router，总空头 <=0.25x |
| 新增 sleeve | 冻结 LS31 的 7D market-neutral funding carry |
| 预算优先级 | LS23 基础多空先占用 gross；carry 只能用剩余 gross 和未重叠资产 |
| 总预算 | hard total gross 1.50x |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS23 20bps 为 **61.9150x / 1.9448 / -39.84% / 0 强平**，但 LS23 的 target gross 审计显示：

- 中位 total gross **0.4738x**；
- 75th percentile **0.7410x**；
- 最大 **1.3000x**；
- 平均 **0.5329x**。

也就是说，LS23 大多数时间没有用满 1.50x hard gross。LS30/LS31 的问题不是 carry 完全无效，
而是 standalone carry 无法超过 LS23，且自身有 turnover 和 long-tail risk。LS33 因此检验：

> 保留已冻结的 LS23 作为最高优先级 alpha；只把 LS23 未使用的 gross 分配给 LS31 carry，
> 是否能在不显著增加回撤的情况下提高收益。

这不是扫描 LS23 profit-lock、short router、carry lookback/rank/count/weight 或 buffer，而是一个新的
组合预算问题。

## 1. 冻结构造

```text
base(D) = LS23 H5_long(D) + LS12_short(D)
base_gross(D) = sum(abs(base(D)))

carry_candidates(D) = LS31 7D funding carry target
carry(D) = carry_candidates(D) with any asset already present in base(D) removed
available(D) = max(0, 1.50 - base_gross(D))
carry_scale(D) = min(1, available(D) / gross(carry(D)))
combined(D) = base(D) + carry_scale(D) * carry(D)
```

- carry 选择完全继承 LS30/LS31：PIT Top20 非 H5 持仓，7D mean funding，lowest 2 long / highest 2
  short，每腿 6.25% NAV，周频 7D，min_assets 8，min_settlements 3；
- base 和 carry 若在任何方向持有同一资产，carry 腿被移除，不做暗净额化；
- LS23 从不被 carry 缩放或替换；
- carry 只获得 `1.50 - base_gross` 的剩余 gross，最多 0.25x；
- 60% long buffer 应用于多头；这是为 carry long 尾部留空间，LONG60 control 用于隔离其影响；
- short stop 20%；不新增 long stop；
- T+1 UTC +3h；hard total gross 1.50x；
- 不扫描 carry 的 2/3/4 币、6.25% 权重、lookback、min_assets、stop 或 buffer。

## 2. 对照

`PR2026-11-LS33C-H5-LS23-LONG60-CONTROL` 与 LS33 完全相同，但关闭 carry sleeve。
它只用于回答“60% long buffer 本身是否改变了 LS23 的相对结果”，不是新的 promotion candidate。

LS33 必须同时胜过 L125、LS23 和 LS33C 的 20bps 结果，才能说明增量来自 carry 而不是 buffer。

## 3. 预注册门槛

研究价值（20bps）：

1. LS33 终值 > LS23 的 61.9150x；
2. LS33 终值 > LS33C control；
3. Sharpe >= max(LS23 1.9448, LS33C control)；
4. MDD 不得比 LS23 的 -39.84% 恶化超过 5pp，即不差于 -44.84%。

风险与成本：

5. 主样本 0 次强平；
6. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
7. 2/20/50/100bps 终值和 Sharpe 均不低于同成本 LS23；
8. 100bps MDD <=50%；
9. 3x short-adverse 0 强平且 MDD <=50%；
10. observed gross <=1.50 且无 gross breach hour。

稳健性：

11. 删除任一最佳年份后终值仍高于 L125；
12. 365 天滚动最差 >= L125 的 0.7325x；
13. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
14. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过 L125，12/12 MDD 5pp；
15. 单资产空头贡献 <=50%，前 3 <=80%；
16. PBO/CSCV <=0.50，White Reality Check p <=0.05；
17. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
18. 12 个月真实 OOS 未满前最高只能 provisional。

## 4. 失败后动作

如果 LS33 的 20bps 终值不超过 LS23 或不超过 LS33C，停止 residual-carry 预算家族，不扫描
carry count/weight/lookback、gross priority、buffer 或 long stop。

如果 LS33 只在 20bps 通过、但高成本或路径失败，仍判 rejected，不能因为主样本收益好看而放宽成本门。

不修改当前实盘 `PR2026-10-D-L125-V2`。

## 5. 复现

```bash
# primary
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS33-H5-LS23-RESIDUAL-CARRY-LONG60 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_residual_carry

# buffer-only control
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS33C-H5-LS23-LONG60-CONTROL \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_residual_carry/control
```

## 6. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
