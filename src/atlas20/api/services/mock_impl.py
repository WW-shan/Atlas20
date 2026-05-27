"""In-memory service implementation for tests and storybook-style shells."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from sqlmodel import Session

from atlas20.api import mock_data
from atlas20.api.db.models import Run
from atlas20.api.schemas import (
    BacktestConfig,
    ComparePayload,
    DataAlert,
    DataSource,
    FeaturedDigest,
    OptionsPayload,
    OverviewPayload,
    ReportEntry,
    ReportFormat,
    RunDetailPayload,
    RunRow,
    RunRowSummary,
    UniverseTimelinePayload,
)


class MockConsoleService:
    def get_overview(self) -> OverviewPayload:
        return OverviewPayload.model_validate(deepcopy(mock_data.fallback_overview))

    def get_options_payload(self) -> OptionsPayload:
        return OptionsPayload.model_validate(deepcopy(mock_data.fallback_options))

    def get_compare(self, ids: list[str], range_: str) -> ComparePayload:
        del ids, range_
        return ComparePayload.model_validate(deepcopy(mock_data.fallback_compare))

    def register_new_backtest(self, session: Session, config: BacktestConfig) -> RunRowSummary:
        del session, config
        return RunRowSummary.model_validate(deepcopy(mock_data.fallback_runs_list[0]))

    def list_runs_queue(self, session: Session) -> list[RunRowSummary]:
        del session
        return [RunRowSummary.model_validate(row) for row in deepcopy(mock_data.fallback_runs_list[:2])]

    def list_runs(
        self,
        session: Session,
        q: str = "",
        chips: list[str] | None = None,
        date_range: str = "30d",
        page: int = 1,
        page_size: int = 14,
    ) -> tuple[list[RunRow], int]:
        del session, q, chips, date_range
        rows = [RunRow.model_validate(row) for row in deepcopy(mock_data.fallback_runs_list)]
        start = (max(page, 1) - 1) * max(page_size, 1)
        end = start + max(page_size, 1)
        return rows[start:end], len(rows)

    def get_run(self, session: Session, run_id: str) -> RunRow | None:
        del session
        for row in mock_data.fallback_runs_list:
            if row["run_id"] == run_id:
                return RunRow.model_validate(deepcopy(row))
        return None

    def get_run_detail(self, session: Session, run_id: str) -> RunDetailPayload | None:
        del session
        if run_id != mock_data.fallback_run_detail["run_id"]:
            return None
        return RunDetailPayload.model_validate(deepcopy(mock_data.fallback_run_detail))

    def toggle_run_favorite(self, session: Session, run_id: str) -> dict[str, object] | None:
        del session
        return {"run_id": run_id, "favorited": False}

    def request_run_cancel(self, session: Session, run_id: str) -> Run | None:
        del session, run_id
        return None

    def get_universe_timeline(self) -> UniverseTimelinePayload:
        return UniverseTimelinePayload.model_validate(deepcopy(mock_data.fallback_universe_timeline))

    def get_data_sources(self) -> list[DataSource]:
        return [DataSource.model_validate(row) for row in deepcopy(mock_data.fallback_data_sources)]

    def get_data_alerts(self) -> list[DataAlert]:
        return [DataAlert.model_validate(row) for row in deepcopy(mock_data.fallback_data_alerts)]

    def refresh_universe(self, session: Session) -> dict[str, str]:
        del session
        return {"run_id": "mock-universe-refresh", "status": "queued"}

    def get_universe_refresh_status(self, session: Session) -> dict[str, str | None]:
        del session
        return {"run_id": None, "status": "idle"}

    def get_featured_digest(self, session: Session) -> FeaturedDigest:
        del session
        return FeaturedDigest.model_validate(deepcopy(mock_data.fallback_featured_digest))

    def list_reports(self, sort: str = "recent", session: Session | None = None) -> list[ReportEntry]:
        del sort, session
        return [ReportEntry.model_validate(row) for row in deepcopy(mock_data.fallback_reports)]

    def resolve_download(self, report_id: str, fmt: ReportFormat | None, session: Session) -> tuple[Path, str, str]:
        del report_id, fmt, session
        raise NotImplementedError("MockConsoleService does not resolve report downloads")
