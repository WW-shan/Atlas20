# Atlas20 Top50 Data Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每个交易日复用一个已存在的 Top20 时，先确保可执行 Top50 的 CMC、Bitget warmup mark/market、live OOS mark/market 和 exact funding 证据完整，并通过幂等 Telegram 事件报告成员变化和阻断原因。

**Architecture:** 新模块只在现有 `panel_daily.csv`、`symbol_map.csv`、`candles/*_mark.csv`、`candles/*_market.csv`、`funding/*.csv` 上做选择和审计，不定义第二套行情格式。CMC 排名继续调用 `prepare_market_data` 与 `build_rebalance_universe`；Bitget 审计继续调用 `audit_derivatives_data`，只是用当日 Top50 子集生成 scoped panel/map 输入。无合约成员先跳过并顺延，已有合约但证据不完整的成员会阻断该日 readiness，不会自动用第 51 名掩盖故障。

**Tech Stack:** Python 3.11、pandas、pydantic、filelock、pytest、ruff、mypy API scope、macOS launchd、现有 Telegram sender。

**Spec:** `docs/superpowers/specs/2026-11-17-top50-data-readiness-design.md`

## Global Constraints

- 当前 live track 保持 `PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090`；本功能不得改写它的 state、journal、manifest、target、stop 或 Telegram state。
- 当前 live 参数保持 H5 long book、LS23 0.50x short request、21D stronger-holder redistribution、1.75x target gross、0.90 margin cap、isolated margin、50% initial buffers per leg、4x venue leverage。
- “无合约跳过并递补”改变 universe 语义，本计划只生成独立 readiness evidence/handoff，不自动把新 universe 规则提升为 live track。
- CMC 是唯一 ranking authority；不得用 CoinGecko、当前名称或人工列表回填当日排名。
- 不要求上市前数据；从资产首条真实可用 bar 起，内部缺口和非尾部缺失必须 fail closed。
- funding 只使用现有 Bitget exact cache；不补零，不伪造 2022 年以前 funding，live OOS 必须完整。
- 每日只做一次主构建；仅在现有 bounded prepare/catch-up 流程内重试，不做盘中高频扫描。
- 所有 state/report 写入必须原子替换；相同 `(event, coin_id, as_of)` 最多成功通知一次。
- 首次初始化只建立基线，不发送 50 条历史进入通知。
- 所有 Python 命令使用 `.venv/bin/python`；使用 `make test`, `make lint`, `make typecheck`。
- 真实数据核验从 `/Users/ww/Project/Atlas20` 只读读取；代码开发和提交在 `/Users/ww/.codex/worktrees/e0f9/Atlas20`。

---

## File Structure

- Create `src/atlas20/derivatives/top50_readiness.py`
  - Top50 membership selection, per-file coverage evidence, scoped audit, snapshot/state/notification primitives.
- Create `scripts/run_top50_readiness.py`
  - CLI, panel freshness gate, one-time backfill orchestration, state/report publication and Telegram delivery.
- Modify `scripts/refresh_derivatives_data.py`
  - Add the readiness step to the existing prepare sequence before the frozen LS104 signal rebuild.
- Modify `Makefile`
  - Add locked and parent-locked readiness targets.
- Create `ops/run_top50_readiness.sh`
  - Manual/daily entry point that sources only Telegram credentials and never trading credentials.
- Create `ops/com.atlas20.top50-readiness.plist`
  - Optional launchd wrapper if the owner later chooses a separate job; default live prepare already invokes readiness.
- Modify `docs/operations/derivatives_live_runbook.md`
  - Exact daily sequence, blockers, report paths and manual recovery.
- Modify `RESEARCH.md`
  - Record the data-readiness milestone and that executable-universe promotion remains separate.
- Create/modify tests:
  - `tests/test_top50_readiness.py`
  - `tests/test_run_top50_readiness.py`
  - `tests/test_launchd_top50_schedule.py`
  - `tests/test_refresh_derivatives_data.py`

---

### Task 1: Executable Top50 Selection

**Files:**
- Create: `src/atlas20/derivatives/top50_readiness.py`
- Test: `tests/test_top50_readiness.py`

**Interfaces:**
- Consumes: ranked DataFrame columns `coin_id`, `symbol`, `universe_rank`; symbol-map DataFrame columns `coin_id`, `panel_symbol`, `bitget_symbol`, `contract_status`.
- Produces:
  - `TOP50_SIZE: int`
  - `TOP20_SIZE: int`
  - `SelectionMember(final_rank, original_rank, coin_id, symbol, bitget_symbol, panel_symbol)`
  - `SelectionSkip(original_rank, coin_id, symbol, reason)`
  - `Top50Selection(as_of, candidate_count, members, skipped, source_fingerprint)`
  - `select_executable_top50(ranked, symbol_map, *, as_of: date, size: int = TOP50_SIZE) -> Top50Selection`

- [ ] **Step 1: Write failing selection tests**

```python
from datetime import date

import pandas as pd
import pytest

from atlas20.derivatives.top50_readiness import select_executable_top50


def _ranked(count: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "coin_id": [f"coin-{index}" for index in range(1, count + 1)],
            "symbol": [f"C{index}" for index in range(1, count + 1)],
            "universe_rank": range(1, count + 1),
        }
    )


def _mapped(ranked: pd.DataFrame, missing_ranks: set[int]) -> pd.DataFrame:
    rows = []
    for row in ranked.to_dict("records"):
        rank = int(row["universe_rank"])
        missing = rank in missing_ranks
        rows.append(
            {
                "coin_id": row["coin_id"],
                "panel_symbol": row["symbol"],
                "bitget_symbol": "" if missing else f"{row['symbol']}USDT",
                "contract_status": "missing" if missing else "normal",
            }
        )
    return pd.DataFrame(rows)


def test_selection_skips_missing_contracts_and_backfills_to_fifty() -> None:
    ranked = _ranked(52)
    result = select_executable_top50(
        ranked,
        _mapped(ranked, {2, 7}),
        as_of=date(2026, 11, 15),
    )

    assert len(result.members) == 50
    assert [row.final_rank for row in result.members] == list(range(1, 51))
    assert [row.original_rank for row in result.members][-2:] == [51, 52]
    assert [(row.original_rank, row.reason) for row in result.skipped] == [
        (2, "VENUE_UNAVAILABLE"),
        (7, "VENUE_UNAVAILABLE"),
    ]


def test_selection_fails_closed_when_ranked_pool_cannot_fill_fifty() -> None:
    ranked = _ranked(51)
    with pytest.raises(ValueError, match="only 49 executable"):
        select_executable_top50(
            ranked,
            _mapped(ranked, {2, 7}),
            as_of=date(2026, 11, 15),
        )


def test_selection_rejects_two_coin_ids_on_the_same_contract() -> None:
    ranked = _ranked(50)
    mapping = _mapped(ranked, set())
    mapping.loc[1, "bitget_symbol"] = mapping.loc[0, "bitget_symbol"]
    with pytest.raises(ValueError, match="duplicate Bitget contract"):
        select_executable_top50(ranked, mapping, as_of=date(2026, 11, 15))


def test_selection_rejects_duplicate_coin_or_rank() -> None:
    ranked = _ranked(50)
    ranked.loc[1, "coin_id"] = ranked.loc[0, "coin_id"]
    with pytest.raises(ValueError, match="duplicate coin_id"):
        select_executable_top50(ranked, _mapped(ranked, set()), as_of=date(2026, 11, 15))
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_top50_readiness.py -q`

Expected: collection failure because `atlas20.derivatives.top50_readiness` does not exist.

- [ ] **Step 3: Implement dataclasses and selector**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json

import pandas as pd

TOP50_SIZE = 50
TOP20_SIZE = 20
VENUE_UNAVAILABLE = "VENUE_UNAVAILABLE"


@dataclass(frozen=True)
class SelectionMember:
    final_rank: int
    original_rank: int
    coin_id: str
    symbol: str
    bitget_symbol: str
    panel_symbol: str


@dataclass(frozen=True)
class SelectionSkip:
    original_rank: int
    coin_id: str
    symbol: str
    reason: str


@dataclass(frozen=True)
class Top50Selection:
    as_of: date
    candidate_count: int
    members: tuple[SelectionMember, ...]
    skipped: tuple[SelectionSkip, ...]
    source_fingerprint: str


