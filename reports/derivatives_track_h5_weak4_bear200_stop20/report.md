# Atlas20 候选 LS11：H5 1.25x + BTC 200D 熊市闸门下的最弱四币空头

日期：2026-11-11  
候选：`PR2026-11-LS11-H5-WEAK4-BEAR200-STOP20`  
状态：**rejected（研究失败）**  
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS11 把 R6 的 14D 最弱四币空头限制在 BTC close < 200D SMA 的周频信号内，目的是保留熊市
相对价值收益并减少牛市噪声换手。它在主成本 20bps 上确实提高了收益和 Sharpe，也改善了 365 天
滚动最差，但没有通过预注册的路径、成本和集中度门槛：

1. **100bps MDD -50.0131%，超过 50% kill line**；
2. **删除 2022 后 46.6087x，低于 L125 的 50.0330x**；
3. **45 个已保存路径的月初切片仅 22/45 三项同时通过**；
4. **前 3 空头贡献 90.57%，超过 80% 上限**。

因此 LS11 不是可晋级候选，也不进入 12 个真实引擎冷启动和 promotion multiple-testing 阶段。
研究输出不是订单，不修改实盘。

## 二、预注册和实现修复

- Spec：`docs/superpowers/specs/2026-11-11-h5-weak4-bear200-stop20-design.md`
- registered spec hash：`f28e7ead5a0cac3bf40aed2cfdf03907b1ddcea4bd085a923ccfa7e6e5ee0b12`
- registration hash：`8980ba19c96250fcfb2c896ef4cdc690cefc71fda53606f1e635a750ab06a1f8`
- registered at：`2026-11-11T14:12:33Z`

实现上新增 `cross_sectional_entry_allowed` 入口，并用 UTC 归一化后的 BTC close/SMA 序列
驱动 200D 闸门。回归测试验证闸门关闭时只保留 H5 多头账本，空头目标必须完全为空。

## 三、冻结构造

| 项目 | 值 |
|---|---|
| H5 多头 | 1.25x target gross |
| 空头候选池 | PIT CMC Top20 ∩ Bitget mark available ∩ funding guard − H5 当前多头 |
| 空头排序 | 14D 收益最弱 4 个，等权 |
| 熊市闸门 | 信号日 BTC close < 200D SMA |
| 再平衡 | 每 7 个自然日，T+1 UTC +3h |
| 单腿权重 | 6.25% NAV |
| 总空头 | 0.25x |
| 单腿 stop | 20% adverse mark |
| target / hard gross | 1.50x / 1.50x |
| 成本 | 2 / 20 / 50 / 100bps |
| funding | Binance proxy/skip，并做 3x short-adverse 压力 |

## 四、主成本结果

| 指标 | L125 基线 | LS11 | 判定 |
|---|---:|---:|---|
| 终值 | 40.2200x | **49.7952x** | 通过 |
| Sharpe | 1.7330 | **1.8069** | 通过 |
| MDD | -40.6506% | **-40.6506%** | 通过 |
| 强平 | 0 | 0 | 通过 |
| short open / stop | 0 / 0 | 278 个 episode / 27 个 stop | 信息项 |
| max observed gross | 1.2811x | 1.3872x | 通过 |
| fees | 1.5861 | 2.5857 | 信息项 |
| funding total | -0.5918 | -0.6754 | 信息项 |

主成本 20bps 的收益提升来自空头 sleeve；多头账本完全冻结，未改 H5 信号。

## 五、成本压力

| 成本 | 基线终值 | LS11 终值 | 基线 Sharpe | LS11 Sharpe | 基线 MDD | LS11 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | **66.9505x** | 1.8249 | **1.9240** | -38.42% | **-38.42%** |
| 20bps | 40.2200x | **49.7952x** | 1.7330 | **1.8069** | -40.65% | **-40.65%** |
| 50bps | 27.3725x | **30.3724x** | 1.5790 | **1.6107** | -44.20% | **-44.20%** |
| 100bps | 14.3794x | 13.2854x | 1.3204 | 1.2817 | -50.0229% | **-50.0131%** |

2/20/50bps 的终值和 Sharpe 都高于同成本基线；100bps 终值低于基线，且 MDD 仍越过 50% kill line。
这是预注册门槛的硬失败，不能通过事后调整 50% 线解决。

## 六、funding 压力

