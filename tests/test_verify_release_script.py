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
