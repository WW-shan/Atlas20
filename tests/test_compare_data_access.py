from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from atlas20.api.data_access.compare import UnknownCompareIdError, load_compare_from_reports
from atlas20.api.settings import Settings
from tests.conftest import (
    EQUITY_HEADER,
    make_rebalance_row,
    write_equity_csv,
    write_rebalance_csv,
    write_summary_csv,
)


def _write_compare_csvs(
    root,
    *,
    dates: list[str] | None = None,
    summary_rows: list[str] | None = None,
    strategies: list[str] | None = None,
) -> None:
    if summary_rows is None:
        summary_rows = [
            "BTC_BH__always_on,0.20,0.10,0.20,0.80,1.10,-0.30,0.33,0.50,0.20,0.10,1",
            "TOP20_MOM_FAST,0.80,0.40,0.25,1.50,2.20,-0.20,2.00,0.62,4.00,0.40,20",
            "TOP20_SECTOR_VALUE,0.55,0.25,0.22,1.90,2.50,-0.15,1.66,0.58,2.50,0.30,20",
            "ATLAS_ALPHA,0.70,0.30,0.20,2.40,3.00,-0.12,2.50,0.65,3.00,0.35,20",
        ]
    if strategies is None:
        strategies = [row.split(",", maxsplit=1)[0] for row in summary_rows]
    if dates is None:
        dates = pd.date_range("2026-04-01", "2026-05-19", freq="D").strftime("%Y-%m-%d").tolist()

    write_summary_csv(root / "reports", summary_rows)

    equity_lines = [f"{EQUITY_HEADER}{','.join(strategies)}"]
    for offset, row_date in enumerate(dates):
        values = [str(100000 + (offset * (index + 1) * 100)) for index, _ in enumerate(strategies)]
        equity_lines.append(",".join([row_date, *values]))
    write_equity_csv(root / "reports", equity_lines[1:], header=equity_lines[0])

    rebalance_rows = [
        make_rebalance_row(symbol, "2026-05-18", rank, sector=sector)
        for rank, (symbol, sector) in enumerate(
            [
                ("BTC", "Layer1"),
                ("ETH", "Layer1"),
                ("SOL", "Layer1"),
                ("LINK", "Oracle"),
                ("AAVE", "DeFi"),
                ("UNI", "DeFi"),
                ("ARB", "Layer2"),
                ("OP", "Layer2"),
                ("SUI", "Layer1"),
                ("TIA", "Data"),
                ("INJ", "DeFi"),
                ("SEI", "Layer1"),
                ("ATOM", "Layer1"),
                ("DOT", "Layer1"),
                ("NEAR", "Layer1"),
                ("AVAX", "Layer1"),
                ("BNB", "Exchange"),
                ("XRP", "Payments"),
                ("ADA", "Layer1"),
                ("DOGE", "Meme"),
            ],
            1,
        )
    ]
    write_rebalance_csv(root / "data", rebalance_rows)


def _settings(root) -> Settings:
    return Settings(report_root=root / "reports", data_root=root / "data", anchor_date=date(2026, 5, 19))


def test_load_compare_filters_by_run_ids(tmp_path):
    _write_compare_csvs(tmp_path)

    payload = load_compare_from_reports(_settings(tmp_path), ["BTC_BH__always_on", "ATLAS_ALPHA"], "ALL")

    assert set(payload["metrics"]["cagr"]) == {"BTC_BH__always_on", "ATLAS_ALPHA"}
    assert set(payload["equity"][0]["values"]) == {"BTC_BH__always_on", "ATLAS_ALPHA"}


def test_load_compare_resolves_legacy_aliases(tmp_path):
    _write_compare_csvs(tmp_path)

    payload = load_compare_from_reports(_settings(tmp_path), ["atlas", "momentum", "meanrev"], "ALL")

    assert set(payload["metrics"]["sharpe"]) == {"ATLAS_ALPHA", "TOP20_MOM_FAST", "TOP20_SECTOR_VALUE"}


def test_load_compare_rejects_unknown_id(tmp_path):
    _write_compare_csvs(tmp_path)

    with pytest.raises(UnknownCompareIdError, match="NO_SUCH_STRATEGY"):
        load_compare_from_reports(_settings(tmp_path), ["BTC_BH__always_on", "NO_SUCH_STRATEGY"], "ALL")


def test_load_compare_all_unknown_raises_unknown_id_error(tmp_path):
    _write_compare_csvs(tmp_path)

    with pytest.raises(UnknownCompareIdError, match="unknown compare id\\(s\\): x, y"):
        load_compare_from_reports(_settings(tmp_path), ["x", "y"], "ALL")


