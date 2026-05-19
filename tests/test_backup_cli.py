import os
import sqlite3
import tarfile
import threading
import time

from atlas20.api.cli.backup import main as backup_main
from atlas20.api.settings import get_settings


def test_backup_cli_creates_tarball_and_purges_old_archives(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "atlas20.sqlite"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        conn.execute("INSERT INTO marker VALUES ('committed')")
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

    ready = threading.Event()
    release = threading.Event()

    def hold_write_transaction() -> None:
        conn = sqlite3.connect(str(db_path), timeout=5)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO marker VALUES ('pending')")
            ready.set()
            release.wait(timeout=5)
            conn.rollback()
        finally:
            conn.close()

    thread = threading.Thread(target=hold_write_transaction)
    thread.start()
    assert ready.wait(timeout=5)
    try:
        backup_main()
        output = capsys.readouterr().out
    finally:
        release.set()
        thread.join(timeout=5)

    archives = sorted(backup_root.glob("atlas20-*.tar.gz"))
    assert "Backup:" in output
    assert old_archive not in archives
    assert len(archives) == 1
    with tarfile.open(archives[0], "r:gz") as archive:
        names = archive.getnames()
        archived_db = archive.extractfile(db_path.name)
        assert archived_db is not None
        restored_db = tmp_path / "restored.sqlite"
        restored_db.write_bytes(archived_db.read())
    assert db_path.name in names
    assert "app_runs" in names
    assert "app_runs/run.txt" in names

    with sqlite3.connect(str(restored_db)) as conn:
        values = [row[0] for row in conn.execute("SELECT value FROM marker").fetchall()]
    assert values == ["committed"]
