import os
import tarfile
import time

from atlas20.api.cli.backup import main as backup_main
from atlas20.api.settings import get_settings


def test_backup_cli_creates_tarball_and_purges_old_archives(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "atlas20.sqlite"
    db_path.write_text("sqlite-data", encoding="utf-8")
    report_root = tmp_path / "reports"
    app_runs = report_root / "app_runs"
    app_runs.mkdir(parents=True)
    (app_runs / "run.txt").write_text("report", encoding="utf-8")
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    old_archive = backup_root / "atlas20-old.tar.gz"
    old_archive.write_text("old", encoding="utf-8")
    old_mtime = time.time() - (60 * 24 * 60 * 60)
    os.utime(old_archive, (old_mtime, old_mtime))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    monkeypatch.setenv("ATLAS20_BACKUP_ROOT", str(backup_root))
    monkeypatch.setenv("ATLAS20_BACKUP_RETENTION_DAYS", "30")
    get_settings.cache_clear()

    backup_main()
    output = capsys.readouterr().out

    archives = sorted(backup_root.glob("atlas20-*.tar.gz"))
    assert "Backup:" in output
    assert old_archive not in archives
    assert len(archives) == 1
    with tarfile.open(archives[0], "r:gz") as archive:
        names = archive.getnames()
    assert db_path.name in names
    assert "app_runs" in names
    assert "app_runs/run.txt" in names
