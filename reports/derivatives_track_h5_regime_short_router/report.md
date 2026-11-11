# Atlas20 候选 LS12：H5 1.25x + BTC 200D 双空头 regime router

日期：2026-11-11  
候选：`PR2026-11-LS12-H5-REGIME-SHORT-ROUTER`  
状态：**rejected（研究失败）**  
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS12 把 LS6 的 funding 拥挤 H5 退出空头与 LS11 的熊市最弱四币空头做成互斥路由：
BTC 在 200D 上方时使用 LS6，跌破 200D 时使用 LS11。这个机制在 20bps 明显提高了收益和
Sharpe，滚动最差、空头集中度和 gross 都通过，但仍有三项预注册硬失败：

1. **100bps 终值 14.3604x < L125 14.3794x**；
2. **100bps Sharpe 1.3129 < L125 1.3204**；
3. **100bps MDD -50.1067%，超过 50% kill line**；

此外，删除 2022 后为 49.2413x，低于 L125 的 50.0330x；45 个已保存路径月初切片只有 44 个
三项同时通过（2023-01 起点失败）。

因此 LS12 不晋级，不进入 12 个真实引擎冷启动和 promotion multiple-testing 阶段。

## 二、预注册和实现修复

- Spec：`docs/superpowers/specs/2026-11-11-h5-regime-short-router-design.md`
- spec hash：`f81f4d0adcd4ce17381a00ff0c1576861ef8a8bcca58a9c2ee41ba740f43bcf5`
- registration hash：`c252b705c99eba3b2854051d49c20dd980597abc40b242033c6afb273785b943`
- registered at：`2026-11-11T14:39:00Z`

实现中修复了两个运行前问题：

- naive 日历与 UTC BTC 序列直接 reindex，导致首轮 regime 全部错误落为 non-bear；修复后 837 个
  bear 日、888 个 non-bear 日；
- H5 退出空头需要显式检查其执行时点是否有 Bitget mark，否则部分历史不完整的资产会进入
  无法成交的空头。

首轮 naive/UTC 错误结果已隔离在 `run_status/invalidated_regime_alignment/`，不进入判定。

## 三、冻结构造

| 项目 | 值 |
|---|---|
| H5 多头 | 1.25x target gross |
| bear sleeve | PIT Top20 14D 最弱 4 个可交易、非 H5 多头；每腿 6.25% NAV |
| bear sleeve 再平衡 | 每 7 个自然日 |
| bear funding guard | 最近 3 个 settlement 均值 > -0.0002 |
| non-bear sleeve | H5 完全退出币中 7D funding 上三分之一；21 日持有；每腿 2.5% NAV |
| 路由 | 同一时点只允许一个空头 sleeve；regime 切换后旧 sleeve 在下一执行时点清空 |
| 执行 | T+1 UTC +3h |
| stop | 20% adverse mark |
| 总空头 | <=0.25x |
| target / hard gross | 1.50x / 1.50x |
| 成本 | 2 / 20 / 50 / 100bps |
| funding | Binance proxy/skip；3x short-adverse 压力 |

## 四、主成本结果

| 指标 | L125 基线 | LS12 | 判定 |
|---|---:|---:|---|
| 终值 | 40.2200x | **55.7859x** | 通过 |
| Sharpe | 1.7330 | **1.8520** | 通过 |
| MDD | -40.6506% | **-40.6440%** | 通过 |
| 强平 | 0 | 0 | 通过 |
| short open / stop | 0 / 0 | 335 / 29 | 信息项 |
| max requested short gross | 0 | 0.25x | 通过 |
| max observed gross | 1.2811x | 1.3308x | 通过 |
| gross breach hours | 0 | 0 | 通过 |
| fees | 1.5861 | 2.7745 | 信息项 |
| funding total | -0.5918 | -0.7238 | 信息项 |

20bps 的增量收益来自两个互斥空头 sleeve；H5 多头未修改。

## 五、成本压力

| 成本 | 基线终值 | LS12 终值 | 基线 Sharpe | LS12 Sharpe | 基线 MDD | LS12 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | **75.6087x** | 1.8249 | **1.9722** | -38.42% | **-38.37%** |
| 20bps | 40.2200x | **55.7859x** | 1.7330 | **1.8520** | -40.65% | **-40.64%** |
| 50bps | 27.3725x | **33.5732x** | 1.5790 | **1.6507** | -44.2048% | -44.2531% |
| 100bps | 14.3794x | 14.3604x | 1.3204 | 1.3129 | -50.0229% | -50.1067% |

