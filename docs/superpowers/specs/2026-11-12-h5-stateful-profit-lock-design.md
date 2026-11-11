# Atlas20 候选预注册：H5 单龙头状态化利润保护

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS25-H5-STATEFUL-PROFIT-LOCK` |
| 基线 ID | `PR2026-10-D-L125` |
| 基础 alpha | 冻结 H5 1.25x 多头 |
| 新机制 | 同一龙头首次触发 21D >=100% 后，保持半仓直到龙头切换 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | target <=1.25x；hard 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS22 在每个 H5 目标事件都会重新检查最大持仓；如果同一龙头持续满足 21D >=100%，它会被
反复减半。2026-09-22 → 2026-11-10 的 50 天 shadow OOS 中，同一 `near` 龙头触发了 8 次
trim，产生不必要的换手和现金拖累。LS25 只检验一个结构修正：

> 同一连续龙头期间，首次触发极端涨幅时减半；之后只要龙头没有切换，就保持该腿为当前 H5
> target 的一半，不重复触发新的 trim；龙头切换后重置状态，新龙头重新判断。

这不是对 LS22 阈值的扫描，也不改变 H5 选币、相位、波动率缩放、dispersion、BTC gate 或 T+1。

## 1. 参数来源与冻结

- 21D / 100% / 0.5 全部沿用已冻结 LS22；
- 不扫描阈值、lookback、scale、top-2/top-3 或再分配；
- 同一事件最大权重并列时，按 coin id 字典序取第一个；
- 缺失/不可用价格不触发首次 trim；已锁定的同一龙头仍按当前 H5 target 的 0.5 保持；
- 释放权重留现金，不转入其他币。

## 2. 冻结构造

```text
base = frozen H5 1.25x long-only
locked_leader = none
for each H5 target event D:
    leader = largest target weight
    if leader changes or target becomes empty:
        locked_leader = none
    if locked_leader == leader:
        output[leader] = target[leader] * 0.5
    elif r21(leader, D) >= 1.0:
        output[leader] = target[leader] * 0.5
        locked_leader = leader
    else:
        output = target
    other weights unchanged
```

## 3. 预注册门槛

1. 20bps 终值 > L125；
2. 20bps Sharpe >= L125；
3. 20bps MDD <= L125 +5pp；
4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
6. 100bps MDD <=50%；
7. 删除任一最佳年份后终值仍高于同成本 L125；
8. 365 天滚动最差 >= L125；
9. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
10. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过基线，12/12 MDD 5pp；
11. observed gross <=1.50 且无 gross breach hour；
12. PBO/CSCV <=0.50，White Reality Check p <=0.05；
13. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
14. 12 个月真实 OOS 未满前最高只能 provisional。

## 4. 失败后动作

如果 LS25 失败：

- 不扫描阈值、lookback、scale、持仓数量、并列规则或再分配；
- 停止“状态化单龙头利润保护”家族；
- 提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 5. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS25-H5-STATEFUL-PROFIT-LOCK \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_stateful_profit_lock
```

## 6. 状态

- 预注册：是；
- 正式运行：是；
- 结果：rejected（20bps 终值和 MDD 失败）；
- 实盘：否；
- 修改当前实盘：否。
