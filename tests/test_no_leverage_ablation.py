from __future__ import annotations

import pandas as pd
import pytest

from atlas20.config import load_config
from atlas20.universe.builder import MarketDataBundle
from scripts.run_no_leverage_ablation import (
    BASE_SPECS,
    OVERLAY_SPECS,
    _calendar_period_return,
    _friction_for_spec,
    _scaled_exposure_for_targets,
    _universe_rebalance_dates,
)


def _market(price: pd.DataFrame) -> MarketDataBundle:
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000,
        volume=pd.DataFrame(1_000_000.0, index=price.index, columns=price.columns),
        history_count=price.notna().cumsum(),
        metadata=pd.DataFrame({"sector": {column: "Other" for column in price.columns}}),
    )


def test_calendar_period_return_stops_at_period_end() -> None:
    returns = pd.Series(
        [0.10, 0.10, 0.10],
        index=pd.to_datetime(["2021-12-30", "2021-12-31", "2022-01-01"]),
    )

    value = _calendar_period_return(returns, "2021-01-01", "2021-12-31")

    assert value == pytest.approx(0.21)


def test_volatility_overlay_can_only_de_risk() -> None:
    dates = pd.date_range("2024-01-01", periods=90, freq="D")
    price = pd.DataFrame(
        {"a": [100.0 * (1.001 ** i) for i in range(90)]},
        index=dates,
    )
    market = _market(price)

    exposure = _scaled_exposure_for_targets(
        {dates[60]: pd.Series({"a": 1.0})},
        market,
        overlay=type("Overlay", (), {"target_volatility": 10.0, "vol_window": 30})(),
    )

    assert exposure is not None
    assert exposure[dates[60]] == pytest.approx(1.0)


def test_concentrated_ablation_spec_disables_diversification_caps() -> None:
    config = load_config("config/base.yaml")
    spec = next(item for item in BASE_SPECS if item.base_id == "CTREND_balanced_top1")

    friction = _friction_for_spec(config, spec)

    assert friction.max_weight_per_coin == 1.0
    assert friction.max_weight_per_sector == 1.0


def test_ablation_grid_has_unique_ids_and_high_volatility_controls() -> None:
    base_ids = [spec.base_id for spec in BASE_SPECS]
    overlay_ids = [overlay.overlay_id for overlay in OVERLAY_SPECS]

    assert len(base_ids) == len(set(base_ids))
    assert len(overlay_ids) == len(set(overlay_ids))
    assert {"vol80", "vol100"}.issubset(overlay_ids)


def _schedule_market() -> MarketDataBundle:
    dates = pd.date_range("2022-01-01", "2022-06-30", freq="D")
    price = pd.DataFrame(
        {coin: [100.0 + i for i in range(len(dates))] for coin in ("bitcoin", "ethereum", "solana")},
        index=dates,
    )
    return _market(price)


def _schedule_config():
    config = load_config("config/base.yaml").model_copy(deep=True)
    config.start_date = "2022-01-01"
    config.end_date = "2022-06-30"
    return config


def _strategy_dates(market: MarketDataBundle, config) -> set[pd.Timestamp]:
    from atlas20.backtest.calendar import get_rebalance_dates

    dates: set[pd.Timestamp] = set()
    for spec in BASE_SPECS:
        if spec.family == "benchmark":
            continue
        value = config.rebalancing.frequencies.get(spec.frequency, spec.frequency)
        dates.update(get_rebalance_dates(market.price.index, config.start_timestamp, spec.frequency, value))
    return dates


def test_universe_dates_cover_every_strategy_rebalance_date() -> None:
    # Legacy bug: month_end was dropped from the universe schedule, so the
    # monthly bases (TOP20_EQ_bull, TOP20_MOM_top6_monthly_bull,
    # TOP20_SECTOR_top3_monthly_bull) found no snapshot on 48 of 56
    # month-ends and sat in cash (average gross 0.035 vs 0.45 biweekly).
    market = _schedule_market()
    config = _schedule_config()

    dates = set(_universe_rebalance_dates(market, config))

    month_ends = {date for date in market.price.index if date.is_month_end}
    assert month_ends <= dates
    assert _strategy_dates(market, config) <= dates


def test_ablation_universe_fails_when_a_rebalance_date_has_no_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.run_no_leverage_ablation as ablation

    market = _schedule_market()
    config = _schedule_config()
    dropped = pd.Timestamp("2022-03-31")

    def fake_build(market: MarketDataBundle, dates: list[pd.Timestamp], config: object) -> pd.DataFrame:
        kept = [date for date in dates if date != dropped]
        return pd.DataFrame({"rebalance_date": kept, "coin_id": ["bitcoin"] * len(kept)})

    monkeypatch.setattr(ablation, "build_rebalance_universe", fake_build)

    with pytest.raises(ValueError, match="2022-03-31"):
        ablation.build_ablation_universe(market, config)


def test_ablation_universe_covers_monthly_bases(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.run_no_leverage_ablation as ablation

    market = _schedule_market()
    config = _schedule_config()

    def fake_build(market: MarketDataBundle, dates: list[pd.Timestamp], config: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"rebalance_date": date, "coin_id": coin, "market_cap": 1.0, "universe_rank": rank}
                for date in dates
                for rank, coin in enumerate(("bitcoin", "ethereum", "solana"), start=1)
            ]
        )

    monkeypatch.setattr(ablation, "build_rebalance_universe", fake_build)
    universe = ablation.build_ablation_universe(market, config)
    regime = pd.DataFrame({"bull": True}, index=market.price.index)
    spec = next(item for item in BASE_SPECS if item.base_id == "TOP20_EQ_bull")

    targets = ablation.build_base_targets(spec, market, universe, regime, config)

    month_ends = [date for date in market.price.index if date.is_month_end]
    assert set(month_ends) <= set(targets)
    assert all(abs(float(targets[date].sum()) - 1.0) < 1e-12 for date in month_ends)
