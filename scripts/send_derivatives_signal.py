"""Send the frozen Atlas20 derivatives signal to Telegram.

Notification-only: this reads the daily target book written by
``scripts/run_ls45_live_signal.py``, formats one message with the signed
long/short rebalance in USDT and the post-trade book, and posts it through the
Bot API. It never places an order and does not know about any real account.

The derivatives book differs from the spot signal in units: weights are
signed notional as a fraction of equity. The LS45-G125 spec caps gross at
1.25x and assigns a 50% initial isolated buffer to each leg. Short entries and
increases carry a 20% mark-price stop. The message shows notional, side,
reference isolated margin and that stop rule so manual execution is explicit.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from math import isfinite
import os
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.live_chain import live_execution_hint_for_signal  # noqa: E402
from atlas20.derivatives.margin import initial_margin_ratio  # noqa: E402
from atlas20.logging_utils import atomic_write_text  # noqa: E402
from scripts.send_telegram_signal import (  # noqa: E402
    _chat_ids,
    _read_state,
    send_telegram_message,
)

TRACKED_SPEC = "PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21"
LEVERAGE = 1.25
LONG_BUFFER = 0.50
SHORT_BUFFER = 0.50
SHORT_STOP_LOSS_PCT = 0.20
MAINTENANCE_MARGIN_RATE = 0.01
FEE_BUFFER = 0.005
DEFAULT_TARGETS_FILE = Path("reports/ls45_live_g125/oos_targets.csv")
DEFAULT_STATE_FILE = Path("data/ls45_g125_telegram_state.json")
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
    frame["signal_date"] = pd.to_datetime(
        frame["signal_date"], utc=True, format="mixed", errors="coerce"
    )
    frame["execution_hint"] = pd.to_datetime(
        frame["execution_hint"], utc=True, format="mixed", errors="coerce"
    )
    if frame["signal_date"].isna().any() or frame["execution_hint"].isna().any():
        raise SystemExit(f"targets file {path} contains an invalid signal_date or execution_hint")
    latest = frame["signal_date"].max()
    book = frame.loc[frame["signal_date"] == latest].copy()
    hints = book["execution_hint"].drop_duplicates()
    if len(hints) != 1:
        raise SystemExit(
            f"targets file {path} has inconsistent execution_hint values on {latest.date()}"
        )
    execution_hint = pd.Timestamp(hints.iloc[0])
    expected_hint = pd.Timestamp(live_execution_hint_for_signal(latest))
    if execution_hint != expected_hint:
        raise SystemExit(
            f"targets file {path} must use the single T+1 01:05 UTC execution_hint "
            f"{expected_hint.isoformat()}, got {execution_hint.isoformat()}"
        )
    assets = book["asset"].astype(str).str.strip().str.lower()
    if (assets == "").any() or assets.duplicated().any():
        raise SystemExit(f"targets file {path} has an empty or duplicate asset on {latest.date()}")
    book["asset"] = assets
    for column in ("target_weight", "change_weight"):
        parsed = pd.to_numeric(book[column], errors="coerce")
        invalid = parsed.isna() | ~parsed.map(isfinite)
        if invalid.any():
            rows = ", ".join(book.loc[invalid, "asset"].astype(str).tolist())
            raise SystemExit(
                f"targets file {path} has a non-finite {column} for: {rows}"
            )
        book[column] = parsed.astype(float)
    return latest, execution_hint, book


def _lag_label(close_utc: pd.Timestamp, execution: pd.Timestamp) -> str:
    lag_minutes = int((execution - close_utc).total_seconds() // 60)
    return (
        f"T+1 +{lag_minutes // 60}h"
        if lag_minutes % 60 == 0
        else f"T+1 +{lag_minutes // 60}h{lag_minutes % 60}m"
    )


def _close_and_execution_lines(
    signal_date: pd.Timestamp,
    execution_hint: pd.Timestamp,
    research_execution_hint: pd.Timestamp | None = None,
) -> list[str]:
    close_utc = signal_date + pd.Timedelta(days=1)
    close_local = close_utc + pd.Timedelta(hours=8)
    execution_local = execution_hint + pd.Timedelta(hours=8)
    lines = [
        f"信号日线（UTC）: {signal_date.date()}（{signal_date.date()} 00:00→24:00 UTC）",
        f"数据收盘: {close_utc.strftime('%Y-%m-%d %H:%M')} UTC / 北京时间 {close_local.strftime('%Y-%m-%d %H:%M')}",
        f"建议执行: 北京时间 {execution_local.strftime('%Y-%m-%d %H:%M')}"
        f"（UTC {execution_hint.strftime('%Y-%m-%d %H:%M')}，"
        f"{_lag_label(close_utc, execution_hint)}）",
    ]
    # Kept only for compatibility with older callers.  A second execution
    # clock would falsely imply that research and live still diverge.
    del research_execution_hint
    return lines


def format_derivatives_message(
    book: pd.DataFrame,
    *,
    signal_date: pd.Timestamp,
    execution_hint: pd.Timestamp,
    research_execution_hint: pd.Timestamp | None = None,
    capital: float = CAPITAL_SCALE,
    spec: str = TRACKED_SPEC,
    leverage: float = LEVERAGE,
    long_buffer: float = LONG_BUFFER,
    short_buffer: float = SHORT_BUFFER,
    short_stop_loss_pct: float = SHORT_STOP_LOSS_PCT,
    now: pd.Timestamp | None = None,
) -> str:
    """Format one Telegram message from the derivatives target book."""

    if capital <= 0.0:
        raise ValueError("capital must be positive")
    scale = capital / CAPITAL_SCALE
    # The engine assigns margin = notional x (buffer + maintenance + fee buffer),
    # i.e. 51.5% for the frozen 50% long buffer - not exactly 50%.  Posting only
    # 50% would move the liquidation distance from -51.01% to -49.49%.
    long_margin_ratio = initial_margin_ratio(
        "long",
        maintenance_margin_rate=MAINTENANCE_MARGIN_RATE,
        fee_buffer=FEE_BUFFER,
        long_buffer=long_buffer,
    )
    short_margin_ratio = initial_margin_ratio(
        "short",
        maintenance_margin_rate=MAINTENANCE_MARGIN_RATE,
        fee_buffer=FEE_BUFFER,
        short_buffer=short_buffer,
    )
    book = book.copy()
    book["target_notional"] = pd.to_numeric(book["target_weight"], errors="coerce").fillna(0.0) * capital
    book["change_notional"] = pd.to_numeric(book["change_weight"], errors="coerce").fillna(0.0) * capital
    book["target_side"] = book["target_notional"].map(
        lambda value: "SHORT" if value < -1e-12 else ("LONG" if value > 1e-12 else "FLAT")
    )
    book["target_margin"] = book["target_notional"].abs() * book["target_side"].map(
        lambda side: short_margin_ratio if side == "SHORT" else long_margin_ratio
    )
    has_short = bool(book["target_side"].eq("SHORT").any())

    lines = [
        f"Atlas20 合约信号 · {spec}",
        *_close_and_execution_lines(
            pd.Timestamp(signal_date),
            pd.Timestamp(execution_hint),
            None if research_execution_hint is None else pd.Timestamp(research_execution_hint),
        ),
        f"模式: Bitget 合约 · 名义上限 {leverage:g}x · 每腿隔离保证金 = 名义 × "
        f"{max(long_margin_ratio, short_margin_ratio) * 100:.1f}% · 手动下单",
    ]
    if has_short:
        lines.append(
            f"风控: 空头止损 {short_stop_loss_pct:.0%} · mark-price · 开/加仓时附带"
        )
    lines += [
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
            side_separator = f"· {row['target_side']} · " if has_short else "· "
            lines.append(
                f"  {str(row['asset']).upper()} 名义 {float(row['target_notional']):.2f} USDT"
                f"（{float(row['target_weight']) * 100:.2f}%）{side_separator}参考隔离保证金 "
                f"{float(row['target_margin']):.2f} USDT"
            )
    gross_weight = float(book["target_weight"].abs().sum())
    gross_notional = float(book["target_notional"].abs().sum())
    margin_used = float(book["target_margin"].sum())
    gross_label = "权益 gross" if has_short else "权益"
    lines += [
        "",
        f"合计名义 {gross_notional:.2f} USDT（{gross_weight * 100:.2f}% {gross_label}，上限 {leverage * 100:.0f}%）",
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
    atomic_write_text(path, json.dumps(state, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--spec", default=TRACKED_SPEC)
    parser.add_argument("--force", action="store_true", help="send even if this signal date was already sent")
    parser.add_argument("--dry-run", action="store_true", help="print the message without sending")
    parser.add_argument(
        "--max-signal-age-hours",
        type=float,
        default=36.0,
        help="refuse to send when the modelled execution is older than this (default 36h)",
    )
    parser.add_argument(
        "--allow-stale-signal",
        action="store_true",
        help="send even when the modelled execution is long past (ledger replay)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=None,
        help="total equity in USDT for notional sizing (default: 1000 or ATLAS20_TELEGRAM_CAPITAL)",
    )
    args = parser.parse_args(argv)

    signal_date, ledger_execution_hint, book = load_latest_targets(args.targets_file)
    execution_hint = pd.Timestamp(live_execution_hint_for_signal(signal_date))
    if ledger_execution_hint != execution_hint:
        raise SystemExit(
            f"target ledger execution_hint {ledger_execution_hint} does not match "
            f"the live execution clock {execution_hint}"
        )
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
        research_execution_hint=None,
        capital=capital,
        spec=args.spec,
        now=pd.Timestamp.now(tz="UTC"),
    )
    if args.dry_run:
        print(message)
        return

    age_hours = float(
        (pd.Timestamp.now(tz="UTC") - pd.Timestamp(execution_hint)).total_seconds() / 3600.0
    )
    if not args.allow_stale_signal and age_hours > float(args.max_signal_age_hours):
        raise SystemExit(
            f"signal {signal_date.date()} was meant to execute at {execution_hint} "
            f"({age_hours:.1f}h ago, limit {args.max_signal_age_hours:g}h); refusing to send a "
            "stale instruction. Refresh the pipeline (make derivatives-live-data derivatives-ls45-signal) "
            "or pass --allow-stale-signal to replay the ledger."
        )

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
