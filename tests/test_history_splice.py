"""Tests for splicing a legacy cached history with a newer source."""

from __future__ import annotations

import pandas as pd
import pytest

from atlas20.data.splice import splice_histories


def _frame(rows: list[tuple[str, float, float]], *, price_col: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime([r[0] for r in rows]),
            price_col: [r[1] for r in rows],
            "volume_usd": [r[2] for r in rows],
        }
    )


def test_splice_prefers_legacy_before_cutover_and_new_after() -> None:
    legacy = _frame(
        [("2024-01-01", 100.0, 1.0), ("2024-01-02", 110.0, 1.0), ("2024-01-03", 120.0, 1.0)],
        price_col="legacy_price",
    )
    new = _frame(
        [("2024-01-02", 110.5, 2.0), ("2024-01-03", 120.5, 2.0), ("2024-01-04", 130.0, 2.0)],
        price_col="new_price",
    )

    result = splice_histories(legacy, new, cutover=pd.Timestamp("2024-01-03"))

    assert result.cutover == pd.Timestamp("2024-01-03")
    assert list(result.frame["date"].dt.strftime("%Y-%m-%d")) == [
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
    ]
    # legacy wins on and before cutover
    assert result.frame.loc[result.frame["date"] == pd.Timestamp("2024-01-03"), "price"].iloc[0] == pytest.approx(120.0)
    # new source supplies strictly after cutover
    assert result.frame.loc[result.frame["date"] == pd.Timestamp("2024-01-04"), "price"].iloc[0] == pytest.approx(130.0)
    assert list(result.frame["price_source"]) == ["legacy", "legacy", "legacy", "new"]


def test_splice_reports_overlap_gap_and_correlation() -> None:
    legacy = _frame(
        [("2024-01-01", 100.0, 1.0), ("2024-01-02", 110.0, 1.0), ("2024-01-03", 120.0, 1.0)],
        price_col="legacy_price",
    )
    new = _frame(
        [("2024-01-01", 100.5, 2.0), ("2024-01-02", 110.5, 2.0), ("2024-01-03", 120.5, 2.0)],
        price_col="new_price",
    )

    result = splice_histories(legacy, new, cutover=pd.Timestamp("2024-01-03"))

    assert result.overlap_days == 3
    assert result.median_gap == pytest.approx(0.5 / 110.5, rel=1e-6)
    assert result.correlation == pytest.approx(1.0)


def test_splice_uses_new_source_when_legacy_empty() -> None:
    empty = pd.DataFrame(columns=["date", "legacy_price", "volume_usd"])
    new = _frame([("2024-01-01", 100.0, 1.0)], price_col="new_price")

    result = splice_histories(empty, new, cutover=pd.Timestamp("2024-01-01"))

    assert len(result.frame) == 1
    assert result.frame["price"].iloc[0] == pytest.approx(100.0)
    assert result.frame["price_source"].iloc[0] == "new"


def test_splice_uses_legacy_when_new_missing() -> None:
    legacy = _frame([("2024-01-01", 100.0, 1.0)], price_col="legacy_price")
    empty = pd.DataFrame(columns=["date", "new_price", "volume_usd"])

    result = splice_histories(legacy, empty, cutover=pd.Timestamp("2024-01-01"))

    assert len(result.frame) == 1
    assert result.frame["price"].iloc[0] == pytest.approx(100.0)
    assert result.frame["price_source"].iloc[0] == "legacy"


def test_splice_drops_non_positive_prices() -> None:
    legacy = _frame(
        [("2024-01-01", 0.0, 0.0), ("2024-01-02", 100.0, 1.0)],
        price_col="legacy_price",
    )
    new = _frame([("2024-01-03", 110.0, 2.0)], price_col="new_price")

    result = splice_histories(legacy, new, cutover=pd.Timestamp("2024-01-02"))

    assert list(result.frame["date"].dt.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]


def test_splice_cutover_defaults_to_legacy_last_date() -> None:
    legacy = _frame([("2024-01-01", 100.0, 1.0), ("2024-01-05", 120.0, 1.0)], price_col="legacy_price")
    new = _frame([("2024-01-06", 130.0, 2.0)], price_col="new_price")

    result = splice_histories(legacy, new)

    assert result.cutover == pd.Timestamp("2024-01-05")
