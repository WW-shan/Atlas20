# Atlas20 双边轮动第六轮预注册：Bottom-Quincile 空头 + 20% 强制止损

| 项目 | 内容 |
|---|---|
| 状态 | 研究预注册；不接实盘 |
| 触发 | 第四/五轮 bottom-4 篮子收益有效，但 50% 和 75% buffer 仍有单腿强平 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 多头底稿 | 冻结 H5 / `PR2026-10-D-L125` |
| 空头 | Top20 中 14D 最弱 4 个币，等权，总 0.25x |
| 保证金 | short buffer=0.50 |
| 止损 | 单腿空头相对入场价不利 20% 时，逐小时 mark 触发平仓 |
| 再平衡 | 每 7 个自然日；T+1 +3h |

## 0. 研究问题

R4/R5 的 bottom-4 篮子有显著收益，但 XRP/TRON 的快速逼空分别穿透了 50% 和 75% 的保证金
缓冲，产生强平。继续提高 buffer 会占用过多保证金且无法排除更极端挤压；本项目原始设计已经
预注册了 `STOP20` 空头邻域，因此本轮检验：

> 在 20% adverse mark 处先平掉单腿，而不是等到清算，是否能保留横截面篮子的收益并消除强平？

这不是新的阈值网格：只使用原设计已登记的 20% stop，不扫 15/25/30%。

## 1. 冻结试验

| trial_id | 构造 | 空头总权重 | short buffer | stop |
|---|---|---:|---:|---:|
| `PR2026-11-RS6-X-WEAK4-STOP20` | H5 ×1.25 + 4 币最弱空头 | 0.25x | 0.50 | 20% adverse |

信号、篮子、再平衡和 funding guard 与 R4 完全一致。

## 2. 止损语义

- 只对空头腿启用；
- 入场价为实际成交价；
- 每个小时用 mark high/low 检查；
- 若当日 open 已越过止损价，按 open（加保守滑点）成交；
- 触发后该腿变现金，直到下一次预注册的周频信号重新选择；
- 止损成交记录为 `reason=stop_loss`，不得计入普通调仓；
- 止损是尾部保险，不是新的收益信号，不能用它来改变 H5 或空头选币。

## 3. 预注册门槛

1. 20bps 终值 > 修正 L125 基线；
2. Sharpe ≥ 基线；
3. MDD ≤ 基线 + 5pp；
4. 主样本 0 次强平；
5. 50bps 终值 > 同成本基线；
6. 100bps MDD ≤ 50%；
7. 3x short-adverse 0 次强平且 MDD ≤ 50%；
8. 移除 2022 后仍高于基线；
9. PBO/CSCV ≤ 0.5；
10. 报告年度、滚动最差、空头开仓/止损次数、单腿最大贡献、最佳年份移除；
11. 真 OOS 不足 12 个月时最多 provisional，禁止接实盘。

任何一项失败即拒绝；不继续调 stop/buffer。

## 4. 复现

```bash
.venv/bin/python scripts/run_derivatives_backtest.py \
  --trial-id PR2026-11-RS6-X-WEAK4-STOP20 \
  --start-date 2022-01-01 --end-date 2026-09-21 \
  --cost-bps 20 --short-buffer 0.50 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_cross_sectional_basket_round6
```

---

## 5. 第六轮结果（2026-11-10）

20bps：`PR2026-11-RS6-X-WEAK4-STOP20` 为 **51.8010x / 1.8918 / -42.5916% / 0 强平**，
止损 50 次；50bps 为 28.3854x / 1.6409 / -47.1790%，高于基线 27.3725x；3x short-adverse
funding 为 49.6029x / 1.8723 / -42.9484% / 0 强平。

但 100bps 为 10.3786x / 1.2196 / **-54.0625%**，低于基线 14.3794x 且越过 50% MDD；
移除 2022 后为 48.5848x，低于基线 50.0330x。PBO/CSCV=0.0281，滚动最差 0.7958x。

判定：**provisional research candidate，拒绝实盘。** 不能因为 20/50bps 通过就忽略 100bps
和 2022 依赖；后续只能预注册降低换手/成本的新机制，不能扫描 stop、buffer 或篮子大小。