def test_load_compare_rejects_nan_numeric_summary_values(tmp_path):
    summary_rows = [
        "BTC_BH__always_on,0.20,0.10,0.20,0.80,1.10,-0.30,0.33,0.50,0.20,0.10,1",
        "ATLAS_ALPHA,0.70,0.30,NaN,2.40,3.00,-0.12,2.50,0.65,3.00,0.35,20",
    ]
    _write_compare_csvs(tmp_path, summary_rows=summary_rows)

    with pytest.raises(ValueError, match="invalid numeric values"):
        load_compare_from_reports(_settings(tmp_path), ["ATLAS_ALPHA"], "ALL")


def test_load_compare_range_filter(tmp_path):
    dates = pd.date_range("2026-03-01", "2026-05-19", freq="D").strftime("%Y-%m-%d").tolist()
    _write_compare_csvs(tmp_path, dates=dates)

    payload = load_compare_from_reports(_settings(tmp_path), ["ATLAS_ALPHA"], "1M")

    assert payload["equity"][0]["ts"] >= "2026-04-19"
    assert payload["equity"][-1]["ts"] == "2026-05-19"


def test_load_compare_requires_anchor_for_bounded_ranges(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS20_ANCHOR_DATE", raising=False)
    _write_compare_csvs(tmp_path)
    settings = Settings(report_root=tmp_path / "reports", data_root=tmp_path / "data")

    with pytest.raises(ValueError, match="anchor_date"):
        load_compare_from_reports(settings, ["ATLAS_ALPHA"], "1M")


def test_load_compare_caps_at_180_points(tmp_path):
    dates = pd.date_range("2025-01-01", "2026-05-19", freq="D").strftime("%Y-%m-%d").tolist()
    _write_compare_csvs(tmp_path, dates=dates)

    payload = load_compare_from_reports(_settings(tmp_path), ["ATLAS_ALPHA"], "ALL")

    assert len(payload["equity"]) <= 180
    assert payload["equity"][0]["ts"] == "2025-01-01"
    assert payload["equity"][-1]["ts"] == "2026-05-19"


def test_load_compare_normalizes_to_base_one(tmp_path):
    _write_compare_csvs(tmp_path)

    payload = load_compare_from_reports(_settings(tmp_path), ["BTC_BH__always_on", "ATLAS_ALPHA"], "ALL")

    assert payload["equity"][0]["values"] == {"BTC_BH__always_on": 1.0, "ATLAS_ALPHA": 1.0}


def test_load_compare_overlap_uses_strategy_weights(tmp_path):
    summary_rows = [
        "ALPHA,0.20,0.20,0.10,1.10,1.20,-0.10,2.00,0.60,0.20,0.10,2",
        "BETA,0.10,0.10,0.10,0.80,1.00,-0.20,0.50,0.50,0.20,0.10,2",
    ]
    _write_compare_csvs(tmp_path, summary_rows=summary_rows)
    weights_dir = tmp_path / "reports" / "latest" / "weights"
    weights_dir.mkdir(parents=True)
    (weights_dir / "ALPHA.csv").write_text(
        "date,BTC,ETH,SOL\n"
        "2026-05-18,0.50,0.50,0.00\n"
        "2026-05-19,0.50,0.50,0.00\n",
        encoding="utf-8",
    )
    (weights_dir / "BETA.csv").write_text(
        "date,BTC,ETH,SOL\n"
        "2026-05-18,0.50,0.00,0.50\n"
        "2026-05-19,0.50,0.00,0.50\n",
        encoding="utf-8",
    )

    payload = load_compare_from_reports(_settings(tmp_path), ["ALPHA", "BETA"], "ALL")

    assert payload["overlap"]["symbols"] == ["ALPHA", "BETA"]
    assert payload["overlap"]["matrix"][0][1] == pytest.approx(1 / 3, abs=1e-4)
    assert payload["overlap"]["matrix"][1][0] == pytest.approx(1 / 3, abs=1e-4)
    assert payload["overlap"]["sharedHoldings"][0] == {"symbol": "BTC", "count": 2, "total": 2}


def test_load_compare_metrics_from_summary(tmp_path):
    _write_compare_csvs(tmp_path)

    payload = load_compare_from_reports(_settings(tmp_path), ["ATLAS_ALPHA"], "ALL")

    assert payload["metrics"]["cagr"]["ATLAS_ALPHA"] == 0.30
    assert payload["metrics"]["sharpe"]["ATLAS_ALPHA"] == 2.40
    assert payload["metrics"]["sortino"]["ATLAS_ALPHA"] == 3.00
    assert payload["metrics"]["max_dd"]["ATLAS_ALPHA"] == -0.12
    assert payload["metrics"]["calmar"]["ATLAS_ALPHA"] == 2.50
    assert payload["metrics"]["win_rate"]["ATLAS_ALPHA"] == 0.65
    assert payload["metrics"]["avg_turnover"]["ATLAS_ALPHA"] == 3.00
    assert payload["metrics"]["trades_per_year"]["ATLAS_ALPHA"] == 3.00
