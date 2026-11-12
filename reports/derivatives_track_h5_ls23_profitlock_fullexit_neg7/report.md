# PR2026-11-LS44-H5-LS23-PROFITLOCK-FULLEXIT-NEG7

- 状态：**rejected at 20bps**
- 基线：L125；LS23；LS42/LS43 仅作机制对照
- 主样本：2022-01-01 → 2026-09-21（UTC），20bps
- 机制：LS22 21D/100% 触发后，如果被减半龙头的 7D return < 0，则该腿完全退出；否则维持原来的 0.5 scale

## 结果

| 指标 | LS23 | LS44 |
|---|---:|---:|
| 终值 | **61.9150x** | 60.5213x |
| Sharpe | **1.9448** | 1.9361 |
| MDD | -39.84% | **-39.056%** |
| 强平 | 0 | 0 |
| trim | 57 | 57 |
| full exit | 0 | 9 |
| 释放权重 | 9.2432 | 10.4255 |
| max observed gross | 1.3308x | 1.3308x |
| gross breach hours | 0 | 0 |
| fees total | 3.1262 | **3.0791** |

LS44 在 9 次 7D 转负事件中完全退出，MDD 改善约 **0.78pp**，费用也略低；但终值比 LS23 低约
**2.25%**，Sharpe 低 **0.0087**，20bps 主收益和 Sharpe 门槛同时失败。

## 判定

**rejected。** 7D 转负并不能稳定地证明剩余一半必然继续下跌；事件审计的负均值不足以抵消路径依赖
和提前退出后的机会成本。按预注册不运行 2/50/100bps、funding stress、路径、cash-start 或
PBO/RC/DSR，不扫描 5D/10D/14D、confirmation 阈值、scale 0.25/0.75 或再分配规则。

停止“极端涨幅 + 短周期 breakdown 全退”家族，保留 LS23；不修改 `PR2026-10-D-L125-V2`。

报告仅用于研究，不是订单或实盘批准。
