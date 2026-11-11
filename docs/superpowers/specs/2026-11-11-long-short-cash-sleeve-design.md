# Atlas20 无杠杆多空候选预注册：H5 + H4 现金 sleeve + 板块龙头空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘，不改 H5 多头账本 |
| 候选 ID | `PR2026-11-LS1-H5-H4-SECTOR20` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 多头底稿 | 冻结 H5 `PR2026-10-H5`，1.0x；H4 `PR2026-10-H4`，0.2x 现金 sleeve |
| 空头 | `SECTOR_LEAD_top2__asset_ma50` 自身目标权重的 0.2x |
| 目标 gross | **0.95x** |
| 硬 gross 上限 | **1.00x**，任何时点不得突破 |
| 保证金 | Bitget USDT-M isolated margin |
| 执行 | 信号日 T，T+1 UTC +3h |
| 数据 | 严格 point-in-time CMC Top20；Bitget mark；Binance funding proxy/skip 仅研究用 |
| 研究边界 | 不改 H5、不改执行器、不接实盘；本轮只验证一个固定点 |

## 0. 研究问题

H5 是低平均 gross 的集中多头策略。历史诊断显示，H5 的闲置现金可以被两个不同来源利用：

1. 用 H4 的分散化多头 sleeve 使用一部分闲置现金；
2. 用历史上表现差、但在 H5 下跌阶段有正贡献的高波动板块龙头策略作为小仓位空头对冲。

本轮只回答一个问题：

> 在 **不提高当前 gross 上限、不使用 1.25x/1.5x 杠杆** 的前提下，
> `H5 1.0 + H4 0.2 + 板块龙头空头 0.2` 能否比 H5 1.0 基线获得明显更高的终值和 Sharpe，
> 同时保持回撤不明显变差、零强平，并通过成本、funding、年份和多重检验？

这不是把历史负收益策略机械地乘 `-1`。空头的经济作用是**尾部对冲**，不是收益的主要来源。负收益策略的独立空头在历史记录中多次失败，不能把本候选解释成“做空亏损策略必然赚钱”。

## 1. 冻结构造

### 1.1 多头 H5

- 使用冻结的 `PR2026-10-H5` 目标；
- 缩放为 **1.0x**；
- 不改变 H5 的 12 个 sleeve、3 日相位、Top20 选币、BTC 闸门、宽度共闸和 dispersion overlay；
- H5 的平均 gross 仍然很低，现金部分由下一节的 H4 sleeve 使用；
- 不允许为了本试验把 H5 改成 1.25x 或其他杠杆。

### 1.2 H4 现金 sleeve

- 使用冻结的 `PR2026-10-H4` 目标；
- H4 规格：`PhaseMomentumSpec(holdings_per_sleeve=4, hold_rank=8)`；
- 目标权重乘以 **0.2**；这里的 0.2 同样是 H4 目标权重的倍数，不是账户权益的 20%；H4 目标 gross 平均约 0.41，故典型 H4 多头 gross 约 0.082x；
- H4 不是本候选的主信号，不允许替换 H5 的选币，也不允许把 H4 的历史低 Sharpe 通过事后调权重“救活”；
- H4 的作用只是在 H5 的 gross 未用满时提供分散化多头暴露。

### 1.3 板块龙头空头

被做空的是历史诊断中的失败多头策略：

```text
SECTOR_LEAD_top2__asset_ma50
```

精确定义：

- `build_sector_lead_v3_targets(..., top_k=2, frequency="14D", regime_mode="bull_only")`；
- 只从当日 point-in-time CMC Top20 的板块和成员中选；
- 每个被选板块选 1 个 leader；
- 应用 `absolute_trend_mask(market.price, ma_window=50)` 的资产级日频退出 overlay；
- 使用该策略当日已经生成的目标权重，不反向重新排序；空的 target 视为无空头；
- 空头权重为：

```text
w_short_i,t = -0.2 * w_sector_leader_i,t
```

这里的 **0.2** 是该策略目标权重的 0.2x，不是账户权益的 0.2x。板块策略的平均 gross 约为 0.43，因此典型空头 gross 约为 `0.2 × 0.43 = 0.086x`，仍受总 gross 上限约束。

### 1.4 合并规则

在每个目标事件日 `t`：

```text
w_raw_i,t =
    w_H5_i,t
  + 0.2 * w_H4_i,t
  - 0.2 * w_sector_leader_i,t
```

目标事件集合为三者事件日的并集：H5 的 target events、H4 的 target events、板块策略的 target events（包括资产级 MA50 overlay 触发的事件）。在每个事件日，三者都按各自最近的 target event 前向填充；空 target 视为现金。信号只能使用当日收盘前可见的数据，不能使用未来目标。若：

```text
gross_raw = sum_i |w_raw_i,t| > 0.95
```

