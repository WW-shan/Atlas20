# Batch 1 Brief — Phase X: Pipeline output extension

## Repo / branch
- `D:/Code/Atlas20`, branch `redesign/r3-premium`, HEAD `53a2e08`
- Roadmap reference: `docs/redesign/ROADMAP.md` Phase X (X1-X4)

## Goal
Extend the standard atlas20 pipeline so every backtest run exports the
artifacts that the R3 API will read, with atomic write semantics so the API
can't observe a half-written report directory.

## Scope of changes

### X1 — Per-strategy `weights/{strategy}.csv`
Each `BacktestResult` already has a `weights: pd.DataFrame` field in memory.
Currently it is NOT written to disk. Add:

- In `src/atlas20/reporting/report.py:export_result_tables`, after the existing
  CSV writes, create `report_dir/weights/` and write one CSV per strategy:
  `report_dir/weights/{strategy_name}.csv`
- Index is rebalance date (or daily — match `result.weights.index`), columns
  are coin_id, values are the weight at that point.
- File names must be filesystem-safe (no slashes); existing strategy names use
  underscores so this is fine, but assert it in code with a `pathvalidate`-style
  guard (use stdlib `re.match(r"^[A-Za-z0-9_]+$", name)` and raise if not).

### X2 — Pipeline-wide `selection_history.csv`
Currently only `profit_max_refine` sub-config emits a `selection_history.csv`
(see `reports/bear_bottom_to_current_2022_11_21_2026_04_22/profit_max_refine/*/`).
The standard pipeline (`atlas20.pipeline`) does NOT emit it for the main
strategy set.

- Derive a unified `selection_history.csv` in `export_result_tables`:
  - For each strategy, for each rebalance date, list the coin_id, rank,
    score (if available — many BH strategies have no score, leave column NaN),
    and weight (from `result.weights` on that date)
  - Schema: `rebalance_date, strategy, coin_id, coin_rank, coin_score, coin_weight`
  - Sorted by `(rebalance_date, strategy, coin_rank)`
- The existing `profit_max_refine` exports stay as-is (different scope), but
  the new file at `report_dir/selection_history.csv` is for the full strategy set.

### X3 — `manifest.json`
For reproducibility tracing, write `report_dir/manifest.json` after all other
artifacts are on disk:

```json
{
  "config_path": "config/base.yaml",
  "config_sha256": "...",
  "code_commit": "53a2e08",
  "pipeline_version": "0.1.0",
  "data_snapshot": {
    "coingecko": "2026-05-18T03:14:22Z",
    "cryptocompare": "2026-05-18T03:14:51Z"
  },
  "generated_at": "2026-05-19T...Z",
  "artifacts": [
    {"kind": "summary", "path": "strategy_summary.csv", "size": 12345, "sha256": "..."},
    ...
  ]
}
```

- `code_commit`: run `git rev-parse HEAD` via `subprocess.run`; fall back to env
  var `ATLAS20_CODE_COMMIT` then to `"unknown"` if neither works.
- `config_sha256`: read the yaml file bytes and hash.
- `data_snapshot`: scan `data/raw/{provider}/` for newest file, take mtime as ISO.
- `pipeline_version`: import from `atlas20.__version__` if exists, else
  hardcode `"0.1.0"` for now.
- `artifacts`: walk the report dir, list every file with its size + sha256.

### X4 — Atomic write protocol
Currently `export_result_tables` writes directly to `report_dir`, so a partial
write can be observed. Refactor:

- Accept the final destination as before.
- Internally write to `{report_dir}.tmp_{pid}_{ts}/`, then on success use
  `shutil.move(tmp, final)` (NOT `os.replace`, since the final dir may not exist
  on first write but may already exist on rerun — handle both cases by removing
  the existing one first if present, OR rename existing to `.bak` before move).
- After successful move, update `reports/latest`:
  - On POSIX: `os.symlink(report_dir, reports/latest)` (replacing existing)
  - On Windows: use `subprocess.run(["cmd", "/c", "mklink", "/J", ...])` for
    a directory junction (or just always copy — junctions need elevated perms
    sometimes). **Simpler approach**: write a 1-line text file
    `reports/latest.txt` containing the relative path, and have the API read
    that file as a pointer. This avoids cross-platform symlink mess.
- The API will be updated separately to honor `reports/latest.txt`.

### Tests
Add `tests/test_report_export.py`:
- Test that `export_result_tables` produces `weights/{strategy}.csv` for every
  strategy in the input dict
- Test that `selection_history.csv` has expected schema columns and is sorted
- Test that `manifest.json` is valid JSON with expected top-level keys
- Test that an exception during write does NOT leave a half-written
  `report_dir` (simulate by raising in the middle and asserting `report_dir`
  doesn't exist OR is the previous good version)
- Test that `reports/latest.txt` contains the relative path to the new run

Use small synthetic `BacktestResult` instances (single strategy, 5 dates,
3 coins) — no need to run the real engine.

### Don't change
- `pipeline.py` flow / public API
- `engine.py` / `BacktestResult` shape
- API code (this batch is pipeline-only)
- Existing tests that pass should still pass

## Files expected to change
- `src/atlas20/reporting/report.py` — main changes (extend `export_result_tables`)
- `src/atlas20/reporting/__init__.py` — re-export if needed
- New: `tests/test_report_export.py`
- Possibly new: `src/atlas20/reporting/manifest.py` if the manifest builder grows

## Acceptance

1. `pytest -q tests/` — all green (current 46 + new ~5)
2. Manually run `python -m atlas20.pipeline --config config/base.yaml` or a
   smaller smoke test if pipeline is slow; verify these files exist:
   - `reports/latest/weights/BTC_BH__always_on.csv` (and 29 others)
   - `reports/latest/selection_history.csv` (~thousands of rows)
   - `reports/latest/manifest.json` (valid JSON, ~30 artifacts listed)
   - `reports/latest.txt` (1 line, relative path)
3. `import json; json.loads(open("reports/latest/manifest.json").read())["artifacts"]`
   length matches actual file count in the dir
4. `pytest -q` second run is still all green (idempotency check)

## Commit format
Single commit:
```
feat(pipeline): X1-X4 weights + selection_history + manifest + atomic writes
```

Body: brief list of what was added per X-item, file count, test count.

## Out of scope (do NOT do in this batch)
- API changes — separate batch
- `pipeline.py` end-to-end refactor — only extend export_result_tables
- Reading manifest in API — separate batch
- Database — separate batch (Phase P)
- New external dependencies — use stdlib only

## After commit
Write `.ccg/tasks/batch-1-phase-x/review.md` summarizing:
- Files changed
- Tests added
- Manual smoke results (which files exist in reports/latest/)
- Any deviations from this brief
