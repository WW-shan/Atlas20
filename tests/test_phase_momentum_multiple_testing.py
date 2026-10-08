from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.run_phase_momentum_multiple_testing import (
    _cscv_blocks,
    _dedupe_identical_columns,
    _deflated_sharpe,
    _excess_over,
    _expected_max_sharpe,
    _load_candidate_returns,
    _oos_logit,
    _project_scopes,
    _require_common_sample,
)


def test_identical_candidates_are_counted_once() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame(
        {
            "primary": [0.01, -0.02, 0.03, 0.0],
            "stop_never_hit": [0.01, -0.02, 0.03, 0.0],
            "other": [0.02, 0.0, -0.01, 0.01],
        },
        index=index,
    )

    unique, duplicates = _dedupe_identical_columns(returns)

    assert list(unique.columns) == ["primary", "other"]
    assert duplicates == {"stop_never_hit": "primary"}


def test_cscv_blocks_use_every_row() -> None:
    returns = pd.DataFrame({"a": np.arange(1725, dtype=float)})

    blocks = _cscv_blocks(returns, 12)

    assert len(blocks) == 12
    assert sum(len(block) for block in blocks) == 1725
    assert blocks[-1].index[-1] == 1724


def test_oos_logit_counts_the_exact_median_rank_as_overfit() -> None:
    performance = pd.Series({"low": 0.1, "mid": 0.2, "high": 0.3})

    # Relative rank w = r / (N + 1): the middle of three is w = 0.5, logit 0.
    assert _oos_logit(performance, "mid") == pytest.approx(0.0)
    assert _oos_logit(performance, "high") == pytest.approx(np.log(3.0))
    assert _oos_logit(performance, "low") == pytest.approx(-np.log(3.0))


def test_common_sample_refuses_partial_rows() -> None:
    returns = pd.DataFrame({"a": [0.01, np.nan], "b": [0.02, 0.03]})

    with pytest.raises(ValueError, match="missing"):
        _require_common_sample(returns)


def test_common_sample_refuses_infinite_returns() -> None:
    # A per-candidate dropna of +/-inf would measure that candidate on fewer days.
    returns = pd.DataFrame({"a": [0.01, np.inf, 0.02], "b": [0.02, 0.03, -0.01]})

    with pytest.raises(ValueError, match="non-finite"):
        _require_common_sample(returns)


def _write_returns(path: Path, rows: list[str]) -> Path:
    path.write_text("\n".join(["date,primary,other", *rows]) + "\n", encoding="utf-8")
    return path


def test_loader_refuses_a_row_where_only_some_candidates_are_missing(tmp_path: Path) -> None:
    # dropna(how="all") used to keep this row and compare candidates over different days.
    path = _write_returns(tmp_path / "r.csv", ["2024-01-01,0.01,0.02", "2024-01-02,,0.01", "2024-01-03,0.0,0.03"])

    with pytest.raises(ValueError, match="missing"):
        _load_candidate_returns(path)


def test_loader_refuses_rows_where_every_candidate_is_missing(tmp_path: Path) -> None:
    path = _write_returns(tmp_path / "r.csv", ["2024-01-01,,", "2024-01-02,0.01,0.02", "2024-01-03,0.0,0.03"])

    with pytest.raises(ValueError, match="missing"):
        _load_candidate_returns(path)


def test_loader_refuses_non_numeric_returns_and_duplicate_dates(tmp_path: Path) -> None:
    corrupt = _write_returns(tmp_path / "corrupt.csv", ["2024-01-01,0.01,0.02", "2024-01-02,oops,0.01"])
    duplicated = _write_returns(tmp_path / "dup.csv", ["2024-01-01,0.01,0.02", "2024-01-01,0.01,0.02"])

    with pytest.raises(ValueError, match="missing"):
        _load_candidate_returns(corrupt)
    with pytest.raises(ValueError, match="duplicate"):
        _load_candidate_returns(duplicated)


def test_loader_keeps_every_complete_row_in_date_order(tmp_path: Path) -> None:
    path = _write_returns(tmp_path / "r.csv", ["2024-01-02,0.02,0.01", "2024-01-01,0.01,0.02"])

    returns = _load_candidate_returns(path)

    assert list(returns.columns) == ["primary", "other"]
    assert [str(day.date()) for day in returns.index] == ["2024-01-01", "2024-01-02"]
    assert returns["primary"].tolist() == pytest.approx([0.01, 0.02])


def _scope(n_trials: int, std_annualized: float) -> dict[str, object]:
    return {
        "n_trials": n_trials,
        "n_with_sharpe": n_trials - 1,
        "sharpe_std_annualized": std_annualized,
        "sharpe_std_per_period": std_annualized / np.sqrt(365.0),
        "periods_per_year": 365,
    }


def test_project_scopes_take_counts_per_scope_and_dispersion_from_the_comparable_pool(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    path.write_text(
        json.dumps({"top20_2022_trials": _scope(6119, 0.3121), "all_trials": _scope(14113, 0.652)}),
        encoding="utf-8",
    )

    scopes = _project_scopes(path)

    assert [(name, count) for name, count, _ in scopes] == [("top20_2022_trials", 6119), ("all_trials", 14113)]
    for _, _, std in scopes:
        assert std == pytest.approx(0.3121 / np.sqrt(365.0))


def test_project_scopes_refuse_an_unusable_summary(tmp_path: Path) -> None:
    tiny = tmp_path / "tiny.json"
    tiny.write_text(json.dumps({"top20_2022_trials": _scope(1, 0.3), "all_trials": _scope(9, 0.6)}), encoding="utf-8")
    weekly = tmp_path / "weekly.json"
    weekly.write_text(
        json.dumps({"top20_2022_trials": {**_scope(50, 0.3), "periods_per_year": 52}, "all_trials": _scope(90, 0.6)}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="too few"):
        _project_scopes(tiny)
    with pytest.raises(ValueError, match="365"):
        _project_scopes(weekly)


def test_expected_max_sharpe_grows_with_the_number_of_trials() -> None:
    assert _expected_max_sharpe(1, 0.01) == 0.0
    few = _expected_max_sharpe(32, 0.01)
    many = _expected_max_sharpe(4000, 0.01)
    assert 0.0 < few < many


def test_deflated_sharpe_falls_when_the_hurdle_rises() -> None:
    rng = np.random.default_rng(3)
    returns = pd.Series(rng.normal(0.002, 0.02, 1000))

    easy = _deflated_sharpe(returns, expected_max_sharpe=0.0)
    hard = _deflated_sharpe(returns, expected_max_sharpe=0.2)

    assert easy["deflated_sharpe_probability"] > hard["deflated_sharpe_probability"]


def test_excess_over_benchmark_requires_every_date() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame({"a": [0.02, 0.01, 0.0]}, index=index)
    benchmark = pd.Series([0.01, 0.01, 0.01], index=index)

    excess = _excess_over(returns, benchmark)

    assert excess["a"].tolist() == pytest.approx([0.01, 0.0, -0.01])
    with pytest.raises(ValueError, match="benchmark"):
        _excess_over(returns, benchmark.iloc[:2])
    with pytest.raises(ValueError, match="benchmark"):
        _excess_over(returns, pd.Series([0.01, np.inf, 0.01], index=index))
