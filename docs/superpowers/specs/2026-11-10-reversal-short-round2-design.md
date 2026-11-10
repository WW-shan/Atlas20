# Atlas20 反手空第二轮预注册：更快的 BTC 趋势空头

| 项目 | 内容 |
|---|---|
| 状态 | 研究预注册；不接实盘，不改当前多头 H5 目标账本 |
| 触发 | 第一轮 200D/30D 反手空未通过；负责人要求继续验证是否只是确认过慢 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 真样本外 | 2026-09-22 起；当前长度不足以支持上线 |
| 多头底稿 | 冻结 H5 / `PR2026-10-D-L125`，严格 point-in-time CMC Top20 |
| 成本 | 20 bps 主口径；50/100 bps 压力 |
| 数据 | Bitget mark；Binance funding 只能标记为 proxy，不能冒充 Bitget 精确历史 |

## 0. 第一轮先验与本次问题

第一轮冻结的规则是 BTC `< 200D SMA` 且 `30D return < 0`，在此状态下开 0.25x BTC 或 weakest-Top20 空头。旧报告的实现有两个研究缺陷，已在第二轮开始前修复：

1. 空头信号只在 H5 发生稀疏调仓事件的日期被检查，而不是在每个 UTC 日线收盘检查；熊市确认和退出会被无关的 H5 事件延迟。
2. runner 把「有 funding 列」错误地当成「整个 H5 长账本可交易」的条件，导致大量无 Binance funding 代理的长仓被静默替换成现金；这改变了空头比较的基线。

修复后，空头在完整日历上评估，H5 权重前向填充，固定空头必须是当时 PIT Top20 成员，且短腿自己的执行 mark 必须存在。旧第一轮数字因此只能作为历史记录，不能作为本次参数选择的依据。

本次只检验一个新的机制假设：**第一轮的 200D/30D 可能确认过慢；更快的中期 BTC 趋势空头是否能在不全样本降仓的情况下提高终值和 Sharpe，同时不把 MDD 恶化超过 5 个百分点？**

这不是对旧 200D 参数的阈值微调。外部证据支持短到中期的趋势窗口，但同样明确警告「市场下跌后做空」经常亏钱：

- Zarattini、Pagani 与 Barbon (2025, [S17]) 在 BTC 上发现 5–30 天的短趋势窗口强于长窗口；本文只取其方向性含义。
- Han、Kang 与 Ryu (2024, [S4]) 的现实假设下最佳市场时间序列回看期是 28 天；该文同时报告“下跌后做空市场在多数情况下亏钱”，所以本次是带明确 kill criterion 的探索，不是假定空头必然有效。
- Man Group (2024, [S18]) 使用 50/200 日均线交叉并强调波动缩放；本次把 50D 作为较快的趋势边界，与 [S4] 的 28D 收益确认组合。

不扫描 `20/30/50/100/200D`，不扫描 `14/21/28/30D`。如果以下两个固定试验失败，方向性 BTC 空头不再通过换窗口救活。

## 1. 冻结的两个试验

| trial_id | 模式 | 空头标的 | 空头权重 | 50D MA | 28D return | 允许的大致 gross |
|---|---|---|---:|---:|---:|---:|
| `PR2026-11-RS2-A-BTC28` | additive | BTC | 0.25x | 50D | 28D | 1.25x long + 0.25x short |
| `PR2026-11-RS2-F-BTC28` | flat-only | BTC | 0.25x | 50D | 28D | H5 现金时最多 0.25x short |

两个试验共享完全相同的时间、数据、成本、funding 过滤和执行口径；唯一差异是空头是否允许与 H5 多头并存。这样可以把“更快确认”与“是否只替代现金”分开，而不是挑一个最好看的模式。

## 2. 精确规则

### 2.1 H5 长账本

`w_long_i,t = 1.25 × w_H5_i,t`，H5 的选币、3 日相位、Top2 hold band、BTC 100D gate、dispersion overlay 全部不变。H5 事件日之间前向填充权重，绝不加入 Top20 之外的新币。

### 2.2 快速 BTC 熊市确认

每个 UTC 日线收盘计算：

```text
fast_bear_t = (BTC_close_t < SMA_50(BTC)_t)
              AND (BTC_close_t / BTC_close_{t-28} - 1 < 0)
```

只有 `fast_bear_t = True` 才允许开空；`False` 时下一可执行时点平掉空头。不得使用未来数据，不把当日收盘填入信号。

### 2.3 Funding 过滤与数据边界

沿用第一轮的固定 guard，不调阈值：

```text
btc_funding_3_t = mean(last 3 BTC settlements at or before t)
btc_funding_ok_t = btc_funding_3_t > -0.0001
btc_short_ok_t = btc_funding_ok_t and fast_bear_t
```

缺失 funding、少于 3 个结算点、空头币不在当时 Top20、执行 mark 不可用：均 fail closed，不开新空。主研究仍使用 Binance funding proxy，报告中必须明确写出 `proxy + skip`；另做 3x short-adverse 压力。Bitget 精确 funding 只有约 90 天，不能覆盖 2022–2026，因此本轮不能凭 proxy 声称 funding 已闭合。

