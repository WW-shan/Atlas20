from datetime import date

import pytest

from atlas20.api.data_access.overview import load_overview_from_reports
from atlas20.api.schemas import OverviewPayload
from atlas20.api.settings import Settings


SUMMARY_HEADER = (
    "strategy,total_return,cagr,annualized_volatility,sharpe,sortino,max_drawdown,"
    "calmar,monthly_win_rate,annualized_turnover,avg_turnover_per_rebalance,average_holdings"
)


def _write_report_csvs(report_root, returns: list[float] | None = None) -> None:
    latest = report_root / "latest"
    latest.mkdir(parents=True)
    latest.joinpath("strategy_summary.csv").write_text(
        "\n".join(
            [
                SUMMARY_HEADER,
                "ALPHA,0.50,0.20,0.30,1.70,2.00,-0.20,1.00,0.60,4.00,0.50,2.00",
                "BETA,0.40,0.18,0.30,1.20,1.60,-0.25,0.80,0.55,3.00,0.40,2.00",
                "BTC_BH__always_on,0.30,0.15,0.35,0.90,1.20,-0.30,0.50,0.52,0.20,1.00,1.00",
            ]
        ),
        encoding="utf-8",
    )

    if returns is None:
        returns = [0.01, 0.02, -0.005, 0.015, 0.0, 0.01]
        rows = [
            "2026-01-31",
            "2026-02-28",
            "2026-03-31",
            "2026-04-30",
            "2026-05-31",
            "2026-06-30",
        ]
    else:
        rows = [f"2026-01-{day:02d}" for day in range(1, len(returns) + 1)]

    daily_lines = [",ALPHA,BETA,BTC_BH__always_on"]
    equity_lines = [",ALPHA,BETA,BTC_BH__always_on"]
    alpha_equity = beta_equity = btc_equity = 100000.0
    for row_date, alpha_return in zip(rows, returns, strict=True):
        beta_return = alpha_return / 2
        btc_return = alpha_return / 3
        alpha_equity *= 1 + alpha_return
        beta_equity *= 1 + beta_return
        btc_equity *= 1 + btc_return
        daily_lines.append(f"{row_date},{alpha_return},{beta_return},{btc_return}")
        equity_lines.append(f"{row_date},{alpha_equity},{beta_equity},{btc_equity}")

    latest.joinpath("daily_returns.csv").write_text("\n".join(daily_lines), encoding="utf-8")
    latest.joinpath("equity_curves.csv").write_text("\n".join(equity_lines), encoding="utf-8")


def test_load_overview_from_reports_validates_payload_and_strategy_ranking(tmp_path):
    _write_report_csvs(tmp_path)

    payload = load_overview_from_reports(Settings(report_root=tmp_path, anchor_date=date(2026, 6, 30)))
    model = OverviewPayload.model_validate(payload)

    assert model.champion.strategy == "ALPHA"
    assert len(model.top_strategies) == 3
    assert [row.strategy for row in model.top_strategies] == ["ALPHA", "BETA", "BTC_BH__always_on"]
    assert len(model.equity_curve) == 6


def test_load_overview_from_reports_computes_ytd_from_daily_returns(tmp_path):
    daily_returns = [0.01] * 30
    _write_report_csvs(tmp_path, returns=daily_returns)

    payload = load_overview_from_reports(Settings(report_root=tmp_path, anchor_date=date(2026, 1, 30)))

    assert payload["hero_kpi"]["ytdReturn"] == pytest.approx((1.01**30) - 1)


def test_load_overview_from_reports_missing_csv_raises_with_path(tmp_path):
    (tmp_path / "latest").mkdir()

    with pytest.raises(FileNotFoundError, match="strategy_summary.csv"):
        load_overview_from_reports(Settings(report_root=tmp_path, anchor_date=date(2026, 6, 30)))


def test_load_overview_from_reports_empty_csv_raises_value_error(tmp_path):
    latest = tmp_path / "latest"
    latest.mkdir()
    latest.joinpath("strategy_summary.csv").write_text("", encoding="utf-8")
    latest.joinpath("daily_returns.csv").write_text(",ALPHA\n2026-01-01,0.01", encoding="utf-8")
    latest.joinpath("equity_curves.csv").write_text(",ALPHA\n2026-01-01,101000", encoding="utf-8")

    with pytest.raises(ValueError):
        load_overview_from_reports(Settings(report_root=tmp_path, anchor_date=date(2026, 1, 1)))


def test_load_overview_from_reports_rejects_non_finite_numbers(tmp_path):
    latest = tmp_path / "latest"
    latest.mkdir()
    latest.joinpath("strategy_summary.csv").write_text(
        "\n".join(
            [
                SUMMARY_HEADER,
                "ALPHA,,0.20,0.30,1.70,2.00,-0.20,1.00,0.60,4.00,0.50,2.00",
            ]
        ),
        encoding="utf-8",
    )
    latest.joinpath("daily_returns.csv").write_text(
        ",ALPHA,BTC_BH__always_on\n2026-01-01,0.01,0.005",
        encoding="utf-8",
    )
    latest.joinpath("equity_curves.csv").write_text(
        ",ALPHA,BTC_BH__always_on\n2026-01-01,101000,100500",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Non-finite numeric value"):
        load_overview_from_reports(Settings(report_root=tmp_path, anchor_date=date(2026, 1, 1)))


def test_load_overview_from_reports_excludes_btc_benchmark_when_ranking(tmp_path):
    latest = tmp_path / "latest"
    latest.mkdir(parents=True)
    latest.joinpath("strategy_summary.csv").write_text(
        "\n".join(
            [
                SUMMARY_HEADER,
                "BTC_BH__always_on,0.40,0.15,0.35,5.00,1.20,-0.30,0.50,0.52,0.20,1.00,1.00",
                "ALPHA,0.50,0.20,0.30,1.70,2.00,-0.20,1.00,0.60,4.00,0.50,2.00",
                "BETA,0.40,0.18,0.30,1.20,1.60,-0.25,0.80,0.55,3.00,0.40,2.00",
            ]
        ),
        encoding="utf-8",
    )
    latest.joinpath("daily_returns.csv").write_text(
        "\n".join(
            [
                ",BTC_BH__always_on,ALPHA,BETA",
                "2026-01-01,0.01,0.01,0.01",
                "2026-02-28,0.02,0.02,0.02",
                "2026-03-31,-0.005,-0.005,-0.005",
                "2026-04-30,0.015,0.015,0.015",
                "2026-05-31,0.0,0.0,0.0",
                "2026-06-30,0.01,0.01,0.01",
            ]
        ),
        encoding="utf-8",
    )
    latest.joinpath("equity_curves.csv").write_text(
        "\n".join(
            [
                ",BTC_BH__always_on,ALPHA,BETA",
                "2026-01-01,100500,101000,101000",
                "2026-02-28,101505,103020,103020",
                "2026-03-31,100997.47,102504.9,102504.9",
                "2026-04-30,102512.43,104042.47,104042.47",
                "2026-05-31,102512.43,104042.47,104042.47",
                "2026-06-30,103537.55,105082.89,105082.89",
            ]
        ),
        encoding="utf-8",
    )

    payload = load_overview_from_reports(Settings(report_root=tmp_path, anchor_date=date(2026, 6, 30)))

    assert payload["champion"]["strategy"] == "ALPHA"
