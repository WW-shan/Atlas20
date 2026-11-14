"""Map point-in-time CMC coin ids to Bitget USDT-M perpetual contracts.

The panel is keyed by CoinGecko-style ``coin_id``; Bitget is keyed by a base
asset symbol such as ``NEAR`` or ``BGB``.  Most mappings are direct, but the
project must also handle rebrands (MATIC -> POL), exchange tokens and
thousand-unit contracts.  Missing contracts are recorded explicitly rather
than replaced with a lower-ranked asset.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

import pandas as pd


class LiveSymbolMap(dict[str, str]):
    """Asset-to-contract map with an explicit reverse index.

    A rebrand can legitimately leave more than one CMC coin id on the same
    Bitget contract (for example MATIC and POL both use POLUSDT).  Targets
    must still be able to resolve either coin id, while venue positions need
    one canonical model asset.  A plain ``dict[str, str]`` cannot represent
    both facts, so the loader keeps all forward aliases and separately records
    the one canonical asset per venue symbol.
    """

    def __init__(
        self,
        assets: Mapping[str, str],
        canonical_by_symbol: Mapping[str, str] | None = None,
    ) -> None:
        normalized_assets = {
            str(asset): str(symbol).strip().upper()
            for asset, symbol in assets.items()
            if str(symbol).strip()
        }
        super().__init__(normalized_assets)
        self.canonical_by_symbol = {
            str(symbol).strip().upper(): str(asset)
            for symbol, asset in (canonical_by_symbol or {}).items()
            if str(symbol).strip()
        }

    def canonical_index(self) -> dict[str, str]:
        """Return a copy of the venue-symbol -> model-asset reverse index."""

        return dict(self.canonical_by_symbol)

    def canonical_asset(self, asset: str) -> str:
        """Resolve one model alias to the canonical asset of its venue symbol."""

        key = str(asset).strip().lower()
        symbol = str(self.get(key, "")).strip().upper()
        return str(self.canonical_by_symbol.get(symbol, key))

# Explicit aliases for rebrands, exchange tokens and contracts quoted in
# thousand-unit form.  The panel symbol is always tried first; aliases are
# fallbacks and the winning alias is recorded in ``reason``.
COIN_BASE_ALIASES: dict[str, list[str]] = {
    "matic-network": ["POL", "MATIC"],
    "polygon-ecosystem-token": ["POL", "MATIC"],
    "bitget-token": ["BGB"],
    "shiba-inu": ["SHIB", "1000SHIB"],
    "pepe": ["PEPE", "1000PEPE"],
    "terra-luna": ["LUNC", "LUNA", "1000LUNC"],
    "elrond-erd-2": ["EGLD"],
    "avalanche-2": ["AVAX"],
    "the-open-network": ["GRAM", "TON"],
    "world-liberty-financial": ["WLFI"],
    "hyperliquid": ["HYPE"],
    "crypto-com-chain": ["CRO"],
    "fantom": ["FTM", "S"],
    "render-token": ["RENDER"],
    "internet-computer": ["ICP"],
    "injective-protocol": ["INJ"],
    "lido-dao": ["LDO"],
    "the-graph": ["GRT"],
    "theta-token": ["THETA"],
    "flow": ["FLOW"],
    "eos": ["EOS"],
    "tezos": ["XTZ"],
    "decentraland": ["MANA"],
    "axie-infinity": ["AXS"],
    "apecoin": ["APE"],
    "gala": ["GALA"],
    "enjincoin": ["ENJ"],
    "chiliz": ["CHZ"],
    "basic-attention-token": ["BAT"],
    "curve-dao-token": ["CRV"],
    "compound-governance-token": ["COMP"],
    "maker": ["MKR"],
    "havven": ["SNX"],
    "dydx-chain": ["DYDX"],
    "sei-network": ["SEI"],
    "celestia": ["TIA"],
    "optimism": ["OP"],
    "arbitrum": ["ARB"],
    "sui": ["SUI"],
    "aptos": ["APT"],
    "kaspa": ["KAS"],
    "monero": ["XMR"],
    "zcash": ["ZEC"],
    "stellar": ["XLM"],
    "vechain": ["VET"],
    "algorand": ["ALGO"],
    "filecoin": ["FIL"],
    "hedera-hashgraph": ["HBAR"],
    "near": ["NEAR"],
    "ripple": ["XRP"],
    "cardano": ["ADA"],
    "solana": ["SOL"],
    "dogecoin": ["DOGE"],
    "tron": ["TRX"],
    "polkadot": ["DOT"],
    "litecoin": ["LTC"],
    "chainlink": ["LINK"],
    "bitcoin": ["BTC"],
    "ethereum": ["ETH"],
    "binancecoin": ["BNB"],
    "uniswap": ["UNI"],
    "cosmos": ["ATOM"],
    "ethereum-classic": ["ETC"],
    "thorchain": ["RUNE"],
    "the-sandbox": ["SAND"],
    "pancakeswap-token": ["CAKE"],
    "osmosis": ["OSMO"],
    "neo": ["NEO"],
    "quant-network": ["QNT"],
    "kucoin-shares": ["KCS"],
    "htx-dao": ["HT"],
    "huobi-token": ["HT"],
    "leo-token": ["LEO"],
    "worldcoin-wld": ["WLD"],
    "memecore": ["M"],
    "aster-2": ["ASTER"],
    "canton-network": ["CC"],
    "venice-token": ["VVV"],
    "pump-fun": ["PUMP"],
    "ondo-finance": ["ONDO"],
    "jupiter-exchange-solana": ["JUP"],
    "morpho": ["MORPHO"],
    "bittensor": ["TAO"],
    "immutable-x": ["IMX"],
}


def _normalise_base(value: Any) -> str:
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip().upper()
    return "" if text in {"NAN", "NONE", "<NA>"} else text


def _contract_priority(contract: dict[str, Any]) -> tuple[int, int, int, float]:
    status = 0 if str(contract.get("symbolStatus", "")).lower() == "normal" else 1
    quote = 0 if _normalise_base(contract.get("quoteCoin")) == "USDT" else 1
    symbol_type = 0 if str(contract.get("symbolType", "")).lower() == "perpetual" else 1
    open_time = pd.to_numeric(contract.get("openTime"), errors="coerce")
    if pd.isna(open_time):
        open_time = -1.0
    return (status, quote, symbol_type, -float(open_time))


def _panel_symbols(panel: pd.DataFrame) -> pd.DataFrame:
    required = {"coin_id", "symbol"}
    missing = required.difference(panel.columns)
    if missing:
        raise ValueError(f"panel is missing required columns: {sorted(missing)}")
    columns = ["coin_id", "symbol"]
    if "name" in panel.columns:
        columns.append("name")
    if "date" in panel.columns:
        columns.append("date")
    frame = panel.loc[:, columns].copy()
    frame["coin_id"] = [
        str(value).strip() if _normalise_base(value) else ""
        for value in frame["coin_id"]
    ]
    frame["symbol"] = [_normalise_base(value) for value in frame["symbol"]]
    frame = frame[frame["coin_id"].ne("")]
    # Keep the most recent symbol for a rebranded coin id.  Do not trust CSV
    # row order: a shuffled or concatenated panel must still select the
    # latest symbol, otherwise TON/GRAM-style rebrands can map backwards.
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
        frame["_row_order"] = range(len(frame))
        frame = frame.sort_values(
            ["coin_id", "date", "_row_order"],
            na_position="first",
        )
    frame = frame.drop_duplicates("coin_id", keep="last")
    return frame.sort_values("coin_id").reset_index(drop=True)


def build_symbol_map(panel: pd.DataFrame, contracts: list[dict[str, Any]]) -> pd.DataFrame:
    """Return one mapping row per panel coin id.

    ``contracts`` is the raw payload from
    ``GET /api/v2/mix/market/contracts?productType=USDT-FUTURES``.
    """
    by_base: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for contract in contracts:
        if not isinstance(contract, dict):
            continue
        base = _normalise_base(contract.get("baseCoin"))
        if base:
            by_base[base].append(contract)
    for base in by_base:
        by_base[base].sort(key=_contract_priority)

    rows: list[dict[str, Any]] = []
    for record in _panel_symbols(panel).to_dict("records"):
        coin_id = str(record["coin_id"])
        panel_symbol = _normalise_base(record["symbol"])
        panel_name = str(record.get("name") or "")
        candidates = [panel_symbol] if panel_symbol else []
        if panel_symbol:
            for alias in COIN_BASE_ALIASES.get(coin_id, []):
                if alias not in candidates:
                    candidates.append(alias)
        chosen: dict[str, Any] | None = None
        chosen_base = ""
        reason = "direct"
        for candidate in candidates:
            matches = by_base.get(candidate)
            if matches:
                chosen = matches[0]
                chosen_base = candidate
                reason = "direct" if candidate == panel_symbol else f"alias:{candidate}"
                break

        if chosen is None:
            rows.append(
                {
                    "coin_id": coin_id,
                    "panel_symbol": panel_symbol,
                    "panel_name": panel_name,
                    "bitget_symbol": "",
                    "base_coin": "",
                    "contract_status": "missing",
                    "reason": "no Bitget USDT-M perpetual",
                    "maker_fee": pd.NA,
                    "taker_fee": pd.NA,
                    "fund_interval": pd.NA,
                    "min_trade_usdt": pd.NA,
                    "size_multiplier": pd.NA,
                    "open_time": pd.NaT,
                }
            )
            continue

        rows.append(
            {
                "coin_id": coin_id,
                "panel_symbol": panel_symbol,
                "panel_name": panel_name,
                "bitget_symbol": str(chosen.get("symbol", "")),
                "base_coin": chosen_base,
                "contract_status": str(chosen.get("symbolStatus", "")),
                "reason": reason,
                "maker_fee": pd.to_numeric(chosen.get("makerFeeRate"), errors="coerce"),
                "taker_fee": pd.to_numeric(chosen.get("takerFeeRate"), errors="coerce"),
                "fund_interval": pd.to_numeric(chosen.get("fundInterval"), errors="coerce"),
                "min_trade_usdt": pd.to_numeric(chosen.get("minTradeUSDT"), errors="coerce"),
                "size_multiplier": pd.to_numeric(chosen.get("sizeMultiplier"), errors="coerce"),
                "open_time": pd.to_datetime(chosen.get("openTime") or None, unit="ms", utc=True, errors="coerce"),
            }
        )

    columns = [
        "coin_id",
        "panel_symbol",
        "panel_name",
        "bitget_symbol",
        "base_coin",
        "contract_status",
        "reason",
        "maker_fee",
        "taker_fee",
        "fund_interval",
        "min_trade_usdt",
        "size_multiplier",
        "open_time",
    ]
    return pd.DataFrame(rows, columns=columns)


def map_panel_symbols(panel: pd.DataFrame, contracts: list[dict[str, Any]]) -> pd.DataFrame:
    """Backward-compatible alias for :func:`build_symbol_map`."""
    return build_symbol_map(panel, contracts)


__all__ = [
    "COIN_BASE_ALIASES",
    "LiveSymbolMap",
    "build_symbol_map",
    "map_panel_symbols",
]
