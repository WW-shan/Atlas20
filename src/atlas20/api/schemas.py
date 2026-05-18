"""Pydantic schemas for the Atlas20 R3 API contract."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


RunStatusEnum = Literal["queued", "running", "completed", "failed"]
StrategyFamily = Literal["ATLAS", "Momentum", "MeanRev", "Carry", "Other"]
ChartRange = Literal["1M", "3M", "YTD", "1Y", "ALL"]


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class StrictApiModel(BaseModel):
    """Request models reject unknown keys to surface frontend/backend drift."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ChampionSummary(ApiModel):
    strategy: str
    window_start: str
    window_end: str
    min_history_days: int | None = None
    min_daily_dollar_volume: float | None = None
    leader_pool: str | None = None
    rebalance_frequency: str | None = None
    regime_mode: str | None = None
    risk_off_asset: str | None = None
    initial_asset: str | None = None
    btc_stop_lookback_days: int | None = None
    btc_stop_confirm_days: int | None = None
    weight_momentum_rank: float | None = None
    weight_ret_21_rank: float | None = None
    weight_ret_42_rank: float | None = None
    weight_near_high_rank: float | None = None
    multiple: float
    total_return: float | None = None
    cagr: float
    sharpe: float
    max_drawdown: float
    annualized_turnover: float
    monthly_win_rate: float
    ending_equity: float


class StrategySummary(ApiModel):
    strategy: str
    multiple: float
    cagr: float
    sharpe: float
    max_drawdown: float
    annualized_turnover: float | None = None
    monthly_win_rate: float | None = None


class SeriesPoint(ApiModel):
    date: str
    value: float


class SelectionHistoryRow(ApiModel):
    rebalance_date: str
    coin_id: str
    coin_rank: int
    coin_score: float | None = None
    coin_weight: float


class Aum(ApiModel):
    current: float
    deltaPct: float
    sparkline: list[float]


class StrategyBreakdownItem(ApiModel):
    family: str
    count: int


class StrategiesBreakdown(ApiModel):
    total: int
    breakdown: list[StrategyBreakdownItem]


class RegimeInfo(ApiModel):
    label: Literal["RISK-ON", "NEUTRAL", "RISK-OFF"]
    score: float
    model: str


class RebalanceSwap(ApiModel):
    out: str
    in_: str = Field(alias="in")
    deltaPct: float


class RebalanceInfo(ApiModel):
    ts: str
    swaps: list[RebalanceSwap]


class EquityOverlayPoint(ApiModel):
    ts: str
    atlas: float
    btc: float


class EquityOverlay(ApiModel):
    series: list[EquityOverlayPoint]
    range: ChartRange


class HeroKpi(ApiModel):
    ytdReturn: float
    sharpe: float
    maxDd: float
    winRate: float


class OverviewPayload(ApiModel):
    champion: ChampionSummary
    top_strategies: list[StrategySummary]
    equity_curve: list[SeriesPoint]
    daily_returns: list[SeriesPoint]
    selection_history: list[SelectionHistoryRow]
    aum: Aum
    strategies: StrategiesBreakdown
    regime: RegimeInfo
    rebalance: RebalanceInfo
    equity_overlay: EquityOverlay
    hero_kpi: HeroKpi


class RunWindow(ApiModel):
    start: str
    end: str


class RunRow(ApiModel):
    run_id: str
    strategy: str
    strategy_family: StrategyFamily | None = None
    universe: str
    window: RunWindow
    status: RunStatusEnum
    return_pct: float | None = None
    sharpe: float | None = None
    max_dd: float | None = None
    duration_s: int | None = None
    eta_s: int | None = None
    spark: list[float] | None = None
    created_at: str
    favorited: bool | None = None


class RunRowSummary(ApiModel):
    run_id: str
    strategy: str
    status: RunStatusEnum
    duration_s: int | None = None
    eta_s: int | None = None
    params_summary: str


class RunDetailEquityOverlay(ApiModel):
    series: list[EquityOverlayPoint]


class RunKpi(ApiModel):
    cagr: float
    sharpe: float
    sortino: float
    max_dd: float
    calmar: float
    win_rate: float


