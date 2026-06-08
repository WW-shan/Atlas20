from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_executable(name: str) -> str | None:
    executable = shutil.which(name)
    if executable is not None:
        return executable

    script_dir = "Scripts" if os.name == "nt" else "bin"
    python_bins = [Path(sys.prefix) / script_dir, Path(sys.executable).parent]
    suffixes = ["", ".exe", ".cmd", ".bat"] if os.name == "nt" else [""]
    for python_bin in dict.fromkeys(python_bins):
        for suffix in suffixes:
            candidate = python_bin / f"{name}{suffix}"
            if candidate.exists():
                return str(candidate)
    return None


def resolve_command(command: list[str]) -> list[str]:
    executable = resolve_executable(command[0])
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
    for executable in ("ruff", "mypy", "pip-audit"):
        if resolve_executable(executable) is None:
            missing.append(f'Missing executable: {executable}. Run `python -m pip install -e ".[dev]"`.')
    if resolve_executable("npm") is None:
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
        ["ruff", "check", "src", "tests"],
        ["mypy", "--strict", "src/atlas20/api"],
        [sys.executable, "-m", "atlas20.api.openapi", "--check"],
        ["npm", "--prefix", "apps/web", "test"],
        ["npm", "--prefix", "apps/web", "run", "typecheck"],
        ["npm", "--prefix", "apps/web", "run", "build"],
        ["npm", "--prefix", "apps/web", "run", "openapi:check"],
        ["pip-audit", "--strict", "."],
        [
            "npm",
            "--prefix",
            "apps/web",
            "audit",
            "--audit-level=moderate",
            "--registry=https://registry.npmjs.org",
        ],
    ]
    for command in checks:
        run(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
