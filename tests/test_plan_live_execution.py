from __future__ import annotations

import pandas as pd

from atlas20.derivatives.execution import (
    AccountState,
    ContractSpec,
    build_execution_plan,
)
from scripts import execute_live_plan
from scripts.plan_live_execution import format_execution_plan


def test_dry_run_plan_displays_the_short_stop() -> None:
    plan = build_execution_plan(
        AccountState(equity=100.0, available_margin=100.0),
        {"near": -0.4},
        {"near": ContractSpec("NEARUSDT", min_order_qty=1.0, quantity_multiplier=1.0)},
        {"near": 5.0},
        short_stop_loss_pct=0.20,
    )

    message = format_execution_plan(
        plan,
        signal_date=pd.Timestamp("2026-11-13", tz="UTC"),
        execution_hint=pd.Timestamp("2026-11-14 03:00", tz="UTC"),
    )

    assert "止损 6" in message


def test_execute_cli_defaults_to_the_ls45_short_stop() -> None:
    args = execute_live_plan.parse_args([])

    assert args.short_stop_loss_pct == 0.20
