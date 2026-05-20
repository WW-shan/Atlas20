from datetime import timedelta

from sqlmodel import Session, select

from atlas20.api._time import utc_now
from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo


def test_terminal_transition_emits_structured_log(db_session: Session, capsys, caplog) -> None:
    run = db_session.exec(select(Run).where(Run.run_id == "btk_0142")).one()
    run.status = "running"
    run.started_at = utc_now() - timedelta(seconds=5)
    db_session.add(run)
    db_session.commit()

    RunsRepo(db_session).update_metrics_from_completion(
        "btk_0142",
        return_pct=0.42,
        sharpe=1.9,
        max_dd=-0.18,
        duration_s=5,
    )

    captured = capsys.readouterr()
    logs = f"{captured.out}\n{captured.err}\n{caplog.text}"
    assert "backtest.terminal" in logs
    assert "btk_0142" in logs
