"""Pydantic configuration models for Atlas20."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class PathConfig(BaseModel):
    raw_dir: str
    processed_dir: str
    reports_dir: str


class LoggingConfig(BaseModel):
    level: str = "INFO"


class UniverseConfig(BaseModel):
    universe_size: int = 20
    current_top_n_candidates: int = 60
    legacy_candidate_ids: list[str] = Field(default_factory=list)
    # CMC drops a symbol from its listing when a coin rebrands or migrates,
    # but keeps serving the history under the same numeric id. Without these
    # aliases the retired ticker resolves to "no id" and the asset silently
    # disappears from the candidate pool - survivorship bias again, just via
    # the id map instead of the ranking.
    cmc_symbol_aliases: dict[str, int] = Field(default_factory=dict)
    min_history_days: int = 90
    min_daily_dollar_volume: float = 25_000_000
    min_price: float = 1e-6
    exclude_wrapped_assets: bool = True
    stablecoin_ids: list[str] = Field(default_factory=list)
    excluded_ids: list[str] = Field(default_factory=list)
    name_exclusion_keywords: list[str] = Field(default_factory=list)
    symbol_exclusion_keywords: list[str] = Field(default_factory=list)
    category_exclusion_keywords: list[str] = Field(default_factory=list)


class RegimeConfig(BaseModel):
    btc_ma_window: int = 120
    tracked_total_mcap_ma_window: int = 120
    tracked_alt_mcap_momentum_window: int = 60
    use_btc_ma: bool = True
    use_tracked_total_mcap_ma: bool = True
    use_tracked_alt_momentum: bool = False
    combine_method: Literal["all", "any", "majority"] = "all"


class RebalancingConfig(BaseModel):
    frequencies: dict[str, str] = Field(default_factory=lambda: {"monthly": "month_end", "biweekly": "14D"})


class FrictionConfig(BaseModel):
    fee_bps: float = 10.0
    slippage_bps: float = 10.0
    max_weight_per_coin: float = 0.35
    max_weight_per_sector: float = 0.50
    missing_return_fill: float = 0.0


class SignalsConfig(BaseModel):
    momentum_windows: dict[int | str, float]
    sector_score_weights: dict[str, float]

    @model_validator(mode="after")
    def validate_weights(self) -> "SignalsConfig":
        momentum_sum = sum(float(v) for v in self.momentum_windows.values())
        sector_sum = sum(float(v) for v in self.sector_score_weights.values())
        if abs(momentum_sum - 1.0) > 1e-6:
            raise ValueError(f"Momentum weights must sum to 1.0, got {momentum_sum}")
        if abs(sector_sum - 1.0) > 1e-6:
            raise ValueError(f"Sector score weights must sum to 1.0, got {sector_sum}")
        return self

    def momentum_weight_map(self) -> dict[int, float]:
        return {int(k): float(v) for k, v in self.momentum_windows.items()}


class StrategyConfig(BaseModel):
    momentum_hold_counts: list[int] = Field(default_factory=lambda: [4, 6, 8])
    momentum_frequencies: list[str] = Field(default_factory=lambda: ["monthly", "biweekly"])
    sector_top_k: list[int] = Field(default_factory=lambda: [2, 3, 4])
    sector_frequencies: list[str] = Field(default_factory=lambda: ["monthly", "biweekly"])
    sector_max_coins_per_sector: int = 2
    include_bull_filter_variants: bool = True
    include_small_cap_comparison: bool = False


class CoinGeckoConfig(BaseModel):
    base_url: str = "https://api.coingecko.com/api/v3"
    rate_limit_seconds: float = 1.25
    timeout_seconds: int = 30
    vs_currency: str = "usd"
    max_retries: int = 5
    retry_backoff_seconds: float = 2.0


class CoinMarketCapConfig(BaseModel):
    base_url: str = "https://api.coinmarketcap.com/data-api/v3.1"
    # Full history window pulled once per refresh. It deliberately starts well
    # before the backtest window so universe-eligibility lookback is covered.
    history_start: str = "2020-01-01"
    timeout_seconds: int = 30
    convert_id: str = "2781"  # USD
    page_size: int = 400
    request_interval_seconds: float = 1.0
    # How many trailing days to re-pull when the cache is merely stale. Keeps
    # a daily refresh to one request per coin instead of a full re-download.
    tail_refresh_days: int = 5


class ProvidersConfig(BaseModel):
    """Only two providers remain: CoinGecko for the catalog, CMC for history."""

    coingecko: CoinGeckoConfig
    coinmarketcap: CoinMarketCapConfig = Field(default_factory=CoinMarketCapConfig)


class ReportingConfig(BaseModel):
    rolling_window_days: int = 365
    selected_strategies_for_plots: list[str] = Field(default_factory=list)


class DataQualityConfig(BaseModel):
    """How much real provider history an asset must have to enter the panel."""

    min_price_days: int = 60
    min_market_cap_days: int = 60
    require_metadata: bool = False
    # Independent verification of recent CoinMarketCap prints against
    # CoinGecko. CMC is a single point of failure: it served Huobi Token at
    # 1/250000th of its real price for 34 days while staying internally
    # consistent. Nothing but a second provider catches that.
    cross_check_recent_days: int = 365
    cross_check_min_overlap_days: int = 30
    cross_check_max_median_gap: float = 0.10
    cross_check_max_latest_gap: float = 0.35
    exclude_on_cross_check_failure: bool = True
    # An asset whose second source is unavailable is "unverified", not
    # "disagreeing". Default: admit it (a CoinGecko outage must not halt the
    # whole pipeline) but record it, so the audit can surface it. Set this to
    # true to refuse anything you could not independently confirm.
    require_cross_check: bool = False


class ResearchConfig(BaseModel):
    project_name: str
    start_date: str
    end_date: str | None = None
    initial_capital: float = 100_000.0
    annualization_days: int = 365
    paths: PathConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    universe: UniverseConfig
    regime: RegimeConfig
    rebalancing: RebalancingConfig
    frictions: FrictionConfig
    signals: SignalsConfig
    strategies: StrategyConfig
    providers: ProvidersConfig
    reporting: ReportingConfig
    data_quality: DataQualityConfig = Field(default_factory=DataQualityConfig)
    project_root: Path | None = None

    @property
    def start_timestamp(self):
        import pandas as pd

        return pd.Timestamp(self.start_date)

    @property
    def end_timestamp(self):
        import pandas as pd

        return pd.Timestamp(self.end_date) if self.end_date else pd.Timestamp.today().normalize()

    @property
    def regime_modes(self) -> list[str]:
        return ["always_on", "bull_only"] if self.strategies.include_bull_filter_variants else ["always_on"]

    def resolve_path(self, relative_path: str) -> Path:
        if self.project_root is None:
            raise ValueError("project_root is not set on the config")
        return (self.project_root / relative_path).resolve()


class SectorConfig(BaseModel):
    default_sector: str = "Other"
    category_keyword_rules: dict[str, list[str]] = Field(default_factory=dict)
    name_keyword_rules: dict[str, list[str]] = Field(default_factory=dict)
    manual_overrides: dict[str, str] = Field(default_factory=dict)


def load_config(config_path: str | Path) -> ResearchConfig:
    """Load the main research configuration file."""
    path = Path(config_path).resolve()
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    config = ResearchConfig.model_validate(raw)
    config.project_root = path.parent.parent.resolve()
    return config


def load_sector_config(config_path: str | Path) -> SectorConfig:
    """Load the human-editable sector mapping configuration."""
    path = Path(config_path).resolve()
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return SectorConfig.model_validate(raw)
