# Atlas20 候选预注册：LS12 的非熊市高 funding 拥挤空头 basket

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS17-H5-FUNDING-BASKET` |
| 基线 ID | `PR2026-10-D-L125` |
| 基础 alpha | 冻结 H5 1.25x + 冻结 BTC 200D bear weakest-four sleeve |
| 新机制 | 非熊市 sleeve 改为全 PIT Top20 中最高正 funding 的 4 个非 H5 资产 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | long 1.25x；short <=0.25x；hard total 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS12 的双空头 router 在 20bps 为 **55.7859x / 1.8520 / -40.64%**，但 100bps 只到
14.3604x，略输 L125；删除 2022 和 2023-01 路径也失败。LS16 证明执行容差能修复 100bps
成本，但会破坏 2023-2024 路径，因此该机制被拒绝。

LS12 非熊市 sleeve 的事件选择范围只包括 **H5 已经退出的资产**。这会把 funding 拥挤信号限制在
一个与 H5 选币高度相关的子集里。LS17 检验一个不同的信号来源：

> 非熊市时，直接在整个 PIT Top20 的 H5 非持仓中，做空 7D funding 最高且仍为正的 4 个资产。
> 高 funding 代表多头杠杆需求拥挤，同时空头可以直接收取 carry；这两个经济机制都与 H5 退出无关。

外部依据：

- Crypto Carry（Management Science，S49）：crypto carry 可以很高且波动，反映杠杆需求与套利资本
  限制；
- S50：累计 funding 和杠杆指标对极端下跌有预测力，支持把 funding 拥挤作为风险信号，而不是收益
  保证。

文献只支持机制方向，不采用其收益数字。

## 1. 可行性审计（正式运行前）

只读审计结果：

- 247 个 weekly 评估日；
- 每日可计算 7D funding 的 PIT Top20 非 H5 资产最少 15 个、中位 18 个；
- positive-funding 资产中位 14 个；
- 243/247 个周有至少 4 个正 funding 候选，另外 4 周用可用正 funding 名称；
- LS12 原有非熊市 H5-exit entries 中只有 5/72 的 7D funding 为负，说明“仅做 funding>0 过滤”
  几乎没有作用；必须改变选币横截面，才是有意义的机制变化。

## 2. 冻结构造

```text
bear_t = BTC_close(t) < SMA200(BTC_close)(t)

if bear_t:
    short_t = weekly_weak4_t       # 与 LS12 完全相同
else:
    short_t = weekly_high_funding_top4_t
```

### Non-bear high-funding sleeve

- 每 7 个自然日评估，anchor = 2022-01-01；
- 候选 = PIT CMC Top20 ∩ Bitget mark available ∩ 非当前 H5 多头；
- 计算最近 7 天 settlement 的 mean funding；
- 只在 mean funding **严格大于 0** 的资产中排序，取最高 4 个；
- 每腿 6.25% NAV，总空头 <=0.25x；
- 有效 funding 资产少于 5 个时 fail closed，该周空头为空；
- 正 funding 名称少于 4 个时按实际数量持有，不把权重转移给负 funding 资产；
- 每腿 20% adverse mark stop；
- regime 切换时旧 sleeve 在下一执行时点清空；
- 不改变 H5 long、LS11 bear sleeve、20% stop、50% short buffer、missing-mark 规则或 gross cap。

### 共享约束

- 同一目标中空头只使用未使用 gross；
- target/hard total gross <=1.50x；
- T+1 UTC +3h；
- funding 缺失按 `skip` 标注，不静默填零；
- funding 主口径仍是 Binance proxy，不能声称 Bitget 精确历史已闭合。

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

如果 LS17 失败：

- 不扫描 funding lookback、rebalance 频率、4 币数量、6.25% 权重、min_assets、正 funding 阈值
  或 stop；
- 停止 high-funding basket 家族；
- 必须提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 5. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS17-H5-FUNDING-BASKET \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_basket
```

## 6. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
