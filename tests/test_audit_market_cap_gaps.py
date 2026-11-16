from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts import audit_market_cap_gaps


def _write_raw(
    directory: Path,
    *,
    cmc_id: int,
    date: str,
    market_cap: float,
    supply: float,
) -> None:
    start = int(pd.Timestamp(date, tz="UTC").timestamp())
    end = int((pd.Timestamp(date, tz="UTC") + pd.Timedelta(days=1)).timestamp())
    path = directory / f"{cmc_id}_{start}_{end}.json"
    path.write_text(
        json.dumps(
            [
                {
                    "timeOpen": f"{date}T00:00:00.000Z",
                    "timeClose": f"{date}T23:59:59.999Z",
                    "quote": {
                        "close": 2.5,
                        "marketCap": market_cap,
                        "circulatingSupply": supply,
                    },
                }
            ]
        ),
        encoding="utf-8",
    )


def _panel(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_market_cap_gap_evidence_accepts_provider_zero_supply(tmp_path: Path) -> None:
    history = tmp_path / "history"
    history.mkdir()
    _write_raw(history, cmc_id=6535, date="2021-01-20", market_cap=0.0, supply=0.0)
    panel = _panel(
        [
            {"date": "2021-01-20", "coin_id": "near", "symbol": "NEAR", "market_cap": float("nan")},
            {"date": "2021-01-21", "coin_id": "near", "symbol": "NEAR", "market_cap": 100.0},
        ]
    )

    evidence, summary = audit_market_cap_gaps.build_market_cap_gap_evidence(
        panel,
        history_dir=history,
        cmc_ids={"NEAR": 6535},
    )

    assert len(evidence) == 1
    assert evidence.iloc[0]["status"] == "provider_zero_supply"
    assert evidence.iloc[0]["raw_market_cap"] == 0.0
    assert evidence.iloc[0]["raw_circulating_supply"] == 0.0
    assert summary["passed"] is True
    assert summary["unexplained_rows"] == 0
    assert summary["latest_rows_valid"] is True


def test_market_cap_gap_evidence_fails_when_provider_has_a_real_cap(tmp_path: Path) -> None:
    history = tmp_path / "history"
    history.mkdir()
    _write_raw(history, cmc_id=6535, date="2021-01-20", market_cap=123.0, supply=50.0)
    panel = _panel(
        [
            {"date": "2021-01-20", "coin_id": "near", "symbol": "NEAR", "market_cap": float("nan")},
            {"date": "2021-01-21", "coin_id": "near", "symbol": "NEAR", "market_cap": 100.0},
        ]
    )

    evidence, summary = audit_market_cap_gaps.build_market_cap_gap_evidence(
        panel,
        history_dir=history,
        cmc_ids={"NEAR": 6535},
    )

    assert evidence.iloc[0]["status"] == "unexpected_missing_cap"
    assert summary["passed"] is False
    assert summary["unexplained_rows"] == 1


def test_market_cap_gap_evidence_checks_current_rows_not_a_delisted_last_row(
    tmp_path: Path,
) -> None:
    history = tmp_path / "history"
    history.mkdir()
    _write_raw(history, cmc_id=6535, date="2021-01-20", market_cap=0.0, supply=0.0)
    panel = _panel(
        [
            {"date": "2021-01-20", "coin_id": "near", "symbol": "NEAR", "market_cap": float("nan")},
            {"date": "2021-01-21", "coin_id": "bitcoin", "symbol": "BTC", "market_cap": 100.0},
        ]
    )

    _, summary = audit_market_cap_gaps.build_market_cap_gap_evidence(
        panel,
        history_dir=history,
        cmc_ids={"NEAR": 6535, "BTC": 1},
    )

    assert summary["latest_panel_rows_valid"] is True
    assert summary["affected_assets_current_valid"] is True
    assert summary["affected_assets_last_observed_valid"] is False