class RunDetailPayload(RunRow):
    equity_overlay: RunDetailEquityOverlay
    kpi: RunKpi


class RunsListResponse(ApiModel):
    items: list[RunRow]
    total: int
    page: int
    pageSize: int


class BacktestUniverse(StrictApiModel):
    topN: int = Field(ge=1)
    excludeStable: bool
    excludeWrapped: bool


class BacktestWindow(StrictApiModel):
    start: date
    end: date
    rebalance: Literal["Weekly", "Biweekly", "Monthly"]

    @model_validator(mode="after")
    def validate_date_order(self) -> "BacktestWindow":
        if self.start > self.end:
            raise ValueError("start must be on or before end")
        return self


class BacktestAllocation(StrictApiModel):
    positionPct: float = Field(ge=0)
    slots: int = Field(ge=1)


class BacktestCosts(StrictApiModel):
    feeBps: float = Field(ge=0)
    slippageBps: float = Field(ge=0)


class BacktestConfig(StrictApiModel):
    preset: str
    universe: BacktestUniverse
    window: BacktestWindow
    allocation: BacktestAllocation
    costs: BacktestCosts


class HistoryFilter(ApiModel):
    q: str = ""
    chips: list[str] = Field(default_factory=list)
    dateRange: Literal["7d", "30d", "90d", "ytd", "all"] = "30d"
    view: Literal["list", "grid"] = "list"
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=14, ge=1)


CompareMetricKey = Literal[
    "cagr",
    "sharpe",
    "sortino",
    "max_dd",
    "calmar",
    "win_rate",
    "avg_turnover",
    "trades_per_year",
]


class CompareMetrics(ApiModel):
    cagr: dict[str, float]
    sharpe: dict[str, float]
    sortino: dict[str, float]
    max_dd: dict[str, float]
    calmar: dict[str, float]
    win_rate: dict[str, float]
    avg_turnover: dict[str, float]
    trades_per_year: dict[str, float]


class CompareSharedHolding(ApiModel):
    symbol: str
    count: int
    total: int


class CompareOverlap(ApiModel):
    symbols: list[str]
    matrix: list[list[float]]
    sharedHoldings: list[CompareSharedHolding]


class CompareEquityPoint(ApiModel):
    ts: str
    values: dict[str, float]


class ComparePayload(ApiModel):
    equity: list[CompareEquityPoint]
    metrics: CompareMetrics
    overlap: CompareOverlap


class UniverseTimelineSegment(ApiModel):
    token: str
    start: str
    end: str


class UniverseRotation(ApiModel):
    ts: str
    label: str


class UniverseRange(ApiModel):
    start: str
    end: str


class UniverseTimelinePayload(ApiModel):
    tokens: list[str]
    segments: list[UniverseTimelineSegment]
    rotations: list[UniverseRotation]
    range: UniverseRange


DataSourceStatus = Literal["healthy", "degraded", "error"]


class DataSource(ApiModel):
    id: str
    name: str
    status: DataSourceStatus
    last_sync_seconds: int


DataAlertSeverity = Literal["rose", "cyan", "emerald"]
DataAlertIcon = Literal["alert-triangle", "info", "check-circle"]


class DataAlert(ApiModel):
    id: str
    severity: DataAlertSeverity
    title: str
    meta: str
    ts: str
    icon: DataAlertIcon


ReportFormat = Literal["markdown", "pdf", "png", "csv"]
ReportStatus = Literal["ready", "generating"]
ReportThumbKind = Literal["equity", "lines", "heatmap", "bars", "horizontal-bars", "sparkbar"]


class FeaturedDigest(ApiModel):
    id: str
    title: str
    subtitle: str
    formats: list[ReportFormat]
    defaultFormat: ReportFormat
    generated_at: str


class ReportEntry(ApiModel):
    id: str
    title: str
    subtitle: str
    thumbnail: ReportThumbKind
    status: ReportStatus
    highlight: bool | None = None
    generated_at: str
    size_bytes: int
    report_type: Literal["weekly", "run", "compare", "universe"]
