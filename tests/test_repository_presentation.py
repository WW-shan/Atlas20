from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_presents_atlas20_as_engineered_research_console():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    required_phrases = [
        "production-minded crypto research console",
        "FastAPI",
        "React/Vite",
        "worker",
        "Prometheus",
        "Docker Compose",
        "GHCR",
        "OpenAPI",
        "pytest",
        "Vitest",
        "mypy",
        "Research only",
    ]
    for phrase in required_phrases:
        assert phrase in readme

    assert "```mermaid" in readme
    assert "## Why It Stands Out" in readme
    assert "## Quickstart" in readme


def test_changelog_has_v021_repository_polish_entry():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## [0.2.1] - 2026-05-30" in changelog
    assert "Repository presentation" in changelog
    assert "release verification" in changelog


def test_release_metadata_matches_v021_tag():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    web_package = (ROOT / "apps" / "web" / "package.json").read_text(encoding="utf-8")
    web_lock = (ROOT / "apps" / "web" / "package-lock.json").read_text(encoding="utf-8")

    assert 'version = "0.2.1"' in pyproject
    assert '"version": "0.2.1"' in web_package
    assert web_lock.count('"version": "0.2.1"') >= 2
