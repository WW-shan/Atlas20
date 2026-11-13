# Atlas20 研究预注册：LS57 + 可执行 alt 空头 / BTC 现货 overlay

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 候选 ID | `PR2026-11-LS78-LS57-CHURN-SPOT-BTC-SHORT-ALT` |
| 基线 | LS57 20bps 68.8077x / Sharpe 1.9819 / MDD -39.84% |
| 信号 | 冻结 LS74 Top20 churn `m=7/h=28/alt_rel_60`，不重新选 m/h/gate |
| 执行结构 | 空 alt 永续 + 多 BTC 现货；BTC 腿不收 funding |
| 窗口 | 2022-01-01 → 2026-09-20 |
| 成本 | 20 / 50 / 100bps 每边；100bps 仅压力报告 |
| Gross | LS57 与 sleeve 合计硬上限 1.50x |

## 0. 研究问题

LS77 的 3x adverse 失败主要来自 sleeve 的 BTC 多头永续腿也被计 funding。LS78 只改变执行结构：
BTC 多头从永续换成现货，alt 空头仍用永续；价格收益和事件规则不变。由于 short 永续需要真实可用的
合约，信号日只保留过去 7 天内至少有一个跨交易所 funding settlement 的 alt；剩余空头腿在事件内
等权重建，保持 BTC 多头与 alt 空头相同的 notional。

funding 使用 Binance、Bybit、Bitget 三个来源的可用数据做保守合成：

- normal：每个 UTC 日的 funding settlement 求和后，跨 venue 取最小值（对 short 最不利）；
- adverse：每个 UTC 日先对 settlement 取绝对值和，再跨 venue 取最大值，再乘 1/2/3 倍；
- normal 只对 alt short 腿收费；BTC spot 腿不收费；
- 缺失 funding 的 short 权重单独报告，不默认为零收益；覆盖率低于 95% 只能判 partial。

这不是把 LS77 的 3x adverse 结果改阈值后宣布通过。LS78 是新执行结构；2x/3x adverse 仍全部报告，
即使失败也不再用调大 allocation、放宽成本或假设 funding 为零来掩盖。

## 1. 预注册验收

在 **20bps normal** 下的最大可晋级 allocation 必须同时满足：

- full 终值 > LS57 68.8077x；
- full Sharpe > 1.9819；
- full MDD 不差于 -40.84%；
- validation 终值和 Sharpe 都高于 LS57 同窗口；
- 最大 combined gross <= 1.50x；
- short funding 覆盖率 >= 95%；
- 同一 allocation 在 **20bps + 1x adverse** 下仍满足上述收益、Sharpe、MDD 和 validation 门槛。

50bps 和 100bps、2x/3x adverse 作为压力证据，不因 100bps 或 3x 未通过而停止研究；它们只阻止
promotion。通过只进入真实 Bitget mark/fill/funding 引擎和 shadow，不接实盘。

## 2. 失败后动作

若可执行币池重建后不能跑赢 LS57，则记录为 rejected，不扫描 m/h/gate/allocation。若只在正常
funding 下通过但 1x adverse 失败，则保留为低置信 sleeve，下一步研究 funding sign/venue
selection，而不是继续调 allocation。无论结果如何，不修改当前 live track。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls57_churn_spot_btc_short_alt.py \
  --start-date 2022-01-01 --end-date 2026-09-20 \
  --output-dir reports/ls57_churn_spot_btc_short_alt_2026
```
