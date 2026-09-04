from datetime import datetime, timezone
from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class HealthResponse(BaseModel):
    """Machine-readable health status."""
    status: str = Field(default="ok", description="Overall health state")
    service: str = Field(default="ai-brain", description="Service identifier")
    version: str = Field(default="0.1.0", description="Service version")


class ResponseMetadata(BaseModel):
    """Standard metadata envelope attached to responses."""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    request_id: Optional[str] = Field(default=None, description="Optional request tracking identifier")


class ApiResponse(BaseModel, Generic[T]):
    """Standard success API response wrapper."""
    success: bool = Field(default=True, description="Indicates request success")
    data: T = Field(description="Payload data")
    error: Optional[Any] = Field(default=None, description="Null for successful responses")
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)


class ApiErrorDetail(BaseModel):
    """Structured error information."""
    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable explanation")
    details: Optional[Any] = Field(default=None, description="Additional context or validation details")


class ApiErrorResponse(BaseModel):
    """Standard error API response wrapper."""
    success: bool = Field(default=False, description="Always false for error responses")
    data: Optional[Any] = Field(default=None, description="Null for errors")
    error: ApiErrorDetail = Field(description="Structured error details")
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)
