import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://arpeggi.io/api/kits/v1"


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Return True if the exception is a 429 rate limit error."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429
    return False


class KitsAIClient:
    """Thin async HTTP wrapper for the Kits AI (Arpeggi) API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                "Authorization": f"Api-Key {api_key}",
                "Accept": "application/json",
            },
            timeout=60.0,
        )

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "KitsAIClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Raise HTTPStatusError with response body context on non-2xx."""
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Kits AI API error %s %s: %s",
                response.status_code,
                str(response.url),
                response.text,
            )
            raise

    @retry(
        retry=retry_if_exception(_is_rate_limit_error),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def get(self, path: str, **params: Any) -> dict:
        """Perform a GET request and return parsed JSON."""
        response = await self._client.get(path, params=params if params else None)
        self._raise_for_status(response)
        return response.json()

    @retry(
        retry=retry_if_exception(_is_rate_limit_error),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def post(
        self,
        path: str,
        data: Optional[dict] = None,
        files: Optional[dict] = None,
    ) -> dict:
        """Perform a POST request.

        If *files* is provided the request is sent as multipart/form-data;
        otherwise it is sent as application/json.
        """
        if files is not None:
            response = await self._client.post(path, data=data or {}, files=files)
        else:
            response = await self._client.post(path, json=data)
        self._raise_for_status(response)
        return response.json()

    @retry(
        retry=retry_if_exception(_is_rate_limit_error),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def post_multipart(
        self,
        path: str,
        form_data: dict,
        files: Optional[dict] = None,
    ) -> dict:
        """Perform a POST request with multipart/form-data encoding."""
        response = await self._client.post(
            path,
            data=form_data,
            files=files or {},
        )
        self._raise_for_status(response)
        return response.json()

    # ------------------------------------------------------------------
    # Voice model endpoints
    # ------------------------------------------------------------------

    async def list_voice_models(
        self,
        query: str = "",
        page: int = 1,
    ) -> dict:
        """List available voice models.

        GET /voice-models
        """
        params: dict[str, Any] = {"page": page}
        if query:
            params["search"] = query
        return await self.get("/voice-models", **params)

    async def get_voice_model(self, model_id: str) -> dict:
        """Retrieve a single voice model by ID.

        GET /voice-models/{model_id}
        """
        return await self.get(f"/voice-models/{model_id}")

    # ------------------------------------------------------------------
    # Voice conversion endpoints
    # ------------------------------------------------------------------

    async def create_voice_conversion(
        self,
        sound_file_path: str,
        voice_model_id: str,
        pitch_shift: int = 0,
    ) -> dict:
        """Submit a new voice conversion job.

        POST /voice-conversions  (multipart/form-data)
        """
        file_path = Path(sound_file_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Sound file not found: {sound_file_path}")

        form_data: dict[str, Any] = {
            "voiceModelId": str(voice_model_id),
            "pitchShift": str(pitch_shift),
        }

        with file_path.open("rb") as fh:
            files = {"soundFile": (file_path.name, fh, "audio/mpeg")}
            result = await self.post_multipart(
                "/voice-conversions",
                form_data=form_data,
                files=files,
            )
        return result

    async def get_voice_conversion(self, conversion_id: str) -> dict:
        """Retrieve the status / result of a voice conversion job.

        GET /voice-conversions/{conversion_id}
        """
        return await self.get(f"/voice-conversions/{conversion_id}")

    async def list_voice_conversions(self) -> dict:
        """List all voice conversion jobs for the authenticated account.

        GET /voice-conversions
        """
        return await self.get("/voice-conversions")


# ---------------------------------------------------------------------------
# Module-level factory â returns a context-managed client from settings
# ---------------------------------------------------------------------------

def get_kits_client() -> KitsAIClient:
    """Create a KitsAIClient using the application settings.

    Intended to be used as an async context manager::

        async with get_kits_client() as client:
            models = await client.list_voice_models()
    """
    from ..config import get_settings  # local import to avoid circular deps

    settings = get_settings()
    return KitsAIClient(api_key=settings.kits_api_key)
