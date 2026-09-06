"""Centralized Google Gemini API client with quota-aware error handling.

Error resilience strategy
--------------------------
*  429 RESOURCE_EXHAUSTED  →  ``LLMQuotaExceededError`` (includes parsed retry-after)
*  502 / 503 / transient   →  ``LLMServiceError`` (hard failure, not retryable here)
*  Missing key             →  ``ConfigurationError`` (startup / configuration problem)

Callers that want to activate a fallback path should catch
``LLMQuotaExceededError`` specifically.  Catching ``LLMServiceError`` (the
parent) will also capture quota errors if a coarser handler is acceptable.
"""

import logging
import re
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import ConfigurationError, LLMQuotaExceededError, LLMServiceError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_UNSET = object()

# Regex to extract "Please retry in Xs." from Gemini error messages
_RETRY_AFTER_RE = re.compile(r"retry\s+in\s+([\d.]+)\s*s", re.IGNORECASE)

# HTTP-status-like codes that indicate transient quota or overload
_QUOTA_HTTP_CODES = {429, 502, 503}


def _parse_retry_after(message: str) -> float:
    """Extract retry-after seconds from a Gemini error message string.

    Falls back to 60 s when no delay is embedded in the message.
    """
    match = _RETRY_AFTER_RE.search(message)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 60.0


def _is_quota_error(exc: Exception) -> bool:
    """Return True when *exc* represents a retriable capacity/quota error.

    Covers:
    * 429 RESOURCE_EXHAUSTED — hard quota limit hit
    * 502 BAD GATEWAY        — transient upstream proxy failure
    * 503 UNAVAILABLE        — transient overload / high demand
    """
    msg = str(exc)
    # Gemini SDK wraps gRPC status codes in the message string
    if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
        return True
    if "UNAVAILABLE" in msg or "503" in msg or "502" in msg or "Bad Gateway" in msg:
        return True
    # Some SDK versions expose a status_code / code attribute
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status in _QUOTA_HTTP_CODES:
        return True
    return False


def _classify_and_raise(exc: Exception, context: str) -> None:
    """Convert a raw SDK / network exception into the appropriate domain error.

    Args:
        exc:     The raw exception caught from the Google GenAI SDK.
        context: Human-readable description of the operation that failed
                 (used in log messages and error strings).

    Raises:
        LLMQuotaExceededError: When the API signals a 429 / quota exhaustion.
        LLMServiceError:       For all other failures.
    """
    msg = str(exc)
    if _is_quota_error(exc):
        retry_after = _parse_retry_after(msg)
        human_msg = (
            f"Gemini API quota exceeded during {context}. "
            f"Retry after {retry_after:.0f}s. "
            "Activating fallback mode."
        )
        logger.warning(
            "GeminiClient quota exceeded [%s]: retry_after=%.0fs | raw=%s",
            context,
            retry_after,
            msg[:200],
        )
        raise LLMQuotaExceededError(
            message=human_msg,
            retry_after_seconds=retry_after,
            details={"raw_error": msg[:500], "context": context},
        ) from exc

    # Hard / unexpected failure
    logger.error("GeminiClient failure [%s]: %s", context, msg[:300])
    raise LLMServiceError(f"Gemini {context} failed: {msg}") from exc