则所有分量统一缩放：

```text
w_i,t = w_raw_i,t * 0.95 / gross_raw
```

不允许只缩放空头或多头中的一边；统一缩放保留三个 sleeve 的相对风险预算。

如果同一资产同时出现在 H5/H4 多头和板块空头中，Broker 层可以按净持仓执行，但研究报告必须同时记录：

- net target；
- long gross；
- short gross；
- total gross（`long + short`，不把净额当作 gross）；
- 每个 sleeve 的独立贡献。

## 2. 风险与执行语义

### 2.1 gross 硬约束

研究回测使用：

- `target_gross = 0.95`；
- `max_gross_exposure = 0.95`。

实盘必须再加一层独立的 gross guard：

- 下单前计算 projected gross；
- projected gross > 1.00 时拒绝或缩减订单；
- 因 mark 漂移使 observed gross > 1.00 时，在下一个可执行 tick 做风险管理减仓，恢复到 ≤0.95；
- 不允许用“账户还有保证金”作为突破 gross 上限的理由；
- gross guard 不得使用未来价格或事后最优减仓顺序。

研究报告必须记录 `max_gross_exposure`。只要主样本任一小时出现 `observed gross > 1.00`，该试验失败，不能事后把阈值改成 1.01 或 1.02。

### 2.2 保证金

- 模式：Bitget USDT-M isolated margin；
- `long_buffer = 0.75`；
- `short_buffer = 0.50`；
- `max_margin_utilization = 0.85`；
- 每个空头腿独立占用保证金，不用账户其他现金替同一腿兜底；
- 主样本 0 次强平；
- 若账户能力导致 isolated margin 不可用，本候选不能进入实盘，不能用 cross margin 结果替代。

### 2.3 空头止损

- 只对空头腿启用 20% adverse mark stop；
- 入场价为实际成交价；
- 每小时用 mark high/low 检查；
- 若开盘已越过止损价，按 open 加保守滑点成交；
- 触发后该腿变现金，直到下一次预注册的板块目标事件重新选择；
- 止损不能在同一小时内反复开仓；
- 止损记录为 `reason=stop_loss`，不得伪装成普通调仓；
- 不扫描 15%/25%/30% 等相邻阈值。20% 是已预注册的尾部保险。

### 2.4 执行

- 信号在 UTC 日线收盘生成；
- T+1 的 UTC +3h 执行；
- 执行缺失 mark 使用不超过 3 小时的 carry，仅用于研究；实盘使用 fail-closed；
- 目标资产离开 Top20、失去 mark 或目标变为空时，下一可执行时点退出；
- 不在数据缺失时用零收益或旧价格静默填洞。

## 3. 数据与 funding

### 3.1 价格

主研究：

- 使用 Bitget mark 1h；
- 所有潜在空头资产必须具备执行时刻 mark；
- 缺失 mark 的资产不进入空头，不重新分配其权重；
- 多头资产缺失 mark 时按既有 fail-closed 规则降为现金，不把权重偷偷转给其他币；
- 覆盖不足的资产和日期必须在报告中列出，不能静默丢弃；
- 空头资产在其被选中的执行日中，mark 覆盖率必须达到 **95%**；否则本试验不能进入实盘准备阶段。

### 3.2 funding

- 研究主口径使用 Binance funding proxy + `skip`，并明确标注不是 Bitget 精确历史；
- 另跑 `funding_multiplier=3`、`funding_stress="short-adverse"`；
- 空头腿的 funding 按资产和实际结算时间计算，不能用 BTC funding 代理所有 alt；
- funding 方向 gate 不作为本试验的收益参数；本轮不新增 funding 阈值搜索；
- 实盘前必须补 Bitget 精确 funding 与至少 12 个月独立 OOS；在此之前最多 provisional。

## 4. 预注册门槛

以下全部固定，不能看到结果后放宽或删除。

基线必须由同一生产引擎、同一成本、同一 mark、同一 gross 约束重跑：

```text
H5 1.0x, target gross 0.95, hard cap 1.00
```

### 4.1 主口径（20bps）

1. 终值严格高于 H5 1.0 基线；
2. Sharpe 严格高于基线；
3. MDD 不差于基线 5 个百分点（`MDD_candidate >= MDD_baseline - 0.05`）；
4. 主样本 0 次强平；
5. `max_gross_exposure <= 1.00`；
6. 空头止损、强平、funding 和调仓费用全部计入。

### 4.2 成本压力

2/50/100bps 全部重跑：

1. 50bps 终值高于同成本 H5 基线；
2. 100bps 终值高于同成本 H5 基线；
3. 100bps MDD 不超过 50%；
4. 2/20/50/100bps 方向一致，不能只在最低成本档有效；
5. 每个成本档都报告 Sharpe、MDD、turnover、fees、funding 和强平次数。

