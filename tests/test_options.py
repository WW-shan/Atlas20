from __future__ import annotations

import pytest

from atlas20.api.data_access.options import load_options_from_reports
from atlas20.api.settings import Settings
from tests.conftest import make_rebalance_row, write_rebalance_csv, write_summary_csv


def test_load_options_payload_from_real_data(tmp_path):
    write_summary_csv(
        tmp_path / "reports",
        [
            "LOW_SHARPE,0.20,0.10,0.20,0.80,1.10,-0.30,0.33,0.50,0.20,0.10,1",
            "HIGH_SHARPE,0.70,0.30,0.20,2.40,3.00,-0.12,2.50,0.65,3.00,0.35,20",
            "MID_SHARPE,0.55,0.25,0.22,1.90,2.50,-0.15,1.66,0.58,2.50,0.30,20",
        ],
    )
    write_rebalance_csv(
        tmp_path / "data",
        [
            make_rebalance_row("BTC", "2026-05-11", 1, coin_id="btc", sector="Layer1"),
            make_rebalance_row("ETH", "2026-05-18", 1, coin_id="eth", sector="Layer1"),
            make_rebalance_row("AAVE", "2026-05-18", 2, coin_id="aave", sector="DeFi"),
            make_rebalance_row("UNI", "2026-05-18", 3, coin_id="uni", sector="DeFi"),
        ],
    )

    payload = load_options_from_reports(Settings(report_root=tmp_path / "reports", data_root=tmp_path / "data"))

    assert payload["presets"] == ["HIGH_SHARPE", "MID_SHARPE", "LOW_SHARPE"]
    assert payload["strategies"] == ["LOW_SHARPE", "HIGH_SHARPE", "MID_SHARPE"]
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
    write_summary_csv(
        tmp_path / "reports",
        [
            "BAD,0.20,0.10,0.20,nan,1.10,-0.30,0.33,0.50,0.20,0.10,1",
        ],
    )
    write_rebalance_csv(
        tmp_path / "data",
        [
            make_rebalance_row("BTC", "2026-05-18", 1, coin_id="btc", sector="Layer1"),
        ],
    )

    with pytest.raises(ValueError):
        load_options_from_reports(Settings(report_root=tmp_path / "reports", data_root=tmp_path / "data"))
