"""Report files repository."""

from __future__ import annotations

from sqlmodel import Session, select

from atlas20.api.db.models import ReportFile


class ReportsRepo:
    def __init__(self, session: Session):
        self._s = session

    def list(self, *, sort: str = "recent") -> list[ReportFile]:
        stmt = select(ReportFile)
        if sort == "oldest":
            stmt = stmt.order_by(ReportFile.generated_at.asc(), ReportFile.id.asc())
        elif sort == "size":
            stmt = stmt.order_by(ReportFile.size_bytes.desc(), ReportFile.id.asc())
        elif sort == "type":
            stmt = stmt.order_by(ReportFile.kind.asc(), ReportFile.generated_at.desc())
        else:
            stmt = stmt.order_by(ReportFile.generated_at.desc(), ReportFile.id.asc())
        return list(self._s.exec(stmt).all())

    def get(self, report_id: int) -> ReportFile | None:
        return self._s.get(ReportFile, report_id)

    def create(self, report: ReportFile) -> ReportFile:
        self._s.add(report)
        self._s.flush()
        self._s.refresh(report)
        return report

    def upsert(self, report: ReportFile) -> ReportFile:
        stmt = select(ReportFile).where(ReportFile.kind == report.kind)
        if report.run_id is None:
            stmt = stmt.where(ReportFile.run_id.is_(None), ReportFile.path == report.path)
        else:
            stmt = stmt.where(ReportFile.run_id == report.run_id)
        existing = self._s.exec(stmt.order_by(ReportFile.generated_at.desc(), ReportFile.id.desc())).first()
        if existing is None:
            return self.create(report)
        existing.path = report.path
        existing.size_bytes = report.size_bytes
        existing.sha256 = report.sha256
        existing.generated_at = report.generated_at
        self._s.add(existing)
        self._s.flush()
        self._s.refresh(existing)
        return existing

    def by_run(self, run_id: str) -> list[ReportFile]:
        stmt = select(ReportFile).where(ReportFile.run_id == run_id).order_by(ReportFile.generated_at.desc())
        return list(self._s.exec(stmt).all())

    def by_run_kind(self, run_id: str | None, kind: str) -> ReportFile | None:
        if run_id is None:
            return None
        stmt = (
            select(ReportFile)
            .where(ReportFile.run_id == run_id, ReportFile.kind == kind)
            .order_by(ReportFile.generated_at.desc(), ReportFile.id.desc())
        )
        return self._s.exec(stmt).first()
