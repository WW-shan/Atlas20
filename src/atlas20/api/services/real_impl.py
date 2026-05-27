"""Default service implementation that delegates to the legacy functions."""

from __future__ import annotations

from pathlib import Path

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


class RealConsoleService:
    def get_overview(self) -> OverviewPayload:
        from atlas20.api import services

        return services.get_overview()

    def get_options_payload(self) -> OptionsPayload:
        from atlas20.api import services

        return services.get_options_payload()

    def get_compare(self, ids: list[str], range_: str) -> ComparePayload:
        from atlas20.api import services

        return services.get_compare(ids, range_)

    def register_new_backtest(self, session: Session, config: BacktestConfig) -> RunRowSummary:
        from atlas20.api import services

        return services.register_new_backtest(session, config)

    def list_runs_queue(self, session: Session) -> list[RunRowSummary]:
        from atlas20.api import services

        return services.list_runs_queue(session)

    def list_runs(
        self,
        session: Session,
        q: str = "",
        chips: list[str] | None = None,
        date_range: str = "30d",
        page: int = 1,
        page_size: int = 14,
    ) -> tuple[list[RunRow], int]:
        from atlas20.api import services

        return services.list_runs(
            session,
            q=q,
            chips=chips,
            date_range=date_range,
            page=page,
            page_size=page_size,
        )

    def get_run(self, session: Session, run_id: str) -> RunRow | None:
        from atlas20.api import services

        return services.get_run(session, run_id)

    def get_run_detail(self, session: Session, run_id: str) -> RunDetailPayload | None:
        from atlas20.api import services

        return services.get_run_detail(session, run_id)

    def toggle_run_favorite(self, session: Session, run_id: str) -> dict[str, object] | None:
        from atlas20.api import services

        return services.toggle_run_favorite(session, run_id)

    def request_run_cancel(self, session: Session, run_id: str) -> Run | None:
        from atlas20.api import services

        return services.request_run_cancel(session, run_id)

    def get_universe_timeline(self) -> UniverseTimelinePayload:
        from atlas20.api import services

        return services.get_universe_timeline()

    def get_data_sources(self) -> list[DataSource]:
        from atlas20.api import services

        return services.get_data_sources()

    def get_data_alerts(self) -> list[DataAlert]:
        from atlas20.api import services

        return services.get_data_alerts()

    def refresh_universe(self, session: Session) -> dict[str, str]:
        from atlas20.api import services

        return services.refresh_universe(session)

    def get_universe_refresh_status(self, session: Session) -> dict[str, str | None]:
        from atlas20.api import services

        return services.get_universe_refresh_status(session)

    def get_featured_digest(self, session: Session) -> FeaturedDigest:
        from atlas20.api import services

        return services.get_featured_digest(session)

    def list_reports(self, sort: str = "recent", session: Session | None = None) -> list[ReportEntry]:
        from atlas20.api import services

        return services.list_reports(sort, session)

    def resolve_download(self, report_id: str, fmt: ReportFormat | None, session: Session) -> tuple[Path, str, str]:
        from atlas20.api import services

        return services.resolve_download(report_id, fmt, session)
