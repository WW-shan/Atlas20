# Atlas20 候选预注册：LS23 + 60D 逆波动率多头权重

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS40-H5-LS23-INVVOL60` |
| 基线 | L125；LS23 |
| 基础 book | 冻结 LS23：H5 1.25x 利润保护 + LS12 双空头 router |
| 新机制 | 在每个 H5 多头目标事件内，用 60D 日收益逆波动率重新分配同一事件 gross |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS23 的 H5 多头由 12 个相位 sleeve 叠加形成，总 gross 已经过 H5 的 60D 组合波动率缩放，但每个
目标事件内部的币权重仍主要反映 sleeve 合流和选币共识，不是按各币风险贡献分配。审计显示 542 个
H5 目标事件中有 380 个持有 2–5 个资产（70.1%），因此事件内部的相对权重有明显影响。

LS40 不增加总 gross、不增加多头资产、不改变 H5 选币和 short router，只把每个非空多头事件内部的
同一 gross 按 60D 逆波动率重新分配。它是对现有风险预算的再分配，不是 new alpha sleeve，也不会
把低波动资产加入 book。选择 60D 是因为 H5 的生产风险缩放已经使用 60D realized volatility；不扫描
20/30/90/120D，也不扫描等权、最小方差、协方差收缩或其他权重变体。

## 1. 冻结构造

```text
base_long(D) = frozen H5 1.25x target before LS22 profit lock
for each non-empty H5 target event D:
  held(D) = assets with base_long(D) > 0
  if len(held(D)) < 2: weighted(D) = base_long(D)
  else:
    sigma_i(D) = sample std(ddof=1) of daily log returns over trailing 60D
    require >=45 finite returns for every held asset
    score_i = 1 / sigma_i
    weighted_i(D) = base_long_i(D).sum() * score_i / sum_j score_j
  if any held asset fails volatility availability: weighted(D) = base_long(D)
  apply frozen LS22 single-leader profit lock to weighted(D)
  carry weighted/trimmed long weights into frozen LS12 short-router combination

short router, 20% stop, 50% buffers, H5 leverage and hard total gross 1.50x unchanged.
```

- 单币事件不改变权重；
- 目标事件 gross 严格保持不变，利润保护在其后再把龙头腿减半并留现金；
- 不使用当日之后的数据，不补缺失收益；缺失波动率时整个事件 fail-closed 保持原 H5 权重；
- 不扫描 max asset cap、lookback、minimum observations 或权重变换；
- sleeve 不增加 gross、不增加多头或空头，且不改变 existing risk controls。

## 2. 预注册门槛

研究价值（20bps，LS23 为 incumbent）：

1. LS40 终值 >= LS23 的 61.9150x；
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

任一 20bps 主收益/Sharpe/MDD 门槛失败，LS40 不得因为机制看起来更“稳健”而保留为实盘候选。
若 20bps 过门但 100bps、压力、路径或集中度失败，则不进入实盘，不扫描替代参数。

## 3. 失败后动作

若 LS40 失败，停止 60D 逆波动率多头权重家族，不扫描 20/30/90/120D、等权、最小方差、协方差、
asset cap 或只对部分币加权的变体。保留 LS23 作为 incumbent，不修改实盘。若 LS40 通过主样本，
仍需完成真实 OOS、funding exact、路径和多重检验，不能直接 promotion。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS40-H5-LS23-INVVOL60 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_invvol60
```

## 5. 状态

- 预注册：是；
- 正式运行：是；
- 结果：**rejected**；20bps 29.8565x / 1.7063 / -41.30%，0 强平但主收益与 Sharpe 失败；
- 实盘：否；
- 修改当前实盘：否。
