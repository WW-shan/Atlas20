# Atlas20 无杠杆多空候选 LS1：H5 + H4 现金 sleeve + 板块龙头空头

日期：2026-11-11  
候选：`PR2026-11-LS1-H5-H4-SECTOR20`  
状态：**rejected（研究失败）**  
实盘：**不接；H5 现有多头配置不变**

## 一、结论

20bps 主口径表面上是正结果：

- H5 基线：**21.3487x**，Sharpe **1.7361**，MDD **-33.36%**
- LS1 候选：**26.2617x**，Sharpe **1.8603**，MDD **-27.60%**
- 候选 0 次强平，14 次空头止损，Broker 净 gross 最大 **0.9655x**

但预注册的硬门槛至少有四项独立失败：

1. **100bps 成本失败**：候选 **9.0509x** 低于同成本基线 **9.3848x**，Sharpe 也略低。
2. **双边 gross 失败**：按预注册的 `long gross + short gross` 口径，目标层最大双边 gross 为 **1.3422x**，超过硬上限 **1.00x**；Broker 净持仓 gross 只有 0.9708x，因为同一资产的多空腿被净额化。
3. **最佳年份依赖**：移除候选最佳年份 2023 后，候选 **6.9143x** 低于同口径基线 **7.0894x**。
4. **全项目 DSR 失败**：按当前全部试验数 `N=14,171` 的 DSR 为 **0.9406**，低于预注册的 **0.95**。

此外，45 个“至少剩余 365 天”的月初收益切片中，只有 **22/45** 的候选终值高于基线，说明前段优势没有稳定延续到更晚的启动时点。

因此，**不能把这个候选升级为 provisional 或 live-ready，也不能在失败后通过扫描 H4 权重、空头权重、stop、buffer 或 funding 阈值来救参。**

## 二、冻结构造

```text
w = 1.0 * w_H5
  + 0.2 * w_H4
  - 0.2 * w_SECTOR_LEAD_top2__asset_ma50
```

| 项目 | 冻结值 |
|---|---|
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 日收益行数 | 1,724 |
| H5 权重 | 1.0x |
| H4 现金 sleeve | 0.2x H4 目标权重 |
| 板块龙头空头 | 0.2x `SECTOR_LEAD_top2__asset_ma50` 目标权重 |
| target net gross | 0.95 |
| Broker 最大净 gross | 0.95 |
| 硬双边 gross | 1.00 |
| long buffer | 0.75 |
| short buffer | 0.50 |
| 空头 adverse mark stop | 20% |
| 执行 | 信号日 T，T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| funding | Binance proxy + missing=`skip`；另跑 3x short-adverse |
| mark | Bitget mark，缺失 carry 最多 3 小时 |

预注册文件：

- Spec：`docs/superpowers/specs/2026-11-11-long-short-cash-sleeve-design.md`
- Plan：`docs/superpowers/plans/2026-11-11-long-short-cash-sleeve.md`
- Ledger registration SHA-256：`8aac98afb3be8e3958db09ec7b5f2161b6cb613597f96661611d97c729b3ffbf`
- Ledger spec SHA-256：`e4941e6f5891c03fbdbe8ebd5b34e7f010cda82d8cd6cb720eb318f6edf100cc`

## 三、20bps 主口径

| 指标 | H5 1.0 基线 | LS1 候选 |
|---|---:|---:|
| 终值 | 21.3487x | **26.2617x** |
| CAGR | 91.26% | **99.83%** |
| Sharpe | 1.7361 | **1.8603** |
| 最大回撤 | -33.36% | **-27.60%** |
| 强平次数 | 0 | 0 |
| 空头止损次数 | 0 | 14 |
| 最大 Broker 净 gross | 0.9568x | 0.9655x |
| 平均 Broker 净 gross | 0.2371x | 0.2832x |
| 平均目标净 gross | 0.4561x | 0.4991x |
| 费用总额 | 0.8830 | 1.4582 |
| funding 净额 | -0.3416 | -0.4051 |

主口径的终值、Sharpe、MDD、零强平、Broker 净 gross 五项通过；但这不足以覆盖下面的独立硬失败。

## 四、成本压力

所有成本档均使用同一 Bitget mark、同一冻结目标和同成本基线。

| 成本 | 基线终值 | 候选终值 | 基线 Sharpe | 候选 Sharpe | 基线 MDD | 候选 MDD | 终值高于基线 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 2bps | 25.6692x | **33.3501x** | 1.8277 | **1.9802** | -31.41% | **-25.22%** | 是 |
| 20bps | 21.3487x | **26.2617x** | 1.7361 | **1.8603** | -33.36% | **-27.60%** | 是 |
| 50bps | 15.6946x | **17.6243x** | 1.5826 | **1.6591** | -36.59% | **-31.40%** | 是 |
| 100bps | **9.3848x** | 9.0509x | **1.3251** | 1.3209 | -41.92% | **-38.09%** | **否（失败）** |

