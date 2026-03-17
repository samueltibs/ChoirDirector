from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MemberRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"
    GUEST = "guest"


class VoicePart(str, Enum):
    SOPRANO = "soprano"
    MEZZO_SOPRANO = "mezzo_soprano"
    ALTO = "alto"
    TENOR = "tenor"
    BARITONE = "baritone"
    BASS = "bass"
    TREBLE = "treble"
    COUNTERTENOR = "countertenor"


class MemberStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class MemberBase(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        use_enum_values=True,
        populate_by_name=True,
    )

    email: EmailStr = Field(
        ...,
        description="The member's email address.",
        examples=["jane.doe@example.com"],
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="The member's full name.",
        examples=["Jane Doe"],
    )
    role: MemberRole = Field(
        default=MemberRole.MEMBER,
        description="The member's role within the organisation.",
    )
    voice_part: Optional[VoicePart] = Field(
        default=None,
        description="The member's vocal part (choral context).",
    )
    status: MemberStatus = Field(
        default=MemberStatus.PENDING,
        description="Current membership status.",
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Optional contact phone number.",
        examples=["+1-555-867-5309"],
    )


class MemberCreate(MemberBase):
    """Schema used when creating a new member."""

    customer_id: uuid.UUID = Field(
        ...,
        description="UUID of the customer (organisation/tenant) this member belongs to.",
    )


class MemberUpdate(BaseModel):
    """Schema used when partially updating an existing member.

    All fields are optional so callers can supply only the fields they wish to
    change (PATCH semantics).
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        use_enum_values=True,
        populate_by_name=True,
    )

    email: Optional[EmailStr] = Field(
        default=None,
        description="Updated email address.",
    )
    full_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated full name.",
    )
    role: Optional[MemberRole] = Field(
        default=None,
        description="Updated role.",
    )
    voice_part: Optional[VoicePart] = Field(
        default=None,
        description="Updated voice part.",
    )
    status: Optional[MemberStatus] = Field(
        default=None,
        description="Updated membership status.",
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Updated phone number.",
    )


class MemberResponse(MemberBase):
    """Schema returned to API consumers."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        use_enum_values=True,
        populate_by_name=True,
        from_attributes=True,
    )

    id: uuid.UUID = Field(
        ...,
        description="Unique identifier for the member.",
    )
    customer_id: uuid.UUID = Field(
        ...,
        description="UUID of the owning customer/tenant.",
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the member record was created (UTC).",
    )
