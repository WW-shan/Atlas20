# Atlas20 候选预注册：LS23 + 5% NAV same-side no-trade band

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS38-H5-LS23-NOTRADE5` |
| 基线 | L125；LS23 |
| 基础 book | 冻结 LS23：H5 1.25x 利润保护 + LS12 双空头 router |
| 新机制 | 已有多空同方向仓位只在偏离目标超过 5% NAV 时交易，并只交易到容差边界 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS33–LS37 已经证明：在 LS23 上增加任何持续 carry sleeve，20bps 可以提高，但 100bps 都会把
base LS23 推过成本尾部。LS23 本身在 100bps 已为 **15.5037x / 1.3745 / -49.48%**，非常接近
50% MDD kill line。

LS38 不再增加 alpha sleeve，只改变执行：对已存在的同方向仓位使用 5% NAV 容差区，减少同方向
权重的噪声交易；开仓、清仓、反手和 H5 选币变化仍精确执行。5% 是项目已冻结的 H5 单币权重容差，
不是收益扫描后选择的阈值。

## 1. 冻结构造

```text
base(D) = 冻结 LS23
target(D) = base(D)

execution:
  if no position or side change: execute target exactly
  else if |target_notional - current_notional| <= 0.05 * equity: do not trade
  else: trade only to the 5%-NAV boundary
```

- 开仓、清仓、反手永远精确执行；
- 当前或交易后 projected gross 超过 1.50x 时放弃容差，执行精确目标；
- 5% 容差绝不放宽 margin、stop、funding、强平或 Top20 约束；
- LS23 的 H5 1.25x、LS22 利润保护、LS12 router、20% stop、50% buffer 全部冻结；
- 不扫描 no-trade 1%/2.5%/7.5%/10%/15%，也不把容差只用于多头或空头。

## 2. 预注册门槛

研究价值（20bps）：

1. LS38 终值 >= LS23 的 61.9150x；
2. Sharpe >= LS23 的 1.9448；
3. MDD 不得比 LS23 的 -39.84% 恶化超过 5pp，即不差于 -44.84%。

风险与成本：

4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均不低于同成本 LS23；
6. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
7. 100bps 终值 > LS23 的 15.5037x，Sharpe > 1.3745，MDD <=50%；
8. 3x short-adverse 0 强平且 MDD <=50%；
9. observed gross <=1.50 且无 gross breach hour。

稳健性：

10. 删除任一最佳年份后终值仍高于 L125；
11. 365 天滚动最差 >= L125 的 0.7325x；
12. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
13. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过 L125，12/12 MDD 5pp；
14. 单资产空头贡献 <=50%，前 3 <=80%；
15. PBO/CSCV <=0.50，White Reality Check p <=0.05；
16. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
17. 12 个月真实 OOS 未满前最高只能 provisional。

LS38 必须至少不弱于 LS23；如果 20bps 低于 LS23，不能因为 100bps 可能更好就保留。

## 3. 失败后动作

如果 LS38 不满足 20bps LS23 对比，或 100bps 任一门槛失败，停止 LS23 no-trade 家族，不扫描
容差、只多头/只空头、事件阈值或再平衡频率。保留 LS23 作为 incumbent，不修改实盘。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS38-H5-LS23-NOTRADE5 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_notrade5
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
