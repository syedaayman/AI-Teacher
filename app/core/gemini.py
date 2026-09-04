from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import ConfigurationError, LLMServiceError

T = TypeVar("T", bound=BaseModel)


_UNSET = object()


class GeminiClient:
    """Centralized isolated wrapper for Google GenAI SDK.
    
    Provides structured output parsing and text generation without
    eagerly connecting on application startup.
    """

    def __init__(self, api_key: Any = _UNSET):
        if api_key is _UNSET:
            self._api_key = settings.GEMINI_API_KEY
        else:
            self._api_key = api_key
        self._client = None

    @property
    def is_configured(self) -> bool:
        """Check if an API key is present."""
        return bool(self._api_key and self._api_key.strip())

    def _get_client(self):
        """Lazy-initialize the official GenAI client only when an operation is invoked."""
        if not self.is_configured:
            raise ConfigurationError(
                "GEMINI_API_KEY is not configured. Please set GEMINI_API_KEY in your .env file."
            )
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except Exception as e:
                raise LLMServiceError(f"Failed to initialize Google GenAI client: {str(e)}") from e
        return self._client

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """Generate plain text from Gemini model."""
        client = self._get_client()
        target_model = model or settings.GEMINI_MODEL
        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
            ) if system_instruction else None

            response = client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=config,
            )
            return response.text or ""
        except Exception as e:
            raise LLMServiceError(f"Gemini text generation failed: {str(e)}") from e

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
    ) -> T:
        """Generate structured output validated against a Pydantic schema."""
        client = self._get_client()
        target_model = model or settings.GEMINI_MODEL
        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                system_instruction=system_instruction,
            )

            response = client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=config,
            )
            
            # If parsed response object is available directly from SDK
            if hasattr(response, "parsed") and response.parsed is not None:
                if isinstance(response.parsed, response_schema):
                    return response.parsed
                return response_schema.model_validate(response.parsed)

            # Fallback to validating raw JSON text
            return response_schema.model_validate_json(response.text)
        except Exception as e:
            raise LLMServiceError(f"Gemini structured generation failed: {str(e)}") from e

    async def embed_text(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> list[float]:
        """Generate a vector embedding for a single text string."""
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty or whitespace-only text.")
        embeddings = await self.embed_batch([text], model=model)
        if not embeddings:
            raise LLMServiceError("Embedding generation returned no embeddings.")
        return embeddings[0]

    async def embed_batch(
        self,
        texts: list[str],
        model: Optional[str] = None,
    ) -> list[list[float]]:
        """Generate vector embeddings for a list of text strings."""
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
            results = []
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
        except Exception as e:
            raise LLMServiceError(f"Gemini embedding generation failed: {str(e)}") from e


# Singleton instance accessible via dependency injection
gemini_client = GeminiClient()
