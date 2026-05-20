# Batch 15 — Phase D + Phase A + R3 Polish

## Goal

Complete the MS-3 production-readiness roadmap by landing Phase D (Docker /
CI / DX tooling), Phase A (a11y polish), and the deferred R3 redesign review
items (C4 / W2 / W7 / W8). After this batch, MS-3 is done — repo is ready
for tagged release.

## Scope (~650 LOC across infra + ~30 tests + a11y + UI cleanups)

### Phase D — Docker / CI / DX

#### D1 — Backend Dockerfile

**File:** `Dockerfile` (repo root).

Multi-stage build. Builder stage installs `pyproject.toml` deps; runtime is
slim image with non-root user. HEALTHCHECK uses the new `/healthz` endpoint
from B14.

```dockerfile
# Build stage
FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev \
    libpango-1.0-0 libpangoft2-1.0-0  # weasyprint native deps
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --user -e ".[dev]"

# Runtime stage
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 atlas
USER atlas
WORKDIR /app
COPY --from=builder --chown=atlas:atlas /root/.local /home/atlas/.local
COPY --chown=atlas:atlas pyproject.toml ./
COPY --chown=atlas:atlas src ./src
COPY --chown=atlas:atlas docs ./docs
ENV PATH=/home/atlas/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1
CMD ["uvicorn", "atlas20.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

Add `.dockerignore` (root): `.git`, `.venv`, `__pycache__`, `node_modules`,
`apps/web/node_modules`, `data/`, `reports/`, `*.pyc`, `.pytest_cache`,
`.ccg/tasks/archive`.

#### D2 — Frontend Dockerfile

**File:** `apps/web/Dockerfile`.

Multi-stage: node builder → nginx runtime serving `dist/`.

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig*.json vite.config.* index.html ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -q --spider http://127.0.0.1/ || exit 1
```

Bundled `apps/web/nginx.conf`: SPA fallback to `index.html`, gzip enabled,
proxy `/api/*` to `http://backend:8000`.

#### D3 — docker-compose

**File:** `docker-compose.yml` (repo root).

```yaml
services:
  backend:
    build: .
    environment:
      ATLAS20_ENV: dev
      ATLAS20_DB_URL: sqlite:///./data/atlas20.sqlite
      ATLAS20_REPORT_ROOT: /app/reports
      ATLAS20_DATA_ROOT: /app/data
      ATLAS20_DISABLE_SCHEDULER: "0"
    volumes:
      - ./data:/app/data
      - ./reports:/app/reports
    ports: ["8000:8000"]
  web:
    build: ./apps/web
    depends_on: [backend]
    ports: ["5173:80"]
```

#### D4 — `.env.example` audit

Already exists; extend with Batch 11/13/14 additions: `ATLAS20_SENTRY_DSN=`,
`ATLAS20_LOG_FILE_PATH=`, `ATLAS20_DISABLE_SCHEDULER=0`. Add comments
documenting each.

#### D5 — Makefile

**File:** `Makefile` (repo root).

```makefile
.PHONY: dev test test-fast lint typecheck build docker-build backup clean

dev:
\tuvicorn atlas20.api.app:create_app --factory --reload --host 127.0.0.1 --port 8000

test:
\tpython -m pytest tests/ -q
\tnpm --prefix apps/web test -- --run

test-fast:
\tpython -m pytest tests/ -x -q --ff

lint:
\truff check src tests
\tnpm --prefix apps/web run lint

typecheck:
\tmypy --strict src/atlas20/api
\tnpm --prefix apps/web run typecheck

build:
\tnpm --prefix apps/web run build

docker-build:
\tdocker compose build

backup:
\tpython -m atlas20.api.backup

clean:
\trm -rf .pytest_cache .mypy_cache apps/web/node_modules apps/web/dist
```

#### D6 — Extend CI

**File:** `.github/workflows/ci.yml`.

Add jobs: `ruff` on Python, `mypy --strict src/atlas20/api/`, `tsc --noEmit`
on web, separate `deploy` job triggered on tag matching `v*` (skip
implementation — print "deploy stub", real publish wires after first tag).

#### D7 — pre-commit

**File:** `.pre-commit-config.yaml`.

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.1.0
    hooks:
      - id: prettier
        files: ^apps/web/.*\.(ts|tsx|css|json|md)$
  - repo: local
    hooks:
      - id: eslint
        name: eslint
        entry: bash -c 'cd apps/web && npm run lint'
        language: system
        files: ^apps/web/src/.*\.(ts|tsx)$
        pass_filenames: false
