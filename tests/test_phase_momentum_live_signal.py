from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json

import pandas as pd
import pytest

from atlas20.config import load_config
from atlas20.data.completeness import LastDayCompleteness
from atlas20.strategies.phase_momentum import (
    PhaseMomentumBuildResult,
    PhaseMomentumSpec,
    SleeveTargets,
)
from atlas20.universe.builder import MarketDataBundle
import scripts.run_phase_momentum_live_signal as live
from scripts.run_phase_momentum import _production_result
from scripts.run_phase_momentum_live_signal import _check_freshness, _latest_signal_payload


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


def _price(panel: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ethereum": [100.0] * len(panel),
            "solana": [50.0] * len(panel),
            "bitcoin": [100.0 + day for day in range(len(panel))],
        },
        index=panel,
    )


def _sleeve(
    signal_name: str,
    phase_offset: int,
    index: pd.DatetimeIndex,
    events: dict[int, tuple[str, float]],
) -> SleeveTargets:
    assets = pd.Series(pd.NA, index=index, dtype="object")
    weights = pd.Series(float("nan"), index=index, dtype=float)
    for position, (asset, weight) in events.items():
        assets.loc[index[position]] = asset
        weights.loc[index[position]] = weight
    return SleeveTargets(signal_name, phase_offset, assets, weights, pd.DataFrame())


def _built(index: pd.DatetimeIndex) -> PhaseMomentumBuildResult:
    return PhaseMomentumBuildResult(
        targets={
            index[0]: pd.Series({"ethereum": 0.50}),
            index[9]: pd.Series({"ethereum": 0.25, "solana": 0.25}),
        },
        exposures={index[0]: 0.50, index[9]: 0.50},
        selection_history=pd.DataFrame(),
        sleeve_targets=(
            _sleeve("signal_a", 0, index, {0: ("ethereum", 0.75), 9: ("solana", 0.50)}),
            _sleeve("signal_b", 1, index, {0: ("__cash__", 0.0)}),
        ),
    )


def _payload(
    market: MarketDataBundle,
    built: PhaseMomentumBuildResult,
    spec: PhaseMomentumSpec,
    index: pd.DatetimeIndex,
    *,
    as_of: pd.Timestamp | str | None = None,
    cost_bps: float = 20.0,
) -> dict[str, object]:
    result = _production_result(
        load_config("config/base.yaml"),
        market,
        built,
        index,
        cost_bps=cost_bps,
    )
    return _latest_signal_payload(
        market,
        built,
        spec,
        index,
        engine_weights=result.weights,
        cost_bps=cost_bps,
        as_of=as_of,
    )


def test_latest_signal_uses_latest_target_and_reports_sleeve_state() -> None:
    index = pd.date_range("2024-01-01", periods=16, freq="D")
    market = _market(_price(index))
    spec = PhaseMomentumSpec(btc_ma_window=2, btc_confirm_days=1)

    payload = _payload(market, _built(index), spec, index, as_of=index[-1])

    assert payload["as_of"] == "2024-01-16"
    assert payload["latest_target_date"] == "2024-01-10"
    assert payload["btc_gate_open"] is True
    assert payload["targets"] == {"ethereum": 0.25, "solana": 0.25}
    assert payload["gross_exposure"] == pytest.approx(0.50)
    assert payload["next_check_date"] == "2024-01-17"
    assert payload["sleeves"] == [
        {
            "book": 0,
            "signal_name": "signal_a",
            "phase_offset": 0,
            "asset": "solana",
            "weight": 0.50,
            "target_date": "2024-01-10",
        },
        {
            "book": 0,
            "signal_name": "signal_b",
            "phase_offset": 1,
            "asset": "__cash__",
            "weight": 0.0,
            "target_date": "2024-01-01",
        },
    ]


def test_as_of_defaults_to_the_evaluated_range_not_the_panel_end() -> None:
    panel = pd.date_range("2024-01-01", periods=16, freq="D")
    # ``--end-date 2024-01-15`` on a panel that already holds 2024-01-16.
    index = panel[:-1]
    price = _price(panel)
    # BTC collapses on the panel's extra day; reading the gate there would
    # report a closed gate for a target that was generated while it was open.
    price.loc[panel[-1], "bitcoin"] = 50.0
    spec = PhaseMomentumSpec(btc_ma_window=2, btc_confirm_days=1)

    payload = _payload(_market(price), _built(index), spec, index)

    assert payload["as_of"] == "2024-01-15"
    assert payload["start_date"] == "2024-01-01"
    assert payload["end_date"] == "2024-01-15"
    assert payload["panel_last_date"] == "2024-01-16"
    assert payload["btc_gate_open"] is True
    assert payload["next_check_date"] == "2024-01-16"


