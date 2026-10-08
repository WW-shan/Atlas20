"""Unit tests for the data-chain audit's check logic.

The audit is the gate a panel has to pass before a backtest is trusted or real
money follows a signal, so every check has to be able to FAIL. Several could
not: a ``warn=`` flag overrode a failing condition and turned it into a WARN,
and some conditions could never be false at all.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import scripts.audit_data_chain as audit
from atlas20.backtest.calendar import get_rebalance_dates
from atlas20.config import FrictionConfig, load_config
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data


@pytest.fixture(autouse=True)
def _fresh_results() -> Iterator[None]:
    audit.RESULTS.clear()
    yield
    audit.RESULTS.clear()


def _status() -> str:
    return audit.RESULTS[-1][1]


# ------------------------------------------------------------ check() itself


def test_a_failing_check_is_never_downgraded_to_warn() -> None:
    audit.check("probe", False, "condition violated", warn=True)

    assert _status() == "FAIL"


@pytest.mark.parametrize(("ok", "warn", "expected"), [(True, False, "PASS"), (True, True, "WARN"), (False, False, "FAIL")])
def test_check_statuses(ok: bool, warn: bool, expected: str) -> None:
    audit.check("probe", ok, "detail", warn=warn)

    assert _status() == expected


# ------------------------------------------------------------------ freshness

# 01:30 on 2026-09-25 in Shanghai is 17:30 UTC on 2026-09-24, so the latest
# completed UTC day is 2026-09-23 while the host's local date is already 09-25.
_SHANGHAI_EARLY_MORNING = pd.Timestamp("2026-09-25 01:30", tz="Asia/Shanghai")


def test_freshness_is_measured_against_the_latest_completed_utc_day() -> None:
    ok, detail = audit.panel_freshness(pd.Timestamp("2026-09-23"), now=_SHANGHAI_EARLY_MORNING)

    assert ok
    assert "0d behind" in detail
    assert "2026-09-23" in detail


def test_one_day_behind_is_allowed_while_the_provider_finalizes() -> None:
    ok, _ = audit.panel_freshness(pd.Timestamp("2026-09-22"), now=_SHANGHAI_EARLY_MORNING)

    assert ok


@pytest.mark.parametrize("days_behind", [2, 30])
def test_a_panel_more_than_one_day_behind_fails(days_behind: int) -> None:
    last = pd.Timestamp("2026-09-23") - pd.Timedelta(days=days_behind)

    ok, detail = audit.panel_freshness(last, now=_SHANGHAI_EARLY_MORNING)
    audit.check("freshness", ok, detail)

    assert not ok
    assert f"{days_behind}d behind" in detail
    assert _status() == "FAIL"


def test_a_panel_row_for_an_unfinished_utc_day_fails() -> None:
    ok, detail = audit.panel_freshness(pd.Timestamp("2026-09-24"), now=_SHANGHAI_EARLY_MORNING)

    assert not ok
    assert "not closed" in detail


def test_a_pinned_end_date_is_the_freshness_reference() -> None:
    ok, detail = audit.panel_freshness(
        pd.Timestamp("2024-03-15"), now=_SHANGHAI_EARLY_MORNING, end_date="2024-03-15"
    )

    assert ok
    assert "0d behind" in detail


# -------------------------------------------------------------- interior gaps

_GAP_NAME = "feed: interior provider gaps are short and named"


def _panel(coin_dates: dict[str, pd.DatetimeIndex]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": day, "coin_id": coin_id, "symbol": coin_id.upper(), "price": 1.0}
            for coin_id, dates in coin_dates.items()
            for day in dates
        ]
    )


_DAYS = pd.date_range("2024-01-01", "2024-06-30", freq="D")


def test_a_long_interior_gap_fails() -> None:
    gap = pd.date_range("2024-03-01", periods=41, freq="D")
    panel = _panel({"link": _DAYS.difference(gap), "bitcoin": _DAYS})

    ok, detail, warn = audit.interior_gaps(panel, start=pd.Timestamp("2024-01-01"))
    audit.check(_GAP_NAME, ok, detail, warn=warn)

    assert _status() == "FAIL"
    assert "LINK (41d, longest run 41d)" in detail


def test_a_short_named_gap_warns() -> None:
    panel = _panel({"link": _DAYS.difference([pd.Timestamp("2024-03-01")]), "bitcoin": _DAYS})

    ok, detail, warn = audit.interior_gaps(panel, start=pd.Timestamp("2024-01-01"))
    audit.check(_GAP_NAME, ok, detail, warn=warn)

    assert _status() == "WARN"
    assert "LINK (1d, longest run 1d)" in detail


def test_gaps_before_the_traded_window_are_ignored_and_no_gap_passes() -> None:
    gap = pd.date_range("2024-01-10", periods=20, freq="D")
    panel = _panel({"link": _DAYS.difference(gap), "bitcoin": _DAYS})

    ok, detail, warn = audit.interior_gaps(panel, start=pd.Timestamp("2024-03-01"))
    audit.check(_GAP_NAME, ok, detail, warn=warn)

    assert _status() == "PASS"


# ---------------------------------------------------- empty CMC tail windows


def _epoch(day: str) -> int:
    return int(pd.Timestamp(day, tz="UTC").timestamp())


def _window(coin_id: int, start: str, end: str) -> str:
    return f"{coin_id}_{_epoch(start)}_{_epoch(end)}.json"


_TAIL_START, _TAIL_END = "2026-09-17", "2026-09-22"


def test_an_empty_tail_window_for_a_live_coin_fails() -> None:
    ok, detail = audit.empty_tail_windows(
        [_window(1, _TAIL_START, _TAIL_END)],
        {1: pd.Timestamp("2026-09-23")},
    )

    assert not ok
    assert "1_" in detail and "last print 2026-09-23" in detail


def test_an_empty_tail_window_for_an_ended_series_passes() -> None:
    """MATIC's feed ended 2025-03-24; a tail window 547 days later is empty."""
    ok, detail = audit.empty_tail_windows(
        [_window(3890, _TAIL_START, _TAIL_END)],
        {3890: pd.Timestamp("2025-03-24")},
    )

    assert ok
    assert "3890 (ended 2025-03-24)" in detail


