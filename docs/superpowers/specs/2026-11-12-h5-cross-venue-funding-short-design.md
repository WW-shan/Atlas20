# Atlas20 候选预注册：H5 利润保护 + 跨所 funding 确认空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS24-H5-PROFIT-LOCK-CROSS-VENUE-SHORT` |
| 基线 | `PR2026-11-LS23-H5-PROFIT-LOCK-REGIME-SHORT` |
| 多头 | 冻结 H5 1.25x + LS22 单龙头利润保护 |
| 空头 | 冻结 LS12 BTC-200D 双空头 router，但每个空头候选必须通过跨所 funding 确认 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | target/hard total 1.50x；short <=0.25x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy + Bybit funding confirmation |

## 0. 研究问题

LS23 的空头 alpha 主要来自 LS12，但 LS12 的 funding 只用 Binance 一个 venue。单 venue 的
funding 可能同时包含真实拥挤和 venue-specific 噪声；跨所 funding premia 已经证明是真实且
双向的（Bybit/Binance 逐年中位数 0.897–1.129，2026 年 0.673；Bitget/Binance 近期 1.59x）。
因此本试验只检验一个新增信息源：

> 如果 Binance 和 Bybit 的资金费率都确认多头在付费，才允许开空；如果两所不一致或 Bybit
> 缺失，则该资产不做空。

这不是对 LS12 的 bottom、lookback、rebalance、stop、buffer 或权重的扫描，也不是对 LS21
正 funding 阈值的重跑。LS21 只用了 Binance；LS24 用两个 venue 的**保守下界**，并把缺失的
第二 venue 当作不合格。

## 1. 跨所数据覆盖审计（运行前）

只读审计：`reports/derivatives_track_cross_venue_funding_audit/`。

- LS12 共 335 个已配对空头 episode；
- Bybit funding 可用 311 个，覆盖率 **92.8%**；
- bear episodes 288 个，Bybit 可用 265 个；Binance 与 Bybit 同时为正 138 个；
- non-bear episodes 47 个，Bybit 可用 46 个；同时为正 39 个；
- 缺失的 Bybit 历史不填充，直接视为不合格；
- 该审计不读取 episode PnL，不用于挑阈值。

## 2. 冻结构造

```text
f_binance_i(D) = mean(last 3 Binance settlements <= D)
f_bybit_i(D)   = mean(last 3 Bybit settlements <= D)
f_cv_i(D)      = min(f_binance_i(D), f_bybit_i(D))

short candidate eligible iff f_cv_i(D) > 0
bear sleeve: frozen LS12 weak-four, with threshold replaced by f_cv > 0
non-bear sleeve: frozen LS12 H5-exit, rank by f_cv; only positive f_cv eligible
long book: frozen H5 1.25x + LS22 profit lock
```

- 任一 venue 缺数据：`f_cv = NaN`，该资产不合格；不得 carry、不得用另一 venue 替代；
- 空头仍只使用未使用 gross，总空头 <=0.25x，hard total gross <=1.50x；
- 20% stop、50% long/short buffer、T+1 +3h、missing-mark carry 3h 全部沿用；
- 不扫描 funding lookback、settlement 数、min 组合方式、阈值、basket size、stop、buffer、
  regime window 或组合权重。

## 3. 预注册门槛

1. 20bps 终值 > LS23 同口径终值；
2. 20bps Sharpe >= LS23 同口径 Sharpe；
3. 20bps MDD <= LS23 +5pp；
4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 LS23；
6. 100bps MDD <=50%；
7. 3x short-adverse funding 0 强平且 MDD <=50%；
8. 删除任一最佳年份后终值仍高于同成本 LS23；
9. 365 天滚动最差 >= LS23；
10. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
11. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过 LS23，12/12 MDD 5pp；
12. 单资产空头贡献 <=50%，前 3 <=80%；
13. observed gross <=1.50 且无 gross breach hour；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月真实 OOS 未满前最高只能 provisional；
17. pre-2022 proxy stress 必须单独报告；若 funding proxy 下终值或 Sharpe 低于 LS23，
    只能保留 provisional，不能 promotion。

## 4. 失败后动作

如果 LS24 失败：

- 不扫描跨所 funding 的 settlement 数、lookback、min/mean/median 组合、正阈值、basket size、
  stop、buffer、regime 窗口或权重；
- 记录为“单 venue funding 的噪声假设未转化为可交易 alpha”；
- 不修改 LS23 的 provisional 状态，不接执行器；
- 下一个机制必须来自新的独立信息源，而不是继续拆 LS12/LS24 的 funding 参数。

## 5. 复现

```bash
.venv/bin/python scripts/audit_cross_venue_funding.py

.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS24-H5-PROFIT-LOCK-CROSS-VENUE-SHORT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --bybit-funding-dir data/raw/alternative_funding/bybit \
  --output-dir reports/derivatives_track_h5_cross_venue_funding_short
```

## 6. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
