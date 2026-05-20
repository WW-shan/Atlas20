from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from atlas20.backtest.engine import BacktestResult
from atlas20.reporting import report
from atlas20.reporting.report import export_result_tables


def _result(name: str, weights: pd.DataFrame) -> BacktestResult:
    dates = weights.index
    return BacktestResult(
        name=name,
        daily_returns=pd.Series([0.01, 0.02, -0.01, 0.00, 0.01], index=dates, name=name),
        equity_curve=pd.Series([101.0, 103.0, 102.0, 102.0, 103.0], index=dates, name=name),
        drawdown=pd.Series([0.0, 0.0, -0.01, -0.01, 0.0], index=dates, name=name),
        weights=weights,
        turnover=pd.Series([0.0, 0.3, 0.2, 0.0, 0.1], index=dates, name=name),
        holdings_count=(weights > 0).sum(axis=1),
        sector_exposure=pd.DataFrame(index=dates),
        rebalance_targets=weights.loc[[dates[0], dates[2]]],
    )


def _inputs() -> tuple[dict[str, BacktestResult], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    first_weights = pd.DataFrame(
        {
            "bitcoin": [0.60, 0.55, 0.00, 0.00, 0.00],
            "ethereum": [0.30, 0.35, 0.50, 0.45, 0.44],
            "solana": [0.10, 0.10, 0.25, 0.30, 0.31],
        },
        index=dates,
    )
    second_weights = pd.DataFrame(
        {
            "bitcoin": [0.00, 0.00, 0.70, 0.65, 0.64],
            "ethereum": [0.50, 0.50, 0.00, 0.00, 0.00],
            "solana": [0.50, 0.50, 0.30, 0.35, 0.36],
        },
        index=dates,
    )
    results = {
        "BTC_BH__always_on": _result("BTC_BH__always_on", first_weights),
        "TOP20_EQ__always_on": _result("TOP20_EQ__always_on", second_weights),
    }
    summary = pd.DataFrame(
        {
            "annualized_turnover": [1.0, 2.0],
            "avg_turnover_per_rebalance": [0.1, 0.2],
            "average_holdings": [2.0, 3.0],
        },
        index=list(results),
    )
    yearly_returns = pd.DataFrame({"BTC_BH__always_on": [0.1], "TOP20_EQ__always_on": [0.2]}, index=[2024])
    regime_performance = pd.DataFrame(
        {
            "strategy": ["BTC_BH__always_on"],
            "regime": ["bull"],
            "annualized_return": [0.1],
        }
    )
    return results, summary, yearly_returns, regime_performance


def _export(report_dir: Path) -> None:
    export_result_tables(*_inputs(), report_dir)


def test_export_result_tables_writes_weights_per_strategy(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "run_001"

    _export(report_dir)

    weights_dir = report_dir / "weights"
    assert sorted(path.name for path in weights_dir.glob("*.csv")) == [
        "BTC_BH__always_on.csv",
        "TOP20_EQ__always_on.csv",
    ]
    exported = pd.read_csv(weights_dir / "BTC_BH__always_on.csv", index_col=0)
    assert exported.columns.tolist() == ["bitcoin", "ethereum", "solana"]


def test_export_result_tables_writes_sorted_selection_history(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "run_001"

    _export(report_dir)

    history = pd.read_csv(report_dir / "selection_history.csv")
    assert history.columns.tolist() == [
        "rebalance_date",
        "strategy",
        "coin_id",
        "coin_rank",
        "coin_score",
        "coin_weight",
    ]
    expected_order = history.sort_values(["rebalance_date", "strategy", "coin_rank"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(history, expected_order)
    first_row = history.iloc[0].to_dict()
    assert first_row["rebalance_date"] == "2024-01-01"
    assert first_row["strategy"] == "BTC_BH__always_on"
    assert first_row["coin_id"] == "bitcoin"
    assert first_row["coin_rank"] == 1
    assert first_row["coin_weight"] == pytest.approx(0.6)
    assert pd.isna(first_row["coin_score"])


def test_export_result_tables_writes_manifest(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "run_001"

    _export(report_dir)

    manifest = json.loads((report_dir / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest) == {
        "config_path",
        "config_sha256",
        "code_commit",
        "pipeline_version",
        "data_snapshot",
        "generated_at",
        "artifacts",
    }
    assert manifest["config_path"] == "config/base.yaml"
    assert len(manifest["config_sha256"]) == 64
    paths = {artifact["path"] for artifact in manifest["artifacts"]}
    assert "strategy_summary.csv" in paths
    assert "weights/BTC_BH__always_on.csv" in paths
    assert "selection_history.csv" in paths
    assert all(artifact["size"] > 0 for artifact in manifest["artifacts"])
    assert all(len(artifact["sha256"]) == 64 for artifact in manifest["artifacts"])


def test_export_result_tables_failure_keeps_previous_report(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "run_001"
    results, summary, yearly_returns, regime_performance = _inputs()
    export_result_tables(results, summary, yearly_returns, regime_performance, report_dir)
    previous_manifest = (report_dir / "manifest.json").read_text(encoding="utf-8")

    bad_results = {"bad/name": next(iter(results.values()))}
    with pytest.raises(ValueError, match="filesystem-safe"):
        export_result_tables(bad_results, summary, yearly_returns, regime_performance, report_dir)

    assert report_dir.exists()
    assert (report_dir / "manifest.json").read_text(encoding="utf-8") == previous_manifest
    assert not any("bad" in path.name for path in (report_dir / "weights").glob("*.csv"))


def test_export_result_tables_publish_failure_restores_previous_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report_dir = tmp_path / "reports" / "run_001"
    results, summary, yearly_returns, regime_performance = _inputs()
    export_result_tables(results, summary, yearly_returns, regime_performance, report_dir)
    previous_manifest = (report_dir / "manifest.json").read_text(encoding="utf-8")
    real_move = report.shutil.move

    def flaky_move(src: str, dst: str) -> str:
        if Path(src).name.startswith(f"{report_dir.name}.tmp_") and Path(dst) == report_dir:
            Path(dst).mkdir(parents=True, exist_ok=True)
            (Path(dst) / "partial.txt").write_text("partial", encoding="utf-8")
            raise OSError("partial move failed")
        return real_move(src, dst)

    monkeypatch.setattr(report.shutil, "move", flaky_move)

    with pytest.raises(OSError, match="partial move failed"):
        export_result_tables(results, summary, yearly_returns, regime_performance, report_dir)

    assert (report_dir / "manifest.json").read_text(encoding="utf-8") == previous_manifest
    assert not (report_dir / "partial.txt").exists()


def test_publish_report_dir_restores_backup_when_tmp_move_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_dir = tmp_path / "reports" / "run_001"
    report_dir.mkdir(parents=True)
    (report_dir / "manifest.json").write_text('{"version": "previous"}\n', encoding="utf-8")
    (report_dir / "keep.txt").write_text("previous\n", encoding="utf-8")
    tmp_dir = tmp_path / "reports" / "run_001.tmp_manual"
    tmp_dir.mkdir()
    (tmp_dir / "manifest.json").write_text('{"version": "new"}\n', encoding="utf-8")
    real_move = report.shutil.move
    move_calls = 0

    def flaky_move(src: str, dst: str) -> str:
        nonlocal move_calls
        move_calls += 1
        if move_calls == 2:
            raise OSError("mid-publish failure")
        return real_move(src, dst)

    monkeypatch.setattr(report.shutil, "move", flaky_move)

    with pytest.raises(OSError, match="mid-publish failure"):
        report._publish_report_dir(tmp_dir, report_dir)

    assert (report_dir / "manifest.json").read_text(encoding="utf-8") == '{"version": "previous"}\n'
    assert (report_dir / "keep.txt").read_text(encoding="utf-8") == "previous\n"
    assert not any(report_dir.parent.glob("run_001.bak_*"))


def test_export_result_tables_writes_latest_pointer(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "app_runs" / "run_001"

    _export(report_dir)

    assert (tmp_path / "reports" / "latest.txt").read_text(encoding="utf-8") == "app_runs/run_001\n"


# ---- Codex review (b00mmn73k) follow-up tests ------------------------------


def test_export_rejects_empty_results(tmp_path: Path) -> None:
    """W5: empty results dict must raise ValueError, not produce confusing artifacts."""
    summary = pd.DataFrame({"annualized_turnover": [], "avg_turnover_per_rebalance": [], "average_holdings": []})
    with pytest.raises(ValueError, match="at least one BacktestResult"):
        export_result_tables({}, summary, pd.DataFrame(), pd.DataFrame(), tmp_path / "reports" / "run")


def test_export_rejects_windows_reserved_name(tmp_path: Path) -> None:
    """W3: 'CON', 'NUL' etc must be rejected even though they pass the regex."""
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    weights = pd.DataFrame({"bitcoin": [1.0] * 5}, index=dates)
    bad = {"CON": _result("CON", weights)}
    summary = pd.DataFrame(
        {"annualized_turnover": [1.0], "avg_turnover_per_rebalance": [0.1], "average_holdings": [1.0]},
        index=["CON"],
    )
    with pytest.raises(ValueError, match="Windows reserved"):
        export_result_tables(bad, summary, pd.DataFrame(), pd.DataFrame(), tmp_path / "reports" / "run")


def test_export_rejects_case_insensitive_collision(tmp_path: Path) -> None:
    """W3: 'Alpha' and 'alpha' would collide on case-insensitive filesystems."""
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    weights = pd.DataFrame({"bitcoin": [1.0] * 5}, index=dates)
    bad = {
        "Alpha": _result("Alpha", weights),
        "alpha": _result("alpha", weights),
    }
    summary = pd.DataFrame(
        {"annualized_turnover": [1.0, 1.0], "avg_turnover_per_rebalance": [0.1, 0.1], "average_holdings": [1.0, 1.0]},
        index=["Alpha", "alpha"],
    )
    with pytest.raises(ValueError, match="case-insensitive"):
        export_result_tables(bad, summary, pd.DataFrame(), pd.DataFrame(), tmp_path / "reports" / "run")


def test_export_rejects_report_dir_outside_reports_root(tmp_path: Path) -> None:
    """W4: report_dir not under a 'reports/' ancestor must fail before any write."""
    out = tmp_path / "scratch" / "run_001"
    with pytest.raises(ValueError, match="reports/"):
        _export(out)
    assert not out.exists()


def test_selection_history_uses_rebalance_targets_weights(tmp_path: Path) -> None:
    """W1: coin_weight must come from rebalance_targets, not from a stale weights row."""
    report_dir = tmp_path / "reports" / "run_001"
    _export(report_dir)
    history = pd.read_csv(report_dir / "selection_history.csv")

    # In _inputs, BTC_BH__always_on has rebalance_targets at dates[0] and dates[2]
    # with weights [0.60, 0.30, 0.10] then [0.00, 0.50, 0.25]. The weight column
    # in history must match those targets exactly, not result.weights values.
    btc = history[history["strategy"] == "BTC_BH__always_on"]
    first_rebalance = btc[btc["rebalance_date"] == btc["rebalance_date"].min()].set_index("coin_id")["coin_weight"]
    assert pytest.approx(first_rebalance["bitcoin"], rel=1e-6) == 0.60
    assert pytest.approx(first_rebalance["ethereum"], rel=1e-6) == 0.30
    assert pytest.approx(first_rebalance["solana"], rel=1e-6) == 0.10


def test_selection_history_collapses_duplicate_rebalance_dates(tmp_path: Path) -> None:
    """W2: duplicate rebalance dates must be collapsed deterministically (keep last)."""
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    weights = pd.DataFrame({"bitcoin": [1.0, 1.0, 1.0], "ethereum": [0.0, 0.0, 0.0]}, index=dates)
    result = BacktestResult(
        name="BTC_BH__always_on",
        daily_returns=pd.Series([0.01, 0.02, -0.01], index=dates, name="BTC_BH__always_on"),
        equity_curve=pd.Series([101.0, 103.0, 102.0], index=dates, name="BTC_BH__always_on"),
        drawdown=pd.Series([0.0, 0.0, -0.01], index=dates, name="BTC_BH__always_on"),
        weights=weights,
        turnover=pd.Series([0.0, 0.3, 0.2], index=dates, name="BTC_BH__always_on"),
        holdings_count=pd.Series([1, 1, 1], index=dates),
        sector_exposure=pd.DataFrame(index=dates),
        rebalance_targets=pd.DataFrame(
            {"bitcoin": [0.30, 0.60], "ethereum": [0.70, 0.40]},
            index=[dates[0], dates[0]],
        ),
    )
    results = {"BTC_BH__always_on": result}
    summary = pd.DataFrame(
        {"annualized_turnover": [1.0], "avg_turnover_per_rebalance": [0.1], "average_holdings": [2.0]},
        index=["BTC_BH__always_on"],
    )
    report_dir = tmp_path / "reports" / "run_dup"
    export_result_tables(results, summary, pd.DataFrame(), pd.DataFrame(), report_dir)
    history = pd.read_csv(report_dir / "selection_history.csv")
    # Only one rebalance_date row group, taking "last" duplicate (bitcoin=0.60, ethereum=0.40)
    first_date = history[history["rebalance_date"] == history["rebalance_date"].min()]
    weights_by_coin = first_date.set_index("coin_id")["coin_weight"].to_dict()
    assert pytest.approx(weights_by_coin["bitcoin"], rel=1e-6) == 0.60
    assert pytest.approx(weights_by_coin["ethereum"], rel=1e-6) == 0.40
