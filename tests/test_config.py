import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_rejects_mock_llm_provider():
    with pytest.raises(ValidationError) as exc_info:
        Settings(app_env="production", llm_provider="mock")

    assert "LLM_PROVIDER=mock is not allowed in production" in str(exc_info.value)


def test_local_allows_mock_llm_provider_for_offline_tests():
    settings = Settings(app_env="local", llm_provider="mock")

    assert settings.llm_provider == "mock"
