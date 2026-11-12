# Atlas20 候选预注册：LS23 + 60D 低波动多空 sleeve

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS39-H5-LS23-LOWVOL-PAIR` |
| 基线 | L125；LS23 |
| 基础 book | 冻结 LS23：H5 1.25x 利润保护 + LS12 双空头 router |
| 新机制 | 28D 月度低波动多空 sleeve；60D 已实现波动率最低 4 名做多、最高 4 名做空 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS23 已经把 H5 动量多头与 LS12 双空头 router 组合成当前最强主样本候选，但它的 alpha 仍主要来自
价格动量和 funding/weakness 状态。LS33–LS38 证明继续增加周频 funding carry 或执行容差没有解决
100bps 成本尾部。因此下一个候选不再微调这些失败家族，而是测试一个机制上独立的横截面风险因子：

- 外部研究报告大型高流动性加密资产存在低波动异象，低波动组合配合简单止损可改善下行风险和
  Sharpe；
- 在横截面上，高波动/彩票型资产容易承受估值压力，低波动资产通常具有更稳定的风险调整收益；
- 但该外部证据主要是低波动多头，不证明“多低波/空高波”的美元中性 pair 在本项目 Top20 中有效，
  所以必须把横截面 pair 当作待证伪假设。

选择 60D 而非新窗口，是因为项目的 H5 生产规格已使用 60D realized volatility；选择 28D 月度
调仓，是为了避免把日频/周频因子变成不可承受的高换手策略。两者都不是根据本次收益结果扫描得到。

## 1. 冻结构造

```text
base(D) = frozen LS23
        = H5 1.25x long book with LS22 single-leader profit lock
          + LS12 BTC-200D dual-short router

sleeve(D) at every 28 calendar days from anchor 2022-01-01:
  members(D) = PIT Top20 members with Bitget mark available,
               excluding current H5 long holdings and any base-book asset
  sigma_i(D) = sample std(ddof=1) of daily log returns over the
               trailing 60 calendar days; require >=45 finite returns
  ranked(D) = sort sigma_i ascending, tie-break by coin_id
  long  = first 4 eligible names, +2.5% NAV each
  short = last 4 eligible names, -2.5% NAV each
  if <8 eligible names: sleeve = cash for that event

combine:
  base book has priority and is never scaled down;
  sleeve assets overlapping any base-book asset are removed;
  sleeve uses only residual non-overlapping gross;
  requested sleeve gross <=0.20x;
  hard total gross <=1.50x.
```

- H5 1.25x、LS22 的 21D/100%/0.5 利润保护、LS12 router、20% stop、50% buffer 全部冻结；
- sleeve 不改变 H5 选币、利润保护、router 方向或空头止损；
- 缺失波动率或不足 45 个有效收益的资产在该事件不合格；
- 不扫描 lookback 20/30/40/90/120D、count 2/3/5/6、权重、调仓频率或只做多/只做空变体；
- 不把 sleeve 当作新的杠杆层；总 gross 仍由 1.50x hard cap 约束。

## 2. 预注册门槛

研究价值（20bps，LS23 为 incumbent）：

1. LS39 终值 >= LS23 的 61.9150x；
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

任一 20bps 主收益/Sharpe/MDD 门槛失败，LS39 不得因为低相关或机制新颖而保留为实盘候选。
若 20bps 过门但 100bps、压力、路径或集中度失败，则该 sleeve 只保留为研究资产，不进入实盘。

## 3. 失败后动作

若 LS39 失败，停止该 60D/28D/4×4 低波动 pair 家族，不扫描替代窗口、数量、权重、频率或
多空方向。保留 LS23 作为 incumbent，不修改实盘。若 LS39 通过主样本，仍需完成真实 OOS、
funding exact、路径和多重检验，不能直接 promotion。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS39-H5-LS23-LOWVOL-PAIR \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_lowvol_pair
```

## 5. 状态

- 预注册：是；
- 正式运行：是；
- 结果：**rejected**；20bps 64.2279x / 1.9731 / -37.65%，但 3 次 long 强平；
- 实盘：否；
- 修改当前实盘：否。
