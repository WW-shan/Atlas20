# Batch 17 — Smoke Follow-up Brief

## Goal

Fix the 3 Critical findings (A/B/C) uncovered by Claude's post-B16 manual
smoke. These were the missing round-2 cross-validation from B16
(ship-audit) — the 21-commit fixer pass landed but nobody actually
exercised it end-to-end. Smoke caught:

- **A** Stale `pip install .` shadowing `src/` made B11/B14/B16 fixes
  invisible at runtime (pytest still green because `pythonpath=["src"]`).
- **B** `build_markdown_report` 500'd on custom backtests that lacked
  `BTC_BH__always_on` / `TOP20_EQ__always_on` (hardcoded `.loc[...]`).
- **C** Worker process counters never reached the API's `/metrics`
  endpoint after B16 split the worker into its own service —
  prometheus_client counters are per-process.

## Scope

3 atomic commits, ~280 LOC + 9 new test cases.

| # | Commit                                                                                              | Files                                                                                                                                              |
| - | --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | `b4b9ed8 fix(reporting): batch 17 — graceful N/A fallback when benchmark strategies absent`         | `src/atlas20/reporting/report.py`, `tests/test_report_build.py`                                                                                    |
| 2 | `89a8b71 fix(api): batch 17 — worker exposes /metrics on dedicated port`                            | `src/atlas20/api/settings.py`, `src/atlas20/api/worker/main.py`, `docker-compose.yml`, `docs/operations/logging.md`, `.env.example`, `tests/test_worker_metrics.py` |
| 3 | `4f7c9f0 fix(infra): batch 17 — Makefile PYTHONPATH=src + README editable install + lifespan shadow warning` | `Makefile`, `README.md`, `src/atlas20/api/app.py`, `tests/test_app_lifespan_shadow.py`                                                              |

## Algorithm (key decisions)

### #1 Benchmark fallback

- Replaced unconditional `summary.loc["BTC_BH__always_on"]` with helper
  `_maybe_row(summary, name)` returning `pd.Series | None`.
- New helpers `_fmt_pct`, `_fmt_num`, `_benchmark_verdict`,
  `_sector_complexity_verdict` render `"N/A"` or
  `"N/A — no <X> benchmark in this run"` when the benchmark is absent.
- **Explicit rejection of fake-substitute**: a previous design draft
  proposed using the top-sharpe strategy as a stand-in benchmark. That
  was semantically wrong — the report labels these as "BTC benchmark" /
  "Equal-weight benchmark" and substituting an unrelated strategy would
  mislead users.

### #2 Worker `/metrics`

- New setting `worker_metrics_port: int = 8001`
  (env `ATLAS20_WORKER_METRICS_PORT`).
- `worker.main.start_metrics_server(port)` calls
  `prometheus_client.start_http_server(port)` once per process
  (idempotent via module-level flag + lock).
- `docker-compose.yml` worker service publishes `8001:8001`.
- `docs/operations/logging.md` documents the dual-scrape requirement
  and the `sum without (instance, job)` aggregation Prometheus queries
  must add.
- **Why not multiproc**: `PROMETHEUS_MULTIPROC_DIR` was considered and
  rejected — shared file state across processes adds race conditions
  on cleanup and the per-process /metrics model is the cleaner
  long-term shape (worker may grow latency histograms a DB collector
  could not reconstruct).

### #3 Shadow-install hardening

- `Makefile dev:` prepends `PYTHONPATH=src` as a safety net so the
  make target always wins over a stale install.
- `README.md` `Install` section recommends `pip install -e ".[dev]"` and
  documents the recovery path
  (`python -m pip uninstall -y atlas20-rotation`).
- `_warn_if_shadow_install()` runs in lifespan before alembic. It only
  fires when **both** `cwd/src/atlas20/__init__.py` exists (dev
  checkout) and `atlas20.__file__` lives outside that tree. Docker is
  silent: the image only copies `src/atlas20/api/db/migrations`, not
  the package root, so the `__init__.py` guard is False.

## Tests

1. `tests/test_report_build.py::test_build_markdown_report_renders_na_when_benchmarks_absent` — verifies no 500 and "N/A" literals appear.
2. `tests/test_report_build.py::test_build_markdown_report_preserves_benchmark_output_when_present` — sanity for the happy path.
3. `tests/test_worker_metrics.py::test_worker_metrics_port_default` — default 8001.
4. `tests/test_worker_metrics.py::test_worker_metrics_port_env_override` — env override.
5. `tests/test_worker_metrics.py::test_start_metrics_server_binds_configured_port` — port is forwarded to prometheus_client.
6. `tests/test_worker_metrics.py::test_start_metrics_server_is_idempotent` — second call is a no-op.
7. `tests/test_app_lifespan_shadow.py::test_warn_when_installed_copy_shadows_repo_src` — main shadow scenario warns.
8. `tests/test_app_lifespan_shadow.py::test_no_warning_when_no_repo_src` — Docker silent.
9. `tests/test_app_lifespan_shadow.py::test_no_warning_when_loaded_from_repo_src` — editable / PYTHONPATH=src silent.

## Out of scope (deferred)

- Actual `docker compose up -d --build` smoke against a daemon — local
  environment may not have docker available; the worker `/metrics`
  end-to-end check still relies on the unit test contract.
- Reverting / auditing every dashboard query for the
  `sum without (instance, job)` change — owner: ops.
- B16's pre-existing scope (21 commits, range `3bfb2df..b4b9ed8^`) —
  reviewers should still cross-check these for residual issues; B17
  commits build on that base.

## Acceptance

- `python -m pytest tests/ -q` → 351 passed, 2 skipped (was 348 after
  B17 #1, then +4 in #2, then +3 in #3; one prior flaky port test now
  reliably passes after multiple reruns).
- `npm --prefix apps/web test` → 161 passed (unchanged from B16).
- `python scripts/verify_release.py` exit 0.
- `git diff --check 3bfb2df..HEAD` clean.

## Review dimensions for reviewers

Each reviewer must explicitly mark **every original A/B/C finding**:
✅ RESOLVED + evidence (file:line) **or** ❌ STILL OPEN + reason.

Additionally:

1. Correctness — is each fix actually fixing the reported failure?
   Does `_warn_if_shadow_install` correctly avoid Docker false
   positives? Does `start_metrics_server` truly bind once?
2. Regression risk — does any change break existing pytest/vitest
   surfaces?
3. Cross-process Prometheus semantics — is the dashboard guidance
   (`sum without (instance, job)`) sufficient, or are there counters
   without `instance` we missed?
4. Test coverage gaps — should there be an end-to-end Prometheus
   scrape test that hits both targets?
5. Scan B16 commit range (`3bfb2df..b4b9ed8^`) for any post-fix
   issue that smoke would have caught.
