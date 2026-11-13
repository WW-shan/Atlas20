# Atlas20 候选预注册：LS57 逐资产 21D SMA 退出

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；研究输出不接实盘 |
| 候选 ID | `PR2026-11-LS89-LS57-ASSET-MA21-EXIT` |
| 基线 | LS57（H5 1.25x + LS23 profit-lock + BTC-regime short router） |
| 新增规则 | 信号日 D 的 long leg 收盘低于自身 21D SMA 时，该 leg 目标降为 0；不重分配 |
| 风险包 | long buffer 60%，目标 gross 1.45x，hard cap 1.50x |
| 空头 | 保持 LS57 router 完全不变 |
| 窗口 | 2022-01-01 → 2026-09-20；warmup 2021-01-01 |
| 执行 | T+1 +3h；Bitget mark/liquidation，Bitget market fill；missing mark carry 3h |
| 成本 | 20 / 50 / 100bps；正常与 3x two-sided adverse funding |

## 0. 研究问题

LS85 的 200D 逐资产过滤太慢：只过滤 68 个事件，却把 LS57 从 58.21x 降到 30.78x。LS57 的利润
保护已经使用 21D 作为强趋势窗口；本 trial 不引入新窗口，而是把 21D 从“判断 leader 是否仍强”
扩展为逐腿退出：任何长仓 signals 日收盘低于自身 21D SMA，就在 T+1 转为现金，不重分配。

## 1. 冻结构造

```text
base_long = LS57 long targets
for each signal date D and long asset i:
  if close_i(D) < SMA21_i(D):
      target_i(D) = 0
  otherwise:
      target_i(D) unchanged
short_targets = LS57 short router unchanged
long_buffer = 0.60; target gross = 1.45x; hard cap = 1.50x
```

- 只使用 D 收盘及之前数据，T+1 +3h 执行。
- 不重分配，不改 profit-lock 参数，不改 short router/stop。
- MA 缺失时保留 leg 并记录；不填零或当作跌破。
- 不扫描 10/14/21/28/50D、部分减仓比例或 redistributing。

## 2. 预注册判定

1. 20bps full multiple >= LS57 60%/1.45x baseline，Sharpe >= baseline，MDD 至少改善 2pp；
2. validation multiple/Sharpe 不低于 baseline；
3. 50bps 和 100bps 不出现收益/Sharpe 反转；
4. 3x two-sided adverse 下 0 强平、0 gross breach；
5. 过滤不能依赖单一资产或单一年份；报告 filtered weight 和资产贡献；
6. 若只是降风险但收益明显下降，标记 risk-only rejected。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls85_asset_trend_filter.py \
  --warmup-start 2021-01-01 --start-date 2022-01-01 --end-date 2026-09-21 \
  --ma-days 21 --long-buffer 0.60 --target-gross 1.45 \
  --costs-bps 20,50,100 --funding-scenarios normal \
  --output-dir reports/ls89_asset_ma21_exit_2026
```
