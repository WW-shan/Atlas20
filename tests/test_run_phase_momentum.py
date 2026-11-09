from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

from atlas20.backtest.engine import run_backtest
from atlas20.config import load_config
from atlas20.strategies.implementations import StrategyDefinition, build_rebalance_targets
from atlas20.strategies.phase_momentum import MomentumSignalSpec, PhaseMomentumSpec
from atlas20.universe.builder import MarketDataBundle
from scripts import run_phase_momentum, run_phase_momentum_robustness
from scripts.run_phase_momentum import _monthly_start_sensitivity


def _market(price: pd.DataFrame) -> MarketDataBundle:
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000.0,
        volume=pd.DataFrame(1_000_000.0, index=price.index, columns=price.columns),
        history_count=pd.DataFrame(200, index=price.index, columns=price.columns),
        metadata=pd.DataFrame({"sector": ["Other"] * len(price.columns)}, index=price.columns),
    )


def test_monthly_start_rebuilds_the_strategy_from_each_start() -> None:
    dates = pd.date_range("2024-01-01", periods=200, freq="D")
    price = pd.DataFrame(
        {"a": 100.0 * 1.01 ** np.arange(len(dates)), "bitcoin": [100.0] * len(dates)},
        index=dates,
    )
    universe = pd.DataFrame({"rebalance_date": dates, "coin_id": "a"})
    spec = PhaseMomentumSpec(
        rebalance_days=1,
        phase_offsets=(0,),
        btc_ma_window=2,
        btc_confirm_days=1,
        target_volatility=10.0,
        vol_window=2,
    )

    table = _monthly_start_sensitivity(
        load_config("config/base.yaml"),
        _market(price),
        universe,
        dates,
        cost_bps=0.0,
        spec=spec,
        signal_specs=(MomentumSignalSpec(name="one_day", window_weights=((1, 1.0),)),),
    )

    march = table.set_index("start").loc[pd.Timestamp("2024-03-01")]
    slice_days = int((dates >= pd.Timestamp("2024-03-01")).sum())
    # Invested from the day after the start rather than parked in cash until
    # an event that the 2024-01-01 build never produces again.
    assert march["multiple"] == pytest.approx(1.01 ** (slice_days - 1), rel=1e-9)


@pytest.mark.parametrize("entrypoint", ["report", "headline", "stress"])
def test_btc_benchmark_excludes_the_return_before_the_window(
    entrypoint: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dates = pd.date_range("2021-12-31", "2022-01-03", freq="D")
    market = _market(pd.DataFrame({"bitcoin": [100.0, 110.0, 121.0, 121.0]}, index=dates))
    original_returns = market.returns.copy(deep=True)
    index = dates[1:]
    config = load_config("config/base.yaml").model_copy(deep=True)
    config.start_date, config.end_date = "2022-01-01", "2022-01-03"
    config.frictions = config.frictions.model_copy(update={
        "fee_bps": 0.0, "slippage_bps": 0.0,
        "max_weight_per_coin": 1.0, "max_weight_per_sector": 1.0,
    })
    universe = pd.DataFrame(columns=["rebalance_date", "coin_id", "sector"])
    strategy = StrategyDefinition(
        "BTC_BH__always_on", "benchmark", "monthly", "always_on", {"coin_id": "bitcoin"}
    )
    targets, _ = build_rebalance_targets(
        strategy, market, universe, pd.DataFrame(index=dates), config
    )
    expected = run_backtest(
        "BTC", market.returns.loc[index], targets, market.metadata["sector"],
        config.frictions, 1.0,
    )
    assert (1.0 + market.returns.loc[index, "bitcoin"]).prod() == pytest.approx(1.21)
    assert expected.equity_curve.iloc[-1] == pytest.approx(1.10)

    module = run_phase_momentum if entrypoint == "report" else run_phase_momentum_robustness
    monkeypatch.setattr(module, "_load_market", lambda *args, **kwargs: (config, market, universe, index))
    argv = ["report", "--start-date", "2022-01-01", "--end-date", "2022-01-03",
            "--output-dir", str(tmp_path / "report")]
    if entrypoint == "report":
        argv += ["--cost-bps", "0"]
    else:
        candidates = tmp_path / "candidates.csv"
        pd.DataFrame({"primary": 0.0, module.PARAMETER_ENSEMBLE_COLUMN: 0.0}, index=index).to_csv(
            candidates, index_label="date"
        )
        argv += ["--candidate-returns", str(candidates), "--stress-start-date", "2022-01-01",
                 "--stress-end-date", "2022-01-03", "--stress-cost-bps", "0"]
    monkeypatch.setattr(sys, "argv", argv)

    def check_btc(returns: pd.Series) -> None:
        assert (1.0 + returns).prod() == pytest.approx(1.10)
        pd.testing.assert_series_equal(returns, expected.daily_returns, check_names=False)
        raise RuntimeError("BTC checked")

    if entrypoint == "headline":
        monkeypatch.setattr(module, "_best_year_removal", lambda headline: check_btc(headline["BTC"]))
    else:
        original_summary = module._summary_row

        def summary(strategy: str, returns: pd.Series, **kwargs: object) -> dict[str, object]:
            if strategy == "BTC":
                check_btc(returns)
            return original_summary(strategy, returns, **kwargs)

        monkeypatch.setattr(module, "_summary_row", summary)

    with pytest.raises(RuntimeError, match="BTC checked"):
        module.main()
    pd.testing.assert_frame_equal(market.returns, original_returns)
