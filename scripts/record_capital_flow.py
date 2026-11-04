"""Record one external deposit or withdrawal in the live capital-flow ledger.

Positive amounts are deposits; negative amounts are withdrawals. This ledger
is separate from strategy PnL so account transfers never become fake returns.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from atlas20.derivatives.live_journal import DEFAULT_CAPITAL_FLOWS_FILE, append_capital_flow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amount", type=float, required=True, help="USDT; deposit > 0, withdrawal < 0")
    parser.add_argument("--timestamp-utc", default=None, help="ISO timestamp; defaults to now")
    parser.add_argument("--note", default="", help="operator note")
    parser.add_argument("--file", type=Path, default=DEFAULT_CAPITAL_FLOWS_FILE)
    args = parser.parse_args(argv)

    timestamp = args.timestamp_utc or datetime.now(timezone.utc).isoformat()
    try:
        append_capital_flow(
            args.file,
            timestamp_utc=timestamp,
            amount_usdt=args.amount,
            note=args.note,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(f"记录外部资金流 {args.amount:+.2f} USDT @ {timestamp} -> {args.file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
