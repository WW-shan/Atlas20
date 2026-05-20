ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply 2 remaining Opus 4.7 Info findings on Batch 10.

## Info I1 — Dialog backdrop mouseDown convention

**File:** `apps/web/src/components/ui/Dialog.tsx:85-87`

**Current:** backdrop closes on `onMouseDown` + currentTarget check.
**Opus note:** functionally OK but inverted from convention (most modals
close on `onClick`, not mouseDown). A click that starts inside panel and
drags out should NOT close. Current `onMouseDown` + currentTarget catches
this correctly but is non-obvious.

**Decision (Claude):** keep `onMouseDown` (it's actually MORE correct for
preventing accidental close on text-selection drag), but add a code
comment explaining why:

```tsx
// We use onMouseDown (not onClick) plus a currentTarget check.
// This prevents accidental close when a user starts text-selection
// inside the dialog panel and releases the mouse outside it — onClick
// would fire on the backdrop and incorrectly close. mouseDown + 
// currentTarget guarantees the press began on the backdrop itself.
onMouseDown={(e) => {
    if (e.target === e.currentTarget) onClose();
}}
```

**No test, no behavior change.**

**Commit:** `docs(ui): batch 10 reviewer pass — document Dialog mouseDown rationale`

## Info I2 — NewReportModal doesn't surface backend errors

**File:** `apps/web/src/features/reports/NewReportModal.tsx:60-64`

**Current:** `handleGenerate` calls API; on resolve closes modal, on
settle resets pending. But on REJECT (e.g., 422 validation), modal stays
open with no error message. Stub backend won't reject so this is latent,
but future Batch 12 real backend will.

**Decision (Claude):** add inline error state shown above the form's
Generate button. On API reject, capture `err.message`, show
`<div role="alert" className="...">{error}</div>`. Clear error on
input change.

```tsx
const [error, setError] = useState<string | null>(null);

const handleGenerate = async () => {
    setError(null);
    setPending(true);
    try {
        await generateReport({...});
        onClose();
    } catch (err) {
        setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
        setPending(false);
    }
};

// In JSX, above Generate button:
{error && (
    <div role="alert" className="...">{error}</div>
)}
```

**Test:** add Vitest case in `ReportsExportsTab.test.tsx`:
- Mock `generateReport` to reject with error
- Open modal, fill form, click Generate
- Assert error message visible with role="alert"
- Assert modal still open (not closed)
- Assert Generate button re-enabled

**Commit:** `fix(ui): batch 10 reviewer pass — surface generateReport errors in NewReportModal`

## Procedure

2 commits. Run pytest + npm test after each.

## Report

- 2 commit hashes
- Final frontend test count (was 131, expect 132)
- Backend unchanged at 220
- Any deviations
</TASK>