def test_a_series_that_stopped_within_the_grace_period_is_not_called_ended() -> None:
    ok, _ = audit.empty_tail_windows(
        [_window(1, _TAIL_START, _TAIL_END)],
        {1: pd.Timestamp("2026-09-16")},
    )

    assert not ok


def test_an_empty_tail_window_for_a_coin_without_any_cached_rows_fails() -> None:
    ok, detail = audit.empty_tail_windows([_window(7, _TAIL_START, _TAIL_END)], {})

    assert not ok
    assert "no cached rows" in detail


def test_backfill_sized_empty_windows_are_left_to_the_backfill_check() -> None:
    ok, detail = audit.empty_tail_windows(
        [_window(1, "2020-01-01", _TAIL_END)],
        {1: pd.Timestamp("2026-09-23")},
    )

    assert ok
    assert "empty tail windows=0" in detail


# ----------------------------------------------- one build: the persisted set
#
# The audit used to run its panel checks on an in-memory rebuild while its
# cross-check and watchlist checks read data_quality.csv from the last
# *persisted* build. After a refused or failed build those are two different
# states, and the audit certified a mixture of both.

_BUILD_STAMP = 1_780_000_000


def _long_panel(coins: list[str], days: pd.DatetimeIndex, *, price: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": day,
                "coin_id": coin,
                "symbol": coin.upper(),
                "price": price,
                "volume_usd": 1_000.0,
                "market_cap": 10_000.0,
            }
            for coin in coins
            for day in days
        ]
    )


def _write_build(
    processed: Path,
    panel: pd.DataFrame,
    *,
    quality: pd.DataFrame | None = None,
    stamps: dict[str, float] | None = None,
) -> None:
    processed.mkdir(parents=True, exist_ok=True)
    coins = sorted(panel["coin_id"].unique())
    panel.assign(date=panel["date"].dt.strftime("%Y-%m-%d")).to_csv(processed / "panel_daily.csv", index=False)
    pd.DataFrame({"coin_id": coins, "symbol": [coin.upper() for coin in coins], "sector": "Other"}).to_csv(
        processed / "metadata.csv", index=False
    )
    if quality is None:
        quality = pd.DataFrame(
            {
                "coin_id": coins,
                "symbol": [coin.upper() for coin in coins],
                "latest_date": panel["date"].max().date().isoformat(),
                "included_in_panel": True,
            }
        )
    quality.to_csv(processed / "data_quality.csv", index=False)
    for name in ("panel_daily.csv", "metadata.csv", "data_quality.csv"):
        stamp = (stamps or {}).get(name, _BUILD_STAMP)
        os.utime(processed / name, (stamp, stamp))


