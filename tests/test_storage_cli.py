from __future__ import annotations

import json

from atlas20.api.cli.storage import main as storage_main
from atlas20.api.settings import get_settings
from atlas20.reporting.report import _write_latest_link


def test_storage_cli_counts_snapshot_and_run_without_duplicating_a_link(
    tmp_path,
    monkeypatch,
    capsys,
):
    """Publication must not create a second copy of the same bytes.

    `latest` is now a real snapshot directory rather than a link, so both it
    and the run directory are counted once each.
    """
    report_root = tmp_path / "reports"
    reports_run = report_root / "app_runs" / "run_001"
    reports_run.mkdir(parents=True)
    reports_run.joinpath("artifact.bin").write_bytes(b"x" * 10)
    latest_snapshot = report_root / "latest"
    latest_snapshot.mkdir(parents=True)
    latest_snapshot.joinpath("snapshot.bin").write_bytes(b"z" * 4)
    _write_latest_link(reports_run)
    data_root = tmp_path / "data"
    data_root.mkdir()
    data_root.joinpath("raw.bin").write_bytes(b"y" * 2)

    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(data_root))
    monkeypatch.setenv("ATLAS20_REPORT_STORAGE_WARN_BYTES", "100")
    monkeypatch.setenv("ATLAS20_DATA_STORAGE_WARN_BYTES", "10")
    get_settings.cache_clear()

    exit_code = storage_main()
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    assert exit_code == 0
    # 10 (run artifact) + 4 (snapshot) + len("app_runs/run_001\n") for the pointer
    assert output == [
        {"label": "reports", "path": str(report_root), "size_bytes": 31, "status": "ok", "threshold_bytes": 100},
        {"label": "data", "path": str(data_root), "size_bytes": 2, "status": "ok", "threshold_bytes": 10},
    ]


def test_storage_cli_alerts_when_reports_exceed_threshold(tmp_path, monkeypatch, capsys):
    report_root = tmp_path / "reports"
    report_root.mkdir()
    report_root.joinpath("archive.bin").write_bytes(b"x" * 10)
    data_root = tmp_path / "data"
    data_root.mkdir()
    data_root.joinpath("raw.bin").write_bytes(b"y" * 2)

    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(data_root))
    monkeypatch.setenv("ATLAS20_REPORT_STORAGE_WARN_BYTES", "5")
    monkeypatch.setenv("ATLAS20_DATA_STORAGE_WARN_BYTES", "10")
    get_settings.cache_clear()

    exit_code = storage_main()
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    assert exit_code == 2
    assert output[0]["status"] == "alert"
    assert output[0]["size_bytes"] == 10
    assert output[1]["status"] == "ok"
