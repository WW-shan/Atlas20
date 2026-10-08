"""docker-compose.yml must not expose an unauthenticated API to the network."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"


def _compose() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def test_compose_publishes_ports_on_loopback_only():
    services = _compose()["services"]

    published = [(name, str(port)) for name, service in services.items() for port in service.get("ports", [])]

    assert published
    assert all(port.startswith("127.0.0.1:") for _, port in published), published


@pytest.mark.parametrize("service", ["backend", "worker"])
def test_compose_requires_api_keys_from_environment(service: str):
    environment = _compose()["services"][service]["environment"]

    assert re.fullmatch(r"\$\{ATLAS20_API_KEYS:\?[^}]+\}", environment["ATLAS20_API_KEYS"])


@pytest.mark.parametrize("service", ["worker", "web"])
def test_compose_dependents_wait_for_backend_start_not_readiness(service: str):
    # /readyz needs fresh data that only the worker produces, so waiting for a
    # healthy backend would deadlock a fresh stack.
    depends_on = _compose()["services"][service]["depends_on"]

    assert depends_on["backend"]["condition"] == "service_started"


def _docker_compose_config(tmp_path: Path, extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("ATLAS20_")}
    env.update(extra_env)
    try:
        return subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "--project-directory", str(tmp_path), "config"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"docker compose unavailable: {exc}")


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker CLI not installed")
def test_docker_compose_fails_fast_without_api_keys(tmp_path: Path):
    missing = _docker_compose_config(tmp_path, {})
    configured = _docker_compose_config(tmp_path, {"ATLAS20_API_KEYS": "k" * 40})

    if "is not a docker command" in missing.stderr or "unknown command" in missing.stderr:
        pytest.skip("docker compose plugin not installed")
    assert missing.returncode != 0
    assert "ATLAS20_API_KEYS" in missing.stderr
    assert configured.returncode == 0, configured.stderr[-2000:]
    assert "127.0.0.1" in configured.stdout
