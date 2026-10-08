# Literature review for the 2026-10 pre-registered research round

| | |
|---|---|
| Date | 2026-09-25 |
| Status | Research input only. No rule in this document is validated, and nothing here changes the champion or `RESEARCH.md`. |
| Scope | Point-in-time CMC Top20, long-only spot, gross exposure <= 1, cash as the only defensive asset, daily close signals (00:00 UTC), costs 2/20/50/100 bps, main sample 2022-01-01 to 2026-09-21. |
| Champion under review | Phase momentum (RESEARCH.md section 0): 4 trailing-return signals x 3 phases = 12 one-coin sleeves, 3-day checks, Top2 hold band, immediate exit on leaving the Top20, BTC 100D MA gate with 2-day confirmation, 60D realised-vol scaling to 80% per sleeve. |
| Evidence files | `/tmp/smart-search-evidence/atlas20-research/` (outside the repo, not durable). Every source below also carries its public URL. |

How to read this document:

- Section 2 is the source-by-source record. Each entry gives the citation, sample, method, headline results (costs, execution lag, out-of-sample evidence where the source reports them) and a transfer label.
- Section 3 is the synthesis for each design decision the project has already made.
- Section 4 holds the pre-registered hypotheses for the next round (4 of them). Their rules and parameter values are fixed here, before any backtest.
- Section 5 lists rejected ideas.

Transfer labels used in section 2:

- **T-direct**: large-cap crypto (about 30 coins or fewer, or BTC/ETH), long-only or long-leg evidence, daily data. The evidence can inform a Top20 daily rule directly.
- **T-partial**: crypto, but a broad universe (hundreds to thousands of coins), long-short construction, or weekly data. The sign of an effect may carry over; magnitudes do not.
- **T-mechanism**: equities, futures or FX. Only the mechanism carries over.

Evidence-handling rules followed here:

- Claims about a source come from text fetched into the evidence directory (full text, or the abstract when only the abstract was available). Where only an abstract was read, the entry says so.
- Sources cited in the older `docs/research/strategy_evidence_audit.md` that were not re-read for this review are listed separately in section 2.6 and are not used to fix any parameter.
- The `smart-search fetch` provider returned empty content for every URL from about midway through this session (even the arXiv API), so a few canonical references could not be re-fetched. They are marked "not re-fetched" and are not used to fix any hypothesis parameter.

---

## 0. Summary

**Most decision-relevant findings**

1. **The execution penalty is signal decay, and published results are upper bounds.** Among the largest coins the latest day's return continues rather than reverses ([S5]); BTC's daily return predicts the next days ([S1]); abnormal daily moves keep going into the next day ([S30]). Hour-of-day return effects are not persistent ([S33]). None of the studies reviewed models a delay between the signal close and the fill ([S17], for example, fills at the signal close by construction), so none measures latency cost. The project's own numbers (23.09x at the close, about 19.6-19.9x three hours later, 12.01x a day later, at 20 bps) fit this picture. The lever with support is latency, not the choice of execution hour.
2. **The champion's 20x rests on two narrow parameter peaks that the literature does not pick.** The BTC gate at MA100 gives 23.09x, while MA50 gives 9.50x and MA150 11.61x; the Top2 hold band gives 23.09x, while ranks 1 and 3 give 14.55x and 9.49x. The literature strongly supports having a market trend gate ([S4], [S17], [S18]) and a hold band ([S36]), but no source supports these particular values, and the standard remedy for horizon uncertainty is an ensemble across horizons ([S17]).
3. **Crypto cross-sectional momentum is real among large coins but fragile.** It is strongest among large coins and in the long leg ([S2], [S4]), yet it is weak or absent in realistic or survivor-only tests ([S4], [S16]), can be decided by a single coin ([S14]), and may have undefined variance ([S15]). Volatility scaling reliably trims tails but should not be expected to add return under a cap of 1 ([S23], [S14], [S25]). Sharpe-based gates need terminal-wealth and rank-based support, and the Deflated Sharpe shortfall (0.74 against 0.95 at 6,119 trials) can only be cured with data after 2026-09-21 that no trial has seen.

**Pre-registered hypotheses (section 4)**

- **H1, decide before the close:** form the signal from 23:00 UTC hourly prices with the latest published (D-2) CMC membership, and fill at the 00:00 UTC close. Kill if less than half of the latency gap is recovered at 20 bps.
- **H2, gate-window ensemble:** replace MA100 with the equal-weight average of the MA50/100/150/200 gates (confirm 2). Kill if it does worse than the median single window.
- **H3, breadth co-gate:** the RESEARCH.md section 0.8 50/50 blend with Top20 breadth (share above MA50) >= 50%. Kill unless drawdown improves by 5 points or more and Sharpe and the one-year rolling worst both improve.
- **H4, top-quintile sleeves:** 4 coins per sleeve (enter top 4, hold while in top 8), equal-weighted and volatility-scaled. Kill unless drawdown improves by 5 points or more and the one-day delay ratio beats the champion's 0.52.

All four are judged at 20 bps with fills 3 hours after the close (the live timing), under the worse of the two missing-candle policies, and reported at 2/20/50/100 bps. H2-H4 are expected to *lower* terminal wealth. If they pass below 20x they are recorded as risk variants, and the champion's 20x is stated as conditional on the parameters they relax.

---

## 1. Why the review is needed now

Three project facts frame the literature questions.

1. **Execution latency is expensive.** The live order goes out after the 02:30 UTC refresh, about 3 hours after the 00:00 UTC close. With Binance 1h candles the champion falls from 23.09x (fill at the close, the headline) to about 19.6-19.9x at 20 bps with a fill 3 hours later (figures from the latest hourly-fill run of `scripts/run_phase_momentum_execution_lag.py`, which runs both missing-candle policies and reports the bracket; that run is not yet in the committed report). A full-day lag gives 12.01x and a two-day lag 5.11x (`reports/phase_momentum_execution_lag_2022/summary.csv`, 20 bps). Most of the one-day loss falls in 2024 (+78.5% at lag 0 against +13.9% at lag 1).
2. **Two parameters sit on narrow peaks.** In the champion's own 25-variant neighbourhood (`reports/phase_momentum_2022/parameter_neighborhood.csv`, 20 bps, lag 0) the BTC gate gives 9.50x at MA50, 23.09x at MA100, 11.61x at MA150 and 6.93x at MA200. The hold band gives 14.55x at hold rank 1, 23.09x at rank 2 and 9.49x at rank 3. The headline therefore depends on two narrow parameter values, which AGENTS.md says a robust strategy may not do. Check frequency declines smoothly instead (1d 27.92x, 2d 23.00x, 3d 23.09x, 5d 15.91x), and target volatility is monotone (0.6: 13.44x, 0.8: 23.09x, 1.0: 29.99x, with drawdown rising from -36.9% to -50.9%).
3. **The trial count is large.** 6,119 Top20 configurations since 2022 (14,124 overall). At that count the champion's Deflated Sharpe is about 0.74, below the 0.95 gate. (RESEARCH.md section 0.2 still reports 0.9945 for the fixed champion; that figure deflates against only 32 candidate trials, per `reports/phase_momentum_multiple_testing_2022/report.md`, not the full Top20 trial history, and should be superseded.) Any new idea has to be economically motivated and cheap in trials.

---

## 2. Source-by-source record

### 2.1 Crypto momentum and trend following

**[S1] Liu, Y. and Tsyvinski, A. (2021). Risks and Returns of Cryptocurrency.** *Review of Financial Studies* 34(6), 2689-2727. doi:10.1093/rfs/hhaa113. Working paper: NBER w24877 (2018), <https://www.nber.org/papers/w24877>. Read: full working paper.

- Sample: BTC 2011-01-01 to 2018-05-31, XRP from 2013-08-04, ETH from 2015-08-07 (CoinDesk), daily and weekly returns.
- Method: time-series predictive regressions of each coin's return on its own past returns, quintile sorts of weekly returns, attention proxies.
- Results: today's BTC return predicts returns 1, 3, 5 and 6 days ahead (a one-standard-deviation move today adds 0.33% to the next day's return). Weekly: the top quintile of past-week returns earns 11.22% the following week (Sharpe 0.45) against 2.60% for the bottom quintile; momentum holds at 1-4 week horizons, in the post-2013 subsample, and in a "no lookahead" variant (Table 17).
- Costs and lag: none modelled; returns are close to close with no execution delay.
- Applicability: time-series evidence on three coins. It supports 1-4 week lookbacks and says that the information in the latest day decays within days, so every hour between signal and fill has a price. **T-direct** for BTC/ETH, **T-partial** for the Top20 cross-section.

**[S2] Liu, Y., Tsyvinski, A. and Wu, X. (2022). Common Risk Factors in Cryptocurrency.** *Journal of Finance* 77(2), 1133-1177. doi:10.1111/jofi.13119. Working paper: NBER w25882, <https://www.nber.org/papers/w25882>. Read: full working paper.

- Sample: 1,707 coins with market cap above $1M, 2014-2018 (109 coins in 2014, 1,583 in 2018), weekly.
- Method: quintile long-short sorts on price, size, volume and volatility characteristics; a three-factor model (market, size, momentum). The momentum factor uses 3-week returns with a 30/40/30 split and value weighting.
- Results: long-short momentum earns 2.7% (1-week), 3.3% (2-week), 4.1% (3-week) and 2.5% (4-week) per week. The three-factor model prices all nine significant strategies. In the size x momentum double sort (Table A.2) the momentum spread is 4.2% per week and significant among **large** coins but 0.6% and insignificant among small coins. The authors report similar results when a BTC short replaces the loser leg.
- Costs and lag: no costs; weekly rebalancing.
- Applicability: the best academic support for 1-4 week lookbacks, and specifically among large coins, which is the part closest to a Top20 universe. Long-short and value-weighted quintiles, so magnitudes do not transfer. **T-partial**.

**[S3] Dobrynskaya, V. (2023). Cryptocurrency Momentum and Reversal.** *The Journal of Alternative Investments* 26(1), 65ff. <https://www.pm-research.com/content/iijaltinv/26/1/65>. Read: abstract only.

