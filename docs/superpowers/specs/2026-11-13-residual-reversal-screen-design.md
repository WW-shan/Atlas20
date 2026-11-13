# Atlas20 研究预注册：PIT Top20 residual reversal screen

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 新假设预注册；不是实盘候选；不修改 live |
| 候选 ID | `PR2026-11-LS61-RESIDUAL-REVERSAL-SCREEN` |
| 发现来源 | LS60 的 residual momentum 在 2022–2026 为负 Sharps；本试验检验符号取反的 residual reversal |
| 主要确认样本 | 2020-09-03 → 2021-12-31（早于 2022 主样本） |
| 次级准 OOS | 2024-01-01 → 2026-09-21（仅作报告，不用于调参） |
| 因子 | 60D BTC beta；28D 残差收益；**只做低残差、空高残差** |
| 组合 | 月度 28D，各 4 个资产，每腿 12.5% NAV，gross 1.0x |
| 成本 | 2 / 20 / 50 / 100bps；本筛查不计 funding |

## 0. 研究问题

LS60 的冻结 residual momentum 口径在 2022–2026 的 20bps Sharpe 为负，且 2bps 仍为负，说明
“高残差赢家继续赢、低残差输家继续输”没有在该样本成立。一个独立的、可解释的反向假设是：
crypto 横截面残差收益可能表现为短期反转而不是中期动量。因此本轮只翻转信号符号：

```text
long  = bottom 4 residual scores
short = top 4 residual scores
```

这是由 LS60 的负结果触发的**新试验**，不是对 LS60 失败结果的参数救援。为了降低符号翻转的
数据窥探风险，主验收放在完全早于 2022 主样本的 2020-09-03 → 2021-12-31；2024–2026 结果只作
次级报告，不能用来重新选择窗口、数量、权重或成本。

## 1. 冻结构造

- 其余规则与 LS60 完全相同：60D beta、45 个 minimum beta observations、28D residual score、
  28D 调仓、4+4、12.5% 每腿、min 8 assets、T+1 生效、换手成本；
- 不扫描 beta/momentum 窗口、资产数量、权重、方向以外的任何参数；
- 缺失收益按 0 计入并报告；缺失行情不得被解释成因子有效信号；
- 2020–2021 数据若不足 200 个交易日或因子事件不足 12 个，直接标记不可评估。

## 2. 预注册筛查门槛

主确认样本（2020-09-03 → 2021-12-31）：

1. 20bps Sharpe >= **0.8**；
2. 20bps multiple > **1.0x**，MDD 不差于 **-40%**；
3. 50bps multiple > 1.0x 且 Sharpe >= **0.5**；
4. 两个日历年（2020 部分年、2021）均为正收益；
5. 主确认样本前后两半收益均为正；
6. 换手、gross、缺失收益、年份和半段分解完整报告。

次级 2024–2026 只报告方向是否一致；即使主确认通过，仍只能进入组合集成研究，不能 promotion。
若主确认失败，停止 residual reversal 家族，不扫描替代窗口或数量。

## 3. 复现

```bash
.venv/bin/python scripts/run_residual_momentum_screen.py \
  --start-date 2020-09-03 --end-date 2021-12-31 \
  --direction -1 \
  --candidate-id PR2026-11-LS61-RESIDUAL-REVERSAL-SCREEN \
  --output-dir reports/residual_reversal_screen_pre2022
```

次级报告：

```bash
.venv/bin/python scripts/run_residual_momentum_screen.py \
  --start-date 2024-01-01 --end-date 2026-09-21 \
  --direction -1 \
  --candidate-id PR2026-11-LS61-RESIDUAL-REVERSAL-SCREEN \
  --output-dir reports/residual_reversal_screen_2024_2026
```

研究输出不是订单，也不是实盘批准。