### 4.3 funding 与尾部

1. 3x short-adverse funding 下 0 次强平；
2. 3x funding 下 MDD 不超过 50%；
3. 报告空头每个资产的最大 adverse excursion；
4. 空头止损次数、开仓次数、最大单腿亏损、最大单腿贡献全部披露；
5. 不能把 funding 压力写成“精确 Bitget 历史”。

### 4.4 日历与稳定性

1. 2022/2023/2024/2025/2026 分年收益；
2. 移除最佳年份后仍高于 H5 基线；
3. 2020-10 至 2021-12 只作为压力窗口，不能进入 headline；
4. 365 天滚动最差 multiple 不低于基线；
5. 至少报告 10 个 non-overlapping start-phase 检查；
6. 不以 2022 单一年份作为主要收益来源；
7. 不以单一资产贡献作为主要收益来源；若前 3 个资产贡献超过 50%，必须标记并拒绝升级为 live-ready。

### 4.5 多重检验

本试验计入新的 N，不得引用旧 H5 的试验数来降低门槛：

- 报告 PBO/CSCV；
- `PBO <= 0.50`；
- 报告 White Reality Check；主候选的 single-step p 值必须 `<= 0.05`；
- 报告 Deflated Sharpe / 试验数敏感性；
- DSR 必须 `>= 0.95` 才能升级；未达到时只能 provisional；
- 不能因为 20bps 结果好就省略多重检验。

### 4.6 样本外

- 2026-09-22 之后为真 OOS，禁止用于调权重、阈值、止损或 sleeve 大小；
- OOS 不足 12 个月时，最高状态为 provisional；
- 没有 12 个月独立 OOS、真实 Bitget funding、isolated margin 和强平/ADL/流动性审查，禁止接实盘。

## 5. 固定失败后的动作

如果任一主门槛失败：

- 立即标记 `rejected` 或 `provisional`，不能把失败项改成“参考指标”；
- **不扫描** H4 权重 0.1/0.3/0.4；
- **不扫描** 板块空头权重 0.1/0.3/0.4；
- **不扫描** 20% 止损的 15/25/30；
- **不扫描** long buffer 0.60/0.65/0.70；
- 不通过改 gross 上限、改 Top20、改 mark 口径或把 100bps 降到 20bps 来救活；
- 下一轮只能提出一个独立的新机制，并重新预注册。

## 6. 与“加杠杆”的区别

本试验明确不属于加杠杆：

- H5 固定 1.0x，不使用 H5 ×1.25；
- H4 是 0.2x 的现金 sleeve；
- 空头是板块策略目标权重的 0.2x；
- 目标 gross 0.95，硬上限 1.00；
- 研究引擎的最大 gross 超出 1.00 即失败；
- 不允许用 cross margin 的可用保证金提高实际 notional。

## 7. 预注册前的诊断（不是正式验证）

2026-11-11 只读诊断曾用生产衍生品引擎得到一个 **pre-spec motivation**：

- H5 1.0 + H4 0.2 + 板块空头 0.2；
- 20bps：约 26.41x、Sharpe 1.85、MDD -28.5%；
- 50bps：约 17.66x；
- 100bps：约 9.02x，低于 H5 1.0 基线约 9.38x；
- 0 次强平、14 次空头止损；
- 诊断使用 target gross 1.0，不是本 spec 的 0.95；
- 诊断没有完成 PBO/DSR、精确 funding 和 12 个月 OOS。

因此上面的数字只能作为动机，不能引用为通过结果。正式试验必须重新以 0.95 target gross 和硬 1.00 上限运行，且 100bps 失败将直接触发拒绝。

## 8. 复现接口

本 spec 需要新增一个研究 runner 入口，至少暴露：

```python
run_derivative_backtest(
    mark_candles=...,
    targets={
        "PR2026-11-LS1-H5-H4-SECTOR20": signed_targets,
    },
    funding_rates=...,
    config=DerivativeBacktestConfig(
        taker_fee_bps=20.0,
        slippage_bps=0.0,
        long_buffer=0.75,
        short_buffer=0.50,
        short_stop_loss_pct=0.20,
        max_gross_exposure=0.95,
        funding_missing_policy="skip",
        missing_mark_policy="carry",
        missing_mark_max_carry_hours=3,
    ),
)
```

正式 runner 必须先从 `PR2026-10-H5` 和 `PR2026-10-H4` 构建 target，再调用板块龙头 builder 生成空头；不得把三者的日收益直接相减冒充生产引擎结果。

---

## 9. 状态

- 当前状态：**pre-registered research candidate**；
- 是否接实盘：**否**；
- 是否修改 H5：**否**；
- 是否增加杠杆：**否**；
- 是否允许在失败后做参数搜索：**否**；
- 下一个允许动作：用本 spec 重跑正式引擎，并记录全部失败项。
