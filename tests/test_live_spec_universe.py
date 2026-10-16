"""A "go to cash" book must still be able to close the held leg.

Venue specs used to be resolved from today's target set alone.  When the
frozen book said "exit everything" the target set was empty, so the held leg
had no contract and ``build_execution_plan`` raised ``KeyError: 'near'``.  The
2026-10-13 live run died exactly that way and the position stayed open, which
is the one case where the exit matters most.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas20.derivatives.execution import (
    AccountState,
    PositionState,
    build_execution_plan,
)
from scripts.plan_live_execution import spec_symbol_universe, specs_from_instruments

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INSTRUMENTS = [
    {
        "symbol": "NEARUSDT",
        "minOrderQty": "1",
        "quantityMultiplier": "1",
        "minOrderAmount": "5",
        "quantityPrecision": "0",
    }
]
SYMBOL_MAP = {"near": "NEARUSDT"}


def _held_account() -> AccountState:
    return AccountState(
        equity=100.0,
        available_margin=50.0,
        positions={
            "near": PositionState(
                asset="near",
                symbol="NEARUSDT",
                side="long",
                size=14.0,
                entry_price=5.27,
                mark_price=5.30,
                margin=37.0,
            )
        },
    )


def test_spec_universe_covers_the_map_even_with_an_empty_target_book() -> None:
    assert spec_symbol_universe(SYMBOL_MAP, [])["near"] == "NEARUSDT"


def test_spec_universe_falls_back_for_unmapped_targets() -> None:
    assert spec_symbol_universe(SYMBOL_MAP, ["bitway"])["bitway"] == "BITWAYUSDT"


def test_spec_universe_does_not_mutate_the_caller_map() -> None:
    source = {"near": "NEARUSDT"}
    spec_symbol_universe(source, ["bitway"])
    assert source == {"near": "NEARUSDT"}


def test_empty_target_book_closes_the_held_leg() -> None:
    specs = specs_from_instruments(INSTRUMENTS, spec_symbol_universe(SYMBOL_MAP, []))
    plan = build_execution_plan(_held_account(), {}, specs, {"near": 5.30})

    assert [order.action for order in plan.orders] == ["CLOSE"]
    assert plan.orders[0].asset == "near"


def test_target_only_specs_still_crash_the_close() -> None:
    """The 2026-10-13 failure, pinned: no contract for the held leg."""

    with pytest.raises(KeyError):
        build_execution_plan(_held_account(), {}, {}, {"near": 5.30})


@pytest.mark.parametrize(
    "script",
    [
        "execute_live_plan.py",
        "plan_live_execution.py",
        "audit_live_track.py",
        "monitor_live_track.py",
    ],
)
def test_every_live_script_resolves_the_full_spec_universe(script: str) -> None:
    source = (PROJECT_ROOT / "scripts" / script).read_text(encoding="utf-8")

    assert "spec_symbol_universe" in source, f"{script} must resolve specs for held legs too"
