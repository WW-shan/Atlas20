from datetime import date

from sqlalchemy import text
from sqlmodel import Session, select

from atlas20.api.db.models import ReportFile, Run
from atlas20.api.repositories import RunsRepo


def _new_run(run_id: str = "btk_0200") -> Run:
    return Run(
        run_id=run_id,
        strategy="ATLAS Adaptive v4",
        strategy_family="ATLAS",
        universe="Top-20",
        window_start=date(2024, 1, 1),
        window_end=date(2026, 5, 18),
        status="queued",
    )


def test_runs_repo_crud_update_and_toggle(db_session: Session):
    repo = RunsRepo(db_session)

    created = repo.create(_new_run())
    assert created.run_id == "btk_0200"
    assert repo.get("btk_0200") is not None

    updated = repo.update("btk_0200", status="running", eta_s=30)
    assert updated is not None
    assert updated.status == "running"
    assert updated.eta_s == 30

    toggled = repo.toggle_favorite("btk_0200")
    assert toggled is not None
    assert toggled.favorited is True
    assert repo.toggle_favorite("missing") is None


def test_runs_repo_list_filters_and_paginates(db_session: Session):
    repo = RunsRepo(db_session)

    atlas_rows, atlas_total = repo.list(q="ATLAS", page_size=20)
    completed_rows, completed_total = repo.list(chips=["completed"], page_size=20)
    family_rows, family_total = repo.list(chips=["ATLAS"], page_size=20)
    combined_rows, combined_total = repo.list(chips=["ATLAS", "completed"], page_size=20)
    favorite_rows, favorite_total = repo.list(chips=["favorited"], page_size=20)
    recent_rows, recent_total = repo.list(date_cutoff=date(2026, 5, 16), page_size=20)
    page_one, total = repo.list(page=1, page_size=5)
    page_two, _ = repo.list(page=2, page_size=5)

    assert atlas_total == 5
    assert all("ATLAS" in row.strategy for row in atlas_rows)
    assert completed_total == 10
    assert all(row.status == "completed" for row in completed_rows)
    assert family_total == 5
    assert all(row.strategy_family == "ATLAS" for row in family_rows)
    assert combined_total == 4
    assert all(row.strategy_family == "ATLAS" and row.status == "completed" for row in combined_rows)
    assert favorite_total == 2
    assert all(row.favorited for row in favorite_rows)
    assert recent_total == 9
    assert all(row.run_id != "btk_0139" for row in recent_rows)
    assert total == 14
    assert page_one[-1].run_id == "btk_0144"
    assert page_two[0].run_id == "btk_0143"


def test_runs_repo_lists_queue_and_next_btk_id(db_session: Session):
    repo = RunsRepo(db_session)

    queue = repo.list_queue()
    assert [run.run_id for run in queue] == ["btk_0148", "btk_0147"]
    assert repo.next_btk_id() == "btk_0149"

    repo.create(_new_run("btk_0149"))

    assert repo.next_btk_id() == "btk_0150"


def test_deleting_run_sets_report_files_run_id_to_null(db_session: Session):
    db_session.exec(text("PRAGMA foreign_keys=ON"))
    run = _new_run("btk_report_fk")
    db_session.add(run)
    db_session.commit()
    report = ReportFile(
        run_id=run.run_id,
        kind="markdown",
        path="reports/btk_report_fk/digest.md",
        size_bytes=123,
        sha256="sha-report-fk",
    )
    db_session.add(report)
    db_session.commit()

    db_session.delete(run)
    db_session.commit()

    row = db_session.exec(select(ReportFile).where(ReportFile.sha256 == "sha-report-fk")).one()
    assert row.run_id is None
