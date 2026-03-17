from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventType(str, Enum):
    rehearsal = "rehearsal"
    performance = "performance"
    sectional = "sectional"
    workshop = "workshop"
    audition = "audition"
    social = "social"


class EventBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Title of the event",
    )
    event_type: EventType = Field(
        ...,
        description="Type/category of the event",
    )
    venue: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Name of the venue where the event takes place",
    )
    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Full address of the event location",
    )
    start_time: datetime = Field(
        ...,
        description="Date and time when the event starts (UTC)",
    )
    end_time: datetime = Field(
        ...,
        description="Date and time when the event ends (UTC)",
    )
    call_time: Optional[datetime] = Field(
        default=None,
        description="Call time for participants (e.g. when musicians should arrive) (UTC)",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Detailed description of the event",
    )
    dress_code: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Dress code or attire requirements for the event",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Additional internal notes about the event",
    )

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank or whitespace only")
        return v

    @model_validator(mode="after")
    def end_time_must_be_after_start_time(self) -> EventBase:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly after start_time")
        return self

    @model_validator(mode="after")
    def call_time_must_be_before_or_at_start_time(self) -> EventBase:
        if self.call_time is not None and self.call_time > self.start_time:
            raise ValueError("call_time must be at or before start_time")
        return self


class EventCreate(EventBase):
    customer_id: uuid.UUID = Field(
        ...,
        description="UUID of the customer (organisation) that owns this event",
    )


class EventUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Title of the event",
    )
    event_type: Optional[EventType] = Field(
        default=None,
        description="Type/category of the event",
    )
    venue: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Name of the venue where the event takes place",
    )
    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Full address of the event location",
    )
    start_time: Optional[datetime] = Field(
        default=None,
        description="Date and time when the event starts (UTC)",
    )
    end_time: Optional[datetime] = Field(
        default=None,
        description="Date and time when the event ends (UTC)",
    )
    call_time: Optional[datetime] = Field(
        default=None,
        description="Call time for participants (UTC)",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Detailed description of the event",
    )
    dress_code: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Dress code or attire requirements for the event",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Additional internal notes about the event",
    )

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("title must not be blank or whitespace only")
        return v

    @model_validator(mode="after")
    def validate_time_ordering(self) -> EventUpdate:
        start = self.start_time
        end = self.end_time
        call = self.call_time

        if start is not None and end is not None:
            if end <= start:
                raise ValueError("end_time must be strictly after start_time")

        if call is not None and start is not None:
            if call > start:
                raise ValueError("call_time must be at or before start_time")

        return self


class EventResponse(EventBase):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        use_enum_values=True,
    )

    id: uuid.UUID = Field(
        ...,
        description="Unique identifier for the event",
    )
    customer_id: uuid.UUID = Field(
        ...,
        description="UUID of the customer (organisation) that owns this event",
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the event record was created (UTC)",
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the event record was last updated (UTC)",
    )
