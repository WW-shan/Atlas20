from __future__ import annotations

import os
from pathlib import Path

import pytest

from atlas20.api.data_access._common import _latest_report_dir
from atlas20.reporting.report import _write_latest_link


def test_latest_report_dir_honors_latest_txt_pointer(tmp_path):
    run_dir = tmp_path / "run_001"
    run_dir.mkdir()
    run_dir.joinpath("strategy_summary.csv").write_text("strategy,sharpe\nA,1.0\n", encoding="utf-8")
    tmp_path.joinpath("latest.txt").write_text("run_001\n", encoding="utf-8")

    assert _latest_report_dir(tmp_path) == run_dir


def test_latest_report_dir_prefers_latest_link_over_pointer(tmp_path):
    report_root = tmp_path / "reports"
    run_dir = report_root / "app_runs" / "run_001"
    run_dir.mkdir(parents=True)
    latest_target = report_root / "app_runs" / "run_002"
    latest_target.mkdir()
    report_root.joinpath("latest.txt").write_text("app_runs/run_001\n", encoding="utf-8")
    _write_latest_link(latest_target)

    assert _latest_report_dir(report_root).resolve() == latest_target.resolve()


def test_latest_report_dir_falls_back_to_latest_dir_for_blank_pointer(tmp_path):
    latest_dir = tmp_path / "latest"
    latest_dir.mkdir()
    tmp_path.joinpath("latest.txt").write_text(" \n\t", encoding="utf-8")

    assert _latest_report_dir(tmp_path) == latest_dir


def test_latest_report_dir_falls_back_to_latest_dir_without_pointer(tmp_path):
    latest_dir = tmp_path / "latest"
    latest_dir.mkdir()

    assert _latest_report_dir(tmp_path) == latest_dir


def test_latest_report_dir_rejects_parent_directory_pointer(tmp_path):
    tmp_path.joinpath("latest.txt").write_text("../escape\n", encoding="utf-8")

    with pytest.raises(ValueError, match="latest.txt points outside report_root"):
        _latest_report_dir(tmp_path)


def test_latest_report_dir_rejects_absolute_pointer(tmp_path):
    absolute_target = Path("C:/Windows") if os.name == "nt" else Path("/etc/passwd")
    tmp_path.joinpath("latest.txt").write_text(str(absolute_target), encoding="utf-8")

    with pytest.raises(ValueError, match="latest.txt points outside report_root"):
        _latest_report_dir(tmp_path)