100bps 候选 MDD 为 -38.09%，低于 50% kill line；但终值和 Sharpe 同时低于基线，仍是明确失败。

## 五、funding 压力

3x short-adverse funding（20bps；空头 adverse funding 乘以 3，多头 funding 置零，避免被多头收入抵消）：

| 指标 | 结果 |
|---|---:|
| 终值 | 27.8544x |
| Sharpe | 1.8887 |
| MDD | -27.89% |
| 强平 | 0 |
| 空头止损 | 14 |
| 最大 Broker 净 gross | 0.9654x |
| funding 净额 | -0.0410 |

该压力测试本身通过，但 funding 仍是 Binance proxy，缺失结算按 `skip`，**不能声称已经闭合 Bitget 精确历史 funding**。

## 六、双边 gross：净额化掩盖了真实暴露

预注册要求同时记录 net target、long gross、short gross 和 `long + short` 的 total gross，不能把净额当作总 gross。

| 指标 | 数值 |
|---|---:|
| 平均 H5 gross | 0.4244x |
| 平均 H4 sleeve gross | 0.1380x |
| 平均空头 sleeve gross | 0.1322x |
| 平均 raw net gross | 0.5100x |
| 平均缩放后 long gross | 0.5515x |
| 平均缩放后 short gross | 0.1310x |
| 平均缩放后 net gross | 0.4991x |
| **最大缩放后双边 gross** | **1.3422x（2025-10-01）** |
| **最大缩放后 long gross** | **1.1461x** |
| 最大缩放后 short gross | 0.2000x |
| 同资产同时多空的 target events | **581 / 843** |

Broker 先净额化同一资产的多空腿，所以引擎的净持仓 gross 没有超过 1.00。但规格明确要求 hard gross 使用 **long + short**，不能以净额通过。该候选因此在目标层已经违反硬约束，且不是事后漂移造成。

## 七、日历与起点稳定性

### 7.1 年度收益

| 年份 | H5 基线 | LS1 候选 |
|---|---:|---:|
| 2022 | -15.74% | -15.40% |
| 2023 | 201.14% | **279.82%** |
| 2024 | 94.61% | **99.67%** |
| 2025 | 112.35% | **113.41%** |
| 2026（至 09-20） | **103.60%** | 91.80% |

收益在 2023 年显著集中，2026 年反而落后。

### 7.2 最佳年份移除

候选最佳年份是 2023。删除该年后，候选终值 **6.9143x**，同口径基线 **7.0894x**，候选低于基线，失败。

### 7.3 365 天滚动最差

| 候选 | 最差滚动 365 天终值 | 中位数 |
|---|---:|---:|
| H5 基线 | 0.7970x | 2.1634x |
| LS1 候选 | **0.8460x** | 2.1949x |

这一项通过。

### 7.4 月初起点切片

对 2022-01 至 2025-09 的 45 个月初，在保留至少 365 天历史的条件下，从该起点重新计算后续收益路径：

- 候选终值高于基线：**22 / 45**
- 候选 Sharpe 高于基线：**34 / 45**
- 候选 MDD 不差于基线 5pp：**45 / 45**
- 三项同时通过：**22 / 45**

2024 年后的多数起点终值低于基线。该结果是 launch-phase 不稳定的明确警告；由于这是对已保存日收益的后续路径切片，不是每次重新生成信号的独立引擎启动，报告不把它升级为样本外证据。

## 八、多重检验

统计使用同一 1,724 天共同样本。

| 项目 | 结果 | 门槛 | 判定 |
|---|---:|---:|---|
| PBO / CSCV | 0.1429 | ≤ 0.50 | 通过 |
| White Reality Check vs zero | p=0.003996 | ≤ 0.05 | 通过 |
| White Reality Check vs BTC | p=0.014985 | ≤ 0.05 | 通过 |
| DSR，候选族 N=2 | 0.999998 | ≥ 0.95 | 通过（但 N 太小） |
| DSR，Top20/2022 scope N=6,142 | 0.957880 | ≥ 0.95 | 通过 |
| **DSR，全项目 N=14,171** | **0.940565** | ≥ 0.95 | **失败** |

全项目 N 包含现货轨和衍生品轨的全部已记录试验。PBO 只有两个正式收益流可比较，不能替代全项目 DSR；它不证明这个固定点在更大搜索历史中没有被选中偏差抬高。

## 九、空头腿事件归因

在 20bps 候选运行中重建 88 个完整空头 episode（26 个资产），交易费用和空头 funding 均与引擎账本逐分对账：

