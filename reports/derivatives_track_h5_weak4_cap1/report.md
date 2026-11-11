# Atlas20 无杠杆多空候选 LS7：H5 0.8x + Weak-Four 0.25x

日期：2026-11-11
候选：`PR2026-11-LS7-H5-WEAK4-CAP1`
状态：**rejected（研究失败）**
实盘：**不接；H5 现有多头配置不变**

## 一、结论

LS7 是资本重分配机制：

- H5 多头从 1.0x 降到 0.8x；
- weak-four 空头总 0.25x，每腿 6.25% NAV；
- 多空两边先按 total gross 计，target 0.95、hard observed 1.00；
- 无 leverage。

20bps 正式结果：

- H5 基线：**21.3487x / Sharpe 1.7361 / MDD -33.36%**
- LS7：**13.4246x / Sharpe 1.8164 / MDD -29.71%**
- 最大 observed gross：**1.000559x**
- gross breach：**1 小时**
- 强平：0

LS7 提高了 Sharpe、改善了 MDD，但终值比 H5 低 **37.1%**，且 observed gross 越过硬上限。按预注册直接 rejected。

## 二、预注册

- Spec：`docs/superpowers/specs/2026-11-11-h5-weak4-cap1-design.md`
- registered spec hash：`1d7fae9694f83d31060ae1e8bec69dcee88235a89fba2e4ac9c02aa3fc2ab44d`
- registration hash：`35f6bf3ba397b3b5a11abecf7dd8ed4171045badf7e3010765577937f6b503fb`

## 三、成本压力

| 成本 | H5 终值 | LS7 终值 | H5 Sharpe | LS7 Sharpe | H5 MDD | LS7 MDD | LS7 gross breach hours |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 25.6692x | 18.0828x | 1.8277 | **2.0048** | -31.41% | **-27.12%** | 1 |
| 20bps | 21.3487x | 13.4246x | 1.7361 | **1.8164** | -33.36% | **-29.71%** | 1 |
| 50bps | 15.6946x | 8.1608x | 1.5826 | 1.5005 | -36.59% | **-33.84%** | 2 |
| 100bps | 9.3848x | 3.5300x | 1.3251 | 0.9652 | -41.92% | -40.59% | 2 |

只有 2bps 和 20bps Sharpe 高于基线；所有成本终值都低于 H5，50/100bps Sharpe 也低于基线。gross hard cap 在所有成本档都被 drift 越过。

## 四、funding 压力

3x short-adverse：

- 终值 12.0207x；
- Sharpe 1.7448；
- MDD -30.33%；
- 0 强平；
- observed gross 1.000259x，1 个 breach hour。

gross 仍失败。

## 五、年度、最佳年份和滚动

| 年份 | H5 基线 | LS7 |
|---|---:|---:|
| 2022 | -15.74% | **+22.62%** |
| 2023 | **+201.14%** | +105.66% |
| 2024 | **+94.61%** | +43.08% |
| 2025 | +112.35% | +105.66% |
| 2026 | **+103.60%** | +80.92% |

LS7 在 2022 很好，但牺牲了 2023、2024、2026 的大部分复利。

删除最佳年份后，LS7 在 2022/2024/2026 删除场景均低于基线；例如删除 2022 后 10.9480x vs 基线 25.3369x。

365 天滚动最差：LS7 **0.8562x**，高于基线 0.7970x。该项通过，但不足以抵消收益和 gross 失败。

## 六、多重检验

| 项目 | 结果 | 判定 |
|---|---:|---|
| PBO / CSCV | **0.5844** | 失败（>0.50） |
| RC vs zero | p=0.003996 | 通过 |
| DSR family N=2 | 0.999995 | 仅 family 通过 |
| DSR Top20/2022 N=6,142 | **0.941000** | 失败 |
| DSR 全项目 N=14,177 | **0.919443** | 失败 |

## 七、执行偏差

LS7 在 20bps 主口径已经同时失败终值、gross 和 PBO；因此没有继续执行 12 个真实引擎冷启动和 episode 归因。该执行偏差明确记录，不计为通过。

## 八、最终判定

**LS7 rejected。**

否决理由：

- 20bps 13.4246x < H5 21.3487x；
- 2/20/50/100bps 终值全部低于 H5；
- observed gross 最高 1.000559x，hard cap 失败；
- PBO 0.5844；
- Top20/2022 DSR 0.9410、全项目 DSR 0.9194；
- 删除多个最佳年份后低于基线。

按预注册，不得扫描 H5 0.5–0.9、short 0.10–0.30、lookback、币数、周频、stop 或 gross。LS7 不接执行器，H5 实盘不变。

## 九、复现

```bash
.venv/bin/python scripts/run_h5_weak4_cap1.py --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_weak4_cap1

.venv/bin/python scripts/run_h5_weak4_cap1.py --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_weak4_cap1
```
