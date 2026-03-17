import io
import json
import logging
import time
import zipfile
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

try:
    from midiutil import MIDIFile
    MIDIUTIL_AVAILABLE = True
except ImportError:
    MIDIUTIL_AVAILABLE = False
    logger.warning("midiutil not available; MIDI export will produce a stub file")

from ..config import get_settings

settings = get_settings()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_job_status(
    job_id: str,
    status: str,
    service_client,
    *,
    meta_patch: dict | None = None,
    result_media_asset_id: str | None = None,
    error_message: str | None = None,
) -> None:
    payload: dict[str, Any] = {"status": status, "updated_at": _now_iso()}
    if status == "running":
        payload["started_at"] = _now_iso()
    if status in ("succeeded", "failed"):
        payload["completed_at"] = _now_iso()
    if result_media_asset_id:
        payload["result_media_asset_id"] = result_media_asset_id
    if error_message:
        payload["error_message"] = error_message
    if meta_patch:
        # merge into existing meta
        row = (
            service_client.table("choirdir_export_jobs")
            .select("meta")
            .eq("id", job_id)
            .single()
            .execute()
        )
        existing_meta: dict = (row.data or {}).get("meta") or {}
        existing_meta.update(meta_patch)
        payload["meta"] = existing_meta

    service_client.table("choirdir_export_jobs").update(payload).eq("id", job_id).execute()


