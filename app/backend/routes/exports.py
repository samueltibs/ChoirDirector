from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
import uuid

from ..config import get_settings
from ..database import get_service_client
from ..auth import get_current_member
from ..services import export_service

router = APIRouter(prefix="/exports", tags=["exports"])
settings = get_settings()


class ExportOptions(BaseModel):
    voice_parts: Optional[list[str]] = None
    include_click: Optional[bool] = None
    include_cues: Optional[bool] = None
    tempo: Optional[float] = None
    is_watermarked: Optional[bool] = None


class GenerateExportRequest(BaseModel):
    project_id: str
    type: str  # midi | pdf | guide_audio
    options: Optional[ExportOptions] = None


JOB_TYPE_MAP = {
    "midi": "export_midi",
    "pdf": "export_pdf",
    "guide_audio": "export_guide_audio",
}


def _assert_project_access(supabase, project_id: str, member_id: str):
    """Verify the member belongs to the choir that owns the project."""
    proj = (
        supabase.table("choirdir_projects")
        .select("id, choir_id")
        .eq("id", project_id)
        .single()
        .execute()
    )
    if not proj.data:
        raise HTTPException(status_code=404, detail="Project not found")

    choir_id = proj.data["choir_id"]
    membership = (
        supabase.table("choirdir_choir_members")
        .select("id")
        .eq("choir_id", choir_id)
        .eq("member_id", member_id)
        .single()
        .execute()
    )
    if not membership.data:
        raise HTTPException(status_code=403, detail="Access denied to this project")
    return proj.data


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_export(
    body: GenerateExportRequest,
    current_member: dict = Depends(get_current_member),
):
    """Create an export job and dispatch it to the export service."""
    if body.type not in JOB_TYPE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid export type '{body.type}'. Must be one of: {list(JOB_TYPE_MAP.keys())}",
        )

    supabase = get_service_client()
    member_id = current_member["id"]

    _assert_project_access(supabase, body.project_id, member_id)

    job_id = str(uuid.uuid4())
    job_type = JOB_TYPE_MAP[body.type]
    options_dict = body.options.model_dump(exclude_none=True) if body.options else {}

    insert_payload = {
        "id": job_id,
        "project_id": body.project_id,
        "requested_by": member_id,
        "job_type": job_type,
        "status": "queued",
        "options": options_dict,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    result = supabase.table("choirdir_export_jobs").insert(insert_payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create export job")

    job = result.data[0]

    # Dispatch async processing without blocking
    import asyncio
    asyncio.create_task(
        export_service.process_export_job(
            job_id=job_id,
            project_id=body.project_id,
            job_type=job_type,
            options=options_dict,
            requested_by=member_id,
        )
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "job_type": job_type,
        "project_id": body.project_id,
        "created_at": job.get("created_at"),
    }


@router.get("/jobs")
async def list_export_jobs(
    project_id: Optional[str] = None,
    current_member: dict = Depends(get_current_member),
):
    """List export jobs for the current user's projects."""
    supabase = get_service_client()
    member_id = current_member["id"]

    # Find all choir_ids this member belongs to
    memberships = (
        supabase.table("choirdir_choir_members")
        .select("choir_id")
        .eq("member_id", member_id)
        .execute()
    )
    choir_ids = [m["choir_id"] for m in (memberships.data or [])]

    if not choir_ids:
        return {"jobs": []}

    # Find all project IDs belonging to those choirs
    projects_query = (
        supabase.table("choirdir_projects")
        .select("id")
        .in_("choir_id", choir_ids)
    )
    if project_id:
        projects_query = projects_query.eq("id", project_id)

    projects_result = projects_query.execute()
    project_ids = [p["id"] for p in (projects_result.data or [])]

    if not project_ids:
        return {"jobs": []}

    jobs_result = (
        supabase.table("choirdir_export_jobs")
        .select("*")
        .in_("project_id", project_ids)
        .order("created_at", desc=True)
        .execute()
    )

    return {"jobs": jobs_result.data or []}


@router.get("/jobs/{job_id}")
async def get_export_job(
    job_id: str,
    current_member: dict = Depends(get_current_member),
):
    """Get job status and result URLs for a specific export job."""
    supabase = get_service_client()
    member_id = current_member["id"]

    job_result = (
        supabase.table("choirdir_export_jobs")
        .select("*")
        .eq("id", job_id)
        .single()
        .execute()
    )
    if not job_result.data:
        raise HTTPException(status_code=404, detail="Export job not found")

    job = job_result.data
    _assert_project_access(supabase, job["project_id"], member_id)

    # Attach signed download URL if the job is complete and has a storage path
    download_url = None
    if job.get("status") == "completed" and job.get("output_path"):
        try:
            signed = supabase.storage.from_("choir-director-exports").create_signed_url(
                job["output_path"], expires_in=3600
            )
            download_url = signed.get("signedURL") or signed.get("signed_url")
        except Exception:
            download_url = None

    return {**job, "download_url": download_url}


@router.get("/jobs/{job_id}/download")
async def download_export(
    job_id: str,
    current_member: dict = Depends(get_current_member),
):
    """Redirect to a signed download URL for the completed export."""
    supabase = get_service_client()
    member_id = current_member["id"]

    job_result = (
        supabase.table("choirdir_export_jobs")
        .select("*")
        .eq("id", job_id)
        .single()
        .execute()
    )
    if not job_result.data:
        raise HTTPException(status_code=404, detail="Export job not found")

    job = job_result.data
    _assert_project_access(supabase, job["project_id"], member_id)

    if job.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Export job is not completed (current status: {job.get('status')})",
        )

    output_path = job.get("output_path")
    if not output_path:
        raise HTTPException(status_code=404, detail="No output file available for this job")

    try:
        signed = supabase.storage.from_("choir-director-exports").create_signed_url(
            output_path, expires_in=3600
        )
        signed_url = signed.get("signedURL") or signed.get("signed_url")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {exc}")

    if not signed_url:
        raise HTTPException(status_code=500, detail="Could not obtain signed download URL")

    return RedirectResponse(url=signed_url, status_code=302)


@router.get("/pack/{project_id}")
async def get_project_packs(
    project_id: str,
    current_member: dict = Depends(get_current_member),
):
    """Get all available export packs (media_assets) for a project."""
    supabase = get_service_client()
    member_id = current_member["id"]

    _assert_project_access(supabase, project_id, member_id)

    assets_result = (
        supabase.table("choirdir_media_assets")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )

    assets = assets_result.data or []

    # Generate signed URLs for private assets
    enriched = []
    for asset in assets:
        storage_path = asset.get("storage_path")
        signed_url = None
        if storage_path:
            bucket = asset.get("bucket", "choir-director-exports")
            try:
                signed = supabase.storage.from_(bucket).create_signed_url(
                    storage_path, expires_in=3600
                )
                signed_url = signed.get("signedURL") or signed.get("signed_url")
            except Exception:
                signed_url = None
        enriched.append({**asset, "signed_url": signed_url})

    # Group by asset_type for convenience
    packs: dict[str, list] = {}
    for asset in enriched:
        asset_type = asset.get("asset_type", "other")
        packs.setdefault(asset_type, []).append(asset)

    return {
        "project_id": project_id,
        "packs": packs,
        "total": len(enriched),
    }


@router.delete("/jobs/{job_id}", status_code=status.HTTP_200_OK)
async def delete_export_job(
    job_id: str,
    current_member: dict = Depends(get_current_member),
):
    """Cancel or delete an export job."""
    supabase = get_service_client()
    member_id = current_member["id"]

    job_result = (
        supabase.table("choirdir_export_jobs")
        .select("*")
        .eq("id", job_id)
        .single()
        .execute()
    )
    if not job_result.data:
        raise HTTPException(status_code=404, detail="Export job not found")

    job = job_result.data
    _assert_project_access(supabase, job["project_id"], member_id)

    # If queued or processing, attempt to cancel via service
    if job.get("status") in ("queued", "processing"):
        try:
            await export_service.cancel_export_job(job_id)
        except Exception:
            pass  # Best-effort cancellation

        # Mark as cancelled in DB
        supabase.table("choirdir_export_jobs").update(
            {"status": "cancelled", "updated_at": datetime.utcnow().isoformat()}
        ).eq("id", job_id).execute()

        return {"job_id": job_id, "status": "cancelled", "message": "Export job cancelled"}

    # For completed/failed/cancelled jobs, hard-delete the record
    # Optionally remove file from storage
    output_path = job.get("output_path")
    if output_path:
        try:
            supabase.storage.from_("choir-director-exports").remove([output_path])
        except Exception:
            pass  # Non-fatal

    supabase.table("choirdir_export_jobs").delete().eq("id", job_id).execute()

    return {"job_id": job_id, "status": "deleted", "message": "Export job deleted"}