```

#### D9 — README quickstart

**File:** `README.md` — keep existing if good; add a "30-minute Quickstart"
section pointing at `make dev`, `docker compose up`, the `/healthz` probe,
seed CLI from Batch 7.

#### D10 — Disk quota note

**File:** `docs/operations/storage.md` (new). Document `reports/` and `data/`
growth expectations, the `make backup` retention policy from Batch 7, and
suggest a cron probe like `du -sh reports/ data/ | logger -t atlas20-disk`.
No code — documentation only.

### Phase A — A11y

Already in place: `lucide-react` icons (semantic), most buttons have
aria-labels. Confirmed via Batch 12 R3 audit. Gaps:

#### A1 — axe-core in CI

**Files:** `apps/web/package.json`, `apps/web/src/test/axe.test.tsx` (new).

Add devDeps: `vitest-axe`, `@axe-core/playwright` (defer playwright to
A6 below — out of scope this batch; just vitest-axe for the per-tab tests).

For each top-level tab component, render with `<QueryClientProvider>` + a
fresh DOM and run `expect(await axe(container)).toHaveNoViolations()`.
Defer if Vitest's jsdom lacks the surfaces axe needs (color contrast may be
unsupported in jsdom — disable that rule).

#### A2 — Skip-to-content + keyboard nav

**File:** `apps/web/src/pages/ResearchConsolePage.tsx`.

Add `<a href="#main-content" className="skip-link">Skip to content</a>` as
the first child. Style in `index.css` to position off-screen until focused.
Tag the main content region with `id="main-content"`. Keyboard test:
Tab from page load → first focusable is the skip link.

#### A3 — Live regions

**File:** `apps/web/src/components/ui/Pill.tsx`, `Toast.tsx` (new or existing).

Status `<Pill>` already pulses; add `aria-live="polite"` to the container
that holds run status updates. For backtest-queue Toast messages, wrap in
`role="status"` + `aria-live="polite"`.

#### A4 — Color contrast AA

Run a Lighthouse / axe sweep against the dark theme. Specifically:
- `var(--muted)` against `var(--bg)` — Batch 14 may have introduced thin
  text. Bump contrast if any pair falls below 4.5:1.
- Gold KPI labels on dark cards — usually high contrast but verify.

Output: a single commit adjusting CSS custom properties if any pair fails.

#### A7 — Mobile responsive

Audit at 375 / 768 / 1024. Specifically:
- Tab switcher overflow horizontally scrollable on 375?
- Run table → card view on 768?
- Compare strategy chips stacked at 375?

May produce 1-3 commits fixing critical break-points; defer cosmetic
adjustments.

#### A8 — ErrorBoundary

**File:** `apps/web/src/components/ui/ErrorBoundary.tsx` (new).

React class component catches render errors per page, displays
`<ErrorBanner>` + "Reload" CTA. Wrap each tab's outer component in
`<ErrorBoundary>` in `ResearchConsolePage.tsx`.

### R3 deferred items

#### C4 — Gold token concentration audit

**Files:** various via grep.

Per Batch 12 review.md C4: catalog every `var(--gold)` usage; decide on the
canonical whitelist. Decision (Claude):
- KEEP gold for: champion KPI value, primary CTA (DOWNLOAD ALL · BUNDLE,
  RUN BACKTEST), gold-outline Pill for FEATURED tag, favorited toggle.
- DOWNGRADE to violet/cyan: any selection-borderColor (use violet for
  active/selected); page number active state (use violet); sparkline strokes
  (use violet/cyan tone).

Concretely: edit `apps/web/src/components/ui/Pager.tsx:46` (gold →
`var(--violet)`), `apps/web/src/components/history/RunTable.tsx:126`
(border gold → border violet for selected row), `apps/web/src/features/history/RunHistoryTab.tsx:216`
(borderColor isSelected gold → violet). Sparkline gold tone is already
optional via prop — leave the API as-is.

Adjust corresponding tests asserting gold styling.

#### W2 — `.mono` wrap audit

Grep for HTML numeric / timestamp / percentage renders not in `<span className="mono">`:

```bash
grep -rn "toFixed\|toISOString\|toLocaleString" apps/web/src/components apps/web/src/features
```

For each finding, wrap the rendered value in `<span className="mono">{...}</span>`.
~10 sites expected.

#### W7 — Tab loading / error / empty state tests

**Files:** `apps/web/src/features/*/tests/`.

For each of the 6 tabs (Overview, Backtest, History, Universe, Compare,
Reports):
- Render with `useQuery` mocked to `isLoading=true` → assert `<Skeleton>` visible.
- Mocked to `isError=true` → assert `<ErrorBanner>` visible + retry button works.
- Mocked to `data=[]` → assert `<EmptyState>` visible (if applicable).

~12 new tests (2 per tab; some tabs have more queries).

#### W8 — Stale CSS cleanup

**File:** `apps/web/src/styles/index.css`.

Grep selectors against actual usage in source tree. Remove orphaned rules.
Estimate: ~30 lines deletable based on Batch 12 R3 audit pointer.

```bash
# Pseudo-audit:
grep -oE '^\.[a-zA-Z][a-zA-Z0-9_-]+' apps/web/src/styles/index.css | sort -u | while read sel; do
    cls="${sel:1}"
    if ! grep -rq "className=.*\b$cls\b\|class=.*\b$cls\b" apps/web/src/; then
        echo "orphan: $sel"
    fi
done
```

Manually verify each "orphan" (some CSS targets non-className like
`.dark *` or attribute selectors).

## Algorithm decisions

- **Docker base**: `python:3.11-slim` + `node:22-alpine` + `nginx:1.27-alpine`.
  Avoid Alpine for Python (compiles slow due to musl). Stick with slim Debian.
- **Frontend nginx**: simple SPA + reverse proxy. Don't add TLS termination
  in MVP (handled by upstream cloud LB).
- **CI deploy stub**: print-only for now. Real GitHub Actions deploy wires
  after first tagged release.
- **mypy --strict**: only `src/atlas20/api/` in MVP. Full strict on
  `src/atlas20/` (pipeline) is bigger refactor; track for post-MS-3.
- **Pre-commit ruff fixed args**: format + check; users opt-in by running
  `pre-commit install`.
- **A11y test boundary**: Vitest + axe-core covers HTML/ARIA structural
  issues. Color contrast and visual-only checks deferred to manual Lighthouse
  audit (A4) since jsdom can't render color.
- **R3 gold downgrade**: violet for "active/selected" semantics (cool
  accent), gold reserved for "premium/featured" semantics (warm accent).
  This matches the original R3 design system intent.

## Tests (~30 new)

1. `tests/test_docker_build.py` (optional MVP — skip if Docker not available
   in CI; uses `subprocess.run(["docker", "build"])` with `pytest.skipif`)
2. `apps/web/src/test/axe.test.tsx` — 6 cases (one per tab)
3. `apps/web/src/components/ui/ErrorBoundary.test.tsx` — 2 cases (renders
   children on success; renders banner on throw)
4. `apps/web/src/pages/ResearchConsolePage.test.tsx` — skip-link a11y assertions
5. ~12 tab state coverage tests (W7) split across feature dirs

Backend: no new tests (no Python source changes beyond Dockerfile / Makefile / CI).

## Out of scope

- TLS termination / cert-manager integration
- Multi-region deployment
- Lighthouse CI automation (manual sweep only this batch)
- E2E Playwright (defer to post-MS-3)
- Light theme (per Roadmap A6 — dropped)
- i18n (per Roadmap A5 — dropped)

## Acceptance

- `python -m pytest tests/ -q` → 327 (no backend changes)
- `cd apps/web && npm run test -- --run` → 132 → ~150 (+ a11y + ErrorBoundary + W7 state coverage)
- `cd apps/web && npm run lint && npm run typecheck` → clean
- `make lint typecheck` → clean (assuming dev installs ruff + mypy)
- `docker compose build` → both images build (test manually if docker available)
- Lighthouse a11y score ≥ 90 on each tab (manual)
- `git diff --check a6a5733..HEAD` → clean

## Files expected to change

| File | Action | Est LOC |
|---|---|---|
| `Dockerfile` | New (backend multi-stage) | +35 |
| `apps/web/Dockerfile` | New (frontend multi-stage) | +20 |
| `apps/web/nginx.conf` | New | +15 |
| `.dockerignore` | New | +15 |
| `docker-compose.yml` | New | +25 |
| `.env.example` | Extend with B11/13/14 vars | +10 |
| `Makefile` | New | +40 |
| `.pre-commit-config.yaml` | New | +25 |
| `.github/workflows/ci.yml` | Add ruff / mypy / tsc / deploy stub | +60 |
| `README.md` | Quickstart section | +50 |
| `docs/operations/storage.md` | New | +40 |
| `pyproject.toml` | Add `ruff`, `mypy` to dev deps | +5 |
| `apps/web/package.json` | Add `vitest-axe` | +3 |
| `apps/web/src/components/ui/ErrorBoundary.tsx` | New | +60 |
| `apps/web/src/pages/ResearchConsolePage.tsx` | Skip link + wrap tabs in ErrorBoundary | +20 |
| `apps/web/src/styles/index.css` | Skip-link rule + dead CSS removal | +25 -30 |
| `apps/web/src/components/ui/Pill.tsx` | aria-live for status pills | +5 |
| `apps/web/src/components/ui/Pager.tsx:46` | gold → violet for active page | +0 (1-char) |
| `apps/web/src/components/history/RunTable.tsx:126` | gold → violet for selected border | +0 |
| `apps/web/src/features/history/RunHistoryTab.tsx:216` | gold → violet for selected | +0 |
| `apps/web/src/features/**/*.tsx` (W2 `.mono` wrap, ~10 sites) | wrap numeric values | +20 |
| `apps/web/src/test/axe.test.tsx` | New | +80 |
| `apps/web/src/components/ui/ErrorBoundary.test.tsx` | New | +30 |
| `apps/web/src/features/**/state-coverage.test.tsx` | New per tab (6 files) | +150 |
| **Total** | | **~730 (300 infra + 350 ui + 80 docs)** |
