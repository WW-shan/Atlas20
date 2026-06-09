# Top20 Convex Leader Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Top20 high-convexity research pack that can validate the current champion and discover stronger, more robust candidate strategies.

**Architecture:** Add a focused strategy-scoring module for CTREND-lite Top20 leaders, then add a research script that generates candidate definitions, screens them, validates the best subset, and writes CSV plus markdown reports. Keep the default Atlas20 pipeline unchanged until a candidate is validated.

**Tech Stack:** Python 3.11, pandas, pytest, existing Atlas20 backtest engine, existing universe builder, existing BTC risk overlays, existing markdown table helper.

---

## File Structure

Create:

- `src/atlas20/strategies/convex_leader.py`
  - Owns CTREND-lite score computation, score-family definitions, and target building for concentrated convex leader strategies.

- `scripts/run_top20_convex_validation.py`
  - Owns candidate generation, full-window screening, robustness diagnostics, CSV output, and markdown report generation.

- `tests/test_convex_leader.py`
  - Unit tests for score computation, deterministic ranking, missing data behavior, BTC exclusion, and target generation.

- `tests/test_top20_convex_validation.py`
  - Unit and integration-style tests for candidate generation, rankings, cost stress, rolling starts, output shape, and report writing.

Modify:

- `src/atlas20/strategies/__init__.py`
  - Export the new convex leader module symbols only if the file currently exports strategy symbols.

Do not modify:

- `scripts/run_profit_max_refine.py`
- `src/atlas20/strategies/momentum_lead.py`
- `src/atlas20/backtest/engine.py`
- Strategy Lab API or frontend in this slice.

## Task 1: Add CTREND-Lite Scoring

**Files:**

- Create: `tests/test_convex_leader.py`
- Create: `src/atlas20/strategies/convex_leader.py`

- [ ] **Step 1: Write failing tests for CTREND-lite scoring**

Create `tests/test_convex_leader.py` with this content:

```python
from __future__ import annotations

import pandas as pd
import pytest

from atlas20.strategies.convex_leader import (
    CTREND_LITE_SCORE_FAMILIES,
    compute_ctrend_lite_scores,
)
from atlas20.universe.builder import MarketDataBundle


def _toy_market() -> MarketDataBundle:
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    price = pd.DataFrame(
        {
            "bitcoin": [100 + i * 0.4 for i in range(100)],
            "ethereum": [80 + i * 0.2 for i in range(100)],
            "solana": [10 + i * 1.2 for i in range(100)],
            "chainlink": [20 + i * 0.15 for i in range(100)],
            "dogecoin": [5 + i * 0.05 for i in range(100)],
        },
        index=dates,
    )
    price.loc[dates[-8]:, "dogecoin"] = [7, 11, 16, 22, 31, 44, 58, 76]
    volume = pd.DataFrame(
        {
            "bitcoin": [1_000_000.0] * 100,
            "ethereum": [800_000.0] * 100,
            "solana": [500_000.0 + i * 20_000 for i in range(100)],
            "chainlink": [300_000.0] * 100,
            "dogecoin": [120_000.0 + i * 50_000 for i in range(100)],
        },
        index=dates,
    )
    metadata = pd.DataFrame(
        {
            "sector": {
                "bitcoin": "Store of Value",
                "ethereum": "Smart Contract Platform / L1",
                "solana": "Smart Contract Platform / L1",
                "chainlink": "Infrastructure",
                "dogecoin": "Meme",
            }
        }
    )
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000,
        volume=volume,
        history_count=price.notna().cumsum(),
        metadata=metadata,
    )


def test_ctrend_lite_scores_rank_structural_leader_above_slow_coin() -> None:
    market = _toy_market()
    date = market.price.index[-1]

    scores = compute_ctrend_lite_scores(
        market,
        date,
        ["bitcoin", "ethereum", "solana", "chainlink"],
        CTREND_LITE_SCORE_FAMILIES["ctrend_lite_balanced"],
    )

    assert scores.index[0] == "solana"
    assert scores.loc["solana"] > scores.loc["chainlink"]
    assert scores.index.is_unique


def test_ctrend_lite_overheat_penalty_reduces_one_window_spike() -> None:
    market = _toy_market()
    date = market.price.index[-1]

    scores = compute_ctrend_lite_scores(
        market,
        date,
        ["solana", "dogecoin"],
        CTREND_LITE_SCORE_FAMILIES["ctrend_lite_vol_adjusted"],
    )

    assert scores.loc["solana"] > scores.loc["dogecoin"]


def test_ctrend_lite_scores_drop_assets_with_no_usable_data() -> None:
    market = _toy_market()
    market.price["newcoin"] = pd.NA
    market.volume["newcoin"] = pd.NA
    date = market.price.index[-1]

    scores = compute_ctrend_lite_scores(
        market,
        date,
        ["solana", "newcoin"],
        CTREND_LITE_SCORE_FAMILIES["ctrend_lite_balanced"],
    )

    assert list(scores.index) == ["solana"]


def test_ctrend_lite_scores_require_btc_and_eth_for_relative_strength() -> None:
    market = _toy_market()
    date = market.price.index[-1]

    with pytest.raises(ValueError, match="bitcoin and ethereum"):
        compute_ctrend_lite_scores(
            market,
            date,
            ["solana", "chainlink"],
            CTREND_LITE_SCORE_FAMILIES["ctrend_lite_balanced"],
            require_reference_assets=True,
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_convex_leader.py -q
```

Expected: failure because `atlas20.strategies.convex_leader` does not exist.

- [ ] **Step 3: Implement CTREND-lite scoring**

Create `src/atlas20/strategies/convex_leader.py` with this content:

