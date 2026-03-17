from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from typing import Optional, List
import uuid
import logging
from datetime import datetime

from ..config import get_settings
from ..database import get_service_client
from ..auth import get_current_member
from ..services import kits_ai

router = APIRouter(prefix="/rehearsal-tracks", tags=["rehearsal-tracks"])
logger = logging.getLogger(__name__)

SIGNED_URL_EXPIRY = 3600  # 1 hour
STORAGE_BUCKET = "choir-director-uploads"


@router.get("")
async def list_rehearsal_tracks(
    repertoire_id: Optional[str] = Query(None),
    voice_part: Optional[str] = Query(None),
    current_member: dict = Depends(get_current_member),
):
    """List rehearsal tracks for the current member's customer."""
    try:
        supabase = get_service_client()
        customer_id = current_member["customer_id"]

        query = supabase.table("choirdir_rehearsal_tracks").select(
            "*, media_assets(*)"
        ).eq("customer_id", customer_id)

        if repertoire_id:
            query = query.eq("repertoire_id", repertoire_id)
        if voice_part:
            query = query.eq("voice_part", voice_part)

        result = query.order("created_at", desc=True).execute()

        tracks = result.data or []
        return {"tracks": tracks, "total": len(tracks)}

    except Exception as e:
        logger.error(f"Error listing rehearsal tracks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signed-url/{track_id}")
