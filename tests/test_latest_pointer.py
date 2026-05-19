from __future__ import annotations

from atlas20.api.data_access._common import _latest_report_dir


def test_latest_report_dir_honors_latest_txt_pointer(tmp_path):
    run_dir = tmp_path / "run_001"
    run_dir.mkdir()
    run_dir.joinpath("strategy_summary.csv").write_text("strategy,sharpe\nA,1.0\n", encoding="utf-8")
    tmp_path.joinpath("latest.txt").write_text("run_001\n", encoding="utf-8")

    assert _latest_report_dir(tmp_path) == run_dir


def test_latest_report_dir_falls_back_to_latest_dir_for_blank_pointer(tmp_path):
    latest_dir = tmp_path / "latest"
    latest_dir.mkdir()
    tmp_path.joinpath("latest.txt").write_text(" \n\t", encoding="utf-8")

    assert _latest_report_dir(tmp_path) == latest_dir


def test_latest_report_dir_falls_back_to_latest_dir_without_pointer(tmp_path):
    latest_dir = tmp_path / "latest"
    latest_dir.mkdir()

    assert _latest_report_dir(tmp_path) == latest_dir