```python
"""High-convexity Top20 leader scoring and target builders."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from atlas20.backtest.calendar import get_rebalance_dates
from atlas20.config import ResearchConfig
from atlas20.signals.momentum import trailing_return
from atlas20.strategies.momentum_lead import MomentumLeadBuildResult
from atlas20.universe.builder import MarketDataBundle


@dataclass(frozen=True)
class CTrendLiteScoreWeights:
    """Rank-based CTREND-lite score weights."""

    ret_7: float = 0.12
    ret_14: float = 0.16
    ret_21: float = 0.18
    ret_28: float = 0.14
    ret_42: float = 0.10
    ret_60: float = 0.08
    btc_relative_28: float = 0.08
    eth_relative_28: float = 0.04
    near_high_90: float = 0.06
    volume_expansion: float = 0.04
    volatility_penalty: float = 0.10
    spike_penalty: float = 0.06


CTREND_LITE_SCORE_FAMILIES: dict[str, CTrendLiteScoreWeights] = {
    "ctrend_lite_balanced": CTrendLiteScoreWeights(),
    "ctrend_lite_acceleration": CTrendLiteScoreWeights(
        ret_7=0.18,
        ret_14=0.20,
        ret_21=0.18,
        ret_28=0.10,
        ret_42=0.06,
        ret_60=0.04,
        btc_relative_28=0.08,
        eth_relative_28=0.04,
        near_high_90=0.06,
        volume_expansion=0.06,
        volatility_penalty=0.12,
        spike_penalty=0.08,
    ),
    "ctrend_lite_breakout": CTrendLiteScoreWeights(
        ret_7=0.08,
        ret_14=0.12,
        ret_21=0.16,
        ret_28=0.16,
        ret_42=0.10,
        ret_60=0.06,
        btc_relative_28=0.08,
        eth_relative_28=0.04,
        near_high_90=0.18,
        volume_expansion=0.04,
        volatility_penalty=0.08,
        spike_penalty=0.06,
    ),
    "ctrend_lite_relative_strength": CTrendLiteScoreWeights(
        ret_7=0.08,
        ret_14=0.12,
        ret_21=0.14,
        ret_28=0.12,
        ret_42=0.08,
        ret_60=0.06,
        btc_relative_28=0.20,
        eth_relative_28=0.10,
        near_high_90=0.04,
        volume_expansion=0.06,
        volatility_penalty=0.08,
        spike_penalty=0.04,
    ),
    "ctrend_lite_vol_adjusted": CTrendLiteScoreWeights(
        ret_7=0.08,
        ret_14=0.12,
        ret_21=0.16,
        ret_28=0.14,
        ret_42=0.10,
        ret_60=0.08,
        btc_relative_28=0.08,
        eth_relative_28=0.04,
        near_high_90=0.06,
        volume_expansion=0.04,
        volatility_penalty=0.20,
        spike_penalty=0.12,
    ),
}


def _rank_high_is_good(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").replace([float("inf"), float("-inf")], pd.NA).dropna()
    return clean.rank(pct=True, method="average") if not clean.empty else clean


def _rank_low_is_good(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").replace([float("inf"), float("-inf")], pd.NA).dropna()
    return (1.0 - clean.rank(pct=True, method="average") + (1.0 / len(clean))) if not clean.empty else clean


def _trailing_return_or_zero(price: pd.DataFrame, date: pd.Timestamp, window: int, coin_ids: list[str]) -> pd.Series:
    values = trailing_return(price, date, window).reindex(coin_ids)
    return pd.to_numeric(values, errors="coerce")


def compute_ctrend_lite_scores(
    market: MarketDataBundle,
    rebalance_date: pd.Timestamp,
    coin_ids: list[str],
    weights: CTrendLiteScoreWeights,
    *,
    require_reference_assets: bool = False,
) -> pd.Series:
    """Compute rank-based CTREND-lite leader scores for one rebalance date."""
    if not coin_ids:
        return pd.Series(dtype=float)

    date = pd.Timestamp(rebalance_date)
    if require_reference_assets and ("bitcoin" not in coin_ids or "ethereum" not in coin_ids):
        raise ValueError("CTREND-lite relative strength requires bitcoin and ethereum in coin_ids")

    available = [coin_id for coin_id in coin_ids if coin_id in market.price.columns]
    if not available or date not in market.price.index:
        return pd.Series(dtype=float)

    frame = pd.DataFrame(index=available)
    for window in (7, 14, 21, 28, 42, 60):
        frame[f"ret_{window}"] = _trailing_return_or_zero(market.price, date, window, available)

    ret_28_all = trailing_return(market.price, date, 28)
    btc_ret_28 = float(ret_28_all.get("bitcoin", 0.0) or 0.0)
    eth_ret_28 = float(ret_28_all.get("ethereum", 0.0) or 0.0)
    frame["btc_relative_28"] = frame["ret_28"] - btc_ret_28
    frame["eth_relative_28"] = frame["ret_28"] - eth_ret_28

    rolling_high = market.price.shift(1).rolling(90, min_periods=30).max().loc[date].reindex(available)
    current_price = market.price.loc[date].reindex(available)
    frame["near_high_90"] = current_price / rolling_high

    recent_volume = market.volume.rolling(14, min_periods=7).mean().loc[date].reindex(available)
    base_volume = market.volume.rolling(60, min_periods=20).mean().loc[date].reindex(available)
    frame["volume_expansion"] = recent_volume / base_volume

    recent_returns = market.returns.reindex(columns=available).loc[:date].tail(14)
    frame["volatility_penalty"] = recent_returns.std(ddof=0)
    frame["spike_penalty"] = frame["ret_7"].abs()

    ranked = pd.DataFrame(index=frame.index)
    for column in (
        "ret_7",
        "ret_14",
        "ret_21",
        "ret_28",
        "ret_42",
        "ret_60",
        "btc_relative_28",
        "eth_relative_28",
        "near_high_90",
        "volume_expansion",
    ):
        ranked[column] = _rank_high_is_good(frame[column])
    ranked["volatility_penalty"] = _rank_low_is_good(frame["volatility_penalty"])
    ranked["spike_penalty"] = _rank_low_is_good(frame["spike_penalty"])
    ranked = ranked.dropna(how="all")
    if ranked.empty:
        return pd.Series(dtype=float)

    score = pd.Series(0.0, index=ranked.index)
    for column, weight in weights.__dict__.items():
        score = score.add(ranked[column].fillna(0.0) * float(weight), fill_value=0.0)
    return score.sort_values(ascending=False, kind="stable")


def _weight_scheme(top_n: int) -> list[float]:
    if top_n <= 0:
        return []
    if top_n == 1:
        return [1.0]
    if top_n == 2:
        return [0.6, 0.4]
    if top_n == 3:
        return [0.5, 0.3, 0.2]
    return [1.0 / top_n] * top_n


def _universe_lookup(universe: pd.DataFrame) -> dict[pd.Timestamp, pd.DataFrame]:
    return {pd.Timestamp(date): frame.copy() for date, frame in universe.groupby("rebalance_date")}


def build_ctrend_lite_targets(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    config: ResearchConfig,
    *,
    top_n: int,
    frequency: str,
    score_family: str,
    include_btc: bool = True,
) -> MomentumLeadBuildResult:
    """Build concentrated CTREND-lite leader targets."""
    if score_family not in CTREND_LITE_SCORE_FAMILIES:
        raise ValueError(f"Unknown CTREND-lite score family: {score_family}")

    frequency_value = config.rebalancing.frequencies.get(frequency, frequency)
    rebalance_dates = get_rebalance_dates(market.price.index, config.start_timestamp, frequency, frequency_value)
    universe_by_date = _universe_lookup(universe)
    targets: dict[pd.Timestamp, pd.Series] = {}
    selection_rows: list[dict[str, object]] = []

    for date in rebalance_dates:
        snapshot = universe_by_date.get(pd.Timestamp(date))
        if snapshot is None or snapshot.empty:
            targets[pd.Timestamp(date)] = pd.Series(dtype=float)
            continue

        coin_ids = [str(value) for value in snapshot["coin_id"].tolist()]
        if not include_btc:
            coin_ids = [coin_id for coin_id in coin_ids if coin_id != "bitcoin"]

        scores = compute_ctrend_lite_scores(
            market,
            pd.Timestamp(date),
            coin_ids,
            CTREND_LITE_SCORE_FAMILIES[score_family],
        )
        selected = scores.head(top_n)
        if selected.empty:
            targets[pd.Timestamp(date)] = pd.Series(dtype=float)
            continue

        weights = _weight_scheme(len(selected))
        target = pd.Series({coin_id: weight for (coin_id, _), weight in zip(selected.items(), weights)})
        targets[pd.Timestamp(date)] = target
        for rank, ((coin_id, score), weight) in enumerate(zip(selected.items(), weights), start=1):
            selection_rows.append(
                {
                    "rebalance_date": pd.Timestamp(date),
                    "coin_id": coin_id,
                    "coin_rank": rank,
                    "coin_score": float(score),
                    "coin_weight": float(weight),
                    "score_family": score_family,
                }
            )

    return MomentumLeadBuildResult(targets=targets, selection_history=pd.DataFrame(selection_rows))
```

- [ ] **Step 4: Run CTREND-lite scoring tests**

Run:

```bash
pytest tests/test_convex_leader.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add src/atlas20/strategies/convex_leader.py tests/test_convex_leader.py
git commit -m "feat: add top20 convex leader scoring"
```

Expected: commit succeeds.

## Task 2: Add Target Generation Tests

**Files:**

- Modify: `tests/test_convex_leader.py`
- Modify: `src/atlas20/strategies/convex_leader.py`

- [ ] **Step 1: Add failing tests for target generation and BTC exclusion**

Append this test code to `tests/test_convex_leader.py`:

```python
from atlas20.config import load_config
from atlas20.strategies.convex_leader import build_ctrend_lite_targets


def _toy_universe(dates: pd.DatetimeIndex) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for date in dates:
        for rank, coin_id in enumerate(["bitcoin", "ethereum", "solana", "chainlink"], start=1):
            rows.append(
                {
                    "rebalance_date": date,
                    "coin_id": coin_id,
                    "universe_rank": rank,
                    "price": 1.0,
                    "market_cap": 10_000_000 / rank,
                    "volume_usd": 1_000_000,
                    "history_days": 100,
                    "symbol": coin_id.upper(),
                    "name": coin_id,
                    "sector": "Layer1",
                }
            )
    return pd.DataFrame(rows)


def test_build_ctrend_lite_targets_respects_top_n_and_weights() -> None:
    market = _toy_market()
    config = load_config("config/base.yaml")
    config.start_date = "2024-03-01"
    config.rebalancing.frequencies["7D"] = "7D"
    dates = pd.date_range("2024-03-01", periods=5, freq="7D")
    universe = _toy_universe(dates)

    result = build_ctrend_lite_targets(
        market,
        universe,
        config,
        top_n=2,
        frequency="7D",
        score_family="ctrend_lite_balanced",
    )

    first_target = next(target for target in result.targets.values() if not target.empty)
    assert first_target.sum() == pytest.approx(1.0)
    assert len(first_target) == 2
    assert sorted(first_target.tolist(), reverse=True) == [0.6, 0.4]
    assert {"rebalance_date", "coin_id", "coin_score", "score_family"}.issubset(result.selection_history.columns)


def test_build_ctrend_lite_targets_can_exclude_btc_from_leader_pool() -> None:
    market = _toy_market()
    config = load_config("config/base.yaml")
    config.start_date = "2024-03-01"
    config.rebalancing.frequencies["7D"] = "7D"
    dates = pd.date_range("2024-03-01", periods=5, freq="7D")
    universe = _toy_universe(dates)

    result = build_ctrend_lite_targets(
        market,
        universe,
        config,
        top_n=3,
        frequency="7D",
        score_family="ctrend_lite_balanced",
        include_btc=False,
    )

    assert all("bitcoin" not in target.index for target in result.targets.values())
```

- [ ] **Step 2: Run target generation tests**

Run:

```bash
pytest tests/test_convex_leader.py -q
```

Expected: all tests pass if Task 1 implementation already included `build_ctrend_lite_targets`; otherwise fail with a missing function or wrong target shape.

- [ ] **Step 3: Fix target generation if the tests fail**

If tests fail because custom `"7D"` is not available, update `build_ctrend_lite_targets()` in `src/atlas20/strategies/convex_leader.py` so it resolves custom frequency names exactly like this:

```python
frequency_value = config.rebalancing.frequencies.get(frequency, frequency)
rebalance_dates = get_rebalance_dates(market.price.index, config.start_timestamp, frequency, frequency_value)
```

