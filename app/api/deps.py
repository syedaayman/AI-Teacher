from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.gemini import GeminiClient, gemini_client
from app.db.session import get_db_session


def get_settings() -> Settings:
    """Dependency for accessing application settings."""
    return settings


def get_gemini() -> GeminiClient:
    """Dependency for accessing the centralized Gemini client."""
    return gemini_client


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for database session injection."""
    async with get_db_session() as session:
        yield session
