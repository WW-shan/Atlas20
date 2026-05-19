from concurrent.futures import ThreadPoolExecutor
from datetime import date

from sqlmodel import SQLModel, Session, create_engine

from atlas20.api.repositories import RunsRepo


def test_create_with_unique_id_allocates_unique_ids_concurrently(tmp_path):
    db_path = tmp_path / "runs.sqlite"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    base_attrs = {
        "strategy": "ATLAS Adaptive v4",
        "strategy_family": "ATLAS",
        "universe": "Top-20",
        "window_start": date(2024, 1, 1),
        "window_end": date(2026, 5, 18),
        "status": "queued",
    }

    def create_run() -> str:
        with Session(engine) as session:
            run = RunsRepo(session).create_with_unique_id(base_attrs)
            session.commit()
            return run.run_id

    with ThreadPoolExecutor(max_workers=10) as executor:
        run_ids = list(executor.map(lambda _: create_run(), range(10)))

    assert len(run_ids) == 10
    assert len(set(run_ids)) == 10
