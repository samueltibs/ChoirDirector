from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

from ..config import get_settings
from ..database import get_service_client
from ..auth import get_current_member

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    customer_slug: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class MemberProfile(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    customer_id: str
    role: Optional[str] = None
    created_at: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    member: MemberProfile


class MessageResponse(BaseModel):
    message: str


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest):
    service_client = get_service_client()

    # Look up customer by slug
    customer_res = (
        service_client.table("choirdir_customers")
        .select("id")
        .eq("slug", body.customer_slug)
        .single()
        .execute()
    )
    if not customer_res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with slug '{body.customer_slug}' not found",
        )
    customer_id = customer_res.data["id"]

    # Create user in Supabase Auth
    try:
        auth_res = service_client.auth.admin.create_user(
            {
                "email": body.email,
                "password": body.password,
                "email_confirm": True,
                "user_metadata": {"full_name": body.full_name},
            }
        )
    except Exception as e:
        logger.error(f"Supabase auth create_user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not auth_res.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create auth user",
        )

    user_id = auth_res.user.id

    # Create choirdir_members row
    try:
        member_res = (
            service_client.table("choirdir_members")
            .insert(
                {
                    "id": user_id,
                    "email": body.email,
                    "full_name": body.full_name,
                    "customer_id": customer_id,
                    "role": "member",
                }
            )
            .select()
            .single()
            .execute()
        )
    except Exception as e:
        logger.error(f"Failed to create member row: {e}")
        # Attempt to clean up auth user
        try:
            service_client.auth.admin.delete_user(user_id)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create member profile",
        )

    member_data = member_res.data

    # Sign in to get tokens
    try:
        sign_in_res = service_client.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as e:
        logger.error(f"Sign-in after signup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account created but login failed. Please login manually.",
        )

    session = sign_in_res.session
    if not session:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account created but session could not be established",
        )

    return AuthResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        member=MemberProfile(
            id=member_data["id"],
            email=member_data["email"],
            full_name=member_data.get("full_name"),
            customer_id=member_data["customer_id"],
            role=member_data.get("role"),
            created_at=member_data.get("created_at"),
        ),
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    service_client = get_service_client()

    try:
        sign_in_res = service_client.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    session = sign_in_res.session
    user = sign_in_res.user
    if not session or not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Fetch member profile
    member_res = (
        service_client.table("choirdir_members")
        .select("*")
        .eq("id", user.id)
        .single()
        .execute()
    )
    if not member_res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member profile not found",
        )

    member_data = member_res.data

    return AuthResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        member=MemberProfile(
            id=member_data["id"],
            email=member_data["email"],
            full_name=member_data.get("full_name"),
            customer_id=member_data["customer_id"],
            role=member_data.get("role"),
            created_at=member_data.get("created_at"),
        ),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(current_member: dict = Depends(get_current_member)):
    service_client = get_service_client()

    try:
        service_client.auth.sign_out()
    except Exception as e:
        logger.warning(f"Logout error (non-fatal): {e}")

    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=MemberProfile)
async def get_me(current_member: dict = Depends(get_current_member)):
    return MemberProfile(
        id=current_member["id"],
        email=current_member["email"],
        full_name=current_member.get("full_name"),
        customer_id=current_member["customer_id"],
        role=current_member.get("role"),
        created_at=current_member.get("created_at"),
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(body: RefreshRequest):
    service_client = get_service_client()

    try:
        refresh_res = service_client.auth.refresh_session(body.refresh_token)
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    session = refresh_res.session
    user = refresh_res.user
    if not session or not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh session",
        )

    # Fetch member profile
    member_res = (
        service_client.table("choirdir_members")
        .select("*")
        .eq("id", user.id)
        .single()
        .execute()
    )
    if not member_res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member profile not found",
        )

    member_data = member_res.data

    return AuthResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        member=MemberProfile(
            id=member_data["id"],
            email=member_data["email"],
            full_name=member_data.get("full_name"),
            customer_id=member_data["customer_id"],
            role=member_data.get("role"),
            created_at=member_data.get("created_at"),
        ),
    )
