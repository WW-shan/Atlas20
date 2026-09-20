"""Fetch true historical market cap + price for the whole candidate universe."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.config import load_config
from atlas20.data.coinmarketcap import CoinMarketCapClient
from atlas20.logging_utils import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch CMC history")
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2026-09-20")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging("WARNING")
    raw = config.resolve_path(config.paths.raw_dir)
    client = CoinMarketCapClient(config.providers.coinmarketcap, raw)

    candidates = json.loads((raw / "coingecko" / "candidate_assets.json").read_text(encoding="utf-8"))
    id_map = client.fetch_id_map(force=args.force)
    print(f"CMC id map: {len(id_map)} symbols")

    ok, miss, err = [], [], []
    for i, asset in enumerate(candidates, 1):
        sym = str(asset["symbol"]).upper()
        cid = id_map.get(sym)
        if cid is None:
            miss.append(sym)
            print(f"[{i}/{len(candidates)}] {sym:10} NO CMC ID")
            continue
        try:
            df = client.fetch_history(cid, start=args.start, end=args.end, force=args.force)
        except Exception as exc:  # noqa: BLE001
            err.append((sym, str(exc)[:50]))
            print(f"[{i}/{len(candidates)}] {sym:10} ERROR {str(exc)[:50]}")
            continue
        if df.empty:
            miss.append(sym)
            print(f"[{i}/{len(candidates)}] {sym:10} EMPTY")
        else:
            ok.append(sym)
            print(f"[{i}/{len(candidates)}] {sym:10} {len(df):5} rows  {df['date'].min().date()} -> {df['date'].max().date()}")

    print(f"\n成功 {len(ok)}/{len(candidates)}")
    if miss:
        print(f"无数据 ({len(miss)}): {miss}")
    if err:
        print(f"错误 ({len(err)}): {err}")


if __name__ == "__main__":
    main()
