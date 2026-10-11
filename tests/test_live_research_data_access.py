from __future__ import annotations

import json
from pathlib import Path

from atlas20.api.data_access.live import load_live_research
from atlas20.api.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(env="test", report_root=tmp_path)


def _write_spot(root: Path) -> None:
    live = root / "phase_momentum_live"
    live.mkdir(parents=True)
    (live / "latest_signal.json").write_text(
        json.dumps(
            {
                "trial_id": "PR2026-10-H5",
                "as_of": "2026-10-08",
                "panel_last_date": "2026-10-08",
                "next_check_date": "2026-10-09",
                "latest_target_date": "2026-10-08",
                "gross_exposure": 0.6214,
                "current_gross_exposure": 0.4605,
                "current_weights": {"near": 0.4605},
                "targets": {"near": 0.6214},
                "btc_gate_open": True,
                "trade_required": True,
                "cost_bps": 20.0,
                "rule": "strict PIT Top20",
                "last_day_check": {
                    "complete": True,
                    "date": "2026-10-08",
                    "market_cap_coverage": 1.0,
                    "median_volume_ratio": 1.2,
                    "volume_floor": 0.6,
                    "reasons": [],
                },
            }
        ),
        encoding="utf-8",
    )


def _write_oos(root: Path) -> None:
    oos = root / "phase_momentum_oos_2026"
    oos.mkdir()
    (oos / "manifest.json").write_text(
        json.dumps(
            {
                "trial_id": "PR2026-10-H5",
                "oos_start": "2026-09-22",
                "oos_end": "2026-10-08",
                "oos_days": 17,
            }
        ),
        encoding="utf-8",
    )
    (oos / "oos_summary.csv").write_text(
        "fill_policy,cost_bps,start,end,days,multiple,cagr,sharpe,max_drawdown\n"
        "close,20.0,2026-09-22,2026-10-08,17,0.9677,-0.5277,-0.9481,-0.0883\n"
        "close,100.0,2026-09-22,2026-10-08,17,0.9624,-0.5829,-1.1590,-0.0923\n",
        encoding="utf-8",
    )
    (oos / "benchmark.csv").write_text(
        "fill_policy,cost_bps,start,end,days,multiple,cagr,sharpe,max_drawdown\n"
        "btc_close,0.0,2026-09-22,2026-10-08,17,0.9431,-0.7371,-5.5871,-0.0569\n",
        encoding="utf-8",
    )


def _write_frozen(root: Path) -> None:
    frozen = root / "phase_momentum_candidate_eval_h5"
    frozen.mkdir()
    (frozen / "decision_table.csv").write_text(
        "trial_id,fill_hours,worse_policy,multiple,sharpe,max_drawdown,rolling_1y_worst,best_year_removed,turnover_annual,avg_gross_exposure,observed_weight_share\n"
        "PR2026-10-H5,1,h1_day_close,22.8004,1.7036,-0.3327,0.8242,7.1138,24.8467,0.2613,0.9378\n"
        "PR2026-10-H5,3,h3_day_close,19.5253,1.6231,-0.3697,0.8063,6.5123,24.8447,0.2613,0.9378\n",
        encoding="utf-8",
    )
    (frozen / "deflated_sharpe.csv").write_text(
        "index,trial_id,fill,fill_hours,deflated_sharpe_probability,observed_sharpe,expected_max_sharpe,n_trials\n"
        "9,PR2026-10-H5,h1_day_close,1.0,0.9006,1.7031,1.1797,6135.0\n"
        "11,PR2026-10-H5,h3_day_close,3.0,0.8598,1.6227,1.1797,6135.0\n",
        encoding="utf-8",
    )


def test_load_live_research_reads_current_spot_and_oos(tmp_path: Path) -> None:
    _write_spot(tmp_path)
    _write_oos(tmp_path)
    _write_frozen(tmp_path)

    payload = load_live_research(_settings(tmp_path))

    assert payload["spot"] is not None
    assert payload["spot"]["trial_id"] == "PR2026-10-H5"
    assert payload["spot"]["signal_date"] == "2026-10-08"
    assert payload["spot"]["weights"] == [
        {"asset": "near", "target": 0.6214, "current": 0.4605}
    ]
    assert payload["spot"]["frozen"][0]["multiple"] == 22.8004
    assert payload["spot"]["frozen"][0]["deflated_sharpe_probability"] == 0.9006

    assert payload["oos"] is not None
    assert payload["oos"]["start"] == "2026-09-22"
    assert payload["oos"]["end"] == "2026-10-08"
    assert payload["oos"]["days"] == 17
    assert payload["oos"]["multiple"] == 0.9677
    assert payload["oos"]["benchmark_multiple"] == 0.9431
    assert [row["cost_bps"] for row in payload["oos"]["stress"]] == [20.0, 100.0]


