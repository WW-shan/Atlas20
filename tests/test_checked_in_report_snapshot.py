from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "reports" / "latest"


def _manifest() -> dict[str, object]:
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
            failures.append(f"{artifact['path']}: size {actual_size} != manifest {artifact['size']}")
        if actual_sha != artifact["sha256"]:
            failures.append(f"{artifact['path']}: sha256 {actual_sha} != manifest {artifact['sha256']}")
    assert failures == []


def test_readme_snapshot_matches_strategy_summary() -> None:
    with (LATEST / "strategy_summary.csv").open(encoding="utf-8") as handle:
        summary_rows = list(csv.DictReader(handle))
    by_strategy = {row["strategy"]: row for row in summary_rows}

    momentum_candidates = [row for row in summary_rows if row["strategy"].startswith("TOP20_MOM_")]
    sector_candidates = [row for row in summary_rows if row["strategy"].startswith("TOP20_SECTOR_")]
    best_momentum = max(momentum_candidates, key=lambda row: (float(row["sharpe"]), float(row["cagr"])))
    best_sector = max(sector_candidates, key=lambda row: (float(row["sharpe"]), float(row["cagr"])))
    btc = by_strategy["BTC_BH__always_on"]
    equal_weight = by_strategy["TOP20_EQ__always_on"]

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"`{best_momentum['strategy']}`" in readme
    assert f"`{best_sector['strategy']}`" in readme
    assert f"{float(btc['cagr']):.1%}" in readme
    assert f"{float(equal_weight['cagr']):.1%}" in readme
    assert f"{float(best_momentum['cagr']):.1%}" in readme
    assert f"{float(best_sector['cagr']):.1%}" in readme
