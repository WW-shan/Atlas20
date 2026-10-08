from __future__ import annotations

import pandas as pd
import pytest

import scripts.run_tsmom_validation as tsmom_validation
from atlas20.config import load_config
from atlas20.universe.builder import MarketDataBundle


def _market() -> MarketDataBundle:
    dates = pd.date_range("2022-01-01", periods=40, freq="D")
    price = pd.DataFrame({"bitcoin": 100.0, "ethereum": 50.0}, index=dates)
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000,
        volume=pd.DataFrame(1_000_000.0, index=dates, columns=price.columns),
        history_count=price.notna().cumsum(),
        metadata=pd.DataFrame({"sector": {"bitcoin": "L1", "ethereum": "L1"}}),
    )


def test_tsmom_grid_is_top20_only() -> None:
    # AGENTS.md: "Top 20 only is a non-negotiable project constraint ... Never
    # run or evaluate Top 50".  The legacy grid looped over (20, 50), so 720 of
    # its 1440 candidates ran on Top50 and competed for the validation slots.
    bases = tsmom_validation._build_base_specs()
    overlays = tsmom_validation._build_overlay_specs()

    assert {base.universe_size for base in bases} == {20}
    assert all(base.base_id.startswith("tsmom_u20__") for base in bases)
    assert len(bases) * len(overlays) == 720


def test_tsmom_base_spec_rejects_non_top20_universe() -> None:
    with pytest.raises(ValueError, match="Top20"):
        tsmom_validation.TSMOMBaseSpec(
            base_id="tsmom_u50__probe",
            universe_size=50,
            lookback=30,
            frequency="7D",
            top_n=1,
            score_family="tsmom",
            weighting="equal",
        )


def test_tsmom_universe_is_built_for_top20_only(monkeypatch: pytest.MonkeyPatch) -> None:
    built_sizes: list[int] = []

    def _fake_build(market: MarketDataBundle, dates: list[pd.Timestamp], config: object) -> pd.DataFrame:
        built_sizes.append(int(config.universe.universe_size))  # type: ignore[attr-defined]
        return pd.DataFrame({"rebalance_date": dates[:1], "coin_id": ["bitcoin"]})

    monkeypatch.setattr(tsmom_validation, "build_rebalance_universe", _fake_build)
    config = load_config("config/base.yaml").model_copy(deep=True)
    config.start_date = "2022-01-08"

    universes, _ = tsmom_validation._universe_variants(_market(), config)

    assert built_sizes == [20]
    assert set(universes) == {20}


def test_tsmom_universe_rejects_non_top20_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tsmom_validation,
        "build_rebalance_universe",
        lambda *args, **kwargs: pytest.fail("a non-Top20 universe must never be built"),
    )
    config = load_config("config/base.yaml").model_copy(deep=True)
    config.universe.universe_size = 50

    with pytest.raises(ValueError, match="Top20"):
        tsmom_validation._universe_variants(_market(), config)
