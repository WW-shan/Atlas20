"""Opt-in rules for the 2026-10 pre-registered hypotheses (H2, H3, H4).

The literature review (docs/research/literature_review_2026-09.md, section 4)
fixes the rules; these tests pin them on small synthetic markets and prove the
champion's default path is untouched.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from atlas20.signals.risk import btc_above_moving_average, realized_volatility
from atlas20.strategies.phase_momentum import (
    PRIMARY_SIGNAL_SPECS,
    PhaseMomentumSpec,
    SleeveTargets,
    aggregate_sleeve_targets,
    build_parameter_ensemble_targets,
    build_phase_momentum_targets,
    build_sleeve_targets,
    parameter_ensemble_sleeve_weights,
)
from atlas20.universe.builder import MarketDataBundle


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


def _universe(rows: list[tuple[pd.Timestamp, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["rebalance_date", "coin_id"])


def _synthetic_market() -> tuple[MarketDataBundle, pd.DataFrame, pd.DatetimeIndex]:
    """A deterministic 300-day market with gate flips, vol differences and Top20 exits."""
    rng = np.random.default_rng(20261001)
    dates = pd.date_range("2023-01-01", periods=300, freq="D")
    coins = ["bitcoin", "c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"]
    drift = np.where(np.arange(len(dates)) < 150, 0.004, -0.004)
    columns = {}
    for position, coin in enumerate(coins):
        scale = 0.02 + 0.01 * position
        shocks = rng.normal(0.0, scale, len(dates))
        columns[coin] = 100.0 * np.exp(np.cumsum(drift + shocks))
    price = pd.DataFrame(columns, index=dates)
    index = dates[70:]
    rows: list[tuple[pd.Timestamp, str]] = []
    for day_number, date in enumerate(index):
        for coin in coins:
            # c3 leaves the universe for ten days and c7 joins late.
            if coin == "c3" and 40 <= day_number < 50:
                continue
            if coin == "c7" and day_number < 30:
                continue
            rows.append((date, coin))
    return _market(price), _universe(rows), index


_DIGEST_DECIMALS = 9


def _digest(built) -> str:
    """Quantised digest of the default targets, exposures and selection history.

    Floats are formatted to ``_DIGEST_DECIMALS`` places before hashing. The
    pipeline is deterministic across refactors, but the last bit of a float
    depends on the CPU/architecture: macOS arm64 (the research box) and the
    Linux CI runner differ by at most 1.1e-16 on this synthetic market
    (measured 2026-10-08), and hashing raw ``repr`` turned that one-ULP
    difference into a spurious digest mismatch. Nine decimals still catches any
    real change; the held-asset sets stay exact and the history's float columns
    are quantised the same way.
    """

    def _quantised(value: float) -> str:
        return f"{float(value):.{_DIGEST_DECIMALS}f}"

    targets = [
        [str(pd.Timestamp(date).date()), [[str(asset), _quantised(weight)] for asset, weight in series.items()]]
        for date, series in sorted(built.targets.items())
    ]
    exposures = [[str(pd.Timestamp(date).date()), _quantised(value)] for date, value in sorted(built.exposures.items())]
    history_frame = built.selection_history.copy()
    for column in history_frame.columns:
        if pd.api.types.is_float_dtype(history_frame[column]):
            history_frame[column] = history_frame[column].map(
                lambda value: None if pd.isna(value) else float(f"{float(value):.{_DIGEST_DECIMALS}f}")
            )
    payload = json.dumps(
        {"targets": targets, "exposures": exposures, "history": history_frame.to_csv(index=False)}, sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# Digest of build_phase_momentum_targets(PhaseMomentumSpec()) on _synthetic_market(),
# computed with src/atlas20/strategies/phase_momentum.py *before* the opt-in fields
# were added (working tree of 2026-09-25, md5 1ed7313b65cb785075f646c35d5cedf2),
# re-quantised to 9 decimals so it is stable across CPU architectures.
DEFAULT_TARGETS_DIGEST = "f745bcbbdf3ade50af26d972ccb7155096f2dffc380c6419b33d25ed03c28c23"


def test_default_targets_match_the_pre_change_champion() -> None:
    market, universe, index = _synthetic_market()

    built = build_phase_momentum_targets(market, universe, index, spec=PhaseMomentumSpec())

    assert len(built.targets) > 20
    assert _digest(built) == DEFAULT_TARGETS_DIGEST


def test_explicit_default_opt_in_values_leave_the_targets_unchanged() -> None:
    market, universe, index = _synthetic_market()
    explicit = PhaseMomentumSpec(
        btc_ma_windows=None,
        holdings_per_sleeve=1,
        breadth_threshold=None,
        breadth_ma_window=50,
    )

    assert explicit == PhaseMomentumSpec()
    built = build_phase_momentum_targets(market, universe, index, spec=explicit)
    assert _digest(built) == DEFAULT_TARGETS_DIGEST


# --------------------------------------------------------------------------- H2


def _gate_market() -> tuple[MarketDataBundle, pd.DataFrame, pd.DatetimeIndex]:
    dates = pd.date_range("2024-01-01", periods=16, freq="D")
    btc = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 103.0, 101.0, 99.0, 97.0, 95.0, 99.0, 104.0, 108.0, 112.0, 116.0]
    price = pd.DataFrame(
        {
            "bitcoin": btc,
            "a": np.linspace(100.0, 160.0, len(dates)),
            "b": np.linspace(100.0, 130.0, len(dates)),
        },
        index=dates,
    )
    universe = _universe([(date, coin) for date in dates for coin in ("a", "b")])
    return _market(price), universe, dates


def test_gate_ensemble_exposure_is_the_share_of_confirmed_gates_that_are_on() -> None:
    # A steady rise and then a slow decline: the short averages turn first.
    dates = pd.date_range("2024-01-01", periods=45, freq="D")
    btc = [100.0 + 2.0 * day if day < 25 else 148.0 - 1.5 * (day - 24) for day in range(len(dates))]
    market = _market(
        pd.DataFrame(
            {"bitcoin": btc, "a": np.linspace(100.0, 160.0, len(dates)), "b": 100.0},
            index=dates,
        )
    )
    windows = (2, 5, 10, 20)
    spec = PhaseMomentumSpec(
        rebalance_days=1,
        phase_offsets=(0,),
        hold_rank=1,
        btc_ma_windows=windows,
        btc_confirm_days=2,
        use_volatility_target=False,
        weight_tolerance=0.0,
    )
    signal_panel = pd.DataFrame({"a": 2.0, "b": 1.0}, index=dates)

    sleeve = build_sleeve_targets(market, signal_panel, dates, spec, signal_name="s", phase_offset=0)

    expected = sum(
        btc_above_moving_average(market.price, ma_window=window, confirm_days=2)
        .reindex(dates)
        .fillna(False)
        .astype(float)
        for window in windows
    ) / len(windows)
    history = sleeve.selection_history.set_index("signal_date")
    assert set(expected.round(10)) >= {0.0, 1.0}
    assert set(expected.round(10)) & {0.25, 0.5, 0.75}
    pd.testing.assert_series_equal(
        history["target_weight"].astype(float),
        expected.astype(float),
        check_names=False,
        check_freq=False,
    )
    assert history["gate_exposure"].astype(float).round(10).tolist() == expected.round(10).tolist()


def test_gate_ensemble_multiplies_the_volatility_scaled_weight() -> None:
    gate_market, _universe_frame, dates = _gate_market()
    price = gate_market.price.copy()
    price["a"] = 100.0 * np.cumprod([1.03 if day % 2 else 0.97 for day in range(len(dates))])
    market = _market(price)
    spec = PhaseMomentumSpec(
        rebalance_days=1,
        phase_offsets=(0,),
        hold_rank=1,
        btc_ma_windows=(2, 3, 4, 5),
        btc_confirm_days=1,
        target_volatility=0.05,
        vol_window=3,
        weight_tolerance=0.0,
    )
    signal_panel = pd.DataFrame({"a": 2.0, "b": 1.0}, index=dates)

    sleeve = build_sleeve_targets(market, signal_panel, dates, spec, signal_name="s", phase_offset=0)

    history = sleeve.selection_history.set_index("signal_date")
    volatility = realized_volatility(market.price, window=3)
    checked = 0
    for date, row in history.iterrows():
        if row["selected_asset"] != "a":
            continue
        vol = float(volatility.at[date, "a"])
        if not np.isfinite(vol):
            continue
        scaled = min(1.0, 0.05 / vol) if vol > 0 else 1.0
        assert scaled < 0.2
        assert float(row["target_weight"]) == pytest.approx(float(row["gate_exposure"]) * scaled)
        checked += 1
    assert checked >= 5


def test_gate_ensemble_resets_to_cash_at_zero_and_reenters_at_rank_one() -> None:
    market, _universe_frame, dates = _gate_market()
    spec = PhaseMomentumSpec(
        rebalance_days=5,
        phase_offsets=(0,),
        hold_rank=2,
        btc_ma_windows=(2, 3),
        btc_confirm_days=1,
        use_volatility_target=False,
        weight_tolerance=0.0,
    )
    # b leads at first and a later; the incumbent b stays inside the hold band
    # until the gate closes, and re-entry takes the rank-1 coin (a) at once.
    signal_panel = pd.DataFrame(
        {"a": [1.0] * 4 + [2.0] * 12, "b": [2.0] * 4 + [1.5] * 12},
        index=dates,
    )

    sleeve = build_sleeve_targets(market, signal_panel, dates, spec, signal_name="s", phase_offset=0)

    history = sleeve.selection_history.set_index("signal_date")
    closed = history[history["gate_exposure"].astype(float) == 0.0]
    assert not closed.empty
    assert (closed["selected_asset"] == "").all()
    assert (closed["target_weight"].astype(float) == 0.0).all()
    first_closed = closed.index[0]
    reopened = history[(history.index > first_closed) & (history["gate_exposure"].astype(float) > 0.0)]
    assert not reopened.empty
    assert reopened["selected_asset"].iloc[0] == "a"
    assert sleeve.assets.loc[first_closed] == "__cash__"
    before_close = history[(history.index < first_closed) & (history["selected_asset"] != "")]
    assert (before_close["selected_asset"].iloc[-1]) == "b"


def test_gate_ensemble_fails_closed_when_btc_history_breaks_after_warm_up() -> None:
    market, _universe_frame, dates = _gate_market()
    price = market.price.copy()
    price.loc[dates[9], "bitcoin"] = np.nan
    broken = _market(price)
    spec = PhaseMomentumSpec(
        rebalance_days=1,
        phase_offsets=(0,),
        hold_rank=1,
        btc_ma_windows=(2, 3),
        btc_confirm_days=1,
        use_volatility_target=False,
    )
    signal_panel = pd.DataFrame({"a": 2.0, "b": 1.0}, index=dates)

    sleeve = build_sleeve_targets(broken, signal_panel, dates, spec, signal_name="s", phase_offset=0)

    history = sleeve.selection_history.set_index("signal_date")
    # Warm-up (no moving average yet) is open; a gap after warm-up is closed.
    assert float(history.loc[dates[0], "gate_exposure"]) == 1.0
    assert float(history.loc[dates[9], "gate_exposure"]) == 0.0
    assert history.loc[dates[9], "selected_asset"] == ""


def test_gate_windows_validation() -> None:
    with pytest.raises(ValueError):
        PhaseMomentumSpec(btc_ma_windows=())
    with pytest.raises(ValueError):
        PhaseMomentumSpec(btc_ma_windows=(50, 50))
    with pytest.raises(ValueError):
        PhaseMomentumSpec(btc_ma_windows=(1, 50))
    with pytest.raises(ValueError):
        PhaseMomentumSpec(btc_ma_windows=(50, 100), use_btc_gate=False)


# --------------------------------------------------------------------------- H4


def _ranking_market(periods: int = 12) -> tuple[MarketDataBundle, pd.DatetimeIndex]:
    dates = pd.date_range("2024-01-01", periods=periods, freq="D")
    coins = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
    price = pd.DataFrame({coin: 100.0 for coin in coins}, index=dates)
    price["bitcoin"] = 100.0
    return _market(price), dates


def _multi_spec(**overrides: object) -> PhaseMomentumSpec:
    values: dict[str, object] = {
        "rebalance_days": 3,
        "phase_offsets": (0,),
        "hold_rank": 8,
        "holdings_per_sleeve": 4,
        "btc_ma_window": 2,
        "btc_confirm_days": 1,
        "use_volatility_target": False,
    }
    values.update(overrides)
    return PhaseMomentumSpec(**values)  # type: ignore[arg-type]


def _scores(dates: pd.DatetimeIndex, rows: dict[int, list[str]]) -> pd.DataFrame:
    """Signal panel whose ranking on day k is the listed order (missing coins have no score)."""
    coins = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
    frame = pd.DataFrame(np.nan, index=dates, columns=coins)
    current: list[str] = rows[0]
    for position, date in enumerate(dates):
        current = rows.get(position, current)
        for rank, coin in enumerate(current):
            frame.loc[date, coin] = float(len(current) - rank)
    return frame


def _held(sleeve: SleeveTargets, date: pd.Timestamp) -> dict[str, float]:
    assert sleeve.holdings is not None
    history = sleeve.assets.loc[:date].dropna()
    return dict(sleeve.holdings.loc[history.index[-1]])


def test_multi_asset_sleeve_enters_the_top_n_with_equal_capital_shares() -> None:
    market, dates = _ranking_market()
    panel = _scores(dates, {0: list("abcdefghij")})

    sleeve = build_sleeve_targets(market, panel, dates, _multi_spec(), signal_name="s", phase_offset=0)

    assert _held(sleeve, dates[0]) == {"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}
    assert sleeve.assets.loc[dates[0]] == "__multi__"
    assert float(sleeve.weights.loc[dates[0]]) == pytest.approx(1.0)


def test_multi_asset_sleeve_keeps_incumbents_inside_the_hold_band_until_a_check() -> None:
    market, dates = _ranking_market()
    panel = _scores(
        dates,
        {
            0: list("abcdefghij"),
            # Day 1 (no check): d drops to rank 9 and c to rank 7.
            1: list("abefghcidj"),
        },
    )

    sleeve = build_sleeve_targets(market, panel, dates, _multi_spec(), signal_name="s", phase_offset=0)

    assert set(_held(sleeve, dates[1])) == {"a", "b", "c", "d"}
    assert set(_held(sleeve, dates[2])) == {"a", "b", "c", "d"}
    # Day 3 is the next scheduled check: d (rank 9) leaves, c (rank 7) stays,
    # and the empty slot goes to the best-ranked coin not held (e).
    assert set(_held(sleeve, dates[3])) == {"a", "b", "c", "e"}


def test_multi_asset_sleeve_sells_a_top20_leaver_at_once_and_refills_the_slot() -> None:
    market, dates = _ranking_market()
    panel = _scores(dates, {0: list("abcdefghij"), 1: list("acdefghij")})

    sleeve = build_sleeve_targets(market, panel, dates, _multi_spec(), signal_name="s", phase_offset=0)

    # b has no score on day 1 (it left the Top20): replaced the same day, not at the check.
    assert set(_held(sleeve, dates[1])) == {"a", "c", "d", "e"}
    assert sleeve.assets.loc[dates[1]] == "__multi__"


def test_multi_asset_sleeve_scales_each_coin_by_its_own_volatility() -> None:
    dates = pd.date_range("2024-01-01", periods=12, freq="D")
    swings = {"a": 0.001, "b": 0.02, "c": 0.05, "d": 0.10, "e": 0.0}
    price = pd.DataFrame(
        {coin: 100.0 * np.cumprod([1.0 + (swing if day % 2 else -swing) for day in range(len(dates))])
         for coin, swing in swings.items()},
        index=dates,
    )
    price["bitcoin"] = 100.0
    market = _market(price)
    panel = pd.DataFrame({"a": 5.0, "b": 4.0, "c": 3.0, "d": 2.0, "e": 1.0}, index=dates)
    spec = _multi_spec(use_volatility_target=True, target_volatility=0.5, vol_window=3, weight_tolerance=0.0)

    sleeve = build_sleeve_targets(market, panel, dates, spec, signal_name="s", phase_offset=0)

    volatility = realized_volatility(market.price, window=3)
    date = dates[-1]
    held = _held(sleeve, date)
    assert set(held) == {"a", "b", "c", "d"}
    for coin, weight in held.items():
        vol = float(volatility.at[date, coin])
        assert weight == pytest.approx(0.25 * min(1.0, 0.5 / vol))
    assert held["a"] == pytest.approx(0.25)
    assert held["d"] < held["c"] < held["b"]


def test_multi_asset_sleeve_goes_to_cash_when_risk_off_and_refills_on_reentry() -> None:
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    coins = list("abcdef")
    price = pd.DataFrame({coin: 100.0 for coin in coins}, index=dates)
    price["bitcoin"] = [100.0, 101.0, 102.0, 90.0, 85.0, 95.0, 100.0, 105.0, 110.0, 115.0]
    market = _market(price)
    panel = pd.DataFrame({coin: float(len(coins) - rank) for rank, coin in enumerate(coins)}, index=dates)

    sleeve = build_sleeve_targets(market, panel, dates, _multi_spec(), signal_name="s", phase_offset=0)

    history = sleeve.selection_history.set_index("signal_date")
    off = history[~history["risk_on"].astype(bool)]
    assert not off.empty
    assert (off["target_weight"].astype(float) == 0.0).all()
    assert _held(sleeve, off.index[0]) == {}
    assert sleeve.assets.loc[off.index[0]] == "__cash__"
    back_on = history[(history.index > off.index[-1]) & history["risk_on"].astype(bool)].index[0]
    assert set(_held(sleeve, back_on)) == {"a", "b", "c", "d"}


def test_multi_asset_aggregate_keeps_every_coin_and_gross_exposure_at_most_one() -> None:
    market, universe, index = _synthetic_market()
    spec = PhaseMomentumSpec(holdings_per_sleeve=4, hold_rank=8)

    built = build_phase_momentum_targets(market, universe, index, spec=spec)

    assert len(built.sleeve_targets) == 12
    assert all(sleeve.holdings is not None for sleeve in built.sleeve_targets)
    assert max(built.exposures.values()) <= 1.0 + 1e-12
    date = max(built.targets)
    expected = pd.Series(0.0, index=market.returns.columns)
    for sleeve in built.sleeve_targets:
        for asset, weight in _held(sleeve, date).items():
            expected[asset] += weight / 12.0
    pd.testing.assert_series_equal(
        built.targets[date].sort_index(),
        expected[expected > 0.0].sort_index(),
        check_names=False,
    )
    assert (built.targets[date] <= 1.0 / 12.0 / 4.0 * 12 + 1e-12).all()
    assert built.selection_history["selected_asset"].str.count(r"\|").max() == 3


def test_multi_asset_validation() -> None:
    with pytest.raises(ValueError):
        PhaseMomentumSpec(holdings_per_sleeve=0)
    with pytest.raises(ValueError):
        PhaseMomentumSpec(holdings_per_sleeve=4, hold_rank=3)
    with pytest.raises(ValueError):
        PhaseMomentumSpec(holdings_per_sleeve=4, hold_rank=8, stop_loss_kind="fixed")
    with pytest.raises(ValueError):
        PhaseMomentumSpec(holdings_per_sleeve=4, hold_rank=8, use_asset_trend_filter=True)


# --------------------------------------------------------------------------- H3


def test_breadth_helper_matches_the_breadth_overlay_script() -> None:
    from atlas20.strategies.phase_momentum import top20_breadth
    from scripts.run_momentum_event_breadth_overlay import _breadth_signal

    market, universe, index = _synthetic_market()

    ours = top20_breadth(market, universe, index, ma_window=50)
    theirs = _breadth_signal(market, universe, index, ma_window=50)

    pd.testing.assert_series_equal(ours, theirs, check_names=False, check_freq=False)
    assert ours.between(0.0, 1.0).all()


def test_breadth_condition_sends_the_sleeve_to_cash_with_the_reset() -> None:
    market, _universe_frame, dates = _gate_market()
    spec = PhaseMomentumSpec(
        rebalance_days=5,
        phase_offsets=(0,),
        hold_rank=2,
        btc_ma_window=2,
        btc_confirm_days=1,
        use_volatility_target=False,
        breadth_threshold=0.5,
    )
    signal_panel = pd.DataFrame({"a": [1.0] * 5 + [2.0] * 11, "b": [2.0] * 5 + [1.5] * 11}, index=dates)
    breadth = pd.Series(1.0, index=dates)
    breadth.iloc[2:4] = 0.45
    breadth.iloc[4] = np.nan

    sleeve = build_sleeve_targets(
        market, signal_panel, dates, spec, signal_name="s", phase_offset=0, breadth=breadth
    )
    no_filter = build_sleeve_targets(
        market, signal_panel, dates, replace(spec, breadth_threshold=None), signal_name="s", phase_offset=0
    )

    history = sleeve.selection_history.set_index("signal_date")
    unfiltered = no_filter.selection_history.set_index("signal_date")
    assert unfiltered["risk_on"].iloc[2:5].astype(bool).all()
    assert not history["risk_on"].iloc[2:5].astype(bool).any()
    assert (history["selected_asset"].iloc[2:5] == "").all()
    assert sleeve.assets.loc[dates[2]] == "__cash__"
    assert history["breadth"].iloc[2] == pytest.approx(0.45)
    # After the reset the sleeve re-enters at rank 1 (a); without the breadth
    # condition the incumbent b stays inside the Top2 hold band.
    assert history["selected_asset"].iloc[1] == "b"
    assert history["selected_asset"].iloc[5] == "a"
    assert unfiltered["selected_asset"].iloc[5] == "b"


def test_breadth_rule_requires_a_breadth_series() -> None:
    market, _universe_frame, dates = _gate_market()
    spec = PhaseMomentumSpec(breadth_threshold=0.5)
    with pytest.raises(ValueError):
        build_sleeve_targets(market, pd.DataFrame(), dates, spec, signal_name="s", phase_offset=0)
    with pytest.raises(ValueError):
        PhaseMomentumSpec(breadth_threshold=0.0)
    with pytest.raises(ValueError):
        PhaseMomentumSpec(breadth_threshold=1.5)
    with pytest.raises(ValueError):
        PhaseMomentumSpec(breadth_ma_window=1)


def test_breadth_blend_gives_each_of_24_sleeves_one_twenty_fourth() -> None:
    market, universe, index = _synthetic_market()
    book_a = PhaseMomentumSpec()
    book_b = PhaseMomentumSpec(breadth_threshold=0.50)

    blend = build_parameter_ensemble_targets(market, universe, index, parameter_specs=(book_a, book_b))
    alone_a = build_phase_momentum_targets(market, universe, index, spec=book_a)
    alone_b = build_phase_momentum_targets(market, universe, index, spec=book_b)

    weights = parameter_ensemble_sleeve_weights((book_a, book_b), signal_count=len(PRIMARY_SIGNAL_SPECS))
    assert len(blend.sleeve_targets) == 24
    assert weights == tuple([1.0 / 24.0] * 24)
    # Book B's sleeves are the champion's sleeves plus the breadth condition.
    breadth_days = alone_b.selection_history.groupby("signal_date")["risk_on"].any()
    champion_days = alone_a.selection_history.groupby("signal_date")["risk_on"].any()
    assert (breadth_days <= champion_days).all()
    assert (breadth_days < champion_days).any()
    # Every blended target is the average of the two books' latest targets.
    for date in sorted(blend.targets)[-15:]:
        expected = pd.Series(0.0, index=market.returns.columns)
        for sleeve in blend.sleeve_targets:
            history = sleeve.assets.loc[:date].dropna()
            if history.empty or history.iloc[-1] == "__cash__":
                continue
            expected[str(history.iloc[-1])] += float(sleeve.weights.loc[history.index[-1]]) / 24.0
        pd.testing.assert_series_equal(
            blend.targets[date].sort_index(),
            expected[expected > 0.0].sort_index(),
            check_names=False,
        )
    assert max(blend.exposures.values()) <= 1.0 + 1e-12


def test_breadth_blend_aggregate_matches_the_two_books() -> None:
    market, universe, index = _synthetic_market()
    book_a = build_phase_momentum_targets(market, universe, index, spec=PhaseMomentumSpec())
    book_b = build_phase_momentum_targets(
        market, universe, index, spec=PhaseMomentumSpec(breadth_threshold=0.50)
    )
    combined = book_a.sleeve_targets + book_b.sleeve_targets

    targets, exposures, _history = aggregate_sleeve_targets(
        combined, market.returns.columns, sleeve_weights=tuple([1.0 / 24.0] * 24)
    )
    blend = build_parameter_ensemble_targets(
        market, universe, index, parameter_specs=(PhaseMomentumSpec(), PhaseMomentumSpec(breadth_threshold=0.50))
    )

    assert sorted(targets) == sorted(blend.targets)
    for date, target in targets.items():
        pd.testing.assert_series_equal(target, blend.targets[date])
    assert exposures == blend.exposures
