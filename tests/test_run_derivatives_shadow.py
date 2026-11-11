import pandas as pd

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
    assert by_asset.loc["bitcoin", "execution_hint"] == signal + pd.Timedelta(days=1, hours=3)


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