If tests fail because BTC is still selected when `include_btc=False`, keep this filtering line before scoring:

```python
if not include_btc:
    coin_ids = [coin_id for coin_id in coin_ids if coin_id != "bitcoin"]
```

- [ ] **Step 4: Re-run target generation tests**

Run:

```bash
pytest tests/test_convex_leader.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add src/atlas20/strategies/convex_leader.py tests/test_convex_leader.py
git commit -m "test: cover convex leader target generation"
```

Expected: commit succeeds.

## Task 3: Add Candidate Definitions And Ranking

**Files:**

- Create: `tests/test_top20_convex_validation.py`
- Create: `scripts/run_top20_convex_validation.py`

- [ ] **Step 1: Write failing candidate and ranking tests**

Create `tests/test_top20_convex_validation.py` with this content:

```python
from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_top20_convex_validation import (
    CandidateDefinition,
    build_candidate_definitions,
    compute_raw_convexity_score,
    compute_robust_convexity_score,
    select_validation_candidates,
)


def test_candidate_definitions_are_bounded_and_include_discovery_lane() -> None:
    candidates = build_candidate_definitions()
    family_ids = {candidate.family_id for candidate in candidates}

    assert "leader_momentum" in family_ids
    assert "ctrend_lite" in family_ids
    assert "champion_ablation" in family_ids
    assert len(candidates) < 2_500
    assert len({candidate.candidate_id for candidate in candidates}) == len(candidates)


def test_raw_convexity_score_prefers_higher_multiple_with_drawdown_penalty() -> None:
    strong = pd.Series(
        {
            "multiple": 100.0,
            "best_rolling_5y_multiple": 120.0,
            "hundred_x_hit_rate_5y": 0.50,
            "max_drawdown": -0.60,
        }
    )
    weak = pd.Series(
        {
            "multiple": 20.0,
            "best_rolling_5y_multiple": 25.0,
            "hundred_x_hit_rate_5y": 0.05,
            "max_drawdown": -0.50,
        }
    )

    assert compute_raw_convexity_score(strong) > compute_raw_convexity_score(weak)


def test_robust_convexity_score_penalizes_fragile_costly_candidate() -> None:
    robust = pd.Series(
        {
            "median_rolling_start_multiple": 40.0,
            "hundred_x_hit_rate_5y": 0.25,
            "max_drawdown": -0.55,
            "cost_survival_100bps": 0.70,
            "stability_score": 0.80,
            "annualized_turnover": 20.0,
        }
    )
    fragile = pd.Series(
        {
            "median_rolling_start_multiple": 60.0,
            "hundred_x_hit_rate_5y": 0.25,
            "max_drawdown": -0.78,
            "cost_survival_100bps": 0.20,
            "stability_score": 0.10,
            "annualized_turnover": 60.0,
        }
    )

    assert compute_robust_convexity_score(robust) > compute_robust_convexity_score(fragile)


def test_select_validation_candidates_keeps_champion_and_deduplicates() -> None:
    frame = pd.DataFrame(
        [
            {"candidate_id": "champion", "raw_convexity_score": 1.0, "robust_convexity_score": 1.0, "multiple": 2.0},
            {"candidate_id": "raw_best", "raw_convexity_score": 5.0, "robust_convexity_score": 1.0, "multiple": 50.0},
            {"candidate_id": "robust_best", "raw_convexity_score": 1.0, "robust_convexity_score": 5.0, "multiple": 30.0},
            {"candidate_id": "also_good", "raw_convexity_score": 4.0, "robust_convexity_score": 4.0, "multiple": 26.0},
        ]
    )

    selected = select_validation_candidates(
        frame,
        champion_candidate_id="champion",
        max_validation_candidates=3,
        min_multiple_for_validation=25.0,
    )

    assert selected == ["champion", "raw_best", "robust_best"]
```

- [ ] **Step 2: Run the candidate tests to verify they fail**

Run:

```bash
pytest tests/test_top20_convex_validation.py -q
```

Expected: failure because `scripts.run_top20_convex_validation` does not exist.

- [ ] **Step 3: Create the initial validation script with candidate definitions and ranking**

Create `scripts/run_top20_convex_validation.py` with this content:

```python
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import math
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.strategies.convex_leader import CTREND_LITE_SCORE_FAMILIES


@dataclass(frozen=True)
class CandidateDefinition:
    candidate_id: str
    family_id: str
    strategy_kind: str
    top_n: int
    frequency: str
    score_family: str
    liquidity_label: str
    min_history_days: int
    min_daily_dollar_volume: float
    include_btc: bool
    overlay_set: str
    risk_off_asset: str
    initial_asset: str
    stop_kind: str
    stop_lookback: int | None
    stop_confirm_days: int
    ma_window: int | None


LIQUIDITY_SETS: dict[str, tuple[int, float]] = {
    "loose": (30, 1_000_000.0),
    "medium": (60, 10_000_000.0),
    "strict": (90, 25_000_000.0),
}


OVERLAY_SETS: dict[str, dict[str, object]] = {
    "champion_like": {
        "stop_kind": "trailing",
        "stop_lookback": 11,
        "stop_confirm_days": 2,
        "ma_window": None,
        "risk_off_asset": "btc",
        "initial_asset": "btc",
    },
    "btc_fast_stop": {
        "stop_kind": "trailing",
        "stop_lookback": 10,
        "stop_confirm_days": 1,
        "ma_window": None,
        "risk_off_asset": "cash",
        "initial_asset": "btc",
    },
    "btc_medium_stop": {
        "stop_kind": "trailing",
        "stop_lookback": 14,
        "stop_confirm_days": 2,
        "ma_window": None,
        "risk_off_asset": "btc",
        "initial_asset": "btc",
    },
    "btc_ma_defensive": {
        "stop_kind": "ma",
        "stop_lookback": None,
        "stop_confirm_days": 2,
        "ma_window": 100,
        "risk_off_asset": "cash",
        "initial_asset": "btc",
    },
    "no_stop_control": {
        "stop_kind": "none",
        "stop_lookback": None,
        "stop_confirm_days": 1,
        "ma_window": None,
        "risk_off_asset": "cash",
        "initial_asset": "cash",
    },
}


LEADER_MOMENTUM_SCORE_FAMILIES = ["base", "short_accel", "breakout", "balanced"]


def _candidate_id(parts: list[object]) -> str:
    return "__".join(str(part).replace(" ", "_").lower() for part in parts)


def _candidate_from_parts(
    *,
    family_id: str,
    strategy_kind: str,
    top_n: int,
    frequency: str,
    score_family: str,
    liquidity_label: str,
    include_btc: bool,
    overlay_set: str,
) -> CandidateDefinition:
    min_history_days, min_daily_dollar_volume = LIQUIDITY_SETS[liquidity_label]
    overlay = OVERLAY_SETS[overlay_set]
    candidate_id = _candidate_id(
        [
            family_id,
            strategy_kind,
            f"top{top_n}",
            frequency,
            score_family,
            liquidity_label,
            "with_btc" if include_btc else "ex_btc",
            overlay_set,
        ]
    )
    return CandidateDefinition(
        candidate_id=candidate_id,
        family_id=family_id,
        strategy_kind=strategy_kind,
        top_n=top_n,
        frequency=frequency,
        score_family=score_family,
        liquidity_label=liquidity_label,
        min_history_days=min_history_days,
        min_daily_dollar_volume=min_daily_dollar_volume,
        include_btc=include_btc,
        overlay_set=overlay_set,
        risk_off_asset=str(overlay["risk_off_asset"]),
        initial_asset=str(overlay["initial_asset"]),
        stop_kind=str(overlay["stop_kind"]),
        stop_lookback=overlay["stop_lookback"] if isinstance(overlay["stop_lookback"], int) else None,
        stop_confirm_days=int(overlay["stop_confirm_days"]),
        ma_window=overlay["ma_window"] if isinstance(overlay["ma_window"], int) else None,
    )


def build_candidate_definitions() -> list[CandidateDefinition]:
    candidates: list[CandidateDefinition] = []

    for liquidity_label in LIQUIDITY_SETS:
        for top_n in (1, 2, 3):
            for frequency in ("7D", "14D", "21D", "28D"):
                for score_family in LEADER_MOMENTUM_SCORE_FAMILIES:
                    for overlay_set in ("champion_like", "btc_fast_stop", "btc_medium_stop", "no_stop_control"):
                        candidates.append(
                            _candidate_from_parts(
                                family_id="leader_momentum",
                                strategy_kind="leader_momentum",
                                top_n=top_n,
                                frequency=frequency,
                                score_family=score_family,
                                liquidity_label=liquidity_label,
                                include_btc=True,
                                overlay_set=overlay_set,
                            )
                        )

    for liquidity_label in LIQUIDITY_SETS:
        for top_n in (1, 2, 3):
            for frequency in ("7D", "14D", "21D", "28D"):
                for score_family in CTREND_LITE_SCORE_FAMILIES:
                    for include_btc in (True, False):
                        for overlay_set in ("champion_like", "btc_fast_stop", "btc_medium_stop", "btc_ma_defensive"):
                            candidates.append(
                                _candidate_from_parts(
                                    family_id="ctrend_lite",
                                    strategy_kind="ctrend_lite",
                                    top_n=top_n,
                                    frequency=frequency,
                                    score_family=score_family,
                                    liquidity_label=liquidity_label,
                                    include_btc=include_btc,
                                    overlay_set=overlay_set,
                                )
                            )

    for stop_lookback in (10, 11, 12, 13, 14, 15):
        overlay_name = f"champion_ablation_stop{stop_lookback}"
        OVERLAY_SETS[overlay_name] = {
            "stop_kind": "trailing",
            "stop_lookback": stop_lookback,
            "stop_confirm_days": 2,
            "ma_window": None,
            "risk_off_asset": "btc",
            "initial_asset": "btc",
        }
        candidates.append(
            _candidate_from_parts(
                family_id="champion_ablation",
                strategy_kind="leader_momentum",
                top_n=1,
                frequency="14D",
                score_family="base",
                liquidity_label="loose",
                include_btc=True,
                overlay_set=overlay_name,
            )
        )

    unique: dict[str, CandidateDefinition] = {}
    for candidate in candidates:
        unique[candidate.candidate_id] = candidate
    return list(unique.values())


def _safe_log_multiple(value: object) -> float:
    numeric = float(value) if pd.notna(value) else 0.0
    return math.log(max(numeric, 1e-9))


def compute_raw_convexity_score(row: pd.Series) -> float:
    return (
        0.45 * _safe_log_multiple(row.get("multiple", 0.0))
        + 0.25 * _safe_log_multiple(row.get("best_rolling_5y_multiple", row.get("multiple", 0.0)))
        + 0.15 * float(row.get("hundred_x_hit_rate_5y", 0.0) or 0.0)
        - 0.15 * abs(float(row.get("max_drawdown", 0.0) or 0.0))
    )


def compute_robust_convexity_score(row: pd.Series) -> float:
    turnover = float(row.get("annualized_turnover", 0.0) or 0.0)
    turnover_penalty = min(turnover / 100.0, 1.0)
    return (
        0.30 * _safe_log_multiple(row.get("median_rolling_start_multiple", row.get("multiple", 0.0)))
        + 0.20 * float(row.get("hundred_x_hit_rate_5y", 0.0) or 0.0)
        - 0.20 * abs(float(row.get("max_drawdown", 0.0) or 0.0))
        + 0.15 * float(row.get("cost_survival_100bps", 0.0) or 0.0)
        + 0.10 * float(row.get("stability_score", 0.0) or 0.0)
        - 0.05 * turnover_penalty
    )


def select_validation_candidates(
    summary: pd.DataFrame,
    *,
    champion_candidate_id: str,
    max_validation_candidates: int,
    min_multiple_for_validation: float,
) -> list[str]:
    selected: list[str] = []

    def add(candidate_id: str) -> None:
        if candidate_id not in selected and len(selected) < max_validation_candidates:
            selected.append(candidate_id)

    if champion_candidate_id in set(summary["candidate_id"]):
        add(champion_candidate_id)

    raw_sorted = summary.sort_values("raw_convexity_score", ascending=False)
    robust_sorted = summary.sort_values("robust_convexity_score", ascending=False)
    threshold_sorted = summary[summary["multiple"] >= min_multiple_for_validation].sort_values("multiple", ascending=False)

    for frame in (raw_sorted, robust_sorted, threshold_sorted):
        for candidate_id in frame["candidate_id"].astype(str):
            add(candidate_id)

    return selected


def candidate_records(candidates: list[CandidateDefinition]) -> pd.DataFrame:
    return pd.DataFrame([asdict(candidate) for candidate in candidates])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Top20 convex leader validation.")
    parser.add_argument("--config", default="config/bear_bottom_to_current_2022_11_21_2026_04_22.yaml")
    parser.parse_args()
    raise SystemExit("Task 6 adds full CLI execution.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run candidate and ranking tests**

Run:

```bash
pytest tests/test_top20_convex_validation.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add scripts/run_top20_convex_validation.py tests/test_top20_convex_validation.py
git commit -m "feat: define top20 convex validation candidates"
```

Expected: commit succeeds.

## Task 4: Add Full-Window Screening

**Files:**

- Modify: `tests/test_top20_convex_validation.py`
- Modify: `scripts/run_top20_convex_validation.py`

- [ ] **Step 1: Add tests for full-window screening output shape**

Append this code to `tests/test_top20_convex_validation.py`:

```python
from atlas20.config import load_config
from atlas20.universe.builder import MarketDataBundle
from scripts.run_top20_convex_validation import run_full_window_screen


