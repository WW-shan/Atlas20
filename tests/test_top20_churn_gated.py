from __future__ import annotations

import pandas as pd
import pytest


def test_gated_targets_skip_events_when_gate_is_false(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import scripts.run_top20_churn_gated as module

    index = pd.date_range("2022-01-01", periods=4, freq="D", tz="UTC")
    present = pd.DataFrame(True, index=index, columns=["a", "b"])
    events = pd.DataFrame(
        [
            {"coin_id": "a", "event_date": index[1], "event_type": "entry", "confirmation_days": 7},
            {"coin_id": "b", "event_date": index[2], "event_type": "exit", "confirmation_days": 7},
        ]
    )
    monkeypatch.setattr(module, "detect_membership_events", lambda *_args, **_kwargs: events)

    gate = pd.Series(False, index=index)
    gate.loc[index[2]] = True
    targets = module.build_gated_targets(present=present, gate=gate, assets=["a", "b"])

    assert targets.loc[index[1]].abs().sum() == pytest.approx(0.0)
    assert targets.loc[index[2], "bitcoin"] == pytest.approx(0.5)
    assert targets.loc[index[2], "b"] == pytest.approx(-0.5)
    assert targets.loc[index[2]].sum() == pytest.approx(0.0)


def test_gate_series_has_frozen_names_and_boolean_values() -> None:
    from scripts.run_top20_churn_gated import build_gate_series

    index = pd.date_range("2020-01-01", periods=260, freq="D", tz="UTC")
    price = pd.DataFrame({"bitcoin": 100.0}, index=index)
    returns = pd.DataFrame({"bitcoin": 0.0, "a": 0.01}, index=index)
    present = pd.DataFrame(True, index=index, columns=["bitcoin", "a"])

    gates = build_gate_series(price=price, returns=returns, present=present, assets=["a"])

    assert set(gates) == {"alt_rel_60", "btc_ma200", "both"}
    assert all(gates[name].dtype == bool for name in gates)