def _config(tmp_path: Path):
    config = load_config("config/base.yaml").model_copy(deep=True)
    config.paths.processed_dir = str(tmp_path / "processed")
    return config


def _named(name: str) -> tuple[str, str, str]:
    matches = [result for result in audit.RESULTS if result[0] == name]
    assert matches, f"no result named {name!r}: {[result[0] for result in audit.RESULTS]}"
    return matches[-1]


_ONE_BUILD = "processed: persisted artifacts are one build"
_NO_DRIFT = "processed: an in-memory rebuild reproduces the persisted panel"
_WEEK = pd.date_range("2026-09-17", "2026-09-23", freq="D")


def test_the_audit_certifies_the_persisted_build_not_a_rebuild(tmp_path: Path) -> None:
    persisted = _long_panel(["bitcoin", "ethereum"], _WEEK)
    _write_build(tmp_path / "processed", persisted)
    rebuilt = _long_panel(["bitcoin", "ethereum", "monero"], _WEEK)

    build = audit.audit_processed_build(_config(tmp_path), rebuild=lambda: (rebuilt, pd.DataFrame()))

    assert build is not None
    assert sorted(build.panel["coin_id"].unique()) == ["bitcoin", "ethereum"]
    assert build.quality["coin_id"].tolist() == ["bitcoin", "ethereum"]
    assert _named(_ONE_BUILD)[1] == "PASS"
    status, detail = _named(_NO_DRIFT)[1:]
    assert status == "FAIL"
    assert "only in the rebuild=['monero']" in detail


def test_a_matching_rebuild_passes(tmp_path: Path) -> None:
    persisted = _long_panel(["bitcoin", "ethereum"], _WEEK)
    _write_build(tmp_path / "processed", persisted)

    audit.audit_processed_build(_config(tmp_path), rebuild=lambda: (persisted.copy(), pd.DataFrame()))

    assert _named(_NO_DRIFT)[1] == "PASS"


def test_changed_values_and_new_days_are_reported_as_drift() -> None:
    persisted = _long_panel(["bitcoin"], _WEEK)
    rebuilt = _long_panel(["bitcoin"], pd.date_range("2026-09-17", "2026-09-24", freq="D"))
    rebuilt.loc[rebuilt["date"] == pd.Timestamp("2026-09-20"), "price"] = 2.0

    ok, detail = audit.panel_drift(persisted, rebuilt)

    assert not ok
    assert "rows only in the rebuild=1" in detail
    assert "differing cells=1" in detail
    assert "bitcoin@2026-09-20 price 1->2" in detail


def test_a_failing_rebuild_is_reported_and_the_persisted_build_is_still_audited(tmp_path: Path) -> None:
    _write_build(tmp_path / "processed", _long_panel(["bitcoin"], _WEEK))

    def _refused() -> tuple[pd.DataFrame, pd.DataFrame]:
        raise RuntimeError("Processed panel regression: refusing to overwrite")

    build = audit.audit_processed_build(_config(tmp_path), rebuild=_refused)

    assert build is not None
    status, detail = _named(_NO_DRIFT)[1:]
    assert status == "FAIL"
    assert "refusing to overwrite" in detail


def test_a_data_quality_file_from_another_build_fails(tmp_path: Path) -> None:
    panel = _long_panel(["bitcoin", "ethereum"], _WEEK)
    stale_quality = pd.DataFrame(
        {
            "coin_id": ["bitcoin", "ethereum", "huobi-token"],
            "symbol": ["BITCOIN", "ETHEREUM", "HT"],
            "latest_date": "2026-09-23",
            "included_in_panel": [True, False, True],
        }
    )
    _write_build(tmp_path / "processed", panel, quality=stale_quality)

    audit.audit_processed_build(_config(tmp_path), rebuild=lambda: (panel.copy(), pd.DataFrame()))

    status, detail = _named(_ONE_BUILD)[1:]
    assert status == "FAIL"
    assert "ethereum" in detail and "huobi-token" in detail


def test_an_admitted_coin_whose_history_predates_the_panel_is_not_a_mismatch(tmp_path: Path) -> None:
    panel = _long_panel(["bitcoin"], _WEEK)
    quality = pd.DataFrame(
        {
            "coin_id": ["bitcoin", "old-coin"],
            "symbol": ["BITCOIN", "OLD"],
            "latest_date": ["2026-09-23", "2019-05-01"],
            "included_in_panel": [True, True],
        }
    )
    _write_build(tmp_path / "processed", panel, quality=quality)

    audit.audit_processed_build(_config(tmp_path), rebuild=lambda: (panel.copy(), pd.DataFrame()))

    assert _named(_ONE_BUILD)[1] == "PASS"


