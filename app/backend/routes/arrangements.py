from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import uuid

from ..config import get_settings
from ..database import get_service_client
from ..auth import get_current_member
from ..services import arrangement_service

router = APIRouter(prefix="/arrangements", tags=["arrangements"])
settings = get_settings()


class ArrangementRequestBody(BaseModel):
    source_type: str  # upload | lyrics | title
    target_voicing: str
    style: str
    key_signature: Optional[str] = None
    tempo_bpm: Optional[int] = None
    difficulty_level: Optional[str] = None
    special_instructions: Optional[str] = None
    source_content: Optional[str] = None
    repertoire_id: Optional[str] = None


@router.post("/request", status_code=status.HTTP_201_CREATED)
async def create_arrangement_request(
    body: ArrangementRequestBody,
    background_tasks: BackgroundTasks,
    current_member: dict = Depends(get_current_member),
):
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")
    member_id = current_member.get("id")

    if body.source_type not in ("upload", "lyrics", "title"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_type must be one of: upload, lyrics, title",
        )

    request_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    insert_data = {
        "id": request_id,
        "customer_id": customer_id,
        "requested_by": member_id,
        "source_type": body.source_type,
        "target_voicing": body.target_voicing,
        "style": body.style,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }

    if body.key_signature is not None:
        insert_data["key_signature"] = body.key_signature
    if body.tempo_bpm is not None:
        insert_data["tempo_bpm"] = body.tempo_bpm
    if body.difficulty_level is not None:
        insert_data["difficulty_level"] = body.difficulty_level
    if body.special_instructions is not None:
        insert_data["special_instructions"] = body.special_instructions
    if body.source_content is not None:
        insert_data["source_content"] = body.source_content
    if body.repertoire_id is not None:
        insert_data["repertoire_id"] = body.repertoire_id

    result = supabase.table("choirdir_arrangement_requests").insert(insert_data).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create arrangement request",
        )

    created_request = result.data[0]

    # Log to BISA log
    try:
        supabase.table("choirdir_bisa_log").insert({
            "id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "member_id": member_id,
            "action": "arrangement_request_created",
            "entity_type": "arrangement_request",
            "entity_id": request_id,
            "metadata": {
                "source_type": body.source_type,
                "target_voicing": body.target_voicing,
                "style": body.style,
            },
            "created_at": now,
        }).execute()
    except Exception:
        pass

    background_tasks.add_task(
        arrangement_service.process_arrangement_request,
        request_id=request_id,
        customer_id=customer_id,
        request_data=body.dict(),
    )

    return {
        "message": "Arrangement request created and queued for processing",
        "request_id": request_id,
        "status": "pending",
        "data": created_request,
    }


@router.get("")
async def list_arrangement_requests(
    current_member: dict = Depends(get_current_member),
):
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")

    result = (
        supabase.table("choirdir_arrangement_requests")
        .select("*")
        .eq("customer_id", customer_id)
        .order("created_at", desc=True)
        .execute()
    )

    return {
        "data": result.data or [],
        "count": len(result.data) if result.data else 0,
    }


@router.get("/{request_id}")
async def get_arrangement_request(
    request_id: str,
    current_member: dict = Depends(get_current_member),
):
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")

    result = (
        supabase.table("choirdir_arrangement_requests")
        .select("*")
        .eq("id", request_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arrangement request not found",
        )

    return {"data": result.data}


@router.delete("/{request_id}", status_code=status.HTTP_200_OK)
async def delete_arrangement_request(
    request_id: str,
    current_member: dict = Depends(get_current_member),
):
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")
    member_id = current_member.get("id")

    existing = (
        supabase.table("choirdir_arrangement_requests")
        .select("id, status")
        .eq("id", request_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arrangement request not found",
        )

    current_status = existing.data.get("status")
    if current_status == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete an arrangement request that is currently being processed",
        )

    delete_result = (
        supabase.table("choirdir_arrangement_requests")
        .delete()
        .eq("id", request_id)
        .eq("customer_id", customer_id)
        .execute()
    )

    # Log cancellation/deletion
    try:
        now = datetime.utcnow().isoformat()
        supabase.table("choirdir_bisa_log").insert({
            "id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "member_id": member_id,
            "action": "arrangement_request_deleted",
            "entity_type": "arrangement_request",
            "entity_id": request_id,
            "metadata": {
                "previous_status": current_status,
            },
            "created_at": now,
        }).execute()
    except Exception:
        pass

    return {
        "message": "Arrangement request deleted successfully",
        "request_id": request_id,
    }
