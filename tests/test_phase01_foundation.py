import os
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConfigurationError
from app.core.gemini import GeminiClient
from main import app


def test_01_app_imports_successfully():
    """Verify that the FastAPI application imports and initializes properly."""
    assert app is not None
    assert app.title == "AI Brain"
    assert app.version == "0.1.0"


@pytest.mark.asyncio
async def test_02_health_endpoint_returns_200(client):
    """Verify that GET /api/v1/health returns HTTP 200 OK."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_03_health_response_structure(client):
    """Verify that health response contains status, service, and version fields."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert "version" in data
    assert data["status"] == "ok"
    assert data["service"] == "ai-brain"
    assert data["version"] == "0.1.0"


def test_04_configuration_loading():
    """Verify that settings can load default values or custom environment variables."""
    custom_settings = Settings(
        APP_NAME="Custom Brain",
        GEMINI_MODEL="gemini-2.5-flash",
        GEMINI_EMBEDDING_MODEL="gemini-embedding-001",
    )
    assert custom_settings.APP_NAME == "Custom Brain"
    assert custom_settings.GEMINI_MODEL == "gemini-2.5-flash"
    assert custom_settings.GEMINI_EMBEDDING_MODEL == "gemini-embedding-001"
    assert custom_settings.DATABASE_URL.startswith("sqlite+aiosqlite://")


def test_05_gemini_client_lazy_instantiation_without_key():
    """Verify GeminiClient can be instantiated without an API key and fails cleanly only on call."""
    unconfigured_client = GeminiClient(api_key=None)
    assert unconfigured_client.is_configured is False
    with pytest.raises(ConfigurationError) as exc_info:
        unconfigured_client._get_client()
    assert "GEMINI_API_KEY is not configured" in str(exc_info.value)


@pytest.mark.asyncio
async def test_06_database_session_initialization(test_db_session: AsyncSession):
    """Verify database async session can execute simple queries against SQLite."""
    result = await test_db_session.execute(text("SELECT 1"))
    scalar_val = result.scalar()
    assert scalar_val == 1
