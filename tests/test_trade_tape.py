from __future__ import annotations

import zipfile
import io
from pathlib import Path

import pandas as pd
import pytest

from atlas20.derivatives.trade_tape import (
    TradeTapeError,
    parse_depth_xlsx,
    parse_trade_csv,
    simulate_maker_order,
)


def _trade(timestamp: str, price: float, side: str, notional: float, trade_id: int = 1) -> dict[str, object]:
    return {
        "trade_id": trade_id,
        "timestamp": int(pd.Timestamp(timestamp).timestamp() * 1000),
        "price": price,
        "side": side,
        "volume(quote)": notional,
        "size(base)": notional / price,
    }


def test_parse_trade_csv_preserves_aggressor_side_and_timestamp() -> None:
    csv = pd.DataFrame(
        [
            _trade("2026-01-04T03:00:01Z", 101.0, "buy", 7.0, 1),
            _trade("2026-01-04T03:00:02Z", 100.0, "sell", 12.0, 2),
        ]
    ).to_csv(index=False).encode()

    trades = parse_trade_csv(csv)

    assert [trade.trade_id for trade in trades] == ["1", "2"]
    assert [trade.side for trade in trades] == ["buy", "sell"]
    assert trades[0].timestamp == pd.Timestamp("2026-01-04T03:00:01Z")
    assert trades[1].quote_notional == pytest.approx(12.0)


def test_parse_trade_csv_rejects_conflicting_duplicate_trade_ids() -> None:
    csv = pd.DataFrame(
        [
            _trade("2026-01-04T03:00:01Z", 100.0, "buy", 7.0, 1),
            _trade("2026-01-04T03:00:02Z", 101.0, "sell", 8.0, 1),
        ]
    ).to_csv(index=False).encode()

    with pytest.raises(TradeTapeError, match="conflicting duplicate trade_id"):
        parse_trade_csv(csv)


def test_simulate_maker_order_uses_strict_through_for_buy_fill() -> None:
    entry = pd.Timestamp("2026-01-04T03:00:00Z")
    trades = parse_trade_csv(
        pd.DataFrame(
            [
                _trade("2026-01-04T03:15:00Z", 99.95, "sell", 40.0, 1),
                _trade("2026-01-04T03:16:00Z", 99.93, "sell", 100.0, 2),
            ]
        ).to_csv(index=False).encode()
    )

    outcome = simulate_maker_order(
        trades,
        side="buy",
        reference_price=100.0,
        order_notional=100.0,
        entry_time=entry,
    )

    assert outcome.limit_price == pytest.approx(99.95)
    assert outcome.maker_filled_notional == pytest.approx(100.0)
    assert outcome.taker_filled_notional == pytest.approx(0.0)
    assert outcome.maker_fill_ratio == pytest.approx(1.0)
    assert outcome.effective_cost_bps == pytest.approx(2.0 - 5.0, abs=1e-6)
    assert outcome.improvement_bps == pytest.approx(23.0, abs=1e-6)


def test_simulate_maker_order_applies_adverse_guard_to_the_remainder() -> None:
    entry = pd.Timestamp("2026-01-04T03:00:00Z")
    trades = parse_trade_csv(
        pd.DataFrame(
            [
                _trade("2026-01-04T03:10:00Z", 99.69, "buy", 30.0, 1),
            ]
        ).to_csv(index=False).encode()
    )

    outcome = simulate_maker_order(
        trades,
        side="sell",
        reference_price=100.0,
        order_notional=100.0,
        entry_time=entry,
    )

    assert outcome.maker_filled_notional == pytest.approx(0.0)
    assert outcome.taker_filled_notional == pytest.approx(100.0)
    assert outcome.guard_triggered is True
    assert outcome.effective_cost_bps == pytest.approx(51.0)


