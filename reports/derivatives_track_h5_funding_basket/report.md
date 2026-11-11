# Atlas20 候选 LS17：LS12 + 非熊市高 funding 拥挤空头 basket

日期：2026-11-12  
候选：`PR2026-11-LS17-H5-FUNDING-BASKET`  
状态：**rejected（gross 与成本失败）**  
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS17 用全 PIT Top20 的高正 funding 非 H5 资产替换 LS12 的非熊市 H5-exit sleeve。它确实降低了
funding 成本并改善了 20bps Sharpe/MDD，但换手和拥挤空头 stop 大幅增加：

- 20bps：**46.2349x / 1.8548 / -37.96% / 0 强平**；
- 但 max observed gross **1.5265x**，57 个 breach hours；
- short open 从 LS12 的 335 增至 **632**，short stop 从 29 增至 **83**；
- 50bps 终值 24.4102x < L125 27.3725x；
- 100bps 8.3872x / 1.1362 / -50.89%，终值、Sharpe 和 MDD 三关失败。

因此 LS17 不晋级。按预注册不扫描 funding lookback、basket size、min assets、正 funding 阈值、
频率、权重或 stop；high-funding basket 家族停止。

## 二、预注册

- Spec：`docs/superpowers/specs/2026-11-11-h5-funding-basket-design.md`
- spec hash：`023e1a4b2dd30f9cf03cd010d3f410fbcf80101b74cc9e37fe04b66491024e6f`
- registration hash：`8269fcc55330949440bf383eab7c74ebae52404901c091d658fcc17a37cdf619`
- registered at：`2026-11-11T16:14:50Z`

正式运行前审计：

- 247 个 weekly 日期中，PIT Top20 非 H5 可计算 funding 的资产最少 15、中位 18；
- positive-funding 中位 14；
- 243/247 周有至少 4 个正 funding 候选；
- LS12 原有 72 个非熊市 entry 中 67 个 funding 已经为正，单纯加“funding>0”过滤不构成有效差异。

## 三、冻结构造

```text
bear_t = BTC_close(t) < SMA200(BTC_close)(t)

if bear_t:
    short_t = LS12 weekly weak-four sleeve
else:
    short_t = top-four positive 7D funding PIT Top20 non-H5 assets
```

- non-bear sleeve 每 7 天评估；
- 排除当前 H5 多头；
- 7D mean funding 必须严格大于 0；
- 有效 funding 资产少于 5 个时 fail closed；
- 最多 4 腿，每腿 6.25% NAV，总 short <=0.25x；
- 20% adverse mark stop；
- long 1.25x、hard total gross 1.50x；
- T+1 UTC +3h；Binance funding proxy/skip。

## 四、成本结果

| 成本 | L125 终值 | LS17 终值 | L125 Sharpe | LS17 Sharpe | L125 MDD | LS17 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | **67.7748x** | 1.8249 | **2.0147** | -38.42% | **-34.88%** |
| 20bps | 40.2200x | **46.2349x** | 1.7330 | **1.8548** | -40.65% | **-37.96%** |
| 50bps | 27.3725x | 24.4102x | 1.5790 | 1.5867 | -44.20% | **-42.79%** |
| 100bps | 14.3794x | 8.3872x | 1.3204 | 1.1362 | -50.02% | -50.89% |

失败项：

- 50bps 终值低于基线；
- 100bps 终值、Sharpe 和 MDD 全部失败；
- 所有成本档 observed gross 超过 1.50x，breach hours 48–118；
- 20bps short stop 83 次，远超 LS12 的 29 次。

## 五、funding 与换手

| 指标 | LS12 20bps | LS17 20bps |
|---|---:|---:|
| funding total | -0.7238 | **-0.3044** |
| fees total | 2.7745 | 3.0720 |
| short opens | 335 | 632 |
| short stops | 29 | 83 |
| max observed gross | 1.3308x | 1.5265x |

高 funding 选币确实减少了 funding 支出，但收益不足以覆盖更高的交易成本和 stop 频率。

## 六、实现修正

首轮运行遗漏了 `non_bear_mode=high_funding` 参数，输出与 LS12 完全相同。该输出和日志已隔离在
`run_status/invalidated_missing_non_bear_mode/`，不进入判定。新增回归测试后重新正式运行，结果
与 LS12 不再相同。

## 七、未继续执行的阶段

LS17 已触发 gross hard fail 和 50/100bps 失败，因此按预注册：

- 不运行 3x funding stress；
- 不运行 remove-best-year、滚动、45 路径、12 冷启动或 PBO/RC/DSR；
- 不扫描 funding lookback、threshold、basket size、min assets、frequency、weights 或 stop；
- 不接入执行器或修改实盘。

## 八、最终判定

**LS17 rejected。**

高 funding 拥挤能降低 funding 成本并改善 20bps 风险指标，但不能通过 gross、50bps 和 100bps。
当前 `PR2026-10-D-L125-V2` 保持不变。
