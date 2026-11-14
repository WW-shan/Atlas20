# Atlas20 研究预注册：LS45 多空 gross 预算网格

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-15 |
| 状态 | 研究预注册；不接实盘；不修改当前 LS45-G125 |
| 基础策略 | `PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21` |
| 基准窗口 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 01:05 UTC，mark 1h open floor |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |
| 成本 | 10 个预注册变体全部 20bps；通过硬门的变体再做 50/100bps |
| 保证金 | 2x isolated，long/short initial buffer 50%，margin utilization 0.85 |
| 实盘边界 | 任何变体都不自动修改 live；仅诊断和后续独立 OOS 候选 |

## 0. 研究问题

负责人要求检验两种直觉：

1. 当前 0.25x 空头是否过于保守，放大空头能否改善收益而不显著恶化 MDD；
2. 把长期 gross 从 1.25x 降到 1.0x，同时把空头提高到 1.0x，是否能形成更好的下跌保护。

这不能再只看单独的空头权重。必须同时控制：

- `L`：H5 多头目标 gross；
- `S`：空头请求 gross；
- `G`：组合目标总 gross；
- 实际有效 gross：受 2x isolated、50% buffers 和 0.85 margin cap 约束后的 engine target；
- 是否发生强平、gross breach、空头止损和 funding 压力下的失败。

## 1. 固定构造

所有变体保持以下规则不变：

```text
H5 1.25x 原始信号 → 按 L/1.25 线性缩放
LS22 21D/100% 单龙头减半
LS45 只向 21D 更强的既有 H5 持有者再分配，单币 cap 60% NAV
LS12/LS23 双空头 router
BTC 200D bear regime 每日检查
bear weak-four 每 7 天重排，14D lookback
每腿 20% adverse mark stop
short_buffer = long_buffer = 0.50
max_margin_utilization = 0.85
funding proxy / missing-mark carry 3h
```

短头总请求在每个 schedule 事件上按 `S` 截断，避免 exit sleeve 在多个退出币同时活跃时超过请求值。多头按 `L` 缩放；没有新增资产、没有改 stop、没有改再分配规则、没有改 7D 重排。

## 2. 预注册网格

| ID | L long | S short | G total | 解释 |
|---|---:|---:|---:|---|
| `LS61-L125-S025-G125` | 1.25x | 0.25x | 1.25x | 当前 live cap，空头只吃未使用多头 gross |
| `LS61-L125-S025-G150` | 1.25x | 0.25x | 1.50x | 当前 LS45 research hard cap |
| `LS61-L125-S050-G175` | 1.25x | 0.50x | 1.75x | 保持多头、放大空头 |
| `LS61-L100-S025-G125` | 1.00x | 0.25x | 1.25x | 只降多头，不放大空头 |
| `LS61-L100-S050-G150` | 1.00x | 0.50x | 1.50x | 1x 多 + 0.5x 空 |
| `LS61-L100-S075-G175` | 1.00x | 0.75x | 1.75x | 1x 多 + 0.75x 空 |
| `LS61-L100-S100-G200` | 1.00x | 1.00x | 2.00x | 负责人提出的 1x 多 + 1x 空 |
| `LS61-L075-S050-G125` | 0.75x | 0.50x | 1.25x | 预留预算的防御版 |
| `LS61-L075-S100-G175` | 0.75x | 1.00x | 1.75x | 长仓明显缩小、空头放大 |
| `LS61-L050-S100-G150` | 0.50x | 1.00x | 1.50x | 接近空头主导的边界诊断 |

`L100-S100-G200` 不是当前 1.25x live cap 可直接上线的配置：在 2x 杠杆和 50% buffer 下，
100% 名义多头 + 100% 名义空头的初始保证金约为权益的 102%，而 engine 只允许 85% margin
utilization。因此它的实际 gross 会被 engine 缩放；本试验的重点就是量化缩放后的真实结果，
而不是把 2.0x 目标当成已成交的 2.0x 暴露。

## 3. 主评估指标

每个变体必须输出：

- 20bps 终值、Sharpe、MDD、CAGR；
- `max_target_total_gross`、`max_observed_gross`、`max_funded_short_gross`；
- `gross_breach_hours`、强平次数、空头止损次数、空头开仓次数；
- 实际 long/short gross 的年度均值；
- 2022、2023、2024、2025、2026 分年收益和 MDD；
- 3x short-adverse funding 的终值、Sharpe、MDD、强平；
- 删除最佳年份后的终值；
- 365D rolling worst。

## 4. 硬门和判定

先固定，不允许看到结果后改：

1. 20bps 终值必须高于当前 live-parity 基准 `65.2592x`；同时报告相对 research 基准 `69.2088x` 的差；
2. 20bps Sharpe 不低于 1.9792；
3. 20bps MDD 不得差于 `-34.06% - 5pp`，即不得低于 `-39.06%`；
4. 50bps 终值和 Sharpe 不得低于当前 0.25x/L125 research 基准；100bps 同样；
5. 100bps MDD 必须 <= 50%；
6. 0 次强平、0 gross breach 小时；
7. 实际观测 gross 必须 <= 该变体声明的 `G`；
8. 3x short-adverse funding 0 强平且 MDD <= 50%；
9. 删除任一最佳年份后仍高于当前 live 基准；
10. 12 个月独立 OOS 未完成前，最高只能 provisional。

只有同时通过 1–9 的变体，才进入下一轮；不看“最高 20bps 终值”单独选冠军。若全部失败，
保持当前 LS45-G125，不调大 live 空头，不降低 live 多头 gross。

## 5. 失败后的动作

- 不因为某一个变体在 20bps 看起来更高就改 live；
- 不扫描未预注册的 L/S 组合；
- 若 1x 多 + 1x 空因 margin utilization 被缩放到约 1.66x，记录“目标不可执行”，
  而不是把缩放后的收益当成 2x 收益；
- 若需要真正持有 1x 多 + 1x 空，必须先单独研究更高 venue leverage、较低 margin buffer
  或其他保证金机制，并重新预注册；不能悄悄放宽当前 2x、50% buffer。

## 6. 复现接口

所有变体用隔离进程 monkeypatch `FROZEN_CONFIG`，不修改源码中的 live 默认值：

```bash
.venv/bin/python /tmp/atlas20_analysis/run_risk_budget_grid.py \
  --long-gross 1.0 --short-gross 1.0 --total-gross 2.0 \
  --cost-bps 20 --output-dir /tmp/atlas20_analysis/risk_grid/l100_s100_g200
```

脚本必须把 `bear_per_asset_weight` 和 `exit_per_asset_weight` 按 `S / 0.25` 缩放，
把每个 schedule 事件的短头总权重截断到 `S`，并保留当前 stop/funding/missing-mark 和
7D 重排规则。

研究输出不是订单，也不是实盘批准。