def test_parse_depth_xlsx_reads_inline_string_cells_and_sorts_rows() -> None:
    sheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="inlineStr"><is><t>timestamp</t></is></c>
      <c r="B1" t="inlineStr"><is><t>ask_price</t></is></c>
      <c r="C1" t="inlineStr"><is><t>bid_price</t></is></c>
      <c r="D1" t="inlineStr"><is><t>ask_volume</t></is></c>
      <c r="E1" t="inlineStr"><is><t>bid_volume</t></is></c>
    </row>
    <row r="2">
      <c r="A2" t="n"><v>1767495602</v></c>
      <c r="B2" t="inlineStr"><is><t>100.2</t></is></c>
      <c r="C2" t="inlineStr"><is><t>100.0</t></is></c>
      <c r="D2" t="inlineStr"><is><t>2</t></is></c>
      <c r="E2" t="inlineStr"><is><t>3</t></is></c>
    </row>
    <row r="3">
      <c r="A3" t="n"><v>1767495600</v></c>
      <c r="B3" t="inlineStr"><is><t>100.1</t></is></c>
      <c r="C3" t="inlineStr"><is><t>99.9</t></is></c>
      <c r="D3" t="inlineStr"><is><t>1</t></is></c>
      <c r="E3" t="inlineStr"><is><t>4</t></is></c>
    </row>
  </sheetData>
</worksheet>
"""
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("xl/worksheets/sheet1.xml", sheet)

    books = parse_depth_xlsx(archive.getvalue())

    assert len(books) == 2
    assert books[0].timestamp == pd.Timestamp("2026-01-04T03:00:00Z")
    assert books[0].bid_price == pytest.approx(99.9)
    assert books[1].ask_price == pytest.approx(100.2)


def test_parse_depth_xlsx_unwraps_nested_xlsx_payload() -> None:
    sheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="inlineStr"><is><t>timestamp</t></is></c>
      <c r="B1" t="inlineStr"><is><t>ask_price</t></is></c>
      <c r="C1" t="inlineStr"><is><t>bid_price</t></is></c>
      <c r="D1" t="inlineStr"><is><t>ask_volume</t></is></c>
      <c r="E1" t="inlineStr"><is><t>bid_volume</t></is></c>
    </row>
    <row r="2">
      <c r="A2" t="n"><v>1767495600</v></c>
      <c r="B2" t="inlineStr"><is><t>100.2</t></is></c>
      <c r="C2" t="inlineStr"><is><t>100.0</t></is></c>
      <c r="D2" t="inlineStr"><is><t>2</t></is></c>
      <c r="E2" t="inlineStr"><is><t>3</t></is></c>
    </row>
  </sheetData>
</worksheet>
"""
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as handle:
        handle.writestr("xl/worksheets/sheet1.xml", sheet)
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as handle:
        handle.writestr("20260104_3.xlsx", inner.getvalue())

    books = parse_depth_xlsx(outer.getvalue())

    assert len(books) == 1
    assert books[0].mid_price == pytest.approx(100.1)


def test_history_cache_path_is_namespaced_by_kind_symbol_and_date(tmp_path) -> None:
    from scripts import simulate_bitget_trade_tape_maker as simulator

    url = "https://example.test/download/20260104_001.zip"
    btc = simulator._history_cache_path(
        tmp_path, kind="depth", symbol="BTCUSDT", date="2026-01-04", url=url
    )
    doge = simulator._history_cache_path(
        tmp_path, kind="depth", symbol="DOGEUSDT", date="2026-01-04", url=url
    )

    assert btc == tmp_path / "depth" / "BTCUSDT" / "2026-01-04" / "20260104_001.zip"
    assert doge != btc
    assert doge.parent.parent.name == "DOGEUSDT"


def test_parse_trade_csv_unwraps_bitget_zip_payload() -> None:
    csv = pd.DataFrame(
        [_trade("2026-01-04T03:00:01Z", 100.0, "sell", 12.0, 1)]
    ).to_csv(index=False).encode()
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as handle:
        handle.writestr("DOGEUSDT_UMCBL_20260104_001.csv", csv)

    trades = parse_trade_csv(payload.getvalue())

    assert len(trades) == 1
    assert trades[0].quote_notional == pytest.approx(12.0)


