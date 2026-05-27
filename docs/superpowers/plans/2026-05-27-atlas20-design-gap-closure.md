# Atlas20 Design Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the highest-value gaps found in the design audit: refreshed report artifacts, true compare holdings overlap, real reports archive discovery, Featured Digest download consistency, and full strategy selection in Compare.

**Status 2026-05-27:** Implemented and verified. The additional R3/T1 unknown compare ID 404 contract was also closed during execution.

**Architecture:** Keep the existing FastAPI service boundaries. Add focused adapter logic where the data already belongs: compare holdings from `weights/`, reports archive discovery from report filesystem + DB records, and frontend strategy modal options from `/api/options.strategies`. Do not restructure the API or introduce a new job system in this pass.

**Tech Stack:** Python 3.11, FastAPI, SQLModel, pandas, pytest, React 19, TanStack Query, Vitest.

---

## Scope

This plan implements the first four practical priorities from the audit:

1. Refresh `reports/latest` so bundled demo artifacts match current pipeline output expectations.
2. Compute Compare holdings overlap from real strategy weights instead of the current latest-universe proxy when weights are available.
3. Make Reports archive discover real report artifacts from disk when the DB has no rows.
4. Make Featured Digest display/download resolve to the same real artifact when no scheduled featured run exists.
5. Feed Compare `+ ADD STRATEGY` from `/api/options.strategies`, not only `presets`.

Out of scope for this pass:

- Full async report-generation progress UI.
- Public-production auth hardening for all GET routes.
- Playwright e2e suite and OpenAPI snapshot generation.
- Full `mypy --strict src/atlas20/api/` expansion.

---

## File Map

- Modify: `src/atlas20/api/data_access/compare.py`
  - Add a weights-backed holdings adapter.
  - Keep the existing latest-universe proxy as fallback.
- Modify: `tests/test_compare_data_access.py`
  - Add regression tests proving Jaccard uses `reports/latest/weights/*.csv`.
- Modify: `src/atlas20/api/services.py`
  - Add disk-backed `list_reports` fallback.
  - Add Featured Digest resolution fallback for newest markdown.
- Modify: `tests/test_api_services.py` or `tests/test_featured_digest.py`
  - Add report archive and featured download consistency tests.
- Modify: `src/atlas20/api/services_download.py`
  - Allow `featured` download to resolve the newest markdown when no featured KV row exists, while preserving report-root and manifest/hash checks where applicable.
- Modify: `tests/test_download_streaming.py` or `tests/test_download_path_safety.py`
  - Add safe featured fallback download coverage.
- Modify: `apps/web/src/features/compare/StrategyCompareTab.tsx`
  - Build Add Strategy modal options from `options.data.strategies` first, with `presets` as fallback.
- Modify: `apps/web/src/features/compare/StrategyCompareTab.test.tsx`
  - Add regression tests for strategy-list modal options and slug/display-name mapping.
- Regenerate artifacts:
  - Run `python scripts/run_research.py --config config/base.yaml` unless cached data is missing.
  - If full research cannot run within the local data state, run a narrower deterministic command or document the blocker and leave code capable of generating current artifacts.

---

## Task 1: Weights-Backed Compare Overlap

**Files:**
- Modify: `src/atlas20/api/data_access/compare.py`
- Test: `tests/test_compare_data_access.py`

- [x] **Step 1: Write the failing test**

Add a test that creates a latest report directory with `strategy_summary.csv`, `equity_curves.csv`, and `weights/*.csv`. Use two strategies with partial overlap:

