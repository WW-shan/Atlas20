# Atlas20 候选 LS20：H5 selection-event common-gross 再平衡

日期：2026-11-12  
候选：`PR2026-11-LS20-H5-COMMON-GROSS`  
状态：**rejected（主收益门槛失败）**  
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS20 只在 H5 持币集合不变时保留旧相对权重，并按新 target gross 统一缩放；选币变化和 gross
变化仍精确执行。20bps：

- **39.4148x / 1.7683 / -40.56%**；
- L125：40.2200x / 1.7330 / -40.65%；
- 终值低于 L125 约 2.0%，主收益门槛失败；
- 0 强平、0 gross breach；
- 跳过 329 个 relative-weight tilt 事件，累计 skipped relative L1 59.9654x（事件口径）。

Sharpe 和 MDD 略优，但收益不足，因此按预注册直接 rejected。

## 二、预注册

- Spec：`docs/superpowers/specs/2026-11-11-h5-common-gross-design.md`
- spec hash：`c5411b8a7bf572388cd89d69ea44111aeb43a92079f9f21a3f8ef681a67df9a7`
- registration hash：`69ebabc4bdff650fa2de864f0d5234b888d3e6617d8d2b54ba5a9dfed74d2f85`
- registered at：`2026-11-11T16:58:51Z`

## 三、机制

```text
if selected_set(D) != selected_set(previous):
    adjusted(D) = target(D)
else:
    adjusted(D) = previous_adjusted * target_gross(D) / previous_adjusted_gross
```

H5 选币、总 gross 变化、LS12 空头 router、20% short stop、buffer、gross cap 和执行时点均不变。
LS16 的 5% 距离阈值不在这里使用；LS20 不设置任何距离参数。

## 四、20bps 结果

| 指标 | L125 | LS20 |
|---|---:|---:|
| 终值 | 40.2200x | 39.4148x |
| Sharpe | 1.7330 | **1.7683** |
| MDD | -40.65% | **-40.56%** |
| 强平 | 0 | 0 |
| max observed gross | 1.2811x | 1.3324x |
| gross breach hours | 0 | 0 |
| fees | 1.5861 | 2.1608 |
| funding total | -0.5918 | -0.5904 |

## 五、解释

换手审计显示 same-set relative tilt 足够大（45.68% of long target L1），但真正被跳过的相对调权
仍承担了收益和风险控制的信号作用。保留旧相对权重虽然稍微改善 Sharpe/MDD，却让终值低于基线；
这是一次有效的负结果：H5 的币间相对调权不能被简单视为噪声。

## 六、未继续执行的阶段

LS20 已触发 20bps 终值失败，因此按预注册：

- 不运行 2/50/100bps；
- 不运行 funding stress、路径、冷启动或 PBO/RC/DSR；
- 不扫描 selection 定义、common-gross 规则、长/短不同处理或频率；
- 不接入执行器或修改实盘。

## 七、最终判定

**LS20 rejected。**

common-gross 不能替代 H5 的相对权重调仓来保持收益。当前 `PR2026-10-D-L125-V2` 保持不变。
