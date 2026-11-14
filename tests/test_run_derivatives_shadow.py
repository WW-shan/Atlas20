import pandas as pd
import pytest

from scripts.run_derivatives_shadow import _shadow_targets


def test_shadow_targets_preserve_signed_long_and_short_weights() -> None:
    signal = pd.Timestamp("2026-09-22", tz="UTC")
    targets = {
        signal: pd.Series({"bitcoin": 0.5, "ethereum": -0.25}),
    }

    rows = _shadow_targets(targets, capital=1000.0)

    by_asset = rows.set_index("asset")
    assert by_asset.loc["bitcoin", "side"] == "long"
    assert by_asset.loc["bitcoin", "target_weight"] == 0.5
    assert by_asset.loc["bitcoin", "target_notional_per_1k"] == 500.0
    assert by_asset.loc["ethereum", "side"] == "short"
    assert by_asset.loc["ethereum", "target_weight"] == -0.25
    assert by_asset.loc["ethereum", "target_notional_per_1k"] == -250.0
    assert by_asset.loc["bitcoin", "execution_hint"] == signal + pd.Timedelta(
        days=1, hours=1, minutes=5
    )


def test_shadow_targets_can_use_the_single_0105_execution_clock() -> None:
    signal = pd.Timestamp("2026-11-13", tz="UTC")
    rows = _shadow_targets(
        {signal: pd.Series({"bitcoin": 0.5})},
        capital=1000.0,
        execution_hour=1,
        execution_minute=5,
    )

    assert rows.iloc[0]["execution_hint"] == pd.Timestamp("2026-11-14 01:05", tz="UTC")


def test_engine_end_includes_the_last_signals_0105_execution() -> None:
    from scripts.run_derivatives_shadow import _engine_end_for_signal_end

    signal_end = pd.Timestamp("2026-11-13", tz="UTC")

    engine_end = _engine_end_for_signal_end(
        signal_end,
        execution_hour=1,
        execution_minute=5,
    )

    assert engine_end == pd.Timestamp("2026-11-14 01:05:01", tz="UTC")


def test_last_signal_executes_before_the_engine_end() -> None:
    from atlas20.derivatives.engine import DerivativeBacktestConfig, run_derivative_backtest
    from scripts.run_derivatives_shadow import _engine_end_for_signal_end

    signal = pd.Timestamp("2026-01-01", tz="UTC")
    frame = pd.DataFrame(
        {"open": [100.0, 100.0, 100.0], "high": [100.0] * 3, "low": [100.0] * 3, "close": [100.0] * 3},
        index=pd.DatetimeIndex(
            ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", "2026-01-02T01:00:00Z"]
        ),
    )
    result = run_derivative_backtest(
        {"bitcoin": frame},
        {signal: pd.Series({"bitcoin": 0.5})},
        config=DerivativeBacktestConfig(
            initial_capital=500.0,
            execution_hour=1,
            execution_minute=5,
            execution_price_snap="floor",
            max_gross_exposure=1.25,
        ),
        start_time=signal,
        end_time=_engine_end_for_signal_end(
            signal,
            execution_hour=1,
            execution_minute=5,
        ),
    )

    assert result.trades[["asset", "action"]].to_dict("records") == [
        {"asset": "bitcoin", "action": "open"}
    ]


def test_short_schedule_is_flattened_after_funding_history_ends() -> None:
    from scripts.run_derivatives_shadow import _cap_short_schedule_at_funding_end

    calendar = pd.date_range("2026-10-08", periods=4, freq="D", tz="UTC")
    schedule = {
        calendar[0]: pd.Series({"bitcoin": 0.0625}),
        calendar[2]: pd.Series({"ethereum": 0.0625}),
    }

    capped = _cap_short_schedule_at_funding_end(
        schedule,
        calendar=calendar,
        funding_last=pd.Timestamp("2026-10-09 08:00", tz="UTC"),
    )

    assert list(capped) == [calendar[0], calendar[2]]
    assert capped[calendar[2]].empty


def test_shadow_ledger_includes_signal_that_fills_inside_the_window() -> None:
    from scripts.run_derivatives_shadow import _targets_executing_after

    signal = pd.Timestamp("2026-09-21", tz="UTC")
    start = pd.Timestamp("2026-09-22", tz="UTC")
    targets = {signal: pd.Series({"bitcoin": 0.5})}

    selected = _targets_executing_after(targets, start)

    assert list(selected) == [signal]


