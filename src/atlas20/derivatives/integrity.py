"""Small fail-closed helpers for derivatives data frames."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


def deduplicate_by_keys_or_raise(
    frame: pd.DataFrame,
    *,
    keys: Sequence[str],
    values: Sequence[str],
    label: str,
    keep: str = "last",
) -> pd.DataFrame:
    """Collapse exact duplicate keys and reject conflicting payload values.

    Re-downloaded public history legitimately overlaps earlier pages.  Those
    rows must be byte-for-byte equivalent (on the canonical value columns).
    A repeated timestamp with a different price, volume or funding rate is a
    data conflict, not a newer truth to install silently.
    """

    key_columns = [str(key) for key in keys]
    value_columns = [str(value) for value in values]
    if not key_columns:
        raise ValueError(f"{label}: at least one duplicate key is required")
    if not value_columns:
        raise ValueError(f"{label}: at least one value column is required")
    if keep not in {"first", "last"}:
        raise ValueError(f"{label}: keep must be 'first' or 'last'")
    missing = set(key_columns + value_columns).difference(frame.columns)
    if missing:
        raise ValueError(f"{label}: missing duplicate-check columns {sorted(missing)}")

    duplicated = frame.duplicated(subset=key_columns, keep=False)
    if duplicated.any():
        duplicate_rows = frame.loc[duplicated]
        for key_value, group in duplicate_rows.groupby(
            key_columns,
            dropna=False,
            sort=False,
        ):
            if len(group.loc[:, value_columns].drop_duplicates()) <= 1:
                continue
            rendered_key = (
                key_value if isinstance(key_value, tuple) else (key_value,)
            )
            key_text = ", ".join(
                f"{column}={value!r}"
                for column, value in zip(key_columns, rendered_key, strict=True)
            )
            raise ValueError(
                f"{label}: conflicting duplicate values for {key_text}"
            )

    return frame.drop_duplicates(subset=key_columns, keep=keep).reset_index(drop=True)


__all__ = ["deduplicate_by_keys_or_raise"]
