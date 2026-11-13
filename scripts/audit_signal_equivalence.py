"""Prove the checked-in LS45 target ledger is reproducible from its data.

This audit is deliberately specific to the current live track:
``PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21``. It rebuilds the ledger with
``run_ls45_live_signal.py`` at the manifest's frozen end date and compares every
signed target row (long, short and flat) with the checked-in
``reports/ls45_live_g125/oos_targets.csv``.

It never places orders. A changed short weight, missing event, changed action,
or a spec/manifest mismatch makes the audit fail.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import ensure_dir  # noqa: E402

from scripts.run_h5_regime_short_router import LS45_CANDIDATE_ID  # noqa: E402
from scripts.run_ls45_live_signal import build_command  # noqa: E402

DEFAULT_TARGETS_FILE = Path("reports/ls45_live_g125/oos_targets.csv")
DEFAULT_MANIFEST_FILE = Path("reports/ls45_live_g125/manifest.json")
DEFAULT_JSON_OUT = Path("reports/ls45_live_g125_live/signal_equivalence.json")
_REQUIRED_COLUMNS = {
    "signal_date",
    "execution_hint",
    "asset",
    "side",
    "target_weight",
    "change_weight",
    "action",
}


def _normalize_ledger(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(_REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(f"target ledger is missing columns: {missing}")
    normalized = frame.copy()
    for column in ("signal_date", "execution_hint"):
        normalized[column] = pd.to_datetime(
            normalized[column], utc=True, format="mixed", errors="raise"
        )
    for column in ("target_weight", "change_weight"):
        normalized[column] = pd.to_numeric(normalized[column], errors="raise")
    normalized["asset"] = normalized["asset"].astype(str).str.lower()
    normalized["side"] = normalized["side"].astype(str).str.lower()
    normalized["action"] = normalized["action"].astype(str).str.upper()
    return normalized.sort_values(["signal_date", "asset"]).reset_index(drop=True)


def _compare_target_ledgers(
    frozen: pd.DataFrame,
    replay: pd.DataFrame,
) -> dict[str, object]:
    """Compare two signed target ledgers without dropping short or flat rows."""

    left = _normalize_ledger(frozen)
    right = _normalize_ledger(replay)
    keys = ["signal_date", "execution_hint", "asset"]
    joined = left.merge(right, on=keys, how="outer", suffixes=("_frozen", "_replay"), indicator=True)

    differences: list[dict[str, object]] = []
    for row in joined.to_dict("records"):
        if row["_merge"] == "left_only":
            differences.append(
                {
                    "kind": "missing_from_replay",
                    "signal_date": str(pd.Timestamp(row["signal_date"]).date()),
                    "asset": row["asset"],
                    "frozen_action": row.get("action_frozen"),
                    "replay_action": None,
                    "max_weight_delta": None,
                }
            )
            continue
        if row["_merge"] == "right_only":
            differences.append(
                {
                    "kind": "only_in_replay",
                    "signal_date": str(pd.Timestamp(row["signal_date"]).date()),
                    "asset": row["asset"],
                    "frozen_action": None,
                    "replay_action": row.get("action_replay"),
                    "max_weight_delta": None,
                }
            )
            continue
        target_delta = abs(float(row["target_weight_frozen"]) - float(row["target_weight_replay"]))
        change_delta = abs(float(row["change_weight_frozen"]) - float(row["change_weight_replay"]))
        same_metadata = (
            str(row["side_frozen"]) == str(row["side_replay"])
            and str(row["action_frozen"]) == str(row["action_replay"])
        )
        max_delta = max(target_delta, change_delta)
        if max_delta > 1e-12 or not same_metadata:
            differences.append(
                {
                    "kind": "changed",
                    "signal_date": str(pd.Timestamp(row["signal_date"]).date()),
                    "asset": row["asset"],
                    "frozen_side": row["side_frozen"],
                    "replay_side": row["side_replay"],
                    "frozen_action": row["action_frozen"],
                    "replay_action": row["action_replay"],
                    "frozen_target_weight": row["target_weight_frozen"],
                    "replay_target_weight": row["target_weight_replay"],
                    "frozen_change_weight": row["change_weight_frozen"],
                    "replay_change_weight": row["change_weight_replay"],
                    "max_weight_delta": max_delta,
                }
            )

    common = joined.loc[joined["_merge"] == "both"]
    missing = joined.loc[joined["_merge"] == "left_only"]
    extra = joined.loc[joined["_merge"] == "right_only"]
    return {
        "passed": not differences,
        "frozen_rows": int(len(left)),
        "replay_rows": int(len(right)),
        "overlapping_rows": int(len(common)),
        "overlapping_signal_days": int(common["signal_date"].nunique()) if not common.empty else 0,
        "differing_rows": len(differences),
        "differences": differences[:50],
        "events_only_in_replay": sorted(
            {
                f"{pd.Timestamp(row.signal_date).date()}|{row.asset}"
                for row in extra.itertuples(index=False)
            }
        ),
        "events_only_in_frozen": sorted(
            {
                f"{pd.Timestamp(row.signal_date).date()}|{row.asset}"
                for row in missing.itertuples(index=False)
            }
        ),
    }


def _rebuild_replay(end_date: str) -> pd.DataFrame:
    with tempfile.TemporaryDirectory(prefix="atlas20-ls45-audit-") as tmp:
        output_dir = Path(tmp) / "ledger"
        command = build_command(end_date=end_date, output_dir=str(output_dir))
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
        path = output_dir / "oos_targets.csv"
        if not path.is_file():
            raise FileNotFoundError(f"replay did not write {path}")
        return pd.read_csv(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--manifest-file", type=Path, default=DEFAULT_MANIFEST_FILE)
    parser.add_argument("--replay-targets-file", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args(argv)

    checked_at = datetime.now(timezone.utc)
    if not args.manifest_file.is_file():
        raise SystemExit(f"manifest not found: {args.manifest_file}")
    if not args.targets_file.is_file():
        raise SystemExit(f"target ledger not found: {args.targets_file}")
    manifest = json.loads(args.manifest_file.read_text(encoding="utf-8"))
    spec = str(manifest.get("tracked_spec") or "")
    end_date = str(manifest.get("end_date") or "")
    if not end_date:
        raise SystemExit("manifest is missing end_date")
    end_date = str(pd.Timestamp(end_date).date())

    frozen = pd.read_csv(args.targets_file)
    if args.replay_targets_file is not None:
        replay = pd.read_csv(args.replay_targets_file)
    else:
        try:
            replay = _rebuild_replay(end_date)
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"LS45 replay failed: {exc}") from exc

    comparison = _compare_target_ledgers(frozen, replay)
    passed = bool(comparison["passed"]) and spec == LS45_CANDIDATE_ID
    payload = {
        "spec": spec,
        "expected_spec": LS45_CANDIDATE_ID,
        "end_date": end_date,
        "checked_at": checked_at.isoformat(),
        **comparison,
        "passed": passed,
    }
    output = ensure_dir(args.json_out.parent)
    (output / args.json_out.name).write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"LS45 信号等价性核对 · {spec or '?'} · end {end_date}")
    print(
        f"  冻结账本 {comparison['frozen_rows']} 行 / 重建账本 {comparison['replay_rows']} 行；"
        f"重叠信号日 {comparison['overlapping_signal_days']}，差异 {comparison['differing_rows']}"
    )
    if payload["differences"]:
        for item in payload["differences"][:10]:
            print(f"  ❌ {item}")
    if spec != LS45_CANDIDATE_ID:
        print(f"  ❌ manifest spec {spec!r} != {LS45_CANDIDATE_ID!r}")
    print(f"  结论: {'一致（同一套 LS45 计算）' if passed else '不一致，必须停下排查'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
