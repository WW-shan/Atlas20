# Atlas20 候选 LS23：H5 利润保护 + LS12 双空头 regime router

日期：2026-11-12
候选：`PR2026-11-LS23-H5-PROFIT-LOCK-REGIME-SHORT`
状态：**provisional（当前最强主样本 promotion candidate；不接实盘）**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS23 把两个已经分别冻结的机制组合起来，而不是重新扫描参数：

- 多头：H5 1.25x 上应用 LS22 的单一龙头利润保护。每个 H5 目标事件中，如果最大权重腿的
  21D trailing return >=100%，只把这一腿减半，释放权重留现金；
- 空头：保留 LS12 的 BTC 200D 双空头 router。BTC 在 200D 下方时做 14D 最弱四币，BTC 在
  200D 上方时做 H5 退出币中的 funding-top-tercile 空头；
- 空头只使用未使用 gross，总空头 <=0.25x，hard total gross <=1.50x。

20bps 主样本：**61.9150x / Sharpe 1.9448 / MDD -39.84% / 0 强平**。同口径 L125 为
**40.2200x / 1.7330 / -40.65%**。LS23 同时提高了终值、Sharpe 和回撤，并在 2/20/50/100bps
四档成本上全部胜过同成本 L125；100bps 也守住了 50% MDD kill line。

但这仍不是可上线策略：12 个月真实 OOS 只完成约 50 天，funding 仍是 Binance proxy，且最新
50 天 cash-start OOS 中 LS23 略低于 L125、Sharpe 明显更差。预注册规则要求满 12 个月 OOS，
因此最高判定只能是 **provisional**。

## 二、预注册与构造

- Spec：`docs/superpowers/specs/2026-11-12-h5-profit-lock-regime-short-design.md`
- spec 文件 SHA-256：`0e31c99f49b4a1beef09b84e40a99f02031da1370ed527ee02b5a933108fc6e4`
- 注册的 canonical spec JSON SHA-256：`68ec43fcef27511685d2da981557aa540b0e0848c7677f40409543bf3ba78a2b`
- registration hash：`104b177beba9a1c4de413b1d4e8bcf7b136db338c5ce6075d2a3ba5797fcc0e7`
- 主样本：2022-01-01 → 2026-09-21（UTC）
- 执行：T+1 UTC +3h
- 数据：严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip
- 冻结规则：H5 1.25x、LS22 的 21D/100%/0.5 利润保护、LS12 的 200D/14D/7D/4 币/20% stop、
  50% buffer 和 1.50x hard gross 均不扫描

运行前没有新增阈值搜索。LS22 和 LS12 的失败/保留状态见 `RESEARCH.md` §00.34、§00.45。

## 三、四档成本

| 成本 | L125 终值 | LS23 终值 | L125 Sharpe | LS23 Sharpe | L125 MDD | LS23 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | **84.4362x** | 1.8249 | **2.0719** | -38.42% | **-37.57%** |
| 20bps | 40.2200x | **61.9150x** | 1.7330 | **1.9448** | -40.65% | **-39.84%** |
| 50bps | 27.3725x | **36.8788x** | 1.5790 | **1.7319** | -44.20% | **-43.45%** |
| 100bps | 14.3794x | **15.5037x** | 1.3204 | **1.3745** | -50.02% | **-49.48%** |

主样本 0 强平、0 gross breach；20bps 最大观测 gross **1.3308x**，低于 1.50x hard cap。
20bps 空头 open 335、short stop 29、利润保护触发 57 次。四档汇总：
`reports/derivatives_track_h5_profit_lock_regime_short/cost_summary.csv`。

## 四、压力、年度和滚动窗口

20bps + 3x short-adverse funding：**62.0165x / 1.9443 / -39.95% / 0 强平**。funding total
从 -0.7465 恶化到 -0.7636，但没有强平或 gross breach。

| 年份 | L125 | LS23 |
|---|---:|---:|
| 2022 | -19.61% | **+23.71%** |
| 2023 | **+277.20%** | +264.98% |
| 2024 | **+119.25%** | +80.33% |
| 2025 | +151.02% | **+194.07%** |
| 2026 | +141.01% | **+158.57%** |

删除任一最佳年份后的终值，LS23 全部高于 L125：

| 删除年份 | L125 | LS23 |
|---:|---:|---:|
| 2022 | 50.0330x | **50.0467x** |
| 2023 | 10.6628x | **16.9638x** |
| 2024 | 18.3441x | **34.3343x** |
| 2025 | 16.0225x | **21.0546x** |
| 2026 | 16.6884x | **23.9447x** |

