# Atlas20 候选预注册：H5 1.25x + BTC 200D 熊市闸门下的最弱四币空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS11-H5-WEAK4-BEAR200-STOP20` |
| 基线 ID | `PR2026-10-D-L125` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 多头 | 冻结 H5，1.25x 目标 gross |
| 空头 | PIT Top20 中 14D 最弱 4 个可交易、非 H5 多头持仓，等权；总空头 0.25x |
| 熊市闸门 | 仅在信号日 BTC close < 200D SMA 时允许新一期空头篮子；否则该周目标为空 |
| 再平衡 | 每 7 个自然日；T+1 UTC +3h |
| 单腿 stop | 20% adverse mark |
| gross | target/hard 1.50x（1.25x 多 + 0.25x 空） |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

R6 已经证明 bottom-quintile 最弱四币空头 + 20% stop 可以把强平尾部转化为可控止损，并在
20bps 达到 51.8010x / Sharpe 1.8918 / MDD -42.59%，但 100bps 失败、移除 2022 后低于基线，
且每周完整重排带来高换手。R7 的宽持有带失败，说明不能靠持有带修复这个 sleeve。

LS11 不再改变选币、持有带、stop 或篮子大小，而是增加一个宏观 regime gate：

> 只有 BTC 已经跌破 200D SMA 时才做 bottom-quartile 空头；BTC 在 200D 上方时空头 sleeve
> 保持现金。

依据：

- H5 多头本身已经使用 BTC 趋势共闸；200D 是项目已有的长期趋势尺度；
- 时间序列动量/趋势过滤文献支持在长期趋势向下时承担空头风险；
- 该 gate 的动机是把空头风险集中在 2022 类熊市，而不是在牛市相对强弱噪声上持续换手。

不扫描 50/100/150/250D 或其他 MA 窗口；不扫描 bottom-3/4/5、14D lookback、7D 再平衡、
0.25x 总空头、20% stop 或 50% short buffer。

## 1. 冻结构造

每个第 7 个自然日的 UTC 收盘：

```text
base_t = PIT CMC Top20_t
         ∩ Bitget mark available at t+1
         ∩ funding guard passes
         − current H5 long holdings

if BTC_close(t) < SMA200(BTC_close)(t):
    ranked_t = ascending 14D return over base_t
    short_t = ranked_t[0:4], each 6.25% NAV
else:
    short_t = empty
```

- funding guard：每腿最近 3 个 funding settlement 均值 > -0.0002；缺失 fail closed；
- 逐周目标为空时，旧空头在下一执行时点退出；
- 空头腿在入场价 adverse 20% 处逐小时 mark 止损；
- 同一资产不会同时作为 H5 多头和空头；
- 缺失 mark 不填充，按引擎 carry≤3h 或退出规则处理。

## 2. 评估门槛

LS11 只能在以下全部满足时升级：

1. 20bps 终值严格高于 L125 基线；
2. 20bps Sharpe 不低于 L125 基线；
3. 20bps MDD 不差于 L125 基线 +5pp；
4. 主样本 0 次强平；
5. 50bps 终值仍高于同成本 L125 基线；
6. 100bps MDD ≤ 50%；
7. 3x short-adverse 0 强平且 MDD ≤ 50%；
8. 删除 2022 后仍高于 L125 基线；
9. 365 天滚动最差不低于 L125 基线；
10. 12 个真实月初引擎启动中至少 8/12 终值和 Sharpe 胜过基线，MDD 5pp 12/12；
11. 单资产空头贡献 ≤50%，前 3 ≤80%；
12. PBO/CSCV ≤0.50，White Reality Check p ≤0.05；
13. Top20/2022 与全项目 DSR ≥0.95 才可 promotion；
14. 12 个月真实 OOS 未满前最高只能 provisional。

## 3. 失败后动作

如果 LS11 失败：

- 不扫描 BTC MA 窗口、bottom 数量、lookback、再平衡、stop、buffer 或总空头权重；
- bottom-quintile 空头族停止继续参数化；
- 必须提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现接口

```bash
.venv/bin/python scripts/run_derivatives_backtest.py \
  --trial-id PR2026-10-D-L125 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_weak4_bear200_stop20

.venv/bin/python scripts/run_derivatives_backtest.py \
  --trial-id PR2026-11-LS11-H5-WEAK4-BEAR200-STOP20 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_weak4_bear200_stop20
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