```python
def test_compare_overlap_uses_strategy_weights(tmp_path, monkeypatch):
    report_root = tmp_path / "reports"
    latest = report_root / "latest"
    weights = latest / "weights"
    weights.mkdir(parents=True)
    latest.joinpath("strategy_summary.csv").write_text(
        "strategy,total_return,cagr,annualized_volatility,sharpe,sortino,max_drawdown,calmar,monthly_win_rate,annualized_turnover,avg_turnover_per_rebalance,average_holdings\n"
        "ALPHA,0.2,0.2,0.1,1.1,1.2,-0.1,2.0,0.6,0.2,0.1,2\n"
        "BETA,0.1,0.1,0.1,0.8,1.0,-0.2,0.5,0.5,0.2,0.1,2\n",
        encoding="utf-8",
    )
    latest.joinpath("equity_curves.csv").write_text(
        ",ALPHA,BETA\n2026-01-01,100,100\n2026-01-02,110,105\n",
        encoding="utf-8",
    )
    weights.joinpath("ALPHA.csv").write_text(
        "date,BTC,ETH,SOL\n2026-01-01,0.5,0.5,0\n2026-01-02,0.5,0.5,0\n",
        encoding="utf-8",
    )
    weights.joinpath("BETA.csv").write_text(
        "date,BTC,ETH,SOL\n2026-01-01,0.5,0,0.5\n2026-01-02,0.5,0,0.5\n",
        encoding="utf-8",
    )

    settings = Settings(report_root=report_root, data_root=tmp_path / "data", anchor_date=date(2026, 1, 2))

    payload = load_compare_from_reports(settings, ["ALPHA", "BETA"], "ALL")

    assert payload["overlap"]["symbols"] == ["ALPHA", "BETA"]
    assert payload["overlap"]["matrix"] == [[1.0, 1 / 3], [1 / 3, 1.0]]
    assert payload["overlap"]["sharedHoldings"][0]["symbol"] == "BTC"
```

- [x] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_compare_data_access.py::test_compare_overlap_uses_strategy_weights -q
```

Expected: FAIL because current overlap is the deterministic latest-universe proxy.

- [x] **Step 3: Implement minimal production code**

In `compare.py`, add helpers:

```python
def _weights_dir(settings: Settings) -> Path:
    return _latest_report_dir(settings.report_root) / "weights"

def _safe_weight_filename(strategy: str) -> str:
    return strategy.replace("/", "_").replace("\\", "_")

def _load_strategy_holdings_from_weights(settings: Settings, strategies: list[str]) -> dict[str, set[str]] | None:
    root = _weights_dir(settings)
    if not root.is_dir():
        return None
    holdings: dict[str, set[str]] = {}
    for strategy in strategies:
        path = root / f"{_safe_weight_filename(strategy)}.csv"
        if not path.exists():
            return None
        frame = pd.read_csv(path)
        if frame.empty:
            return None
        date_col = frame.columns[0]
        numeric = frame.drop(columns=[date_col], errors="ignore").apply(pd.to_numeric, errors="coerce")
        latest = numeric.dropna(how="all").tail(1)
        if latest.empty:
            return None
        held = {str(column) for column, value in latest.iloc[0].items() if pd.notna(value) and float(value) > 1e-8}
        holdings[strategy] = held
    return holdings
```

Change `load_compare_from_reports` so it tries weights first:

```python
holdings = _load_strategy_holdings_from_weights(settings, resolved_ids)
if holdings is None:
    latest_universe = _load_latest_universe(settings)
    overlap = _build_overlap(resolved_ids, latest_universe)
else:
    overlap = _build_overlap_from_holdings(resolved_ids, holdings)
```

Add `_build_overlap_from_holdings` mirroring `_build_overlap`, but using the supplied holdings sets and ranking shared holdings by count then symbol.

- [x] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_compare_data_access.py::test_compare_overlap_uses_strategy_weights -q
```

Expected: PASS.

- [x] **Step 5: Run focused compare tests**

Run:

```powershell
python -m pytest tests/test_compare_data_access.py -q
```

Expected: PASS.

---

## Task 2: Real Reports Archive From Disk

**Files:**
- Modify: `src/atlas20/api/services.py`
- Test: `tests/test_api_services.py`

- [x] **Step 1: Write the failing test**

Add a test that creates real report files under `reports/latest` with an empty DB and expects `list_reports` to return those files instead of `mock_data.fallback_reports`.

```python
def test_list_reports_discovers_report_files_when_db_empty(tmp_path, monkeypatch, db_session):
    report_root = tmp_path / "reports"
    latest = report_root / "latest"
    latest.mkdir(parents=True)
    digest = latest / "atlas20_report.md"
    digest.write_text("# Real report\n", encoding="utf-8")
    png = latest / "equity_curves.png"
    png.write_bytes(b"png")
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    get_settings.cache_clear()

    reports = list_reports("recent", db_session)

    titles = [report.title for report in reports]
    assert any("atlas20_report.md" in title for title in titles)
    assert any(report.thumbnail == "equity" for report in reports)
    assert all(report.id not in {"weekly_2026w20", "risk_note_2026w20"} for report in reports)
```

