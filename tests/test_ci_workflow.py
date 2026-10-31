from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
PACKAGE_LOCK = ROOT / "apps" / "web" / "package-lock.json"


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(".") if part.isdigit())


def test_security_scan_keeps_high_and_production_moderate_gates() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["security-scan"]
    commands = [str(step.get("run", "")) for step in job["steps"]]

    assert "npm --prefix apps/web audit --omit=dev --audit-level=moderate" in commands
    assert "npm --prefix apps/web audit --audit-level=high" in commands
    assert "npm --prefix apps/web audit --audit-level=moderate" not in commands


def test_known_high_risk_frontend_dependencies_are_patched() -> None:
    packages = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))["packages"]
    minimums = {
        "node_modules/vite": "7.3.7",
        "node_modules/vitest": "4.1.12",
        "node_modules/zod": "4.6.6",
    }

    for package, minimum in minimums.items():
        installed = str(packages[package]["version"])
        assert _version_tuple(installed) >= _version_tuple(minimum), (
            f"{package} is {installed}; expected at least {minimum}"
        )
