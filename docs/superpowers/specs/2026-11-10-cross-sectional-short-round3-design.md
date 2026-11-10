# Atlas20 双边轮动第三轮预注册：Top20 横截面最弱空头

| 项目 | 内容 |
|---|---|
| 状态 | 研究预注册；不接实盘，不改 H5 多头账本 |
| 触发 | 第二轮方向性 BTC 空头失败；继续检验“双边都做”的相对价值机制 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 多头底稿 | 冻结 H5 / `PR2026-10-D-L125`，严格 point-in-time CMC Top20 |
| 空头 | 0.25x，Top20 中 14D 最弱且不在当前 H5 多头账本的币 |
| 成本 | 20bps 主口径；50/100bps 压力 |
| 数据 | Bitget mark；Binance funding proxy/skip，明确不是 Bitget 精确历史 |

## 0. 为什么换机制

第二轮测试的是“BTC 趋势向下时做空 BTC”。它在 20bps 下曾略高于基线，但：

- 50bps 后低于基线；
- 收益依赖 2022；
- PBO=0.8355；
- 100bps 越过 50% MDD；
- 2022 贡献了约 85% 的空头相对收益。

因此不再扫描 BTC 趋势窗口。第三轮改为**横截面相对价值**：不预测市场方向，只做多 H5 选出的强势币，同时做空同一 Top20 中 14D 最弱的币。这样测试的是“强势币相对弱势币的价差”，而不是 BTC 方向。

外部证据是混合的，必须如实记录：

- Liu、Tsyvinski 与 Wu (2022, [S2]) 在大型币上发现显著的长短动量价差，3 周动量约 4.1%/周；并报告用 BTC 空头替代 loser leg 的结果相近。
- Han、Kang 与 Ryu (2024, [S4]) 使用现实成本后发现横截面动量收益主要来自 long leg，空头腿经常被反弹伤害；其最佳横截面参数为 14D lookback / 7D holding。
- Grobys 等 (2026, [S14]) 的记录显示 top-30 长短组合可能被单一币的极端反弹支配。

所以这是一个有外部动机、但空头腿已知脆弱的探索；不是“把亏损的空头换成更小窗口”。

## 1. 唯一冻结试验

| trial_id | 构造 | 空头选择 | 空头权重 | 再平衡 |
|---|---|---|---:|---:|
| `PR2026-11-RS3-X-WEAK14` | H5 多头 ×1.25 + 空头 0.25 | PIT Top20 中 14D 收益最弱、且不在当前 H5 多头账本中的可交易币 | 0.25x | 每 7 个自然日 |

只跑这一条。不能同时扫 7D/14D/21D、top1/top3 或 0.25x/0.50x。

## 2. 精确规则

### 2.1 H5 多头

H5 的选币、3 日相位、Top2 hold band、BTC 100D gate、dispersion overlay 不变，
`w_long = 1.25 × w_H5`。H5 事件之间前向填充权重；不加入 Top20 外资产。

### 2.2 空头候选

每个第 7 个自然日的 UTC 收盘：

```text
eligible_t = PIT_CMC_Top20_t
              ∩ Bitget mark available at t+1 execution
              ∩ not currently held by H5 long book
weak_t = argmin_{i in eligible_t} (price_i,t / price_i,t-14 - 1)
```

若 `weak_t` 不在 Top20、mark 不可用、或 funding guard 失败，则该周期不持有空头。空头为
负权重 `-0.25`；H5 持有该币时自动退出/不建立空头，避免同一资产被静默净额化。

### 2.3 执行与 funding

- 信号：每周锚点 UTC 日线收盘；
- 执行：T+1 03:00 UTC（+3h）；
- funding guard：目标空头最近 3 个结算点均值必须 `> -0.0002`，缺失则 fail closed；
- 主研究使用 Binance funding proxy + `skip`；3x short-adverse 是压力带，不是精确费用；
- 空头不因短期反弹自动止损，也不加 stop；强平由引擎逐小时 mark 检查。

## 3. 预注册门槛

主口径为 20bps、Bitget mark、T+1 +3h、missing mark carry≤3h：

1. 终值严格高于同口径 L125 基线；
2. Sharpe 不低于基线；
3. MDD 不差于基线 + 5pp；
4. 主样本 0 次强平；
5. 50bps 终值仍高于基线；
6. 100bps MDD ≤ 50%；
7. 3x short-adverse funding 0 次强平且 MDD ≤50%；
8. 移除 2022 后仍高于基线，且 2022 贡献不超过超额的一半；
9. 基线 + 本试验的 PBO/CSCV ≤0.5；
10. 报告空头开仓次数、逐区间贡献、年度收益、365 天滚动最差、最佳年份移除；
11. 真 OOS 不足 12 个月时最多 provisional，禁止接实盘。

## 4. 试验记账

新增 `PR2026-11-RS3-X-WEAK14` 到 `reports/research_trial_inventory/preregistered_trials.csv`，
`counts_as_trial=True`。该试验与 L125 基线共同构成 R3 决策族；不能只报告最好周或最好年份。

## 5. 复现

```bash
.venv/bin/python scripts/run_derivatives_backtest.py \
  --trial-id PR2026-11-RS3-X-WEAK14 \
  --start-date 2022-01-01 --end-date 2026-09-21 \
  --cost-bps 20 --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_cross_sectional_short_round3
```

## 6. 边界

- 不修改当前 H5 多头实盘账本；
- 不进入 `ops/run_derivatives_daily.sh`；
- 不把“空头腿”说成已验证 alpha；
- 若失败，下一步才考虑事件驱动空头或完全放弃方向性空头，不继续微调这里的周频/回看参数。

---

## 7. 第三轮结果（2026-11-10）

按本文件冻结规则运行：

| trial | 终值 | Sharpe | MDD | 强平 |
|---|---:|---:|---:|---:|
| L125 基线 | 40.2200x | 1.7330 | -40.6506% | 0 |
| `PR2026-11-RS3-X-WEAK14` | 38.5909x | 1.7106 | -47.0461% | **1** |

唯一的强平发生在 2023-07-13：XRP 空头从 0.4841 被挤到 0.7278。空头腿有 157 次开仓、累计空头成交名义约 475.5x NAV，成本与单币尾部都不可接受。

判定：**拒绝；不再扫描单币最弱的 7D/14D 或权重参数。** 若继续，只能预注册一次 bottom-quintile（4 币）空头篮子作为风险分散机制，不能把它说成对单币策略的调参。
