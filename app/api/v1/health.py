from fastapi import APIRouter
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns service health status without exposing sensitive credentials.",
)
async def health_check() -> HealthResponse:
    """Returns basic service health status."""
    return HealthResponse(
        status="ok",
        service="ai-brain",
        version="0.1.0",
    )
