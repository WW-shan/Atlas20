# Atlas20 无杠杆多空候选预注册：H5 退出币 21 天空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘，不改 H5 多头账本 |
| 候选 ID | `PR2026-11-LS3-H5-EXIT-SHORT21` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 多头 | 冻结 H5 `PR2026-10-H5`，1.0x |
| 空头信号 | H5 实际清仓退出的资产，固定 21 个日历日 |
| 空头资金 | 只使用 H5 未使用的 gross 预算，不重分配 H5 多头 |
| target total gross | **0.95x** |
| hard observed gross | **1.00x** |
| 保证金 | Bitget USDT-M isolated margin |
| 执行 | H5 信号日 T，T+1 UTC +3h |
| 数据 | 严格 point-in-time CMC Top20；Bitget mark；Binance funding proxy/skip |
| 研究边界 | 本轮只验证一个固定点，不扫描持有期、stop、buffer、权重或 gross 阈值 |

## 0. 研究问题

LS1（H4 现金 sleeve + 板块龙头空头）和 LS2（月频板块长策略反向）都被正式拒绝。两者的共同失败是：
空头信号本身没有稳定超额，且在真实 stop、保证金、成本和持仓漂移下无法保持优势。

本轮不再反向一个外部长策略，而是检验 H5 自身的一个可观测事件：

> 当 H5 把一个资产从多头账本中完全卖出后，这个资产在未来 21 天是否继续跑输当时的 point-in-time
> Top20 等权篮子？如果存在，能否只用 H5 闲置的 gross 预算做空它，在不降低 H5 多头的前提下
> 提高收益/Sharpe，并保持回撤和 gross 约束？

## 1. 预注册前的退出事件诊断（不是正式回测）

使用冻结 H5 的目标事件，比较“前一个 H5 目标持有、当前目标已完全退出”的资产。只保留在信号日
仍属于 point-in-time Top20 的资产。入场按退出信号后的下一个日线交易日，收益对当时 Top20 等权篮子计算。

| 前向窗口 | 观测数 | 平均相对收益 | 中位数 | 跑输概率 | iid t |
|---:|---:|---:|---:|---:|---:|
| 7D | 117 | -1.10% | -1.36% | 61.5% | -1.30 |
| 14D | 117 | -2.44% | -1.94% | 61.5% | -2.23 |
| **21D** | **117** | **-4.18%** | **-4.97%** | **66.7%** | **-3.18** |
| 30D | 117 | -4.66% | -4.05% | 63.2% | -2.89 |
| 60D | 117 | -5.46% | -6.70% | 65.0% | -2.61 |

21D 年度拆分：2022 -0.61%、2023 +0.93%、2024 -9.50%、2025 -5.98%、2026 -0.18%。
这说明效应不是只靠 2022；但 2023 为正，不能声称每年都有效。

诊断文件：

- `reports/h5_exit_short_diagnostic_2026_11_11/exit_forward_returns.csv`
- `reports/h5_exit_short_diagnostic_2026_11_11/exit_short_summary.csv`

该诊断不是生产引擎回测，不含空头 stop、margin、funding、Bolton 成本或 gross 漂移；不能作为正式结果。

## 2. 冻结构造

### 2.1 H5 多头

- 使用冻结 `PR2026-10-H5`；
- 权重 1.0x；
- 不修改 H5 的选币、BTC gate、breadth gate、dispersion overlay、sleeve、相位和调仓规则；
- H5 多头只在其自身目标事件变化。

### 2.2 退出定义

在 H5 目标事件日 `t`：

- `P` = 前一个 H5 目标事件中权重 > 0 的资产集合；
- `C` = 当前 H5 目标事件中权重 > 0 的资产集合；
- `E = P - C` 是退出集合；
- 只有同时满足以下条件的资产可以进入空头：
  - 在 `t` 的 point-in-time CMC Top20 中；
  - 有 Bitget 执行 mark；
  - 当前没有同一资产的活跃空头。

若资产在 21 天持有期内重新进入 H5 目标，空头立即在下一次执行时点关闭。

### 2.3 空头权重

活跃退出资产等权占用“H5 未使用的 gross”：

```text
long_gross_t = sum(abs(w_H5_t))
available_t = max(0, 0.95 - long_gross_t)
short_budget_t = min(1.0, available_t / requested_short_gross_t)
w_short_i,t = -short_budget_t / N_active
```

其中 `N_active` 是当日有 mark 的活跃退出资产数。空头不缩减 H5 多头。

如果 H5 自身 gross 超过 0.95（极少见的 target event），则先把 H5 目标缩放到 0.95，且该事件不新开
空头；不允许通过加杠杆保留 H5 超额 gross。

### 2.4 空头生命周期

- 持有期固定 **21 个日历日**；
- 到期后在下一执行时点关闭；
- H5 重新买入时提前关闭；
- 空头 20% adverse mark stop；
- 空头 stop 后该腿回到现金，直到下一次新的退出事件；
- 同一资产不因重复退出事件延长期限，必须等前一次 episode 结束。