def _upload_bytes(
    data: bytes,
    storage_path: str,
    bucket: str,
    content_type: str,
    service_client,
) -> str:
    """Upload bytes to Supabase Storage and return the storage path."""
    service_client.storage.from_(bucket).upload(
        path=storage_path,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return storage_path


def _create_media_asset(
    project_id: str,
    asset_type: str,
    storage_path: str,
    bucket: str,
    file_name: str,
    file_size: int,
    mime_type: str,
    service_client,
    meta: dict | None = None,
) -> str:
    """Insert a choirdir_media_assets row and return the new id."""
    payload = {
        "project_id": project_id,
        "asset_type": asset_type,
        "storage_path": storage_path,
        "bucket": bucket,
        "file_name": file_name,
        "file_size": file_size,
        "mime_type": mime_type,
        "meta": meta or {},
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    result = service_client.table("choirdir_media_assets").insert(payload).execute()
    return result.data[0]["id"]


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

async def process_export_job(job_id: str, service_client) -> dict:
    """Fetch the export job, route to the correct handler, manage status transitions."""
    row_result = (
        service_client.table("choirdir_export_jobs")
        .select("*")
        .eq("id", job_id)
        .single()
        .execute()
    )
    if not row_result.data:
        raise ValueError(f"Export job {job_id} not found")

    job = row_result.data
    job_type: str = job.get("job_type") or job.get("type", "")
    project_id: str = job.get("project_id", "")
    options: dict = job.get("options") or job.get("meta") or {}

    _update_job_status(job_id, "running", service_client)

    try:
        if job_type == "export_midi":
            result = await export_midi(job_id, project_id, options, service_client)
        elif job_type == "export_guide_audio":
            result = await export_guide_audio_pack(job_id, project_id, options, service_client)
        elif job_type == "export_pdf":
            result = await export_pdf(job_id, project_id, options, service_client)
        else:
            raise ValueError(f"Unknown export job type: {job_type!r}")

        _update_job_status(
            job_id,
            "succeeded",
            service_client,
            result_media_asset_id=result.get("media_asset_id"),
        )
        return result
    except Exception as exc:  # noqa: BLE001
        logger.exception("Export job %s failed", job_id)
        _update_job_status(job_id, "failed", service_client, error_message=str(exc))
        raise


async def export_midi(
    job_id: str,
    project_id: str,
    options: dict,
    service_client,
) -> dict:
    """Generate a MIDI file from harmony_notes and upload to Storage."""
    # --- fetch project info ------------------------------------------------
    project_result = (
        service_client.table("choirdir_projects")
        .select("id, name")
        .eq("id", project_id)
        .single()
        .execute()
    )
    project_name: str = (
        project_result.data.get("name", "project") if project_result.data else "project"
    )
    safe_name = project_name.replace(" ", "_").replace("/", "-")[:60]

    # --- fetch harmony notes -----------------------------------------------
    notes_result = (
        service_client.table("choirdir_harmony_notes")
        .select("midi_note, start_time_sec, end_time_sec, velocity, voice_part_id")
        .eq("project_id", project_id)
        .order("start_time_sec")
        .execute()
    )
    notes = notes_result.data or []

    # --- build MIDI --------------------------------------------------------
    midi_bytes = _build_midi(notes, options)

    # --- upload ------------------------------------------------------------
    bucket = "choir-director-exports"
    storage_path = f"exports/{project_id}/{safe_name}.mid"
    _upload_bytes(midi_bytes, storage_path, bucket, "audio/midi", service_client)

    # --- media asset -------------------------------------------------------
    asset_id = _create_media_asset(
        project_id=project_id,
        asset_type="export_midi",
        storage_path=storage_path,
        bucket=bucket,
        file_name=f"{safe_name}.mid",
        file_size=len(midi_bytes),
        mime_type="audio/midi",
        service_client=service_client,
        meta={"note_count": len(notes), "job_id": job_id},
    )

    # update the job with asset id
    service_client.table("choirdir_export_jobs").update(
        {"result_media_asset_id": asset_id, "updated_at": _now_iso()}
    ).eq("id", job_id).execute()

    signed_url = await generate_signed_download_url(storage_path, bucket)

    return {
        "media_asset_id": asset_id,
        "storage_path": storage_path,
        "signed_url": signed_url,
        "note_count": len(notes),
    }


async def export_guide_audio_pack(
    job_id: str,
    project_id: str,
    options: dict,
    service_client,
) -> dict:
    """Build per-voice-part zip packs and upload to Storage."""
    bucket = "choir-director-exports"

    # --- fetch voice parts -------------------------------------------------
    vp_result = (
        service_client.table("choirdir_voice_parts")
        .select("id, name")
        .eq("project_id", project_id)
        .execute()
    )
    voice_parts = vp_result.data or []
    if not voice_parts:
        # fallback: try global voice parts
        vp_result = (
            service_client.table("choirdir_voice_parts")
            .select("id, name")
            .is_("project_id", "null")
            .execute()
        )
        voice_parts = vp_result.data or []

    # --- fetch media assets that are guide audio for this project ----------
    assets_result = (
        service_client.table("choirdir_media_assets")
        .select("id, voice_part_id, storage_path, file_name, bucket, mime_type")
        .eq("project_id", project_id)
        .eq("asset_type", "guide_audio")
        .execute()
    )
    assets = assets_result.data or []

    # group assets by voice_part_id
    assets_by_vp: dict[str, list[dict]] = {}
    for asset in assets:
        vpid = asset.get("voice_part_id") or "__unassigned"
        assets_by_vp.setdefault(vpid, []).append(asset)

    pack_urls: dict[str, str] = {}
    pack_asset_ids: dict[str, str] = {}
    packs_generated: list[str] = []

    for vp in voice_parts:
        vp_id: str = vp["id"]
        vp_name: str = vp.get("name", vp_id).replace(" ", "_")[:40]
        vp_assets = assets_by_vp.get(vp_id, [])

        if not vp_assets:
            continue

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for asset in vp_assets:
                src_path: str = asset.get("storage_path", "")
                src_bucket: str = asset.get("bucket") or "choir-director-uploads"
                fname: str = asset.get("file_name") or src_path.split("/")[-1]
                try:
                    file_bytes = service_client.storage.from_(src_bucket).download(src_path)
                    zf.writestr(fname, file_bytes)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Could not download asset %s for zip: %s", asset.get("id"), exc
                    )

        zip_bytes = zip_buffer.getvalue()
        zip_path = f"exports/{project_id}/guide_audio/{vp_name}_guide.zip"
        _upload_bytes(zip_bytes, zip_path, bucket, "application/zip", service_client)

        pack_asset_id = _create_media_asset(
            project_id=project_id,
            asset_type="export_guide_audio_pack",
            storage_path=zip_path,
            bucket=bucket,
            file_name=f"{vp_name}_guide.zip",
            file_size=len(zip_bytes),
            mime_type="application/zip",
            service_client=service_client,
            meta={"voice_part_id": vp_id, "voice_part_name": vp["name"], "job_id": job_id},
        )

        signed_url = await generate_signed_download_url(zip_path, bucket)
        pack_urls[vp_id] = signed_url
        pack_asset_ids[vp_id] = pack_asset_id
        packs_generated.append(vp_id)

    meta_patch = {
        "pack_urls": pack_urls,
        "pack_asset_ids": pack_asset_ids,
        "packs_generated": packs_generated,
    }
    _update_job_status(job_id, "running", service_client, meta_patch=meta_patch)

    # return the first pack asset id (or None) as the primary result
    primary_asset_id = next(iter(pack_asset_ids.values()), None)
    return {
        "media_asset_id": primary_asset_id,
        "pack_urls": pack_urls,
        "pack_asset_ids": pack_asset_ids,
        "packs_generated": packs_generated,
    }


async def export_pdf(
    job_id: str,
    project_id: str,
    options: dict,
    service_client,
) -> dict:
    """Stub PDF export â returns a placeholder until a PDF engine is wired in."""
    logger.info("PDF export requested for project %s (job %s) â stub", project_id, job_id)
    bucket = "choir-director-exports"
    stub_bytes = b"%PDF-1.4 % Placeholder generated by Choir Director\n"
    storage_path = f"exports/{project_id}/score.pdf"
    _upload_bytes(stub_bytes, storage_path, bucket, "application/pdf", service_client)

    asset_id = _create_media_asset(
        project_id=project_id,
        asset_type="export_pdf",
        storage_path=storage_path,
        bucket=bucket,
        file_name="score.pdf",
        file_size=len(stub_bytes),
        mime_type="application/pdf",
        service_client=service_client,
        meta={"stub": True, "job_id": job_id},
    )
    signed_url = await generate_signed_download_url(storage_path, bucket)
    return {"media_asset_id": asset_id, "storage_path": storage_path, "signed_url": signed_url}


async def generate_signed_download_url(
    storage_path: str,
    bucket: str,
    expires_in: int = 3600,
) -> str:
    """Return a signed URL for a private bucket object using the Supabase REST API."""
    import httpx

    supabase_url = "https://cakuwqkjodopzxvyrytz.supabase.co"
    service_role_key = settings.supabase_service_role_key

    url = f"{supabase_url}/storage/v1/object/sign/{bucket}/{storage_path}"
    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }
    payload = {"expiresIn": expires_in}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=headers, json=payload)

    if resp.status_code != 200:
        logger.warning(
            "Failed to generate signed URL for %s/%s: %s %s",
            bucket,
            storage_path,
            resp.status_code,
            resp.text,
        )
        return ""

    data = resp.json()
    signed_path: str = data.get("signedURL") or data.get("signedUrl") or ""
    if signed_path.startswith("/"):
        return f"{supabase_url}/storage/v1{signed_path}"
    return signed_path


