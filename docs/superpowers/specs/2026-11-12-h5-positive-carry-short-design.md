# Atlas20 候选预注册：H5 positive-carry 熊市空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS21-H5-POSITIVE-CARRY-SHORT` |
| 基线 ID | `PR2026-10-D-L125` |
| 基础 alpha | 冻结 LS12：H5 1.25x + BTC 200D 双空头 regime router |
| 新机制 | 熊市 weak-four 空头只允许最近 3 个 settlement 的 mean funding 严格大于 0 的资产 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | target/hard total 1.50x；short <=0.25x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS12 的熊市 weak-four sleeve 使用 `mean funding > -0.0002` 作为闸门，允许空头在 funding 为负时继续持有。
负 funding 表示空头在支付、且多头拥挤度并未得到同方向确认；这与“做空拥挤多头”的经济机制相反，也会增加
被反弹挤出前的持有成本。

LS21 只改变这一条件：

> 熊市 weak-four 候选必须同时满足 `mean(last 3 funding settlements) > 0`；否则不进入空头篮子。
> 非熊市 funding-exit sleeve、H5 多头、20% stop、buffer、gross 和路由规则全部不变。

这不是扫描 `-0.0001/0/+0.0001` 等阈值。0 是 funding 方向的经济分界：只有正 funding 时空头才获得 carry；
负 funding 时不做方向性空头。失败后该阈值族停止。

## 1. 运行前 funding 审计

只读审计以 LS12 已保存的 335 个空头 episode 为对象，在 entry date 读取该资产最近 3 个实际 funding
settlement 的均值，并按 LS12 当天的 bear/non-bear regime 分组。

审计输出：`reports/derivatives_track_h5_regime_short_router/bear_funding_sign_audit/`。

- 熊市 weak-four episode：288 个；
- mean funding > 0：166 个；
- mean funding <= 0：122 个；
- 正 funding 组累计 episode PnL **+29.61% NAV**；
- 非正 funding 组累计 episode PnL **+0.28% NAV**，几乎全部是噪声；
- 非正 funding 组在 2023/2024 的 episode PnL 分别为 **-3.93% / -4.55% NAV**，单位 episode 亏损大于正 funding 组；但正 funding 组这两年也仍为负（-1.97% / -5.98%），因此本试验不假设过滤器能单独修复这两年的路径。

该审计只用于证明“过滤后仍有足够的正 carry 机会”，不作为收益验证；正式判断仍以完整引擎结果为准。

## 2. 冻结构造

```text
base = frozen LS12
if BTC < 200D SMA:
    candidates = PIT Top20 non-H5, PIT-tradable, weekly 14D weakest
    eligible = candidates with mean(last 3 settlements funding) > 0.0
    shorts = first 4 eligible, 6.25% NAV each
else:
    non-bear funding-exit sleeve exactly as LS12
```

- 若正 funding 候选少于 4 个，只做可用候选；少于 1 个则熊市 sleeve 为现金；
- 不对不足 4 个的情况放宽阈值或补入负 funding 资产；
- 每周仍只在 LS12 原有 anchor 和 7 日节奏评估；
- stop、buffer、missing mark、funding stress、gross cap 全部沿用 LS12；
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

如果 LS21 失败：

- 不扫描 funding 阈值、lookback、结算数、basket size、weight、stop 或 regime 窗口；
- 停止“positive-carry 熊市空头”阈值族；
- 提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 5. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS21-H5-POSITIVE-CARRY-SHORT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_positive_carry_short
```

## 6. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
