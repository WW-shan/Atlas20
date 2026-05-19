# Requirements

- Frontend-only Batch 6 UI wiring for U4, U5, U7, U9, and U12.
- Remove fallback-first rendering in the affected tabs where it prevents first-load loading/error states.
- Use the real UI component signatures on disk:
  - `Skeleton({ variant: "text" | "chart" | "table" | "card", width?, height? })`
  - `EmptyState({ title, sub?, action? })`
  - `ErrorBanner({ message, onRetry? })`
  - `Button({ variant, size?, loading?, disabled?, onClick?, children })`
- Keep tab switching responsive: overview loading/error must not block other tab content.
- Add Vitest + Testing Library coverage with explicit `lib/api` mocks per affected test file.
- Run the required frontend and backend verification commands.
