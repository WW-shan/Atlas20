from __future__ import annotations

import pytest

from atlas20.api.data_access.options import load_options_from_reports
from atlas20.api.settings import Settings


SUMMARY_HEADER = (
    "strategy,total_return,cagr,annualized_volatility,sharpe,sortino,max_drawdown,"
    "calmar,monthly_win_rate,annualized_turnover,avg_turnover_per_rebalance,average_holdings"
)
REBALANCE_HEADER = (
    "coin_id,price,market_cap,volume_usd,history_days,symbol,name,sector,"
    "rebalance_date,universe_rank"
)


def test_load_options_payload_from_real_data(tmp_path):
    latest = tmp_path / "reports" / "latest"
    latest.mkdir(parents=True)
    latest.joinpath("strategy_summary.csv").write_text(
        "\n".join(
            [
                SUMMARY_HEADER,
                "LOW_SHARPE,0.20,0.10,0.20,0.80,1.10,-0.30,0.33,0.50,0.20,0.10,1",
                "HIGH_SHARPE,0.70,0.30,0.20,2.40,3.00,-0.12,2.50,0.65,3.00,0.35,20",
                "MID_SHARPE,0.55,0.25,0.22,1.90,2.50,-0.15,1.66,0.58,2.50,0.30,20",
            ]
        ),
        encoding="utf-8",
    )
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    processed.joinpath("rebalance_universe.csv").write_text(
        "\n".join(
            [
                REBALANCE_HEADER,
                "btc,1,1000,100,30,BTC,BTC,Layer1,2026-05-11,1",
                "eth,1,1000,100,30,ETH,ETH,Layer1,2026-05-18,1",
                "aave,1,1000,100,30,AAVE,AAVE,DeFi,2026-05-18,2",
                "uni,1,1000,100,30,UNI,UNI,DeFi,2026-05-18,3",
            ]
        ),
        encoding="utf-8",
    )

    payload = load_options_from_reports(Settings(report_root=tmp_path / "reports", data_root=tmp_path / "data"))

    assert payload["presets"] == ["HIGH_SHARPE", "MID_SHARPE", "LOW_SHARPE"]
    assert payload["universes"] == [
        {"topN": 5, "label": "Top 5"},
        {"topN": 10, "label": "Top 10"},
        {"topN": 20, "label": "Top 20"},
    ]
    assert payload["rebalances"] == [
        {"value": "Weekly", "label": "Weekly"},
        {"value": "Biweekly", "label": "Biweekly"},
        {"value": "Monthly", "label": "Monthly"},
    ]
    assert payload["feeBpsRange"] == [0.0, 10.0, 50.0]
    assert payload["slippageBpsRange"] == [0.0, 5.0, 25.0]
    assert payload["sectors"] == ["DeFi", "Layer1"]


def test_load_options_rejects_nan_sharpe(tmp_path):
    latest = tmp_path / "reports" / "latest"
    latest.mkdir(parents=True)
    latest.joinpath("strategy_summary.csv").write_text(
        "\n".join(
            [
                SUMMARY_HEADER,
                "BAD,0.20,0.10,0.20,nan,1.10,-0.30,0.33,0.50,0.20,0.10,1",
            ]
        ),
        encoding="utf-8",
    )
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    processed.joinpath("rebalance_universe.csv").write_text(
        "\n".join(
            [
                REBALANCE_HEADER,
                "btc,1,1000,100,30,BTC,BTC,Layer1,2026-05-18,1",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_options_from_reports(Settings(report_root=tmp_path / "reports", data_root=tmp_path / "data"))
