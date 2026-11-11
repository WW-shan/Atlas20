# LS24 预注册勘误：跨所 funding 覆盖率审计时点修正

日期：2026-11-12
原预注册：`docs/superpowers/specs/2026-11-12-h5-cross-venue-funding-short-design.md`
原 registration hash：`a933acdcb585464733d338f82bcd98e4d47d045553933d9c2f456ae71de1c978`

## 修正内容

原审计把 episode 的**执行日**当成 funding 观测日，并在同日 `normalize()` 后把 08:00/16:00
settlement 也纳入，造成最多两个 settlement 的前视。正确口径是：

- 信号日 = 执行日（entry_time）的 UTC 日期减 1 天；
- 只使用信号日 00:00 UTC 及之前的 settlement；
- 同一 settlement 的毫秒时间戳先 floor 到分钟，避免 Binance/Bybit 时间戳抖动；
- 不足 3 个 settlement 时视为不可用，不填充。

该修正只改审计时点，不改变 LS24 的策略规则、阈值、lookback、数据源或预注册 hash。

## 修正后的覆盖

| 口径 | 修正前（错误） | 修正后 |
|---|---:|---:|
| 总 episodes | 335 | 335 |
| Bybit 可用 | 311 / 335 (92.8%) | **307 / 335 (91.6%)** |
| bear episodes | 288 | **297** |
| bear Bybit 可用 | 265 | **270** |
| bear 两所同时为正 | 138 | **138** |
| non-bear episodes | 47 | **38** |
| non-bear Bybit 可用 | 46 | **37** |
| non-bear 两所同时为正 | 39 | **34** |

覆盖率仍高于预注册的 90% 门槛，因此 LS24 可以进入正式回测；但原 spec 中的 92.8%/288/47
数字应视为已被本勘误取代。规则本身没有改变。

## 审计文件

- `reports/derivatives_track_cross_venue_funding_audit/`
- `reports/derivatives_track_h5_regime_short_router/bear_funding_sign_audit/`
- `scripts/audit_cross_venue_funding.py`
- `scripts/audit_h5_bear_funding_sign.py`
