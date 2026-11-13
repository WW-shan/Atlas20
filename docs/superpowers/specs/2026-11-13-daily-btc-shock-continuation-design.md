# Atlas20 研究预注册：daily BTC shock relative continuation

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 候选族 ID | `PR2026-11-LS69-DAILY-BTC-SHOCK-CONTINUATION` |
| 来源 | LS68 的反向描述性观察：日频 relative gap 更像 continuation，而不是 reversal |
| 状态 | 组合级因子回测；不连接实盘、不修改 live target |
| 数据 | strict PIT CMC Top20，`data/processed/panel_daily.csv` |
| 评估窗口 | 2021-01-01 → 2026-11-12 |
| Discovery | 2022-01-01 → 2023-12-31 |
| Validation | 2024-01-01 → 2026-11-12 |
| Independent OOS | 2021-01-01 → 2021-12-31（LS68 未使用；只用于冻结候选后检验） |
| 基准 | BTC buy-and-hold；LS57 20bps 日收益仅作 overlay 参考 |
| 成本 | 2 / 20 / 50 / 100bps 每边；初步筛查不扣 funding，后续必须补 |

## 0. 研究问题与防止重复挑参

LS68 的预注册反转假设失败，但 96 个 discovery cell 的 contrarian spread 全部为负；这不是可用结论，
只能产生一个新假设：**BTC shock 后，相对 BTC beta 更强的 Top20 alt 在接下来数日继续跑赢，弱的继续跑输。**

本族把这个方向单独注册，不再使用 LS68 的 validation 结果选参数。参数只按 discovery 指标排序；
2024–2026 与 2021 的结果只用于检验，不允许回头改网格。所有 96 个 cell 都要记录，不能只保存赢家。

## 1. 冻结信号

对每个 signal day `t`、形成窗口 `k`：

```text
btc_shock_k(t) = log(close_btc(t) / close_btc(t-k))
beta_i(t)      = 120D rolling BTC beta, min 90 observations, clip [0, 4]
gap_i,k(t)     = log(close_i(t) / close_i(t-k)) - beta_i(t) * btc_shock_k(t)
z_k(t)         = btc_shock_k(t) / rolling_120D_std(btc_shock_k(t))
```

长腿为 gap 最高的一组，短腿为 gap 最低的一组；两腿等美元名义，形成 gross 1.0 的
dollar-neutral book。与 LS68 的 reversal 方向相反，这是本族唯一的方向。

冻结网格：

- `k ∈ {1, 3, 5, 10}` 日；
- `h ∈ {1, 3, 5, 10}` 日；
- shock gate：`all`、`|z| >= 2.0`、`|z| >= 2.5`；
- 每腿 tail：10% 与 20%；
- 每个横截面至少 8 个 PIT Top20 合格资产；
- 共 `4 × 4 × 3 × 2 = 96` 个 cell。

## 2. 执行与 phase 处理

信号在 `t` 日 close 后产生，最早在下一个 close（`t+1`）执行，不能使用同日收盘成交。
每个 `h` 的 **所有 h 个 phase** 都进入组合：每个 phase 在固定的 `t, t+h, t+2h, ...` 日更新，
每次只分配 `1/h` 的组合 gross。这样平均持有 h 日，但不会把同一 shock 叠加成 h 倍 gross，
也不需要用 validation 选一个幸运 phase。

每个 tranche 的目标 gross 为 1.0；所有 phase 合计 gross 不超过 1.0。每个 cell 都按
2/20/50/100bps 每边扣除 turnover 成本，权重在 next-close 后生效。缺失收益逐日计数并在报告中披露；
若持有资产缺价，本筛查按 0 贡献处理只能作为诊断，不能当作执行级回测。

## 3. Discovery 选择规则

只在 discovery 上选一个 cell：

1. discovery 20bps Sharpe > 0；
2. discovery 50bps Sharpe > 0；
3. 按 discovery 20bps Sharpe 从高到低选第一个；完全并列时按更低的 turn-over 选；
4. 若没有 cell 满足，LS69 本族直接 rejected，不进入 validation 或 overlay 展示性择优。

不使用 validation、pre-2022 或 LS57 overlay 结果改变规则或参数。

## 4. 验收标准（先于运行冻结）

相对于 BTC 和 LS57，研究者当前的目标是“收益明显提高，回撤不要大幅恶化”。因此冻结如下门槛：

- validation 20bps Sharpe > 0 且 50bps Sharpe > 0；
- independent OOS 2021 的 20bps Sharpe > 0 且 50bps Sharpe > 0；
- full 20bps 终值高于 BTC buy-and-hold；
- full 20bps MDD 不差于 -50%；
- full 20bps Sharpe > 0.5；
- 月度/年度收益不能由一个资产或一个短窗口完全主导；报告至少列出资产贡献和逐年收益；
- return-space overlay（LS57 20bps + 10%/20% sleeve）只作展示，不单独构成 promotion。

全部通过才可进入 funding、Bitget mark/fill、gross 和 live integration 的第二阶段。任一项失败则
冻结这个 LS69 family，不通过扫邻近 `k/h`、换 tail 或改 phase 来救结果；可以另起新的预注册假设。

## 5. 复现

计划命令：

```bash
.venv/bin/python scripts/run_daily_btc_shock_continuation.py \
  --start-date 2021-01-01 \
  --end-date 2026-11-12 \
  --output-dir reports/daily_btc_shock_continuation_2026
```

输出必须包含全部 96 个 cell 的 `trial_summary.csv`、各 cell 的日收益、discovery-selected
book 的权重/资产贡献/年度表、BTC/LS57 对照和 manifest。该文件是预注册记录，运行后不得改门槛。
