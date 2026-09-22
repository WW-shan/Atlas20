from __future__ import annotations

import pandas as pd
import pytest

from atlas20.config import load_config
from atlas20.strategies.tsmom import TSMOMSettings, build_tsmom_targets
from atlas20.universe.builder import MarketDataBundle


def _market() -> MarketDataBundle:
    dates = pd.date_range("2024-01-01", periods=220, freq="D")
    price = pd.DataFrame(
        {
            "bitcoin": [100.0 * (1.002**i) for i in range(220)],
            "ethereum": [80.0 * (1.004**i) for i in range(220)],
            "downcoin": [50.0 * (0.995**i) for i in range(220)],
            "flatcoin": [10.0 for _ in range(220)],
        },
        index=dates,
    )
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000,
        volume=pd.DataFrame(1_000_000.0, index=dates, columns=price.columns),
        history_count=price.notna().cumsum(),
        metadata=pd.DataFrame(index=price.columns),
    )


def _universe() -> pd.DataFrame:
    dates = pd.date_range("2024-06-01", periods=8, freq="14D")
    rows = []
    for date in dates:
        for rank, coin_id in enumerate(["ethereum", "bitcoin", "downcoin", "flatcoin"], start=1):
            rows.append(
                {
                    "rebalance_date": date,
                    "coin_id": coin_id,
                    "universe_rank": rank,
                    "price": 1.0,
                    "market_cap": 1_000_000.0 / rank,
                    "volume_usd": 1_000_000.0,
                    "history_days": 200,
                    "symbol": coin_id.upper(),
                    "name": coin_id,
                    "sector": "Test",
                }
            )
    return pd.DataFrame(rows)


def _config():
    config = load_config("config/base.yaml")
    config.start_date = "2024-06-01"
    config.end_date = "2024-09-01"
    config.rebalancing.frequencies["14D"] = "14D"
    return config


def test_tsmom_gates_out_negative_trend_assets() -> None:
    result = build_tsmom_targets(
        _market(),
        _universe(),
        _config(),
        top_n=None,
        settings=TSMOMSettings(lookback=90, weighting="equal"),
    )

    for target in result.targets.values():
        assert "downcoin" not in target.index
        assert "flatcoin" not in target.index
        assert target.sum() == pytest.approx(1.0)
        assert (target >= 0.0).all()


def test_tsmom_selects_strongest_own_trend() -> None:
    result = build_tsmom_targets(
        _market(),
        _universe(),
        _config(),
        top_n=1,
        settings=TSMOMSettings(lookback=90, weighting="equal"),
    )

    nonempty = [target for target in result.targets.values() if not target.empty]
    assert nonempty
    assert all(target.index[0] == "ethereum" for target in nonempty)
    assert result.selection_history["coin_id"].dropna().eq("ethereum").any()


def test_tsmom_caps_weights_without_leverage() -> None:
    result = build_tsmom_targets(
        _market(),
        _universe(),
        _config(),
        top_n=None,
        settings=TSMOMSettings(lookback=90, weighting="inverse_vol", max_weight=0.40),
    )

    for target in result.targets.values():
        assert target.sum() <= 1.0 + 1e-12
        assert (target <= 0.40 + 1e-12).all()


def test_tsmom_unknown_family_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown TSMOM score_family"):
        build_tsmom_targets(
            _market(),
            _universe(),
            _config(),
            settings=TSMOMSettings(score_family="not-a-factor"),
        )
