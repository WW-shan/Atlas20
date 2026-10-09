"""Send the frozen Atlas20 derivatives signal to Telegram.

Notification-only: this reads the daily target book written by
``scripts/run_derivatives_oos.py``, formats one message with the implied
rebalance in USDT and the post-trade book, and posts it through the Bot API.
It never places an order and does not know about any real account.

The derivatives book differs from the spot signal in units: weights are
*notional as a fraction of equity*, the frozen spec runs 1.25x notional with
isolated margin, and the 50% long buffer is the margin actually assigned to
each leg.  The message therefore shows both the notional and the reference
isolated margin so the order can be sized without guessing.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.send_telegram_signal import (  # noqa: E402
    _chat_ids,
    _read_state,
    send_telegram_message,
)

TRACKED_SPEC = "PR2026-10-D-L125-V2"
LEVERAGE = 1.25
LONG_BUFFER = 0.50
DEFAULT_TARGETS_FILE = Path("reports/derivatives_track_oos_2026/oos_targets.csv")
DEFAULT_STATE_FILE = Path("data/derivatives_telegram_state.json")
CAPITAL_SCALE = 1000.0


def load_latest_targets(path: Path) -> tuple[pd.Timestamp, pd.Timestamp, pd.DataFrame]:
    """Latest signal row-set from the OOS target ledger."""

    try:
        frame = pd.read_csv(path)
    except FileNotFoundError as exc:
        raise SystemExit(f"targets file not found: {path}") from exc
    required = {
        "signal_date",
        "execution_hint",
        "asset",
        "target_weight",
        "change_weight",
        "action",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise SystemExit(f"targets file {path} is missing columns: {missing}")
    if frame.empty:
        raise SystemExit(f"targets file {path} has no rows")
    frame["signal_date"] = pd.to_datetime(frame["signal_date"], utc=True, format="mixed")
    frame["execution_hint"] = pd.to_datetime(frame["execution_hint"], utc=True, format="mixed")
    latest = frame["signal_date"].max()
    book = frame.loc[frame["signal_date"] == latest].copy()
    return latest, pd.Timestamp(book["execution_hint"].iloc[0]), book


def _close_and_execution_lines(signal_date: pd.Timestamp, execution_hint: pd.Timestamp) -> list[str]:
    close_utc = signal_date + pd.Timedelta(days=1)
    close_local = close_utc + pd.Timedelta(hours=8)
    execution_local = execution_hint + pd.Timedelta(hours=8)
    return [
        f"信号日线（UTC）: {signal_date.date()}（{signal_date.date()} 00:00→24:00 UTC）",
        f"数据收盘: {close_utc.strftime('%Y-%m-%d %H:%M')} UTC / 北京时间 {close_local.strftime('%Y-%m-%d %H:%M')}",
        f"建议执行: 北京时间 {execution_local.strftime('%Y-%m-%d %H:%M')}（UTC {execution_hint.strftime('%Y-%m-%d %H:%M')}，T+1 +3h）",
    ]


def format_derivatives_message(
    book: pd.DataFrame,
    *,
    signal_date: pd.Timestamp,
    execution_hint: pd.Timestamp,
    capital: float = CAPITAL_SCALE,
    spec: str = TRACKED_SPEC,
    leverage: float = LEVERAGE,
    long_buffer: float = LONG_BUFFER,
    now: pd.Timestamp | None = None,
) -> str:
    """Format one Telegram message from the derivatives target book."""

    if capital <= 0.0:
        raise ValueError("capital must be positive")
    scale = capital / CAPITAL_SCALE
    book = book.copy()
    book["target_notional"] = pd.to_numeric(book["target_weight"], errors="coerce").fillna(0.0) * capital
    book["change_notional"] = pd.to_numeric(book["change_weight"], errors="coerce").fillna(0.0) * capital
    book["target_margin"] = book["target_notional"] * long_buffer

    lines = [
        f"Atlas20 合约信号 · {spec}",
        *_close_and_execution_lines(pd.Timestamp(signal_date), pd.Timestamp(execution_hint)),
        f"模式: Bitget 合约 · 名义上限 {leverage:g}x · 隔离保证金缓冲 {long_buffer * 100:.0f}% · 手动下单",
        "",
        f"今日调仓（按权益 {capital:.2f} USDT）:",
    ]
    trades = book.loc[book["change_notional"].abs() > 0.005].sort_values("change_notional", ascending=False)
    if trades.empty:
        lines.append("  今日无需调仓")
    else:
        for row in trades.to_dict("records"):
            action = "BUY" if float(row["change_notional"]) > 0.0 else "SELL"
            lines.append(
                f"  {action} {str(row['asset']).upper()} 名义 {float(row['change_notional']):+.2f} USDT"
                f"（{float(row['change_weight']) * 100:+.2f}pp 权重）"
            )
    lines += ["", "调仓后目标持仓:"]
    holdings = book.loc[book["target_notional"].abs() > 0.005].sort_values(
        "target_notional", ascending=False
    )
    if holdings.empty:
        lines.append("  CASH 100.00%（不使用保证金）")
    else:
        for row in holdings.to_dict("records"):
            lines.append(
                f"  {str(row['asset']).upper()} 名义 {float(row['target_notional']):.2f} USDT"
                f"（{float(row['target_weight']) * 100:.2f}%）· 参考隔离保证金 {float(row['target_margin']):.2f} USDT"
            )
    gross_weight = float(book["target_weight"].sum())
    gross_notional = float(book["target_notional"].sum())
    margin_used = float(book["target_margin"].sum())
    lines += [
        "",
        f"合计名义 {gross_notional:.2f} USDT（{gross_weight * 100:.2f}% 权益，上限 {leverage * 100:.0f}%）",
        f"占用隔离保证金 {margin_used:.2f} USDT（{margin_used / capital * 100:.2f}%）"
        f" · 剩余可用 {capital - margin_used:.2f} USDT",
        f"参考缩放系数: {scale:g}（模型账本以 1000 USDT 权益计）",
    ]
    if now is not None and pd.Timestamp(now) > pd.Timestamp(execution_hint) + pd.Timedelta(hours=2):
        lines.append(
            f"注意: 该执行时点已过去（现在 {pd.Timestamp(now).strftime('%Y-%m-%d %H:%M')} UTC），"
            "本条仅作记录，请勿追单。"
        )
    lines.append("信号仅供参考，请手动执行；每天播报一次。")
    return "\n".join(lines)


def _state_key(spec: str, signal_date: pd.Timestamp) -> str:
    return f"{spec}|{pd.Timestamp(signal_date).date()}"


def _mark_sent(path: Path, chat_id: str, *, spec: str, signal_date: pd.Timestamp) -> None:
    key = _state_key(spec, signal_date)
    state = _read_state(path)
    sent_keys = state.get("sent_keys")
    if not isinstance(sent_keys, dict):
        sent_keys = {}
    sent_keys[str(chat_id)] = key
    state["sent_keys"] = sent_keys
    state["last_sent_key"] = key
    state["trial_id"] = spec
    state["signal_date"] = str(pd.Timestamp(signal_date).date())
    state["sent_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--spec", default=TRACKED_SPEC)
    parser.add_argument("--force", action="store_true", help="send even if this signal date was already sent")
    parser.add_argument("--dry-run", action="store_true", help="print the message without sending")
    parser.add_argument(
        "--capital",
        type=float,
        default=None,
        help="total equity in USDT for notional sizing (default: 1000 or ATLAS20_TELEGRAM_CAPITAL)",
    )
    args = parser.parse_args(argv)

    signal_date, execution_hint, book = load_latest_targets(args.targets_file)
    raw_capital = args.capital if args.capital is not None else os.environ.get("ATLAS20_TELEGRAM_CAPITAL", "1000")
    try:
        capital = float(raw_capital)
    except (TypeError, ValueError) as exc:
        raise SystemExit("ATLAS20_TELEGRAM_CAPITAL/--capital must be a number") from exc
    if capital <= 0.0:
        raise SystemExit("ATLAS20_TELEGRAM_CAPITAL/--capital must be positive")

    message = format_derivatives_message(
        book,
        signal_date=signal_date,
        execution_hint=execution_hint,
        capital=capital,
        spec=args.spec,
        now=pd.Timestamp.now(tz="UTC"),
    )
    if args.dry_run:
        print(message)
        return

    chat_ids = _chat_ids(os.environ.get("ATLAS20_TELEGRAM_CHAT_ID"))
    if not chat_ids:
        raise SystemExit("ATLAS20_TELEGRAM_CHAT_ID is not set")
    key = _state_key(args.spec, signal_date)
    state = _read_state(args.state_file)
    sent_keys = state.get("sent_keys")
    if not isinstance(sent_keys, dict):
        sent_keys = {}
    pending = chat_ids if args.force else [chat_id for chat_id in chat_ids if sent_keys.get(chat_id) != key]
    if not pending:
        print(f"Already sent {key} to all configured chat ids; skipping")
        return

    token = os.environ.get("ATLAS20_TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("ATLAS20_TELEGRAM_BOT_TOKEN is not set")
    api_base = os.environ.get("ATLAS20_TELEGRAM_API_BASE", "https://api.telegram.org")
    for chat_id in pending:
        send_telegram_message(message, token=token, chat_id=chat_id, api_base=api_base)
        _mark_sent(args.state_file, chat_id, spec=args.spec, signal_date=signal_date)
        print(f"Sent derivatives signal for {key} to {chat_id}")


if __name__ == "__main__":
    main()
