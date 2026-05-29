from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
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


def check_prerequisites() -> list[str]:
    missing: list[str] = []
    web_node_modules = PROJECT_ROOT / "apps" / "web" / "node_modules"
    if importlib.util.find_spec("pytest") is None:
        missing.append('Missing Python test dependency: pytest. Run `python -m pip install -e ".[dev]"`.')
    if shutil.which("npm") is None:
        missing.append("Missing executable: npm. Install Node.js/npm, then run `npm --prefix apps/web ci`.")
    elif not web_node_modules.is_dir():
        missing.append("Missing frontend dependencies: apps/web/node_modules. Run `npm --prefix apps/web ci`.")
    return missing


def main() -> int:
    missing = check_prerequisites()
    if missing:
        print("Release verification prerequisites are missing:", file=sys.stderr)
        for message in missing:
            print(f"- {message}", file=sys.stderr)
        return 1

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
