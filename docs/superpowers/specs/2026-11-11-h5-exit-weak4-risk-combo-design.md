# Atlas20 无杠杆多空候选预注册：H5 退出币 + 14D 最弱篮子固定风险空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘，不改 H5 多头账本 |
| 候选 ID | `PR2026-11-LS5-H5-EXIT-WEAK4-RISK05` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 多头 | 冻结 H5 `PR2026-10-H5`，1.0x |
| 空头 sleeve A | H5 完全退出资产，固定 21 个日历日 |
| 空头 sleeve B | PIT Top20 内 14D 最弱 4 个可交易资产，固定 7 日再平衡 |
| 单腿 notional | 2.5% NAV |
| 单腿名义 stop 风险 | 0.5% NAV |
| 空头 stop | 20% adverse mark |
| 重叠处理 | 同一资产最多一条 2.5% NAV 空头腿 |
| 资金约束 | 只使用 H5 未使用的 gross |
| target total gross | 0.95x |
| hard observed gross | 1.00x |
| 执行 | T+1 UTC +3h |
| 数据 | 严格 point-in-time CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS4 证明 H5 exit-short 具有真实的正贡献，并且固定 2.5% NAV 单腿可以把 observed gross 压到 1.00 以下：

- 20bps：23.8448x / Sharpe 1.8091 / MDD -34.12%；
- 2/20/50/100bps 全部高于 H5；
- 12/12 真实引擎月度冷启动通过；
- 但 365 天滚动最差 0.7838x 低于基线 0.7970x，Top20 DSR 0.9424、全项目 DSR 0.9207 均失败。

R6 证明 Top20 内 14D 最弱 4 币空头具有更强的 Sharpe，但其 H5 ×1.25、0.25x 短篮子和周换手在 100bps 与 2022 依赖上失败。

本轮研究问题：

> 把两个已经分别验证过、但失败原因不同的空头信号合并，并统一使用 LS4 的 2.5% NAV 固定风险腿，能否在**不加杠杆、hard gross <= 1.00** 的条件下提高收益、改善滚动最差并通过全项目多重检验？

这不是 LS4 或 R6 的参数扫描。组合机制只改变空头信号来源和合并方式；单腿风险、stop、持有期、周频与 gross 上限均沿用已预注册值。

## 1. 预注册前证据

### 1.1 LS4

LS4 的固定风险规则：

```text
short_notional = risk_budget / stop_distance
               = 0.005 / 0.20
               = 0.025 NAV
```

其 140 个 exit-short episode 合计贡献 +10.497% 开仓权益，最大 adverse mark loss 0.6491% NAV。该偏差必须由实际引擎继续披露。

### 1.2 R6

R6 使用 H5 ×1.25 加 Top20 14D 最弱 4 币等权空头，总空头 0.25x，每腿 6.25% NAV，20% stop。20bps Sharpe 1.8918，但 100bps MDD -54.06%、移除 2022 后低于基线。

### 1.3 组合近似诊断

只读近似：把 R6 相对 L125 的空头日收益按 2.5/6.25 = 0.4 缩放，再叠加到 LS4：

| 指标 | LS4 | 0.4x R6 overlay approximation |
|---|---:|---:|
| 终值 | 23.8448x | 约 26.3847x |
| Sharpe | 1.8091 | 约 1.8961 |
| MDD | -34.12% | 约 -34.98% |
| 365 天滚动最差 | 0.7838x | 约 0.8200x |
| LS4 与 R6 overlay 日收益相关 | — | **-0.2392** |

该近似不是正式回测，不能作为候选结果。它只用于决定是否值得预注册一个真实引擎试验。

## 2. 冻结构造

### 2.1 H5 多头

- 使用冻结 H5 `PR2026-10-H5`；
- 多头乘数 1.0；
- 若 H5 long gross > 0.95，缩放到 0.95；
- 不重分配 H5，不增加杠杆。

### 2.2 sleeve A：H5 exit-short

与 LS4 相同：

- H5 前一个目标持有、当前目标完全退出；
- 退出资产仍属于 PIT Top20；
- Bitget execution mark 可用；
- 固定持有 21 个日历日；
- H5 重新买入时提前关闭；
- 同一资产只在没有活跃 sleeve A 空头时进入。

### 2.3 sleeve B：Top20 14D weak-four

- 信号日历为完整 UTC 日线；
- 再平衡网格每 7 个日历日，以样本起点为 anchor；
- 在再平衡信号日，对当日 PIT Top20 中：
  - 排除当前 H5 多头持仓；
  - 要求 Bitget execution mark 可用；
  - 要求最近 3 个 Binance funding settlement 的均值 > -0.0002（沿用 R6 的 funding filter，缺失 fail closed）；
  - 计算 14 日 trailing return；
  - 选择 trailing return 最低的 4 个资产；
