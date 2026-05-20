# Review

## Verification

- `python -m pytest tests/ -x -q`: 286 passed, 2 skipped.
- `npm run lint` in `apps/web`: clean.
- `npm run typecheck` in `apps/web`: clean.

## Self-review checks

- Download paths resolve under `settings.report_root` before streaming.
- `report_manifest.json` is enforced when present; file sha256 and size must match.
- DB sha256 is checked when a manifest is absent.
- `POST /api/reports/generate` keeps `verify_api_key` and the existing `5/minute` limiter.
- Logs use run ids and errors only; no raw API key values are logged.
- APScheduler is disabled by `ATLAS20_DISABLE_SCHEDULER=1` in tests and imports lazily at runtime.

## Notes

- External CCG dual-model review was not run because `~/.claude/bin/codeagent-wrapper` is not present in this environment.