def test_as_of_outside_the_evaluated_range_is_rejected() -> None:
    panel = pd.date_range("2024-01-01", periods=16, freq="D")
    index = panel[:-1]
    market = _market(_price(panel))
    spec = PhaseMomentumSpec(btc_ma_window=2, btc_confirm_days=1)

    # The panel has 2024-01-16, but the evaluated range ends on 2024-01-15.
    with pytest.raises(ValueError, match="after the evaluated range"):
        _payload(market, _built(index), spec, index, as_of="2024-01-16")
    with pytest.raises(ValueError, match="on or before 2023-12-31"):
        _payload(market, _built(index), spec, index, as_of="2023-12-31")


def test_trade_required_only_when_the_latest_target_is_dated_as_of() -> None:
    index = pd.date_range("2024-01-01", periods=16, freq="D")
    market = _market(_price(index))
    built = _built(index)
    spec = PhaseMomentumSpec(btc_ma_window=2, btc_confirm_days=1)

    on_target_day = _payload(market, built, spec, index, as_of=index[9])
    later = _payload(market, built, spec, index, as_of=index[-1])

    assert on_target_day["as_of"] == on_target_day["latest_target_date"] == "2024-01-10"
    assert on_target_day["trade_required"] is True
    assert on_target_day["targets"] == {"ethereum": 0.25, "solana": 0.25}
    # Until the new target is traded the book is still the 2024-01-01 one.
    assert on_target_day["current_weights"] == pytest.approx({"ethereum": 0.50})
    assert later["latest_target_date"] == "2024-01-10"
    assert later["trade_required"] is False


def _drifted_market(index: pd.DatetimeIndex) -> MarketDataBundle:
    price = _price(index)
    # Ethereum doubles two days after the 2024-01-10 target was executed.
    price.loc[index[12]:, "ethereum"] = 200.0
    return _market(price)


def test_current_weights_are_the_production_engines_drifted_book() -> None:
    index = pd.date_range("2024-01-01", periods=16, freq="D")
    market = _drifted_market(index)
    spec = PhaseMomentumSpec(btc_ma_window=2, btc_confirm_days=1)

    payload = _payload(market, _built(index), spec, index, cost_bps=20.0)

    assert payload["trade_required"] is False
    # ``targets`` stays the target to trade toward; the book has drifted:
    # 0.25 x 2 / 1.25 = 0.40 ethereum and 0.25 / 1.25 = 0.20 solana.
    assert payload["targets"] == {"ethereum": 0.25, "solana": 0.25}
    assert payload["current_weights"] == pytest.approx({"ethereum": 0.40, "solana": 0.20})
    assert payload["current_gross_exposure"] == pytest.approx(0.60)
    assert payload["cost_bps"] == 20.0


def _patch_inputs(
    monkeypatch: pytest.MonkeyPatch,
    index: pd.DatetimeIndex,
    captured: dict[str, str] | None = None,
) -> None:
    config = load_config("config/base.yaml")
    market = _drifted_market(index)
    built = _built(index)

    def load_market(config_path: str, *, start_date: str, end_date: str):
        if captured is not None:
            captured.update(start_date=start_date, end_date=end_date)
        return config, market, pd.DataFrame(), index

    def assess_last_day(_config, end):
        # The synthetic inputs are a finished panel; the real (gitignored)
        # data/processed/panel_daily.csv is not present on a CI runner, so the
        # completeness check must be faked here rather than read from disk.
        return LastDayCompleteness(
            date=pd.Timestamp(end),
            complete=True,
            assets=len(market.price.columns),
            median_volume_ratio=1.0,
            low_volume_share=0.0,
            market_cap_coverage=1.0,
            volume_floor=0.6,
            reasons=(),
            low_volume_assets=(),
        )

    monkeypatch.setattr(live, "_load_market", load_market)
    monkeypatch.setattr(live, "_assess_last_day", assess_last_day)
    # These tests exercise the single-book champion path; pin the frozen spec
    # to the sentinel so ``main`` uses the monkeypatched builder.
    monkeypatch.setattr(live, "FROZEN_TRIAL_ID", "champion-defaults")
    monkeypatch.setattr(live, "build_phase_momentum_targets", lambda *args, **kwargs: built)


