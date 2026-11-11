# Atlas20 候选 LS21：H5 positive-carry 熊市空头

日期：2026-11-12  
候选：`PR2026-11-LS21-H5-POSITIVE-CARRY-SHORT`  
状态：**rejected（研究失败）**  
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS21 只把 LS12 的熊市 weak-four funding 门槛从 `mean funding > -0.0002` 收紧为
`mean funding > 0`。20bps 仍明显高于 L125，但 100bps 同时失败终值、Sharpe 和 50% MDD kill line：

| 成本 | L125 终值 | LS21 终值 | L125 Sharpe | LS21 Sharpe | L125 MDD | LS21 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | **67.8290x** | 1.8249 | **1.9334** | -38.42% | **-38.37%** |
| 20bps | 40.2200x | **49.7281x** | 1.7330 | **1.8102** | -40.65% | -40.64% |
| 50bps | 27.3725x | **29.6103x** | 1.5790 | **1.6039** | -44.20% | -44.25% |
| 100bps | 14.3794x | 12.4408x | 1.3204 | 1.2579 | -50.02% | **-50.10%** |

主样本 0 强平、0 gross breach；20bps 最大观测 gross 1.3308x。20bps 累计费用
2.7027，低于 LS12 的 2.7745；但空头 open 从 LS12 的 335 增至 **367**，stop 从 29 增至 **37**。
说明“只做正 funding”降低了部分 funding 成本，却没有降低空头换手。

## 二、预注册与实现

- Spec：`docs/superpowers/specs/2026-11-12-h5-positive-carry-short-design.md`
- spec hash：`07a4dee05aced8ba54cdf172a8a04386ccff48df15ebd699eacbe5185887edcb`
- registration hash：`34686b03399835bc8d9907b33604015f8b24649065dead24588da36851952d2e`
- 运行前审计：`reports/derivatives_track_h5_regime_short_router/bear_funding_sign_audit/`
- 唯一规则变化：熊市 weak-four 候选必须满足最近 3 个 settlement 的 mean funding 严格大于 0；
  非熊市 funding-exit sleeve、H5 多头、stop、buffer、route 和 gross cap 全部不变。

## 三、失败项

1. 100bps 终值低于 L125；
2. 100bps Sharpe 低于 L125；
3. 100bps MDD -50.10%，越过 50% kill line；
4. 20bps 终值低于 LS12（49.7281x vs 55.7859x），没有保留原机制的全部 alpha。

按预注册停止：

- 不继续 3x funding stress；
- 不跑删除年份、365 天滚动最差、45 个路径切片、12 个引擎冷启动；
- 不执行 PBO/RC/DSR；
- 不扫描 funding 阈值、settlement 数、lookback、basket size、weight、stop 或 regime 窗口；
- “positive-carry 熊市空头”阈值族停止。

## 四、复现

```bash
# 20bps
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS21-H5-POSITIVE-CARRY-SHORT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_positive_carry_short

# 2/50/100bps 分别使用同参数和
# reports/derivatives_track_h5_positive_carry_short_cost{2,50,100}
```

完整输出：

- `reports/derivatives_track_h5_positive_carry_short/PR2026-11-LS21-H5-POSITIVE-CARRY-SHORT/`
- `reports/derivatives_track_h5_positive_carry_short_cost2/PR2026-11-LS21-H5-POSITIVE-CARRY-SHORT/`
- `reports/derivatives_track_h5_positive_carry_short_cost50/PR2026-11-LS21-H5-POSITIVE-CARRY-SHORT/`
- `reports/derivatives_track_h5_positive_carry_short_cost100/PR2026-11-LS21-H5-POSITIVE-CARRY-SHORT/`

## 五、最终判定

**LS21 rejected。** 正 funding 是合理的经济条件，但它不是成本问题的解；LS12 的高换手空头
在 100bps 下仍无法生存。继续研究必须改变空头信息源或收益结构，不能继续调 funding 阈值。
