"""Regression tests for build_markdown_report graceful benchmark fallback."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from atlas20.api.config_adapter import to_research_config
from atlas20.api.schemas import BacktestConfig
from atlas20.api.settings import Settings
from atlas20.reporting.report import build_markdown_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _config() -> "object":
    api_config = BacktestConfig.model_validate(
        {
            "preset": "ATLAS Adaptive v3",
            "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
            "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
            "allocation": {"positionPct": 5.0, "slots": 10},
            "costs": {"feeBps": 10, "slippageBps": 5},
        }
    )
    return to_research_config(api_config, api_config.preset, Settings(project_root=PROJECT_ROOT))


_SUMMARY_COLUMNS = [
    "cagr",
    "annualized_volatility",
    "sharpe",
    "sortino",
    "max_drawdown",
    "calmar",
    "annualized_turnover",
    "average_holdings",
]


def _summary_row(values: dict[str, float]) -> dict[str, float]:
    base = {col: 0.0 for col in _SUMMARY_COLUMNS}
    base.update(values)
    return base


def _yearly() -> pd.DataFrame:
    return pd.DataFrame(
        {"TOP20_MOM_alpha": [0.08, 0.20]},
        index=pd.Index([2025, 2026], name="year"),
    )


def _regime() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"strategy": "TOP20_MOM_alpha", "regime": "bull", "annualized_return": 0.20},
        ]
    )


def test_build_markdown_report_renders_na_when_benchmarks_absent(tmp_path: Path) -> None:
    """Custom backtest without BTC_BH/TOP20_EQ benchmarks must still render report,
    not raise KeyError → 500. Missing benchmarks become 'N/A' literals; verdicts
    that depend on a benchmark explain why they cannot be decided."""
    summary = pd.DataFrame(
        {
            "TOP20_MOM_alpha": _summary_row({"cagr": 0.25, "sharpe": 1.5, "max_drawdown": -0.20}),
            "TOP20_SECTOR_beta": _summary_row({"cagr": 0.22, "sharpe": 1.3, "max_drawdown": -0.22}),
        }
    ).T
    summary.index.name = "strategy"

    output = tmp_path / "digest.md"
    text = build_markdown_report(_config(), summary, _yearly(), _regime(), output)

    assert output.exists()
    assert "BTC benchmark CAGR: **N/A**" in text
    assert "Equal-weight benchmark CAGR: **N/A**" in text
    assert "N/A — no BTC benchmark in this run" in text
    assert "N/A — no equal-weight benchmark in this run" in text
    # Verdicts decided locally (regime/bull comparison) still render normally
    assert "Average bull-only Sharpe:" in text


def test_build_markdown_report_preserves_benchmark_output_when_present(tmp_path: Path) -> None:
    """Sanity: when benchmarks ARE present, output keeps the original semantics."""
    summary = pd.DataFrame(
        {
            "BTC_BH__always_on": _summary_row({"cagr": 0.10, "sharpe": 0.80, "max_drawdown": -0.30}),
            "TOP20_EQ__always_on": _summary_row({"cagr": 0.15, "sharpe": 1.00, "max_drawdown": -0.25}),
            "TOP20_MOM_alpha": _summary_row({"cagr": 0.25, "sharpe": 1.5, "max_drawdown": -0.20}),
            "TOP20_SECTOR_beta": _summary_row({"cagr": 0.22, "sharpe": 1.3, "max_drawdown": -0.22}),
        }
    ).T
    summary.index.name = "strategy"

    output = tmp_path / "digest.md"
    text = build_markdown_report(_config(), summary, _yearly(), _regime(), output)

    assert "BTC benchmark CAGR: **10.00%**" in text
    assert "Equal-weight benchmark CAGR: **15.00%**" in text
    assert "N/A — no BTC benchmark in this run" not in text
    assert "N/A — no equal-weight benchmark in this run" not in text


def test_build_markdown_report_scope_uses_chosen_cadence_not_hardcoded_text(tmp_path: Path) -> None:
    """Report scope line used to be hardcoded "monthly and biweekly". Once
    config_adapter constrains strategies.{momentum,sector}_frequencies to the
    user's choice, the report must reflect THAT cadence — not the
    pre-adapter default. Otherwise reports lie about what was tested."""
    api_config = BacktestConfig.model_validate(
        {
            "preset": "ATLAS Adaptive v3",
            "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
            "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
            "allocation": {"positionPct": 5.0, "slots": 10},
            "costs": {"feeBps": 10, "slippageBps": 5},
        }
    )
    config = to_research_config(api_config, api_config.preset, Settings(project_root=PROJECT_ROOT))
    summary = pd.DataFrame(
        {
            "BTC_BH__always_on": _summary_row({"cagr": 0.10, "sharpe": 0.80}),
            "TOP20_EQ__always_on": _summary_row({"cagr": 0.15, "sharpe": 1.00}),
            "TOP20_MOM_alpha": _summary_row({"cagr": 0.25, "sharpe": 1.5}),
            "TOP20_SECTOR_beta": _summary_row({"cagr": 0.22, "sharpe": 1.3}),
        }
    ).T
    summary.index.name = "strategy"

    text = build_markdown_report(config, summary, _yearly(), _regime(), tmp_path / "digest.md")

    assert "Rebalancing tested: weekly." in text
    assert "monthly and biweekly" not in text