def test_main_reports_the_engine_book_at_the_stated_cost(tmp_path, monkeypatch) -> None:
    index = pd.date_range("2024-01-01", periods=16, freq="D")
    _patch_inputs(monkeypatch, index)

    # A 2024 range is a backfill, so the freshness guard is skipped explicitly.
    live.main(["--output-dir", str(tmp_path / "default"), "--allow-stale"])
    live.main(["--output-dir", str(tmp_path / "stressed"), "--cost-bps", "50", "--allow-stale"])

    default = json.loads((tmp_path / "default" / "latest_signal.json").read_text(encoding="utf-8"))
    stressed = json.loads((tmp_path / "stressed" / "latest_signal.json").read_text(encoding="utf-8"))
    assert default["cost_bps"] == 20.0
    assert stressed["cost_bps"] == 50.0
    assert default["trade_required"] is False
    assert default["current_weights"] == pytest.approx({"ethereum": 0.40, "solana": 0.20})
    assert default["targets"] == {"ethereum": 0.25, "solana": 0.25}
    markdown = (tmp_path / "default" / "latest_signal.md").read_text(encoding="utf-8")
    assert "- Trade required: False" in markdown
    assert "| ethereum | 0.400000 |" in markdown
    assert "- Evaluated range: 2024-01-01 .. 2024-01-16 (phase offsets count from 2024-01-01)" in markdown
    assert "- Panel last date: 2024-01-16" in markdown


# 01:00 UTC on 2026-09-24: the latest completed UTC day is 2026-09-23.
NOW = datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc)


def test_freshness_guard_rejects_a_panel_older_than_the_tolerance() -> None:
    with pytest.raises(ValueError, match="stale") as error:
        _check_freshness(pd.Timestamp("2026-09-21"), max_staleness_days=1, now=NOW)

    message = str(error.value)
    assert "2026-09-21" in message
    assert "latest completed UTC day is 2026-09-23" in message
    assert "--allow-stale" in message


def test_freshness_guard_accepts_the_latest_completed_day_minus_the_tolerance() -> None:
    _check_freshness(pd.Timestamp("2026-09-22"), max_staleness_days=1, now=NOW)
    _check_freshness(pd.Timestamp("2026-09-23"), max_staleness_days=0, now=NOW)
    with pytest.raises(ValueError, match="stale"):
        _check_freshness(pd.Timestamp("2026-09-22"), max_staleness_days=0, now=NOW)


def test_freshness_guard_counts_utc_days_not_local_days() -> None:
    # 07:00 on 2026-09-24 in UTC+8 is still 2026-09-23 in UTC, so the latest
    # completed UTC day is 2026-09-22 even though the local calendar says 24th.
    shanghai_morning = datetime(2026, 9, 24, 7, 0, tzinfo=timezone(timedelta(hours=8)))

    _check_freshness(pd.Timestamp("2026-09-21"), max_staleness_days=1, now=shanghai_morning)
    with pytest.raises(ValueError, match="stale"):
        _check_freshness(pd.Timestamp("2026-09-20"), max_staleness_days=1, now=shanghai_morning)


def test_main_refuses_a_stale_panel_unless_explicitly_allowed(tmp_path, monkeypatch) -> None:
    index = pd.date_range("2024-01-01", periods=16, freq="D")
    _patch_inputs(monkeypatch, index)
    # The evaluated range ends 2024-01-16; the latest completed UTC day is
    # 2024-01-19, so one day of tolerance needs data through 2024-01-18.
    now = datetime(2024, 1, 20, 12, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="stale"):
        live.main(["--output-dir", str(tmp_path / "strict")], now=now)
    assert not (tmp_path / "strict").exists()

    live.main(["--output-dir", str(tmp_path / "tolerant"), "--max-staleness-days", "3"], now=now)
    live.main(["--output-dir", str(tmp_path / "backfill"), "--allow-stale"], now=now)
    assert (tmp_path / "tolerant" / "latest_signal.json").exists()
    assert (tmp_path / "backfill" / "latest_signal.json").exists()


