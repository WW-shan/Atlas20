import os
import time
from datetime import date

import pandas as pd
import pytest

from atlas20.api.data_access.overview import (
    BTC_BENCHMARK,
    _build_equity_overlay,
    _compute_last_sync_seconds,
    _format_display_name,
    _parse_cadence,
    load_overview_from_reports,
)
from atlas20.api.schemas import OverviewPayload
from atlas20.api.settings import Settings


SUMMARY_HEADER = (
    "strategy,total_return,cagr,annualized_volatility,sharpe,sortino,max_drawdown,"
    "calmar,monthly_win_rate,annualized_turnover,avg_turnover_per_rebalance,average_holdings"
)


def _write_report_csvs(report_root, returns: list[float] | None = None) -> None:
    latest = report_root / "latest"
    latest.mkdir(parents=True)
    latest.joinpath("strategy_summary.csv").write_text(
        "\n".join(
            [
                SUMMARY_HEADER,
                "ALPHA,0.50,0.20,0.30,1.70,2.00,-0.20,1.00,0.60,4.00,0.50,2.00",
                "BETA,0.40,0.18,0.30,1.20,1.60,-0.25,0.80,0.55,3.00,0.40,2.00",
                "BTC_BH__always_on,0.30,0.15,0.35,0.90,1.20,-0.30,0.50,0.52,0.20,1.00,1.00",
            ]
        ),
        encoding="utf-8",
    )

    if returns is None:
        returns = [0.01, 0.02, -0.005, 0.015, 0.0, 0.01]
        rows = [
            "2026-01-31",
            "2026-02-28",
            "2026-03-31",
            "2026-04-30",
            "2026-05-31",
            "2026-06-30",
        ]
    else:
        rows = [f"2026-01-{day:02d}" for day in range(1, len(returns) + 1)]

    daily_lines = [",ALPHA,BETA,BTC_BH__always_on"]
    equity_lines = [",ALPHA,BETA,BTC_BH__always_on"]
    alpha_equity = beta_equity = btc_equity = 100000.0
    for row_date, alpha_return in zip(rows, returns, strict=True):
        beta_return = alpha_return / 2
        btc_return = alpha_return / 3
        alpha_equity *= 1 + alpha_return
        beta_equity *= 1 + beta_return
        btc_equity *= 1 + btc_return
        daily_lines.append(f"{row_date},{alpha_return},{beta_return},{btc_return}")
        equity_lines.append(f"{row_date},{alpha_equity},{beta_equity},{btc_equity}")

    latest.joinpath("daily_returns.csv").write_text("\n".join(daily_lines), encoding="utf-8")
    latest.joinpath("equity_curves.csv").write_text("\n".join(equity_lines), encoding="utf-8")


def test_load_overview_from_reports_validates_payload_and_strategy_ranking(tmp_path):
    _write_report_csvs(tmp_path)

    payload = load_overview_from_reports(Settings(report_root=tmp_path, anchor_date=date(2026, 6, 30)))
    model = OverviewPayload.model_validate(payload)

    assert model.champion.strategy == "ALPHA"
    assert len(model.top_strategies) == 3
    assert [row.strategy for row in model.top_strategies] == ["ALPHA", "BETA", "BTC_BH__always_on"]
    assert len(model.equity_curve) == 6


def test_load_overview_from_reports_computes_ytd_from_daily_returns(tmp_path):
    daily_returns = [0.01] * 30
    _write_report_csvs(tmp_path, returns=daily_returns)

    payload = load_overview_from_reports(Settings(report_root=tmp_path, anchor_date=date(2026, 1, 30)))

    assert payload["hero_kpi"]["ytdReturn"] == pytest.approx((1.01**30) - 1)


def test_load_overview_from_reports_missing_csv_raises_with_path(tmp_path):
    (tmp_path / "latest").mkdir()

    with pytest.raises(FileNotFoundError, match="strategy_summary.csv"):
        load_overview_from_reports(Settings(report_root=tmp_path, anchor_date=date(2026, 6, 30)))


def test_load_overview_from_reports_empty_csv_raises_value_error(tmp_path):
    latest = tmp_path / "latest"
    latest.mkdir()
    latest.joinpath("strategy_summary.csv").write_text("", encoding="utf-8")
    latest.joinpath("daily_returns.csv").write_text(",ALPHA\n2026-01-01,0.01", encoding="utf-8")
    latest.joinpath("equity_curves.csv").write_text(",ALPHA\n2026-01-01,101000", encoding="utf-8")

    with pytest.raises(ValueError):
        load_overview_from_reports(Settings(report_root=tmp_path, anchor_date=date(2026, 1, 1)))


