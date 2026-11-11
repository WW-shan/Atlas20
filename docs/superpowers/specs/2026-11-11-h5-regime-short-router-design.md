# Atlas20 候选预注册：H5 1.25x + 按 BTC 200D 路由的双空头 sleeve

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS12-H5-REGIME-SHORT-ROUTER` |
| 基线 ID | `PR2026-10-D-L125` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 多头 | 冻结 H5，1.25x target gross |
| 空头 sleeve A | BTC close < 200D SMA：14D 最弱 4 个 PIT Top20 可交易、非 H5 多头；每腿 6.25% NAV |
| 空头 sleeve B | BTC close >= 200D SMA：H5 完全退出币中 funding 拥挤的 21 日空头；每腿 2.5% NAV |
| 路由 | 同一时点只允许一个空头 sleeve 有目标；regime 切换时旧 sleeve 在下一执行时点清空 |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |
| gross | long 1.25x；target/hard total 1.50x；单一时点 short <=0.25x |

## 0. 研究问题

LS6 证明 funding 拥挤的 H5 退出币空头有稳定的增量，但滚动最差仍低于 H5；LS11 证明
BTC 熊市闸门下的最弱四币空头可以显著改善 2022 和滚动最差，但 100bps、删除 2022、路径切片
和空头集中度失败。

两者不是同一机制：

- LS6 是**事件驱动的个股/资产退出 + funding 拥挤**，在正常和牛市环境中寻找相对价值；
- LS11 是**熊市中的横截面弱势 basket**，承担更高波动来换取危机期的下行保护。

LS6 与 LS11 相对 H5 的日增量收益相关性约 0.23，说明它们不是同一 alpha 的重复表达。LS12 不再
尝试把两者按任意权重叠加，而是用已存在的 BTC 200D regime 做成互斥路由：熊市承担横截面空头风险，
非熊市回到 funding 退出空头。这样不引入新的权重、lookback、basket size、stop 或 funding 参数。

LS12 不扫描 50/100/150/250D MA、bottom 数量、14D/21D 持有期、7D 再平衡、20% stop、0.25x
总空头或任何 sleeve 权重；两个 sleeve 的内部构造均沿用已冻结规格。

## 1. 冻结构造

每个 UTC 日收盘生成一次目标，T+1 UTC +3h 执行：

```text
bear_t = BTC_close(t) < SMA200(BTC_close)(t)

if bear_t:
    short_t = weekly_weak4_t
else:
    short_t = funding_exit_t
```

### Sleeve A：bear weak4

- 在每 7 个自然日的 UTC 收盘评估；
- PIT CMC Top20 ∩ Bitget mark available ∩ funding guard − 当前 H5 多头；
- 按 14D 收益从低到高取最多 4 个；
- 每腿 6.25% NAV；
- funding guard：最近 3 个 settlement 均值 > -0.0002，缺失 fail closed；
- 20% adverse mark 单腿 stop；
- 非熊市或 regime 切换时，下一执行时点清空旧 basket。

### Sleeve B：non-bear funding exit

- 在 H5 完全退出某资产时评估；
- 资产仍须在 PIT Top20、Bitget mark available；
- 7D funding rank 位于 eligible cross-section 的上三分之一，至少 5 个有效资产；
- 21 日持有，H5 重新买入则提前退出；
- 每腿 2.5% NAV；
- 20% adverse mark 单腿 stop；
- 熊市或 regime 切换时，下一执行时点清空旧 sleeve。

### 共享约束

- 同一资产不得同时是 H5 多头和空头；
- 两 sleeve 不得同时有非零目标；
- 空头只使用未使用 gross，target/hard total 1.50x；
- long buffer 0.50、short buffer 0.50；
- 缺失 mark 按引擎 carry≤3h 或退出规则处理；
- funding 缺失按 `skip` 标注，不静默填零。

## 2. 评估门槛

LS12 只能在以下全部满足时升级：

1. 20bps 终值严格高于 L125 基线；
2. 20bps Sharpe 不低于 L125；
3. 20bps MDD 不差于 L125 +5pp；
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

如果 LS12 失败：

- 不扫描 sleeve 权重、MA 窗口、bottom 数量、lookback、再平衡、stop、buffer 或总空头；
- 不把 LS6/LS11 的失败参数重新组合成同一族继续调参；
- 必须提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现接口

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS12-H5-REGIME-SHORT-ROUTER \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_regime_short_router
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
