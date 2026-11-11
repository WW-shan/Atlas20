# Atlas20 候选预注册：H5 相对 BTC 走弱时周频轮入 25% BTC

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS14-H5-WEAK-ROTATE-BTC25` |
| 基线 ID | `PR2026-10-D-L125` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 基础 alpha | 冻结 LS12：H5 1.25x + BTC 200D 双空头 regime router |
| 新增风险层 | H5 影子 14D 收益低于 BTC 14D 时，把多头风险的 25% 轮入 BTC |
| risk-on | H5 多头 1.25x，BTC 防御 sleeve 0 |
| risk-off | H5 多头缩到 0.9375x，BTC 防御 sleeve 0.3125x |
| 空头 sleeve | LS12 的 bear weak4 / non-bear funding exit 互斥路由 |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | long target 1.25x；target/hard total 1.50x |

## 0. 研究问题

LS13 在 H5 相对 BTC 走弱时把多头减半到现金，MDD 改善到 -28.37%，但 20bps 终值只有
33.7083x，低于 L125 的 40.2200x，第一门槛失败。

这说明 H5 相对强度信号有风险识别价值，但直接去现金过度牺牲了复利来源。LS14 不再减 gross；
当 H5 弱于 BTC 时，把多头风险预算的 25% 从 H5 名单轮入 BTC，让组合仍保持市场暴露，只是把
一部分仓位转向更强的基准资产。

依据：

- 相对强度/双动量文献支持在风险资产弱于基准时把部分风险预算转移给基准；
- BTC 是该项目的基准资产，不是新的参数化选币模型；
- 25% 是一档防御风险预算，不扫描 10%/20%/30%/40%/50% 或改用 ETH/现金混合。

LS14 不改变 H5 选币、空头 router、stop、funding 或 bear/non-bear sleeve。风险开关只改变多头
权重和 BTC sleeve。

## 1. 冻结构造

### 风险信号

使用未减仓 H5 影子策略的日收益：

```text
h5_shadow_14d_t = prod(1 + r_h5_shadow[t-13:t+1]) - 1
btc_14d_t       = BTC_close[t] / BTC_close[t-14] - 1
weak_t          = h5_shadow_14d_t < btc_14d_t
```

每 7 个自然日采样 `weak_t`，持有到下个采样点；T+1 UTC +3h 执行。

### 目标账本

```text
if weak_t:
    h5_target = 1.25 * H5_weights_t * 0.75
    btc_target = 1.25 * 0.25 = 0.3125
else:
    h5_target = 1.25 * H5_weights_t
    btc_target = 0

if BTC is already in H5_weights_t:
    btc_target += 0.75 * H5_BTC_weight_t
```

- 多头目标 gross 仍为 1.25x（若 H5 自身 gross 小于 1.25x，则按实际 H5 gross 缩放）；
- BTC sleeve 不额外加杠杆，只替换原有 long risk budget；
- 空头仍然只能使用未使用 gross，hard total gross 1.50x；
- H5 持币名单不变，除 BTC 防御 sleeve 外没有新资产；
- 同一资产不能同时是多头和空头。

## 2. 评估门槛

LS14 只能在以下全部满足时升级：

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

如果 LS14 失败：

- 不扫描相对强度 lookback、评估频率、BTC 替代比例或防御资产；
- 不继续在同一 H5-relative-risk 家族内调参；
- 必须提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现接口

```bash
.venv/bin/python scripts/run_h5_btc_rotation.py \
  --trial-id PR2026-11-LS14-H5-WEAK-ROTATE-BTC25 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_btc_rotation
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
