"""Pydantic schemas for the Atlas20 research console API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


StrategyFamily = Literal["momentum_lead"]
RiskMode = Literal["always_on", "bull_only"]
RiskOffAsset = Literal["cash", "bitcoin", "ethereum"]


class StrategySummary(BaseModel):
    strategy: str
    multiple: float
    cagr: float
    sharpe: float
    max_drawdown: float
    annualized_turnover: float | None = None
    monthly_win_rate: float | None = None


class ChampionResponse(BaseModel):
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


class SeriesPoint(BaseModel):
    date: str
    value: float


class SelectionHistoryRow(BaseModel):
    rebalance_date: str
    coin_id: str
    coin_rank: int
    coin_score: float | None = None
    coin_weight: float


class OverviewResponse(BaseModel):
    champion: ChampionResponse
    top_strategies: list[StrategySummary]
    equity_curve: list[SeriesPoint]
    daily_returns: list[SeriesPoint]
    selection_history: list[SelectionHistoryRow]


class OptionsResponse(BaseModel):
    strategy_families: list[str]
    top_n_values: list[int]
    frequencies: list[str]
    risk_modes: list[str]
    risk_off_assets: list[str]
    min_history_days: list[int]
    min_daily_dollar_volume: list[float]


class WindowInput(BaseModel):
    start_date: str
    end_date: str

    @model_validator(mode="after")
    def validate_date_order(self) -> "WindowInput":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class StrategyConfigInput(BaseModel):
    family: StrategyFamily
    top_n: int = Field(ge=1, le=4)
    frequency: Literal["7D", "14D", "biweekly", "monthly"]


class UniverseConfigInput(BaseModel):
    min_history_days: int = Field(ge=1, le=365)
    min_daily_dollar_volume: float = Field(ge=0)
    exclude_btc: bool = False


class RiskConfigInput(BaseModel):
    mode: RiskMode
    stop_lookback_days: int = Field(ge=0, le=365)
    confirm_days: int = Field(ge=1, le=30)
    risk_off_asset: RiskOffAsset


class WeightInput(BaseModel):
    momentum_rank: float = Field(ge=0)
    ret_21_rank: float = Field(ge=0)
    ret_42_rank: float = Field(ge=0)
    near_high_rank: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_weight_sum(self) -> "WeightInput":
        total = self.momentum_rank + self.ret_21_rank + self.ret_42_rank + self.near_high_rank
        if total <= 0:
            raise ValueError("at least one scoring weight must be positive")
        return self

    def normalized(self) -> dict[str, float]:
        values = {
            "momentum_rank": self.momentum_rank,
            "ret_21_rank": self.ret_21_rank,
            "ret_42_rank": self.ret_42_rank,
            "near_high_rank": self.near_high_rank,
        }
        total = sum(values.values())
        return {key: float(value) / total for key, value in values.items()}


class BacktestRequest(BaseModel):
    window: WindowInput
    strategy: StrategyConfigInput
    universe: UniverseConfigInput
    risk: RiskConfigInput
    weights: WeightInput


class RunStatus(BaseModel):
    run_id: str
    status: Literal["completed", "failed"]
    name: str
    summary: dict[str, float | str | int | None] = Field(default_factory=dict)
    error: str | None = None
