import importlib.util
from pathlib import Path


def _load_verify_release_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_release.py"
    spec = importlib.util.spec_from_file_location("verify_release", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_command_uses_shutil_lookup_for_npm(monkeypatch):
    module = _load_verify_release_module()

    def fake_which(name: str) -> str | None:
        return "C:/Program Files/nodejs/npm.CMD" if name == "npm" else None

    monkeypatch.setattr(module.shutil, "which", fake_which)

    assert module.resolve_command(["npm", "--version"])[0] == "C:/Program Files/nodejs/npm.CMD"


def test_check_prerequisites_reports_missing_pytest(monkeypatch, tmp_path):
    module = _load_verify_release_module()
    web_node_modules = tmp_path / "apps" / "web" / "node_modules"
    web_node_modules.mkdir(parents=True)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/npm" if name == "npm" else None)
    monkeypatch.setattr(module.importlib.util, "find_spec", lambda name: None if name == "pytest" else object())

    assert module.check_prerequisites() == [
        'Missing Python test dependency: pytest. Run `python -m pip install -e ".[dev]"`.',
    ]


def test_check_prerequisites_reports_missing_web_dependencies(monkeypatch, tmp_path):
    module = _load_verify_release_module()
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/npm" if name == "npm" else None)
    monkeypatch.setattr(module.importlib.util, "find_spec", lambda name: object())

    assert module.check_prerequisites() == [
        "Missing frontend dependencies: apps/web/node_modules. Run `npm --prefix apps/web ci`.",
    ]


def test_main_prints_preflight_failures_without_running_checks(monkeypatch, capsys):
    module = _load_verify_release_module()
    monkeypatch.setattr(module, "check_prerequisites", lambda: ["missing pytest"])

    def fail_run(command: list[str]) -> None:
        raise AssertionError(f"run should not be called for {command}")

    monkeypatch.setattr(module, "run", fail_run)

    assert module.main() == 1
    captured = capsys.readouterr()
    assert "Release verification prerequisites are missing:" in captured.err
    assert "- missing pytest" in captured.err


def test_makefile_typecheck_matches_ci_mypy_scope():
    root = Path(__file__).resolve().parents[1]
    makefile = (root / "Makefile").read_text(encoding="utf-8")

    assert "mypy --strict src/atlas20/api\n" in makefile
