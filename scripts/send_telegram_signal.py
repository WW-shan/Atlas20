"""Send the daily Atlas20 phase-momentum signal to Telegram.

This is a notification-only tool.  It reads the signal snapshot written by
``scripts/run_phase_momentum_live_signal.py``, formats the model's order
instructions and target book, and posts one message through the Telegram Bot
API.  It never places an order and it does not know about any real brokerage
account.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import time
from typing import Any

import requests


def _weight_map(raw: object) -> dict[str, float]:
    if not isinstance(raw, Mapping):
        raise ValueError("signal weights must be a JSON object")
    weights: dict[str, float] = {}
    for asset, weight in raw.items():
        value = float(weight)
        if not math.isfinite(value):
            raise ValueError(f"weight for {asset!r} must be finite")
        if value < 0.0:
            raise ValueError(f"negative weight for {asset!r}")
        weights[str(asset)] = value
    if sum(weights.values()) > 1.0 + 1e-9:
        raise ValueError("signal weights exceed 100% gross exposure")
    return weights


def _cash_weight(weights: Mapping[str, float]) -> float:
    return max(0.0, 1.0 - sum(weights.values()))


def _holding_lines(weights: Mapping[str, float], capital: float) -> list[str]:
    lines: list[str] = []
    for asset, weight in sorted(weights.items(), key=lambda item: (-item[1], item[0])):
        lines.append(
            f"  {asset.upper()} {weight * 100:.2f}% / {weight * capital:.2f} USDT"
        )
    cash = _cash_weight(weights)
    lines.append(f"  CASH {cash * 100:.2f}% / {cash * capital:.2f} USDT")
    return lines


def _operation_lines(
    target: Mapping[str, float],
    current: Mapping[str, float],
    *,
    trade_required: bool,
    capital: float,
) -> list[str]:
    if not trade_required:
        return ["  今日无需调仓"]
    assets = sorted(set(target) | set(current))
    lines: list[str] = []
    for asset in assets:
        delta = target.get(asset, 0.0) - current.get(asset, 0.0)
        if abs(delta) < 5e-7:
            continue
        action = "BUY" if delta > 0.0 else "SELL"
        lines.append(
            f"  {action} {asset.upper()} {abs(delta) * capital:.2f} USDT "
            f"({delta * 100:+.2f}pp)"
        )
    if not lines:
        lines.append("  今日无需调仓")
    return lines


def _yes_no(value: object) -> str:
    return "YES" if bool(value) else "NO"


def _date_lines(payload: Mapping[str, Any]) -> list[str]:
    """Explain the UTC signal date and the local T+1 execution date."""
    raw_as_of = payload.get("as_of", "unknown")
    signal_date = str(raw_as_of)
    try:
        as_of_date = date.fromisoformat(signal_date)
    except ValueError:
        return [
            f"信号日期（UTC日线）: {signal_date}",
            "数据收盘: unknown",
            "执行日期: unknown",
        ]
    execution_date = as_of_date + timedelta(days=1)
    return [
        f"信号日期（UTC日线）: {signal_date}",
        f"数据收盘: {as_of_date.isoformat()} 23:59 UTC / 北京时间 {execution_date.isoformat()} 08:00",
        f"执行日期: {execution_date.isoformat()}（T+1）",
    ]


def format_signal_message(
    payload: Mapping[str, Any],
    *,
    capital: float = 1000.0,
) -> str:
    """Format one Telegram message from a live-signal payload."""
    if capital <= 0.0:
        raise ValueError("capital must be positive")
    target = _weight_map(payload.get("targets", {}))
    current = _weight_map(payload.get("current_weights", {}))
    lines = [
        "Atlas20 H5 每日信号",
        *_date_lines(payload),
        f"目标生成日: {payload.get('latest_target_date', 'unknown')}",
        f"Trade required: {_yes_no(payload.get('trade_required'))}",
        f"BTC gate: {'OPEN' if bool(payload.get('btc_gate_open')) else 'CLOSED'}",
        f"Gross target: {float(payload.get('gross_exposure', sum(target.values()))) * 100:.2f}%",
        "",
        f"今日操作（按总资金 {capital:.2f} USDT）:",
        *_operation_lines(
            target,
            current,
            trade_required=bool(payload.get("trade_required")),
            capital=capital,
        ),
        "",
        "目标持仓（调仓后）:",
        *_holding_lines(target, capital),
        "",
        f"Trial: {payload.get('trial_id', 'unknown')}",
        f"Cost: {float(payload.get('cost_bps', 0.0)):g} bps",
        "信号仅供参考，请手动执行。",
    ]
    return "\n".join(lines)


DEFAULT_SIGNAL_FILE = Path("reports/phase_momentum_live/latest_signal.json")
DEFAULT_STATE_FILE = Path("data/telegram_signal_state.json")


def _state_key(payload: Mapping[str, Any]) -> str:
    """Identity of one daily message, independent of retries."""
    return f"{payload.get('trial_id', 'unknown')}|{payload.get('as_of', 'unknown')}"


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return state if isinstance(state, dict) else {}


def _chat_ids(raw: str | None) -> list[str]:
    """Parse one or more comma-separated Telegram chat ids."""
    if not raw:
        return []
    seen: set[str] = set()
    chat_ids: list[str] = []
    for value in raw.split(","):
        chat_id = value.strip()
        if chat_id and chat_id not in seen:
            seen.add(chat_id)
            chat_ids.append(chat_id)
    return chat_ids


def _mark_sent(path: Path, chat_id: str, payload: Mapping[str, Any]) -> None:
    """Record one successful recipient without losing other recipients."""
    key = _state_key(payload)
    state = _read_state(path)
    sent_keys = state.get("sent_keys")
    if not isinstance(sent_keys, dict):
        sent_keys = {}
    sent_keys[str(chat_id)] = key
    state["sent_keys"] = sent_keys
    state["last_sent_key"] = key
    state["trial_id"] = payload.get("trial_id")
    state["as_of"] = payload.get("as_of")
    state["sent_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _load_signal(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"signal file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"signal file is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"signal file must contain a JSON object: {path}")
    return payload


def _telegram_error(status_code: int, description: object) -> str:
    detail = str(description) if description else "unknown error"
    return f"Telegram sendMessage failed with HTTP {status_code}: {detail}"


def send_telegram_message(
    message: str,
    *,
    token: str,
    chat_id: str,
    api_base: str = "https://api.telegram.org",
    max_attempts: int = 3,
) -> None:
    """Post ``message`` to Telegram with bounded retries.

    The bot token is part of the URL, so errors must never echo the URL.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    url = f"{api_base.rstrip('/')}/bot{token}/sendMessage"
    body = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }
    last_error = "unknown error"
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(url, json=body, timeout=10)
        except requests.RequestException as exc:
            last_error = f"network error: {exc.__class__.__name__}"
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Telegram sendMessage failed after {max_attempts} attempts: {last_error}"
                ) from exc
            time.sleep(2 ** (attempt - 1))
            continue

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        description = payload.get("description") if isinstance(payload, dict) else None

        if response.ok and isinstance(payload, dict) and payload.get("ok") is True:
            return

        if response.status_code == 429 or response.status_code >= 500:
            last_error = _telegram_error(response.status_code, description)
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Telegram sendMessage failed after {max_attempts} attempts: {last_error}"
                )
            time.sleep(2 ** (attempt - 1))
            continue

        raise RuntimeError(_telegram_error(response.status_code, description))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signal-file", type=Path, default=DEFAULT_SIGNAL_FILE)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--force", action="store_true", help="send even if this as-of date was already sent")
    parser.add_argument("--dry-run", action="store_true", help="print the message without sending")
    parser.add_argument(
        "--capital",
        type=float,
        default=None,
        help="total model capital in USDT for amount instructions (default: 1000 or ATLAS20_TELEGRAM_CAPITAL)",
    )
    args = parser.parse_args(argv)

    payload = _load_signal(args.signal_file)
    key = _state_key(payload)
    chat_ids = _chat_ids(os.environ.get("ATLAS20_TELEGRAM_CHAT_ID"))

    raw_capital = args.capital if args.capital is not None else os.environ.get("ATLAS20_TELEGRAM_CAPITAL", "1000")
    try:
        capital = float(raw_capital)
    except (TypeError, ValueError) as exc:
        raise SystemExit("ATLAS20_TELEGRAM_CAPITAL/--capital must be a number") from exc
    if capital <= 0.0:
        raise SystemExit("ATLAS20_TELEGRAM_CAPITAL/--capital must be positive")
    message = format_signal_message(payload, capital=capital)
    if args.dry_run:
        print(message)
        return
    if not chat_ids:
        raise SystemExit("ATLAS20_TELEGRAM_CHAT_ID is not set")

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
        send_telegram_message(
            message,
            token=token,
            chat_id=chat_id,
            api_base=api_base,
        )
        _mark_sent(args.state_file, chat_id, payload)
        print(f"Sent Telegram signal for {key} to {chat_id}")


if __name__ == "__main__":
    main()
