from collections.abc import Iterator
from datetime import date, datetime
import json
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from atlas20.api import mock_data
from atlas20.api.db.models import Run
from atlas20.api.repositories._session import dispose_all_engines
from atlas20.api.settings import get_settings


SUMMARY_HEADER = (
    "strategy,total_return,cagr,annualized_volatility,sharpe,sortino,max_drawdown,"
    "calmar,monthly_win_rate,annualized_turnover,avg_turnover_per_rebalance,average_holdings"
)
EQUITY_HEADER = ","
DAILY_RETURNS_HEADER = ","
REBALANCE_HEADER = (
    "coin_id,price,market_cap,volume_usd,history_days,symbol,name,sector,"
    "rebalance_date,universe_rank"
)
DATA_QUALITY_HEADER = (
    "symbol,validation_passed,validation_reason,latest_overlap_date,latest_price_gap,"
    "median_price_gap,price_correlation,included_in_panel"
)

@pytest.fixture(autouse=True)
def atlas20_test_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ATLAS20_ANCHOR_DATE", "2026-05-19")
    get_settings.cache_clear()
    yield
    dispose_all_engines()
    get_settings.cache_clear()


def _write_csv(directory: Path, filename: str, header: str, rows: list[str]) -> None:
    target = directory / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join([header, *rows]), encoding="utf-8")


def write_summary_csv(report_root: Path, rows: list[str], *, header: str = SUMMARY_HEADER) -> None:
    _write_csv(Path(report_root) / "latest", "strategy_summary.csv", header, rows)


def write_equity_csv(report_root: Path, rows: list[str], *, header: str = EQUITY_HEADER) -> None:
    _write_csv(Path(report_root) / "latest", "equity_curves.csv", header, rows)


def write_daily_returns_csv(report_root: Path, rows: list[str], *, header: str = DAILY_RETURNS_HEADER) -> None:
    _write_csv(Path(report_root) / "latest", "daily_returns.csv", header, rows)


def write_rebalance_csv(data_root: Path, rows: list[str], *, header: str = REBALANCE_HEADER) -> None:
    _write_csv(Path(data_root) / "processed", "rebalance_universe.csv", header, rows)


def write_data_quality_csv(data_root: Path, rows: list[str], *, header: str = DATA_QUALITY_HEADER) -> None:
    _write_csv(Path(data_root) / "processed", "data_quality.csv", header, rows)


def write_alpha_btc_report_csvs(report_root: Path) -> None:
    write_summary_csv(
        report_root,
        [
            "ALPHA,0.50,0.20,0.30,1.70,2.00,-0.20,1.00,0.60,4.00,0.50,2.00",
            "BTC_BH__always_on,0.30,0.15,0.35,0.90,1.20,-0.30,0.50,0.52,0.20,1.00,1.00",
        ],
    )
    write_daily_returns_csv(
        report_root,
        [
            "2026-01-01,0.01,0.005",
            "2026-02-01,0.02,0.006",
            "2026-03-01,-0.01,-0.002",
            "2026-04-01,0.03,0.01",
            "2026-05-01,0.00,0.00",
            "2026-06-01,0.01,0.003",
        ],
        header=",ALPHA,BTC_BH__always_on",
    )
    write_equity_csv(
        report_root,
        [
            "2026-01-01,101000,100500",
            "2026-02-01,103020,101103",
            "2026-03-01,101989.8,100900.8",
            "2026-04-01,105049.49,101909.81",
            "2026-05-01,105049.49,101909.81",
            "2026-06-01,106099.98,102215.54",
        ],
        header=",ALPHA,BTC_BH__always_on",
    )


def _parse_utc_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _run_from_seed_row(row: dict[str, object]) -> Run:
    window = row["window"]
    assert isinstance(window, dict)
    return Run(
        run_id=str(row["run_id"]),
        strategy=str(row["strategy"]),
        strategy_family=str(row.get("strategy_family")) if row.get("strategy_family") is not None else None,
        universe=str(row["universe"]),
        window_start=date.fromisoformat(str(window["start"])),
        window_end=date.fromisoformat(str(window["end"])),
        status=str(row["status"]),
        return_pct=row.get("return_pct"),
        sharpe=row.get("sharpe"),
        max_dd=row.get("max_dd"),
        duration_s=row.get("duration_s"),
        eta_s=row.get("eta_s"),
        spark=json.dumps(row.get("spark") or []),
        created_at=_parse_utc_datetime(str(row["created_at"])),
        favorited=bool(row.get("favorited", False)),
    )


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for row in mock_data.fallback_runs_list:
            session.add(_run_from_seed_row(row))
        session.commit()
        yield session
        session.rollback()
    engine.dispose()


def make_summary_row(strategy: str, **overrides: object) -> str:
    values: dict[str, object] = {
        "strategy": strategy,
        "total_return": 0.20,
        "cagr": 0.10,
        "annualized_volatility": 0.20,
        "sharpe": 0.80,
        "sortino": 1.10,
        "max_drawdown": -0.30,
        "calmar": 0.33,
        "monthly_win_rate": 0.50,
        "annualized_turnover": 0.20,
        "avg_turnover_per_rebalance": 0.10,
        "average_holdings": 1,
    }
    values.update(overrides)
    return ",".join(str(values[field]) for field in SUMMARY_HEADER.split(","))


def make_rebalance_row(symbol: str, rebalance_date: str, rank: int, **overrides: object) -> str:
    values: dict[str, object] = {
        "coin_id": symbol.lower(),
        "price": 1,
        "market_cap": 1000,
        "volume_usd": 100,
        "history_days": 30,
        "symbol": symbol,
        "name": symbol,
        "sector": "Layer1",
        "rebalance_date": rebalance_date,
        "universe_rank": rank,
    }
    values.update(overrides)
    return ",".join(str(values[field]) for field in REBALANCE_HEADER.split(","))


def make_data_quality_row(
    symbol: str,
    validation_passed: bool,
    validation_reason: str,
    latest_overlap_date: str,
    latest_price_gap: float,
    price_correlation: float,
    included_in_panel: bool = True,
    **overrides: object,
) -> str:
    values: dict[str, object] = {
        "symbol": symbol,
        "validation_passed": validation_passed,
        "validation_reason": validation_reason,
        "latest_overlap_date": latest_overlap_date,
        "latest_price_gap": latest_price_gap,
        "median_price_gap": 0.001,
        "price_correlation": price_correlation,
        "included_in_panel": included_in_panel,
    }
    values.update(overrides)
    return ",".join(str(values[field]) for field in DATA_QUALITY_HEADER.split(","))
