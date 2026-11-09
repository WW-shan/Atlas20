from __future__ import annotations

from pathlib import Path

import pytest

from atlas20.derivatives.live_journal import load_capital_flows
from scripts.record_capital_flow import main


def test_record_capital_flow_cli_appends_a_deposit(tmp_path: Path) -> None:
    path = tmp_path / "capital_flows.csv"

    exit_code = main(
        [
            "--amount",
            "400",
            "--timestamp-utc",
            "2026-11-04T11:17:00+00:00",
            "--note",
            "用户报告入金；精确到账时间未取得",
            "--file",
            str(path),
        ]
    )

    assert exit_code == 0
    frame = load_capital_flows(path)
    assert frame.iloc[0]["amount_usdt"] == pytest.approx(400.0)
    assert str(frame.iloc[0]["timestamp_utc"]) == "2026-11-04 11:17:00+00:00"


@pytest.mark.parametrize(
    ("amount", "timestamp"),
    [
        ("nan", "2026-11-04"),
        ("inf", "2026-11-04"),
        ("-inf", "2026-11-04"),
        ("100", "NaT"),
    ],
)
def test_record_capital_flow_cli_rejects_invalid_values(
    tmp_path: Path,
    amount: str,
    timestamp: str,
) -> None:
    path = tmp_path / "capital_flows.csv"

    with pytest.raises(SystemExit) as error:
        main([f"--amount={amount}", "--timestamp-utc", timestamp, "--file", str(path)])

    assert error.value.code == 2
    assert not path.exists()
