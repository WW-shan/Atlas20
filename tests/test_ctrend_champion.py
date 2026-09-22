from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from atlas20.config import load_config
from scripts.run_ctrend_champion import _latest_signal_payload


def test_latest_signal_uses_latest_data_date_and_latest_target() -> None:
    index = pd.date_range("2024-01-01", periods=15, freq="D")
    market = SimpleNamespace(price=pd.DataFrame({"bitcoin": range(15)}, index=index))
    targets = {
        pd.Timestamp("2024-01-01"): pd.Series({"bitcoin": 1.0}),
        pd.Timestamp("2024-01-10"): pd.Series(dtype=float),
    }
    risk_on = pd.Series(True, index=index)
    config = load_config("config/base.yaml")
    config.start_date = "2024-01-01"

    payload = _latest_signal_payload(targets, risk_on, market, config)

    assert payload["as_of"] == "2024-01-15"
    assert payload["latest_target_date"] == "2024-01-10"
    assert payload["btc_gate_open"] is True
    assert payload["targets"] == {}
    assert payload["gross_exposure"] == 0.0
    assert payload["next_scheduled_rebalance"] == "2024-01-22"
