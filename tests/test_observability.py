import logging

from fastapi.testclient import TestClient

import app.main as main_module
from app.config import Settings
from app.main import app
from app.utils.logger import get_logger


client = TestClient(app)


def test_health_reports_app_state():
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "patent-easy-backend"
    assert "version" in payload
    assert "environment" in payload


def test_ready_reports_cache_and_dependency_configuration(monkeypatch, tmp_path):
    monkeypatch.setattr(
        main_module,
        "settings",
        Settings(
            llm_provider="mock",
            kipris_api_key="kipris-key",
            cache_db_path=str(tmp_path / "cache.sqlite"),
        ),
    )

    response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["cache"]["status"] == "ok"
    assert payload["checks"]["kipris"]["status"] == "configured"
    assert payload["checks"]["llm"]["status"] == "mock"
    assert "kipris-key" not in response.text


def test_ready_returns_503_when_cache_is_unavailable(monkeypatch, tmp_path):
    invalid_parent = tmp_path / "not-a-directory"
    invalid_parent.write_text("file", encoding="utf-8")
    monkeypatch.setattr(
        main_module,
        "settings",
        Settings(
            llm_provider="mock",
            kipris_api_key="kipris-key",
            cache_db_path=str(invalid_parent / "cache.sqlite"),
        ),
    )

    response = client.get("/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["cache"]["status"] == "error"


def test_request_logging_includes_duration_without_query_string(caplog):
    with caplog.at_level("INFO", logger="app.main"):
        response = client.get("/health?api_key=secret")

    assert response.status_code == 200
    assert "request method=GET path=/health status_code=200 duration_ms=" in caplog.text
    assert "api_key=secret" not in caplog.text


def test_external_http_client_loggers_do_not_emit_info_urls():
    get_logger("tests.observability")

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