- Sample: 2,000 largest coins, 2014-2020; sorting and holding periods from 1 week to 2 years.
- Results: positive momentum up to 2-4 weeks and significant reversal beyond about one month. The switch comes after about a month, much faster than in equities. Reversal is driven mainly by past losers. Returns are not explained by standard crypto factors.
- Costs and lag: not stated in the abstract.
- Applicability: supports lookbacks of 28 days or less. The champion's 42D and 60D components sit in the zone where the broad cross-section reverses, but the reversal comes from losers, which a long-only winner book does not hold. **T-partial**.

**[S4] Han, C., Kang, B. and Ryu, J. (2024). Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market: A Comprehensive Analysis under Realistic Assumptions.** Working paper, SSRN 4675565; conference version <https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>. Read: full text.

- Sample: CMC coins with market cap of at least $1M and daily volume of at least $1M, December 2013 to August 2023, stablecoins removed. With both filters the daily cross-section peaks at 784 coins (December 2021) and ends at 433; a Binance-futures subset is used for short selling.
- Method: look-back and holding periods from 1 to 56 days chosen by regression; daily mark-to-market; liquidation modelling; 15 bps per trade (10 bps Binance spot fee plus slippage estimated from 15.7 million Binance futures market orders).
- Time-series results: a long-only strategy that holds the value-weighted market only when its look-back return is positive is best at (28, 5): Sharpe 1.51 against 0.84 for the market, cumulative 36,686% against 2,696%, invested 48% of the time. The gain comes mainly from lower downside risk, and time-series momentum is "concentrated in a bullish market". Shorting the market after declines loses money in most cases.
- Cross-sectional results: weak. Of 21 cross-sectional portfolios, 5 are liquidated and only 6 beat the market; the best, (14, 7), has Sharpe 1.28 against 1.01. Profits come from the long leg and from large coins; losers often rebound and hurt the short leg.
- Large-cap subset (section 5.2.2): restricted to the top 5% of coins by market cap (as few as 2 coins in 2017, at most 42 in 2021), with a median split instead of quintiles and value weights. Long-only portfolios have higher Sharpe ratios than in the full sample for most look-back/holding pairs, and most beat the market's Sharpe ratio, **but with larger maximum drawdowns than the market**. The best long-only portfolio is (14, 5) with Sharpe 1.54 after the 15 bps cost. This is the closest published analogue to a Top20 long-only cross-sectional rule.
- Lag evidence: a one-day look-back shows strong reversal in their broad universe. Excluding the last day of the look-back raises the Sharpe of 12 of 18 long-short portfolios, but it cuts the (14, 7) cumulative return from 101,218% to 37,389%.
- Also: the t-test on mean returns is inadequate for fat-tailed crypto returns; several portfolios with significant means lose money or are liquidated.
- Applicability: the most realistic crypto momentum study available here. It supports a market trend gate and long-only winner selection among large coins, and warns against mean-return statistics. The universe is far wider than Top20. **T-partial**.

**[S5] Zaremba, A., Bilgin, M.H., Long, H., Mercik, A. and Szczygielski, J.J. (2021). Up or down? Short-term reversal, momentum, and liquidity effects in cryptocurrency markets.** *International Review of Financial Analysis* 78, 101908. doi:10.1016/j.irfa.2021.101908. Read: abstract.

- Sample: daily prices of more than 3,600 coins.
- Results: coins with a low last-day return beat coins with a high last-day return (daily reversal), an effect the authors attribute to illiquidity. It depends on liquidity: "the handful of largest and most tradeable coins exhibit daily momentum rather than a reversal."
- Applicability: this is the key source for the execution question. In a Top20 universe the latest day's move tends to continue, which is exactly what a delayed fill gives away. It also argues against a skip-a-day rule inside Top20, even though skipping helps in broad universes ([S4], [S16]). **T-direct** for the large-coin result; the headline reversal does not transfer.

**[S6] Li, Y., Urquhart, A., Wang, P. and Zhang, W. (2021). MAX momentum in cryptocurrency markets.** *International Review of Financial Analysis* 77, 101829. doi:10.1016/j.irfa.2021.101829. Read: abstract.

- Result: unlike equities, coins with higher maximum daily returns earn higher future returns ("MAX momentum"). The effect varies with market conditions, sentiment and underpricing, and survives longer holding periods and alternative samples.
- Applicability: extreme recent up-days are not followed by reversal on average, which is consistent with buying the recent winner. Broad universe. **T-partial**.

**[S7] Fieberg, C., Liedtke, G., Metko, D. and Zaremba, A. (2023). Cryptocurrency factor momentum.** *Quantitative Finance* 23(12), 1853-1869. doi:10.1080/14697688.2023.2269999. Read: abstract.

- Sample: more than 3,900 coins, 2014-2022, 34 replicated anomalies.
- Result: factor momentum exists, comes mostly from size and volatility factors, and originates in price momentum.
- Applicability: long-short factor level, broad universe. No direct use. **T-partial**.

**[S8] Jia, B., Goodell, J.W. and Shen, D. (2022). Momentum or reversal: Which is the appropriate third factor for cryptocurrencies?** *Finance Research Letters* 45, 102139. doi:10.1016/j.frl.2021.102139. Read: abstract.

- Result: in a more recent sample a market-size-momentum model beats the market-size-reversal model of Shen et al. (2020).
- Applicability: momentum rather than reversal in the post-2018 cross-section. **T-partial**.

**[S9] Grobys, K. and Sapkota, N. (2019). Cryptocurrencies and momentum.** *Economics Letters* 180, 6-10. doi:10.1016/j.econlet.2019.03.028. Read: abstract.

- Sample: 143 coins, 2014-2018.
- Result: no significant momentum payoffs.
- Applicability: counter-evidence from an early, small sample; formation details were not in the abstract. **T-partial**.

**[S10] Kosc, K., Sakowski, P. and Ślepaczuk, R. (2019). Momentum and contrarian effects on the cryptocurrency market.** *Physica A* 523, 691-701. Read: abstract.

- Sample: the 100 largest coins with a 14-day volume filter (out of more than 1,200 in November 2017).
- Result: a short-term contrarian effect clearly dominates both momentum and the benchmarks, with information ratios that sometimes reach double digits.
- Applicability: contradicts the champion, but the sample ends before 2018 and the universe is Top100. The implausibly high information ratios suggest caution. **T-partial**.

**[S11] Tzouvanas, P., Kizys, R. and Tsend-Ayush, B. (2020). Momentum trading in cryptocurrencies: Short-term returns and diversification benefits.** *Economics Letters* 191, 108728. doi:10.1016/j.econlet.2019.108728. Read: abstract.

- Sample: 12 coins, daily data, about three years.
- Result: classic J/K momentum is highly significant for short-term portfolios and disappears at longer horizons; momentum portfolios diversify and hedge traditional assets.
- Applicability: a small universe like Top20; supports short formation periods. **T-direct** (small, old sample).

**[S12] Borgards, O. (2021). Dynamic time series momentum of cryptocurrencies.** *North American Journal of Economics and Finance* 57, 101428. doi:10.1016/j.najef.2021.101428. Read: abstract.

- Sample: twenty cryptocurrencies against the US stock market, daily and intraday price levels.
- Result: most formation periods are followed by momentum periods, and in crypto these are larger and longer at every frequency. A dynamic momentum strategy beats buy-and-hold, and only in crypto with higher risk-adjusted returns and lower downside risk. Volatility bursts at critical price levels start impulses in the direction of the momentum.
- Applicability: 20 large coins, time-series. **T-direct** on universe, but the dynamic rule is not specified in the abstract.

**[S13] Begušić, S. and Kostanjčar, Z. (2019). Momentum and liquidity in cryptocurrencies.** arXiv:1904.00890. Read: abstract. Preprint; no journal reference on arXiv.

- Result: a strong momentum effect in the most liquid coins; two long-only strategies ("illiquid losers" and "liquid winners") beat the cap-weighted market on a risk-adjusted basis.
- Applicability: supports long-only winners among liquid coins. **T-partial** (unrefereed).

**[S14] Grobys, K., Kolari, J.W., Sandretto, D., Shahzad, S.J.H. and Äijö, J. (2025). Cryptocurrency momentum has (not) its moments.** *Financial Markets and Portfolio Management* 39(4). doi:10.1007/s11408-025-00474-9. Full text: <https://osuva.uwasa.fi/bitstreams/994474fd-8d6c-4669-9f43-98836145cad6/download>. Read: full text.

- Sample: the 30 largest coins by market cap at each prior year-end (stablecoins excluded; the set turns over 37% a year), January 2016 to December 2023, 416 weeks.
- Method: quintile sort on the past 30-day return, skipping the most recent day; equal-weighted long-short; weekly rebalancing. Risk management scales the strategy by c / sigma, where sigma is the standard deviation of the strategy's own returns over the prior 4, 8 or 12 weeks.
- Results: plain momentum is insignificant because of one crash driven by a single coin (a -255.28% weekly return). Volatility-managed versions earn 1.86-2.40% a week and stay significant after factor adjustment. Power-law tail exponents are below 3, so the variance is undefined, and volatility management does not change tail risk.
- Applicability: large caps, so the closest cross-sectional study to Top20. It supports volatility management but warns that tails remain, and it shows that one coin can decide the outcome of a momentum book. Long-short, so magnitudes do not transfer. **T-direct** on universe, **T-partial** on construction.

**[S15] Grobys, K. and Shahzad, S.J.H. (2025). Cryptocurrency Momentum: Is It an Illusion?** *International Journal of Finance and Economics*, doi:10.1002/ijfe.70036. Read: abstract.

- Result: the realised variances of six crypto momentum strategies follow power laws; block-bootstrap tests say the population mean and variance of those realised variances are not defined. Performance metrics that use variance as an input (such as the Sharpe ratio) are therefore "not informative".
- Applicability: methodological. The project's Deflated Sharpe and Probabilistic Sharpe gates assume finite higher moments. They should be complemented with drawdown, terminal-wealth and rank-based evidence (section 4.0). **T-direct** for the caveat.

**[S16] Grobys, K., Sandretto, D. and Äijö, J. (2026). On survivor cryptocurrency momentum.** *Finance Research Letters*, 109602. doi:10.1016/j.frl.2026.109602. Read: abstract and highlights.

