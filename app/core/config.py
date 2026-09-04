from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_NAME: str = "AI Brain"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Gemini LLM & Embeddings Configuration
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google Gemini API key")
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash", description="Primary generative model identifier")
    GEMINI_EMBEDDING_MODEL: str = Field(default="gemini-embedding-001", description="Primary embedding model identifier")

    # Relational Database Configuration
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./ai_brain.db",
        description="Async database connection string",
    )

    # Vector Storage Persistence
    CHROMA_PERSIST_DIRECTORY: str = Field(
        default="./chroma_data",
        description="Local directory for persistent vector database",
    )

    # CORS configuration for Member 2 Frontend integration
    CORS_ORIGINS: List[str] = Field(
        default=["*"],
        description="Allowed CORS origin domains",
    )


settings = Settings()
