# Atlas20 双边轮动第五轮预注册：Bottom-Quincile 空头 + 75% buffer

| 项目 | 内容 |
|---|---|
| 状态 | 研究预注册；不接实盘 |
| 触发 | 第四轮 bottom-4 篮子有收益，但 3 次单腿强平；只测试一个风险控制版本 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 多头底稿 | 冻结 H5 / `PR2026-10-D-L125` |
| 空头 | Top20 中 14D 最弱 4 个币，等权，总 0.25x |
| 保证金 | 空头 buffer=0.75（不是 0.50）；其他规则不变 |
| 再平衡 | 每 7 个自然日；T+1 +3h |
| 数据 | Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

第四轮 `PR2026-11-RS4-X-WEAK4` 在 20bps 下终值 53.0245x、Sharpe 1.8980、MDD -41.5294%，
但出现 3 次强平：XRP 两次、TRON 一次。收益信号本身值得继续核实，但强平是不可接受的硬失败。

本轮不改变选币、14D lookback、7D holding、0.25x 总空头或 4 币等权，只改变**空头保证金
buffer**：从 50% 提高到 75%。这是单一名义的尾部保险，不是收益参数扫描。

## 1. 冻结试验

| trial_id | 构造 | 空头腿 | short buffer |
|---|---|---|---:|
| `PR2026-11-RS5-X-WEAK4-SB75` | H5 ×1.25 + 4 币最弱空头 | 0.0625x × 4 | 0.75 |

只跑这一条。若失败，不能继续扫 60/80/90% buffer。

## 2. 规则

与第四轮完全相同：

```text
long_i,t = 1.25 × w_H5_i,t
short_basket_t = bottom 4 by 14D return among eligible PIT Top20
short_i,t = -0.0625 for each selected coin
rebalance every 7 calendar days
funding guard per short: last 3 settlements mean > -0.0002
```

唯一差异是 `short_buffer=0.75`，使空头强平距离从约 50% 提高到更保守的水平。空头总 gross
仍为 0.25x，gross 上限仍为 1.5x。

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
10. 报告年度、滚动最差、空头开仓次数、单腿最大贡献、最佳年份移除；
11. 真 OOS 不足 12 个月时最多 provisional，禁止接实盘。

## 4. 判定边界

若 R5 仍强平、50bps 低于基线或 PBO >0.5，则 bottom-quintile 双边空头线停止；不再调整
buffer、篮子大小或窗口。当前实盘仍只运行 H5 多头。

## 5. 复现

```bash
.venv/bin/python scripts/run_derivatives_backtest.py \
  --trial-id PR2026-11-RS5-X-WEAK4-SB75 \
  --start-date 2022-01-01 --end-date 2026-09-21 \
  --cost-bps 20 --short-buffer 0.75 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_cross_sectional_basket_round5
```

---

## 6. 第五轮结果（2026-11-10）

`PR2026-11-RS5-X-WEAK4-SB75` 在 20bps 下为 51.2754x / 1.8817 / -41.5294%，但仍有
**2 次强平**（XRP、TRON）。75% buffer 未能消除单腿挤压尾部；按预注册停止，不再扫 80/90%。
