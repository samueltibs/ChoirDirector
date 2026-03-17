from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Any
import uuid
from datetime import datetime, timezone

from ..config import get_settings
from ..database import get_service_client
from ..auth import get_current_member

router = APIRouter(prefix="/customers", tags=["customers"])


class CustomerUpdateRequest(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    settings: Optional[dict[str, Any]] = None


class CustomerCreateRequest(BaseModel):
    name: str
    slug: str
    type: Optional[str] = "choir"
    subscription_plan: Optional[str] = "free"


class BrandBrainUpdateRequest(BaseModel):
    tone: Optional[str] = None
    voice_attributes: Optional[list[str]] = None
    description: Optional[str] = None
    mission_statement: Optional[str] = None
    target_audience: Optional[str] = None
    keywords: Optional[list[str]] = None
    avoid_words: Optional[list[str]] = None
    example_content: Optional[str] = None
    extra_data: Optional[dict[str, Any]] = None


@router.get("/me")
async def get_my_customer(current_member: dict = Depends(get_current_member)):
    """
    Get the current customer/organization profile based on the authenticated member.
    """
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No customer associated with this member.",
        )

    response = (
        supabase.table("choirdir_customers")
        .select("*")
        .eq("id", customer_id)
        .single()
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    return response.data


@router.put("/me")
async def update_my_customer(
    body: CustomerUpdateRequest,
    current_member: dict = Depends(get_current_member),
):
    """
    Update current customer settings. Only admins or directors can update.
    """
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No customer associated with this member.",
        )

    member_role = current_member.get("role", "member")
    if member_role not in ("admin", "director", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins or directors can update customer settings.",
        )

    update_data: dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    if body.name is not None:
        update_data["name"] = body.name
    if body.logo_url is not None:
        update_data["logo_url"] = body.logo_url
    if body.settings is not None:
        update_data["settings"] = body.settings

    if len(update_data) == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update.",
        )

    response = (
        supabase.table("choirdir_customers")
        .update(update_data)
        .eq("id", customer_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update customer.",
        )

    return response.data[0]


@router.get("/me/stats")
async def get_my_customer_stats(current_member: dict = Depends(get_current_member)):
    """
    Get dashboard stats for the current customer:
    - member count
    - repertoire count
    - upcoming events count
    - attendance rate (last 90 days)
    """
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No customer associated with this member.",
        )

    # Member count
    member_resp = (
        supabase.table("choirdir_members")
        .select("id", count="exact")
        .eq("customer_id", customer_id)
        .eq("status", "active")
        .execute()
    )
    member_count = member_resp.count if member_resp.count is not None else 0

    # Repertoire count
    rep_resp = (
        supabase.table("choirdir_repertoire")
        .select("id", count="exact")
        .eq("customer_id", customer_id)
        .execute()
    )
    repertoire_count = rep_resp.count if rep_resp.count is not None else 0

    # Upcoming events count (events with start_date >= now)
    now_iso = datetime.now(timezone.utc).isoformat()
    events_resp = (
        supabase.table("choirdir_events")
        .select("id", count="exact")
        .eq("customer_id", customer_id)
        .gte("start_date", now_iso)
        .execute()
    )
    upcoming_events = events_resp.count if events_resp.count is not None else 0

    # Attendance rate: last 90 days
    from datetime import timedelta

    ninety_days_ago = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

    attendance_resp = (
        supabase.table("choirdir_attendance")
        .select("id, status")
        .eq("customer_id", customer_id)
        .gte("created_at", ninety_days_ago)
        .execute()
    )

    attendance_records = attendance_resp.data or []
    total_records = len(attendance_records)
    if total_records > 0:
        present_records = sum(
            1
            for r in attendance_records
            if r.get("status") in ("present", "attended", "yes")
        )
        attendance_rate = round((present_records / total_records) * 100, 2)
    else:
        attendance_rate = 0.0

    return {
        "member_count": member_count,
        "repertoire_count": repertoire_count,
        "upcoming_events": upcoming_events,
        "attendance_rate": attendance_rate,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreateRequest,
    current_member: dict = Depends(get_current_member),
):
    """
    Create a new customer/organization. Admin only.
    """
    member_role = current_member.get("role", "member")
    if member_role not in ("admin", "owner", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create new organizations.",
        )

    supabase = get_service_client()

    # Check slug uniqueness
    slug_check = (
        supabase.table("choirdir_customers")
        .select("id")
        .eq("slug", body.slug)
        .execute()
    )
    if slug_check.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer with this slug already exists.",
        )

    new_customer = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "slug": body.slug,
        "type": body.type or "choir",
        "subscription_plan": body.subscription_plan or "free",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    response = supabase.table("choirdir_customers").insert(new_customer).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create customer.",
        )

    return response.data[0]


@router.get("/me/brand-brain")
async def get_brand_brain(current_member: dict = Depends(get_current_member)):
    """
    Get the brand brain profile for the current customer.
    """
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No customer associated with this member.",
        )

    response = (
        supabase.table("choirdir_brand_brain")
        .select("*")
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not response.data:
        # Return empty brand brain structure if none exists yet
        return {
            "customer_id": customer_id,
            "tone": None,
            "voice_attributes": [],
            "description": None,
            "mission_statement": None,
            "target_audience": None,
            "keywords": [],
            "avoid_words": [],
            "example_content": None,
            "extra_data": {},
        }

    return response.data


@router.put("/me/brand-brain")
async def update_brand_brain(
    body: BrandBrainUpdateRequest,
    current_member: dict = Depends(get_current_member),
):
    """
    Upsert the brand brain for the current customer.
    Only admins or directors can update.
    """
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No customer associated with this member.",
        )

    member_role = current_member.get("role", "member")
    if member_role not in ("admin", "director", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins or directors can update brand brain.",
        )

    # Check if brand brain already exists
    existing = (
        supabase.table("choirdir_brand_brain")
        .select("id")
        .eq("customer_id", customer_id)
        .execute()
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    update_data: dict[str, Any] = {"updated_at": now_iso}

    if body.tone is not None:
        update_data["tone"] = body.tone
    if body.voice_attributes is not None:
        update_data["voice_attributes"] = body.voice_attributes
    if body.description is not None:
        update_data["description"] = body.description
    if body.mission_statement is not None:
        update_data["mission_statement"] = body.mission_statement
    if body.target_audience is not None:
        update_data["target_audience"] = body.target_audience
    if body.keywords is not None:
        update_data["keywords"] = body.keywords
    if body.avoid_words is not None:
        update_data["avoid_words"] = body.avoid_words
    if body.example_content is not None:
        update_data["example_content"] = body.example_content
    if body.extra_data is not None:
        update_data["extra_data"] = body.extra_data

    if existing.data:
        brand_brain_id = existing.data[0]["id"]
        response = (
            supabase.table("choirdir_brand_brain")
            .update(update_data)
            .eq("id", brand_brain_id)
            .execute()
        )
    else:
        update_data["id"] = str(uuid.uuid4())
        update_data["customer_id"] = customer_id
        update_data["created_at"] = now_iso
        response = supabase.table("choirdir_brand_brain").insert(update_data).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update brand brain.",
        )

    return response.data[0]
