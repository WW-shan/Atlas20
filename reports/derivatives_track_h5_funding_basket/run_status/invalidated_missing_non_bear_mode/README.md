# Invalidated LS17 run

首轮运行没有把 `non_bear_mode=high_funding` 传给 `build_regime_short_schedules`，因此输出与 LS12 完全相同。
这是实现调用错误，不是 LS17 结果。输出与日志保留在此处，不进入判定；修复后的正式运行重新生成
`reports/derivatives_track_h5_funding_basket/PR2026-11-LS17-H5-FUNDING-BASKET/`。