- 每个选中资产固定 2.5% NAV；
- 持有到下一次 7 日再平衡或 20% adverse stop；
- 若资产在周中 stop，不因同一周内重复目标而自动重开；下一次正式周再平衡可以重新选中；
- 如果可投资资产少于 4 个，不补入不合格资产。

### 2.4 合并 sleeve A 与 sleeve B

两个 sleeve 都输出每资产正的 request short weight，单位为 NAV 比例。

对每个事件日：

```text
requested_short_i = max(weight_A_i, weight_B_i)
```

因为两条 sleeve 的冻结单腿权重都为 2.5% NAV，所以重叠资产仍只有一条 2.5% 空头腿，不能相加为 5%。

时间轴：

- 对两条 sleeve 的 schedule 做 forward-fill；
- union event date 上重新计算；
- 只有目标变化时才产生新的目标事件；
- 空 target 必须产生明确事件，用于平仓；
- engine 的 20% stop 是唯一会关闭单腿的中途事件；
- stop 后不生成隐式重开目标，直到下一次正式 sleeve event。

### 2.5 总 gross

使用现有 `combine_long_with_cash_budgeted_short`：

```text
available = max(0, 0.95 - scaled_H5_long_gross)
funded_short = requested_short * min(1, available / requested_short_gross)
total_target_gross = scaled_H5_long_gross + funded_short_gross <= 0.95
```

不允许为了放空头而减少 H5 多头；只有 H5 自身超过 0.95 时才缩放。

### 2.6 风险与执行

- 20% adverse mark stop；
- long buffer 0.75；
- short buffer 0.50；
- target total gross 0.95；
- hard observed gross 1.00；
- next-tick gross guard：observed > 1.00 后下一小时按比例减仓到 0.95；
- T+1 UTC +3h；
- missing mark 最多 carry 3 小时；
- funding 主口径 Binance proxy/skip；
- 另跑 3x short-adverse。

## 3. 评估门槛

### 3.1 主口径

1. 20bps 终值严格高于 H5 基线；
2. 20bps Sharpe 严格高于 H5 基线；
3. MDD 不差于基线 5pp；
4. 0 次强平；
5. max target total gross <= 1.00；
6. max observed gross <= 1.00；
7. 所有 stop、funding、费用和 gross guard 成交计入。

### 3.2 成本

- 2/20/50/100bps 全部重跑；
- 50bps 和 100bps 终值均高于同成本基线；
- 四档 Sharpe 均高于同成本基线；
- 100bps MDD <= 50%；
- 四档 observed gross 都 <= 1.00。

### 3.3 funding 与尾部

- 3x short-adverse funding 下 0 强平且 MDD <= 50%；
- 实际最大 adverse short mark loss 超过名义 0.5% 时必须披露；
- 报告每个资产的最大 adverse excursion 和 episode PnL。

### 3.4 日历、起点和集中度

- 分年收益；
- 删除最佳年份后仍高于基线；
- 365 天滚动最差不低于基线；
- 至少 12 个真实月初引擎启动，至少剩余 365 天：
  - 终值胜过基线 >= 8/12；
  - Sharpe 胜过基线 >= 8/12；
  - MDD 5pp 门槛 12/12；
- 单资产空头贡献 <= 50%；
- 前 3 资产空头贡献 <= 80%。

### 3.5 多重检验

- PBO/CSCV <= 0.50；
- White Reality Check single-step p <= 0.05；
- 全项目 DSR >= 0.95；
- 报告 family、Top20/2022 和 all_trials scope。

### 3.6 样本外

- 2026-09-22 后为真 OOS，不得用于调参数；
- 不足 12 个月 OOS 时最高 provisional；
- 无 Bitget 精确 funding、isolated margin、ADL/强平审查，禁止接实盘。

## 4. 失败后动作

- 不扫描 sleeve A 持有期 7/14/28/30/60D；
- 不扫描 sleeve B lookback 7/14/28/30/60D；
- 不扫描 weak basket 2/3/4/5/8；
- 不扫描 weekly 以外的再平衡频率；
- 不扫描 stop 15%/20%/25%/30%；
- 不扫描单腿 1%/2.5%/5%；
- 不扫描 funding threshold 或 lookback；
- 不扫描 A/B 的权重比例；
- 不把同一资产的 A+B 改成 5%；
- 不扫描 gross 0.90/0.95/1.00；
- 失败后必须设计新的、机制不同的候选并重新预注册。

## 5. 复现接口

```bash
.venv/bin/python scripts/run_h5_exit_weak_combo.py --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_weak4_risk

.venv/bin/python scripts/run_h5_exit_weak_combo.py --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_weak4_risk
```

## 6. 状态

- 当前状态：pre-registered research candidate；
- 是否接实盘：否；
- 是否修改 H5：否；
- 是否增加杠杆：否；
- 是否允许失败后参数搜索：否。
