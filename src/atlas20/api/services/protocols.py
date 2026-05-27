"""Service-layer interfaces used by FastAPI routes."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from sqlmodel import Session

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


@runtime_checkable
class ConsoleService(Protocol):
    """Contract consumed by route modules.

    The legacy module-level functions remain as the compatibility API; this
    protocol gives routes and tests a narrow injectable seam without forcing a
    large service-layer rewrite.
    """

    def get_overview(self) -> OverviewPayload: ...

    def get_options_payload(self) -> OptionsPayload: ...

    def get_compare(self, ids: list[str], range_: str) -> ComparePayload: ...

    def register_new_backtest(self, session: Session, config: BacktestConfig) -> RunRowSummary: ...

    def list_runs_queue(self, session: Session) -> list[RunRowSummary]: ...

    def list_runs(
        self,
        session: Session,
        q: str = "",
        chips: list[str] | None = None,
        date_range: str = "30d",
        page: int = 1,
        page_size: int = 14,
    ) -> tuple[list[RunRow], int]: ...

    def get_run(self, session: Session, run_id: str) -> RunRow | None: ...

    def get_run_detail(self, session: Session, run_id: str) -> RunDetailPayload | None: ...

    def toggle_run_favorite(self, session: Session, run_id: str) -> dict[str, object] | None: ...

    def request_run_cancel(self, session: Session, run_id: str) -> Run | None: ...

    def get_universe_timeline(self) -> UniverseTimelinePayload: ...

    def get_data_sources(self) -> list[DataSource]: ...

    def get_data_alerts(self) -> list[DataAlert]: ...

    def refresh_universe(self, session: Session) -> dict[str, str]: ...

    def get_universe_refresh_status(self, session: Session) -> dict[str, str | None]: ...

    def get_featured_digest(self, session: Session) -> FeaturedDigest: ...

    def list_reports(self, sort: str = "recent", session: Session | None = None) -> list[ReportEntry]: ...

    def resolve_download(self, report_id: str, fmt: ReportFormat | None, session: Session) -> tuple[Path, str, str]: ...
