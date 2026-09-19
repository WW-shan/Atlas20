# Project Health Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore dependency-security, report-manifest, and README-snapshot consistency without changing application behavior or public contracts.

**Architecture:** Add repository-level regression tests around the checked-in research snapshot, rebuild the stale manifest from the existing artifacts, update README metrics to the checked-in strategy summary, and upgrade the frontend dependency lockfile. Keep all behavior changes inside tests and generated/metadata files.

**Tech Stack:** Python 3.11, pytest, hashlib/json/csv, npm, Vite/Vitest, GitHub Actions.

---

### Task 1: Add report-snapshot integrity regression tests

**Files:**
- Create: `tests/test_checked_in_report_snapshot.py`
- Modify: none

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "reports" / "latest"


def _manifest() -> dict:
    return json.loads((LATEST / "manifest.json").read_text(encoding="utf-8"))


def test_checked_in_report_manifest_matches_artifacts() -> None:
    failures: list[str] = []
    for artifact in _manifest()["artifacts"]:
        path = LATEST / artifact["path"]
        if not path.is_file():
            failures.append(f"{artifact['path']}: missing")
            continue
        payload = path.read_bytes()
        actual_size = len(payload)
        actual_sha = hashlib.sha256(payload).hexdigest()
        if actual_size != artifact["size"]:
            failures.append(
                f"{artifact['path']}: size {actual_size} != manifest {artifact['size']}"
            )
        if actual_sha != artifact["sha256"]:
            failures.append(
                f"{artifact['path']}: sha256 {actual_sha} != manifest {artifact['sha256']}"
            )
    assert failures == []


def test_readme_snapshot_matches_strategy_summary() -> None:
    summary_rows = list(
        csv.DictReader((LATEST / "strategy_summary.csv").open(encoding="utf-8"))
    )
    by_strategy = {row["strategy"]: row for row in summary_rows}

    momentum_candidates = [
        row
        for row in summary_rows
        if row["strategy"].startswith("TOP20_MOM_")
    ]
    sector_candidates = [
        row
        for row in summary_rows
        if row["strategy"].startswith("TOP20_SECTOR_")
    ]
    best_momentum = max(
        momentum_candidates,
        key=lambda row: (float(row["sharpe"]), float(row["cagr"])),
    )
    best_sector = max(
        sector_candidates,
        key=lambda row: (float(row["sharpe"]), float(row["cagr"])),
    )
    btc = by_strategy["BTC_BH__always_on"]
    equal_weight = by_strategy["TOP20_EQ__always_on"]

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"`{best_momentum['strategy']}`" in readme
    assert f"`{best_sector['strategy']}`" in readme
    assert f"{float(btc['cagr']):.1%}" in readme
    assert f"{float(equal_weight['cagr']):.1%}" in readme
    assert f"{float(best_momentum['cagr']):.1%}" in readme
    assert f"{float(best_sector['cagr']):.1%}" in readme
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_checked_in_report_snapshot.py -q`

Expected: FAIL because 38 manifest artifacts have stale size/hash values and README still contains the old snapshot metrics.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_checked_in_report_snapshot.py
git commit -m "test: guard checked-in report snapshot consistency"
```

---

### Task 2: Rebuild the report manifest from checked-in artifacts

**Files:**
- Modify: `reports/latest/manifest.json`
- Test: `tests/test_checked_in_report_snapshot.py`

- [ ] **Step 1: Rebuild the manifest with the same schema**

Run:

```bash
.venv/bin/python - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path("reports/latest")
manifest_path = root / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
for artifact in manifest["artifacts"]:
    path = root / artifact["path"]
    payload = path.read_bytes()
    artifact["size"] = len(payload)
    artifact["sha256"] = hashlib.sha256(payload).hexdigest()
manifest_path.write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
```

- [ ] **Step 2: Run the manifest test**

Run: `.venv/bin/python -m pytest tests/test_checked_in_report_snapshot.py::test_checked_in_report_manifest_matches_artifacts -q`

Expected: PASS.

- [ ] **Step 3: Commit the manifest refresh**

```bash
git add reports/latest/manifest.json
git commit -m "fix: refresh checked-in report manifest"
```

---

### Task 3: Align README snapshot metrics

**Files:**
- Modify: `README.md:247-258`
- Test: `tests/test_checked_in_report_snapshot.py`

- [ ] **Step 1: Update the README snapshot values**

Replace the stale block with the values from `reports/latest/strategy_summary.csv`:

```markdown
## Current Included Snapshot

Using the cached public-data run included in this workspace:

- Best momentum variant: `TOP20_MOM_top8_biweekly__bull_only`
- Best sector variant: `TOP20_SECTOR_top4_biweekly__bull_only`
- BTC buy-and-hold CAGR: about 16.8%
- Top-20 equal-weight CAGR: about 6.8%
- Best momentum CAGR: about 20.3%
- Best sector CAGR: about 18.1%
```

- [ ] **Step 2: Run the README consistency test**

Run: `.venv/bin/python -m pytest tests/test_checked_in_report_snapshot.py::test_readme_snapshot_matches_strategy_summary -q`

Expected: PASS.

- [ ] **Step 3: Commit the README correction**

```bash
git add README.md
git commit -m "docs: align README with checked-in research snapshot"
```

---

### Task 4: Remove or upgrade the vulnerable frontend dependency

**Files:**
- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`
- Test: `apps/web/src/**/*.test.tsx`

- [ ] **Step 1: Confirm whether `echarts` is imported**

Run: `rg -n "from [\"']echarts|require\\([\"']echarts|echarts" apps/web/src`

Expected: no runtime import. If confirmed, remove the unused direct dependency.

- [ ] **Step 2: Apply the minimal dependency fix**

Run: `npm --prefix apps/web uninstall echarts`

Then run: `npm --prefix apps/web audit fix`

- [ ] **Step 3: Run frontend tests**

Run: `npm --prefix apps/web test`

Expected: PASS.

- [ ] **Step 4: Run frontend typecheck and build**

Run: `npm --prefix apps/web run typecheck && npm --prefix apps/web run build`

Expected: PASS.

- [ ] **Step 5: Re-run the audit and record residual advisories**

Run: `npm --prefix apps/web audit --audit-level=moderate --registry=https://registry.npmjs.org`

Expected: zero production vulnerabilities; any remaining development-only advisory must be documented in the final report rather than fixed with `--force`.

- [ ] **Step 6: Commit the dependency change**

```bash
git add apps/web/package.json apps/web/package-lock.json
git commit -m "fix: remove vulnerable unused frontend dependency"
```

---

### Task 5: Full verification

**Files:**
- Modify: none

- [ ] **Step 1: Run Python tests**

Run: `make test`

Expected: all Python and Vitest tests pass.

- [ ] **Step 2: Run lint, typecheck, and OpenAPI checks**

Run:

```bash
make lint
make typecheck
.venv/bin/python -m atlas20.api.openapi --check
npm --prefix apps/web run openapi:check
```

Expected: all pass with no drift.

- [ ] **Step 3: Run repository health and dependency audits**

Run:

```bash
.venv/bin/python scripts/check_repo_health.py
.venv/bin/python -m pip_audit --strict .
npm --prefix apps/web audit --audit-level=moderate --registry=https://registry.npmjs.org
```

Expected: repository health and Python audit pass; frontend audit has no unresolved production vulnerability.