def test_artifacts_written_by_different_builds_fail(tmp_path: Path) -> None:
    panel = _long_panel(["bitcoin"], _WEEK)
    _write_build(tmp_path / "processed", panel, stamps={"data_quality.csv": _BUILD_STAMP - 2 * 86_400})

    audit.audit_processed_build(_config(tmp_path), rebuild=lambda: (panel.copy(), pd.DataFrame()))

    status, detail = _named(_ONE_BUILD)[1:]
    assert status == "FAIL"
    assert "apart" in detail


def test_missing_persisted_artifacts_fail(tmp_path: Path) -> None:
    build = audit.audit_processed_build(_config(tmp_path), rebuild=lambda: (pd.DataFrame(), pd.DataFrame()))

    assert build is None
    status, detail = _named(_ONE_BUILD)[1:]
    assert status == "FAIL"
    assert "panel_daily.csv" in detail


# ------------------------------------------- engine: missing-return handling
#
# base.yaml runs missing_return_policy=carry: a held coin is marked at its last
# close through a provider gap inside its printed range for at most
# missing_return_max_carry_days, and every carried day is recorded in
# BacktestResult.gap_carries. The probe has to prove the configured policy
# does what it says, and fail when the engine quietly does something else.


def _friction(policy: str, max_carry_days: int = 3) -> FrictionConfig:
    return FrictionConfig(
        fee_bps=0.0,
        slippage_bps=0.0,
        max_weight_per_coin=1.0,
        missing_return_policy=policy,
        missing_return_max_carry_days=max_carry_days,
    )


@pytest.mark.parametrize("policy", ["carry", "error"])
def test_the_engine_probe_passes_for_the_real_engine(policy: str) -> None:
    ok, detail = audit.engine_missing_return_probe(_friction(policy))

    assert ok, detail
    assert "ended feed liquidated=True" in detail
    if policy == "carry":
        assert "1-day interior gap carried and recorded in gap_carries=True" in detail
    else:
        assert "1-day interior gap refused=True" in detail
    assert "4-day gap refused=True" in detail


def _lenient_engine(name, asset_returns, targets, sector_by_coin, friction, initial_capital, **kwargs):
    """An engine that never raises, never sells and never records a carry."""
    weights = pd.DataFrame(1.0, index=asset_returns.index, columns=asset_returns.columns)
    return SimpleNamespace(weights=weights, gap_carries=pd.DataFrame(columns=["date", "asset", "weight", "event"]))


@pytest.mark.parametrize("policy", ["carry", "error"])
def test_the_engine_probe_fails_when_the_engine_is_lenient(policy: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "run_backtest", _lenient_engine)

    ok, detail = audit.engine_missing_return_probe(_friction(policy))
    audit.check("engine probe", ok, detail)

    assert _status() == "FAIL"
    assert "ended feed liquidated=False" in detail
    assert "4-day gap refused=False" in detail


@pytest.mark.parametrize(
    ("policy", "expected"),
    [("error", "PASS"), ("carry", "PASS"), ("fill", "WARN")],
)
def test_missing_return_policy_statuses(policy: str, expected: str) -> None:
    ok, detail, warn = audit.missing_return_policy(_friction(policy))
    audit.check("policy", ok, detail, warn=warn)

    assert _status() == expected
    assert f"policy={policy}" in detail
    if policy == "carry":
        assert "3 day(s)" in detail and "gap_carries" in detail


def test_the_leverage_probe_passes_when_the_engine_refuses_a_2x_cap() -> None:
    ok, detail = audit.leverage_refusal_probe(_friction("carry"))

    assert ok, detail
    assert "refused" in detail


def test_the_leverage_probe_fails_when_a_2x_cap_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "run_backtest", _lenient_engine)

    ok, detail = audit.leverage_refusal_probe(_friction("carry"))
    audit.check("leverage", ok, detail)

    assert _status() == "FAIL"
    assert "accepted" in detail


# ------------------------------------------------ universe: which dates count
#
# The universe checks used to run on a 7-day grid, which hits only 10 of the
# 69 month-end rebalance dates (and the champion re-ranks every day). A rank
# built on a forward-filled market cap on a month end was never looked at.


