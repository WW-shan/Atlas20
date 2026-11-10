# Atlas20 双边轮动第七轮预注册：Bottom-8 持有带降低空头换手

| 项目 | 内容 |
|---|---|
| 状态 | 研究预注册；不接实盘，不改 H5 多头账本 |
| 触发 | R6 的 100bps 成本失败，空头止损 50 次，费用约为 L125 基线的 2 倍 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 多头底稿 | 冻结 H5 / `PR2026-10-D-L125`，严格 point-in-time CMC Top20 |
| 空头 | Top20 中按 14D 收益排序的 bottom-quintile 4 币，等权，总 0.25x |
| 持有带 | 已有空头只要仍在可投资候选的 bottom-8（bottom 40%）内就保留，否则退出 |
| 成本 | 20bps 主口径；50/100bps 压力 |
| 数据 | Bitget mark；Binance funding proxy/skip，明确不是 Bitget 精确历史 |

## 0. 研究问题与外部依据

R6 已证明 bottom-quintile 空头加 20% 单腿止损可以消除强平并提高 20/50bps 收益，但：

- 100bps 终值只有 10.3786x、MDD -54.06%，低于 L125 基线的 14.3794x / -50.02%；
- 50 次止损和每周完整重排使费用总额约为 L125 的 2 倍；
- 移除 2022 后低于基线，说明现版本没有通过预注册门槛。

本轮只检验一个成本机制，不继续扫描 stop、margin buffer、篮子大小或 lookback：

> 用“宽进严出”的持有带减少空头换手，能否保留相对价值收益，同时把 100bps 成本和回撤拉回门槛内？

外部依据是 Novy-Marx & Velikov (2016, [S36])：买入/持有带（开仓条件比继续持有条件更严格）是文献中最有效的交易成本缓释技术之一；低换手异常在设计成本缓释后更可能保留净收益。项目 H5 多头也采用 `Top1 entry / Top2 hold` 的同类结构。原文不支持一个具体带宽，因此本轮不扫描 6/8/10 等相邻值，只使用预先定义的 **2 倍持有带**：进入 bottom-4，持有至跌出 bottom-8。

## 1. 唯一冻结试验

| trial_id | 构造 | 空头总权重 | 开仓 | 持有 | stop |
|---|---|---:|---|---|---:|
| `PR2026-11-RS7-X-WEAK4-HOLD8-STOP20` | H5 ×1.25 + bottom-quintile 空头 | 0.25x | 14D 最弱 4 个可投资 Top20 | 仍在最弱 8 个则保留 | 20% adverse |

只跑这一条。不能同时扫 hold rank 6/8/10、4/8/12 周周期、stop 15/25/30 或不同空头权重。

## 2. 精确规则

### 2.1 多头与执行

H5 的选币、3 日相位、Top2 hold band、BTC 100D gate、dispersion overlay 不变，
`w_long = 1.25 × w_H5`。H5 事件之间前向填充权重；不加入 Top20 外资产。

### 2.2 空头候选与持有带

每个第 7 个自然日的 UTC 收盘：

```text
base_t     = PIT_CMC_Top20_t
              ∩ Bitget mark available at t+1 execution
              ∩ funding guard passes
              − current H5 long holdings
ranked_t   = ascending 14D return over base_t
entry_t    = ranked_t[0:4]
hold_set_t = ranked_t[0:8]
```

选择顺序：

1. 已有空头若仍在 `hold_set_t`，保留；
2. 空位按 `ranked_t` 从弱到强补足至 4 个；
3. 已跌出 `hold_set_t`、离开 Top20、成为 H5 多头、mark 不可用或 funding guard 失败的旧空头退出；
4. 若不足 4 个可投资候选，按实际数量等权，总空头仍不超过 0.25x，不把缺失腿转移到其他币；
5. 空头为负权重；H5 同时持有该币时自动退出/不建立空头。

持有带只改变空头组合的换手，不改变 14D 排序、bottom-quintile 定义或 20% 单腿止损。

### 2.3 空头止损与 funding

- 保持 R6 的原始预注册 20% adverse mark stop，逐小时检查；
- 触发后该腿变现金；只有下一次实际目标变更才会按当时目标执行，不为它单独制造再入场；
- short margin buffer 固定 0.50；
- 主研究使用 Binance funding proxy + `skip`；3x short-adverse 是压力带，不是精确费用；
- 强平由引擎逐小时 mark 检查。

## 3. 预注册门槛

主口径为 20bps、Bitget mark、T+1 +3h、missing mark carry≤3h：

1. 终值严格高于同口径 L125 基线；
2. Sharpe 不低于基线；
3. MDD 不差于基线 + 5pp；
4. 主样本 0 次强平；
5. 50bps 终值仍高于同成本 L125 基线；
6. 100bps MDD ≤ 50%；
7. 3x short-adverse funding 0 次强平且 MDD ≤50%；
8. 移除 2022 后仍高于基线；
9. 365 天滚动最差不低于基线；
10. 基线 + R6 + R7 的 PBO/CSCV ≤0.5；
11. 报告空头开仓/止损次数、费用、逐区间贡献、年度收益和最佳年份移除；
12. 真 OOS 不足 12 个月时最多 provisional，禁止接实盘。

任何一项失败即拒绝；不能事后改门槛或继续扫相邻持有带宽度。

## 4. 试验记账

新增 `PR2026-11-RS7-X-WEAK4-HOLD8-STOP20` 到
`reports/research_trial_inventory/preregistered_trials.csv`，`counts_as_trial=True`。
决策族至少包含 L125、R6 和 R7，不能只报告 R7。

## 5. 复现

```bash
.venv/bin/python scripts/run_derivatives_backtest.py \
  --trial-id PR2026-11-RS7-X-WEAK4-HOLD8-STOP20 \
  --start-date 2022-01-01 --end-date 2026-09-21 \
  --cost-bps 20 --short-buffer 0.50 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_cross_sectional_basket_round7
```

## 6. 边界

- 不修改当前 H5 多头实盘账本；
- 不进入 `ops/run_derivatives_daily.sh`；
- 不把持有带造成的低换手当成 alpha 证据；
- 若 R7 仍失败，bottom-quintile 空头线停止继续扫参；只能补 Bitget 精确 funding、累积真实 OOS，或转向预注册的独立实时风险规则。

---

## 7. 第七轮结果（2026-11-10）

`PR2026-11-RS7-X-WEAK4-HOLD8-STOP20` 在 20bps 为 **43.2909x / Sharpe 1.8266 /
MDD -42.3961% / 0 强平 / 73 次止损**，高于 L125 基线；费用总额从 R6 的 3.1904 降到
2.5646，持有带确实降低了换手成本。

但：

- 50bps 为 24.6027x，低于基线 27.3725x；
- 100bps 为 9.5638x / MDD **-53.6419%**，失败；
- 3x short-adverse funding 为 40.6830x / MDD -42.8806% / 0 强平，通过；
- 移除 2022 后为 41.7015x，低于基线 50.0330x；
- 365 天滚动最差为 0.7048x，低于基线 0.7325x；
- L125 + R6 + R7 的 PBO/CSCV 为 0.2576，通过。

判定：**rejected。** 持有带不是足够的成本修复，且保留弱币导致止损次数从 50 升至 73。
按预注册停止，不再扫 hold rank 或该空头族的其他参数。完整报告：
`reports/derivatives_track_cross_sectional_basket_round7/report.md`。
