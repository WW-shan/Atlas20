# Atlas20 候选 LS18：H5 多头内部 funding 拥挤去权重

日期：2026-11-12  
候选：`PR2026-11-LS18-H5-FUNDING-TILT`  
状态：**rejected（主收益门槛失败）**  
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS18 在每个 H5 目标事件日，把 funding 位于 PIT Top20 上三分之一且为正的 H5 多头腿减半，
再把释放权重分配给同书非拥挤持仓，单币上限 60%，无法分配的部分留现金。它降低了 funding 成本
和 drawdown，但收益下降过多：

- 20bps：**34.6700x / 1.7700 / -33.05% / 0 强平**；
- L125：40.2200x / 1.7330 / -40.65%；
- Sharpe 和 MDD 改善，但终值低于 L125 **13.8%**，第一门槛失败。

LS18 只运行主成本；按预注册不再运行 2/50/100bps、funding stress、路径、冷启动或
multiple-testing。long-leg funding tilt 家族停止。

## 二、预注册

- Spec：`docs/superpowers/specs/2026-11-11-h5-funding-tilt-design.md`
- spec hash：`ba3b6685749627f8c11eda2486cff1fb2be2b1c6c2a2ede87ef13278a25a151b`
- registration hash：`75e329cbe44ca54f47e4464cf70c1277710a4f88212ef4ef3111cf6a8228c1d8`
- registered at：`2026-11-11T16:38:42Z`

运行前可行性审计：

- 1,053 个 H5 holding-events，511 个事件日；
- 325 个 crowded holding-events，覆盖 256 个事件日；
- 触发时释放 gross 中位数 31.25%，90 分位 50%；
- 触发资产分散，不是单一名目事件。

## 三、冻结构造

```text
crowded_i = funding_rank_i >= 2/3 and mean_funding_7d_i > 0
w_i' = 0.5 * w_i                    if crowded_i
w_i' = w_i                          otherwise
freed = sum(w_i - w_i')
allocate pro rata to non-crowded H5 legs
cap each recipient at 0.60 NAV
unallocated = cash
```

H5 选币、LS12 双空头 router、20% short stop、short buffer、gross cap 和执行时点均不变。

## 四、20bps 结果

| 指标 | L125 | LS18 | 变化 |
|---|---:|---:|---:|
| 终值 | 40.2200x | 34.6700x | **-13.8%** |
| Sharpe | 1.7330 | **1.7700** | +0.037 |
| MDD | -40.65% | **-33.05%** | +7.60pp |
| 强平 | 0 | 0 | — |
| max observed gross | 1.2811x | 1.3305x | 信息项 |
| gross breach hours | 0 | 0 | 通过 |
| funding total | -0.5918 | **-0.4436** | 成本改善 |
| fees | 1.5861 | 2.2429 | 高于 L125 |

542 个目标事件全部记录；325 个 crowded leg 被减半。累计未分配 cash weight 为 20.3969
（事件权重之和，不是时间平均值）。

## 五、解释

funding 拥挤腿往往是强势/高关注资产；减半和同书再分配降低了组合尾部，但也削掉了复利的主要来源。
“减少 funding 成本”本身不等于“提高股东回报”。LS18 与 LS13/LS14/LS15 一样，属于收益不足的风险
变体，而不是可晋级的收益增强。

## 六、失败后动作

按预注册：

- 不扫描 crowded rank、lookback、减半比例、单币 cap 或再分配规则；
- 不运行 2/50/100bps、路径、冷启动、PBO/RC/DSR；
- 停止 long-leg funding tilt 家族；
- 当前实盘保持 `PR2026-10-D-L125-V2`。

## 七、最终判定

**LS18 rejected。**
