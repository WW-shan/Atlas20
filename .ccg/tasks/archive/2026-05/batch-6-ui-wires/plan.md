# Plan

1. Update UI primitives needed by U12, especially `Button` `aria-busy` behavior and pager disabled support.
2. Wire `ResearchConsolePage` overview query loading/error states without blocking non-overview tabs.
3. Wire `BacktestStudioTab` detail and queue loading/error branches, keeping the run mutation disabled while pending.
4. Wire `RunHistoryTab` list loading/error/empty branches, disabled filter chips, disabled pager controls, and favorite-button busy state.
5. Wire `ReportsExportsTab` featured/archive loading/error/empty branches and disabled featured download controls.
6. Update tests with explicit `lib/api` mocks and add the required loading/error/empty/disabled cases.
7. Run checks, perform CCG review, archive the task, then stage and commit.