| 指标 | 结果 |
|---|---:|
| 空头开仓 episode | 88 |
| 正贡献 episode | 52 |
| 负贡献 episode | 36 |
| 空头 stop | 14 |
| episode PnL 对开仓时权益的合计 | **+3.854%** |
| 最差 episode | **-3.699%** |
| 最好 episode | **+2.954%** |
| 最大 adverse mark loss 对开仓时权益 | **3.546%** |

说明：

- 百分比以每个 episode 开仓时的账户权益为分母；不同 episode 的分母不同，因此合计是诊断性加总，不是可直接复利的组合收益。
- 空头不是稳定的独立 alpha，更像小权重、事件型、与多头部分净额化的对冲腿。
- 同资产同时多空的事件有 581/843，因此无法仅靠 88 个空头 episode 把 H4 与空头的组合层贡献完全拆开；这项归因只覆盖可审计的空头腿，不把它外推为 sleeve 的完整收益归因。

## 十、预注册门槛逐项判定

| 门槛 | 结果 | 判定 |
|---|---|---|
| 20bps 终值高于基线 | 26.2617x > 21.3487x | 通过 |
| 20bps Sharpe 高于基线 | 1.8603 > 1.7361 | 通过 |
| MDD 不比基线差 5pp | -27.60% vs -33.36% | 通过 |
| 主样本 0 强平 | 0 | 通过 |
| Broker 最大净 gross ≤ 1.00 | 0.9655x | 通过 |
| **双边 total gross ≤ 1.00** | **1.3422x** | **失败** |
| 50bps 终值高于基线 | 17.6243x > 15.6946x | 通过 |
| 100bps 终值高于基线 | 9.0509x < 9.3848x | **失败** |
| 100bps MDD ≤ 50% | -38.09% | 通过 |
| 3x short-adverse funding 0 强平 | 0 | 通过 |
| 3x short-adverse funding MDD ≤ 50% | -27.89% | 通过 |
| 移除最佳年份仍高于基线 | 6.9143x < 7.0894x | **失败** |
| 365 天滚动最差不低于基线 | 0.8460x > 0.7970x | 通过 |
| 月初起点稳定 | 22/45 三项通过 | **不稳定** |
| PBO ≤ 0.50 | 0.1429 | 通过 |
| Reality Check p ≤ 0.05 | 0.003996 / 0.014985 | 通过 |
| **全项目 DSR ≥ 0.95** | **0.940565** | **失败** |
| 12 个月真 OOS | 未完成 | 不可升级 |
| Bitget 精确 funding | 未完成 | 不可升级 |
| isolated-margin 实盘验证 | 未进行 | 不可升级 |

## 十一、最终判定与后续

**判定：rejected。**

失败原因不是单一的“成本略高”，而是：

- 高换手在 100bps 下把优势完全吃掉；
- 预注册的双边 gross 定义下，构造本身超过 1.00；
- 超额收益依赖 2023；
- 更晚的月初起点多数不再优于基线；
- 全项目多重检验后的 DSR 未过 0.95。

按预注册约束，不允许继续扫描：

- H4 权重 0.1 / 0.3 / 0.4；
- 空头权重 0.1 / 0.3 / 0.4；
- 20% stop 的 15% / 25% / 30%；
- long buffer 0.60 / 0.65 / 0.70；
- funding threshold；
- 更改 Top20 或成本档位来救活本候选。

下一轮若继续，只能预注册一个**机制不同**的候选：先遵守 `long + short` 的硬 gross 预算，并且在进入回测前固定成本、年份、起点、funding 和多重检验 kill criteria。当前 H5 实盘不受影响。

## 十二、复现

```bash
.venv/bin/python scripts/run_long_short_cash_sleeve.py \
  --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_long_short_cash_sleeve

.venv/bin/python scripts/run_long_short_cash_sleeve.py \
  --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_long_short_cash_sleeve

.venv/bin/python scripts/run_long_short_cash_sleeve.py \
  --cost-bps 20 --funding-source binance-proxy \
  --funding-missing-policy skip --funding-stress short-adverse \
  --funding-multiplier 3 \
  --output-dir reports/derivatives_track_long_short_cash_sleeve
```

明细文件：

- `returns_20bps.csv`
- `cost_comparison.csv`
- `target_sleeve_attribution.csv`
- `PR2026-11-LS1-H5-H4-SECTOR20_cost20_proxy/short_episodes.csv`
- `PR2026-11-LS1-H5-H4-SECTOR20_cost20_proxy/short_asset_attribution.csv`
- `robustness/yearly_returns.csv`
- `robustness/best_year_removal.csv`
- `robustness/rolling_worst.csv`
- `robustness/monthly_start_slices.csv`
- `multiple_testing/summary.json`
- `multiple_testing_project/deflated_sharpe.csv`
