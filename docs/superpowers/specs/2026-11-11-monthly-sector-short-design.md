# Atlas20 无杠杆多空候选预注册：H5 - 月频板块轮动空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘，不改 H5 多头账本 |
| 候选 ID | `PR2026-11-LS2-H5-MONTHLY-SECTOR` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 多头底稿 | 冻结 H5 `PR2026-10-H5`，1.0x |
| 空头 | `TOP20_SECTOR_top3_monthly_bull__none` 的 1.0x 反向目标 |
| target total gross | **0.95x**，口径为 `long gross + short gross` |
| hard total gross | **1.00x** |
| 保证金 | Bitget USDT-M isolated margin |
| 执行 | 信号日 T，T+1 UTC +3h |
| 数据 | 严格 point-in-time CMC Top20；Bitget mark；Binance funding proxy/skip 仅研究用 |
| 研究边界 | 本轮只验证一个固定点，不扫描权重、stop、buffer、周期或 funding 阈值 |

## 0. 研究问题

LS1（H5 + H4 + 14D 板块龙头空头）在 20bps 为正，但因 100bps 成本、双边 gross
超过 1.00、最佳年份依赖和全项目 DSR 不足被拒绝。LS1 的空头策略年换手约 20.5，
不适合高成本和小账户。

本轮改用一个**独立机制**：

> 历史长策略 `TOP20_SECTOR_top3_monthly_bull__none` 是亏损的、低换手的板块轮动。
> 把它以 1.0x 反向作为 H5 的空头 sleeve，同时先满足 `long + short <= 0.95`，
> 能否在无杠杆、回撤不显著变差的前提下，提高终值和 Sharpe，并通过成本、年份、
> 起点、funding 和多重检验？

这不是 LS1 的参数邻域，也不是把 LS1 的 14D 板块龙头换成另一个相似阈值。它改变的是：

- 信号频率从 14D 改为月频；
- 组合从“每个板块一个 leader”改为“前三个板块的标准行业组合”；
- 不再使用 H4 现金 sleeve；
- 空头权重从 0.2x 提高到 1.0x；
- gross 约束从“Broker 净额后 ≤0.95”改为“先按 long+short ≤0.95 缩放，再允许 Broker 净额”。

这些差异必须在报告中明确披露，不能把 LS2 的结果归因于 LS1 的 H4 sleeve。

## 1. 为什么选这个负收益长策略

项目已记录的 `reports/no_leverage_ablation_v2/` 中：

| 项目 | `TOP20_SECTOR_top3_monthly_bull__none` |
|---|---:|
| 长策略总收益 | -65.07% |
| Sharpe | -0.455 |
| MDD | -73.94% |
| 年化换手 | 1.747 |
| 平均 gross | 7.18% |
| 平均持仓数 | 0.331 |

这个长策略的机制不是“随便反向一个亏损策略”，而是：

- 只在 bull regime 持仓，天然有大量现金；
- 月频换手显著低于 LS1 的 14D 板块龙头；
- 失败来自板块轮动的选择质量，而不是低成本高频噪声；
- 反向后的平均 gross 很小，1.0x sleeve 仍然不会自动构成杠杆。

预注册前的只读日收益诊断（把已保存的长策略日收益直接取反，未经过生产引擎、未做
gross/total 约束）显示 H5 - 1.0x 该策略可能显著提高终值。该数字只作为动机，不能作为
正式验证，也不得替代生产引擎结果：

- H5 日收益：19.5253x / Sharpe 1.6231 / MDD -36.97%
- 线性反向诊断：37.7795x / Sharpe 1.9090 / MDD -31.58%
- 这是“日收益相减”的上界式诊断，不包含 short stop、margin、funding、双边 gross、
  成本方向不对称和执行时点，因此正式结果可能差很多。

## 2. 冻结构造

### 2.1 多头 H5

- 使用冻结的 `PR2026-10-H5` 目标；
- 权重为 1.0x；
- 不修改 H5 的选币、BTC gate、breadth gate、dispersion overlay、sleeve、相位和调仓规则。

### 2.2 月频板块空头

使用 `BaseSpec("TOP20_SECTOR_top3_monthly_bull", "sector", "standard", "monthly", "bull_only", top_n=3)`：

- 严格 point-in-time CMC Top20；
- 月频、bull-only；
- 前三个板块的 standard 组合；
- `overlay_id="none"`；
- 不使用 LS1 的 `sector_lead` 或 `asset_ma50`；
- 空头权重为：

```text
w_short_i,t = -1.0 * w_sector_i,t
```

这里的 1.0 是**该策略目标权重的 1.0x**，不是账户 NAV 的 100%。历史该策略平均 gross 只有
7.18%，故平均空头 gross 约为 0.072x；上限仍由总 gross 预算约束。

### 2.3 合并与双边 gross

预注册要求所有 sleeve 先合并出长期与短期 gross，再统一缩放：

```text
w_raw = 1.0 * w_H5 - 1.0 * w_sector
long_gross_raw = sum_i max(w_raw_i, 0)
short_gross_raw = sum_i max(-w_raw_i, 0)
total_gross_raw = long_gross_raw + short_gross_raw
```