def test_parse_trade_csv_rejects_any_duplicate_trade_id() -> None:
    trade = _trade("2026-01-04T03:00:01Z", 100.0, "buy", 7.0, 1)
    csv = pd.DataFrame([trade, trade]).to_csv(index=False).encode()

    with pytest.raises(TradeTapeError, match="duplicate trade_id"):
        parse_trade_csv(csv)


def test_parse_trade_csv_rejects_out_of_order_timestamps() -> None:
    csv = pd.DataFrame(
        [
            _trade("2026-01-04T03:00:02Z", 100.0, "buy", 7.0, 2),
            _trade("2026-01-04T03:00:01Z", 101.0, "sell", 8.0, 1),
        ]
    ).to_csv(index=False).encode()

    with pytest.raises(TradeTapeError, match="timestamps are not nondecreasing"):
        parse_trade_csv(csv)


def test_load_trade_window_does_not_silently_skip_malformed_files(monkeypatch) -> None:
    from scripts import simulate_bitget_trade_tape_maker as simulator

    monkeypatch.setattr(
        simulator,
        "_download_cached",
        lambda *args, **kwargs: b"not a trade file",
    )
    entry = pd.Timestamp("2026-01-04T03:00:00Z")

    with pytest.raises(TradeTapeError, match="trade CSV"):
        simulator._load_trade_window(
            object(),  # type: ignore[arg-type]
            [{"fileUrl": "https://example.test/20260104_001.zip"}],
            symbol="DOGEUSDT",
            date="2026-01-04",
            entry_time=entry,
            end_time=entry + pd.Timedelta(hours=2),
            cache_dir=Path("."),
            timeout_seconds=1.0,
        )


def test_normalise_depth_scale_aligns_power_of_ten_contract_units() -> None:
    from scripts import simulate_bitget_trade_tape_maker as simulator
    from atlas20.derivatives.trade_tape import TopOfBook

    book = TopOfBook(
        timestamp=pd.Timestamp("2026-03-01T02:59:51Z"),
        ask_price=0.005928,
        bid_price=0.005926,
        ask_volume=100.0,
        bid_volume=100.0,
    )

    adjusted, factor = simulator._normalise_depth_scale(
        book,
        trade_prices=(5.922e-06, 5.92e-06, 5.925e-06),
    )

    assert factor == pytest.approx(1000.0)
    assert adjusted.ask_price == pytest.approx(0.000005928)
    assert adjusted.bid_price == pytest.approx(0.000005926)


def test_normalise_depth_scale_rejects_non_power_of_ten_mismatch() -> None:
    from scripts import simulate_bitget_trade_tape_maker as simulator
    from atlas20.derivatives.trade_tape import TopOfBook

    book = TopOfBook(
        timestamp=pd.Timestamp("2026-03-01T02:59:51Z"),
        ask_price=2.0,
        bid_price=1.9,
        ask_volume=100.0,
        bid_volume=100.0,
    )

    with pytest.raises(TradeTapeError, match="depth/trade price scale mismatch"):
        simulator._normalise_depth_scale(book, trade_prices=(1.0, 1.01, 0.99))


def test_history_date_uses_bitget_utc_plus_eight_day_boundary() -> None:
    from scripts import simulate_bitget_trade_tape_maker as simulator

    assert simulator._history_date(pd.Timestamp("2026-03-15T03:00:00Z")) == "2026-03-15"
    assert simulator._history_date(pd.Timestamp("2026-03-15T21:00:00Z")) == "2026-03-16"


def test_history_dates_include_every_utc_plus_eight_day_touched() -> None:
    from scripts import simulate_bitget_trade_tape_maker as simulator

    dates = simulator._history_dates(
        pd.Timestamp("2026-03-15T16:00:00Z"),
        pd.Timestamp("2026-03-15T18:00:00Z"),
    )

    assert dates == ("2026-03-16",)
    dates = simulator._history_dates(
        pd.Timestamp("2026-03-15T14:30:00Z"),
        pd.Timestamp("2026-03-15T16:30:00Z"),
    )
    assert dates == ("2026-03-15", "2026-03-16")