async def get_signed_url(
    track_id: str,
    current_member: dict = Depends(get_current_member),
):
    """Get a fresh signed URL for a private audio file."""
    try:
        supabase = get_service_client()
        customer_id = current_member["customer_id"]

        track_result = supabase.table("choirdir_rehearsal_tracks").select(
            "*, media_assets(*)"
        ).eq("id", track_id).eq("customer_id", customer_id).single().execute()

        if not track_result.data:
            raise HTTPException(status_code=404, detail="Track not found")

        track = track_result.data
        storage_path = track.get("storage_path")

        if not storage_path:
            media_asset = track.get("media_assets")
            if media_asset and isinstance(media_asset, dict):
                storage_path = media_asset.get("storage_path")

        if not storage_path:
            raise HTTPException(status_code=404, detail="No storage path found for track")

        signed = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(
            storage_path, SIGNED_URL_EXPIRY
        )

        if not signed or "signedURL" not in signed:
            signed_url = signed.get("signedUrl") if signed else None
        else:
            signed_url = signed.get("signedURL")

        if not signed_url:
            raise HTTPException(status_code=500, detail="Failed to generate signed URL")

        return {
            "track_id": track_id,
            "signed_url": signed_url,
            "expires_in": SIGNED_URL_EXPIRY,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating signed URL for track {track_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{track_id}")
async def get_rehearsal_track(
    track_id: str,
    current_member: dict = Depends(get_current_member),
):
    """Get a single rehearsal track with a signed URL for the audio."""
    try:
        supabase = get_service_client()
        customer_id = current_member["customer_id"]

        track_result = supabase.table("choirdir_rehearsal_tracks").select(
            "*, media_assets(*)"
        ).eq("id", track_id).eq("customer_id", customer_id).single().execute()

        if not track_result.data:
            raise HTTPException(status_code=404, detail="Track not found")

        track = track_result.data
        storage_path = track.get("storage_path")

        if not storage_path:
            media_asset = track.get("media_assets")
            if media_asset and isinstance(media_asset, dict):
                storage_path = media_asset.get("storage_path")

        signed_url = None
        if storage_path:
            try:
                signed = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(
                    storage_path, SIGNED_URL_EXPIRY
                )
                signed_url = signed.get("signedURL") or signed.get("signedUrl")
            except Exception as sign_err:
                logger.warning(f"Could not generate signed URL: {sign_err}")

        return {"track": track, "signed_url": signed_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching rehearsal track {track_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_rehearsal_track(
    repertoire_id: str = Form(...),
    voice_part: str = Form(...),
    track_type: str = Form(...),
    audio_file: UploadFile = File(...),
    current_member: dict = Depends(get_current_member),
):
    """Upload an audio file for a rehearsal track."""
    valid_track_types = {"full", "isolated", "click", "cue"}
    if track_type not in valid_track_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid track_type. Must be one of: {', '.join(valid_track_types)}",
        )

    allowed_content_types = {
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
        "audio/ogg", "audio/aac", "audio/flac", "audio/m4a",
        "audio/x-m4a", "application/octet-stream",
    }
    if audio_file.content_type and audio_file.content_type not in allowed_content_types:
        logger.warning(f"Potentially unsupported content type: {audio_file.content_type}")

    try:
        supabase = get_service_client()
        customer_id = current_member["customer_id"]
        member_id = current_member["id"]

        # Verify repertoire belongs to customer
        repertoire_result = supabase.table("choirdir_repertoire").select("id").eq(
            "id", repertoire_id
        ).eq("customer_id", customer_id).single().execute()

        if not repertoire_result.data:
            raise HTTPException(status_code=404, detail="Repertoire not found")

        file_content = await audio_file.read()
        if not file_content:
            raise HTTPException(status_code=400, detail="Empty audio file")

        safe_voice_part = voice_part.replace(" ", "_").replace("/", "-")
        storage_path = f"tracks/{customer_id}/{repertoire_id}/{safe_voice_part}_{track_type}.mp3"

        content_type = audio_file.content_type or "audio/mpeg"

        try:
            upload_response = supabase.storage.from_(STORAGE_BUCKET).upload(
                storage_path,
                file_content,
                file_options={"content-type": content_type, "upsert": "true"},
            )
        except Exception as upload_err:
            logger.error(f"Storage upload error: {upload_err}")
            raise HTTPException(status_code=500, detail=f"Failed to upload audio file: {upload_err}")

        track_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        media_asset_data = {
            "id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "storage_path": storage_path,
            "bucket": STORAGE_BUCKET,
            "file_name": audio_file.filename or f"{safe_voice_part}_{track_type}.mp3",
            "content_type": content_type,
            "file_size": len(file_content),
            "created_at": now,
            "updated_at": now,
        }

        media_result = supabase.table("media_assets").insert(media_asset_data).execute()
        media_asset_id = None
        if media_result.data:
            media_asset_id = media_result.data[0]["id"]

        track_data = {
            "id": track_id,
            "customer_id": customer_id,
            "repertoire_id": repertoire_id,
            "voice_part": voice_part,
            "track_type": track_type,
            "storage_path": storage_path,
            "media_asset_id": media_asset_id,
            "source": "upload",
            "status": "ready",
            "uploaded_by": member_id,
            "file_name": audio_file.filename,
            "file_size": len(file_content),
            "created_at": now,
            "updated_at": now,
        }

        track_result = supabase.table("choirdir_rehearsal_tracks").insert(track_data).execute()

        if not track_result.data:
            raise HTTPException(status_code=500, detail="Failed to create track record")

        created_track = track_result.data[0]

        # Generate signed URL for immediate use
        signed_url = None
        try:
            signed = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(
                storage_path, SIGNED_URL_EXPIRY
            )
            signed_url = signed.get("signedURL") or signed.get("signedUrl")
        except Exception as sign_err:
            logger.warning(f"Could not generate signed URL after upload: {sign_err}")

        return {
            "track": created_track,
            "signed_url": signed_url,
            "message": "Track uploaded successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading rehearsal track: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_rehearsal_track(
    body: dict,
    current_member: dict = Depends(get_current_member),
):
    """Trigger Kits AI voice generation for a rehearsal track."""
    repertoire_id = body.get("repertoire_id")
    voice_part = body.get("voice_part")
    voice_model_id = body.get("voice_model_id")
    source_audio_url = body.get("source_audio_url")

    if not repertoire_id:
        raise HTTPException(status_code=400, detail="repertoire_id is required")
    if not voice_part:
        raise HTTPException(status_code=400, detail="voice_part is required")
    if not voice_model_id:
        raise HTTPException(status_code=400, detail="voice_model_id is required")

    try:
        supabase = get_service_client()
        customer_id = current_member["customer_id"]
        member_id = current_member["id"]

        repertoire_result = supabase.table("choirdir_repertoire").select("id, title").eq(
            "id", repertoire_id
        ).eq("customer_id", customer_id).single().execute()

        if not repertoire_result.data:
            raise HTTPException(status_code=404, detail="Repertoire not found")

        track_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        track_data = {
            "id": track_id,
            "customer_id": customer_id,
            "repertoire_id": repertoire_id,
            "voice_part": voice_part,
            "track_type": "isolated",
            "source": "kits_ai",
            "status": "generating",
            "voice_model_id": voice_model_id,
            "source_audio_url": source_audio_url,
            "uploaded_by": member_id,
            "created_at": now,
            "updated_at": now,
        }

        track_result = supabase.table("choirdir_rehearsal_tracks").insert(track_data).execute()

        if not track_result.data:
            raise HTTPException(status_code=500, detail="Failed to create track record")

        created_track = track_result.data[0]

        generation_result = None
        generation_error = None

        try:
            generation_result = await kits_ai.generate_voice_track(
                voice_model_id=voice_model_id,
                source_audio_url=source_audio_url,
                repertoire_id=repertoire_id,
                voice_part=voice_part,
                customer_id=customer_id,
                track_id=track_id,
            )

            update_data = {
                "status": "processing",
                "generation_job_id": generation_result.get("job_id") or generation_result.get("id"),
                "updated_at": datetime.utcnow().isoformat(),
            }
            supabase.table("choirdir_rehearsal_tracks").update(update_data).eq("id", track_id).execute()

        except Exception as gen_err:
            generation_error = str(gen_err)
            logger.error(f"Kits AI generation error for track {track_id}: {gen_err}")
            supabase.table("choirdir_rehearsal_tracks").update({
                "status": "failed",
                "error_message": generation_error,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", track_id).execute()

        return {
            "track": created_track,
            "generation_result": generation_result,
            "status": "processing" if generation_result else "failed",
            "error": generation_error,
            "message": "Voice generation triggered" if generation_result else "Voice generation failed",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering voice generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{track_id}")
async def delete_rehearsal_track(
    track_id: str,
    current_member: dict = Depends(get_current_member),
):
    """Delete a rehearsal track and its associated storage file."""
    try:
        supabase = get_service_client()
        customer_id = current_member["customer_id"]

        track_result = supabase.table("choirdir_rehearsal_tracks").select(
            "*, media_assets(*)"
        ).eq("id", track_id).eq("customer_id", customer_id).single().execute()

        if not track_result.data:
            raise HTTPException(status_code=404, detail="Track not found")

        track = track_result.data
        storage_path = track.get("storage_path")

        if not storage_path:
            media_asset = track.get("media_assets")
            if media_asset and isinstance(media_asset, dict):
                storage_path = media_asset.get("storage_path")

        # Delete from storage if we have a path
        storage_deleted = False
        if storage_path:
            try:
                supabase.storage.from_(STORAGE_BUCKET).remove([storage_path])
                storage_deleted = True
                logger.info(f"Deleted storage file: {storage_path}")
            except Exception as storage_err:
                logger.warning(f"Could not delete storage file {storage_path}: {storage_err}")

        # Delete media asset record if exists
        media_asset = track.get("media_assets")
        if media_asset and isinstance(media_asset, dict):
            media_asset_id = media_asset.get("id")
            if media_asset_id:
                try:
                    supabase.table("media_assets").delete().eq("id", media_asset_id).execute()
                except Exception as ma_err:
                    logger.warning(f"Could not delete media asset {media_asset_id}: {ma_err}")

        # Delete the track record
        supabase.table("choirdir_rehearsal_tracks").delete().eq("id", track_id).execute()

        return {
            "message": "Track deleted successfully",
            "track_id": track_id,
            "storage_deleted": storage_deleted,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting rehearsal track {track_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
