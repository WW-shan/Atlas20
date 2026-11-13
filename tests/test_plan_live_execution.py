from __future__ import annotations

import pandas as pd
import pytest

from atlas20.derivatives.execution import (
    AccountState,
    ContractSpec,
    build_execution_plan,
)
from scripts import execute_live_plan
from scripts.plan_live_execution import format_execution_plan, load_symbol_map


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


def test_dry_run_plan_separates_live_fast_path_from_research_fill() -> None:
    plan = build_execution_plan(
        AccountState(equity=100.0, available_margin=100.0),
        {"near": 0.4},
        {"near": ContractSpec("NEARUSDT", min_order_qty=1.0, quantity_multiplier=1.0)},
        {"near": 5.0},
    )

    message = format_execution_plan(
        plan,
        signal_date=pd.Timestamp("2026-11-13", tz="UTC"),
        execution_hint=pd.Timestamp("2026-11-14 01:05", tz="UTC"),
        research_execution_hint=pd.Timestamp("2026-11-14 03:00", tz="UTC"),
    )

    assert "建议执行 2026-11-14 01:05 UTC / 北京 2026-11-14 09:05" in message
    assert "研究回测成交口径 2026-11-14 03:00 UTC / 北京 2026-11-14 11:00" in message


def test_execute_cli_defaults_to_the_ls45_short_stop() -> None:
    args = execute_live_plan.parse_args([])

    assert args.short_stop_loss_pct == 0.20


class _AccountClient:
    def __init__(self, assets: dict, positions: list[dict]):
        self._assets = assets
        self._positions = positions

    def account_assets(self) -> dict:
        return self._assets

    def current_positions(self, **kwargs) -> list[dict]:
        return self._positions


def test_load_symbol_map_drops_missing_contracts_and_alias_duplicates(tmp_path):
    path = tmp_path / "symbol_map.csv"
    path.write_text(
        "coin_id,bitget_symbol,contract_status,reason\n"
        "matic-network,POLUSDT,normal,alias:POL\n"
        "polygon-ecosystem-token,POLUSDT,normal,direct\n"
        "waves,,missing,no Bitget USDT-M perpetual\n"
        "near,NEARUSDT,normal,direct\n",
        encoding="utf-8",
    )

    assert load_symbol_map(path) == {
        "polygon-ecosystem-token": "POLUSDT",
        "near": "NEARUSDT",
    }


def test_account_equity_zero_does_not_fall_back_to_another_field():
    from scripts.plan_live_execution import account_state_from_bitget

    client = _AccountClient(
        assets={
            "usdtEquity": 0,
            "accountEquity": 100,
            "assets": [{"coin": "USDT", "available": "0"}],
        },
        positions=[],
    )

    account = account_state_from_bitget(client, {"near": "NEARUSDT"})

    assert account.equity == 0.0


def test_account_state_rejects_an_invalid_position_mark_price():
    import pytest

    from scripts.plan_live_execution import account_state_from_bitget

    client = _AccountClient(
        assets={"usdtEquity": "100", "assets": [{"coin": "USDT", "available": "25"}]},
        positions=[
            {
                "symbol": "NEARUSDT",
                "posSide": "long",
                "total": "10",
                "avgPrice": "5",
                "markPrice": "not-a-number",
                "positionBalance": "3",
            }
        ],
    )

    with pytest.raises(ValueError, match="markPrice"):
        account_state_from_bitget(client, {"near": "NEARUSDT"})


def test_account_state_rejects_an_unknown_position_side():
    from scripts.plan_live_execution import account_state_from_bitget

    client = _AccountClient(
        assets={"usdtEquity": "100", "assets": [{"coin": "USDT", "available": "25"}]},
        positions=[
            {
                "symbol": "NEARUSDT",
                "posSide": "long_typo",
                "total": "10",
                "avgPrice": "5",
                "markPrice": "5",
                "positionBalance": "3",
            }
        ],
    )

    with pytest.raises(ValueError, match="posSide"):
        account_state_from_bitget(client, {"near": "NEARUSDT"})


def test_target_gross_weight_uses_absolute_long_and_short_notionals():
    from scripts.plan_live_execution import target_gross_weight

    assert target_gross_weight({"near": 0.8, "tron": -0.45}) == pytest.approx(1.25)
    assert target_gross_weight({"near": 0.8, "tron": -0.5}) > 1.25
