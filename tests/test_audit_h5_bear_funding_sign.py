import pandas as pd

from scripts.audit_h5_bear_funding_sign import build_audit


def test_funding_sign_audit_uses_signal_date_and_signal_regime() -> None:
    episodes = pd.DataFrame(
        [
            {
                "asset": "bitcoin",
                "entry_time": "2022-01-02T03:00:00Z",
                "exit_time": "2022-01-09T03:00:00Z",
                "net_pnl_pct_nav": 1.0,
            }
        ]
    )
    sleeve_audit = pd.DataFrame(
        [
            {"date": "2022-01-01T00:00:00Z", "regime": "bear"},
            {"date": "2022-01-02T00:00:00Z", "regime": "non_bear"},
        ]
    )
    funding = pd.DataFrame(
        {
            "bitcoin": [0.001, 0.002, 0.003, 9.0],
        },
        index=pd.to_datetime(
            [
                "2021-12-31T00:00:00Z",
                "2021-12-31T08:00:00Z",
                "2021-12-31T16:00:00Z",
                "2022-01-02T00:00:00Z",
            ]
        ),
    )

    detailed, _ = build_audit(episodes, sleeve_audit, funding)

    assert detailed.loc[0, "entry_regime"] == "bear"
    assert detailed.loc[0, "funding_mean_3"] == 0.002
