"""Bitget USDT-M derivatives research data layer."""

from atlas20.derivatives.bitget import (
    BITGET_CATEGORY,
    BitgetAPIError,
    BitgetClient,
    candle_frame,
    funding_frame,
)
from atlas20.derivatives.mapping import build_symbol_map, map_panel_symbols

__all__ = [
    "BITGET_CATEGORY",
    "BitgetAPIError",
    "BitgetClient",
    "build_symbol_map",
    "candle_frame",
    "funding_frame",
    "map_panel_symbols",
]
