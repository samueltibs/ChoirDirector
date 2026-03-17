import io
import os
import uuid
import subprocess
import tempfile
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ..config import get_settings
from ..database import get_service_client
from ..auth import get_current_member

router = APIRouter(prefix="/sheet-music", tags=["sheet-music"])

ALLOWED_FILE_TYPES = {"pdf", "musicxml", "midi", "lilypond"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
SIGNED_URL_EXPIRES = 3600  # 1 hour

STORAGE_BUCKET = "choir-director-uploads"
EXPORTS_BUCKET = "choir-director-exports"


class GeneratePDFRequest(BaseModel):
    repertoire_id: str
    source_type: str  # musicxml | lilypond
    source_content: str


class SheetMusicResponse(BaseModel):
    id: str
    customer_id: str
    repertoire_id: str
    file_type: str
    storage_path: str
    voicing: Optional[str] = None
    version: Optional[str] = None
    notes: Optional[str] = None
    file_size: Optional[int] = None
    original_filename: Optional[str] = None
    created_at: str
    updated_at: str
    signed_url: Optional[str] = None


def _get_customer_id(member: dict) -> str:
    customer_id = member.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="Member has no associated customer")
    return customer_id


async def _verify_repertoire_access(supabase, repertoire_id: str, customer_id: str):
    result = (
        supabase.table("choirdir_repertoire")
        .select("id, customer_id")
        .eq("id", repertoire_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Repertoire not found or access denied",
        )
    return result.data


async def _get_signed_url(supabase, bucket: str, path: str) -> Optional[str]:
    try:
        result = supabase.storage.from_(bucket).create_signed_url(
            path, SIGNED_URL_EXPIRES
        )
        if isinstance(result, dict):
            return result.get("signedURL") or result.get("signed_url")
        return None
    except Exception:
        return None


@router.get("", response_model=List[SheetMusicResponse])
async def list_sheet_music(
    repertoire_id: Optional[str] = Query(None),
    file_type: Optional[str] = Query(None),
    member: dict = Depends(get_current_member),
):
    """List sheet music for the current customer, optionally filtered."""
    supabase = get_service_client()
    customer_id = _get_customer_id(member)

    query = (
        supabase.table("choirdir_sheet_music")
        .select("*")
        .eq("customer_id", customer_id)
    )

    if repertoire_id:
        query = query.eq("repertoire_id", repertoire_id)
    if file_type:
        if file_type not in ALLOWED_FILE_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid file_type. Allowed: {ALLOWED_FILE_TYPES}")
        query = query.eq("file_type", file_type)

    result = query.order("created_at", desc=True).execute()
    rows = result.data or []

    items = []
    for row in rows:
        items.append(
            SheetMusicResponse(
                id=row["id"],
                customer_id=row["customer_id"],
                repertoire_id=row["repertoire_id"],
                file_type=row["file_type"],
                storage_path=row["storage_path"],
                voicing=row.get("voicing"),
                version=row.get("version"),
                notes=row.get("notes"),
                file_size=row.get("file_size"),
                original_filename=row.get("original_filename"),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )
    return items


@router.get("/{sheet_id}", response_model=SheetMusicResponse)
async def get_sheet_music(
    sheet_id: str,
    member: dict = Depends(get_current_member),
):
    """Get a single sheet music record with a signed download URL."""
    supabase = get_service_client()
    customer_id = _get_customer_id(member)

    result = (
        supabase.table("choirdir_sheet_music")
        .select("*")
        .eq("id", sheet_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Sheet music not found")

    row = result.data
    bucket = row.get("bucket", STORAGE_BUCKET)
    signed_url = await _get_signed_url(supabase, bucket, row["storage_path"])

    return SheetMusicResponse(
        id=row["id"],
        customer_id=row["customer_id"],
        repertoire_id=row["repertoire_id"],
        file_type=row["file_type"],
        storage_path=row["storage_path"],
        voicing=row.get("voicing"),
        version=row.get("version"),
        notes=row.get("notes"),
        file_size=row.get("file_size"),
        original_filename=row.get("original_filename"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        signed_url=signed_url,
    )


@router.post("/upload", response_model=SheetMusicResponse, status_code=status.HTTP_201_CREATED)
async def upload_sheet_music(
    repertoire_id: str = Form(...),
    file_type: str = Form(...),
    file: UploadFile = File(...),
    voicing: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    member: dict = Depends(get_current_member),
):
    """Upload a sheet music file and create a database record."""
    if file_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file_type '{file_type}'. Allowed: {sorted(ALLOWED_FILE_TYPES)}",
        )

    supabase = get_service_client()
    customer_id = _get_customer_id(member)

    await _verify_repertoire_access(supabase, repertoire_id, customer_id)

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE // (1024*1024)} MB",
        )

    original_filename = file.filename or f"upload.{file_type}"
    ext = os.path.splitext(original_filename)[1] or f".{file_type}"
    unique_filename = f"{uuid.uuid4()}{ext}"
    storage_path = f"sheet-music/{customer_id}/{repertoire_id}/{unique_filename}"

    content_type_map = {
        "pdf": "application/pdf",
        "musicxml": "application/vnd.recordare.musicxml+xml",
        "midi": "audio/midi",
        "lilypond": "text/plain",
    }
    content_type = content_type_map.get(file_type, "application/octet-stream")

    try:
        supabase.storage.from_(STORAGE_BUCKET).upload(
            storage_path,
            content,
            {"content-type": content_type},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {exc}")

    sheet_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    insert_data = {
        "id": sheet_id,
        "customer_id": customer_id,
        "repertoire_id": repertoire_id,
        "file_type": file_type,
        "storage_path": storage_path,
        "bucket": STORAGE_BUCKET,
        "original_filename": original_filename,
        "file_size": len(content),
        "voicing": voicing,
        "version": version,
        "notes": notes,
        "created_at": now,
        "updated_at": now,
    }

    try:
        db_result = (
            supabase.table("choirdir_sheet_music")
            .insert(insert_data)
            .execute()
        )
    except Exception as exc:
        # Attempt cleanup of uploaded file
        try:
            supabase.storage.from_(STORAGE_BUCKET).remove([storage_path])
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Database insert failed: {exc}")

    row = db_result.data[0] if db_result.data else insert_data
    signed_url = await _get_signed_url(supabase, STORAGE_BUCKET, storage_path)

    return SheetMusicResponse(
        id=row["id"],
        customer_id=row["customer_id"],
        repertoire_id=row["repertoire_id"],
        file_type=row["file_type"],
        storage_path=row["storage_path"],
        voicing=row.get("voicing"),
        version=row.get("version"),
        notes=row.get("notes"),
        file_size=row.get("file_size"),
        original_filename=row.get("original_filename"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        signed_url=signed_url,
    )


@router.post("/generate-pdf", response_model=SheetMusicResponse, status_code=status.HTTP_201_CREATED)
async def generate_pdf(
    body: GeneratePDFRequest,
    member: dict = Depends(get_current_member),
):
    """Generate a PDF from MusicXML or LilyPond source content."""
    if body.source_type not in ("musicxml", "lilypond"):
        raise HTTPException(
            status_code=400,
            detail="source_type must be 'musicxml' or 'lilypond'",
        )

    supabase = get_service_client()
    customer_id = _get_customer_id(member)

    await _verify_repertoire_access(supabase, body.repertoire_id, customer_id)

    pdf_bytes: Optional[bytes] = None
    generation_error: Optional[str] = None

    with tempfile.TemporaryDirectory() as tmpdir:
        if body.source_type == "lilypond":
            src_path = os.path.join(tmpdir, "score.ly")
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(body.source_content)

            try:
                proc = subprocess.run(
                    ["lilypond", "-o", tmpdir, src_path],
                    capture_output=True,
                    timeout=60,
                )
                pdf_path = os.path.join(tmpdir, "score.pdf")
                if proc.returncode == 0 and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as pf:
                        pdf_bytes = pf.read()
                else:
                    generation_error = proc.stderr.decode(errors="replace")[:500]
            except FileNotFoundError:
                generation_error = "LilyPond is not installed on this server"
            except subprocess.TimeoutExpired:
                generation_error = "LilyPond generation timed out"

        elif body.source_type == "musicxml":
            src_path = os.path.join(tmpdir, "score.musicxml")
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(body.source_content)

            # Try MuseScore first, then mscore
            for cmd in ["mscore", "musescore", "MuseScore3"]:
                try:
                    pdf_path = os.path.join(tmpdir, "score.pdf")
                    proc = subprocess.run(
                        [cmd, "-o", pdf_path, src_path],
                        capture_output=True,
                        timeout=120,
                    )
                    if proc.returncode == 0 and os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as pf:
                            pdf_bytes = pf.read()
                        generation_error = None
                        break
                    else:
                        generation_error = proc.stderr.decode(errors="replace")[:500]
                except FileNotFoundError:
                    generation_error = f"{cmd} is not installed on this server"
                except subprocess.TimeoutExpired:
                    generation_error = "MusicXML to PDF conversion timed out"
                    break

    if pdf_bytes is None:
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {generation_error or 'Unknown error'}",
        )

    unique_name = f"{uuid.uuid4()}.pdf"
    storage_path = f"generated-pdfs/{customer_id}/{body.repertoire_id}/{unique_name}"

    try:
        supabase.storage.from_(EXPORTS_BUCKET).upload(
            storage_path,
            pdf_bytes,
            {"content-type": "application/pdf"},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {exc}")

    sheet_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    insert_data = {
        "id": sheet_id,
        "customer_id": customer_id,
        "repertoire_id": body.repertoire_id,
        "file_type": "pdf",
        "storage_path": storage_path,
        "bucket": EXPORTS_BUCKET,
        "original_filename": unique_name,
        "file_size": len(pdf_bytes),
        "notes": f"Generated from {body.source_type} source",
        "created_at": now,
        "updated_at": now,
    }

    try:
        db_result = (
            supabase.table("choirdir_sheet_music")
            .insert(insert_data)
            .execute()
        )
    except Exception as exc:
        try:
            supabase.storage.from_(EXPORTS_BUCKET).remove([storage_path])
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Database insert failed: {exc}")

    row = db_result.data[0] if db_result.data else insert_data
    signed_url = await _get_signed_url(supabase, EXPORTS_BUCKET, storage_path)

    return SheetMusicResponse(
        id=row["id"],
        customer_id=row["customer_id"],
        repertoire_id=row["repertoire_id"],
        file_type=row["file_type"],
        storage_path=row["storage_path"],
        voicing=row.get("voicing"),
        version=row.get("version"),
        notes=row.get("notes"),
        file_size=row.get("file_size"),
        original_filename=row.get("original_filename"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        signed_url=signed_url,
    )


@router.delete("/{sheet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sheet_music(
    sheet_id: str,
    member: dict = Depends(get_current_member),
):
    """Delete sheet music record and its associated storage file."""
    supabase = get_service_client()
    customer_id = _get_customer_id(member)

    result = (
        supabase.table("choirdir_sheet_music")
        .select("*")
        .eq("id", sheet_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Sheet music not found")

    row = result.data
    bucket = row.get("bucket", STORAGE_BUCKET)
    storage_path = row["storage_path"]

    # Delete from storage
    try:
        supabase.storage.from_(bucket).remove([storage_path])
    except Exception:
        # Log but don't fail if storage delete errors
        pass

    # Delete from database
    supabase.table("choirdir_sheet_music").delete().eq("id", sheet_id).execute()

    return None


@router.get("/{sheet_id}/download")
async def download_sheet_music(
    sheet_id: str,
    member: dict = Depends(get_current_member),
):
    """Redirect to a signed download URL for the sheet music file."""
    supabase = get_service_client()
    customer_id = _get_customer_id(member)

    result = (
        supabase.table("choirdir_sheet_music")
        .select("*")
        .eq("id", sheet_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Sheet music not found")

    row = result.data
    bucket = row.get("bucket", STORAGE_BUCKET)
    signed_url = await _get_signed_url(supabase, bucket, row["storage_path"])

    if not signed_url:
        raise HTTPException(status_code=500, detail="Could not generate download URL")

    return RedirectResponse(url=signed_url, status_code=302)
