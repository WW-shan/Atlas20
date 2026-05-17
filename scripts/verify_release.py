from __future__ import annotations

import subprocess
import sys
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_command(command: list[str]) -> list[str]:
    executable = shutil.which(command[0])
    if executable is None:
        return command
    return [executable, *command[1:]]


def run(command: list[str]) -> None:
    print(f"$ {' '.join(command)}", flush=True)
    subprocess.run(resolve_command(command), cwd=PROJECT_ROOT, check=True)


def main() -> int:
    checks = [
        [sys.executable, "scripts/check_repo_health.py"],
        [sys.executable, "-m", "pytest", "-q"],
        ["npm", "--prefix", "apps/web", "test"],
        ["npm", "--prefix", "apps/web", "run", "build"],
    ]
    for command in checks:
        run(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
