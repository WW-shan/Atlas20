# Atlas20 候选预注册：H5 相对 BTC 走弱时周频半仓 + LS12 双空头 router

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS13-H5-REL14-WEEKLY-HALF-RISK` |
| 基线 ID | `PR2026-10-D-L125` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 基础 alpha | 冻结 LS12：H5 1.25x + BTC 200D 双空头 regime router |
| 新增风险层 | 每周检查 H5 影子策略 14D 收益是否低于 BTC 14D 收益；走弱时 H5 多头减半 |
| 风险开 / 风险关 | long 1.25x / 0.625x |
| 空头 sleeve | LS12 的 bear weak4 与 non-bear funding exit 互斥路由 |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | target/hard total 1.50x |

## 0. 研究问题

LS12 在 20bps 达到 55.7859x / Sharpe 1.8520，但 100bps 仍为 14.3604x / 1.3129 /
MDD -50.1067%，且删除 2022 后低于 L125。项目的 100bps 最大回撤主要发生在 2023 年上半年：
H5 多头仍然满仓，但组合相对 BTC 明显走弱。

LS13 不再增加空头权重，也不修改 LS12 的空头路由。新增一层独立的**相对强度风险开关**：

> 如果 H5 影子策略过去 14D 的收益低于 BTC 过去 14D 的收益，则下一周 H5 多头目标减半；
> 否则恢复 1.25x。空头 sleeve 不受此开关影响。

依据：

- 相对强度/横截面动量文献支持在组合持续弱于基准时降低风险暴露；
- 14D 是 H5/LS11 已冻结的短周期尺度，7D 是 LS12 bear sleeve 已冻结的再平衡尺度；
- 50% 是明确的半风险状态，不扫描 60%/70%/80%/90% 或 21D/30D/60D 窗口。

LS13 不扫描相对强度 lookback、评估频率、减仓比例、空头参数或 gross。相对强度只决定
H5 多头风险预算，不改变持币名单、空头选币或 stop。

## 1. 冻结构造

### 风险信号

使用**未减仓的 H5 影子策略**（L125、同 mark、同 funding、同成本假设）的日收益，保证信号本身
不会被减仓后的实际收益路径反向污染：

```text
h5_shadow_14d_t = prod(1 + r_h5_shadow[t-13:t]) - 1
btc_14d_t       = BTC_close[t] / BTC_close[t-14] - 1
weak_t          = h5_shadow_14d_t < btc_14d_t
```

每个 7 个自然日的 UTC 收盘采样 `weak_t`，持有到下个采样点；信号只使用完成日数据，T+1 UTC +3h
执行。若历史不足 14D，fail closed 为 weak=false（保持 1.25x）。

### 目标账本

```text
long_scale_t = 0.50 if weak_t else 1.00
long_target_t = 1.25 * H5_weights_t * long_scale_t
short_target_t = LS12 regime-routed short schedule
hard total gross <= 1.50x
```

- H5 多头持币名单不变；
- 空头路由、funding、stop、gross 和 bear/non-bear sleeve 全部沿用 LS12；
- 相对强度开关只缩放多头权重，不重新归一化或换币；
- 现金是减仓后的唯一防御资产。

## 2. 评估门槛

LS13 只能在以下全部满足时升级：

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

## 3. 失败后动作

如果 LS13 失败：

- 不扫描相对强度 lookback、周频变日频/月频、减仓比例或弱/强阈值；
- 不继续在同一 H5 relative-risk 家族内调参；
- 必须提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现接口

```bash
.venv/bin/python scripts/run_h5_relative_half_risk.py \
  --trial-id PR2026-11-LS13-H5-REL14-WEEKLY-HALF-RISK \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_relative_half_risk
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