def test_acceptance_checks_require_coverage_fill_improvement_and_event_count() -> None:
    from scripts import simulate_bitget_trade_tape_maker as simulator

    passing = simulator._acceptance_checks(
        covered_events=250,
        event_coverage=0.75,
        notional_coverage=0.80,
        strict_fill_rate=0.72,
        weighted_improvement_bps=6.0,
    )
    assert all(passing.values())

    failing = simulator._acceptance_checks(
        covered_events=199,
        event_coverage=0.69,
        notional_coverage=0.69,
        strict_fill_rate=0.69,
        weighted_improvement_bps=4.99,
    )
    assert not any(failing.values())


def test_post_file_list_retries_transient_http_errors(monkeypatch) -> None:
    from scripts import simulate_bitget_trade_tape_maker as simulator

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise simulator.requests.HTTPError(f"status {self.status_code}")

        def json(self) -> dict[str, object]:
            return self._payload

    class FakeSession:
        def __init__(self) -> None:
            self.calls = 0

        def post(self, *args, **kwargs) -> FakeResponse:
            self.calls += 1
            if self.calls == 1:
                return FakeResponse(429, {})
            return FakeResponse(
                200,
                {"code": "0", "data": [{"fileUrl": "https://example.test/20260104.zip"}]},
            )

    session = FakeSession()
    monkeypatch.setattr(simulator.time, "sleep", lambda _seconds: None)

    files = simulator._post_file_list(
        session,  # type: ignore[arg-type]
        symbol="DOGEUSDT",
        business_type=2,
        date="2026-01-04",
        retries=3,
    )

    assert session.calls == 2
    assert files == [{"fileUrl": "https://example.test/20260104.zip"}]


def test_robustness_metrics_report_weekly_breadth_and_top_asset_dependence() -> None:
    from scripts import simulate_bitget_trade_tape_maker as simulator

    events = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01T03:00:00Z",
                    "2026-01-02T03:00:00Z",
                    "2026-01-08T03:00:00Z",
                    "2026-01-09T03:00:00Z",
                ]
            ),
            "asset": ["alpha", "beta", "alpha", "beta"],
            "requested_notional": [100.0, 50.0, 100.0, 50.0],
            "strict_effective_cost_bps": [0.0, 10.0, 0.0, 10.0],
            "strict_improvement_bps": [20.0, 10.0, 20.0, 10.0],
            "strict_maker_filled_notional": [100.0, 25.0, 100.0, 25.0],
        }
    )

    metrics = simulator._robustness_metrics(events)

    assert metrics["weeks"] == 2
    assert metrics["positive_weeks"] == 2
    assert metrics["weeks_ge_5bps"] == 2
    assert metrics["top_savings_asset"] == "alpha"
    assert metrics["top_savings_share"] == pytest.approx(0.8)
    assert metrics["ex_top_savings_improvement_bps"] == pytest.approx(10.0)


def test_simulate_maker_order_applies_fill_haircut_to_available_volume() -> None:
    entry = pd.Timestamp("2026-01-04T03:00:00Z")
    trades = parse_trade_csv(
        pd.DataFrame(
            [
                _trade("2026-01-04T03:15:00Z", 99.93, "sell", 100.0, 1),
            ]
        ).to_csv(index=False).encode()
    )

    outcome = simulate_maker_order(
        trades,
        side="buy",
        reference_price=100.0,
        order_notional=100.0,
        entry_time=entry,
        fill_haircut=0.25,
    )

    assert outcome.maker_filled_notional == pytest.approx(25.0)
    assert outcome.taker_filled_notional == pytest.approx(75.0)
    assert outcome.maker_fill_ratio == pytest.approx(0.25)
    assert outcome.status == "timeout"


