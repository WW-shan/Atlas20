"""Tests for the independent phase-momentum selection audit."""

from __future__ import annotations

from dataclasses import asdict
import json

import numpy as np
import pandas as pd
import pytest

from atlas20.config import load_config
from atlas20.strategies.phase_momentum import PRIMARY_SIGNAL_SPECS, PhaseMomentumSpec
from atlas20.universe.builder import MarketDataBundle
import scripts.audit_phase_momentum_selections as audit


def _market(raw_price: pd.DataFrame, price: pd.DataFrame | None = None) -> MarketDataBundle:
    price = raw_price if price is None else price
    return MarketDataBundle(
        raw_price=raw_price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000.0,
        volume=pd.DataFrame(1_000_000.0, index=price.index, columns=price.columns),
        history_count=pd.DataFrame(200, index=price.index, columns=price.columns),
        metadata=pd.DataFrame({"sector": ["Other"] * len(price.columns)}, index=price.columns),
    )


def _history(rows: list[tuple[pd.Timestamp, int, str, float | None]]) -> pd.DataFrame:
    """Sleeve selection rows as (signal_date, phase_offset, selected_asset, selected_rank)."""
    return pd.DataFrame(
        [(date, "signal", phase, asset, rank) for date, phase, asset, rank in rows],
        columns=["signal_date", "signal_name", "phase_offset", "selected_asset", "selected_rank"],
    )


def test_selection_audit_flags_every_configured_stablecoin_and_excluded_id() -> None:
    config = load_config("config/base.yaml")
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    # ethena-usde and tether-gold are configured stablecoins that a short
    # hard-coded list misses; wrapped-bitcoin and rain are excluded ids.
    assets = ["ethena-usde", "tether-gold", "wrapped-bitcoin", "rain"]
    history = _history([(date, 0, asset, 1) for date, asset in zip(dates, assets)])
    membership = {date: set(assets) for date in dates}
    market = _market(pd.DataFrame(1.0, index=dates, columns=assets))

    rows = audit._selection_audit(history, membership, market, config)

    assert rows["is_stablecoin"].tolist() == [True, True, False, False]
    assert rows["is_excluded_id"].tolist() == [False, False, True, True]
    assert rows["is_rain"].tolist() == [False, False, False, True]
    counts = audit._selection_counts(rows)
    assert counts["stablecoin_rows"] == 2
    assert counts["excluded_id_rows"] == 2
    assert counts["rain_rows"] == 1
    assert counts["violations"] == 4


def test_selection_audit_counts_a_carried_price_as_missing() -> None:
    config = load_config("config/base.yaml")
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    raw_price = pd.DataFrame({"solana": [10.0, np.nan, 12.0]}, index=dates)
    # prepare_market_data carries a price across short provider gaps.
    market = _market(raw_price, price=raw_price.ffill(limit=3))
    history = _history([(date, 0, "solana", 1) for date in dates])
    membership = {date: {"solana"} for date in dates}

    rows = audit._selection_audit(history, membership, market, config)

    assert rows["has_price"].tolist() == [True, False, True]
    counts = audit._selection_counts(rows)
    assert counts["missing_price_rows"] == 1
    assert counts["violations"] == 1


def test_selection_audit_flags_a_selection_outside_the_snapshot() -> None:
    config = load_config("config/base.yaml")
    dates = pd.date_range("2024-01-01", periods=2, freq="D")
    history = _history([(dates[0], 0, "solana", 1), (dates[1], 0, "solana", 1), (dates[1], 1, "", None)])
    membership = {dates[0]: {"solana", "ethereum"}, dates[1]: {"ethereum"}}
    market = _market(pd.DataFrame(1.0, index=dates, columns=["solana", "ethereum"]))

    rows = audit._selection_audit(history, membership, market, config)

    # The empty selection is cash, not a row to audit.
    assert rows["in_point_in_time_top20"].tolist() == [True, False]
    assert rows["snapshot_size"].tolist() == [2, 1]
    counts = audit._selection_counts(rows)
    assert counts["selection_rows"] == 2
    assert counts["outside_top20_rows"] == 1
    assert counts["violations"] == 1


def test_snapshot_audit_reports_missing_dates_and_wrong_sizes() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    universe = pd.DataFrame(
        [(index[0], coin) for coin in ("a", "b", "c")]
        + [(index[1], coin) for coin in ("a", "b")]
        # index[2] has no snapshot at all.
        + [(index[3], coin) for coin in ("a", "b", "c")],
        columns=["rebalance_date", "coin_id"],
    )

    sizes = audit._snapshot_size_audit(universe, index, expected_size=3)

    assert sizes["date"].tolist() == list(index)
    assert sizes["universe_size"].tolist() == [3, 2, 0, 3]
    assert sizes["has_snapshot"].tolist() == [True, True, False, True]
    counts = audit._snapshot_counts(sizes)
    assert counts["dates_without_snapshot"] == 1
    assert counts["dates_with_wrong_size"] == 1
    assert counts["min_universe_size"] == 0
    assert counts["max_universe_size"] == 3


