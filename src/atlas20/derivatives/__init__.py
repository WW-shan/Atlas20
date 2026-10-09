"""Bitget USDT-M derivatives research data and isolated-margin engine."""

from atlas20.derivatives.bitget import (
    BITGET_BASE_URL,
    BITGET_CATEGORY,
    CANDLE_COLUMNS,
    FUNDING_COLUMNS,
    BitgetAPIError,
    BitgetClient,
    candle_frame,
    funding_frame,
)
from atlas20.derivatives.data import (
    load_binance_funding,
    load_bitget_funding,
    load_mark_candles,
)
from atlas20.derivatives.engine import (
    DerivativeBacktestConfig,
    DerivativeBacktestResult,
    run_derivative_backtest,
)
from atlas20.derivatives.mapping import build_symbol_map, map_panel_symbols
from atlas20.derivatives.margin import (
    initial_margin_ratio,
    liquidation_distance,
    liquidation_price,
)
from atlas20.derivatives.signals import (
    bear_regime,
    build_derivative_targets,
    funding_filter,
    scale_long_targets,
    weakest_top20,
)

__all__ = [
    "BITGET_BASE_URL",
    "BITGET_CATEGORY",
    "CANDLE_COLUMNS",
    "FUNDING_COLUMNS",
    "BitgetAPIError",
    "BitgetClient",
    "DerivativeBacktestConfig",
    "DerivativeBacktestResult",
    "bear_regime",
    "build_derivative_targets",
    "build_symbol_map",
    "candle_frame",
    "funding_filter",
    "funding_frame",
    "load_binance_funding",
    "load_bitget_funding",
    "load_mark_candles",
    "initial_margin_ratio",
    "liquidation_distance",
    "liquidation_price",
    "map_panel_symbols",
    "run_derivative_backtest",
    "scale_long_targets",
    "weakest_top20",
]
