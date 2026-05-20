from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_TRACKED_FILE_BYTES = 95 * 1024 * 1024
SECRET_PATTERNS = [
    ("credential assignment", re.compile(r"\b(api[_-]?key|client[_-]?secret|secret[_-]?key|access[_-]?token|refresh[_-]?token|password)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]?", re.IGNORECASE)),
    ("private key block", re.compile(r"BEGIN (RSA|OPENSSH|PRIVATE)", re.IGNORECASE)),
    ("github token", re.compile(r"\bghp_[A-Za-z0-9_]+\b")),
    ("slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]+\b")),
]
EXCLUDE_PATHS = (
    ".ccg/tasks/archive/",
    "tests/",
)


@dataclass(frozen=True)
class Finding:
    path: Path
    message: str


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files"], cwd=PROJECT_ROOT, text=True)
    return [PROJECT_ROOT / line for line in output.splitlines() if line]


def detect_large_files(paths: list[Path], max_bytes: int = MAX_TRACKED_FILE_BYTES) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        if path.exists() and path.is_file() and path.stat().st_size > max_bytes:
            findings.append(Finding(path=path, message=f"{path.stat().st_size} bytes exceeds {max_bytes} byte limit"))
    return findings


def _read_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:2048]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def detect_secret_patterns(paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        try:
            relative_path = path.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            relative_path = None
        if relative_path is not None and relative_path.startswith(EXCLUDE_PATHS):
            continue
        text = _read_text(path)
        if text is None:
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(Finding(path=path, message=f"matches secret pattern: {label}"))
                break
    return findings


def main() -> int:
    paths = tracked_files()
    findings = [*detect_large_files(paths), *detect_secret_patterns(paths)]
    if findings:
        print("Repository health check failed:")
        for finding in findings:
            display = finding.path.relative_to(PROJECT_ROOT) if finding.path.is_relative_to(PROJECT_ROOT) else finding.path
            print(f"- {display}: {finding.message}")
        return 1
    print("Repository health check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
