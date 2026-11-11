# Atlas20 候选预注册：H5 + 28D 横截面反转多空 sleeve

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS19-H5-REVERSAL-PAIR` |
| 基线 ID | `PR2026-10-D-L125` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 多头底稿 | 冻结 H5，1.25x target gross |
| 新 sleeve | 28D 横截面反转：多最弱 4 个、空最强 4 个 PIT Top20 非 H5 资产 |
| 单腿 | 2.5% NAV；long 0.10x + short 0.10x = 0.20x gross |
| 再平衡 | 每 28 个自然日 |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | target 1.45x；hard observed 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

此前的增强主要来自空头 overlay、风险减仓或执行容差；它们要么在 100bps 失败，要么以牺牲收益换回撤。
LS19 引入一个与 H5 选币方向相反、但可解释的 alpha：

> 在严格 PIT Top20 内，做多过去 28 天最弱的 4 个非 H5 资产、做空过去 28 天最强的 4 个非 H5
> 资产，形成小规模 dollar-neutral 反转 sleeve。H5 仍是主多头，反转 sleeve 只占 0.20x gross。

外部依据：

- Dobrynskaya (2023), S3：crypto 的正动量约持续 2–4 周，超过约一个月后出现显著反转，且反转
  主要由过去输家驱动；
- S2/S4/S14：横截面动量/反转在大币中更可测，但单一币可能主导结果，因此必须用 Top20 分位组合
  并报告集中度。

本试验不扫描 14/21/28/35/42D；28D 和 28D 再平衡直接来自 S3 的“约一个月切换点”。

## 1. 可行性审计

- 62 个 28D 评估日；
- PIT Top20 中排除 H5 后的可用候选最少 16、中位 19；
- long 4 与 short 4 从未重叠；
- 月度持有集合 turnover 中位 76.9%，最高 93.3%；
- 2022–2026 每年均有足够候选。

## 2. 冻结构造

```text
r28_i = close_i(D) / close_i(D-28) - 1
eligible = PIT Top20 ∩ Bitget mark available ∩ not current H5 long

losers  = four lowest r28_i
winners = four highest r28_i

factor: +0.025 NAV on each loser
        -0.025 NAV on each winner
H5 long: 1.25 × frozen H5 weights
total target gross <= 1.45
hard observed gross <= 1.50
```

- 每 28 个自然日评估一次，anchor = 2022-01-01；
- 候选少于 8 个时 fail closed，反转 sleeve 为空；
- long 与 short 必须来自不同资产；
- winner short 使用 20% adverse mark stop；
- 同一资产的长短腿在组合层按 signed target netting，报告净额；
- H5 选币、3 日相位、BTC gate、dispersion/volatility scaling 不变；
- T+1 UTC +3h；
- funding 主口径 Binance proxy/skip。

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

## 4. 失败后动作

如果 LS19 失败：

- 不扫描反转 lookback、rebalance 周期、4 币数量、2.5% 单腿、min assets、stop 或 H5/factor 比例；
- 停止 28D reversal-pair 家族；
- 提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 5. 复现

```bash
.venv/bin/python scripts/run_h5_reversal_pair.py \
  --trial-id PR2026-11-LS19-H5-REVERSAL-PAIR \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_reversal_pair
```

## 6. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
