# Contributing

Atlas20 is a research codebase. Contributions should preserve reproducibility,
avoid hidden data dependencies, and keep strategy assumptions explicit.

## Local Setup

```bash
python -m pip install -e ".[dev]"
npm --prefix apps/web install
```

## Verification

Run the release verification script before opening a pull request:

```bash
python scripts/verify_release.py
```

At minimum, changes should pass:

```bash
pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
```

## Guidelines

- Add tests for new strategy, API, or UI behavior.
- Keep generated research artifacts out of `reports/app_runs/`.
- Document any new data source, cache format, or survivorship-bias assumption.
- Do not commit API keys, private datasets, or exchange credentials.