如果 `total_gross_raw > 0.95`：

```text
scale = 0.95 / total_gross_raw
w_exec = scale * w_raw
```

缩放必须同时作用于多空两侧，不允许只缩放空头或只缩放多头。合并后的 Broker 净 gross
另行记录，但不能用净 gross 替代 `long + short` 的 total gross 通过硬门槛。

### 2.4 空头风险

- `long_buffer = 0.75`；
- `short_buffer = 0.50`；
- 每个空头腿 20% adverse mark stop；
- 空头 stop 后该腿回到现金，直到下一次预注册的板块目标事件重新选币；
- 不使用杠杆；target total gross 0.95，hard total gross 1.00。

### 2.5 执行与数据

- Bitget mark 1h；
- 信号日 UTC 收盘生成，T+1 UTC +3h 执行；
- 缺失 mark 资产不进入空头，不重新分配权重；
- 缺失 mark 使用不超过 3 小时的 carry，仅用于研究；
- 主研究 funding 使用 Binance proxy + `skip`，另跑 3x short-adverse；
- 缺失结算不得静默填零。

## 3. 评估门槛

### 3.1 主口径（20bps）

1. 终值严格高于同成本 H5 1.0 基线；
2. Sharpe 严格高于基线；
3. MDD 不差于基线 5 个百分点；
4. 主样本 0 次强平；
5. `max_scaled_target_total_gross <= 1.00`；
6. `max_observed_broker_gross <= 1.00`；
7. 费用、funding、空头 stop 和强平全部计入。

### 3.2 成本压力

1. 2/20/50/100bps 全部重跑；
2. 50bps 终值高于同成本基线；
3. 100bps 终值高于同成本基线；
4. 100bps MDD 不超过 50%；
5. 所有成本档都必须满足双边 gross 硬约束。

### 3.3 funding 与尾部

1. 3x short-adverse funding 下 0 次强平；
2. 3x short-adverse funding 下 MDD 不超过 50%；
3. 报告空头开仓、stop、每腿最大 adverse excursion、最差 episode 和最好 episode；
4. funding 仍是 proxy，不能称为 Bitget 精确历史。

### 3.4 日历、起点与稳定性

1. 2022/2023/2024/2025/2026 分年收益；
2. 删除候选最佳年份后仍高于同口径基线；
3. 365 天滚动最差不低于基线；
4. 至少 12 个月初的真实引擎启动重跑（每次重新构造 H5 与板块目标），且每次至少剩余 365 天：
   - 候选终值高于基线：**至少 8/12**；
   - 候选 Sharpe 高于基线：**至少 8/12**；
   - 候选 MDD 不差于基线 5pp：**12/12**。
5. 不以 2022 单一年份或单一资产贡献为主要收益来源；报告前 3 资产贡献和集中度。

### 3.5 多重检验

- 新试验必须计入 N，不得引用旧 H5 的试验数来降低门槛；
- PBO/CSCV `<= 0.50`；
- White Reality Check single-step p `<= 0.05`；
- 全项目 Deflated Sharpe `>= 0.95` 才能升级；
- 报告家族 N、Top20/2022 scope 和 all_trials scope 的 DSR；
- 不得因为 20bps 好就省略多重检验。

### 3.6 样本外

- 2026-09-22 之后为真 OOS，禁止用于调权重、stop、buffer 或周期；
- OOS 不足 12 个月时最高状态为 provisional；
- 没有 12 个月 OOS、Bitget 精确 funding、isolated margin 和强平/ADL 审查，禁止接实盘。

## 4. 失败后的动作

如果任一硬门槛失败：

- 标记 `rejected`，不能把失败项改成参考指标；
- 不扫描 H5 权重、空头权重、20% stop、long/short buffer、月频改为双周/周频；
- 不替换板块数 3 为 2/4/5；
- 不改变 Top20、成本档、funding 阈值或 total gross 定义来救本候选；
- 下一轮只能提出一个独立新机制，并在查看正式结果前重新预注册。

## 5. 与 LS1 的区别

| 维度 | LS1 | LS2 |
|---|---|---|
| 多头 | H5 1.0 + H4 0.2x | H5 1.0 |
| 空头信号 | `SECTOR_LEAD_top2` 14D + asset_ma50 | `TOP20_SECTOR_top3` 月频 none |
| 空头权重 | 0.2x | 1.0x |
| gross 定义 | Broker 净 gross 0.95 | long+short total gross 0.95 |
| 预期换手 | 高 | 低 |
| 研究问题 | H4 现金 sleeve + 龙头尾部对冲 | 低换手负收益板块长策略反向 |

## 6. 复现接口

```bash
.venv/bin/python scripts/run_monthly_sector_short.py \
  --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_monthly_sector_short

.venv/bin/python scripts/run_monthly_sector_short.py \
  --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_monthly_sector_short
```

## 7. 状态

- 当前状态：**pre-registered research candidate**；
- 是否接实盘：**否**；
- 是否修改 H5：**否**；
- 是否增加杠杆：**否**；
- 是否允许失败后参数搜索：**否**。
