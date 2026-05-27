from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pandas as pd
from sqlmodel import SQLModel, Session, create_engine, select
import yaml

from atlas20.api.db.models import ReportFile, Run
from atlas20.api.repositories import RunsRepo
from atlas20.api.schemas import BacktestConfig
from atlas20.api.settings import Settings
from atlas20.api.worker import run_one


SMALL_BACKTEST_CONFIG = {
    "preset": "base",
    "universe": {"topN": 5, "excludeStable": True, "excludeWrapped": True},
    "window": {"start": "2026-04-19", "end": "2026-05-18", "rebalance": "Weekly"},
    "allocation": {"positionPct": 25.0, "slots": 3},
    "costs": {"feeBps": 1.0, "slippageBps": 1.0},
}

ASSETS = [
    ("bitcoin", "BTC", "Bitcoin", "Store of Value", 100.0, 1_000_000_000.0, 1),
    ("ethereum", "ETH", "Ethereum", "Layer1", 50.0, 600_000_000.0, 2),
    ("solana", "SOL", "Solana", "Layer1", 25.0, 300_000_000.0, 3),
    ("cardano", "ADA", "Cardano", "Layer1", 10.0, 200_000_000.0, 4),
    ("chainlink", "LINK", "Chainlink", "Oracle", 15.0, 150_000_000.0, 5),
]


def _write_small_project_config(project_root: Path) -> None:
    config_dir = project_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    raw = yaml.safe_load(Path("config/base.yaml").read_text(encoding="utf-8"))
    raw["project_name"] = "Atlas20 Test Fixture"
    raw["paths"] = {"raw_dir": "data/raw", "processed_dir": "data/processed", "reports_dir": "reports/latest"}
    raw["universe"]["universe_size"] = 5
    raw["universe"]["current_top_n_candidates"] = 5
    raw["universe"]["legacy_candidate_ids"] = []
    raw["universe"]["min_history_days"] = 65
    raw["universe"]["min_daily_dollar_volume"] = 1
    raw["regime"]["btc_ma_window"] = 5
    raw["regime"]["tracked_total_mcap_ma_window"] = 5
    raw["regime"]["tracked_alt_mcap_momentum_window"] = 5
    raw["signals"]["momentum_windows"] = {"3": 0.5, "5": 0.3, "7": 0.2}
    raw["strategies"]["momentum_hold_counts"] = [2]
    raw["strategies"]["sector_top_k"] = [1]
    raw["strategies"]["sector_max_coins_per_sector"] = 2
    raw["strategies"]["include_bull_filter_variants"] = False
    raw["reporting"]["rolling_window_days"] = 7
    raw["reporting"]["selected_strategies_for_plots"] = [
        "BTC_BH__always_on",
        "ETH_BH__always_on",
        "TOP20_EQ__always_on",
        "TOP20_MOM_top2_weekly__always_on",
        "TOP20_SECTOR_top1_weekly__always_on",
    ]
    raw["data_quality"]["coingecko_recent_days"] = 120
    raw["data_quality"]["min_overlap_days"] = 5
    raw["data_quality"]["min_direct_market_cap_days"] = 5
    (config_dir / "base.yaml").write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    sectors = {
        "default_sector": "Other",
        "manual_overrides": {coin_id: sector for coin_id, _symbol, _name, sector, *_rest in ASSETS},
    }
    (config_dir / "sectors.yaml").write_text(yaml.safe_dump(sectors, sort_keys=False), encoding="utf-8")


