"""
Test configuration — shared fixtures and test client setup.

pytest-asyncio is configured in auto mode (see pyproject.toml), so
async test functions work without explicit @pytest.mark.asyncio decorators.
"""

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.core.config import AppSettings, get_settings
from app.main import create_app


def _test_settings() -> AppSettings:
    """Override settings for unit tests — avoids needing a real .env file."""
    # Reset the lru_cache so tests get a fresh settings object
    get_settings.cache_clear()
    return AppSettings(
        environment="local",
        debug=True,
        log_level="DEBUG",
        # Minimal Azure stubs — real values not needed for unit tests
        azure_openai={
            "endpoint": "https://test.openai.azure.com",
            "api_key": "test-key",
            "chat_deployment": "gpt-4o-test",
            "embedding_deployment": "embedding-test",
        },
        azure_search={
            "endpoint": "https://test.search.windows.net",
            "api_key": "test-key",
        },
        azure_blob={
            "connection_string": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;",
        },
    )


@pytest.fixture(scope="session")
def test_app():
    """Create a test FastAPI application instance."""
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_settings] = _test_settings
    return app


@pytest.fixture
def client(test_app) -> TestClient:
    """Synchronous test client for simple endpoint tests."""
    return TestClient(test_app)


@pytest.fixture
async def async_client(test_app) -> AsyncClient:
    """Async test client for async endpoint and service tests."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        yield client
