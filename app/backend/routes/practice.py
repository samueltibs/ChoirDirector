from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from ..config import get_settings
from ..database import get_service_client
from ..auth import get_current_member

router = APIRouter(prefix="/practice", tags=["practice"])
settings = get_settings()


class CreateAssignmentRequest(BaseModel):
    repertoire_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    target_type: str  # all | voice_part | individual
    target_voice_part: Optional[str] = None
    target_member_ids: Optional[List[str]] = None
    due_date: Optional[datetime] = None
    focus_areas: Optional[List[str]] = None


class UpdateAssignmentRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_type: Optional[str] = None
    target_voice_part: Optional[str] = None
    target_member_ids: Optional[List[str]] = None
    due_date: Optional[datetime] = None
    focus_areas: Optional[List[str]] = None
    is_active: Optional[bool] = None


class LogProgressRequest(BaseModel):
    assignment_id: str
    practice_minutes: int
    sessions_count: Optional[int] = 1
    self_rating: Optional[int] = None
    confidence_level: Optional[int] = None
    notes: Optional[str] = None


class UpdateProgressRequest(BaseModel):
    practice_minutes: Optional[int] = None
    sessions_count: Optional[int] = None
    self_rating: Optional[int] = None
    confidence_level: Optional[int] = None
    notes: Optional[str] = None


