import hashlib
import json
import sqlite3
import time
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

from app.config import get_settings


T = TypeVar("T")


class SQLiteCache:
    def __init__(self, db_path: str | None = None) -> None:
        settings = get_settings()
        self.db_path = Path(db_path or settings.cache_db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get(self, key: str) -> Any | None:
        now = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache_entries WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        value, expires_at = row
        if expires_at < now:
            self.delete(key)
            return None
        return json.loads(value)

    def set(self, key: str, value: Any, ttl: int) -> None:
        expires_at = int(time.time()) + ttl
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO cache_entries(key, value, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, expires_at = excluded.expires_at
                """,
                (key, payload, expires_at),
            )

    def delete(self, key: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                )
                """
            )


def normalize_cache_key(prefix: str, payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.lower().strip().encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def cached(ttl: int, key_prefix: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    cache = SQLiteCache()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = normalize_cache_key(key_prefix, {"args": args, "kwargs": kwargs})
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result

        return wrapper

    return decorator