def _write_derivatives(root: Path) -> None:
    execution = root / "derivatives_track_execution"
    execution.mkdir()
    (execution / "latest.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "signal_date": "2026-10-08",
                "execution_hint": "2026-10-09 03:00:00+00:00",
                "spec": "PR2026-10-D-L125-V2",
                "plan": {
                    "equity": 99.97,
                    "expected_gross_notional": 75.13,
                    "leverage": 2.0,
                },
                "report": {
                    "equity_before": 99.97,
                    "equity_after": 99.97,
                    "balance_after": 99.87,
                    "position_value": 75.13,
                    "traded": False,
                    "margin_mode": "crossed",
                    "failures": [],
                    "margin_notes": ["crossed position"],
                },
            }
        ),
        encoding="utf-8",
    )

    live = root / "derivatives_track_live"
    live.mkdir()
    (live / "health.json").write_text(
        json.dumps(
            {
                "audit_exit": 0,
                "issues": [],
                "checked_at": "2026-10-10T21:58:25Z",
            }
        ),
        encoding="utf-8",
    )
    (live / "audit.json").write_text(
        json.dumps(
            {
                "checked_at": "2026-10-10T20:59:44Z",
                "equity": 99.95,
                "position_value": 75.11,
                "signal_date": "2026-10-08",
                "spec": "PR2026-10-D-L125-V2",
                "hard_failures": 0,
                "checks": [
                    {
                        "check": "gross cap",
                        "detail": "0.751x",
                        "hard": True,
                        "ok": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (live / "signal_equivalence.json").write_text(
        json.dumps(
            {
                "passed": True,
                "checked_at": "2026-10-10T20:58:46Z",
                "backtest_end": "2026-09-21",
                "live_end": "2026-10-09",
                "differing_event_days": 0,
                "differences": [],
                "events_only_in_backtest": [],
                "events_only_in_live": ["2026-10-08"],
                "overlapping_event_days": 599,
                "spec": "PR2026-10-D-L125-V2",
                "trial_id_backtest": "PR2026-10-H5",
                "trial_id_live": "PR2026-10-H5",
            }
        ),
        encoding="utf-8",
    )
    (live / "journal.csv").write_text(
        "date,run_at_utc,signal_date,equity,position_value,cash,day_pnl,day_return,fees_today,funding_total,unrealised_pnl,positions,trades,notes\n"
        f'2026-10-10,2026-10-10T21:02:07Z,2026-10-08,99.974147,75.131,99.871947,,,0,0.0,0.1008,{json.dumps([{"asset": "near"}])},[],[]\n',
        encoding="utf-8",
    )


def test_load_live_research_reads_derivatives_and_journal(tmp_path: Path) -> None:
    _write_derivatives(tmp_path)

    payload = load_live_research(_settings(tmp_path))

    assert payload["derivatives"] is not None
    assert payload["derivatives"]["health"]["status"] == "healthy"
    assert payload["derivatives"]["health"]["hard_failures"] == 0
    assert payload["derivatives"]["health"]["checks"][0]["check"] == "gross cap"
    assert payload["derivatives"]["equivalence"]["passed"] is True
    assert payload["derivatives"]["execution"]["equity_after"] == 99.97
    assert payload["derivatives"]["journal"][0]["date"] == "2026-10-10"
    assert payload["derivatives"]["journal"][0]["positions"] == 1
    assert payload["derivatives"]["journal"][0]["notes"] == []


def test_load_live_research_reports_missing_artifacts_without_fabricating_data(tmp_path: Path) -> None:
    payload = load_live_research(_settings(tmp_path))

    assert payload["spot"] is None
    assert payload["oos"] is None
    assert payload["derivatives"] is None
    unavailable = {row["id"] for row in payload["artifacts"] if not row["available"]}
    assert {
        "spot_signal",
        "frozen_decision",
        "oos_summary",
        "derivatives_execution",
        "derivatives_health",
    } <= unavailable