def test_hold_rule_audit_checks_ranks_on_each_sleeves_scheduled_days() -> None:
    index = pd.date_range("2024-01-01", periods=6, freq="D")
    spec = PhaseMomentumSpec(rebalance_days=3, phase_offsets=(0, 1, 2), hold_rank=2)
    history = _history(
        [
            (index[0], 0, "a", 1),  # day 0 is phase 0's check: rank 1 passes
            (index[1], 0, "a", 3),  # not phase 0's check: holding at rank 3 is allowed
            (index[3], 0, "a", 3),  # day 3 is phase 0's check: rank 3 > hold_rank
            (index[4], 1, "b", 2),  # day 4 is phase 1's check: rank 2 passes
            (index[5], 2, "c", None),  # day 5 is phase 2's check: an unranked hold fails closed
            (index[2], 2, "", None),  # cash is not a hold
        ]
    )

    rows = audit._hold_rule_audit(history, index, spec)

    assert rows["signal_date"].tolist() == [index[0], index[3], index[4], index[5]]
    assert rows["hold_rule_ok"].tolist() == [True, False, True, False]
    assert audit._hold_rule_counts(rows) == {
        "hold_rule_checked_rows": 4,
        "hold_rule_violations": 2,
    }


def test_traded_target_audit_checks_every_positive_weight() -> None:
    dates = pd.date_range("2024-01-01", periods=2, freq="D")
    raw_price = pd.DataFrame(
        {"a": [1.0, 1.0], "b": [1.0, np.nan], "c": [1.0, 1.0]},
        index=dates,
    )
    market = _market(raw_price, price=raw_price.ffill(limit=3))
    membership = {dates[0]: {"a", "b"}, dates[1]: {"a", "b"}}
    targets = {
        # c is outside the Top20 snapshot; a zero weight is not a trade.
        dates[0]: pd.Series({"a": 0.50, "c": 0.25, "b": 0.0}),
        # b is in the snapshot but only has a carried price that day.
        dates[1]: pd.Series({"b": 0.40}),
    }

    rows = audit._traded_target_audit(targets, membership, market)

    assert rows[["target_date", "asset"]].values.tolist() == [
        [dates[0], "a"],
        [dates[0], "c"],
        [dates[1], "b"],
    ]
    assert rows["in_point_in_time_top20"].tolist() == [True, False, True]
    assert rows["has_price"].tolist() == [True, True, False]
    assert audit._traded_counts(rows) == {
        "traded_rows": 3,
        "traded_outside_top20": 1,
        "traded_without_price": 1,
    }


def _patch_run(monkeypatch: pytest.MonkeyPatch, *, drop_snapshot: bool = False) -> pd.DatetimeIndex:
    """Serve a synthetic three-coin Top3 run to main() in place of the panel."""
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    rng = np.random.default_rng(20240101)
    drift = {"bitcoin": 0.002, "ethereum": 0.003, "solana": 0.005}
    price = pd.DataFrame(
        {
            coin: 100.0 * np.cumprod(1.0 + mu + rng.normal(0.0, 0.02, len(dates)))
            for coin, mu in drift.items()
        },
        index=dates,
    )
    universe = pd.DataFrame(
        [(date, coin) for date in dates for coin in price.columns],
        columns=["rebalance_date", "coin_id"],
    )
    if drop_snapshot:
        universe = universe[universe["rebalance_date"] != dates[100]]
    config = load_config("config/base.yaml").model_copy(deep=True)
    config.universe.universe_size = 3
    monkeypatch.setattr(
        audit,
        "_load_market",
        lambda *args, **kwargs: (config, _market(price), universe, dates),
    )
    return dates


def test_main_passes_a_clean_run_and_records_the_spec_actually_used(tmp_path, monkeypatch) -> None:
    dates = _patch_run(monkeypatch)

    audit.main(["--output-dir", str(tmp_path)])

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["spec"] == {**asdict(PhaseMomentumSpec()), "phase_offsets": [0, 1, 2]}
    assert manifest["signal_names"] == [signal.name for signal in PRIMARY_SIGNAL_SPECS]
    summary = manifest["summary"]
    assert summary["dates_evaluated"] == len(dates)
    assert summary["selection_rows"] > 0
    assert summary["hold_rule_checked_rows"] > 0
    assert summary["traded_rows"] > 0
    for key in (
        "violations",
        "missing_price_rows",
        "outside_top20_rows",
        "rain_rows",
        "stablecoin_rows",
        "excluded_id_rows",
        "dates_without_snapshot",
        "dates_with_wrong_size",
        "hold_rule_violations",
        "traded_outside_top20",
        "traded_without_price",
    ):
        assert summary[key] == 0, key
    for name in ("selection_audit.csv", "hold_rule_audit.csv", "traded_target_audit.csv", "report.md"):
        assert (tmp_path / name).exists(), name


def test_main_exits_non_zero_when_any_check_fails(tmp_path, monkeypatch) -> None:
    _patch_run(monkeypatch, drop_snapshot=True)

    with pytest.raises(SystemExit) as exit_info:
        audit.main(["--output-dir", str(tmp_path)])

    assert exit_info.value.code == 1
    # The evidence is written before the audit fails.
    summary = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["summary"]
    assert summary["dates_without_snapshot"] == 1
    assert "FAIL" in (tmp_path / "report.md").read_text(encoding="utf-8")
