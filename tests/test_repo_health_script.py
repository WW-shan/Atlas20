import importlib.util
import sys
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_repo_health.py"
    spec = importlib.util.spec_from_file_location("check_repo_health", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_detect_large_files_reports_files_over_limit(tmp_path):
    module = _load_module()
    small = tmp_path / "small.txt"
    large = tmp_path / "large.bin"
    small.write_text("ok", encoding="utf-8")
    large.write_bytes(b"x" * 11)

    findings = module.detect_large_files([small, large], max_bytes=10)

    assert findings == [module.Finding(path=large, message="11 bytes exceeds 10 byte limit")]


def test_detect_secret_patterns_ignores_binary_files(tmp_path):
    module = _load_module()
    text = tmp_path / "config.txt"
    binary = tmp_path / "image.png"
    credential_name = "pass" + "word"
    text.write_text(f"{credential_name} = 'cleartext'", encoding="utf-8")
    binary.write_bytes(b"\x89PNG\r\n\x1a\n" + credential_name.encode("utf-8"))

    findings = module.detect_secret_patterns([text, binary])

    assert findings == [module.Finding(path=text, message="matches secret pattern: credential assignment")]


def test_detect_secret_patterns_allows_public_project_names(tmp_path):
    module = _load_module()
    text = tmp_path / "metadata.json"
    text.write_text('{"name": "Secret Network", "platform": "secret"}', encoding="utf-8")

    assert module.detect_secret_patterns([text]) == []
