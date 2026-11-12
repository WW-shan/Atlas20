# Atlas20 LS39：LS23 + 60D 低波动多空 sleeve

日期：2026-11-12
候选：`PR2026-11-LS39-H5-LS23-LOWVOL-PAIR`
状态：**rejected（20bps 主样本即触发 3 次多头强平）**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS39 把冻结 LS23 作为 base book，只在剩余、非重叠 gross 中加入一个 28D 月度低波动 pair：
60D 日对数收益波动率最低 4 名做多、最高 4 名做空，每腿 2.5% NAV。规则在运行前冻结；60D 来自
H5 已使用的风险窗口，28D/4×4 是单一月度低换手构造，没有做参数扫描。

20bps 主样本的表面收益和风险指标改善：

| 策略 | 终值 | Sharpe | MDD | 强平 | max gross | gross breach |
|---|---:|---:|---:|---:|---:|---:|
| LS23 | 61.9150x | 1.9448 | -39.84% | 0 | 1.3308x | 0 |
| LS39 | **64.2279x** | **1.9731** | **-37.65%** | **3** | 1.4938x | 0 |

但预注册的“0 次强平”是硬门槛。3 次强平全部来自低波动腿的 **long**，不是 high-vol short：

- 2022-06-18 17:00 UTC：BTC long，entry 37,182.05，liquidation 18,609.42；
- 2025-04-09 01:00 UTC：ETH long，entry 2,789.85，liquidation 1,387.01；
- 2025-10-10 21:00 UTC：TON long，entry 3.1167，liquidation 1.5269。

这些不是数据错误，也不是引擎超出 gross cap。当前实盘用 2x isolated venue leverage 实现 1.25x
notional 与 50% long buffer；任何低波动 long 腿如果在两次 28D rebalance 之间接近腰斩，就会在
isolated margin 下被清算。LS39 的额外多头正是把“低波动”误当成“没有长尾”，忽略了杠杆化的
持仓路径风险。

**判定：rejected。** 20bps 表面增量不足以抵消结构性清算风险；不运行 2/50/100bps、funding stress、
路径、冷启动或 PBO/RC/DSR，也不修改实盘。

## 二、成本与换手诊断

| 指标 | LS23 | LS39 |
|---|---:|---:|
| 20bps 终值 | 61.9150x | 64.2279x |
| 20bps Sharpe | 1.9448 | 1.9731 |
| fees total | 3.1262 | 3.5980 |
| short opens | 335 | 450 |
| short stops | 29 | 111 |
| funding total | -0.7465 | -0.7243 |

低波动 sleeve 增加了短腿止损次数和实际换手，且把低波 long 暴露推向 isolated liquidation。
改善后的 MDD 是样本路径结果，不能抵消“先发生强平”的执行事实。

## 三、失败后动作

按预注册规则，停止 LS39 的 60D/28D/4×4 低波动 pair 家族：

- 不扫描 20/30/40/90/120D lookback；
- 不扫描 2/3/5/6 个 leg，不扫描权重；
- 不扫描 14D/21D/56D rebalance；
- 不尝试事后把 long leg 删除、缩小或加未注册的长止损；
- 不把 LS39 当作 LS23 的替代或 promotion candidate。

保留 LS23 作为主样本 incumbent，继续研究真正独立、且与现有 isolated margin 执行模型兼容的
alpha 来源。

## 四、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS39-H5-LS23-LOWVOL-PAIR \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_lowvol_pair
```

输出目录：`reports/derivatives_track_h5_ls23_lowvol_pair/PR2026-11-LS39-H5-LS23-LOWVOL-PAIR/`。