def test_load_overview_from_reports_rejects_non_finite_numbers(tmp_path):
    latest = tmp_path / "latest"
    latest.mkdir()
    latest.joinpath("strategy_summary.csv").write_text(
        "\n".join(
            [
                SUMMARY_HEADER,
                "ALPHA,,0.20,0.30,1.70,2.00,-0.20,1.00,0.60,4.00,0.50,2.00",
            ]
        ),
        encoding="utf-8",
    )
    latest.joinpath("daily_returns.csv").write_text(
        ",ALPHA,BTC_BH__always_on\n2026-01-01,0.01,0.005",
        encoding="utf-8",
    )
    latest.joinpath("equity_curves.csv").write_text(
        ",ALPHA,BTC_BH__always_on\n2026-01-01,101000,100500",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Non-finite numeric value"):
        load_overview_from_reports(Settings(report_root=tmp_path, anchor_date=date(2026, 1, 1)))


def test_load_overview_from_reports_excludes_btc_benchmark_when_ranking(tmp_path):
    latest = tmp_path / "latest"
    latest.mkdir(parents=True)
    latest.joinpath("strategy_summary.csv").write_text(
        "\n".join(
            [
                SUMMARY_HEADER,
                "BTC_BH__always_on,0.40,0.15,0.35,5.00,1.20,-0.30,0.50,0.52,0.20,1.00,1.00",
                "ALPHA,0.50,0.20,0.30,1.70,2.00,-0.20,1.00,0.60,4.00,0.50,2.00",
                "BETA,0.40,0.18,0.30,1.20,1.60,-0.25,0.80,0.55,3.00,0.40,2.00",
            ]
        ),
        encoding="utf-8",
    )
    latest.joinpath("daily_returns.csv").write_text(
        "\n".join(
            [
                ",BTC_BH__always_on,ALPHA,BETA",
                "2026-01-01,0.01,0.01,0.01",
                "2026-02-28,0.02,0.02,0.02",
                "2026-03-31,-0.005,-0.005,-0.005",
                "2026-04-30,0.015,0.015,0.015",
                "2026-05-31,0.0,0.0,0.0",
                "2026-06-30,0.01,0.01,0.01",
            ]
        ),
        encoding="utf-8",
    )
    latest.joinpath("equity_curves.csv").write_text(
        "\n".join(
            [
                ",BTC_BH__always_on,ALPHA,BETA",
                "2026-01-01,100500,101000,101000",
                "2026-02-28,101505,103020,103020",
                "2026-03-31,100997.47,102504.9,102504.9",
                "2026-04-30,102512.43,104042.47,104042.47",
                "2026-05-31,102512.43,104042.47,104042.47",
                "2026-06-30,103537.55,105082.89,105082.89",
            ]
        ),
        encoding="utf-8",
    )

    payload = load_overview_from_reports(Settings(report_root=tmp_path, anchor_date=date(2026, 6, 30)))

    assert payload["champion"]["strategy"] == "ALPHA"


def test_format_display_name_produces_stable_labels():
    assert _format_display_name("TOP20_MOM_top8_biweekly__bull_only") == "Momentum Rotation · Top8 Biweekly · Bull Only"
    assert _format_display_name("TOP20_SECTOR_top3_biweekly__bull_only") == "Sector Rotation · Top3 Biweekly · Bull Only"
    assert _format_display_name("BTC_BH__always_on") == "BTC Benchmark · Always On"
    assert (
        _format_display_name("MOMENTUM_LEAD_TOP1_ALL_14D_STOP11_CONFIRM2_BTC_PARK")
        == "Momentum Lead Top1 All 14D Stop11 Confirm2 Btc Park"
    )


def test_parse_cadence_uses_slug_token():
    assert _parse_cadence("TOP20_MOM_top8_biweekly__bull_only", None) == "Biweekly"


def test_parse_cadence_falls_back_to_selection_history_median():
    history = pd.DataFrame(
        {
            "strategy": ["CUSTOM_ROTATION"] * 4,
            "rebalance_date": ["2026-01-01", "2026-01-15", "2026-01-29", "2026-02-12"],
        }
    )

    assert _parse_cadence("CUSTOM_ROTATION", history) == "Biweekly"


def test_parse_cadence_dedupes_rebalance_dates():
    history = pd.DataFrame(
        {
            "strategy": ["CUSTOM_ROTATION"] * 6,
            "rebalance_date": [
                "2026-01-01",
                "2026-01-01",
                "2026-01-15",
                "2026-01-15",
                "2026-01-29",
                "2026-01-29",
            ],
        }
    )

    assert _parse_cadence("CUSTOM_ROTATION", history) == "Biweekly"


def test_parse_cadence_returns_none_without_slug_or_history():
    assert _parse_cadence("CUSTOM_ROTATION", None) is None
    assert _parse_cadence("CUSTOM_ROTATION", pd.DataFrame()) is None


def test_compute_last_sync_seconds_uses_latest_pointer_and_missing_files(tmp_path):
    report_dir = tmp_path / "report_2026"
    report_dir.mkdir()
    (tmp_path / "latest.txt").write_text("report_2026", encoding="utf-8")
    stale_mtime = time.time() - 120
    os.utime(report_dir, (stale_mtime, stale_mtime))

    assert _compute_last_sync_seconds(tmp_path) >= 100
    assert _compute_last_sync_seconds(tmp_path / "missing") == 0


def test_compute_last_sync_seconds_clock_skew_returns_non_negative(tmp_path, monkeypatch):
    report_dir = tmp_path / "report_2026"
    report_dir.mkdir()
    (tmp_path / "latest.txt").write_text("report_2026", encoding="utf-8")
    future_mtime = time.time() + 120
    os.utime(report_dir, (future_mtime, future_mtime))
    monkeypatch.setattr(time, "time", lambda: future_mtime - 60)

    assert _compute_last_sync_seconds(tmp_path) == 0


def test_compute_last_sync_seconds_rejects_escaping_pointer(tmp_path):
    (tmp_path / "latest.txt").write_text("../escape", encoding="utf-8")

    assert _compute_last_sync_seconds(tmp_path) == 0


def test_build_equity_overlay_falls_back_to_all_when_ytd_empty():
    champion = "TOP20_MOM_top8_biweekly__bull_only"
    frame = pd.DataFrame(
        {
            champion: [100.0, 125.0],
            BTC_BENCHMARK: [100.0, 110.0],
        },
        index=pd.to_datetime(["2024-01-31", "2024-02-29"]),
    )

    overlay = _build_equity_overlay(frame, champion, date(2026, 1, 31))

    assert overlay["range"] == "ALL"
    assert overlay["series"]


def test_build_equity_overlay_nan_in_ytd_slice_uses_dropna():
    champion = "TOP20_MOM_top8_biweekly__bull_only"
    frame = pd.DataFrame(
        {
            champion: [100.0, float("nan"), 130.0],
            BTC_BENCHMARK: [100.0, 110.0, 140.0],
        },
        index=pd.to_datetime(["2026-01-31", "2026-02-28", "2026-03-31"]),
    )

    overlay = _build_equity_overlay(frame, champion, date(2026, 3, 31))

    assert overlay["range"] == "YTD"
    assert overlay["series"]
    assert all(pd.notna(point["atlas"]) and pd.notna(point["btc"]) for point in overlay["series"])


def test_build_equity_overlay_falls_back_to_all_when_ytd_rows_are_all_nan():
    champion = "TOP20_MOM_top8_biweekly__bull_only"
    frame = pd.DataFrame(
        {
            champion: [100.0, 112.0, 125.0, float("nan"), 150.0],
            BTC_BENCHMARK: [100.0, 108.0, 118.0, 132.0, float("nan")],
        },
        index=pd.to_datetime(["2025-10-31", "2025-11-30", "2025-12-31", "2026-01-31", "2026-02-28"]),
    )

    overlay = _build_equity_overlay(frame, champion, date(2026, 2, 28))

    assert overlay["range"] == "ALL"
    assert overlay["series"]
    assert all(pd.notna(point["atlas"]) and pd.notna(point["btc"]) for point in overlay["series"])


def test_build_equity_overlay_includes_display_labels():
    champion = "TOP20_SECTOR_top3_biweekly__bull_only"
    frame = pd.DataFrame(
        {
            champion: [100.0, 125.0],
            BTC_BENCHMARK: [100.0, 110.0],
        },
        index=pd.to_datetime(["2026-01-31", "2026-02-28"]),
    )

    overlay = _build_equity_overlay(frame, champion, date(2026, 2, 28))

    assert overlay["atlas_label"] == _format_display_name(champion)
    assert overlay["btc_label"] == "BTC Benchmark"