class GeminiClient:
    """Centralized isolated wrapper for Google GenAI SDK.

    Provides structured output parsing and text generation without
    eagerly connecting on application startup.

    All methods distinguish quota errors (``LLMQuotaExceededError``) from
    hard failures (``LLMServiceError``) so callers can activate graceful
    fallback paths instead of surfacing a raw 502 to the frontend.
    """

    def __init__(self, api_key: Any = _UNSET):
        if api_key is _UNSET:
            self._api_key = settings.GEMINI_API_KEY
        else:
            self._api_key = api_key
        self._client = None

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        """Return True when a non-empty API key is present."""
        return bool(self._api_key and self._api_key.strip())

    def _get_client(self):
        """Lazy-initialise the official GenAI client on first use."""
        if not self.is_configured:
            raise ConfigurationError(
                "GEMINI_API_KEY is not configured. Please set GEMINI_API_KEY in your .env file."
            )
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except Exception as e:
                raise LLMServiceError(
                    f"Failed to initialise Google GenAI client: {e}"
                ) from e
        return self._client

    # ------------------------------------------------------------------
    # Text generation
    # ------------------------------------------------------------------

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """Generate plain text from Gemini model.

        Raises:
            LLMQuotaExceededError: On 429 / RESOURCE_EXHAUSTED.
            LLMServiceError:       On all other failures.
        """
        client = self._get_client()
        target_model = model or settings.GEMINI_MODEL
        fallback_pool = [
            target_model,
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash",
        ]
        # De-duplicate while preserving priority order
        candidate_models = list(dict.fromkeys(fallback_pool))

        last_error = None
        for cand in candidate_models:
            try:
                from google.genai import types

                config = (
                    types.GenerateContentConfig(system_instruction=system_instruction)
                    if system_instruction
                    else None
                )
                response = client.models.generate_content(
                    model=cand,
                    contents=prompt,
                    config=config,
                )
                return response.text or ""
            except (LLMServiceError, LLMQuotaExceededError):
                raise
            except Exception as e:
                err_str = str(e)
                if ("404" in err_str or "NOT_FOUND" in err_str or "not found" in err_str.lower() or "503" in err_str) and cand != candidate_models[-1]:
                    logger.warning("Model '%s' failed or not found, cascading to next model", cand)
                    last_error = e
                    continue
                _classify_and_raise(e, context="text generation")
        if last_error:
            _classify_and_raise(last_error, context="text generation")
        return ""

    # ------------------------------------------------------------------
    # Structured / JSON generation
    # ------------------------------------------------------------------

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
    ) -> T:
        """Generate structured output validated against a Pydantic schema.

        Raises:
            LLMQuotaExceededError: On 429 / RESOURCE_EXHAUSTED.
            LLMServiceError:       On all other failures.
        """
        client = self._get_client()
        target_model = model or settings.GEMINI_MODEL
        fallback_pool = [
            target_model,
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash",
        ]
        candidate_models = list(dict.fromkeys(fallback_pool))

        last_error = None
        for cand in candidate_models:
            try:
                from google.genai import types

                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    system_instruction=system_instruction,
                )
                response = client.models.generate_content(
                    model=cand,
                    contents=prompt,
                    config=config,
                )

                # Prefer the SDK's native parsed object when available
                if hasattr(response, "parsed") and response.parsed is not None:
                    if isinstance(response.parsed, response_schema):
                        return response.parsed
                    return response_schema.model_validate(response.parsed)

                # Fallback: validate raw JSON text
                return response_schema.model_validate_json(response.text)
            except (LLMServiceError, LLMQuotaExceededError):
                raise
            except Exception as e:
                err_str = str(e)
                if ("404" in err_str or "NOT_FOUND" in err_str or "not found" in err_str.lower()) and cand != candidate_models[-1]:
                    logger.warning("Model '%s' not found on API for structured generation, cascading to '%s'", cand, candidate_models[-1])
                    last_error = e
                    continue
                _classify_and_raise(e, context="structured generation")
        if last_error:
            _classify_and_raise(last_error, context="structured generation")

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    async def embed_text(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> list[float]:
        """Generate a single vector embedding.

        Raises:
            LLMQuotaExceededError: On 429 / RESOURCE_EXHAUSTED.
            LLMServiceError:       On all other failures.
        """
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty or whitespace-only text.")
        embeddings = await self.embed_batch([text], model=model)
        if not embeddings:
            raise LLMServiceError("Embedding generation returned no results.")
        return embeddings[0]

    async def embed_batch(
        self,
        texts: list[str],
        model: Optional[str] = None,
    ) -> list[list[float]]:
        """Generate vector embeddings for a list of text strings.

        Raises:
            LLMQuotaExceededError: On 429 / RESOURCE_EXHAUSTED.
            LLMServiceError:       On all other failures.
        """
        if not texts:
            return []
        for idx, t in enumerate(texts):
            if not t or not t.strip():
                raise ValueError(f"Cannot generate embedding for empty text at index {idx}.")

        client = self._get_client()
        target_model = model or settings.GEMINI_EMBEDDING_MODEL
        try:
            response = client.models.embed_content(
                model=target_model,
                contents=texts,
            )
            results: list[list[float]] = []
            if hasattr(response, "embeddings") and response.embeddings:
                for emb in response.embeddings:
                    if hasattr(emb, "values"):
                        results.append(list(emb.values))
                    elif isinstance(emb, (list, tuple)):
                        results.append(list(emb))
                    else:
                        results.append(list(getattr(emb, "embedding", [])))
            elif hasattr(response, "embedding"):
                emb = response.embedding
                if hasattr(emb, "values"):
                    results.append(list(emb.values))
                else:
                    results.append(list(emb))
            return results
        except (LLMServiceError, LLMQuotaExceededError):
            raise  # already classified — re-raise as-is
        except Exception as e:
            _classify_and_raise(e, context="embedding generation")


# Singleton instance accessible via dependency injection
gemini_client = GeminiClient()
