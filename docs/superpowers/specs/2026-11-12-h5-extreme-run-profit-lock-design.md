# Atlas20 候选预注册：H5 单一龙头极端涨幅利润保护

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS22-H5-EXTREME-RUN-PROFIT-LOCK` |
| 基线 ID | `PR2026-10-D-L125` |
| 基础 alpha | 冻结 H5 1.25x 多头 |
| 新机制 | H5 最大持仓在 21D 涨幅 >=100% 时，仅减半该腿并留现金 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | target <=1.25x；hard 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

项目已有诊断（RESEARCH.md §00.18）显示：H5 最大持仓的 21D 涨幅进入历史上五分之一高位后，
未来 21 天策略收益显著低于其他状态；但此前没有把“极端涨幅后减仓”做成正式规则。LS22 只检验一个
简单、可解释的利润保护：

> 在每个 H5 多头目标事件，找出权重最大的单腿。如果该腿的 21D trailing return >= 100%，只把
> 这一腿的 target weight 减半，释放的权重全部留现金；不把资金再分配给其他币。

该机制直接对应负责人反复提出的“赚到的又亏回去”，同时不改变 H5 选币、相位、波动率缩放、
dispersion、BTC gate、gross cap 或 T+1 执行。

## 1. 参数来源与冻结

- 21D：与 RESEARCH.md §00.18 的极端涨幅诊断一致；
- 100%：诊断的五分之一阈值是 87%，但本试验使用更简单、更保守的事前整数阈值 **100%**，
  不使用 87% 这个样本内分位点；
- 0.5：与项目已登记的 H6/LS18 half-risk 机制一致；
- 不扫描 75%/87%/125%、不扫描 0.25/0.75 scale、不扫描 top-2/top-3、不扫描 lookback；
- 若最大持仓并列，按 coin id 字典序取第一个。

## 2. 运行前审计

只读审计：`reports/derivatives_track_h5_regime_short_router/profit_lock_audit/`。

| 项目 | 数值 |
|---|---:|
| H5 target events | 542 |
| 触发 trim 的事件 | 57（10.52%） |
| trim 时释放 gross 中位数 | 0.1717x NAV |
| trim 时释放 gross 最大值 | 0.2806x NAV |
| 2022/2023/2024/2025/2026 trim 次数 | 1/16/32/4/4 |

这说明机制不是只在单一事件触发；同时 2024 年触发最多，存在削减强势趋势收益的风险，必须在完整
成本档和路径检验中验证。

## 3. 冻结构造

```text
base = frozen H5 1.25x long-only
for each H5 target event D:
    leader = largest target weight
    r21(leader, D) = price(D) / price(D-21) - 1
    if r21 >= 1.0:
        weight(leader) *= 0.5
    all other weights unchanged
    freed weight -> cash
```

- 只作用于多头；不带空头；
- 不改变 H5 目标日期、选币、相位、波动率目标和 dispersion；
- 不把减仓资金转入其他币或 BTC；
- 下一次 H5 目标事件重新按当时 21D return 判断，不做额外状态机；
- 缺失/不可用价格不触发 trim；
- T+1 UTC +3h；Bitget mark；funding proxy/skip。

## 4. 预注册门槛

1. 20bps 终值 > L125；
2. 20bps Sharpe >= L125；
3. 20bps MDD <= L125 +5pp；
4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
6. 100bps MDD <=50%；
7. 删除任一最佳年份后终值仍高于同成本 L125；
8. 365 天滚动最差 >= L125；
9. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
10. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过基线，12/12 MDD 5pp；
11. observed gross <=1.50 且无 gross breach hour；
12. PBO/CSCV <=0.50，White Reality Check p <=0.05；
13. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
14. 12 个月真实 OOS 未满前最高只能 provisional。

## 5. 失败后动作

如果 LS22 失败：

- 不扫描涨幅阈值、lookback、scale、持仓数量、并列规则或再分配规则；
- 停止“单龙头极端涨幅减仓”家族；
- 提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 6. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS22-H5-EXTREME-RUN-PROFIT-LOCK \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_extreme_run_profit_lock
```

## 7. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