def _write_small_raw_cache(project_root: Path) -> None:
    raw_dir = project_root / "data" / "raw"
    cg_dir = raw_dir / "coingecko"
    cc_dir = raw_dir / "cryptocompare" / "histoday"
    (cg_dir / "coin_metadata").mkdir(parents=True, exist_ok=True)
    (cg_dir / "market_chart").mkdir(parents=True, exist_ok=True)
    cc_dir.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2026-02-01", "2026-05-18", freq="D")

    candidates: list[dict[str, object]] = []
    for asset_index, (coin_id, symbol, name, sector, base_price, market_cap, rank) in enumerate(ASSETS, start=1):
        candidates.append(
            {
                "id": coin_id,
                "symbol": symbol.lower(),
                "name": name,
                "current_price": base_price,
                "market_cap": market_cap,
                "total_volume": 10_000_000.0,
                "market_cap_rank": rank,
                "circulating_supply": market_cap / base_price,
            }
        )
        cc_rows: list[dict[str, float | int]] = []
        prices: list[list[float | int]] = []
        market_caps: list[list[float | int]] = []
        volumes: list[list[float | int]] = []
        for day, ts in enumerate(dates):
            price = base_price * (1.0 + 0.002 * day + 0.0002 * asset_index * day)
            cap = market_cap * (price / base_price)
            volume = 5_000_000.0 + asset_index * 100_000.0
            seconds = int(ts.value // 1_000_000_000)
            millis = int(ts.value // 1_000_000)
            cc_rows.append({"time": seconds, "close": price, "volumeto": volume})
            prices.append([millis, price])
            market_caps.append([millis, cap])
            volumes.append([millis, volume])

        (cc_dir / f"{symbol}.json").write_text(
            json.dumps({"Response": "Success", "Data": {"Data": cc_rows}}),
            encoding="utf-8",
        )
        (cg_dir / "coin_metadata" / f"{coin_id}.json").write_text(
            json.dumps({"id": coin_id, "symbol": symbol.lower(), "name": name, "categories": [sector]}),
            encoding="utf-8",
        )
        (cg_dir / "market_chart" / f"{coin_id}_120d.json").write_text(
            json.dumps({"prices": prices, "market_caps": market_caps, "total_volumes": volumes}),
            encoding="utf-8",
        )

    (cg_dir / "candidate_assets.json").write_text(json.dumps(candidates), encoding="utf-8")


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        db_url=f"sqlite:///{(tmp_path / 'real-worker.sqlite').as_posix()}",
        report_root=tmp_path / "reports",
        data_root=tmp_path / "data",
        project_root=tmp_path,
        run_timeout_seconds=60,
        worker_poll_interval_seconds=0.01,
    )


def _create_engine(settings: Settings):
    engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def _create_run(engine) -> None:
    config = BacktestConfig.model_validate(SMALL_BACKTEST_CONFIG)
    with Session(engine) as session:
        session.add(
            Run(
                run_id="btk_0001",
                strategy=config.preset,
                strategy_family="Other",
                universe="Top-5",
                window_start=date(2026, 4, 19),
                window_end=date(2026, 5, 18),
                status="running",
                params=config.model_dump_json(),
            )
        )
        session.commit()


def test_run_one_real_small_window_writes_artifacts_and_db_rows(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS20_WORKER_MOCK", raising=False)
    _write_small_project_config(tmp_path)
    _write_small_raw_cache(tmp_path)
    settings = _settings(tmp_path)
    engine = _create_engine(settings)
    _create_run(engine)

    assert run_one.run("btk_0001", settings) == 0

    final_dir = settings.report_root / "app_runs" / "btk_0001"
    expected_artifacts = {
        "summary.csv",
        "strategy_summary.csv",
        "equity_curve.csv",
        "equity_curves.csv",
        "daily_returns.csv",
        "weights/BTC_BH__always_on.csv",
        "selection_history.csv",
        "manifest.json",
        "params.json",
        "atlas20_report.md",
    }
    assert expected_artifacts.issubset(
        {path.relative_to(final_dir).as_posix() for path in final_dir.rglob("*") if path.is_file()}
    )
    latest_path = settings.report_root / "latest"
    assert latest_path.exists()
    assert latest_path.resolve() == final_dir.resolve()
    summary = pd.read_csv(final_dir / "summary.csv")
    assert {"BTC_BH__always_on", "TOP20_EQ__always_on", "TOP20_MOM_top2_weekly__always_on"}.issubset(
        set(summary["strategy"])
    )
    selection_history = pd.read_csv(final_dir / "selection_history.csv")
    assert not selection_history.empty

    with Session(engine) as session:
        completed = RunsRepo(session).get("btk_0001")
        report_files = session.exec(select(ReportFile).where(ReportFile.run_id == "btk_0001")).all()
    assert completed is not None
    assert completed.status == "completed"
    assert completed.duration_s is not None
    assert completed.sharpe is not None
    assert {"markdown", "png", "csv", "bundle"}.issubset({row.kind for row in report_files})
