from __future__ import annotations

import pytest

from atlas20.api.data_access._common import _as_float


def test_as_float_reports_column_for_non_finite_value():
    with pytest.raises(ValueError, match="foo"):
        _as_float(float("nan"), "foo")
