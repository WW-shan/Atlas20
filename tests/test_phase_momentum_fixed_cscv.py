from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from scripts.run_phase_momentum_fixed_cscv import main


def test_fixed_cscv_script_writes_one_row_per_candidate(tmp_path, monkeypatch) -> None:
    rng = np.random.default_rng(42)
    index = pd.date_range("2024-01-01", periods=48, freq="D")
    returns = pd.DataFrame(
        {
            "stable": rng.normal(0.001, 0.01, len(index)),
            "volatile": rng.normal(0.002, 0.03, len(index)),
        },
        index=index,
    )
    returns.index.name = "date"
    returns_path = tmp_path / "returns.csv"
    returns.to_csv(returns_path)
    output_dir = tmp_path / "fixed-cscv"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_phase_momentum_fixed_cscv.py",
            "--candidate-returns",
            str(returns_path),
            "--candidates",
            "stable,volatile",
            "--cscv-blocks",
            "4",
            "--output-dir",
            str(output_dir),
        ],
    )

    main()

    summary = pd.read_csv(output_dir / "summary.csv")
    assert summary["candidate"].tolist() == ["stable", "volatile"]
    assert summary["splits"].tolist() == [6, 6]
    assert summary["below_median_rate"].between(0.0, 1.0).all()
