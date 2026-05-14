from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import wraps
import hashlib
import inspect
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, ParamSpec, TypeVar, cast

from pydantic import BaseModel

from app.config import get_settings
from app.utils.logger import get_logger


P = ParamSpec("P")
R = TypeVar("R")

logger = get_logger(__name__)

DEFAULT_SYNONYMS = {
    "ai": "인공지능",
    "a.i.": "인공지능",
    "인공 지능": "인공지능",
    "전기 자동차": "전기차",
    "전기자동차": "전기차",
    "ev": "전기차",
    "llm": "대규모 언어 모델",
}


class SQLiteCache:
    """Small SQLite-backed JSON cache with TTL semantics."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        settings = get_settings()
        self.db_path = Path(db_path or settings.cache_db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get(self, key: str) -> Any | None:
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache_entries WHERE key = ?",
                (key,),
            ).fetchone()

        if row is None:
            logger.info("cache miss key=%s", _short_key(key))
            return None

        value, expires_at = row
        if expires_at <= now:
            logger.info("cache expired key=%s", _short_key(key))
            self.delete(key)
            return None

        logger.info("cache hit key=%s", _short_key(key))
        return json.loads(value)

    def set(self, key: str, value: Any, ttl: int) -> None:
        now = _now()
        expires_at = now + ttl
        payload = json.dumps(_to_jsonable(value), ensure_ascii=False, sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cache_entries(key, value, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (key, payload, now, expires_at),
            )
        logger.info("cache set key=%s ttl=%s", _short_key(key), ttl)

    def delete(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM cache_entries")

    def purge_expired(self) -> int:
        now = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM cache_entries WHERE expires_at <= ?",
                (now,),
            )
            return cursor.rowcount

    def ping(self) -> bool:
        with self._connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return True

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at
                ON cache_entries(expires_at)
                """
            )


def normalize_cache_key(
    prefix: str,
    payload: Any,
    synonyms: Mapping[str, str] | None = None,
) -> str:
    normalized_payload = normalize_cache_payload(payload, synonyms=synonyms)
    serialized = json.dumps(normalized_payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"{normalize_cache_text(prefix)}:{digest}"


def normalize_cache_payload(
    value: Any,
    synonyms: Mapping[str, str] | None = None,
) -> Any:
    if isinstance(value, BaseModel):
        return normalize_cache_payload(value.model_dump(), synonyms=synonyms)

    if isinstance(value, Mapping):
        return {
            str(key): normalize_cache_payload(value[key], synonyms=synonyms)
            for key in sorted(value)
        }

    if isinstance(value, tuple | list):
        return [normalize_cache_payload(item, synonyms=synonyms) for item in value]

    if isinstance(value, set):
        normalized_items = [normalize_cache_payload(item, synonyms=synonyms) for item in value]
        return sorted(normalized_items, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))

    if isinstance(value, str):
        return normalize_cache_text(value, synonyms=synonyms)

    return value


def normalize_cache_text(
    value: str,
    synonyms: Mapping[str, str] | None = None,
) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    replacements = synonyms if synonyms is not None else DEFAULT_SYNONYMS
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        normalized_source = re.sub(r"\s+", " ", source.strip().lower())
        normalized_target = re.sub(r"\s+", " ", target.strip().lower())
        normalized = normalized.replace(normalized_source, normalized_target)
    return normalized


def cached(
    ttl: int,
    key_prefix: str,
    *,
    cache: SQLiteCache | None = None,
    serializer: Callable[[Any], Any] | None = None,
    deserializer: Callable[[Any], Any] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    target_cache = cache or SQLiteCache()

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(func):
            async_func = cast(Callable[P, Any], func)

            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                key = normalize_cache_key(key_prefix, {"args": args, "kwargs": kwargs})
                cached_value = target_cache.get(key)
                if cached_value is not None:
                    return deserializer(cached_value) if deserializer else cached_value

                result = await async_func(*args, **kwargs)
                target_cache.set(key, serializer(result) if serializer else result, ttl)
                return result

            return cast(Callable[P, R], async_wrapper)

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            key = normalize_cache_key(key_prefix, {"args": args, "kwargs": kwargs})
            cached_value = target_cache.get(key)
            if cached_value is not None:
                return deserializer(cached_value) if deserializer else cached_value

            result = func(*args, **kwargs)
            target_cache.set(key, serializer(result) if serializer else result, ttl)
            return result

        return cast(Callable[P, R], sync_wrapper)

    return decorator


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, set):
        return [_to_jsonable(item) for item in sorted(value)]
    return value


def _short_key(key: str) -> str:
    prefix, _, digest = key.partition(":")
    return f"{prefix}:{digest[:12]}"


def _now() -> int:
    return int(time.time())
