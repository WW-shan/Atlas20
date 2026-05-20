ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\reviewer.md
<TASK>
Round-2 security validation of Atlas20 Batch 11 reviewer fixes.

10 commits in scope, range `5f49e01..HEAD`:

```
107b764 chore: archive ccg task batch-11-round-1-reviewer-fixes
339cbdf fix(api): avoid SlowAPI response shadowing
fa2b145 docs(ops): document GET routes unauth'd in MVP
9108d0a fix(api): return principal id from verify_api_key, not raw key
ad1de55 docs(ops): document rate-limit per-process behavior
2b64b05 fix(api): refuse default secret_key in prod
0175c46 fix(api): rate-limit cancel route at 30/min
1c2c5ec fix(api): invalidate R7 cache on settings change
abbab97 fix(api): emit Retry-After header on 429
efa4738 fix(api): tighten CORS gates (dev origins + wildcard+credentials)
```

These address round-1 findings from Opus (2W+8I) and codex (2W).

For each commit verify the original finding is closed:
- efa4738 → Opus W1 + I1 (CORS allow_credentials + dev-origins-in-prod)
- abbab97 → Codex W (Retry-After header on 429)
- 1c2c5ec → Codex W (R7 cache settings invalidation)
- 0175c46 → Opus I6 (cancel rate limit)
- 2b64b05 → Opus I7 (secret_key prod gate)
- ad1de55 → Opus I2 (rate-limit per-process docs)
- 9108d0a → Opus I4 (verify_api_key returns principal)
- fa2b145 → Opus W2 (GET unauth'd docs)
- 339cbdf → codex internal review fix (response shadowing)

For each:
- Code change matches the brief
- Regression test exists (where applicable)
- No new race / regression

WATCH:
- efa4738: does the CORS validator reject dev origins ONLY in prod, not dev?
- abbab97: does the 429 test actually assert Retry-After numeric value?
- 1c2c5ec: is the cache keyed on (data_root, ts) or similar; settings change triggers recompute?
- 9108d0a: the principal id format consistent? Returns `client-{8 hex chars}`. Test asserts raw key NOT in returned value.
- 339cbdf: what was the shadowing? Look at the diff carefully.

Run yourself:
- `python -m pytest tests/ -x -q` (expect 264)
- `cd apps/web && npm run test -- --run` (expect 132)
- `cd apps/web && npm run lint && npm run typecheck`

AUTHORITY: apply additional fixes ONLY for new Critical/Warning.
Commit: `fix(api): batch 11 round 2 — <summary>`.

REPORT:
- Score X/100
- Per-commit: ✅ RESOLVED / ❌ STILL OPEN
- New findings: Critical/Warning/Info
- Fixes applied: commits or 'none'
- Final test count
- Verdict: APPROVE / REQUEST_CHANGES

If no new findings AND all originals closed → APPROVE.

Keep under 1000 words.
</TASK>
