from pathlib import Path

from atlas20.api.services import (
    load_champion_summary,
    load_selection_history,
    load_time_series,
    load_top_strategies,
)


REPORT_DIR = Path("reports/bear_bottom_to_current_2022_11_21_2026_04_22")
CHAMPION_DIR = REPORT_DIR / "profit_max_refine" / "champion_all_1m_14d_stop11_confirm2"


def test_load_champion_summary_reads_profit_max_artifact():
    summary = load_champion_summary(CHAMPION_DIR)

    assert summary.strategy == "MOMENTUM_LEAD_TOP1_ALL_14D_STOP11_CONFIRM2_BTC_PARK"
    assert summary.multiple > 200
    assert summary.rebalance_frequency == "14D"
    assert summary.btc_stop_lookback_days == 11


def test_load_top_strategies_from_strategy_summary():
    rows = load_top_strategies(REPORT_DIR, limit=5)

    assert len(rows) == 5
    assert rows[0].strategy
    assert rows[0].multiple > 1


def test_load_time_series_returns_date_value_points():
    rows = load_time_series(CHAMPION_DIR / "equity_curve.csv", "equity", limit=3)

    assert len(rows) == 3
    assert rows[0].date == "2022-11-21"
    assert rows[0].value == 100000.0


def test_load_selection_history_limits_rows():
    rows = load_selection_history(CHAMPION_DIR / "selection_history.csv", limit=2)

    assert len(rows) == 2
    assert rows[0].coin_rank == 1
    assert rows[0].coin_weight == 1.0
