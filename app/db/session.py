from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# Declarative Base for future SQLAlchemy models
Base = declarative_base()

# Async Engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

# Async Session Factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


_tables_initialized = False


async def init_db() -> None:
    """Initialize all relational database tables and perform lightweight schema migrations."""
    global _tables_initialized
    import app.db.models  # Ensure models are imported and registered with Base.metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _migrate_columns(sync_conn):
            try:
                res = sync_conn.exec_driver_sql("PRAGMA table_info(concept_mastery_records)")
                existing_cols = {row[1] for row in res.fetchall()}
                new_cols = {
                    "repetition_number": "INTEGER DEFAULT 0 NOT NULL",
                    "interval_days": "FLOAT DEFAULT 1.0 NOT NULL",
                    "easiness_factor": "FLOAT DEFAULT 2.5 NOT NULL",
                    "last_reviewed_at": "DATETIME",
                    "next_review_due_at": "DATETIME",
                }
                for col, col_type in new_cols.items():
                    if col not in existing_cols and existing_cols:
                        sync_conn.exec_driver_sql(f"ALTER TABLE concept_mastery_records ADD COLUMN {col} {col_type}")
            except Exception:
                pass

        await conn.run_sync(_migrate_columns)
    _tables_initialized = True


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI & service context manager for obtaining an async database session."""
    global _tables_initialized
    if not _tables_initialized:
        await init_db()
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


