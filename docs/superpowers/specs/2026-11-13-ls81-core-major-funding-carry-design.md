# Atlas20 候选预注册：LS57 + core-major PIT funding carry

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；等待正式运行；研究输出不接实盘 |
| 候选 ID | `PR2026-11-LS81-LS57-CORE8-FUNDING-CARRY` |
| 基线 | `PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE` |
| 主窗口 | 2022-01-01 → 2026-09-20（UTC，warmup 从 2021-01-01 开始） |
| 基础策略 | 冻结 LS57：H5 1.25x + LS23 profit-lock + BTC-regime short router |
| Sleeve | core-major 8 币 funding carry；主组固定为 core8，extended10 仅作预注册敏感性 |
| 总 gross | 1.50x hard cap；sleeve 只使用 base book 的剩余 gross |
| 执行 | T+1 UTC +3h；Bitget mark 做标记/强平，Bitget market candle 做成交；缺失 mark carry 最多 3h |

## 0. 研究问题

LS57 的收益主要来自 H5 多头和 BTC regime short router。此前的 LS30–LS37 已经测试过
PIT Top20 的 funding carry sleeve，但那些试验把 carry 放在 H5 1.25x 的固定 gross 上，
成本、long buffer 和 sleeve 组合方式与当前 LS57 不同；LS57 的 profit-lock 会周期性释放
gross，因此可以检验一个更窄、更高流动性的 core-major sleeve 是否能在不增加 gross 上限的前提下
改善收益，而不是重复旧 Top20 carry 的参数扫描。

本 trial 只问一个问题：在 LS57 已释放的 residual gross 中，core8 funding carry 是否能在
严格 PIT、真实 Bitget mark/fill/funding/liquidation 下产生可重复的增量。

## 1. 冻结构造

```text
core8 = bitcoin, ethereum, solana, ripple, binancecoin, dogecoin, cardano, avalanche-2
extended10 = core8 + chainlink, polkadot  # sensitivity only

at weekly signal D:
  eligible = core8 assets with Bitget mark availability in prior 3 days
             and at least 3 Binance funding settlements in [D-7D, D)
  exclude any asset active in the LS57 base book at D
  require at least 6 eligible assets

score_i = mean(Binance funding settlements in [D-7D, D))
long  = two lowest scores, each +0.25x NAV before residual scaling
short = two highest scores, each -0.25x NAV before residual scaling
sleeve target gross = 1.00x before residual scaling

allocation ∈ {10%, 20%, 25%} NAV; scale sleeve first, then apply
combine_signed_book_with_residual_sleeve against the LS57 base and hard 1.50x.
```

- `D` 是信号日，funding 只用 `index < D` 的 settlement；当日 `D` settlement 不使用。
- funding 信号使用 Binance 8h funding；Bitget 历史 funding 不足以覆盖主窗口，因此这是
  cross-venue proxy，报告中必须明确标注。Bitget mark、market fill、funding accounting 和
  liquidation 则由真实 Bitget 数据/引擎处理。
- 不使用未来 universe、当前 market-cap 排名或事后币种白名单；core8 是预先固定的流动性主组。
- 不允许同一资产同时出现在 LS57 base 和 carry sleeve；若发生重叠，carry 腿在组合层剔除，
  不进行净额化。
- 不扫描 count、lookback、leg weight、rebalance 频率、min_assets 或 allocation 之外的参数。
- 20/50/100bps 作为成本带；正常 funding、two-sided adverse funding 和 3x adverse funding
  分别报告。任一风险失败都保留为失败记录，不通过改参数救结果。

## 2. 预注册验收

1. 25% allocation 的 20bps full multiple 和 Sharpe 都高于 LS57；MDD 不差于 LS57 的
   -39.8350% 减去 1pp；
2. 20bps validation（2024-01-01 → 2026-09-20）multiple 和 Sharpe 都高于 LS57；
3. 20bps 0 次强平、0 gross breach、observed gross <=1.50x；mark carry 记录完整且没有
   超过 3h 的 carry；
4. 50bps 和 100bps 的成本带必须报告，不能只看 20bps；如果收益优势在 50bps 消失，标记为
   成本敏感而非 promotion；
5. 3x adverse funding 下报告终值、Sharpe、MDD、强平和 funding 总计；
6. 2021 价格-only、365D rolling、逐年和 bootstrap/NW 结果至少作为稳健性证据报告；
7. 只有通过真实引擎和独立 OOS，且 owner 明确批准，才允许讨论 promotion。研究结果本身不
   修改当前 live default。

## 3. 失败后的动作

如果 core8 在 20bps full/validation 或风险门禁失败，记录为 rejected。允许继续研究新的独立
信息源或新的组合机制，但不通过调整 core8 名单、funding lookback、腿数、权重、allocation、
成本或止损来重新拟合同一结果。

## 4. 复现

```bash
.venv/bin/python scripts/run_ls81_core_major_funding_carry.py \
  --warmup-start 2021-01-01 --start-date 2022-01-01 --end-date 2026-09-21 \
  --costs-bps 20,50,100 --allocations 0.10,0.20,0.25 \
  --output-dir reports/ls81_core_major_funding_carry_2026
```

