# LS25：H5 单龙头状态化利润保护（rejected）

候选：`PR2026-11-LS25-H5-STATEFUL-PROFIT-LOCK`  
基线：`PR2026-10-D-L125`  
主样本：2022-01-01 → 2026-09-21（UTC）  
成本：20bps；Bitget mark；Binance funding proxy/skip；T+1 UTC +3h

## 构造

LS22 在每次 H5 目标事件都重新检查最大持仓，同一龙头持续极端上涨时会被反复减半。LS25 只修正
这一点：同一连续龙头首次达到 21D trailing return >=100% 后，保持该腿为当前 H5 target 的
0.5 倍；龙头切换后重置，新龙头重新判断。释放权重留现金，不分配、不做空。

## 结果

| 策略 | 终值 | Sharpe | MDD | trim 次数 | max observed gross | 强平 |
|---|---:|---:|---:|---:|---:|---:|
| L125 baseline | 40.2200x | 1.7330 | -40.65% | 0 | — | 0 |
| LS22（每次事件重判） | 44.6607x | 1.8257 | -39.84% | 57 | — | 0 |
| LS23（LS22 + LS12 short） | 61.9150x | 1.9448 | -39.84% | 57 | 1.3308x | 0 |
| **LS25（状态化锁）** | **35.1755x** | **1.7691** | **-41.15%** | **17** | **1.2811x** | **0** |

LS25 把重复 trim 从 57 次降到 17 次，但没有改善收益：终值比 L125
低 5.0445x，MDD 比 L125 差 0.50%。
Sharpe 略高于 L125，但第一收益门槛和 MDD 容忍线失败，不能靠加入 LS12 空头或继续调 lock 状态来救活。

## 判定

**rejected。** 不运行 2/50/100bps、funding stress、删除年份、滚动窗口、45 路径、冷启动或
PBO/RC/DSR；不扫描阈值、lookback、scale、release 规则或再分配。状态化单龙头利润保护家族停止。
不修改当前实盘 `PR2026-10-D-L125-V2`。

## 产物

- `PR2026-11-LS25-H5-STATEFUL-PROFIT-LOCK/summary.json`
- `PR2026-11-LS25-H5-STATEFUL-PROFIT-LOCK/profit_lock_audit.csv`
- `PR2026-11-LS25-H5-STATEFUL-PROFIT-LOCK/daily_returns.csv`
