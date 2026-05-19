from datetime import datetime, timezone

from sqlmodel import Session

from atlas20.api.db.models import ReportFile
from atlas20.api.repositories import ReportsRepo


def _report(kind: str, path: str, size_bytes: int, generated_at: datetime) -> ReportFile:
    return ReportFile(
        run_id="btk_0142" if kind == "run" else None,
        kind=kind,
        path=path,
        size_bytes=size_bytes,
        sha256=f"sha-{path}",
        generated_at=generated_at,
    )


def test_reports_repo_crud_sort_and_by_run(db_session: Session):
    repo = ReportsRepo(db_session)
    old = repo.create(_report("weekly", "weekly.md", 200, datetime(2026, 5, 1, tzinfo=timezone.utc)))
    run = repo.create(_report("run", "run.md", 100, datetime(2026, 5, 3, tzinfo=timezone.utc)))
    compare = repo.create(_report("compare", "compare.md", 300, datetime(2026, 5, 2, tzinfo=timezone.utc)))

    assert run.id is not None
    assert repo.get(run.id).path == "run.md"
    assert [report.id for report in repo.by_run("btk_0142")] == [run.id]
    assert [report.id for report in repo.list(sort="recent")] == [run.id, compare.id, old.id]
    assert [report.id for report in repo.list(sort="oldest")] == [old.id, compare.id, run.id]
    assert [report.id for report in repo.list(sort="size")] == [compare.id, old.id, run.id]
    assert [report.id for report in repo.list(sort="type")] == [compare.id, run.id, old.id]