def test_shadow_ledger_window_filter_uses_the_0105_clock() -> None:
    from scripts.run_derivatives_shadow import _targets_executing_after

    signal = pd.Timestamp("2026-09-21", tz="UTC")
    targets = {signal: pd.Series({"bitcoin": 0.5})}

    included = _targets_executing_after(
        targets,
        pd.Timestamp("2026-09-22 01:00", tz="UTC"),
        execution_hour=1,
        execution_minute=5,
    )
    excluded = _targets_executing_after(
        targets,
        pd.Timestamp("2026-09-22 01:06", tz="UTC"),
        execution_hour=1,
        execution_minute=5,
    )

    assert list(included) == [signal]
    assert excluded == {}


def test_shadow_ledger_marks_a_close_as_flat() -> None:
    from scripts.run_derivatives_shadow import _shadow_targets

    first = pd.Timestamp("2026-09-22", tz="UTC")
    second = pd.Timestamp("2026-09-23", tz="UTC")
    rows = _shadow_targets(
        {
            first: pd.Series({"bitcoin": 0.5}),
            second: pd.Series(dtype=float),
        }
    )

    close = rows.loc[rows["signal_date"] == second].iloc[0]
    assert close["asset"] == "bitcoin"
    assert close["side"] == "flat"
    assert close["target_weight"] == 0.0
    assert close["action"] == "CLOSE"


def test_mark_coverage_detects_hourly_page_boundary_gaps() -> None:
    from scripts.run_derivatives_shadow import _mark_coverage

    start = pd.Timestamp("2026-01-01", tz="UTC")
    end = start + pd.Timedelta(hours=4)
    full = pd.DataFrame({"close": [1.0, 1.0, 1.0, 1.0]}, index=pd.date_range(start, periods=4, freq="h"))
    gapped = full.drop(full.index[2])

    coverage = _mark_coverage({"full": full, "gapped": gapped}, start=start, end=end)

    assert coverage["expected_hours"] == 4
    assert coverage["missing_hours"] == 1
    assert coverage["max_gap_hours"] == 2.0
    assert coverage["gap_event_count"] == 1
    assert coverage["two_hour_gap_count"] == 1
    assert coverage["assets_with_observations"] == 2
    assert coverage["assets_with_gaps"] == 1


def test_mark_coverage_does_not_count_pre_listing_history_as_a_gap() -> None:
    from scripts.run_derivatives_shadow import _mark_coverage

    start = pd.Timestamp("2026-01-01", tz="UTC")
    end = start + pd.Timedelta(hours=6)
    late = pd.DataFrame(
        {"close": [1.0, 1.0, 1.0, 1.0]},
        index=pd.date_range(start + pd.Timedelta(hours=2), periods=4, freq="h"),
    )

    coverage = _mark_coverage({"late": late}, start=start, end=end)

    assert coverage["missing_hours"] == 0
    assert coverage["assets_with_gaps"] == 0
    assert coverage["expected_hours"] == 4


def test_execution_mark_availability_uses_the_0105_floor_clock() -> None:
    from scripts.run_derivatives_backtest import _has_execution_mark

    signal = pd.Timestamp("2026-01-01", tz="UTC")
    frame = pd.DataFrame(
        {"open": [100.0], "high": [100.0], "low": [100.0], "close": [100.0]},
        index=pd.DatetimeIndex(["2026-01-02T01:00:00Z"]),
    )
    candles = {"bitcoin": frame}

    assert _has_execution_mark(
        candles,
        "bitcoin",
        signal,
        execution_hour=1,
        execution_minute=5,
        execution_price_snap="floor",
    )
    assert not _has_execution_mark(candles, "bitcoin", signal)


def test_merge_mark_maps_lets_oos_marks_override_warmup_overlap() -> None:
    from scripts.run_derivatives_shadow import _merge_mark_maps

    index = pd.date_range("2026-01-01", periods=3, freq="h", tz="UTC")
    warmup = {"A": pd.DataFrame({"close": [1.0, 2.0]}, index=index[:2])}
    execution = {"A": pd.DataFrame({"close": [20.0, 3.0]}, index=index[1:])}

    merged = _merge_mark_maps(warmup, execution)

    assert merged["A"]["close"].tolist() == [1.0, 20.0, 3.0]


def test_shadow_spec_selects_ls42_and_rejects_unknown_trials() -> None:
    from scripts.run_derivatives_shadow import _shadow_spec
    from scripts.run_h5_regime_short_router import (
        LS42_CANDIDATE_ID,
        LS42_SPEC_PATH,
        LS43_CANDIDATE_ID,
        LS43_SPEC_PATH,
    )

    assert _shadow_spec(LS42_CANDIDATE_ID) == LS42_SPEC_PATH
    assert _shadow_spec(LS43_CANDIDATE_ID) == LS43_SPEC_PATH
    with pytest.raises(ValueError, match="unsupported shadow trial"):
        _shadow_spec("not-a-trial")


