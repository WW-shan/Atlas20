"""Runtime settings for the Atlas20 API."""

from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


DEV_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _parse_string_collection(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            value = json.loads(stripped)
        else:
            return [item.strip() for item in stripped.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    raise TypeError("expected comma-separated string or collection")


class Settings(BaseSettings):
    env: Literal["dev", "test", "prod"] = "dev"
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: list(DEV_CORS_ORIGINS))
    db_url: str = "sqlite:///./data/atlas20.sqlite"
    secret_key: str = "dev-only-do-not-use-in-prod"
    api_keys: Annotated[set[str], NoDecode] = Field(default_factory=set)
    enable_docs: bool = True
    report_root: Path = Path("reports")
    backup_root: Path = Path("backups")
    backup_retention_days: int = 30
    data_root: Path = Path("data")
    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])
    anchor_date: date | None = None
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "text"] = "json"
    run_timeout_seconds: int = 1800
    worker_poll_interval_seconds: float = 2.0
    worker_heartbeat_interval_seconds: float = 2.0
    worker_cancel_grace_seconds: float = 3.0

    model_config = SettingsConfigDict(env_prefix="ATLAS20_", env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        return _parse_string_collection(value)

    @field_validator("api_keys", mode="before")
    @classmethod
    def parse_api_keys(cls, value: Any) -> set[str]:
        return set(_parse_string_collection(value))

    @model_validator(mode="after")
    def enforce_prod_gates(self) -> "Settings":
        if self.env == "prod":
            self.enable_docs = False
            if "*" in self.cors_origins:
                raise RuntimeError("ATLAS20_CORS_ORIGINS must not include '*' in prod")
            if not self.cors_origins or (
                self.cors_origins == DEV_CORS_ORIGINS and "ATLAS20_CORS_ORIGINS" not in os.environ
            ):
                raise RuntimeError("ATLAS20_CORS_ORIGINS must be set in prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