def _toy_config():
    config = load_config("config/base.yaml").model_copy(deep=True)
    config.start_date = "2021-04-01"
    config.end_date = "2021-08-31"
    config.universe.min_turnover_ratio = 0.0
    return config


def _toy_market_inputs(missing_cap_on: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    days = pd.date_range("2021-01-01", "2021-08-31", freq="D")
    coins = {"bitcoin": 1e12, "ethereum": 5e11, "solana": 1e11}
    panel = pd.DataFrame(
        [
            {
                "date": day,
                "coin_id": coin,
                "symbol": coin[:3].upper(),
                "name": coin.title(),
                "price": 10.0,
                "volume_usd": 1e9,
                "market_cap": cap,
            }
            for coin, cap in coins.items()
            for day in days
        ]
    )
    if missing_cap_on is not None:
        gap = (panel["coin_id"] == "solana") & (panel["date"] == pd.Timestamp(missing_cap_on))
        panel.loc[gap, "market_cap"] = float("nan")
    metadata = pd.DataFrame(
        {
            "coin_id": list(coins),
            "symbol": [coin[:3].upper() for coin in coins],
            "name": [coin.title() for coin in coins],
            "sector": "Other",
            "category_list": "",
        }
    ).set_index("coin_id")
    return panel, metadata


def test_audit_dates_cover_every_configured_rebalance_date_and_every_day() -> None:
    config = _toy_config()
    index = pd.date_range("2021-04-01", "2021-08-31", freq="D")

    dates, counts = audit.universe_audit_dates(index, config)
    frequency_only, _ = audit.universe_audit_dates(index, config, include_daily=False)

    month_ends = get_rebalance_dates(index, config.start_timestamp, "monthly", "month_end")
    biweekly = get_rebalance_dates(index, config.start_timestamp, "biweekly", "14D")
    assert set(month_ends) | set(biweekly) == set(frequency_only)
    assert dates == list(index)
    assert counts == {"monthly": len(month_ends), "biweekly": len(biweekly), "daily": len(index)}


def test_a_forward_filled_rank_on_a_month_end_is_caught() -> None:
    config = _toy_config()
    panel, metadata = _toy_market_inputs(missing_cap_on="2021-06-30")
    market = prepare_market_data(panel, metadata, config)
    index = market.returns.loc[config.start_timestamp : config.end_timestamp].index
    weekly = get_rebalance_dates(index, config.start_timestamp, "weekly", "7D")
    assert pd.Timestamp("2021-06-30") not in weekly, "the old 7-day grid never looks at this month end"

    dates, _ = audit.universe_audit_dates(index, config)
    universe = build_rebalance_universe(market, dates, config)
    # The builder no longer ranks a coin on a carried cap, so the clean build
    # passes; re-insert the carried rank to prove the audit would catch a
    # builder that regressed.
    assert audit.ranks_without_raw_cap(universe, panel)[0]
    month_end = pd.Timestamp("2021-06-30")
    carried_rank = universe[universe["rebalance_date"] == month_end].iloc[[0]].copy()
    carried_rank["coin_id"] = "solana"
    carried_rank["market_cap"] = float(market.market_cap.loc[month_end, "solana"])
    regressed = pd.concat([universe, carried_rank], ignore_index=True)
    ok, detail = audit.ranks_without_raw_cap(regressed, panel)

    assert not ok
    assert "solana@2021-06-30" in detail


def test_same_day_market_cap_ranks_pass_and_a_mismatch_fails() -> None:
    config = _toy_config()
    panel, metadata = _toy_market_inputs()
    market = prepare_market_data(panel, metadata, config)
    index = market.returns.loc[config.start_timestamp : config.end_timestamp].index
    dates, _ = audit.universe_audit_dates(index, config)
    universe = build_rebalance_universe(market, dates, config)

    ok, detail = audit.ranks_use_same_day_cap(universe, market.market_cap)
    assert ok, detail
    assert audit.ranks_without_raw_cap(universe, panel)[0]

    tampered = universe.copy()
    row = tampered.index[tampered["rebalance_date"] == pd.Timestamp("2021-07-31")][0]
    tampered.loc[row, "market_cap"] = tampered.loc[row, "market_cap"] * 2
    ok, detail = audit.ranks_use_same_day_cap(tampered, market.market_cap)
    assert not ok
    assert "@2021-07-31" in detail


# ------------------------------------------------- price-level corruption
#
# CMC served Huobi Token at ~1/250,000th of its price for 34 days. The
# processor removes such blocks before the panel is written, and the audit
# then re-ran the same filter on the already-filtered panel - so it reported
# 0 rows by construction while 34 had been removed.


def _corrupted_prices(days: int = 260, block: tuple[int, int] = (100, 133)) -> pd.Series:
    index = pd.date_range("2025-01-01", periods=days, freq="D")
    prices = pd.Series(0.5, index=index)
    prices.iloc[block[0] : block[1] + 1] = 0.000002
    return prices


def _clean_panel() -> pd.DataFrame:
    days = pd.date_range("2025-01-01", periods=260, freq="D")
    return pd.DataFrame({"date": days, "coin_id": "bitcoin", "symbol": "BTC", "price": 50_000.0})


def _no_raw_history() -> dict[str, pd.Series]:
    raise AssertionError("the processor's own count must be used when data_quality.csv has it")


def test_the_detector_flags_exactly_the_corrupted_block() -> None:
    assert int(audit.level_corruption_mask(_corrupted_prices()).sum()) == 34


def test_removals_are_reported_from_the_processor_column() -> None:
    quality = pd.DataFrame(
        {"coin_id": ["huobi-token", "bitcoin"], "symbol": ["HT", "BTC"], "level_corruption_rows": [34, 0]}
    )

    ok, detail, warn = audit.level_corruption_report(_clean_panel(), quality, raw_histories=_no_raw_history)
    audit.check("panel: no reverted price-level corruption", ok, detail, warn=warn)

    assert _status() == "WARN"
    assert "34 row(s)" in detail and "HT (34)" in detail
    assert "level_corruption_rows" in detail


def test_without_the_column_the_filter_runs_on_the_unfiltered_raw_history() -> None:
    quality = pd.DataFrame({"coin_id": ["huobi-token", "bitcoin"], "symbol": ["HT", "BTC"]})

    ok, detail, warn = audit.level_corruption_report(
        _clean_panel(),
        quality,
        raw_histories=lambda: {"HT": _corrupted_prices(), "BTC": pd.Series(1.0, index=_corrupted_prices().index)},
    )

    assert ok and warn
    assert "34 row(s)" in detail and "HT (34)" in detail
    assert "unfiltered raw" in detail


def test_corruption_left_in_the_persisted_panel_fails() -> None:
    prices = _corrupted_prices()
    panel = pd.DataFrame({"date": prices.index, "coin_id": "huobi-token", "symbol": "HT", "price": prices.values})
    quality = pd.DataFrame({"coin_id": ["huobi-token"], "symbol": ["HT"], "level_corruption_rows": [0]})

    ok, detail, warn = audit.level_corruption_report(panel, quality, raw_histories=_no_raw_history)
    audit.check("panel: no reverted price-level corruption", ok, detail, warn=warn)

    assert _status() == "FAIL"
    assert "still in the persisted panel: 34 row(s)" in detail


def test_no_corruption_anywhere_passes() -> None:
    quality = pd.DataFrame({"coin_id": ["bitcoin"], "symbol": ["BTC"], "level_corruption_rows": [0]})

    ok, detail, warn = audit.level_corruption_report(_clean_panel(), quality, raw_histories=_no_raw_history)
    audit.check("panel: no reverted price-level corruption", ok, detail, warn=warn)

    assert _status() == "PASS"


# ------------------------------------------------ last day is a finished day


def _week_panel(last_volume_factor: float) -> pd.DataFrame:
    days = pd.date_range(end="2026-09-23", periods=10, freq="D")
    rows = [
        {
            "date": day,
            "coin_id": f"coin-{coin:02d}",
            "symbol": f"C{coin:02d}",
            "price": 1.0,
            "volume_usd": 1e8 * (coin + 1) * (last_volume_factor if day == days[-1] else 1.0),
            "market_cap": 1e10 * (coin + 1),
        }
        for day in days
        for coin in range(25)
    ]
    return pd.DataFrame(rows)


def test_the_audit_fails_a_partial_last_day() -> None:
    ok, detail = audit.last_day_completeness(_week_panel(0.4))
    audit.check("panel: the last day is a finished provider day", ok, detail)

    assert _status() == "FAIL"
    assert "2026-09-23" in detail


def test_the_audit_passes_a_finished_last_day() -> None:
    ok, detail = audit.last_day_completeness(_week_panel(1.0))

    assert ok, detail