def _script_toy_market() -> MarketDataBundle:
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    price = pd.DataFrame(
        {
            "bitcoin": [100 + i * 0.4 for i in range(100)],
            "ethereum": [80 + i * 0.2 for i in range(100)],
            "solana": [10 + i * 1.2 for i in range(100)],
            "chainlink": [20 + i * 0.15 for i in range(100)],
        },
        index=dates,
    )
    metadata = pd.DataFrame(
        {
            "sector": {
                "bitcoin": "Store of Value",
                "ethereum": "Smart Contract Platform / L1",
                "solana": "Smart Contract Platform / L1",
                "chainlink": "Infrastructure",
            }
        }
    )
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000,
        volume=pd.DataFrame(1_000_000.0, index=dates, columns=price.columns),
        history_count=price.notna().cumsum(),
        metadata=metadata,
    )


def _script_toy_universe(dates: pd.DatetimeIndex) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for date in dates:
        for rank, coin_id in enumerate(["bitcoin", "ethereum", "solana", "chainlink"], start=1):
            rows.append(
                {
                    "rebalance_date": date,
                    "coin_id": coin_id,
                    "universe_rank": rank,
                    "price": 1.0,
                    "market_cap": 10_000_000 / rank,
                    "volume_usd": 1_000_000,
                    "history_days": 100,
                    "symbol": coin_id.upper(),
                    "name": coin_id,
                    "sector": "Layer1",
                }
            )
    return pd.DataFrame(rows)


def test_run_full_window_screen_writes_metrics_for_candidates() -> None:
    market = _script_toy_market()
    config = load_config("config/base.yaml")
    config.start_date = "2024-03-01"
    config.rebalancing.frequencies["14D"] = "14D"
    universe_by_liquidity = {"loose": _script_toy_universe(pd.date_range("2024-03-01", periods=4, freq="14D"))}
    candidates = [
        CandidateDefinition(
            candidate_id="ctrend_lite_test",
            family_id="ctrend_lite",
            strategy_kind="ctrend_lite",
            top_n=1,
            frequency="14D",
            score_family="ctrend_lite_balanced",
            liquidity_label="loose",
            min_history_days=30,
            min_daily_dollar_volume=1_000_000.0,
            include_btc=True,
            overlay_set="no_stop_control",
            risk_off_asset="cash",
            initial_asset="cash",
            stop_kind="none",
            stop_lookback=None,
            stop_confirm_days=1,
            ma_window=None,
        )
    ]

    summary, results = run_full_window_screen(market, universe_by_liquidity, config, candidates)

    assert summary.loc[0, "candidate_id"] == "ctrend_lite_test"
    assert summary.loc[0, "multiple"] > 0
    assert "raw_convexity_score" in summary.columns
    assert "robust_convexity_score" in summary.columns
    assert "ctrend_lite_test" in results
```

- [ ] **Step 2: Run screening tests to verify they fail**

Run:

```bash
pytest tests/test_top20_convex_validation.py::test_run_full_window_screen_writes_metrics_for_candidates -q
```

Expected: failure because `run_full_window_screen` does not exist.

- [ ] **Step 3: Implement full-window screening helpers**

Add these imports to `scripts/run_top20_convex_validation.py` after the existing Atlas20 import:

```python
from atlas20.analytics.metrics import compute_summary_metrics
from atlas20.backtest.engine import BacktestResult, run_backtest
from atlas20.config import FrictionConfig, ResearchConfig
from atlas20.signals.risk import btc_above_moving_average, btc_above_trailing_price
from atlas20.strategies.convex_leader import build_ctrend_lite_targets
from atlas20.strategies.momentum_lead import build_momentum_lead_targets
from atlas20.strategies.overlays import apply_daily_risk_overlay
from atlas20.universe.builder import MarketDataBundle
```

Add these constants after `LEADER_MOMENTUM_SCORE_FAMILIES`:

```python
LEADER_MOMENTUM_WEIGHTS: dict[str, dict[str, float]] = {
    "base": {
        "momentum_rank": 0.45,
        "ret_21_rank": 0.25,
        "ret_42_rank": 0.20,
        "near_high_rank": 0.10,
    },
    "short_accel": {
        "momentum_rank": 0.35,
        "ret_21_rank": 0.35,
        "ret_42_rank": 0.15,
        "near_high_rank": 0.15,
    },
    "breakout": {
        "momentum_rank": 0.30,
        "ret_21_rank": 0.20,
        "ret_42_rank": 0.15,
        "near_high_rank": 0.35,
    },
    "balanced": {
        "momentum_rank": 0.40,
        "ret_21_rank": 0.20,
        "ret_42_rank": 0.20,
        "near_high_rank": 0.20,
    },
}

