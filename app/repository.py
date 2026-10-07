from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class UrlRecord:
    id: int
    short_code: str
    original_url: str
    created_at: datetime
    expires_at: datetime
    custom_alias: bool
    is_active: bool


@dataclass(frozen=True)
class AnalyticsRecord:
    total_clicks: int
    unique_visitors: int
    last_accessed_at: datetime | None


class UrlRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    short_code TEXT UNIQUE NOT NULL,
                    original_url TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    custom_alias INTEGER NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS click_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url_id INTEGER NOT NULL,
                    clicked_at TEXT NOT NULL,
                    visitor_hash TEXT NOT NULL,
                    referrer TEXT,
                    user_agent TEXT,
                    FOREIGN KEY(url_id) REFERENCES urls(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_click_events_url_id
                ON click_events(url_id)
                """
            )

    def insert_url(
        self,
        short_code: str,
        original_url: str,
        created_at: datetime,
        expires_at: datetime,
        custom_alias: bool,
    ) -> UrlRecord:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO urls(short_code, original_url, created_at, expires_at, custom_alias, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    short_code,
                    original_url,
                    created_at.isoformat(),
                    expires_at.isoformat(),
                    1 if custom_alias else 0,
                ),
            )
            url_id = int(cursor.lastrowid)
            return UrlRecord(
                id=url_id,
                short_code=short_code,
                original_url=original_url,
                created_at=created_at,
                expires_at=expires_at,
                custom_alias=custom_alias,
                is_active=True,
            )

    def get_by_short_code(self, short_code: str) -> UrlRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM urls WHERE short_code = ?",
                (short_code,),
            ).fetchone()
            return _row_to_url_record(row) if row else None

    def get_active_by_original_url(self, original_url: str, now: datetime) -> UrlRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM urls
                WHERE original_url = ? AND is_active = 1 AND expires_at > ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (original_url, now.isoformat()),
            ).fetchone()
            return _row_to_url_record(row) if row else None

    def add_click_event(
        self,
        url_id: int,
        clicked_at: datetime,
        visitor_hash: str,
        referrer: str | None,
        user_agent: str | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO click_events(url_id, clicked_at, visitor_hash, referrer, user_agent)
                VALUES (?, ?, ?, ?, ?)
                """,
                (url_id, clicked_at.isoformat(), visitor_hash, referrer, user_agent),
            )

    def get_analytics(self, url_id: int) -> AnalyticsRecord:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_clicks,
                    COUNT(DISTINCT visitor_hash) AS unique_visitors,
                    MAX(clicked_at) AS last_accessed_at
                FROM click_events
                WHERE url_id = ?
                """,
                (url_id,),
            ).fetchone()
            last_accessed_raw = row["last_accessed_at"]
            return AnalyticsRecord(
                total_clicks=int(row["total_clicks"]),
                unique_visitors=int(row["unique_visitors"]),
                last_accessed_at=datetime.fromisoformat(last_accessed_raw).astimezone(timezone.utc)
                if last_accessed_raw
                else None,
            )


def _row_to_url_record(row: sqlite3.Row) -> UrlRecord:
    return UrlRecord(
        id=int(row["id"]),
        short_code=str(row["short_code"]),
        original_url=str(row["original_url"]),
        created_at=datetime.fromisoformat(str(row["created_at"])).astimezone(timezone.utc),
        expires_at=datetime.fromisoformat(str(row["expires_at"])).astimezone(timezone.utc),
        custom_alias=bool(row["custom_alias"]),
        is_active=bool(row["is_active"]),
    )
