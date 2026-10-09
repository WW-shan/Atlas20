"""Map point-in-time CMC coin ids to Bitget USDT-M perpetual contracts.

The panel is keyed by CoinGecko-style ``coin_id``; Bitget is keyed by a base
asset symbol such as ``NEAR`` or ``BGB``.  Most mappings are direct, but the
project must also handle rebrands (MATIC -> POL), exchange tokens and
thousand-unit contracts.  Missing contracts are recorded explicitly rather
than replaced with a lower-ranked asset.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd

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
    "the-open-network": ["TON"],
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
    return str(value or "").strip().upper()


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
    frame = panel.loc[:, ["coin_id", "symbol"]].copy()
    frame["coin_id"] = frame["coin_id"].astype(str)
    frame["symbol"] = frame["symbol"].astype(str)
    frame = frame.dropna(subset=["coin_id", "symbol"])
    frame = frame[frame["symbol"].str.len() > 0]
    # Keep the most recent symbol for a rebranded coin id.  The panel is
    # ordered by date; a stable de-duplication keeps the last observation.
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
        candidates = [panel_symbol]
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


__all__ = ["COIN_BASE_ALIASES", "build_symbol_map", "map_panel_symbols"]