PARKING_TARGETS: dict[str, pd.Series | None] = {
    "cash": None,
    "btc": pd.Series({"bitcoin": 1.0}),
    "eth": pd.Series({"ethereum": 1.0}),
}
```

Add these functions before `candidate_records()`:

```python
def _risk_on_series(market: MarketDataBundle, candidate: CandidateDefinition) -> pd.Series:
    if candidate.stop_kind == "none":
        return pd.Series(True, index=market.price.index, name="no_stop")
    if candidate.stop_kind == "trailing":
        if candidate.stop_lookback is None:
            raise ValueError(f"{candidate.candidate_id} trailing stop requires stop_lookback")
        return btc_above_trailing_price(
            market.price,
            lookback_days=candidate.stop_lookback,
            confirm_days=candidate.stop_confirm_days,
        )
    if candidate.stop_kind == "ma":
        if candidate.ma_window is None:
            raise ValueError(f"{candidate.candidate_id} MA stop requires ma_window")
        return btc_above_moving_average(
            market.price,
            ma_window=candidate.ma_window,
            confirm_days=candidate.stop_confirm_days,
        )
    raise ValueError(f"Unknown stop_kind for {candidate.candidate_id}: {candidate.stop_kind}")


def _build_base_targets(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    config: ResearchConfig,
    candidate: CandidateDefinition,
) -> dict[pd.Timestamp, pd.Series]:
    if candidate.strategy_kind == "ctrend_lite":
        return build_ctrend_lite_targets(
            market,
            universe,
            config,
            top_n=candidate.top_n,
            frequency=candidate.frequency,
            score_family=candidate.score_family,
            include_btc=candidate.include_btc,
        ).targets
    if candidate.strategy_kind == "leader_momentum":
        regime_frame = pd.DataFrame({"bull": True}, index=market.price.index)
        return build_momentum_lead_targets(
            market,
            universe,
            regime_frame,
            config,
            top_n=candidate.top_n,
            frequency=candidate.frequency,
            regime_mode="always_on",
            weighted=candidate.top_n > 1,
            score_weights=LEADER_MOMENTUM_WEIGHTS[candidate.score_family],
        ).targets
    raise ValueError(f"Unknown strategy_kind for {candidate.candidate_id}: {candidate.strategy_kind}")


def _candidate_targets(
    market: MarketDataBundle,
    universe_by_liquidity: dict[str, pd.DataFrame],
    config: ResearchConfig,
    candidate: CandidateDefinition,
) -> dict[pd.Timestamp, pd.Series]:
    universe = universe_by_liquidity[candidate.liquidity_label]
    base_targets = _build_base_targets(market, universe, config, candidate)
    risk_on = _risk_on_series(market, candidate)
    return apply_daily_risk_overlay(
        base_targets,
        risk_on,
        risk_off_target=PARKING_TARGETS[candidate.risk_off_asset],
        initial_target=PARKING_TARGETS[candidate.initial_asset],
    )


def _friction_with_total_cost(base: FrictionConfig, total_cost_bps: float | None = None) -> FrictionConfig:
    friction = base.model_copy(deep=True)
    if total_cost_bps is not None:
        friction.fee_bps = total_cost_bps / 2.0
        friction.slippage_bps = total_cost_bps / 2.0
    return friction


def run_one_candidate(
    market: MarketDataBundle,
    universe_by_liquidity: dict[str, pd.DataFrame],
    config: ResearchConfig,
    candidate: CandidateDefinition,
    *,
    total_cost_bps: float | None = None,
) -> BacktestResult:
    targets = _candidate_targets(market, universe_by_liquidity, config, candidate)
    return run_backtest(
        name=candidate.candidate_id,
        asset_returns=market.returns,
        rebalance_targets=targets,
        sector_by_coin=market.metadata["sector"],
        friction=_friction_with_total_cost(config.frictions, total_cost_bps),
        initial_capital=config.initial_capital,
        gross_target_exposure=1.0,
    )


def run_full_window_screen(
    market: MarketDataBundle,
    universe_by_liquidity: dict[str, pd.DataFrame],
    config: ResearchConfig,
    candidates: list[CandidateDefinition],
) -> tuple[pd.DataFrame, dict[str, BacktestResult]]:
    rows: list[dict[str, object]] = []
    results: dict[str, BacktestResult] = {}
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}

    for candidate in candidates:
        result = run_one_candidate(market, universe_by_liquidity, config, candidate)
        results[candidate.candidate_id] = result
        metrics = compute_summary_metrics(result, config.annualization_days)
        row = asdict(candidate)
        row.update(metrics)
        row["multiple"] = float(metrics["total_return"]) + 1.0
        row["best_rolling_5y_multiple"] = row["multiple"]
        row["hundred_x_hit_rate_5y"] = 1.0 if row["multiple"] >= 100.0 else 0.0
        row["median_rolling_start_multiple"] = row["multiple"]
        row["cost_survival_100bps"] = 0.0
        row["stability_score"] = 0.0
        rows.append(row)

    summary = pd.DataFrame(rows)
    summary["raw_convexity_score"] = summary.apply(compute_raw_convexity_score, axis=1)
    summary["robust_convexity_score"] = summary.apply(compute_robust_convexity_score, axis=1)
    summary["trial_count_estimate"] = len(candidate_by_id)
    summary = summary.sort_values(["raw_convexity_score", "multiple"], ascending=[False, False]).reset_index(drop=True)
    return summary, results
```

- [ ] **Step 4: Run full-window screening test**

Run:

```bash
pytest tests/test_top20_convex_validation.py::test_run_full_window_screen_writes_metrics_for_candidates -q
```

Expected: test passes.

- [ ] **Step 5: Run all script tests**

Run:

```bash
pytest tests/test_top20_convex_validation.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add scripts/run_top20_convex_validation.py tests/test_top20_convex_validation.py
git commit -m "feat: screen top20 convex candidates"
```

Expected: commit succeeds.

## Task 5: Add Validation Diagnostics

**Files:**

- Modify: `tests/test_top20_convex_validation.py`
- Modify: `scripts/run_top20_convex_validation.py`

- [ ] **Step 1: Add tests for rolling starts, rolling windows, cost stress, stability, and contribution attribution**

Append this code to `tests/test_top20_convex_validation.py`:

```python
from scripts.run_top20_convex_validation import (
    compute_contribution_summary,
    compute_cost_sensitivity,
    compute_rolling_start_validation,
    compute_rolling_window_summary,
    compute_stability_surface,
)


def test_compute_rolling_window_summary_detects_hundred_x_window() -> None:
    dates = pd.date_range("2020-01-01", periods=365 * 5 + 5, freq="D")
    daily_returns = pd.Series(100.0 ** (1.0 / len(dates)) - 1.0, index=dates, name="candidate")

    summary, windows = compute_rolling_window_summary(
        {"candidate": daily_returns},
        windows_days=(365 * 5,),
    )

    assert summary.loc[0, "candidate_id"] == "candidate"
    assert summary.loc[0, "best_rolling_5y_multiple"] >= 99.0
    assert summary.loc[0, "hundred_x_hit_rate_5y"] > 0
    assert not windows.empty


def test_compute_cost_sensitivity_reports_survival_ratio() -> None:
    base_summary = pd.DataFrame(
        [{"candidate_id": "candidate", "multiple": 10.0, "max_drawdown": -0.4}]
    )
    stressed = {
        20.0: {"candidate": 9.0},
        100.0: {"candidate": 6.0},
    }

    result = compute_cost_sensitivity(base_summary, stressed)

    assert set(result["total_cost_bps"]) == {20.0, 100.0}
    assert result[result["total_cost_bps"] == 100.0].iloc[0]["survival_ratio"] == pytest.approx(0.6)


def test_compute_stability_surface_marks_neighbor_region() -> None:
    summary = pd.DataFrame(
        [
            {
                "candidate_id": "a",
                "family_id": "ctrend_lite",
                "top_n": 1,
                "frequency": "14D",
                "stop_lookback": 11,
                "multiple": 50.0,
            },
            {
                "candidate_id": "b",
                "family_id": "ctrend_lite",
                "top_n": 2,
                "frequency": "14D",
                "stop_lookback": 11,
                "multiple": 40.0,
            },
            {
                "candidate_id": "c",
                "family_id": "ctrend_lite",
                "top_n": 1,
                "frequency": "21D",
                "stop_lookback": 12,
                "multiple": 35.0,
            },
        ]
    )

    result = compute_stability_surface(summary, candidate_ids=["a"], multiple_floor=25.0)

    assert result.loc[0, "candidate_id"] == "a"
    assert result.loc[0, "neighbor_count"] == 2
    assert result.loc[0, "stability_score"] > 0