365 天滚动最差从 L125 的 **0.7325x** 改善到 **0.8551x**；滚动中位数从 2.5547x 改善到
2.8034x。45 个“至少剩余 365 天”的月初路径切片全部通过终值、Sharpe 和 MDD 5pp 门槛
（**45/45**），这是 LS22 没有通过而 LS23 修复的关键项。

## 五、真实引擎冷启动

12 个真实 cash-start 引擎季度起点全部通过：

- 终值胜 L125：**12/12**；
- Sharpe 胜 L125：**12/12**；
- MDD 不差于 L125 +5pp：**12/12**；
- 0 强平、0 gross breach、max observed gross <=1.50x：**12/12**。

最弱相对优势出现在 2023-01：终值 50.3499x vs 50.0330x，Sharpe 2.1246 vs 2.0657，MDD
-39.84% vs -40.65%。完整表：
`reports/derivatives_track_h5_profit_lock_regime_short/engine_monthly_starts/`。

## 六、空头归因与集中度

335 个已配对空头 episode：169 个正贡献、166 个负贡献；平均每 episode +0.1010% NAV，
中位数 +0.0099%，最好 +6.3847% NAV，最差 -1.3807% NAV。单资产最大贡献 **23.44%**，前 3
合计 **62.09%**，均低于预注册的 50% / 80% 集中度 kill line。

该归因是 saved engine outputs 的平均成本重建，不是交易所 execution ledger；不证明真实成交
和 funding 完全一致。2026-11-12 修复了 attribution 脚本的两处缺陷：大数量 close 的绝对浮点
容差过紧，以及 short liquidation 未纳入 episode 关闭；修复后 LS23 从 333 个 episode 更正为
335 个，结论不变。

## 七、多重检验

9 个冻结候选矩阵（L125 + LS12 + LS17..LS23）：

- PBO/CSCV：**0.3528**（<=0.50）；
- White Reality Check：zero **p=0.003996**、BTC **p=0.009990**（均 <=0.05）；
- LS23 DSR：按最新台账重算，all-project N=14,209 **0.958974**，Top20/2022 N=6,142
  **0.971481**（均 >=0.95）；family-only 为 0.999998，不作为项目级选择偏差证据；
- 当前 inventory trial count：all-project **14,209**；Top20/2022 **6,142**。旧
  `0.9999832/0.9999858` 与 14,192 计数基于过期 inventory，已作废；
- 刷新共同样本为 1,724 天（2022-01-01 → 2026-09-20），因此观测 Sharpe 为 1.9443；
  manifest SHA-256 记录的 trial summary 为
  `90f55c49d49013876b12b96c6ede06a073046100862ec7b8aa2b5e19d2ecd0ad`。
  目录为 `multiple_testing_refresh_20261112_r3/`；`_20261112/` 与 `_r2/` 保留为更早的历史刷新。

这些统计量支持“在已记录的候选族里，LS23 不是明显的选择偏差产物”，但不能替代 12 个月 OOS，
也不能证明未来收益。

## 八、50 天 cash-start OOS（关键警告）

冻结后窗口：2026-09-22 → 2026-11-10，20bps，Bitget OOS mark，zero funding，cash-start：

| 口径 | 终值 | Sharpe | MDD | 0 强平 | max gross |
|---|---:|---:|---:|---:|---:|
| L125 baseline | 0.9484x | -0.2771 | -17.47% | 是 | 0.8149x |
| LS23 candidate | 0.9403x | -0.5641 | -17.47% | 是 | 0.8153x |

该窗口 BTC 在 200D 上方，因此 LS23 **没有开空头**，实际只检验了多头利润保护。50 天内触发
8 次 trim；相对同口径 baseline，终值低约 0.85%，Sharpe 更差，最大回撤基本不变。这个结果不能
判定 LS23 失败——50 天只有 12 个月 OOS 的 13.7%——但足以阻止 promotion 和任何实盘切换。

注意：这与 `run_derivatives_oos.py` 的 carry-in L125 0.9787x 不是同一口径；此处 baseline
和 candidate 都是同一 cash-start 引擎，因此只能看相对差。

汇总：`reports/derivatives_track_h5_profit_lock_regime_short/oos_2026_11/summary.csv`。

## 九、pre-2022 proxy stress（2020-10-03 → 2022-01-01）

在 64 个可加载的 pre-2022 proxy mark 序列上，20bps、+3h、carry 3h、0 强平：

