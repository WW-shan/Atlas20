from __future__ import annotations

import pandas as pd
import pytest

from scripts.audit_signal_equivalence import _compare_target_ledgers


def _ledger(weight: float = -0.25) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "signal_date": "2026-11-06 00:00:00+00:00",
                "execution_hint": "2026-11-07 03:00:00+00:00",
                "asset": "ethereum",
                "side": "short",
                "target_weight": weight,
                "change_weight": weight,
                "action": "OPEN",
            }
        ]
    )


def test_signal_equivalence_accepts_an_identical_signed_ledger() -> None:
    result = _compare_target_ledgers(_ledger(), _ledger())

    assert result["passed"] is True
    assert result["differing_rows"] == 0
    assert result["events_only_in_frozen"] == []
    assert result["events_only_in_replay"] == []


def test_signal_equivalence_rejects_a_changed_short_weight() -> None:
    result = _compare_target_ledgers(_ledger(), _ledger(-0.20))

    assert result["passed"] is False
    assert result["differing_rows"] == 1
    assert result["differences"][0]["asset"] == "ethereum"
    assert result["differences"][0]["max_weight_delta"] == pytest.approx(0.05)
