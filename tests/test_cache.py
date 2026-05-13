import asyncio

from app.services.cache import SQLiteCache, cached, normalize_cache_key


def test_sqlite_cache_get_set_delete_and_expiration(tmp_path):
    cache = SQLiteCache(tmp_path / "cache.sqlite")

    cache.set("sample", {"value": "cached"}, ttl=60)
    assert cache.get("sample") == {"value": "cached"}

    cache.delete("sample")
    assert cache.get("sample") is None

    cache.set("expired", {"value": "old"}, ttl=-1)
    assert cache.get("expired") is None


def test_sqlite_cache_ping_checks_connection(tmp_path):
    cache = SQLiteCache(tmp_path / "cache.sqlite")

    assert cache.ping() is True


def test_cache_logs_hit_and_miss_without_cached_payload(caplog, tmp_path):
    cache = SQLiteCache(tmp_path / "cache.sqlite")

    with caplog.at_level("INFO", logger="app.services.cache"):
        cache.get("sample")
        cache.set("sample", {"secret": "payload"}, ttl=60)
        cache.get("sample")

    assert "cache miss key=sample:" in caplog.text
    assert "cache set key=sample:" in caplog.text
    assert "cache hit key=sample:" in caplog.text
    assert "payload" not in caplog.text


def test_cache_key_normalizes_case_whitespace_and_synonyms():
    first = normalize_cache_key("Search", {"query": " 전기 자동차   AI "})
    second = normalize_cache_key("search", {"query": "전기차 인공지능"})

    assert first == second


def test_sync_cached_decorator_reuses_result(tmp_path):
    cache = SQLiteCache(tmp_path / "cache.sqlite")
    calls = 0

    @cached(ttl=60, key_prefix="sync", cache=cache)
    def expensive(value: str) -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"value": value}

    assert expensive("전기 자동차") == {"value": "전기 자동차"}
    assert expensive("전기차") == {"value": "전기 자동차"}
    assert calls == 1


def test_async_cached_decorator_reuses_result(tmp_path):
    async def run() -> None:
        cache = SQLiteCache(tmp_path / "cache.sqlite")
        calls = 0

        @cached(ttl=60, key_prefix="async", cache=cache)
        async def expensive(value: str) -> dict[str, str]:
            nonlocal calls
            calls += 1
            return {"value": value}

        assert await expensive("LLM") == {"value": "LLM"}
        assert await expensive("대규모 언어 모델") == {"value": "LLM"}
        assert calls == 1

    asyncio.run(run())