def test_compute_rolling_start_validation_runs_multiple_starts() -> None:
    market = _script_toy_market()
    config = load_config("config/base.yaml")
    config.start_date = "2024-02-01"
    config.rebalancing.frequencies["14D"] = "14D"
    universe_by_liquidity = {"loose": _script_toy_universe(pd.date_range("2024-02-01", periods=5, freq="14D"))}
    candidate = CandidateDefinition(
        candidate_id="ctrend_lite_test",
        family_id="ctrend_lite",
        strategy_kind="ctrend_lite",
        top_n=1,
        frequency="14D",
        score_family="ctrend_lite_balanced",
        liquidity_label="loose",
        min_history_days=30,
        min_daily_dollar_volume=1_000_000.0,
        include_btc=True,
        overlay_set="no_stop_control",
        risk_off_asset="cash",
        initial_asset="cash",
        stop_kind="none",
        stop_lookback=None,
        stop_confirm_days=1,
        ma_window=None,
    )

    summary, by_candidate = compute_rolling_start_validation(
        market,
        universe_by_liquidity,
        config,
        {candidate.candidate_id: candidate},
        [candidate.candidate_id],
        min_days_after_start=30,
    )

    assert summary.loc[0, "candidate_id"] == "ctrend_lite_test"
    assert summary.loc[0, "start_count"] >= 1
    assert {"candidate_id", "start_date", "multiple", "max_drawdown"}.issubset(by_candidate.columns)


def test_compute_contribution_summary_records_top_dependency() -> None:
    market = _script_toy_market()
    dates = market.price.index[:4]
    weights = pd.DataFrame(
        {
            "bitcoin": [0.0, 0.0, 0.0, 0.0],
            "ethereum": [0.0, 0.0, 0.0, 0.0],
            "solana": [1.0, 1.0, 1.0, 1.0],
            "chainlink": [0.0, 0.0, 0.0, 0.0],
        },
        index=dates,
    )
    from atlas20.backtest.engine import BacktestResult

    result = BacktestResult(
        name="candidate",
        daily_returns=pd.Series([0.0, 0.1, 0.1, 0.1], index=dates),
        equity_curve=pd.Series([1.0, 1.1, 1.21, 1.331], index=dates),
        drawdown=pd.Series([0.0, 0.0, 0.0, 0.0], index=dates),
        weights=weights,
        turnover=pd.Series([0.0, 1.0, 0.0, 0.0], index=dates),
        holdings_count=pd.Series([1.0, 1.0, 1.0, 1.0], index=dates),
        sector_exposure=pd.DataFrame(index=dates),
        rebalance_targets=weights,
    )

    summary = compute_contribution_summary({"candidate": result}, market)

    assert summary.loc[0, "candidate_id"] == "candidate"
    assert summary.loc[0, "top_coin_id"] == "solana"
    assert summary.loc[0, "top1_contribution_share"] == pytest.approx(1.0)
```

- [ ] **Step 2: Run diagnostic tests to verify they fail**

Run:

```bash
pytest tests/test_top20_convex_validation.py::test_compute_rolling_window_summary_detects_hundred_x_window tests/test_top20_convex_validation.py::test_compute_cost_sensitivity_reports_survival_ratio tests/test_top20_convex_validation.py::test_compute_stability_surface_marks_neighbor_region tests/test_top20_convex_validation.py::test_compute_rolling_start_validation_runs_multiple_starts tests/test_top20_convex_validation.py::test_compute_contribution_summary_records_top_dependency -q
```

Expected: failure because diagnostic functions do not exist.

- [ ] **Step 3: Extend candidate execution to support alternate start dates**

Change the `run_one_candidate()` signature in `scripts/run_top20_convex_validation.py` to include `start_date`, and replace its body with this code:

```python
def run_one_candidate(
    market: MarketDataBundle,
    universe_by_liquidity: dict[str, pd.DataFrame],
    config: ResearchConfig,
    candidate: CandidateDefinition,
    *,
    total_cost_bps: float | None = None,
    start_date: pd.Timestamp | None = None,
) -> BacktestResult:
    local_config = config.model_copy(deep=True)
    if start_date is not None:
        local_config.start_date = pd.Timestamp(start_date).strftime("%Y-%m-%d")

    targets = _candidate_targets(market, universe_by_liquidity, local_config, candidate)
    returns = market.returns.loc[local_config.start_timestamp :].copy()
    return run_backtest(
        name=candidate.candidate_id,
        asset_returns=returns,
        rebalance_targets=targets,
        sector_by_coin=market.metadata["sector"],
        friction=_friction_with_total_cost(local_config.frictions, total_cost_bps),
        initial_capital=local_config.initial_capital,
        gross_target_exposure=1.0,
    )
```

- [ ] **Step 4: Implement diagnostic functions**

Add these functions to `scripts/run_top20_convex_validation.py` before `run_full_window_screen()`:

```python
def compute_rolling_start_validation(
    market: MarketDataBundle,
    universe_by_liquidity: dict[str, pd.DataFrame],
    config: ResearchConfig,
    candidate_by_id: dict[str, CandidateDefinition],
    candidate_ids: list[str],
    *,
    min_days_after_start: int = 365,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    start_dates = pd.date_range(config.start_timestamp, market.price.index.max(), freq="MS")
    max_start = market.price.index.max() - pd.Timedelta(days=min_days_after_start)

    for candidate_id in candidate_ids:
        candidate = candidate_by_id[candidate_id]
        for start_date in start_dates:
            if start_date > max_start:
                continue
            result = run_one_candidate(
                market,
                universe_by_liquidity,
                config,
                candidate,
                start_date=pd.Timestamp(start_date),
            )
            metrics = compute_summary_metrics(result, config.annualization_days)
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "start_date": pd.Timestamp(start_date).date().isoformat(),
                    "multiple": float(metrics["total_return"]) + 1.0,
                    "cagr": metrics["cagr"],
                    "sharpe": metrics["sharpe"],
                    "max_drawdown": metrics["max_drawdown"],
                    "annualized_turnover": metrics["annualized_turnover"],
                }
            )

    by_candidate = pd.DataFrame(rows)
    if by_candidate.empty:
        return pd.DataFrame(columns=["candidate_id", "start_count"]), by_candidate

    summary = (
        by_candidate.groupby("candidate_id")
        .agg(
            start_count=("start_date", "count"),
            median_rolling_start_multiple=("multiple", "median"),
            min_rolling_start_multiple=("multiple", "min"),
            max_rolling_start_drawdown=("max_drawdown", "min"),
            median_rolling_start_drawdown=("max_drawdown", "median"),
        )
        .reset_index()
    )
    return summary, by_candidate


def compute_rolling_window_summary(
    daily_returns_by_candidate: dict[str, pd.Series],
    *,
    windows_days: tuple[int, ...] = (365 * 3, 365 * 5),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, object]] = []
    window_rows: list[dict[str, object]] = []

    for candidate_id, returns in daily_returns_by_candidate.items():
        clean = pd.to_numeric(returns, errors="coerce").fillna(0.0).sort_index()
        row: dict[str, object] = {"candidate_id": candidate_id}
        for window_days in windows_days:
            label = "3y" if window_days <= 365 * 3 else "5y"
            rolling_multiple = (1.0 + clean).rolling(window_days).apply(lambda values: float(values.prod()), raw=True)
            valid = rolling_multiple.dropna()
            if valid.empty:
                row[f"best_rolling_{label}_multiple"] = 0.0
                row[f"median_rolling_{label}_multiple"] = 0.0
                row[f"hundred_x_hit_rate_{label}"] = 0.0
                continue
            row[f"best_rolling_{label}_multiple"] = float(valid.max())
            row[f"median_rolling_{label}_multiple"] = float(valid.median())
            row[f"hundred_x_hit_rate_{label}"] = float((valid >= 100.0).mean())
            for end_date, multiple in valid[valid >= 100.0].items():
                window_rows.append(
                    {
                        "candidate_id": candidate_id,
                        "window_label": label,
                        "window_end": end_date,
                        "multiple": float(multiple),
                    }
                )
        summary_rows.append(row)

    return pd.DataFrame(summary_rows), pd.DataFrame(window_rows)


def compute_cost_sensitivity(
    base_summary: pd.DataFrame,
    stressed_multiples: dict[float, dict[str, float]],
) -> pd.DataFrame:
    base_by_id = base_summary.set_index("candidate_id")
    rows: list[dict[str, object]] = []
    for total_cost_bps, multiples in stressed_multiples.items():
        for candidate_id, stressed_multiple in multiples.items():
            base_multiple = float(base_by_id.loc[candidate_id, "multiple"])
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "total_cost_bps": float(total_cost_bps),
                    "base_multiple": base_multiple,
                    "stressed_multiple": float(stressed_multiple),
                    "survival_ratio": float(stressed_multiple) / base_multiple if base_multiple > 0 else 0.0,
                }
            )
    return pd.DataFrame(rows)