def test_haircut_summary_reports_fill_and_weighted_cost_by_scenario() -> None:
    from scripts import simulate_bitget_trade_tape_maker as simulator

    events = pd.DataFrame(
        {
            "requested_notional": [100.0, 100.0],
            "haircut_025_maker_filled_notional": [25.0, 0.0],
            "haircut_025_taker_filled_notional": [75.0, 100.0],
            "haircut_025_effective_cost_bps": [10.0, 50.0],
            "haircut_025_improvement_bps": [10.0, -30.0],
            "haircut_025_guard_triggered": [False, True],
            "haircut_025_status": ["timeout", "guard"],
        }
    )

    summary = simulator._haircut_summary(events, (0.25,))

    assert len(summary) == 1
    row = summary.iloc[0]
    assert row["haircut"] == pytest.approx(0.25)
    assert row["events"] == 2
    assert row["strict_maker_fill_rate"] == pytest.approx(0.125)
    assert row["strict_effective_cost_bps"] == pytest.approx(30.0)
    assert row["strict_improvement_bps"] == pytest.approx(-10.0)
    assert row["strict_guard_event_share"] == pytest.approx(0.5)


def test_haircut_breakdowns_cover_side_month_and_asset() -> None:
    from scripts import simulate_bitget_trade_tape_maker as simulator

    events = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-01-01T03:00:00Z", "2026-02-01T03:00:00Z"]),
            "date": ["2026-01-01", "2026-02-01"],
            "asset": ["alpha", "beta"],
            "exec_side": ["buy", "sell"],
            "requested_notional": [100.0, 50.0],
            "haircut_025_maker_filled_notional": [25.0, 40.0],
            "haircut_025_taker_filled_notional": [75.0, 10.0],
            "haircut_025_effective_cost_bps": [10.0, 5.0],
            "haircut_025_improvement_bps": [10.0, 15.0],
            "haircut_025_guard_triggered": [True, False],
            "haircut_025_status": ["guard", "filled"],
        }
    )

    breakdowns = simulator._haircut_breakdowns(events, (0.25,))

    assert set(breakdowns) == {"side", "month", "asset"}
    assert breakdowns["side"]["group"].tolist() == ["buy", "sell"]
    assert breakdowns["month"]["group"].tolist() == ["2026-01", "2026-02"]
    assert breakdowns["asset"]["group"].tolist() == ["alpha", "beta"]


def test_haircut_acceptance_requires_25pct_improvement_and_monotonicity() -> None:
    from scripts import simulate_bitget_trade_tape_maker as simulator

    summary = pd.DataFrame(
        {
            "haircut": [0.25, 0.5, 0.75],
            "strict_improvement_bps": [6.0, 8.0, 9.0],
        }
    )
    passing = simulator._haircut_acceptance(
        summary,
        coverage_checks={"events_ge_200": True, "notional_coverage_ge_70pct": True},
    )
    assert all(passing.values())

    failing_summary = summary.copy()
    failing_summary.loc[0, "strict_improvement_bps"] = 4.99
    failing_summary.loc[1, "strict_improvement_bps"] = 4.5
    failing = simulator._haircut_acceptance(
        failing_summary,
        coverage_checks={"events_ge_200": True, "notional_coverage_ge_70pct": True},
    )
    assert not failing["haircut_25_improvement_ge_5bps"]
    assert not failing["improvement_monotonic_with_haircut"]


def test_haircut_acceptance_treats_single_scenario_monotonicity_as_not_applicable() -> None:
    from scripts import simulate_bitget_trade_tape_maker as simulator

    summary = pd.DataFrame({"haircut": [0.25], "strict_improvement_bps": [10.0]})

    checks = simulator._haircut_acceptance(
        summary,
        coverage_checks={"events_ge_200": True, "notional_coverage_ge_70pct": True},
    )

    assert checks["improvement_monotonic_with_haircut"] is True
