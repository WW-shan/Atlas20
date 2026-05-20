"""Report artifact generation services."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
import zipfile

from fastapi import HTTPException
import matplotlib
import pandas as pd
from sqlmodel import Session

from atlas20.api._time import utc_now
from atlas20.api.config_adapter import to_research_config
from atlas20.api.db.models import ReportFile
from atlas20.api.manifest import ReportArtifact, sha256_file, write_report_manifest
from atlas20.api.repositories import ReportsRepo, RunsRepo
from atlas20.api.schemas import BacktestConfig, ReportFormat
from atlas20.api.settings import Settings, get_settings

matplotlib.use("Agg")

from atlas20.reporting.charts import plot_equity_curves
from atlas20.reporting.report import build_markdown_report

logger = logging.getLogger(__name__)

PDF_UNAVAILABLE_WARNING = "pdf skipped: weasyprint unavailable"
REPORT_FORMATS: set[str] = {"markdown", "pdf", "png", "csv", "bundle"}


@dataclass(frozen=True)
class GeneratedReports:
    files: list[ReportFile]
    warnings: list[str]


def _tmp_path(path: Path, suffix: str = ".tmp") -> Path:
    return path.with_name(f"{path.name}{suffix}_{os.getpid()}")


def _first_existing(run_dir: Path, names: list[str]) -> Path:
    for name in names:
        candidate = run_dir / name
        if candidate.exists():
            return candidate
    raise HTTPException(
        status_code=404,
        detail=f"run output missing: expected one of {names} under {run_dir.name}",
    )


def _read_summary(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "strategy" in df.columns:
        df = df.set_index("strategy")
    elif len(df.columns) > 1:
        first = str(df.columns[0])
        if first.startswith("Unnamed") or first in {"", "index"}:
            df = df.set_index(df.columns[0])
    return df


def _read_indexed_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if len(df.columns) > 1:
        first = str(df.columns[0])
        if first.startswith("Unnamed") or first in {"", "index", "year", "date"}:
            df = df.set_index(df.columns[0])
    return df


def _research_config(run_params: str | None, settings: Settings) -> object:
    if not run_params:
        raise HTTPException(status_code=422, detail="run params missing")
    try:
        config = BacktestConfig.model_validate_json(run_params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="run params invalid") from exc
    try:
        return to_research_config(config, config.preset, settings)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _run_dir(settings: Settings, run_id: str) -> Path:
    run_dir = Path(settings.report_root) / "app_runs" / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run output not found")
    return run_dir


def _register_file(session: Session, settings: Settings, run_id: str, kind: str, path: Path) -> ReportFile:
    report_root = Path(settings.report_root).resolve()
    resolved = path.resolve()
    try:
        relative_path = resolved.relative_to(report_root).as_posix()
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="report path outside report_root") from exc
    report = ReportFile(
        run_id=run_id,
        kind=kind,
        path=relative_path,
        sha256=sha256_file(resolved),
        size_bytes=resolved.stat().st_size,
        generated_at=utc_now(),
    )
    return ReportsRepo(session).upsert(report)


def _artifacts_from_rows(settings: Settings, rows: list[ReportFile]) -> list[ReportArtifact]:
    report_root = Path(settings.report_root)
    return [ReportArtifact(kind=row.kind, path=report_root / row.path) for row in rows]


def _generate_markdown(run_id: str, run_dir: Path, run_params: str | None, settings: Settings) -> Path:
    summary_path = _first_existing(run_dir, ["summary.csv", "strategy_summary.csv"])
    yearly_path = _first_existing(run_dir, ["yearly_returns.csv"])
    regime_path = _first_existing(run_dir, ["regime_performance.csv"])
    output_path = run_dir / "digest.md"
    tmp_path = _tmp_path(output_path)
    try:
        build_markdown_report(
            _research_config(run_params, settings),
            _read_summary(summary_path),
            _read_indexed_csv(yearly_path),
            pd.read_csv(regime_path),
            tmp_path,
        )
        os.replace(tmp_path, output_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return output_path


def generate_pdf(markdown_path: Path, output_path: Path) -> bool:
    try:
        from markdown import markdown as md_to_html
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        logger.warning("%s: %s", PDF_UNAVAILABLE_WARNING, exc)
        return False

    html = md_to_html(Path(markdown_path).read_text(encoding="utf-8"))
    try:
        HTML(string=html).write_pdf(output_path)
    except OSError as exc:
        logger.warning("%s: %s", PDF_UNAVAILABLE_WARNING, exc)
        return False
    return True


def _equity_results(equity_path: Path) -> dict[str, object]:
    df = pd.read_csv(equity_path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    elif len(df.columns) > 1:
        first = str(df.columns[0])
        if first.startswith("Unnamed") or first in {"", "index"}:
            df[df.columns[0]] = pd.to_datetime(df[df.columns[0]])
            df = df.set_index(df.columns[0])
    numeric = df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
    if numeric.empty:
        raise HTTPException(status_code=422, detail="equity_curve.csv has no numeric series")
    return {
        str(column): SimpleNamespace(equity_curve=numeric[column].dropna())
        for column in numeric.columns
        if not numeric[column].dropna().empty
    }


def _generate_png(run_dir: Path) -> Path:
    output_path = run_dir / "equity_curve.png"
    equity_path = _first_existing(run_dir, ["equity_curve.csv", "equity_curves.csv"])
    tmp_path = output_path.with_name(f"{output_path.stem}.tmp_{os.getpid()}{output_path.suffix}")
    try:
        plot_equity_curves(_equity_results(equity_path), tmp_path)
        os.replace(tmp_path, output_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return output_path


def generate_bundle(run_id: str, run_dir: Path | None = None) -> Path:
    settings = get_settings()
    run_dir = Path(run_dir) if run_dir is not None else Path(settings.report_root) / "app_runs" / run_id
    output_path = run_dir / "bundle.zip"
    tmp_path = _tmp_path(output_path)
    include_names = [
        "digest.md",
        "equity_curve.png",
        "summary.csv",
        "equity_curve.csv",
        "manifest.json",
    ]
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in include_names:
                candidate = run_dir / name
                if candidate.exists():
                    archive.write(candidate, arcname=name)
            weights_dir = run_dir / "weights"
            if weights_dir.exists():
                for path in sorted(weights_dir.glob("*.csv")):
                    archive.write(path, arcname=path.relative_to(run_dir).as_posix())
        os.replace(tmp_path, output_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return output_path


def generate_run_report_with_warnings(
    run_id: str,
    formats: set[ReportFormat] | set[str],
    *,
    session: Session,
    settings: Settings | None = None,
) -> GeneratedReports:
    settings = settings or get_settings()
    requested = {str(item) for item in formats}
    unknown = requested - REPORT_FORMATS
    if unknown:
        raise HTTPException(status_code=422, detail=f"unsupported report format: {sorted(unknown)[0]}")
    if not requested:
        raise HTTPException(status_code=422, detail="formats must not be empty")

    run = RunsRepo(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    run_dir = _run_dir(settings, run_id)
    files: list[ReportFile] = []
    warnings: list[str] = []

    needs_markdown = bool(requested & {"markdown", "pdf", "bundle"})
    markdown_path: Path | None = None
    if needs_markdown:
        markdown_path = _generate_markdown(run_id, run_dir, run.params, settings)
        if "markdown" in requested:
            files.append(_register_file(session, settings, run_id, "markdown", markdown_path))

    if "pdf" in requested:
        markdown_path = markdown_path or _generate_markdown(run_id, run_dir, run.params, settings)
        pdf_path = run_dir / "digest.pdf"
        tmp_pdf = _tmp_path(pdf_path)
        try:
            if generate_pdf(markdown_path, tmp_pdf):
                os.replace(tmp_pdf, pdf_path)
                files.append(_register_file(session, settings, run_id, "pdf", pdf_path))
            else:
                warnings.append(PDF_UNAVAILABLE_WARNING)
        finally:
            if tmp_pdf.exists():
                tmp_pdf.unlink()

    if requested & {"png", "bundle"}:
        png_path = _generate_png(run_dir)
        if "png" in requested:
            files.append(_register_file(session, settings, run_id, "png", png_path))

    if "csv" in requested:
        summary_path = _first_existing(run_dir, ["summary.csv", "strategy_summary.csv"])
        files.append(_register_file(session, settings, run_id, "csv", summary_path))

    if "bundle" in requested:
        bundle_path = generate_bundle(run_id, run_dir)
        files.append(_register_file(session, settings, run_id, "bundle", bundle_path))

    write_report_manifest(run_id, run_dir, _artifacts_from_rows(settings, files))
    return GeneratedReports(files=files, warnings=warnings)


def generate_run_report(
    run_id: str,
    formats: set[ReportFormat] | set[str],
    *,
    session: Session,
    settings: Settings | None = None,
) -> list[ReportFile]:
    return generate_run_report_with_warnings(run_id, formats, session=session, settings=settings).files
