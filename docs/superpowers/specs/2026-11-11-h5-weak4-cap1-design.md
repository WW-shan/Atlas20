# Atlas20 无杠杆多空候选预注册：H5 0.8x + Weak-Four 0.25x 总 gross 1.0

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘，不改 H5 多头账本 |
| 候选 ID | `PR2026-11-LS7-H5-WEAK4-CAP1` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 多头 | 冻结 H5 `PR2026-10-H5` × 0.8 |
| 空头 | PIT Top20 14D 最弱 4 币，总 0.25x，每腿 6.25% NAV |
| 空头 stop | 20% adverse mark |
| 再平衡 | 7 个日历日 |
| target total gross | 0.95x |
| hard observed gross | 1.00x |
| 执行 | T+1 UTC +3h |
| 数据 | 严格 point-in-time CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS5 把 weak4 当作 overlay，每腿只有 2.5% NAV，weak4 sleeve 净贡献 -2.662%，并产生大量
周频重定权换手。R6 使用更大 weak4 空头（总 0.25x）时 Sharpe 较高，但 H5 用 1.25x，
导致杠杆、observed gross 1.54x 和 100bps 失败。

本轮不是继续调 LS5 或 R6 参数，而是改变资本结构：

> H5 多头从 1.0x 降到 0.8x，释放 0.2x 资本；weak4 空头用 0.25x；多空合计按
> target gross 0.95、hard gross 1.00 缩放。无杠杆，净敞口通常低于 1.0。

该机制把 weak4 从“额外 overlay”改成“与多头竞争同一 gross 预算的 sleeve”。

## 1. 预注册前证据

R6 20bps：51.8010x / Sharpe 1.8918 / MDD -42.59%，但 H5 1.25x + short 0.25x、
observed gross 1.54x、100bps MDD -54.06%，不满足无杠杆要求。

只读近似把 R6 的多头部分缩放到 0.8，同时保持同一 short overlay：

| 指标 | H5 1.0x 基线 | 近似 0.8x H5 + R6 overlay |
|---|---:|---:|
| 终值 | 21.3487x | 约 24.743x |
| Sharpe | 1.7361 | 约 1.8847 |
| MDD | -33.36% | 约 -36.37% |
| 365 天滚动最差 | 0.7970x | 约 0.8421x |
| 最大 gross | 0.9568x | <=1.00 设计约束 |

该近似不是正式回测，只用于决定预注册一个新的无杠杆资本结构。

## 2. 冻结构造

### 2.1 H5 多头

- H5 冻结目标乘数 **0.8**；
- 不允许超过 0.8；
- 不重分配 H5 到其他多头资产。

### 2.2 Weak-four 空头

- 完整 UTC 日线；
- 7 日再平衡网格，以样本起点为 anchor；
- 当日 PIT Top20；
- 排除当前 H5 多头持仓；
- 要求 Bitget execution mark 可用；
- 最近 3 个 Binance funding settlement 均值 > -0.0002，沿用 R6；
- 14D trailing return 最弱 4 个；
- 每个 6.25% NAV，总 request short 0.25x；
- 持有到下次周再平衡或 20% adverse stop；
- stop 后在下一周再平衡前不重开。

### 2.3 总 gross

使用 `combine_sleeve_targets_by_total_gross_with_audit`：

```text
raw_long = 0.8 * H5
raw_short = 0.25 * weak-four basket
if raw_long_gross + raw_short_gross > 0.95:
    both sleeves scale proportionally
```

- target total gross 0.95；
- hard observed gross 1.00；
- observed breach 后下一小时减仓到 0.95；
- 不允许 leverage。

### 2.4 风险与执行

- long buffer 0.75；
- short buffer 0.50；
- 20% adverse mark stop；
- T+1 UTC +3h；
- missing mark carry 最多 3 小时；
- funding 主口径 Binance proxy/skip；
- 另跑 3x short-adverse。

## 3. 评估门槛

### 3.1 主口径

1. 20bps 终值严格高于 H5 1.0x 基线；
2. 20bps Sharpe 严格高于 H5 基线；
3. MDD 不差于基线 5pp；
4. 0 次强平；
5. max target total gross <= 0.95；
6. max observed gross <= 1.00；
7. 所有 stop、funding、费用和 gross guard 成交计入。

### 3.2 成本

- 2/20/50/100bps 全部重跑；
- 50bps 和 100bps 终值均高于同成本 H5 基线；
- 四档 Sharpe 均高于同成本基线；
- 100bps MDD <= 50%；
- 四档 observed gross <= 1.00。

### 3.3 funding 与尾部

- 3x short-adverse funding 下 0 强平且 MDD <= 50%；
- 实际最大 adverse short mark loss 超过名义 20% × 6.25% = 1.25% NAV 时必须披露；
- 报告每个资产 episode PnL 和最大 adverse excursion。

### 3.4 日历、起点和集中度

- 分年收益；
- 删除最佳年份后仍高于基线；
- 365 天滚动最差不低于基线；
- 12 个真实月初引擎启动：
  - 终值胜过基线 >= 8/12；
  - Sharpe 胜过基线 >= 8/12；
  - MDD 5pp 12/12；
- 单资产空头贡献 <= 50%；
- 前 3 资产空头贡献 <= 80%。

### 3.5 多重检验

- PBO/CSCV <= 0.50；
- White Reality Check p <= 0.05；
- Top20/2022 和全项目 DSR >= 0.95。

### 3.6 样本外

- 2026-09-22 后为真 OOS；
- 不足 12 个月 OOS 时最高 provisional；
- 无 Bitget 精确 funding、isolated margin、ADL 审查，禁止接实盘。

## 4. 失败后动作

- 不扫描 H5 乘数 0.5/0.6/0.7/0.75/0.85/0.9；
- 不扫描 short 总权重 0.10/0.15/0.20/0.30；
- 不扫描 weak lookback 7/14/28/30/60D；
- 不扫描 2/3/4/5/8 币；
- 不扫描周频；
- 不扫描 stop、buffer、funding filter 或 gross cap；
- 失败后必须换机制并重新预注册。

## 5. 复现接口

```bash
.venv/bin/python scripts/run_h5_weak4_cap1.py --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_weak4_cap1

.venv/bin/python scripts/run_h5_weak4_cap1.py --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_weak4_cap1
```

## 6. 状态

- research only；
- no live changes；
- no leverage；
- no post-result parameter scan。
