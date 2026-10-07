from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    base_url: str
    database_path: Path
    default_ttl_days: int
    api_key: str
    api_rate_limit_per_minute: int
    redirect_rate_limit_per_minute: int


def load_settings() -> Settings:
    base_url = os.getenv("SHORTENER_BASE_URL", "http://localhost:8000")
    db_path = Path(os.getenv("SHORTENER_DB_PATH", "data/shortener.db"))
    ttl_days = int(os.getenv("SHORTENER_DEFAULT_TTL_DAYS", "365"))
    api_key = os.getenv("SHORTENER_API_KEY", "dev-interview-key")
    api_rate_limit_per_minute = int(os.getenv("SHORTENER_API_RATE_LIMIT_PER_MINUTE", "120"))
    redirect_rate_limit_per_minute = int(os.getenv("SHORTENER_REDIRECT_RATE_LIMIT_PER_MINUTE", "240"))
    return Settings(
        base_url=base_url.rstrip("/"),
        database_path=db_path,
        default_ttl_days=ttl_days,
        api_key=api_key,
        api_rate_limit_per_minute=api_rate_limit_per_minute,
        redirect_rate_limit_per_minute=redirect_rate_limit_per_minute,
    )
