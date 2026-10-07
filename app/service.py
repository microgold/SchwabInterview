from __future__ import annotations

import hashlib
import secrets
import string
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlite3 import IntegrityError, OperationalError

from app.repository import AnalyticsRecord, UrlRecord, UrlRepository

BASE62 = string.ascii_letters + string.digits


class UrlServiceError(Exception):
    """Base exception for URL shortener service failures."""


class AliasAlreadyExistsError(UrlServiceError):
    pass


class UrlNotFoundError(UrlServiceError):
    pass


class UrlExpiredError(UrlServiceError):
    pass


@dataclass(frozen=True)
class CreateUrlResult:
    short_code: str
    original_url: str
    expires_at: datetime


@dataclass(frozen=True)
class ResolveResult:
    original_url: str
    short_code: str


@dataclass(frozen=True)
class AnalyticsResult:
    short_code: str
    total_clicks: int
    unique_visitors: int
    last_accessed_at: datetime | None


class UrlService:
    def __init__(self, repository: UrlRepository, default_ttl_days: int) -> None:
        self._repository = repository
        self._default_ttl_days = default_ttl_days

    def create_short_url(
        self,
        original_url: str,
        custom_alias: str | None,
        ttl_days: int | None,
    ) -> CreateUrlResult:
        now = datetime.now(timezone.utc)
        expiration_days = ttl_days if ttl_days is not None else self._default_ttl_days
        expires_at = now + timedelta(days=expiration_days)

        if custom_alias:
            self._try_insert(custom_alias, original_url, now, expires_at, custom_alias=True)
            return CreateUrlResult(custom_alias, original_url, expires_at)

        existing = self._repository.get_active_by_original_url(original_url=original_url, now=now)
        if existing:
            return CreateUrlResult(existing.short_code, existing.original_url, existing.expires_at)

        for _ in range(5):
            candidate = _generate_short_code(length=7)
            try:
                self._try_insert(candidate, original_url, now, expires_at, custom_alias=False)
                return CreateUrlResult(candidate, original_url, expires_at)
            except AliasAlreadyExistsError:
                continue

        raise UrlServiceError("Could not generate a unique short code after multiple attempts.")

    def get_url_info(self, short_code: str) -> UrlRecord:
        record = self._repository.get_by_short_code(short_code)
        if not record:
            raise UrlNotFoundError(f"Short code '{short_code}' does not exist.")
        return record

    def resolve_short_code(
        self,
        short_code: str,
        user_agent: str | None,
        referrer: str | None,
        client_host: str | None,
    ) -> ResolveResult:
        record = self.get_url_info(short_code)
        now = datetime.now(timezone.utc)
        if record.expires_at <= now or not record.is_active:
            raise UrlExpiredError(f"Short code '{short_code}' has expired.")

        visitor_hash = _compute_visitor_hash(client_host=client_host, user_agent=user_agent)
        self._repository.add_click_event(
            url_id=record.id,
            clicked_at=now,
            visitor_hash=visitor_hash,
            referrer=referrer,
            user_agent=user_agent,
        )
        return ResolveResult(original_url=record.original_url, short_code=record.short_code)

    def get_analytics(self, short_code: str) -> AnalyticsResult:
        record = self.get_url_info(short_code)
        analytics: AnalyticsRecord = self._repository.get_analytics(record.id)
        return AnalyticsResult(
            short_code=short_code,
            total_clicks=analytics.total_clicks,
            unique_visitors=analytics.unique_visitors,
            last_accessed_at=analytics.last_accessed_at,
        )

    def _try_insert(
        self,
        short_code: str,
        original_url: str,
        created_at: datetime,
        expires_at: datetime,
        custom_alias: bool,
    ) -> UrlRecord:
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                return self._repository.insert_url(
                    short_code=short_code,
                    original_url=original_url,
                    created_at=created_at,
                    expires_at=expires_at,
                    custom_alias=custom_alias,
                )
            except IntegrityError as exc:
                raise AliasAlreadyExistsError(f"Alias '{short_code}' already exists.") from exc
            except OperationalError:
                if attempt == max_attempts:
                    raise
                time.sleep(0.05 * attempt)
        raise UrlServiceError("Insert failed unexpectedly.")


def _generate_short_code(length: int) -> str:
    return "".join(secrets.choice(BASE62) for _ in range(length))


def _compute_visitor_hash(client_host: str | None, user_agent: str | None) -> str:
    payload = f"{client_host or 'unknown'}::{user_agent or 'unknown'}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
