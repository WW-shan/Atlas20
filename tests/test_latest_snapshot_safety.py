"""The published `reports/latest` directory must not be replaced by a link.

`reports/latest` is a checked-in snapshot. Publishing a run used to replace
that directory with a symlink/junction pointing at the run, which made every
tracked snapshot file show up as deleted in git. The pointer file is the
supported way to redirect readers.
"""

from __future__ import annotations

from pathlib import Path

from atlas20.api.data_access._common import _latest_report_dir
from atlas20.reporting.report import _write_latest_link


def _snapshot(report_root: Path) -> Path:
    latest = report_root / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "strategy_summary.csv").write_text("strategy,sharpe\nOLD,1.0\n", encoding="utf-8")
    return latest


def test_write_latest_link_preserves_checked_in_snapshot_directory(tmp_path: Path) -> None:
    report_root = tmp_path / "reports"
    snapshot = _snapshot(report_root)
    run_dir = report_root / "app_runs" / "run_001"
    run_dir.mkdir(parents=True)
    (run_dir / "strategy_summary.csv").write_text("strategy,sharpe\nNEW,2.0\n", encoding="utf-8")

    _write_latest_link(run_dir)

    assert snapshot.is_dir(), "snapshot directory must survive publication"
    assert not snapshot.is_symlink(), "snapshot directory must not become a link"
    assert (snapshot / "strategy_summary.csv").read_text(encoding="utf-8") == "strategy,sharpe\nOLD,1.0\n"


def test_write_latest_link_points_pointer_at_run(tmp_path: Path) -> None:
    report_root = tmp_path / "reports"
    _snapshot(report_root)
    run_dir = report_root / "app_runs" / "run_001"
    run_dir.mkdir(parents=True)

    _write_latest_link(run_dir)

    pointer = report_root / "latest.txt"
    assert pointer.exists(), "publication must record the run via latest.txt"
    assert pointer.read_text(encoding="utf-8").strip() == "app_runs/run_001"


def test_latest_report_dir_resolves_run_while_snapshot_stays_intact(tmp_path: Path) -> None:
    report_root = tmp_path / "reports"
    _snapshot(report_root)
    run_dir = report_root / "app_runs" / "run_001"
    run_dir.mkdir(parents=True)
    (run_dir / "strategy_summary.csv").write_text("strategy,sharpe\nNEW,2.0\n", encoding="utf-8")

    _write_latest_link(run_dir)

    assert _latest_report_dir(report_root).resolve() == run_dir.resolve()
    assert not (report_root / "latest").is_symlink()
