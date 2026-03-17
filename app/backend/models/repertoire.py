from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Genre(str, Enum):
    CLASSICAL = "classical"
    BAROQUE = "baroque"
    ROMANTIC = "romantic"
    CONTEMPORARY = "contemporary"
    FOLK = "folk"
    SPIRITUAL = "spiritual"
    GOSPEL = "gospel"
    JAZZ = "jazz"
    POP = "pop"
    MUSICAL_THEATRE = "musical_theatre"
    OPERA = "opera"
    WORLD = "world"
    RENAISSANCE = "renaissance"
    MEDIEVAL = "medieval"
    OTHER = "other"


class RepertoireBase(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Title of the piece",
    )
    composer: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Name of the composer",
    )
    arranger: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Name of the arranger, if applicable",
    )
    genre: Optional[Genre] = Field(
        default=None,
        description="Musical genre of the piece",
    )
    voicing: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Voicing of the piece (e.g. SATB, SSA, TTBB)",
    )
    difficulty_level: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Difficulty level from 1 (easiest) to 5 (hardest)",
    )
    key_signature: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Key signature of the piece (e.g. C major, G minor)",
    )
    language: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Language of the lyrics",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="List of tags associated with the piece",
    )
    lyrics_text: Optional[str] = Field(
        default=None,
        description="Full text of the lyrics",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes or comments about the piece",
    )

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: object) -> List[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("tags must be a list")
        sanitized: List[str] = []
        for tag in v:
            if not isinstance(tag, str):
                raise ValueError(f"Each tag must be a string, got {type(tag)}")
            stripped = tag.strip()
            if stripped:
                sanitized.append(stripped)
        return sanitized

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v: object) -> str:
        if isinstance(v, str):
            return v.strip()
        return v  # type: ignore[return-value]


class RepertoireCreate(RepertoireBase):
    customer_id: int = Field(
        ...,
        gt=0,
        description="ID of the customer (choir/ensemble) that owns this piece",
    )


class RepertoireUpdate(BaseModel):
    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Title of the piece",
    )
    composer: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Name of the composer",
    )
    arranger: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Name of the arranger, if applicable",
    )
    genre: Optional[Genre] = Field(
        default=None,
        description="Musical genre of the piece",
    )
    voicing: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Voicing of the piece (e.g. SATB, SSA, TTBB)",
    )
    difficulty_level: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Difficulty level from 1 (easiest) to 5 (hardest)",
    )
    key_signature: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Key signature of the piece (e.g. C major, G minor)",
    )
    language: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Language of the lyrics",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="List of tags associated with the piece",
    )
    lyrics_text: Optional[str] = Field(
        default=None,
        description="Full text of the lyrics",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes or comments about the piece",
    )

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: object) -> Optional[List[str]]:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("tags must be a list")
        sanitized: List[str] = []
        for tag in v:
            if not isinstance(tag, str):
                raise ValueError(f"Each tag must be a string, got {type(tag)}")
            stripped = tag.strip()
            if stripped:
                sanitized.append(stripped)
        return sanitized

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v: object) -> Optional[str]:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped else None
        return v  # type: ignore[return-value]


class RepertoireResponse(RepertoireBase):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    id: int = Field(
        ...,
        gt=0,
        description="Unique identifier of the repertoire piece",
    )
    customer_id: int = Field(
        ...,
        gt=0,
        description="ID of the customer (choir/ensemble) that owns this piece",
    )
