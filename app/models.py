from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class ShortenRequest(BaseModel):
    url: HttpUrl
    custom_alias: str | None = Field(default=None, min_length=4, max_length=32)
    ttl_days: int | None = Field(default=None, ge=1, le=3650)


class ShortenResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: HttpUrl
    expires_at: datetime


class UrlInfoResponse(BaseModel):
    short_code: str
    original_url: str
    created_at: datetime
    expires_at: datetime
    is_active: bool


class AnalyticsResponse(BaseModel):
    short_code: str
    total_clicks: int
    unique_visitors: int
    last_accessed_at: datetime | None


class ErrorResponse(BaseModel):
    detail: str