3x short-adverse funding：

| 指标 | 结果 |
|---|---:|
| 终值 | 50.7173x |
| Sharpe | 1.8130 |
| MDD | -40.7198% |
| 强平 | 0 |
| stop | 27 |
| max observed gross | 1.3870x |

funding 压力通过，但不是足以抵消其他硬失败的证据。

## 七、年度、最佳年份和滚动窗口

| 年份 | L125 基线 | LS11 |
|---|---:|---:|
| 2022 | -19.61% | **+6.84%** |
| 2023 | +277.20% | +252.85% |
| 2024 | +119.25% | +98.74% |
| 2025 | +151.02% | **+162.04%** |
| 2026（至 09-20） | +141.01% | **+153.64%** |

删除最佳年份后的终值：

| 删除年份 | L125 基线 | LS11 | 判定 |
|---:|---:|---:|---|
| 2022 | 50.0330x | 46.6087x | **失败** |
| 2023 | 10.6628x | **14.1121x** | 通过 |
| 2024 | 18.3441x | **25.0554x** | 通过 |
| 2025 | 16.0225x | **19.0027x** | 通过 |
| 2026 | 16.6884x | **19.6325x** | 通过 |

365 天滚动最差：

| 候选 | 滚动最差 | 中位数 |
|---|---:|---:|
| L125 基线 | 0.7325x | 2.5547x |
| LS11 | **0.7735x** | **2.5585x** |

滚动最差改善，但删除 2022 后仍失败；这说明 LS11 把过多增量收益集中到 2022 熊市窗口。

## 八、45 个已保存路径月初切片

| 门槛 | 通过数 |
|---|---:|
| 终值胜过基线 | 24/45 |
| Sharpe 胜过基线 | 22/45 |
| MDD 不差于基线 +5pp | 29/45 |
| 三项同时通过 | **22/45** |

这不是单一全样本路径上的小瑕疵，而是多数滚动起点无法同时保持收益、Sharpe 和回撤约束。

## 九、空头归因

278 个可配对空头 episode：

| 指标 | 结果 |
|---|---:|
| 正贡献 episode | 138 |
| 负贡献 episode | 140 |
| episode PnL 对开仓权益合计 | +16.9344% |
| 平均 | +0.0609% |
| 中位 | -0.0060% |
| 最差 episode | -5.1868% |
| 最好 episode | +6.7086% |

资产集中度：

| 资产 | episode | 净贡献份额 |
|---|---:|---:|
| Ethereum | 13 | 32.20% |
| Sui | 9 | 30.55% |
| Bitcoin Cash | 13 | 27.81% |
| 前 3 合计 | 35 | **90.57%** |

单资产最大 32.20% 通过，但前 3 90.57% 超过 80% 上限。LS11 的增量收益不是广泛横截面
alpha，而是少数资产贡献主导的结果。

## 十、未继续执行的阶段

LS11 已触发 100bps MDD、删除 2022、路径切片和空头集中度四个硬失败，因此按预注册：

- 不继续 12 个真实引擎月初冷启动；
- 不把 PBO/RC/DSR 的高计算成本阶段用来救活已被硬门槛拒绝的候选；
- 不扫描 BTC MA 窗口、bottom 数量、lookback、再平衡、stop、buffer 或总空头权重；
- 不把本候选接入执行器或修改当前实盘。

后续研究必须提出机制不同的新候选，并重新预注册。

## 十一、复现

```bash
.venv/bin/python scripts/run_derivatives_backtest.py \
  --trial-id PR2026-11-LS11-H5-WEAK4-BEAR200-STOP20 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_weak4_bear200_stop20

.venv/bin/python scripts/derivatives_robustness.py \
  --returns reports/derivatives_track_h5_weak4_bear200_stop20/returns_20bps.csv \
  --output-dir reports/derivatives_track_h5_weak4_bear200_stop20/robustness
```

完整成本日志在 `run_status/`，归因文件在候选目录下的
`short_episode_attribution.csv`、`short_asset_attribution.csv` 和 `short_attribution_summary.json`。

## 十二、最终判定

**LS11 rejected。**

BTC 200D 熊市闸门改善了 2022 和滚动最差，但没有解决 100bps 尾部、2022 依赖、多数路径
起点失败和空头集中度。按预注册不得用事后参数调整重试；当前实盘 H5 多头配置保持不变。