- Sample: nine "survivor" coins that stayed in the top 100 altcoins from January 2017 to August 2024, and a "plain" momentum strategy on the 30 largest coins each year; weekly.
- Results: no momentum among survivor coins. Plain momentum is profitable only after the data are trimmed. The authors conclude that significant momentum payoffs are "an artefact of coins that are only temporarily accessible for trading".
- Applicability: this goes to the economic source of the champion's return. Top20 winners are often temporary entrants, so a test must show where the return comes from (entrants versus incumbents) and that entrants were tradable at the fill time. **T-direct**.

**[S17] Zarattini, C., Pagani, A. and Barbon, A. (2025). Catching Crypto Trends: A Tactical Approach for Bitcoin and Altcoins.** Swiss Finance Institute Research Paper 25-80 (<https://ideas.repec.org/p/chf/rpseri/rp2580.html>), SSRN 5209907. Full text: <https://concretumgroup.com/wp-content/uploads/2026/02/Catching-Crypto-Trends.pdf>. Read: full text.

- Sample: CMC data. BTC from 2015-01-01 to 2025-03-19; a survivorship-free set of all coins since 2015. The rotational universe is the top B coins by median daily volume over the prior month (B = 5 to 50), rebuilt monthly, after filters: listed for at least 365 days, no stablecoins, wrapped tokens or NFTs, median volume of at least $2M. Coins are dropped if median volume falls below $1M or the median daily price change is below 0.5%.
- Method: per-coin Donchian breakout. Enter when the close reaches the n-day high; exit on a close below a trailing stop that equals the running maximum of the Donchian midpoint. An equal-weight ensemble over n in {5, 10, 20, 30, 60, 90, 150, 250, 360}. Per-coin volatility targeting to 25% using 3-month daily volatility, with a per-coin weight cap of 200%. Capital is split 1/B across coins. Returns are w(t-1) x r(t), i.e. **filled at the signal close with no delay**.
- Costs: the BTC tables are gross. The cost study uses 0, 10, 25 and 50 bps; at 50 bps the 5-day model's CAGR drops from 34% to 18%. A 20% rebalance threshold cuts turnover. The portfolio results include 10 bps and the 20% threshold.
- Results: BTC ensemble Sharpe 1.58, Sortino 2.03, maximum drawdown 19%, alpha 14% (gross); short lookbacks (5-30 days) are best on BTC. The long-only top-20 portfolio, net of 10 bps, has Sharpe 1.57, CAGR 18%, volatility 9%, maximum drawdown 11% and alpha 10.8%. The Sharpe ratio is flat from 10 to 50 coins (1.50-1.57); 5 coins give 1.44.
- Applicability: the closest universe (top 20 liquid coins, daily). The design is different, though: diversified per-coin time-series trend at 9% volatility, not concentrated cross-sectional selection, and returns far below 20x. It supports volatility-based sizing, ensembles across lookbacks, trailing trend exits and turnover thresholds. The 200% weight cap implies leverage, which is out of scope here. Its zero-delay fills make its results an upper bound for any live implementation. **T-direct** on universe, **T-partial** on design.

**[S18] Rzym, A. and Abou Zeid, T. (2024). In crypto we trend.** Man Group insight, December 2024. <https://www.man.com/insights/in-crypto-we-trend>. Read: full article.

- Evidence: average high-frequency pairwise correlation between coins of about 0.6. In a simplified model with equal risk per coin, ranked by average daily volume and including trading costs, shorting costs and liquidity limits, the Sharpe ratio of a 50/200-day moving-average crossover peaks at about 10-15 coins, and of breakout models at about 10 coins. Volatility scaling is central, and once volatility is scaled BTC's left tail is milder than the S&P 500's (citing Harvey et al. 2022, "An Investor's Guide to Crypto").
- Applicability: practitioner evidence, long-short, no numeric performance given. It supports volatility scaling and moderate diversification. **T-partial**.

**[S19] Rozario, E., Holt, S., West, J. and Ng, S. (2020). A Decade of Evidence of Trend Following Investing in Cryptocurrencies.** arXiv:2009.12155. Read: abstract.

- Claims 255% walk-forward annualised returns from trend following since the early days of bitcoin.
- Applicability: unrefereed and implausibly large; given no weight. **T-partial**, low quality.

### 2.2 Risk management: volatility scaling, stop-losses, market states

**[S20] Barroso, P. and Santa-Clara, P. (2015). Momentum has its moments.** *Journal of Financial Economics* 116(1), 111-120. <https://econpapers.repec.org/RePEc:eee:jfinec:v:116:y:2015:i:1:p:111-120>. Read: abstract, plus the method description in [S14].

- Sample and method: US equity momentum (winners minus losers). Returns are scaled by the inverse of the strategy's own six-month realised variance times a target constant ([S14], section 2).
- Result: the risk of momentum is highly variable and predictable; managing it "virtually eliminates crashes and nearly doubles the Sharpe ratio".
- Applicability: strategy-level scaling of a long-short book that may lever up in calm periods. The champion scales one coin per sleeve and can only de-lever. **T-mechanism**.

**[S21] Daniel, K. and Moskowitz, T.J. (2016). Momentum crashes.** NBER Working Paper 20439, <https://econpapers.repec.org/RePEc:nbr:nberwo:20439>; published in the *Journal of Financial Economics* (2016; published version not re-fetched). Read: abstract.

- Result: momentum crashes are partly forecastable. They happen in "panic" states, after market declines and when market volatility is high, at the same time as market rebounds, because past losers carry option-like payoffs. A dynamic strategy based on forecasts of momentum's mean and variance roughly doubles alpha and Sharpe.
- Applicability: the crash channel is the short loser leg. A long-only winner book does not suffer loser rebounds; its risk in panic rebounds is lagging the market while in cash or in low-beta winners. **T-mechanism**.

**[S22] Moreira, A. and Muir, T. (2017). Volatility-Managed Portfolios.** *Journal of Finance* 72(4), 1611-1644. <https://ideas.repec.org/a/bla/jfinan/v72y2017i4p1611-1644.html>; NBER w22208. Read: abstract.

- Result: portfolios that take less risk when volatility is high earn large alphas and higher Sharpe ratios for the market, value, momentum, profitability, ROE and investment factors and the currency carry trade, because volatility changes are not matched by proportional changes in expected returns.
- Applicability: evidence comes from in-sample spanning regressions; see [S23]. **T-mechanism**.

**[S23] Cederburg, S., O'Doherty, M.S., Wang, F. and Yan, X. (2020). On the performance of volatility-managed portfolios.** *Journal of Financial Economics* 138(1), 95-117. doi:10.1016/j.jfineco.2020.04.015. Read: abstract.

- Sample: 103 equity strategies.
- Result: volatility-managed portfolios do not systematically beat their unmanaged versions in direct comparisons. The spanning-regression alphas are not implementable in real time, and reasonable out-of-sample versions generally earn lower certainty-equivalent returns and Sharpe ratios than the unmanaged portfolios, because the underlying regressions are structurally unstable.
- Applicability: the main caution against expecting return gains from volatility scaling. **T-mechanism**.

**[S24] Harvey, C.R., Hoyle, E., Korgaonkar, R., Rattray, S., Sargaison, M. and Van Hemert, O. (2018). The Impact of Volatility Targeting.** *Journal of Portfolio Management* 45(1), 14ff; SSRN 3175538. Summary: <https://www.man.com/insights/the-impact-of-volatility-targeting>. Read: Man summary page.

- Sample: more than 60 assets, daily data from 1926.
- Results: volatility targeting raises the Sharpe ratio of "risk assets" (equities, credit) and of portfolios with large allocations to them, through the leverage effect (the negative link between returns and volatility changes). For bonds, currencies and commodities the Sharpe effect is negligible. For all assets it reduces extreme returns and volatility of volatility, and it reduces the maximum drawdown of balanced and risk-parity portfolios.
- Applicability: the dependable benefit is thinner tails, not a higher Sharpe. Whether crypto has an equity-like leverage effect was not established by any source read here, so a Sharpe gain should not be assumed. **T-mechanism**.

**[S25] Yang, A. (2025). Cryptocurrency market risk-managed momentum strategies.** *Finance Research Letters* 85(PA), 107879. doi:10.1016/j.frl.2025.107879. Read: abstract.

- Method: the Barroso and Santa-Clara (2015) risk-managed momentum applied to crypto.
- Results: average weekly returns rise from 3.18% to 3.47% and the annualised Sharpe from 1.12 to 1.42. Unlike in equities, the gain comes from **higher returns**, since crypto momentum shows no extended crashes. Robust to transaction costs, short-sale constraints and horizons (details not in the abstract).
- Conflict: [S14] finds a large single-coin crash in the top-30 momentum book and no change in tail risk. The two samples differ; neither abstract settles which is right.
- Applicability: a return gain from scaling needs exposure above 1 in calm periods, which the project forbids. With a cap of 1.0 only the de-risking half of the mechanism is available. **T-partial**.

**[S26] Kaminski, K.M. and Lo, A.W. (2014). When do stop-loss rules stop losses?** *Journal of Financial Markets* 18, 234-254. doi:10.1016/j.finmar.2013.07.001. Read: abstract.

- Method: an analytical framework for the effect of stop-loss rules on expected return and volatility, with an empirical study on index-futures buy-and-hold.
- Result: at longer sampling frequencies certain stop-loss policies can raise expected return while substantially reducing volatility.
- Applicability: whether a stop helps depends on the return process (the abstract does not spell out the conditions). **T-mechanism**.

**[S27] Lo, A.W. and Remorov, A. (2017). Stop-loss strategies with serial correlation, regime switching, and transaction costs.** *Journal of Financial Markets* 34, 1-15. doi:10.1016/j.finmar.2017.02.003. Read: **abstract not captured** (IDEAS, EconPapers, SSRN and ScienceDirect fetches returned no abstract text). Listed for completeness and not used for any decision.

**[S28] Han, Y., Zhou, G. and Zhu, Y. (2016). Taming Momentum Crashes: A Simple Stop-Loss Strategy.** Working paper, CICF 2016 version <https://www.cicfconf.org/sites/default/files/paper_811.pdf>; later circulated as CEPR Discussion Paper 19030. Read: full CICF text.

- Sample: CRSP common stocks, January 1926 to December 2013; decile momentum.
- Method: a 10% stop at the stock level within the month. A winner is sold when its price falls 10% below the start-of-month price, and short losers are covered after a 10% rise; daily open and close prices determine the trigger.
- Results: the worst monthly loss of equal-weighted momentum improves from -49.79% to -11.36%, value-weighted from -64.97% to -23.28%; average returns and Sharpe ratios more than double. About 30% of winners are sold in an average month.
- Caveats in the paper: from July 1962 to June 1992 CRSP has no open prices, so fills are assumed at the stop level, which "will over-state the results". The stop needs intraday or at-the-open execution.
- Applicability: much of the benefit is on the short leg, and intraday stop execution is out of scope here. A 10% equity stop corresponds to a much wider crypto stop. **T-mechanism**.

**[S29] Sadaqat, M. and Butt, H.A. (2023). Stop-loss rules and momentum payoffs in cryptocurrencies.** *Journal of Behavioral and Experimental Finance* 39, 100833. doi:10.1016/j.jbef.2023.100833. Read: abstract.

- Sample: 147 cryptocurrencies, January 2015 to June 2022.
- Result: stop-loss momentum earns higher returns, Sharpe ratios and alphas than benchmark momentum strategies, in all market states; the authors explain it through the disposition effect.
- Applicability: the stop level, construction (long-short or not) and execution assumptions are not in the abstract, so no parameter can be taken from it. **T-partial**.

### 2.3 Intraday behaviour, execution timing and 00:00 UTC

**[S30] Caporale, G.M. and Plastun, A. (2020). Momentum effects in the cryptocurrency market after one-day abnormal returns.** *Financial Markets and Portfolio Management* 34(3), 251-266 (CESifo Working Paper 7917, 2019: <https://ideas.repec.org/p/ces/ceswps/_7917.html>). Read: abstract.

- Sample: BTC, ETH and LTC against USD, 2017-01-01 to 2019-09-01, hourly data.
- Results: on days with abnormal ("overreaction") moves, hourly returns keep moving in the direction of the move until the end of the day, and the effect and its trading profits carry over into the **following day**. Two exceptions (BTC positive overreactions, ETH negative overreactions) show contrarian behaviour instead.
- Applicability: direct evidence that the hours after a large daily move continue the move for large coins. A ranking signal that favours coins that just jumped will lose part of that continuation to a delayed fill. **T-direct** (three coins, short sample).

**[S31] Wen, Z., Bouri, E., Xu, Y. and Zhao, Y. (2022). Intraday return predictability in the cryptocurrency markets: Momentum, reversal, or both.** *North American Journal of Economics and Finance* 62, 101733. doi:10.1016/j.najef.2022.101733. Read: abstract.

- Sample: BTC high-frequency data from 2013-03-03 to 2020-05-31, plus ETH, LTC and XRP.
- Result: both intraday momentum and intraday reversal, with patterns that change around large jumps, FOMC announcements, liquidity levels and COVID-19. Timing strategies built on the intraday predictors beat always-long and buy-and-hold.
- Applicability: intraday predictability exists but its sign is state dependent, so it gives no stable rule for choosing an execution hour. **T-partial**.

**[S32] Shen, D., Urquhart, A. and Wang, P. (2022). Bitcoin intraday time series momentum.** *Financial Review* 57(2), doi:10.1111/fire.12290. Accepted manuscript: <https://centaur.reading.ac.uk/100181/>. Read: abstract and data tables of the manuscript.

- Sample: BTC/USD on Bitfinex, Bitstamp, CEX.IO, Coinbase and Kraken, 2013-2020. Because bitcoin has no open or close, the "session" is defined by volume as roughly 09:00-17:00 US Eastern time.
- Results: the first half-hour return (including the overnight return) predicts the last half-hour return; predictability is strongest when the first session has the highest volume or volatility; the effect comes from liquidity provision rather than late-informed trading.
- Applicability: it concerns the US session, not the 00:00-03:00 UTC window, so it says nothing directly about the champion's fill time. **T-partial**.

**[S33] Baur, D.G., Cahill, D., Godfrey, K. and Liu, Z. (2019). Bitcoin time-of-day, day-of-week and month-of-year effects in returns and trading volume.** *Finance Research Letters* 31, 78-92. doi:10.1016/j.frl.2019.04.023. Read: abstract.

- Sample: more than 15 million observations from seven continuously traded bitcoin exchanges.
- Results: time-specific anomalies appear in returns but are **not persistent** over time. Trading activity differences are persistent (lower in local evenings and at weekends).
- Applicability: no stable hour-of-day return effect is available to explain or exploit the 3-hour fill penalty. The penalty is better read as signal decay after the close ([S5], [S30]). **T-direct** for BTC.

**[S34] Wątorek, M., Skupień, M., Kwapień, J. and Drożdż, S. (2023). Decomposing cryptocurrency high-frequency price dynamics into recurring and noisy components.** *Chaos* 33, 083146; arXiv:2306.17095. Read: abstract.

- Sample: BTC, ETH, DOGE and WIN, January 2020 to December 2022, sampled every 10 seconds.
- Results: three activity phases matching the Asian, European and US sessions; activity surges at 15-minute marks and especially at full hours, which the authors link to algorithmic trading; recurring bursts at US macro release times.
- Applicability: the 00:00 UTC close is itself a full-hour burst. Orders fired exactly at hh:00:00 meet crowded books, so an execution window a few minutes wide and cost stress (50/100 bps) are sensible. **T-direct** (four coins).

**[S35] Petukhina, A.A., Reule, R.C.G. and Härdle, W.K. (2021). Rise of the Machines? Intraday High-Frequency Trading Patterns of Cryptocurrencies.** *The European Journal of Finance* (online 2020); arXiv:2009.04200. Read: abstract.

- Result: documents intraday return, volume and volatility periodicity and argues that intraday trading patterns carry predictable economic value.
- Applicability: descriptive; no rule for the daily fill. **T-partial**.

### 2.4 Implementation: turnover control

**[S36] Novy-Marx, R. and Velikov, M. (2016). A Taxonomy of Anomalies and Their Trading Costs.** *Review of Financial Studies* 29(1), 104-147 (NBER w20721). <https://econpapers.repec.org/RePEc:oup:rfinst:v:29:y:2016:i:1:p:104-147.>. Read: abstract.

- Result: a buy/hold spread, i.e. stricter conditions for opening a position than for keeping it, is the most effective cost-mitigation technique. Most anomalies with less than 50% monthly turnover earn significant net spreads when designed to mitigate costs; few with higher turnover do.
- Applicability: supports having a hold band. It does not say how wide the band should be. **T-mechanism**.

### 2.5 Sources found but not used

| Source | Reason |
|---|---|
| Bui, D. and Nguyen, T. (2026). Systematic Trend-Following with Adaptive Portfolio Construction. arXiv:2602.11708 | 6-hour intraday trading, 150+ pairs, 70/30 long-short. Out of scope on universe, shorting and intraday trading. |
| "Intraday time series momentum: Global evidence and links to market characteristics", *Journal of Financial Markets* 57 (2022), RePEc handle `eee:finmar:v:57:y:2022:i:c:s138641812100001x` | Not a crypto study and the abstract was not captured. |
| Proelss, J., Schweizer, D. and Buchwalter, B. (2025). Do risk preferences drive momentum in cryptocurrencies? *Finance Research Letters* 73, 106531 | Abstract not captured. |
| arXiv query results on crypto price forecasting (transformers, LSTM, reinforcement learning, sentiment) | Machine-learning forecasting with no transparent rule; high multiple-testing cost. |

### 2.6 Sources relied on elsewhere but not re-read for this review

These are cited in `docs/research/strategy_evidence_audit.md` or are standard method references. None of them fixes a parameter in section 4.

| Source | Status | Relevance |
|---|---|---|
| Clare, Seaton, Smith and Thomas, "Breaking into the Blackbox: Trend Following, Stop Losses, and the Frequency of Trading" | Audit summary only | S&P 500: month-end decisions beat more frequent trading; stop rules add no value. |
| Białkowski (2020), *Economics Letters* 191, "Cryptocurrencies in institutional investors' portfolios: evidence from industry stop-loss rules" | Audit summary only | Stops cut volatility and returns. |
| Kaya and Mostowfi (2022), *Finance Research Letters*, doi:10.1016/j.frl.2021.102422 | Audit summary only | Low-volatility crypto portfolios with simple stops. |
| Duarte (2022), "Trailing Stop-Loss and Re-Entry Strategies in Europe", *EJBMR* 7(3) | Audit summary only | Re-entry is a separate decision point. |
| Le and Ruthbah, "Trend-following Strategies for Crypto Investors" (Monash) | Audit summary only | MA 20/65/150/200 on BTC, ETH and a large-cap index; 65D best for BTC, 20D for ETH and large non-BTC coins; costs matter. |
| Grobys, Ahmed and Sapkota (2020), "Technical trading rules in the cryptocurrency market", *Finance Research Letters* | Audit summary only | 11 liquid coins 2016-2018; MA20 did well in a short sample. |
| Platanakis, Sutcliffe and Urquhart (2018), "Optimal vs naïve diversification in cryptocurrencies", *Economics Letters* 171, 93-96 | Audit summary only | 1/N is as good as Markowitz for four coins. |
| Ammann, Burdorf, Liebi and Stöckl, "Survivorship and Delisting Bias in Cryptocurrency Markets" | Audit summary only | Up to 62% survivorship bias in equal-weighted returns; momentum-beta link disappears once delisting returns are included. |
| Cooper, Gutierrez and Hameed (2004), "Market States and Momentum", *Journal of Finance* 59(3) | Not re-fetched (fetch outage) | Equity momentum profits depend on the prior market state. |
| Jegadeesh and Titman (1993), *Journal of Finance* 48(1) | Not re-fetched | Overlapping-portfolio construction, the ancestor of phase-staggered sleeves. |
| Bailey and López de Prado (2014), "The Deflated Sharpe Ratio", *Journal of Portfolio Management* 40(5); White (2000), "A Reality Check for Data Snooping", *Econometrica* 68(5); Bailey, Borwein, López de Prado and Zhu (2017), "The Probability of Backtest Overfitting", *Journal of Computational Finance* 20(4) | Not re-fetched; already implemented in the project | Multiple-testing gates used in section 4. |

---

## 3. Synthesis by design decision

Each decision gets the project rule, the in-project evidence, what the literature supports, what it contradicts, where sources conflict, and a verdict. In-project numbers are at 20 bps with fills at the close (lag 0) unless stated otherwise.

### 3.1 Selection signal and lookbacks

- **Rule.** Four equal-weight trailing-return signals: a 7/14/21/28/42/60D blend weighted 10/15/20/25/15/15%, ret21, an equal 7/14/28/60 blend and an equal 14/21/28 blend.
- **In-project evidence.** Dropping any one signal gives 20.58x-27.58x (RESEARCH.md section 0.2). Older score-family tests showed the result is not family-insensitive (section 0.5).
- **Supported.** Horizons of 1-4 weeks are the best-documented crypto momentum horizons: [S1] (time series, 1-4 weeks), [S2] (cross-section, strongest at 3 weeks, and significant only among large coins), [S3] (momentum up to 2-4 weeks), [S4] (best cross-sectional look-back 14 days, best market time-series look-back 28 days, and, in its top-5% large-cap subset, a best long-only (14, 5) portfolio with Sharpe 1.54 after costs), [S11] (short-term momentum in 12 coins). For the largest coins even the last day's return continues [S5], and extreme up-days do not reverse on average [S6].
- **Contradicted.** No momentum in 143 coins over 2014-2018 [S9]; a short-term contrarian effect among the top 100 before 2018 [S10]; weak cross-sectional momentum overall and one-day reversal in a broad universe [S4]; momentum payoffs as an artefact of temporarily tradable coins [S16]; Sharpe-based inference unreliable because variances are undefined [S15].
- **Conflicts.** (a) The 42D and 60D components fall where [S3] finds broad cross-sectional reversal, but that reversal is driven by losers, and trend-following studies use horizons out to 360 days [S17]. No source isolates 42-60D winners among large coins. (b) Skipping the last day helps in broad or top-30 long-short books ([S4], [S14]), but [S5] finds daily momentum among the largest coins, so a skip rule should hurt inside Top20.
- **Verdict.** The 7-28D core is well supported. The 42D/60D weights and the exact blend weights are in-project constructs with no external support either way. Do not open new signal-family trials; the family is already a known source of selection risk.

### 3.2 Holding rule and hysteresis (Top2 hold band)

- **Rule.** Keep the incumbent while it stays in the sleeve's Top2; otherwise switch to rank 1.
- **In-project evidence.** Hold rank 1: 14.55x; rank 2: 23.09x; rank 3: 9.49x. Both neighbours lose 37-59% of terminal wealth.
- **Supported.** A buy/hold spread is the most effective cost-mitigation technique [S36]; turnover thresholds work in crypto trend following [S17].
- **Contradicted.** Nothing contradicts having a band. Nothing supports a width of 2.
- **Conflicts.** Short-horizon decay ([S1], [S5], [S30]) argues for a narrow band so that fading winners are dropped quickly; costs [S36] argue for a wider one. The project's two neighbours fail in opposite directions, which is consistent with both forces being real and with rank 2 being a lucky balance point in this sample.
- **Verdict.** Keep the band, but record it as the second parameter on a narrow peak. H4 tests a band expressed in quintile terms rather than a new rank width.

### 3.3 Check frequency and phase staggering

- **Rule.** Each sleeve checks every 3 days; 3 phases per signal, so some sleeve checks every day.
- **In-project evidence.** 1-day checks 27.92x, 2-day 23.00x, 3-day 23.09x, 5-day 15.91x: a smooth decline as checks slow down. For the old 21D champion the fixed-start result (22.44x) was far above the median over 21 phases (3.94x) (RESEARCH.md section 0.4), which is timing luck.
- **Supported.** Crypto momentum works best with holding periods of about 5-7 days ([S4]: time series (28, 5), cross-section (14, 7), large-cap long-only (14, 5)) and weekly rebalancing [S2]. Phase staggering is the overlapping-portfolio method of Jegadeesh and Titman (1993; not re-fetched) and removes start-date luck, as the project's own phase audit shows.
- **Contradicted.** Only equity evidence that less frequent trading is better (Clare et al., secondary).
- **Conflicts.** None material. The monotone gain from faster checks has the same cause as the execution-delay penalty: the information decays within days ([S1], [S5], [S30]).
- **Verdict.** Keep 3-day checks with staggered phases. Do not move to the 1-day neighbour after the fact (it is already in the trial ledger); the faster the checks, the more the strategy depends on low latency.

### 3.4 BTC trend gate (MA100, 2-day confirmation)

- **Rule.** All sleeves go to cash when BTC closes below its 100-day moving average for 2 consecutive days, and re-enter immediately when the confirmed state flips back.
- **In-project evidence.** Without the gate: 2.88x and -76.0% drawdown. MA50: 9.50x; MA100: 23.09x; MA150: 11.61x; MA200: 6.93x. In the separate section 0.7 event ensemble MA100 was also best (at 2 bps: MA50 12.15-13.79x, MA100 23.62-28.95x, MA200 16.32-18.19x), and confirm 1 and confirm 2 were almost identical.
- **Supported.** Market-level time-series momentum is the strongest realistic crypto momentum result, and it works by holding the market only in bull phases [S4]. Coins move with BTC [S4], so a BTC state variable is a sensible market proxy. Momentum crash risk rises after market declines (for long-short books) [S21]; the equity market-state evidence of Cooper et al. (2004) points the same way (not re-fetched). Crypto trend-following studies ([S17], [S18]) back trend exits in general.
- **Contradicted.** No source argues against a long-only market gate. None supports 100 days specifically: Le and Ruthbah (secondary) prefer 65D for BTC, [S4] uses a 28-day market look-back, Man [S18] uses 50/200 crossovers, and [S17] averages 5-360 days.
- **Conflicts.** The confirmation rule lowers whipsaw but adds up to one day of lag to exits and entries, and the lag evidence ([S5], [S30] and the project's lag study) says a day of lag is expensive. No source tests confirmation days.
- **Verdict.** The gate's existence is well supported and carries most of the result. Its window is the single largest fragility in the champion. The literature's standard answer to horizon uncertainty is an ensemble across horizons ([S17]; RESEARCH.md section 0.6 found fixed equal-weight ensembles more stable out of sample than choosing parameters). H2 tests that.

### 3.5 Volatility targeting and scaling

- **Rule.** Each sleeve's weight is min(1, 0.80 / annualised 60-day realised volatility of the held coin); gross exposure is capped at 1.
- **In-project evidence.** Without volatility targeting: 24.55x with -66.9% drawdown, against 23.09x with -44.9%. Targets 0.6/0.7/0.9/1.0 give 13.44x/17.80x/26.26x/29.99x with drawdowns from -36.9% to -50.9%.
- **Supported.** De-risking in high volatility cuts crashes and tails ([S20], [S22], [S24]), and in large-cap crypto momentum it is the difference between an insignificant and a significant strategy [S14]. Crypto trend-following practice sizes by volatility ([S17], [S18]).
- **Contradicted.** Real-time volatility management does not beat unmanaged portfolios out of sample for most equity strategies [S23]; tail risk is unchanged in crypto momentum [S14]; Sharpe gains depend on a leverage effect that was not shown for crypto here [S24].
- **Conflicts.** [S25] reports higher crypto momentum returns from risk management, [S14] reports only risk reduction with unchanged tails. [S20] and [S14] scale the strategy, [S17] and [S18] scale each asset; with one coin per sleeve the champion's scaling is effectively per asset. [S25]'s return gain requires exposure above 1 in calm periods, which is forbidden.
- **Verdict.** The project's result (similar return, drawdown 22 points lower) is what the literature predicts for a cap-1 de-risking overlay. The 80% target sits on a monotone return/drawdown frontier; it is a risk preference, not a discovered optimum. No new volatility trials.

### 3.6 Stop-losses and trend exits

- **Rule.** None beyond the gate and the Top20 exit.
- **In-project evidence.** Fixed stops at 15-40%: 20.29x-24.54x; trailing stops at 15-40%: 15.58x-23.51x; own-coin trend filters at 50-200D: 10.57x-17.57x. None beats the champion on return, Sharpe and drawdown together.
- **Supported.** Stops improved equity momentum [S28], stop-loss momentum beat plain momentum in 147 coins [S29], and stops can raise return and cut volatility under some return processes [S26].
- **Contradicted.** Equity trend stops added no value (Clare et al., secondary); the project's own ablation.
- **Conflicts.** [S28] gets much of its benefit from the short leg and needs intraday fills (and overstates results where open prices are missing); [S29] gives no transferable parameter. A daily-close stop filled 3 hours later is a different instrument.
- **Verdict.** No new stop trials. The immediate exit on leaving the Top20 is a universe constraint, not a stop, and stays.

### 3.7 Concentration (one coin per sleeve)

- **Rule.** Each of the 12 sleeves holds a single coin; distinct coins across sleeves give partial diversification.
- **In-project evidence.** Removing the best year (2023) leaves 4.83x; per-year returns range from -22.8% to +378.4%.
- **Supported (concentration).** Crypto momentum profit sits in the long leg and among large winners [S4]; among large coins the long-only winner half beats the market's Sharpe ratio [S4]; extreme up-days do not reverse (MAX momentum) [S6]; liquid winners do best [S13].
- **Supported (diversification).** In a top-20 crypto trend portfolio the Sharpe ratio is flat from 10 to 50 coins and lower at 5 [S17]; Man finds a Sharpe peak at about 10-15 coins [S18]; one coin can make a top-30 momentum book insignificant [S14]; payoffs may come from coins that are only temporarily tradable [S16]; the large-cap long-only winner portfolios in [S4] carry larger drawdowns than the market; 1/N is hard to beat in crypto (Platanakis et al., secondary).
- **Conflicts.** Concentration maximises the chance of reaching 20x; diversification protects the Sharpe ratio and reduces dependence on one coin, one year and a few trades, which AGENTS.md requires.
- **Verdict.** Cross-sectional crypto momentum studies define "winners" as the top quintile ([S2], [S4], and [S14] inside the top 30 coins); [S4]'s top-5% subset uses the top half instead because it has so few coins. In a 20-coin universe the quintile is 4 coins. H4 tests it as a single pre-registered risk hypothesis.

### 3.8 Execution delay and intraday behaviour around 00:00 UTC

- **Rule.** Signal at the 00:00 UTC close; the live order goes out after the 02:30 UTC refresh.
- **In-project evidence.** 23.09x at the close, about 19.6-19.9x with a fill 3 hours later, 12.01x one day later, 5.11x two days later.
- **Supported explanation.** Recent returns of large coins continue over the next day: daily momentum among the largest coins [S5], BTC's daily return predicting the next days [S1], continuation into the following day after abnormal moves [S30], no reversal after extreme up-days [S6]. A strategy that buys recent winners loses part of that continuation for every hour of delay.
- **No stable hour-of-day effect.** Bitcoin's time-of-day return anomalies are not persistent [S33]; intraday predictability flips sign with conditions [S31]; the best-known intraday momentum result concerns the US session, not 00:00 UTC [S32]. Activity bursts at full hours [S34], so the 00:00:00 print itself is crowded.
- **Gap.** None of the sources models a delay between the signal close and the fill; [S17] fills at the signal close by construction (w(t-1) x r(t)), and [S1], [S2] and [S4] measure returns from the formation close. None measures the cost of a few hours of latency, so published crypto momentum results are upper bounds for live trading.
- **Verdict.** Treat the penalty as signal decay, not seasonality. The lever with support is latency: decide before the close and trade at it (H1). Choosing a "best" execution hour from 23 candidates would be an unsupported multiple-testing exercise and is rejected (section 5).

### 3.9 Universe membership and entrants

- **Rule.** Point-in-time CMC Top20; a holding that leaves the day's Top20 is sold immediately.
- **Evidence.** [S16] argues that crypto momentum payoffs come from coins that are only temporarily tradable; [S14] finds that the top-30 set turns over 37% a year and that one coin can dominate. Zarattini et al. require 365 days of listing history and minimum volume, and drop coins whose volume or price activity dries up [S17].
- **Verdict.** No rule change is proposed (the Top20 rule is a hard constraint). Every hypothesis report must split returns between coins that entered the Top20 within the prior 30 days and incumbents, so that the [S16] critique can be checked directly.

---

## 4. Pre-registered hypotheses for the next round

Four hypotheses, fixed before any backtest. Three target fragility or drawdown, one targets execution latency; none is designed to add return. H5 was added on 2026-10-08 in a second, separately pre-registered round (mechanism and full rule below; registered in `reports/research_trial_inventory/preregistered_trials.csv` before it ran).

Each primary run counts as one trial. The diagnostic runs listed under each hypothesis are declared here and logged, but they are attribution runs and may not be promoted to candidates.

> **2026-10-08 addendum.** The pre-declared neighbourhoods were run this day, after H2 and H3 passed their
> kill criteria: six new ledger trials (H2 leave-one-window-out x4; H3 thresholds 0.45/0.55), registered
> before running. Results and the updated multiple-testing count are in `RESEARCH.md` section 00.6. The panel
> also grew from the 101 coins recorded above to 102 at the CMC refresh; the frozen research window and the
> point-in-time membership rule are unchanged.

> **2026-10-08 addendum (H5).** H5 was registered in the ledger, run through the production engine, and it
> **passed** its kill criterion at 2/20/50 bps (MDD improvement 8.71 pp over B, Sharpe 1.623 vs H3's 1.466,
> one-year rolling worst 0.806 vs H3's 0.733 at the protocol setting). Its pre-declared 0.60/0.90 percentile
> neighbourhoods both keep the criterion. It is also the first specification in this project to pass the PBO
> gate (**0.192** over the extended 36-candidate family; H3 0.558 and B 0.526 both fail). It remains provisional:
> the Deflated Sharpe over the project's 6,135 Top20/2022 trials is **0.860 < 0.95**, and the protocol return
> (19.53x at 20 bps +3h) is below 20x, the "recorded risk variant" case written into the kill criterion. H5 was
> adopted as the frozen specification on that basis; the full record, including the two evaluator defects fixed
> during the adoption (a missing H5 entry in `NEIGHBOURHOOD_IDS` and H5 falling through to H4's criterion), is
> in `RESEARCH.md` section 00.13.

### 4.0 Common protocol

- **Data.** The champion's panel (`data/processed/panel_daily.csv`, 101 coins, 2020-10-03 to 2026-09-21) and Binance 1h candles (`data/raw/binance_1h`, 57 symbols, earliest candles 2021-12-25) through `atlas20.backtest.intraday`. Point-in-time CMC Top20 membership as in production; no universe changes.
- **Window.** Main sample 2022-01-01 to 2026-09-21. The 2020-10 to 2021-12 stress window is run at lag 0 and lag 1 day only, because the hourly candles start on 2021-12-25.
- **Execution.** Primary fill: 3 hours after the signal close (the close of the 02:00-03:00 UTC candle), which matches the live 02:30 UTC refresh. Run under both missing-candle policies of `pre_fill_returns` (`day_close` and `prior_close`) and decide on the **worse** of the two. Also report lag 0 and lag 1 day, and the delay ratios D3h = M(+3h) / M(lag 0) and D1d = M(lag 1d) / M(lag 0). For the champion at 20 bps, D1d = 12.01 / 23.09 = 0.52.
- **Costs.** 2, 20, 50 and 100 bps under the engine's existing cost convention. Kill criteria are evaluated at 20 bps (the level of the RESEARCH.md headline); the verdict must point the same way at 2 and 50 bps, and 100 bps is reported.
- **Baseline.** The champion (`PhaseMomentumSpec` defaults, `PRIMARY_SIGNAL_SPECS`) rerun in the same harness with the same fill rule. Written B below.
- **Metrics.** Multiple, CAGR, Sharpe, maximum drawdown, one-year rolling worst and median multiple, yearly returns, the bull/non-bull split of `scripts/run_phase_momentum_regime_breakdown.py`, the multiple without the best year, turnover, and the share of return earned on coins that entered the Top20 within the previous 30 days versus incumbents (to check the [S16] critique).
- **Multiple testing.** Log every run in the trial ledger before running it. Report the Deflated Sharpe with N = 6,119 plus all new Top20 trials, and the White Reality Check p-value, with the project's existing scripts. Because crypto momentum variances may be undefined ([S14], [S15]), Sharpe-based statistics are not enough on their own: also report a block-bootstrap distribution of the terminal-wealth ratio against B (the project's existing bootstrap settings, not new ones) and the number of calendar years and regimes in which the hypothesis beats B.
- **Outcome tiers.** (1) *Execution protocol adopted* (H1 only; the strategy rules do not change). (2) *Risk variant recorded*: the risk endpoints pass, but the multiple is below 20x at 20 bps with +3h fills. (3) *Champion candidate*: 20x or more at 20 bps with +3h fills under the worse missing-candle policy, Deflated Sharpe of at least 0.95, and all AGENTS.md robustness gates passed. The gates are not relaxed for any tier.
- **What this round cannot fix.** None of these hypotheses can lift the champion's Deflated Sharpe from 0.74 to 0.95; that shortfall comes from the selection history. The only clean remedy is data that no trial has seen. Freeze the champion (and, if adopted, the H1 protocol) now and evaluate it on returns after 2026-09-21 as a genuine out-of-sample period, with no further tuning.

### H1. Decide one hour before the close, trade at the close

**Question.** Can the latency penalty (23.09x at the close against about 19.6-19.9x with a 3-hour fill, at 20 bps) be removed by deciding before the close instead of after it?

**Rule.**

1. Decision time is 23:00 UTC on day D-1, one hour before the daily close that ends D-1.
2. Decision price P*(c) for each coin c: the close of the Binance 1h candle that opens at 22:00 UTC on D-1, if it exists and passes the same 5% open-gap check `pre_fill_returns` applies. Otherwise the latest price observable at 23:00, which is the panel close of D-2.
3. Signals: the same four blends, with every trailing return computed as P*(c) / P(c, D-1-L) - 1, where P(c, D-1-L) is the panel close L days earlier, for L in {7, 14, 21, 28, 42, 60}.
4. Membership: the CMC Top20 snapshot of D-2, the latest one published by 23:00 on D-1. A holding outside that snapshot is exited.
5. BTC gate: the raw state compares P*(BTC) with the 100-day average of the panel closes from D-100 to D-2 plus P*(BTC); the 2-day confirmation is unchanged.
6. Volatility scaling: 60-day realised volatility from panel returns up to D-2.
7. Fill at the panel close of D-1 (00:00 UTC on D), i.e. the engine's lag-0 fill. Hold band, 3-day checks, phases, the 80% target and the cap of 1 are unchanged.

**Parameters and their sources.** The one-hour offset is the smallest offset on the available hourly grid and is not chosen by backtest; no other offset will be tried. The one-snapshot membership lag is forced by point-in-time availability. Everything else is the champion's.

**Rationale.** For the largest coins the latest day's return continues rather than reverses ([S5]); BTC's daily return predicts the following days ([S1]); after abnormal daily moves, prices keep moving in the same direction into the next day ([S30]). A strategy that buys recent winners therefore gives up part of its edge in every hour between signal and fill. A 7- to 60-day return barely changes in its final hour (one hour is at most 1/168 of the shortest window), so deciding at 23:00 should keep almost all of the signal while removing most of the latency. There is no persistent hour-of-day return effect that makes either 23:00 or 00:00 special ([S33]). The 00:00 print is a full-hour activity burst ([S34]), which the 20/50/100 bps stress covers. Filling at 00:00 rather than right after the 23:00 decision leaves one hour of latency in the test, so the backtest is conservative relative to a live order sent at about 23:05.

**What could make it fail.** (a) Membership is one day older: new Top20 entrants become eligible a day later and leavers are sold a day later. If [S16] is right that entrants carry much of the return, this could cost more than the latency saves. (b) Coins without Binance candles fall back to a 23-hour-old price.

**Expected direction.** At every cost level M(H1) lies between B (+3h) and the lag-0 champion; maximum drawdown is close to the lag-0 figure.

**Test.** H1 at 2/20/50/100 bps. Declared diagnostics, not candidates: (i) the lag-0 champion with D-2 membership only, to isolate the membership cost; (ii) the share of sleeve-days on which H1's holding differs from the champion's 00:00 holding; (iii) the share of coin-days on the stale fallback price.

**Kill criterion.** Reject if, at 20 bps, M(H1) < B + 0.5 x (M(lag 0) - B), with B taken under the worse missing-candle policy; or if maximum drawdown is more than 2 percentage points worse than B's; or if diagnostic (ii) exceeds 10% of sleeve-days (H1 would then be a different strategy and would have to be evaluated as a new candidate, not as an execution protocol).

**Governance note.** AGENTS.md says signals are generated at the close and executed afterwards. H1 keeps one decision per day, executes after the decision and uses no future data, but it moves the decision to 23:00 using intraday prices. The task brief allows intraday data for timing the daily execution; the project owner should still confirm this reading before H1 is adopted. If it is not accepted, the compliant alternative is operational rather than a new trial: compute the signal at the close from live CMC data published just after 00:00 and fill at about +1h. Its backtest is the existing `--fill-hours 1` run, and it needs only an audit that the live data reproduce the historical daily snapshot.

### H2. Ensemble of BTC gate windows

**Question.** Does the champion survive when the gate's window, its most fragile parameter, is averaged over the windows already tested instead of fixed at the peak?

**Rule.** Replace the single MA100 gate with the equal-weight average of four gates. Gate k is on when BTC's close is at or above its w_k-day simple moving average, with the champion's 2-day confirmation, for w_k in {50, 100, 150, 200}. Gate exposure g(D) = (number of gates on) / 4, one of 0, 0.25, 0.5, 0.75 or 1. Each sleeve's target weight is g(D) x min(1, 0.80 / sigma60). When g(D) = 0 the sleeves go to cash with the champion's risk-off reset (re-entry at rank 1 once g > 0); otherwise selection runs exactly as in the champion.

**Parameters and their sources.** The window set is exactly the set of gate windows already in the champion's neighbourhood (`parameter_neighborhood.csv`); no window is added or removed. Equal weights follow the ensemble construction of [S17] and the project's finding that fixed equal-weight ensembles are more stable out of sample than choosing a parameter (RESEARCH.md section 0.6). The confirmation rule is the champion's.

**Rationale.** Market-level trend is the most robust crypto momentum evidence ([S4]), but no source fixes a window: 28 days in [S4], 50/200 crossovers in [S18], 5-360 days in [S17], 65 days for BTC in Le and Ruthbah (secondary). With neighbours at 41-50% of the MA100 result, the headline depends on one narrow value, which AGENTS.md rules out as evidence of robustness. [S17]'s remedy for horizon uncertainty is to average across horizons.

**Expected direction.** Lower terminal wealth than the MA100 champion (likely below 20x), a smoother equity curve, and maximum drawdown no more than 2 points worse. Sensitivity to the gate window falls by construction.

**Test.** 2/20/50/100 bps; +3h fills under both policies; lag 0 and lag 1 day. Declared diagnostics: the four single-window variants rerun at +3h (already in the ledger at lag 0).

**Kill criterion.** Reject if, at 20 bps with +3h fills (worse policy), M(H2) is below the median of the four single-window variants under the same settings (the ensemble would not even diversify horizon risk), or if maximum drawdown is more than 2 points worse than the MA100 champion's. If H2 passes but stays below 20x, record it as a risk variant and state in RESEARCH.md that the champion's 20x depends on the MA100 window. Pre-declared neighbourhood if it passes: the four leave-one-window-out ensembles.

### H3. Top20 breadth co-gate, 50/50 blend

**Question.** Does the drawdown reduction seen in RESEARCH.md section 0.8 carry over to the champion?

**Rule.** Exactly the section 0.8 specification. Breadth(D) is the share of the point-in-time Top20 on D whose close is above its own 50-day simple moving average, computed by `_breadth_signal` in `scripts/run_momentum_event_breadth_overlay.py` (coins without 50 days of history count as not above). Book A is the champion. Book B is the champion with an extra risk-on condition, breadth(D) >= 0.50; when the condition fails, book B's sleeves go to cash with the risk-off reset. The portfolio is 50% A and 50% B, rebalanced to 50/50 daily as in section 0.8.

**Parameters and their sources.** The 50-day average, the 0.50 threshold and the 50/50 mix come unchanged from the section 0.8 in-project ablation, run there on the event ensemble. Disclosure: section 0.8 picked them from a five-point threshold grid (0.40-0.60) and a three-point mix grid (25/50/75); those trials are already in the ledger. No new values are tried here.

**Rationale.** Crypto time-series momentum pays in bull phases and coins move together ([S4]); breadth is the cross-sectional reading of that state, and the gross exposure of a diversified top-20 trend book is essentially the share of coins in uptrends ([S17]). In section 0.8 the 50/50 mix cut maximum drawdown from -46.2% to -36.0% and raised Sharpe from 1.434 to 1.867 at 2 bps, at the cost of terminal wealth (28.92x to 23.10x). No external source tests a breadth gate in crypto, so this is the hypothesis with the weakest outside support.

**Expected direction.** Maximum drawdown at least 5 points better, higher Sharpe, lower terminal wealth.

**Test.** 2/20/50/100 bps; +3h fills under both policies; lag 0 and lag 1 day; yearly, regime, best-year-removed and one-year rolling results.

**Kill criterion.** Reject unless, at 20 bps with +3h fills (worse policy), all three hold: maximum drawdown improves by at least 5 percentage points, Sharpe is higher than B's, and the one-year rolling worst multiple is higher than B's. A pass below 20x is a recorded risk variant. Pre-declared neighbourhood if it passes: thresholds 0.45 and 0.55 (the adjacent section 0.8 grid points).

### H4. Top-quintile sleeves

**Question.** Does holding the academic "winner" portfolio (the top quintile) in each sleeve, instead of one coin, reduce single-coin drawdown and latency sensitivity at an acceptable cost in return?

**Rule.** In every sleeve the target set at each scheduled check is the top 4 coins by that sleeve's signal (4 is one quintile of a 20-coin universe). An incumbent is kept while it ranks in the top 8 (the top two quintiles); empty slots are filled from the highest-ranked coins not already held. Each held coin receives 1/4 of the sleeve's capital times min(1, 0.80 / its 60-day realised volatility). A coin that leaves the day's Top20 is sold at once and its slot refilled from the ranking immediately, as the champion does after a Top20 exit. Gate, phases, 3-day checks, costs and the cap of 1 are unchanged.

**Parameters and their sources.** N = 4 applies the top-quintile convention of cross-sectional crypto momentum studies ([S2] and [S4] quintile sorts; [S14] quintile sorts inside the 30 largest coins) to 20 coins. [S4]'s top-5% subset used a median split instead; that alternative (10 coins) is not tested here. The hold band of the top two quintiles keeps the champion's 1:2 ratio between entry rank and hold rank; that ratio is an in-project choice and itself sits on a narrow peak (section 3.2), which is disclosed here.

**Rationale.** A single coin can decide a large-cap momentum book ([S14]) and momentum payoffs may come from temporarily tradable coins ([S16]); trend-following Sharpe ratios in crypto peak with ten or more coins ([S17], [S18]). The momentum profit sits among the top winners of large coins ([S2], [S4]), so the top quintile keeps the source of return while spreading single-coin risk. A switch now moves a quarter of a sleeve, and the name that just jumped (the most latency-sensitive trade, [S5], [S30]) is one of four holdings, so D3h and D1d should move closer to 1.

**Expected direction.** Lower maximum drawdown, delay ratios closer to 1, lower terminal wealth.

**Test.** 2/20/50/100 bps; +3h fills under both policies; lag 0 and lag 1 day (for D3h and D1d); turnover; entrant attribution.

**Kill criterion.** Reject unless, at 20 bps with +3h fills (worse policy), maximum drawdown improves by at least 5 percentage points and D1d is above the champion's 0.52. A pass below 20x is recorded as a risk variant, and RESEARCH.md should then describe the champion's one-coin sleeves as trading robustness for return. Pre-declared neighbourhood if it passes: N = 3 with a top-6 band and N = 5 with a top-10 band.

### H5. Cross-sectional dispersion overlay

**Question.** Cross-sectional dispersion predicts momentum breakdowns better than market volatility in crypto; does scaling the book down while dispersion sits above its own recent quantile cut drawdown and lift Sharpe without giving up the 20x return?

**Rule.** Keep every champion and H3 rule and multiply each sleeve's target weight by
`dispersion_factor(D) = min(1, rolling 252-day P75 of dispersion / dispersion(D))`, where `dispersion(D)` is
the cross-sectional standard deviation (ddof = 1) of the point-in-time Top20's trailing 21-day returns on
day D; a day with fewer than five usable members has no reading and leaves the factor at 1. The registered
primary construction is the H3 blend (champion + Top20 breadth co-gate at 0.50, mixed 50/50 at the target
level) with the overlay applied to both books, so H5 is a change to the then-frozen specification rather
than to the champion alone. Gross exposure still caps at 1: the overlay can only de-risk.

**Parameters and their sources.** Mechanism: Makgolo and Zhang (2026), "Cross-Sectional Dispersion and the
State Dependence of Cryptocurrency Momentum", SSRN 6648082 - dispersion predicts momentum breakdowns better
than BTC volatility, and a dispersion-scaled book cut maximum drawdown from -42.5% to -17.1% (Sharpe 0.63 to
0.80). The paper's exact scaling function could not be read (SSRN blocks the full text), so the
`min(1, rolling-percentile / current)` form is the in-project analogue of the volatility target the champion
already uses. 21 days is the project's shortest documented momentum horizon; 252 days and the 0.75 target are
in-project choices fixed before running, on the screening in `RESEARCH.md` section 00.12.

**Rationale.** Section 3.5's volatility scaling reacts to each coin's own volatility. The cross-sectional
co-movement of returns is a different state variable. The screening in `RESEARCH.md` section 00.12 found the
top dispersion quintile of the point-in-time Top20 earns -0.17% over the following 21 days against +6.11% for
the other four quintiles (Spearman -0.196), and inverse-dispersion scaling was the only screened overlay that
kept 20x at 20 bps while lifting Sharpe.

**Expected direction.** Lower maximum drawdown and a higher Sharpe, at or slightly below the H3 return.

**Test.** 2/20/50/100 bps; +3h fills under both missing-candle policies; lag 0 and lag 1 day; turnover (the
overlay's extra turnover must be charged, unlike the screening); entrant attribution; the 2020-10 to 2021-12
stress window; the bull/non-bull split.

**Kill criterion.** Reject unless, at 20 bps with +3h fills (worse policy), all hold: MDD(H5) - MDD(B) >=
0.05, Sharpe(H5) > Sharpe(H3), and the one-year rolling worst multiple is above H3's. The same verdict is
required at 2 and 50 bps. A pass below 20x is recorded as a risk variant. Pre-declared neighbourhood if it
passes: the dispersion-target percentiles 0.60 and 0.90.

**Deviation stated before running.** The section 00.12 screening applied the overlay to H3's daily returns
without charging its extra turnover; this run charges everything through the production engine at the target
event. The screening also only ever saw the blend, so "overlay on both books" is an in-project choice
disclosed here rather than a screened result.

### 4.5 Trial budget

| Item | Runs | Counted as |
|---|---:|---|
| H1-H4 primary runs | 4 | new trials (N rises from 6,119 to 6,123) |
| H5 primary run (added 2026-10-08, registered before running) | 1 | new trial (N 6,132 -> 6,133; H5's own neighbourhood adds 2 more after its pass) |
| Cost and fill-policy repeats (2/20/50/100 bps x 2 policies, lag 0 and lag 1d) | per hypothesis | the same trial at different stress settings |
| Declared diagnostic runs: H1 (i) and the four H2 single-window reruns at +3h. H1 (ii) and (iii) are statistics of the H1 run, not extra runs | 5 | logged, never promotable |
| Pre-declared neighbourhoods (only after a pass) | at most 4 (H2) + 2 (H3) + 2 (H4) + 2 (H5) | new trials, logged before running |

---

## 5. Rejected ideas

| Idea | Source(s) | Reason |
|---|---|---|
| Replicate results from Top50, Top100 or all-coin universes (including [S17]'s 30-50 coin portfolios) | [S2], [S4], [S5], [S7], [S17] | Out of scope: AGENTS.md forbids any universe other than point-in-time Top20, even as a diagnostic. Only the large-coin parts of these studies are used, and only as direction. |
| Long-short momentum, shorting losers or shorting BTC | [S2], [S4], [S14], [S20], [S21] | Out of scope (no shorting). [S4] also finds short legs lose money in crypto. |
| Volatility scaling above 1 in calm periods (the return-enhancing half of risk management) | [S20], [S22], [S25], [S17] (200% cap) | Out of scope (gross exposure <= 1). Only the de-risking half is available, and the champion already has it. |
| Futures, perpetual funding or basis trades, or derivative hedges | none needed | Out of scope (derivatives). |
| Intraday strategies: first-half-hour momentum, overreaction-day trading, intraday timing, 6-hour trend following | [S30], [S31], [S32], arXiv:2602.11708 | Out of scope (intraday trading). Intraday data are used only to time the daily execution (H1). |
| Picking the "best" execution hour by backtest (+1h to +23h) | [S33], [S31] | No persistent hour-of-day return effect to motivate it; a 23-way search is pure multiple testing. |
| Skipping the most recent day in the look-back | [S4], [S14] | Contradicted for the largest coins, which show daily momentum ([S5]). In Top20 it amounts to adding signal latency, which the lag study shows is costly. |
| Short-term reversal or contrarian selection | [S10], [S5] (headline) | The daily reversal is an illiquidity effect in small coins ([S5]); the largest coins show momentum. [S10]'s sample ends before 2018 and uses Top100. |
| Further stop-loss variants (fixed, trailing, ATR, Donchian-midpoint) | [S26], [S28], [S29], [S17] | None of the 10 fixed and trailing stop variants in the champion's neighbourhood beat it on return, Sharpe and drawdown together (section 3.6); the supportive evidence depends on short legs or intraday fills ([S28]) or gives no transferable parameter ([S29]). |
| Coin-level absolute trend filters ("dual momentum" per coin) | [S17] | Project ablation: 10.57x-17.57x against 23.09x. Not reopened. |
| A second, strategy-level volatility target on top of per-sleeve scaling | [S20], [S14], [S23] | With a cap of 1 and per-sleeve scaling already in place it could only de-risk further; the target would be a free parameter; [S23] finds such overlays fail out of sample in equities. |
| Switching to 1-day checks (the 27.92x neighbour) or raising the volatility target to 0.9-1.0 (26-30x) | project neighbourhood | Post-hoc choice of already-tested neighbours. The higher targets buy return with drawdown (-48% to -51%) on a monotone frontier; that is risk, not an edge. |
| MAX-return or factor-momentum selection signals | [S6], [S7] | Broad-universe evidence; a new signal family would add selection risk the project has already documented (section 0.5). |
| Volume or attention filters on winners | [S4], [S13], [S17] | Conflicting evidence ([S4]: high-volume winners underperform; [S13]: liquid winners do best); would need a new data dimension and new parameters. |
| Machine-learning forecasters (transformers, LSTM, reinforcement learning, sentiment) | arXiv query results | No transparent rule, very high multiple-testing cost, no Top20 evidence. |
| On-chain flow signals | arXiv:2411.06327 | Non-price data, intraday horizon, single-asset evidence. |
| Other breadth thresholds or mixes than 0.50 and 50/50 | RESEARCH.md section 0.8 | Already swept; re-sweeping would be selection. |
| Seasoning filter for new entrants (for example [S17]'s 365-day listing age) | [S16], [S17] | Deferred. Run the entrant attribution in section 4.0 first: if entrants carry the return, a seasoning filter removes the return source; if they do not, the filter is moot. |

---

## 6. Evidence index

Local evidence lives in `/tmp/smart-search-evidence/atlas20-research/` (JSON from `smart-search fetch`, `content` field). It is outside the repository and may be cleaned up; the public URLs in section 2 are the durable references.

| Source | Evidence file(s) | What was read |
|---|---|---|
| S1 | `02-liu-tsyvinski-2021-nber-pdf.json`, `02-liu-tsyvinski-2021-nber.json` | full working paper, NBER page |
| S2 | `02-liu-tsyvinski-wu-2022-nber-pdf.json`, `02-liu-tsyvinski-wu-2022-nber.json` | full working paper, NBER page |
| S3 | `02-dobrynskaya-2023-hse.json`, `02-dobrynskaya-2023-pmr.json` | abstract |
| S4 | `02-han-kang-ryu-2024-acfr-pdf.json`, `disc-ddg-han-kang-ryu.json` | full text |
| S5 | `02-zaremba-2021-upordown-repec.json`, `02-dobrynskaya-2023-openalex.json` | abstract |
| S6 | `02-li-urquhart-2021-max-momentum-repec.json` | abstract |
| S7 | `02-fieberg-2023-factor-momentum-repec.json` | abstract |
| S8 | `02-jia-goodell-shen-2022-repec.json` | abstract |
| S9 | `02-grobys-sapkota-2019-repec.json` | abstract |
| S10 | `02-kosc-2019-repec.json` | abstract |
| S11 | `02-tzouvanas-2020-repec.json` | abstract |
| S12 | `02-borgards-2021-repec.json` | abstract |
| S13 | `arxiv-abstracts-1.xml`, `arxiv-crypto-momentum.xml` | abstract |
| S14 | `03-grobys-2025-moments-fulltext.json` | full text |
| S15 | `03-grobys-illusion-openalex.json` | abstract |
| S16 | `03-grobys-survivor-openalex.json` | abstract and highlights |
| S17 | `01-zarattini2025-fulltext-pdf.json`, `01-zarattini2025-repec.json` | full text |
| S18 | `01-man-ahl-2024-in-crypto-we-trend.json` | full article |
| S19 | `arxiv-crypto-trend.xml` | abstract |
| S20 | `03-barroso-santaclara-2015-repec.json` | abstract |
| S21 | `03-daniel-moskowitz-2016-repec.json` | abstract |
| S22 | `03-moreira-muir-2017-nber.json`, `03-moreira-muir-2017-repec.json` | abstract |
| S23 | `03-cederburg-2020-repec.json` | abstract |
| S24 | `03-harvey-2018-vol-targeting-man.json`, `disc-ddg-03-harvey-2018-vol-targeting-repec.json` | Man summary |
| S25 | `03-yang-2025-risk-managed-crypto-momentum-repec.json` | abstract |
| S26 | `04-kaminski-lo-2014-repec.json` | abstract |
| S27 | `04-lo-remorov-2017-openalex.json`, `07-lo-remorov-2017-sd.json` | metadata only |
| S28 | `04-han-zhou-zhu-2016-cicf-pdf.json` | full text |
| S29 | `04-sadaqat-butt-2023-repec.json`, `04-sadaqat-butt-2023-iba.json` | abstract |
| S30 | `02-caporale-plastun-2020-repec.json` | abstract |
| S31 | `06-wen-2022-intraday-repec.json` | abstract |
| S32 | `07-shen-urquhart-wang-2022-reading-pdf.json`, `disc-ddg-06-shen-urquhart-wang-2022-repec.json` | abstract and data tables |
| S33 | `08-baur-2019.json` | abstract |
| S34 | `arxiv-crypto-intraday.xml` | abstract |
| S35 | `arxiv-abstracts-1.xml` | abstract |
| S36 | `08-novymarx-velikov-2016.json` | abstract |

Fetch pattern used for new evidence: `smart-search fetch <url> --format json --output <file>` (with the retry wrapper `tools/fr.sh`), IDEAS/RePEc pages located through DuckDuckGo HTML results (`tools/ideas.sh`), and OpenAlex title search (`tools/oat.sh`). From mid-session the fetch provider returned empty content for every URL; the affected references are marked in section 2.6.
