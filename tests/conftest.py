from collections.abc import Iterator

import pytest

from atlas20.api.settings import get_settings


@pytest.fixture(autouse=True)
def atlas20_test_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ATLAS20_ANCHOR_DATE", "2026-05-19")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
