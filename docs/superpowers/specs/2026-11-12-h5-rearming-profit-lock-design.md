# Atlas20 候选预注册：H5 单龙头重新武装利润保护

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS26-H5-REARMING-PROFIT-LOCK` |
| 基线 ID | `PR2026-10-D-L125` |
| 基础 alpha | 冻结 H5 1.25x 多头 |
| 新机制 | 同一龙头极端涨幅减半；21D 回落至 <100% 后解除，下一次再 >=100% 才重新减半 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | target <=1.25x；hard 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS22 在同一龙头持续 >=100% 时，每个 H5 目标事件都会重新减半，2022-01-01 → 2026-09-21
共触发 57 次。LS25 把锁保持到龙头切换，触发次数降到 17 次，但锁得过久，20bps 终值
35.1755x、MDD -41.15%，被拒绝。

LS26 检验一个不使用新阈值的中间状态机：

> 同一龙头首次达到 21D trailing return >=100% 时减半；如果后续 21D return 回落至 <100%，
> 解除锁并恢复当前 H5 target；只有再次回到 >=100% 时才重新触发一次新的减半。

这样避免同一极端区间内每次事件都 trim，同时在动量降温后允许恢复仓位。100% 是 LS22 已冻结的
触发阈值，不是新扫描参数。

## 1. 冻结构造

```text
base = frozen H5 1.25x long-only
locked_leader = none
for each H5 target event D:
    leader = largest target weight
    if leader changes or target becomes empty:
        locked_leader = none
    r21 = trailing 21D return of leader
    if locked_leader == leader:
        if r21 is available and r21 < 1.0:
            locked_leader = none
            output = target
        else:
            output[leader] = target[leader] * 0.5
    elif r21 >= 1.0:
        output[leader] = target[leader] * 0.5
        locked_leader = leader
    else:
        output = target
    other weights unchanged
```

- 缺失/不可用价格不触发首次减半；已锁定时也不因缺价解除；
- 释放权重留现金，不转入其他币；
- 不改变 H5 选币、相位、波动率缩放、dispersion、BTC gate、T+1 或成本。

## 2. 预注册门槛

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

## 3. 失败后动作

如果 LS26 失败：

- 不扫描 75%/87%/100%/125%、lookback、scale、release 阈值或再分配；
- 停止“单龙头极端涨幅减半”状态机家族；
- 提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS26-H5-REARMING-PROFIT-LOCK \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_rearming_profit_lock
```

## 5. 状态

- 预注册：是；
- 正式运行：是；
- 结果：rejected / duplicate（与 LS22 日收益完全相同）；
- 实盘：否；
- 修改当前实盘：否。
