# Atlas20 候选预注册：LS57 + core8 low-funding long-only

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；研究输出不接实盘 |
| 候选 ID | `PR2026-11-LS88-LS57-CORE8-LOWFUNDING-LONG` |
| 基线 | 冻结 LS57 |
| Sleeve | core8 中 7D mean Binance funding 最低 2 币，每腿 25% NAV；只做多 |
| 风险包 | long buffer 60%，目标 gross 1.45x，hard cap 1.50x |
| 总 sleeve gross | 10% / 20% / 25% NAV（residual gross 上限内） |
| 窗口 | 2022-01-01 → 2026-09-20；warmup 2021-01-01 |
| 执行 | T+1 +3h；Bitget mark/liquidation，Bitget market fill；missing mark carry 3h |
| 成本/压力 | 20/50/100bps；正常与 3x long-adverse funding |

## 0. 研究问题

LS81/LS82 的 market-neutral carry 在正常 funding 下有小幅增量，但成本/adverse funding 失败。
本 trial 只改变 sleeve 的方向结构：去掉高 funding 空头，只保留最低 funding 的 2 个 long leg，
检验 LS81 的增量是否来自 long leg，还是来自多空组合的会计/风险结构。它不是重新调 core8、
lookback、腿数或 allocation；`allocation` 定义为目标 sleeve gross，不是原始 schedule 的倍数。

## 1. 冻结构造

```text
core8 = BTC/ETH/SOL/XRP/BNB/DOGE/ADA/AVAX
score_i(D) = mean Binance funding settlements in [D-7D, D)
eligible = core8 with mark/fill and finite score; exclude LS57 base active assets
long = two lowest scores, each +25% NAV before sleeve scaling
sleeve target gross = 10/20/25% NAV, capped by LS57 residual gross
```

- 信号严格 PIT；不使用 D 当天 settlement 或未来价格。
- 只做多，不加空头；long buffer 60%，目标 gross 1.45x，hard cap 1.50x。
- 不扫描 score window、count、per-leg weight、allocation 范围或 long buffer。
- 50/100bps 和 3x long-adverse funding 必报。

## 2. 预注册判定

1. 25% sleeve gross 的 20bps full multiple 和 Sharpe 都高于 LS57 60%/1.45x 基线；
2. validation multiple/Sharpe 也高于基线；
3. 20bps 0 强平、0 gross breach、max observed gross <=1.50x；
4. 50bps 和 100bps 不出现收益/Sharpe 反转；
5. 3x long-adverse funding 下报告终值、Sharpe、MDD、强平和 funding；
6. 若结果只是 beta/牛市暴露，必须标记 concentration/regime fail，不晋级。

如果失败，long-only carry 家族停止，不再用 short-only、count 或 allocation 救结果。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls81_core_major_funding_carry.py \
  --trial-id PR2026-11-LS88-LS57-CORE8-LOWFUNDING-LONG \
  --warmup-start 2021-01-01 --start-date 2022-01-01 --end-date 2026-09-21 \
  --costs-bps 20,50,100 --allocations 0.10,0.20,0.25 \
  --funding-scenarios normal,two-sided-adverse-3x \
  --carry-side long-only --long-buffer 0.60 --target-gross 1.45 \
  --output-dir reports/ls88_lowfunding_long_2026
```
