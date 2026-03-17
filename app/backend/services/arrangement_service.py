from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import get_settings
from ..database import get_service_client

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_request_status(
    client,
    request_id: str,
    status: str,
    result: dict | None = None,
    error_message: str | None = None,
) -> None:
    payload: dict[str, Any] = {"status": status, "updated_at": _now_iso()}
    if result is not None:
        payload["result"] = result
    if error_message is not None:
        payload["error_message"] = error_message
    client.table("choirdir_arrangement_requests").update(payload).eq(
        "id", request_id
    ).execute()


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def process_arrangement_request(
    request_id: str, customer_id: str
) -> dict:
    """Orchestrate the full arrangement pipeline for a given request row."""

    client = get_service_client()

    # 1. Fetch the arrangement request ----------------------------------------
    resp = (
        client.table("choirdir_arrangement_requests")
        .select("*")
        .eq("id", request_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not resp.data:
        raise ValueError(f"Arrangement request {request_id!r} not found.")

    row: dict[str, Any] = resp.data

    # 2. Mark as processing ---------------------------------------------------
    _update_request_status(client, request_id, "processing")

    try:
        source_type: str = row.get("source_type", "lyrics")
        result: dict[str, Any] = {}
        track_ids: list[str] = []

        # ------------------------------------------------------------------ #
        # Branch on source_type                                               #
        # ------------------------------------------------------------------ #
        if source_type == "lyrics":
            lyrics: str = row.get("lyrics", "") or ""
            style: str = row.get("style", "classical") or "classical"
            voicing: str = row.get("voicing", "SATB") or "SATB"
            key: str = row.get("key", "C major") or "C major"

            arrangement = await generate_arrangement_from_lyrics(
                lyrics=lyrics, style=style, voicing=voicing, key=key
            )
            result = arrangement

            repertoire_id: str | None = row.get("repertoire_id")
            if not repertoire_id:
                # Create a placeholder repertoire entry so tracks have a parent
                rep_resp = (
                    client.table("choirdir_repertoire")
                    .insert(
                        {
                            "id": str(uuid.uuid4()),
                            "customer_id": customer_id,
                            "title": row.get("title") or "Untitled Arrangement",
                            "source_type": "lyrics",
                            "created_at": _now_iso(),
                            "updated_at": _now_iso(),
                        }
                    )
                    .execute()
                )
                if rep_resp.data:
                    repertoire_id = rep_resp.data[0]["id"]

            if repertoire_id:
                track_ids = await create_rehearsal_tracks_for_arrangement(
                    arrangement=arrangement,
                    repertoire_id=repertoire_id,
                    customer_id=customer_id,
                    supabase_client=client,
                )
                result["track_ids"] = track_ids
                result["repertoire_id"] = repertoire_id

        elif source_type == "upload":
            audio_url: str | None = row.get("audio_url")
            if not audio_url:
                raise ValueError("source_type='upload' requires audio_url on the request.")

            kits_result = await _process_audio_via_kits(
                audio_url=audio_url,
                voice_conversion_model=row.get("voice_model") or "default",
            )
            result = {"kits_response": kits_result, "source_type": "upload"}

            # Build minimal arrangement shell so we can create rehearsal tracks
            arrangement_shell = _build_arrangement_shell_from_kits(kits_result)
            repertoire_id = row.get("repertoire_id")
            if repertoire_id:
                track_ids = await create_rehearsal_tracks_for_arrangement(
                    arrangement=arrangement_shell,
                    repertoire_id=repertoire_id,
                    customer_id=customer_id,
                    supabase_client=client,
                )
                result["track_ids"] = track_ids

        elif source_type == "title":
            title: str = row.get("title", "") or ""
            repertoire_row = _lookup_repertoire_by_title(
                client=client, customer_id=customer_id, title=title
            )
            if not repertoire_row:
                raise ValueError(
                    f"No repertoire piece found with title {title!r} for customer {customer_id!r}."
                )

            template = _build_arrangement_template_from_repertoire(repertoire_row)
            result = template

            track_ids = await create_rehearsal_tracks_for_arrangement(
                arrangement=template,
                repertoire_id=repertoire_row["id"],
                customer_id=customer_id,
                supabase_client=client,
            )
            result["track_ids"] = track_ids
            result["repertoire_id"] = repertoire_row["id"]

        else:
            raise ValueError(f"Unknown source_type: {source_type!r}")

        # 3. Persist result & mark completed ----------------------------------
        _update_request_status(client, request_id, "completed", result=result)
        return {"request_id": request_id, "status": "completed", **result}

    except Exception as exc:  # noqa: BLE001
        logger.exception("Arrangement processing failed for request %s", request_id)
        _update_request_status(
            client, request_id, "failed", error_message=str(exc)
        )
        raise


# ---------------------------------------------------------------------------


async def generate_arrangement_from_lyrics(
    lyrics: str,
    style: str = "classical",
    voicing: str = "SATB",
    key: str = "C major",
) -> dict:
    """Generate a structured SATB arrangement skeleton from a lyrics string.

    Returns a dict with keys: soprano, alto, tenor, bass (list of phrase dicts),
    plus measures (int), suggested_tempo (int), style, voicing, key.
    """

    # Split lyrics into lines / phrases for distribution
    lines = [ln.strip() for ln in lyrics.splitlines() if ln.strip()]
    if not lines:
        lines = ["(no lyrics provided)"]

    # Style-based tempo defaults
    _tempo_map = {
        "classical": 72,
        "gospel": 96,
        "contemporary": 108,
        "jazz": 120,
        "folk": 88,
        "spiritual": 60,
    }
    suggested_tempo = _tempo_map.get(style.lower(), 80)

    # Estimate measures: roughly 2 measures per line
    measures = max(4, len(lines) * 2)

    # Determine active voice parts from voicing string
    voicing_upper = voicing.upper()
    parts: list[str] = []
    for part in ["SOPRANO", "ALTO", "TENOR", "BASS"]:
        if part[0] in voicing_upper or part[:2] in voicing_upper:
            parts.append(part.lower())
    if not parts:
        parts = ["soprano", "alto", "tenor", "bass"]

    # Build per-part phrase assignments
    def _build_part_phrases(part_name: str) -> list[dict]:
        phrases = []
        for idx, line in enumerate(lines):
            phrases.append(
                {
                    "measure_start": idx * 2 + 1,
                    "measure_end": idx * 2 + 2,
                    "text": line,
                    "part": part_name,
                    "notes": _default_note_range(part_name, key),
                    "dynamics": "mf",
                }
            )
        return phrases

    arrangement: dict[str, Any] = {
        "style": style,
        "voicing": voicing,
        "key": key,
        "measures": measures,
        "suggested_tempo": suggested_tempo,
        "soprano": [],
        "alto": [],
        "tenor": [],
        "bass": [],
    }

    for part in ["soprano", "alto", "tenor", "bass"]:
        if part in parts:
            arrangement[part] = _build_part_phrases(part)
        else:
            arrangement[part] = []

    return arrangement


# ---------------------------------------------------------------------------


async def create_rehearsal_tracks_for_arrangement(
    arrangement: dict,
    repertoire_id: str,
    customer_id: str,
    supabase_client,
) -> list[str]:
    """Insert choirdir_rehearsal_tracks rows for each voice part and return IDs."""

    track_ids: list[str] = []
    now = _now_iso()

    voice_parts = ["soprano", "alto", "tenor", "bass"]
    for part in voice_parts:
        phrases = arrangement.get(part, [])
        if not phrases:
            # Still create a track entry for empty parts so the choir sees all voices
            phrases = []

        track_id = str(uuid.uuid4())
        track_payload: dict[str, Any] = {
            "id": track_id,
            "customer_id": customer_id,
            "repertoire_id": repertoire_id,
            "voice_part": part,
            "track_data": {
                "phrases": phrases,
                "measures": arrangement.get("measures", 0),
                "suggested_tempo": arrangement.get("suggested_tempo", 80),
                "key": arrangement.get("key", "C major"),
                "style": arrangement.get("style", "classical"),
            },
            "status": "ready",
            "created_at": now,
            "updated_at": now,
        }

        resp = (
            supabase_client.table("choirdir_rehearsal_tracks")
            .insert(track_payload)
            .execute()
        )
        if resp.data:
            track_ids.append(track_id)
        else:
            logger.warning(
                "Failed to insert rehearsal track for part=%s repertoire=%s",
                part,
                repertoire_id,
            )

    return track_ids


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _default_note_range(part: str, key: str) -> dict:
    """Return a simple suggested note range for a voice part."""
    ranges = {
        "soprano": {"low": "C4", "high": "G5", "default": "E4"},
        "alto": {"low": "G3", "high": "C5", "default": "A3"},
        "tenor": {"low": "C3", "high": "G4", "default": "E3"},
        "bass": {"low": "E2", "high": "C4", "default": "G2"},
    }
    return ranges.get(part, {"low": "C3", "high": "C5", "default": "G3"})


async def _process_audio_via_kits(
    audio_url: str,
    voice_conversion_model: str = "default",
) -> dict:
    """Send uploaded audio to Kits AI for voice conversion and return the response."""

    api_key = getattr(settings, "kits_api_key", None)
    if not api_key:
        logger.warning("KITS_API_KEY not configured â returning stub Kits response.")
        return {
            "status": "stub",
            "audio_url": audio_url,
            "model": voice_conversion_model,
            "note": "KITS_API_KEY not set; skipped real conversion.",
        }

    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "audioUrl": audio_url,
        "conversionType": voice_conversion_model,
    }

    async with httpx.AsyncClient(timeout=60.0) as http:
        response = await http.post(
            "https://arpeggi.io/api/kits/v1/voice-conversion",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


def _build_arrangement_shell_from_kits(kits_result: dict) -> dict:
    """Build a minimal arrangement structure from a Kits AI response."""
    return {
        "style": "upload",
        "voicing": "SATB",
        "key": "unknown",
        "measures": 0,
        "suggested_tempo": 80,
        "soprano": [],
        "alto": [],
        "tenor": [],
        "bass": [],
        "kits_output_url": kits_result.get("outputUrl") or kits_result.get("audio_url"),
        "kits_status": kits_result.get("status"),
    }


def _lookup_repertoire_by_title(
    client,
    customer_id: str,
    title: str,
) -> dict | None:
    """Fuzzy title lookup in choirdir_repertoire (case-insensitive ilike)."""
    resp = (
        client.table("choirdir_repertoire")
        .select("*")
        .eq("customer_id", customer_id)
        .ilike("title", f"%{title}%")
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0]
    return None


def _build_arrangement_template_from_repertoire(repertoire_row: dict) -> dict:
    """Build an arrangement template dict from an existing repertoire row."""
    return {
        "style": repertoire_row.get("style", "classical"),
        "voicing": repertoire_row.get("voicing", "SATB"),
        "key": repertoire_row.get("key", "C major"),
        "measures": repertoire_row.get("measures") or 32,
        "suggested_tempo": repertoire_row.get("tempo") or 80,
        "title": repertoire_row.get("title", ""),
        "composer": repertoire_row.get("composer", ""),
        "soprano": [],
        "alto": [],
        "tenor": [],
        "bass": [],
        "source": "repertoire_lookup",
    }
