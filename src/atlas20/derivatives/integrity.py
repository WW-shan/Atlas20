"""Small fail-closed helpers for derivatives data frames."""

from __future__ import annotations

from collections.abc import Sequence
import math

import numpy as np
import pandas as pd


def _values_agree(left: object, right: object) -> bool:
    """Compare canonical values without treating float round-trip noise as data.

    Public JSON numbers arrive as decimal strings and are parsed independently
    on each fetch.  The same decimal can land on adjacent IEEE-754 values on
    two runs (the CAKE ``10168712.597007013`` case).  Such a 1-ULP difference
    is not a market-data revision.  A relative tolerance of 1e-12 accepts that
    serialization noise while still rejecting every economically meaningful
    change; non-numeric values must remain exactly equal.
    """

    if isinstance(left, (float, int, np.number)) and isinstance(
        right, (float, int, np.number)
    ):
        a = float(left)
        b = float(right)
        if not (math.isfinite(a) and math.isfinite(b)):
            return a == b
        return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
    if left is None or right is None:
        return left is None and right is None
    return bool(left == right)


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
    rows must carry the same decimal values (on the canonical value columns).
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
            rows = list(group.loc[:, value_columns].itertuples(index=False, name=None))
            if all(
                _values_agree(left, right)
                for row in rows[1:]
                for left, right in zip(rows[0], row, strict=True)
            ):
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
