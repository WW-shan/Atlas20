# GitHub Repository Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the Atlas20 GitHub repository presentation and publish the docs-only release as `v0.2.1`.

**Architecture:** Keep the change documentation-only, guarded by a lightweight pytest that checks README and changelog presentation invariants. Update README for GitHub first-impression quality, then update the changelog and tag the verified commit.

**Tech Stack:** Markdown, Mermaid, pytest, git annotated tags.

---

### Task 1: Add Presentation Regression Test

**Files:**
- Create: `tests/test_repository_presentation.py`

- [ ] **Step 1: Write a failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --isolated --with-editable ".[dev]" pytest -q tests/test_repository_presentation.py`

Expected: FAIL because README and CHANGELOG do not yet contain the new presentation content.

### Task 2: Polish README and Changelog

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Rewrite README**

Update README with:
- Strong opening and badges.
- Engineering credibility section.
- Mermaid architecture diagram.
- Quickstart paths for Docker and local dev.
- Quality gates and operational notes.
- Research caveats kept visible.

- [ ] **Step 2: Update changelog**

Add:

```markdown
## [0.2.1] - 2026-05-30

### Added
- Repository presentation refresh ...

### Changed
- Release verification now ...
```

- [ ] **Step 3: Run focused test**

Run: `uv run --isolated --with-editable ".[dev]" pytest -q tests/test_repository_presentation.py`

Expected: PASS.

### Task 3: Verify and Publish

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run release verification**

Run: `uv run --isolated --with-editable ".[dev]" python scripts/verify_release.py`

Expected: PASS.

- [ ] **Step 2: Run markdown/presentation tests**

Run: `uv run --isolated --with-editable ".[dev]" pytest -q tests/test_repository_presentation.py tests/test_verify_release_script.py`

Expected: PASS.

- [ ] **Step 3: Commit and push**

```bash
git add README.md CHANGELOG.md tests/test_repository_presentation.py docs/superpowers/specs/2026-05-30-github-repository-polish-design.md docs/superpowers/plans/2026-05-30-github-repository-polish.md
git commit -m "docs: polish repository presentation"
git push origin main
```

- [ ] **Step 4: Tag and push**

```bash
git tag -a v0.2.1 -m "v0.2.1"
git push origin v0.2.1
```
