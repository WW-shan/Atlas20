# Atlas20 反手空研究线预注册（2026-11-10）

| 项目 | 内容 |
|---|---|
| 状态 | 研究预注册；不接实盘，不改现货 `Spot Track` |
| 触发 | 负责人明确要求：收益优先，回撤可以变差但不能明显恶化 |
| 主样本 | 2022-01-01 → 2026-09-21 |
| 真样本外 | 2026-09-22 起，当前仅有约 49 天，不能用于选规则 |
| 多头底稿 | 冻结 H5 / `PR2026-10-D-L125-V2`，严格 point-in-time CMC Top20 |
| 空头上限 | 0.25x gross；0.50x 只做压力，不进入主候选 |
| 成本 | 20 bps 主口径；50/100 bps 压力 |
| 数据 | Bitget mark 为主；funding 只接受 Bitget 精确值或明确标注的 proxy/压力带 |

## 0. 研究问题

“平仓后反手开空”是否能在不把最大回撤显著推高的前提下，提高冻结多头策略的终值和 Sharpe？

旧的空头 overlay 是**多头仍然持有 + 额外加 0.25x 空头**，已在预注册门槛下失败（最大回撤没有改善 5pp，PBO 约 0.96）。本文件不重跑、也不放宽那个已经失败的家族；本文件检验的是**目标账本状态切换**：

1. **R 模式（reverse）**：BTC 熊市确认 + funding 过滤通过时，把 H5 多头账本整体替换为现金 + 0.25x 单币空头；过滤失效或熊市结束时恢复 H5 多头账本。
2. **F 模式（flat-only）**：只有当 H5 本身已经把账本全部转为现金时，才开 0.25x 单币空头；H5 仍持有多头时不加空头。

R 是负责人“平仓后反手”的实质版本；F 是严格的“只在现金状态加空”诊断。由于 H5 很少全现金，F 可能几乎没有交易，不能因为结果小就事后改成 R。

## 1. 冻结的四条试验

| trial_id | 空头标的 | 模式 | 空头权重 |
|---|---|---|---:|
| `PR2026-11-RS-R-BTC25` | BTC | replace | 0.25x |
| `PR2026-11-RS-R-WEAK25` | 当时 Top20 中 30D 最弱且可交易币 | replace | 0.25x |
| `PR2026-11-RS-F-BTC25` | BTC | flat-only | 0.25x |
| `PR2026-11-RS-F-WEAK25` | 当时 Top20 中 30D 最弱且可交易币 | flat-only | 0.25x |

规则参数不扫：BTC 熊市 = BTC close < 200D SMA 且 30D return < 0；funding = 过去 3 个结算点均值高于预注册阈值（BTC `-0.0001`，空头标的 `-0.0002`）。空头权重上限和各 trial 的 ID 一样冻结。

## 2. 验收门槛（先写死，后看结果）

主口径为 20 bps、Bitget mark、T+1、无强平：

- **收益**：终值必须高于同口径 L125 多头基线，且 Sharpe 不低于基线；
- **回撤**：最大回撤允许比基线差，但不得差超过 **5 个百分点**；超过即拒绝；
- **强平**：必须为 0；
- **成本**：50/100 bps 下方向不能反转成不可接受的结构；至少 50 bps 仍要优于基线终值或给出明确失败原因；
- **极端 funding**：0x / 1x / 3x adverse 资金费压力下，不能出现强平或回撤突破 50%；
- **多重检验**：四条试验必须一起做 DSR、Reality Check、PBO；不能用单条最好结果绕过选择偏差；
- **依赖**：报告最佳年份移除、年度收益、滚动最坏一年、空头激活次数和单次最大贡献；若收益只来自一次空头交易，标记为不稳健；
- **OOS**：2026-09-22 起的样本外太短，任何结果都只能是 provisional，不得据此接实盘。

这组门槛不是对旧空头 overlay 门槛的放宽；旧家族仍然失败。R/F 是新的机制假设，若通过也只获得“继续研究”的资格。

## 3. 实盘边界

- 本文件不修改 `ops/run_derivatives_daily.sh`、plist、systemd 或当前多头目标账本；
- 不把做空接入 Telegram 实盘执行器；
- 不改变 `AGENTS.md` 的现货 long-only 约束；
- 任何实盘化都需要新的负责人签核、风险预算、逐结算点 funding 和至少 12 个月独立 OOS；当前不满足。

## 4. 复现

```bash
# 四条试验分别跑 20 bps、Bitget mark、零 funding 上界；先看方向和强平
make derivatives-oos-data
.venv/bin/python scripts/run_derivatives_backtest.py \
  --trial-id PR2026-11-RS-R-BTC25 \
  --start-date 2022-01-01 --end-date 2026-09-21 \
  --cost-bps 20 --output-dir reports/derivatives_track_reversal_short
# ...其余三条同理，随后对共同的 daily_returns 做 evaluate_derivatives_candidates.py
```

## 5. 首轮结果（2026-11-10）

首轮按上述冻结规则运行，数据为 Bitget mark、2022-01-01 → 2026-09-21、T+1 +3h、missing mark=carry、20bps 主口径；funding 只能使用 Binance proxy 并标记 `funding_missing_policy=skip`，不是 Bitget 精确历史。

| trial | 终值 | Sharpe | MDD | 20bps 判定 |
|---|---:|---:|---:|---|
| L125 baseline | 34.8735x | 1.6935 | -40.65% | 基线 |
| RS-R-BTC25 | 34.3995x | 1.6887 | -40.65% | 拒绝（收益低于基线） |
| RS-R-WEAK25 | 33.9680x | 1.6716 | -40.65% | 拒绝（收益低于基线） |
| RS-F-BTC25 | 36.0045x | 1.7025 | -40.65% | provisional |
| RS-F-WEAK25 | 37.4394x | 1.7079 | -40.65% | 拒绝（3x adverse funding 下 1 次强平） |

- PBO = **0.9307**，远高于 0.5；
- `F-WEAK25` 只在 4 个区间开空，收益集中来自 2022 年；
- 365 天滚动最差：基线 0.7325x，`F-WEAK25` 0.6854x；
- 50bps 下 `F-WEAK25` 仍高于基线，但 100bps 下所有版本都约触及 -50% MDD kill line；
- funding 3x 压力已改为按持仓方向施加并置零非受压腿；`F-BTC25` 为 38.8886x / -40.72% / 0 强平，`F-WEAK25` 为 37.8467x / -40.72% / **1 次强平**。

因此：`replace` / “平仓即反手”拒绝；`F-BTC25` 的 `flat-only` 只保留为 provisional；`F-WEAK25` 因 funding 压力强平被拒绝；不接实盘。

完整结果：`reports/derivatives_track_reversal_short/report.md`。
