# Batch 23a Round 1 — Codex Reviewer Report

> Note: codex printed this report to stdout instead of writing it directly (interpreted read-only role as no-write). Captured verbatim from session stdout.
> Session-ID: 019e4d09-d1ae-7b51-ae1f-0e6d5732a3b8

**Verdict:** REQUEST_CHANGES
**Score:** 84/100

| id | severity | file:line | description | fix direction | requires_regression_test |
|---|---|---:|---|---|---|
| W1 | Warning | `apps/web/src/features/overview/OverviewTab.tsx:136` | Accessible labels still say YTD/year-to-date even when backend range is `ALL`; screen-reader UX still lies. | Build card/chart aria labels from `equity_overlay.range`, `atlas_label`, `btc_label`. | Yes |
| W2 | Warning | `src/atlas20/api/data_access/overview.py:302` | `_compute_last_sync_seconds` bypasses `_latest_report_dir` safety and can stat an existing path outside `report_root` if `latest.txt` is malicious/bad. | Reuse `_latest_report_dir` or apply same `relative_to(report_root)` guard and require directory targets. | Yes |
| W3 | Warning | `tests/test_overview_data_access.py:196` | Requested edge regressions are not locked: duplicate rebalance dates, clock skew, broken pointer fallback, NaN-only YTD slice. Code appears mostly correct, but tests are thin. | Add focused tests for those four cases. | Yes |
| I1 | Info | `src/atlas20/api/mock_data.py:9` | `mock_data.py` changed despite out-of-scope note, but only to keep fallback schema-compatible with required new fields. | No action. | No |

**Brief Tests 1-13**
1 COVERED `tests/test_overview_data_access.py:182`
2 COVERED `:192`
3 COVERED `:196`
4 COVERED `:207`
5 COVERED basic pointer/missing cases `:212`, but edge coverage weak per W3
6 COVERED `:223`
7 COVERED `:239`
8 COVERED `apps/web/src/features/overview/OverviewTab.test.tsx:18`
9 COVERED `:33`
10 COVERED `:49`
11 COVERED `:60`
12 COVERED `:74`
13 COVERED `:12-15`

No critical security issues, SQL/command injection, secrets, or raw HTML sinks were introduced. Frontend tablist removal is clean: no remaining `role="tab"`, `tablist`, or `aria-selected` in `OverviewTab.tsx`.

REVIEW COMPLETE — REQUEST_CHANGES — Findings: 0 Critical, 3 Warning, 1 Info.
