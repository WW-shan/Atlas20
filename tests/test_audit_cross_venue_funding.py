import pandas as pd

from scripts.audit_cross_venue_funding import (
    build_cross_venue_audit,
    summarize_cross_venue_audit,
)


def test_cross_venue_audit_uses_only_prior_settlements_and_marks_missing() -> None:
    episodes = pd.DataFrame(
        [
            {
                "asset": "bitcoin",
                "entry_date": "2022-01-05T00:00:00Z",
                "entry_regime": "bear",
            },
            {
                "asset": "ethereum",
                "entry_date": "2022-01-05T00:00:00Z",
                "entry_regime": "bear",
            },
            {
                "asset": "solana",
                "entry_date": "2022-01-05T00:00:00Z",
                "entry_regime": "non_bear",
            },
        ]
    )
    bybit_rates = {
        "bitcoin": pd.Series(
            [0.0001, 0.0002, 0.0003, 9.0],
            index=pd.to_datetime(
                [
                    "2022-01-01T00:00:00Z",
                    "2022-01-02T00:00:00Z",
                    "2022-01-03T00:00:00Z",
                    "2022-01-06T00:00:00Z",
                ]
            ),
        ),
        "solana": pd.Series(
            [-0.0001, -0.0002, -0.0003],
            index=pd.to_datetime(
                [
                    "2022-01-01T00:00:00Z",
                    "2022-01-02T00:00:00Z",
                    "2022-01-03T00:00:00Z",
                ]
            ),
        ),
    }

    audit = build_cross_venue_audit(episodes, bybit_rates)

    assert audit.loc[audit["asset"] == "bitcoin", "bybit_mean_3"].iloc[0] == 0.0002
    assert not bool(audit.loc[audit["asset"] == "ethereum", "bybit_available"].iloc[0])
    assert bool(audit.loc[audit["asset"] == "solana", "bybit_available"].iloc[0])


def test_cross_venue_audit_summarizes_coverage_and_agreement() -> None:
    audit = pd.DataFrame(
        [
            {"entry_regime": "bear", "bybit_available": True, "both_positive": True, "same_sign": True},
            {"entry_regime": "bear", "bybit_available": True, "both_positive": False, "same_sign": False},
            {"entry_regime": "bear", "bybit_available": False, "both_positive": False, "same_sign": False},
            {"entry_regime": "non_bear", "bybit_available": True, "both_positive": True, "same_sign": True},
        ]
    )

    summary = summarize_cross_venue_audit(audit)

    assert summary["total_episodes"] == 4
    assert summary["bybit_available"] == 3
    assert summary["bybit_coverage"] == 0.75
    assert summary["bear_episodes"] == 3
    assert summary["bear_bybit_available"] == 2
    assert summary["bear_both_positive"] == 1
    assert summary["bear_same_sign"] == 1


def test_cross_venue_audit_uses_signal_date_not_execution_date() -> None:
    episodes = pd.DataFrame(
        [
            {
                "asset": "bitcoin",
                "entry_time": "2022-01-02T03:00:00Z",
                "entry_regime": "bear",
            }
        ]
    )
    bybit_rates = {
        "bitcoin": pd.Series(
            [0.001, 0.002, 0.003, 9.0],
            index=pd.to_datetime(
                [
                    "2021-12-31T00:00:00Z",
                    "2021-12-31T08:00:00Z",
                    "2021-12-31T16:00:00Z",
                    "2022-01-02T00:00:00Z",
                ]
            ),
        )
    }

    audit = build_cross_venue_audit(episodes, bybit_rates)

    assert audit.loc[0, "bybit_mean_3"] == 0.002


def test_cross_venue_audit_requires_three_prior_settlements() -> None:
    episodes = pd.DataFrame(
        [
            {
                "asset": "bitcoin",
                "entry_time": "2022-01-02T03:00:00Z",
                "entry_regime": "bear",
            }
        ]
    )
    bybit_rates = {
        "bitcoin": pd.Series(
            [0.001, 0.002],
            index=pd.to_datetime(
                ["2021-12-31T08:00:00Z", "2021-12-31T16:00:00Z"]
            ),
        )
    }

    audit = build_cross_venue_audit(episodes, bybit_rates)

    assert pd.isna(audit.loc[0, "bybit_mean_3"])
    assert not bool(audit.loc[0, "bybit_available"])
