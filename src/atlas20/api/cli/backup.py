"""Backup SQLite DB and generated app run reports."""

from __future__ import annotations

from pathlib import Path
import tarfile

from sqlalchemy.engine import make_url

from atlas20.api._time import utc_now, utc_now_iso
from atlas20.api.settings import get_settings


def _db_path_from_url(db_url: str) -> Path | None:
    url = make_url(db_url)
    if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
        return None
    return Path(url.database).expanduser()


def _purge_old(backup_root: Path, *, retention_days: int) -> int:
    cutoff = utc_now().timestamp() - (retention_days * 24 * 60 * 60)
    purged = 0
    for path in backup_root.glob("atlas20-*.tar.gz"):
        if path.stat().st_mtime < cutoff:
            path.unlink()
            purged += 1
    return purged


def main() -> None:
    settings = get_settings()
    backup_root = settings.backup_root
    backup_root.mkdir(parents=True, exist_ok=True)
    ts = utc_now_iso().replace(":", "").replace("-", "")
    archive_path = backup_root / f"atlas20-{ts}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tf:
        db_path = _db_path_from_url(settings.db_url)
        if db_path and db_path.exists():
            tf.add(db_path, arcname=db_path.name)
        reports_dir = settings.report_root / "app_runs"
        if reports_dir.exists():
            tf.add(reports_dir, arcname="app_runs")
    print(f"Backup: {archive_path}")
    _purge_old(backup_root, retention_days=settings.backup_retention_days)
