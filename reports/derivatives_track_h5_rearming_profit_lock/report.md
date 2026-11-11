# LS26：H5 单龙头重新武装利润保护（rejected / duplicate）

候选：`PR2026-11-LS26-H5-REARMING-PROFIT-LOCK`  
基线：`PR2026-10-D-L125`  
主样本：2022-01-01 → 2026-09-21（UTC）  
成本：20bps；Bitget mark；Binance funding proxy/skip；T+1 UTC +3h

## 构造

LS26 在同一龙头首次达到 21D trailing return >=100% 时减半；如果后续 21D return 回落至
<100%，解除锁并恢复当前 H5 target；再次回到 >=100% 时重新减半。它使用 LS22 已冻结的
100% 阈值，没有新增 release 参数，也没有扫描。

## 结果：与 LS22 行为等价

| 策略 | 终值 | Sharpe | MDD | trim 计数 | locked 事件 | max observed gross | 强平 |
|---|---:|---:|---:|---:|---:|---:|---:|
| LS22 | 44.6607x | 1.8257 | -39.84% | 57 | — | — | 0 |
| **LS26** | **44.6607x** | **1.8257** | **-39.84%** | **22** | **57** | **1.2811x** | **0** |

LS26 的日收益与 LS22 完全相同（1724 个日收益，最大差 0.0）。原因不是实现错误，而是数学等价：

- LS22 在每个 21D >=100% 的事件都把当前 H5 target 减半；
- LS26 在同一区间保持“当前 H5 target 的一半”，并在 <100% 时释放；
- 因此两者在所有 >=100% 的目标事件上产生相同的权重路径，只是 LS26 把“首次触发”和“持续
  locked 事件”分开计数：22 次初始化、57 个半仓事件，而 LS22 把 57 个事件都记成 trim。

## 判定

**rejected / duplicate。** 这不是新的收益机制，也没有改善 LS22 的任何指标；不运行
2/50/100bps、funding stress、路径、冷启动或 PBO/RC/DSR，不把它当作新的独立候选或救活
LS25。保留该实现和报告，是为了把“重复 trim”与“状态化锁”的等价关系记录清楚。

不修改当前实盘 `PR2026-10-D-L125-V2`。

## 产物

- `PR2026-11-LS26-H5-REARMING-PROFIT-LOCK/summary.json`
- `PR2026-11-LS26-H5-REARMING-PROFIT-LOCK/profit_lock_audit.csv`
- `PR2026-11-LS26-H5-REARMING-PROFIT-LOCK/daily_returns.csv`
