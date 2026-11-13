from __future__ import annotations

import pandas as pd
import pytest


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2025-01-01T03:00:00Z",
                    "2025-01-02T03:00:00Z",
                    "2025-02-01T03:00:00Z",
                ]
            ),
            "date": ["2025-01-01", "2025-01-02", "2025-02-01"],
            "asset": ["alpha", "beta", "alpha"],
            "exec_side": ["buy", "sell", "buy"],
            "position_side": ["long", "long", "short"],
            "action": ["open", "close", "close"],
            "requested_notional": [100.0, 200.0, 50.0],
            "haircut_025_maker_filled_notional": [25.0, 180.0, 40.0],
            "haircut_025_taker_filled_notional": [75.0, 20.0, 10.0],
            "haircut_025_effective_cost_bps": [30.0, 2.0, 5.0],
            "haircut_025_improvement_bps": [-10.0, 18.0, 15.0],
            "haircut_025_guard_triggered": [False, False, False],
            "haircut_025_status": ["timeout", "filled", "filled"],
        }
    )


def test_apply_taker_route_only_overrides_long_open_legs() -> None:
    from scripts.analyze_bitget_maker_routing import apply_taker_route

    routed = apply_taker_route(
        _events(),
        haircut=0.25,
        route_position_side="long",
        route_action="open",
        baseline_cost_bps=20.0,
    )

    assert routed["taker_routed"].tolist() == [True, False, False]
    assert routed["routed_effective_cost_bps"].tolist() == [20.0, 2.0, 5.0]
    assert routed["routed_improvement_bps"].tolist() == [0.0, 18.0, 15.0]
    assert routed["routed_maker_filled_notional"].tolist() == [0.0, 180.0, 40.0]
    assert routed["routed_taker_filled_notional"].tolist() == [100.0, 20.0, 10.0]
    assert routed["routed_status"].tolist() == ["taker_route", "filled", "filled"]


def test_routing_acceptance_requires_independent_route_benefit_and_breadth() -> None:
    from scripts.analyze_bitget_maker_routing import routing_acceptance

    passing = routing_acceptance(
        covered_events=400,
        notional_coverage=0.9,
        baseline_improvement_bps=6.0,
        long_open_baseline_improvement_bps=-2.0,
        routed_improvement_bps=7.0,
        routed_minus_baseline_bps=1.0,
        months=10,
        months_ge_5bps=8,
        ex_top_asset_improvement_bps=6.5,
    )
    assert all(passing.values())

    failing = routing_acceptance(
        covered_events=400,
        notional_coverage=0.9,
        baseline_improvement_bps=6.0,
        long_open_baseline_improvement_bps=1.0,
        routed_improvement_bps=5.2,
        routed_minus_baseline_bps=0.1,
        months=10,
        months_ge_5bps=6,
        ex_top_asset_improvement_bps=4.9,
    )
    assert not failing["long_open_baseline_not_profitable"]
    assert not failing["routed_gain_ge_0_5bps"]
    assert not failing["month_breadth_ge_70pct"]
    assert not failing["ex_top_asset_ge_5bps"]


def test_routing_summary_reports_baseline_and_routed_costs() -> None:
    from scripts.analyze_bitget_maker_routing import apply_taker_route, routing_summary

    routed = apply_taker_route(
        _events(),
        haircut=0.25,
        route_position_side="long",
        route_action="open",
        baseline_cost_bps=20.0,
    )

    summary = routing_summary(routed)

    assert set(summary["policy"]) == {"baseline_maker_25pct", "long_open_taker"}
    baseline = summary.set_index("policy").loc["baseline_maker_25pct"]
    policy = summary.set_index("policy").loc["long_open_taker"]
    assert baseline["events"] == 3
    assert policy["routed_notional_share"] == pytest.approx(100.0 / 350.0)
    assert policy["improvement_bps"] > baseline["improvement_bps"]
