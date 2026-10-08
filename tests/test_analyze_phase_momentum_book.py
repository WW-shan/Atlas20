from __future__ import annotations

import pandas as pd
import pytest

import scripts.analyze_phase_momentum_book as book


def _weights() -> pd.DataFrame:
    index = pd.date_range("2022-01-01", periods=4, freq="D")
    return pd.DataFrame(
        {
            "a": [1.0, 0.5, 0.0, 0.25],
            "b": [0.0, 0.5, 0.0, 0.25],
            "c": [0.0, 0.0, 0.0, 0.25],
        },
        index=index,
    )


def test_book_concentration_counts_coins_and_the_largest_share() -> None:
    frame = book.book_concentration(_weights())
    assert frame["gross_exposure"].tolist() == pytest.approx([1.0, 1.0, 0.0, 0.75])
    assert frame["distinct_coins"].tolist() == [1, 2, 0, 3]
    assert frame["largest_share"].tolist()[:2] == pytest.approx([1.0, 0.5])
    assert frame["largest_share"].iloc[2] is pd.NA or pd.isna(frame["largest_share"].iloc[2])
    assert frame["hhi"].iloc[1] == pytest.approx(0.5)


def test_summarise_ignores_days_with_no_position() -> None:
    summary = book.summarise(book.book_concentration(_weights()))
    # the empty day is excluded from the "while invested" statistics
    assert summary["invested_days"] == 3.0
    assert summary["avg_distinct_coins_invested"] == pytest.approx((1 + 2 + 3) / 3)
    assert summary["share_days_single_coin"] == pytest.approx(1 / 3)
    assert summary["share_days_top_coin_over_50pct"] == pytest.approx(2 / 3)
