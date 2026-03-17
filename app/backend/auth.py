import logging
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from supabase import Client

from app.backend.config import get_settings
from app.backend.database import get_service_client

logger = logging.getLogger(__name__)

settings = get_settings()
security = HTTPBearer()


def verify_token(token: str) -> dict:
    """
    Verify a Supabase JWT token and return the decoded payload.

    Args:
        token: The JWT token string to verify.

    Returns:
        The decoded JWT payload as a dictionary.

    Raises:
        HTTPException: If the token is expired, invalid, or cannot be decoded.
    """
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={
                "verify_aud": False,
            },
        )
        return payload
    except ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as exc:
        logger.warning("JWT validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as exc:
        logger.error("Unexpected error verifying token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict:
    """
    FastAPI dependency that extracts and validates the current user from
    the Authorization Bearer token.

    Args:
        credentials: The HTTP Authorization credentials extracted by HTTPBearer.

    Returns:
        A dictionary containing:
            - uid (str): The user's unique identifier (Supabase user ID).
            - email (str): The user's email address.
            - role (str): The user's Supabase role (e.g. 'authenticated').

    Raises:
        HTTPException: If the token is missing, invalid, or the payload
                       does not contain the expected fields.
    """
    token = credentials.credentials
    payload = verify_token(token)

    uid: Optional[str] = payload.get("sub")
    if not uid:
        logger.warning("JWT payload missing 'sub' field")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email: Optional[str] = payload.get("email")
    role: str = payload.get("role", "authenticated")

    return {
        "uid": uid,
        "email": email,
        "role": role,
        "raw_payload": payload,
    }


def get_current_member(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_service_client),
) -> dict:
    """
    FastAPI dependency that retrieves the choirdir_members row for the
    currently authenticated user.

    Args:
        user: The current user dict returned by get_current_user.
        supabase: The Supabase service-role client.

    Returns:
        A dictionary containing the member record, which includes at minimum:
            - id (str): The member's primary key.
            - user_id (str): The Supabase auth user ID.
            - customer_id (str | None): Stripe customer ID.
            - role (str): The member's application role.
            - voice_part (str | None): The member's voice part.
            - email (str | None): The member's email.

    Raises:
        HTTPException 404: If no member record exists for this user.
        HTTPException 500: If the database query fails.
    """
    uid = user["uid"]

    try:
        response = (
            supabase.table("choirdir_members")
            .select(
                "id, user_id, customer_id, role, voice_part, email, created_at, updated_at"
            )
            .eq("user_id", uid)
            .single()
            .execute()
        )
    except Exception as exc:
        logger.error(
            "Database error looking up member for user_id=%s: %s", uid, exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving member record",
        )

    if not response.data:
        logger.info("No member record found for user_id=%s", uid)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member record not found",
        )

    member: dict = response.data
    member.setdefault("email", user.get("email"))

    return member
