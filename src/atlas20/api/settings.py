"""Runtime settings for the Atlas20 API."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: Literal["dev", "test", "prod"] = "dev"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])
    db_url: str = "sqlite:///./data/atlas20.sqlite"
    secret_key: str = "dev-only-do-not-use-in-prod"
    api_keys: set[str] = Field(default_factory=set)
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

    model_config = SettingsConfigDict(env_prefix="ATLAS20_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
