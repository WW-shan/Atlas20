# Dispersion overlay screening

Book `PR2026-10-H3` at 20 bps, 2022-01-01 .. 2026-09-21. Dispersion = trailing_21d cross-sectional std of the point-in-time Top20; percentile over 252 days; cash when the percentile is at/above the threshold.

| index | rule | multiple | sharpe | max_drawdown | annualized_volatility | days_in_market |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | none | 22.5301 | 1.5238 | -0.3787 | 0.5162 | 877.0000 |
| 1 | cash when dispersion_pct >= 0.60 | 4.0836 | 1.1001 | -0.3388 | 0.3136 | 997.0000 |
| 2 | cash when dispersion_pct >= 0.70 | 9.0596 | 1.4731 | -0.3388 | 0.3584 | 1,112.0000 |
| 3 | cash when dispersion_pct >= 0.80 | 11.9098 | 1.5301 | -0.3787 | 0.3908 | 1,248.0000 |
| 4 | cash when dispersion_pct >= 0.90 | 15.7686 | 1.5642 | -0.3787 | 0.4305 | 1,391.0000 |

Screening only - turnover is not charged here.