def test_main_defaults_the_end_date_to_the_latest_completed_utc_day(tmp_path, monkeypatch) -> None:
    index = pd.date_range("2024-01-01", periods=16, freq="D")
    captured: dict[str, str] = {}
    _patch_inputs(monkeypatch, index, captured)
    # 07:00 on 2024-01-17 in UTC+8 is 23:00 on 2024-01-16 in UTC, a day that
    # has not closed yet.
    now = datetime(2024, 1, 17, 7, 0, tzinfo=timezone(timedelta(hours=8)))

    live.main(["--output-dir", str(tmp_path)], now=now)

    assert captured["end_date"] == "2024-01-15"


def test_rule_text_is_derived_from_the_spec_and_the_signals_built() -> None:
    index = pd.date_range("2024-01-01", periods=16, freq="D")
    market = _market(_price(index))
    spec = PhaseMomentumSpec(
        rebalance_days=5,
        phase_offsets=(0, 1, 2, 3, 4),
        hold_rank=3,
        btc_ma_window=150,
        btc_confirm_days=3,
        target_volatility=0.7,
        vol_window=30,
    )

    payload = _payload(market, _built(index), spec, index)

    assert payload["rule"] == (
        "Strict point-in-time Top20; 2 trailing-return signals (signal_a, signal_b) "
        "x 5 calendar phases of a 5D rebalance cycle; hold while in Top3; "
        "BTC 150D MA + confirm3; 30D volatility target at 70%; "
        "long-only spot, no leverage; T+1"
    )
    assert payload["signal_names"] == ["signal_a", "signal_b"]
    assert payload["target_spec"] == {**asdict(spec), "phase_offsets": [0, 1, 2, 3, 4]}

    overlays = PhaseMomentumSpec(
        use_btc_gate=False,
        use_volatility_target=False,
        stop_loss_kind="trailing",
        stop_loss_pct=0.25,
        use_asset_trend_filter=True,
        asset_ma_window=50,
    )
    rule = _payload(market, _built(index), overlays, index)["rule"]
    assert "no BTC gate; no volatility target; trailing stop at 25%; asset above its 50D MA" in rule
    assert "BTC 100D MA" not in rule


def _verdict(complete: bool) -> LastDayCompleteness:
    return LastDayCompleteness(
        date=pd.Timestamp("2024-01-16"),
        complete=complete,
        assets=18,
        median_volume_ratio=1.02 if complete else 0.41,
        low_volume_share=0.1 if complete else 0.9,
        market_cap_coverage=1.0,
        volume_floor=0.60,
        reasons=() if complete else ("median last-day volume ratio 0.41 is below the weekday floor 0.60",),
        low_volume_assets=() if complete else ("bitcoin", "ethereum"),
    )


def test_main_refuses_a_partial_last_day_unless_explicitly_allowed(tmp_path, monkeypatch) -> None:
    index = pd.date_range("2024-01-01", periods=16, freq="D")
    _patch_inputs(monkeypatch, index)
    monkeypatch.setattr(live, "_assess_last_day", lambda config, end: _verdict(False))
    # The latest completed UTC day is 2024-01-16, so the freshness guard passes.
    now = datetime(2024, 1, 17, 12, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="partial") as error:
        live.main(["--output-dir", str(tmp_path / "strict")], now=now)
    assert "--allow-partial-day" in str(error.value)
    assert "0.41" in str(error.value)
    assert not (tmp_path / "strict").exists()

    live.main(["--output-dir", str(tmp_path / "override"), "--allow-partial-day"], now=now)
    payload = json.loads((tmp_path / "override" / "latest_signal.json").read_text(encoding="utf-8"))
    assert payload["last_day_check"]["complete"] is False
    assert payload["last_day_check"]["reasons"] == [
        "median last-day volume ratio 0.41 is below the weekday floor 0.60"
    ]