def compute_stability_surface(
    summary: pd.DataFrame,
    *,
    candidate_ids: list[str],
    multiple_floor: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    indexed = summary.set_index("candidate_id")
    for candidate_id in candidate_ids:
        candidate = indexed.loc[candidate_id]
        same_family = summary[summary["family_id"] == candidate["family_id"]].copy()
        neighbors = same_family[
            (same_family["candidate_id"] != candidate_id)
            & (same_family["multiple"] >= multiple_floor)
            & (
                (same_family["top_n"].sub(int(candidate["top_n"])).abs() <= 1)
                | (same_family["frequency"] == candidate["frequency"])
                | (same_family["stop_lookback"].fillna(-999).sub(float(candidate.get("stop_lookback") or -999)).abs() <= 1)
            )
        ]
        neighbor_count = int(len(neighbors))
        median_neighbor_multiple = float(neighbors["multiple"].median()) if neighbor_count else 0.0
        base_multiple = float(candidate["multiple"])
        stability_score = min(median_neighbor_multiple / base_multiple, 1.0) if base_multiple > 0 else 0.0
        rows.append(
            {
                "candidate_id": candidate_id,
                "neighbor_count": neighbor_count,
                "median_neighbor_multiple": median_neighbor_multiple,
                "stability_score": stability_score,
            }
        )
    return pd.DataFrame(rows)


def compute_contribution_summary(
    results: dict[str, BacktestResult],
    market: MarketDataBundle,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for candidate_id, result in results.items():
        weights = result.weights.reindex(columns=market.returns.columns).fillna(0.0)
        returns = market.returns.reindex(index=weights.index, columns=weights.columns).fillna(0.0)
        contribution = (weights.shift(1).fillna(0.0) * returns).sum(axis=0).sort_values(ascending=False)
        positive = contribution[contribution > 0]
        total_positive = float(positive.sum())
        if total_positive <= 0:
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "top_coin_id": "",
                    "top1_contribution_share": 0.0,
                    "top3_contribution_share": 0.0,
                    "top5_contribution_share": 0.0,
                }
            )
            continue
        rows.append(
            {
                "candidate_id": candidate_id,
                "top_coin_id": str(positive.index[0]),
                "top1_contribution_share": float(positive.head(1).sum() / total_positive),
                "top3_contribution_share": float(positive.head(3).sum() / total_positive),
                "top5_contribution_share": float(positive.head(5).sum() / total_positive),
            }
        )
    return pd.DataFrame(rows)
```

- [ ] **Step 5: Run diagnostic tests**

Run:

```bash
pytest tests/test_top20_convex_validation.py::test_compute_rolling_window_summary_detects_hundred_x_window tests/test_top20_convex_validation.py::test_compute_cost_sensitivity_reports_survival_ratio tests/test_top20_convex_validation.py::test_compute_stability_surface_marks_neighbor_region tests/test_top20_convex_validation.py::test_compute_rolling_start_validation_runs_multiple_starts tests/test_top20_convex_validation.py::test_compute_contribution_summary_records_top_dependency -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Run all validation-script tests**

Run:

```bash
pytest tests/test_top20_convex_validation.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit Task 5**

Run:

```bash
git add scripts/run_top20_convex_validation.py tests/test_top20_convex_validation.py
git commit -m "feat: add convex validation diagnostics"
```

Expected: commit succeeds.

## Task 6: Add CLI Execution And Report Writing

**Files:**

- Modify: `tests/test_top20_convex_validation.py`
- Modify: `scripts/run_top20_convex_validation.py`

- [ ] **Step 1: Add tests for report output**

Append this code to `tests/test_top20_convex_validation.py`:

```python
from scripts.run_top20_convex_validation import write_validation_outputs


def test_write_validation_outputs_creates_required_files(tmp_path: Path) -> None:
    candidate_summary = pd.DataFrame(
        [
            {
                "candidate_id": "candidate",
                "family_id": "ctrend_lite",
                "multiple": 12.0,
                "cagr": 1.2,
                "sharpe": 2.0,
                "max_drawdown": -0.5,
                "raw_convexity_score": 2.0,
                "robust_convexity_score": 1.5,
            }
        ]
    )
    empty = pd.DataFrame()

    write_validation_outputs(
        tmp_path,
        candidate_summary=candidate_summary,
        champion_ablation=empty,
        rolling_start_summary=empty,
        rolling_start_by_candidate=empty,
        rolling_window_summary=empty,
        hundred_x_windows=empty,
        stability_surface=empty,
        cost_sensitivity=empty,
        liquidity_sensitivity=empty,
        contribution_summary=empty,
        trial_log=candidate_summary[["candidate_id", "family_id"]],
    )

    assert (tmp_path / "candidate_summary.csv").exists()
    assert (tmp_path / "candidate_top50_raw.csv").exists()
    assert (tmp_path / "candidate_top50_robust.csv").exists()
    assert (tmp_path / "top20_convex_validation_report.md").exists()
    report = (tmp_path / "top20_convex_validation_report.md").read_text(encoding="utf-8")
    assert "Best Raw Convexity Candidate" in report
    assert "candidate" in report
```

- [ ] **Step 2: Run report test to verify it fails**

Run:

```bash
pytest tests/test_top20_convex_validation.py::test_write_validation_outputs_creates_required_files -q
```

Expected: failure because `write_validation_outputs` does not exist.

- [ ] **Step 3: Implement report output helper**

Add this import to `scripts/run_top20_convex_validation.py`:

```python
from atlas20.reporting.report import dataframe_to_markdown
```

Add this function before `main()`:

```python
def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _markdown_section(title: str, frame: pd.DataFrame, columns: list[str]) -> list[str]:
    if frame.empty:
        return [f"## {title}", "", "No rows.", ""]
    available = [column for column in columns if column in frame.columns]
    return [
        f"## {title}",
        "",
        dataframe_to_markdown(
            frame.head(10)[available],
            percent_columns={"cagr", "max_drawdown"},
            number_columns={"multiple", "sharpe", "raw_convexity_score", "robust_convexity_score"},
        ),
        "",
    ]


