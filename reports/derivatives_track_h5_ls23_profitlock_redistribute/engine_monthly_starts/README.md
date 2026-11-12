# LS42 Engine Monthly Starts

12 个真实 cash-start 引擎起点用于检验冻结 LS42 的路径稳定性。每个 start 的 candidate
`summary.json` 来自同一 runner 的 `--evaluation-start YYYY-MM-01` 运行；baseline metrics 复用
LS23 同一组 12 个起点的已归档真实 L125 结果，并写入各 start 的
`baseline/archived_l125_engine_summary/summary.json`，避免重复运行相同基线。

门禁：至少 10/12 终值和 Sharpe 胜过 L125、12/12 MDD 在 5pp 容差内、0 强平、max observed gross
<=1.50x、0 gross breach hours。汇总文件为 `summary.csv`、`summary.json`、`report.md`。

完整 per-start 交易账本可由此 runner 重跑；为控制仓库体积，当前只保留 summary 证据。
