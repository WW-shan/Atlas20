from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from atlas20.api import services_report
from atlas20.api.app import create_app
from atlas20.api.db.models import ReportFile
from atlas20.api.repositories import ReportsRepo, RunsRepo, get_session
from atlas20.api.settings import get_settings


VALID_PARAMS = {
    "preset": "ATLAS Adaptive v3",
    "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
    "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
    "allocation": {"positionPct": 5.0, "slots": 10},
    "costs": {"feeBps": 10, "slippageBps": 5},
}


def _client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    *,
    raise_server_exceptions: bool = True,
) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'generate.sqlite').as_posix()}")
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prepare_run(db_session: Session, report_root: Path, run_id: str = "btk_0142") -> Path:
    run = RunsRepo(db_session).get(run_id)
    assert run is not None
    run.status = "completed"
    run.params = json.dumps(VALID_PARAMS)
    db_session.add(run)
    db_session.flush()
    run_dir = report_root / "app_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.csv").write_text(
        "\n".join(
            [
                "strategy,total_return,cagr,annualized_volatility,sharpe,sortino,max_drawdown,calmar,monthly_win_rate,annualized_turnover,avg_turnover_per_rebalance,average_holdings",
                "BTC_BH__always_on,0.20,0.10,0.20,0.80,1.00,-0.30,0.33,0.50,0.10,0.05,1",
                "TOP20_EQ__always_on,0.30,0.15,0.25,1.00,1.20,-0.25,0.60,0.55,0.20,0.10,5",
                "TOP20_MOM_alpha,0.50,0.20,0.30,1.50,1.80,-0.20,1.00,0.60,0.30,0.10,5",
                "TOP20_SECTOR_beta,0.40,0.18,0.28,1.30,1.50,-0.22,0.80,0.58,0.25,0.10,5",
                "TOP20_MOM_alpha__bull_only,0.45,0.19,0.27,1.60,1.90,-0.18,1.05,0.62,0.22,0.10,4",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "yearly_returns.csv").write_text(
        "year,BTC_BH__always_on,TOP20_EQ__always_on,TOP20_MOM_alpha,TOP20_SECTOR_beta\n"
        "2025,0.10,0.12,0.20,0.18\n"
        "2026,0.05,0.06,0.08,0.07\n",
        encoding="utf-8",
    )
    (run_dir / "regime_performance.csv").write_text(
        "strategy,regime,annualized_return\n"
        "BTC_BH__always_on,bull,0.10\n"
        "TOP20_EQ__always_on,bull,0.12\n"
        "TOP20_MOM_alpha,bull,0.20\n"
        "TOP20_SECTOR_beta,bull,0.18\n",
        encoding="utf-8",
    )
    (run_dir / "equity_curve.csv").write_text(
        "date,BTC_BH__always_on,TOP20_MOM_alpha\n"
        "2026-01-01,1.0,1.0\n"
        "2026-01-02,1.1,1.25\n",
        encoding="utf-8",
    )
    weights = run_dir / "weights"
    weights.mkdir(exist_ok=True)
    (weights / "TOP20_MOM_alpha.csv").write_text("date,BTC,ETH\n2026-01-01,0.5,0.5\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text('{"run_id": "btk_0142"}\n', encoding="utf-8")
    (run_dir / "params.json").write_text(json.dumps(VALID_PARAMS) + "\n", encoding="utf-8")
    return run_dir


def test_generate_report_unknown_run_id_returns_404(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)

    response = client.post("/api/reports/generate", json={"run_id": "btk_9999", "formats": ["markdown"]})

    assert response.status_code == 404


def test_generate_markdown_report_registers_file_and_sha256(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    _prepare_run(db_session, report_root)

    response = client.post("/api/reports/generate", json={"run_id": "btk_0142", "formats": ["markdown"]})

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "completed"
    markdown_file = next(item for item in payload["files"] if item["kind"] == "markdown")
    digest = report_root / markdown_file["path"]
    assert digest.exists()
    assert markdown_file["sha256"] == _sha256(digest)
    db_row = db_session.exec(select(ReportFile).where(ReportFile.run_id == "btk_0142", ReportFile.kind == "markdown")).one()
    assert db_row.sha256 == _sha256(digest)


def test_generate_report_returns_404_when_run_outputs_are_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session, raise_server_exceptions=False)
    report_root = get_settings().report_root
    run_dir = _prepare_run(db_session, report_root)
    (run_dir / "summary.csv").unlink()

    response = client.post("/api/reports/generate", json={"run_id": "btk_0142", "formats": ["markdown"]})

    assert response.status_code == 404
    assert "run output missing" in response.json()["detail"]


def test_generate_multiple_formats_writes_png_and_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    _prepare_run(db_session, report_root)

    response = client.post(
        "/api/reports/generate",
        json={"run_id": "btk_0142", "formats": ["markdown", "png", "bundle"]},
    )

    assert response.status_code == 202
    files = response.json()["files"]
    kinds = {item["kind"] for item in files}
    assert {"markdown", "png", "bundle"}.issubset(kinds)
    for item in files:
        assert (report_root / item["path"]).exists()


def test_generate_pdf_skips_when_weasyprint_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    _prepare_run(db_session, get_settings().report_root)
    monkeypatch.setattr(services_report, "generate_pdf", lambda markdown_path, output_path: False)

    response = client.post("/api/reports/generate", json={"run_id": "btk_0142", "formats": ["pdf"]})

    assert response.status_code == 202
    payload = response.json()
    assert payload["files"] == []
    assert any("pdf" in warning.lower() for warning in payload["warnings"])


def test_generate_pdf_writes_file_when_weasyprint_available(tmp_path: Path) -> None:
    try:
        pytest.importorskip("weasyprint")
    except OSError as exc:
        pytest.skip(f"weasyprint native dependencies unavailable: {exc}")
    markdown_path = tmp_path / "digest.md"
    pdf_path = tmp_path / "digest.pdf"
    markdown_path.write_text("# Digest\n", encoding="utf-8")

    if not services_report.generate_pdf(markdown_path, pdf_path):
        pytest.skip("weasyprint runtime unavailable")
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_reports_repo_upsert_replaces_same_run_kind(db_session: Session) -> None:
    repo = ReportsRepo(db_session)
    first = repo.upsert(
        ReportFile(
            run_id="btk_0142",
            kind="markdown",
            path="app_runs/btk_0142/old.md",
            sha256="old",
            size_bytes=1,
        )
    )
    second = repo.upsert(
        ReportFile(
            run_id="btk_0142",
            kind="markdown",
            path="app_runs/btk_0142/digest.md",
            sha256="new",
            size_bytes=2,
        )
    )

    assert second.id == first.id
    assert repo.by_run("btk_0142")[0].sha256 == "new"
