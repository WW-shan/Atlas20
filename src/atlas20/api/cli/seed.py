"""Seed SQLite persistence from fallback run fixtures."""

from __future__ import annotations

import json
from datetime import date, datetime

from sqlmodel import Session

from atlas20.api import mock_data
from atlas20.api.db.models import Run
from atlas20.api.db.migrate import upgrade_to_head
from atlas20.api.repositories import RunsRepo, get_engine
from atlas20.api.settings import get_settings


def _parse_utc_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def run_from_seed_row(row: dict[str, object]) -> Run:
    window = row["window"]
    assert isinstance(window, dict)
    return Run.model_validate(
        {
            "run_id": row["run_id"],
            "strategy": row["strategy"],
            "strategy_family": row.get("strategy_family"),
            "universe": row["universe"],
            "window_start": date.fromisoformat(str(window["start"])),
            "window_end": date.fromisoformat(str(window["end"])),
            "status": row["status"],
            "return_pct": row.get("return_pct"),
            "sharpe": row.get("sharpe"),
            "max_dd": row.get("max_dd"),
            "duration_s": row.get("duration_s"),
            "eta_s": row.get("eta_s"),
            "spark": json.dumps(row.get("spark") or []),
            "created_at": _parse_utc_datetime(str(row["created_at"])),
            "favorited": bool(row.get("favorited", False)),
        }
    )


def main() -> None:
    settings = get_settings()
    upgrade_to_head(settings)
    engine = get_engine(settings)
    with Session(engine) as session:
        runs_repo = RunsRepo(session)
        if runs_repo.list(page_size=1)[1] > 0:
            print("DB already seeded, skipping")
            return
        for row in mock_data.fallback_runs_list:
            runs_repo.create(run_from_seed_row(row))
        session.commit()
    print(f"Seeded {len(mock_data.fallback_runs_list)} runs")
