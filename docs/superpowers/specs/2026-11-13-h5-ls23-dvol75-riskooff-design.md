# Atlas20 候选：DVOL 高波动状态下的 H5 多头风险关闭

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；等待主样本评估；不接实盘 |
| 候选 ID | `PR2026-11-LS58-H5-LS23-DVOL75-RISKOFF` |
| 基线 | `PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE` |
| 机制 | 当信号日的 Deribit BTC DVOL 日收盘 > 75 时，把 H5 多头目标缩放到 0；LS57 的空头 router、利润保护、止损、T+1 和 gross 规则不变 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip；Deribit BTC DVOL 日线 |
| 交易 | T+1 UTC +3h；missing mark carry 3h；20% short stop；hard total gross 1.50x |

## 0. 研究问题

LS57 的收益和回撤仍高度集中在少数高波动阶段。项目此前的日频量能、小时线状态和 funding
筛查都无法区分“好月份”和“崩溃月份”。Deribit DVOL 是未使用过的**期权隐含波动率**读数，
不是现货价格或资金费率的线性变体。

先做了一个**非正式诊断**：2022-2026 日频中，DVOL 水平与 LS57 未来 20 日收益的 Spearman
相关为约 -0.28，而 BTC 自身的未来 20 日相关约为 -0.06。绝对阈值 75 的粗略日收益缩放
诊断改善了终值和 Sharpe，且没有恶化样本内 MDD。这个诊断已经看过结果，因此 LS58 是
**post-hoc follow-up**，不是独立样本外发现，也不能单独作为 promotion 证据。

## 1. 规则

```text
对每个 H5 target signal date D：
    dvol_D = Deribit BTC DVOL 日线在 D 的 close
    如果 dvol_D > 75:
        H5 long target weights = 0
    否则:
        H5 long target weights 保持 LS57 原值
    LS57 的短头、利润保护、20% short stop、gross cap 和 T+1 +3h 全部不变
```

- 使用 D 的已完成日线 close；D+1 01:05 UTC 才发布/执行目标，不使用未来数据。
- DVOL 缺失、非有限或时间索引不能严格对齐时 fail closed，不做“缺失=关闭”。
- 只关闭多头；不把释放的 gross 加杠杆或转去空头。
- 不扫描 70/75/80/90、半仓/全仓、MA 或确认天数；75 是全仓阈值，0 是全退。

## 2. 验收标准

1. 20bps 终值 > LS57 的 68.8077x，Sharpe > 1.9819，MDD 不差于 -40.84%；
2. 2/20/50/100bps 终值和 Sharpe 均不低于同成本 LS57；
3. 100bps 终值 > 17.1724x、MDD <= 50%，0 强平、0 gross breach；
4. 3x short-adverse funding 下 0 强平、MDD <= 50%；
5. 删除任一最佳年份后终值仍高于同删除年份 L125；
6. 365D rolling worst >= LS57 的 0.8551x；
7. 45 个月初路径全部通过终值、Sharpe 和 MDD 5pp（相对 L125）；
8. 12 个真实 cash-start 至少 10/12 终值和 Sharpe 胜 L125，12/12 MDD 5pp；
9. 单资产空头贡献 <=50%，前 3 <=80%；
10. 报告 DVOL 触发的事件数、触发日 LS57 收益和触发后恢复的换手；
11. 至少 12 个月独立 OOS 才可谈 live promotion；当前 51 天窗口只记录，不足以证明
    DVOL 阈值在样本外稳定。

不因 LS58 的样本内结果好而降低 PBO、独立 OOS 或任何已声明风险标准；如果失败，登记为
rejected，不继续调 DVOL 阈值。

## 3. 复现

```bash
.venv/bin/python scripts/download_deribit_dvol.py \
  --start 2021-03-24 --end 2026-11-12 \
  --output data/raw/deribit_dvol/BTC_DVOL_1D.csv

.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS58-H5-LS23-DVOL75-RISKOFF \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_dvol75_riskooff
```

研究输出不是订单，也不是实盘批准。
