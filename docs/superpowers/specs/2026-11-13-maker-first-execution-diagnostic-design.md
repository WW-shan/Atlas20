# Atlas20 execution research: maker-first fills for the frozen LS57 book

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 诊断已完成（平均通过；仍不接实盘） |
| 研究问题 | 在不改变 LS57/LS23 alpha、目标权重、T+1 时点和 gross 的前提下，被动限价单优先、超时后 taker 回退，能否稳定降低有效成交成本 |
| 交易样本 | `PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE` 的全部成交 |
| 主数据 | Bitget USDT-M mark 1h K 线（与回测/成交同一 venue） |
| 交叉检查 | Binance 30m K 线（只作为路径稳健性检查，覆盖率不足时明确标记） |
| 主窗口 | 2022-01-01 → 2026-09-21（UTC） |
| 研究输出 | `reports/derivatives_track_maker_execution_diagnostic/` |

## 0. 研究问题

LS57 的 20bps 成本档为 68.8077x；同一规则在 2bps 档为 93.9064x。这个差距说明执行成本
可能比继续微调 alpha 更有价值。因此本诊断不复用任何新的预测信号，只问：

> 在每个目标成交时点，先在盘口内侧挂被动限价单；若一个短窗口内没有足够穿透，再以市价
> 回退，是否能在真实路径上降低平均有效成本，而不是只把未成交订单换成更差的追价？

这不是“把回测成本改成 2bps”，也不是假设所有订单都能拿到 maker 费率。每个成交单独模拟
限价触碰、未成交回退和对应费率。

## 1. 固定构造

主配置在运行前冻结：

```text
at each frozen trade timestamp:
    reference = first 1h bar open
    buy limit  = reference * (1 - 5bps)
    sell limit = reference * (1 + 5bps)
    require the bar range to trade through the limit by 1bp
    wait at most 2 one-hour bars
    if filled: maker fee = 2bps, fill at the limit
    else:      taker fee = 20bps, fill at the timeout bar close
```

- 5bps：只在盘口内侧要价，不追逐短时突破；
- 2 bars：给被动单一个有限成交窗口，避免无限挂单；
- 1bp through：比“刚好触碰”更保守，降低队列位置假设；
- 2bps maker / 20bps taker：显式费率假设，不从交易所账户反推；
- 不使用未来价格选择 offset 或 timeout；敏感性表只用于检查方向和稳定性。

同时报告 2/5/10bps offset 与 1/2/4 bars timeout 的完整敏感性，不隐藏失败格点。

## 2. 验收标准

1. Bitget mark 成交名义覆盖率 >= 95%；
2. 主配置按名义加权的被动成交率 >= 85%；
3. 主配置有效成本相对 20bps taker 基线改善 >= 5bps；
4. 至少 4/5 个日历年改善为正，且没有单年出现超过 2bps 的恶化；
5. Binance 30m 交叉检查的改善方向与 Bitget 主数据一致；
6. 结果不能依赖单一资产或单一年份；报告前 3 资产/年份贡献和未成交回退尾部；
7. 不改变 LS57 的收益、回撤、空头、stop 或 gross 口径。

若全部通过，下一步只能是**真实盘口/订单簿 shadow 执行**，不是直接切实盘。若失败，记录负结果，
不通过改 offset、timeout 或费率把诊断救活。

## 3. 明确不证明的事情

- mark K 线不是可成交盘口，K 线 high/low 触碰不等于真实 maker 成交；
- 没有队列位置、部分成交、撤单延迟、滑点、ADL 或交易所拒绝；
- 不能用本诊断声称“实盘成本已经是 8.9bps”；
- 不能把执行改善重复计入 alpha 的 DSR/PBO，也不能据此提升 LS57 的 promotion 状态。

## 4. 复现

```bash
.venv/bin/python scripts/analyze_maker_execution.py \
  --trades-path reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_stable1d_redistribute/PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE/trades.csv \
  --bar-source bitget-mark \
  --raw-dir data/raw/bitget_derivatives/merged_20261009 \
  --output-dir reports/derivatives_track_maker_execution_diagnostic
```

## 5. 结果（2026-11-13）

Bitget 主数据：2,524 笔成交、名义成交额 1,707.1142，覆盖率 **100%**。主配置：

| 指标 | 结果 |
|---|---:|
| 名义加权被动成交率 | **91.40%** |
| 有效成本 | **8.45bps** |
| 相对 20bps 基线改善 | **+11.55bps** |
| 改善为正的成交名义占比 | **91.41%** |
| 未成交回退名义占比 | 8.60% |
| 未成交回退改善中位数 | -76.26bps |
| 未成交回退改善 5% 分位 | -278.55bps |

主配置 2022–2026 各年改善分别为 +16.15 / +10.67 / +12.25 / +16.32 / +7.67bps，
全部为正；买入 +10.08bps、卖出 +12.96bps。Binance 30m 交叉检查覆盖率只有 **81.61%**，
但方向一致：有效成本 6.54bps、改善 +13.46bps。

**结论：平均执行改善成立，但尾部不合格直接切实盘。** 未成交回退的 8.6% 名义在不利行情中
承担了很大的追价成本（中位 -76bps，5% 分位 -279bps）；mark K 线触碰、队列位置和部分成交
也尚未验证。下一步必须先做真实盘口/订单簿 shadow，并测试“首小时逆向移动 guard”，而不是
把 8.45bps 直接写进 live 成本假设。

- 正式运行：是；
- 实盘：否；
- 修改当前实盘：否。
