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
