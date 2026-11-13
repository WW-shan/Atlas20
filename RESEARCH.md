# Atlas20 策略研究记录（唯一权威版本）

> 本文取代此前所有口头结论、临时 `/tmp` 结果、旧报告和 README 里过时的策略叙述。
> 与本文冲突的旧数字一律作废。
>
> | | |
> |---|---|
> | 最后更新 | 2026-11-13（现货：§00.13 采用 **H5**；§00.15–00.17 三族外部状态筛查全部被拒；§00.18 当前信号 = 100% NEAR / 目标 gross 0.621，全样本 22.68x @20bps（至 10-07），样本外更新至 2026-11-11（51 天）：H5 +3h 较差口径 **0.9524x**、L125-V2 衍生品 **0.9787x**、BTC **0.8512x**；51 天 cash-start shadow：zero 口径 LS23 **0.9403x** vs L125 **0.9484x**，Bitget exact **0.9365x** vs **0.9440x**，仍 provisional；§00.19 资金费率 overlay（H6）**被拒**；**§00.20 H5 原候选在 N=6,142 下 DSR 结构性不可达；后续 §00.63 的 LS23 以同一 Top20/2022 台账刷新为 0.971481，已过该门槛**；样本内结论仍以 2026-09-25 审计为准。衍生品（§9.8/§9.9）：Bitget **真实 mark** 全量重跑，L125 **44.197x**（零 funding 上界）/ 30.078x（Bitget 实测 funding 水平 1.59x）/ 24.327x（3x adverse），全档 0 强平；DSR/RC/PBO（0.229）在真实 mark 候选族上同时通过；成交价口径已用 market K 线闭合（差 0.14–0.29%）；样本外 2026-09-22 起 51/365 天 L125-V2 0.9787x；**ZEC 集中度触发单一资产条款**、真实 funding 仅部分闭合（90 天水平校准）、pre-2022 压力窗口为 partial，故保持 provisional；§00.21：执行提前到 00:30/01:05 UTC，空头研究首轮和方向性快速 BTC 空头均被拒；§00.21.4：bottom-quintile 空头 + 20% stop 在 20bps 为 **51.8010x / 1.8918 / -42.59% / 0 强平**，但 100bps MDD -54.06% 且移除 2022 后低于基线，仍为 provisional，不接实盘；§00.21.5：bottom-8 持有带（R7）费用降至 2.56，但 50bps/100bps/MDD、移除 2022 和滚动最差均失败，rejected；§00.22：小时级 BTC 闸门与组合止损诊断全部不升级，实盘仍为 H5 多头；§00.23：30m 执行时点全扫被拒，00:30/01:30/02:00/50-50 分片均低于 01:00 同数据基线，成交权重覆盖率仅 78.14%，实盘继续 01:05 不改；§00.24：H5+H4+板块空头的 LS1 在 20bps 为 **26.2617x / 1.8603 / -27.60% / 0 强平**，但 100bps、双边 gross=1.3422x、移除最佳年份和全项目 DSR=0.9406 均失败，判定 rejected，实盘 H5 不变；§00.25：月频板块轮动 LS2 正式失败，候选 20bps **6.1748x / 1.2122 / -30.13%**，观测 Broker gross **1.2318x**，全成本档、滚动最差、最佳年份和 all_trials DSR=0.4634 均失败，rejected，实盘 H5 不变；§00.26：H5 退出币 21D 空头 LS3 在 20bps 为 **45.9190x / 1.8107 / -40.75%**，但观测 gross 1.0820x、MDD 超容忍线、100bps/滚动最差/PBO/DSR 失败，空头贡献 63.5% 来自 NEAR，rejected，实盘 H5 不变）；§00.27：H5 退出币固定风险空头 LS4 在 20bps 为 **23.8448x / 1.8091 / -34.12% / 0 强平**，2/20/50/100bps 全部高于同成本基线、observed gross 最高 0.9616x、12/12 真实引擎月度冷启动通过，但 365 天滚动最差 0.7838x 低于基线 0.7970x、Top20 DSR=0.9424 和全项目 DSR=0.9207 均失败，且实际最大单笔 adverse loss 0.6491% NAV 超过名义 0.5%，判定 rejected，实盘 H5 不变）；§00.28：LS5 在 LS4 退出空头上叠加 2.5% NAV/腿的 14D 最弱 4 币周频空头，20bps 为 **24.1210x / 1.8424 / -34.31% / 0 强平**，滚动最差 0.8083x、Top20 DSR 0.9523 和 12 个冷启动通过，但 100bps 7.7417x 低于基线 9.3848x、移除 2022 后低于基线、全项目 DSR 0.9334、前 3 空头贡献 126.53%，且 weak4 sleeve 净贡献 -2.662%，判定 rejected，实盘 H5 不变）；§00.29：LS6 只做 7D funding 上三分之一的 H5 退出币空头，20bps 为 **22.9279x / 1.7811 / -33.40% / 0 强平**，2/20/50/100bps、全部年份/最佳年份移除、45/45 路径切片、12/12 冷启动和集中度均通过，但滚动最差 0.7923x 低于基线 0.7970x，Top20 DSR=0.9326、全项目 DSR=0.9085 失败，判定 rejected，实盘 H5 不变）；§00.30：LS8 修复 UTC 日期 bug 后真实激活 37 个空头，20bps **22.8336x / 1.7744 / -33.52%**，但滚动最差 0.7909x 与 DSR 失败，rejected；§00.31：LS9 连续未使用风险预算 20bps **23.8832x / 1.7984 / -33.54%**，四档成本、45/45 路径、12/12 冷启动、集中度、PBO/RC 通过，但滚动最差 0.7865x、Top20 DSR 0.9382、全项目 DSR 0.9156 失败，rejected；实盘 H5 不变；§00.32：LS10 14D 相对 BTC 动量确认 20bps **22.1461x / 1.7567 / -33.54%**，成本/压力/年度通过，但滚动最差 0.7946x、NEAR 集中度 67.62%、DSR 失败，rejected；§00.33：LS11 BTC 200D 熊市闸门 + 最弱四币空头 20bps **49.7952x / 1.8069 / -40.65%**，2/20/50bps、funding 和滚动最差改善通过，但 100bps MDD -50.01%、删除 2022 后低于基线、45 个路径仅 22 个三项通过、前 3 空头贡献 90.57%，rejected；§00.34：LS12 双空头 regime router 20bps **55.7859x / 1.8520 / -40.64%**，2/50bps、funding、滚动最差和集中度通过，但 100bps 终值/Sharpe/MDD 三关失败、删除 2022 后 49.2413x 低于基线、路径 44/45，rejected；§00.35：LS13 周频 H5 相对 BTC 半仓 + LS12 20bps **33.7083x / 1.9633 / -28.37%**，Sharpe/MDD 改善但终值低于 L125 40.2200x，第一门槛失败，rejected；§00.36：LS14 周频轮入 25% BTC + LS12 20bps **43.5326x / 1.8786 / -36.49%**，2/20bps 通过，但 50bps 终值 26.3206x 低于基线 27.3725x、100bps 终值/Sharpe 失败、删除 2022 后低于基线、路径仅 13/45，rejected；§00.37：LS15 牛市弱 H5 10% 现金缓冲 20bps **48.3225x / 1.8431 / -38.11%**，2/20/50bps 和 100bps MDD 通过，但 100bps 终值/Sharpe 失败、删除 2022 后低于基线、路径仅 18/45，rejected；§00.38：LS16 5% NAV no-trade region 20bps **50.0481x / 1.8278 / -39.51%**，2/20/50/100bps 全胜同成本基线、100bps **15.4488x / 1.3536 / -49.12%**、费用较 LS12 -19.8%，但删除 2022 后 44.9539x < 50.0330x、路径仅 23/45 且 2023-2024 多起点 MDD 差 6.5-7.7pp，rejected；§00.39：LS17 非熊市全 Top20 高正 funding 4 币空头 20bps **46.2349x / 1.8548 / -37.96%**，funding 成本从 -0.7238 降至 -0.3044，但 observed gross 1.5265x / 57 breach hours、short stop 83 次、50bps 24.4102x 低于基线、100bps 8.3872x / 1.1362 / -50.89%，rejected；§00.40：LS18 H5 多头 funding 拥挤腿减半 20bps **34.6700x / 1.7700 / -33.05%**，Sharpe/MDD/funding 改善但终值低于 L125 40.2200x，主收益门槛失败，rejected；§00.41：LS19 H5 + 28D 反转多空 20bps **37.3924x / 1.6969 / -40.15%**，低于 L125 40.2200x/1.7330，且 11 次强平全在 long loser 腿，rejected；§00.42：LS20 H5 same-selection common-gross 20bps **39.4148x / 1.7683 / -40.56%**，0 强平/0 breach、跳 329 次 relative tilt，但终值略低于 L125 40.2200x，主收益门槛失败，rejected；§00.43：LS21 熊市空头只做正 funding 20bps **49.7281x / 1.8102 / -40.64%**，2/20/50bps 胜基线，但 100bps **12.4408x / 1.2579 / -50.10%** 三关失败，且 short episode 增至 367，rejected；§00.44：冻结样本外更新至 2026-11-10（50 天），H5 +3h 较差口径 **0.9524x / MDD -17.06%**、L125-V2 **0.9787x / MDD -17.47%**、BTC **0.8512x / MDD -14.88%**，相对 BTC 仍胜但绝对收益为负，窗口过短不解除 provisional；§00.45：LS22 单龙头极端涨幅减半 20bps **44.6607x / 1.8257 / -39.84%**，2/20/50/100bps 全胜 L125、100bps MDD -49.40%、滚动最差 0.8134x，但 45 个月初路径仅 37/45，预注册 gate 失败，provisional，不接实盘；§00.46：LS23 = LS22 多头利润保护 + LS12 双空头 router，20bps **61.9150x / 1.9448 / -39.84% / 0 强平**，四档成本全胜 L125、45/45 路径、12/12 冷启动、PBO 0.3528 / RC p=0.003996，DSR 见 §00.63 且仍通过，但 51 天 cash-start OOS 为 **0.9403x / -0.5584** 略低于同引擎 L125 0.9484x / -0.2743，pre-2022 funding proxy stress 为 **2.5189x / 1.7131 / -20.88%** 低于 L125 3.9238x/1.9618，12 个月 OOS 未满且 funding 仍为 proxy，provisional，不接实盘；§00.47：LS24 跨所 funding 确认空头 20bps **52.7881x / 1.8860 / -39.71% / 0 强平**，低于 LS23 61.9150x/1.9448，主收益与 Sharpe 门槛失败，rejected；修正审计时点后 Bybit 覆盖 91.6%，原 92.8% 读数作废；§00.48：LS23 shadow v2 完整 Bitget funding 0.9365x / -0.6125 / -17.65%，仍低于 L125 0.9440x / -0.3270 / -17.65%，provisional；§00.49：LS25 状态化利润保护 35.1755x / 1.7691 / -41.15%，rejected；§00.50：LS26 与 LS22 日收益完全等价，rejected/duplicate；§00.51：LS27 动态 LS12+R6 空头预算 20bps **68.8876x / 1.9599 / -41.40%**，但 50/100bps 成本失败、100bps MDD -56.08%、5 个 gross breach hours，rejected；§00.52：LS28 优先级 LS12→R6 预算 20bps **68.9318x / 1.9612 / -41.32%**，同样 50/100bps 失败、100bps MDD -56.00%、69–82 个 gross breach hours，rejected；§00.53：LS29 25% NAV 集中度条件利润保护 20bps **60.4392x / 1.9325 / -39.84%**，低于 LS23 61.9150x/1.9448，rejected；§00.54：LS30 市场中性 funding carry 20bps **48.9409x / 1.8110 / -40.34%**，高于 L125，但 1 次 DOT long 强平、26 个 gross breach hours，rejected；§00.55：LS31 60% long buffer 修正后 20bps **48.9593x / 1.8168 / -40.13% / 0 强平 / 0 breach**，但 50/100bps 成本失败、100bps MDD -56.40%，rejected at costs；§00.56：LS32 2x-entry-count carry 持有带 20bps **44.3989x / 1.7772 / -40.09%**，换腿 L1 从 70.5x 降至 48.875x，但低于 LS23 61.9150x/1.9448，且持有带让 DOT 多留至 **1 次 long 强平**，rejected；§00.57：LS33 LS23 优先 + residual funding carry 20bps **80.6764x / 2.0566 / -39.19% / 0 强平 / 0 breach**，2/20/50bps 全胜 LS23，LONG60 control 与 LS23 完全等价，但 100bps **11.8172x / 1.2648 / -52.87%** 低于 LS23 且越过 50% MDD 线，rejected at cost gate；§00.58：LS34 只在 residual carry 空头使用 2x 持有带，20bps **77.3635x / 2.0396 / -39.48% / 0 强平**，空头换手 688→502、累计 L1 70.5→58.875，但收益和 Sharpe 低于 LS33 80.6764x/2.0566，primary gate 失败，rejected；§00.59：LS35 true-carry（long funding<0 / short funding>0）20bps **74.0476x / 2.0383 / -39.50%**，100bps **11.2205x / 1.2515 / -52.15%** 仍低于 LS23，rejected；§00.60：LS36 short-only residual carry 20bps **69.5943x / 2.0159 / -39.94%**，100bps **12.6244x / 1.3029 / -51.37%**，仍越过 50% MDD，rejected；§00.61：LS37 14D residual carry 20bps **73.2343x / 2.0172 / -41.26%**，100bps **12.8731x / 1.2993 / -52.75%** 仍低于 LS23，低频化未修复成本尾部，rejected，停止 carry 频率家族；§00.62：LS38 LS23 same-side 5% no-trade band 20bps **54.5335x / 1.9102 / -38.69%**，费用 3.1262→2.5007 但终值和 Sharpe 低于 LS23，primary gate 失败，rejected；LS23 no-trade 家族停止，转回 incumbent 稳健性审计；§00.63/00.65/00.67/00.70：LS23 在当前 N=14,210/6,142 台账下 DSR **0.958973/0.971481**，PBO **0.3528**、RC zero p=**0.003996** / BTC p=**0.009990**，全部仍过预注册门槛，旧 0.99998 口径作废，候选仍 provisional、不接实盘；§00.64：LS39 LS23 + 60D/28D 低波动 4×4 pair 20bps **64.2279x / 1.9731 / -37.65%**，但新增 3 次 isolated long 强平（BTC/ETH/TON），违反零强平硬门槛，rejected；不扫描窗口、腿数、权重或频率，实盘不变；§00.66：LS40 LS23 + 60D 逆波动率多头重分配 20bps **29.8565x / 1.7063 / -41.30%**，0 强平、费用降至 2.3195，但终值和 Sharpe 远低于 LS23，说明 H5 sleeve 共识权重包含真实 alpha，rejected；停止逆波动率权重家族，实盘不变；§00.69：LS41 H5 多头 20% 逐腿 stop 20bps **57.2522x / 1.9036 / -39.835%**，19 次 long stop、0 强平、费用 2.9556，但终值和 Sharpe 低于 LS23，rejected；停止固定百分比 long-stop 家族，实盘不变；§00.71：LS42 LS23 利润保护释放权重仅向既有 H5 多头再分配，20bps **65.8147x / 1.9589 / -40.134% / 0 强平 / 0 breach**，四档成本、rolling、45 paths、12 cash-starts、PBO/RC/DSR 全过，但 51 天 OOS zero **0.9220x** / exact **0.9183x** 均低于 LS23 与 L125，故仅 provisional，不接实盘；§00.72：LS43 只向 7D 强于被减半 leader 的既有 H5 多头再分配，20bps **66.6800x / 1.9667 / -40.134% / 0 强平 / 0 breach**，四档成本均高于 LS23/LS42/L125，PBO 0.2532、DSR Top20/2022 0.974767、all 0.963433，当前 51 天 shadow 与 LS23 相同且无合格接收者；但删除 2024 后低于 LS23 2.71%、pre-2022 proxy MDD 差约 2–3pp，且无预注册后独立 12 个月 OOS，provisional，不接实盘；§00.73：LS44 在 LS22 触发后对 7D 转负龙头全退，20bps **60.5213x / 1.9361 / -39.056%**，9 次 full exit、0 强平、0 breach，MDD 改善约 0.78pp 但终值和 Sharpe 低于 LS23，rejected；§00.74：LS45 利润保护只向 21D 更强的既有 H5 持有者再分配，20bps **69.2088x / 1.9846 / -39.835%**，四档成本全胜 LS23/L125，但增量仍集中在 2024，51 天 OOS 与 LS23 相同，provisional；§00.75：LS46 在 LS44 全退后反手 0.20x / 28D 空头，20bps **67.6951x / 1.9919 / -34.916%**，四档成本、funding、12/12 冷启动、PBO/DSR 通过，但 51 天 OOS exact **0.9192x** 低于 LS23，provisional；§00.76：LS47 在 LS46 上禁止同一资产立即回补，20bps **69.4109x / 2.0023 / -34.916%**，四档成本、funding、12 个冷启动和 PBO/DSR 通过，但 45 条路径仅 42/45 胜 L125，51 天 OOS exact **0.9018x** 低于 LS23，provisional、不接实盘 |；§00.90 真实盘口 smoke：500 USDT 下单 25bps 深度充足、最大可见冲击约 0.46bps；§00.91 DVOL>75 多头全退主样本 73.8729x 但 2021 proxy 仅 1.0738x vs LS57 1.8872x，reject；§00.92 Bitget 官方逐笔成交 + L1 深度 maker shadow 在 2026 LS57 样本通过：433/443 events、名义覆盖 99.9938%、strict maker fill 74.9361%、加权成本 10.4467bps、相对 20bps taker 改善 +9.5533bps；仅为 shadow execution candidate；§00.93 maker fill haircut 25/50/75% 全部保持 >5bps：25% 下成本 13.0164bps、改善 +6.9836bps、fill 70.09%，但买入侧仅 +4.1094bps、long-open 为 -6.0770bps；结论仍为 shadow-only；§00.94 long-open taker routing 独立确认失败：2024-07→2025-12 的 long-open maker 改善 +15.24bps，而 2026 discovery 为 -6.08bps；路由使总体改善 +10.40→+7.69bps，rejected；§00.95 将 EX4 的 25% haircut 成本 13.0164bps 回填 LS57：77.6356x / 2.0312 / -38.964%，较 20bps 68.8077x 提升 12.83%，0 强平/0 breach；仅为 execution shadow，不修 PBO |
> | 数据 | `data/processed/panel_daily.csv`，研究样本 2022-01-01 → **2026-09-21**；冻结规格样本外跟踪 2026-09-22 → **2026-11-10**（仅运行跟踪，不用于选规则） |
> | 数据口径 | 市值与排名来自 CoinMarketCap；Gate/Binance/CoinGecko 只做独立校验；当天没有 CMC 市值的币当天不参与排名 |
> | 杠杆 | 现货轨：**全部无杠杆**，引擎默认强制 gross exposure ≤ 1.0，不做空。衍生品轨（§9，独立风险预算，Bitget isolated margin）在单独设计文档 `docs/superpowers/specs/2026-10-09-bitget-derivatives-track-design.md` 下研究，不得与现货轨的口径混用 |
> | 执行 | 信号收盘生成、T+1 执行；现货轨为收盘后约 3 小时成交，衍生品轨已切到 01:05 UTC 早盘执行（回测仍用 +3h 保守口径），用 Binance/Gate 1 小时 K 线模拟；缺失行情不静默填 0（短缺口按 carry 规则持有并逐条报告） |
> | 成本口径 | 基准 **2bps**（AGENTS.md），20/50/100bps 为压力测试 |
> | 主回测起点 | **2022-01-01**，剔除 2021 泡沫行情 |

> **硬约束（不可突破）**：所有策略研究、回测和实盘候选必须严格限制在 **point-in-time Top 20** 内。不得使用 Top 50、Top 100 或任何更宽股票池，包括“仅作灵敏度测试”的场景；如果某个假设需要更宽股票池，应直接否决或重新设计为 Top 20 内可验证的版本。Top 20 必须按当时真实市值重建，禁止用当前名单回填历史。

---

## 00. 2026-09-25 全面审计与修复后的权威结论（取代 §0 中与此冲突的数字和判定）

> 2026-09-23 → 09-25 对全仓库做了代码审查（数据层、回测引擎、策略、验证统计、API、前端、历史研究代码）。每个确认的缺陷都先写失败测试再修复；随后在修复后的代码上重跑了全部 phase momentum 报告。研究样本仍为 2022-01-01 → 2026-09-21，**此后的数据保留为冻结冠军的真正样本外**，不再用于任何挑选。

### 00.1 判定：冠军仍是研究候选（provisional），不是已验证策略

> **规格已被 §00.11 取代（2026-10-08）**：冻结规格现在是 H3（Top20 宽度共闸 50/50 混合，`PR2026-10-H3`），不再是本节表中的 B（单 book 冠军）。下表保留为切换前的 B 审计记录，数字仍然有效（B 依旧是基线）。

| 门槛（AGENTS.md） | 结果 | 判定 |
|---|---|---|
| ≥20x（基准成本 2bps，实盘成交时点：收盘后 3h，取两种缺 K 线假设中较差者） | **24.42x**，Sharpe 1.45，最大回撤 -43.7% | 通过 |
| 20bps 压力，同一成交时点 | **19.56x**（50bps 13.50x，100bps 7.27x） | 略低于 20x |
| 多重检验：Deflated Sharpe，按项目真实试验数 | Top20/2022 口径 N=6,132：**0.731**；全部 N=14,126：0.678；只算 30 个变体家族：0.995 | **失败**（<0.95） |
| 事后挑参数的过拟合概率 PBO | 0.526 | **失败**（>0.5）；只能用固定主规格 |
| 参数邻域 | BTC 闸门 MA100 → MA50/MA150/MA200：9.50x/11.61x/6.93x；持有排名 Top2 → Top1/Top3：14.55x/9.49x（20bps，收盘成交）；H2/H3 预注册邻域复核见 §00.6 | **失败**：结果依赖单一窄参数（AGENTS.md 明确不算稳健） |
| White Reality Check（30 变体家族） | 对零 p=0.019；对 BTC 买入持有 p=0.025 | 家族内通过；全项目无法计算（多数历史试验没有保存日收益） |
| walk-forward（预设 25 变体，365D 训练/90D 测试，2023 起，40bps 切换成本，收盘成交） | 20.78x，Sharpe 1.62 | 通过（仅收盘成交口径） |
| 去掉最佳年份 2023 | 4.83x（BTC 0.71x） | 仍优于 BTC |
| 2020-10 → 2021-12 压力 | 20bps 4.55x，Sharpe 2.39，回撤 -18.9%（BTC 4.39x） | 通过 |
| 逐条选币审计（更严格版本） | 10,308 条选币、3,436 次持有规则检查、990 条成交目标：0 违规 | 通过 |

结论：按 AGENTS.md，冠军在**基准成本下即使按真实成交时点也超过 20x**，但**多重检验（DSR 0.73、PBO 0.53）和参数窄峰两道门槛不通过**，所以只能保持 provisional。这两项都来自研究历史本身（6,132 次 Top20 试验、窄峰参数），在同一段样本上再怎么调都无法修复；唯一干净的办法是冻结规格，用 2026-09-21 之后没有任何试验见过的数据做真正的样本外检验。2026-10-08 按预注册补跑的 H2/H3 邻域（6 个新试验，见 §00.6）进一步显示：窗口集成 H2 去掉 MA50/MA100/MA150 任一窗口即失去判据，宽度共闸 H3 只在 0.55 阈值下保住判据——两者都只能作为已记录的 risk variant，不能替代或“修复”冠军。

### 00.2 修正前后对照（旧数字一律作废）

| 项目 | 旧（§0.1/§0.2） | 新（2026-09-25） | 说明 |
|---|---|---|---|
| 成交时点 @20bps | 未测，隐含“收盘价成交” | 收盘 23.09x；+1h 21.22x；**+3h 19.56x**；+6h 20.78x；+12h 21.57x；次日收盘 12.01x；延迟 2 天 5.11x | `reports/phase_momentum_execution_lag_2022/`；91.8% 的成交权重在成交时刻有可用的 Binance/Gate 小时 K 线，其余（Bitget Token 两家都没有、个别币在交易所上市前的日期、开盘价与 CMC 前收差距 >5% 的日期）分别按“次日收盘”和“信号收盘”两种假设成交，取较差者 |
| Deflated Sharpe | 0.9945（只按 32 个候选） | 家族 0.995；**Top20/2022 全部试验 0.731**（N=6,132）；全部试验 0.678（N=14,126） | `reports/research_trial_inventory/`（可复现盘点）、`reports/phase_momentum_multiple_testing_2022/` |
| White Reality Check | p=0.0150 | 家族对零 p=0.019、对 BTC p=0.025 | 旧值只对主策略单独做，没有任何多重校正 |
| PBO | 0.6288 | 0.526 | 按论文 logit 规则、去掉 2 个与主策略完全相同的候选、分块覆盖全部日期 |
| 固定主策略 CSCV | “通过”，低于中位数 7.47% | 2.06% | **不再计为证据**：训练/测试排名分布在构造上相同，只是样本内诊断 |
| 固定主策略 2023 起 | “OOS 29.91x” | 29.91x | **重标为样本内**：参数是用全样本挑的 |
| 市场状态拆分 | bull 51.83x / non-bull 0.445x | bull **25.37x**（BTC 3.27x）；non-bull **0.91x**（BTC 0.57x） | 旧版用当天收盘判定当天状态（前视），现用前一天状态 |
| 币自身趋势过滤 50/100/150/200D | 17.57/14.71/10.68/10.57x | **24.39/16.70/17.03/11.13x** | 旧版按列而不是按行取趋势，导致每天强制换仓；trend_50 事后看三项都优于主策略，但属事后发现，不能直接升级 |
| 参数等权集成 | “等权” | 按参数组真正等权：20bps **16.63x**；leave-one-parameter-out 15.81–17.65x | 旧版实为按 sleeve 等权 |
| 月度起点敏感性（54 个起点） | 沿用 2022 年起的路径 | 每个起点重新构建：中位 7.18x，最差 1.69x，最好 31.57x | 旧版切片起步空仓且继承 2022 路径 |
| 收盘成交主数字 | 20bps 23.09x、2bps 28.80x | 不变 | 各项修复没有改变冠军的实际交易 |

### 00.3 本轮修复中影响研究数字的缺陷

- **回测引擎**：权重上限按 NAV 而不是按已投资部分施加；NaN 目标/敞口直接报错；窗口外的目标日期不再静默丢弃；杠杆被默认禁止；新增收盘后 H 小时成交（`pre_fill_returns`）和短缺口 carry 规则（`gap_carries` 逐条报告）。
- **股票池/数据**：缺行情日的成交量不再填 0；缺口日收益改为缺失并由下一次报价补齐跨缺口涨跌，不再静默记 0；**当天没有 CMC 市值的币当天不参与排名**（2022-07-31 chainlink、kucoin-shares，2022-07-29/30 curve）；CoinGecko 日期错位一天（中位偏差 2.61% → 0.079%）；多源校验不再“一个源通过就忽略其他源的分歧”；CEL 别名错指到 COMP（已移除）；120 日均线预热不足（buffer 按配置最长回看推导）；数据层对 2022 年以来的面板数值**零改动**。
- **分析指标**：Sortino 改用下行偏差；回撤从初始资金起算；切片结果的总收益不再丢第一天；月末再平衡日不再把未结束月份的最后一天当月末；类别排除（稳定币等）的兜底真正生效；总市值指数改为链式计算（不再受面板进出影响）。
- **验证统计**：见 §00.2；试验盘点改为仓库内可复现脚本 `scripts/build_trial_inventory.py`，并新增预先登记台账 `reports/research_trial_inventory/preregistered_trials.csv`。

### 00.4 下一步

1. **冻结**当前主规格（`PhaseMomentumSpec` 默认值 + `PRIMARY_SIGNAL_SPECS`），以 2026-09-22 起的数据做真正样本外记录，不再调参。
2. **预先登记的新一轮假设**（依据 `docs/research/literature_review_2026-09.md` 第 4 节，参数全部来自文献或已有消融，不做网格）：H2 BTC 闸门窗口集成、H3 Top20 市场宽度共同闸门、H4 每个 sleeve 持有前五分之一（4 个币）。结果写入 `reports/phase_momentum_hypotheses_2026_10/`，每次运行先登记再执行，计入试验总数。
3. **H1（23:00 UTC 提前一小时决策、收盘成交）需要项目负责人决定**：它与“信号在收盘生成”的规则冲突，未经确认不运行。符合现行规则的替代方案是缩短数据链路：+1h 成交在 20bps 下为 21.22x（+3h 为 19.56x）。该替代方案的落地清单见 `docs/operations/execution_latency.md`。**测量已于 2026-10-08 启动**：`ops/com.atlas20.cmc-probe.plist` 已安装为 launchd 作业，在 00:05–03:50 UTC 每 15 分钟跑一次 `scripts/probe_cmc_publication.py`（每次 10 个币、160 请求/天，约为一次正常刷新的 1.5 倍），结果追加写入 `reports/provider_publication/cmc_publication_probe.csv`；首次冒烟运行成功（2026-10-07 覆盖 10/10）。用 T90（≥90% 样本拿到 D-1 的最早 UTC 时刻）决定刷新时点与成交时点。

### 00.5 2026-10-08 冻结规格样本外跟踪（16 天，仍为 provisional）

> **规格已被 §00.11 取代（2026-10-08）**：本节记录的是切换前的 B（单 book 冠军）。`reports/phase_momentum_oos_2026/` 现在跟踪 H3；在这 16 天里宽度共闸从未触发，H3 与 B 的收益逐位相同，所以本节数字对 H3 同样成立。

- **规格冻结**：`PhaseMomentumSpec` 默认值 + `PRIMARY_SIGNAL_SPECS`；没有根据 2026-09-22 之后的结果调参、换币、改成本或改执行规则。
- **样本外窗口**：2026-09-22 → 2026-10-07，共 16 个日收益。面板已刷新至 2026-10-07，且该日通过完整收盘校验（97 个资产全周数据、成交量与市值覆盖率达标）。
- **执行口径**：信号收盘生成，T+1；实盘成交按收盘后 3 小时，使用 Binance 1 小时 K 线。该窗口实际交易目标为 `NEAR`、`ZEC`，小时 K 线成交权重覆盖率为 **100%**，因此 `day_close` 与 `prior_close` 缺 K 线假设在本窗口结果相同。

| 成本 | +3h 总收益 | Sharpe | 最大回撤 | BTC 同期 |
|---:|---:|---:|---:|---:|
| 2bps | **1.0902x** | 3.316 | -10.50% | 0.9616x |
| 20bps | **1.0883x** | 3.260 | -10.57% | 0.9616x |
| 50bps | **1.0853x** | 3.166 | -10.67% | 0.9616x |
| 100bps | **1.0803x** | 3.009 | -10.84% | 0.9616x |

- **解读**：样本外开局为正，并跑赢同期 BTC；但 16 天远远不足以通过 DSR、PBO、参数邻域和多年份稳健性门槛。冠军仍然是 **provisional**，这段结果不能用来解除任何门槛，也不能反过来成为调参依据。
- **最新信号（截至 2026-10-07）**：BTC 100D 闸门开启；12 个 sleeve 的聚合目标为 `NEAR 68.37%`，生产引擎当前漂移仓位为 `NEAR 70.62%`；最近一次目标日期为 2026-10-03，因此当前 `trade_required=false`；下一次检查日期为 2026-10-08。
- **数据链修正（2026-10-08 刷新）**：EOS、HT、MKR 在迁移/退市后 CMC 仍打印 legacy 价格但 `marketCap=0`。处理器现在截断「最后一次正市值之后、超出 7 天宽限」的纯价格尾部，并把「市值 feed 已结束、当前独立缓存无法回看比对」的资产标记为 `crosscheck_historical_unverified`：历史保留（point-in-time 名单不重写），但市值结束日之后永不参与排名；审计对这类资产报 WARN 而非 FAIL，已证实的分歧仍然 FAIL。HT 的 34 行价格级损坏（已移除）在缺口检查中按文档化移除豁免为 WARN。数据链审计现为 **FAIL=0**（42 PASS / 9 WARN）。
- **对研究样本无影响（已核验）**：被截断的行全部在「最后一次正市值」之后；`build_rebalance_universe` 对 carry 来的市值明确拒绝排名（逐日记录 "no same-day market cap from CMC"）。在 2022-01-01 → 2026-10-07 的日频名单里，EOS、HT 从未进入 universe，MKR 最后一次进入是 2023-10-14（其市值 feed 结束于 2025-05-25），因此被截断的行不可能被选中或持有；冠军与 H2-H4（样本到 2026-09-21）的选币名单和组合收益不会因本次截断而改变。
- **复现**：`.venv/bin/python scripts/run_phase_momentum_oos.py --end-date 2026-10-07`；最新信号 `.venv/bin/python scripts/run_phase_momentum_live_signal.py --output-dir reports/phase_momentum_live`。报告在 `reports/phase_momentum_oos_2026/`，不包含任何参数搜索。


### 00.6 2026-10-08 H2/H3 预注册邻域结果（6 个新试验，N 6,126 → 6,132）

- **为什么现在跑**：文献综述 §4 规定邻域只在父假设通过 kill criterion 之后运行；H2（8.79x）和 H3（19.90x）在 2026-09-25 都通过了各自判据，因此按预注册先登记、后运行 6 个新试验：H2 的 4 个 leave-one-window-out 集成（分别去掉 MA50/100/150/200）与 H3 的相邻阈值 0.45/0.55。样本窗口、成本与成交口径不变（2022-01-01 → 2026-09-21；20bps 判定，2/50bps 复读；+3h 成交、两种缺 K 线假设取较差者）。每个邻域试验沿用其父假设的判据。
- **H2（BTC 闸门窗口集成）不稳健**：4 个 LOO 里只有去掉 MA200 的集成保住判据；去掉 MA50/MA150 超回撤容忍（MDD 差于 B 的 2 个百分点），去掉 MA100 低于四个单窗口变体的中位数（7.67x）。

| LOO（去掉） | 20bps +3h 总收益 | 最大回撤 | 判定 |
|---|---:|---:|---|
| MA50 | 9.93x | -51.5% | FAIL（回撤超限，阈值 -47.7%） |
| MA100 | 7.37x | -47.8% | FAIL（低于单窗口中位数 7.67x） |
| MA150 | 8.71x | -47.8% | FAIL（回撤超限） |
| MA200 | 9.91x | -42.7% | 通过 |

- **H3（Top20 宽度共同闸门）只在 0.55 阈值下稳健**：阈值 0.55 在 20/2/50bps 三个成本下都满足全部三个端点（20bps：MDD 改善 10.91pp、Sharpe 1.383 > B 1.370、1 年滚动最差 0.744 > B 0.711）；阈值 0.45 在 20bps（MDD 改善 7.00pp）与 2bps 通过，但 50bps 回撤改善降到 4.70pp（<5pp）→ 方向不一致，判为未通过。
- **判定与门槛不变**：邻域结果只用于稳健性解读，冠军仍冻结、仍为 **provisional**；新增 6 个试验使 DSR 分母从 N=6,126 升到 **N=6,132**，冠军 DSR 由 0.735 降到 **0.731**（全部试验口径 0.682 → 0.678；家族 30 口径 0.995 不变），PBO 0.526 不变，DSR/PBO/窄峰三关结论不变（仍失败）。
- **复现**：`.venv/bin/python scripts/build_trial_inventory.py` → `scripts/run_phase_momentum_hypotheses.py` → `scripts/run_phase_momentum_hypotheses.py --evaluate-only` → `scripts/run_phase_momentum_multiple_testing.py`。明细见 `reports/phase_momentum_hypotheses_2026_10/neighbourhood.csv` 与 `reports/phase_momentum_multiple_testing_2022/`。

### 00.7 2026-10-08 入场者归因：冠军收益来自在位币，不是临时入场币（直接检验 [S16]）

- **为什么做**：文献综述 §3.9 与 §4.0 要求每个假设把收益拆成「进入 Top20 不超过 29 天的入场币」与「在位币」，用来直接检验 [S16]（Grobys et al. 2026, *On survivor cryptocurrency momentum*）的幸存者批评——「加密动量收益是那些只能临时交易的币的假象」。这是一个**预声明**的归因指标，不是新试验，不计入 N。
- **口径**：用引擎实际账本按日归因（目标日按成交时刻前/后分段计收益，其余按漂移仓位），按**信号日 t-1** 的 CMC Top20 身份分类：`entrant` = 当前连续入榜区间开始 ≤29 天；`incumbent` = ≥30 天；`non_member` = 持有但当天已不在 Top20（正常应为 0）。贡献 = Σ 各币当日「权重 × 收益」；份额 = 该类贡献 / 全部贡献之和。样本 2022-01-01 → 2026-09-21，成本 20bps。
- **结果（冠军 PR2026-10-B）**：

| 成交口径 | entrant 份额 | incumbent 份额 | non_member 份额 | entrant 贡献 | incumbent 贡献 |
|---|---:|---:|---:|---:|---:|
| 收盘成交（lag 0） | **-7.81%** | 107.81% | 0.00% | -0.322 | 4.447 |
| +3h（`day_close`，较差口径） | **-9.28%** | 107.49% | 1.79% | -0.367 | 4.254 |
| +3h（`prior_close`） | **-7.97%** | 106.98% | 0.99% | -0.318 | 4.264 |
| 延迟一天（lag 1） | **-15.23%** | 110.70% | 4.53% | -0.526 | 3.821 |

- **解读**：在冠军里，入场币是**小幅负贡献**（实盘 +3h 口径 −8% 到 −9%），在位币贡献了全部收益（>100%）。也就是说冠军的收益**不是** [S16] 所说的「临时可交易币」假象，反而是这些新入榜币略微拖累收益；延迟一天时入场币的负贡献扩大到 −15%，与「入场币是最滞后、最容易被延迟吃掉的那部分」一致。H3（Top20 宽度共闸）的入场币份额约 −0.5%（风险关闭时入场币更少），方向相同。
- **对 seasoning filter（只买上市/入榜满 N 天的币）的判定**：文献综述 §5 的逻辑是「若入场币贡献收益，则 seasoning 砍掉收益来源；若不是，则 seasoning 无关紧要」。这里入场币贡献为负，所以按该逻辑 seasoning **无关紧要**；虽然事后看剔除它可能小幅提高样本内收益，但那是**在样本上事后挑选**、且会引入一个新自由参数（窗口 N）、进一步抬高 N，因此**不新增该试验**。
- **边界**：这是单一样本（2022-01-01 → 2026-09-21）的归因，不构成稳健性证据，也不改变冠军的 provisional 状态。它只回答「收益是否来自临时入场币」这一个问题。
- **复现**：`.venv/bin/python scripts/run_phase_momentum_hypotheses.py`（完整运行会在 `reports/phase_momentum_hypotheses_2026_10/` 写出 `entrant_attribution.csv`；`--evaluate-only` 只重算判定并读取该文件）；明细见同目录 `entrant_attribution.csv`（同一脚本输出 H2/H3/H4 与邻域的全部归因行）。

### 00.8 2026-10-08 逐币归因：20x 是「五个币」的故事（AGENTS.md 的「单一资产依赖」条款）

- **为什么做**：AGENTS.md 明确「结果不能依赖一个窄参数、一个相位、一年、**一个资产**或少量交易」。此前项目只做过 leave-one-sleeve（21.26x–23.91x）、leave-one-signal（20.58x–27.58x）和去掉最佳年份，**没有做过逐币归因**。这是补上这一条，不是新试验。
- **口径**：与 §00.7 入场者归因完全相同的引擎账本会计（目标日按成交时刻前/后分段，其余按漂移仓位），但保留币维度：贡献 = Σ 每日「权重 × 收益」，share = 该币贡献 / 全部贡献之和。冠军、20bps、+3h、较差缺 K 线口径（`h3_day_close`，19.5575x）。
- **结果（贡献份额，前 7 名）**：

| 排名 | 币 | 贡献 | 份额 | 累计 |
|---:|---|---:|---:|---:|
| 1 | solana | 1.216 | 30.73% | 30.73% |
| 2 | zcash | 0.708 | 17.89% | 48.62% |
| 3 | hyperliquid | 0.573 | 14.48% | 63.10% |
| 4 | avalanche-2 | 0.556 | 14.05% | 77.15% |
| 5 | bitcoin-cash | 0.521 | 13.15% | **90.31%** |
| 6 | sui | 0.362 | 9.16% | 99.46% |
| 7 | dogecoin | 0.334 | 8.45% | 107.92% |

前 5 个币合计 **90.31%**；贡献 HHI = 0.2112。共持有过 37 个币，而且**被选中的 sleeve-日分布是均匀的**（10,308 条选币里最高是 hyperliquid 8.1%、solana 7.8%、zcash 6.9%）——所以集中不是「一直满仓某个币」，而是少数几个币在被持有期间跑出了极端行情（文献 [S14]「一个币就能决定大盘动量组合」的形态）。
- **反事实（只去掉该币的每日贡献，仓位不变）**：

| 情景 | 终值 |
|---|---:|
| 完整冠军 | **19.56x** |
| 去掉 solana | **6.62x** |
| 去掉前 3（SOL/ZEC/HYPE） | **2.07x** |
| 去掉前 5（+AVAX/BCH） | **0.80x** |

去掉前 3 后只剩 2.07x（BTC 买入持有为 1.87x），去掉前 5 后直接亏损。**必须同时说明：这不是一个可交易策略**——事前不知道哪 5 个币会赢——它只回答「收益从哪来」，是集中度度量。
- **判定**：这**直接触发 AGENTS.md 的「不能依赖单一资产」条款**，是冠军必须保持 **provisional** 的又一条独立理由，且这条在样本内无法修复：唯一被预注册过的分散化方案 H4 已被证伪（3.15x）。H3（宽度共闸）也解决不了它——前 5 份额 84.1%，去掉前 5 后 1.08x，只是略好于冠军。
- **对后续的含义**：① 样本外跟踪必须同时报告这个集中度（同样的 5 个币是否还在贡献收益）；② 任何「提高稳健性」的尝试都要面对「收益就是来自少数币的大行情」这一事实，不能指望用分散化同时保住 20x。
- **现金计息敏感性（计量口径，默认不计入 headline）**：引擎给现金 0% 利息，而组合平均 gross exposure 只有 **36.0%**（64% 现金）。把闲置现金按固定年化利率计息后，冠军 20bps +3h 口径为：0% → 19.5575x；**2% → 20.7772x**；4% → 22.0729x；5% → 22.7507x。这是一个**保守假设的敏感性**，不是 alpha：它不改任何规则，也不改善 DSR/PBO/窄峰三关；是否把它计入 headline 需要项目负责人明确决定（未经决定前 §00.1/§00.5 的数字保持不变）。H3 同样口径为 19.9004x / 21.2634x / 22.7196x / 23.4847x。
### 00.10 2026-10-08 候选同口径横评：H3 全面优于冠军（含 DSR 口径修正）

- **先修一个口径错误**：此前冠军的 DSR 引的是 `reports/phase_momentum_multiple_testing_2022/` 的 **0.731**（候选 `primary`，Sharpe **1.4325**，即**收盘成交**），而 H2/H3/H4 的 DSR 来自 `reports/phase_momentum_hypotheses_2026_10/dsr.csv`（Sharpe 1.3700，即**+3h 成交**）。文献综述 §4.0 规定 DSR 用 **20bps、+3h、较差缺 K 线** 的日收益，所以在协议口径下冠军的 DSR 是 **0.679**，不是 0.731。两者都远低于 0.95，门槛结论不变；但这让"冠军 vs 变体"的比较一直不是同口径的。
- **做法**：把 5 个已注册规格放进同一个 harness、同一批成交口径重跑（`scripts/evaluate_phase_momentum_candidates.py`）。不新增试验、不做任何选择。
- **20bps、较差缺 K 线、+1h 成交（实盘目标口径）**：

| 规格 | 总收益 | Sharpe | 最大回撤 | 1年滚动最差 | 去掉最佳年 | 年换手 | 平均仓位 | DSR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B 冠军 | 21.22x | 1.398 | -46.6% | 0.753 | 4.57x | 26.0 | 36.0% | 0.703 |
| H2 闸门集成 | 10.02x | 1.177 | -47.8% | 0.749 | 2.95x | 27.8 | 36.8% | 0.501 |
| **H3 宽度共闸 (0.50)** | **23.44x** | **1.534** | **-33.4%** | **0.768** | **6.44x** | **24.6** | **29.9%** | **0.808** |
| H3 邻域 0.45 | 22.87x | 1.514 | -34.6% | 0.768 | 6.28x | 24.8 | 30.4% | 0.793 |
| H3 邻域 0.55 | 18.62x | 1.456 | -30.2% | 0.768 | 4.78x | 24.6 | 29.3% | 0.751 |

- **20bps、较差缺 K 线、+3h 成交（当前实盘口径）**：

| 规格 | 总收益 | Sharpe | 最大回撤 | DSR |
|---|---:|---:|---:|---:|
| B 冠军 | 19.56x | 1.370 | -45.7% | 0.679 |
| H3 (0.50) | 19.90x | 1.466 | -37.7% | 0.758 |
| H3 邻域 0.45 | 17.72x | 1.412 | -38.7% | 0.714 |
| H3 邻域 0.55 | 15.48x | 1.383 | -34.8% | 0.691 |

- **DSR 按成交口径**：B = 0.731（收盘）/0.703（+1h）/0.679（+3h）；H3 = 0.801/0.808/0.758。**H3 在每一个口径上 DSR 都高于冠军。**
- **评估**：在实盘目标口径（+1h）下，H3 在**收益、Sharpe、最大回撤、1 年滚动最差、去掉最佳年、换手、平均仓位、DSR 八项上全部优于冠军**，且是预注册通过判据的规格，不是事后挑的。它唯一不稳健的是**收益**：阈值 0.45/0.50/0.55 在 +1h 下为 22.87x/23.44x/18.62x（0.50 是峰值，但 0.45 只低 2.4%）；**回撤优势是单调且稳健的**（-34.6%/-33.4%/-30.2%）。
- **判定**：H3 仍是 **provisional**（DSR 0.808 < 0.95；PBO 尚未对 H3 计算；阈值邻域仍属窄峰）。按预注册 tier 规则，+3h 口径下它仍是 tier 2（19.90x < 20x），+1h 口径下 23.44x ≥ 20x。但按同口径比较，**它已经是一个严格更好的候选**。
- **本轮评估结论（我的判断，待项目负责人批准后才改写 §00.1/§00.5 的主规格）**：
  1. 如果目标函数是「在可接受风险下跑赢 BTC」（AGENTS.md 的措辞），**H3 是更好的规格，我建议采用**：它在实盘目标口径下八项全胜，回撤优势单调稳健（-30% 到 -35% vs -46.6%），且它是预注册通过的。
  2. 如果目标函数是「最大化收益上限」，则维持冠军：H3 的**收益**优势来自 0.50 这个阈值，而该阈值本身是 §0.8 早期样本内扫描选出来的（40/45/50/55/60 → 50 最优），属于二次选择，不能当作可靠优势。
  3. 无论选哪个，都仍是 **provisional**（DSR 最高 0.808 < 0.95，PBO 未对 H3 计算），且都要靠 +1h 执行才能真正站上「20bps 下 20x」。
  4. 换规格不是一行文档改动：`scripts/run_phase_momentum_live_signal.py` 目前只构造冠军的单 book 规格，采用 H3 需要同时改造它（OOS 跟踪端已支持 `--trial-id PR2026-10-H3`）。
- **复现**：`.venv/bin/python scripts/evaluate_phase_momentum_candidates.py`；明细 `reports/phase_momentum_candidate_eval/`。

### 00.9 2026-10-08 实际持仓：所谓「12 个 sleeve」其实是一个 1–2 币的组合

- **为什么做**：规格一直被描述成「12 个单币 sleeve」，听起来像 12 个独立下注、互相分散。§00.8 发现收益集中在 5 个币，于是直接测量组合**实际**持有了几个币。
- **口径**：冠军（`PhaseMomentumSpec` 默认 + `PRIMARY_SIGNAL_SPECS`），20bps、收盘成交、2022-01-01 → 2026-09-21（1725 天）；`largest_share` = 当日最大单币权重 / 当日 gross exposure。
- **结果**：

| 指标 | 数值 |
|---|---:|
| 有仓位天数（gross > 0） | 858 / 1725 |
| 平均 gross exposure（全样本） | 36.0% |
| **有仓位时平均持有的不同币数** | **1.99** |
| 最大单币占组合比的中位数 | **75.3%** |
| 最大单币占组合比的 75 分位 | **100.0%** |
| 单币 ≥50% 组合的有仓位天数 | **90.0%** |
| 单币 ≥75% 组合的有仓位天数 | 50.3% |
| 只持有一个币的有仓位天数 | 26.9% |
| 组合 HHI（等权 2 币 = 0.5） | **0.685** |

持有币数分布（有仓位天数）：1 币 231 天、2 币 439 天、3 币 151 天、4 币 36 天、5 币 1 天。

- **解读**：12 个 sleeve 的信号高度相关（都是 7–60 日 trailing return，只差检查相位），所以它们绝大多数时候指向同一个币——**这个策略实际上是一个单币（最多两币）轮动**，不是 12 币组合。这直接解释了 §00.8（5 个币贡献 90% 收益）和 -45% 的回撤：回撤就是那一个币的回撤。它也说明 §3.7「distinct coins across sleeves give partial diversification」这个设计假设**在当前规格下不成立**。
- **对「优化」的含义**（这是本轮最重要的结论）：既然实际只有一个币，那么
  - 所有分散化尝试都会**削掉收益**而不是「免费降风险」——H4（每个 sleeve 持 4 币）把 19.56x 打成 3.15x；§0.8 的宽度闸门也把 2bps 全样本从 28.92x 降到 23.10x/16.61x（换来的是回撤与 2024 起收益）。
  - 剩余的风险旋钮（vol target、闸门、止损）全都是**收益/风险权衡**，不是免费的：0.6/0.8/1.0 → 13.44x/-36.9%、23.09x/-44.9%、29.99x/-50.9%。
  - 也就是说：**样本内不存在「免费提高收益」的杠杆了**。20x 就是这个集中度的价格。
- **复现**：`.venv/bin/python scripts/analyze_phase_momentum_book.py`；明细 `reports/phase_momentum_book_concentration/daily_book.csv`。
- **已接入样本外跟踪**：`scripts/run_phase_momentum_oos.py` 现在同时输出 `oos_coin_attribution.csv` 与 `oos_concentration.csv`，report.md 增加「OOS per-coin concentration」小节（每个成本取较差缺 K 线口径），并给出同样的 drop-top1/drop-top5 反事实。当前 16 天窗口只有 `near` 一个贡献币（份额 122%，窗口太短、不构成证据）。
- **复现**：`.venv/bin/python scripts/attribute_phase_momentum_assets.py`（冠军）与 `... --trial-id PR2026-10-H3 --output-dir reports/phase_momentum_asset_attribution_h3`；报告在 `reports/phase_momentum_asset_attribution/` 与 `reports/phase_momentum_asset_attribution_h3/`。

### 00.11 2026-10-08 采用 H3 作为冻结规格（仍为 provisional；取代 §00.1/§00.5 的规格指定）

> **规格已被 §00.13 取代（2026-10-08）**：冻结规格现在是 **H5**（`PR2026-10-H5`，H3 的 50/50 结构 + 横截面离散度叠加）。本节记录 H3 的采用过程，数字仍然有效（H3 依旧是 H5 的对照规格）。

- **决定**：按 §00.10 的同口径横评，本轮把冻结规格从 **B（单 book 冠军）** 切换为 **H3（Top20 宽度共闸 50/50 混合，注册号 `PR2026-10-H3`）**。这是一次**规格指定**的切换，不是新的参数搜索：H3 在运行前已登记、通过了自己的 kill criterion，切换没有使用 2026-09-22 之后的任何数据来挑参数。
- **切换后的规格**：24 个 sleeve = 2 个 book × 12 个 sleeve，等权 1/24。
  - book A = 冠军（`PhaseMomentumSpec` 默认值 + `PRIMARY_SIGNAL_SPECS`）。
  - book B = 冠军 + Top20 宽度共闸：breadth(D) = 当日 point-in-time Top20 中收盘价高于自身 50D SMA 的占比，breadth(D) ≥ 0.50 才 risk-on（无 confirm）；不满足时 book B 的 sleeve 全部转现金。
  - 在**目标层面**做 50/50 混合，生产引擎在每次目标事件向 50/50 再平衡并按该次运行的成本计费；其余规则（信号收盘生成、T+1、2bps 基准成本、长仓现货无杠杆、gross ≤ 1.0）不变。
- **协议口径（20bps、+3h、较差缺 K 线）的头条结果**（`reports/phase_momentum_candidate_eval/`）：

| 指标 | B（切换前） | **H3（切换后）** |
| --- | ---: | ---: |
| 总收益 | 19.56x | **19.90x** |
| Sharpe | 1.370 | **1.466** |
| 最大回撤 | -45.7% | **-37.7%** |
| DSR | 0.679 | **0.758** |

- **+1h 实盘目标口径**（若 CMC 发布时间探针证明 00:30 UTC 前可拿到 D-1 收盘）：H3 **23.44x** / Sharpe 1.534 / MDD **-33.4%** / DSR 0.808；B 21.22x / 1.398 / -46.6% / 0.703。H3 在 +1h 口径下同时站上 20x。
- **仍然失败 / 未证明的门槛**（与 §00.1 相同，只是数字换成 H3；任何一条都不因切换而解除）：
  - **DSR**：协议口径 **0.758**（+1h 0.808）< 0.95 → **失败**。
  - **PBO**：已补算 → **失败**。在同一 20bps、收盘成交口径下，把 H3 三档（0.45/0.50/0.55）并入原 30 个单规格变体（去重后 33 个候选）重跑 CSCV（`scripts/run_phase_momentum_multiple_testing.py`，与 §00.1 的 B 同一方法，先复现 B 的 0.525974 再算）：**PBO = 0.558**（B 为 0.526）。只看 H3 邻域的口径更差：H3 三档 + B 共 4 个候选为 **0.658**，只看 H3 三档为 **0.775**。H3 (0.50) 在这族里的全样本收盘 Sharpe 最高（1.5233），也是被选中最多的候选（334/924），但样本外排名落在中位数以下的比例仍 >50%。结论：**PBO 门槛对 H3 同样不通过**（B 也不通过），切换规格不能解除这道门槛；这与 §00.10 的采用理由一致——采用 H3 靠的是回撤优势，不是 PBO。
  - **参数窄峰**：收益对宽度阈值敏感（+1h 下 0.45/0.50/0.55 → 22.87x/23.44x/18.62x，0.50 是峰值，0.45 只低 2.4%）；该阈值来自 §0.8 样本内 5 点网格，属**二次选择**。**回撤优势是单调且稳健的**（-34.6%/-33.4%/-30.2%），这才是采用 H3 的主要理由。
  - **单资产依赖**：§00.9 的结论（12 个 sleeve 实际是 1–2 币组合）对两个 book 都成立；H3 没有降低对单一币的依赖，只是用宽度闸门把 book B 在风险期转现金。
- **样本外**：2026-09-22 → 2026-10-07 的 16 天窗口里，宽度共闸从未触发（breadth 始终 ≥ 0.50），因此 H3 与 B 的收益逐位相同（+3h 20bps **1.0883x**，MDD -10.57%）。这段窗口原本是 B 的冻结窗口，对 H3 也是切参前数据，但**不构成 H3 的独立证据**。`reports/phase_momentum_oos_2026/` 现已切换为跟踪 H3（manifest `trial_id=PR2026-10-H3`，report.md 首行标明 tracked specification）；B 的旧快照保留在 git 历史与本文件 §00.5。
- **实盘信号工具**：`scripts/run_phase_momentum_live_signal.py` 现在默认构造 H3（模块常量 `FROZEN_TRIAL_ID = "PR2026-10-H3"`），`--trial-id champion-defaults` 可回到 B。输出新增 `trial_id` 字段，sleeve 快照新增 `book` 列（0 = book A，1 = book B），多 book 的规则描述列出两个 book 的闸门。
- **复现**：
  ```bash
  .venv/bin/python scripts/run_phase_momentum_live_signal.py --output-dir reports/phase_momentum_live
  .venv/bin/python scripts/run_phase_momentum_oos.py --trial-id PR2026-10-H3 --end-date 2026-10-07
  # H3 的 PBO（把 H3 三档并入原候选族后重跑 CSCV）
  .venv/bin/python scripts/build_phase_momentum_h3_candidates.py
  .venv/bin/python scripts/run_phase_momentum_multiple_testing.py \
      --candidate-returns reports/phase_momentum_multiple_testing_h3/candidate_returns.csv \
      --primary h3_breadth_050 --output-dir reports/phase_momentum_multiple_testing_h3
  ```
  明细：`reports/phase_momentum_candidate_eval/`、`reports/phase_momentum_oos_2026/`、`reports/phase_momentum_live/`、`reports/phase_momentum_multiple_testing_h3/`。

### 00.12 2026-10-08 新方向：横截面离散度（dispersion）风险叠加（仅筛查，未预注册、未过生产引擎）

> **状态已被 §00.13 取代（2026-10-08）**：本节当时的「仅筛查、未预注册、未过生产引擎」已推进——离散度叠加已正式预注册为 **H5**、用生产引擎（按目标事件计费）重跑并通过自己的 kill criterion，且是本项目第一个通过 PBO 的规格。下方筛查数字保留为设计依据。

> 背景：§00.11 的结论是 H3 仍过不了 DSR/PBO，而唯一干净的修复（等样本外积累）太慢。本轮回到外部文献，找 **§5「已否决」清单之外**的新机制。**本节全部是筛查，不是候选，也没有改变冻结规格。**

- **新证据（2026 年，均不在原 §2 清单内）**：
  - Makgolo & Zhang (2026), *Cross-Sectional Dispersion and the State Dependence of Cryptocurrency Momentum*, SSRN 6648082（University of Chicago Booth / Bentley）。要点：**横截面离散度比 BTC 波动率更能预测加密动量的崩溃**；极端离散度状态下动量显著走弱；按离散度缩放的策略 Sharpe **0.63 → 0.80**，最大回撤 **-42.5% → -17.1%**。来源：SSRN 摘要页 + QuantSeeker 2026-04-28 综述（SSRN 正文被反爬，未能取到全文，缩放函数的确切形式未核实）。
  - Xu & Wu (2026), *Size-Momentum Puzzle in Cryptocurrencies*, SSRN 6628860：小币（最小五分位）周度反转 4.9%，大币动量 +1.0%——**支持 Top20-only 的设定**（本项目选的都是大币）。
  - Li et al. (2026), *Taming crypto anomalies: A Lasso-type factor model*, Finance Research Letters：加密三因子模型含 **residual momentum** 因子（列在此备查，本轮未测）。
- **本项目诊断**（`scripts/diagnose_cross_sectional_dispersion.py`；`reports/phase_momentum_dispersion_diagnostic/`）：在 2022-01-01..2026-09-21 上，把 H3 的前瞻收益按**当日 point-in-time Top20** 的横截面离散度分五档（无前视，离散度只用当日及之前的数据）：

| 离散度定义 | 前瞻窗口 | 最高档前瞻均值 | 其余四档均值 | 差 | Spearman |
|---|---|---:|---:|---:|---:|
| 近 21 日收益的横截面 std | 21 天 | **-0.17%** | +6.11% | **-6.28pp** | -0.196 |
| 近 7 日收益的横截面 std | 21 天 | +1.26% | +5.75% | -4.50pp | -0.161 |
| 当日收益的横截面 std | 21 天 | +1.90% | +5.59% | -3.70pp | -0.153 |

  外部机制在本策略上**成立**：离散度越高，未来 21 天越差。

- **可交易版本的筛查**（`scripts/backtest_dispersion_overlay.py`；`reports/phase_momentum_dispersion_overlay/`）：直接在 H3 的日收益上乘一个由**当日**离散度算出的敞口系数（**只用 t-1 的信息**）。**注意：这是筛查，按日缩放隐含每日调仓、且没有计入这部分额外换手**，所以收益被高估；真实实现只在目标事件上再平衡。

| 叠加规则 | 2bps 总收益 | 2bps Sharpe | 2bps MDD | 20bps 总收益 | 20bps Sharpe | 20bps MDD |
|---|---:|---:|---:|---:|---:|---:|
| 无（H3） | 27.77x | 1.609 | -35.6% | 22.53x | 1.524 | -37.9% |
| 二元闸：pct≥0.80 转现金 | 11.91x | 1.530 | -37.9% | — | — | — |
| 逆离散度缩放 `min(1, 252D median / disp)` | 15.69x | 1.701 | -33.8% | 13.16x | 1.605 | -36.1% |
| 逆离散度缩放 `min(1, 252D P75 / disp)` | **25.27x** | **1.755** | -35.5% | **20.82x** | **1.664** | -37.8% |

- **解读**：
  1. 二元"极端就转现金"的闸门**伤害收益**（高离散度常常伴随强趋势，砍掉的是好日子），**否决**。
  2. 连续的**逆离散度缩放**（dispersion targeting，和波动率目标同构）在 P75 目标下把 Sharpe 从 **1.52 提到 1.66（+9%）**，20bps 总收益从 22.53x 降到 20.82x（**仍 >20x**），回撤基本不变（-37.8% vs -37.9%）。
  3. 这是本轮到目前**唯一一个在 20bps 下同时保住 20x 并提高 Sharpe 的方向**；但它**没有降低回撤**（这是 H3 采用时的主要理由），也没有解决 DSR/PBO 的试验数问题。
- **状态**：**未预注册、未过生产引擎、未计入试验台账**。要成为候选必须：(1) 写进预注册台账；(2) 用生产引擎（按目标事件计费）重跑；(3) 过 H3 的 kill criterion，并补 DSR/PBO/邻域/成本压力。**尚未做任何一步**，因此**不能**据此改冻结规格。
- **复现**：
  ```bash
  .venv/bin/python scripts/diagnose_cross_sectional_dispersion.py
  .venv/bin/python scripts/backtest_dispersion_overlay.py
  ```
  明细：`reports/phase_momentum_dispersion_diagnostic/`、`reports/phase_momentum_dispersion_overlay/`。

### 00.13 2026-10-08 采用 H5 作为冻结规格（横截面离散度叠加；仍为 provisional；取代 §00.11 的规格指定与 §00.12 的「仅筛查」状态）

- **决定**：本轮把冻结规格从 **H3** 切换为 **H5**（注册号 `PR2026-10-H5`）。§00.12 的横截面离散度叠加已正式预注册、用生产引擎（按目标事件计费）重跑、并通过自己的 kill criterion；它同时是**本项目第一个通过 PBO 门槛的规格**。这是一次**规格指定**的切换：H5 在运行前登记（`scripts/run_phase_momentum_hypotheses.py` 的 `TRIALS`；台账 `reports/research_trial_inventory/preregistered_trials.csv`），切换没有使用 2026-09-22 之后的任何数据。
- **切换后的规格**：在 §00.11 的 H3 结构（2 个 book × 12 个 sleeve，目标层 50/50 混合）之上，给**两个 book 都**加同一个离散度缩放（`PhaseMomentumSpec.dispersion_target_percentile = 0.75`）：
  - `dispersion(D)` = 当日 point-in-time Top20 的**近 21 日收益横截面标准差（ddof=1）**；可用成员 < 5 → 无读数（`top20_dispersion`）。
  - `factor(D)` = `min(1, 过去 252 日离散度的 75 分位 / dispersion(D))`；无读数时 factor = 1（不做叠加，而不是强制转现金）（`dispersion_exposure`）。
  - 每个 sleeve 的（已波动率缩放、已宽度共闸的）目标权重乘以 `factor(D)`；gross ≤ 1.0 不变，因此叠加**只降风险、不抬杠杆**。其余规则（信号收盘生成、T+1、2bps 基准成本、长仓现货无杠杆）不变。
- **协议口径（20bps、+3h、较差缺 K 线）的头条结果**（`reports/phase_momentum_candidate_eval_h5/`）：

| 指标 | B（原始基线） | H3（被取代） | **H5（冻结）** |
| --- | ---: | ---: | ---: |
| 总收益 | 19.56x | 19.90x | 19.53x |
| Sharpe | 1.370 | 1.466 | **1.623** |
| 最大回撤 | -45.7% | -37.7% | **-37.0%** |
| 1 年滚动最差 | 0.711 | 0.733 | **0.806** |
| 去掉最好一年 | 4.34x | 5.90x | **6.51x** |
| 年化换手 | 26.09 | 24.65 | 24.84 |
| 平均 gross | 36.0% | 29.9% | **26.1%** |

- **+1h 实盘目标口径**：H5 **22.80x** / Sharpe 1.704 / MDD -33.3%（H3 23.44x / 1.534 / -33.4%；B 21.22x / 1.398 / -46.6%）。
- **kill criterion（预注册并已实装进评估器，20bps +3h 较差缺 K 线）**：`MDD improvement 8.71pp >= 5pp`（MDD -0.3697 vs B -0.4567）✔；`Sharpe 1.6231 > H3 1.4658` ✔；`1 年滚动最差 0.8063 > H3 0.7325` ✔。2bps（+9.02pp / 1.7223 > 1.5504 / 0.8130 > 0.7507）与 50bps（+8.21pp / 1.4570 > 1.3240 / 0.7517 > 0.6728）同判 → **通过**（`reports/phase_momentum_hypotheses_2026_10/kill.csv`）。H5 是本项目**第一个既通过 kill criterion、又通过 PBO 的规格**。
- **仍然失败 / 未证明的门槛**（任何一条都不因切换而解除；H5 仍为 **provisional**，tier 2「risk variant recorded」）：
  - **DSR**：协议口径 **0.860**（+1h 0.901，收盘 0.892）< 0.95 → **失败**（H3 0.755、B 0.675，同一口径）。DSR 用 `top20_2022_trials` 的 **N=6,135**（本轮把 3 个 H5 试验并入台账后重建的 `reports/research_trial_inventory/summary.json`，N 6,132→6,135）与家庭内 N=36 两个口径；家庭内 DSR 0.999 只是说明「在本家族里它是最强的」，不解除项目级门槛。
  - **DSR 差距有多远（新增，`scripts/analyze_dsr_gap.py`，`reports/phase_momentum_dsr_gap/`）**：保持 H5 协议日收益的分布形状（波动、偏度、峰度）不变、只把均值抬到刚好让 DSR = 0.95，需要的年化 Sharpe 是：

| DSR 口径 | N | E[max] 年化 | 现在 DSR | 现在的 Sharpe | 达到 0.95 所需 Sharpe | 差距 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| family（本族候选） | 36 | 0.398 | **0.999** ✅ | 1.623 | 1.623 | 已通过 |
| top20_2022_trials（项目口径） | 6,135 | 1.180 | 0.860 ❌ | 1.623 | **1.846** | **+13.7%** |
| all_trials | 14,129 | 1.244 | 0.822 ❌ | 1.623 | **1.908** | **+17.6%** |

    这是**反事实定价**，不是可达性声明：它说明项目级 DSR 门槛要求 Sharpe 再高约 14%，而不是「差一点」。同一份计算也说明为什么不能靠换口径过关——只有 family 口径会通过，而 family 口径不反映选择历史。
  - **PBO**：**通过**。把 H5 三档（0.60/0.75/0.90）与 H3 三档一起并入原 30 个单规格变体（去重后 **36 个候选**）重跑 CSCV（`scripts/build_phase_momentum_extended_candidates.py` + `scripts/run_phase_momentum_multiple_testing.py`；`reports/phase_momentum_multiple_testing_overlays/`）：**PBO = 0.192 < 0.5 → 通过**（H3 0.558、B 0.526，两者都是 fail）。H5(0.75) 是该族里被选中最多的候选（623/924），且全样本收盘 Sharpe 最高（1.6836）。White Reality Check：对零 p=0.019，对 BTC p=0.025。
  - **参数邻域**：**稳健**。预注册邻域 0.60/0.90 在 2/20/50bps 下都**保持** H5 的 kill criterion（H5-T60 协议口径 13.63x / Sharpe 1.540 / MDD -36.3%；H5-T90 21.68x / 1.555 / -37.0%）。收益对分位敏感（0.60 明显更低，18.16x@2bps vs 26.51x），但**风险指标（MDD、1 年滚动最差）对三档单调且稳健**——这正是采用 H5 的理由，不是收益。
  - **单资产依赖**：§00.9 的结论（12 个 sleeve 实际是 1–2 币组合）对 H5 同样成立；H5 没有降低对单一币的依赖。
  - **收益天花板**：叠加只做 de-risk（factor ≤ 1），**不抬收益上限**；协议口径下 H5 总收益（19.53x）略低于 H3（19.90x），属预注册里写明的「pass below 20x 记为 risk variant」情形。H5 在 2bps 与 +1h 口径下都 ≥ 20x，但头条（20bps +3h）低于 20x。
- **压力窗口 2020-10-03 .. 2021-12-31（20bps，收盘）**：H5 **5.177x** / Sharpe 2.553 / MDD -20.6%；H3 5.372x / 2.493 / -21.0%；B 5.129x / 2.456 / -18.9%；BTC 4.390x。
- **市场状态**（`reports/phase_momentum_regime_overlays/`，无前视标签）：H5 在 bull 20.05x / Sharpe 2.483 / MDD -37.7%，**非 bull 1.071x / Sharpe 0.255 / MDD -19.7%**，是三者里最好的非 bull（B 0.910x / -0.083 / -29.0%；H3 1.022x / 0.136 / -23.2%）。离散度叠加主要在风险期降暴露，与 §00.12 的机制一致。
- **样本外**：2026-09-22 → 2026-10-07 的 16 天里，离散度叠加**确实触发**（不像 H3 的宽度共闸从未触发）：20bps +3h 下 H5 **1.0576x** / MDD -6.39%，H3 1.0883x / -10.57%，BTC 0.9616x——H5 少赚约 2.9%，回撤小约 4.2pp。这段窗口对 H5 仍是切参前数据，**不构成独立证据**。`reports/phase_momentum_oos_2026/` 现已切换为跟踪 H5（manifest `trial_id=PR2026-10-H5`）。
- **实盘信号工具**：`scripts/run_phase_momentum_live_signal.py` 现在默认构造 H5（模块常量 `FROZEN_TRIAL_ID = "PR2026-10-H5"`），`--trial-id champion-defaults` 回到 B、`--trial-id PR2026-10-H3` 回到 H3。规则文本与 sleeve 快照现在也列出离散度叠加；`reports/phase_momentum_live/latest_signal.md` 的 Trial 字段为 `PR2026-10-H5`。
- **本轮同时修掉的两个评估器缺陷**（都会让 H5 的判定失真，记录在此以免误读）：
  1. `NEIGHBOURHOOD_IDS` 原来只有 H2/H3，H5 的 0.60/0.90 邻域虽在 `TRIALS` 里、却不在评估器的 trial 列表里，写台账时直接 `KeyError`；已补上。
  2. `_criteria` 原来只有 H2/H3/H4 三套判据，H5 会被**误用 H4 判据**评估；已实装 H5 判据（MDD 对 B、Sharpe 与 1 年滚动最差对 H3）。修正后 H5 与两个邻域都在 2/20/50bps 下通过。
- **复现**：
  ```bash
  # 1) 全量重跑预注册试验，重算判据 / DSR / Reality Check / 压力窗口
  .venv/bin/python scripts/run_phase_momentum_hypotheses.py
  # 2) 重建试验台账（把 3 个 H5 试验计入 DSR 分母 N=6,135）
  .venv/bin/python scripts/build_trial_inventory.py
  # 3) H5 与 B/H3 及各自邻域的同口径横评（含 DSR）
  .venv/bin/python scripts/evaluate_phase_momentum_candidates.py \
      --trial-ids PR2026-10-B,PR2026-10-H3,PR2026-10-H5,PR2026-10-H5-T60,PR2026-10-H5-T90 \
      --output-dir reports/phase_momentum_candidate_eval_h5
  # 4) 把 H3+H5 六档并入原候选族后重算 PBO / DSR / Reality Check
  .venv/bin/python scripts/build_phase_momentum_extended_candidates.py
  .venv/bin/python scripts/run_phase_momentum_multiple_testing.py \
      --candidate-returns reports/phase_momentum_multiple_testing_overlays/candidate_returns.csv \
      --primary h5_disp_p75 --output-dir reports/phase_momentum_multiple_testing_overlays
  # 5) 市场状态拆分
  .venv/bin/python scripts/run_phase_momentum_regime_breakdown.py \
      --returns-file reports/phase_momentum_multiple_testing_overlays/candidate_returns.csv \
      --candidates primary,h3_breadth_050,h5_disp_p75 \
      --output-dir reports/phase_momentum_regime_overlays
  # 6) DSR 差距定价（达到 0.95 所需的年化 Sharpe）
  .venv/bin/python scripts/analyze_dsr_gap.py --output-dir reports/phase_momentum_dsr_gap
  # 6f) 追高进场诊断（§00.18）
  .venv/bin/python scripts/analyze_momentum_chase_risk.py --output-dir reports/phase_momentum_chase_risk

  # 6e) 永续资金费率筛查（§00.17，全部被拒）
  .venv/bin/python scripts/download_funding_rates.py --start-month 2020-09 --end-month 2026-09
  .venv/bin/python scripts/analyze_momentum_funding_states.py --output-dir reports/phase_momentum_funding_states

  # 6d) 小时线日内状态筛查（§00.16，全部被拒）
  .venv/bin/python scripts/analyze_momentum_hourly_states.py --output-dir reports/phase_momentum_hourly_states

  # 6c) 量能/换手/集中度状态筛查（§00.15，全部被拒）
  .venv/bin/python scripts/analyze_momentum_flow_states.py --output-dir reports/phase_momentum_flow_states

  # 6b) 崩溃月归因：有没有状态变量能标记最差月份（§00.14，表格已被 §00.15 勘误）
  .venv/bin/python scripts/analyze_momentum_crash_states.py --output-dir reports/phase_momentum_crash_states
  # 7) 实盘信号与样本外跟踪
  .venv/bin/python scripts/run_phase_momentum_live_signal.py --output-dir reports/phase_momentum_live
  .venv/bin/python scripts/run_phase_momentum_oos.py --trial-id PR2026-10-H5 --end-date 2026-10-07
  ```
  明细：`reports/phase_momentum_candidate_eval_h5/`、`reports/phase_momentum_multiple_testing_overlays/`、`reports/phase_momentum_regime_overlays/`、`reports/phase_momentum_dsr_gap/`、`reports/phase_momentum_hypotheses_2026_10/`、`reports/phase_momentum_oos_2026/`、`reports/phase_momentum_live/`。

### 00.14 2026-10-08 诊断：DSR 差距不能靠「再加一层市场状态 overlay」补上（否定性结果）

> 背景：§00.13 把 H5 的 DSR 差距定价为「年化 Sharpe 还需再高 **13.7%**」。本节先做归因，回答「这 13.7% 到底亏在哪、能不能靠再叠一层状态变量补上」，再决定要不要开新试验。**本节只做诊断：不预注册、不新增试验、不改变冻结规格。**

- **亏损集中度**：H5 协议口径（20bps、+3h）57 个日历月里 17 个月为负（29.8%；同期 BTC 为 25/57）。回撤主要由**少数几个月**贡献。最扎眼的是「大盘上涨、策略却大跌」的月份：2023-04（H5 **-19.3%** vs BTC +2.8%）、2024-01（-10.6% vs +0.8%）、2023-07（-11.4% vs -4.1%），以及 2024-04（-19.0% vs -15.0%，这一类主要是市场型）。
- **这些月份叠加层在干什么**（`scripts/analyze_momentum_crash_states.py`；`reports/phase_momentum_crash_states/`）：

| 月份 | H5（净） | BTC | BTC 闸门开 | disp_ratio | gross |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2023-04 | **-19.3%** | +2.8% | 100% | **0.59** | **0.90** |
| 2024-04 | -19.0% | -15.0% | 100% | 0.69 | 0.34 |
| 2023-07 | -11.4% | -4.1% | 100% | 1.66 | 0.34 |
| 2024-01 | -10.6% | +0.8% | 100% | 0.70 | 0.41 |

  （`disp_ratio` = 当日离散度 / 其自身 252 日 75 分位；< 1 表示叠加层认为「离散度不高」，factor 保持 1。）

- **关键观察**：2023-04 的 disp_ratio 全月均值 **0.59** —— 离散度一直低于 75 分位，**factor 全程 = 1.000，叠加层根本没触发**，而 gross 高达 **90%**。也就是说，除了市场型下跌之外，最伤人的「大盘没事、动量自己反转」月份恰好落在叠加层的**盲区**里（低离散度，按 Makgolo–Zhang 的机制本该对动量*有利*）。当月亏损来自 OKB（-7.7pp）、cardano（-2.8pp）、ripple（-2.3pp）、dogecoin（-1.1pp）；2024-01 来自 internet-computer（-6.4pp）、ethereum-classic（-3.0pp）。
- **状态变量筛查（否定性结果）**：把 9 个崩溃月（≤ -8%）与其余 44 个月对比 6 个**当日可观测**的状态变量：

| 状态变量 | 崩溃月均值 | 其余月均值 | 差值 / 其余月标准差 |
| --- | ---: | ---: | ---: |
| BTC 闸门开 | 0.650 | 0.499 | +0.35 |
| breadth | 0.370 | 0.480 | -0.37 |
| disp_ratio | 0.751 | 0.943 | -0.38 |
| 市场 60D 已实现波动 | 0.718 | 0.705 | +0.06 |
| 策略自身过去 63 日收益 | 0.217 | 0.122 | +0.36 |
| gross | 0.310 | 0.266 | +0.18 |

  **没有一个变量的区分度超过 0.4σ。** 换句话：在这一族状态变量里找不到能标记崩溃月的变量，因此**再加一层同族 overlay 更可能只是增加试验数**（分母变大、所需 Sharpe 反而更高），而不是补上 13.7%。
- **结论（方向性）**：
  1. H5 的 Sharpe 增益（1.466 → 1.623）来自**整体降波动**，不是靠躲过崩溃月 —— 崩溃月不在它的状态空间里。
  2. 要补上 13.7% 的 Sharpe，需要**这一族（价格动量 / 波动 / 宽度 / 离散度）之外的新信息源**，而不是继续微调现有状态变量。
  3. 本节是**样本内假设生成**：即便将来某个变量能区分崩溃月，也必须在预注册后由样本外数据确认，才可能改规则。**当前冻结规格不变。**
- **复现**：
  ```bash
  .venv/bin/python scripts/analyze_momentum_crash_states.py
  ```
  明细：`reports/phase_momentum_crash_states/monthly_state.csv`、`state_separation.csv`、`report.md`。
- **勘误（2026-10-09，§00.15 给出）**：上表是在 **53/57** 个月上算的 —— 该脚本按行 dropna，而 `disp_ratio` 需要 126 个可用离散度读数、`own63` 需要 63 日收益序列预热，于是**整行丢掉了 2022-01..04**，其中 2022-04（-10.5%）正是一个崩溃月。按「逐状态丢缺失值 + 原口径」重算后结论不变（见 §00.15 表二），但样本应为 **57 个月、10 个崩溃月**。

---

### 00.15 2026-10-09 诊断：量能/换手状态变量筛查 —— 全部被拒（否定性结果，仍不开新试验）

> 背景：§00.14 的结论是「要补上 13.7% 的 Sharpe，需要价格动量 / 波动 / 宽度 / 离散度这一族之外的**新信息源**」。在不新增数据拉取的前提下，面板里唯一没被用过的信息就是**成交量与市值**。本节对该族做**只筛查、不预注册、不新增试验、不改规则**的诊断；筛选门槛在跑数之前写死在脚本 docstring 里。外部证据见 `docs/research/literature_review_2026-09.md` §7（S37–S43，逐条 fetch 验证）。

**外部机制（与筛查变量的对应）**

| 机制 | 来源 | 对应状态变量 |
| --- | --- | --- |
| 流动性/换手率作为情绪指标：换手率越高，随后收益越低（卖空约束下的过度反应） | Baker & Stein (2004), JFM, doi:10.1016/j.finmar.2003.11.005（NBER w8816 摘要已 fetch） | `turnover`、`turnover_ratio`、`volume_ratio` |
| 过去换手率同时预测动量的幅度与持续性；高换手赢家长期反转 | Lee & Swaminathan (2000), JF, doi:10.1111/0022-1082.00280 | `holdings_turnover_ratio` |
| 动量集中在**流动性最好**的币（羊群机制） | Begušić & Kostanjčar (2019), arXiv:1904.00890（arXiv API 摘要已 fetch） | `turnover_disp_ratio` |
| 日频数据可构造有效加密流动性指标；流动性波动被定价 | Brauneis et al. (2021), JBF, doi:10.1016/j.jbankfin.2020.106041；FRL 2021, doi:10.1016/j.frl.2021.102031 | `amihud_ratio` |
| 集中度/羊群：Top20 内部市值与成交量集中度 | 本项目内机制（`mcap_hhi`、`btc_share`、`volume_top3_share`）；外部证据仅部分支持 | 3 个集中度变量 |

**预设门槛（先写后跑）**：同时满足三条才允许升级为 H6 —— ① `|Spearman(状态, 次月 H5−BTC)| ≥ 0.25`；② `H5−BTC` 的三分位均值单调；③ `|崩溃月−其余月| / 其余月标准差 ≥ 0.50`。对照量取**超额收益**（H5 − BTC），因为 §00.14 的失败模式是「大盘涨、策略跌」。

**结果：9 个状态变量全部未通过**（`reports/phase_momentum_flow_states/`）

| 状态变量 | Spearman（对超额） | 崩溃−其余（σ） | 三分位单调 | 升级 H6 |
| --- | ---: | ---: | :--: | :--: |
| `turnover` | -0.069 | +0.04 | 否 | 否 |
| `turnover_ratio` | +0.083 | -0.22 | 是 | 否 |
| `volume_ratio` | +0.090 | +0.21 | 是 | 否 |
| `turnover_disp_ratio` | +0.126 | +0.68 | 否 | 否 |
| `amihud_ratio` | -0.109 | -0.15 | 否 | 否 |
| `mcap_hhi` | +0.166 | **-0.53**（t≈-2.1） | 否 | 否 |
| `btc_share` | +0.158 | **-0.52**（t≈-2.0） | 否 | 否 |
| `volume_top3_share` | -0.171 | -0.42 | 否 | 否 |
| `holdings_turnover_ratio` | -0.175 | **+2.09**（仅 28/57 个月可用） | 否 | 否 |

- **唯一接近的方向**是市值集中度：崩溃月之前的 Top20 **更分散**（HHI 0.412 vs 0.448、BTC 占比 0.599 vs 0.635），但它的秩相关只有 0.166（p≈0.21），且三分位不单调 —— **未达预设门槛，不升级**。`holdings_turnover_ratio` 的 2.09σ 不可用：它只在持仓月有定义（28/57，崩溃月只剩 7 个），是典型的选择性样本，且极端值（2023-07 达 11.9）主导。
- **§00.14 勘误与「可执行口径」重算**：按同样的**月内均值**口径、逐状态丢缺失值、全 57 个月重算，结论不变（σ：`gate_open` +0.36、`breadth` -0.31、`disp_ratio` -0.38、`mkt_vol` +0.05、`gross` +0.22）。但换成**月初读数**（overlay 真正能用的口径）后，同一个变量族其实**是能区分**的：

| 月初可执行状态 | 崩溃月均值 | 其余月均值 | 差值/σ | Welch t |
| --- | ---: | ---: | ---: | ---: |
| BTC 闸门开 | **0.900** | 0.447 | +0.90 | 3.66 |
| breadth | **0.690** | 0.372 | +0.95 | 3.94 |
| 月初 gross | **0.455** | 0.226 | +0.72 | 2.27 |

  即：**H5 进入最差月份时并不是防守状态，而是「闸门开、宽度高、仓位接近半仓」的满风险状态**，而这些状态在牛市中同样长期为真 —— 用它们做减仓过滤器，等于砍掉大部分收益。这正是 §00.14 否定性结论的可执行表述，也是为什么这条线**不值得再开 H6**。
- **结论**：
  1. 量能/换手/集中度这一族**不能**补 DSR 缺口：最强的候选也达不到预设的样本内门槛。
  2. 已记录的**被拒假设**：Top20 换手率择时（Baker–Stein 方向）、持仓拥挤度、Amihud 非流动性、集中度择时。除非有**新的样本外数据**，不再从这一族派生新试验。
  3. 若要继续追 DSR，剩下三条诚实路径：(a) 接受 H5 为「冻结但未通过 DSR」的当前最优；(b) 用 2026-09-22 起的**真实样本外**累积来正当地降低试验数权重（慢，且不能调参）；(c) 引入**面板之外**的新数据源（链上/资金费率等），需要先解决数据获取。
  4. **冻结规格不变**；本节不新增试验，台账计数不变。
- **复现**：
  ```bash
  .venv/bin/python scripts/analyze_momentum_flow_states.py --output-dir reports/phase_momentum_flow_states
  ```
  明细：`reports/phase_momentum_flow_states/{monthly_state.csv,daily_flow_state.csv,state_separation.csv,state_separation_legacy_corrected.csv,state_separation_legacy_actionable.csv,state_information.csv,state_terciles.csv,state_redundancy.csv,state_verdicts.csv,report.md,manifest.json}`。

---

### 00.16 2026-10-09 诊断：小时线（日内）状态变量筛查 —— 同样全部被拒（否定性结果）

> 背景：§00.15 关闭了面板里的**日频**量能/换手/集中度信息。仓库里还剩最后一块策略看不到的信息：**Binance 小时线**（`data/raw/binance_1h`，56 个交易对，2021-12-25 起；它本来只被用于 +1h/+3h 成交协议）。本节对它做同样的「只筛查、不预注册、不新增试验」诊断；门槛在跑之前写死。外部证据见 `docs/research/literature_review_2026-09.md` §8（S44–S48）。

**覆盖度**：评价窗口内出现过的 **53 个 PIT Top20 成员**中，只有 `bitget-token` 没有小时线；成员-日覆盖 **34,381 / 34,500 = 99.66%**（最低单日 95%）。

**7 个候选状态**（全部按「月初前一收盘」读数，截面只取 PIT Top20 成员，单日不足 5 个成员记缺失，小时数不足 20 的残日整日丢弃）：

| 状态变量 | 机制与来源 |
| --- | --- |
| `rv_ratio` | 24 小时已实现方差（小时对数收益平方和）7 日均值 ÷ 自身 252 日中位数；Andersen–Bollerslev–Diebold–Labys (2003) 证明已实现方差比日频平方收益噪声小得多 |
| `range_ratio` | 日均 (high−low)/close 的 7 日均值 ÷ 自身中位数；Parkinson (1980) 极值波动率估计 |
| `rvs_down_share` | 下行半方差占已实现方差的比例（「坏波动」）；Barndorff-Nielsen–Kinnebrock–Shephard（已实现半方差） |
| `hour_share_ratio` | 单小时最大成交额占当日比重 ÷ 自身中位数；Cong–Li–Tang–Yang「Crypto Wash Trading」：不受监管交易所的刷量平均占报告量 **70%+** |
| `venue_share_ratio` | Binance 成交额 ÷ 成员 CMC 报告成交额（7 日均值）÷ 自身中位数：报告量中可被单一场所验证的比例 |
| `hourly_autocorr` | 各成员小时收益 30 日一阶自相关的截面中位数：日内趋势 vs 日内反转 |
| `night_minus_day` | 等权 Top20 组合 00:00–08:00 UTC 收益减 08:00–24:00 UTC 收益的 7 日和；Hansen–Kim–Kimbrough 记录加密波动与成交量的**小时效应** |

**预设门槛（比 §00.15 更严）**：这是同一样本上的**第二个**筛查，因此信息门槛按 18 个候选做族错误率校正：`|Spearman(状态, 次月 H5−BTC)| ≥ 0.38`（n≈57 时双侧 5% 除以 18），加三分位单调，加 `|崩溃−其余| / 其余σ ≥ 0.50`。

**结果：7 个状态全部未通过**

| 状态变量 | Spearman（对超额） | 崩溃−其余（σ） | 三分位单调 | 升级 H6 |
| --- | ---: | ---: | :--: | :--: |
| `rv_ratio` | +0.036 | +0.25 | 否 | 否 |
| `range_ratio` | +0.081 | +0.23 | 是 | 否 |
| `rvs_down_share` | -0.183 | -0.35 | 否 | 否 |
| `hour_share_ratio` | **+0.262** | -0.33 | 是 | 否 |
| `venue_share_ratio` | -0.177 | -0.04 | 是 | 否 |
| `hourly_autocorr` | -0.043 | -0.03 | 是 | 否 |
| `night_minus_day` | +0.123 | +0.23 | 是 | 否 |

- `hour_share_ratio` 是**日频+小时线共 16 个候选里最强的**：三分位单调，秩相关 +0.262 甚至能过 §00.15 的未校正门槛 0.25 —— 但它连 0.50σ 的区分度门槛都没到（-0.33），因此**不升级**，只登记为被拒假设。
- **已实现波动率（教科书式的崩溃条件变量）对次月超额收益的秩相关只有 +0.036**。这与 §00.14 的结论一致：H5 的问题不在「波动率状态」里。
- **结论**：项目现有的**全部信息源**（日频价格/成交量/市值 + 小时线）都已被筛过；在三类面板内派生状态里都找不到能补 DSR 缺口的新信息。要么接受 H5 为「冻结但未过 DSR」的当前最优，要么等 **2026-09-22 起的真实样本外** 累积，要么引入**面板之外**的数据（需要先解决获取，且必须重新走预注册流程）。**冻结规格与试验计数不变。**
- **复现**：
  ```bash
  .venv/bin/python scripts/analyze_momentum_hourly_states.py --output-dir reports/phase_momentum_hourly_states
  ```
  明细：`reports/phase_momentum_hourly_states/{monthly_state.csv,daily_hourly_state.csv,hourly_coverage.csv,state_separation.csv,state_information.csv,state_terciles.csv,state_redundancy.csv,state_verdicts.csv,report.md,manifest.json}`。

---

### 00.17 2026-10-09 诊断：永续合约资金费率筛查 —— 被拒，但它是目前最强的崩溃月区分变量（否定性结果）

> 背景：§00.15（日频现货量能）与 §00.16（小时线）都在**现货**信息里，且都被拒。项目从未用过的最后一块信息是**衍生品持仓**：多头为持有仓位支付的资金费率。`data.binance.vision` 按月归档每个 Binance USDT 永续的完整资金费率历史，`scripts/download_funding_rates.py` 已把 57 个币中的 **52 个**落到 `data/raw/binance_funding/`（`fapi.binance.com` 在本网络不可达，故走公开归档）。本节同样是**只筛查、不预注册、不新增试验**。外部证据见 `docs/research/literature_review_2026-09.md` §9（S49–S51）。

**外部机制**：*Management Science* (2026) 的 "Crypto Carry" 证明期货-现货 carry 可达年化 40%+，来源是「**追趋势的小投资者加杠杆的需求** + 套利资本受限」——资金费率因此是"杠杆拥挤度"的直接读数；另一篇 2026 年 Binance 永续面板研究显示「累计资金费率」显著预测 8 小时内 ≥5% 的暴跌（样本外 AUROC 0.76）。

**4 个候选状态**（月初前一收盘读数，截面只取有资金费率的 PIT Top20 成员，单日不足 5 个记缺失）：`funding_level`（成员日均资金费率的 7 日均值，单位 bps/日）、`funding_pct`（该序列在自身 252 日窗口内的分位）、`funding_positive_share`（正费率成员占比的 7 日均值）、`funding_disp_ratio`（截面离散度 ÷ 自身 252 日中位数）。

**覆盖度**：53 个 PIT 成员中 5 个没有资金费率历史（4 个 Gate 专属 + bitget-token），成员-日覆盖 **33,043 / 34,500 = 95.78%**，**没有任何一天低于 5 成员下限**。

**预设门槛**（同一样本上的第三个筛查，20 个候选族错误率校正）：`|Spearman(状态, 次月 H5−BTC)| ≥ 0.38` + 三分位单调 + `|崩溃−其余| ≥ 0.50σ`。

**结果：4 个状态全部未通过 —— 但 `funding_level` 是目前全部 20 个候选里崩溃月区分度最强的**

| 状态变量 | Spearman（对超额） | 崩溃−其余（σ） | Welch t | 三分位单调 | 升级 H6 |
| --- | ---: | ---: | ---: | :--: | :--: |
| `funding_level` | +0.162 | **+1.12** | 1.99 | 是 | 否 |
| `funding_positive_share` | +0.168 | **+0.76** | **3.57** | 否 | 否 |
| `funding_pct` | +0.088 | +0.51 | 1.52 | 否 | 否 |
| `funding_disp_ratio` | +0.067 | -0.12 | -0.27 | 否 | 否 |

- **崩溃月之前的多头杠杆明显更贵**：崩溃月月初的日均资金费率 **3.19 bps**，其余月份只有 **0.70 bps**（差 1.12σ，t≈2.0），方向与「杠杆拥挤 → 崩塌」机制一致。这是三次筛查里唯一超过 1σ 的区分度。
- **但它不是方向性过滤器**：同样是这个高费率三分位，也是**平均最好的月份**（H5 均值 **+12.7%** vs 低三分位 +3.1%；超额 +6.3% vs +1.6%）。按崩溃月区分度去「高费率就减仓」，会砍掉最好的月份 —— 这正是它的超额秩相关只有 +0.162（远低于 0.38 门槛）的原因。
- **而且它并不新**：`funding_level` 与规格已看到的状态高度重合 —— 与 breadth 相关 0.66、与 BTC 闸门 0.65、与 gross 0.61、与 mkt_vol −0.40。也就是说，拥挤杠杆主要是**波动率/风险偏好放大器**，而 H5 已经通过 gross 和 breadth 看到其中大部分。
- **结论**：资金费率族**不升级为 H6**，登记为被拒假设。三次筛查（日频量能、小时线、资金费率，共 20 个候选）合起来说明：**在项目可低成本获得的信息里，找不到能补 DSR 缺口的定向信号**。
- **落地限制（必须记录）**：Binance 只按月归档资金费率（没有日档），且 `fapi.binance.com` 在本网络不可达 —— 因此即便将来某个资金费率状态被预注册并验证，也**无法直接驱动实盘**，需要另找数据通道。
- **复现**：
  ```bash
  .venv/bin/python scripts/download_funding_rates.py --start-month 2020-09 --end-month 2026-09
  .venv/bin/python scripts/analyze_momentum_funding_states.py --output-dir reports/phase_momentum_funding_states
  ```
  明细：`reports/phase_momentum_funding_states/{monthly_state.csv,daily_funding_state.csv,funding_coverage.csv,state_separation.csv,state_information.csv,state_terciles.csv,state_redundancy.csv,state_verdicts.csv,report.md,manifest.json}`。

---

### 00.18 2026-10-09 现状与诊断：当前信号、样本外进度，以及「追高进场」的历史表现

**一、当前信号（数据截至 2026-10-07，UTC 日已收完）**

| 项目 | 值 |
| --- | --- |
| 目标 | **100% `near`**，gross **0.505**（其余为现金） |
| 当前持仓 | `near` 0.5048 |
| BTC 闸门 | 开 |
| 需要交易 | 是（目标 0.5057 vs 当前 0.5048，仅漂移补仓） |
| 建仓过程 | 2026-09-18 之前是 100% `zcash`；09-19 起 `near`+`zcash`；**10-04 起 100% `near`** |

单币集中不是异常：本规格由 **24 个单币 sleeve**（2 本账 × 4 信号 × 3 相位）叠加而成，历史上有 26.9% 的持仓日为单一币种、最大持仓占比中位数 75.3%（`reports/phase_momentum_book_concentration/`）。真正约束风险的是**波动率目标**：`near` 60 日已实现波动 **120% 年化**，因此目标仓位只给到 50.5%，其余留现金。

**二、业绩（20bps、引擎收盘成交口径）**

| 区间 | 策略 | BTC |
| --- | ---: | ---: |
| 全样本 2022-01-01 .. 2026-10-07 | **22.68x** | 2026 YTD -6% |
| 2022 | -16.34% | — |
| 2023 | +215.81% | — |
| 2024 | +90.17% | — |
| 2025 | +102.13% | — |
| 2026 YTD（至 10-07） | **+123.26%** | **-6%** |
| 样本外 2026-09-22 .. 2026-10-07（16 天） | **+5.61%**（+3h 口径 +5.76%） | **-3.84%** |
| 样本外回撤 | -6.5% | -3.8% |

- 研究截止（2026-09-21）时的注册结论是 **19.53x**；样本外这两周把它推到 **22.68x**（至 10-07），同期 BTC 下跌。样本外窗口太短，**不构成验证**，只记录。
- **2026-10-08 数据推进一天后的更新**：样本外窗口延长到 **17 天**，H5 在 10-08 单日回吐，20bps +3h 较差口径从 1.0576x 降到 **0.9689x（−3.11%）**，同期 BTC **0.9431x（−5.69%）**；最大回撤 H5 -8.6% vs BTC -5.7%。也就是说，**样本外绝对收益转为小幅为负，但相对 BTC 仍然领先**。当前信号（10-08 收盘）仍是 100% `near`，目标 gross 从 0.505 升到 **0.621**（`near` 波动率回落，波动率目标允许更大仓位），需要加仓。`reports/phase_momentum_oos_2026/` 与 `reports/phase_momentum_live/` 已同步刷新到 10-08。
- 2026 年的收益高度依赖 `zcash`（YTD +153%）与 `near`（9 月以来 +183%）两段行情 —— 这正是动量设计要抓的东西，但也意味着**当前这仓是本轮行情后段进场**。
- 换手随行情下降：2023 年累计成交 42.5x gross，2026 年至今只有 9.6x（长期持有领涨币）。

**三、新诊断：追高进场之后会怎样（`scripts/analyze_momentum_chase_risk.py`）**

对每个持仓日，取**最大持仓币的过去 21 日涨幅**（动量 sleeve 正在追的东西），再看策略自己随后的 5/10/21 日收益：

| 分位（按追涨幅度） | 天数 | 中位涨幅 | 21 日前瞻均值 | 21 日胜率 | 21 日最差回撤 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1（最低） | 175 | +4.9% | +5.33% | 56.0% | -21.8% |
| 2 | 175 | +22.3% | +6.70% | 46.9% | -21.0% |
| 3 | 174 | +40.8% | +8.33% | 51.7% | -20.1% |
| 4 | 175 | +67.9% | **+10.71%** | **61.7%** | -19.3% |
| 5（最极端） | 175 | **+113.7%** | **+1.78%** | **42.9%** | -19.4% |

- **最强的一档（前 20%，门槛 21 日 +87%）之后，21 日前瞻收益只有 +1.78%，约为第 4 档（+10.71%）的 1/6**；5 日/10 日差异较小，说明是**约三周尺度**的边际衰减，不是立刻崩。
- **不是波动率目标造成的假象**：按前瞻期平均 gross 归一后，极端档 **+6.55%** vs 其余 **+14.86%**（Welch t **-2.83**）；原始口径差 -5.97pp（t **-4.99**）。极端档 gross 确实更低（0.36 vs 0.49），但归一后差距仍在。
- **当前这仓正好落在这一档**：`near` 过去 21 日 **+104.3%**（第 **87** 分位）。
- **外部证据存在冲突，已如实记录**：股票 MAX 效应（Bali–Cakici–Whitelaw 2011）说极端涨幅后收益更低；加密 MAX 动量研究（Li–Urquhart 等 2021，本综述 S6）结论相反。本项目用**最大单日涨幅**复现该构造时，对策略前瞻收益**没有显著影响**（21 日 t=-1.17，按 gross 归一 t=+0.37），因此两者都不能直接支持或否定本节的「21 日累计涨幅」结果。
- **结论与边界**：极端追涨档**仍然是正收益**（+1.78% / 21 日），所以这不是「不能买」的信号，而是「边际更薄、胜率更低」的状态；且本结果是**样本内、且以策略自己选择持有为条件**。**不改规则**：任何「追涨就减仓/不买」的改动都属于新的预注册试验，在当前 DSR 已因试验数过多而失败的前提下，加试验只会让门槛更高。本节只做记录与风险披露。
- **复现**：
  ```bash
  .venv/bin/python scripts/analyze_momentum_chase_risk.py --output-dir reports/phase_momentum_chase_risk
  ```
  明细：`reports/phase_momentum_chase_risk/{daily_chase.csv,chase_buckets.csv,chase_extreme_vs_rest.csv,max_daily_buckets.csv,max_daily_extreme_vs_rest.csv,report.md,manifest.json}`。

---

### 00.19 2026-10-09 预注册试验 H6：永续资金费率 overlay —— **被拒**（负结果）

**一、为什么做 H6**

`§00.17` 的资金费率筛查发现：point-in-time Top20 成员日均永续资金费率的 7 日均值（`funding_level`）是全部 20 个候选状态里**最强的崩溃月区分变量**（崩溃月 3.19 bps/日 vs 其余 0.70，差 +1.12 个 rest-std），只是**月频 Spearman 不达标**（+0.162 < 0.38 门槛）。筛查本身不构成规则，因此把它升级为一个**预注册**（`PR2026-10-H6`，登记在 `reports/research_trial_inventory/preregistered_trials.csv` 后才运行）的生产引擎试验：机制沿用 H5 的「反向分位缩放」形式，把分散度换成资金费率水平。

**二、规则（登记原文）**

在冻结的 **H5** 账本（champion + H3 breadth 共闸，50/50 目标层混合，已含 dispersion overlay）之上，再乘一个 point-in-time 拥挤因子：

- `state(D)` = point-in-time Top20 中有 Binance USDT 永续的成员，其**当日资金费率截面均值**的 **7 日均值**（bps/日；可用成员 < 5 → 无读数）。
- `f(D) = min(1, 过去 252 日的 P80(state) / state)`，**下限 0.25**，取**信号收盘前一日**的值；缺失/非正读数 → `f(D)=1`。
- 两个账本统一乘 `f(D)`（拥挤是市场级状态）；gross 仍 ≤ 1，overlay 只能减仓。

预注册的 kill criterion（20bps、+3h、更差缺失K线策略，且 2/50bps 同向）：`MDD(H6) >= MDD(H5)-0.05`、`Sharpe(H6) > Sharpe(H5)`、`rolling 1y worst(H6) > H5`、且 `M(H6) >= 0.85 x M(H5)`；否则拒绝。

**三、结果：被拒（2022-01-01 .. 2026-09-21，20bps，+3h 更差策略）**

| 指标 | H5（冻结） | **H6** | 判定 |
| --- | ---: | ---: | --- |
| 总收益 | **19.53x** | **12.02x** | `12.02 < 0.85×19.53=16.60` → **FAIL** |
| Sharpe | **1.623** | **1.537** | 未提升 → **FAIL** |
| 最大回撤 | -36.97% | **-27.58%** | 改善 9.4pp（达标） |
| rolling 1y worst | 0.806 | 0.806 | 未提升 → **FAIL** |
| 年均 gross | 0.261 | 0.226 | 减仓确实发生 |
| 年换手 | 24.84 | 22.47 | — |

- 三个成本档方向一致：2bps 24.12x→14.55x、20bps 19.53x→12.02x、50bps 13.72x→8.74x、100bps 7.61x→5.13x；Sharpe 全部下降（1.72→1.64 / 1.62→1.54 / 1.46→1.36 / 1.18→1.08）。
- 预注册邻域同样不达标：P70 → 10.09x / Sharpe 1.518 / MDD -27.1%；P90 → 14.18x / Sharpe 1.556 / MDD -35.3%。三档 P80/P70/P90 都是「降回撤、更降收益」。
- 分年看，损失集中在趋势最强的年份：2023 1.998→1.307、2024 0.949→0.678、2026 1.064→0.949；2022 熊市两者完全相同（2022-01 起才有资金费率覆盖，且当时组合基本空仓）。也就是说，**高资金费率状态同时包含「崩溃前」和「动量最强」两类时段**，减仓把两者一起削掉。

**四、结论与不变量**

- **H6 被拒，冻结规格仍为 H5。** 资金费率的崩溃区分度真实存在，但作为**减仓规则**它净损失收益与 Sharpe，达不到任何一条提升要求；这解释了为什么 `§00.17` 的筛查结论不能直接变成规则。
- **H5 的 DSR 因新试验数上升而进一步变差**：把 H6 与其预注册邻域（P70/P90）计入后，Top20/2022 试验数由 6,135 升至 **6,138**，H5 的 Deflated Sharpe 由 0.860 微降到 **0.858**（`reports/phase_momentum_hypotheses_2026_10/dsr.csv`，`top20_2022_trials` scope）。这是选择偏差的诚实记账，**不通过放宽门槛来掩盖**。
- **部署约束（登记时已声明）**：项目目前没有日频资金费率实时源（`data/raw/binance_funding` 来自 Binance 月度归档），即使 H6 通过也只能回测、不能上实盘；这一点写进了 `docs/research/literature_review_2026-09.md` §H6 的 deviation。
- **复现**：
  ```bash
  .venv/bin/python scripts/run_phase_momentum_hypotheses.py --register
  .venv/bin/python scripts/run_phase_momentum_hypotheses.py
  ```
  明细：`reports/phase_momentum_hypotheses_2026_10/{runs.csv,decision.csv,kill.csv,neighbourhood.csv,dsr.csv,yearly.csv,returns_20bps.csv,report.md}`。

---

### 00.20 2026-10-09 上线路线：DSR 在当前试验数下结构性不可达，必须先做规则决策

**一、问题被量化了**

`AGENTS.md` 要求多重检验/选择偏差门槛。H5 唯一没过的就是它（DSR 0.858 < 0.95）。
新增工具 `scripts/analyze_dsr_horizon.py`（`reports/phase_momentum_dsr_horizon/`）回答
「还需要多少新数据」：保持 H5 日收益的波动/偏度/峰度不变、只改新数据均值，
以项目真实试验数 N=6,138（期望最大年化 Sharpe 1.184）重算合并样本 DSR。

| 假设的新样本外年化 Sharpe | 达到 DSR 0.95 所需新数据 |
| ---: | ---: |
| 1.40 | > 10,000 天（≈27 年，实质不可达） |
| **1.623（＝样本内水平）** | **2,340 天（6.4 年）** |
| 1.80 | 1,232 天（3.4 年） |
| 2.00 | 776 天（2.1 年） |

**结论：DSR 把「从 6,138 个候选里挑出最好的」这个选择惩罚再收一次费，且收在整个样本上。
只要新数据 Sharpe 不超过样本内水平，合并 Sharpe 会被拉低，DSR 上升极慢。**
这不是「差一点」，是**在当前 N 下的结构性不可达**。

**二、对比：只用样本外的检验便宜约 6 倍**

样本外窗口没有参与选规格，其 Sharpe 是无偏估计，不需要再付选择惩罚。假设 Sharpe≈1.6：
单侧 t 检验 95% 需要 **386 天（1.06 年）**，99% 需要 **772 天（2.11 年）**。

**三、这必须先由项目负责人决策，不能自行改规则**

`AGENTS.md` 原文允许「an equivalent documented method」和「genuinely out-of-sample splits」，
但也明确「Never weaken, reinterpret, or remove a constraint after seeing a backtest result」。
因此这里**不能由我自行把 DSR 换成 t 检验**。两条路：

- **A. 维持 DSR ≥ 0.95 为硬门槛** → H5 在本项目试验数下实际上**永远无法上线**，
  只能长期保持 provisional 的样本外记录。
- **B. 负责人现在（在样本外仍无信息量时）批准一套预声明的样本外验收协议** →
  DSR 继续报告但不再作为唯一门槛，用 12–18 个月的真实样本外按事先写死的判据决定。

**我的建议是 B**，但**必须由负责人批准，且必须现在批准**；等样本外攒到能看出结论再定规则
就是事后挑口径，规则本身不允许。

**三之二、推论：继续「优化策略规则」现在是负收益动作**

DSR 的分母 N 统计所有在 Top20/2022 上回测过的配置。**每加一条规则、每扫一个参数，
N 就变大、期望最大 Sharpe 就变高、DSR 就更远。** 在规则决策（§三）解决之前，
任何新的策略试验都在把上线推远；而 §00.14–00.19 已连续证明没有免费杠杆
（再加 overlay 无效、H4/H6 被拒、三族状态筛查全被拒）。
**策略层面已经到顶**——不是「暂时没找到更好的」，而是「再找会变差」。
剩余可做且有效的只有：执行（+1h）、数据链路与告警、预声明验收协议 + 攒样本外、资金分层与熔断。

**四、上线路线图**

完整方案写入 `docs/operations/go_live_plan.md`：预声明样本外验收协议（§3）、
+1h 执行杠杆（§4，20bps 下 19.53x → **22.80x**、Sharpe 1.623 → 1.704、MDD -37.0% → -33.3%，
纯运营、不改规则、不抬高 N）、运营就绪清单（§5）、资金分层（§6）、gate 表（§7）、
时间线（§8）。**最早可上线 ≈ 2027 年 9 月之后**（样本外满 365 天 + 影子/小额期）。

**五、复现**

```bash
.venv/bin/python scripts/analyze_dsr_horizon.py --output-dir reports/phase_momentum_dsr_horizon
```

明细：`reports/phase_momentum_dsr_horizon/{dsr_by_horizon.csv,required_oos_sharpe.csv,required_oos_days.csv,oos_only_significance.csv,report.md,manifest.json}`。

---

## 0. 2026-09-23 新主候选：相位错开多周期动量（生产引擎已验收）

> 本节是新主候选的权威结论，取代旧 21D、11D/2 BTC 闸门和此前“无稳定 20x 策略”的叙述。旧章节仅保留为历史审计记录。

### 0.0 策略规则

- 股票池：严格 point-in-time **Top 20**，包含 BTC；CMC 决定成员，缺失 CMC 的币不参与排名。
- 信号：四条透明 trailing-return 动量，等权：
  1. `weighted_multi_horizon`：7/14/21/28/42/60D = 10/15/20/25/15/15%；
  2. `ret21`；
  3. `equal_7_14_28_60`；
  4. `equal_14_21_28`。
- 每条信号做 3 个相位错开，共 12 个 sleeve；每 sleeve 每 3 天检查一次，合起来每天都有 sleeve 在检查。
- 持仓只要仍在当前 sleeve 的 Top2 就继续持有；跌出 Top2 才换到当前第 1 名；跌出当天 Top20 立即退出。
- 风控：BTC 100D MA + confirm2；单 sleeve 按 60D 已实现波动率缩放到 80% 目标波动；gross exposure 硬上限 1.0，无杠杆、无做空。
- 执行：收盘信号，T+1；所有成本按 2/20/50/100bps 分别重跑生产引擎 `run_backtest`。

### 0.1 主结果

2022-01-01 → 2026-09-21，严格 Top20、无杠杆：

| 往返总成本 | 总收益 | CAGR | Sharpe | 最大回撤 |
|---|---:|---:|---:|---:|
| **2bps** | **28.80x** | 103.69% | 1.514 | -42.61% |
| **20bps** | **23.09x** | 94.38% | 1.433 | -44.92% |
| 50bps | 15.97x | 79.78% | 1.297 | -48.72% |
| 100bps | 8.62x | 57.79% | 1.069 | -54.49% |
| BTC 买入持有 | 1.87x | 14.17% | 0.515 | -66.89% |

逐年收益（20bps 主策略 vs BTC）：

| 年份 | 主策略 | BTC |
|---|---:|---:|
| 2022 | -22.8% | -64.3% |
| 2023 | +378.4% | +155.4% |
| 2024 | +78.5% | +121.1% |
| 2025 | +65.5% | -6.3% |
| 2026 YTD | +111.7% | -1.0% |

### 0.2 过拟合与稳健性门槛

| 检验 | 结果 | 判定 |
|---|---:|---|
| 参数邻域（25 个固定变体 @20bps） | 除“去掉 BTC 闸门”为 2.88x 外，其余约 9.5x–30.0x；主策略 23.09x | 通过；BTC 闸门是必要风险开关 |
| ~~固定主策略 Deflated Sharpe~~ | ~~0.9945~~ | **作废**：只按 32 个候选计算；按真实试验数为 0.731（2026-10-08，N=6,132），失败（见 §00） |
| ~~固定主策略 White Reality Check~~ | ~~p=0.0150~~ | **作废**：只对主策略单独做；家族内对零 p=0.019、对 BTC p=0.025（见 §00） |
| 动态 walk-forward（365D 训练/90D 测试，2023 起，含 40bps 切换成本） | 20.78x，Sharpe 1.621 | 通过（>20x） |
| 固定主策略 2023 起（~~OOS~~ 样本内） | 29.91x，Sharpe 1.734 | **重标**：参数用全样本挑选，不是样本外（见 §00） |
| ~~固定主策略 CSCV（12 块、924 折）~~ | ~~低于中位数比例 7.47%~~ | **不计为证据**：训练/测试分布构造上相同，只是样本内诊断（见 §00） |
| 参数等权集成 CSCV | OOS 排名中位数 0.438；低于中位数比例 85.71% | 拒绝作为冠军 |
| 去掉最佳年份 2023 | 主策略 4.83x、Sharpe 1.112；BTC 同期 0.71x | 通过；收益不依赖单一年份 |
| 去掉任意一条信号 @20bps | 20.58x–27.58x | 通过；不依赖单一信号 |
| 去掉任意一个相位 @20bps | 21.26x–23.91x | 通过；不依赖单一相位 |
| 市场状态拆分（bull / non-bull）@20bps | ~~bull 51.83x vs BTC 13.65x；non-bull 0.445x vs BTC 0.137x~~ | **作废**（同日标签前视）；前一日标签：bull 25.37x vs BTC 3.27x，non-bull 0.91x vs BTC 0.57x（见 §00） |
| 参数等权集成 leave-one-parameter-out @20bps | 15.11x–16.93x | 集成低于 20x，仅保留为风险分散参考，不替代固定主策略 |
| 2020-10-03 → 2021-12-31 压力 | 20bps 4.55x，Sharpe 2.394，最大回撤 -18.9% | 通过 |
| 逐条选币审计 | 10,308 条选币记录，0 条不在当天 Top20、0 条无价格、0 条 Rain/稳定币；所有快照恰好 20 个币 | 通过 |
| 事后挑最佳参数 PBO | ~~0.6288~~ 0.526（修正后） | 失败；因此禁止动态挑选全样本最佳参数，使用固定主策略 |

解释：

- ~~PBO 0.63 否定的不是固定主策略……固定主策略的 CSCV OOS 排名稳定性为 7.47% 低于中位数，反而是通过的。~~ **作废（2026-09-25）**：固定主策略 CSCV 在构造上无法提供样本外证据；PBO 修正后为 0.526，仍失败（见 §00）。
- 参数等权集成 2bps 为 20.06x，但 20bps 只有 15.97x，且 CSCV 不稳定，因此只保留为风险分散参考，不替代主策略。
- 止损、移动止损和币自身均线过滤都跑过：固定 20% 止损 20bps 为 24.54x 但回撤略差；移动 20% 止损为 22.00x、回撤 -43.32%；币自身 50D/100D/150D/200D 趋势过滤 ~~仅 17.57x/14.71x/10.68x/10.57x~~（列查找 bug，作废）修正后为 24.39x/16.70x/17.03x/11.13x；trend_50 在三项上都优于主策略，但这是修复后事后看到的，不能据此升级规格（见 §00）。
- 市场状态拆分（修正后，前一日状态标签）：bull 阶段主策略 25.37x、BTC 3.27x；non-bull 阶段主策略 0.91x、BTC 0.57x。两种状态下都优于 BTC，但 non-bull 阶段仍是小幅负收益，不能把整体 23.09x 理解成全天候绝对收益。
- ~~这已经是可上实盘测试的研究冠军~~ **（2026-09-25 修正）**：多重检验和参数窄峰两道门槛未通过，冠军只能保持 provisional，按 §00.4 冻结规格做样本外记录；容量、真实滑点、交易所退市、数据延迟和监控仍需验证。

### 0.3 复现实验

按依赖顺序（默认参数即权威口径，样本 2022-01-01 → 2026-09-21；2026-09-25 全部重跑过）：

```bash
# 1) 主报告、候选矩阵、成交时点（Binance/Gate 小时 K 线见 scripts/download_hourly_prices.py）
.venv/bin/python scripts/run_phase_momentum.py
.venv/bin/python scripts/run_phase_momentum_candidates.py
.venv/bin/python scripts/run_phase_momentum_execution_lag.py --lags 0,1,2 --fill-hours 1,3,6,12 --cost-bps 2,20,50,100

# 2) 试验盘点（多重检验的试验数来源）
.venv/bin/python scripts/build_trial_inventory.py

# 3) 读取候选矩阵的验证
.venv/bin/python scripts/run_phase_momentum_multiple_testing.py
.venv/bin/python scripts/run_phase_momentum_walk_forward.py
.venv/bin/python scripts/run_phase_momentum_fixed_cscv.py
.venv/bin/python scripts/run_phase_momentum_regime_breakdown.py
.venv/bin/python scripts/run_phase_momentum_robustness.py
.venv/bin/python scripts/run_phase_momentum_parameter_ensemble.py

# 4) 其余独立研究与审计
.venv/bin/python scripts/run_phase_momentum_leave_one_out.py
.venv/bin/python scripts/run_phase_momentum_parameter_leave_one_out.py
.venv/bin/python scripts/audit_phase_momentum_selections.py

# 5) 实盘信号（最新已完成的 UTC 日；拒绝过期或未收完的最后一天，见 --max-staleness-days / --allow-partial-day）
.venv/bin/python scripts/run_phase_momentum_live_signal.py
```

权威报告：

- `reports/phase_momentum_2022/`（含 `gap_carries.csv`：缺口 carry 记录）
- `reports/phase_momentum_execution_lag_2022/`（`fill_timing.csv`：收盘后 1/3/6/12 小时成交）
- `reports/research_trial_inventory/`（全项目试验盘点与预先登记台账）
- `reports/phase_momentum_walk_forward_2022/`
- `reports/phase_momentum_multiple_testing_2022/`
- `reports/phase_momentum_fixed_cscv_2022/`
- `reports/phase_momentum_leave_one_out_2022/`
- `reports/phase_momentum_parameter_leave_one_out_2022/`
- `reports/phase_momentum_regime_2022/`
- `reports/phase_momentum_robustness_2022/`
- `reports/phase_momentum_selection_audit_2022/`
- `reports/phase_momentum_live/`

---

## 0.4 历史相位审计：旧 21D 冠军不能直接上线

固定 21D 的 25.87x/22.44x 结果对调仓日历起算日极其敏感。保持所有规则不变，只把 21D 日历平移 0–20 天：

| 指标 @20bps | 数值 |
|---|---:|
| 当前 2022-01-01 相位 | **22.44x** |
| 21 个相位中位数 | **3.94x** |
| 21 个相位最差 | **0.61x** |
| 21 份完全错开组合 | **5.51x** |
| 21 份错开 Sharpe / 最大回撤 | **1.11 / -34.6%** |

因此：

- 22.44x 是相位上尾，不是稳定预期；
- 无杠杆条件下，当前证据不支持稳定做到 20x；
- 旧冠军标记为 **phase-sensitive / provisional**；
- 逐决策点外部证据见 `docs/research/strategy_evidence_audit.md`；
- 复现实验见 `reports/strategy_evidence_audit_2022/`。

### 0.1 决策点消融：11D BTC 闸门是局部尖峰，不能直接上线

第二阶段审计保持 Top20、CTREND-breakout、无杠杆、T+1 不变，分别开关自身止损、BTC 闸门和重入规则，并在 21 个调仓相位及 21 份完全错开组合上评估。20bps 下：

| 变体 | 21 份错开组合总收益 | CAGR | Sharpe | 最大回撤 |
|---|---:|---:|---:|---:|
| 当前组合：75D/3 止损 + 11D/2 BTC 闸门 | **5.51x** | 43.5% | 1.11 | -34.6% |
| 仅 BTC 11D/2 闸门，无自身止损 | 5.17x | 41.6% | 1.07 | -35.6% |
| 无自身止损、无 BTC 闸门 | 2.42x | 20.6% | 0.62 | -67.5% |
| 仅自身 75D/3 止损，无 BTC 闸门 | 2.37x | 20.1% | 0.60 | -58.0% |
| 止损后立即重入，无 BTC 闸门 | 2.22x | 18.4% | 0.58 | -62.7% |
| 自身止损 + BTC 闸门都立即重入 | 1.49x | 8.8% | 0.42 | -60.0% |
| 仅 BTC 闸门，立即重入 | 1.37x | 6.9% | 0.39 | -61.2% |

关键参数邻域：

| BTC trailing lookback（confirm2） | 10D | 11D | 14D | 20D | 30D | 50D |
|---|---:|---:|---:|---:|---:|---:|
| 21 份组合 @20bps | 3.05x | **5.51x** | 1.98x | 2.92x | 4.47x | 4.09x |

| BTC 11D 闸门 confirm | 1 日 | 2 日 | 3 日 | 5 日 |
|---|---:|---:|---:|---:|
| 21 份组合 @20bps | 2.20x | **5.51x** | 5.02x | 2.30x |

自身止损网格（20/50/65/75/100/150/200 × confirm1/2/3）在 20bps 下的 21 份组合约为 3.75x–5.66x；50–100D、confirm1–3 是宽平台，75D/3 不是唯一最优，但也没有被邻域否定。

结论：

- **11D/2 BTC 闸门目前是过拟合嫌疑最大的继承规则**；它把 2.4x 基准提高到 5.5x，但 10D/14D 和 confirm1/5 都显著崩落，不能把它当成已验证规律。
- **“止损后等下一次调仓再重入”得到项目内实证支持**：立即重入因来回打脸和换手，21 份组合明显更差。
- **75D/3 自身止损处在宽参数平台内**，方向上可保留；但它不是论文规定的唯一参数。
- 当前没有可直接上实盘的冠军。11D/2 必须替换为参数不敏感的市场闸门，或通过独立样本重新验证。
- 复现实验见 `reports/decision_point_ablation_2022/`。

### 0.2 波动率缩放 BTC 闸门：方向合理，但还不足以替代

按 Moreira/Muir 和 Yang 的波动率管理方向，把固定 11D 阈值换成 BTC 自身波动率缩放的 trailing 闸门（Chandelier 风格），并保持 75D/3 自身止损、下一次调仓重入、无杠杆和 T+1 不变。20bps 下最佳参数邻域：

| 参数 | 21 份错开组合 | 相位中位数 | 最差相位 | Sharpe | 最大回撤 |
|---|---:|---:|---:|---:|---:|
| lookback 30D / vol30 / 1.5σ / confirm2 | 3.22x | 1.89x | 0.20x | 0.70 | -56.0% |
| lookback 50D / vol30 / 1.5σ / confirm2 | 3.08x | 1.68x | 0.16x | 0.69 | -56.9% |

结论：

- 波动率缩放闸门比 11D/2 的参数邻域更连续，但绝对收益和相位稳定性仍不足；它不能把策略恢复到“稳定 20x”。
- 很多更宽的波动率倍数几乎不触发退出，退化回“无 BTC 闸门”版本。
- 该方向可以继续研究，但当前不替换冠军规则。
- 复现实验见 `reports/volatility_gate_validation_2022/`。

---

### 0.3 相位不敏感 + 波动率目标：新的领先候选（仍为研究态）

> 2026-09-23 修正：早期快速模拟器会在非调仓日无成本地把权重重置回目标值，和生产引擎不一致。现已改为“目标事件生效后持仓权重随价格漂移”，并与 `run_backtest` 对拍。下表的数字均为修正后结果；旧报告中的 3.91x/4.57x 等数字作废。

这轮不再固定 21D，也不再用 11D/2 BTC 闸门，而是：

- 选币改为 **14D balanced top1，排除 BTC**；
- 持仓仍用 **75D/3 自身趋势止损，下一次调仓重入**；
- 市场闸门改为 **BTC 100D MA，confirm2**；
- 仓位按 **60D 已实现波动率** 缩放到目标波动，**只能降仓，最大 gross exposure = 1.0，不加杠杆**；
- 所有相位等权错开，报告相位不敏感组合，而不是固定起点上尾。

2022-01-01 → 2026-09-21，20bps，相位不敏感 14 份组合：

| 目标波动 | 总收益 | Sharpe | 最大回撤 | 2025–2026 测试段 | 测试 Sharpe | 测试最大回撤 |
|---|---:|---:|---:|---:|---:|---:|
| 50% | 4.14x | 1.091 | -33.5% | 1.65x | 1.121 | -16.1% |
| 60% | 4.75x | 1.070 | -38.1% | 1.75x | 1.117 | -18.2% |
| 70% | 5.21x | 1.049 | -42.1% | 1.82x | 1.107 | -20.8% |
| 80% | 5.22x | 1.006 | -45.4% | 1.85x | 1.074 | -23.3% |

同期 BTC 约 1.87x；2025–2026 测试段 BTC 约 0.93x。这个候选的参数邻域是连续的：50%–80% 目标波动、60D 波动窗口、7D/14D 调仓周期都能得到相近结论，不像 11D/2 那样一跳就崩。

但结论仍然不能夸大：

- 全样本约 4x–5x，不是 20x；
- 最大回撤仍有 34%–45%；
- 单币集中和 2024/2026 行情依赖仍然存在；
- 这只是一个更稳健的领先候选，尚未完成成本、滚动窗口、因子家族和多重检验。

复现实验：

- `reports/vol_target_neighborhood_2022/`：7/14/21/28D × 目标波动 50%–80% × 20/30/60D 波动窗口。
- `reports/vol_target_frontier_2022/`：目标波动 80%–200% 的收益/回撤边界。
- `reports/phase_invariant_vol_target_gates_2022/`：BTC 100D/200D 闸门和止损开关对照。

### 0.4 领先候选的成本和滚动窗口压力测试

以更保守的 **14D balanced top1 ex-BTC + 75D/3 自身止损 + BTC 100D MA confirm2 + 60D 波动率目标 50%** 为例（修正漂移口径后重跑）：

| 往返总成本 | 全样本 | Sharpe | 最大回撤 | 2025–2026 测试段 | 1 年滚动最差窗口 |
|---|---:|---:|---:|---:|---:|
| 2bps | 4.69x | 1.174 | -32.7% | 1.72x | 0.821x |
| 20bps | 4.14x | 1.091 | -33.5% | 1.65x | 0.812x |
| 100bps | 2.37x | 0.724 | -38.1% | 1.37x | 0.765x |

逐年收益（20bps）：

| 年份 | 策略 | BTC |
|---|---:|---:|
| 2022 | -13.6% | -64.3% |
| 2023 | +58.0% | +155.4% |
| 2024 | +84.2% | +121.1% |
| 2025 | +8.3% | -6.3% |
| 2026 YTD | +51.9% | -1.0% |

解释：

- 这个版本在 2023 年明显跑输 BTC，但在 2022、2025、2026 胜出；
- 100bps 压力下仍约为 BTC 的 1.27 倍，但 1 年滚动最差窗口约 0.77x，不是无风险；
- 最大回撤主要来自 2024 年末的震荡回撤，不是旧策略的单次 -80% 崩盘；
- 这是目前“收益、回撤、成本、滚动窗口”四项最平衡的候选。

复现实验见 `reports/vol_target_cost_rolling_2022/`。

### 0.5 选币分数族邻域：收益并非来自一个已验证的因子

为了确认领先候选不是只依赖 `balanced` 这一组自建权重，保持 **14D、60D 波动率目标、own75、BTC MA100、20bps、全部相位错开** 不变，只替换 CTREND-lite 的分数族：

| 分数族 | 50% 目标波动总收益 | 50% Sharpe | 50% 最大回撤 | 60% 目标波动总收益 | 60% Sharpe | 60% 最大回撤 |
|---|---:|---:|---:|---:|---:|---:|
| balanced | **4.14x** | 1.091 | -33.5% | **4.75x** | 1.070 | -38.1% |
| relative_strength | 3.92x | **1.091** | **-30.1%** | 4.54x | **1.070** | **-34.9%** |
| breakout | 3.67x | 1.028 | -34.3% | 4.12x | 1.010 | -39.0% |
| acceleration | 3.20x | 0.949 | -35.3% | 3.44x | 0.921 | -40.2% |
| vol_adjusted | 1.92x | 0.632 | -31.2% | 1.86x | 0.597 | -33.3% |

结论：

- `balanced`、`relative_strength`、`breakout` 处在同一量级，说明结果不完全依赖某一个分数族；
- 但 `acceleration` 和 `vol_adjusted` 明显更差，说明“因子族不敏感”并不成立；
- 因此当前候选的收益不能被表述为“已验证的选币 alpha”，它仍然混合了波动率控制、BTC 闸门、单币集中和样本内分数选择；
- 更保守的研究对照是 `relative_strength` 50%：全样本略低，但 Sharpe 相同、最大回撤更低；
- 下一步必须做滚动 walk-forward 和多重检验修正，而不是继续在完整样本上挑最高分。

复现实验：`reports/vol_target_score_family_*_2022/`。

### 0.6 Walk-forward 与参数集成：不要动态挑参数，固定等权集成更稳

为了回答“2022–2026 全样本挑出来的 50%/60%/70%/80% 参数是不是事后有效”，新增了真正的 walk-forward：

- 训练窗口：过去 365 天；
- 测试窗口：接下来 90 天；
- 每 90 天只用过去数据重新选择 7D/14D × 50%–80% 中的 8 个版本；
- 20bps，策略切换额外按 40bps 计；
- 样本外起点：2023-01-01。

结果：

| 方案（2023-01-01 → 2026-09-21） | 总收益 | Sharpe | 最大回撤 |
|---|---:|---:|---:|
| trailing Sharpe 动态选参数 | 4.12x | 1.166 | -37.0% |
| trailing 收益动态选参数 | 5.43x | 1.159 | -48.5% |
| **8 个参数版本固定等权集成** | **6.17x** | **1.287** | **-42.0%** |
| BTC 买入持有 | 5.23x | 1.183 | -53.1% |

结论：

- 动态挑参数没有创造稳定超额；按 trailing Sharpe 选甚至跑不过 BTC；
- 固定等权集成反而在收益、Sharpe、最大回撤三项都优于 BTC；
- 原因是它不押注某个精确周期/目标波动，而是把 7D/14D × 50%/60%/70%/80% 全部纳入，降低了单参数风险；
- 这仍然是单币集中轮动，等权集成只分散参数，不分散底层单币风险。

等权集成的成本和全样本表现：

| 往返成本 | 全样本 2022–2026 | 全样本 Sharpe | 全样本最大回撤 | 2023 起样本外 | 样本外 Sharpe |
|---|---:|---:|---:|---:|---:|
| 2bps | 6.22x | 1.139 | -40.4% | 7.54x | 1.403 |
| 20bps | 5.05x | 1.033 | -42.0% | 6.17x | 1.287 |
| 100bps | 2.00x | 0.559 | -49.1% | 2.52x | 0.765 |

风险提示：

- 20bps 下 1 年滚动最差窗口仍为 **0.72x**，不是无风险；
- 100bps 下样本外仍有 2.52x，但 Sharpe 只有 0.765；
- 等权集成的优势来自参数分散，不代表 CTREND 选币因子已经被验证；
- 下一步应该做多重检验修正、容量/滑点和退市场景，而不是继续加参数。

复现实验：

- `reports/vol_target_walk_forward_2022/`
- `reports/vol_target_walk_forward_multiple_2022/`
- `reports/vol_target_ensemble_2022/`

### 0.7 新的高收益候选：Top20 内三族动量事件组合（仍为研究态）

在严格 Top20、无杠杆、T+1、2bps 真实成本口径下，新增了一组比波动率目标集成收益更高、但参数更敏感的候选：

- 每天在 point-in-time Top20 内计算 `balanced`、`relative_strength`、`breakout` 三族 CTREND-lite 分数；
- 每族使用同一事件规则：最少持有 5 天、持仓排名带 2、挑战者分数领先 10% 才切换、1 天确认；
- 持仓一旦跌出当天 Top20，立即退出，不再等待最少持有期；
- BTC 低于 100 日均线且连续确认 2 天时全部转现金；
- 60 日已实现波动率目标，主候选等权组合 70% 和 80% 两个目标波动版本；
- 总敞口硬上限 1.0，不做空、不加杠杆、不使用 Top20 以外资产。

严格 Top20 版本结果：

| 2022-01-01 → 2026-09-21 | @2bps | @20bps | @50bps | @100bps |
|---|---:|---:|---:|---:|
| 总收益 | **28.92x** | **19.69x** | **10.37x** | **3.54x** |
| CAGR | 103.9% | 87.9% | 64.1% | 30.7% |
| Sharpe | 1.434 | 1.306 | 1.090 | 0.725 |
| 最大回撤 | -46.2% | -48.7% | -54.5% | -63.5% |

分段结果（2bps / 20bps）：

| 区间 | 总收益 | Sharpe | 最大回撤 |
|---|---:|---:|---:|
| 2023 起 | **39.91x / 27.68x** | 1.751 / 1.612 | -46.2% / -48.7% |
| 2024 起 | **13.60x / 10.75x** | 1.696 / 1.575 | -46.2% / -48.7% |

年度收益（2bps）：2022 **-27.5%**、2023 **+193.3%**、2024 **+287.6%**、2025 **+81.8%**、2026 至 9 月 **+93.1%**。2020-10 至 2021-12 的固定规则压力检查为 **6.62x @2bps**，说明它不是只在 2024 年单点有效；但这仍不是实盘授权。

事件规则邻域敏感性（全样本 2022–2026，2bps）：

| 事件规则 | 总收益 | 2024 起 |
|---|---:|---:|
| 主候选：mh5 / hr2 / gap10% / confirm1 | **28.92x** | **13.60x** |
| gap 降到 5% | 24.66x | 8.84x |
| hold-rank 放宽到 3 | 15.79x | 6.57x |
| 最少持有放宽到 10 天 | 8.80x | 4.59x |

严格 Top20 退出的代价也很大：如果不要求跌出 Top20 后立即退出，全样本 2bps 为 41.52x、20bps 为 28.43x；严格版本分别降到 28.92x 和 19.69x。由于用户硬约束是“不能超过 Top20”，报告只把严格版本作为主口径。

闸门和目标波动邻域也做了低维审计。2bps 下：无 BTC 闸门只有 10.80x；MA50/confirm1–3 为 12.15x–13.79x；MA100/confirm1–3 为 23.62x–28.95x；MA200/confirm1–3 为 16.32x–18.19x。MA100 的 confirm1 和 confirm2 几乎相同（28.95x / 28.92x），是当前闸门平台；目标波动从 70%/80% 提高到 90%/100% 后全样本反而降到 28.05x、2024 起仅 13.70x，因此没有采用更高目标波动。

结论：

- 这是本轮新增的**高收益严格 Top20 研究候选**：在 2022–2026 全样本、2bps 实际成本口径下超过 20x；
- 但它的收益高度依赖一个事件规则尖峰，邻近参数虽然仍为正，却从 28.9x 掉到 8.8x–24.7x，不能据此宣称稳定 alpha；
- 2024 起子区间只有 13.6x @2bps，说明 20x 目标主要由 2023 年贡献，未来不能外推；
- 因此新候选标记为 **高收益研究候选 / provisional**，不能覆盖更稳健但收益较低的波动率目标集成，也不能直接上实盘；
- 下一步必须做真正的嵌套 walk-forward、多重检验修正、换手/容量压力和不同市场阶段的独立验证。

复现实验：

- `reports/momentum_event_ensemble_2022/`
- `scripts/run_momentum_event_ensemble.py`


### 0.8 Top20 市场宽度闸门：风险明显下降，2024 起收益改善

前一轮三族动量事件组合的弱点是 2024 起只有 13.60x @2bps，且最大回撤 -46.2%。新增一个只用 **当前 Top20 成员**计算的市场宽度信号：

- 宽度 = 当前 Top20 中收盘价高于自身 50 日均线的币占比；
- 基础闸门仍是 BTC 100 日均线、确认 2 天；
- 宽度闸门版本再要求宽度 ≥ 50%；
- 混合版本 = 50% 基础版本 + 50% 宽度版本，每天等权再平衡。

结果（严格 Top20、无杠杆、T+1、60D 波动率目标 70%/80%）：

| 策略 | 成本 | 全样本 2022–2026 | 2023 起 | 2024 起 | Sharpe | 最大回撤 |
|---|---:|---:|---:|---:|---:|---:|
| 基础：BTC MA100 | 2bps | **28.92x** | **39.91x** | 13.60x | 1.434 | -46.2% |
| 宽度 ≥50% | 2bps | 16.61x | 22.45x | **17.66x** | **1.962** | **-32.7%** |
| 50/50 混合 | 2bps | **23.10x** | **31.54x** | **15.95x** | **1.867** | **-36.0%** |
| 基础：BTC MA100 | 20bps | **19.69x** | **27.68x** | 10.75x | 1.306 | -48.7% |
| 宽度 ≥50% | 20bps | 11.51x | 15.82x | **14.09x** | **1.833** | **-34.8%** |
| 50/50 混合 | 20bps | 15.87x | 22.04x | **12.66x** | **1.739** | **-37.2%** |

阈值邻域（全样本 / 2024 起，2bps）：

| 宽度阈值 | 全样本 | 2024 起 | 最大回撤 |
|---|---:|---:|---:|
| 40% | 11.55x | 11.08x | -55.5% |
| 45% | 13.99x | 14.81x | -55.3% |
| **50%** | **16.61x** | **17.66x** | **-54.7%** |
| 55% | 13.83x | 13.71x | -51.4% |
| 60% | 10.42x | 10.55x | -52.3% |

50% 是当前最优阈值，但 45% 和 55% 仍然有效，说明它不是单点尖峰；40% 和 60% 明显更差。混合权重邻域也连续：基础权重 25%/50%/75% 时，2bps 全样本为 19.85x/23.10x/26.18x，2024 起为 16.91x/15.95x/14.83x。

年度收益（2bps）：

| 策略 | 2022 | 2023 | 2024 | 2025 | 2026 至 9 月 |
|---|---:|---:|---:|---:|---:|
| 基础 | -27.5% | +193.3% | +287.6% | +81.8% | +93.1% |
| 宽度 ≥50% | -26.0% | +27.1% | **+457.0%** | +69.0% | +87.7% |
| 50/50 混合 | -26.8% | +97.8% | +368.4% | +76.7% | +92.7% |

2020-10 至 2021-12 压力检查（2bps）：基础 **6.62x**、宽度 50% **5.07x**、50/50 混合 **5.83x**。宽度闸门牺牲了部分 2021 和 2023 收益，但显著改善了 2024 起收益和回撤。

结论：

- 宽度 50% 是目前**风险调整后最干净**的新版本：2024 起 17.66x @2bps，Sharpe 1.962，最大回撤 -32.7%；
- 50/50 混合是收益/风险折中：全样本 23.10x、2023 起 31.54x、2024 起 15.95x @2bps，最大回撤 -36.0%；
- 但它仍然没有在 2024 起单独超过 20x，且宽度阈值仍是项目内选择的参数；
- 外部研究支持“大市值/高流动性币的动量和趋势更稳”，但宽度信号本身还没有同等强度的学术证据，因此该版本标记为**高收益研究候选 / provisional**，不能直接上实盘。

复现实验：

- `reports/momentum_event_breadth_overlay_2022/`
- `scripts/run_momentum_event_breadth_overlay.py`


---

## 1. 一句话结论（有领先研究候选，但仍不可直接上实盘）

在 **真实 point-in-time Top20 + 无杠杆 + 现货** 约束下，当前有两条不同定位的研究路线：**最稳健路线**仍是 **7D/14D × 50%/60%/70%/80% 共 8 个波动率目标版本的固定等权集成**（balanced top1、75D/3 自身止损、BTC 100D MA 闸门）；**最高收益但更参数敏感路线**是第 0.7 节的三族动量事件组合（严格 Top20、2bps 全样本 28.92x，但 2024 起只有 13.60x）。两者都不能直接上实盘。旧的固定起点高收益组合仍保留作上尾对照：

**旧上尾候选：CTREND-breakout 单币集中轮动 + 每日自身趋势止损**
= 历史 Top20 内排除 BTC → 21 天调仓选 CTREND-breakout 第 1 名 → 每日检查持仓是否连续 3 个交易日收盘低于自身 75 日均线 → 若是则转现金，下一次 21 天调仓才允许重入 → BTC 跌破 11 日前收盘连续 2 天则全部转现金。

| 2022-01-01 → 2026-09-21 | 旧上尾候选 @2bps | 旧上尾候选 @10bps | 旧上尾候选 @20bps | BTC |
|---|---:|---:|---:|---:|
| 总收益 | **25.87x** | **24.28x** | **22.44x** | 1.87x |
| CAGR | 99.1% | 96.5% | 93.2% | 13.5% |
| Sharpe | 1.360 | 1.339 | 1.313 | 0.502 |
| 最大回撤 | -41.8% | -42.6% | -44.0% | -67.0% |
| 年换手 | 16.7x | 16.7x | 16.7x | ~0.2x |

> 注意：上表是 2022-01-01 单一相位的上尾结果。相位中位数和错开组合见第 0 节。

**为什么不是每天重新选币**：每天检查数据是对的，但“每天重新选第一名”会显著放大噪声和换手。项目实测了 176 组每日事件驱动/hysteresis 变体：固定起点最高的一组在 20bps 下到 **76.48x**，但参数邻域中位数只有 **2.20x**、邻域最差 **0.11x**，属于明显的参数尖峰，不能作为稳健冠军。第 0.7 节进一步加入了严格 Top20 退出、BTC MA100 闸门和波动率目标，三族动量事件组合在 2bps 全样本达到 **28.92x**，但事件规则邻域从 8.8x 到 24.7x、2024 起只有 13.60x，因此它被记录为高收益研究候选，而不是实盘冠军。把每日检查用于“持仓自身趋势退出”和严格 Top20 风险控制，比每日裸选第一名更可解释。

**止损后为什么不立即重入**：这不是凭直觉保留的规则。逐决策点审计把“下一次调仓重入”和“信号恢复后立即重入”分开比较；立即重入的换手显著上升，21 份错开组合从 5.51x 降到 1.49x，因此当前样本支持等待下一次调仓。

**为什么 11D/2 闸门仍标记为高风险**：它虽然在当前数据上把 21 份组合从 2.37x 提到 5.51x，但 10D/14D、confirm1/5 的邻域都明显更差。没有外部研究直接支持 11D/2；它更像样本内挑出来的参数尖峰，而不是稳定规律。

**结论不是“可以稳定每年翻倍”**：25.87x 仍是 2022-01-01 固定起点的结果。45 个月度起点滚动回测中，@2bps 中位数 **3.80x**、最差 **0.62x**；@20bps 中位数 **3.51x**、最差 **0.585x**。即使改成 21 份错开组合，当前完整规则也只有 5.51x，而且依赖 11D/2 闸门；无闸门版本只有 2.42x。对于旧上尾候选，当前证据不支持稳定 20x；第 0.7 节新候选虽然在 2bps 全样本超过 20x，但 2024 起只有 13.60x，且事件规则邻域敏感，因此同样不支持直接上实盘。

---

## 2. 定义（完全可复现）

| 步骤 | 规则 |
|---|---|
| ① 股票池 | 每个调仓日按 CMC 市值重建 **当时 Top20**；严格流动性门槛：历史 ≥90 天、日成交额 ≥$25M、CMC 市值 >0、价格 >0，并应用项目流动性/包装资产过滤 |
| ② 基础策略 | `ctrend_lite_breakout`：趋势 7/14/21/28/42/60 日收益、短期加速度、90 日高点突破、相对 BTC/ETH 强度、成交量扩张、波动率和过热惩罚的加权排名 |
| ③ 选币 | Top20 内排除 BTC，取分数第 1 名，单币 100% |
| ④ 持仓趋势止损 | 每日检查当前持仓；连续 3 个交易日收盘低于自身 75 日均线 → 目标改为 100% 现金，下一次 21 天调仓日才允许重入 |
| ⑤ 市场风控 | BTC 收盘跌破其 11 日前收盘 → 状态为 risk-off；连续 2 天确认后，目标改为 100% 现金；下一次 21 天调仓日若已恢复 risk-on，才允许重新买币 |
| ⑥ 调仓 | 选币 21 天一次；信号在收盘生成，T+1 执行；持仓趋势和市场风控每日检查，退出可在两次调仓之间发生 |
| ⑦ 成本 | 2bps/10bps/20bps 分别报告；表内均为**往返总成本**（例如 2bps = 每边 1bps 手续费+滑点），2bps 对应你声明的实际成本+返佣口径，20bps 是保守压力测试 |
| ⑧ 无杠杆 | 目标权重之和 ≤1.0，engine 的 `max_gross_exposure=1.0` 会拒绝超限 |

**主动排除 BTC 选币**：加入 BTC 后同一策略 @2bps 只有约 15x，因为 BTC 会在部分高弹性阶段取代真正上涨的币。这里的“排除 BTC”只针对选币，风控仍然使用 BTC 作为大盘闸门。

---

## 3. 权威结果

### 2.1 成本与总收益

| 往返总成本（脚本拆成每边一半） | 总收益 | CAGR | Sharpe | 最大回撤 |
|---|---:|---:|---:|---:|
| 2bps | **25.87x** | 99.1% | 1.360 | -41.8% |
| 5bps | 25.26x | 98.1% | 1.352 | -41.9% |
| 10bps | **24.28x** | 96.5% | 1.339 | -42.6% |
| 20bps | **22.44x** | 93.2% | 1.313 | -44.0% |
| 50bps | 17.68x | 83.7% | 1.236 | -47.9% |
| 100bps | 11.87x | 68.8% | 1.105 | -53.8% |
| BTC @2bps | 1.82x | 13.5% | 0.502 | -67.0% |

### 2.2 逐年表现（策略 @2bps vs BTC）

| 年份 | 策略 | BTC |
|---|---:|---:|
| 2022 | -5.9% | -65.3% |
| 2023 | +66.7% | +155.4% |
| 2024 | **+347.2%** | +121.1% |
| 2025 | +42.7% | -6.3% |
| 2026 YTD | **+158.3%** | -1.0% |

2023 仍然明显输给 BTC；2024 和 2026 是超额收益的主要来源。不要只看 CAGR 或累计倍数。

### 2.3 滚动起点（45 个月度起点）

| 指标 | @2bps | @20bps |
|---|---:|---:|
| 中位数倍数 | 3.80x | 3.51x |
| 最差起点 | 0.62x | 0.585x |
| 最好起点 | 25.87x | 22.44x |
| 中位数最大回撤 | -47.4% | -49.4% |
| 最差最大回撤 | -74.7% | -76.3% |

这张表比 25.87x 更重要：**从 2022-01-01 起跑很好，不代表任意时点开始都很好。**

---

## 4. 候选对比与为什么没有选更高倍数

### 3.1 同一 Top20 面板上的近距离候选

| 基准/候选 | @2bps | @20bps | 滚动起点中位数 | 最差起点 | 最大回撤 |
|---|---:|---:|---:|---:|---:|
| BTC 50/100/120 日均线等 | — | 通常 2–8x | — | — | 高 |
| CTREND-breakout top1 21D + BTC trailing11 confirm2 + BTC停车 | 24.00x | 18.27x | **4.05x** | 0.57x | -64.6% |
| CTREND-breakout top1 21D + BTC trailing11 confirm2 + cash（旧冠军） | 21.56x | 18.57x | 3.48x | **0.67x** | -49.2% |
| **CTREND-breakout top1 21D + 每日自身75日MA confirm3止损 + BTC trailing11 + cash（新冠军）** | **25.87x** | **22.44x** | 3.80x | 0.62x | **-41.8%** |
| 每日事件驱动最高固定起点尖峰（mh5/hr2/gap10/c1） | 137.43x | 76.48x | 邻域中位仅 2.20x | 邻域最差 0.11x | -61.1% |

**取舍**：
- 每日事件驱动最高固定起点看似远超新策略，但参数邻域塌陷，不能采用。
- 新冠军用同一 21 天选币频率，把每日数据只用于持仓自身趋势退出；它提高了固定起点收益、Sharpe 和回撤，同时换手没有上升。
- 新策略在 2022-2023、2022-2024 和 2025-2026 都优于旧冠军；在 2024-2026 基本持平（20bps 下约 1.62x vs 1.63x）。

### 3.2 Top50 灵敏度（不是你的 Top20 规则）

Top50 + strict 流动性 + CTREND relative-strength top1 14D + BTC MA150 在 2022 起 @20bps 达到 **23.54x**。但它不是生产规则：

- 滚动起点中位数 **2.15x**，最差 **0.096x**，最好 59.7x；
- 中位数回撤 -70.8%，最差 -94.9%；
- 收益几乎全部来自 2024 年 11–12 月的 DOGE/XRP 行情；
- Top50 的流动性、冲击成本和容量都不如 Top20。

**结论：Top50 版本可以作为研究线索，不能当作“你的 Top20 策略”上线。**

### 3.3 纯时间序列动量（TSMOM）

基于 Han/Kang/Ryu 的论文，另外实现了并全跑 **1,440 组 TSMOM**（Top20/Top50 × 30/90/180 日回看 × 7/14/28 日调仓 × top1/top3/all × equal/inverse-vol × 8 种 overlay）：

| 宇宙 | 最佳总收益 | 最佳 Sharpe | ≥5x 候选数 |
|---|---:|---:|---:|
| Top50 灵敏度 | 4.95x | 0.90 | 0 |
| Top20 | 2.72x | 0.82 | 0 |

结论：在这批数据上，**“每币自身趋势闸门 + 广泛风险平价”远弱于“Top20 内集中选最强币”**。论文说 TSMOM 证据较强，是在不同的资产池、权重和样本定义下；本项目的真实数据在这一段没有支持纯 TSMOM 达到 20x。

### 3.4 多策略集成

对 Top50 的 5 种 CTREND 家族做 2/3/5/10 组件等权集成：

- 2 组件：13.65x，DD -49.8%；
- 3 组件：12.75x，DD -52.6%；
- 5/10 组件：更低。

集成确实降低了单币和单参数风险，但达不到 20x，所以没有取代冠军。

### 3.5 每日重检/事件驱动调仓研究（2026-09-23 新增）

问题不是“能不能每天看数据”，而是“每天看到变化后该不该交易”。当前旧策略本来就已经每日检查 BTC 风控；固定的是选币日历。为了验证每日选币是否更好，项目跑了：

- 176 组固定频率 + daily event/hysteresis 变体（最小持有、hold-rank band、score gap、确认天数）；
- 36 组“21 天选币 + 每日 rank-stop 退出”混合变体；
- 27 组“21 天选币 + 每日自身均线止损”变体（MA 20–200 日 × 1–3 日确认）。

结果：

| 方向 | 最佳固定起点 @20bps | 稳健性结论 |
|---|---:|---|
| 每日事件驱动轮动 | 76.48x（mh5/hr2/gap0.10/c1） | 参数邻域中位数仅 2.20x，邻域最差 0.11x；拒绝 |
| 21 天选币 + 每日 rank-stop | 25.33x（hr5/c3/mh10） | 2024-2026 仅 1.16x，低于旧冠军 1.63x；拒绝 |
| 21 天选币 + 每日自身 MA75 confirm3 止损 | **22.44x** | 滚动中位数 3.51x、最差 0.585x；MA 50–100 日邻域均约 21–24x；采用 |

**结论**：每日检查有价值，但价值主要在风险退出、确认和 hysteresis，而不是每天重新排序换仓。固定 21 天选币日历是换手和过拟合控制，不是拒绝每日数据的理由。自身趋势止损方向可以保留，但整体候选仍受第 0.1 节的 BTC 闸门参数脆弱性约束。

---

## 5. 数据与选币审计

### 4.1 Point-in-time Top20 独立审计

`scripts/audit_ctrend_selections.py` 不经过 processed 市值矩阵，而是直接从 `data/raw/coinmarketcap/history` 的原始 CMC payload 重建每个 21 天调仓日的 Top20，再和策略实际使用的 universe 逐日比较：

| 项目 | 结果 |
|---|---:|
| 比较调仓日 | **83** |
| Top20 集合一致 | **83 / 83** |
| Top20 顺序一致 | **83 / 83** |
| 市值数值不符 | **0** |
| 选中的币不在当日 Top20 | **0** |
| 实际有持仓的调仓日 | 42 |

完整逐日明细：
- `reports/trend_stop_champion_2022/audit/selections.csv`
- `reports/trend_stop_champion_2022/audit/universe_audit.csv`
- `reports/trend_stop_champion_2022/audit/selection_audit.md`

### 4.2 数据质量

- 数据链审计：`scripts/audit_data_chain.py`，**43 PASS / 6 WARN / 0 FAIL**（2026-09-23 时点；**已被 §00.5 的 2026-10-08 结果取代：42 PASS / 9 WARN / 0 FAIL**）；
- 被独立源拒绝的标的：CEL、HT（价格不一致），不进入排名/策略（**2026-10-08 更新：CEL 仍被拒绝；HT 的市值 feed 已结束、当前缓存无可比对区间，改为 historical-only——保留历史、市值结束后永不参与排名。见 §00.5**）；
- RAIN 被流动性门槛排除；
- 缺失行情策略为 `error`（2026-10-08 现状：`carry`，单次缺口 ≤3 天且逐条记入 `gap_carries`，更长即中止；结束的 feed 按最后价格卖出），不会把停牌/下架误当 0% 收益；
- 买入后行情终止：按最后一个有效收盘价强制退出并计成本，不继续假装能交易；
- 研究脚本使用 `persist=False` 在内存中构建面板，不会覆盖 canonical `data/processed/panel_daily.csv`；
- 每日刷新写盘前有回归闸门：如果新面板会让已有资产消失、或把面板起止日期往内/往回移动，直接报错并保留旧面板。

### 4.3 外部研究参考

已查阅并保留原始结果：

- Han, Kang, Ryu, *Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market: A Comprehensive Analysis under Realistic Assumptions*：<https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>。核心结论：考虑真实成本和日间波动后，很多横截面组合会被清算；时间序列动量证据相对更强，动量集中在大赢家；换仓日选择本身会显著影响结论。
- Yang, *Cryptocurrency market risk-managed momentum strategies*：<https://doi.org/10.1016/j.frl.2025.107879>。风险缩放把周均收益从 3.18% 提升到 3.47%，年化 Sharpe 从 1.12 提升到 1.42，且在交易成本下仍有稳健性。
- Kaya, Mostowfi, *Low-volatility strategies for highly liquid cryptocurrencies*：<https://doi.org/10.1016/j.frl.2021.102422>。低波动组合加简单止损能显著降低下行风险并改善 Sharpe。
- Kaminski, Lo, *When do stop-loss rules stop losses?*：<https://doi.org/10.1016/j.finmar.2013.07.001>。止损是否增加收益取决于采样频率和市场状态；论文支持“止损可以降低波动”，但不支持任意固定参数。
- Sadaqat, Butt, *Stop-loss rules and momentum payoffs in cryptocurrencies*：<https://doi.org/10.1016/j.jbef.2023.100833>。147 个币、2015-01 至 2022-06 的样本中，止损版动量在收益、Sharpe 和 alpha 上优于普通动量；这支持“止损方向”，不支持直接照搬某个均线周期。
- Le, Ruthbah, *Trend-following Strategies for Crypto Investors*：<https://www.monash.edu/__data/assets/pdf_file/0011/3744821/Trend-following-Strategies-for-Crypto-Investors.pdf>。测试 20/65/150/200 日均线；BTC 上 65D 较好，ETH 和大型非 BTC 指数上 20D 较好；交易成本显著侵蚀收益。
- Duarte, *Trailing Stop-Loss and Re-Entry Strategies in Europe*：<https://doi.org/10.24018/ejbmr.2022.7.3.1426>。止损后的重入规则是独立决策点；文章使用 3% 回撤止损和 3% 回升重入，结果显示重入规则有场景依赖，不能默认“一回升就买”。
- Alpha Architect, *Portfolio Rebalancing Research: Momentum and Tolerance Bands*：<https://alphaarchitect.com/destabilizing-rebalancing>。更频繁地“检查”不等于更频繁地交易；no-trade band 能减少无效换手。
- Aligrithm, *Percentile-Rank Momentum With Hysteresis*：<https://aligrithm.com/percentile-rank-momentum-with-hysteresis-low-churn-signals>。用高低阈值之间的 hysteresis band 抑制排名噪声；该文也明确指出其 crypto 回测缺少成本和基准，因此本项目只采用方法方向，不采用其收益结论。
- Vilnius University, *Momentum strategies in cryptocurrency markets* (2026)：8 个大币样本，TSMOM 风险调整后优于 XSMOM：<https://www.journals.vu.lt/BATP/en/article/view/44540>。
- Starkiller Capital, cross-sectional momentum in crypto：<https://www.starkiller.capital/post/cross-sectional-momentum-in-cryptocurrency-markets>。

外部论文只能提供方向，不能代替本项目的 point-in-time 数据和成本回测；本文所有结论以项目实跑为准。

---

## 6. 已知局限（上实盘前必须知道）

1. **起点敏感**：固定 2022-01-01 的 25.87x 不是任意起点可达；@2bps 滚动中位数 3.80x、最差 0.62x。完全错开 21 份组合也只有 5.51x。
2. **市场闸门参数尖峰**：11D/2 BTC trailing 闸门把 21 份组合从 2.37x 提到 5.51x，但 10D/14D、confirm1/5 都显著崩落；当前不能把它当成稳定规律，更不能直接上实盘。
3. **收益集中**：2024 年 +347%，2026 YTD +158%；如果未来没有类似的单币大行情，收益会显著下降。
4. **单币集中**：同一时间只持 1 个币，存在跳空、下架、流动性枯竭和单币黑天鹅风险。
5. **每日止损会误伤**：75 日均线 + 3 日确认处在 50–100D/confirm1–3 的宽平台内，但趋势震荡期仍可能卖在低点；不能用更高频的每日轮动替代确认机制。
6. **重入规则**：当前样本支持“止损后等到下一次调仓再重入”，立即重入的 21 份组合只有 1.49x；这条结论仍需独立样本验证。
7. **成本假设**：2bps 依赖你实际成交和返佣；20bps 下为 22.44x，50bps 下为 17.68x，100bps 下为 11.87x。
8. **容量**：Top20 虽比 Top50 好，但单币满仓时规模受币种深度限制；大额资金需要重新做冲击成本测试。
9. **过拟合风险**：每日事件驱动最高固定起点 76.48x 和 11D/2 BTC 闸门都已暴露为参数尖峰；新策略仍需持续做 walk-forward、参数邻域和成本压力测试。
10. **未建模**：税务、返佣到账延迟、交易所限价/滑点、借贷/资金费（当前无杠杆不适用）。

---

## 7. 复现命令

```bash
# 新冠军：21D 选币 + 每日自身75日MA confirm3止损，2/5/10/20/50/100bps
.venv/bin/python scripts/run_trend_stop_champion.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --cost-bps 2,5,10,20,50,100 \
  --output-dir reports/trend_stop_champion_2022

# 每日自身趋势止损全参数扫描（MA20-200 × confirm1-3 + fresh rolling）
.venv/bin/python scripts/run_trend_stop_validation.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --output-dir reports/trend_stop_validation_2022

# 每日事件驱动/hysteresis/rank-stop 全参数扫描
.venv/bin/python scripts/run_event_driven_validation.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --output-dir reports/event_driven_validation_2022

# 独立 CMC Top20 + 选币审计（新冠军基础选币）
.venv/bin/python scripts/audit_ctrend_selections.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --output-dir reports/trend_stop_champion_2022/audit

# 旧冠军（保留作对照）
.venv/bin/python scripts/run_ctrend_champion.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --cost-bps 2,5,10,20,50,100 \
  --output-dir reports/ctrend_champion_top20_2022

# 2218 组 Top20 全量筛选（2022 起，screen-only）
.venv/bin/python scripts/run_top20_convex_validation.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --universe-size 20 --screen-only --workers 8 \
  --output-dir reports/convex_validation_2022_top20

# 1440 组 TSMOM 对照筛
.venv/bin/python scripts/run_tsmom_validation.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --workers 8 --screen-only --output-dir reports/tsmom_validation_2022

# 相位敏感性 + 错开组合审计（判断 21D 冠军是否只是日历运气）
.venv/bin/python scripts/run_strategy_evidence_audit.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --cost-bps 2,20 --tranche-counts 1,3,7,21 \
  --output-dir reports/strategy_evidence_audit_2022

# 逐决策点消融：自身止损、BTC 闸门、重入方式（21 相位 + 错开组合）
.venv/bin/python scripts/run_decision_point_ablation.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --cost-bps 2,20 --output-dir reports/decision_point_ablation_2022

# BTC 波动率缩放 trailing 闸门验证
.venv/bin/python scripts/run_volatility_gate_validation.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --cost-bps 2,20 --output-dir reports/volatility_gate_validation_2022

# 相位不敏感 + 波动率目标仓位：主候选邻域
.venv/bin/python scripts/run_phase_invariant_vol_target.py \
  --config config/base.yaml --start-date 2022-01-01 \
  --cycles 7,14,21,28 --target-vols 0.5,0.6,0.7,0.8 \
  --vol-windows 20,30,60 --stop-modes own75 --gate-modes btc_ma100 \
  --cost-bps 2,20 --output-dir reports/vol_target_neighborhood_2022

# 数据链审计
.venv/bin/python scripts/audit_data_chain.py --config config/base.yaml
```

---

## 8. 文件索引（权威性）

| 路径 | 内容 | 状态 |
|---|---|---|
| `RESEARCH.md` | **本文，唯一权威结论** | ✅ 权威 |
| `docs/research/literature_review_2026-09.md` | H1–H5 的预注册规则、参数来源与 kill criterion（H5 于 2026-10-08 追加） | ✅ 权威预注册 |
| `reports/phase_momentum_hypotheses_2026_10/` | H2–H5 预注册试验：判据、DSR、Reality Check、压力窗口、逐年、逐币归因 | ✅ 当前权威 |
| `reports/phase_momentum_candidate_eval_h5/` | B / H3 / H5 与两族邻域的同口径横评（含 DSR） | ✅ 当前权威 |
| `reports/phase_momentum_multiple_testing_overlays/` | 36 候选族的 CSCV/PBO（H5 = 0.192，首个通过）、DSR、Reality Check | ✅ 当前权威 |
| `reports/phase_momentum_execution_timing_30m/` | 30m 执行时点：00:30/01:00/01:30/02:00/50-50 分片、两套缺失口径、2/20/50/100bps；全部被拒（§00.23） | ✅ 当前权威（否定结果） |
| `reports/phase_momentum_regime_overlays/` | B / H3 / H5 的 bull 与 non-bull 拆分 | ✅ 当前权威 |
| `reports/phase_momentum_dsr_gap/` | DSR 差距定价：达到 0.95 所需的年化 Sharpe（family / top20 / all_trials） | ✅ 当前权威 |
| `reports/phase_momentum_dsr_horizon/` | DSR 的时间维度定价：保持样本内 Sharpe 需 6.4 年新数据；只用样本外的 t 检验需 1.06 年（§00.20） | ✅ 当前权威 |
| `reports/phase_momentum_crash_states/` | 崩溃月与可观测状态变量的对照（否定性结果：无变量区分度 > 0.4σ） | ✅ 当前权威 |
| `reports/phase_momentum_flow_states/` | 量能/换手/集中度状态筛查（9 个变量全部被拒）；含 §00.14 表格的全样本勘误 | ✅ 当前权威 |
| `reports/phase_momentum_hourly_states/` | 小时线日内状态筛查（已实现方差/半方差/小时成交集中度/场所占比/日内自相关/时段效应；7 个变量全部被拒） | ✅ 当前权威 |
| `reports/phase_momentum_funding_states/` | 永续资金费率状态筛查（4 个变量全部被拒；`funding_level` 崩溃月区分度 +1.12σ 为三次筛查最强，但方向与冗余度决定不可用） | ✅ 当前权威 |
| `reports/phase_momentum_chase_risk/` | 追高进场诊断：极端 21 日涨幅后策略前瞻收益衰减（21 日 +1.78% vs +7.74%，按 gross 归一 t=-2.83）；含 MAX 构造的对照 | ✅ 当前权威 |
| `reports/phase_momentum_dispersion_diagnostic/` | 离散度机制的项目内诊断（五档前瞻 + Spearman） | ✅ 筛查证据 |
| `reports/phase_momentum_dispersion_overlay/` | 离散度叠加的日频筛查（**未计**额外换手，收益偏高） | ⚠️ 仅筛查，非候选 |
| `reports/phase_momentum_live/` | 冻结规格（H5）的最新目标快照；信号工具，不下单 | ✅ 当前 |
| `reports/phase_momentum_oos_2026/` | 冻结规格自 2026-09-22 起的样本外跟踪 | ✅ 当前 |
| `reports/phase_momentum_multiple_testing_2022/` | 30 个单规格变体的 CSCV/PBO（B = 0.526） | ✅ 历史基线 |
| `reports/phase_momentum_candidate_eval/` | H3 采用时的横评快照 | ⚠️ 已被 §00.13 取代 |
| `reports/phase_momentum_multiple_testing_h3/` | H3 的 PBO（0.558，fail） | ⚠️ 历史 |
| `reports/research_trial_inventory/` | 试验台账、DSR 分母（Top20/2022 = 6,142）与 manifest | ✅ 权威计数 |
| `reports/trend_stop_champion_2022/` | 固定 21D 冠军结果、逐年、子区间、目标历史、最新信号、基础选币审计 | ⚠️ 相位敏感，只能作为上尾参考 |
| `reports/trend_stop_validation_2022/` | MA20-200 × confirm1-3 每日自身趋势止损全扫 + fresh rolling | ✅ 权威研究 |
| `reports/event_driven_validation_2022/` | 176 组每日事件/hysteresis + 36 组每日 rank-stop 混合；用于证明每日轮动未采用 | ✅ 权威研究 |
| `reports/strategy_evidence_audit_2022/` | 21D 相位扫描 + 1/3/7/21 份错开组合稳健性审计 | ✅ 权威审计 |
| `reports/decision_point_ablation_2022/` | 自身止损、BTC 闸门、重入方式的 21 相位/错开组合消融 | ✅ 权威审计，否定 11D/2 为稳定规律 |
| `reports/volatility_gate_validation_2022/` | BTC 波动率缩放 trailing 闸门参数邻域验证 | ✅ 方向合理，但当前不足以替代 |
| `reports/phase_invariant_vol_target_gates_2022/` | 相位不敏感 + 波动率目标 + BTC MA 闸门对照 | ✅ 新领先候选研究 |
| `reports/vol_target_neighborhood_2022/` | 7/14/21/28D × 目标波动 × 波动窗口参数平台 | ✅ 当前最完整稳健性证据 |
| `reports/vol_target_frontier_2022/` | 目标波动 80%–200% 收益/回撤边界 | ✅ 边界研究 |
| `reports/vol_target_cost_rolling_2022/` | 领先候选 2–100bps 成本压力 + 1 年滚动窗口 | ✅ 当前最关键稳健性报告 |
| `docs/research/strategy_evidence_audit.md` | 逐决策点外部证据矩阵和未验证假设 | ✅ 权威审计 |
| `docs/superpowers/specs/2026-10-09-bitget-derivatives-track-design.md` | Bitget 衍生品独立轨道设计稿（long/short、杠杆、保证金、funding、强平、预注册 trials） | ⚠️ 设计稿，待负责人审阅 |
| `docs/research/derivatives_track_research_2026-10.md` | 衍生品外部研究、项目内诊断、Bitget API 事实和 Phase 1 数据审计 | ⚠️ 研究输入，不构成上线批准 |
| `reports/derivatives_track_data_audit/` | Phase 1 合约映射、K 线抽样覆盖和 funding 重叠审计 | ⚠️ funding 代理未通过预注册门槛 |
| `reports/derivatives_track_engine_validation/` | Phase 2 isolated-margin 1.0x 对 H5 的代理 mark 校验 | ⚠️ 代理诊断，非 Bitget 结果 |
| `reports/derivatives_track_margin_calibration/` | 8 个预注册保证金 buffer 校准 trial | ⚠️ 代理诊断；50% buffer 当前最小零强平点 |
| `reports/derivatives_track_proxy_trials*/` | V2 long-only 代理试验与成本压力 | ⚠️ 代理诊断，待 Bitget mark 重跑 |
| `reports/ctrend_champion_top20_2022/` | 旧冠军（固定21D，无每日自身趋势止损） | ⚠️ 已被新冠军取代 |
| `reports/convex_validation_2022_top20/` | 2218 组 Top20 2022 起点全量筛选 | ✅ 权威研究 |
| `reports/convex_validation_2022_top50/` | Top50 灵敏度全量筛选 | ⚠️ 只做灵敏度，不是生产规则 |
| `reports/tsmom_validation_2022/` | 1440 组纯 TSMOM 对照 | ✅ 对照结论 |
| `reports/no_leverage_ablation_2022/` | 400 组跨家族无杠杆消融 | ✅ 保守基准 |
| `reports/convex_overlay_sweep_2022_top20/` | 1584 组 BTC 风控/停车资产参数扫描 | ✅ 冠军选择依据 |
| `reports/ctrend_focus_2022_top50/`、`reports/ctrend_focus_2022_top20/` | Top50/Top20 小范围 overlay 聚焦 | ⚠️ 已被更完整的 overlay sweep 取代 |
| `reports/bull_offense_finalist*` | 旧冠军 bull-offense | ❌ 已被本文取代 |
| `reports/top20_convex_validation/` | 旧面板 2218 筛选 | ❌ 旧面板，仅历史参考 |
| `reports/latest/` | 主流水线 32 个策略（含 BTC/ETH 基准） | ✅ 仍可用于基准对比 |

**数据更新方案**：`ops/com.atlas20.daily-refresh.plist` 已安装到用户 `launchd`，每日 02:30/02:55/06:30 UTC 执行（2026-10-16 起增加 02:55 盘前补跑；`scripts/refresh_daily_data.py` 在面板已覆盖最后完整 UTC 日时直接跳过，并持文件锁防止两次刷新并发写 raw）；CoinGecko 独立校验缓存有 3 小时 TTL，避免 Gate 不上市资产长期使用旧缓存后被错误排除。

---

## 9. Derivatives Track（独立研究轨道）

> 本节不修改 H5 Spot Track 的任何结论，也不构成衍生品上线批准。它只记录 Bitget USDT-M 独立轨道的研究、设计和 Phase 1 数据审计状态。

### 9.1 文档与数据

- 设计稿：`docs/superpowers/specs/2026-10-09-bitget-derivatives-track-design.md`
- 外部研究：`docs/research/derivatives_track_research_2026-10.md`
- Phase 1 审计报告：`reports/derivatives_track_data_audit/report.md`
- 下载器：`scripts/download_bitget_derivatives_data.py`
- 并行下载分片合并器：`scripts/merge_bitget_derivatives_shards.py`
- Bitget mark V2 矩阵运行器：`scripts/run_bitget_mark_matrix.py`
- 审计器：`scripts/audit_bitget_derivatives_data.py`
- 客户端与映射：`src/atlas20/derivatives/`

### 9.2 2026-10-09 Phase 1 结论

- PIT Top20 历史池 102 个 coin id，其中 **88 个映射到 Bitget USDT-M**，14 个缺失：EOS、FLOW、FTT、HNT、HTX、HT、KCS、LEO、MKR、MNT、OKB、OSMO、WAVES、YFI。
- Bitget 历史 funding 主端点是 `/api/v2/mix/market/history-fund-rate`，`pageNo` 有效，覆盖最近约 90 天；v3 端点忽略 `pageNo`，每次只返回最近 20 条。
- BTC/NEAR/SOL 的 Bitget vs Binance funding 重叠验证均**未通过**设计稿 §5.2.1 的预注册门槛：符号一致率 0.694–0.853，Pearson 0.250–0.505；中位误差 0.050–0.378 bps、95 分位 0.947–1.421 bps。
- Binance funding 只能作为 **proxy/uncertain 压力带**，不能称为 Bitget 精确历史；在找到更好的 Bitget 历史 funding 来源前，依赖精确 funding 的 2022–2026 衍生品回测不能作为上线依据。
- Bitget 历史 mark K 线 API 可用，但单次 `limit<=100`、窗口<=90 天，且返回 `endTime` 之前最近 100 条；下载器必须从 `endTime` 向前分页。BTC/NEAR/SOL 的抽样 mark 覆盖为 6/6 窗口完整，但全量 88 合约 × 3 类型下载尚未完成。

### 9.3 当前判定

- **H5 Spot Track 不变，仍为 provisional；DSR/PBO/窄峰门槛不因衍生品轨道放宽。**
- **Derivatives Track 仍为 provisional，Phase 1 数据质量门未全通过。**
- 在 full candle coverage、historical funding 数据源、isolated margin/强平引擎、multiple-testing 和 12 个月 OOS 全部通过前，不启用杠杆、不做空、不接实盘。

### 9.4 2026-10-09 Phase 2：isolated-margin 引擎与 1.0x 校验（**重大设计修正**）

> **口径修正（同日）**：初版 Phase 2 直接对 mark/funding 全量时间轴做回测，结果被两类污染放大：一是 2022 前的预热/零收益；二是数据源在 2026-09-21 之后的最新批次。前者会人为压低 Sharpe/CAGR，后者会把主样本之后的价格路径计入结果。引擎现已支持左闭右开的 `start_time`/`end_time` 评估窗口，所有下表结果均为 **2022-01-01 00:00 至 2026-09-21 23:00 UTC**；旧数字全部废止。

- 已实现独立衍生品引擎 `src/atlas20/derivatives/engine.py`：小时 mark OHLC、T+1 +3h 执行、逐结算点 funding、isolated margin、小时级强平、差分调仓（不再每次全平全开）、手续费/滑点分开记录；缺失 mark 默认 fail closed，诊断模式可显式 `exit_last`/`carry`。传入每币 `funding_intervals_hours` 后，持仓若超过合约 funding 间隔仍没有结算记录会直接报错，不再把缺失 funding 静默当作 0。
- 已实现保证金/强平数学 `src/atlas20/derivatives/margin.py`、信号构造 `src/atlas20/derivatives/signals.py`、Bitget/Binance 数据加载 `src/atlas20/derivatives/data.py`，以及 Phase 2 验证/校准/代理试验脚本。
- 先用 Binance/Gate 1h K 线作为 **mark 代理** 做 1.0x 对 H5 的引擎校验；这不是 Bitget 结果，不能作为上线依据。比较基准必须是 **H5 同成本的 +3h 成交**，不能拿 close-fill 的 21.47x 与 +3h 衍生品路径对比。
- 2022-01-01 至 2026-09-21、20 bps、+3h、代理 mark 的结果：
  - H5 全池现货：19.5253x，Sharpe 1.6231，MDD -36.97%；
  - 同一 H5 选币但仅保留代理中有小时 mark 的资产：15.2974x，Sharpe 1.6258，MDD -26.29%；
  - 30% long buffer + isolated margin 的 1.0x 衍生品：15.4917x，Sharpe 1.6312，MDD -26.20%，**4 次强平**；
  - 50% long buffer（V2）的 1.0x 衍生品：15.3380x，Sharpe 1.6267，MDD -26.20%，**0 次强平**。
- 强平事件仍出现在 2022-11-08 DOGE、2023-08-17 SHIB、2024-03-05 SHIB、2024-04-25 HEDERA 等历史回撤段，说明原设计 `long_margin_ratio = 0.30 + MMR + 0.005` 在 H5 这种 1–2 币集中持仓上**不能通过“1.0x 不得强平”的门槛**；这不是参数小修，而是原规则被 Phase 2 校验否决。
- 30% buffer 的原始 11 个衍生品 trial 因此不能直接进入最终验收；已追加 8 个 margin calibration trials，并把 V2 规则单独记录为 Phase 2 diagnostic。所有结果仍需在 Bitget mark 数据上重跑。

### 9.5 2026-10-09 保证金校准：50% long buffer 是当前最小可行点

预注册的 calibration grid 为 long buffer 0.40/0.50/0.60/0.75 × leverage 1.0x/1.25x，固定 fee_buffer 0.005、MMR 0.01、最大保证金占用 85%、20 bps、+3h、零 funding，使用代理 mark：

| 规则 | leverage | 实际最大 gross | 强平次数 | 终值 | Sharpe | MDD |
|---|---:|---:|---:|---:|---:|---:|
| MB40 | 1.00x | 1.002x | 1 | 15.062x | 1.617 | -26.20% |
| MB50 | 1.00x | 1.002x | **0** | 15.338x | 1.627 | -26.20% |
| MB60 | 1.00x | 1.002x | **0** | 15.338x | 1.627 | -26.20% |
| MB75 | 1.00x | 1.002x | **0** | 15.338x | 1.627 | -26.20% |
| MB40 | 1.25x | 1.281x | 1 | 26.171x | 1.616 | -32.10% |
| MB50 | 1.25x | 1.281x | **0** | 26.782x | 1.626 | -32.10% |
| MB60 | 1.25x | 1.281x | **0** | 26.782x | 1.626 | -32.10% |
| MB75 | 1.25x | 1.124x | **0** | 26.582x | 1.636 | -30.80% |

- 40% buffer 仍各有 1 次强平；50% buffer 是两个 leverage 档位下最小的零强平点。
- 75% buffer 在 1.25x 下因为 85% 最大保证金占用而把实际 gross 压到 1.124x，收益略低、MDD 略好；当前不优先。
- 因此，**Provisional V2 默认改为 long buffer 50%**；short buffer 仍保持 50% 或更高，具体由后续空头试验决定。
- V2 long-only 代理诊断（50% buffer、零 funding、20 bps、+3h）：

  | trial | leverage | 实际最大 gross | 强平 | 终值 | Sharpe | MDD |
  |---|---:|---:|---:|---:|---:|---:|
  | L125-V2 | 1.25x | 1.281x | 0 | 26.782x | 1.626 | -32.10% |
  | L150-V2 | 1.50x | 1.574x | 0 | 44.674x | 1.625 | -37.70% |
  | L200-V2 | 2.00x | 1.758x | 0 | 105.010x | 1.634 | -45.03% |

- L125-V2 的成本压力（代理 mark、零 funding、+3h）与 **H5 同成本 +3h 基准**比较：

  | 成本 | 衍生品终值 | 衍生品 Sharpe | 衍生品 MDD | H5 +3h 终值 | H5 Sharpe | H5 MDD | 终值比 | Sharpe 比 |
  |---:|---:|---:|---:|---:|---:|---:|---:|---:|
  | 6 bps | 31.395x | 1.693 | -29.99% | 23.016x | 1.700 | -35.22% | 1.364 | 0.996 |
  | 8 bps | 30.691x | 1.684 | -30.29% | 22.482x | 1.689 | -35.47% | 1.365 | 0.997 |
  | 11 bps | 29.663x | 1.669 | -30.75% | 21.703x | 1.673 | -35.85% | 1.367 | 0.998 |
  | 20 bps | 26.782x | 1.626 | -32.10% | 19.525x | 1.623 | -36.97% | 1.372 | 1.002 |
  | 50 bps | 19.039x | 1.482 | -36.42% | 13.721x | 1.457 | -40.56% | 1.388 | 1.017 |
  | 100 bps | 10.760x | 1.240 | -43.53% | 7.614x | 1.178 | -46.24% | 1.413 | 1.052 |

- 在代理 mark、零 funding、+3h 的诊断下，L125-V2 全部成本无强平、MDD < 50%、终值 >= 1.36 × H5、Sharpe 与 H5 基本持平或更高；这比旧口径看起来更强，但仍是 **proxy diagnostic**，不能用于上线。
- 这些数字只证明保证金规则修正和窗口修正方向；**Bitget mark、真实 funding、Bitget 合约可用性、完整 multiple-testing、12 个月 OOS 全部未完成**，不能作为上线或最终收益结论。

### 9.6 2026-10-09 空头 overlay 代理诊断：仍被拒，但拒绝理由修正

在 V2 50% long buffer 之上，使用代理 mark 和 **未通过 Phase 1 重叠门槛的 Binance funding proxy** 跑 4 个空头 overlay（20 bps、+3h、已修正窗口）：

| trial | 终值 | Sharpe | MDD | 强平 | 相对 L125-V2 |
|---|---:|---:|---:|---:|---|
| SBTC25 | 26.793x | 1.624 | -32.10% | 0 | 收益基本持平；Sharpe 略低；MDD 不改善 |
| SBTC50 | 28.626x | 1.638 | -32.10% | 0 | 收益略高；Sharpe 略高；MDD 不改善 |
| SWEAK25 | 27.225x | 1.623 | -32.10% | 0 | 收益略高；Sharpe 略低；MDD 不改善 |
| SWEAK50 | 29.778x | 1.629 | -32.94% | 0 | 收益略高；Sharpe 略高；MDD 反而变差 |

- L125-V2 基准：26.782x，Sharpe 1.626，MDD -32.10%，0 次强平。
- 修正窗口后，空头 overlay 并没有“Sharpe 大幅下降”；真正的未通过点是 **MDD 完全没有改善**，SWEAK50 还略差。预注册 kill criterion 要求 MDD 至少改善 5 个百分点且 Sharpe 不低于 long-only 基准，因此 4 个空头仍全部被拒。
- 该结论是代理诊断，且 funding 代理本身未通过 Phase 1 重叠门槛；即使未来 Bitget 精确 funding 改变结果，也必须重新预注册并重新跑完整门槛，不能把本次结论当作最终上线依据。

### 9.7 2026-10-09 multiple-testing 代理诊断（仍需补全正式 scope）

- `reports/derivatives_track_proxy_multiple_testing/` 已加入长期收益矩阵、DSR、White Reality Check 和 PBO/CSCV；输入是当前已跑出的 7 个 20 bps、+3h 代理候选（3 个 long-only leverage + 4 个 short overlay），日期严格为 2022-01-01 至 2026-09-21。
- 结果：Deflated Sharpe（N=11 的预注册 scope 记账，7 个可用候选的波动率）约 0.99997；White Reality Check p≈0.00699；**PBO/CSCV≈0.960**，最常被选中为 SWEAK50（309/924）。
- 这 **不能** 宣布 multiple-testing 通过：design 稿要求候选矩阵覆盖 11 个 trial，目前 stop20 变体仍未实现/未跑，成本档位也不是独立策略候选；7 个高度相关的 long/short 变体给出的 PBO≈0.96 是明确的选参不稳定警告。DSR 的高值不能覆盖 PBO 失败。
- 该报告仍标注为 **proxy diagnostic**；正式 gate 必须在 Bitget mark、真实 funding、完整候选矩阵和 12 个月 OOS 上重跑。固定规格与试验计数不变。

### 9.8 2026-10-09 Bitget 真实 mark 重跑：数字取代 9.4–9.7 的代理结果

- **窗口口径修正**：两个 Bitget runner 的 `--end-date` 现在就是**左闭右开的冻结窗口右端**（默认 2026-09-21 = 样本在 2026-09-21 00:00 UTC 结束）。此前 `end_date + 1 day` 的写法让 funding 结算时间戳把权益路径拖出 mark 数据（1725 天样本 + 用 carry 价格给 2026-09-21 估值）。所有 Bitget mark 结果统一为 **1724 个日收益（2022-01-01 → 2026-09-20）**，与现货主样本右端一致。
- **funding 缺失口径**：`skip`（缺失结算按 0）对多头是乐观的。引擎新增 `carry_last`（沿用上一结算，超出 `funding_carry_max_hours` 或无历史则 fail closed）与 `stress_median`（用同一时刻 funding 池正向费率中位数计多头成本，覆盖 TON 这类持仓期完全没有 funding 历史的资产），且只在资产按其 `fund_interval` 确实该结算时才收费，避免在更快的结算网格上重复收费。
- **数据**：`data/raw/bitget_derivatives/merged_20261009/`，88 个映射合约（MATIC/POL 共用 `POLUSDT`），0 error window；审计 `reports/derivatives_track_data_audit_full/`（88/102 coin 有合约；mark 窗口覆盖 78%，新币晚上市属设计内；最大 gap 2h）。
- **零 funding 上界（真实 mark，20 bps，+3h）**：L125 **44.125x** / Sharpe 1.769 / MDD -40.72%；L150 **80.084x** / 1.768 / -46.88%；L200 **210.175x** / 1.770 / -53.95%；全部 0 次强平，实际最大 gross 1.281x / 1.575x / 1.759x。
- **funding 缺口未闭合**：Bitget 精确 funding 历史只回溯约 90 天，2022 起无公开精确源（`funding_overlap.csv` 0/88）。只能用 Binance funding proxy（覆盖 49/88 资产）并标为压力带。
- **funding 压力带（真实 mark）**，`stress_median` 保守口径 / `skip` 乐观口径：L125 34.477x / 34.874x（proxy）、28.266x / 28.921x（2x adverse）、**24.290x / 25.140x（3x adverse）**；L150 60.015x / 60.843x、47.311x / 48.625x、39.457x / 41.113x；L200 146.567x / 149.251x、107.511x / 111.488x、84.888x / 89.643x。强平全 0。`skip` 的乐观偏差 1.1%–5.3%（杠杆越高、压力越大越多）。限制到 49 资产 funding 池的零 funding 上界为 38.260x / 67.977x / 172.267x。
- **成本压力（L125，真实 mark，`skip`）**：零 funding 下 6/8/11/20/50/100 bps = 52.782x / 51.449x / 49.512x / 44.125x / 30.036x / 15.784x；3x adverse funding 下 = 29.891x / 29.162x / 28.100x / 25.140x / 17.336x / 9.310x。对同成本 +3h 现货 H5（23.016x → 7.614x）的比值在所有档位 ≥1.22。
- **保证金校准在真实 mark 上复跑（取代代理校准）**：40% long buffer 在 1.0x/1.25x 各 1 次强平 → 拒绝；**50% 是最小零强平点**（1.0x 23.111x / 1.25x **44.125x**）；60% 与 50% 相同；75% 受 85% 最大保证金占用约束，实际 gross 降到 1.124x（1.25x 下 43.313x，Sharpe 1.776，MDD -38.98%）。
- **multiple-testing（真实 mark，取代 9.7 作为该口径的判定）**：`reports/derivatives_track_bitget_mark_multiple_testing/`，15 个真实 mark 候选、严格同日期 1724 天、记账 N=22：Deflated Sharpe 0.99974–0.99997（门槛 0.95），White Reality Check p=0.0050（门槛 0.05），**PBO/CSCV=0.229**（门槛 ≤0.50，最常选中 L200-zero 332/924；候选族已换成 stress_median funding 口径）。三项同时通过。
- **不等于 9.7 被推翻**：9.7 的 PBO≈0.960 度量的是“含已被拒绝的空头 overlay 的结构族”，9.8 的 0.229 度量的是“结构已定 long-only、只在杠杆与 funding 假设间选择”的族。**任何重新引入结构变化（空头/止损/新规则）都必须重算 PBO**，不得引用 0.229 覆盖历史 0.960。
- **日历稳健性（真实 mark，`reports/derivatives_track_bitget_mark_robustness/`）**：2022 是亏损年（L125 -19.4%，L200 -30.7%，同期 BTC -65.3%）；剔除 2022 终值上升（44.125x → 54.725x）。**去掉最优年 2023 后 L125-zero 仍有 11.648x**（Sharpe 1.591；3x adverse 口径 7.407x）。全部候选最差一年滚动窗口都从 2022-05-12 开始：L125-zero 0.733x / 3x adverse 0.705x / L200 0.610x。同窗口 BTC 买入持有 1.740x、Sharpe 0.099、MDD -67.38%，L125 在最保守档 24.290x / Sharpe 1.548 / MDD -42.49%，收益/Sharpe/回撤三项同时占优。
- **pre-2022 压力窗口（2020-10-03 → 2022-01-01）：partial**。Bitget mark 该区间只有 32 个合约且有分批上线（14 个完整覆盖），L125/L150/L200 零强平、最大 gross 0.726x/0.869x/1.207x、终值 0.969x/0.953x/0.909x、MDD -20.6%/-24.7%/-32.5%；但 `dropped_target_rows=199`，当年想持有的 LUNA/MANA/SAND/GALA 等在 Bitget 无 mark 被降为现金，因此该门槛记为 partial 而非 pass。
- **逐 legs 强平余量（`reports/derivatives_track_bitget_mark_leg_risk/`）**：isolated margin 下多头强平距离恒为入场价 -51.01%，与杠杆无关；137 笔 legs 的最强不利偏移 -41.14%（XRP 2025-01-16 → 02-06），中位 -7.51%，仅 1 笔超 -40%，距强平约 9.9pp。把 buffer 降到 0.40 后强平距离变 -40.91%，同一条 XRP legs 恰好击穿 → 脚本独立复现出“1 次强平”，与校准结果一致。
- **样本外已启动（`reports/derivatives_track_oos_2026/`）**：冻结规格 `PR2026-10-D-L125-V2` 自 2026-09-22 起按日记录（`scripts/run_derivatives_oos.py`，只重建信号 + 换算目标仓位，无任何样本外调参）；数据 `merged_oos_20261009`（88 合约、2026-09-21 → 2026-10-09）。17 个完整日 2026-09-22 → 2026-10-08：**0.9598x**（-4.02%）、MDD -10.81%，同期现货 H5 +3h/20bps 0.9692x、BTC 约 0.9431x；日收益为现货的 1.20–1.32 倍，符合 1.25x 杠杆；零 funding 仍为上界，未发生强平。远不足 12 个月门槛。
- **funding 盈亏平衡（真实 mark，L125，`stress_median`）**：把不利 funding 放大到 1x/2x/3x/4x/5x/6x/8x 后终值为 34.477x / 28.266x / 24.290x / 20.870x / 17.929x / 15.400x / 11.357x，全程零强平。同成本现货 H5 +3h 为 19.525x/Sharpe 1.623/MDD -36.97%，因此**收益优势的平衡点约在 4.3 倍 funding 压力**（Sharpe 优势平衡点约 1.5 倍，MDD 从一开始就更差）。这些是同一候选的资金费敏感性档，不计为新 trial。
- **市场状态分解（`reports/derivatives_track_bitget_mark_regime/`，收益日使用前一日状态标签）**：bull 806 天 L125-zero 39.734x / Sharpe 2.603，non_bull 918 天 1.111x / Sharpe 0.313 / MDD -24.13%；同期 BTC 在 bull 3.060x、**non_bull 0.573x（-42.7%）/ MDD -62.12%**。收益来自 bull，价值在于熊市防守（几乎走平且回撤远小于 BTC）；三个杠杆档在 non_bull 几乎无差异。
- **资产集中度（`reports/derivatives_track_bitget_mark_leg_risk/asset_pnl.csv`）**：L200 口径下 `zcash` 占已实现盈亏 59.6%、`hyperliquid` 15.4%；去掉 `zcash` 后 L125 由 44.125x 降到 **20.295x**，再去掉 `hyperliquid` 降到 **12.429x**（Sharpe 1.769 → 1.511 → 1.333），MDD 完全不变。这与现货轨 §00.8（前 5 币贡献 90.31%、去掉前 3 只剩 2.07x）是同一事实，**同样触发 AGENTS.md 的“不能依赖单一资产”条款**，是本轨道保持 provisional 的独立理由；上线规划应按“去 ZEC 约 20x / 去 ZEC+HYPE 约 12x”而非 44x 来设预期。
- **风险尺度（L125，真实 mark）**：最大回撤 -40.72%（零 funding）/ -42.49%（3x adverse），最差 7/30/90/365 天为 -18.8%/-22.4%/-38.6%/-26.7%（3x adverse 略差）。按用户计划的 3% 总资金折算，最深一段亏损约 **占总资金 -1.27%**，隔离保证金下的理论上限是 -3%；同期 BTC 买入持有 MDD -67.38%（3% 仓位对应 -2.0%）。
- **funding proxy 水平校准（`reports/derivatives_track_funding_calibration/`）**：用 Bitget 公开 funding 的 90 天重叠窗口（2026-07-11 → 10-10，48 个资产）测代理偏差——**总 funding 之比中位数 1.590、均值 1.631**（单次费率比 1.449；BTC 约 0.97x，山寨币 1.3x–5.6x）。按实测水平（proxy × 1.59）在真实 mark 上重跑：L125 **30.078x**/Sharpe 1.634/MDD -41.66%、L150 50.963x、L200 118.435x，全部 0 强平；相对同成本现货 H5（19.525x/1.623/-36.97%）仍高 54%。结合 4.3x 盈亏平衡，资金费还有约 2.7 倍安全边际。该门槛记为**部分闭合**（90 天水平校准，不能保证 2022–2025 水平不变）。
- **成交价口径已闭合（`reports/derivatives_track_fill_price_comparison*/`）**：87 个合约的 market(last) K 线（2022-01-01 → 2026-09-21 23:00）下载完成后，引擎用 mark 估值/强平/funding、market 成交。9 个（funding × leverage）组合下 market 成交终值比 mark 成交高 **0.14%–0.29%**，Sharpe 略升、MDD 不变或微好，**0 次 downgrade**；零 funding L125 44.125x → 44.197x，3x adverse L125 24.290x → 24.327x。该门槛记为**通过**。
- **轮动机制证据（`reports/phase_momentum_rotation_skill_2022/`）**：t 日信号对 t+1 的 PIT Top20 等权篮子比较，520 个信号日——组合日均 +0.560% vs 篮子 +0.217%，**日均超额 +0.343%**（年化 +125%），但超额中位数 -0.126%、胜率 47.3%、Newey-West t=1.81（5% 不显著）；选中的币落在篮子前 20% 的概率 **33.1%**（随机 20%），2023/2024/2025/2026 超额分别为 +0.09%/+0.55%/+0.34%/+0.87%。
- **逐腿分布（L125，129 条腿）**：盈利腿 45.0%、腿收益中位 +0.2%、p10 -15%/p90 +36.9%、单腿最大 +187%（DOGE 2024-10）；最大单腿占总盈亏 25.5%，前 3/前 5 条腿占 57.0%/74.4%。**即使到单腿粒度也是「多数小赢小输 + 少数巨赢」**，这是动量统计指纹。
- **对「单一资产依赖」条款的处理（负责人 2026-10-09 决定）**：板块轮动、重仓最强币是策略设计本体，不是缺陷；记录为**设计属性 + 机制证据**（选择有正超额且方向一致），保留两点残差风险不做粉饰：① 超额 t=1.81 未达 5% 显著；② 未来若没有右尾行情，表现会是「低胜率 + 小幅亏损」。控制手段只有仓位规模与隔离保证金缓冲，不是分散化（H4 已证伪）。
- **跨所 funding 偏差（`reports/derivatives_track_funding_venue_premia/`，49 个币，Bybit 有完整历史）**：Bybit/Binance 逐年中位数为 2022 0.897 / 2023 1.129 / 2024 1.020 / 2025 0.989 / 2026(至 09-20) **0.673**；同一 91 天窗口 Bitget/Binance **1.590x**、Bybit/Binance **0.761x**（两者相差 2.09 倍）。说明跨所资金费差异真实且双向，不能用「1.59x 恒定」外推；但即便按跨所最大离散度 ≈2x 假设 Bitget 历史溢价，终值仍 28.266x > 现货 19.525x，距 4.3x 盈亏平衡还有 2.15 倍。口径定为：中心 1.59x（30.078x）/ 上界 2x（28.266x）/ 压力 3x（24.290x）/ 平衡 4.3x。另注：2026 年 Bybit 仅 0.67x Binance，说明当前是 funding 偏高阶段，用 90 天校准作长期假设反而偏保守。
- **仍未闭合（本轨道保持 provisional）**：(1) 无 2022 起真实 funding（只有 90 天水平校准 + 跨所上界 2x）；(2) 2020-10..2021-12 压力窗口已用代理 mark 从 32 扩到 64 条序列（dropped 199→0、0 强平、最坏腿 MAE -44.35% vs -51.01% 强平线，余量 6.66pp），但因代理为竞对现货盘、3 条腿落在 Bitget 未上架币、39 币当时不存在，记为 partial-with-bounding；(3) 12 个月真 OOS 不足（17/365 天）。

### 9.9 2026-10-09 衍生品轨上线路线（状态表）

完整表格见 `docs/research/derivatives_track_research_2026-10.md` §13。摘要：

| # | 门槛 | 状态 |
|---|---|---|
| 1 | 收益与 BTC 基准 | 通过（44.125x / 24.290x / 去 ZEC+HYPE 12.429x，BTC 1.740x） |
| 2 | 无强平 | 通过（137 腿最坏 MAE -41.14% vs 强平 -51.01%） |
| 3 | 成本压力 | 通过 |
| 4 | multiple-testing | 通过（结构已定的候选族；新增结构需重算） |
| 5 | 单一资产依赖 | **设计属性**（负责人 2026-10-09 确认：轮动重仓最强币是策略本体；残差=右尾依赖，见 §9.8） |
| 6 | 参数/年度/滚动/状态 | 通过（除 #5） |
| 7 | 真实 funding | 部分闭合（Bitget 实测 1.59x、跨所离散 0.76–1.59x、上界 2x；L125 30.078x；平衡 4.3x） |
| 8 | 成交价口径（market） | **通过**（9 组合差 0.14%–0.29%，0 次 downgrade） |
| 9 | pre-2022 压力窗口 | partial-with-bounding（代理 mark 64 序列、dropped 归零、0 强平、最坏余量 6.66pp） |
| 10 | 12 个月样本外 | 进行中（17/365 天，0.9598x） |
| 11 | 实盘执行前置（普通 API key / 逐仓可得） | **阻塞**（2026-10-10 真钱实测：跟单/精英 API key 不支持逐仓、`set-margin`、持仓模式与账户模式切换；详见 `docs/research/derivatives_track_research_2026-10.md` §12.8.23） |

2026-10-11 信号正确性双重核对通过：① 账本是**事件序列**（只在 sleeve 换仓时新增一行），
10-08 之后无新事件＝继续持有，manifest 显示 mark 最新 2.0h、账本评估日 = 数据可判定最新日
（无跳日）；② `make audit-signal` 用回测同一套函数重建两遍账本（结束日 2026-09-21 vs 2026-10-09），
**重叠 599 个事件日 0 不一致、0 缺失**，只在实盘侧多出 11 个样本外事件 —— 既是"同一信号"的证明，
也是 no-look-ahead 回归。同时把执行器"信号日 >36h 就拒绝"的缺陷改成按**数据管线新鲜度**判定
（事件驱动策略持仓期间信号日天然会变旧）。

2026-10-16 **macOS 与 Ubuntu 两条部署线对齐**：`ops/systemd/` 之前仍是被修复前的管线，若哪天把
Ubuntu 那台拉起来就会退回"一天刷两次、刷到什么都照着交易"的老行为。改动：
`atlas20-data-refresh.timer` 补上 **02:55 UTC 盘前补跑**（02:30 主刷、02:55 盘前、06:30 晚补），
`atlas20-data-refresh.service` 改走 `scripts/refresh_daily_data.py`（加锁 + 已覆盖最后完整日则跳过），
`atlas20-derivatives-execute.service` 改走 `ops/run_derivatives_daily.sh`（同样的窗口闸 + 面板自愈），
用 `ATLAS20_PROJECT_ROOT=/opt/atlas20`、`ATLAS20_CONFIG_DIR=/etc/atlas20` 覆盖默认路径；包装脚本
改写为 POSIX `sh`（Ubuntu 默认没有 zsh）并支持这两个覆盖，macOS 侧行为不变（plist 仍显式调
`/bin/zsh`）。systemd 的 `Persistent=true` 本身就是 launchd `RunAtLoad` 的等价物（开机补跑错过的
timer），补跑同样受 03:05–09:05 UTC 窗口闸约束。回归：`tests/test_systemd_units.py`。

2026-10-16 **执行器在"清仓"信号上崩溃（KeyError: 'near'）**：2026-10-13 11:05 的实盘任务抛
`KeyError: 'near'` 退出（`scripts/execute_live_plan.py` → `build_execution_plan` → `_spec`），
**持仓没被平掉**。根因：合约规格（`specs`）只用当日目标集合去解析（
`relevant_symbols = {asset: ... for asset in targets}`），而冻结账本是事件驱动、全清仓那天的
`targets` 恰好是空集（`load_latest_targets` 过滤掉 `target_weight == 0` 的行），于是持仓腿
拿不到合约规格，`_spec` 抛 `KeyError`。当天 19:00 巡检按设计告警（"今天的调仓还没执行"），
持仓由人工平掉，所以 10-14 台账出现"仓位归零但成交为空"。修复：新增
`spec_symbol_universe(symbols_by_asset, targets)`——合约集合按**整张 symbol map** 解析（外加未映射
目标的 symbol 兜底），执行器、计划器、`audit-live`、巡检四处统一改用；回归测试
`tests/test_live_spec_universe.py` 同时钉住"空目标集合 + 持仓"必须产出 CLOSE 单，以及旧的
target-only 写法仍然会 KeyError。

2026-10-16 **重启打断面板刷新、当日调仓被跳过的故障与修复**：当天 10:30 北京的主刷新在 10:34:58
被系统关机杀死（`last` 记录 shutdown 10:34、`kern.boottime` 10:35:17），死在写
`data/processed/panel_daily.csv` 之前，面板停在 2026-10-14；11:05 的调仓任务用这份旧面板重建账本
（manifest `index_end_date=2026-10-14`），而 Bitget mark 已到 10-16 02:00 UTC
（`signal_end_date=2026-10-15`），执行器"账本评估日 = 数据最新日"的闸门按设计**拒绝下单**
（exit 2，当日无成交；日志无 traceback，是关机信号而非代码错误）。修复三件事：

1. `ops/com.atlas20.daily-refresh.plist` 增加 **10:55 北京 = 02:55 UTC** 盘前补跑（主跑 10:30、晚补
   14:30 保留），保证补跑落在 11:05 调仓之前；
2. 刷新改走 `scripts/refresh_daily_data.py`：面板已覆盖最后完整 UTC 日时**直接跳过**（正常日只跑一次
   下载，比原来省一次），下载+构建全程持 `filelock`（进程被杀由内核释放，重启不留死锁），避免盘前补跑
   与慢主跑并发写 raw；
3. 调仓包装脚本新增 `scripts/live_chain_preflight.py` 两道闸：`--check window` 用
   `atlas20.derivatives.live_chain.within_run_window` 限定"03:05 UTC 起 6 小时窗口内 **且** 当日 run day
   尚未成功"（失败状态仍可重试），`--check panel` 落后则先自愈刷新再进链；同时把
   `ops/com.atlas20.derivatives-execute.plist` 改为 **`RunAtLoad=true`**，使重启后落在窗口内能自动补跑，
   窗口外或当日已成交则静默退出（exit 3 与真错误区分），窗口外漏跑仍由 19:00 巡检告警。

执行器既有的新鲜度闸门**未放宽**，仍是最后兜底。回归测试：`tests/test_derivatives_live_chain.py`、
`tests/test_live_chain_preflight.py`、`tests/test_refresh_daily_data.py`、
`tests/test_launchd_refresh_schedule.py`、`tests/test_launchd_derivatives_schedule.py`。

2026-10-11 负责人决定实盘**改用全仓**（"全仓和杠杆无所谓，只要仓位价值对"）：实盘仓位约束改为
**总名义 ≤ 权益 × 1.25** 一条，逐仓 −51% 逐腿强平线在实盘不再存在（模型口径未变，差值落在 −51% 以外
的尾部）。新增每日台账 `reports/derivatives_track_live/journal.csv`（权益/仓位/盈亏/成交/持仓，同日覆盖）
与只读全链路对账 `make audit-live`（账户恒等式、仓位市值、台账成交 vs 交易所订单历史、目标一致性、
名义上限、PnL 链）——首跑 10 项硬校验全过。

2026-10-11 每日自动调仓上线：`make execute-plan-live` / `ops/systemd/atlas20-derivatives-execute.timer`
（03:05 UTC）会按真实权益下单、回读真实成交与持仓、发一条全真实数据的 Telegram；安全闸含 kill-switch、
36h 信号上限、权益下限、同日幂等。首次真钱自动执行 = 买入 14 NEAR（75.03 USDT，均价 5.3593，费 0.045），
播报里的持仓/占比全部来自交易所回读。详见 research §12.8.23 第 4 节。

2026-10-11 负责人决定**暂不部署 Ubuntu，自动调仓改为本机 macOS launchd 运行**：新增
`ops/com.atlas20.derivatives-execute.plist` + `ops/run_derivatives_daily.sh`（launchd 不读 shell rc，
包装脚本自己 `set -a` 加载 `~/.config/atlas20/{bitget,telegram}.env`，缺文件退出 1），每天
**11:05 北京 = 03:05 UTC**（T+1 成交点 +5 分钟、面板刷新之后）跑
`make derivatives-oos-data derivatives-oos execute-plan-live`；调度换算由
`tests/test_launchd_derivatives_schedule.py` 钉住。加载后已用 `launchctl kickstart` 触发一次真实全链路：
mark 下载 → 账本重建（评估日 2026-10-09、0 不一致）→ 执行器正确以"同日已执行"幂等跳过（当日 key
`…|2026-10-08|2026-10-10`，下一次运行日 2026-10-11 会正常执行）。注意：前一条"36h 信号上限"的表述
已过期，执行器实际以 **mark 树 ≤30h + 账本评估日 = 数据最新日** 作新鲜度闸门。本机同时存在
`com.atlas20.daily-refresh`（10:30/10:55/14:30 北京，面板）与 `com.atlas20.cmc-probe`（08:05–11:50 每 15 分钟，
研究采样）两个旧任务；无 crontab、无常驻 Atlas20 进程。

2026-10-11 新增**盘中只读巡检**（`com.atlas20.live-monitor`，每天 19:00 北京 = 调仓后 8 小时）：
`scripts/monitor_live_track.py` 复用 `audit-live` 的 12 项硬校验，另查仓位偏离（>执行器 5 USDT
调仓阈值或目标 2%）、总名义 >1.25x、执行新鲜度（当天 06:00 UTC 后未执行或 >36h）、权益下限；
**只读、只在下单链之外发告警**（正常时 TG 静默）。目的：把"非调仓时间无法发现实盘问题"的盲区补上——
调仓没跑、跑歪、被手动平仓、名义超限当天即可见。首跑（kickstart 实测）健康、exit 0。

2026-10-11 负责人确认：**退出按信号策略执行，实盘不加止损**。理由与口径：退出唯一来源是模型
目标权重变化（权重归零=平仓、换仓=先减后加，T+1 11:05 执行），回测引擎本身也无止损路径；
cross 全仓下没有逐腿强平线，账户级风险由「总名义 ≤ 1.25× 权益」约束。止损消融**未做**，
仅在回测 DD 被突破（例如样本外实际回撤显著超出历史 −10.8% 口径）时才重新讨论，并须走完整
参数邻域/多次检验流程后冻结，不在实盘中临时加规则。

2026-10-10 首次真钱全链路实测（100 USDT）：读账户 → 计划器按真实权益出单 → 下单成交 → 回读持仓 → 平仓，全部跑通（一个来回成本 0.0866 USDT ≈ 5.81 bps/边）；但**逐仓在跟单 key 下不可得**（`25200 fixedMargin not support`、`set-margin` `40731`），执行层因此新增 `close_position()`（按 `holdMode` 自动选 hedge/单边写法）与 key 前置自检，见 runbook §1.1。**换普通 API key 复测逐仓之前，实盘不得开启。**

最小上线动作：成交价敏感性（#8）已通过，不再阻塞；剩余动作 = 每日累积样本外（#10）+ 预 2022 覆盖率收口（#9），随后按 3% 总资金 / 1.25x / 50% buffer 隔离保证金小规模试运行，继续逐日记录样本外。**每日播报已上线**（`scripts/send_derivatives_signal.py`，systemd timer，含「执行时点已过请勿追单」保护）；实盘执行、监控与 kill criteria 见 `docs/operations/derivatives_live_runbook.md`。

---

## 00.21 2026-11-10 执行实时化与反手空研究

### 00.21.1 步骤一：把执行从 +3h 提前到 +1h（已实现，不改策略）

负责人要求“收益优先，回撤只要不要明显变差”。在不改变 H5 选币、权重、1.25x gross 和 T+1 信号规则的前提下，执行链改为：

- 主面板刷新：08:30 / 08:50 北京 = **00:30 / 00:50 UTC**，旧的 02:30/02:55/06:30 UTC 全部保留为回退；
- 主执行：09:05 北京 = **01:05 UTC**，旧的 03:05/03:35/04:35/06:35 UTC 全部保留为重试；
- 交易窗口：01:05–07:05 UTC；
- 下单前新增 Bitget 最新价/mark/best-bid/best-ask/顶档数量快照；缺失或超过 120 秒的必需报价 fail closed，点差、last/mark 偏离和“订单大于可见顶档”进入执行报告；
- 面板现在不仅要求日期等于最后完整 UTC 日，还必须通过 `data.completeness.assess_last_day` 的成交量/市值覆盖检查；不通过时包装脚本强制重建并**再次检查**，仍不完整则拒绝进入下单链。

回测操作口径：`reports/phase_momentum_execution_lag_2022/fill_timing.csv` 的 +1h vs +3h（20bps，较差缺 K 线口径）为 21.22x vs 19.56x，终值约 +8.5%；代价是 MDD 从 -45.67% 到 -46.59%，约变差 0.9 个百分点，符合“不要变差特别多”的约束。该数字是 H5/B 的现货执行替代口径，不证明新的衍生品 OOS 收益。

CMC 发布探针（10 个最大候选，非全 102 资产）从 2026-10-08 到 2026-11-09 共 34 个目标日；最近 32 个目标日在 00:20 UTC 均为 10/10 覆盖。由于样本只有 10 个资产，00:30 只是候选刷新时点，生产面板完整性检查才是每次交易的权威闸门。部署后本机 `launchd` 日历已同步到新时点；旧时间表仍作为回退。

### 00.21.2 步骤二：反手空首轮研究（不接实盘）

新预注册文件：`docs/superpowers/specs/2026-11-10-reversal-short-research-design.md`。四条固定试验（不扫参数、最大空头 0.25x，使用 BTC 200D+30D 熊市确认和 3 结算点 funding 过滤）：

| trial | 模式 | 空头 | 20bps 终值 | Sharpe | MDD | 结论 |
|---|---|---|---:|---:|---:|---|
| `PR2026-10-D-L125` | 多头基线 | 无 | 34.8735x | 1.6935 | -40.65% | 基线 |
| `PR2026-11-RS-R-BTC25` | replace | BTC | 34.3995x | 1.6887 | -40.65% | 收益低于基线，拒绝 |
| `PR2026-11-RS-R-WEAK25` | replace | 最弱 Top20 | 33.9680x | 1.6716 | -40.65% | 收益低于基线，拒绝 |
| `PR2026-11-RS-F-BTC25` | flat-only | BTC | 36.0045x | 1.7025 | -40.65% | 小幅度改善，provisional |
| `PR2026-11-RS-F-WEAK25` | flat-only | 最弱 Top20 | 37.4394x | 1.7079 | -40.65% | 小幅度改善，但 3x adverse funding 强平，拒绝 |

关键淘汰证据：

- `replace` 模式（最接近“平仓后反手”）反而低于基线，说明把 H5 多头整体换空并不创造足够收益；
- `flat-only` 在 20bps 相对基线约 +7.4%，50bps 相对基线约 +6.8%，但全样本只有 4 次空头开仓，收益集中在 2022 年熊市；
- 四条新试验 + 基线的 PBO = **0.9307**，远高于 0.5；DSR 虽然高，但不能抵消 PBO 所揭示的选择不稳定性；
- 365 天滚动最差：基线 0.7325x，F-WEAK25 0.6854x，空头版本最坏一年反而更差；
- 100bps 压力下基线和空头版本都约 -50.02%，空头版本没有解除项目的 50% kill line；
- 修正 funding 压力实现后，3x adverse 下 F-BTC25 为 38.89x / MDD -40.72% / 0 强平，F-WEAK25 为 37.85x / MDD -40.72% / **1 次强平**；F-WEAK25 因强平被拒绝，F-BTC25 仍只是 provisional；
- Binance funding proxy 的 Phase 1 重合门槛失败，且本次使用 `funding_missing_policy=skip`，不能称为 Bitget 精确 funding 回测。

此外，首轮复现发现 runner 原先没有显式把 `btc_asset` 指向实际 funding 列名 `bitcoin`；在 lower-case coin-id funding matrix 上，旧 `BTC` 默认会让空头 funding 闸门静默为 false。新 runner 显式传 `btc_asset="bitcoin"`，并新增 case-insensitive funding 列匹配测试；旧的空头报告不能直接当作“已经激活过空头”的证据。

判定：**“平仓即反手”拒绝；F-BTC25 的 `flat-only` 仅保留为 provisional research candidate，F-WEAK25 因 3x adverse funding 强平被拒绝；不修改当前多头实盘，不接空头执行。** 下一步只能补 Bitget 精确 funding、累积至少 30–60 天真实 OOS，并独立复测；不能通过提高空头权重、改 funding 阈值或只报 2022 年结果来救活。

复现与完整输出：`reports/derivatives_track_reversal_short/report.md`、`reports/derivatives_track_reversal_short/multiple_testing/`、`reports/derivatives_track_reversal_short/robustness/`。

### 00.21.3 2026-11-10 实现修正与第二轮快速 BTC 空头

首轮报告发现了两个会改变结论的实现问题：空头只在 H5 稀疏调仓日评估，且 runner 把 funding
列交集错误地当成整个长账本的可交易条件。修正后同规则重跑（`reports/derivatives_track_reversal_short_schedule_fix/`）：

| trial | 修正后终值 | Sharpe | MDD |
|---|---:|---:|---:|
| L125 基线 | **40.2200x** | **1.7330** | -40.6506% |
| RS-R-BTC25 | 34.8199x | 1.6706 | -40.6506% |
| RS-R-WEAK25 | 36.4769x | 1.6732 | -41.8808% |
| RS-F-BTC25 | 36.1592x | 1.6812 | -40.6506% |
| RS-F-WEAK25 | 39.6348x | 1.7030 | -40.6506% |

因此首轮四条空头全部低于修正基线，旧报告的 provisional 结论撤销。

第二轮按 `docs/superpowers/specs/2026-11-10-reversal-short-round2-design.md` 预注册了两个
快速 BTC 趋势空头（50D SMA + 28D return，每日评估，0.25x）：additive 和 flat-only。
20bps 下 additive 为 42.1308x / 1.7489 / -40.3874%，暂时高于基线，但：

- 50bps 为 26.1010x，低于基线 27.3725x；
- 移除 2022 后为 47.0582x，低于基线 50.0330x；
- PBO/CSCV = **0.8355**；
- 61 次空头开仓中仅 19 次正贡献，约 85% 相对收益来自 2022；
- 365 天滚动最差 0.7271x，低于基线 0.7325x；
- 100bps MDD -51.13%，越过 50% kill line。

判定：**第二轮两个候选均拒绝，不再扫描相邻 BTC 趋势窗口。** 方向性 BTC 空头只有在
20bps 口径下出现事件型增益，不能通过成本、年份集中度和多重检验。当前实盘仍是 H5 多头
账本；空头不接实盘。完整报告见 `reports/derivatives_track_reversal_short_round2/report.md`。

### 00.21.4 2026-11-10 双边轮动 R3-R6：单币失败，bottom-quintile + stop 仅 provisional

R3 单币横截面最弱空头（`PR2026-11-RS3-X-WEAK14`）在 20bps 为 38.5909x / Sharpe 1.7106 /
MDD -47.0461%，并在 2023-07-13 被 XRP 逼空触发 1 次强平，拒绝。

R4 改为 Top20 的 bottom-quintile 4 币等权空头（总 0.25x，14D/7D，每周再平衡）。20bps
表面为 53.0245x / 1.8980 / -41.5294%，但有 **3 次强平**（XRP 两次、TRON 一次），拒绝。

R5 只把 short buffer 从 50% 提到 75%。20bps 为 51.2754x / 1.8817 / -41.5294%，仍发生
**2 次强平**；按预注册停止，不再扫 buffer。

R6 保持 R4 信号，加入原设计已预注册的 **20% adverse short stop**（逐小时 mark，单腿止损）。

| 口径 | L125 基线 | R6 STOP20 |
|---|---:|---:|
| 20bps | 40.2200x / 1.7330 / -40.65% / 0 强平 | **51.8010x / 1.8918 / -42.59% / 0 强平** |
| 50bps | 27.3725x / 1.5790 / -44.20% | **28.3854x / 1.6409 / -47.18%** |
| 100bps | 14.3794x / 1.3204 / -50.02% | 10.3786x / 1.2196 / **-54.06%** |
| 3x short-adverse | 44.1253x（零 funding 上界） | 49.6029x / 1.8723 / -42.95% / 0 强平 |

R6 的 PBO=0.0281，365 天滚动最差 0.7958x（基线 0.7325x），但移除 2022 后 48.5848x
低于基线 50.0330x；2022 仍决定相对优势。加上 100bps MDD 已超过 50%，按预注册判定为
**provisional research candidate，不是可上线策略**。

结论：bottom-quintile + STOP20 是当前最强的空头研究线，证明了相对价值信号和尾部止损能同时
工作；但成本、2022 依赖、funding proxy 和不足 12 个月 OOS 仍不合格。下一步只能预注册
降低换手/成本的新机制；不能继续扫 stop、buffer、篮子大小或趋势窗口。

完整报告：`reports/derivatives_track_cross_sectional_basket_round6/report.md`。

### 00.21.5 2026-11-10 双边轮动 R7：Bottom-8 持有带被拒

R6 的失败点是 100bps 成本和 2022 依赖。R7 只预注册一个机制：进入 bottom-4 空头后，只要仍在
可投资候选的 bottom-8 就继续持有，用 buy/hold spread 降低换手（外部依据 [S36]）。H5、14D
信号、0.25x 空头、50% margin buffer、20% 单腿 stop 全部不变；没有扫描 6/10 或 stop/buffer。

| 口径 | L125 基线 | R7 HOLD8 + STOP20 |
|---|---:|---:|
| 20bps | 40.2200x / 1.7330 / -40.65% / 0 强平 | **43.2909x / 1.8266 / -42.40% / 0 强平** |
| 50bps | 27.3725x / 1.5790 / -44.20% | 24.6027x / 1.5890 / -46.89% |
| 100bps | 14.3794x / 1.3204 / -50.02% | 9.5638x / 1.1906 / **-53.64%** |
| 3x short-adverse | 44.1253x（零 funding 上界） | 40.6830x / 1.7992 / -42.88% / 0 强平 |

持有带确实把费用总额从 R6 的 3.1904 降到 2.5646，但 50bps 低于基线、100bps MDD 越过 50%，
且空头止损从 50 次升到 73 次。移除 2022 后 R7 为 41.7015x（基线 50.0330x），365 天滚动
最差 0.7048x（基线 0.7325x），两项均失败。L125 + R6 + R7 的 PBO/CSCV=0.2576，Reality Check
p≈0.0040，均通过，但不能抵消成本和年份依赖。

判定：**R7 rejected；bottom-quintile 空头族停止参数搜索。** 不接实盘，不再扫 hold rank、
周期、stop、buffer 或空头权重。下一步若继续实时化，只能预注册一个与空头选币正交、可独立验证的
小时内风险规则，并先固定 kill criteria；不能把“逃顶”直觉直接写进实盘。

完整报告：`reports/derivatives_track_cross_sectional_basket_round7/report.md`。

### 00.22 2026-11-10 小时级逃顶诊断：全部不升级（仅诊断，不新增试验）

负责人要求把“每天 11 点才调仓、逃顶太慢”作为独立方向研究。本节不是预注册试验，也不改变
冻结 H5；目标是先回答一个更基本的问题：**在小时级提前退出，是否真的比 H5 现有的日线风控更好？**

- 数据：`data/raw/binance_1h`，2022-01-01 至 2026-09-21；H5 的 38 个实际持仓资产；
  target-asset-day 中 **84.71%** 有完整 24 小时线，其余 15.29% 用当日收盘收益做几何插值并单独
  报告。生产 +1h H5 锚为 22.8004x / Sharpe 1.7036 / MDD -33.27%；小时模拟基线为
  21.5644x / 1.6687 / -37.45%，与生产日收益相关性 **0.9932**。因此只可比较模拟基线内的相对
  变化，不能把模拟绝对值当作生产替代。
- 执行：H5 目标在 T+1 01:00 UTC 成交；任何小时信号在下一小时收盘执行；成本和换手按生产
  20bps 口径计。
- 预筛选的两族规则：
  1. 把 H5 已有的 **BTC 100D MA + 2 次确认** 从“2 个日收盘”加快为“2 个小时收盘”，分别测试
     对称快速再入和“快速退出、等下一次 H5 目标再入”；
  2. 组合级固定/移动止损，阈值仅作诊断网格 5%/8%/10%，触发后等下一次 H5 目标再入。

| overlay | 20bps 终值 | Sharpe | MDD | 相对基线 |
|---|---:|---:|---:|---|
| 小时模拟基线 | **21.5644x** | **1.6687** | -37.45% | — |
| 小时 BTC 闸门，快速双向 | 16.2994x | 1.5606 | -38.16% | 收益、Sharpe、MDD 全部更差 |
| 小时 BTC 闸门，快速退/慢再入 | 18.4954x | 1.6283 | -39.67% | 全部更差 |
| 固定止损 5% | 16.6936x | 1.5639 | -42.54% | 全部更差 |
| 固定止损 8% | 20.4288x | 1.6412 | -39.51% | 全部更差 |
| 固定止损 10% | 21.5210x | 1.6718 | -36.90% | 收益略低，Sharpe/回撤仅微小改善 |
| 移动止损 5% | 10.4127x | 1.4287 | -42.24% | 全部更差 |
| 移动止损 8% | 21.0815x | 1.6526 | -40.23% | 全部更差 |
| 移动止损 10% | 21.5210x | 1.6718 | -36.90% | 与固定 10% 相同，仍不足以升级 |

结论：

- **没有一个小时级 overlay 同时提高收益、Sharpe 和回撤。** 最快的 BTC 闸门反而因为来回触发
  把收益从 21.56x 降到 16.30x；等待下一次目标再入也只恢复到 18.50x。
- 只有 10% 组合止损把 MDD 改善约 0.55pp、Sharpe 提高约 0.003，但终值下降约 0.2%，且这是
  在 84.71% 小时覆盖率和插值假设下的结果；不满足“收益提升优先、回撤不能明显变差”的方向，
  更不足以进入预注册或实盘。
- 本节**不新增 trial，不改变 H5，不把 stop 接到实盘**。实时化目前唯一已通过执行口径检验的
  改动仍是 §00.21.1 的 00:30/01:05 UTC 提前执行；继续研究必须引入与价格路径正交的新数据源，
  不能继续扫小时确认数、MA 窗口、止损阈值或再入延迟。

复现：

```bash
.venv/bin/python scripts/diagnose_intraday_risk.py \
  --output-dir reports/phase_momentum_intraday_risk_diagnostic
```

明细：`reports/phase_momentum_intraday_risk_diagnostic/{report.md,summary.csv,yearly_returns.csv,hourly_coverage.csv,manifest.json}`。

---

### 00.23 2026-11-10 30 分钟执行时点：全部被拒，停止继续扫成交分钟

负责人要求继续研究“更实时/分批成交是否能提高收益”。本节只改变 H5 的成交时点，不改
point-in-time Top20、目标权重、T+1、long-only、gross<=1 或成本模型。先修数据，再按固定门槛
比较 `00:30 / 01:00 / 01:30 / 02:00` 与 `50% 01:00 + 50% 01:30`。

**一、先修复 30m 数据污染**

旧 `data/raw/binance_30m` 不可用：Binance 月度归档的 `open_time` 在 2022–2024 是毫秒，
2025 起改为微秒；旧解析把两者都当毫秒，随后又对旧 CSV 重复换算，产生 1970 和 58718 年。
本轮没有修补旧文件，而是改用 Binance 官方 kline API，直接按整数 epoch-milliseconds
重建，并在加载时拒绝秒/微秒/1970/重复/乱序数据。结果：

- 32 个资产、**2,383,150 根 30m K 线**，全部毫秒时间戳、升序、无重复。
- 21 个 2022 年即存在的资产各 **83,230 根**，边界为 2022-01-01 00:00 → 2026-09-30 23:30 UTC。
- 仅保留 Binance 自身的 2023-03-24 约 1.5h 维护缺口，以及 TON→GRAM 换名期间约 53.5h 缺口；
  不插值、不静默填价。
- H5 实际目标资产为 **37 个**，其中 31 个有 30m 数据；缺 30m 的是
  `bitget-token, crypto-com-chain, hyperliquid, kaspa, mantle, okb`。再叠加 MONERO/LUNC 退市后、
  TON 换名等未覆盖时段，实际成交权重覆盖率只有 **78.14%**，低于预先写死的 95% 可执行门槛。

**二、同数据口径结果（20bps）**

30m 基线与旧 1h 锚不可直接比较，因为两者覆盖的交易所/资产不同；下表全部相对“同一 30m
数据集里的 01:00 基线”。旧 1h 锚分别为 21.6900x（prior_close）和 21.2173x（day_close）。

| 缺失 K 线口径 | 方案 | 终值 | Sharpe | MDD | 相对 01:00 终值 |
|---|---|---:|---:|---:|---:|
| prior_close | 01:00 基线 | **20.4051x** | **1.3851** | -46.48% | 1.0000 |
| prior_close | 00:30 | 20.1493x | 1.3835 | -47.42% | 0.9875 |
| prior_close | 01:30 | 18.8732x | 1.3575 | -45.80% | 0.9249 |
| prior_close | 02:00 | 19.7897x | 1.3741 | -44.44% | 0.9698 |
| prior_close | 50/50 01:00+01:30 | 19.6392x | 1.3717 | -46.15% | 0.9625 |
| day_close | 01:00 基线 | **25.4570x** | **1.4683** | -47.12% | 1.0000 |
| day_close | 00:30 | 25.1280x | 1.4669 | -48.06% | 0.9871 |
| day_close | 01:30 | 23.5472x | 1.4417 | -46.47% | 0.9250 |
| day_close | 02:00 | 24.6161x | 1.4571 | -45.17% | 0.9670 |
| day_close | 50/50 01:00+01:30 | 24.5021x | 1.4555 | -46.81% | 0.9625 |

- 四个替代方案在 2/20/50/100bps 全部低于同成本基线：提前 30m 为 0.987–0.989；延后 30m
  为 0.9246–0.9251；延后 60m 为 0.9660–0.9701；50/50 分片为 0.9623–0.9625。
- 00:30 的收益与 Sharpe 都略低，MDD 反而变差约 0.94pp；延后 60m 虽然把 MDD 改善约
  2.0pp，但终值低约 3.0%、Sharpe 低约 0.011、365 天滚动最差更差。
- 覆盖到的成交权重上，价格优势也是负的：00:30 **-1.46bps**、01:30 **-7.64bps**、
  02:00 **-4.35bps**、50/50 **-3.82bps**；正价格优势事件占比只有 46.6%–49.4%，接近抛硬币。
- 逐年结果不稳定：例如 02:00 在 2024 年多出约 12pp，却在 2023/2025/2026 分别少约
  18/6/5pp；提前 30m 在 2022/2023 略好、2024/2026 明显更差。不存在可依赖的固定执行分钟。

**三、判定**

预写门槛为：成交权重覆盖 >=95%；20bps 收益和 Sharpe 高于同数据基线；MDD 不比基线差
超过 2pp；移除 2022 后仍不低于基线；365 天滚动最差不变差；50/100bps 不劣于基线。
**8 个“方案 × 缺失口径”没有一组通过全部门槛。** 其中覆盖率先行失败，而且即便只看覆盖到的
78.14% 成交，price edge 也全部为负，因此不是“补几个交易所数据就会翻盘”的正结果。

结论：**rejected。停止继续扫 00:45/00:50/01:15 等相邻成交分钟，也不上 50/50 分片。**
实盘继续 H5 的 01:05 UTC 单次执行。真正可能提升实时性的下一步不再是挪分钟，而是引入与
价格路径正交的新信息（真实盘口/冲击成本、Bitget funding、订单簿深度）或继续积累冻结样本外。

**四、试验记账**

四个不同执行配置已加入 `reports/research_trial_inventory/`，Top20/2022 N 由 6,138 升至
**6,142**，全部试验 N=**14,170**；缺失行情口径和成本档位按同配置敏感性记录，不重复虚增。
刷新后 H5 的 DSR 为 **0.856**（top20_2022_trials）和 **0.817**（all_trials），仍明显低于
0.95；本次负结果没有改变 H5 的 provisional 状态。B 的多重检验报告同步刷新为
top20_2022_trials **0.7227**、all_trials **0.6680**。

复现：

```bash
.venv/bin/python scripts/download_binance_30m.py \
  --members data/processed/metadata.csv \
  --only aptos,avalanche-2,binancecoin,bitcoin,bitcoin-cash,bittensor,cardano,celestia,chainlink,dogecoin,ethereum,ethereum-classic,filecoin,hedera-hashgraph,immutable-x,internet-computer,litecoin,matic-network,monero,near,optimism,pepe,ripple,shiba-inu,solana,stellar,sui,terra-luna,the-open-network,tron,uniswap,zcash \
  --start-month 2022-01 --end-month 2026-09 --force

.venv/bin/python scripts/analyze_intraday_execution_timing.py \
  --costs 2,20,50,100 --analysis-cost-bps 20 \
  --output-dir reports/phase_momentum_execution_timing_30m

.venv/bin/python scripts/build_trial_inventory.py
.venv/bin/python scripts/run_phase_momentum_hypotheses.py --evaluate-only
```

明细：`reports/phase_momentum_execution_timing_30m/` 及
`reports/research_trial_inventory/{summary.json,trial_inventory.csv,trial_sharpes.csv}`。

### 00.24 2026-11-11 无杠杆多空候选 LS1：H5 + H4 现金 sleeve + 板块龙头空头（rejected）

预注册试验 `PR2026-11-LS1-H5-H4-SECTOR20` 使用：

```text
w = 1.0 * w_H5 + 0.2 * w_H4 - 0.2 * w_SECTOR_LEAD_top2__asset_ma50
```

H5、H4、板块龙头、Top20、20% 空头 stop、T+1 +3h 和 2/20/50/100bps 均在查看正式结果前冻结；
本轮没有扫描权重、stop、buffer、funding 阈值或成本档。

**20bps 主口径表面为正：**

| 指标 | H5 1.0 基线 | LS1 候选 |
|---|---:|---:|
| 终值 | 21.3487x | **26.2617x** |
| Sharpe | 1.7361 | **1.8603** |
| MDD | -33.36% | **-27.60%** |
| 强平 | 0 | 0 |
| 空头 stop | 0 | 14 |
| 最大 Broker 净 gross | 0.9568x | 0.9655x |

**但至少四项独立硬失败：**

1. **100bps 成本失败**：候选 9.0509x，低于同成本基线 9.3848x；Sharpe 1.3209 也低于 1.3251。
2. **双边 gross 失败**：按预注册口径 `long gross + short gross`，目标层最大双边 gross 为
   **1.3422x**（2025-10-01），超过 1.00；Broker 净额化后的最大净 gross 只有 0.9708x。
   581/843 个 target event 存在同资产同时多空，净额化不能替代本试验要求的 total gross。
3. **最佳年份依赖**：移除候选最佳年份 2023 后，候选 6.9143x，低于同口径基线 7.0894x。
4. **全项目 DSR 失败**：`N=14,171` 下 DSR **0.9406**，低于 0.95。Top20/2022 scope
   N=6,142 的 DSR 为 0.9579，但不能替代全项目试验数。

补充稳健性：

- 2bps：33.3501x vs 25.6692x，通过；
- 50bps：17.6243x vs 15.6946x，通过；
- 100bps MDD -38.09%，未越过 50% kill line；
- 3x short-adverse funding：27.8544x / 1.8887 / -27.89% / 0 强平，通过风险压力；
- 365 天滚动最差：候选 0.8460x，基线 0.7970x，通过；
- 45 个“至少剩余 365 天”的月初后续路径切片中，候选终值只在 22/45 高于基线；
- PBO=0.1429，Reality Check vs zero p=0.003996、vs BTC p=0.014985，均通过；
- 88 个空头 episode、26 个资产：52 正 / 36 负，episode PnL 对开仓权益合计 +3.854%，
  最差 -3.699%，最好 +2.954%，单 episode 最大 adverse mark loss 3.546%；这是诊断性归因，
  不是可复利组合收益。

**判定：rejected。** 失败不是单一成本问题，而是双边 gross 构造本身越界、2023 依赖、后续起点
不稳定和高成本下优势消失。按预注册约束，不再扫描 H4 权重、空头权重、20% stop、buffer、
funding threshold 或成本档；下一轮只能预注册一个机制不同、先满足 `long + short` hard gross
预算的新候选。

完整报告：`reports/derivatives_track_long_short_cash_sleeve/report.md`。
账本登记哈希：`8aac98afb3be8e3958db09ec7b5f2161b6cb613597f96661611d97c729b3ffbf`。
本试验没有修改 H5 实盘目标、执行器或账本；H5 仍为多头实盘配置，LS1 不接实盘。

### 00.25 2026-11-11 月频板块轮动空头 LS2：正式失败（rejected）

LS1 被拒后，按“旧负收益策略反向”思路预注册了独立候选
`PR2026-11-LS2-H5-MONTHLY-SECTOR`：

```text
w = 1.0 * w_H5 - 1.0 * w_TOP20_SECTOR_top3_monthly_bull__none
```

旧长策略来自 `reports/no_leverage_ablation_v2/`，历史上为 -65.07% 总收益、
Sharpe -0.455、MDD -73.94%、年换手 1.747。LS2 的预注册动机是低换手负收益板块轮动
反向，且先按 `long + short <= 0.95` 缩放多空两侧，再允许 Broker 净额执行。

**20bps 正式结果：**

| 指标 | H5 基线 | LS2 候选 |
|---|---:|---:|
| 终值 | **21.3487x** | 6.1748x |
| Sharpe | **1.7361** | 1.2122 |
| MDD | -33.36% | **-30.13%** |
| 强平 | 0 | 0 |
| 空头开仓 | 0 | 137 |
| 空头 stop | 0 | 47 |
| 最大 scaled target total gross | 0.9500x | 0.9500x |
| **最大观测 Broker gross** | 0.9568x | **1.2318x** |

候选在所有成本档都低于基线：

| 成本 | 基线 | LS2 |
|---:|---:|---:|
| 2bps | 25.6692x | 7.9019x |
| 20bps | 21.3487x | 6.1748x |
| 50bps | 15.6946x | 4.0904x |
| 100bps | 9.3848x | 2.0544x |

其他失败证据：

- 100bps MDD -52.77%，越过 50% kill line；
- 3x short-adverse funding：5.2363x / 1.1183 / -34.61% / 0 强平，但观测 gross 仍 1.2329x；
- 365 天滚动最差：候选 0.7671x，低于基线 0.7970x；
- 移除候选最佳年份 2023 后：候选 2.4753x，低于基线 7.0894x；
- 45 个“至少剩余 365 天”的月初后续路径切片，候选终值和 Sharpe 均为 **0/45** 通过；
- PBO=0.1407，但 CSCV 最常被选中的候选是 **H5 基线**；
- Reality Check vs zero p=0.003996（最优为基线），vs BTC p=0.050949，未达 0.05；
- 全项目 DSR N=14,172：**0.4634**，Top20/2022 scope 0.5233。

关键工程结论：目标层先按 `long + short <= 0.95` 缩放并不能保证实际逐小时 gross 不漂移。
本候选在 1.0x 空头、20% stop 和月频目标下，实际 Broker gross 达到 1.2318x。后续任何多空
候选都必须加入逐小时 gross guard，或在目标层预留足够 drifts buffer；不能只报目标层 gross。

另一个研究结论：把历史负收益策略的日收益直接取反是**危险的上界式诊断**。线性反向在
预注册前看起来可从 H5 的 19.53x 提升到约 37.78x，但正式生产引擎只有 6.1748x。空头止损、
保证金、双边 gross、持仓漂移、funding 和执行时点会完全改写结果。

**判定：rejected。** 按预注册不再扫描空头权重、stop、buffer、月频改双周/周频、板块数 2/4/5、
bull_only 改 always_on 或 gross 定义。H5 实盘不变，LS2 不接执行器。

完整报告：`reports/derivatives_track_monthly_sector_short/report.md`。
账本登记哈希：`e9216eac0210aa7d594c9b14ff4a0dfbfc568d05c0867593e6d9e117995bd790`。

### 00.26 2026-11-11 H5 退出币 21 天空头 LS3：信号有效但风险/稳健性不合格（rejected）

LS1、LS2 失败后，本轮改为只做空 **H5 自己刚刚完全卖出的 Top20 币**。预注册前诊断
（`reports/h5_exit_short_diagnostic_2026_11_11/`）显示：

| H5 exit 后窗口 | 观测 | 相对 Top20 等权平均 | 跑输概率 | iid t |
|---|---:|---:|---:|---:|
| 7D | 117 | -1.10% | 61.5% | -1.30 |
| 14D | 117 | -2.44% | 61.5% | -2.23 |
| **21D** | **117** | **-4.18%** | **66.7%** | **-3.18** |
| 30D | 117 | -4.66% | 63.2% | -2.89 |
| 60D | 117 | -5.46% | 65.0% | -2.61 |

正式候选 `PR2026-11-LS3-H5-EXIT-SHORT21`：

- 只使用 H5 未使用的 gross；
- 退出资产等权；
- 固定 21 个日历日；
- H5 重新买入时提前平空；
- 20% short stop；
- 目标 total gross 0.95，hard observed 1.00；
- 新增逐小时 next-tick gross guard，成交 `reason=gross_guard`。

**20bps 正式结果：**

| 指标 | H5 基线 | LS3 |
|---|---:|---:|
| 终值 | 21.3487x | **45.9190x** |
| Sharpe | 1.7361 | **1.8107** |
| MDD | **-33.36%** | -40.75% |
| 强平 | 0 | 0 |
| 空头开仓 | 0 | 140 |
| 空头 stop | 0 | 19 |
| 最大 target total gross | 0.9500x | 0.9500x |
| **最大 observed gross** | 0.9568x | **1.0820x** |
| gross breach hours | 0 | **145** |
| gross guard reductions | 0 | **502** |

成本压力：

| 成本 | 基线 | LS3 |
|---:|---:|---:|
| 2bps | 25.6692x | 69.3355x |
| 20bps | 21.3487x | 45.9190x |
| 50bps | 15.6946x | 22.9462x |
| 100bps | 9.3848x | 7.1521x |

失败项：

- MDD 比基线差 7.39pp，超过预注册 5pp 容忍线；
- observed gross 1.0820x，145 个 breach hours；
- 100bps 终值低于基线，MDD -57.32% 超过 50%；
- 3x short-adverse funding：39.2913x / 1.7466 / -42.91% / 0 强平，但 gross 仍 1.0825x；
- 365 天滚动最差：LS3 0.5957x，基线 0.7970x；
- 45 个月初收益路径切片：终值 45/45 通过，但 Sharpe 只有 17/45、MDD 5pp 只有 8/45，
  三项同时 7/45；
- PBO/CSCV **0.8225**，失败；
- RC vs zero p=0.000999、vs BTC p=0.008991，通过；
- DSR：Top20/2022 **0.9277**、all_trials N=14,173 **0.9043**，失败；
- 140 个空头 episode、31 个资产；NEAR 单资产贡献 **63.5%**，前 3 资产 **99.0%**，
  最差 episode -17.11%，最好 +49.57%，最大 adverse mark loss 14.76%。

工程结论：新增的 next-tick gross guard 可以降低持续风险，但不能阻止第一次 mark 漂移越界；
目标层 0.95 不等于 observed gross 0.95。LS3 的 45.92x 主要说明 exit-short 信号有统计价值，
不说明当前风险分配可以实盘化。按预注册，不得扫描 7/14/28/30/60D 持有期、stop、buffer、
权重或 gross 阈值；下一轮必须换成不同的风险分配机制。

**判定：rejected。** H5 实盘不变，LS3 不接执行器。

完整报告：`reports/derivatives_track_h5_exit_short/report.md`。
账本登记哈希：`1018daeee77d256c0f347d5eee0093c417833a18e4ddbdc9059d31b9ded7878d`。


### 00.27 2026-11-11 H5 退出币固定风险空头 LS4：收益改善但稳健性仍未闭合（rejected）

LS3 的 gross 和单资产集中度问题促成本轮预注册新机制 `PR2026-11-LS4-H5-EXIT-RISK05`：
H5 完全退出的 Top20 资产继续做 21 天空头，但每腿固定 2.5% NAV，20% stop 对应名义
0.5% NAV 单笔风险；空头只使用 H5 未使用的 gross，target total gross 0.95、hard observed
gross 1.00。该机制在正式运行前登记，不是对 LS3 权重的回扫。

**20bps 正式结果：**

| 指标 | H5 基线 | LS4 |
|---|---:|---:|
| 终值 | 21.3487x | **23.8448x** |
| CAGR | 91.26% | **95.79%** |
| Sharpe | 1.7361 | **1.8091** |
| MDD | **-33.36%** | -34.12% |
| 强平 | 0 | 0 |
| 空头开仓 / stop | 0 / 0 | 140 / 18 |
| 最大 observed gross | 0.9568x | **0.9616x** |
| observed gross breach hours | 0 | **0** |
| gross guard reductions | 0 | **0** |

成本压力：

| 成本 | 基线 | LS4 | 基线 Sharpe | LS4 Sharpe |
|---:|---:|---:|---:|---:|
| 2bps | 25.6692x | **29.0746x** | 1.8277 | **1.9089** |
| 20bps | 21.3487x | **23.8448x** | 1.7361 | **1.8091** |
| 50bps | 15.6946x | **17.1246x** | 1.5826 | **1.6418** |
| 100bps | 9.3848x | **9.8473x** | 1.3251 | **1.3610** |

100bps MDD -43.35%，低于 50% kill line；3x short-adverse funding 为 25.1403x / 1.8347 /
-34.34% / 0 强平。

通过项：

- MDD 只比基线差 0.75pp，在 5pp 容忍线内；
- 四档成本终值和 Sharpe 全部高于同成本基线；
- gross 硬约束和 0 强平全部通过；
- 删除任意最佳年份后全部高于基线；
- 45 个保存收益路径月初切片三项同时通过 45/45；
- 12 个真实引擎月度冷启动中，终值 12/12、Sharpe 12/12、MDD 5pp 12/12 通过；
- 140 个空头 episode 的 NEAR 净贡献 27.13%、前 3 54.08%，集中度门槛通过；
- PBO 0.00649、RC vs zero p=0.003996、RC vs BTC p=0.018981。

失败项：

- 365 天滚动最差：LS4 **0.7838x**，基线 **0.7970x**；
- DSR Top20/2022 N=6,142：**0.942360**，低于 0.95；
- DSR 全项目 N=14,174：**0.920719**，低于 0.95；
- 名义 0.5% NAV 单笔风险没有封住实际 adverse mark loss：最大值为 **0.6491% NAV**
  （`internet-computer`，2024-02-16 至 2024-03-05），必须显式报告 gap/intrabar 和权益变化偏差。

**判定：rejected。** 按预注册不得继续扫描 0.25%/0.75%/1.0% risk budget、15%/25%/30% stop、
7/14/28/30/60D 持有期、权重或 gross 阈值。H5 实盘不变，LS4 不接执行器。

完整报告：`reports/derivatives_track_h5_exit_risk_budget/report.md`。
账本登记哈希：`425dcbbf78acd4fa4399e780a8c87cad9bb5f5afd02783d41075c263bdbab087`。


### 00.28 2026-11-11 LS5：H5 exit + 14D 最弱篮子固定风险空头（rejected）

LS4 的 exit-short 解决了 gross 和单腿风险，但滚动最差与全项目 DSR 失败；R6 的 14D
weak-four 信号 Sharpe 更高但成本、2022 依赖和杠杆不合格。LS5 预注册组合两条 sleeve：

- H5 保持 1.0x；
- sleeve A：H5 完全退出资产，固定 21 天；
- sleeve B：PIT Top20 14D 最弱 4 币，固定 7 日再平衡，沿用 R6 funding filter；
- 每腿 2.5% NAV、20% stop；
- 同资产重叠只保留一条 2.5% 腿；
- 只使用 H5 未使用 gross，target total gross 0.95、hard observed gross 1.00。

**20bps 正式结果：**

| 指标 | H5 基线 | LS5 |
|---|---:|---:|
| 终值 | 21.3487x | **24.1210x** |
| CAGR | 91.26% | **96.27%** |
| Sharpe | 1.7361 | **1.8424** |
| MDD | **-33.36%** | -34.31% |
| 强平 | 0 | 0 |
| short open / stop | 0 / 0 | 721 / 87 |
| 最大 observed gross | 0.9568x | **0.9669x** |
| gross breach hours | 0 | **0** |

成本：

| 成本 | H5 基线 | LS5 | H5 Sharpe | LS5 Sharpe |
|---:|---:|---:|---:|---:|
| 2bps | 25.6692x | **31.1231x** | 1.8277 | **1.9732** |
| 20bps | 21.3487x | **24.1210x** | 1.7361 | **1.8424** |
| 50bps | 15.6946x | **15.7624x** | 1.5826 | **1.6231** |
| 100bps | **9.3848x** | 7.7417x | **1.3251** | 1.2552 |

3x short-adverse funding：23.9464x / 1.8372 / -34.58% / 0 强平 / gross 0.9661x。

通过项：

- 20bps 收益、Sharpe、MDD、gross 与 0 强平；
- 2/20/50bps 收益和 Sharpe 高于基线；
- 100bps MDD -45.20% 未越过 50%；
- 365 天滚动最差 **0.8083x**，高于基线 0.7970x；
- 12 个真实引擎冷启动：终值 11/12、Sharpe 12/12、MDD 5pp 12/12；
- PBO 0.09524、RC vs zero p=0.003996、RC vs BTC p=0.020979；
- Top20/2022 DSR **0.952281**，首次超过 0.95。

失败项：

- 100bps 终值 7.7417x 低于基线 9.3848x，Sharpe 也低；
- 移除 2022 后 24.4989x，低于基线 25.3369x；
- 全项目 DSR N=14,175 为 **0.933398**；
- 713 个空头 episode：exit sleeve +7.921%、overlap +2.464%，但 weak4 sleeve 550 笔为 **-2.662%**；
- 前 3 空头贡献 126.53%，超过 80%；
- 最大 adverse mark loss **0.7088% NAV**，高于名义 0.5%。

**判定：rejected。** LS5 修复滚动最差，但没有解决 100bps 成本、年份依赖、全项目 DSR 和集中度；
weak4 sleeve 在该上下文中没有正增量。按预注册不得扫描 14D、4 币、7 日、funding filter、
stop、单腿权重或组合比例。H5 实盘不变，LS5 不接执行器。

完整报告：`reports/derivatives_track_h5_exit_weak4_risk/report.md`。
账本登记哈希：`113030ad110255ca8c9064f8fb948c3bfb8961e397f21faaebc58aa944a31f96`。


### 00.29 2026-11-11 LS6：H5 退出币 funding 拥挤空头（rejected）

LS5 的 weak4 sleeve 自身为负，说明高换手横截面空头不适合作为固定风险 overlay。LS6 回到 LS4
的 exit sleeve，只增加一个已有先验的入场条件：H5 退出资产在信号日的 7D funding 横截面中
必须位于 PIT Top20 上三分之一；有效资产少于 5 个或 funding 缺失则 fail closed。

冻结构造：H5 1.0x；21 天；每腿 2.5% NAV；20% stop；只用未使用 gross；target total gross 0.95；
hard observed gross 1.00；T+1 +3h。

**20bps：**

| 指标 | H5 基线 | LS6 |
|---|---:|---:|
| 终值 | 21.3487x | **22.9279x** |
| CAGR | 91.26% | **94.17%** |
| Sharpe | 1.7361 | **1.7811** |
| MDD | **-33.36%** | -33.40% |
| 强平 | 0 | 0 |
| short open / stop | 0 / 0 | 52 / 8 |
| 最大 observed gross | 0.9568x | 0.9568x |
| gross breach hours | 0 | 0 |

成本：

| 成本 | 基线 | LS6 | 基线 Sharpe | LS6 Sharpe | LS6 MDD |
|---:|---:|---:|---:|---:|---:|
| 2bps | 25.6692x | **27.7169x** | 1.8277 | **1.8760** | -31.39% |
| 20bps | 21.3487x | **22.9279x** | 1.7361 | **1.7811** | -33.40% |
| 50bps | 15.6946x | **16.7044x** | 1.5826 | **1.6221** | -36.72% |
| 100bps | 9.3848x | **9.8394x** | 1.3251 | **1.3552** | -42.20% |

3x short-adverse funding：24.5246x / 1.8139 / -33.51% / 0 强平。

通过项：

- 四档成本终值和 Sharpe；
- 100bps MDD；
- 所有年度收益高于基线；
- 删除任意最佳年份后高于基线；
- 45/45 月初路径切片三项通过；
- 12/12 真实引擎冷启动终值、Sharpe、MDD 通过；
- 52 个空头 episode 中 33 正、19 负，合计 +7.025% 开仓权益；
- NEAR 单资产贡献 38.74%、前 3 71.15%，集中度通过；
- PBO 0.004329、RC vs zero p=0.003996、RC vs BTC p=0.015984。

失败项：

- 365 天滚动最差 **0.7923x**，低于基线 0.7970x；
- Top20/2022 DSR **0.932636**；
- 全项目 DSR **0.908511**；
- 最大 adverse mark loss **0.5971% NAV**，高于名义 0.5%，需要披露 gap/intrabar 偏差。

**判定：rejected。** LS6 是目前质量最高、风险最接近可用的空头机制，但 Sharpe 不足且滚动最差
仍低于基线。按预注册不得扫描 funding lookback、rank、min_assets、持有期、stop、单腿或 gross。
H5 实盘不变，LS6 不接执行器。

完整报告：`reports/derivatives_track_h5_funding_exit_short/report.md`。
账本登记哈希：`1bcd620f657249f4f272142a272972c953cbb624b51fc0e73bb430d04f453594`。

### 00.30 2026-11-11 LS8：低多头 gross 才做 funding 退出空头（rejected）

LS6 的滚动最差失败后，预注册了 `PR2026-11-LS8-H5-LOWLONG-FUNDING-EXIT`：只有退出后的 H5
目标 long gross ≤ 0.50 时才允许开 2.5% NAV/腿的 funding 拥挤退出空头。

> **数据修复**：首轮 LS8 把 H5 gross 的 naive datetime 与 UTC schedule 日期直接比较，导致入场检查
> 永远返回 false，错误报告“0 激活”。把 `_long_gross_series` 统一归一化到 UTC 并加入回归测试后，
> LS8 实际产生 37 个空头。旧的“未激活”结论作废。

修复后 20bps：

- H5 基线：21.3487x / Sharpe 1.7361 / MDD -33.36%；
- LS8：**22.8336x / Sharpe 1.7744 / MDD -33.52%**；
- 37 个空头、5 个 stop、0 强平；
- max requested short gross 0.10、max observed gross 0.9568x；
- 2/20/50/100bps 终值和 Sharpe 全部高于基线，100bps MDD -42.15%；
- 3x short-adverse：24.4605x / 1.8078 / -33.60%、0 强平；
- 所有年度、最佳年份移除、45/45 路径切片、12/12 真实引擎冷启动、集中度、PBO 和 RC 通过；
- **365 天滚动最差 0.7909x < 基线 0.7970x，失败**；
- Top20/2022 DSR 0.9302、全项目 DSR 0.9055，失败。

**判定：rejected。** 不扫描 0.30/0.40/0.50/0.60/0.70 等硬阈值。报告：
`reports/derivatives_track_h5_lowlong_funding_exit/report.md`。
登记哈希：`148c31d2dcf2cfeddf0a64ffdfed0f3bf82de5d77bf0e733a2a44bcb44555134`。

### 00.31 2026-11-11 LS9：连续未使用风险预算 + funding 退出空头（rejected）

LS9 用连续预算替换 LS8 的硬开关：

`per-leg weight = 5% × max(0, 1 - post-exit H5 target long gross)`。

权重在空头开仓时确定一次，持有期内不随 H5 变化；仍只使用未使用 gross，沿用 LS6 的 7D funding
上三分之一、PIT Top20、21 日持有、H5 重新买入提前关闭和 20% adverse stop。

初版 LS9 受同一个 naive/UTC datetime bug 影响，所有空头误用 5% 满额权重，24.7348x 结果作废。
修复后权重出现 26 种取值，连续预算真实生效。

修复后 20bps：

| 指标 | H5 基线 | LS9 |
|---|---:|---:|
| 终值 | 21.3487x | **23.8832x** |
| Sharpe | 1.7361 | **1.7984** |
| MDD | -33.36% | -33.54% |
| 强平 | 0 | 0 |
| short open / stop | 0 / 0 | 49 / 8 |
| max requested short gross | 0 | 0.1750x |
| max observed gross | 0.9568x | 0.9568x |

成本：

| 成本 | 基线 | LS9 | 基线 Sharpe | LS9 Sharpe | LS9 MDD |
|---:|---:|---:|---:|---:|---:|
| 2bps | 25.6692x | **28.9016x** | 1.8277 | **1.8936** | -31.56% |
| 20bps | 21.3487x | **23.8832x** | 1.7361 | **1.7984** | -33.54% |
| 50bps | 15.6946x | **17.3705x** | 1.5826 | **1.6389** | -36.80% |
| 100bps | 9.3848x | **10.2023x** | 1.3251 | **1.3711** | -42.18% |

3x short-adverse funding：25.4862x / Sharpe 1.8299 / MDD -33.62% / 0 强平。

通过项：

- 四档成本终值和 Sharpe；
- 100bps MDD、funding、gross、0 强平；
- 所有年度收益和删除任意最佳年份后高于基线；
- 45/45 月初路径切片；
- 12/12 真实引擎冷启动；
- 49 个空头 episode 中 31 正、18 负，合计 +11.3364% 开仓权益；
- NEAR 单资产贡献 39.17%、前 3 65.22%，集中度通过；
- PBO 0.004329、RC vs zero p=0.003996、RC vs BTC p=0.014985；
- 最大 adverse mark loss 0.8762% NAV，低于 5% 权重 × 20% stop 的名义 1.0% NAV。

失败项：

- **365 天滚动最差 0.7865x < H5 基线 0.7970x**；
- Top20/2022 DSR **0.938229**；
- 全项目 DSR **0.915567**。

**判定：rejected。** 连续风险预算提高了收益和 Sharpe，但没有修复最差路径。按预注册不得扫描
base weight、指数、H5 gross 阈值或任何 funding/holding/stop/gross 参数。H5 实盘不变，LS9 不接执行器。

报告：`reports/derivatives_track_h5_riskbudget_funding_exit/report.md`。
登记哈希：`b37a27c5a6ba2742cb871b0290596f00aa745bdd751d5da96145821351269ceb`。

### 00.32 2026-11-11 LS10：14D 相对 BTC 动量确认 + funding 退出空头（rejected）

LS10 在 LS9 上只增加一个机制条件：信号日资产 14D 回报必须低于 BTC 的 14D 回报；funding、21D
持有、5%×未使用 gross 的定权、20% stop 和 gross 上限全部沿用 LS9。

20bps：**22.1461x / Sharpe 1.7567 / MDD -33.54% / 0 强平**，15 个空头、4 个 stop，max observed
gross 0.9568x。四档成本和 3x short-adverse 均通过；所有年度和最佳年份移除也高于基线。

失败项：

- 365 天滚动最差 **0.7946x**，仍低于 H5 的 0.7970x；
- 单资产空头贡献 **67.62%**（NEAR），前 3 **104.60%**，集中度硬失败；
- Top20/2022 DSR **0.9237**、全项目 DSR **0.8974**；
- 44/45 路径切片通过，但不再继续 12 个真实引擎冷启动，因为已有多个硬失败。

**判定：rejected。** 相对动量过滤把 LS9 的最差窗口从 0.7865x 改善到 0.7946x，但砍掉了正贡献并
把收益集中到单一资产。按预注册不得扫描 7D/14D/30D/60D lookback、阈值、分位数或其他空头参数。

报告：`reports/derivatives_track_h5_relmom_riskbudget_funding_exit/report.md`。
登记哈希：`d9260b80a8077e5b6483c968ea91906ce94b94dbdeecd67dc8e5d290711f005c`。


### 00.33 2026-11-11 LS11：BTC 200D 熊市闸门 + 最弱四币空头（rejected）

LS11 在 R6 的 14D 最弱四币周频空头上只增加一个宏观闸门：信号日 BTC close < 200D SMA 才允许
新一期空头，否则空头 sleeve 保持现金。H5 多头、14D、bottom-4、7D、20% stop、0.25x 总空头和
50% short buffer 全部冻结；没有扫描 MA 窗口、篮子大小、lookback、再平衡、stop 或权重。

20bps：**49.7952x / Sharpe 1.8069 / MDD -40.6506% / 0 强平**；L125 基线为
40.2200x / 1.7330 / -40.6506%。278 个空头 episode、27 个 stop，max observed gross 1.3872x。
2bps 66.9505x、50bps 30.3724x，均高于同成本基线；3x short-adverse 为
50.7173x / 1.8130 / -40.72% / 0 强平。

通过项：

- 2/20/50bps 终值和 Sharpe 高于同成本 L125；
- 20bps MDD 与 L125 完全相同；
- 3x funding 压力 0 强平且 MDD <=50%；
- 365 天滚动最差从 L125 的 0.7325x 改善到 **0.7735x**；
- 单资产最大空头贡献 32.20%，低于 50%。

失败项：

- **100bps MDD -50.0131%，超过 50% kill line**；同期 L125 为 -50.0229%，说明该成本档
  本身已贴近并越过项目尾部边界；
- **删除 2022 后 46.6087x，低于 L125 的 50.0330x**；
- 45 个已保存收益路径月初切片中，终值/Sharpe/MDD 三项全部通过仅 **22/45**；
- 前 3 空头贡献 **90.57%**（Ethereum 32.20%、Sui 30.55%、Bitcoin Cash 27.81%），超过 80% 上限。

已有四个硬失败，因此不继续 12 个真实引擎冷启动，也不把 PBO/RC/DSR 阶段用来救活候选。

**判定：rejected。** 200D 闸门改善了 2022 和滚动最差，但把增量收益集中到熊市年份和少数资产，
没有解决 100bps 尾部、删除 2022 和多数路径起点的问题。按预注册不得扫描 MA/bottom/lookback/
rebalance/stop/buffer/weight 参数。当前实盘 `PR2026-10-D-L125-V2` 不变，LS11 不接执行器。

报告：`reports/derivatives_track_h5_weak4_bear200_stop20/report.md`。
登记哈希：`8980ba19c96250fcfb2c896ef4cdc690cefc71fda53606f1e635a750ab06a1f8`。


### 00.34 2026-11-11 LS12：BTC 200D 双空头 regime router（rejected）

LS12 将两条已冻结的空头机制做成互斥路由：BTC close < 200D SMA 时使用 LS11 的周频最弱四币
basket；BTC 在 200D 上方时使用 LS6 的 funding 拥挤 H5 退出空头。两 sleeve 共享 20% stop、
T+1 +3h 和 <=0.25x 总空头，不按任意权重叠加。实现修复了 naive/UTC regime 对齐和不完整
mark 历史两个运行前问题；错误首轮已隔离。

20bps：**55.7859x / Sharpe 1.8520 / MDD -40.6440% / 0 强平**；L125 为
40.2200x / 1.7330 / -40.6506%。335 个 short open、29 个 stop，max requested/observed gross
0.25x/1.3308x，0 gross breach hour。2bps 75.6087x、50bps 33.5732x，均高于同成本基线；
3x short-adverse 为 56.1088x / 1.8531 / -40.76% / 0 强平。

通过项：

- 20bps/50bps 收益与 Sharpe，20bps MDD 基本不变；
- funding、gross、0 强平；
- 365 天滚动最差从 L125 0.7325x 改善到 **0.7731x**；
- 单资产空头贡献 23.35%、前 3 61.92%，集中度通过。

失败项：

- **100bps 终值 14.3604x < L125 14.3794x**；
- **100bps Sharpe 1.3129 < L125 1.3204**；
- **100bps MDD -50.1067%，超过 50% kill line**；
- 删除 2022 后 49.2413x，低于 L125 50.0330x；
- 45 个月初路径切片仅 **44/45** 三项通过，2023-01 起点终值和 Sharpe 略低于基线。

**判定：rejected。** Regime routing 证明 LS6/LS11 的 alpha 可以互补，但仍未修复 100bps 尾部、
2022 依赖和 2023 起点路径。按预注册不扫描 sleeve 权重、MA、bottom、lookback、rebalance、
stop、buffer 或总空头。当前实盘 `PR2026-10-D-L125-V2` 不变，LS12 不接执行器。

报告：`reports/derivatives_track_h5_regime_short_router/report.md`。
登记哈希：`c252b705c99eba3b2854051d49c20dd980597abc40b242033c6afb273785b943`。


### 00.35 2026-11-11 LS13：H5 相对 BTC 周频半仓（rejected）

LS13 在 LS12 上增加一个独立风险层：当未减仓 H5 影子策略的 14D 收益低于 BTC 14D 收益时，下一周
把 H5 多头目标从 1.25x 减到 0.625x；空头 router 不变。信号每 7 个自然日采样，T+1 +3h，
不读取未来目标。

20bps：**33.7083x / Sharpe 1.9633 / MDD -28.3702% / 0 强平**；L125 为
40.2200x / 1.7330 / -40.6506%。798/1724 天处于 risk-off，78 次切换；335 个 short open、29 个
stop，max observed gross 1.2669x。

风险指标明显改善，但**第一门槛 20bps 终值严格高于 L125 失败**：33.7083x < 40.2200x。按预注册
停止后续 2/50/100bps、funding stress、路径切片、引擎冷启动和 multiple-testing，不扫描 14D/
21D/30D、日/周/月频、50%/60%/70%/80% 减仓比例。

**判定：rejected。** LS13 是一个有效的低风险变体，但把收益压得过低，不是当前“收益优先、
回撤不能明显变差”的改进。实盘 `PR2026-10-D-L125-V2` 不变，LS13 不接执行器。

报告：`reports/derivatives_track_h5_relative_half_risk/report.md`。
登记哈希：`4a3445fa44d6c9eb1b1333e1f99e59bff167648300ea1ea42c785706e7d6fa85`。


### 00.36 2026-11-11 LS14：H5 弱于 BTC 时轮入 25% BTC（rejected）

LS14 不再把 H5 弱于 BTC 的仓位转现金，而是把 25% 的 long risk budget 轮入 BTC：risk-off 时
H5 缩到 0.9375x、BTC 防御 sleeve 为 0.3125x，总多头 gross 仍约 1.25x；LS12 双空头 router 不变。

20bps：**43.5326x / Sharpe 1.8786 / MDD -36.49% / 0 强平**；L125 为
40.2200x / 1.7330 / -40.65%。2bps 57.6393x / 1.9957 / -33.19% 也高于基线。798 个 risk-off 日、
78 次切换、336 个 short open / 29 个 stop，max observed gross 1.3269x。

失败项：

- **50bps 终值 26.3206x < L125 27.3725x**；
- **100bps 终值 11.0949x < 14.3794x，Sharpe 1.2861 < 1.3204**（100bps MDD -49.22% 已低于 50%）；
- **删除 2022 后 37.6007x < L125 50.0330x**；
- **45 个月初路径切片仅 13/45 三项同时通过**，2023-2024 多数起点终值低于基线；
- 365 天滚动最差 0.8290x 虽然优于基线，但不能抵消上述失败。

**判定：rejected。** BTC 轮入能在主成本降低回撤，但中高成本和多数路径起点下收益不够稳健。
按预注册不扫描轮入比例、防御资产、lookback 或频率。当前实盘 `PR2026-10-D-L125-V2` 不变，
LS14 不接执行器。

报告：`reports/derivatives_track_h5_btc_rotation/report.md`。
登记哈希：`91f43be5ec6b53c70348dfb8c5ade17aee29123a9618f4a53d1e44f3fbdad9e9`。


### 00.37 2026-11-11 LS15：牛市弱 H5 的 10% 现金缓冲（rejected）

LS15 把 LS13/LS14 的风险状态收窄到“BTC 在 200D 上方且 H5 影子 14D 弱于 BTC”，并且只把
整个 LS12 目标账本缩小到 90%，不改变 H5 名单、空头 router 或 stop。

20bps：**48.3225x / Sharpe 1.8431 / MDD -38.11% / 0 强平**；L125 为
40.2200x / 1.7330 / -40.65%。2bps 63.8718x / 1.9554 / -35.87%，50bps 29.7306x / 1.6438 /
-42.79% 均优于同成本基线；100bps MDD 也降到 -49.85%。475 个 insurance 日、52 次切换、328 个
short open / 34 个 stop，max observed gross 1.2669x。

失败项：

- **100bps 终值 13.0924x < L125 14.3794x**；
- **100bps Sharpe 1.3067 < L125 1.3204**；
- **删除 2022 后 42.6535x < L125 50.0330x**；
- **45 个月初路径切片仅 18/45 三项同时通过**，2024 年收益从 +119.25% 降到 +82.76%。

365 天滚动最差 0.8131x 优于基线 0.7325x，但不能抵消上述失败。

**判定：rejected。** 这是目前最接近“收益和回撤同时改善”的风险层，2/20/50bps 和 100bps MDD
都通过，但极端成本下的收益和 2023-2024 路径仍不够稳健。按预注册不扫描现金缓冲比例、阈值、
lookback 或频率。当前实盘 `PR2026-10-D-L125-V2` 不变，LS15 不接执行器。

报告：`reports/derivatives_track_h5_bull_weak_cash/report.md`。
登记哈希：`569d43533b138d04b70bc8792a738a8b40c97b68e0ff0c984cc44ad8eee13e3f`。

### 00.38 2026-11-12 LS16：LS12 + 5% NAV 单腿 no-trade region（rejected）

LS12 在 20bps 为 55.7859x，但 100bps 略输 L125。只读换手审计显示，672 个目标事件产生 167.9132x
目标 L1 变化，其中同方向增减仓 77.4587x；LS12 的 20bps 累计费用为 2.7745x 初始权益单位。LS16
对已有同方向仓位使用冻结 H5 同源的 5% NAV 容差：距离不超过 5% 不交易，超过则只交易到容差边界；
新开、清仓、反手、stop、funding 和强平仍精确执行，projected gross 超过 1.50x 时放弃容差。

预注册哈希：

- spec：`5979b4d516c9445a9ae7365be6df6f15787a79e3a68d23f40d4bf12ffed3348d`
- registration：`70406d35d1f5900d1877b0c4dea192441d84bdfa88557dcbd61b4d57128010dd`

四档成本：

| 成本 | L125 终值 | LS16 终值 | L125 Sharpe | LS16 Sharpe | L125 MDD | LS16 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | **65.1061x** | 1.8249 | **1.9335** | -38.42% | **-37.44%** |
| 20bps | 40.2200x | **50.0481x** | 1.7330 | **1.8278** | -40.65% | **-39.51%** |
| 50bps | 27.3725x | **32.2466x** | 1.5790 | **1.6508** | -44.20% | **-42.81%** |
| 100bps | 14.3794x | **15.4488x** | 1.3204 | **1.3536** | -50.02% | **-49.12%** |

20bps 成交数从 2,524 降到 1,537，费用从 2.7745 降到 2.2248（-19.8%）；全档 0 强平、
0 gross breach。3x short-adverse funding 为 50.6045x / 1.8313 / -39.63%，通过。365 天滚动
最差从 0.7325x 改善到 **0.7995x**。

失败项：

- **删除 2022 后 44.9539x < L125 50.0330x**；
- **45 个月初路径切片仅 23/45 三项同时通过**，终值 23/45、Sharpe 24/45、MDD 29/45；
- 2023-03 至 2024-06 的起点最大回撤比基线差 **6.5–7.7pp**；
- 2024 年收益从 L125 的 +119.25% 降到 **+85.33%**，说明容差延迟恢复多头目标存在机会成本。

**判定：rejected。** no-trade region 本身被证明能修复成本尾部，但没有修复 2023-2024 的路径和
延迟调仓风险。按预注册不扫描容差、事件阈值、频率或多空不同容差；该家族停止。当前实盘
`PR2026-10-D-L125-V2` 不变，LS16 不接执行器。

报告：`reports/derivatives_track_h5_no_trade_band/report.md`。
登记哈希：`70406d35d1f5900d1877b0c4dea192441d84bdfa88557dcbd61b4d57128010dd`。

### 00.39 2026-11-12 LS17：非熊市高 funding 拥挤空头 basket（rejected）

LS17 保留 H5 1.25x 和 LS12 的 BTC 200D 熊市 weak-four sleeve，只替换非熊市 sleeve：每周在
PIT Top20 的 H5 非持仓中，按 7D mean funding 从高到低做空最多 4 个 funding 严格为正的资产，
每腿 6.25% NAV，总空头 <=0.25x；有效 funding 资产少于 5 个时不开仓。

正式运行前审计：247 个 weekly 日期中，可计算 funding 的非 H5 资产最少 15、中位 18；
positive-funding 中位 14，243/247 周有至少 4 个正 funding 候选。LS12 原有非熊市 entry 中
67/72 本来就是正 funding，因此“仅加 funding>0 过滤”没有实质差异，真正候选是全横截面选币。

20bps：**46.2349x / 1.8548 / -37.96% / 0 强平**；L125 为 40.2200x / 1.7330 / -40.65%。
funding total 从 LS12 的 -0.7238 改善到 **-0.3044**，说明正 carry 选择有效。

失败项：

- **max observed gross 1.5265x，57 个 breach hours**；
- short open 从 LS12 的 335 增至 **632**，short stop 从 29 增至 **83**；
- 50bps 终值 **24.4102x < L125 27.3725x**；
- 100bps **8.3872x / 1.1362 / -50.89%**，终值、Sharpe、MDD 三关失败；
- 2bps 为 67.7748x / 2.0147 / -34.88%，说明低成本和低冲击下信号有效，但换手不具成本生存性。

首轮实现遗漏 `non_bear_mode=high_funding` 调用，输出与 LS12 相同；已隔离在
`reports/derivatives_track_h5_funding_basket/run_status/invalidated_missing_non_bear_mode/`，
并新增调用链回归测试。该无效输出不计入结果。

**判定：rejected。** 高 funding 拥挤能改善 20bps 风险指标和 funding 成本，但过高的每周换手与
short stop 使其无法通过 50/100bps，且 gross 硬上限被 drift 突破。按预注册不扫描 funding
lookback、basket size、min assets、正阈值、频率、权重或 stop；该家族停止。当前实盘
`PR2026-10-D-L125-V2` 不变。

报告：`reports/derivatives_track_h5_funding_basket/report.md`。
登记哈希：`8269fcc55330949440bf383eab7c74ebae52404901c091d658fcc17a37cdf619`。

### 00.40 2026-11-12 LS18：H5 多头内部 funding 拥挤去权重（rejected）

LS18 不再做空高 funding 资产，也不缩放整个 H5；它只处理 H5 当前多头：7D funding 位于 PIT
Top20 上三分之一且为正的腿减半，释放权重按原权重重分配给同书非拥挤腿，单币上限 60%，无法
分配的部分留现金。H5 选币、LS12 空头 router、stop、buffer 和 gross cap 全部不变。

运行前审计：1,053 个 H5 holding-events、511 个事件日，其中 325 个 crowded holding-events 覆盖
256 个事件日；触发时释放 gross 中位数 31.25%、90 分位 50%，不是单一名目事件。

20bps：**34.6700x / 1.7700 / -33.05% / 0 强平**；L125 为 40.2200x / 1.7330 / -40.65%。
funding total 从 -0.5918 改善到 **-0.4436**，费用 2.2429；Sharpe 和 MDD 都改善，但终值低于
L125 **13.8%**，第一收益门槛失败。

**判定：rejected。** funding 拥挤腿往往也是强势资产；减半和同书再分配能降低尾部，却削掉了主要
复利来源。按预注册不扫描 rank、lookback、减半比例、单币 cap 或再分配规则；long-leg funding
tilt 家族停止。2/50/100bps、funding stress、路径、引擎启动和 multiple-testing 均未在硬失败后运行。
当前实盘 `PR2026-10-D-L125-V2` 不变。

报告：`reports/derivatives_track_h5_funding_tilt/report.md`。
登记哈希：`75e329cbe44ca54f47e4464cf70c1277710a4f88212ef4ef3111cf6a8228c1d8`。

### 00.41 2026-11-12 LS19：H5 + 28D 横截面反转多空 sleeve（rejected）

LS19 按文献 S3 的“约一个月后反转”构造：H5 保持 1.25x；每 28 天在 PIT Top20 的非 H5 资产中，
按 28D 收益取最弱 4 个做多、最强 4 个做空，每腿 2.5% NAV，反转 sleeve 总 gross 0.20x。
target total gross 1.45x，hard observed 1.50x，short winner 腿使用 20% stop。

运行前审计：62 个 28D 评估日；排除 H5 后候选最少 16、中位 19；long 4 / short 4 从不重叠；
月度 selected-set turnover 中位 76.9%。

20bps：**37.3924x / 1.6969 / -40.15%**；L125 为 40.2200x / 1.7330 / -40.65%。
终值和 Sharpe 均低于基线；max observed gross 1.4965x，0 breach；short open 292、stop 90；
**11 次强平全部在 long loser 腿**（2022 年 10 次，2023 SHIB，2024 INTERNET-COMPUTER，2025-10
LINK/TON 各一次）。

事后把 short winner 腿单独归因：292 个 episode，145 正/147 负，累计 net PnL **-0.2925 NAV**，
平均 -0.0215% NAV、中位 -0.0094% NAV、最差 -1.0136% NAV。因此“去掉 long loser、只做
28D winner short”也不是有效变体；该家族不能靠保留单边救活。

**判定：rejected。** 反转的主要收益腿无法在高波动级联中活到反转完成；S3 关于“反转由过去输家
驱动”的结论在本项目 Top20 + isolated margin 口径下转化为不可接受的强平尾部。按预注册不扫描
lookback、rebalance、数量、权重、stop 或 H5/factor 比例；该分支停止。当前实盘
`PR2026-10-D-L125-V2` 不变。

报告：`reports/derivatives_track_h5_reversal_pair/report.md`。
登记哈希：`bf8892b568cee8ef95f10fcbc35d904c8dcb7e57c28cbf85470a698c362332aa`。

### 00.42 2026-11-12 LS20：H5 selection-event common-gross 再平衡（rejected）

LS20 试图修复 LS16 的缺陷：不做距离阈值、不让 gross 滞后，只在 H5 持币集合不变时保留旧币间
相对权重，并按新的 target gross 统一缩放；选币变化和 gross 变化仍精确执行。空头 router 和所有
stop/buffer 不变。

换手审计：542 个 long 事件中 208 个集合变化、334 个集合不变；long target L1 129.7632x，
same-set 占 59.2774x（45.68%）。

20bps：**39.4148x / 1.7683 / -40.56% / 0 强平**；L125 为 40.2200x / 1.7330 / -40.65%。
跳过 329 个 relative tilt，累计 skipped relative L1 59.9654；0 gross breach，费用 2.1608。

失败项：

- **终值 39.4148x < L125 40.2200x**，主收益门槛失败；
- Sharpe/MDD 仅小幅改善，不能抵消收益损失。

**判定：rejected。** H5 的币间相对调权不是噪声；保留旧相对权重会丢失一部分选币/风险信号。
按预注册不扫描 selection 定义、common-gross 规则、长短不同处理或频率；common-gross 家族停止。
2/50/100bps、funding stress、路径、冷启动和 multiple-testing 未在硬失败后运行。当前实盘
`PR2026-10-D-L125-V2` 不变。

报告：`reports/derivatives_track_h5_common_gross/report.md`。
登记哈希：`69ebabc4bdff650fa2de864f0d5234b888d3e6617d8d2b54ba5a9dfed74d2f85`。


### 00.43 2026-11-12 LS21：positive-carry 熊市空头（rejected）

LS21 只改变 LS12 熊市 weak-four sleeve 的 funding 条件：候选必须满足最近 3 个 settlement 的 mean
funding 严格大于 0；非熊市 funding-exit sleeve、H5 1.25x、20% stop、buffer、route 和 gross
全部不变。事后修正审计时点（信号日，而非执行日；只用到信号日 00:00 前的 settlement）后，
LS12 的 297 个熊市空头 episode 中 177 个 entry 为正 funding，累计 episode PnL
**+14.9005% NAV**；120 个非正 funding，累计 **+13.5094% NAV**。原先的 288/166/122 与
+29.6110%/+0.2770% 是执行日 normalize 造成的错误读数，已作废。修正后的审计不再支持
“正 funding 组贡献几乎全部 alpha”的叙述；LS21 的正式回测本身使用 exact-timestamp
`funding_filter`，不依赖这个错误审计。

四档成本：

| 成本 | L125 终值 | LS21 终值 | L125 Sharpe | LS21 Sharpe | L125 MDD | LS21 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | **67.8290x** | 1.8249 | **1.9334** | -38.42% | **-38.37%** |
| 20bps | 40.2200x | **49.7281x** | 1.7330 | **1.8102** | -40.65% | -40.64% |
| 50bps | 27.3725x | **29.6103x** | 1.5790 | **1.6039** | -44.20% | -44.25% |
| 100bps | 14.3794x | 12.4408x | 1.3204 | 1.2579 | -50.02% | **-50.10%** |

主样本 0 强平、0 gross breach；20bps 最大观测 gross 1.3308x。20bps 费用从 LS12 的 2.7745
降至 2.7027，但空头 open 从 335 增至 367、stop 从 29 增至 37；正 funding 没有降低换手。

**判定：rejected。** 100bps 终值、Sharpe 和 50% MDD kill line 三关失败；20bps 也低于 LS12 的
55.7859x。按预注册不继续 funding stress、年度/路径/冷启动/PBO/DSR，也不扫描 funding 阈值、
settlement 数、lookback、basket size、weight、stop 或 regime 窗口。positive-carry 熊市空头
阈值族停止。

同时修复了研究台账分类：`PR2026-11-LS*` 现在强制归入 derivatives，不再污染现货
`top20_2022_trials` 的 DSR 分母。LS19/LS20 重分类后 Top20/2022 试验数从 6,151 修正为 **6,142**。

报告：`reports/derivatives_track_h5_positive_carry_short/report.md`。
登记哈希：`34686b03399835bc8d9907b33604015f8b24649065dead24588da36851952d2e`。


### 00.44 2026-11-12 冻结规格样本外更新（50 天，仍为 provisional）

把样本外窗口从 2026-09-22 → 2026-10-08 更新到 **2026-09-22 → 2026-11-10**，不改变任何冻结规则：

| 口径 | 终值 | Sharpe | MDD | 相对 BTC |
|---|---:|---:|---:|---:|
| H5 spot 20bps +3h `day_close` | 0.9524x | -0.4247 | -17.06% | 1.119x |
| H5 spot 20bps +3h `prior_close` | 0.9981x | 0.2386 | -13.10% | 1.173x |
| L125-V2 Bitget mark 20bps | **0.9787x** | 0.0879 | -17.47% | 1.150x |
| BTC buy-and-hold | 0.8512x | -3.6565 | -14.88% | 1.000x |

- 50 个交易日里，策略相对 BTC 仍为正，但绝对收益为负；H5 +3h 较差口径回撤 -17.06%，比 BTC 差约
  2.2pp，不能称为已经通过风险门槛；
- L125-V2 的 Bitget mark 口径比现货 H5 略好，但杠杆把回撤放大到 -17.47%；
- 50 天只覆盖 **50/365 = 13.7%** 的 12 个月 OOS 要求，不改变 provisional、DSR、PBO、funding
  proxy 或 pre-2022 压力结论；
- 该窗口在规则冻结后才可观察，不能用于选参数或救活任何已被拒绝的候选。

报告：`reports/phase_momentum_oos_2026/`、`reports/derivatives_track_oos_research_2026_11/`。


### 00.45 2026-11-12 LS22：H5 单一龙头极端涨幅利润保护（provisional）

LS22 不改变 H5 选币，只在每个 H5 多头目标事件中检查权重最大的单腿：若该腿 21D trailing
return >=100%，把这一腿的 target weight 减半，释放权重留现金，不向其他币再分配。

运行前审计：542 个 H5 target event 中 57 个触发（10.52%），释放 gross 中位数 0.1717x NAV、
最大 0.2806x NAV；年度触发次数 1/16/32/4/4。

| 成本 | L125 终值 | LS22 终值 | L125 Sharpe | LS22 Sharpe | L125 MDD | LS22 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | **56.5820x** | 1.8249 | **1.9237** | -38.42% | **-37.61%** |
| 20bps | 40.2200x | **44.6607x** | 1.7330 | **1.8257** | -40.65% | **-39.84%** |
| 50bps | 27.3725x | **30.0813x** | 1.5790 | **1.6613** | -44.20% | **-43.40%** |
| 100bps | 14.3794x | **15.5305x** | 1.3204 | **1.3853** | -50.02% | **-49.40%** |

3x long-adverse funding：32.8229x / 1.6991 / -41.70% / 0 强平。年度收益除 2024 年
（+96.09% vs +119.25%）外均不低于 L125；删除任一最佳年份后终值全部高于 L125；365 天滚动
最差从 0.7325x 改善到 **0.8134x**。

失败项：预注册 45 个月初路径仅 **37/45** 终值胜 L125（Sharpe 45/45、MDD 45/45）。其中四个
2023-03 至 2023-06 起点只是 0.0002% 的数值平局，真正落后的是 2023-12 至 2024-03 四个起点，
落后 2.0–2.6%，来自 2024-03 SHIB 连续被减半而牺牲右尾。

**判定：provisional。** 四档成本、Sharpe、MDD、年度删除、滚动最差和 funding 压力均通过，
但预注册路径 gate 失败，所以不进入 12 个真实引擎冷启动、PBO/RC/DSR 或实盘。该候选不删除，
作为后续“独立机制组合”的研究资产；不扫描涨幅阈值、scale、top-N 或再分配规则。

报告：`reports/derivatives_track_h5_extreme_run_profit_lock/report.md`。
登记哈希：`6cbb3b6b48a7e4f1d34607d3a72b0c1dfe1c6a0f3877d7b3166ab6654b7a4280`。


### 00.46 2026-11-12 LS23：H5 利润保护 + LS12 双空头 router（provisional，当前最强 promotion candidate）

LS23 不再新增参数搜索，而是组合两个已经分别冻结、且失败点互补的机制：

- 多头：在冻结 H5 1.25x 上应用 LS22；每个 H5 目标事件只检查最大权重腿，21D trailing
  return >=100% 时把该腿减半，释放权重留现金，不向其他币再分配；
- 空头：完整保留 LS12 BTC-200D 双空头 router。BTC 在 200D 下方时做 14D 最弱四币；BTC 在
  200D 上方时做 H5 退出币中的 funding-top-tercile 空头；
- 空头只使用未使用 gross，总空头 <=0.25x，hard total gross <=1.50x；20% stop、50% buffer、
  T+1 +3h 和 missing-mark carry 3h 全部不变。

四档成本：

| 成本 | L125 终值 | LS23 终值 | L125 Sharpe | LS23 Sharpe | L125 MDD | LS23 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | **84.4362x** | 1.8249 | **2.0719** | -38.42% | **-37.57%** |
| 20bps | 40.2200x | **61.9150x** | 1.7330 | **1.9448** | -40.65% | **-39.84%** |
| 50bps | 27.3725x | **36.8788x** | 1.5790 | **1.7319** | -44.20% | **-43.45%** |
| 100bps | 14.3794x | **15.5037x** | 1.3204 | **1.3745** | -50.02% | **-49.48%** |

主样本 0 强平、0 gross breach；20bps max observed gross **1.3308x**。3x short-adverse funding
为 **62.0165x / 1.9443 / -39.95% / 0 强平**。删除任一最佳年份后终值全部高于 L125；365 天
滚动最差从 **0.7325x** 改善到 **0.8551x**，中位数从 2.5547x 改善到 2.8034x；45 个月初路径
切片 **45/45** 三项通过；12 个真实 cash-start 引擎季度起点终值和 Sharpe **12/12** 胜 L125，
MDD 5pp **12/12** 通过，0 强平/0 gross breach。

空头归因：修复 attribution 脚本后为 335 个 episode，169 正/166 负；平均每 episode
+0.1010% NAV、中位数 +0.0099%、最差 -1.3807% NAV；单资产最大贡献 **23.44%**、前 3
**62.09%**，通过 50%/80% 集中度门槛。修复前误记为 333 个，原因是大数量 close 的绝对浮点
容差过紧，导致两个已平仓 episode 被留在 open-at-end。9 个冻结候选矩阵 PBO/CSCV **0.3528**；White Reality Check zero **p=0.003996**、
BTC **p=0.009990**。按最新试验台账 N=14,210 / 6,142 刷新后，LS23 DSR all-trial
**0.958973**、Top20/2022 scope **0.971481**，均 >=0.95；旧 `0.9999832/0.9999858`
基于过期试验数，已作废。刷新口径见 §00.63。

51 天 cash-start OOS（2026-09-22 → 2026-11-11，20bps，Bitget OOS mark，zero funding）：

| 口径 | 终值 | Sharpe | MDD | 0 强平 | max gross |
|---|---:|---:|---:|---:|---:|
| L125 baseline | 0.9484x | -0.2743 | -17.47% | 是 | 0.8149x |
| LS23 candidate | 0.9403x | -0.5584 | -17.47% | 是 | 0.8153x |

该窗口 BTC 在 200D 上方，LS23 没有开空头，只检验了多头利润保护；50 天触发 8 次 trim，终值
相对同引擎 baseline 低约 0.85%，Sharpe 更差，回撤基本不变。50 天只占 12 个月 OOS 的 13.7%，
不足以判定失败，但足以阻止 promotion。

pre-2022 proxy stress（2020-10-03 → 2022-01-01，20bps，64 个可加载 mark 序列，0 强平）：
zero funding 面板 L125 4.2956x / 2.0754 / -27.76%，LS23 3.5113x / 2.2331 / -19.49%（无空头，
83 次 trim）；Binance funding proxy 面板 L125 3.9238x / 1.9618 / -28.24%，LS23
2.5189x / 1.7131 / -20.88%（67 个空头、25 个 stop、83 次 trim）。pre-2022 在 funding proxy
下终值和 Sharpe 低于 L125，只在 MDD 上改善，因此只能算 partial-with-bounding 压力证据。

**判定：provisional / strongest main-sample promotion candidate。** 样本内和稳健性门槛已基本闭合，但
12 个月真实 OOS 未完成、funding 仍是 Binance proxy、pre-2022 funding-proxy stress 的终值和
Sharpe 低于 L125，且最新 OOS 相对 baseline 没有正增量。因此不接执行器、不修改当前实盘
`PR2026-10-D-L125-V2`、不扫描 profit-lock/short/stop/regime/组合权重。

报告：`reports/derivatives_track_h5_profit_lock_regime_short/report.md`。
Spec 文件 SHA-256：`0e31c99f49b4a1beef09b84e40a99f02031da1370ed527ee02b5a933108fc6e4`。
注册 canonical spec JSON SHA-256：`68ec43fcef27511685d2da981557aa540b0e0848c7677f40409543bf3ba78a2b`。
登记哈希：`41435927fb85c0b170e53072284af68decbfb7999a5b53f865bff459660eb9bf`。


### 00.47 2026-11-12 LS24：跨所 funding 确认空头（rejected）

LS24 只加一个独立信息源：空头候选必须同时得到 Binance 和 Bybit 的正 funding 确认。分数取
两所最近 3 个 settlement 均值的逐元素最小值；任一 venue 缺失或不足 3 个 settlement，该资产
不合格。LS23 的 H5 1.25x、LS22 利润保护、LS12 路由、20% stop、50% buffer、0.25x short 和
1.50x gross 全部冻结不变。

运行前审计（修正后）：LS12 的 335 个空头 episode 中 Bybit 可用 **307 个（91.6%）**；bear
297 个、Bybit 可用 270 个、两所同时为正 138 个；non-bear 38 个、Bybit 可用 37 个、两所同时
为正 34 个。原 spec 中的 92.8%/288/47 是执行日 normalize 造成的错误读数，已由
`docs/superpowers/specs/2026-11-12-h5-cross-venue-funding-short-design-erratum.md` 取代；
规则和 registration hash 未改，修正后覆盖率仍高于 90% 门槛。

20bps 主样本：

| 指标 | LS23 | LS24 |
|---|---:|---:|
| 终值 | **61.9150x** | 52.7881x |
| Sharpe | **1.9448** | 1.8860 |
| MDD | -39.84% | **-39.71%** |
| 强平 | 0 | 0 |
| max observed gross | 1.3308x | **1.3029x** |
| gross breach hours | 0 | 0 |
| short open / stop | 335 / 29 | 343 / 27 |
| funding total | -0.7465 | **-0.5359** |

跨所确认降低了 funding 成本和 short stop，但没有提高收益或 Sharpe；终值和 Sharpe 均低于
LS23，按预注册第一、第二门槛直接失败。funding 确认在每周目标事件上评估，和 LS12 一样，
已停止的腿可以在下一次周度 rebalance 前从同一 target 重开；343 个 short open 中有 4 个这类
stale re-entry 在开仓时点 funding 下界已转负，未做事后过滤。首轮实现用精确 index union 对齐
Binance/Bybit，毫秒时间戳导致大量 NaN，已隔离在
`reports/derivatives_track_h5_cross_venue_funding_short/run_status/invalidated_misaligned_cross_venue/`；
正式结果来自按分钟对齐 settlement 的运行。

**判定：rejected。** 不运行 2/50/100bps、funding stress、删除年份、滚动窗口、45 路径、冷启动
或 PBO/RC/DSR；不扫描 settlement 数、lookback、min/mean/median、正阈值、basket size、stop、
buffer、regime 或组合权重；不接执行器。跨所 funding 家族停止。

报告：`reports/derivatives_track_h5_cross_venue_funding_short/report.md`。
Spec 文件 SHA-256：`f5200669908cf4a28b053be79ee1d697e6ae191fea0b9b7b2faf533774397091`。
注册 canonical spec JSON SHA-256：`dbf834fdd99e6a7f33bec508f846354d430e62ef72c0aa9b413f0695bd353f99`。
登记哈希：`a933acdcb585464733d338f82bcd98e4d47d045553933d9c2f456ae71de1c978`。


### 00.48 2026-11-12 LS23 真实 shadow tracker v2：完整 Bitget funding 与分页修复

新增研究工具 `scripts/run_derivatives_shadow.py`，只重建冻结 LS23/L125 目标并运行研究引擎，
不产生订单、不接触执行器、不改变 `PR2026-10-D-L125-V2`。账本保留多空符号，包含 carry-in
信号（信号日 2026-09-21、实际在 2026-09-22 03:00 UTC 成交），并把引擎首个初始化日排除在
Sharpe/波动率统计之外，避免首日零收益污染。

2026-09-22 → 2026-11-10，20bps，50 个日行/49 个有效收益；OOS mark 88 个资产窗口内
**0 missing hours / max gap 1h**；状态 warmup 使用 `merged_20261009` 完整历史：

| funding 口径 | 策略 | 终值 | Sharpe | MDD | funding total | trim | short open |
|---|---|---:|---:|---:|---:|---:|---:|
| zero（上界） | L125 | 0.9484x | -0.2771 | -17.47% | 0 | 0 | 0 |
| zero（上界） | LS23 | 0.9403x | -0.5584 | -17.47% | 0 | 8 | 0 |
| Bitget exact（完整） | L125 | 0.9440x | -0.3303 | -17.65% | -0.4808% | 0 | 0 |
| Bitget exact（完整） | LS23 | **0.9365x** | **-0.6125** | **-17.65%** | **-0.4088%** | 8 | 0 |

完整 funding 下 LS23 仍低于 L125 约 0.0074x，Sharpe 低约 0.2855；零 funding 下也低约 0.85%。
该窗口 BTC 在 200D 上方，LS23 的 LS12 空头 sleeve **0 次开仓**；本轮只检验 LS22 利润保护，
不能把结果当作完整 LS23 多空结论。

数据审计发现 Bitget funding 与 Binance proxy 的跨所 overlap gate **0/88 通过**，所以 Binance
proxy 不能替代 Bitget 成本；Bitget exact funding 88/88 存在，已作为成本口径。首次新快照还暴露
Bitget candle 分页 bug：`endTime` 是小时开区间，旧代码用 `first_open - 1ms` 导致每 100 行边界
少 1 小时（88 个资产、OOS 窗口 1056 个缺失小时）；已改为 `next_end = first_open`，并增加
shadow tracker 的 mark coverage fail-closed 检查和下载器 `partial` 状态。

**判定：仍为 provisional，不 promotion。** 50 天只覆盖 12 个月 OOS 的 13.7%；两个 funding
口径下 LS23 都低于 L125，空头 sleeve 未触发；不修改实盘，不把 shadow 结果当作下单信号。

报告：`reports/derivatives_track_h5_profit_lock_regime_short/shadow_oos_2026_11_refresh/report.md`
（SHA-256 `a27245fe5a00c0ad8a503ec21b38202b7d8d2efa2a7c1f265d9e46e25cf995d0`）。
汇总：`reports/derivatives_track_h5_profit_lock_regime_short/shadow_oos_2026_11_refresh/summary.csv`
（SHA-256 `76a85424e84e7aef6db9e2770478cc7ebea42db7bf3032721cb79d69848ddd65`）。
数据审计：`reports/derivatives_track_h5_profit_lock_regime_short/shadow_oos_2026_11_refresh/data_audit/report.md`。


### 00.49 2026-11-12 LS25：H5 单龙头状态化利润保护（rejected）

LS22 在每个 H5 目标事件重新判断最大持仓；同一龙头持续极端上涨时会被反复减半。LS25 只把
这个状态改成“同一连续龙头首次触发后保持半仓，直到龙头切换”，不改变 21D/100%/0.5 参数，
不扫描 release 阈值，也不加空头。

20bps 主样本：

| 策略 | 终值 | Sharpe | MDD | trim | max gross | 强平 |
|---|---:|---:|---:|---:|---:|---:|
| L125 baseline | 40.2200x | 1.7330 | -40.65% | 0 | — | 0 |
| LS22 | 44.6607x | 1.8257 | -39.84% | 57 | — | 0 |
| LS23 | 61.9150x | 1.9448 | -39.84% | 57 | 1.3308x | 0 |
| **LS25** | **35.1755x** | **1.7691** | **-41.15%** | **17** | **1.2811x** | **0** |

状态化确实把重复 trim 从 57 次降到 17 次，但损失了更多右尾：终值低于 L125 5.0445x，MDD 比
L125 差约 0.50pp；Sharpe 略高但第一收益门槛和 MDD 容忍线失败。

**判定：rejected。** 不运行 2/50/100bps、funding stress、删除年份、滚动窗口、45 路径、冷启动
或 PBO/RC/DSR；不扫描阈值、lookback、scale、release 规则或再分配。状态化单龙头利润保护家族
停止，不修改实盘 `PR2026-10-D-L125-V2`。

报告：`reports/derivatives_track_h5_stateful_profit_lock/report.md`。
登记哈希：`42941b530a57003c58f37efdad85c917fa8c549fffe5dae6fc519f1b2085af92`。


### 00.50 2026-11-12 LS26：重新武装利润保护与 LS22 等价（rejected / duplicate）

LS26 预先注册为“同一龙头 21D 回落到 <100% 时解除锁、再次 >=100% 时重新减半”，没有新增
release 阈值。20bps 主样本结果与 LS22 **完全相同的日收益**：

| 策略 | 终值 | Sharpe | MDD | 初始化 trim | locked 事件 | 强平 |
|---|---:|---:|---:|---:|---:|---:|
| LS22 | 44.6607x | 1.8257 | -39.84% | 57 | — | 0 |
| **LS26** | **44.6607x** | **1.8257** | **-39.84%** | **22** | **57** | **0** |

1724 个日收益最大差为 0.0。原因是 LS22 在每次 21D >=100% 事件都把当前 H5 target 减半，
LS26 在同一区间保持“当前 target 的一半”；两者权重路径相同，只是 LS26 把“首次触发”和
“持续 locked”分开计数。LS26 不是新的独立 alpha，也不改善 LS22。

**判定：rejected / duplicate。** 不运行成本档、funding stress、路径、冷启动或 PBO/RC/DSR；
不把它当作新候选或救活 LS25。保留实现和报告，用于记录重复 trim 与状态化锁的等价关系。
不修改实盘 `PR2026-10-D-L125-V2`。

报告：`reports/derivatives_track_h5_rearming_profit_lock/report.md`。
登记哈希：`f0cd7eebfa8bffd785bb500a1c4098a61849b01cc308ea6aec96ac4c84f836db`。


### 00.51 2026-11-12 LS27：H5 利润保护 + 动态多空预算（rejected）

LS27 把 LS22、LS12 双空头 router 和 R6 bottom-four 空头合并：两个空头组件各请求 0.25x，
目标 total gross 1.48x、1.50x hard guard；正常满多头时只使用 0.25x 空头，LS22 释放 cash 后
才扩大短 gross。

四档成本（LS23 为 incumbent）：

| 成本 | LS23 终值 | LS27 终值 | LS23 Sharpe | LS27 Sharpe | LS23 MDD | LS27 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 84.4362x | **109.9219x** | 2.0719 | **2.1476** | -37.57% | -38.30% |
| 20bps | 61.9150x | **68.8876x** | 1.9448 | **1.9599** | -39.84% | -41.40% |
| 50bps | **36.8788x** | 31.4739x | **1.7319** | 1.6443 | **-43.45%** | -46.34% |
| 100bps | **15.5037x** | 8.4896x | **1.3745** | 1.1146 | **-49.48%** | **-56.08%** |

20bps 表面提高收益和 Sharpe，但 50/100bps 成本门槛失败，100bps MDD 跌破 50%。gross 也未闭合：
1.48x target + 1.50x hard guard 下仍有 5 个 observed breach hours、最大 observed gross 1.5157x；
无 buffer 的初始版本为 259 小时、最大 1.5627x。主样本 0 强平。

实现修复：

- bottom-four 周频短腿在资产进入 H5 多头或离开 PIT Top20 时必须提前退出；新增
  `route_short_schedule_with_long_exclusions`，避免同资产多空重叠和虚假 gross；
- 允许 `hard_gross_exposure == max_gross_exposure`，LS27 启用逐小时 hard guard；该 guard 只把
  超额暴露限制在一个可观察周期内，不把 breach 当作合规。

**判定：rejected。** 不扫描 bottom-N、stop、target gross、buffer、等权比例或 regime；不运行
funding/年度/路径/冷启动/多重检验；不修改实盘。

报告：`reports/derivatives_track_h5_profit_lock_dynamic_short/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-profit-lock-dynamic-short-design.md`
（SHA-256 `5ae61863378fc0e4cf9a220c9fccafc392fee68d3d390c5904dc903cd8af44f6`）。
登记哈希：`e150be01042864ec9ce9c290f6d1b79f4c9ea3193c194dafc63c283cc2b940d3`。


### 00.52 2026-11-12 LS28：H5 利润保护 + 优先级空头预算（rejected）

LS28 是 LS27 的低换手修正：LS12 router 先获得最多 0.25x，R6 bottom-four 只能使用 LS22
释放出来的剩余 gross；新增 `combine_long_with_priority_short_sleeves`，同资产短腿上限 0.25x。

| 成本 | LS23 终值 | LS28 终值 | LS23 Sharpe | LS28 Sharpe | LS23 MDD | LS28 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 84.4362x | **110.1001x** | 2.0719 | **2.1494** | -37.57% | -38.19% |
| 20bps | 61.9150x | **68.9318x** | 1.9448 | **1.9612** | -39.84% | -41.32% |
| 50bps | **36.8788x** | 31.5191x | **1.7319** | 1.6457 | **-43.45%** | -46.22% |
| 100bps | **15.5037x** | 8.5055x | **1.3745** | 1.1158 | **-49.48%** | **-56.00%** |

优先级控制没有改变成本曲线：50bps 起低于 LS23，100bps MDD 失败；gross guard 仍未闭合，
20bps breach 69 小时、最大 1.5169x；100bps breach 82 小时、最大 1.5219x。0 强平。

**判定：rejected。** 不扫描 priority ratio、extra weight、stop、bottom-N、gross buffer 或 regime；
不运行 funding/年度/路径/冷启动/多重检验；不修改实盘。

报告：`reports/derivatives_track_h5_profit_lock_priority_short/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-profit-lock-priority-short-design.md`
（SHA-256 `fd6098244616203732a2ea9ea8dc81182cefd130a34cf5f9a9945d46ceb2f224`）。
登记哈希：`48c6c155a50d1d8c8bf6d1fa7aea1681c59611402d8fb220f66eeba37cf1f3af`。


### 00.53 2026-11-12 LS29：H5 集中度条件利润保护 + LS12 空头（rejected）

LS29 只给 LS22 增加一个集中度条件：仅当最大多头腿权重 >=25% NAV 且 21D trailing return
>=100% 时减半该腿；低于 25% 的极端龙头保留右尾。其余 LS23 规则不变。

20bps：

| 策略 | 终值 | Sharpe | MDD | trim | max observed gross | 强平 | gross breach |
|---|---:|---:|---:|---:|---:|---:|---:|
| LS23 | **61.9150x** | **1.9448** | **-39.84%** | 57 | 1.3308x | 0 | 0 |
| LS29 | 60.4392x | 1.9325 | -39.84% | 41 | 1.3308x | 0 | 0 |

集中度条件把 trim 降到 41 次，但终值低 2.38%、Sharpe 低 0.0123，MDD 无改善；第一、第二门槛
失败。说明 LS22 的问题不是“削减了不够集中的腿”，而是 2024 右尾本身无法用这个条件区分。

**判定：rejected。** 集中度条件利润保护家族停止；不扫描 20/30/35% 门槛；不运行成本档、
funding、路径、冷启动或多重检验；不修改实盘。

报告：`reports/derivatives_track_h5_concentration_profit_lock/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-concentration-profit-lock-regime-short-design.md`
（SHA-256 `2ff20b3d86d83f309106294f864d6d8fd6e3e704a46b1de0a95338e1347d7a16`）。
登记哈希：`d8869a38f26b3ecf175add975de81e689fb10835f98e4d362034bb1f900a8c7a`。


### 00.54 2026-11-12 LS30：H5 + 市场中性 funding carry sleeve（rejected）

LS30 在 H5 1.25x 上叠加一个 0.25x gross 的市场中性 funding carry sleeve：PIT Top20 非 H5
成员中，7D mean funding 最低 2 币做多、最高 2 币做空，每腿 6.25% NAV，周频 7D，min_assets 8，
min_settlements 3，short stop 20%，T+1 +3h。

20bps：

| 策略 | 终值 | Sharpe | MDD | 强平 | max observed gross | breach hours |
|---|---:|---:|---:|---:|---:|---:|
| L125 | 40.2200x | 1.7330 | -40.65% | 0 | — | 0 |
| LS30 | **48.9409x** | **1.8110** | **-40.34%** | **1** | **1.5103x** | **26** |

收益/Sharpe/回撤表面改善，但 2022-05-11 DOT long 从 17.5681 跌到 8.4220，越过 50% long
buffer 的理论强平价 8.4263；同时 observed gross 1.5103x、26 个 breach hours。风险门槛失败。

实现新增：

- `build_cross_sectional_funding_carry_schedule`：低 funding 多 / 高 funding 空的中性 sleeve；
- `route_signed_sleeve_with_long_exclusions`：carry 腿进入 H5 或离开 PIT Top20 时提前退出；
- `combine_long_with_signed_sleeve`：只把未使用 gross 分配给 signed sleeve，按 long + |carry| 计
  gross。

**判定：rejected。** 不运行 2/50/100bps、funding、路径、冷启动或 PBO/RC/DSR；不扫描
funding lookback、rank、count、腿权重或 min_assets；不修改实盘。

报告：`reports/derivatives_track_h5_funding_carry_neutral/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-funding-carry-neutral-sleeve-design.md`
（SHA-256 `69b3c481b0bea714c730236e1150698c09b2b8e4da4cf77478f3461f11b63410`）。
登记哈希：`7edad94bc882b660f65b8d7654be12098979e82a1d5e025a07fa6d334b7725d5`。


### 00.55 2026-11-12 LS31：market-neutral funding carry + 60% long buffer（rejected at costs）

LS31 与 LS30 完全相同，只把 long buffer 从 50% 提高到 60%，用于处理 LS30 的 DOT long
强平。四档成本：

| 成本 | L125 终值 | LS31 终值 | L125 Sharpe | LS31 Sharpe | L125 MDD | LS31 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | **70.9970x** | 1.8249 | **1.9655** | -38.42% | **-37.11%** |
| 20bps | 40.2200x | **48.9593x** | 1.7330 | **1.8168** | -40.65% | **-40.13%** |
| 50bps | **27.3725x** | 26.3191x | **1.5790** | 1.5675 | **-44.20%** | -44.89% |
| 100bps | **14.3794x** | 9.3188x | **1.3204** | 1.1491 | **-50.02%** | **-56.40%** |

20bps 风险修正成功：**0 强平、0 gross breach**，max observed gross **1.4364x**；2/20bps
终值、Sharpe、MDD 均优于 L125。但 50bps 起低于 L125，100bps MDD -56.40%，成本门槛失败。

**判定：rejected（低换手 carry 研究资产，不是 LS23 替代）。** 不扫描 55/65/70% long buffer、
不扫 funding lookback/rank/count/腿权重；不运行 funding stress、路径、冷启动或 PBO/RC/DSR；
不修改实盘。

报告：`reports/derivatives_track_h5_funding_carry_long60/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-funding-carry-long60-design.md`
（SHA-256 `2a5b3ce2ad123546d48d7e296d5dfbc7338a06ef510c7a547787f0d1b9915e5d`）。
登记哈希：`f9de0689cd258ae416dfd152cf2a54c807d92352c5e9752092c5106b31ac8ceb`。

### 00.56 2026-11-12 LS32：2x-entry-count funding carry 持有带（rejected）

LS32 在 LS31 的 60% long buffer 上只增加一个预注册持有带：已有 carry 腿仍在最低/最高 4 名
内就继续持有，跌出持有带才替换。持有带确实降低了机械换手：

| 指标 | LS31 | LS32 | 变化 |
|---|---:|---:|---:|
| carry target cumulative L1 change | 70.5000x | 48.8750x | -30.7% |
| long name changes | 440 | 280 | -36.4% |
| short name changes | 688 | 502 | -27.0% |
| short opens | 381 | 294 | -22.8% |

但 20bps 结果没有改善：

| 策略 | 终值 | Sharpe | MDD | 强平 | max observed gross |
|---|---:|---:|---:|---:|---:|
| L125 | 40.2200x | 1.7330 | -40.65% | 0 | — |
| LS23 | **61.9150x** | **1.9448** | **-39.84%** | 0 | 1.3308x |
| LS31 | 48.9593x | 1.8168 | -40.13% | 0 | 1.4364x |
| LS32 | 44.3989x | 1.7772 | -40.09% | **1** | 1.4331x |

DOT long 于 2022-05-12 05:00 UTC 被强平，entry **20.0831785**、execution **7.4284490**
（约 -63.0%）。这不是 engine bug：持有带使 DOT 比 LS31 的精确排名退出多留了一段，因而即使
long buffer 为 60% 仍进入强平边界。较低的换手不足以补偿滞后退出和选币质量下降。

**判定：rejected。** 停止该 carry 持有带家族；不扫描 hold_count 3/5/6/8，不运行 2/50/100bps、
funding stress、路径、冷启动或 PBO/RC/DSR。不修改实盘 `PR2026-10-D-L125-V2`。

同时修复了 LS30/LS31 manifest 未记录实际 carry 参数、LS31 frozen long buffer 误写 0.5 的问题；
新增 `_trial_frozen_config` 回归测试，后续 trial 的 manifest 会记录真实 buffer、carry 参数和 sleeve。

报告：`reports/derivatives_track_h5_funding_carry_holdband/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-funding-carry-holdband-design.md`
（SHA-256 `7b87fb5684f21458704c884dadabe30576ca37612d4b2949a06820d6eb1cdd84`）。
登记哈希：`8490b289436bafac17c0073ec7dff48b33d4850ab1a0db5ad7265a0bf4c570bc`。

### 00.57 2026-11-12 LS33：LS23 优先 + 剩余 gross funding carry（rejected at 100bps）

LS33 把冻结 LS23 作为最高优先级 book：H5 1.25x 利润保护 + LS12 双空头 router 先占用 gross；
LS31 的 market-neutral funding carry 只使用 `1.50 - base_gross` 的剩余、非重叠资产。60% long
buffer 的 LS33C control 与 LS23 日收益完全相同，因此 20bps 增量来自 carry，而不是 buffer。

| 策略 | 20bps 终值 | Sharpe | MDD | 强平 | max observed gross | breach hours |
|---|---:|---:|---:|---:|---:|---:|
| L125 | 40.2200x | 1.7330 | -40.65% | 0 | — | 0 |
| LS23 | 61.9150x | 1.9448 | -39.84% | 0 | 1.3308x | 0 |
| LS33C LONG60 control | 61.9150x | 1.9448 | -39.84% | 0 | 1.3308x | 0 |
| LS33 | **80.6764x** | **2.0566** | **-39.19%** | **0** | 1.4420x | **0** |

carry 平均实际占用 **0.2201x NAV**，60.2% 的 target event 能用满 0.25x；base gross 平均
0.5188x，说明 residual budget 是真实存在的。年度收益相对 LS23：2022 +25.25% vs +23.71%、
2023 262.29% vs 264.98%、2024 **+112.61%** vs +80.33%、2025 **+213.89%** vs +194.07%、
2026 **+166.42%** vs +158.57%。

四档成本：

| 成本 | LS23 终值 | LS33 终值 | LS23 Sharpe | LS33 Sharpe | LS23 MDD | LS33 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 84.4362x | **124.0468x** | 2.0719 | **2.2326** | -37.57% | **-36.07%** |
| 20bps | 61.9150x | **80.6764x** | 1.9448 | **2.0566** | -39.84% | **-39.19%** |
| 50bps | 36.8788x | **39.3242x** | 1.7319 | **1.7612** | -43.45% | -44.07% |
| 100bps | **15.5037x** | 11.8172x | **1.3745** | 1.2648 | **-49.48%** | **-52.87%** |

2/20/50bps 终值和 Sharpe 全部高于同成本 L125 与 LS23；但 100bps 三项全败并越过 50% MDD
kill line。**判定：rejected at 100bps cost gate。** 不运行 funding stress、路径、冷启动或
PBO/RC/DSR；不扫描 carry count/weight/lookback、gross priority、stop 或 buffer。LS33 保留为
“residual carry 有真实 alpha、但换手成本未解决”的研究资产。

实现新增 `combine_signed_book_with_residual_sleeve`：base 从不被缩放；carry 移除与 base 任何方向
重叠的资产；只按剩余 gross 比例缩放；hard total gross 1.50x。

报告：`reports/derivatives_track_h5_ls23_residual_carry/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-residual-carry-design.md`
（SHA-256 `7afd165ba27aa5d8edde18139bd59c1a054730b44ad96c30f4c925ab003f2983`）。
Spec canonical SHA-256：`510bb2ec705eb6f82d34d334207543c6f7e5ccef01c5e41dc117e1190ccbdaea`。
登记哈希：`37efa9a9e85992303d27c75e9ff063b10021684c89f14368cfe824c19a3c4473`。

### 00.58 2026-11-12 LS34：LS33 residual carry 的空头持有带（rejected）

LS34 只改变 LS33 residual carry 的空头腿：已有空头仍在最高 4 名内就继续持有，跌出才替换；
多头腿仍按 lowest 2 精确退出。它是 LS32 stale-long 失败的机制修正，不扫描 hold_count。

| 指标 | LS33 | LS34 | 变化 |
|---|---:|---:|---:|
| carry target cumulative L1 change | 70.5000x | 58.8750x | -16.5% |
| long name changes | 440 | 440 | 0% |
| short name changes | 688 | 502 | -27.0% |
| short opens | 629 | 556 | -11.6% |
| fees total @20bps | 5.4067 | 5.1618 | -4.5% |

20bps：

| 策略 | 终值 | Sharpe | MDD | 强平 | max observed gross | breach hours |
|---|---:|---:|---:|---:|---:|---:|
| LS23 | 61.9150x | 1.9448 | -39.84% | 0 | 1.3308x | 0 |
| LS33 | **80.6764x** | **2.0566** | **-39.19%** | 0 | 1.4420x | 0 |
| LS34 | 77.3635x | 2.0396 | -39.48% | 0 | 1.4424x | 0 |

LS34 的终值和 Sharpe 均低于 LS33，第一门槛失败。节省的成本小于保留失效空头带来的 alpha 损失。
**判定：rejected。** 停止 residual carry 空头持有带家族；不扫描 hold_count 3/5/6/8，不运行
2/50/100bps、funding stress、路径、冷启动或 PBO/RC/DSR。不修改实盘。

实现新增 `hold_long` / `hold_short` 参数；LS34 固定 `hold_long=False`、`hold_short=True`。

报告：`reports/derivatives_track_h5_ls23_residual_carry_shorthold/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-residual-carry-shorthold-design.md`
（SHA-256 `e2848596071ad91d7d8be3cfb2ff9b6bd5541cb497ceda7faf017f1e4da83e93`）。
Spec canonical SHA-256：`9178e0a246da25c9e0417f251bd8fde6cbe78b7ccc3ce2a4f4ea0e8541e50405`。
登记哈希：`8c878d3e93ee54f6f5c4281ce43cfa1f73839eb79d60ad734e59c559bbb023ba`。

### 00.59 2026-11-12 LS35：true-carry residual sleeve（rejected at 100bps）

LS35 在 LS33 上只加入严格经济符号：long funding<0、short funding>0，不足两腿时持有更少或现金。
只读归因曾显示 LS33 的 carry short 约 **99.7%** 时间为正 funding，long 只有约 **78.8%** 为负 funding；
因此该过滤主要删除 positive-funding long。

| 成本 | LS23 终值 | LS35 终值 | LS23 Sharpe | LS35 Sharpe | LS23 MDD | LS35 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 20bps | 61.9150x | **74.0476x** | 1.9448 | **2.0383** | -39.84% | -39.50% |
| 100bps | **15.5037x** | 11.2205x | **1.3745** | 1.2515 | **-49.48%** | **-52.15%** |

20bps 0 强平、0 gross breach、max observed gross 1.4420x；100bps 三项全败并越过 50% MDD。
**判定：rejected。** 不运行 2/50bps、funding stress、路径、冷启动或 PBO/RC/DSR；不扫描 sign
threshold、count、weight、lookback 或 buffer。

报告：`reports/derivatives_track_h5_ls23_residual_carry_sign/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-residual-carry-sign-design.md`
（SHA-256 `07ad42e900af3ddafdbba99a1e24a864886bff8417d78ea9fd0fad99401a44c3`）。
Spec canonical SHA-256：`bb53e80e85b7689b317832b5811c562324c6a105a96f8a6be6ed4b54618c5897`。
登记哈希：`a5dea5216240debb625e2aa1658669b985af1537f4dc5a9c6a3a522ab4c98fde`。


### 00.60 2026-11-12 LS36：short-only residual carry（rejected at 100bps）

LS36 把 LS33 carry 缩减为只做 short 腿：highest positive 7D funding 2 币，每腿 6.25% NAV，
carry gross 最多 0.125x，long carry 关闭。它是 LS33 的干净单腿分解，不扫描 short 数量或权重。

| 成本 | LS23 终值 | LS36 终值 | LS23 Sharpe | LS36 Sharpe | LS23 MDD | LS36 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 20bps | 61.9150x | **69.5943x** | 1.9448 | **2.0159** | -39.84% | -39.94% |
| 100bps | **15.5037x** | 12.6244x | **1.3745** | 1.3029 | **-49.48%** | **-51.37%** |

20bps 0 强平、0 gross breach、max observed gross 1.4368x，费用 4.2032（低于 LS33 的 5.4067）；
100bps 仍低于 LS23 三项门槛并越过 50% MDD kill line。

**判定：rejected。** short-only carry 有真实 20bps 增量，但 base LS23 在 100bps 已接近成本尾部，
任何持续 weekly carry 换手都会把组合推过门。不扫描 short count、weight、lookback、stop 或 buffer。
下一步只能转向有数据支撑的低频 rebalance；funding rank 的跨期 Spearman 代理为 7D 0.6655、
14D 0.5576、28D 0.4726，14D 是唯一预注册的低频候选。

报告：`reports/derivatives_track_h5_ls23_residual_short_carry/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-residual-short-carry-design.md`
（SHA-256 `77fe71cabe3cdfee63087f7cc1acd1af115131324fda49e5e738b336128f96ce`）。
Spec canonical SHA-256：`326aed6ef97689b9323b7b015e675f3b1dfcc8b331505a006d901cd5b1f63e73`。
登记哈希：`ad25053fc6e0885434cda84fc24f2c1b0a0ea73654fee217fcb2afca24ea2f29`。

### 00.61 2026-11-12 LS37：14D residual carry（rejected at 100bps）

LS37 只把 LS33 residual carry 的 rebalance 从 7D 改为 14D；7D funding score、count=2、
每腿 6.25%、exact ranking、60% long buffer 和 20% short stop 全部冻结。14D 是预注册的
唯一低频候选，依据是 funding rank 跨期相关从 7D 0.6655 降到 14D 0.5576，而 28D 已降到 0.4726。

| 成本 | LS23 终值 | LS37 终值 | LS23 Sharpe | LS37 Sharpe | LS23 MDD | LS37 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 20bps | 61.9150x | **73.2343x** | 1.9448 | **2.0172** | -39.84% | -41.26% |
| 100bps | **15.5037x** | 12.8731x | **1.3745** | 1.2993 | **-49.48%** | **-52.75%** |

20bps 0 强平、0 gross breach、max observed gross 1.4429x；费用 4.6678（低于 LS33 的 5.4067）。
但 100bps 三项仍失败并越过 50% MDD。**判定：rejected。** 停止 carry 低频 rebalance 家族，
不扫描 21D/28D 或其他频率；base LS23 在 100bps 已接近成本边界，继续加 sleeve 不是有效方向。

报告：`reports/derivatives_track_h5_ls23_residual_carry_14d/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-residual-carry-14d-design.md`
（SHA-256 `b4ee432893bae26bfae23b04ff803042bd063533867109337c71746127dde7d3`）。
Spec canonical SHA-256：`1b4ddd5cbe907d199e539b86e9fecee18ac738bb06f2ec066a1f9637a13506dc`。
登记哈希：`329254fc1e23027e7a6e25dd1888d755c538d04cba5a7a709ec6070d35032f5f`。

### 00.62 2026-11-12 LS38：LS23 same-side 5% no-trade band（rejected）

LS38 在冻结 LS23 上只增加 5% NAV same-side no-trade band；开仓、清仓、反手和 gross guard
仍精确执行。5% 来自既有 H5 权重容差，没有扫描其他阈值。

| 策略 | 20bps 终值 | Sharpe | MDD | fees total | short opens | short stops |
|---|---:|---:|---:|---:|---:|---:|
| LS23 | **61.9150x** | **1.9448** | -39.84% | 3.1262 | 335 | 29 |
| LS38 | 54.5335x | 1.9102 | **-38.69%** | **2.5007** | 333 | 27 |

费用下降约 20%、MDD 改善约 1.15pp，但终值下降约 11.9%、Sharpe 下降 0.0346；第一门槛失败。
no-trade band 让利润保护和 router 的目标响应滞后，节省的成本小于 alpha 损失。**判定：rejected。**
不运行 100bps、funding stress、路径、冷启动或 PBO/RC/DSR；不扫描 1%/2.5%/5%/7.5%/10%/15%，
不尝试只对多头或空头设置容差；LS23 no-trade 家族停止。

报告：`reports/derivatives_track_h5_ls23_notrade5/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-notrade5-design.md`
（SHA-256 `58dcedc6e38a0788e92178817947d7bb05de08e4f789794ee23a34a2e98e9fbd`）。
Spec canonical SHA-256：`2169b2da6d9048eae1500e6e65622e2feeb2ec350e34dcd20f0e0647b1ae4dd4`。
登记哈希：`7503404f19a7b3eff4bd61b219731a50419afb9f0c8260c9a726ba8012309258`。

### 00.63 2026-11-12 LS23 multiple-testing refresh：以最新试验台账重算 DSR/PBO/RC

旧 LS23 多重检验结果使用过期 trial count，不能继续作为当前证据。本次不改变候选规则、收益序列、
成本或门槛，只把 9 个冻结候选的同一份 20bps 日收益面板按最新 inventory 重算。结果目录：
`reports/derivatives_track_h5_profit_lock_regime_short/multiple_testing_refresh_20261112/`。

共同样本为 2022-01-01 → 2026-09-20，共 **1,724 天**；要求 LS23、全部 9 个冻结候选和 BTC
benchmark 每天都有有限收益，否则整次运行失败，不允许在不完整样本上计算。由于比主回测终点少
一天，LS23 在此面板上的观测 Sharpe 为 **1.9442716**（主报 1.9448），这是样本坐标差异，不是规则
变化。

| scope | trial count | expected max Sharpe | LS23 DSR | 门槛 |
|---|---:|---:|---:|---:|
| family（9 个冻结候选） | 9 | 0.112920 | **0.9999979** | >=0.95 |
| Top20/2022 inventory | 6,142 | 1.186580 | **0.9714805** | >=0.95 |
| all-project inventory | 14,207 | 1.251909 | **0.9589766** | >=0.95 |

`all_trials` 的 DSR 仍用 Top20/2022 pool 的 Sharpe dispersion（0.3172858 annualized）定价，因为跨
窗口、跨 universe 的 Sharpe 不可直接比较；trial count 则使用最新全项目计数 14,207。当前 inventory
中 all/top20 分别有 34/15 个没有 Sharpe 的配置，也按既有规则计入分母。

其余刷新结果：PBO/CSCV **0.352814**（924 个组合、1,724 行、低于 0.50）；White Reality Check
对 zero 的 p=**0.003996**、对 BTC buy-and-hold 的 p=**0.009990**（1,000 次 stationary bootstrap，
block length 20，seed 20260923）。PBO 仍支持冻结候选族内部的选择稳定性，RC 仍只覆盖该候选族的
收益序列；更早家族的选择偏差由项目级 DSR 计入。

manifest：`multiple_testing_refresh_20261112/manifest.json`；trial summary SHA-256：
`6ee5ff694f1cdc4557874fc4bd9f0d7ca4d49b9313ff8cbee346b5d16bebffc7`。**判定不变：LS23 仍是
provisional / strongest main-sample promotion candidate。** 刷新通过 DSR/PBO/RC 不能替代 12 个月
真实 OOS、Bitget exact funding 闭合或 promotion 批准，也不修改当前实盘 `PR2026-10-D-L125-V2`。

### 00.64 2026-11-12 LS39：LS23 + 60D 低波动多空 sleeve（rejected at 20bps）

LS39 在冻结 LS23 上加入一个预注册的 28D 月度低波动 pair：严格 PIT Top20 中，排除当前 H5
多头和所有 base-book overlap，按 60D 日对数收益的样本波动率排序，最低 4 名做多、最高 4 名
做空，每腿 2.5% NAV；只使用 LS23 的剩余 gross，hard total gross 1.50x。60D 继承 H5 已使用的
风险窗口，28D/4×4 是单一低换手构造，运行前未扫描 lookback、count、weight 或频率。

| 口径（20bps） | LS23 | LS39 |
|---|---:|---:|
| 终值 | 61.9150x | **64.2279x** |
| Sharpe | 1.9448 | **1.9731** |
| MDD | -39.84% | **-37.65%** |
| 强平 | 0 | **3** |
| max observed gross | 1.3308x | 1.4938x |
| gross breach hours | 0 | 0 |
| fees total | 3.1262 | 3.5980 |
| short opens / stops | 335 / 29 | 450 / 111 |

3 次强平全部是低波动 long 腿：BTC 2022-06-18（entry 37,182.05，liq 18,609.42）、ETH
2025-04-09（2,789.85，1,387.01）、TON 2025-10-10（3.1167，1.5269）。机制不是数据错误：
当前 2x isolated venue leverage + 50% long buffer 下，即使低波动 long leg 只要在两次 28D
rebalance 之间接近腰斩，也会被 isolated margin 清算。低波动信号没有消除杠杆化持仓的路径风险。

**判定：rejected。** 20bps 的表面收益/Sharpe/MDD 改善不能抵消预注册的零强平硬门槛；不运行
2/50/100bps、funding stress、路径、冷启动或 PBO/RC/DSR，事后也不删除或缩小 long leg、不添加
未注册的长止损。停止 LS39 的 60D/28D/4×4 低波动 pair 家族，不扫描替代参数。实盘继续
`PR2026-10-D-L125-V2`。

报告：`reports/derivatives_track_h5_ls23_lowvol_pair/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-lowvol-pair-design.md`。
Spec canonical SHA-256：`2bf4addfc66e2ab7fe947ce8f026f19597e8c24ee1db12ea72728b2870e976bb`。
登记哈希：`ebbd58eeadd4e7a8d8e327e81cb58784f40303e824231444a53fadf47689b4d3`。

### 00.65 2026-11-12 LS39 记账后的 DSR 再刷新

LS39 作为已评估试验进入 inventory 后，全项目 trial count 从 14,207 增至 **14,208**；Top20/2022
scope 仍为 **6,142**，因为该 20bps-only 早停试验在 inventory 的 scope 规则下只计入 all-project，
没有新增完整 Top20/2022 成本矩阵。用同一 9 候选收益面板重算，LS23 的统计量仍通过：

| scope | trial count | LS23 DSR | 门槛 |
|---|---:|---:|---:|
| family | 9 | **0.9999979** | >=0.95 |
| Top20/2022 inventory | 6,142 | **0.9714805** | >=0.95 |
| all-project inventory | 14,208 | **0.9589750** | >=0.95 |

PBO 仍为 **0.352814**，Reality Check zero p=**0.003996**、BTC p=**0.009990**。新目录为
`reports/derivatives_track_h5_profit_lock_regime_short/multiple_testing_refresh_20261112_r2/`；
manifest 中 trial summary SHA-256 为
`00e8955ec48338059298bc8e15c55479a7ddff84f068db54fce9e02b8f960df6`。§00.63 的 N=14,207 结果
保留为历史刷新，不再作为当前数字。**LS23 仍为 provisional，不接实盘；DSR 通过不能替代 12 个月
真实 OOS 或 promotion 批准。**

### 00.66 2026-11-12 LS40：LS23 多头 60D 逆波动率权重（rejected at 20bps）

LS40 只在冻结 LS23 的 H5 多头目标事件内部，按 60D 日对数收益的逆波动率重新分配同一事件 gross；
不增加资产、gross 或杠杆，单币事件不变，任一持仓缺少 45 个有效收益时整个事件保持原权重，LS22
利润保护在重分配之后执行，LS12 双空头 router、20% stop、50% buffer 和 1.50x hard gross 不变。

运行前结构审计：542 个 H5 目标事件中 380 个为多资产事件；实际运行中 380/542 个事件发生权重
变化，0 个因波动率历史不足而跳过，单事件 gross 误差最大 `2.22e-16`。

| 口径（20bps） | LS23 | LS40 |
|---|---:|---:|
| 终值 | 61.9150x | 29.8565x |
| Sharpe | 1.9448 | 1.7063 |
| MDD | -39.84% | -41.30% |
| 强平 | 0 | 0 |
| max observed gross | 1.3308x | 1.3229x |
| gross breach hours | 0 | 0 |
| fees total | 3.1262 | 2.3195 |
| profit-lock trims | 57 | 55 |

**判定：rejected。** 逆波动率确实运行了并降低了费用，但 H5 原始权重反映 12 个相位 sleeve 的
选币共识与信号合流；把这些权重当作纯风险噪声重新分配会移走 alpha。终值只剩 LS23 的约 48%，
Sharpe 低 0.2385，MDD 还恶化 1.46pp，主收益/Sharpe/MDD 三条门槛失败。不运行 2/50/100bps、
funding stress、路径、冷启动或 PBO/RC/DSR；不扫描 20/30/90/120D、等权、最小方差、协方差收缩、
asset cap 或部分资产加权。停止该权重家族，实盘继续 `PR2026-10-D-L125-V2`。

报告：`reports/derivatives_track_h5_ls23_invvol60/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-inverse-vol60-design.md`。
Spec canonical SHA-256：`54b2c217f15fc0ce2853ab1a1248e1bd68a6e9508317d2ba24523322e6d2db9b`。
登记哈希：`f3a45f6c52dfdfade21cbc32d91596d30ec1c7023d0fd503322dc849bcae534e`。

### 00.67 2026-11-12 LS40 记账后的 DSR 再刷新

LS40 进入 inventory 后，全项目 trial count 从 14,208 增至 **14,209**；Top20/2022 scope 仍为
**6,142**。同一 9 候选收益面板的最新结果：

| scope | trial count | LS23 DSR | 门槛 |
|---|---:|---:|---:|
| family | 9 | **0.9999979** | >=0.95 |
| Top20/2022 inventory | 6,142 | **0.9714805** | >=0.95 |
| all-project inventory | 14,209 | **0.9589743** | >=0.95 |

PBO 仍为 **0.352814**，Reality Check zero p=**0.003996**、BTC p=**0.009990**。当前目录：
`reports/derivatives_track_h5_profit_lock_regime_short/multiple_testing_refresh_20261112_r3/`；
trial summary SHA-256 为 `90f55c49d49013876b12b96c6ede06a073046100862ec7b8aa2b5e19d2ecd0ad`。
§00.63/§00.65 保留为历史刷新；LS23 仍为 provisional，不接实盘。

### 00.68 2026-11-12 OOS 推进到 51 天与 Bitget mark 链路修复

旧默认 mark 树 `merged_oos_20261009` 在 OOS 窗口中有四个所有资产共同缺失的小时：
2026-09-22 14:00、09-26 19:00、10-01 00:00、10-05 05:00，共 352 个资产小时缺口。
fail-closed shadow 首次因此拒绝运行；没有使用 `--allow-incomplete-marks`，而是用 Bitget 下载器
强制重拉一条新快照 `oos_refresh_20261112`。校验结果：88/88 资产覆盖 2026-09-22 →
2026-11-12 00:00 UTC，**0 missing hours、0 gap**；Bitget exact funding 最新到 2026-11-12 12:00 UTC。

shadow tracker 现在把 `raw_dir` 和 `warmup_raw_dir` 都写入 summary/manifest，默认 raw dir 改为
`merged_oos_20261112`；覆盖失败的错误也会明确打印实际 raw dir。完整四臂（L125/LS23 ×
zero/exact）写入 `reports/derivatives_track_h5_profit_lock_regime_short/shadow_oos_2026_11_12/`。

| funding | L125 | LS23 | LS23 相对差 |
|---|---:|---:|---:|
| zero | 0.9484x / -0.2743 / -17.47% | 0.9403x / -0.5584 / -17.47% | **-0.85%** |
| Bitget exact | 0.9440x / -0.3270 / -17.65% | 0.9365x / -0.6125 / -17.65% | **-0.79%** |

窗口为 51 个日行、50 个有效收益；2026-11-11 日收益为 0，因此终值和 MDD 与 50 天版本相同，
Sharpe/CAGR 因多一个零收益观测而变化。BTC 仍在 200D 上方，LS23 空头 sleeve 0 次开仓，这段
OOS 只检验利润保护，不能外推完整 LS23。51 天仅约 12 个月门槛的 14.0%，结论保持 provisional，
不修改实盘 `PR2026-10-D-L125-V2`。

报告：`reports/derivatives_track_h5_profit_lock_regime_short/shadow_oos_2026_11_12/report.md`。
汇总：`reports/derivatives_track_h5_profit_lock_regime_short/shadow_oos_2026_11_12/summary.csv`。

### 00.69 2026-11-12 LS41：H5 多头 20% 逐腿止损（rejected at 20bps）

LS41 在冻结 LS23 上增加与现有 short stop 对称的 20% long stop：每个 H5 多头腿从平均入场价
adverse 20% 时，按 Bitget hourly mark 的 open/high/low 路径触发；funding 先结算，stop 在
isolated liquidation 前执行，止损腿只能在下一次 H5 target event 再入场。20% 沿用现有 short
stop，不是新阈值扫描。

| 口径（20bps） | LS23 | LS41 |
|---|---:|---:|
| 终值 | 61.9150x | 57.2522x |
| Sharpe | 1.9448 | 1.9036 |
| MDD | -39.84% | -39.835% |
| 强平 | 0 | 0 |
| long stops | 0 | 19 |
| short stops | 29 | 29 |
| fees total | 3.1262 | 2.9556 |
| max observed gross | 1.3308x | 1.3308x |

**判定：rejected。** 19 次 long stop 证明风险控制确实执行，且 0 强平、费用略低；但止损切断了部分
随后恢复或继续上涨的 H5 龙头，重新入场又只能等下一次 target event。终值下降约 7.5%，Sharpe 低
0.0412，MDD 没有实质改善，主收益和 Sharpe 门槛失败。不运行 2/50/100bps、funding stress、路径、
冷启动或 PBO/RC/DSR；不扫描 10%/15%/25%/30%、ATR、trailing、re-entry delay 或组合 stop。
停止该固定百分比 long-stop 家族，实盘继续 `PR2026-10-D-L125-V2`。

报告：`reports/derivatives_track_h5_ls23_longstop20/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-long-stop20-design.md`。
Spec canonical SHA-256：`f6052e33c211ec1b92be6bbf39b3f9c6257dc304cb2b685a9f2183640f7ba157`。
登记哈希：`b46b7974d01fc1c6e1592ebd5b1132e9525bc1f597f65ea94bb1eb6a06fa55df`。

### 00.70 2026-11-12 LS41 记账后的 DSR 再刷新

LS41 进入 inventory 后，全项目 trial count 从 14,209 增至 **14,210**；Top20/2022 scope 仍为
**6,142**。同一 9 候选面板的最新 LS23 结果：family **0.9999979**、Top20/2022 **0.9714805**、
all-project **0.9589731**；PBO **0.352814**、Reality Check zero p=**0.003996**、BTC
p=**0.009990**。当前目录为 `multiple_testing_refresh_20261112_r4/`。LS23 仍为 provisional，不接
实盘；§00.63/§00.65/§00.67 保留为历史刷新。

### 00.71 2026-11-12 LS42：LS23 利润保护释放权重再分配（provisional，样本内最强）

LS42 在冻结 LS23 上只改变 LS22 利润保护释放出来的权重去向：当 21D trailing return >=100% 的
单一龙头被减半后，把释放权重按同一 H5 事件内其他正权重多头的相对权重分配，单币上限 60% NAV；
没有其他持仓或 cap 挡住时留现金。不新增资产、不改变 H5 选币、LS12 空头 router、20% short stop、
50% buffer、1.25x H5 或 1.50x hard gross，也不扫描触发/scale/cap。

| 成本 | L125 终值 | LS23 终值 | LS42 终值 | L125 Sharpe | LS23 Sharpe | LS42 Sharpe | LS23 MDD | LS42 MDD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | 84.4362x | **90.2632x** | 1.8249 | 2.0719 | **2.0874** | -37.57% | -37.865% |
| 20bps | 40.2200x | 61.9150x | **65.8147x** | 1.7330 | 1.9448 | **1.9589** | -39.84% | -40.134% |
| 50bps | 27.3725x | 36.8788x | **38.8335x** | 1.5790 | 1.7319 | **1.7437** | -43.45% | -43.744% |
| 100bps | 14.3794x | 15.5037x | **16.0700x** | 1.3204 | 1.3745 | **1.3825** | -49.48% | -49.775% |

20bps 相对 LS23 提高终值 **6.30%**、Sharpe **0.0141**，MDD 只恶化 **0.294pp**；四档成本均高于
同成本 LS23 和 L125。0 强平、0 gross breach，max observed gross **1.3308x**；3x short-adverse
funding 为 **66.0923x / 1.9593 / -40.253%**，仍 0 强平和 0 breach。

机制审计：57 次 trim，释放权重 **9.2432**，其中 **4.3556** 重新分配、**4.8876** 留现金；短端
target schedule 与 LS23 逐元素一致（335 opens、29 stops）。short attribution 335 episodes，
单资产最大 **23.32%**、前 3 **61.95%**。删除任一最佳年份后终值仍高于 L125；365D rolling
worst **0.8508x** 高于 L125 的 **0.7325x**；45/45 路径切片；12/12 true cash-start 引擎起点
终值和 Sharpe 胜 L125、MDD 5pp 全部通过。10 候选面板 PBO **0.2132**、RC zero p=**0.003996**、
BTC p=**0.009990**；当前 N=14,211 / 6,142 下 LS42 DSR 为 family **0.999998**、Top20/2022
**0.973375**、all-project **0.961571**。

51 天 cash-start shadow（2026-09-22 → 2026-11-11，20bps，Bitget mark，0 missing hours）：

| funding | L125 | LS23 | LS42 |
|---|---:|---:|---:|
| zero | 0.9484x / -0.2743 / -17.47% | 0.9403x / -0.5584 / -17.47% | 0.9220x / -0.7874 / -17.47% |
| Bitget exact | 0.9440x / -0.3270 / -17.65% | 0.9365x / -0.6125 / -17.65% | 0.9183x / -0.8405 / -17.65% |

LS42 在两条 funding 口径下都比 LS23 低约 1.82pp；该窗口 BTC 在 200D 上方，短端 0 次开仓，
51/365 天仅覆盖 12 个月 OOS 的 14.0%。因此 **判定：provisional**——样本内和所有可完成的
稳健性/多重检验门禁通过，是当前最强的样本内 LS42 版本，但真实 OOS 尚未支持 promotion，
不接实盘、不修改 `PR2026-10-D-L125-V2`。若后续 12 个月 OOS 仍落后 LS23，则不保留该再分配机制；
不扫描 cap、redistribution 权重、触发阈值或频率。

报告：`reports/derivatives_track_h5_ls23_profitlock_redistribute/report.md`。
Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-profit-lock-redistribute-design.md`。
Spec canonical SHA-256：`fcd155c0355dad49007be33f50d0b9f99387d3f812739c50ff915fcb855e8cc7`。
登记哈希：`4a4c9938c745f044e8650da71883a90a0f303d51fecc347107cb77f5aa7167eb`。
门禁：`reports/derivatives_track_h5_ls23_profitlock_redistribute/PR2026-11-LS42-H5-LS23-PROFITLOCK-REDISTRIBUTE/gate_audit.json`。

### 00.72 2026-11-13 LS43：利润保护只向更强 7D 持有者再分配（provisional）

LS42 在主样本内提高了终值和 Sharpe，但 2026-09-22 → 2026-11-11 的诊断显示：`NEAR` 被利润
保护减半后，LS42 把释放权重转给 `ZEC`；随后 `ZEC` 明显下跌而 `NEAR` 保持强势。只读事件审计
进一步显示，LS42 在所有事件上的接收者篮子未来 21D 平均 +4.18%，但在该 51 天窗口平均 -19.05%；
只要求接收者 7D 为正仍为 -18.24%，只有要求接收者 7D **严格强于 leader** 才会把该窗口全部留现金。

LS43 因此冻结 LS23/LS42 的其他规则，只把接收者条件改为：

```text
7D return(recipient) > 7D return(trimmed leader)
```

7D 是 H5 已有最短 horizon，不是新阈值；无合格接收者时释放权重留现金。由于 51 天窗口在预注册前
已被诊断使用，LS43 不把该窗口当作独立 OOS，promotion 仍要求预注册后的新 12 个月数据。

| 成本 | LS23 终值 | LS42 终值 | LS43 终值 | LS23 Sharpe | LS42 Sharpe | LS43 Sharpe | LS23 MDD | LS43 MDD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 84.4362x | 90.2632x | **91.2523x** | 2.0719 | 2.0874 | **2.0945** | -37.57% | -37.865% |
| 20bps | 61.9150x | 65.8147x | **66.6800x** | 1.9448 | 1.9589 | **1.9667** | -39.84% | -40.134% |
| 50bps | 36.8788x | 38.8335x | **39.4863x** | 1.7319 | 1.7437 | **1.7525** | -43.45% | -43.744% |
| 100bps | 15.5037x | 16.0700x | **16.4391x** | 1.3745 | 1.3825 | **1.3932** | -49.48% | -49.775% |

20bps 相对 LS23 提高终值 **7.70%**、Sharpe **0.0219**，MDD 恶化 **0.294pp**；相对 LS42
提高终值 **1.31%**、Sharpe **0.0078**，MDD 相同。0 强平、0 gross breach，max observed gross
**1.3308x**；3x short-adverse funding 为 **66.8826x / 1.9667 / -40.253%**。57 次 trim 中只有
14 次存在合格接收者，释放权重 9.2432，其中 1.9606 再分配、7.2826 留现金；short schedule 与
LS23 逐元素一致。删除最佳年份、365D rolling 0.8508x、45/45 paths、12/12 cash-start、short
集中度 23.35%/61.99% 均通过。11 候选 PBO **0.2532**、RC zero p=**0.003996**、BTC p=**0.008991**；
N=14,212 / 6,142 下 DSR family **0.999997**、Top20/2022 **0.974767**、all-project **0.963433**。

当前 51 天 shadow 中 LS43 的 8 次 trim 都没有合格接收者，因此 zero 口径 **0.9403x / -0.5584**
和 exact 口径 **0.9365x / -0.6125** 与 LS23 完全相同，避免了 LS42 的 1.82pp 额外损失；但这段
窗口已被诊断使用，不是独立 OOS。pre-2022 proxy 为 zero **4.4496x / 2.4105 / -22.48%**、
funding **3.1599x / 1.9261 / -22.73%**，相对 LS23 提高收益/Sharpe，但 MDD 差约 1.85–2.99pp。

关键风险：删除 2024 后 LS43 为 **33.4034x**，比 LS23 的 **34.3343x** 低 **2.71%**；相对 LS23
的样本内优势高度集中在 2024 的利润保护再分配事件。**判定：provisional**——所有可完成的预注册
样本内门禁通过，但增量年份集中且没有预注册后的独立 12 个月 OOS，不接实盘、不修改
`PR2026-10-D-L125-V2`。若独立 OOS 不保持相对 LS23 的增量，则停止整个 LS22 释放权重再分配家族，
不扫描 7D、cap、收益差或接收者数量。

报告：`reports/derivatives_track_h5_ls23_profitlock_stronger7/report.md`。
Spec：`docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-stronger7-design.md`。
Spec canonical SHA-256：`0243c48f1ad70b59b2ad04b0e616263f0e9c1154b844dea9cd68bdcd1044c466`。
登记哈希：`4b777d8f67ac920d1a4ab6a96f2f472339dca2b575c34971973c7aecd25e0114`。
门禁：`reports/derivatives_track_h5_ls23_profitlock_stronger7/PR2026-11-LS43-H5-LS23-PROFITLOCK-STRONGER7/gate_audit.json`。

### 00.73 2026-11-13 LS44：利润保护在 7D 转负时全退（rejected at 20bps）

LS44 在冻结 LS23 上只改变一个分支：LS22 21D/100% 触发后，如果被减半龙头自己的 7D trailing
return < 0，就把该腿从原来的半仓进一步降到 0；7D 仍为正时保持原来的 0.5 scale。7D 是 H5 已
使用的最短 horizon，没有扫描 5D/10D/14D 或阈值。

事件审计曾显示 7D 转负的 9 次 trim 未来 21D 均值 **-6.02%**，而 7D 非负的 48 次均值
**+0.87%**，因此该规则有明确机制动机。正式 20bps 结果：

| 指标 | LS23 | LS44 |
|---|---:|---:|
| 终值 | **61.9150x** | 60.5213x |
| Sharpe | **1.9448** | 1.9361 |
| MDD | -39.84% | **-39.056%** |
| 强平 | 0 | 0 |
| full exit | 0 | 9 |
| 释放权重 | 9.2432 | 10.4255 |
| max observed gross | 1.3308x | 1.3308x |
| fees total | 3.1262 | **3.0791** |

MDD 改善约 **0.78pp**、费用略低，但终值下降约 **2.25%**、Sharpe 低 **0.0087**，主收益和
Sharpe 门槛同时失败。**判定：rejected。** 不运行 2/50/100bps、funding stress、路径、cash-start
或 PBO/RC/DSR；停止“极端涨幅 + 短周期 breakdown 全退”家族，不扫描 confirmation window、
阈值、scale 或再分配。实盘继续 `PR2026-10-D-L125-V2`。

报告：`reports/derivatives_track_h5_ls23_profitlock_fullexit_neg7/report.md`。
Spec：`docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-fullexit-neg7-design.md`。
Spec canonical SHA-256：`2342fc34b5627bd7bd6322b2ce38e19ee0dc18b27c4562b28cf6b29e2dcbeefa`。
登记哈希：`752c7016d82e65687b1cea11ddc74ac56ba7ff4713129c39bef05a031ae21873`。


### 00.74 2026-11-13 LS45：利润保护释放权重只给更强 21D 持有者（provisional）

LS45 在 LS23 上只改变 LS22 释放权重的接收者条件：其他 H5 持有者的 21D trailing return 必须严格高于
被减半龙头的 21D return。21D 与利润保护触发使用同一 horizon；单币 cap 60% NAV，剩余留现金。

20bps 主样本：**69.2088x / 1.9846 / -39.835%**，57 次 trim 中 6 次有合格接收者，再分配
0.4803，0 强平、0 gross breach、max observed gross 1.3308x。四档成本全部高于同成本 LS23 与
L125；3x short-adverse funding 为 **69.3386x / 1.9841 / -39.951%**。

稳健性：365D rolling worst 0.8551x；45/45 路径胜 L125；但删除 2024 后与 LS23 完全相同，
45 条路径相对 LS23 只有 35/45 全通过。51 天 OOS zero **0.9403x**、exact **0.9365x**，与 LS23
相同，因为该窗口没有合格接收者。

**判定：provisional。** 主样本和成本族较强，但增量集中在 2024，且尚未运行 PBO/DSR/RC；不能把 21D 窗口当作独立
预注册证据；不接实盘。

报告：`reports/derivatives_track_h5_ls23_profitlock_stronger21/report.md`。
Spec：`docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-stronger21-design.md`。

### 00.75 2026-11-13 LS46：利润保护全退后反手 28D 空头（provisional；OOS 失败）

LS46 在 LS44 的 9 次 full-exit 事件上反手做空同一龙头：总空头 0.20x，持有 28 个日历日，
20% short stop；反转空头优先于 LS12 router，hard total gross 仍为 1.50x。

20bps 主样本：**67.6951x / 1.9919 / -34.916%**，0 强平、0 gross breach、max observed gross
1.4778x、343 个 short episodes、28 个 stop。四档成本：2bps **92.8053x / 2.1221 / -32.658%**、
50bps **39.9697x / 1.7737 / -38.709%**、100bps **16.5589x / 1.4077 / -45.371%**；3x
short-adverse funding **66.9159x / 1.9857 / -35.273%**。

稳健性：365D rolling worst **0.9279x**；删除 2024 后 **37.1511x**，高于 LS23 的 34.3343x；
45/45 路径胜 L125；12/12 真实 cash-start 终值和 Sharpe 胜 L125，MDD 12/12；short attribution
单资产最大 23.18%、前 3 63.08%；13 候选 PBO 0.193723、RC zero p=0.003996、BTC p=0.008991，
Top20/2022 DSR 0.979268、all-project DSR 0.969481（N=14,215）。

51 天 OOS（2026-09-22 → 2026-11-11，0 missing hours）：zero **0.9218x / -1.2188 / -12.54%**，
exact **0.9192x / -1.2686 / -12.70%**，均低于 LS23 的 0.9403x/0.9365x 和 L125 的
0.9484x/0.9440x。OOS 的 NEAR 反手空头在 10-04 开仓，10-11 被 20% stop 平掉，随后重开并继续
亏损。

**判定：provisional，不接实盘。** 主样本和多重检验很强，但 50 天 OOS 已经给出负结果；不能
把 2024 的主样本增量当作稳定 alpha。

报告：`reports/derivatives_track_h5_ls23_profitlock_reversal_short28/report.md`。
Spec：`docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-reversal-short28-design.md`。

### 00.76 2026-11-13 LS47：反手空头期间禁止同一资产回补（provisional；OOS 失败）

LS47 在 LS46 上只增加一条执行约束：反手空头活跃时，把同一资产从 H5 多头目标中移除，防止下一次
H5 调仓立即回补。其他 H5 资产继续正常调仓，不是冻结整个长账本。

20bps 主样本：**69.4109x / 2.0023 / -34.916%**，0 强平、0 gross breach、max observed gross
1.4778x、342 个 short episodes、31 个 stop。四档成本：2bps **94.7995x / 2.1309 / -32.658%**、
50bps **41.2416x / 1.7868 / -38.709%**、100bps **17.2669x / 1.4252 / -45.371%**；3x
short-adverse funding **68.2319x / 1.9938 / -35.273%**。

稳健性：365D rolling worst **0.9279x**；删除 2024 后 **38.7997x**，高于 LS23 的 34.3343x；
12 个真实 cash-start multiple **11/12**、Sharpe **12/12**、MDD **12/12**、0 强平/0 breach；
short attribution 单资产最大 23.46%、前 3 64.87%；14 候选 PBO **0.1775**、RC zero p
**0.003996**、BTC p **0.008991**，N=14,216 下 DSR all-project **0.971299**。

失败项：45 个月初路径相对 L125 只有 **42/45** 的终值胜出（Sharpe 45/45、MDD 45/45），
相对 LS23 只有 21/45 全通过。51 天 OOS：zero **0.9033x / -2.2542 / -11.02%**、exact
**0.9018x / -2.2925 / -11.21%**，均低于 LS23 和 L125。禁止回补降低了 OOS 回撤，但没有
避免 NEAR 反手空头在 10-11 被 20% stop 后的亏损。

**判定：provisional，不接实盘。** 主样本、成本、funding、冷启动和多重检验很强，但路径 gate
失败且 OOS 为负；下一步应研究反手空头的止损/再入场状态机，而不是直接提高空头权重或接实盘。

报告：`reports/derivatives_track_h5_ls23_profitlock_reversal_short28_noreentry/report.md`。
Spec：`docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-reversal-short28-noreentry-design.md`。

### 00.77 2026-11-13 shadow zero-funding 修复

`_cap_short_schedule_at_funding_end` 原先在 `funding_last is None` 时返回空 schedule，导致
zero-funding shadow 把所有空头（包括 LS46/LS47 的反转空头）静默关闭；LS46 的 zero OOS 因此
错误地显示 0 个 short opens。现在 zero funding 保留完整 short schedule，只有实际 funding 数据
结束日才添加 flatten target。修复后 LS46 zero OOS 为 **0.9218x / -1.2188 / -12.54%**，
LS47 zero OOS 为 **0.9033x / -2.2542 / -11.02%**；旧 zero OOS 数字作废。

### 00.78 2026-11-13 LS48：反手空头止损后同窗口禁止重开（rejected）

LS48 在 LS47 的 28D 反手空头状态机上增加：20% short stop 后，同一显式 28D 反转窗口内 routine
rebalance 不得重开；只有新的 full-exit 窗口可以重新武装。该规则把“已经失败的一次反手”与
“仍在延续的反转窗口”分开，不改变 H5、LS12 router、0.20x 反手权重或 hard gross。

20bps 主样本：**62.7698x / 1.9576 / -34.916%**；51 天 OOS exact **0.8732x**、zero **0.8749x**。
终值和 Sharpe 均低于 LS47 的 69.4109x / 2.0023，OOS 也低于 LS47 的 0.9018x / 0.9033x。

**判定：rejected。** 禁止整个窗口的所有重开确实避免了部分 stop 后亏损，但也删掉了有利的二次
入场；这不是可用的止损后状态机。未继续扫描 stop 后延迟、确认窗口或一次性重开次数。

报告：`reports/derivatives_track_h5_ls23_profitlock_reversal_short28_oneshot/`。
Spec：`docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-reversal-short28-oneshot-design.md`。

### 00.79 2026-11-13 LS49/LS50：MA21 或跌回 stop 价后再武装（rejected / null）

LS49 在 LS48 上把“窗口内禁止重开”改成“最后完整日收盘低于自身 MA21 后才重新武装”。20bps
主样本 **66.3327x / 1.9838 / -34.916%**，仍低于 LS47；OOS exact **0.8885x**、zero
**0.8901x**，也低于 LS47。判定 **rejected / partial mechanism**：MA21 重新武装改善了长期
主样本相对 LS48 的表现，但没有修复反手空头的样本外亏损。

LS50 改用实际 stop fill：只有最后完整日收盘重新跌回 stop 成交价下方才允许重开。20bps
**69.4109x / 2.0023 / -34.916%**，OOS exact **0.9018x**、zero **0.9033x**，与 LS47
逐项相同。判定 **null result**：该确认在真实 path 上没有产生任何增量，不能再把 stop retest
当成已完成的风险控制。

报告：`reports/derivatives_track_h5_ls23_profitlock_reversal_short28_ma21/`；
`reports/derivatives_track_h5_ls23_profitlock_reversal_short28_belowstop/`。

### 00.80 2026-11-13 LS51：7D 转负时跳过 LS22 半仓减半（provisional；rolling 与 100bps 失败）

LS51 只在 LS22 已触发 `21D >=100%` 后增加一个确认：如果同一 leader 的 7D trailing return
仍为负，则保留完整 leader weight；正收益或缺失 7D 价格时继续执行原来的 0.5 半仓减半。该规则
不新增资产、不改变 H5/LS12 空头/stop/leverage/gross，也不扫描确认窗口。

| 成本 | LS23 终值 | LS51 终值 | LS23 Sharpe | LS51 Sharpe | LS23 MDD | LS51 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 84.4362x | **86.1442x** | 2.0719 | **2.0780** | -37.57% | -38.374% |
| 20bps | 61.9150x | **63.0633x** | 1.9448 | **1.9504** | -39.84% | -40.644% |
| 50bps | 36.8788x | **37.4596x** | 1.7319 | **1.7366** | -43.45% | -44.253% |
| 100bps | 15.5037x | **15.6757x** | 1.3745 | **1.3778** | -49.48% | **-50.275%** |

3x short-adverse funding：**63.1782x / 1.9499 / -40.756%**，0 强平、0 gross breach。12 个真实
cash-start 的 multiple、Sharpe 和 MDD 均 12/12；45/45 个月初路径相对 L125 通过；short
attribution 单资产最大 **23.32%**、前 3 **61.95%**。PBO **0.429654**、RC zero
p=**0.003996**、BTC p=**0.008991**、Top20/2022 DSR **0.972339**、all-project DSR
**0.960124**（N=14,220）。

失败项：365D rolling worst **0.843596x**，低于 LS23 的 **0.855093x**；100bps MDD
**-50.275%**，超过预注册的 50% 上限。51 天 OOS zero **0.9727x**、exact **0.9685x**，均高于
LS23 的 0.9403x / 0.9365x，但 OOS 不能抵消两个预先声明的失败门禁。

**判定：provisional，不接实盘。** 不因 OOS 改善而放宽 rolling 或 100bps MDD；后续只改变
skip 部分持有比例，验证是否能在保留 OOS 收益的同时修复尾部。

报告：`reports/derivatives_track_h5_ls23_profitlock_skip7dneg/report.md`。
Spec：`docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-skip7dneg-design.md`。

### 00.81 2026-11-13 LS52/LS53：BTC 牛市条件与 MA21 条件（duplicate / rejected）

LS52 只在 BTC close > MA200 时启用 LS51 skip。主样本与 LS51 完全相同：**63.0633x / 1.9504 /
-40.644%**。检查全部 9 次实际 skip event 后确认它们本来就都发生在 BTC MA200 上方，因此新增
regime 条件没有任何独立增量。判定 **duplicate diagnostic**，不把相同收益重复当成第二个 alpha。

LS53 把条件改成 leader close > 自身 MA21：若 7D <0 且已跌破 MA21，则恢复原来的 0.5 trim。
20bps 主样本 **61.4684x / 1.9411 / -40.644%**，终值和 Sharpe 低于 LS23；OOS exact
**0.9685x**、zero **0.9727x** 与 LS51 相同，因为 OOS 的 NEAR skip event 全部仍在 MA21 上方。
第一次实现把 MA21 状态算在 leader 赋值之前，结果无效；修正后的 run 只作为 post-hoc
implementation check，不是独立 OOS。判定 **rejected / partial mechanism**。

报告：`reports/derivatives_track_h5_ls23_profitlock_skip7dneg_bull/`；
`reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21/`。

### 00.82 2026-11-13 LS54：MA21 skip + LS45 强 21D 再分配（provisional / partial）

LS54 组合 LS53 与 LS45：跳过 7D 负确认的减仓时保留完整 leader；未跳过且 LS22 真正减半时，把
释放权重只分配给同一 H5 事件内 21D trailing return 更强的既有持有者，单币 cap 60% NAV，
剩余留现金。skip event 不分配权重。

| 成本 | LS23 终值 | LS54 终值 | LS23 Sharpe | LS54 Sharpe | LS23 MDD | LS54 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 84.4362x | **91.9258x** | 2.0719 | **2.1001** | -37.57% | -38.374% |
| 20bps | 61.9150x | **67.2667x** | 1.9448 | **1.9727** | -39.84% | -40.644% |
| 50bps | 36.8788x | **39.9276x** | 1.7319 | **1.7593** | -43.45% | -44.253% |
| 100bps | 15.5037x | **16.6883x** | 1.3745 | **1.4011** | -49.48% | **-50.275%** |

3x short-adverse funding：**67.3782x / 1.9721 / -40.756%**，0 强平、0 gross breach，max
observed gross 1.3309x。12 个真实 cash-start multiple、Sharpe、MDD 均 **12/12**；45/45 路径
通过；short attribution 单资产最大 **23.36%**、前 3 **61.94%**。21 候选面板（20 个唯一收益流）
PBO **0.491342**、RC zero p=**0.003996**、BTC p=**0.008991**；Top20/2022 DSR **0.975855**、
all-project DSR **0.964880**（N=14,223）。删除任一最佳年份后各项仍高于同删除年份的 L125。

51 天 OOS：zero **0.9727x / -0.0804 / -17.47%**、exact **0.9685x / -0.1380 / -17.65%**，
与 LS51 相同，高于 LS23 的 0.9403x / 0.9365x。原因不是伪装的独立 OOS，而是该窗口没有产生
LS54 与 LS51 不同的非 skip 再分配事件。

失败项：365D rolling worst **0.843596x**，仍低于 LS23 的 **0.855093x**；100bps MDD
**-50.275%**，仍超过 50%。再分配提高了终值和 Sharpe，但没有修复 LS51 的尾部风险。

**判定：provisional / partial mechanism，不接实盘。** 下一候选 LS55 预注册为：在 LS54 中把
7D 负确认的完整 skip 改为保留 75% leader，其余 0.5 trim 和 LS45 再分配不变；不扫描
0.70/0.80/0.90，不降低 rolling 或 100bps MDD 门禁。

报告：`reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_redistribute/report.md`。
Spec：`docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-skip7dneg-ma21-redistribute-design.md`。

### 00.83 2026-11-13 LS55：负 7D skip 保留 75%（partial；rolling 失败）

LS55 在 LS54 上把 MA21-confirmed 的 7D 负确认 skip 从保留 100% 改成保留 75%，释放的 25%
留现金；未 skip 的 LS22 trim 仍为 0.5，并继续使用 LS45 的强 21D 既有持有者再分配。0.75 是
1.0 与 0.5 的唯一预注册中点，没有扫描其他 scale。

20bps 主样本：**67.5438x / 1.9750 / -40.239%**。四档成本：2bps **92.1984x / 2.1019 /
-37.970%**、50bps **40.1690x / 1.7623 / -43.850%**、100bps **16.8431x / 1.4052 /
-49.879%**；100bps MDD 首次回到 50% 内。3x short-adverse funding：**67.6600x / 1.9744 /
-40.354%**。45/45 路径和 12/12 真实 cash-start 通过；short attribution 单资产 23.37%、前 3
61.98%。PBO **0.483766**、RC zero p=0.003996、BTC p=0.008991；Top20/2022 DSR 0.976204、
all-project 0.965353（N=14,224）。

失败项：365D rolling worst **0.849344x**，仍低于 LS23 的 **0.855093x**；51 天 OOS zero
**0.9566x**、exact **0.9526x**，高于 LS23 但低于 LS54/LS51 的完整 skip。

**判定：partial，不接实盘。** 75% 修复了高成本 MDD，但没有修复 rolling。

报告：`reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_s075_redistribute/`。

### 00.84 2026-11-13 LS56：62.5% 中点（partial；scale 家族停止）

LS56 使用 0.5 与 0.75 的中点 0.625，其他规则与 LS55 相同。20bps 主样本 **67.6580x /
1.9759 / -40.037%**，45/45 路径通过；365D rolling worst **0.852219x**，仍低于 LS23 的
0.855093x。

逐日分解显示 LS56 的 rolling 差异几乎全部来自 **2023-02-04 APTOS** skip 后的 2/5–2/6：
相对 LS23 两天合计少 0.33% NAV，其余 364 天几乎逐日相同。继续把 scale 推向 0.5 只会退化成
LS45 再分配，而该路径的 rolling 也只有约 0.8508x，仍低于 LS23。

**判定：partial / rejected for promotion。** 不做 2/50/100bps、funding、冷启动或 PBO/RC/DSR
的“救活”运行；停止 scale 参数家族，不扫描 0.55/0.60/0.65/0.70。

报告：`reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_s0625_redistribute/`。

### 00.85 2026-11-13 LS57：1D 止跌确认的 skip（当前最强研究候选；PBO 失败）

LS57 在 LS54 上增加最后一个完整日确认：只有 7D 为负的 extreme leader **1D return >= 0** 时
才跳过 LS22 半仓减仓；如果 1D 仍为负，则 fail closed 执行原 0.5 trim。未 skip 的 trim 继续
按 LS45 只向 21D 更强的既有 H5 持有者再分配。该规则过滤了 APTOS/BCH/DOGE 的继续破位，
同时保留 2024 SHIB/XLM/HBAR 和 OOS NEAR 两次 1D 已止跌的 skip。

| 成本 | LS23 终值 | LS57 终值 | LS23 Sharpe | LS57 Sharpe | LS23 MDD | LS57 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 84.4362x | **93.9064x** | 2.0719 | **2.1088** | -37.57% | -37.566% |
| 20bps | 61.9150x | **68.8077x** | 1.9448 | **1.9819** | -39.84% | **-39.835%** |
| 50bps | 36.8788x | **40.9332x** | 1.7319 | **1.7694** | -43.45% | -43.446% |
| 100bps | 15.5037x | **17.1724x** | 1.3745 | **1.4128** | -49.48% | **-49.484%** |

3x short-adverse funding：**68.9474x / 1.9815 / -39.951%**，0 强平、0 gross breach，max
observed gross 1.3309x。365D rolling worst **0.855093x**，正好等于 LS23 并因此通过 >= 门禁；
45/45 路径通过；删除任一最佳年份后终值均高于同删除年份 L125；12/12 真实 cash-start 的
multiple、Sharpe、MDD 全部通过；short attribution 单资产 23.35%、前 3 61.96%。

51 天 OOS：zero **0.9727x / -0.0804 / -17.47%**、exact **0.9685x / -0.1380 / -17.65%**，
高于 LS23 的 0.9403x/0.9365x，也高于 L125 的 0.9484x/0.9440x。因为两次 OOS NEAR skip
的 1D 都为正，LS57 与 LS51/LS54 的 OOS 完全相同。

多重检验（24 个候选、22 个唯一收益流）：RC zero p=**0.003996**、BTC p=**0.008991**，
Top20/2022 DSR **0.977203**、all-project **0.966714**（N=14,226）；但 PBO/CSCV
**0.609307**，高于预注册 0.50 上限。CSCV 主要在 LS57、LS47、LS46、LS49 等不同机制之间
切换；把问题归因于单一参数尖峰并不成立，PBO 失败就是失败，不能通过删除 LS55/LS56 或缩小
候选面板重算。

**判定：provisional，不接实盘。** LS57 是当前唯一通过收益、Sharpe、MDD、四档成本、funding、
rolling、45 paths、12 个真实 cash-start、集中度、RC 和 DSR 的研究候选，但 PBO 失败且独立 OOS
只有 51/365 天（14.0%）。不降低 PBO 门槛，不修改实盘 `PR2026-10-D-L125-V2`。

报告：`reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_stable1d_redistribute/`。
Spec：`docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-skip7dneg-ma21-stable1d-redistribute-design.md`。

### 00.86 2026-11-13 LS57 pre-2022 压力与 50/50 混合诊断

LS57 在 2020-10-03 → 2022-01-01 的 64 条代理 mark 压力窗口：zero **3.9064x / 2.2070 /
-20.442%**；Binance funding proxy **2.7858x / 1.7339 / -24.018%**；0 强平、0 breach，
dropped rows 0。与 LS23 参考（zero 3.5113x / 2.2331 / -19.49%，funding 2.5189x / 1.7131 /
-20.88%）相比，LS57 终值更高、funding Sharpe 更高，但 MDD 差约 1–3pp。该窗口是代理 mark
压力，不是独立 12 个月 OOS，结论保持 partial-with-bounding。

另一个诊断是 50/50 资金混合 LS57 + LS47：主样本 **69.5031x / 2.0007 / -37.294%**、rolling
worst 0.8912x，51 天 OOS exact **0.9418x**（高于 LS23 0.9365x，但低于 L125 0.9440x）；
把它加入候选面板后 PBO 反而升到 **0.6569**。因此不把它预注册为新 trial，也不把等权混合当作
PBO 修复手段。

这一轮的可复用结论：LS22 利润保护的最高收益来自 skip，但任何固定的 skip/scale 规则都会在
APTOS 式继续破位和 NEAR 式止跌反转之间二选一；1D 止跌确认是目前唯一同时保留 OOS 收益和
修复 rolling 的可观察条件。下一步不能继续在同一 2022–2026 样本上扫 scale 或混合权重，而应
把 LS57 作为 provisional shadow track 积累真实 OOS，并用独立数据检验 1D 条件的稳定性。

### 00.87 2026-11-13 Maker-first execution diagnostic：平均成本改善，但未成交尾部不合格

本轮第一次把“更实时”从 alpha 调到执行层：不改变 LS57/LS23 的选币、权重、T+1、空头、
stop 或 gross，只对 LS57 的 2,524 笔历史成交逐一模拟“盘口内侧被动限价单、短窗口未成交
后 taker 回退”。主数据使用与成交同一 venue 的 Bitget mark 1h K 线，Binance 30m 只作交叉
检查。主配置预注册为 **5bps offset / 2 bars timeout / 1bp through / 2bps maker / 20bps
taker / 20bps baseline**。

| 指标 | Bitget mark 主结果 |
|---|---:|
| 成交名义覆盖率 | **100%** |
| 名义加权被动成交率 | **91.40%** |
| 有效成本 | **8.45bps** |
| 相对 20bps 基线改善 | **+11.55bps** |
| 改善为正的名义占比 | **91.41%** |
| 未成交回退名义占比 | 8.60% |
| 未成交回退改善中位数 | **-76.26bps** |
| 未成交回退改善 5% 分位 | **-278.55bps** |

主配置 2022–2026 各年改善 **+16.15 / +10.67 / +12.25 / +16.32 / +7.67bps**，买入
+10.08bps、卖出 +12.96bps。Binance 30m 交叉检查覆盖率仅 **81.61%**，但方向一致：
有效成本 6.54bps、改善 +13.46bps。

**判定：执行诊断平均通过，尾部失败，不接实盘。** 8.6% 的未成交回退在不利行情中承担了
很大的追价成本；mark K 线触碰也不等于真实 maker 成交，且没有队列位置、部分成交、撤单延迟、
ADL 或交易所拒绝。下一步只能是真实盘口/订单簿 shadow，并测试“首小时逆向移动 guard”，
不能把 8.45bps 直接写进 live 成本假设或 LS57 的 promotion 结论。

报告：`reports/derivatives_track_maker_execution_diagnostic/`；
交叉检查：`reports/derivatives_track_maker_execution_diagnostic_binance_30m/`；
Spec：`docs/superpowers/specs/2026-11-13-maker-first-execution-diagnostic-design.md`。

### 00.88 2026-11-13 利润保护后续诊断：BTC fallback 与深回撤退出均被拒

在 LS57 之后又做了四个机制诊断，全部使用同一 20bps/T+1 +3h/Bitget mark/funding skip
口径；这些结果标记为 exploratory，不新增 promotion 结论：

| 变体 | 终值 | Sharpe | MDD | 判定 |
|---|---:|---:|---:|---|
| LS45 基线 | **69.2088x** | 1.9846 | -39.835% | 参考 |
| LS57 基线 | 68.8077x | 1.9819 | -39.835% | 参考 |
| 释放权重转 BTC（MA200 上） | 68.0224x | 1.9715 | -40.023% | rejected |
| 释放权重转 BTC（MA100 上） | 64.5174x | 1.9489 | -40.023% | rejected |
| 7D < -5% 时全退 | 67.5924x | 1.9759 | -39.056% | rejected |
| 7D < -8% 时全退 | 67.8148x | 1.9767 | -39.835% | rejected |
| 7D < -10% 时全退 | 68.3776x | 1.9802 | -39.835% | rejected |
| 只跳过 7D >= -10% 的浅回撤 | 69.8013x | 1.9881 | -39.835% | post-hoc diagnostic |

BTC fallback 想解决 bull market 的 cash drag，但把利润保护释放权重重新暴露到 BTC beta，
既没有提高终值也没有改善 MDD。深 7D full exit 在 -5% 档改善了约 0.78pp MDD，却牺牲了
更多收益；更深的 -10% 档仍低于 LS45。`7D >= -10%` 浅回撤版本是 **事后扫描**，只在
2024 SHIB 事件上比 LS57 少一次 skip，主样本略高；当前 OOS 窗口没有该事件，因此 OOS 与
LS57 相同，不是新的独立证据。另一个“post-skip MA21 日内/日线 stop”在测试路径上没有产生
可执行的非重复目标，是 null diagnostic。

**判定：不接实盘，不修改 LS57/LS45 状态。** 利润保护阈值扫描到此停止；后续优先研究
执行成本、真实盘口和独立 OOS，而不是继续在同一 2022–2026 样本上调 7D/1D 阈值。

报告：`reports/derivatives_track_profitlock_followup_diagnostics/report.md`。

### 00.89 2026-11-13 Maker-first adverse guard：尾部改善，仍是 shadow 执行候选

上一节 maker-first 的平均成本改善成立，但未成交回退尾部太大。本节预注册一个**事后
follow-up**：每根未成交 bar 检查相对 reference 的 adverse move，若达到 **30bps**，立即在
该 bar close 以 taker 回退，而不是继续等第二根 bar。其余仍为 5bps offset / 2 bars /
1bp through / 2bps maker / 20bps taker。

| 指标 | 无 guard | 30bps guard |
|---|---:|---:|
| 被动成交率 | 91.40% | **90.48%** |
| 有效成本 | 8.45bps | **7.06bps** |
| 相对基线改善 | +11.55bps | **+12.94bps** |
| 未成交名义占比 | 8.60% | 9.52% |
| 未成交改善中位数 | -76.26bps | **-64.17bps** |
| 未成交改善 5% 分位 | -278.55bps | **-214.08bps** |

2022–2026 年度改善 **+15.00 / +14.97 / +11.91 / +14.15 / +12.05bps**，五年全为正。
Binance 30m 交叉检查覆盖率 81.61%，改善 +11.46bps，方向一致。Bitget mark 的名义覆盖率
仍为 100%。

**判定：follow-up 通过，仍是 shadow 执行候选，不接实盘。** 30bps guard 改善了平均成本和
尾部，但没有解决 mark K 线触碰、队列位置、部分成交、撤单延迟和交易所拒绝。下一步必须做
真实盘口/订单簿 shadow；不能把 7.06bps 直接写进 live 成本、LS57 的 DSR 或 promotion 结论。

报告：`reports/derivatives_track_maker_execution_guard30_bps/`；
交叉检查：`reports/derivatives_track_maker_execution_guard30_bps_binance_30m/`；
Spec：`docs/superpowers/specs/2026-11-13-maker-adverse-guard-followup-design.md`。

### 00.90 2026-11-13 真实盘口快照：500 USDT 账户的可见冲击远小于手续费

本轮把执行研究从 mark K 线推进到真实 Bitget v3 order book。新增只读采集器，按最新目标账本的
非零 change leg 从一个参考权益计算订单名义，并逐档走真实 bid/ask 深度；不发送、不撤销、不修改
任何订单。首次 smoke 采集为 2026-11-13（本地）的 12 个快照、3 个平仓腿，全部成功，0 错误。

参考权益 **500 USDT**，使用最新 2026-11-06 信号（11-07 已平仓）的 CLOSE 腿：

| asset | requested USDT | median spread | p95 spread | median impact | p95 impact | max impact | min fill |
|---|---:|---:|---:|---:|---:|---:|---:|
| HYPE | 52.08 | 0.209bps | 0.759bps | 0.000bps | 0.240bps | 0.434bps | 100% |
| XMR | 234.38 | 4.033bps | 6.173bps | 0.180bps | 0.419bps | 0.464bps | 100% |
| NEAR | 14.97 | 0.292bps | 0.292bps | 0.000bps | 0.000bps | 0.000bps | 100% |

25bps 内的可见深度相对订单中位数分别为 **2,095x / 927x / 13,495x**。结论是：在 500 USDT
规模下，主要问题不是订单打穿盘口；即使 XMR 的最差可见冲击也只有约 0.46bps，而交易所 taker
费率约 6bps。maker-first 的平均改善必须来自费率与逆向选择的权衡，不能被“盘口太薄”这一错误
直觉驱动。

**判定：执行基础设施 smoke 通过，不能据此声称真实成交质量。** 这是 off-window 快照，不是
01:05 UTC 调仓时点的成交证据；没有真实挂单、队列位置、部分成交、撤单延迟或交易所拒绝。
需要围绕实际调仓持续采集，且真实 maker 单只能做 shadow，不能直接改 live executor。

报告：`reports/derivatives_track_execution_microstructure_20261113/`。
脚本：`scripts/record_execution_microstructure.py`；核心深度计算：`src/atlas20/derivatives/orderbook.py`。

### 00.91 2026-11-13 LS58：DVOL>75 多头风险关闭（rejected；样本外 proxy 决定性失败）

在 LS57 上只增加一个独立信息源：Deribit BTC DVOL 日收盘 > 75 时，把 H5 多头目标全退；
LS57 的空头、利润保护、20% short stop、gross cap 和 T+1 +3h 不变。数据由 Deribit 公共 API
落盘，20bps 主样本 **73.8729x / 2.0132 / -39.835%**，高于 LS57 的 **68.8077x / 1.9819 /
-39.835%**；2/50/100bps 为 **100.9431x / 43.8564x / 18.3357x**，Sharpe 分别为
**2.1407 / 1.7996 / 1.4410**，0 强平、0 gross breach。3x short-adverse funding 为
**73.8190x / 2.0115 / -39.951%**。365D rolling worst 0.855093x，45/45 paths、12/12
真实 cash-start、short concentration 均通过。

但增量并不是跨 regime 的：DVOL overlay 只在 **10 个 target event** 改变 gross，其中
2022-11-08 事前 gross 已经为 0，其余 9 个事件全部落在 **2024 年 3 月**。删除 2024 后
LS58 与 LS57 完全相等（34.3343x），所以主样本改善来自单一 episode。

更关键的是独立 proxy 窗口：2021-03-24 → 2022-01-01，zero funding，LS57 **1.8872x /
1.8907 / -20.44%**，LS58 **1.0738x / 1.9112 / -0.12%**；收益相对少 **43.1%**。DVOL
在该窗口触发 79 次，反复把 H5 多头卖在反弹前；MDD 看起来极低只是因为长期空仓。这是
“高 DVOL 同时对应崩盘和反弹”的直接反例，说明水平阈值不能单独作为方向性退出信号。

把 LS58 加入同一候选面板后，PBO/CSCV 从 LS57 的 0.609307 升至 **0.617965**，LS58 在
924 个 split 中仍是最高被选中次数（278），但整体 procedure 继续失败；试验台账增至
**N=14,227**。这不是可以靠“再加一个指标”修掉的问题。

**判定：rejected。** 不扫描 70/75/80/90、半仓/全仓、MA 确认或更长确认天数；不修改 LS57，
不接实盘，不把主样本改善包装成通过。下一步若继续使用 DVOL，应研究它与价格/波动确认的
交互，或把它用于执行时点而不是持续性风险关闭。

报告：`reports/derivatives_track_h5_ls23_dvol75_riskoff/report.md`。
Spec：`docs/superpowers/specs/2026-11-13-h5-ls23-dvol75-riskooff-design.md`。
数据：`data/raw/deribit_dvol/BTC_DVOL_1D.csv`；下载器：`scripts/download_deribit_dvol.py`。

### 00.92 2026-11-13 Bitget 官方逐笔成交 + L1 深度 maker shadow（通过 shadow 门槛，未接实盘）

本轮把 maker-first 从 mark K 线触碰推进到 Bitget 官方历史逐笔成交与 Level1 深度：不改变 LS57 的
选币、权重、T+1、空头、利润保护或 stop，只对 2026-01-01 → 2026-09-21 的 443 个 LS57 target
trade 重新模拟 500 USDT 参考账户的执行。预注册主口径为 **5bps offset / 2h timeout / 1bp
through / 30bps adverse guard / 2bps maker fee / 20bps taker fee / L1 reference max age
10min**。

| 指标 | 主结果 |
|---|---:|
| expected events | **443** |
| covered events | **433** |
| 未覆盖 | 10 个低于 Bitget 5 USDT 最小名义的 trade，合计仅 24.53 USDT |
| 名义覆盖率 | **99.9938%** |
| strict maker fill rate | **74.9361%** |
| taker fallback notional | **99,653.34 USDT / 397,596.57 USDT** |
| notional-weighted strict effective cost | **10.4467bps** |
| 相对 20bps immediate taker 改善 | **+9.5533bps** |
| strict effective cost p95 | **50.8996bps** |
| filled / guard / timeout | **336 / 93 / 4** |

分方向，买入 189 个 event：strict fill **69.37%**、加权成本 **13.3621bps**、改善
**+6.6379bps**；卖出 244 个 event：fill **80.43%**、成本 **7.5676bps**、改善
**+12.4324bps**。买入侧未达到 70% fill，但整体与两侧收益改善均通过预注册门槛，因此不能让
“整体通过”掩盖买入侧更差的成交质量。分月加权改善全部为正，但 2026-04 仅 **+2.85bps**、
2026-08 为 **+5.47bps**，成本尾部仍然是真实约束。

稳健性：38 个周中 **34 个**加权改善为正、**27 个**至少 +5bps。最大节省贡献资产是 ZEC
（**38.38%** of total savings），剔除 ZEC 后仍有 **+8.6577bps**；剔除 3 个负贡献资产后为
**+12.2708bps**。因此结果不是单一资产或单周造成的，但 ZEC/HYPE 的集中度、买入侧 fill
不足和 5% 成本分位约 -30.9bps 必须保留为限制。

数据链本轮修复了六个会直接污染结论的问题：外层 zip 内再包 xlsx、成交 zip 内 CSV 未解包、
Bitget 历史文件使用 UTC+8 日切而非 UTC 日切、2h 窗口跨日、depth/trade cache 按文件名跨 symbol
冲突、以及 SHIB depth 价格比逐笔成交大 1000 倍。最后一项通过“仅接受 10 的整数次幂、且校正后
mid 与 contemporaneous trade median 相差不超过 2%”的显式校验修复，不能校正的情况 fail closed；
全样本仅 SHIB 的 7 个 event 触发 x1000。重复 `trade_id`、时间倒序、缺失 depth/trade 和
格式损坏均显式报错，不再静默跳过。

**判定：PASS（shadow execution candidate only），不接实盘。** strict fill 仍不能证明队列位置、
hidden liquidity、撤单延迟、部分成交优先级、ADL 或交易所拒绝；2h 未成交回退和 30bps guard
的真实尾部也没有被消除。下一步应做 maker fill haircut 敏感性（例如只承认 25%/50%/75% 的
逐笔可成交量），验证改善是否仍大于 5bps；再考虑真实小单挂撤单 shadow，且必须走独立审批，不能
直接把该成本假设写进 live executor 或 LS57 promotion。

报告：`reports/derivatives_track_trade_tape_maker_shadow_2026/report.md`；
Spec：`docs/superpowers/specs/2026-11-13-bitget-trade-tape-maker-shadow-design.md`；
核心解析/模拟：`src/atlas20/derivatives/trade_tape.py`；
脚本：`scripts/simulate_bitget_trade_tape_maker.py`。

### 00.93 2026-11-13 Maker fill haircut 25/50/75%：整体通过，买入侧暴露弱点

EX3 的 strict fill 仍把每笔穿价主动成交的完整 `volume(quote)` 当作可获得成交量，无法证明队列位置。
本轮不猜真实 queue，而是在同一次数据读取中把每笔可成交量统一乘以 **25% / 50% / 75%** haircut，
未获得的部分继续等待并在 timeout/guard 时 taker 回退。数据、UTC+8 日切、价格尺度校验和
fail-closed 规则均与 EX3 相同，样本仍是 2026-01-01 → 2026-09-21 的 433 个覆盖 event。

| haircut | maker fill | 加权有效成本 | 相对 20bps taker 改善 | guard notional | timeout event |
|---:|---:|---:|---:|---:|---:|
| **25%** | **70.09%** | **13.0164bps** | **+6.9836bps** | 29.91% | 1.15% |
| 50% | 73.01% | 11.4683bps | +8.5317bps | 26.99% | 1.15% |
| 75% | 74.25% | 10.8107bps | +9.1893bps | 25.75% | 0.92% |

三个 haircut 场景按预注册方向单调改善，25% 仍高于 +5bps；有效成本 p95 约 **50.97bps**。
分方向的结果暴露了真正的问题：25% haircut 下卖出侧改善 **+9.8221bps**、fill **75.45%**，
买入侧改善只有 **+4.1094bps**、fill **64.66%**。进一步拆 action，买入侧的主要拖累不是
short-close/减仓，而是 **long open**：14 个 event、54,810 USDT 名义，25% haircut 下改善
**-6.0770bps**；short close 为 **+8.0168bps**，long increase 为 **+7.7374bps**。这不是
“maker 完全无效”，而是开多腿的逆向选择明显更强。

25% haircut 的分组稳健性也弱于 EX3：38 周中 **31 周**改善为正、**25 周**至少 +5bps（EX3 为
34/38 与 27/38）；2026-04 仅 **+0.5660bps**、2026-08 **+2.1600bps**。最大节省贡献仍是
ZEC（39.07%），剔除 ZEC 后 25% haircut 改善 **+6.2572bps**，仍高于 5bps，但安全边际明显缩小。
因此不能把 EX3 的 9.55bps 当作真实可实现成本，25% 的 6.98bps 是更合适的保守执行上界。

**判定：PASS under 25% volume-capacity haircut（shadow execution candidate only），不接实盘。**
整体通过不能掩盖买入侧 +4.11bps 和 long-open 负改善；也不能证明 hidden liquidity、真实 queue、
撤单延迟或部分成交优先级。下一步应先在独立的 pre-2026 样本上检验一个事前可解释的
side/action-aware 路由：long open 用 taker，其余保持 maker；不得在 2026 结果上直接调 offset
或只挑买/卖方向来制造通过。

报告：`reports/derivatives_track_trade_tape_maker_haircut_2026/report.md`；
Spec：`docs/superpowers/specs/2026-11-13-bitget-trade-tape-maker-haircut-design.md`。

### 00.94 2026-11-13 Long-open taker routing 独立确认：机制反转，rejected

EX4 的 2026 discovery 样本显示 long open 是 maker 的主要拖累：25% haircut 下该组 **-6.0770bps**。
因此本轮在完全早于 2026 的 **2024-07-01 → 2025-12-31** 确认样本上，预注册检验一个单一规则：
long open 立即 taker，其他 leg 保持 25% haircut maker-first；不扫描资产、月份、offset 或其他 action。

确认样本有 807 个 LS57 target trade、684 个达到 venue minimum，最终覆盖 **622 个 event**；
事件覆盖 **77.08%**、名义覆盖 **93.42%**。62 个未覆盖 event 均显式记录，主要是历史成交文件
窗口为空或缺失 depth；没有静默补齐。全 maker、25% haircut 的确认样本基线改善为
**+10.4015bps**，比 2026 的 +6.9836bps 更好。

但 long-open 机制在确认样本中完全反转：

| 指标 | 2026 discovery | 2024-07→2025-12 确认 |
|---|---:|---:|
| long-open events | 14 | **40** |
| long-open requested notional | 54,810 USDT | **60,219 USDT** |
| long-open 25% maker 改善 | **-6.0770bps** | **+15.2366bps** |
| 全体 baseline 改善 | +6.9836bps | +10.4015bps |
| long-open taker 后改善 | +7.8214bps | **+7.6933bps** |
| 路由增益 vs baseline | **+0.8377bps** | **-2.7081bps** |

确认样本中 long-open taker 路由把 maker fill 从 76.57% 降到 61.38%，taker 名义占比从
23.43% 升到 38.62%，但 long-open 本身原本是正改善组，因此路由只是主动放弃收益。2024-25
的分月结果有 **12 / 18 个月**路由变差，最大单月负贡献 **-7.54bps**；这不是可以靠“只看 2026”解释的
小噪声，而是执行收益本身具有明显 phase dependence。

**判定：rejected。** long-open taker routing 不接实盘，也不继续扫描“所有 buy taker”、
资产白名单、月份条件、timeout 或 haircut 组合。保留全 leg maker-first 作为 provisional
shadow execution candidate；任何 side/action 路由都必须先有真实小单挂撤单或独立实时队列数据，
不能从单一年份的事后分组直接上线。

报告：`reports/derivatives_track_trade_tape_maker_routing_confirm_2024_2025/routing/report.md`；
2026 discovery 对照：`reports/derivatives_track_trade_tape_maker_haircut_2026/routing_long_open_discovery/report.md`；
Spec：`docs/superpowers/specs/2026-11-13-bitget-maker-routing-confirmatory-design.md`。

### 00.95 2026-11-13 将 25% haircut 成本回填 LS57：执行改善的收益价值可量化

EX4 的 2026 真实逐笔样本给出 25% volume-capacity haircut 下加权有效成本 **13.0164bps**。
本轮不改变 LS57 的任何交易规则，只把同一 2022–2026 回测的每边成本从 20bps 替换为 13.0164bps，
量化如果没有额外杠杆、且 maker-first 真能达到该成本水平，收益会怎样。

| 口径 | 终值 | Sharpe | MDD | 费用 | funding |
|---|---:|---:|---:|---:|---:|
| LS57 @20bps | 68.8077x | 1.9819 | -39.835% | 3.4142 | -0.8011 |
| LS57 @13.0164bps | **77.6356x** | **2.0312** | **-38.964%** | 2.4458 | -0.8720 |

相对提升 **+8.8279x（+12.83%）**、Sharpe **+0.0493**、MDD 改善 **+0.871pp**；
0 强平、0 gross breach，最大 observed gross **1.3299x**，与 20bps 口径的仓位和交易集合相同。
这不是新的 alpha，也不改变 LS57 的 PBO 0.609、pre-2022 proxy 和 12 个月 OOS 限制；它只是证明
执行成本从 20bps 降到可解释的 13.0164bps 时，现有候选的复利收益有实质改善。

**判定：PASS（execution translation，shadow only），不接实盘。** 13.0164bps 来自单一
2026 execution 样本，不能外推成 2022–2026 已验证成本；真实 queue、hidden liquidity、
部分成交、撤单延迟和 ADL 仍未被证明。最高只能把 13.0164bps 作为 shadow 成本敏感性，不能修改
`PR2026-10-D-L125-V2` 的 live cost assumption，也不能据此把 LS57 升为 live。

报告：`reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_stable1d_redistribute_cost130164/PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE/report.md`；
Spec：`docs/superpowers/specs/2026-11-13-ls57-maker25-cost-translation-design.md`。

### 00.96 2026-11-13 LS60：PIT Top20 短周期 residual momentum 筛查失败

本轮首次独立检验 strict PIT CMC Top20 内的 residual momentum：用 60D BTC beta 去除市场共同
波动，按 28D residual return 排序，做多最强 4 个、做空最弱 4 个，每腿 12.5% NAV，gross
固定 1.0x，T+1 生效并按换手收费；不计 funding，也不接实盘。主样本
2022-01-01 → 2026-09-21 共 62 个有效 rebalance。

| 成本 | 终值 | Sharpe | MDD |
|---|---:|---:|---:|
| 2bps | 0.6365x | -0.1389 | -50.48% |
| 20bps | **0.5346x** | **-0.2515** | **-57.04%** |
| 50bps | 0.3992x | -0.4385 | -67.63% |
| 100bps | 0.2446x | -0.7444 | -79.97% |

同期 BTC buy-and-hold 为 1.8161x / 0.5026 / -66.89%。LS60 在 2bps 已经亏损，成本不是主因；
年份收益为 2022 -19.27%、2023 +6.39%、2024 -36.18%、2025 +7.72%、2026 YTD -9.46%，
前后半段都为负。组合平均净 beta 约 -0.036，但逐日绝对净 beta 均值为 0.147，说明它不是
完全 beta-neutral，不过解释不了全部亏损。

资产贡献分解补上了原报告遗漏的规格要求：FTX token +0.262、BCH +0.241、ATOM +0.214，而
NEAR -0.283、LUNA -0.248、XLM -0.246。亏损不是单一资产故障，但赢家和输家贡献都很集中，
说明该构造对少数跳跃式残差事件敏感。贡献 CSV 现在写入
`asset_contributions.csv`，报告只摘录最大正负项。

**判定：该冻结配置 rejected。** 不接实盘，不修改 LS57/L125-V2。此失败只否定
`60D beta + 28D residual momentum` 这一格，不终止 residual-factor 研究；后续假设重新登记。

报告：`reports/residual_momentum_screen_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-residual-momentum-screen-design.md`。

### 00.97 2026-11-13 LS61：同口径 residual reversal 三段样本均不合格

LS60 的 20bps Sharpe 为负，因此把同一信号的符号翻转，检验“低 residual 赢家继续赢、高
residual 输家继续输”的反向假设。参数、资产数、gross、T+1 和成本口径完全冻结，只把方向
翻成 low-minus-high；主确认样本为 2020-09-03 → 2021-12-31。按 owner 的最新要求，即使主确认
失败也继续跑完 2022–2026 与 2024–2026，避免用旧 stop rule 阻断研究记录。

| 样本 | 20bps 终值 | 20bps Sharpe | 20bps MDD | 2bps Sharpe |
|---|---:|---:|---:|---:|
| 2020-09→2021-12 | 0.6632x | -0.5237 | -49.78% | -0.4510 |
| 2022-01→2026-09 | 0.7463x | 0.0012 | -61.66% | 0.1138 |
| 2024-01→2026-09 | 1.1837x | 0.3734 | -35.78% | 0.5255 |

主样本的逐年收益为 2022 -17.75%、2023 -17.16%、2024 +34.51%、2025 -18.83%、
2026 YTD +0.32%，完全依赖 2024；2024–2026 子样本又由 2024 的 +51.56% 支配，2026 YTD
为 -23.77%。同期 BTC 在 2024–2026 为 1.9608x / 0.7554 / -53.06%，LS61 仍明显落后。
资产贡献同样集中：NEAR +0.244、XLM +0.217、SOL +0.124，说明结果不是宽基因子。

**判定：rejected。** residual momentum 与 residual reversal 在独立和主样本之间没有稳定符号，
同一 28D 因子不能直接改成方向性空头或多头 sleeve。下一步改为检验更经典、经济含义更明确的
11M-1M residual momentum（跳过最近一个月），并把 discovery 与 validation 分开；不把
LS61 的 2024 单年反弹当成可交易边缘。

报告：`reports/residual_reversal_screen_pre2022/`、
`reports/residual_reversal_screen_2022/`、`reports/residual_reversal_screen_2024_2026/`；
Spec：`docs/superpowers/specs/2026-11-13-residual-reversal-screen-design.md`。

### 00.98 2026-11-13 LS63：30m BTC shock lead-lag 有预测相关，但存在 phase 选择偏差

在 Binance 30m 的 32 个可用 PIT Top20 资产上，先做纯预测诊断：用 30D rolling BTC beta 去掉
市场冲击，计算 BTC shock 后的 relative gap，并检验 gap 与下一段 beta-adjusted residual 的
cross-sectional rank IC。样本 2022-01-01 → 2026-09-30，共 **83,230 根 30m bar**；discovery
2022–2023，validation 2024–2026-09。

48 个 `(signal window 1/2/4/8 bars) × (future horizon 1/2/4/8) × (shock bucket all/1.5σ/2.5σ)`
cell 中有 **41/48** 个在 discovery 和 validation 同时出现负 IC、正 contrarian spread。最显眼的
`k=4,h=8,|z|>=2.5` discovery spread **20.07bps**、validation **18.57bps**；`k=2,h=4,|z|>=2.5`
分别为 **11.91 / 3.55bps**。这看起来像可交易 lead-lag，但诊断脚本最初误把 30m bar reindex 到
日频，只得到 1,734 根 bar；修复后才是完整 83,230 根。该工程 bug 已由测试和报告固定。

更重要的是，诊断的非重叠抽样固定从 bar 0 开始，相当于暗含一个未登记的 30m/2h/4h time-of-day
phase。后续 phase 分解显示 edge 对 phase 很敏感，因此这一节只能作为**发现线索**，不能当作
独立可交易结论。

报告：`reports/intraday_btc_leadlag_diagnostic_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-intraday-btc-leadlag-diagnostic-design.md`。

### 00.99 2026-11-13 LS64：重叠 tranche lead-lag backtest 被集群信号和费用吃掉（rejected）

LS64 把诊断转成可执行组合：每根 bar 在 `|z|>=2.5` 时可开一个 `1/h` gross tranche，最多 h 个
同时活跃，long low-gap / short high-gap，下一根 open 入场，逐 30m open→close 记账，成本
6/12/20bps per side。四个 cell 加 ensemble 全部 rejected。

| 变体 | 6bps full 终值 | 6bps Sharpe | 6bps MDD | 12bps full 终值 |
|---|---:|---:|---:|---:|
| `LL_4_8`（最好） | 0.7800x | -1.6144 | -23.16% | 0.5197x |
| `LL_2_8` | 0.7334x | -2.2439 | -27.33% | 0.4944x |
| `LL_2_4` | 0.5426x | -2.9473 | -46.38% | 0.2465x |
| `LL_1_4` | 0.5691x | -2.6943 | -43.69% | 0.2716x |
| ensemble | 0.6490x | -2.8253 | -35.56% | 0.3626x |

原因很清楚：每根 bar 都允许开仓会把同一次 BTC shock 拆成许多重叠、陈旧、相关的信号；平均
active gross 只有约 **3%**，但 4 年多累计 turnover 达 **657–1,315x**，成本超过 gross alpha。
这说明“信号有预测相关”不等于“这个执行结构能赚钱”。

报告：`reports/intraday_btc_leadlag_backtest_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-intraday-btc-leadlag-backtest-design.md`。

### 00.100 2026-11-13 LS65：单事件 full-gross lead-lag 仍然失败（rejected）

LS65 试图消除重叠：一次 BTC shock 只做一个 full-gross 事件，持有 h 根 bar，期间跳过新信号。
四个 cell 仍然全部失败。最好的 `LL_4_8` 在 6bps full 为 **0.3754x / -1.9178 / -67.75%**，
12bps 仅 **0.1071x**；ensemble 6bps **0.2380x / -2.9309 / -77.12%**。事件数约 1,044–1,785，
平均 gross 8.6%–12.7%，但单事件平均 gross PnL 只有约 **0.5–2.9bps**，低于一次 round-trip
的 12bps。单事件并没有把预测 edge 提升到成本之上。

报告：`reports/intraday_btc_leadlag_single_event_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-intraday-leadlag-single-event-design.md`。

### 00.101 2026-11-13 LS66：phase-0 / 10% tail / 3.0–3.5σ follow-up 仅为 watch

在 LS63–LS65 的 phase 诊断后，登记一个明确带选择偏差的 follow-up：固定 phase-0 UTC 日程，
tail 10%，阈值 3.0/3.5σ，k=2/4、h=8，单事件 full gross。`LL_P4_8_T35` 是唯一接近可用的 cell：

| 口径 | 终值 | Sharpe | MDD | 事件数 |
|---|---:|---:|---:|---:|
| 6bps/side full | **1.5548x** | **0.9612** | **-4.28%** | 134 |
| 12bps/side full | 1.3240x | 0.6331 | -4.28% | 134 |
| 20bps/side full | 1.0685x | 0.1857 | -8.40% | 134 |

ensemble 在 6bps 为 1.2225x / 0.4679 / -7.75%，12bps 为 1.0109x / 0.0690 / -11.94%。它只有
约 **28 个事件/年**、平均 active gross **1.3%**，并非高收益策略；且 phase、tail、threshold 都是
在前一轮结果之后才确定，validation 不能算 fresh OOS。

把它作为低相关 sleeve 与 LS57 日收益做资金混合：相关性只有 **0.018**，但 2.5%/5%/10%/20%
配置把 LS57 的 68.8077x 降到 63.5039x/58.5666x/49.7051x/35.4896x，只把 Sharpe 从 1.9814
抬到 1.9860/1.9909/2.0012/2.0247，MDD 从 -39.84% 改善到 -39.00/-38.16/-36.45/-32.92%。
这符合它的防守属性，但不符合 owner 当前“收益提升”的目标。

**判定：watch，不接实盘、不并入 LS57。** 这条研究线的可复用结论是：真正的 intraday
lead-lag 在高费率和 phase 不确定下没有足够净 edge；继续研究时应优先寻找更高频且能降低单次
round-trip 的机制，或改用 maker/queue 的真实成交数据，而不是拿 phase-0 的 1.55x 当实盘信号。

报告：`reports/intraday_btc_leadlag_phase_tail_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-intraday-leadlag-phase-tail-design.md`。

### 00.102 2026-11-13 LS67：LS66 fresh OOS 仅 4 个事件，正收益但证据不足

用 2026-09-01 → 2026-11-13 的 **未参与历史筛选** Binance 30m 数据，对 LS66 的四个冻结 cell
做 fresh OOS；beta warm-up 用 2026-09-01 起，事件必须在 2026-10-01 后入场并完整体退出。
新 cache 有 30/32 个资产；MATIC（Binance spot pair 已不可用）和 XMR 缺失，未用历史 bar
拼接、未零填充，报告中显式记录。

| 变体 | 6bps OOS | 12bps OOS | 20bps OOS | 事件数 |
|---|---:|---:|---:|---:|
| `LL_P4_8_T35` | **1.0107x / Sharpe 1.4159 / MDD -0.94%** | 1.0059x / 0.8075 / -1.05% | 0.9995x | 4 |
| `LL_P4_8_T30` | 1.0003x / 0.0725 / -1.54% | 0.9943x | 0.9864x | 5 |
| `LL_P2_8_T35` | 0.9870x | 0.9847x | 0.9815x | 2 |
| ensemble | 0.9963x / -1.1095 / -0.76% | 0.9924x | 0.9873x | 13 |

同期 BTC 为 **0.8409x / Sharpe -4.1561**，因此 `LL_P4_8_T35` 的防守方向在 OOS 是对的；
但 44 天只有 **4 个事件**，12bps 也只剩 0.59% 的毛收益，20bps 已转负。这个窗口不足以把
LS66 从 watch 升级为 shadow，更不能接实盘。它的价值是：在不改 phase/tail/threshold 的前提下，
看到了一次方向一致的 live-like 小样本，而不是证明 alpha 稳定。

**判定：保持 watch，不 promotion。** 不再用同一个 6 周窗口调 phase/tail/threshold；后续若要
提高统计功效，应继续记录新的实时事件，或换成更低单次成本的 maker/queue 执行，而不是把
4 个事件的 Sharpe 1.42 当成年化能力。

报告：`reports/intraday_btc_leadlag_fresh_oos_20261113/`；Spec：
`docs/superpowers/specs/2026-11-13-intraday-leadlag-fresh-oos-design.md`。

### 00.103 2026-11-13 LS68：日频 BTC shock relative-gap 反转假设失败，但反向动量方向留下新假设

LS63–LS67 的 30m lead-lag 成本过高，因此 LS68 把相同经济机制降到日频：BTC 发生
1/3/5/10 日冲击后，按相对 BTC beta 的 residual gap 做 10%/20% 两端，检验低 gap 资产是否在
接下来 1/3/5/10 日跑赢高 gap 资产。冻结网格共 `4 × 4 × 3 × 2 = 96` 个 cell，discovery 为
2022–2023，validation 为 2024–2026-11-12；只报 gross spread，不接实盘、不计 funding。

预注册的**反转方向**完全失败：96/96 cell 都是 `rejected-now`；discovery 排名前 16 的 cell 中，
validation 没有任何一个同时满足负 IC 与正 contrarian spread。更基础地看，discovery 的 96 个
cell **全部**是负 contrarian spread，说明相对落后后的短期表现是继续落后，而不是补涨。

这不等于数据没有信息，但也不能把事后翻符号直接当成已验证策略。按同一份汇总做描述性反向核对，
有 36/96 个 cell 在 discovery 与 validation 都呈现 `IC > 0` 且 `contrarian spread < 0`，即
日频相对动量方向同号。该反向观察不是 LS68 的预注册结论，且 2024 之后已被用于观察符号，
不能作为 fresh OOS。下一步若要研究，必须预注册为新的 LS69，只使用 discovery 冻结规则，
再用独立样本做组合级回测；不能把本表的 gross spread 当作可交易收益。

**判定：LS68 反转假设 rejected；反向动量仅登记为新假设，不接实盘。**

报告：`reports/daily_btc_shock_leadlag_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-daily-btc-shock-leadlag-design.md`。

### 00.104 2026-11-13 LS69：日频 BTC shock relative continuation 仍未通过独立样本（rejected）

LS68 的 reversal 失败后，反向的 continuation 只能作为新假设单独注册。LS69 冻结
`k/h ∈ {1,3,5,10}`、shock bucket `all/|z|≥2.0/|z|≥2.5`、10%/20% 两端、96 个 cell；
每个信号按 `1/h` tranche 持有，所有 phase 等权，信号后下一收盘才执行，组合 gross 不超过 1.0。
选参只看 2022–2023 discovery，2021 是独立样本，2024–2026 不参与选参。

Discovery 规则选出的 cell 是 `BTC_CONT_k3_h3_abs_z_ge_2_5_tail20`。它的 20bps
discovery **1.1289x / Sharpe 1.1694**、validation **1.0651x / 0.4370**，但独立 2021
只有 **0.9801x / -1.0794**；full 为 **1.1785x / 0.5933 / -6.99%**，而同期 BTC 是
**2.4288x / 0.5500 / -76.63%**。所以不能通过“Sharpe 略高”把它包装成收益策略。

96 个 cell 中，discovery Sharpe20 为正的有 57 个，但 validation 只剩 42 个，2021 只剩 33 个；
pre-2022 是这次唯一没有被 LS68 使用的独立窗口。return-space 把该 sleeve 以 10%/20% 加到
LS57：full 从 68.8077x 仅升到 **70.0355x / 71.2760x**，MDD 几乎不变，但收益增量太小，
不符合当前“收益明显提升”的目标。

**判定：rejected。** 不扫描 phase、k/h、tail、bucket 或 overlay 权重；不修改实盘。保留的有效
信息是：日频 relative gap 更像 continuation 而不是 reversal，但这个方向在单资产极端和 2021
样本上不稳定，不能直接当 alpha。

报告：`reports/daily_btc_shock_continuation_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-daily-btc-shock-continuation-design.md`。

### 00.105 2026-11-13 LS70：intraday 下行 shock 的弱尾空头也不成立（rejected）

LS64/LS65 的 long-short 成本失败后，LS70 检验“只保留弱资产空头腿”是否更有效。信号冻结为
negative BTC shock `z≤-2.5/-3.0`、弱 10% relative gap、k∈{1,2,4} 根 30m bar、h∈{4,8,16}
根 bar，18 个 cell，一次只允许一个 active event；6/12/20bps 每边，不扣 funding。

结果在 discovery 就没有一个 cell 同时满足 6bps 与 12bps Sharpe 为正：只有 2/18 的 discovery
6bps Sharpe 为正，validation 和 full 都是 **0/18** 为正。最好的 discovery cell
`SHORT_DOWN_k2_t30_h4` 在 full 只有 **0.5157x / -0.3700 / -60.78%**；18 个 cell 的 full
全部亏损，说明短腿本身没有足够 gross alpha，LS64/LS65 的问题不是“多头腿拖累”可以解释的。

**判定：rejected。** 不扫描 threshold、k/h、tail、phase 或 overlay 权重；不接空头实盘，也不把
它作为 LS57 的 crash hedge。该结果意味着下一个方向必须换机制或数据源，而不是继续从同一个
BTC shock lead-lag 里切腿。

报告：`reports/intraday_down_shock_short_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-intraday-down-shock-short-design.md`。

### 00.106 2026-11-13 LS71：PIT Top20 membership event diagnostic（rejected）

LS71 检验新进入/跌出点时间 Top20 的事件收益：要求连续 `m∈{3,7,14}` 日确认、30 日冷却，
forward 7/14/28/56 日，收益从下一 close 起算。事件级输出有 4,407 行，但预注册的“每个 cell
至少 3 个同日事件”过滤只留下极少 cell，说明 Top20 边界事件高度分散；唯一留下的 4 个 discovery
exit cell 也没有稳定方向。

作为补充描述，事件级按日期聚类后，entry 和 exit 在 discovery/validation 的平均 BTC excess
都没有稳定为正；没有达到进入组合回测的条件。**判定：diagnostic rejected，不新增策略配置。**
同日过滤的限制保留下，不把事件级均值当成已验证 alpha。

报告：`reports/top20_membership_event_diagnostic_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-top20-membership-event-diagnostic-design.md`。

### 00.107 2026-11-13 LS72：Top20 churn short（2022–2026 为正，2021 失真，rejected standalone）

LS72 把 entry+exit 事件合并成一个 market-neutral book：短事件资产、等名义做多 BTC，m/h 网格
12 个 cell，成本 2/20/50/100bps，不扣 funding。Discovery 选出的 `CHURN_m7_h28` 在
**2022–2023 1.0697x / Sharpe 1.2246**、**2024–2026 1.1325x / 1.3552**；把
**2022–2026 合并为 1.2114x / 1.3027 / -3.18%**，但 **2021 独立负控为 0.7604x /
-2.6950 / -26.02%**，全期因此为 0.9212x / -0.2542。说明 churn short 更像 alt-weak regime
下的条件策略，而不是无条件 alpha。

报告：`reports/top20_churn_short_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-top20-churn-short-design.md`。

### 00.108 2026-11-13 LS73：alt-weak 闸门修复 2021 负控（低收益 provisional）

LS73 不重新挑 m/h，只冻结 LS72 `m=7/h=28`，分别测试 `alt_rel_60`、`btc_ma200` 和两者 AND。
`alt_rel_60` 通过预注册门槛：discovery **1.0400x / Sharpe 0.9978**、validation
**1.0341x / 0.6509**、2021 **0.9864x / -1.1047**、full **1.0608x / 0.5686 /
-2.56%**。它把 2021 的 -24% 亏损压到约 -1.4%，但也暴露出收益规模很小：full 5 年只有 6.1%。

return-space 以 10%/20% 加到 LS57，full 仅从 **68.8077x** 到 **69.33x / 69.86x**，Sharpe
约 1.985–1.989，MDD 约 -39.7% 到 -39.5%。**判定：provisional low-risk sleeve，不是收益
主引擎。** 不接实盘，下一步只检验能否在不加总 gross 的前提下提高资金利用率。

报告：`reports/top20_churn_gated_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-top20-churn-regime-gate-design.md`。

### 00.109 2026-11-13 LS74：churn full-gross 归一到 1.0（partial overlay candidate）

LS74 只改变 LS73 的仓位利用率：有 active churn tranche 时把当日权重归一到 gross 1.0，没有
事件时保持现金；总 gross 仍 <=1.0，没有加杠杆。full 从 LS73 的 1.0608x 提升到
**1.4820x / 0.4530 / -22.65%**，但 full Sharpe 未过 0.5，2021 为 **0.8742x /
-0.7601 / -22.65%**，因此 standalone 仍 fail。

它的价值在 overlay：LS57 20bps 加 10%/20% 的 return-space sleeve 后为
**73.4385x / 2.0118 / -38.56%** 和 **78.2480x / 2.0389 / -37.27%**，相对 LS57 的
68.8077x / 1.9819 / -39.84% 同时提高收益和改善回撤。但这是直接在收益序列上相加，尚未处理
LS57 已占用的 gross、真实 funding、两腿成交成本和执行冲突。

**判定：partial overlay candidate，不 promotion。** 下一步必须做残差 gross 合并：只在 LS57
未使用 gross 内开 churn tranche，按统一账户计算成本和 funding；若合并后不能再现
70x 以上且回撤不明显恶化，就停止这条 overlay 家族。

报告：`reports/top20_churn_fullgross_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-top20-churn-fullgross-design.md`。

### 00.110 2026-11-13 LS75：LS57 + residual-gross LS74 overlay（partial，通过 gross-budget 诊断）

LS75 首次把 LS57 的真实 `target_gross.csv` 纳入 overlay：每天只允许 LS74 使用
`1.50 - LS57_total_gross` 的剩余 gross，再按 10%/20%/25% 三档分配；不重算 LS57 或 sleeve
的选币。LS57 刷新后的平均总 gross 为 **0.534x**，最大 1.30x，因此这个约束不是形式上的。

| allocation | full 终值 | Sharpe | MDD | validation 终值 | validation Sharpe | max combined gross |
|---:|---:|---:|---:|---:|---:|---:|
| 10% | 73.6173x | 2.0128 | -38.56% | 15.8284x | 2.1403 | 1.40x |
| 20% | 78.6296x | 2.0410 | -37.27% | 16.4219x | 2.1698 | 1.50x |
| 25% | **81.2613x** | **2.0543** | **-36.59%** | **16.7250x** | **2.1836** | 1.50x |

相对 LS57 的 68.8077x / 1.9819 / -39.84%，25% 档提高终值约 **18.1%**、Sharpe 约 +0.072、
MDD 改善约 3.25pp。**判定：partial overlay candidate，不 promotion。** 这是 return-space
gross-budget 结果，尚未计 sleeve funding、scale-change 成本和真实 Bitget fill；下一步必须做
funding-aware 与成本压力版本。

报告：`reports/ls57_churn_overlay_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls57-churn-overlay-design.md`。

### 00.111 2026-11-13 LS76：churn overlay 加入 funding proxy 与 scale-change 成本

LS76 在 LS75 上加入 sleeve 的 Binance 8h funding proxy、按 UTC 日 settlement 汇总，并对
sleeve scale 每日变化额外收取 20bps 成本；LS57 原有 funding 不重复计。加权 funding 覆盖率为
**92.60%**，sleeve funding 累计贡献约 -0.0195（25% scale 后约 -0.0049）。

| allocation | full 终值 | Sharpe | MDD | validation 终值 | validation Sharpe | funding coverage |
|---:|---:|---:|---:|---:|---:|---:|
| 10% | 73.2946x | 2.0109 | -38.63% | 15.8168x | 2.1397 | 92.60% |
| 20% | 77.9415x | 2.0372 | -37.42% | 16.3978x | 2.1686 | 92.60% |
| 25% | **80.3435x** | **2.0494** | **-36.80%** | **16.6928x** | **2.1820** | 92.60% |

在 funding + scale-cost 下仍通过 LS76 预注册门槛，且 25% 档仍比 LS57 高约 16.8%、回撤改善
约 3.0pp。**判定：funding-aware partial overlay candidate，不接实盘。** 仍缺 Bitget exact
funding、mark/fill、margin、liquidation 和真正的 target-level 合并；下一步做 3x adverse
funding 与成本压力，不得把 92.6% proxy 覆盖当作精确历史。

报告：`reports/ls57_churn_overlay_funding_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls57-churn-overlay-funding-design.md`。

### 00.112 2026-11-13 LS77：churn overlay 压力矩阵（100bps 通过，3x adverse funding 失败）

LS77 固定 LS75/LS76 的 residual-gross 规则，对 sleeve 做 20/50/100bps × normal/3x adverse
funding 的压力。普通 funding 下 25% allocation 在 100bps 仍有 **69.1799x / 1.9873 / -37.59%**，
略高于 LS57；10% allocation 也有 69.08x。但 3x adverse 下 25% 跌到
**56.6938x / 1.9065 / -38.36%**，10% 也低于 LS57。**判定：stress fail，不 promotion。**

这不是 allocation 太小的问题，而是 sleeve 的 BTC 多头腿也在 adverse funding 中被收费。下一轮
只改变执行结构为“空 alt 永续 + 多 BTC 现货”，不在已看过的结果上调 allocation、成本或 funding
阈值。

报告：`reports/ls57_churn_overlay_stress_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls57-churn-overlay-stress-design.md`。

### 00.113 2026-11-13 LS78：可执行 alt 永续空头 + BTC 现货仍被 1x adverse validation 拒绝

LS78 只改变 LS77 的执行结构：BTC 多头改现货、alt 空头仍为永续；信号日仅保留过去 7 天内有
Binance/Bybit/Bitget funding settlement 的 alt，并把事件内剩余空头腿等权重建。103 个有短腿的
事件中 84 个至少保留一腿，138 条原始空头腿保留 106 条；被剔除的是 bitget-token、CRO、LEO、
MNT、OKB、RENDER、LUNA、TON 这 8 个缺少同期 funding 证据的标的。short funding 覆盖率因此
从 LS76 的 92.6% 提升到 **100%**，但这不是免费改进：可执行币池缩窄后 standalone sleeve 从
LS74 的 1.4820x 降到 **1.3389x**（20bps）。

BTC 现货腿确实消除了正常 funding 的拖累。25% allocation 在 20bps normal 为
**77.4407x / 2.0338 / -35.56%**，validation **15.8832x / 2.1466**；20% 为
75.7112x / 2.0252 / -36.43%。但同一 allocation 的 20bps **1x adverse** 只有
**71.2339x / 2.0001 / -35.82%**，full 和 MDD 都仍优于 LS57，validation 却降到
**15.0421x**，低于 LS57 的 15.2386x；2x/3x adverse 分别为
66.4249x / 13.7851x 的 validation（更差）。**判定：normal 有真实增益，但 1x adverse
validation 未通过，LS78 stress fail，不 promotion。**

这轮排除了“只要把 BTC 腿从永续换现货就会自动闭合风险”的假设。下一步不再改 allocation，
而是研究 **point-in-time funding sign/venue selection**：只空 funding 结构对空头不劣势的
事件，或把同一空头腿路由到成本更低的 venue；必须同时报告过滤后的事件数、币池集中度和
正常/1x adverse 的 validation，不能只看 full 终值。

报告：`reports/ls57_churn_spot_btc_short_alt_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls57-churn-spot-btc-short-alt-design.md`。

### 00.114 2026-11-13 LS79：12-cell 多相位 churn ensemble 通过点估计门槛，但统计置信仍弱

LS79 不再只挑 discovery 排名第一的 `m7_h28`，而是把 LS72 已注册的 `m∈{3,7,14} ×
h∈{7,14,28,56}` 全部 12 个 cell 在当日等权。每个 cell 先生成 `alt_rel_60` gated target，再套用
LS74 active-day gross=1 与 LS78 可执行 alt 永续空头币池；ensemble 权重是所有 active cell 归一
权重之和 / active cell 数，所以总 gross 始终 <=1。成本、funding、residual scale 都在合成后的
权重上重新计算，不是把 12 条收益率直接相加。

25% allocation 在 20bps normal 为 **79.0382x / 2.0503 / -35.23%**，相对 LS57 的 68.8077x
提高约 **14.86%**、Sharpe +0.0683、MDD 改善约 4.61pp；validation 为
**16.9096x / 2.2056**。20bps **1x adverse** 仍有 **70.8376x / 2.0054 / -35.53%**，
validation **15.6768x / 2.1538**，同时超过 LS57；20% allocation 也通过两个口径。50bps
normal 25% 为 **73.4390x / 2.0198 / -35.54%**。但 100bps normal 降到
**64.9718x**，2x/3x adverse 分别降到 **64.7120x / 59.1154x**，均未通过。

这个结果不是无条件的“更强策略”：

- ensemble standalone 20bps 只有 **1.3546x / Sharpe 0.3868 / MDD -43.49%**，必须依附 LS57；
- 单币最大空头权重占比 **11.72%（MONERO）**，没有单一币垄断，但前 5 名仍占约 37.7%；
- 2021 price-only 负控为 **0.9264x / Sharpe -0.2896 / MDD -23.50%**，说明 sleeve 不是全天候；
- 逐年只有 3/5 年跑赢 LS57；normal 留一年后仍全部为正（最小 excess multiple 约 +1.16），
  365 天滚动窗口 77.78% 跑赢、median excess +15.00%，但 worst rolling 为 -24.41%；
- normal 的 Newey-West(63) t 仅 **1.04**，circular block bootstrap 的 95% total log excess CI
  为 **[-10.78%, +38.08%]**，包含 0；1x adverse 的 CI 更宽且 t 仅 0.16。

**判定：LS79 是 conditional overlay candidate，不是 promotion，也不是已证明 robust。** 它相对
LS76/LS78 的改进是：不再依赖单个 `m/h`、成本/funding 在合并权重上重算、可执行币池和
funding 覆盖率 100%、并显式披露统计置信不足。下一步只做真实 Bitget mark/fill/funding/margin/
liquidation 合并与更长 forward OOS；不再扫描 cell 子集、allocation 或 funding threshold。

> **已被 §00.115 supersede 的可执行性结论：** LS79 的“可执行”仅指跨 exchange funding proxy，
> 不代表当时 Bitget 有 mark/合约。严格 Bitget mark+funding 审计失败，因此 LS79 的 conditional
> promotion 已撤回；其上表只保留为研究点估计，不得作为 live/shadow promotion 依据。

报告：`reports/ls57_churn_multiphase_ensemble_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls79-churn-multiphase-ensemble-design.md`。

### 00.115 2026-11-13 LS80：LS79 在严格 Bitget mark/funding 币池中失败

LS80 不是新 alpha，而是把 LS79 的空头腿进一步限制为“信号日过去 3 天有 Bitget market mark，
且过去 7 天有 Binance/Bybit/Bitget funding settlement”。原 LS79 的 34 个短币中，按权重只有
**85.92%** 的 mark 覆盖；`flow/ftx-token/maker` 完全没有 Bitget mark，`monero/kaspa/canton-network`
只在样本后段上线。剔除不可执行腿并在事件内重建后，严格币池的 12-cell ensemble standalone
从 LS79 的 **1.3546x** 掉到 **0.7725x / Sharpe -0.0599 / MDD -57.84%**（20bps）。

合并 LS57 后，25% allocation 在 20bps normal 只有 **69.7688x / 2.0060 / -35.24%**，
validation **15.2399x / 2.1472**，相对 LS57 几乎贴着门槛；同一 allocation 的 1x adverse
跌到 **62.9643x / 1.9638 / -35.55%**，validation **14.2124x**。50bps normal 也只有
65.0316x，低于 LS57。**判定：strict Bitget executable fail；LS79 conditional promotion
撤回，churn overlay 家族停止。** 不能再用“跨交易所 funding 存在”代替“Bitget 当时可成交 +
可计 funding”。

这次失败不是参数问题，而是实现可行性问题：之前看起来有效的 sleeve 有相当一部分收益来自
Bitget 当时没有合约或数据无法闭合的币。下一步转向只使用 Bitget 自己有完整 mark/funding 的
高流动性标的，且先用真实引擎验证，再讨论 alpha；不再调 churn 的 lookback、币种白名单或
allocation。

报告：`reports/ls57_churn_bitget_executable_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls80-bitget-executable-churn-ensemble-design.md`。


### 00.116 2026-11-13 LS81：LS57 + core8 PIT funding carry（rejected）

LS81 在冻结 LS57 上只增加一个固定的 8 币主力组（BTC/ETH/SOL/XRP/BNB/DOGE/ADA/AVAX）
funding carry：按信号日之前 7D 的 Binance funding settlement，最低 2 币做多、最高 2 币做空，
每腿 25% NAV（sleeve 原始 gross 1.0x），只在 LS57 base book 的 residual gross 内按 10/20/25%
缩放。信号使用严格 PIT（排除信号日当天 settlement），base 已持有的资产从 carry 候选中剔除，
Bitget mark 做标记/强平，Bitget market candle 做成交，missing mark carry 上限 3h。

同一套严格 market-fill 引擎下的 20bps normal 结果：

| 策略 | 终值 | Sharpe | MDD | 强平 | gross breach hours | max observed gross |
|---|---:|---:|---:|---:|---:|---:|
| LS57 baseline | 58.2059x | 1.9143 | -39.83% | 0 | 0 | 1.3306x |
| LS81 10% | 60.2890x | 1.9332 | -39.11% | 1 | 0 | 1.3943x |
| LS81 20% | 61.5485x | 1.9439 | -38.38% | 1 | 0 | 1.4978x |
| LS81 25% | **62.0545x** | **1.9475** | **-38.07%** | **1** | **59** | **1.5163x** |

25% validation 为 14.6803x / Sharpe 2.0921，baseline validation 为 13.8153x / Sharpe 2.0417；
表面上 full/validation 都赢，但风险门禁已经失败，因此不能作为 promotion。强平事件是
**SOL long 2022-05-12 07:00 UTC**：entry 81.0926、theoretical liquidation 39.5079、50% long
buffer 下在 2022-05 崩盘中被强平。低 funding 的“carry long”在压力期会主动买入下跌最快的
资产，市场中性 sleeve 仍然保留了每条腿的孤立保证金风险。

成本和 funding 压力直接否定了这个方向：

| 成本 | LS57 baseline | LS81 10% | LS81 20% | LS81 25% |
|---:|---:|---:|---:|---:|
| 50bps 终值 | 34.6316x | 33.3424x | 31.7118x | 30.8170x |
| 100bps 终值 | 14.5318x | 12.3804x | 10.4567x | 9.5522x |
| 20bps + 1x two-sided adverse | 50.1759x | 48.7861x | 46.7593x | 45.6780x |
| 20bps + 3x two-sided adverse | 31.4655x | 27.7030x | 24.0513x | 22.3633x |

扩展 10 币（加 LINK/DOT）在 20bps normal 也没有改善：10% 为 58.0311x / Sharpe 1.9191，
20% 为 56.9244x，25% 为 57.4495x；因此不是 core8 名单偶然太窄，而是该 carry 机制的成本与
尾部风险不匹配。

**判定：rejected。** 不通过调 allocation、core8 名单、funding lookback、腿数或止损来救这个
结果；LS81 不接实盘，不修改当前 `PR2026-10-D-L125-V2`。后续如果继续做 carry，必须把它作为
新的 risk-first trial（例如显式 long buffer/leg stop 或只做 short carry），不能用本次结果做
事后参数选择。

报告：`reports/ls81_core_major_funding_carry_2026/`；
敏感性：`reports/ls81_core_major_funding_carry_2026_cost50_100/`、
`reports/ls81_core_major_funding_carry_2026_adverse/`、
`reports/ls81_core_major_funding_carry_2026_extended10/`；Spec：
`docs/superpowers/specs/2026-11-13-ls81-core-major-funding-carry-design.md`。

### 00.117 2026-11-13 LS82：core8 carry 的风险包修复（risk pass；cost/adverse fail）

LS82 不改变 LS81 的 core8、PIT funding、腿数、权重或 25% allocation，只把 long buffer 从 50%
提高到 60%，把目标 gross 从 1.50x 降到 1.45x，hard cap 仍为 1.50x。这样可以在同一基线臂上
隔离“孤立保证金/漂移”风险，而不是用事后改币池或 funding lookback 救 LS81。

20bps normal：

| 策略 | 终值 | Sharpe | MDD | 强平 | gross breach hours | max observed gross |
|---|---:|---:|---:|---:|---:|---:|
| LS57 baseline 60%/1.45x | 58.2059x | 1.9143 | -39.83% | 0 | 0 | 1.3306x |
| LS82 core8 25% | **62.1228x** | **1.9519** | **-37.98%** | **0** | **0** | **1.4545x** |

LS82 的 validation 为 **14.5712x / Sharpe 2.0921**，baseline 为 13.8153x / 2.0417。风险包
确实消除了 2022-05 SOL long 强平和 25% 的 gross breach；mark carry 最长 1h。这个结果说明
LS81 的失败可以被显式保证金/漂移缓冲修复，不能说明 carry alpha 在成本后有效。

成本与 adverse funding 仍然失败：

| 场景 | baseline | LS82 25% |
|---|---:|---:|
| 50bps normal | 34.6316x / 1.7012 / -43.44% | 30.8855x / 1.6629 / -42.03% |
| 100bps normal | 14.5318x / 1.3440 / -49.42% | 9.5926x / 1.1784 / -49.50% |
| 20bps + 1x two-sided adverse | 50.1759x / 1.8533 / -41.23% | 45.7220x / 1.8250 / -39.75% |
| 20bps + 3x two-sided adverse | 31.4655x / 1.6633 / -43.76% | 22.3991x / 1.5309 / -43.22% |

**判定：risk fix 成功，alpha/cost fail；LS82 不晋级。** 不能再用 50/55/60/65% buffer、1.40/
1.45x target gross、allocation 或其他 carry 参数救同一个结果。core8 funding carry 家族停止，
后续研究转向独立信息源；实盘仍为 `PR2026-10-D-L125-V2`，不修改。

报告：`reports/ls82_core8_carry_risk_2026/`；
成本敏感性：`reports/ls82_core8_carry_risk_2026_cost50_100/`；
funding 压力：`reports/ls82_core8_carry_risk_2026_adverse/`；Spec：
`docs/superpowers/specs/2026-11-13-ls82-core8-carry-risk-design.md`。

### 00.118 2026-11-13 LS83：core8 funding settlement 短周期事件筛选（rejected）

LS83 检验一个与 7D carry 不同的短期机制：在每日 00:00 UTC funding settlement 已知后，
按 Binance funding 横截面最低 2 币做多、最高 2 币做空，事件后 1h 用 Bitget market close 入场，
分别持有 8h 和 24h。固定 core8，不扫描 settlement hour、horizon、count 或阈值。

| 窗口 | horizon | n | gross mean | 20bps net mean | 50bps net mean | NW t | hit rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| full | 8h | 1,666 | **0.0015%** | **-0.3985%** | -0.9985% | 0.05 | 51.62% |
| full | 24h | 1,666 | 0.0469% | -0.3531% | -0.9531% | 0.76 | 51.32% |
| discovery | 8h | 704 | -0.0490% | -0.4490% | -1.0490% | -0.81 | 51.14% |
| discovery | 24h | 704 | 0.0868% | -0.3132% | -0.9132% | 0.84 | 52.70% |
| validation | 8h | 962 | 0.0385% | -0.3615% | -0.9615% | 1.06 | 51.98% |
| validation | 24h | 962 | 0.0177% | -0.3823% | -0.9823% | 0.24 | 50.31% |

8h 是主 horizon，validation gross spread 不足以覆盖 20bps 完成一次多空组合的入场+出场成本；
24h 辅助 horizon 也不显著。2,000 次事件内 funding 随机错配 placebo 的 p95 spread 高于或接近
实际值，validation 8h placebo p=0.157，不能支持可交易 edge。**判定：rejected。** 不建立
LS84 组合回测，不扫描 08/16 UTC、1h/3h/7h、3 币/4 币、funding 阈值或 only-positive 条件；
funding settlement 短周期家族停止。

报告：`reports/ls83_funding_settlement_screen_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls83-funding-settlement-screen.md`。

### 00.119 2026-11-13 LS84：core8 高成交量反转筛选（rejected）

LS84 固定 core8，按每日 quote_volume / 过去 20 日 median 计算 volume surprise，只在量能最高
4 个币中选择 24h return 最低 2 个做多、最高 2 个做空；D+1 03:00 UTC 入场，24h/72h 用
Bitget market close 出场。该规则检验“高量能单向波动后的过度反应反转”。

| 窗口 | horizon | n | gross mean | 20bps net mean | 50bps net mean | NW t | hit rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| full | 24h | 1,644 | **-0.1292%** | -0.5292% | -1.1292% | -1.90 | 47.99% |
| full | 72h | 1,644 | -0.2150% | -0.6150% | -1.2150% | -1.70 | 48.60% |
| discovery | 24h | 686 | -0.2056% | -0.6056% | -1.2056% | -1.85 | 47.08% |
| discovery | 72h | 686 | -0.5102% | -0.9102% | -1.5102% | -2.36 | 45.77% |
| validation | 24h | 958 | -0.0744% | -0.4744% | -1.0744% | -0.87 | 48.64% |
| validation | 72h | 958 | -0.0036% | -0.4036% | -1.0036% | -0.02 | 50.63% |

24h/72h 方向均为负，validation 不显著；2,000 次高量能组内随机选腿的 placebo p=0.801（24h）
和 0.502（72h），实际结果没有超过随机选择。**判定：rejected。** 不建立 LS85 组合回测；
不扫描 volume lookback、top-3/4/5、return 1D/3D/7D、腿数或 horizon。

报告：`reports/ls84_volume_reversal_screen_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls84-volume-reversal-screen.md`。

### 00.120 2026-11-13 LS85：LS57 逐资产 200D 趋势过滤（rejected）

LS85 不改变 LS57 的 H5、profit-lock 或 short router，只在每个 long target event 上检查该资产
信号日收盘是否低于自身 200D SMA；低于则把该腿降为 0，释放的权重留现金，不重分配。这样直接
检验“逐资产趋势过滤能否改善逃顶”，而不是继续调整 LS57 的利润保护参数。

同一 strict market-fill 引擎、20bps normal：

| 策略 | 终值 | Sharpe | MDD | validation multiple | validation Sharpe | 强平 |
|---|---:|---:|---:|---:|---:|---:|
| LS57 baseline | **58.2059x** | **1.9143** | **-39.83%** | **13.8153x** | **2.0417** | 0 |
| LS85 200D filter | 30.7807x | 1.7354 | -47.50% | 11.3117x | 1.9376 | 0 |

过滤只触发了 68/661 个事件、累计过滤权重 22.33x NAV，但收益接近腰斩、回撤反而恶化；50bps
为 18.7131x vs baseline 34.6316x，100bps 为 8.1411x vs 14.5318x；3x two-sided adverse
下为 17.0906x vs baseline 31.4655x。缺失 MA 的 leg 按预注册规则保留并记录了 35 次。
**判定：rejected。** 这个 200D 过滤把长期趋势中的反转/回归段错误地当成风险，不能用来逃顶；
不扫描 50/100/150/250D、不改成部分减仓、不按资产或年份手工筛选。

报告：`reports/ls85_asset_trend_filter_2026/`；压力：
`reports/ls85_asset_trend_filter_2026_adverse/`；Spec：
`docs/superpowers/specs/2026-11-13-ls85-asset-trend-filter-design.md`。

### 00.121 2026-11-13 LS86：core8 realized-skew / lottery-demand 筛选（rejected）

LS86 固定 core8，使用 30D daily-return realized skewness：skew 最低 2 币做多、最高 2 币做空，
7D 周频，D+1 03:00 UTC 入场，持有 7D。该机制独立于 momentum/funding/volume，用于检验
“彩票型资产被高估、低偏度资产获得补偿”的横截面假设。

| 窗口 | n | gross mean | 20bps net mean | 50bps net mean | NW t | hit rate |
|---|---:|---:|---:|---:|---:|---:|
| full | 235 | **-0.1515%** | -0.5515% | -1.1515% | -0.26 | 51.06% |
| discovery | 98 | -0.1802% | -0.5802% | -1.1802% | -0.20 | 50.00% |
| validation | 137 | -0.1310% | -0.5310% | -1.1310% | -0.17 | 51.82% |

gross spread 在两个样本段都为负，validation t 接近 0；core8 的 realized skew 没有形成可交易的
lottery-demand 溢价。**判定：rejected。** 不建立 LS87 组合回测，不扫描 20/30/60D skew、
3/5/7/14D hold、count 或 volatility normalize。

报告：`reports/ls86_realized_skew_screen_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls86-realized-skew-screen.md`。

### 00.122 2026-11-13 LS87：PIT Top20 realized-skew 宽币池筛选（rejected）

LS87 把 LS86 的 30D realized-skew 机制移到 PIT CMC Top20，只保留 Bitget market candle 可成交
的成员，每 7D 做多最低 skew 2 币、做空最高 skew 2 币，D+1 03:00 UTC 入场、7D 后出场。这样
检验宽币池是否能提供 core8 缺失的横截面离散度，同时避免用当前 universe 回填历史。

| 窗口 | n | gross mean | 20bps net mean | 50bps net mean | NW t | hit rate |
|---|---:|---:|---:|---:|---:|---:|
| full | 241 | -0.4712% | -0.8712% | -1.4712% | -0.70 | 53.53% |
| discovery | 102 | -1.1815% | -1.5815% | -2.1815% | -1.15 | 47.06% |
| validation | 139 | **+0.0500%** | **-0.3500%** | -0.9500% | 0.06 | 58.27% |

validation 的 gross 仅约 5bps/7D，远低于一次多空组合入场+出场成本；20/50bps 后都为负，
discovery 方向相反。**判定：rejected。** 不建立 LS88 引擎回测，不扫描 Top20、skew window、
weekly horizon、count 或可成交池门槛；lottery-demand 家族停止。

报告：`reports/ls87_top20_skew_screen_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls87-top20-skew-screen.md`。

### 00.123 2026-11-13 LS88：LS57 + core8 low-funding long-only（rejected）

LS88 把 LS81/LS82 的 market-neutral carry 拆成只做 low-funding long 腿：core8 中 7D funding
最低 2 币，每腿 25% NAV，目标 sleeve gross 10/20/25% NAV，沿用 60% long buffer、目标 gross
1.45x 和 hard cap 1.50x。

20bps normal：

| 策略 | 终值 | Sharpe | MDD | validation multiple | validation Sharpe | 强平 |
|---|---:|---:|---:|---:|---:|---:|
| LS57 baseline | **58.2059x** | **1.9143** | -39.83% | **13.8153x** | **2.0417** | 0 |
| LS88 10% gross | 61.4661x | 1.9062 | -39.41% | 14.3776x | 2.0185 | 0 |
| LS88 20% gross | **63.0370x** | 1.8759 | -38.65% | 14.5795x | 1.9717 | 0 |
| LS88 25% gross | 63.0364x | 1.8528 | -38.49% | 14.6717x | 1.9474 | 0 |

终值上升但 Sharpe 和 validation Sharpe 全部下降，说明增量主要是多头 beta/收益放大，不是免费的
风险调整 alpha。50bps 20% 为 32.7778x / 1.6208，baseline 34.6316x / 1.7012；100bps 为
10.9744x / 1.1930，baseline 14.5318x / 1.3440；3x two-sided adverse 为 24.5404x，baseline
31.4655x。**判定：rejected。** long-only carry 不是可接受的独立升级；不扫描 10/15/20/25/30%
或 short-only 变体救结果。

报告：`reports/ls88_lowfunding_long_2026/`；成本：
`reports/ls88_lowfunding_long_2026_cost50_100/`；压力：
`reports/ls88_lowfunding_long_2026_adverse/`；Spec：
`docs/superpowers/specs/2026-11-13-ls88-lowfunding-long-design.md`。

### 00.124 2026-11-13 LS89：LS57 逐资产 21D SMA 退出（risk-only rejected）

LS89 使用 LS57 已有的 21D 窗口做逐腿退出：long asset 信号日收盘低于自身 21D SMA 时转为现金，
不重分配；同时使用 60% long buffer 和目标 gross 1.45x，short router 不变。

| 成本 | LS57 baseline 终值/Sharpe/MDD | LS89 终值/Sharpe/MDD | baseline validation | LS89 validation |
|---:|---:|---:|---:|---:|
| 20bps | 58.2059x / 1.9143 / -39.83% | 54.7231x / **1.9275** / **-36.48%** | 13.8153x / 2.0417 | 12.1321x / 2.0093 |
| 50bps | 34.6316x / 1.7012 / -43.44% | 32.4785x / **1.7075** / **-40.16%** | 9.9768x / 1.8223 | 8.7115x / 1.7771 |
| 100bps | 14.5318x / 1.3440 / -49.42% | 13.5751x / 1.3386 / **-47.35%** | 5.7885x / 1.4535 | 5.0071x / 1.3868 |

21D 过滤比 200D 明显更好，确实降低了 MDD，并让 20bps Sharpe 小幅上升；但终值和 validation
全面下降，20bps full multiple 与 validation 门槛失败。3x two-sided adverse 下终值 30.8057x /
Sharpe 1.6868 / MDD -40.24%，baseline 31.4655x / 1.6633 / -43.76%，仍是 risk-only。
**判定：rejected。** 不扫描 10/14/28/50D、不改成部分减仓、不把释放权重再分配；逐资产 SMA
退出家族停止。

报告：`reports/ls89_asset_ma21_exit_2026/`；压力：
`reports/ls89_asset_ma21_exit_2026_adverse/`；Spec：
`docs/superpowers/specs/2026-11-13-ls89-asset-ma21-exit-design.md`。

### 00.125 2026-11-13 LS90：四个真实引擎候选的等资本组合（validation fail）

LS90 把 LS57 60%/1.45x、LS82 market-neutral carry、LS88 long-only carry、LS89 21D exit 四个
已保存真实引擎子账户按初始资本 25% 等权，买入后不调仓；每个子账户的 20bps 成本已内含，不做
免费每日再平衡。

| 组合 | full 终值 | Sharpe | MDD | validation 终值 | validation Sharpe |
|---|---:|---:|---:|---:|---:|
| LS57 | 58.2059x | 1.9143 | -39.83% | 13.8153x | 2.0417 |
| LS90 四等权 | **59.1295x** | **1.9322** | **-38.42%** | 13.7014x | **2.0492** |

LS90 full 和 Sharpe/MDD 改善，但 validation multiple 13.7014x 低于 LS57 的 13.8153x，预注册
门槛失败。子账户相关性显示四个 sleeve 高度同源，不能把它当作独立 alpha 组合。**判定：
validation fail，不 promotion。** 不通过调 20/30/40% 权重救结果。

报告：`reports/ls90_multi_strategy_ensemble_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls90-multi-strategy-ensemble.md`。

### 00.126 2026-11-13 LS91：LS57 核心 + carry 卫星（20bps pass；50/100bps fail）

LS91 把 LS90 的角色拆开：50% LS57、25% LS82 market-neutral carry、25% LS88 low-funding long；
LS89 是 risk-only overlay，权重固定 0。仍是无再平衡的子账户组合，不增加总 gross。

| 成本 | LS57 终值/Sharpe/MDD | LS91 终值/Sharpe/MDD | LS57 validation | LS91 validation |
|---:|---:|---:|---:|---:|
| 20bps | 58.2059x / 1.9143 / -39.83% | **60.0002x / 1.9242 / -39.28%** | 13.8153x / 2.0417 | **14.1470x / 2.0505** |
| 50bps | 34.6316x / 1.7012 / -43.44% | 33.5719x / 1.6862 / -43.02% | 9.9768x / 1.8223 | 9.8181x / 1.8050 |
| 100bps | 14.5318x / 1.3440 / -49.42% | 12.8555x / 1.2920 / -49.41% | 5.7885x / 1.4535 | 5.3831x / 1.3994 |

LS91 首次通过 20bps full/validation 主门槛，但 50bps 终值和 Sharpe 已低于 LS57，100bps 明显
落后；这是**成本敏感的 20bps portfolio candidate，不是可晋级策略**。组合的收益增量来自
LS82/LS88 的低成本档，不能把 maker/低费率假设直接带入 promotion。**判定：conditional；
不接实盘，不修改当前 `PR2026-10-D-L125-V2`。**

报告：`reports/ls91_core_satellite_ensemble_2026/`；成本：
`reports/ls91_core_satellite_ensemble_2026_cost50/`、
`reports/ls91_core_satellite_ensemble_2026_cost100/`；Spec：
`docs/superpowers/specs/2026-11-13-ls91-core-satellite-ensemble.md`。

### 00.127 2026-11-13 LS92：LS91 core-satellite 的 maker-shadow 成本敏感性（shadow pass）

LS92 不改变 LS91 的 50/25/25 资本分配、子策略规则、universe、funding、mark/fill、stop 或 gross
cap，只把三个子账户的每边成本从 20bps 重新跑为 **13.0164bps**。13.0164bps 来自 §00.92/§00.95
的 Bitget 逐笔/L1 maker shadow（25% volume-capacity haircut），不是已验证的 2022–2026 历史
成交成本。

| 子账户/组合 | 终值 | Sharpe | MDD | validation 终值 | validation Sharpe |
|---|---:|---:|---:|---:|---:|
| LS57 @13.0164bps | 65.6712x | 1.9638 | -38.96% | 14.9011x | 2.0925 |
| LS82 carry @13.0164bps | 73.0767x | 2.0189 | -36.997% | 16.1532x | 2.1621 |
| LS88 long-only @13.0164bps | 70.4673x | 1.9610 | -38.51% | 15.6631x | 2.0743 |
| LS89 21D @13.0164bps | 61.7783x | 1.9785 | -35.59% | 13.1031x | 2.0631 |
| **LS92 50/25/25** | **68.7216x** | **1.9798** | **-38.37%** | **15.4108x** | **2.1078** |

相对同成本 LS57，LS92 提升 **+4.65% 终值**、Sharpe **+0.0160**、MDD 改善约 **0.59pp**，
validation 终值 **+3.42%**、Sharpe **+0.0153**。这是执行成本假设改善后的 portfolio candidate，
不是新 alpha；13.0164bps 仍受 2026 单一样本、queue/部分成交/撤单延迟和 ADL 外推限制。
**判定：shadow pass；不接实盘，不修改当前 `PR2026-10-D-L125-V2`。**

报告：`reports/ls92_core_satellite_maker_shadow_2026/`；子账户：
`reports/ls92_ls57_maker13_2026/`、`reports/ls92_ls82_maker13_2026/`、
`reports/ls92_ls88_maker13_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls92-core-satellite-maker-shadow.md`。

### 00.128 2026-11-13 LS93：LS92 core-satellite 稳健性归因（inconclusive）

LS93 冻结 LS92 的 50% LS57 + 25% LS82 + 25% LS88 权重，分别在 13.0164bps 和 20bps 下与同成本
LS57 比较；不重新拟合、不扫描权重、不改变 live track。两个场景严格使用 1,724 个共同交易日
（2022-01-01→2026-09-20），缺失或非有限收益直接失败，不用 0 填充。

| 成本 | 组合 full 终值/Sharpe/MDD | LS57 full | 组合 validation 终值/Sharpe | LS57 validation |
|---:|---:|---:|---:|---:|
| 13.0164bps | **68.7216x / 1.9798 / -38.37%** | 65.6712x / 1.9638 / -38.96% | **15.4108x / 2.1078** | 14.9011x / 2.0925 |
| 20bps | **60.0002x / 1.9242 / -39.28%** | 58.2059x / 1.9143 / -39.83% | **14.1470x / 2.0505** | 13.8153x / 2.0417 |

表面上两个成本档的 full/validation 终值、Sharpe 和 MDD 都改善，但增量不稳健：

- 13.0164bps 逐年超额为 2022 **-0.0423x**、2023 **+0.1930x**、2024 **+0.1056x**、
  2025 **-0.0598x**、2026 **+0.0053x**；20bps 为 2022 **-0.0444x**、2023 **+0.1770x**、
  2024 **+0.0943x**、2025 **-0.0681x**、2026 **-0.0009x**。
- leave-one-year-out 在 13.0164bps 下最差为剔除 2024 的 **-0.1990x**；20bps 下最差为剔除
  2024 的 **-0.5124x**。改善依赖 2023/2024 的少数年份。
- 365D rolling 为正的比例只有 **67.70% / 64.75%**，最差滚动超额为 **-7.97% / -8.96%**。
- 日 log excess 的 Newey-West t(63) 为 **0.9435 / 0.6483**；circular block bootstrap 5,000 次
  的总 log excess 2.5% 分位为 **-5.28% / -6.72%**，为正概率 **81.78% / 73.00%**。
- CSCV/PBO 为 **0.4892 / 0.6515**；Reality Check 对零的 p=**0.0030 / 0.0034**，但对 LS57
  超额的 p=**0.4891 / 0.5613**，不能证明组合优于 LS57。
- 项目级 DSR 在纳入 LS81-LS92 的 12 个真实引擎衍生品组合后，all_trials N=14,410 下为
  **0.5754 / 0.5200**；Top20/2022 N=6,201 下为 **0.6705 / 0.6181**，均低于 0.95。新增组合的
  universe 记为 `Derivatives`，不改变 Top20/2022 scope；更早的衍生品代理试验若继续加入，分母只会更大。
- 增量贡献约 **60.7% 来自 LS82、39.3% 来自 LS88**，不是单一 sleeve 垄断；但子账户相关性
  **0.974-0.995**，所谓分散化主要是同源 beta，而不是独立 alpha。

**判定：inconclusive。** LS92 不能称为 robust-shadow，也不能晋级实盘；但 LS82 standalone 在同一
两个成本档的 full 终值、Sharpe、MDD 都优于 LS92（73.0767x / 2.0189 / -36.997%；
62.1228x / 1.9519 / -37.978%），说明“去掉 LS88、把卫星权重集中到 LS82”是下一步值得预注册的
研究分支，而不是继续扫描 LS92 的 50/25/25 邻域。当前 live track 仍为
`PR2026-10-D-L125-V2`，不修改。

报告：`reports/ls93_core_satellite_robustness_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls93-core-satellite-robustness.md`。

### 00.129 2026-11-13 LS94：LS82 carry-core 独立稳健性（year-concentrated）

LS94 不改变 LS82 的 25% residual、60% long buffer、1.45x target gross、funding 或执行，只在
13.0164bps 与 20bps 两个成本档比较 LS82 vs 同成本 LS57。两个场景均为 1,724 个共同交易日。

| 成本 | LS82 full 终值/Sharpe/MDD | LS57 full | LS82 validation 终值/Sharpe | LS57 validation |
|---:|---:|---:|---:|---:|
| 13.0164bps | **73.0767x / 2.0189 / -36.997%** | 65.6712x / 1.9638 / -38.96% | **16.1532x / 2.1621** | 14.9011x / 2.0925 |
| 20bps | **62.1228x / 1.9519 / -37.978%** | 58.2059x / 1.9143 / -39.83% | **14.5712x / 2.0921** | 13.8153x / 2.0417 |

LS82 standalone 的确优于 LS92 core-satellite 的全样本指标，但独立稳健性仍不通过：

- 13.0164bps 逐年超额：2022 **-0.0758x**、2023 **+0.3788x**、2024 **+0.2076x**、2025
  **-0.1165x**、2026 **+0.0530x**；20bps 为 **-0.0821x / +0.3373x / +0.1781x /
  -0.1424x / +0.0366x**。收益集中在 2023/2024，2022/2025 为负。
- leave-one-year-out：13.0164bps 最差仍为 **+0.2161x**，但 20bps 剔除 2024 后为
  **-0.6806x**；高成本档对单一年份敏感。
- 365D rolling 为正比例 **70.35% / 63.72%**，最差滚动超额 **-31.58% / -36.96%**。
- Newey-West t(63) **0.9414 / 0.5404**；bootstrap 总 log excess 2.5% 分位 **-9.81% /
  -14.07%**，为正概率 **84.02% / 73.36%**。
- CSCV/PBO **0.3052 / 0.5108**；Reality Check 对零 p=**0.0012 / 0.0018**，对 LS57 超额
  p=**0.1834 / 0.2995**。对零显著只说明策略有收益，不能证明相对 LS57 的增量显著。
- all_trials DSR **0.6139 / 0.5477**，Top20/2022 DSR **0.7058 / 0.6444**，均远低于 0.95。

**判定：year-concentrated。** LS82 比 LS92 更简洁、全样本指标更好，但没有证明增量来自可重复的
carry alpha；不能因为 LS82 全样本更高就直接晋级。下一步应做 carry sleeve 的逐年/逐资产/多空腿
归因，并预注册一个只针对 2022/2025 失败机制的 regime 假设；不扫描 allocation 或 funding 阈值。

报告：`reports/ls94_ls82_robustness_2026/`；Spec：
`docs/superpowers/specs/2026-11-13-ls94-ls82-robustness.md`。
