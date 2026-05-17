"""Run artifact API routes."""

from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException

from atlas20.api.runner import APP_RUNS_DIR

router = APIRouter(prefix="/api", tags=["runs"])


@router.get("/runs")
def get_runs() -> dict:
    if not APP_RUNS_DIR.exists():
        return {"items": []}
    items = []
    for path in sorted(APP_RUNS_DIR.iterdir(), reverse=True):
        summary_path = path / "summary.csv"
        if path.is_dir() and summary_path.exists():
            summary = pd.read_csv(summary_path).iloc[0].to_dict()
            items.append({"run_id": path.name, "summary": summary})
    return {"items": items}


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    run_dir = APP_RUNS_DIR / run_id
    summary_path = run_dir / "summary.csv"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run_id, "summary": pd.read_csv(summary_path).iloc[0].to_dict()}


@router.get("/runs/{run_id}/{artifact}")
def get_run_artifact(run_id: str, artifact: str) -> dict:
    allowed = {
        "equity": "equity_curve.csv",
        "drawdown": "drawdowns.csv",
        "daily-returns": "daily_returns.csv",
        "selection-history": "selection_history.csv",
    }
    filename = allowed.get(artifact)
    if filename is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    path = Path(APP_RUNS_DIR / run_id / filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"items": pd.read_csv(path).to_dict(orient="records")}
