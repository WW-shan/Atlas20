# Atlas20 候选预注册：H5 + 市场中性 funding carry sleeve

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS30-H5-FUNDING-CARRY-NEUTRAL` |
| 基线 | L125（`PR2026-10-D-L125`）；同时报告 LS23 作为 incumbent research candidate |
| 多头 | 冻结 H5 1.25x |
| 中性 sleeve | PIT Top20 非 H5 持仓中，7D funding 最低 2 币做多、最高 2 币做空；每腿 6.25% NAV，总 gross 25% NAV，净方向零 |
| 总预算 | long 1.25x + sleeve 0.25x = 1.50x hard total gross |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；50% buffer；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

此前的 funding 研究主要是：
- LS17/LS21/LS24：只做高 funding 空头；
- LS18：对 H5 多头做 funding 拥挤减半；
- H6：按组合 funding state 缩放整个 H5。

这些都不是一个**市场中性 carry 组合**。LS30 直接检验 Crypto Carry 文献的核心机制（S49）：
高 funding 的一端做空、低/负 funding 的一端做多，赚取 funding 差，同时用 H5 1.25x 保留
原策略的方向收益。中性 sleeve 只使用 H5 之外的 PIT Top20 成员，避免与 H5 多头在同一资产上
悄悄净额化；总 gross 仍严格不超过 1.50x。

## 1. 冻结构造

```text
H5_long = frozen H5 1.25x
carry_universe(D) = PIT Top20 members at D, excluding H5 holdings at D
score_i(D) = mean Binance funding settlement in [D-7D, D)
long_carry = 2 lowest score_i
short_carry = 2 highest score_i
w_i = +0.0625 if long_carry, -0.0625 if short_carry
carry_gross = 0.25x
combined = H5_long + carry_sleeve
max_total_gross = 1.50x
```

- 每 7 天再平衡，anchor 与 R6 相同；
- 至少 8 个可交易、有 funding、非 H5 持仓的成员才开仓，否则 sleeve 空仓；
- funding 只用信号日之前或当天的结算；缺失不插值、不填零；
- 若 carry 腿进入 H5 或离开 PIT Top20，下一次可用日退出，不等下一周；
- short 腿使用 20% adverse mark stop；long 腿无单独 stop；
- 不扫描 lookback、rank、2 币、6.25% 腿、min_assets 或 stop；
- 不把 H5 现有 1.25x 与 sleeve 的净额混为一谈；gross 按 long + |carry| 计。

## 2. 预注册门槛

1. 20bps 终值 > L125；
2. 20bps Sharpe > L125；
3. 20bps MDD <= L125 +5pp；
4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
6. 100bps MDD <= 50%；
7. 3x short-adverse 0 强平且 MDD <= 50%；
8. 删除任一最佳年份后终值仍高于 L125；
9. 365 天滚动最差 >= L125 的 0.7325x；
10. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
11. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过 L125，12/12 MDD 5pp；
12. 单资产空头贡献 <= 50%，前 3 <= 80%；
13. observed gross <=1.50 且无 gross breach hour；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月真实 OOS 未满前最高只能 provisional。

## 3. 失败后动作

如果 LS30 在 20bps 三项主门槛或成本门槛失败，停止该 carry sleeve，不扫描 lookback、rank、
2/3/4 币、腿权重、min_assets、stop 或再平衡周期；保留结果并继续研究新的独立信息源。

不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS30-H5-FUNDING-CARRY-NEUTRAL \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_carry_neutral
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
