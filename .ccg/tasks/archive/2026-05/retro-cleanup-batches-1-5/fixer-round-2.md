ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply 2 Info findings from Opus 4.7 round-2 review on Atlas20.

## Fix #1 — `_latest_report_dir` path-traversal containment

File: `src/atlas20/api/data_access/_common.py` (around lines 13-25, `_latest_report_dir` function)

Current behavior: reads `report_root/latest.txt`, resolves `report_root / target_name`, returns if exists. If `latest.txt` contains `../../etc/passwd` or an absolute path, target could escape report_root.

Fix: after building target, verify `target.resolve()` is inside `report_root.resolve()`. If not, raise ValueError("latest.txt points outside report_root"). Continue to use `target` (not `target.resolve()`) for downstream code that may rely on the unresolved path.

```python
def _latest_report_dir(report_root: Path) -> Path:
    pointer = report_root / "latest.txt"
    if pointer.exists():
        try:
            target_name = pointer.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(f"Could not read {pointer}: {exc}") from exc
        if target_name:
            target = report_root / target_name
            resolved_root = report_root.resolve()
            resolved_target = target.resolve()
            try:
                resolved_target.relative_to(resolved_root)
            except ValueError as exc:
                raise ValueError(
                    f"latest.txt points outside report_root: {target_name!r}"
                ) from exc
            if target.exists():
                return target
    fallback = report_root / "latest"
    return fallback if fallback.exists() else report_root
```

Test: add to `tests/test_latest_pointer.py`:
- given `latest.txt` contains `../escape`, assert ValueError
- given `latest.txt` contains absolute path `/etc/passwd` (or `C:\\Windows` on Windows), assert ValueError

Commit: `fix(api): retro — guard _latest_report_dir against path-traversal`

## Fix #2 — Featured digest title separator

File: `src/atlas20/api/services.py:282` (in `get_featured_digest`)

Current: title = `f"Atlas20 Digest - {generated_date}"` (ASCII hyphen)
Mock at `mock_data.py:556` uses `—` (em-dash).
Frontend `apps/web/src/lib/api.ts:500` uses `—`.

Fix: change title to use em-dash:
```python
"title": f"Atlas20 Digest — {generated_date}",
```

Test: update `tests/test_featured_digest.py` if it asserts the title format. Add assertion that title contains `"—"`.

Commit: `fix(api): retro — align featured digest title separator to em-dash`

## Procedure

1. Apply Fix #1 first (more invasive, includes regression test)
2. Run `python -m pytest tests/ -x -q` — green
3. Apply Fix #2
4. Run `python -m pytest tests/ -x -q` — green again
5. Each fix = separate commit

## Report

- 2 commit hashes
- Final test count (should be 119 + 2 new tests = 121)
- Any deviations
</TASK>