### 2.4 两种账本模式

- **additive**：H5 多头保留，空头按 0.25x 叠加；同币净额处理沿用引擎的 signed target 语义。gross 上限 1.5x。
- **flat-only**：只有 H5 已产生目标且当前全部为现金时，才允许 0.25x 空头；H5 持有多头时不加空。gross 上限 1.25x。

空头从信号日 `D` 的下一日 `D+1 03:00 UTC` 执行，和 H5 的 T+1 +3h 完全一致；不是用一个更快的盘中信号偷跑。

## 3. 先写死的验收门槛

主口径：Bitget mark、20bps、T+1 +3h、missing mark carry≤3h、Binance funding proxy/skip。

任一候选必须全部满足才可称为“继续研究候选”：

1. 20bps 终值严格高于同口径修正后的 L125 基线；
2. 20bps Sharpe 不低于基线；
3. 20bps MDD 不差于基线 **+5 个百分点**；
4. 主样本 0 次强平；
5. 50bps 终值仍高于同成本基线；100bps 不得出现 0 强平以外的结构性失败；
6. 3x short-adverse funding 下 0 次强平，MDD 不超过 50%；
7. 报告空头开仓次数、逐区间贡献、最差单次区间、按年收益、最佳年份移除和 365 天滚动最差；
8. 不允许收益只来自 2022 或单一空头区间；若 2022 贡献超过总超额的一半，判为不稳健；
9. 三个候选（基线 + 两个试验）一起做 DSR、White Reality Check、PBO/CSCV；PBO > 0.5 视为失败；
10. 2026-09-22 之后的真样本外不足 12 个月时，最多只能 provisional，禁止接实盘。

这不是放宽第一轮门槛：第一轮仍被拒绝；新增两个 horizon 试验只会增加多重检验分母。

## 4. 多重检验与试验记账

新增两条必须进入 `reports/research_trial_inventory/preregistered_trials.csv`，`counts_as_trial=True`。其 trial_count 与基线一起构成 R2 的 3 个决策候选；不能只报表现好的那一条。

如果两个试验都失败，下一步不继续做 `14D/20D/30D/40D` 的窗口搜索；应转向非方向性、事件或市场中性机制，并重新预注册。

## 5. 复现命令

```bash
.venv/bin/python scripts/run_derivatives_backtest.py \
  --trial-id PR2026-11-RS2-A-BTC28 \
  --start-date 2022-01-01 --end-date 2026-09-21 \
  --cost-bps 20 --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_reversal_short_round2

.venv/bin/python scripts/run_derivatives_backtest.py \
  --trial-id PR2026-11-RS2-F-BTC28 \
  --start-date 2022-01-01 --end-date 2026-09-21 \
  --cost-bps 20 --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_reversal_short_round2
```

## 6. 当前边界

- 不修改 `ops/run_derivatives_daily.sh`、plist、systemd 或 Telegram 实盘执行器；
- 不把空头加入当前多头目标账本；
- 不改变现货轨的 long-only 约束；
- 任何实盘化都需要精确 funding、至少 12 个月独立 OOS、强平/ADL/流动性审查和负责人签核。

---

## 7. 第二轮结果（2026-11-10）

两个试验已按本文件冻结规则运行。20bps 主口径：

| trial | 模式 | 终值 | Sharpe | MDD | 强平 |
|---|---|---:|---:|---:|---:|
| `PR2026-10-D-L125` | baseline | 40.2200x | 1.7330 | -40.6506% | 0 |
| `PR2026-11-RS2-A-BTC28` | additive | 42.1308x | 1.7489 | -40.3874% | 0 |
| `PR2026-11-RS2-F-BTC28` | flat-only | 39.1204x | 1.7116 | -42.1363% | 0 |

`RS2-A` 在 20bps 下有增量，但未通过预注册门槛：

- 50bps：26.1010x，低于基线 27.3725x；
- 100bps：11.7179x，MDD -51.1320%，越过 50% kill line；
- PBO/CSCV：0.8355，高于 0.5；
- 移除 2022 后：47.0582x，低于基线 50.0330x；
- 61 次空头开仓，2022 贡献了相对收益合计约 85%；
- 365 天滚动最差：0.7271x，低于基线 0.7325x。

判定：**两个候选均拒绝；不再搜索相邻 BTC 趋势窗口。** 结果和完整表格见
`reports/derivatives_track_reversal_short_round2/report.md`。

---

## 7. 第二轮结果（2026-11-10）

20bps：基线 40.2200x / 1.7330 / -40.6506%；`PR2026-11-RS2-A-BTC28`
42.1308x / 1.7489 / -40.3874%，`PR2026-11-RS2-F-BTC28` 39.1204x / 1.7116 / -42.1363%。

A 版本 50bps 26.1010x 低于基线 27.3725x；100bps 11.7179x / MDD -51.13%；
PBO=0.8355；移除 2022 后 47.0582x 低于基线 50.0330x；61 次空头开仓中约 85% 相对收益来自
2022。按预注册拒绝，且不再扫描相邻 BTC 趋势窗口。完整报告：
`reports/derivatives_track_reversal_short_round2/report.md`。