| funding 口径 | 口径 | 终值 | Sharpe | MDD | 空头 open | trim |
|---|---|---:|---:|---:|---:|---:|
| zero funding | L125 | 4.2956x | 2.0754 | -27.76% | 0 | 0 |
| zero funding | LS23 | 3.5113x | **2.2331** | **-19.49%** | 0 | 83 |
| Binance funding proxy | L125 | 3.9238x | 1.9618 | -28.24% | 0 | 0 |
| Binance funding proxy | LS23 | 2.5189x | 1.7131 | **-20.88%** | 67 | 83 |

zero funding 面板中 LS23 只实际运行了多头利润保护，因此空头 open=0；它提高了 Sharpe 和 MDD，
但终值低于 L125。加入 Binance funding proxy 后 LS23 真正运行 67 个空头、25 个 stop，终值和
Sharpe 均低于 L125，但 MDD 仍改善约 7.6pp。该窗口不是主样本，不能直接替代 2022+ 结论；它说明
LS23 在 2021 式单边牛市中会牺牲收益，且空头 sleeve 在该环境没有提供足够补偿。pre-2022 仍
只能视为 **partial-with-bounding**：mark 是 Binance/Gate proxy，Bitget 真实 mark 和完整 funding
settlement 不可得。

汇总：`reports/derivatives_track_h5_profit_lock_regime_short/pre2022_stress.csv`。

## 十、判定与边界

**Provisional / strongest main-sample promotion candidate。** 预注册的 2/20/50/100bps、funding stress、
年度删除、滚动最差、45 个路径切片、12 个真实引擎起点、gross/强平、集中度、PBO/RC/DSR 均已
完成并通过；但：

- 12 个月真实 OOS 尚未完成；
- 主样本 funding 仍是 Binance proxy；OOS 已用完整 Bitget exact funding，但跨所 overlap gate
  0/88，不能把 proxy 当作 exact；
- pre-2022 proxy stress 在 funding proxy 下终值和 Sharpe 低于 L125，只在 MDD 上改善；
- 最新 50 天 cash-start OOS 相对 baseline 没有正增量：zero 0.9403x vs 0.9484x，Bitget exact
  0.9365x vs 0.9440x。

因此：

- 不接执行器；
- 不修改 `PR2026-10-D-L125-V2`；
- 不因为 LS23 通过样本内门槛就增加杠杆；
- 不把 pre-2022 MDD 改善误读成收益或 Sharpe 通过；
- 不扫描 profit-lock 阈值、short 权重、stop、regime 窗口或组合权重来救 OOS；
- 继续做真实 shadow OOS 和独立风险层研究。

## 十一、复现

```bash
# 20bps 主样本
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS23-H5-PROFIT-LOCK-REGIME-SHORT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_profit_lock_regime_short

# 50 天 cash-start OOS
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS23-H5-PROFIT-LOCK-REGIME-SHORT \
  --start-date 2022-01-01 --evaluation-start 2026-09-22 \
  --end-date 2026-11-10 --cost-bps 20 \
  --raw-dir data/raw/bitget_derivatives/merged_oos_20261009 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source zero --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_profit_lock_regime_short/oos_2026_11/candidate
```

研究输出不是订单，也不是 live approval。


## 十二、2026-11-12 v2：完整 Bitget funding 复跑

修复 Bitget candle 分页边界（`endTime` 小时开区间，旧 `first_open - 1ms` 每 100 行少 1 小时）
后，新 OOS 快照 88 个资产窗口内 **0 missing hours / max gap 1h**；状态 warmup 使用
`merged_20261009` 完整历史，成本使用完整 Bitget exact funding：

| funding | 策略 | 终值 | Sharpe | MDD | funding total | trim | short open |
|---|---|---:|---:|---:|---:|---:|---:|
| zero（上界） | L125 | 0.9484x | -0.2771 | -17.47% | 0 | 0 | 0 |
| zero（上界） | LS23 | 0.9403x | -0.5641 | -17.47% | 0 | 8 | 0 |
| Bitget exact | L125 | 0.9440x | -0.3303 | -17.65% | -0.4808% | 0 | 0 |
| Bitget exact | LS23 | **0.9365x** | **-0.6187** | **-17.65%** | **-0.4088%** | 8 | 0 |

完整 funding 下 LS23 仍低于 L125 约 0.0074x，Sharpe 低约 0.2884；零 funding 下也低约
0.85%。该窗口 BTC 在 200D 上方，空头 sleeve 0 次开仓；结论与旧 partial-funding 版本一致，
旧 0.9391x / 0.9465x 读数由本 v2 取代。

报告：`reports/derivatives_track_h5_profit_lock_regime_short/shadow_oos_2026_11_refresh/report.md`。
数据审计：`reports/derivatives_track_h5_profit_lock_regime_short/shadow_oos_2026_11_refresh/data_audit/report.md`。
