from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from ..config import get_settings
from ..database import get_service_client
from ..auth import get_current_member

router = APIRouter(prefix="/members", tags=["members"])
settings = get_settings()

VOICE_PARTS = [
    "soprano", "alto", "tenor", "bass",
    "soprano_1", "soprano_2",
    "alto_1", "alto_2",
    "tenor_1", "tenor_2",
    "baritone",
    "bass_1", "bass_2"
]

ROLES = ["admin", "director", "member"]


class MemberCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: str
    voice_part: str
    phone: Optional[str] = None


class MemberUpdate(BaseModel):
    role: Optional[str] = None
    voice_part: Optional[str] = None
    status: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None


@router.get("", summary="List all members for current customer")
async def list_members(current_member: dict = Depends(get_current_member)):
    client = get_service_client()
    customer_id = current_member["customer_id"]
    response = (
        client.table("choirdir_members")
        .select("*")
        .eq("customer_id", customer_id)
        .neq("status", "deleted")
        .order("full_name")
        .execute()
    )
    return {"members": response.data}


@router.get("/by-voice-part/{voice_part}", summary="Get members by voice part")
async def members_by_voice_part(
    voice_part: str,
    current_member: dict = Depends(get_current_member)
):
    if voice_part not in VOICE_PARTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid voice part. Must be one of: {', '.join(VOICE_PARTS)}"
        )
    client = get_service_client()
    customer_id = current_member["customer_id"]
    response = (
        client.table("choirdir_members")
        .select("*")
        .eq("customer_id", customer_id)
        .eq("voice_part", voice_part)
        .neq("status", "deleted")
        .order("full_name")
        .execute()
    )
    return {"voice_part": voice_part, "members": response.data, "count": len(response.data)}


@router.get("/{member_id}", summary="Get a single member")
async def get_member(
    member_id: str,
    current_member: dict = Depends(get_current_member)
):
    client = get_service_client()
    customer_id = current_member["customer_id"]
    response = (
        client.table("choirdir_members")
        .select("*")
        .eq("id", member_id)
        .eq("customer_id", customer_id)
        .neq("status", "deleted")
        .single()
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found"
        )
    return response.data


@router.post("", status_code=status.HTTP_201_CREATED, summary="Add a new member")
async def create_member(
    body: MemberCreate,
    current_member: dict = Depends(get_current_member)
):
    if current_member.get("role") not in ("admin", "director"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only directors and admins can add members"
        )
    if body.role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(ROLES)}"
        )
    if body.voice_part not in VOICE_PARTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid voice part. Must be one of: {', '.join(VOICE_PARTS)}"
        )
    client = get_service_client()
    customer_id = current_member["customer_id"]
    existing = (
        client.table("choirdir_members")
        .select("id")
        .eq("customer_id", customer_id)
        .eq("email", body.email)
        .neq("status", "deleted")
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A member with this email already exists"
        )
    new_member = {
        "customer_id": customer_id,
        "email": body.email,
        "full_name": body.full_name,
        "role": body.role,
        "voice_part": body.voice_part,
        "status": "active",
    }
    if body.phone:
        new_member["phone"] = body.phone
    response = (
        client.table("choirdir_members")
        .insert(new_member)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create member"
        )
    return response.data[0]


@router.put("/{member_id}", summary="Update a member")
async def update_member(
    member_id: str,
    body: MemberUpdate,
    current_member: dict = Depends(get_current_member)
):
    client = get_service_client()
    customer_id = current_member["customer_id"]
    existing = (
        client.table("choirdir_members")
        .select("*")
        .eq("id", member_id)
        .eq("customer_id", customer_id)
        .neq("status", "deleted")
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found"
        )
    is_self = current_member["id"] == member_id
    is_privileged = current_member.get("role") in ("admin", "director")
    if not is_self and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this member"
        )
    if body.role is not None and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only directors and admins can change roles"
        )
    if body.status is not None and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only directors and admins can change member status"
        )
    if body.role is not None and body.role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(ROLES)}"
        )
    if body.voice_part is not None and body.voice_part not in VOICE_PARTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid voice part. Must be one of: {', '.join(VOICE_PARTS)}"
        )
    if body.status is not None and body.status not in ("active", "inactive"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be 'active' or 'inactive'"
        )
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    response = (
        client.table("choirdir_members")
        .update(updates)
        .eq("id", member_id)
        .eq("customer_id", customer_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update member"
        )
    return response.data[0]


@router.delete("/{member_id}", summary="Soft delete a member")
async def delete_member(
    member_id: str,
    current_member: dict = Depends(get_current_member)
):
    if current_member.get("role") not in ("admin", "director"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only directors and admins can remove members"
        )
    client = get_service_client()
    customer_id = current_member["customer_id"]
    existing = (
        client.table("choirdir_members")
        .select("id")
        .eq("id", member_id)
        .eq("customer_id", customer_id)
        .neq("status", "deleted")
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found"
        )
    if current_member["id"] == member_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account"
        )
    response = (
        client.table("choirdir_members")
        .update({"status": "inactive"})
        .eq("id", member_id)
        .eq("customer_id", customer_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete member"
        )
    return {"message": "Member deactivated successfully", "member_id": member_id}