100bps 同时失败终值、Sharpe 和 50% MDD kill line。该成本档本身已接近项目尾部边界，LS12 的
高换手空头 sleeve 没有解决这个尾部问题。

## 六、funding 压力

3x short-adverse funding：

| 指标 | 结果 |
|---|---:|
| 终值 | 56.1088x |
| Sharpe | 1.8531 |
| MDD | -40.7564% |
| 强平 | 0 |
| stop | 29 |
| max observed gross | 1.3309x |

funding 压力通过。

## 七、年度、最佳年份和滚动窗口

| 年份 | L125 基线 | LS12 |
|---|---:|---:|
| 2022 | -19.61% | **+13.29%** |
| 2023 | +277.20% | +250.95% |
| 2024 | +119.25% | +100.85% |
| 2025 | +151.02% | **+170.60%** |
| 2026（至 09-20） | +141.01% | **+158.16%** |

删除最佳年份后的终值：

| 删除年份 | L125 基线 | LS12 | 判定 |
|---:|---:|---:|---|
| 2022 | 50.0330x | 49.2413x | **失败** |
| 2023 | 10.6628x | **15.8955x** | 通过 |
| 2024 | 18.3441x | **27.7753x** | 通过 |
| 2025 | 16.0225x | **20.6160x** | 通过 |
| 2026 | 16.6884x | **21.6088x** | 通过 |

365 天滚动最差：

| 候选 | 滚动最差 | 中位数 |
|---|---:|---:|
| L125 基线 | 0.7325x | 2.5547x |
| LS12 | **0.7731x** | **2.6444x** |

滚动最差和删除 2023/2024/2025/2026 都通过；删除 2022 失败说明增量收益仍偏向 2022，
LS12 没有完全摆脱熊市依赖。

## 八、45 个月初路径切片

| 门槛 | 通过数 |
|---|---:|
| 终值胜过基线 | 44/45 |
| Sharpe 胜过基线 | 44/45 |
| MDD 不差于基线 +5pp | 45/45 |
| 三项同时通过 | **44/45** |

唯一失败起点为 2023-01-01：终值 49.2413x vs 50.0330x，Sharpe 2.0605 vs 2.0657；
MDD 通过了 5pp 约束。

## 九、空头归因

335 个可配对空头 episode：

| 指标 | 结果 |
|---|---:|
| 正贡献 episode | 169 |
| 负贡献 episode | 166 |
| episode PnL 对开仓权益合计 | +33.6287% |
| 平均 | +0.1004% |
| 中位 | +0.0099% |
| 最差 episode | -1.3807% |
| 最好 episode | +6.3847% |

资产集中度：

| 资产 | episode | 净贡献份额 |
|---|---:|---:|
| Ethereum | 15 | 23.35% |
| Sui | 11 | 20.24% |
| Bitcoin Cash | 15 | 18.32% |
| 前 3 合计 | 41 | **61.92%** |

单资产最大 23.35%、前 3 61.92%，集中度门槛通过。

## 十、未继续执行的阶段

LS12 已触发 100bps 终值/Sharpe/MDD、删除 2022 和 44/45 路径切片失败，因此按预注册：

- 不继续 12 个真实引擎月初冷启动；
- 不把 PBO/RC/DSR 阶段用于救活已被硬门槛拒绝的候选；
- 不扫描 sleeve 权重、MA 窗口、bottom 数量、lookback、再平衡、stop、buffer 或总空头；
- 不接入执行器或修改当前实盘。

## 十一、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS12-H5-REGIME-SHORT-ROUTER \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_regime_short_router
```

完整成本日志在 `run_status/`；归因文件在候选目录下的
`short_episode_attribution.csv`、`short_asset_attribution.csv` 和
`short_attribution_summary.json`。

## 十二、最终判定

**LS12 rejected。**

regime router 证明两种空头 alpha 可以互补，并在 20bps/50bps 明显增强收益，但没有修复
100bps 尾部、删除 2022 和 2023 起点路径。按预注册不得用事后权重或参数调整重试；当前实盘
H5 多头配置保持不变。