def test_shadow_spec_selects_ls49_ma21_rearm() -> None:
    from scripts.run_derivatives_shadow import _shadow_spec
    from scripts.run_h5_regime_short_router import LS49_CANDIDATE_ID, LS49_SPEC_PATH

    assert _shadow_spec(LS49_CANDIDATE_ID) == LS49_SPEC_PATH


def test_shadow_spec_selects_ls50_below_stop_rearm() -> None:
    from scripts.run_derivatives_shadow import _shadow_spec
    from scripts.run_h5_regime_short_router import LS50_CANDIDATE_ID, LS50_SPEC_PATH

    assert _shadow_spec(LS50_CANDIDATE_ID) == LS50_SPEC_PATH


def test_zero_funding_shadow_keeps_short_schedule() -> None:
    from scripts.run_derivatives_shadow import _cap_short_schedule_at_funding_end

    calendar = pd.date_range("2026-10-08", periods=3, freq="D", tz="UTC")
    schedule = {calendar[0]: pd.Series({"bitcoin": 0.20})}

    kept = _cap_short_schedule_at_funding_end(
        schedule,
        calendar=calendar,
        funding_last=None,
    )

    assert list(kept) == [calendar[0]]
    assert kept[calendar[0]].to_dict() == {"bitcoin": pytest.approx(0.20)}


def test_max_total_gross_override_is_validated() -> None:
    from scripts.run_derivatives_shadow import _resolve_max_total_gross
    from scripts.run_h5_regime_short_router import FROZEN_CONFIG

    assert _resolve_max_total_gross(None) == pytest.approx(
        float(FROZEN_CONFIG["max_total_gross"])
    )
    assert _resolve_max_total_gross(1.25) == pytest.approx(1.25)
    with pytest.raises(ValueError, match="max_total_gross"):
        _resolve_max_total_gross(0.0)


def test_mark_tree_provenance_hashes_each_symbol_file(tmp_path) -> None:
    from scripts.run_derivatives_shadow import _mark_tree_provenance

    candles = tmp_path / "candles"
    candles.mkdir()
    for symbol in ("BTCUSDT", "ETHUSDT"):
        (candles / f"{symbol}_mark.csv").write_text(
            "open_time,open,high,low,close\n"
            "2026-01-01T00:00:00Z,1,1,1,1\n",
            encoding="utf-8",
        )
    symbol_map = pd.DataFrame(
        {
            "coin_id": ["bitcoin", "ethereum", "missing", "unmapped"],
            "bitget_symbol": ["BTCUSDT", "ETHUSDT", "MISSINGUSDT", float("nan")],
        }
    )

    provenance = _mark_tree_provenance(tmp_path, symbol_map)

    assert provenance["mark_file_count"] == 2
    assert provenance["missing_symbols"] == ["MISSINGUSDT"]
    assert set(provenance["files"]) == {
        "candles/BTCUSDT_mark.csv",
        "candles/ETHUSDT_mark.csv",
    }
    assert provenance["fingerprint"].startswith("sha256:")


def test_execution_mark_audit_records_a_missing_0100_floor_bar() -> None:
    from scripts.run_derivatives_shadow import _execution_mark_audit

    first_signal = pd.Timestamp("2026-01-01", tz="UTC")
    second_signal = pd.Timestamp("2026-01-03", tz="UTC")
    frame = pd.DataFrame(
        {"open": [100.0], "high": [100.0], "low": [100.0], "close": [100.0]},
        index=pd.DatetimeIndex(["2026-01-02T01:00:00Z"]),
    )

    audit = _execution_mark_audit(
        {
            first_signal: pd.Series({"bitcoin": 0.5}),
            second_signal: pd.Series({"bitcoin": -0.25}),
        },
        {"bitcoin": frame},
        execution_hour=1,
        execution_minute=5,
        execution_price_snap="floor",
    )

    assert audit["required_pair_count"] == 2
    assert audit["resolved_pair_count"] == 1
    assert audit["floor_resolved_count"] == 1
    assert audit["exact_bar_count"] == 0
    assert audit["missing_pair_count"] == 1
    assert audit["missing"][0]["signal_date"] == str(second_signal)
    assert audit["missing"][0]["asset"] == "bitcoin"
