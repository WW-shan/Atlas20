from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_presents_atlas20_as_engineered_research_console():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    normalized = " ".join(readme.split())

    required_phrases = [
        "production-minded crypto research and derivatives execution system",
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
        "gated live derivatives executor",
        "provide financial advice",
    ]
    for phrase in required_phrases:
        assert phrase in normalized

    assert "```mermaid" in readme
    assert "## Why It Stands Out" in readme
    assert "## Quickstart" in readme


def test_changelog_has_v022_release_prep_entry():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## [0.2.2] - 2026-06-08" in changelog
    assert "Seed CLI now records Alembic migration state" in changelog
    assert "Release verification now mirrors CI" in changelog


def test_readme_quality_gate_documents_the_current_suite():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "complete Python and Vitest suites" in readme
    assert ".venv/bin/pip-audit --strict ." in readme
    assert ".venv/bin/python -m pip_audit --strict ." not in readme
    assert "RESEARCH.md` sections 00.152–00.155" in readme


def test_release_metadata_matches_v022_tag():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    web_package = (ROOT / "apps" / "web" / "package.json").read_text(encoding="utf-8")
    web_lock = (ROOT / "apps" / "web" / "package-lock.json").read_text(encoding="utf-8")

    assert 'version = "0.2.2"' in pyproject
    assert '"version": "0.2.2"' in web_package
    assert web_lock.count('"version": "0.2.2"') >= 2
