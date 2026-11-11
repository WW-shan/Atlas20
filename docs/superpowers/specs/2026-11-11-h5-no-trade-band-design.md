# Atlas20 候选预注册：LS12 上的 5% NAV 单腿 no-trade region

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS16-H5-REGIME-SHORT-NOTRADE5` |
| 基线 ID | `PR2026-10-D-L125` |
| 基础 alpha | 冻结 LS12：H5 1.25x + BTC 200D 双空头 regime router |
| 新增机制 | 已有多空同方向仓位只在偏离目标超过 5% NAV 时交易，并只交易到容差边界 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | target/hard total 1.50x；short <=0.25x |

## 0. 研究问题

LS12 在 20bps 达到 **55.7859x / 1.8520 / -40.64%**，但 100bps 为
**14.3604x / 1.3129 / -50.1067%**，三项都略差于 L125 的
**14.3794x / 1.3204 / -50.0229%**。这说明 LS12 不是 alpha 不足，而是高换手成本在 100bps 下抹平了
20bps 的大部分增量。

只读换手审计（`reports/derivatives_track_h5_regime_short_router/turnover_audit/`）得到：

- 672 个组合目标事件、1,641 个单币目标变化；
- 目标向量 L1 变化合计 **167.9132x NAV**；
- 新开/清仓/反手是强制成交，合计 **90.4545x**；
- 同方向增减仓为 **77.4587x**，是可以使用 no-trade region 的部分；
- 20bps 实际累计成交名义额为 **1,387.25x 初始权益单位**，累计费用 **2.7745x**，
  其中多头约 72%、空头约 28%。

LS16 只改变执行节奏，不改变收益信号、持币名单、空头选币、funding、stop 或 gross 上限。它检验：

> 对已存在的同方向仓位设置 5% NAV 容差区，能否保留 LS12 的 alpha，同时把 100bps 成本尾部
> 修复到基线之上。

## 1. 5% 容差的来源

5% 不是对收益结果扫描后选择的阈值。它来自项目已冻结的 H5 `weight_tolerance = 0.05`：
H5 原始信号本身就用 5% 单币权重容差避免噪声换手。衍生品引擎此前每天把目标精确恢复到权重，
等于抹掉了该执行容差。LS16 将同一 5% 容差显式应用到已有同方向仓位。

不扫描 1%/2.5%/7.5%/10%/15% 等替代值；LS16 失败后停止该容差家族。

## 2. 冻结构造

基础目标与 LS12 完全相同：

```text
target_t = H5_L125_t - routed_short_t
```

执行时，对每个资产：

1. **目标缺失、目标为零或方向变化**：完全清仓；若新方向存在，再按目标全额开仓。
2. **当前无仓位、目标非零**：按目标全额开仓。
3. **当前与目标同方向**：
   - 若 `abs(target_notional - current_notional) <= 0.05 * equity`，不交易；
   - 若超过容差，只交易到距目标 5% NAV 的边界：
     `boundary = target_notional - sign(delta) * 0.05 * equity`。

示例：当前 10% NAV、目标 16% NAV、5% 容差时，不同步到 16%，只增加到 11%；等后续目标或价格
漂移使距离再次超过 5% 时才继续调整。减仓方向对称。

强制约束：

- 开仓、清仓和反手始终精确执行，不受容差影响；
- 当前或交易后 projected gross 超过 1.50x 时，放弃容差并对该事件执行精确目标；
- 5% 容差绝不用于放宽 margin、stop、funding、强平或 Top20 约束。

## 3. 预注册门槛

1. 20bps 终值 > L125；
2. 20bps Sharpe >= L125；
3. 20bps MDD <= L125 +5pp；
4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
6. 100bps MDD <=50%；
7. 3x short-adverse 0 强平且 MDD <=50%；
8. 删除任一最佳年份后终值仍高于同成本 L125；
9. 365 天滚动最差 >= L125；
10. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
11. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过基线，12/12 MDD 5pp；
12. 单资产空头贡献 <=50%，前 3 <=80%；
13. observed gross <=1.50 且无 gross breach hour；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月真实 OOS 未满前最高只能 provisional。

## 4. 判定逻辑

LS16 是**交易成本控制机制**，不是新 alpha。它必须同时满足：

- 20bps 不显著劣于 LS12，避免为了省费用破坏收益；
- 100bps 终值、Sharpe 和 MDD 至少严格优于同成本 L125；
- 删除 2022 和路径切片不得继续失败。

如果只改善 100bps 但仍保留 remove-2022、路径依赖或 DSR 失败，则仍判 rejected。

## 5. 失败后动作

如果 LS16 失败：

- 不扫描 no-trade 容差、事件阈值、再平衡频率或仅对多头/空头的不同容差；
- 停止同一 no-trade region 家族；
- 提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 6. 复现接口

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS16-H5-REGIME-SHORT-NOTRADE5 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_no_trade_band
```

## 7. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