def test_main_records_a_passed_last_day_check(tmp_path, monkeypatch) -> None:
    index = pd.date_range("2024-01-01", periods=16, freq="D")
    _patch_inputs(monkeypatch, index)
    monkeypatch.setattr(live, "_assess_last_day", lambda config, end: _verdict(True))
    now = datetime(2024, 1, 17, 12, 0, tzinfo=timezone.utc)

    live.main(["--output-dir", str(tmp_path)], now=now)

    payload = json.loads((tmp_path / "latest_signal.json").read_text(encoding="utf-8"))
    assert payload["last_day_check"]["complete"] is True
    assert payload["last_day_check"]["date"] == "2024-01-16"
    markdown = (tmp_path / "latest_signal.md").read_text(encoding="utf-8")
    assert "- Last day complete: True" in markdown

def _two_book_build(index: pd.DatetimeIndex) -> tuple[PhaseMomentumBuildResult, tuple]:
    """A synthetic 2-book build: book A's 6 sleeves then book B's 6."""
    book_a = PhaseMomentumSpec(btc_ma_window=2, btc_confirm_days=1)
    book_b = PhaseMomentumSpec(
        btc_ma_window=2,
        btc_confirm_days=1,
        breadth_threshold=0.50,
        breadth_ma_window=50,
    )
    books = ((book_a, 0.5), (book_b, 0.5))
    sleeves = tuple(
        _sleeve(name, phase, index, {0: ("ethereum", 0.5)})
        for name in ("signal_a", "signal_b")
        for phase in (0, 1, 2)
    ) * 2
    built = PhaseMomentumBuildResult(
        targets={index[0]: pd.Series({"ethereum": 0.5})},
        exposures={index[0]: 0.5},
        selection_history=pd.DataFrame(),
        sleeve_targets=sleeves,
    )
    return built, books


def test_book_labels_split_multi_book_sleeves_in_build_order() -> None:
    index = pd.date_range("2024-01-01", periods=16, freq="D")
    built, books = _two_book_build(index)

    labels = live._book_labels(built, books)

    assert labels == [0] * 6 + [1] * 6


def test_multi_book_payload_names_the_h3_books_and_labels_every_sleeve() -> None:
    index = pd.date_range("2024-01-01", periods=16, freq="D")
    market = _market(_price(index))
    built, books = _two_book_build(index)
    book_a = books[0][0]
    result = _production_result(
        load_config("config/base.yaml"), market, built, index, cost_bps=20.0
    )

    payload = _latest_signal_payload(
        market,
        built,
        book_a,
        index,
        engine_weights=result.weights,
        cost_bps=20.0,
        as_of=index[-1],
        books=books,
        trial_id="PR2026-10-H3",
    )

    assert payload["trial_id"] == "PR2026-10-H3"
    assert payload["target_spec"]["construction"].startswith("build_parameter_ensemble_targets")
    assert [book["weight"] for book in payload["target_spec"]["books"]] == [0.5, 0.5]
    assert "2 books at [0.50, 0.50]" in payload["rule"]
    assert "book B: hold while in Top2" in payload["rule"]
    assert "Top20 breadth >= 0.50 above own 50D SMA" in payload["rule"]
    assert {sleeve["book"] for sleeve in payload["sleeves"]} == {0, 1}
    assert len(payload["sleeves"]) == 12

def test_frozen_spec_is_the_h3_breadth_cogate_blend() -> None:
    # The live signal must default to the adopted frozen spec, not the
    # pre-switch single-book champion.
    assert live.FROZEN_TRIAL_ID == "PR2026-10-H3"


def test_main_defaults_to_the_frozen_trial_id(tmp_path, monkeypatch) -> None:
    index = pd.date_range("2024-01-01", periods=16, freq="D")
    _patch_inputs(monkeypatch, index)
    monkeypatch.setattr(live, "FROZEN_TRIAL_ID", "PR2026-10-H3")

    def fake_resolve(market, universe, idx, trial_id):
        built = _built(idx)
        spec = PhaseMomentumSpec(btc_ma_window=2, btc_confirm_days=1)
        assert trial_id is None
        return ((spec, 1.0),), spec, built, "PR2026-10-H3"

    monkeypatch.setattr(live, "_resolve_build", fake_resolve)

    live.main(["--output-dir", str(tmp_path), "--allow-stale"])

    payload = json.loads((tmp_path / "latest_signal.json").read_text(encoding="utf-8"))
    assert payload["trial_id"] == "PR2026-10-H3"