def _source_fingerprint(ranked: pd.DataFrame, symbol_map: pd.DataFrame) -> str:
    payload = {
        "ranked": ranked.sort_values("universe_rank").to_dict("records"),
        "map": symbol_map.sort_values("coin_id").to_dict("records"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def select_executable_top50(
    ranked: pd.DataFrame,
    symbol_map: pd.DataFrame,
    *,
    as_of: date,
    size: int = TOP50_SIZE,
) -> Top50Selection:
    required = {"coin_id", "symbol", "universe_rank"}
    missing = required.difference(ranked.columns)
    if missing:
        raise ValueError(f"ranked is missing columns {sorted(missing)}")
    if size <= 0:
        raise ValueError("size must be positive")
    if ranked["coin_id"].astype(str).duplicated().any():
        raise ValueError("ranked contains a duplicate coin_id")
    if ranked["universe_rank"].astype(int).duplicated().any():
        raise ValueError("ranked contains a duplicate universe_rank")
    mapping = symbol_map.drop_duplicates("coin_id", keep="last").set_index("coin_id")
    members: list[SelectionMember] = []
    skipped: list[SelectionSkip] = []
    used_symbols: set[str] = set()
    for row in ranked.sort_values("universe_rank").to_dict("records"):
        original_rank = int(row["universe_rank"])
        coin_id = str(row["coin_id"]).strip()
        symbol = str(row["symbol"]).strip().upper()
        mapped = mapping.loc[coin_id] if coin_id in mapping.index else None
        venue_symbol = "" if mapped is None else str(mapped.get("bitget_symbol") or "").strip().upper()
        status = "" if mapped is None else str(mapped.get("contract_status") or "").strip().lower()
        if status != "normal" or not venue_symbol:
            skipped.append(SelectionSkip(original_rank, coin_id, symbol, VENUE_UNAVAILABLE))
            continue
        if venue_symbol in used_symbols:
            raise ValueError(f"duplicate Bitget contract {venue_symbol} in executable top50")
        used_symbols.add(venue_symbol)
        members.append(
            SelectionMember(
                final_rank=len(members) + 1,
                original_rank=original_rank,
                coin_id=coin_id,
                symbol=symbol,
                bitget_symbol=venue_symbol,
                panel_symbol="" if mapped is None else str(mapped.get("panel_symbol") or ""),
            )
        )
        if len(members) == size:
            break
    if len(members) != size:
        raise ValueError(
            f"ranked pool has only {len(members)} executable member(s), require {size}"
        )
    return Top50Selection(
        as_of=as_of,
        candidate_count=len(ranked),
        members=tuple(members),
        skipped=tuple(skipped),
        source_fingerprint=_source_fingerprint(ranked, symbol_map),
    )
```

- [ ] **Step 4: Run tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_top50_readiness.py -q`

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/atlas20/derivatives/top50_readiness.py tests/test_top50_readiness.py
git commit -m "feat: add executable top50 selection"
```

---

### Task 2: Point-in-Time Candidate Ranking

**Files:**
- Modify: `src/atlas20/derivatives/top50_readiness.py`
- Test: `tests/test_top50_readiness.py`

**Interfaces:**
- Consumes: existing `load_config`, `prepare_market_data`, `build_rebalance_universe`.
- Produces:
  - `rank_current_candidates(*, config_path: Path, panel_path: Path, metadata_path: Path, as_of: date, limit: int) -> pd.DataFrame`
  - Output is the existing universe-builder schema sorted by `universe_rank`.

- [ ] **Step 1: Add failing ranking tests**

```python
def test_rank_current_candidates_delegates_to_existing_universe_builder(
    tmp_path, monkeypatch
) -> None:
    import atlas20.derivatives.top50_readiness as readiness

    captured: dict[str, object] = {}
    config = type(
        "Config",
        (),
        {
            "model_copy": lambda self, deep=True: self,
            "universe": type("Universe", (), {"universe_size": 60})(),
        },
    )()

    panel = pd.DataFrame({"coin_id": ["bitcoin"], "date": ["2026-11-15"]})
    metadata = pd.DataFrame({"coin_id": ["bitcoin"], "sector": ["Other"]})
    market = type(
        "Market",
        (),
        {"price": pd.DataFrame(index=pd.DatetimeIndex(["2026-11-15"], tz="UTC"))},
    )()
    monkeypatch.setattr(readiness, "load_config", lambda _path: config)
    monkeypatch.setattr(
        readiness.pd,
        "read_csv",
        lambda path: panel if "panel" in str(path) else metadata,
    )
    monkeypatch.setattr(readiness, "prepare_market_data", lambda _panel, _metadata, _cfg: market)
    monkeypatch.setattr(
        readiness,
        "build_rebalance_universe",
        lambda _market, days, cfg: captured.update(days=days, size=cfg.universe.universe_size)
        or _ranked(60),
    )

    result = readiness.rank_current_candidates(
        config_path=tmp_path / "base.yaml",
        panel_path=tmp_path / "panel.csv",
        metadata_path=tmp_path / "metadata.csv",
        as_of=date(2026, 11, 15),
        limit=60,
    )

    assert captured == {"days": [pd.Timestamp("2026-11-15")], "size": 60}
    assert result["universe_rank"].tolist() == list(range(1, 61))
```

- [ ] **Step 2: Run test and verify RED**

Run: `.venv/bin/python -m pytest tests/test_top50_readiness.py::test_rank_current_candidates_delegates_to_existing_universe_builder -q`

Expected: `AttributeError: rank_current_candidates`.

- [ ] **Step 3: Implement ranking by using the production builder**

```python
from pathlib import Path
from atlas20.config import load_config
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data


def rank_current_candidates(
    *,
    config_path: Path,
    panel_path: Path,
    metadata_path: Path,
    as_of: date,
    limit: int,
) -> pd.DataFrame:
    if limit <= 0:
        raise ValueError("limit must be positive")
    config = load_config(config_path).model_copy(deep=True)
    config.universe.universe_size = int(limit)
    panel = pd.read_csv(panel_path)
    metadata = pd.read_csv(metadata_path).set_index("coin_id")
    market = prepare_market_data(panel, metadata, config)
    day = pd.Timestamp(as_of).normalize()
    if day not in market.price.index:
        raise ValueError(f"panel has no ranking row for {as_of}")
    ranked = build_rebalance_universe(market, [day], config)
    if ranked.empty:
        raise ValueError(f"no eligible CMC candidates on {as_of}")
    return ranked.sort_values("universe_rank").reset_index(drop=True)
```

- [ ] **Step 4: Run the focused test**

Run: `.venv/bin/python -m pytest tests/test_top50_readiness.py::test_rank_current_candidates_delegates_to_existing_universe_builder -q`

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/atlas20/derivatives/top50_readiness.py tests/test_top50_readiness.py
git commit -m "feat: rank top50 with production universe builder"
```

---

### Task 3: Per-Member Evidence Checks

**Files:**
- Modify: `src/atlas20/derivatives/top50_readiness.py`
- Test: `tests/test_top50_readiness.py`

**Interfaces:**
- Produces:
  - `CoverageEvidence(first, last, rows, missing_intervals, failures)`
  - `MemberEvidence(cmc, warmup_mark, warmup_market, live_mark, live_market, funding, status, failure_details)`
  - `check_panel_history(panel, *, coin_id: str, latest_day: date) -> CoverageEvidence`
  - `check_mark_coverage(path, *, start, required_end, allow_late_first_bar: bool) -> CoverageEvidence`
  - `check_market_execution_coverage(path, *, required_first_day, end_day, execution_utc=time(1, 5), max_lag_minutes=60) -> CoverageEvidence`
  - `check_market_alignment(market_path, mark_paths) -> CoverageEvidence`
  - `check_funding_coverage(path, *, required_start, required_end, interval_hours) -> CoverageEvidence`
  - `collect_member_evidence(...) -> MemberEvidence`
  - `assess_selection(...) -> tuple[dict[str, object], set[str]]`

- [ ] **Step 1: Write failing coverage tests**

```python
def _ohlc(times: list[str]) -> pd.DataFrame:
    index = pd.to_datetime(times, utc=True)
    return pd.DataFrame(
        {
            "open_time": index,
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.0,
        }
    )


def test_mark_coverage_rejects_interior_gap(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import check_mark_coverage

    path = tmp_path / "BTC_mark.csv"
    _ohlc(["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z", "2026-01-01T03:00:00Z"]).to_csv(path, index=False)
    result = check_mark_coverage(
        path,
        start=pd.Timestamp("2026-01-01T00:00:00Z"),
        required_end=pd.Timestamp("2026-01-01T04:00:00Z"),
        allow_late_first_bar=False,
    )
    assert result.missing_intervals == 1
    assert any("missing hour" in item for item in result.failures)


def test_market_coverage_requires_one_usable_floor_bar_per_execution_day(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import check_market_execution_coverage

    path = tmp_path / "BTC_market.csv"
    _ohlc(["2026-01-01T01:00:00Z", "2026-01-03T01:00:00Z"]).to_csv(path, index=False)
    result = check_market_execution_coverage(
        path,
        required_first_day=date(2026, 1, 1),
        end_day=date(2026, 1, 3),
    )
    assert result.missing_intervals == 1
    assert any("2026-01-02" in item for item in result.failures)


def test_panel_coverage_rejects_missing_completed_day() -> None:
    from atlas20.derivatives.top50_readiness import check_panel_history

    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-03"], utc=True),
            "coin_id": ["bitcoin", "bitcoin"],
            "price": [1.0, 1.0],
            "volume_usd": [10.0, 10.0],
            "market_cap": [100.0, 100.0],
        }
    )
    result = check_panel_history(panel, coin_id="bitcoin", latest_day=date(2026, 1, 3))
    assert result.missing_intervals == 1
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_top50_readiness.py -q -k 'coverage'`

Expected: import failures for the three missing functions.

- [ ] **Step 3: Implement coverage primitives**

```python
from datetime import time
import math


@dataclass(frozen=True)
class CoverageEvidence:
    first: str | None
    last: str | None
    rows: int
    missing_intervals: int
    failures: tuple[str, ...]


def _failure(first: str | None, last: str | None, rows: int, failures: list[str]) -> CoverageEvidence:
    return CoverageEvidence(first, last, rows, sum("missing hour" in item for item in failures), tuple(failures))


def check_panel_history(panel: pd.DataFrame, *, coin_id: str, latest_day: date) -> CoverageEvidence:
    selected = panel.loc[panel["coin_id"].astype(str).eq(coin_id)].copy()
    failures: list[str] = []
    if selected.empty:
        return CoverageEvidence(None, None, 0, 0, ("missing CMC history",))
    selected["date"] = pd.to_datetime(selected["date"], utc=True, errors="coerce").dt.normalize()
    if selected["date"].isna().any():
        failures.append("invalid CMC date")
    if selected["date"].duplicated().any():
        failures.append("duplicate CMC date")
    for column in ("price", "market_cap", "volume_usd"):
        selected[column] = pd.to_numeric(selected[column], errors="coerce")
    if not (selected["price"] > 0).all():
        failures.append("non-positive CMC price")
    if not (selected["market_cap"] > 0).all():
        failures.append("non-positive CMC market cap")
    if not (selected["volume_usd"] >= 0).all():
        failures.append("negative CMC volume")
    dates = pd.DatetimeIndex(selected["date"].dropna().sort_values().unique())
    if dates.empty:
        return CoverageEvidence(None, None, len(selected), 0, tuple(failures + ["no valid CMC dates"]))
    expected = pd.date_range(dates.min(), pd.Timestamp(latest_day, tz="UTC"), freq="D")
    missing = expected.difference(dates)
    failures.extend(f"missing CMC day {item.date().isoformat()}" for item in missing)
    if dates.max().date() != latest_day:
        failures.append(f"CMC series ends {dates.max().date()}, require {latest_day}")
    return CoverageEvidence(
        first=dates.min().isoformat(),
        last=dates.max().isoformat(),
        rows=len(selected),
        missing_intervals=len(missing),
        failures=tuple(failures),
    )


def check_mark_coverage(
    path: Path,
    *,
    start: pd.Timestamp,
    required_end: pd.Timestamp,
    allow_late_first_bar: bool,
) -> CoverageEvidence:
    if not path.is_file():
        return CoverageEvidence(None, None, 0, 0, (f"missing mark file {path}",))
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        return CoverageEvidence(None, None, 0, 0, (f"unreadable mark file: {exc}",))
    if not {"open_time", "open", "high", "low", "close"}.issubset(frame.columns):
        return CoverageEvidence(None, None, len(frame), 0, ("missing OHLC columns",))
    times = pd.DatetimeIndex(pd.to_datetime(frame["open_time"], utc=True, errors="coerce"))
    numeric = frame.loc[:, ["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    failures: list[str] = []
    if times.isna().any() or numeric.isna().any().any():
        failures.append("invalid mark row")
    clean_times = times.dropna().sort_values()
    if clean_times.duplicated().any():
        failures.append("duplicate mark timestamp")
    clean = numeric.dropna().copy()
    clean.index = times[numeric.notna().all(axis=1)]
    clean = clean.sort_index()
    if (clean <= 0).any().any():
        failures.append("non-positive mark price")
    if ((clean["high"] < clean[["open", "close", "low"]].max(axis=1)) | (clean["low"] > clean[["open", "close", "high"]].min(axis=1))).any():
        failures.append("invalid mark OHLC")
    if clean_times.empty:
        return CoverageEvidence(None, None, len(frame), 0, tuple(failures + ["empty mark file"]))
    effective_start = clean_times.min() if allow_late_first_bar else pd.Timestamp(start)
    if not allow_late_first_bar and clean_times.min() > pd.Timestamp(start):
        failures.append(f"mark starts {clean_times.min()}, require {start}")
    end = pd.Timestamp(required_end)
    expected = pd.date_range(effective_start, end, freq="h", inclusive="left")
    missing = expected.difference(clean_times)
    failures.extend(f"missing hour {item.isoformat()}" for item in missing)
    if clean_times.max() < end - pd.Timedelta(hours=1):
        failures.append(f"mark ends {clean_times.max()}, require {end - pd.Timedelta(hours=1)}")
    return CoverageEvidence(clean_times.min().isoformat(), clean_times.max().isoformat(), len(frame), len(missing), tuple(failures))


def check_market_execution_coverage(
    path: Path,
    *,
    required_first_day: date,
    end_day: date,
    execution_utc: time = time(1, 5),
    max_lag_minutes: float = 60.0,
) -> CoverageEvidence:
    if not path.is_file():
        return CoverageEvidence(None, None, 0, 0, (f"missing market file {path}",))
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        return CoverageEvidence(None, None, 0, 0, (f"unreadable market file: {exc}",))
    if not {"open_time", "open", "high", "low", "close"}.issubset(frame.columns):
        return CoverageEvidence(None, None, len(frame), 0, ("missing market OHLC columns",))
    times = pd.DatetimeIndex(pd.to_datetime(frame["open_time"], utc=True, errors="coerce"))
    numeric = frame.loc[:, ["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    failures: list[str] = []
    if times.isna().any() or numeric.isna().any().any():
        failures.append("invalid market row")
    clean_times = times.dropna().drop_duplicates().sort_values()
    clean = numeric.loc[numeric.notna().all(axis=1)].copy()
    clean.index = times.loc[numeric.notna().all(axis=1)]
    clean = clean.sort_index()
    if (clean <= 0).any().any():
        failures.append("non-positive market price")
    if ((clean["high"] < clean[["open", "close", "low"]].max(axis=1)) | (clean["low"] > clean[["open", "close", "high"]].min(axis=1))).any():
        failures.append("invalid market OHLC")
    if clean_times.empty:
        return CoverageEvidence(None, None, len(frame), 0, tuple(failures + ["empty market file"]))
    if clean_times.min().date() > required_first_day:
        failures.append(
            f"market starts {clean_times.min().date()}, require {required_first_day} or the contract listing day"
        )
    missing_days: list[date] = []
    for day in pd.date_range(required_first_day, end_day, freq="D"):
        target = day + pd.Timedelta(hours=execution_utc.hour, minutes=execution_utc.minute)
        earlier = clean_times[clean_times <= target]
        if earlier.empty or target - earlier[-1] > pd.Timedelta(minutes=max_lag_minutes):
            missing_days.append(day.date())
    failures.extend(f"missing market execution coverage {day.isoformat()}" for day in missing_days)
    return CoverageEvidence(clean_times.min().isoformat(), clean_times.max().isoformat(), len(frame), len(missing_days), tuple(failures))


def check_market_alignment(market_path: Path, mark_paths: tuple[Path, ...]) -> CoverageEvidence:
    if not Path(market_path).is_file():
        return CoverageEvidence(None, None, 0, 0, (f"missing market file {market_path}",))
    market = pd.read_csv(market_path, usecols=["open_time"])
    market_times = set(pd.to_datetime(market["open_time"], utc=True, errors="coerce").dropna())
    mark_times: set[pd.Timestamp] = set()
    for path in mark_paths:
        if path.is_file():
            marks = pd.read_csv(path, usecols=["open_time"])
            mark_times.update(pd.to_datetime(marks["open_time"], utc=True, errors="coerce").dropna())
    if not mark_times:
        return CoverageEvidence(None, None, len(market_times), 0, ("no mark timestamps for market alignment",))
    low, high = min(mark_times), max(mark_times)
    inside = {stamp for stamp in market_times if low <= stamp <= high}
    extra = sorted(inside.difference(mark_times))
    failures = tuple(f"market timestamp has no mark bar: {stamp.isoformat()}" for stamp in extra[:20])
    return CoverageEvidence(
        min(market_times).isoformat() if market_times else None,
        max(market_times).isoformat() if market_times else None,
        len(market_times),
        len(extra),
        failures,
    )


def check_funding_coverage(
    path: Path,
    *,
    required_start: pd.Timestamp,
    required_end: pd.Timestamp,
    interval_hours: float,
) -> CoverageEvidence:
    if not path.is_file():
        return CoverageEvidence(None, None, 0, 0, (f"missing funding file {path}",))
    frame = pd.read_csv(path)
    required = {"funding_time", "funding_rate"}
    if not required.issubset(frame.columns) or frame.empty:
        return CoverageEvidence(None, None, len(frame), 0, ("missing funding rows/columns",))
    times = pd.DatetimeIndex(pd.to_datetime(frame["funding_time"], utc=True, errors="coerce").dropna()).sort_values()
    rates = pd.to_numeric(frame["funding_rate"], errors="coerce")
    failures: list[str] = []
    if times.empty or times.min() > required_start:
        failures.append(f"funding starts after {required_start}")
    if times.max() < required_end:
        failures.append(f"funding ends before {required_end}")
    if times.duplicated().any():
        failures.append("duplicate funding timestamp")
    if not pd.Series(rates).map(math.isfinite).all():
        failures.append("non-finite funding rate")
    if not math.isfinite(float(interval_hours)) or interval_hours <= 0:
        failures.append(f"invalid declared funding interval {interval_hours!r}")
        irregular = pd.Series(dtype="timedelta64[ns]")
    else:
        gaps = times.to_series().diff().dropna()
        irregular = gaps[gaps != pd.Timedelta(hours=float(interval_hours))]
        failures.extend(f"irregular funding interval {gap}" for gap in irregular.iloc[:5])
    return CoverageEvidence(times.min().isoformat(), times.max().isoformat(), len(frame), len(irregular), tuple(failures))
```

- [ ] **Step 3b: Wire contract listing dates and declared funding cadence**

`collect_member_evidence` uses `symbol_map.open_time` for the expected warmup/live data start:

```python
open_day = pd.Timestamp(row["open_time"]).date()
warmup_expected = max(warmup_start.date(), open_day)
live_expected = max(oos_start.date(), open_day)
warmup_mark = check_mark_coverage(
    warmup_mark_path,
    start=pd.Timestamp(warmup_expected, tz="UTC"),
    required_end=warmup_end,
    allow_late_first_bar=False,
)
live_mark = check_mark_coverage(
    live_mark_path,
    start=pd.Timestamp(live_expected, tz="UTC"),
    required_end=required_last_mark_time(now.to_pydatetime()) + pd.Timedelta(hours=1),
    allow_late_first_bar=False,
)
live_market = check_market_execution_coverage(
    live_market_path,
    required_first_day=live_expected,
    end_day=latest_signal_day + pd.Timedelta(days=1),
)
funding = check_funding_coverage(
    funding_path,
    required_start=pd.Timestamp(oos_start, tz="UTC"),
    required_end=required_last_mark_time(now.to_pydatetime()),
    interval_hours=float(row["fund_interval"]),
)
assert check_market_alignment(live_market_path, (warmup_mark_path, live_mark_path)).failures == ()
```

A market timestamp outside the union of warmup/live mark coverage is allowed only at the warmup tail; a timestamp inside that range without a matching mark bar blocks the member.

- [ ] **Step 4: Run coverage tests**

Expected: `3 passed` plus selector/ranking tests remain green.

- [ ] **Step 5: Commit**

```bash
git add src/atlas20/derivatives/top50_readiness.py tests/test_top50_readiness.py
git commit -m "feat: add top50 per-member data evidence"
```

---

### Task 4: Scoped Existing Audit and Snapshot Publication

**Files:**
- Modify: `src/atlas20/derivatives/top50_readiness.py`
- Test: `tests/test_top50_readiness.py`

**Interfaces:**
- Produces:
  - `write_scoped_audit_inputs(*, output_dir, selection, panel_path, symbol_map_path) -> tuple[Path, Path]`
  - `audit_selected_top50(*, raw_dir, scoped_panel, scoped_symbol_map, selection, now) -> DataAuditReport`
  - `build_readiness_payload(...) -> dict[str, object]`
  - `publish_readiness_payload(*, reports_dir, payload) -> dict[str, Path]`

- [ ] **Step 1: Write failing scoped-audit and snapshot tests**

```python
def test_scoped_audit_inputs_contain_exactly_the_selected_members(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import write_scoped_audit_inputs

    ranked = _ranked(52)
    mapping = _mapped(ranked, {2, 7})
    selection = select_executable_top50(ranked, mapping, as_of=date(2026, 11, 15))
    panel = pd.DataFrame(
        {
            "date": ["2026-11-15"] * 52,
            "coin_id": ranked["coin_id"],
            "symbol": ranked["symbol"],
        }
    )
    panel_path = tmp_path / "panel.csv"
    map_path = tmp_path / "symbol_map.csv"
    panel.to_csv(panel_path, index=False)
    mapping.assign(panel_symbol=mapping["panel_symbol"]).to_csv(map_path, index=False)

    scoped_panel, scoped_map = write_scoped_audit_inputs(
        output_dir=tmp_path / "audit",
        selection=selection,
        panel_path=panel_path,
        symbol_map_path=map_path,
    )

    selected_ids = {row.coin_id for row in selection.members}
    assert set(pd.read_csv(scoped_panel)["coin_id"]) == selected_ids
    assert set(pd.read_csv(scoped_map)["coin_id"]) == selected_ids


def test_publish_only_creates_latest_ready_for_complete_fifty(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import publish_readiness_payload

    blocked = {
        "as_of": "2026-11-15",
        "ready": False,
        "members": [{"coin_id": "bitcoin", "status": "READY"}],
        "top20": [{"coin_id": "bitcoin", "status": "READY"}],
    }
    paths = publish_readiness_payload(reports_dir=tmp_path, payload=blocked)
    assert paths["history"].is_file()
    assert paths["latest"].is_file()
    assert not paths["latest_ready"].exists()

    ready = {**blocked, "ready": True, "members": [{"coin_id": str(index)} for index in range(50)]}
    paths = publish_readiness_payload(reports_dir=tmp_path, payload=ready)
    assert paths["latest_ready"].is_file()
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_top50_readiness.py -q -k 'scoped or publish'`

Expected: import failures for missing functions.

- [ ] **Step 3: Implement scoped inputs, audit wrapper and atomic publication**

```python
from atlas20.derivatives.data_audit import DataAuditReport, audit_derivatives_data
from atlas20.logging_utils import atomic_write_text


def write_scoped_audit_inputs(
    *,
    output_dir: Path,
    selection: Top50Selection,
    panel_path: Path,
    symbol_map_path: Path,
) -> tuple[Path, Path]:
    wanted = {row.coin_id for row in selection.members}
    panel = pd.read_csv(panel_path)
    mapping = pd.read_csv(symbol_map_path)
    panel = panel.loc[panel["coin_id"].astype(str).isin(wanted)].copy()
    mapping = mapping.loc[mapping["coin_id"].astype(str).isin(wanted)].copy()
    if set(panel["coin_id"].astype(str)) != wanted:
        raise ValueError("scoped panel does not cover every selected member")
    if set(mapping["coin_id"].astype(str)) != wanted:
        raise ValueError("scoped symbol map does not cover every selected member")
    output_dir.mkdir(parents=True, exist_ok=True)
    panel_out = output_dir / "panel_top50.csv"
    map_out = output_dir / "symbol_map_top50.csv"
    panel.to_csv(panel_out, index=False)
    mapping.to_csv(map_out, index=False)
    return panel_out, map_out


def audit_selected_top50(
    *,
    raw_dir: Path,
    scoped_panel: Path,
    scoped_symbol_map: Path,
    selection: Top50Selection,
    now: pd.Timestamp,
) -> DataAuditReport:
    assets = {row.coin_id for row in selection.members}
    return audit_derivatives_data(
        raw_dir,
        scoped_panel,
        scoped_symbol_map,
        now=now.to_pydatetime(),
        expected_panel_day=selection.as_of,
        min_panel_assets=TOP50_SIZE,
        required_leverage_assets=assets,
        required_funding_assets=assets,
        required_leverage=4.0,
        require_all_funding_fresh=True,
    )


def _fingerprint(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def publish_readiness_payload(
    *,
    reports_dir: Path,
    payload: dict[str, object],
) -> dict[str, Path]:
    body = dict(payload)
    body.pop("fingerprint", None)
    body["fingerprint"] = _fingerprint(body)
    text = json.dumps(body, indent=2, sort_keys=True, default=str) + "\n"
    reports_dir = Path(reports_dir)
    history = reports_dir / "history" / f"{body['as_of']}.json"
    latest = reports_dir / "latest.json"
    top50 = reports_dir / "top50.csv"
    top20 = reports_dir / "top20.csv"
    atomic_write_text(history, text)
    atomic_write_text(latest, text)
    pd.DataFrame(body["members"]).to_csv(top50, index=False)
    pd.DataFrame(body["top20"]).to_csv(top20, index=False)
    result = {"history": history, "latest": latest, "top50": top50, "top20": top20}
    latest_ready = reports_dir / "latest_ready.json"
    result["latest_ready"] = latest_ready
    if bool(body["ready"]):
        ready_history = reports_dir / "ready" / f"{body['as_of']}.json"
        atomic_write_text(ready_history, text)
        atomic_write_text(latest_ready, text)
        result["ready_history"] = ready_history
    return result
```

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_top50_readiness.py -q -k 'scoped or publish'`

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/atlas20/derivatives/top50_readiness.py tests/test_top50_readiness.py
git commit -m "feat: audit and publish scoped top50 evidence"
```

---

### Task 5: State and Idempotent Telegram Events

**Files:**
- Modify: `src/atlas20/derivatives/top50_readiness.py`
- Test: `tests/test_top50_readiness.py`

**Interfaces:**
- Produces:
  - `load_state(path) -> dict[str, object]`
  - `notification_key(event, coin_id, as_of) -> str`
  - `build_notification_events(previous, payload, *, initialized: bool) -> tuple[dict[str, str], ...]`
  - `format_event_message(event: dict[str, str]) -> str`
  - `queue_notification_events(state, events) -> None`
  - `record_notification_result(state, event, *, sent: bool, error: str | None, sent_at: str | None) -> None`
  - `write_state(path, state) -> None`

- [ ] **Step 1: Write failing event/state tests**

```python
def _payload() -> dict[str, object]:
    return {
        "as_of": "2026-11-15",
        "ready": True,
        "members": [
            {"coin_id": "ethereum", "symbol": "ETH", "status": "READY", "failure_details": []}
        ],
        "top20": [
            {"coin_id": "ethereum", "symbol": "ETH", "status": "READY", "failure_details": []}
        ],
    }


def test_first_run_initializes_without_fifty_messages() -> None:
    from atlas20.derivatives.top50_readiness import build_notification_events

    events = build_notification_events({}, _payload(), initialized=False)
    assert events == ()


def test_new_top50_and_top20_members_emit_one_event_each() -> None:
    from atlas20.derivatives.top50_readiness import build_notification_events

    events = build_notification_events(
        {"members": ["bitcoin"], "top20": ["bitcoin"]},
        _payload(),
        initialized=True,
    )
    assert [event["event"] for event in events] == [
        "TOP50_ENTER",
        "TOP50_DATA_READY",
        "TOP20_ENTER",
    ]
    assert {event["coin_id"] for event in events} == {"ethereum"}
    assert len({event["key"] for event in events}) == 3


def test_failed_delivery_stays_pending_and_success_is_deduplicated() -> None:
    from atlas20.derivatives.top50_readiness import record_notification_result, write_state, load_state

    event = {
        "key": "TOP50_ENTER|ethereum|2026-11-15",
        "event": "TOP50_ENTER",
        "coin_id": "ethereum",
        "symbol": "ETH",
        "as_of": "2026-11-15",
        "status": "READY",
        "details": "",
    }
    state = {"version": 1, "notifications": {"sent_keys": {}, "pending": {}}}
    queue_notification_events(state, (event,))
    record_notification_result(state, event, sent=False, error="telegram down", sent_at=None)
    assert event["key"] in state["notifications"]["pending"]
    record_notification_result(state, event, sent=True, error=None, sent_at="2026-11-15T10:00:00Z")
    assert event["key"] in state["notifications"]["sent_keys"]
    assert event["key"] not in state["notifications"]["pending"]
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_top50_readiness.py -q -k 'notification or first_run or failed_delivery'`

Expected: imports fail for notification functions.

- [ ] **Step 3: Implement event ledger**

```python
EVENTS = ("TOP50_ENTER", "TOP50_DATA_READY", "TOP50_DATA_BLOCKED", "TOP20_ENTER")


def notification_key(event: str, coin_id: str, as_of: str) -> str:
    if event not in EVENTS:
        raise ValueError(f"unsupported event {event}")
    return f"{event}|{coin_id}|{as_of}"


def format_event_message(event: dict[str, str]) -> str:
    lines = [
        f"Atlas20 Top50 {event['event']}",
        f"日期: {event['as_of']}",
        f"币种: {event['symbol']} ({event['coin_id']})",
        f"状态: {event['status']}",
    ]
    if event["event"] == "TOP50_ENTER":
        lines.append("开始构建/审核完整数据。")
    elif event["event"] == "TOP50_DATA_READY":
        lines.append("数据完整，可进入 Top20 时直接构建信号。")
    elif event["event"] == "TOP50_DATA_BLOCKED":
        lines.append("数据审核失败；禁止用第 51 名掩盖该故障。")
    elif event["event"] == "TOP20_ENTER":
        lines.append("已进入 Top20；READY 时无需临时下载历史数据。")
    if event.get("details"):
        lines.extend(["", "缺口:", event["details"]])
    return "\n".join(lines)


def build_notification_events(
    previous: dict[str, object],
    payload: dict[str, object],
    *,
    initialized: bool,
) -> tuple[dict[str, str], ...]:
    if not initialized:
        return ()
    previous_members = {str(item) for item in previous.get("members", [])}
    previous_top20 = {str(item) for item in previous.get("top20", [])}
    as_of = str(payload["as_of"])
    members = {str(item["coin_id"]): item for item in payload["members"]}
    top20 = {str(item["coin_id"]): item for item in payload["top20"]}
    events: list[dict[str, str]] = []
    for coin_id, member in members.items():
        if coin_id not in previous_members:
            events.append(_event("TOP50_ENTER", coin_id, as_of, member))
        if coin_id not in previous_members or member["status"] != "READY":
            event = "TOP50_DATA_READY" if member["status"] == "READY" else "TOP50_DATA_BLOCKED"
            events.append(_event(event, coin_id, as_of, member))
    for coin_id, member in top20.items():
        if coin_id not in previous_top20:
            events.append(_event("TOP20_ENTER", coin_id, as_of, member))
    return tuple(events)


def _event(event: str, coin_id: str, as_of: str, member: dict[str, object]) -> dict[str, str]:
    status = str(member.get("status") or "BLOCKED")
    details = "; ".join(str(item) for item in member.get("failure_details", []))
    return {
        "event": event,
        "coin_id": coin_id,
        "symbol": str(member.get("symbol") or ""),
        "as_of": as_of,
        "status": status,
        "details": details,
        "key": notification_key(event, coin_id, as_of),
    }


def record_notification_result(
    state: dict[str, object],
    event: dict[str, str],
    *,
    sent: bool,
    error: str | None,
    sent_at: str | None,
) -> None:
    notifications = state.setdefault("notifications", {"sent_keys": {}, "pending": {}})
    assert isinstance(notifications, dict)
    sent_keys = notifications.setdefault("sent_keys", {})
    pending = notifications.setdefault("pending", {})
    assert isinstance(sent_keys, dict) and isinstance(pending, dict)
    key = event["key"]
    if sent:
        pending.pop(key, None)
        sent_keys[key] = {"sent_at": sent_at}
    else:
        pending[key] = {**event, "last_error": error, "attempted_at": sent_at}


def queue_notification_events(state: dict[str, object], events: tuple[dict[str, str], ...]) -> None:
    notifications = state.setdefault("notifications", {"sent_keys": {}, "pending": {}})
    assert isinstance(notifications, dict)
    pending = notifications.setdefault("pending", {})
    sent_keys = notifications.setdefault("sent_keys", {})
    assert isinstance(pending, dict) and isinstance(sent_keys, dict)
    for event in events:
        key = event["key"]
        if key not in sent_keys:
            pending[key] = event


def load_state(path: Path) -> dict[str, object]:
    if not Path(path).is_file():
        return {"version": 1, "initialized": False, "members": [], "top20": [], "notifications": {"sent_keys": {}, "pending": {}}}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("top50 state must be a JSON object")
    return payload


def write_state(path: Path, state: dict[str, object]) -> None:
    atomic_write_text(Path(path), json.dumps(state, indent=2, sort_keys=True) + "\n")
```

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_top50_readiness.py -q -k 'notification or first_run or failed_delivery'`

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/atlas20/derivatives/top50_readiness.py tests/test_top50_readiness.py
git commit -m "feat: add idempotent top50 event state"
```

---

### Task 6: Backfill Planner and Cycle Orchestration

**Files:**
- Create: `scripts/run_top50_readiness.py`
- Test: `tests/test_run_top50_readiness.py`

**Interfaces:**
- Consumes: `Top50Selection`, `audit_selected_top50`, `publish_readiness_payload`, existing downloader/repair CLIs, existing `send_telegram_message`.
- Produces:
  - `build_backfill_commands(*, session, selection, blocked_members, python, project_root, oos_start, warmup_end, end) -> list[list[str]]`
  - `run_readiness_cycle(*, session, now, notify, dry_run, runner, send_message, rank_fn=rank_current_candidates, assess_fn=assess_selection) -> dict[str, object]`
  - `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write failing backfill and cycle tests**

```python
def _selection() -> object:
    from atlas20.derivatives.top50_readiness import SelectionMember, Top50Selection

    return Top50Selection(
        as_of=date(2026, 11, 15),
        candidate_count=52,
        members=(
            SelectionMember(1, 1, "bitcoin", "BTC", "BTCUSDT", "BTC"),
            SelectionMember(2, 3, "ethereum", "ETH", "ETHUSDT", "ETH"),
        ),
        skipped=(),
        source_fingerprint="sha256:test",
    )


def _session(tmp_path: Path) -> object:
    from scripts.run_top50_readiness import ReadinessSession

    return ReadinessSession(
        project_root=tmp_path,
        config_path=tmp_path / "config/base.yaml",
        panel_path=tmp_path / "data/processed/panel_daily.csv",
        metadata_path=tmp_path / "data/processed/metadata.csv",
        raw_dir=Path("data/raw/bitget_derivatives/merged_oos_20261112"),
        warmup_mark_dir=Path("data/raw/bitget_derivatives/merged_20261009"),
        warmup_market_dir=Path("data/raw/bitget_derivatives/merged_market_20261009"),
        symbol_map_path=Path("data/raw/bitget_derivatives/merged_oos_20261112/symbol_map.csv"),
        state_path=tmp_path / "data/top50_readiness_state.json",
        reports_dir=tmp_path / "reports/top50_data_readiness",
        lock_path=tmp_path / "data/derivatives_execution.lock",
        oos_start=pd.Timestamp("2026-09-01", tz="UTC"),
        warmup_start=pd.Timestamp("2022-01-01", tz="UTC"),
        warmup_end=pd.Timestamp("2026-09-20T23:00:00Z"),
        universe_limit=60,
    )


def test_backfill_planner_uses_existing_downloaders_and_repair_only_for_blocked_mapped_members(tmp_path) -> None:
    from scripts.run_top50_readiness import build_backfill_commands

    selection = _selection()
    commands = build_backfill_commands(
        session=_session(tmp_path),
        selection=selection,
        blocked_members={"ethereum"},
        python="/venv/python",
        project_root=tmp_path,
        oos_start=pd.Timestamp("2026-09-01", tz="UTC"),
        warmup_end=pd.Timestamp("2026-09-21", tz="UTC"),
        end=pd.Timestamp("2026-11-17", tz="UTC"),
    )

    flattened = [" ".join(command) for command in commands]
    assert any("--output-dir data/raw/bitget_derivatives/merged_20261009" in item for item in flattened)
    assert any("--output-dir data/raw/bitget_derivatives/merged_market_20261009" in item for item in flattened)
    assert any("--output-dir data/raw/bitget_derivatives/merged_oos_20261112" in item for item in flattened)
    assert all("--symbols ethereum" in item for item in flattened)
    assert not any("bitcoin" in item for item in flattened)


def test_cycle_initializes_state_without_notifications(tmp_path) -> None:
    from scripts.run_top50_readiness import run_readiness_cycle

    calls: list[list[str]] = []
    sent: list[str] = []
    result = run_readiness_cycle(
        session=_session(tmp_path),
        now=pd.Timestamp("2026-11-16T18:00:00Z"),
        notify=True,
        dry_run=False,
        runner=lambda command: calls.append(command) or 0,
        send_message=lambda message: sent.append(message),
        rank_fn=lambda **_kwargs: pd.DataFrame(),
        assess_fn=lambda *_args, **_kwargs: (_payload(), set()),
    )
    assert result["initialized_now"] is True
    assert result["payload"]["ready"] is True
    assert sent == []
    assert (tmp_path / "data" / "top50_readiness_state.json").is_file()
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_run_top50_readiness.py -q`

Expected: module import failure for `scripts.run_top50_readiness`.

- [ ] **Step 3: Implement CLI session, planner and cycle**

```python
@dataclass(frozen=True)
class ReadinessSession:
    project_root: Path
    config_path: Path
    panel_path: Path
    metadata_path: Path
    raw_dir: Path
    warmup_mark_dir: Path
    warmup_market_dir: Path
    symbol_map_path: Path
    state_path: Path
    reports_dir: Path
    lock_path: Path
    oos_start: pd.Timestamp
    warmup_start: pd.Timestamp
    warmup_end: pd.Timestamp
    universe_limit: int = 60


def build_backfill_commands(
    *,
    session: ReadinessSession,
    selection: Top50Selection,
    blocked_members: set[str],
    python: str,
    project_root: Path,
    oos_start: pd.Timestamp,
    warmup_end: pd.Timestamp,
    end: pd.Timestamp,
) -> list[list[str]]:
    selected_ids = {member.coin_id for member in selection.members}
    unknown = set(blocked_members).difference(selected_ids)
    if unknown:
        raise ValueError("blocked_members are not selected mapped members: " + ", ".join(sorted(unknown)))
    blocked = sorted(blocked_members)
    if not blocked:
        return []
    symbols = ",".join(blocked)
    downloader = [python, "scripts/download_bitget_derivatives_data.py", "--panel", str(session.panel_path)]
    warmup = [
        *downloader,
        "--output-dir", str(session.warmup_mark_dir),
        "--start", str(session.warmup_start.date()),
        "--end", str(warmup_end.date()),
        "--types", "mark",
        "--skip-funding",
        "--symbols", symbols,
    ]
    warmup_market = [
        *downloader,
        "--output-dir", str(session.warmup_market_dir),
        "--start", str(session.warmup_start.date()),
        "--end", str(warmup_end.date()),
        "--types", "market",
        "--skip-funding",
        "--symbols", symbols,
    ]
    live = [
        *downloader,
        "--output-dir", str(session.raw_dir),
        "--start", str(oos_start.date()),
        "--end", str((end + pd.Timedelta(days=1)).date()),
        "--types", "mark,market",
        "--symbols", symbols,
    ]
    repair_warmup = [
        python, "scripts/repair_bitget_mark_gaps.py",
        "--raw-dir", str(session.warmup_mark_dir),
        "--start", str(session.warmup_start.date()),
        "--end", str(warmup_end.date()),
        "--symbols", symbols,
    ]
    repair_live = [
        python, "scripts/repair_bitget_mark_gaps.py",
        "--raw-dir", str(session.raw_dir),
        "--start", str(oos_start.date()),
        "--end", str((end + pd.Timedelta(days=1)).date()),
        "--symbols", symbols,
    ]
    return [warmup, warmup_market, live, repair_warmup, repair_live]


def run_readiness_cycle(
    *,
    session: ReadinessSession,
    now: pd.Timestamp,
    notify: bool,
    dry_run: bool,
    runner: Callable[[list[str]], int],
    send_message: Callable[[str], None],
    rank_fn: Callable[..., pd.DataFrame] = rank_current_candidates,
    assess_fn: Callable[..., tuple[dict[str, object], set[str]]] = assess_selection,
) -> dict[str, object]:
    as_of = (now - pd.Timedelta(days=1)).date()
    ranked = rank_fn(
        config_path=session.config_path,
        panel_path=session.panel_path,
        metadata_path=session.metadata_path,
        as_of=as_of,
        limit=session.universe_limit,
    )
    mapping = pd.read_csv(session.symbol_map_path)
    selection = select_executable_top50(ranked, mapping, as_of=as_of)
    payload, blocked = assess_fn(session=session, selection=selection, now=now)
    if blocked and not dry_run:
        for command in build_backfill_commands(
            session=session,
            selection=selection,
            blocked_members=set(blocked),
            python=sys.executable,
            project_root=session.project_root,
            oos_start=session.oos_start,
            warmup_end=session.warmup_end,
            end=now,
        ):
            completed = runner(command)
            if completed != 0:
                raise RuntimeError(f"backfill command failed ({completed}): {' '.join(command)}")
        payload, blocked = assess_fn(session=session, selection=selection, now=now)
    state = load_state(session.state_path)
    initialized = bool(state.get("initialized"))
    payload["initialized_now"] = not initialized
    events = build_notification_events(state, payload, initialized=initialized)
    state["initialized"] = True
    state["last_as_of"] = payload["as_of"]
    state["members"] = [item["coin_id"] for item in payload["members"]]
    state["top20"] = [item["coin_id"] for item in payload["top20"]]
    write_state(session.state_path, state)
    publish_readiness_payload(reports_dir=session.reports_dir, payload=payload)
    notification_failures: list[str] = []
    if notify and not dry_run:
        queue_notification_events(state, events)
        pending = dict(state["notifications"]["pending"])
        for event in pending.values():
            try:
                send_message(format_event_message(event))
            except Exception as exc:  # noqa: BLE001 - persisted for retry
                notification_failures.append(event["key"])
                record_notification_result(state, event, sent=False, error=str(exc), sent_at=now.isoformat())
            else:
                record_notification_result(state, event, sent=True, error=None, sent_at=now.isoformat())
        write_state(session.state_path, state)
    if notification_failures:
        raise RuntimeError("Telegram delivery failed for: " + ", ".join(notification_failures))
    return {"payload": payload, "events": events, "initialized_now": not initialized}
```

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_run_top50_readiness.py -q`

Expected: `2 passed`; the injected `rank_fn` and `assess_fn` keep the cycle test deterministic while the CLI uses the production defaults.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_top50_readiness.py tests/test_run_top50_readiness.py
git commit -m "feat: orchestrate top50 readiness and backfill"
```

---

### Task 7: Freshness, Lock and Parent-Prepare Integration

**Files:**
- Modify: `scripts/run_top50_readiness.py`
- Modify: `scripts/refresh_derivatives_data.py`
- Modify: `Makefile`
- Test: `tests/test_refresh_derivatives_data.py`
- Test: `tests/test_run_top50_readiness.py`

**Interfaces:**
- Produces CLI flags:
  - `--config`, `--panel`, `--metadata`, `--raw-dir`, `--warmup-mark-dir`, `--warmup-market-dir`, `--symbol-map`, `--state-file`, `--reports-dir`
  - `--oos-start 2026-09-01`, `--warmup-start 2022-01-01`, `--warmup-end 2026-09-21`
  - `--notify`, `--dry-run`, `--no-backfill`, `--lock-file`, `--no-lock`
- Parent prepare sequence adds:
  - `/usr/bin/make top50-readiness-unlocked`
  - only after `derivatives-live-data` and before `derivatives-ls104-signal`.

- [ ] **Step 1: Add failing lock and command-sequence tests**

```python
def test_prepare_sequence_runs_top50_before_frozen_signal() -> None:
    from scripts.refresh_derivatives_data import build_refresh_commands

    commands = build_refresh_commands(make_command="/usr/bin/make")
    names = [command[1] for command in commands]
    assert names.index("top50-readiness-unlocked") < names.index("derivatives-ls104-signal")


def test_top50_cli_refuses_noncurrent_panel(tmp_path) -> None:
    from scripts.run_top50_readiness import main

    panel = tmp_path / "panel_daily.csv"
    pd.DataFrame({"date": ["2026-11-14"], "coin_id": ["bitcoin"]}).to_csv(panel, index=False)
    with pytest.raises(SystemExit, match="panel does not carry"):
        main(["--panel", str(panel), "--now", "2026-11-16T18:00:00Z", "--no-lock"])
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_refresh_derivatives_data.py tests/test_run_top50_readiness.py -q`

Expected: failing command-sequence assertion and missing stale-panel guard.

- [ ] **Step 3: Implement freshness gate, locks and Make targets**

```python
from filelock import FileLock, Timeout
from atlas20.derivatives.live_chain import panel_lags_last_completed_day


def _require_current_panel(panel_path: Path, now: pd.Timestamp) -> None:
    if panel_lags_last_completed_day(panel_path, now.to_pydatetime()):
        raise SystemExit(f"panel does not carry the last completed UTC day for {now.isoformat()}")


def _acquire_lock(path: Path, *, wait_seconds: float) -> FileLock | None:
    lock = FileLock(str(path))
    try:
        lock.acquire(timeout=wait_seconds)
    except Timeout:
        return None
    return lock
```

Makefile:

```make
TOP50_READINESS_STATE ?= data/top50_readiness_state.json
TOP50_READINESS_REPORTS ?= reports/top50_data_readiness
TOP50_READINESS_LOCK ?= data/derivatives_execution.lock

top50-readiness: $(VENV_STAMP)
	$(PYTHON) scripts/run_top50_readiness.py \
		--state-file $(TOP50_READINESS_STATE) \
		--reports-dir $(TOP50_READINESS_REPORTS) \
		--lock-file $(TOP50_READINESS_LOCK) \
		--wait-seconds 900 $(ARGS)

# Called only from refresh_derivatives_data.py while its execution lock is held.
top50-readiness-unlocked: $(VENV_STAMP)
	$(PYTHON) scripts/run_top50_readiness.py \
		--state-file $(TOP50_READINESS_STATE) \
		--reports-dir $(TOP50_READINESS_REPORTS) \
		--no-lock $(ARGS)
```

Modify `build_refresh_commands`:

```python
return [
    [make_command, "derivatives-live-data"],
    [make_command, "top50-readiness-unlocked"],
    [make_command, "derivatives-ls104-signal"],
    [make_command, "audit-data-chain"],
    [make_command, "audit-data-ls104"],
    [make_command, "audit-symbols-ls104"],
    [make_command, "audit-contract-specs-ls104"],
    [make_command, "audit-signal-ls104"],
]
```

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_refresh_derivatives_data.py tests/test_run_top50_readiness.py -q`

Expected: all focused tests pass.

- [ ] **Step 5: Commit**

```bash
git add Makefile scripts/refresh_derivatives_data.py scripts/run_top50_readiness.py tests/test_refresh_derivatives_data.py tests/test_run_top50_readiness.py
git commit -m "feat: gate top50 readiness before prepare completes"
```

---

### Task 8: Telegram Wrapper, Optional Launchd Schedule and Runbook

**Files:**
- Create: `ops/run_top50_readiness.sh`
- Create: `ops/com.atlas20.top50-readiness.plist`
- Test: `tests/test_launchd_top50_schedule.py`
- Modify: `docs/operations/derivatives_live_runbook.md`

**Interfaces:**
- Wrapper sources only `/Users/ww/.config/atlas20/telegram.env`.
- Wrapper runs `make top50-readiness ARGS=--notify`.
- Optional plist fires once daily at 09:45 Beijing = 01:45 UTC as a manual/recovery fallback and does not call executor.
- Primary readiness remains inside the 08:35/08:55 prepare, so a separate 09:45 job cannot delay the 09:05 fill.

- [ ] **Step 1: Write failing schedule test**

```python
def test_top50_fallback_runs_once_after_prepare_and_before_late_window() -> None:
    import plistlib
    from pathlib import Path

    path = Path("ops/com.atlas20.top50-readiness.plist")
    payload = plistlib.loads(path.read_bytes())
    intervals = payload["StartCalendarInterval"]
    assert intervals == [{"Hour": 9, "Minute": 45}]
    assert payload["RunAtLoad"] is False
    assert "operator" in " ".join(payload.get("ProgramArguments", [])) or payload["ProgramArguments"][-1].endswith("run_top50_readiness.sh")
```

- [ ] **Step 2: Run test and verify RED**

Run: `.venv/bin/python -m pytest tests/test_launchd_top50_schedule.py -q`

Expected: `FileNotFoundError` for the plist.

- [ ] **Step 3: Create wrapper and plist**

`ops/run_top50_readiness.sh`:

```sh
#!/bin/sh
set -eu
PROJECT_ROOT="/Users/ww/Project/Atlas20"
TELEGRAM_ENV="${ATLAS20_CONFIG_DIR:-$HOME/.config/atlas20}/telegram.env"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
if [ ! -r "$TELEGRAM_ENV" ]; then
  echo "missing Telegram environment: $TELEGRAM_ENV" >&2
  exit 1
fi
set -a
. "$TELEGRAM_ENV"
set +a
cd "$PROJECT_ROOT"
exec /usr/bin/make top50-readiness ARGS=--notify
```

`ops/com.atlas20.top50-readiness.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.atlas20.top50-readiness</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>/Users/ww/Project/Atlas20/ops/run_top50_readiness.sh</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/ww/Project/Atlas20</string>
  <key>StartCalendarInterval</key>
  <array><dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>45</integer></dict></array>
  <key>RunAtLoad</key><false/>
  <key>ThrottleInterval</key><integer>300</integer>
  <key>StandardOutPath</key><string>/Users/ww/Library/Logs/atlas20-top50-readiness.log</string>
  <key>StandardErrorPath</key><string>/Users/ww/Library/Logs/atlas20-top50-readiness.log</string>
</dict>
</plist>
```

Runbook additions must state:

```text
Primary path:
08:30/08:50 CMC panel -> prepare acquires execution lock -> derivatives-live-data
-> top50-readiness-unlocked -> repair only newly blocked mapped members -> scoped audit
-> publish readiness -> rebuild LS104 ledger -> audits.

A READY Top50 is the only handoff source for a future executable-universe Top20.
A missing Bitget contract is skipped and backfilled by rank.
A mapped asset with missing data blocks readiness and sends TOP50_DATA_BLOCKED.
It never silently promotes rank 51 over rank 50.
```

- [ ] **Step 4: Run schedule test and lint shell syntax**

Run: `.venv/bin/python -m pytest tests/test_launchd_top50_schedule.py -q && sh -n ops/run_top50_readiness.sh`

Expected: `1 passed` and exit 0.

- [ ] **Step 5: Commit**

```bash
git add ops/run_top50_readiness.sh ops/com.atlas20.top50-readiness.plist tests/test_launchd_top50_schedule.py docs/operations/derivatives_live_runbook.md
git commit -m "ops: document and schedule top50 readiness"
```

---

### Task 9: Real-Data Backfill and Artifact Audit

**Files:**
- Modify: `RESEARCH.md`
- Modify: `docs/operations/derivatives_live_runbook.md`
- No code file is allowed to be used as fabricated data; run against `/Users/ww/Project/Atlas20`.

**Interfaces:**
- Consumes the real panel and raw cache.
- Produces `reports/top50_data_readiness/latest_ready.json`, history, `top50.csv`, `top20.csv`, and byte-hash evidence for untouched LS104 artifacts.

- [ ] **Step 1: Capture the live-artifact hashes before any real run**

```bash
shasum -a 256 \
  /Users/ww/Project/Atlas20/data/ls45_g175_execution_state.json \
  /Users/ww/Project/Atlas20/reports/ls45_live_g175_live/audit.json \
  /Users/ww/Project/Atlas20/reports/ls45_live_g175_live/journal.csv \
  /Users/ww/Project/Atlas20/reports/ls45_live_g175_live/latest.json \
  > /tmp/atlas20-ls104-before.sha256
```

- [ ] **Step 2: Run a read-only dry assessment first**

```bash
cd /Users/ww/Project/Atlas20
.venv/bin/python scripts/run_top50_readiness.py \
  --dry-run --no-lock \
  --now 2026-11-16T18:00:00Z
```

Expected: report identifies exactly current raw Top50, HTX/MNT as `VENUE_UNAVAILABLE`, and any live market-history gap as a mapped-member blocker. It writes no state or backfill.

- [ ] **Step 3: Backfill only the real blocked mapped members with the existing downloader**

```bash
cd /Users/ww/Project/Atlas20
.venv/bin/python scripts/run_top50_readiness.py \
  --no-lock --notify \
  --now 2026-11-16T18:00:00Z
```

Expected: existing `download_bitget_derivatives_data.py` fills missing Top50 warmup/live mark/market, `repair_bitget_mark_gaps.py` repairs mark interiors, scoped `audit_derivatives_data` passes, and `latest_ready.json` is published only if all 50 members are READY.

- [ ] **Step 4: Inspect every readiness node from the real artifacts**

```bash
cd /Users/ww/Project/Atlas20
.venv/bin/python - <<'PY'
import json
from pathlib import Path
import pandas as pd
p = Path("reports/top50_data_readiness/latest.json")
r = json.loads(p.read_text())
assert r["ready"] is True
assert len(r["members"]) == 50
assert len({m["coin_id"] for m in r["members"]}) == 50
assert len({m["bitget_symbol"] for m in r["members"]}) == 50
assert [m["final_rank"] for m in r["members"]] == list(range(1, 51))
assert [m["original_rank"] for m in r["members"]] == sorted(m["original_rank"] for m in r["members"])
assert {s["coin_id"] for s in r["skipped"]} >= {"htx-dao", "mantle"}
assert len(r["top20"]) == 20
assert all(m["status"] == "READY" for m in r["top20"])
for member in r["members"]:
    assert member["cmc"]["failures"] == []
    assert member["warmup_mark"]["failures"] == []
    assert member["warmup_market"]["failures"] == []
    assert member["live_mark"]["failures"] == []
    assert member["live_market"]["failures"] == []
    assert member["funding"]["failures"] == []
print(r["fingerprint"])
print(pd.DataFrame(r["members"])[["final_rank", "original_rank", "coin_id", "status"]].to_string(index=False))
PY
```

- [ ] **Step 5: Prove the live LS104 artifacts were unchanged**

```bash
shasum -a 256 \
  /Users/ww/Project/Atlas20/data/ls45_g175_execution_state.json \
  /Users/ww/Project/Atlas20/reports/ls45_live_g175_live/audit.json \
  /Users/ww/Project/Atlas20/reports/ls45_live_g175_live/journal.csv \
  /Users/ww/Project/Atlas20/reports/ls45_live_g175_live/latest.json \
  > /tmp/atlas20-ls104-after.sha256
cmp /tmp/atlas20-ls104-before.sha256 /tmp/atlas20-ls104-after.sha256
```

Expected: `cmp` exits 0.

- [ ] **Step 6: Record the milestone in `RESEARCH.md` and runbook**

Add a section containing the exact as-of date, 50/50 readiness, skipped HTX/MNT, final ranks 51/52 that filled OP/GALA, audit fingerprint, CMC/live/warmup/funding ranges, and the explicit sentence:

```text
This milestone proves data readiness and signal handoff for the executable Top50. It does not alter the live LS104 universe rule; executable-universe promotion remains a separate owner-approved track change.
```

- [ ] **Step 7: Commit**

```bash
git add RESEARCH.md docs/operations/derivatives_live_runbook.md
git commit -m "docs: record top50 real-data readiness audit"
```

---

### Task 10: Full Verification and Handoff

**Files:**
- No new files.
- Review every implementation node and real artifact.

**Interfaces:**
- Consumes all prior tasks.
- Produces final command evidence and a review record.

- [ ] **Step 1: Run the targeted suite**

```bash
.venv/bin/python -m pytest \
  tests/test_top50_readiness.py \
  tests/test_run_top50_readiness.py \
  tests/test_refresh_derivatives_data.py \
  tests/test_launchd_top50_schedule.py \
  tests/test_bitget_derivatives.py \
  tests/test_derivatives_data_audit.py \
  tests/test_audit_venue_symbols.py \
  tests/test_live_spec_universe.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run repository gates**

```bash
make test
make lint
make typecheck
```

Expected: all pass. If `make typecheck` intentionally covers only `src/atlas20/api`, also run `.venv/bin/python -m mypy --strict src/atlas20/derivatives/top50_readiness.py scripts/run_top50_readiness.py` and record any pre-existing scope limitation.

- [ ] **Step 3: Re-run the real artifact audit after all code changes**

```bash
cd /Users/ww/Project/Atlas20
.venv/bin/python scripts/run_top50_readiness.py --dry-run --no-lock --now 2026-11-16T18:00:00Z
```

Expected: same fingerprint as the published ready snapshot unless source files materially changed; if changed, record the new fingerprint and explain every changed member.

- [ ] **Step 4: Review all twelve spec audit nodes manually**

Check and record evidence for:

1. CMC source and last completed day;
2. skip/backfill order for HTX/MNT and final OP/GALA positions;
3. panel continuity, same-day cap, no stale ranking carry, no future row;
4. warmup mark/market coverage and repair before/after;
5. live mark/market coverage and latest required bar;
6. funding intervals, publication and live OOS completeness;
7. contract online/perpetual/USDT-M/4x/short/flip;
8. readiness fingerprint reproducibility;
9. Top20 handoff and no temporary downloads;
10. Telegram initialization and idempotent retry;
11. lock, blocked path and protect-only isolation;
12. byte-identical LS104 state/journal/manifest/target.

- [ ] **Step 5: Commit verification documentation**

```bash
git add RESEARCH.md docs/operations/derivatives_live_runbook.md
git commit -m "docs: record top50 verification and residual risks"
```

- [ ] **Step 6: Push the branch**

```bash
git push -u origin feat/top50-data-readiness
```

Expected: branch pushed. Do not merge or promote to live unless the owner explicitly approves the executable-universe track change.