# ---------------------------------------------------------------------------
# internal MIDI builder
# ---------------------------------------------------------------------------

def _build_midi(notes: list[dict], options: dict) -> bytes:
    """
    Build a MIDI file from harmony_notes rows.

    Each row: {midi_note, start_time_sec, end_time_sec, velocity, voice_part_id}
    Voice parts are mapped to separate tracks.
    """
    tempo: int = int(options.get("tempo_bpm", 120))
    ticks_per_beat: int = int(options.get("ticks_per_beat", 480))

    if not MIDIUTIL_AVAILABLE:
        # Return a minimal valid MIDI header as a stub
        return _minimal_midi_stub()

    # group notes by voice_part_id so each part gets its own track
    tracks_map: dict[str | None, list[dict]] = {}
    for note in notes:
        vpid = note.get("voice_part_id")
        tracks_map.setdefault(vpid, []).append(note)

    num_tracks = max(len(tracks_map), 1)
    midi = MIDIFile(num_tracks, ticks_per_beat=ticks_per_beat)

    beats_per_sec = tempo / 60.0

    for track_idx, (vpid, track_notes) in enumerate(tracks_map.items()):
        midi.addTempo(track_idx, 0, tempo)
        channel = track_idx % 16

        for note in track_notes:
            pitch = int(note.get("midi_note") or 60)
            start_sec = float(note.get("start_time_sec") or 0.0)
            end_sec = float(note.get("end_time_sec") or start_sec + 0.5)
            velocity = int(note.get("velocity") or 80)

            start_beat = start_sec * beats_per_sec
            duration_beat = max((end_sec - start_sec) * beats_per_sec, 0.01)

            midi.addNote(
                track=track_idx,
                channel=channel,
                pitch=pitch,
                time=start_beat,
                duration=duration_beat,
                volume=velocity,
            )

    buf = io.BytesIO()
    midi.writeFile(buf)
    return buf.getvalue()


def _minimal_midi_stub() -> bytes:
    """Return a minimal, valid (but empty) MIDI file."""
    # MIDI header chunk: MThd + length 6 + format 1 + 1 track + 480 ticks
    header = b"MThd" + (6).to_bytes(4, "big") + (1).to_bytes(2, "big") + (1).to_bytes(2, "big") + (480).to_bytes(2, "big")
    # Track chunk: MTrk + length 4 + end-of-track meta event
    eot = b"\x00\xff\x2f\x00"  # delta=0, meta end-of-track
    track = b"MTrk" + (len(eot)).to_bytes(4, "big") + eot
    return header + track