### 2.5 总 gross、执行和数据

- target total gross 0.95；
- hard observed gross 1.00；
- `long_buffer=0.75`；
- `short_buffer=0.50`；
- Bitget mark 1h；T+1 UTC +3h；
- 缺失 mark 资产不进入空头，不重新分配其权重；
- 缺失 mark 最多 carry 3 小时，仅研究用；
- 主 funding 用 Binance proxy + `skip`；另跑 3x short-adverse；
- 任何分钟级 gross 超过 1.00 都必须报告。

### 2.6 逐小时 gross guard

引擎在收盘观察到 `observed gross > 1.00` 后，必须在**下一个可执行小时**按市价减仓，
把 gross 恢复到 `<=0.95`。guard：

- 不使用未来价格；
- 记录实际费用和 `reason=gross_guard` 的成交；
- 不得用目标层 gross 替代 observed gross；
- 不得在 historical path 中事后挑选减仓顺序；所有多空腿按同一比例缩减。

guard 是风险自愈机制，不是放宽 hard gross 门槛：主样本只要出现任何 `observed gross > 1.00`
仍记为失败，guard 只能降低持续时间和后续风险。

## 3. 评估门槛

### 3.1 主口径（20bps）

1. 终值严格高于同成本 H5 基线；
2. Sharpe 严格高于基线；
3. MDD 不差于基线 5 个百分点；
4. 主样本 0 次强平；
5. max target total gross <= 1.00；
6. max observed gross <= 1.00；
7. 所有空头 stop、funding、费用和 guard 成交计入。

### 3.2 成本压力

1. 2/20/50/100bps 全部重跑；
2. 50bps 终值高于同成本基线；
3. 100bps 终值高于同成本基线；
4. 100bps MDD 不超过 50%；
5. 四档都满足 gross 硬约束。

### 3.3 funding 与尾部

1. 3x short-adverse funding 下 0 次强平；
2. 3x short-adverse funding 下 MDD 不超过 50%；
3. 报告空头 episode 数、stop 数、最差/最好 episode 和每个资产的最大 adverse excursion；
4. funding 仍是 proxy，不能称为 Bitget 精确历史。

### 3.4 日历、起点和稳定性

1. 2022/2023/2024/2025/2026 分年收益；
2. 删除候选最佳年份后仍高于同口径基线；
3. 365 天滚动最差不低于基线；
4. 至少 12 个月初的真实引擎启动重跑，每次重新构造 H5 exit schedule 且至少剩余 365 天：
   - 候选终值高于基线：至少 8/12；
   - 候选 Sharpe 高于基线：至少 8/12；
   - 候选 MDD 不差于基线 5pp：12/12。
5. 不应由 2022 单一自然年或单资产主导；报告资产贡献和集中度。

### 3.5 多重检验

- 新试验计入 N；
- PBO/CSCV <= 0.50；
- White Reality Check single-step p <= 0.05；
- 全项目 Deflated Sharpe >= 0.95 才能升级；
- 报告 family、Top20/2022 scope 和 all_trials scope；
- 不因 20bps 正结果省略多重检验。

### 3.6 样本外

- 2026-09-22 之后是真 OOS，不得用于调权重、stop、持有期或 guard；
- OOS 不足 12 个月时最高状态 provisional；
- 没有 12 个月 OOS、Bitget 精确 funding、isolated margin 与 ADL 审查，禁止接实盘。

## 4. 失败后的动作

如果任一硬门槛失败：

- 标记 `rejected`，失败项不能降级成参考指标；
- 不扫描持有期 7/14/28/30/60；
- 不扫描 15%/25%/30% stop；
- 不扫描 long/short buffer；
- 不改变 0.95 target / 1.00 hard；
- 不把 exit 定义改成“部分减仓”或“任何权重变化”；
- 不改变 Top20、成本档或 funding policy 来救候选；
- 下一轮只能提出新的独立机制并重新预注册。

## 5. 与 LS1/LS2 的区别

| 维度 | LS1 | LS2 | LS3 |
|---|---|---|---|
| 信号 | H4 + 14D 板块龙头 | 月频板块长策略反向 | H5 自身退出事件 |
| 多头 | H5+H4 | H5 | H5 |
| 空头资金 | 与多头同时占用 | 缩放 both sides | 只用 H5 闲置 gross |
| 持有期 | 14D 策略事件 | 月频 | 固定 21D |
| stop | 20% | 20% | 20% |
| gross guard | 无 | 无 | 逐小时 next-tick guard |
| 证据 | 旧负收益诊断 | 旧负收益长策略 | H5 退出后相对跑输 4.18%/21D |

## 6. 复现接口

```bash
.venv/bin/python scripts/run_h5_exit_short.py \
  --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_short

.venv/bin/python scripts/run_h5_exit_short.py \
  --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_short
```

## 7. 状态

- 当前状态：**pre-registered research candidate**；
- 是否接实盘：**否**；
- 是否修改 H5：**否**；
- 是否增加杠杆：**否**；
- 是否允许失败后参数搜索：**否**。