@router.get("/assignments")
async def list_assignments(current_member: dict = Depends(get_current_member)):
    client = get_service_client()
    customer_id = current_member["customer_id"]
    member_id = current_member["id"]
    role = current_member.get("role", "member")

    query = client.table("choirdir_practice_assignments").select("*").eq("customer_id", customer_id)

    if role not in ("director", "admin", "owner"):
        voice_part = current_member.get("voice_part")
        filters = f"target_type.eq.all"
        response = (
            client.table("choirdir_practice_assignments")
            .select("*")
            .eq("customer_id", customer_id)
            .eq("is_active", True)
            .execute()
        )
        assignments = response.data or []
        filtered = []
        for a in assignments:
            if a["target_type"] == "all":
                filtered.append(a)
            elif a["target_type"] == "voice_part" and a.get("target_voice_part") == voice_part:
                filtered.append(a)
            elif a["target_type"] == "individual" and member_id in (a.get("target_member_ids") or []):
                filtered.append(a)
        return {"assignments": filtered}
    else:
        response = query.order("created_at", desc=True).execute()
        return {"assignments": response.data or []}


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
async def create_assignment(
    body: CreateAssignmentRequest,
    current_member: dict = Depends(get_current_member),
):
    role = current_member.get("role", "member")
    if role not in ("director", "admin", "owner"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only directors can create assignments")

    if body.target_type not in ("all", "voice_part", "individual"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target_type must be all, voice_part, or individual")

    if body.target_type == "voice_part" and not body.target_voice_part:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target_voice_part required when target_type is voice_part")

    if body.target_type == "individual" and not body.target_member_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target_member_ids required when target_type is individual")

    client = get_service_client()
    now = datetime.utcnow().isoformat()

    payload = {
        "customer_id": current_member["customer_id"],
        "created_by": current_member["id"],
        "title": body.title,
        "target_type": body.target_type,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }

    if body.repertoire_id:
        payload["repertoire_id"] = body.repertoire_id
    if body.description:
        payload["description"] = body.description
    if body.target_voice_part:
        payload["target_voice_part"] = body.target_voice_part
    if body.target_member_ids:
        payload["target_member_ids"] = body.target_member_ids
    if body.due_date:
        payload["due_date"] = body.due_date.isoformat()
    if body.focus_areas:
        payload["focus_areas"] = body.focus_areas

    response = client.table("choirdir_practice_assignments").insert(payload).execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create assignment")

    return {"assignment": response.data[0]}


@router.get("/assignments/{assignment_id}")
async def get_assignment(
    assignment_id: str,
    current_member: dict = Depends(get_current_member),
):
    client = get_service_client()
    customer_id = current_member["customer_id"]

    response = (
        client.table("choirdir_practice_assignments")
        .select("*")
        .eq("id", assignment_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    assignment = response.data

    progress_response = (
        client.table("choirdir_practice_progress")
        .select("*, choirdir_members(id, first_name, last_name, voice_part)")
        .eq("assignment_id", assignment_id)
        .execute()
    )
    assignment["progress"] = progress_response.data or []

    total_members = 0
    members_started = len(set(p["member_id"] for p in assignment["progress"]))
    total_minutes = sum(p.get("practice_minutes", 0) for p in assignment["progress"])
    assignment["stats"] = {
        "members_started": members_started,
        "total_minutes_logged": total_minutes,
    }

    return {"assignment": assignment}


@router.put("/assignments/{assignment_id}")
async def update_assignment(
    assignment_id: str,
    body: UpdateAssignmentRequest,
    current_member: dict = Depends(get_current_member),
):
    role = current_member.get("role", "member")
    if role not in ("director", "admin", "owner"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only directors can update assignments")

    client = get_service_client()
    customer_id = current_member["customer_id"]

    existing = (
        client.table("choirdir_practice_assignments")
        .select("id")
        .eq("id", assignment_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    updates = {"updated_at": datetime.utcnow().isoformat()}
    if body.title is not None:
        updates["title"] = body.title
    if body.description is not None:
        updates["description"] = body.description
    if body.target_type is not None:
        if body.target_type not in ("all", "voice_part", "individual"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target_type")
        updates["target_type"] = body.target_type
    if body.target_voice_part is not None:
        updates["target_voice_part"] = body.target_voice_part
    if body.target_member_ids is not None:
        updates["target_member_ids"] = body.target_member_ids
    if body.due_date is not None:
        updates["due_date"] = body.due_date.isoformat()
    if body.focus_areas is not None:
        updates["focus_areas"] = body.focus_areas
    if body.is_active is not None:
        updates["is_active"] = body.is_active

    response = (
        client.table("choirdir_practice_assignments")
        .update(updates)
        .eq("id", assignment_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update assignment")

    return {"assignment": response.data[0]}


@router.get("/progress")
async def get_progress(current_member: dict = Depends(get_current_member)):
    client = get_service_client()
    customer_id = current_member["customer_id"]
    member_id = current_member["id"]
    role = current_member.get("role", "member")

    if role in ("director", "admin", "owner"):
        response = (
            client.table("choirdir_practice_progress")
            .select("*, choirdir_members(id, first_name, last_name, voice_part), choirdir_practice_assignments(id, title)")
            .eq("customer_id", customer_id)
            .order("created_at", desc=True)
            .execute()
        )
    else:
        response = (
            client.table("choirdir_practice_progress")
            .select("*, choirdir_practice_assignments(id, title)")
            .eq("member_id", member_id)
            .eq("customer_id", customer_id)
            .order("created_at", desc=True)
            .execute()
        )

    return {"progress": response.data or []}


@router.post("/progress", status_code=status.HTTP_201_CREATED)
async def log_progress(
    body: LogProgressRequest,
    current_member: dict = Depends(get_current_member),
):
    client = get_service_client()
    customer_id = current_member["customer_id"]
    member_id = current_member["id"]

    assignment_response = (
        client.table("choirdir_practice_assignments")
        .select("id, target_type, target_voice_part, target_member_ids, is_active")
        .eq("id", body.assignment_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not assignment_response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    assignment = assignment_response.data
    role = current_member.get("role", "member")

    if role not in ("director", "admin", "owner"):
        if not assignment.get("is_active"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignment is not active")
        voice_part = current_member.get("voice_part")
        if assignment["target_type"] == "voice_part" and assignment.get("target_voice_part") != voice_part:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this member")
        if assignment["target_type"] == "individual" and member_id not in (assignment.get("target_member_ids") or []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this member")

    if body.self_rating is not None and not (1 <= body.self_rating <= 5):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self_rating must be between 1 and 5")

    if body.confidence_level is not None and not (1 <= body.confidence_level <= 5):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="confidence_level must be between 1 and 5")

    now = datetime.utcnow().isoformat()
    payload = {
        "customer_id": customer_id,
        "member_id": member_id,
        "assignment_id": body.assignment_id,
        "practice_minutes": body.practice_minutes,
        "sessions_count": body.sessions_count or 1,
        "created_at": now,
        "updated_at": now,
    }

    if body.self_rating is not None:
        payload["self_rating"] = body.self_rating
    if body.confidence_level is not None:
        payload["confidence_level"] = body.confidence_level
    if body.notes:
        payload["notes"] = body.notes

    response = client.table("choirdir_practice_progress").insert(payload).execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to log progress")

    return {"progress": response.data[0]}


@router.put("/progress/{progress_id}")
async def update_progress(
    progress_id: str,
    body: UpdateProgressRequest,
    current_member: dict = Depends(get_current_member),
):
    client = get_service_client()
    customer_id = current_member["customer_id"]
    member_id = current_member["id"]
    role = current_member.get("role", "member")

    existing_response = (
        client.table("choirdir_practice_progress")
        .select("*")
        .eq("id", progress_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not existing_response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Progress entry not found")

    existing = existing_response.data

    if role not in ("director", "admin", "owner") and existing["member_id"] != member_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update another member's progress")

    if body.self_rating is not None and not (1 <= body.self_rating <= 5):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self_rating must be between 1 and 5")

    if body.confidence_level is not None and not (1 <= body.confidence_level <= 5):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="confidence_level must be between 1 and 5")

    updates = {"updated_at": datetime.utcnow().isoformat()}
    if body.practice_minutes is not None:
        updates["practice_minutes"] = body.practice_minutes
    if body.sessions_count is not None:
        updates["sessions_count"] = body.sessions_count
    if body.self_rating is not None:
        updates["self_rating"] = body.self_rating
    if body.confidence_level is not None:
        updates["confidence_level"] = body.confidence_level
    if body.notes is not None:
        updates["notes"] = body.notes

    response = (
        client.table("choirdir_practice_progress")
        .update(updates)
        .eq("id", progress_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update progress")

    return {"progress": response.data[0]}


@router.get("/assignments/{assignment_id}/progress")
async def get_assignment_progress(
    assignment_id: str,
    current_member: dict = Depends(get_current_member),
):
    client = get_service_client()
    customer_id = current_member["customer_id"]
    member_id = current_member["id"]
    role = current_member.get("role", "member")

    assignment_response = (
        client.table("choirdir_practice_assignments")
        .select("*")
        .eq("id", assignment_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not assignment_response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    assignment = assignment_response.data

    if role in ("director", "admin", "owner"):
        progress_response = (
            client.table("choirdir_practice_progress")
            .select("*, choirdir_members(id, first_name, last_name, voice_part)")
            .eq("assignment_id", assignment_id)
            .eq("customer_id", customer_id)
            .order("created_at", desc=True)
            .execute()
        )
    else:
        voice_part = current_member.get("voice_part")
        if assignment["target_type"] == "voice_part" and assignment.get("target_voice_part") != voice_part:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this member")
        if assignment["target_type"] == "individual" and member_id not in (assignment.get("target_member_ids") or []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this member")

        progress_response = (
            client.table("choirdir_practice_progress")
            .select("*")
            .eq("assignment_id", assignment_id)
            .eq("member_id", member_id)
            .eq("customer_id", customer_id)
            .order("created_at", desc=True)
            .execute()
        )

    progress_list = progress_response.data or []

    total_minutes = sum(p.get("practice_minutes", 0) for p in progress_list)
    total_sessions = sum(p.get("sessions_count", 0) for p in progress_list)
    rated = [p["self_rating"] for p in progress_list if p.get("self_rating") is not None]
    avg_rating = sum(rated) / len(rated) if rated else None
    confident = [p["confidence_level"] for p in progress_list if p.get("confidence_level") is not None]
    avg_confidence = sum(confident) / len(confident) if confident else None

    return {
        "assignment": assignment,
        "progress": progress_list,
        "summary": {
            "total_minutes": total_minutes,
            "total_sessions": total_sessions,
            "average_self_rating": round(avg_rating, 2) if avg_rating is not None else None,
            "average_confidence_level": round(avg_confidence, 2) if avg_confidence is not None else None,
            "entries_count": len(progress_list),
        },
    }
