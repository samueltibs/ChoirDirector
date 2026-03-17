import asyncio
import logging
import tempfile
import os
from pathlib import Path
from typing import Optional

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)

KITS_AI_BASE_URL = "https://arpeggi.io/api/kits/v1"


def _get_headers() -> dict:
    settings = get_settings()
    api_key = settings.kits_ai_api_key
    return {
        "Authorization": f"Api-Key {api_key}",
        "Accept": "application/json",
    }


async def _request_with_retry(
    method: str,
    url: str,
    max_retries: int = 3,
    **kwargs,
) -> httpx.Response:
    """
    Perform an HTTP request with retry logic for 429 (rate limit) responses.
    """
    headers = _get_headers()
    if "headers" in kwargs:
        kwargs["headers"].update(headers)
    else:
        kwargs["headers"] = headers

    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(max_retries):
            try:
                response = await client.request(method, url, **kwargs)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 5 * (attempt + 1)))
                    logger.warning(
                        "Rate limited by Kits AI (429). Waiting %s seconds before retry %s/%s.",
                        retry_after,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 and attempt < max_retries - 1:
                    retry_after = int(exc.response.headers.get("Retry-After", 5 * (attempt + 1)))
                    logger.warning(
                        "Rate limited (HTTPStatusError). Waiting %s seconds.",
                        retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    continue
                logger.error(
                    "HTTP error from Kits AI: %s %s â %s",
                    method,
                    url,
                    exc,
                )
                raise
            except httpx.RequestError as exc:
                logger.error(
                    "Request error communicating with Kits AI: %s %s â %s",
                    method,
                    url,
                    exc,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        raise RuntimeError(f"Kits AI request failed after {max_retries} attempts: {method} {url}")


async def list_voice_models(query: str = "") -> list:
    """
    GET /voice-models â search available voice models.

    Args:
        query: Optional search string to filter voice models.

    Returns:
        List of voice model dicts.
    """
    url = f"{KITS_AI_BASE_URL}/voice-models"
    params = {}
    if query:
        params["search"] = query

    logger.info("Listing Kits AI voice models. Query: '%s'", query)
    response = await _request_with_retry("GET", url, params=params)
    data = response.json()

    # The API may return a list directly or a dict with a results/data key
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "results", "voiceModels", "voice_models", "items"):
            if key in data:
                return data[key]
        return [data]
    return []


async def get_voice_model(model_id: str) -> dict:
    """
    GET /voice-models/{id} â retrieve a specific voice model.

    Args:
        model_id: The voice model identifier.

    Returns:
        Voice model dict.
    """
    url = f"{KITS_AI_BASE_URL}/voice-models/{model_id}"
    logger.info("Fetching Kits AI voice model: %s", model_id)
    response = await _request_with_retry("GET", url)
    return response.json()


async def convert_voice(
    audio_file_path: str,
    voice_model_id: str,
    pitch_shift: int = 0,
) -> dict:
    """
    POST /voice-conversions â submit a voice conversion job.

    Args:
        audio_file_path: Local path to the audio file.
        voice_model_id: The Kits AI voice model ID to convert to.
        pitch_shift: Semitone pitch shift value (default 0).

    Returns:
        Conversion job dict including the job id.
    """
    url = f"{KITS_AI_BASE_URL}/voice-conversions"
    file_path = Path(audio_file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    logger.info(
        "Submitting voice conversion. Model: %s, File: %s, Pitch shift: %s",
        voice_model_id,
        audio_file_path,
        pitch_shift,
    )

    with open(file_path, "rb") as audio_fp:
        mime_type = _guess_mime_type(file_path.suffix)
        files = {
            "soundFile": (file_path.name, audio_fp, mime_type),
        }
        data = {
            "voiceModelId": str(voice_model_id),
            "pitchShiftValue": str(pitch_shift),
        }
        # For multipart we need to pass headers without Content-Type
        # (httpx will set it automatically for multipart)
        headers = _get_headers()
        async with httpx.AsyncClient(timeout=120.0) as client:
            for attempt in range(3):
                try:
                    response = await client.post(
                        url,
                        headers=headers,
                        files=files,
                        data=data,
                    )
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 5 * (attempt + 1)))
                        logger.warning(
                            "Rate limited on voice conversion. Waiting %s seconds.",
                            retry_after,
                        )
                        await asyncio.sleep(retry_after)
                        # Re-open file for next attempt
                        audio_fp.seek(0)
                        continue
                    response.raise_for_status()
                    result = response.json()
                    logger.info("Voice conversion job submitted: %s", result.get("id"))
                    return result
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 429 and attempt < 2:
                        retry_after = int(
                            exc.response.headers.get("Retry-After", 5 * (attempt + 1))
                        )
                        await asyncio.sleep(retry_after)
                        audio_fp.seek(0)
                        continue
                    logger.error("HTTP error submitting voice conversion: %s", exc)
                    raise
                except httpx.RequestError as exc:
                    logger.error("Request error submitting voice conversion: %s", exc)
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        audio_fp.seek(0)
                        continue
                    raise

    raise RuntimeError("Voice conversion submission failed after retries.")


async def get_conversion_status(conversion_id: str) -> dict:
    """
    GET /voice-conversions/{id} â retrieve conversion job status.

    Args:
        conversion_id: The conversion job identifier.

    Returns:
        Conversion job dict with status field.
    """
    url = f"{KITS_AI_BASE_URL}/voice-conversions/{conversion_id}"
    logger.debug("Polling conversion status for: %s", conversion_id)
    response = await _request_with_retry("GET", url)
    return response.json()


async def wait_for_conversion(
    conversion_id: str,
    max_wait: int = 300,
    poll_interval: int = 5,
) -> dict:
    """
    Poll a conversion job until it is done or the timeout is reached.

    Args:
        conversion_id: The conversion job identifier.
        max_wait: Maximum seconds to wait before raising TimeoutError.
        poll_interval: Seconds between status polls.

    Returns:
        Final conversion job dict when status is 'done'.

    Raises:
        TimeoutError: If the conversion does not complete within max_wait.
        RuntimeError: If the conversion fails.
    """
    logger.info(
        "Waiting for conversion %s to complete (max %s seconds).",
        conversion_id,
        max_wait,
    )
    elapsed = 0
    while elapsed < max_wait:
        status_data = await get_conversion_status(conversion_id)
        status = status_data.get("status", "").lower()

        logger.debug(
            "Conversion %s status: %s (elapsed: %ss)",
            conversion_id,
            status,
            elapsed,
        )

        if status in ("done", "complete", "completed", "succeeded", "success"):
            logger.info("Conversion %s completed successfully.", conversion_id)
            return status_data

        if status in ("failed", "error", "cancelled", "canceled"):
            error_msg = status_data.get("error") or status_data.get("message", "Unknown error")
            logger.error(
                "Conversion %s failed with status '%s': %s",
                conversion_id,
                status,
                error_msg,
            )
            raise RuntimeError(
                f"Kits AI voice conversion {conversion_id} failed: {error_msg}"
            )

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(
        f"Kits AI conversion {conversion_id} did not complete within {max_wait} seconds."
    )


async def convert_voice_from_url(
    audio_url: str,
    voice_model_id: str,
    pitch_shift: int = 0,
) -> dict:
    """
    Download an audio file from a URL, then run a voice conversion.

    Args:
        audio_url: URL of the audio file to convert.
        voice_model_id: The Kits AI voice model ID.
        pitch_shift: Semitone pitch shift value.

    Returns:
        Conversion job dict (after submission, not completion).
    """
    logger.info(
        "Downloading audio from URL for voice conversion: %s",
        audio_url,
    )

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.get(audio_url)
        response.raise_for_status()
        audio_bytes = response.content

    # Determine extension from URL or content-type
    content_type = response.headers.get("content-type", "")
    extension = _extension_from_content_type(content_type) or _extension_from_url(audio_url)

    with tempfile.NamedTemporaryFile(
        suffix=extension, delete=False, prefix="choirdir_kits_"
    ) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    logger.info(
        "Audio downloaded to temporary file: %s (%s bytes)",
        tmp_path,
        len(audio_bytes),
    )

    try:
        result = await convert_voice(tmp_path, voice_model_id, pitch_shift=pitch_shift)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError as exc:
            logger.warning("Failed to delete temporary file %s: %s", tmp_path, exc)

    return result


async def generate_choir_parts(
    audio_url: str,
    voice_model_ids: dict,
) -> dict:
    """
    Generate all four SATB choir parts in parallel using Kits AI voice conversion.

    Args:
        audio_url: URL of the source audio file.
        voice_model_ids: Dict mapping part names to voice model IDs.
                         Expected keys: soprano, alto, tenor, bass.
                         Missing keys will be skipped.

    Returns:
        Dict with the same keys as voice_model_ids, each mapped to its
        conversion result dict (after waiting for completion).
    """
    parts = list(voice_model_ids.keys())
    logger.info(
        "Generating choir parts in parallel. Parts: %s, Source: %s",
        parts,
        audio_url,
    )

    async def _convert_part(part_name: str, model_id: str) -> tuple:
        """Submit, wait, and return (part_name, result)."""
        logger.info("Starting conversion for part: %s (model: %s)", part_name, model_id)
        try:
            job = await convert_voice_from_url(audio_url, model_id)
            job_id = job.get("id")
            if not job_id:
                raise ValueError(
                    f"No job ID returned for part '{part_name}'. Response: {job}"
                )
            result = await wait_for_conversion(job_id)
            logger.info("Part '%s' conversion complete.", part_name)
            return part_name, result
        except Exception as exc:
            logger.error(
                "Failed to convert part '%s' with model '%s': %s",
                part_name,
                model_id,
                exc,
                exc_info=True,
            )
            return part_name, {"error": str(exc), "status": "failed"}

    tasks = [
        _convert_part(part, model_id)
        for part, model_id in voice_model_ids.items()
    ]

    results_list = await asyncio.gather(*tasks, return_exceptions=False)

    results = {part: result for part, result in results_list}
    logger.info(
        "Choir part generation complete. Parts processed: %s",
        list(results.keys()),
    )
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _guess_mime_type(suffix: str) -> str:
    """Return a MIME type string for common audio file extensions."""
    mapping = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".aiff": "audio/aiff",
        ".aif": "audio/aiff",
    }
    return mapping.get(suffix.lower(), "application/octet-stream")


def _extension_from_content_type(content_type: str) -> str:
    """Derive a file extension from an HTTP Content-Type header value."""
    mapping = {
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/flac": ".flac",
        "audio/ogg": ".ogg",
        "audio/mp4": ".m4a",
        "audio/aac": ".aac",
        "audio/aiff": ".aiff",
    }
    # Strip parameters (e.g. "audio/mpeg; charset=utf-8")
    base = content_type.split(";")[0].strip().lower()
    return mapping.get(base, "")


def _extension_from_url(url: str) -> str:
    """Extract file extension from a URL path, defaulting to .mp3."""
    path = url.split("?")[0].split("#")[0]
    _, ext = os.path.splitext(path)
    return ext if ext else ".mp3"
