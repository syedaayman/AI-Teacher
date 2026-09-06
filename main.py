from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.exceptions import (
    AIBrainException,
    ConfigurationError,
    DatabaseError,
    LLMQuotaExceededError,
    LLMServiceError,
    ResourceNotFoundError,
)
from app.schemas.common import ApiErrorDetail, ApiErrorResponse


from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup tasks: initialize database tables
    await init_db()
    yield
    # Shutdown tasks (if any)



def create_application() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Modular AI Brain backend for AI Teacher application.",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ApiErrorResponse(
                error=ApiErrorDetail(
                    code="RESOURCE_NOT_FOUND",
                    message=exc.message,
                    details=exc.details,
                )
            ).model_dump(),
        )

    @app.exception_handler(ConfigurationError)
    async def config_error_handler(request: Request, exc: ConfigurationError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiErrorResponse(
                error=ApiErrorDetail(
                    code="CONFIGURATION_ERROR",
                    message=exc.message,
                    details=exc.details,
                )
            ).model_dump(),
        )

    @app.exception_handler(LLMQuotaExceededError)
    async def llm_quota_handler(request: Request, exc: LLMQuotaExceededError):
        """Return 429 with Retry-After so clients can back off gracefully."""
        retry_after = int(getattr(exc, "retry_after_seconds", 60))
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content=ApiErrorResponse(
                error=ApiErrorDetail(
                    code="LLM_QUOTA_EXCEEDED",
                    message=exc.message,
                    details=exc.details,
                )
            ).model_dump(),
        )

    @app.exception_handler(LLMServiceError)
    async def llm_error_handler(request: Request, exc: LLMServiceError):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=ApiErrorResponse(
                error=ApiErrorDetail(
                    code="LLM_SERVICE_ERROR",
                    message=exc.message,
                    details=exc.details,
                )
            ).model_dump(),
        )

    @app.exception_handler(AIBrainException)
    async def ai_brain_exception_handler(request: Request, exc: AIBrainException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ApiErrorResponse(
                error=ApiErrorDetail(
                    code="AI_BRAIN_ERROR",
                    message=exc.message,
                    details=exc.details,
                )
            ).model_dump(),
        )

    # Top-level direct health check convenience route
    app.include_router(health_router, prefix="", tags=["Health"])

    # Versioned API Router (/api/v1/...)
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
