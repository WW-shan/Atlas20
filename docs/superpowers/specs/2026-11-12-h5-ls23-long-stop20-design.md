# Atlas20 候选预注册：LS23 + 20% 多头逐腿止损

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS41-H5-LS23-LONGSTOP20` |
| 基线 | L125；LS23 |
| 基础 book | 冻结 LS23：H5 1.25x 利润保护 + LS12 双空头 router |
| 新机制 | 每个 H5 多头腿从平均入场价 adverse 20% 时逐小时 mark 止损 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；long/short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

当前 H5 多头使用 1.25x notional、2x isolated venue leverage 和 50% long buffer。多头的理论
强平区约在入场价腰斩附近；H5 自身只有 BTC 200D 闸门和选币退出，没有逐腿 adverse stop。
LS39 进一步证明，即使一个 leg 名义很小，持有到接近 50% adverse move 也会触发 isolated liquidation。

LS41 补上一个与现有 short stop 对称的风险控制：每个多头腿从平均入场价 adverse 20% 时止损。
20% 不是新扫描阈值，而是项目当前 short stop 已冻结的同一风险阈值；long/short 两边都使用 20%
也避免方向不对称。止损后不在同一价格立即重开，只在下一个 H5 target event 才允许重新建仓。

## 1. 冻结构造

```text
base = frozen LS23
for every hourly mark timestamp and every open long position:
  trigger = average_entry_price * (1 - 0.20)
  if open <= trigger: close at open
  elif low <= trigger: close at trigger
  else: hold

stop executes before the hourly liquidation check;
funding is charged before stop/liquidation exactly as in the current engine;
a stopped leg can re-enter only at the next scheduled H5 target event;
short router, LS22 profit lock, buffers, gross caps and 1.25x H5 leverage unchanged.
```

- 止损使用 Bitget hourly mark，不使用 close-only 近似；
- long stop 只作用于 H5 多头腿，不改变选币或目标权重；
- 止损后保留现金，不立即把权重转给其他资产；
- 不扫描 10%/15%/25%/30%、ATR stop、trailing stop、再入延迟或组合层 stop；
- 不改变 short stop 20%。

## 2. 预注册门槛

研究价值（20bps，LS23 为 incumbent）：

1. LS41 终值 >= LS23 的 61.9150x；
2. Sharpe >= LS23 的 1.9448；
3. MDD 不得比 LS23 的 -39.84% 恶化超过 5pp，即不差于 -44.84%。

成本与尾部：

4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均 >= 同成本 LS23，且均高于同成本 L125；
6. 100bps 终值 > LS23 的 15.5037x、Sharpe > 1.3745、MDD <=50%；
7. 3x short-adverse funding 0 强平且 MDD <=50%；
8. observed gross <=1.50 且 gross breach hour = 0。

稳健性：

9. 删除任一最佳年份后终值仍高于 L125；
10. 365 天滚动最差 >= L125 的 0.7325x；
11. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
12. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过 L125，12/12 MDD 5pp；
13. 单资产空头贡献 <=50%，前 3 <=80%；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月真实 OOS 未满前最高只能 provisional。

任一 20bps 主收益/Sharpe/MDD 门槛失败，LS41 不得因为“风险控制听起来合理”而保留为实盘候选。

## 3. 失败后动作

若 LS41 失败，停止 H5 多头逐腿固定百分比 stop 家族，不扫描阈值、ATR 或 trailing 变体。
保留 LS23 作为 incumbent，不修改实盘。若通过主样本，仍需完成 funding stress、成本档、路径、
冷启动、PBO/RC/DSR 和 12 个月真实 OOS。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS41-H5-LS23-LONGSTOP20 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_longstop20
```

## 5. 状态

- 预注册：是；
- 正式运行：是；
- 结果：**rejected**；20bps 57.2522x / 1.9036 / -39.835%，19 次 long stop、0 强平，但主收益和 Sharpe 失败；
- 实盘：否；
- 修改当前实盘：否。