def write_validation_outputs(
    report_dir: Path,
    *,
    candidate_summary: pd.DataFrame,
    champion_ablation: pd.DataFrame,
    rolling_start_summary: pd.DataFrame,
    rolling_start_by_candidate: pd.DataFrame,
    rolling_window_summary: pd.DataFrame,
    hundred_x_windows: pd.DataFrame,
    stability_surface: pd.DataFrame,
    cost_sensitivity: pd.DataFrame,
    liquidity_sensitivity: pd.DataFrame,
    contribution_summary: pd.DataFrame,
    trial_log: pd.DataFrame,
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    raw_top50 = candidate_summary.sort_values("raw_convexity_score", ascending=False).head(50)
    robust_top50 = candidate_summary.sort_values("robust_convexity_score", ascending=False).head(50)

    outputs = {
        "candidate_summary.csv": candidate_summary,
        "candidate_top50_raw.csv": raw_top50,
        "candidate_top50_robust.csv": robust_top50,
        "champion_ablation.csv": champion_ablation,
        "rolling_start_summary.csv": rolling_start_summary,
        "rolling_start_by_candidate.csv": rolling_start_by_candidate,
        "rolling_window_summary.csv": rolling_window_summary,
        "hundred_x_windows.csv": hundred_x_windows,
        "stability_surface.csv": stability_surface,
        "cost_sensitivity.csv": cost_sensitivity,
        "liquidity_sensitivity.csv": liquidity_sensitivity,
        "contribution_summary.csv": contribution_summary,
        "trial_log.csv": trial_log,
    }
    for filename, frame in outputs.items():
        _write_csv(report_dir / filename, frame)

    markdown_lines: list[str] = [
        "# Top20 Convex Leader Validation",
        "",
        "This report ranks high-convexity Top20 candidate strategies and separates raw upside from robustness.",
        "",
    ]
    markdown_lines.extend(
        _markdown_section(
            "Best Raw Convexity Candidate",
            raw_top50,
            ["candidate_id", "family_id", "multiple", "cagr", "sharpe", "max_drawdown", "raw_convexity_score"],
        )
    )
    markdown_lines.extend(
        _markdown_section(
            "Best Robust Convexity Candidate",
            robust_top50,
            ["candidate_id", "family_id", "multiple", "cagr", "sharpe", "max_drawdown", "robust_convexity_score"],
        )
    )
    markdown_lines.extend(
        _markdown_section(
            "100x Rolling Windows",
            hundred_x_windows,
            ["candidate_id", "window_label", "window_end", "multiple"],
        )
    )
    markdown_lines.extend(
        [
            "## Notes",
            "",
            "- Raw convexity emphasizes upside.",
            "- Robust convexity emphasizes rolling-start stability, cost survival, drawdown, and parameter neighborhood strength.",
            "- This is research output only and does not execute trades.",
            "",
        ]
    )
    (report_dir / "top20_convex_validation_report.md").write_text("\n".join(markdown_lines), encoding="utf-8")
```

- [ ] **Step 4: Run report output test**

Run:

```bash
pytest tests/test_top20_convex_validation.py::test_write_validation_outputs_creates_required_files -q
```

Expected: test passes.

- [ ] **Step 5: Implement real CLI orchestration**

Replace `main()` in `scripts/run_top20_convex_validation.py` with this code:

```python
def _all_rebalance_dates(index: pd.DatetimeIndex, config: ResearchConfig) -> list[pd.Timestamp]:
    from atlas20.backtest.calendar import get_rebalance_dates

    dates: set[pd.Timestamp] = set()
    for frequency_name, frequency_value in config.rebalancing.frequencies.items():
        dates.update(get_rebalance_dates(index, config.start_timestamp, frequency_name, frequency_value))
    for frequency in ("7D", "14D", "21D", "28D"):
        dates.update(get_rebalance_dates(index, config.start_timestamp, frequency, frequency))
    return sorted(dates)


def _build_universe_variants(market: MarketDataBundle, config: ResearchConfig) -> dict[str, pd.DataFrame]:
    from atlas20.universe.builder import build_rebalance_universe

    universe_by_liquidity: dict[str, pd.DataFrame] = {}
    rebalance_dates = _all_rebalance_dates(market.price.index, config)
    for liquidity_label, (min_history_days, min_daily_dollar_volume) in LIQUIDITY_SETS.items():
        local_config = config.model_copy(deep=True)
        local_config.universe.min_history_days = min_history_days
        local_config.universe.min_daily_dollar_volume = min_daily_dollar_volume
        universe_by_liquidity[liquidity_label] = build_rebalance_universe(market, rebalance_dates, local_config)
    return universe_by_liquidity


def main() -> None:
    from atlas20.config import load_config, load_sector_config
    from atlas20.data.processor import build_processed_datasets
    from atlas20.logging_utils import configure_logging, ensure_dir
    from atlas20.universe.builder import prepare_market_data

    parser = argparse.ArgumentParser(description="Run Top20 convex leader validation.")
    parser.add_argument("--config", default="config/bear_bottom_to_current_2022_11_21_2026_04_22.yaml")
    parser.add_argument("--max-validation-candidates", type=int, default=60)
    parser.add_argument("--min-multiple-for-validation", type=float, default=25.0)
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(config.logging.level)
    sector_config = load_sector_config(config.resolve_path("config/sectors.yaml"))
    panel, metadata = build_processed_datasets(config, sector_config)
    market = prepare_market_data(panel, metadata, config)
    universe_by_liquidity = _build_universe_variants(market, config)
    candidates = build_candidate_definitions()

    candidate_summary, results = run_full_window_screen(market, universe_by_liquidity, config, candidates)
    champion_id = "champion_ablation__leader_momentum__top1__14d__base__loose__with_btc__champion_ablation_stop11"
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    validation_ids = select_validation_candidates(
        candidate_summary,
        champion_candidate_id=champion_id,
        max_validation_candidates=args.max_validation_candidates,
        min_multiple_for_validation=args.min_multiple_for_validation,
    )

    daily_returns = {candidate_id: results[candidate_id].daily_returns for candidate_id in validation_ids if candidate_id in results}
    rolling_window_summary, hundred_x_windows = compute_rolling_window_summary(daily_returns)
    rolling_start_summary, rolling_start_by_candidate = compute_rolling_start_validation(
        market,
        universe_by_liquidity,
        config,
        candidate_by_id,
        validation_ids,
    )
    stability_surface = compute_stability_surface(
        candidate_summary,
        candidate_ids=validation_ids,
        multiple_floor=args.min_multiple_for_validation,
    )

    stressed: dict[float, dict[str, float]] = {}
    for total_cost_bps in (20.0, 50.0, 100.0, 150.0):
        stressed[total_cost_bps] = {}
        for candidate_id in validation_ids:
            result = run_one_candidate(
                market,
                universe_by_liquidity,
                config,
                candidate_by_id[candidate_id],
                total_cost_bps=total_cost_bps,
            )
            stressed[total_cost_bps][candidate_id] = compute_summary_metrics(result, config.annualization_days)["total_return"] + 1.0
    cost_sensitivity = compute_cost_sensitivity(candidate_summary, stressed)

    report_dir = ensure_dir(config.resolve_path(config.paths.reports_dir) / "top20_convex_validation")
    champion_ablation = candidate_summary[candidate_summary["family_id"] == "champion_ablation"].copy()
    liquidity_sensitivity = candidate_summary[
        ["candidate_id", "family_id", "liquidity_label", "multiple", "max_drawdown", "annualized_turnover"]
    ].copy()
    validation_results = {candidate_id: results[candidate_id] for candidate_id in validation_ids if candidate_id in results}
    contribution_summary = compute_contribution_summary(validation_results, market)
    trial_log = candidate_records(candidates)

    write_validation_outputs(
        report_dir,
        candidate_summary=candidate_summary,
        champion_ablation=champion_ablation,
        rolling_start_summary=rolling_start_summary,
        rolling_start_by_candidate=rolling_start_by_candidate,
        rolling_window_summary=rolling_window_summary,
        hundred_x_windows=hundred_x_windows,
        stability_surface=stability_surface,
        cost_sensitivity=cost_sensitivity,
        liquidity_sensitivity=liquidity_sensitivity,
        contribution_summary=contribution_summary,
        trial_log=trial_log,
    )
```

- [ ] **Step 6: Run focused report and script tests**

Run:

```bash
pytest tests/test_top20_convex_validation.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Run the validation script on the bear-bottom config**

Run:

```bash
python scripts/run_top20_convex_validation.py --config config/bear_bottom_to_current_2022_11_21_2026_04_22.yaml --max-validation-candidates 20
```

Expected:

- Command exits with status 0.
- `reports/bear_bottom_to_current_2022_11_21_2026_04_22/top20_convex_validation/candidate_summary.csv` exists.
- `reports/bear_bottom_to_current_2022_11_21_2026_04_22/top20_convex_validation/top20_convex_validation_report.md` exists.

- [ ] **Step 8: Commit Task 6**

Run:

```bash
git add scripts/run_top20_convex_validation.py tests/test_top20_convex_validation.py reports/bear_bottom_to_current_2022_11_21_2026_04_22/top20_convex_validation
git commit -m "feat: write top20 convex validation report"
```

Expected: commit succeeds.

## Task 7: Final Verification

**Files:**

- No planned file changes.

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
pytest tests/test_convex_leader.py tests/test_top20_convex_validation.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run existing core research tests touched by this work**

Run:

```bash
pytest tests/test_engine.py tests/test_generate_report.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run Ruff on new and touched files**

Run:

```bash
ruff check src/atlas20/strategies/convex_leader.py scripts/run_top20_convex_validation.py tests/test_convex_leader.py tests/test_top20_convex_validation.py
```

Expected: no Ruff violations.

- [ ] **Step 4: Run the script once with the main target config**

Run:

```bash
python scripts/run_top20_convex_validation.py --config config/bear_bottom_to_current_2022_11_21_2026_04_22.yaml --max-validation-candidates 20
```

Expected:

- The script exits with status 0.
- `candidate_summary.csv` has more than 100 rows.
- `candidate_top50_raw.csv` has at least one `ctrend_lite` candidate.
- `candidate_top50_robust.csv` has at least one candidate.
- `top20_convex_validation_report.md` contains `Best Raw Convexity Candidate`.

- [ ] **Step 5: Inspect the top results**

Run:

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd

root = Path("reports/bear_bottom_to_current_2022_11_21_2026_04_22/top20_convex_validation")
summary = pd.read_csv(root / "candidate_summary.csv")
print(summary[["candidate_id", "family_id", "multiple", "max_drawdown", "raw_convexity_score", "robust_convexity_score"]].head(10).to_string(index=False))
PY
```

Expected:

- The output prints 10 candidate rows.
- The table includes `multiple`, `max_drawdown`, `raw_convexity_score`, and `robust_convexity_score`.

- [ ] **Step 6: Final commit if verification caused report changes**

Run:

```bash
git status --short
```

Expected:

- If only intended report artifacts changed, commit them with:

```bash
git add reports/bear_bottom_to_current_2022_11_21_2026_04_22/top20_convex_validation
git commit -m "chore: refresh top20 convex validation outputs"
```

- If no files changed, do not create an empty commit.

## Plan Self-Review

Spec coverage:

- Current champion validation is covered by `champion_ablation` candidates, report outputs, and the champion validation subset.
- Candidate discovery is covered by `ctrend_lite` candidates and raw/robust rankings.
- Top20 liquidity is covered by loose, medium, and strict liquidity sets.
- Cost stress is covered by `compute_cost_sensitivity()` and CLI stress reruns.
- Rolling 3-year and 5-year windows are covered by `compute_rolling_window_summary()`.
- Parameter stability is covered by `compute_stability_surface()`.
- Trial logging is covered by `candidate_records()` and `trial_log.csv`.
- Default pipeline isolation is covered by avoiding changes to `run_research.py`, `momentum_lead.py`, and the engine.

Known scope notes:

- The first implementation uses an approximate coin contribution method based on previous-day portfolio weights multiplied by same-day asset returns. This is sufficient for dependency checks; exact trade-level attribution can be added only if the engine later records per-fill execution data.

Verification commands:

- `pytest tests/test_convex_leader.py tests/test_top20_convex_validation.py -q`
- `pytest tests/test_engine.py tests/test_generate_report.py -q`
- `ruff check src/atlas20/strategies/convex_leader.py scripts/run_top20_convex_validation.py tests/test_convex_leader.py tests/test_top20_convex_validation.py`
- `python scripts/run_top20_convex_validation.py --config config/bear_bottom_to_current_2022_11_21_2026_04_22.yaml --max-validation-candidates 20`
