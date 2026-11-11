# Atlas20 候选 LS19：H5 + 28D 横截面反转多空 sleeve

日期：2026-11-12  
候选：`PR2026-11-LS19-H5-REVERSAL-PAIR`  
状态：**rejected（收益与强平失败）**  
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS19 按 S3 的“约一个月反转”构造：H5 1.25x 保留，另外做多 4 个最弱、做空 4 个最强的 PIT Top20
非 H5 资产，每腿 2.5% NAV，28 天再平衡，target gross 1.45x。20bps 结果：

- **37.3924x / 1.6969 / -40.15%**；
- L125 为 40.2200x / 1.7330 / -40.65%；
- 终值和 Sharpe 都低于基线，第一门槛失败；
- **11 次强平**，全部发生在反转 long loser 腿；
- 292 个 short open、90 个 short stop。

按预注册直接 rejected，不继续成本档或稳健性阶段。

## 二、预注册

- Spec：`docs/superpowers/specs/2026-11-h5-reversal-pair-design.md`
- spec hash：`5d39aa0106a45f42645e3e0322d2c87a99a5d4ed8bfe7098e8f61c6e6028560a`
- registration hash：`bf8892b568cee8ef95f10fcbc35d904c8dcb7e57c28cbf85470a698c362332aa`
- registered at：`2026-11-11T16:52:41Z`

外部依据 S3：正动量约持续 2–4 周，超过一个月后出现反转，且反转主要由过去输家驱动。LS19 固定
28D lookback/28D rebalance、4×4、2.5%/leg，不扫描参数。

## 三、冻结构造

```text
eligible = PIT Top20 ∩ Bitget mark available ∩ not current H5 long
r28_i = close_i(D) / close_i(D-28) - 1

long  = four lowest r28_i, +2.5% NAV each
short = four highest r28_i, -2.5% NAV each
H5    = frozen 1.25x long book
target gross <=1.45x; hard observed <=1.50x
short stop = 20%
```

## 四、结果与失败原因

| 指标 | L125 | LS19 |
|---|---:|---:|
| 终值 | 40.2200x | 37.3924x |
| Sharpe | 1.7330 | 1.6969 |
| MDD | -40.65% | -40.15% |
| 强平 | 0 | **11** |
| max observed gross | 1.2811x | 1.4965x |
| gross breach hours | 0 | 0 |
| short open / stop | 0 / 0 | 292 / 90 |

11 次强平全部是 **long loser** 腿：

- 2022 年 10 次（SOL、ATOM、LINK、ADA、UNI、NEAR 等）；
- 2023 年 SHIB 1 次；
- 2024 年 INTERNET-COMPUTER 1 次；
- 2025-10-10 有 2 次（LINK、TON）。

反转 long 腿虽然捕获部分反弹，但在高波动/级联行情中会先被强平，无法等到反转完成。

## 五、未继续执行的阶段

LS19 已触发 20bps 终值/Sharpe 和 11 次强平硬失败，因此按预注册：

- 不运行 2/50/100bps；
- 不运行 funding stress、路径切片、冷启动或 PBO/RC/DSR；
- 不扫描 lookback、rebalance、4 币数量、单腿权重、stop、H5/factor 比例；
- 不接入执行器或修改实盘。

## 六、最终判定

**LS19 rejected。**

28D reversal pair 在 Top20 上不能提供稳定的增量收益，且 long loser 腿的尾部强平风险显著。
当前 `PR2026-10-D-L125-V2` 保持不变。
