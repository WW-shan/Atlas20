"""Storage usage probe for reports/ and data/ directories."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import stat as stat_module

from atlas20.api.settings import Settings, get_settings


@dataclass(frozen=True)
class StorageProbeResult:
    label: str
    path: str
    size_bytes: int
    threshold_bytes: int
    status: str


def _is_reparse_point(stat_result: os.stat_result) -> bool:
    if os.name != "nt":
        return False
    file_attributes = getattr(stat_result, "st_file_attributes", 0)
    reparse_point = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(file_attributes & reparse_point)


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    with os.scandir(path) as entries:
        for entry in entries:
            if entry.is_symlink():
                continue
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if _is_reparse_point(entry_stat):
                continue
            if entry.is_dir(follow_symlinks=False):
                total += _directory_size(Path(entry.path))
            else:
                total += entry_stat.st_size
    return total


def _probe_directory(label: str, path: Path, threshold_bytes: int) -> StorageProbeResult:
    size_bytes = _directory_size(path)
    alert = threshold_bytes > 0 and size_bytes > threshold_bytes
    return StorageProbeResult(
        label=label,
        path=str(path),
        size_bytes=size_bytes,
        threshold_bytes=threshold_bytes,
        status="alert" if alert else "ok",
    )


def main(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    results = [
        _probe_directory("reports", settings.report_root, settings.report_storage_warn_bytes),
        _probe_directory("data", settings.data_root, settings.data_storage_warn_bytes),
    ]
    for result in results:
        print(json.dumps(result.__dict__, sort_keys=True))
    return 2 if any(result.status == "alert" for result in results) else 0