- [x] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_api_services.py::test_list_reports_discovers_report_files_when_db_empty -q
```

Expected: FAIL because current `list_reports` returns fallback mock rows.

- [x] **Step 3: Implement minimal production code**

In `services.py`, add `_discover_report_entries(report_root: Path) -> list[ReportEntry]`:

- Scan `reports/latest`, `reports/app_runs/*`, and one-level historical report directories.
- Include extensions `.md`, `.pdf`, `.png`, `.csv`, `.zip`.
- Skip `.tmp`, `.bak_*`, and hidden files.
- Build stable IDs from relative path with lowercase alphanumerics/underscore.
- Infer thumbnail by extension/name:
  - `equity` for equity png/csv names.
  - `lines` for markdown.
  - `bars` for pdf.
  - `horizontal-bars` for csv.
  - `sparkbar` for zip.
- Sort according to `sort`.

Change `list_reports`:

```python
disk_entries = _discover_report_entries(get_settings().report_root)
if disk_entries:
    return _sort_report_entries(disk_entries, sort)
return [ReportEntry.model_validate(row) for row in fallback_rows]
```

Keep DB rows highest priority when present.

- [x] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_api_services.py::test_list_reports_discovers_report_files_when_db_empty -q
```

Expected: PASS.

- [x] **Step 5: Add sort coverage**

Add or extend a test for `sort="size"` and `sort="type"` using disk entries.

Run:

```powershell
python -m pytest tests/test_api_services.py -q
```

Expected: PASS.

---

## Task 3: Featured Digest Download Consistency

**Files:**
- Modify: `src/atlas20/api/services_download.py`
- Test: `tests/test_download_streaming.py`

- [x] **Step 1: Write the failing test**

Add a test that creates `reports/latest/atlas20_report.md`, does not create a featured KV run, and expects `/api/reports/digest/download?format=markdown` to stream that markdown.

```python
def test_featured_digest_download_falls_back_to_latest_markdown(client, tmp_path, monkeypatch):
    report_root = tmp_path / "reports"
    latest = report_root / "latest"
    latest.mkdir(parents=True)
    latest.joinpath("atlas20_report.md").write_text("# Latest Digest\n", encoding="utf-8")
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    get_settings.cache_clear()

    response = client.get("/api/reports/digest/download?format=markdown")

    assert response.status_code == 200
    assert b"Latest Digest" in response.content
```

- [x] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_download_streaming.py::test_featured_digest_download_falls_back_to_latest_markdown -q
```

Expected: FAIL with 404 from `_resolve_featured_file`.

- [x] **Step 3: Implement minimal production code**

In `services_download.py`, add:

```python
def _newest_markdown(report_root: Path) -> Path | None:
    candidates = [path for path in report_root.rglob("*.md") if path.is_file() and ".tmp" not in path.parts]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None
```

In `_resolve_featured_file`, after KV lookup misses, if `fmt == "markdown"`:

```python
markdown = _newest_markdown(Path(settings.report_root))
if markdown is not None:
    return markdown, None, sha256_file(markdown)
```

This keeps report-root and sha validation active through existing `_resolve_under_report_root` and `_validate_manifest_and_hash`.

- [x] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_download_streaming.py::test_featured_digest_download_falls_back_to_latest_markdown -q
```

Expected: PASS.

---

## Task 4: Compare Modal Uses Full Strategy Options

**Files:**
- Modify: `apps/web/src/features/compare/StrategyCompareTab.tsx`
- Test: `apps/web/src/features/compare/StrategyCompareTab.test.tsx`

- [x] **Step 1: Write the failing test**

Add a Vitest case where `/api/options` returns a strategy that is not in `presets`, open Add Strategy, and assert it appears.

```tsx
it("shows full strategy options in the add strategy modal", async () => {
  vi.mocked(api.getOptions).mockResolvedValue({
    ...api.fallbackOptions,
    presets: [{ slug: "ALPHA", display_name: "Alpha Preset" }],
    strategies: [{ strategy: "OMEGA_REAL_STRATEGY", display_name: "Omega Real Strategy" }],
  });

  render(<StrategyCompareTab />);

  await screen.findByText("Alpha Preset");
  await userEvent.click(screen.getByRole("button", { name: /add strategy/i }));

  expect(await screen.findByText("Omega Real Strategy")).toBeInTheDocument();
});
```

- [x] **Step 2: Verify RED**

Run:

```powershell
npm --prefix apps/web test -- src/features/compare/StrategyCompareTab.test.tsx --run
```

Expected: FAIL because the modal currently builds options from presets only.

- [x] **Step 3: Implement minimal production code**

In `StrategyCompareTab.tsx`, change option derivation:

```tsx
const strategyOptions = useMemo(() => {
  const strategyLabels = (options.data?.strategies ?? []).map((s) => s.display_name);
  const presetLabels = (options.data?.presets ?? []).map((p) => p.display_name);
  return Array.from(new Set([...selections.map((s) => s.label), ...strategyLabels, ...presetLabels]));
}, [options.data?.strategies, options.data?.presets, selections]);
```

Change `handleAddStrategies` mapping:

```tsx
const presetByLabel = new Map((options.data?.presets ?? []).map((p) => [p.display_name, p.slug]));
const strategyByLabel = new Map((options.data?.strategies ?? []).map((s) => [s.display_name, s.strategy]));
const id = strategyByLabel.get(label) ?? presetByLabel.get(label) ?? label;
```

- [x] **Step 4: Verify GREEN**

Run:

```powershell
npm --prefix apps/web test -- src/features/compare/StrategyCompareTab.test.tsx --run
```

Expected: PASS.

---

## Task 5: Refresh `reports/latest` Artifacts

**Files:**
- Generated output under `reports/latest/`
- Potentially generated `reports/latest.txt`

- [x] **Step 1: Verify current artifact gap**

Run:

```powershell
Test-Path reports/latest/weights
Test-Path reports/latest/selection_history.csv
Test-Path reports/latest/manifest.json
```

Expected before refresh: at least one `False`.

- [x] **Step 2: Run the research pipeline**

Run:

```powershell
python scripts/run_research.py --config config/base.yaml
```

Expected: command exits 0 and `reports/latest` contains `weights/`, `selection_history.csv`, and `manifest.json`.

- [x] **Step 3: Full pipeline was not blocked**

If the command fails because ignored local data is absent or a provider fetch is unavailable, do not fabricate tracked research results. Instead:

- Capture the exact failure.
- Run the smallest existing test proving exporter behavior:

```powershell
python -m pytest tests/test_report_export.py -q
```

- Leave final response stating the code path is implemented but local snapshot refresh needs data/provider recovery.

- [x] **Step 4: Verify refreshed artifacts**

Run:

```powershell
Get-ChildItem reports/latest/weights -File | Measure-Object
Test-Path reports/latest/selection_history.csv
Test-Path reports/latest/manifest.json
```

Expected: weights count greater than 0, both paths `True`.

---

## Task 6: Focused And Full Verification

**Files:**
- No new production changes.

- [x] **Step 1: Run focused Python tests**

Run:

```powershell
python -m pytest tests/test_compare_data_access.py tests/test_api_services.py tests/test_download_streaming.py -q
```

Expected: PASS.

- [x] **Step 2: Run focused frontend tests**

Run:

```powershell
npm --prefix apps/web test -- src/features/compare/StrategyCompareTab.test.tsx --run
```

Expected: PASS.

- [x] **Step 3: Run full Python tests**

Run:

```powershell
python -m pytest -q
```

Expected: PASS.

- [x] **Step 4: Run full frontend tests and build**

Run:

```powershell
npm --prefix apps/web test
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

Expected: all PASS.

- [x] **Step 5: Run static checks**

Run:

```powershell
ruff check src tests
mypy --strict src/atlas20/api/schemas.py src/atlas20/api/settings.py src/atlas20/api/_metrics.py
```

Expected: all PASS.

---

## Risk Controls

- Keep DB-backed report rows higher priority than disk discovery.
- Preserve fallback mock data only for fresh installs with no DB rows and no disk artifacts.
- Do not change public API response shapes except using already-defined fields.
- Do not invent report data if the pipeline cannot regenerate local artifacts.
- Do not remove current fallback paths; this project still supports demo/fresh-install mode.

---

## Self-Review

- No plan step requires an undefined helper without also defining it in the same task.
- Each production behavior change has a failing test before implementation.
- The plan avoids unrelated production hardening and e2e/OpenAPI work.
- The artifact refresh step allows a documented blocker instead of fabricating outputs.
