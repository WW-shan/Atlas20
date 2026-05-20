from pathlib import Path
import re


SECRET_ASSIGNMENT = re.compile(
    r"(api[_-]?key|secret|password|token)\s*=\s*['\"][A-Za-z0-9]{16,}",
    re.IGNORECASE,
)


def test_env_file_is_gitignored():
    root = Path(__file__).resolve().parents[1]
    lines = {
        line.strip()
        for line in (root / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    assert ".env" in lines
    assert "!.env.example" in lines


def test_src_contains_no_hardcoded_secret_assignments():
    root = Path(__file__).resolve().parents[1]
    findings: list[str] = []
    for path in sorted((root / "src").rglob("*")):
        if path.is_file() and path.suffix in {".py", ".toml", ".yaml", ".yml", ".json"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if SECRET_ASSIGNMENT.search(text):
                findings.append(path.relative_to(root).as_posix())

    assert findings == []
