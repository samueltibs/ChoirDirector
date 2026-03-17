from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from pydantic import BaseModel
from ..config import get_settings
from ..database import get_service_client
from ..auth import get_current_member

router = APIRouter(prefix="/repertoire", tags=["repertoire"])
settings = get_settings()


class RepertoireCreate(BaseModel):
    title: str
    composer: Optional[str] = None
    arranger: Optional[str] = None
    genre: str
    voicing: str
    difficulty_level: Optional[str] = None
    key_signature: Optional[str] = None
    time_signature: Optional[str] = None
    tempo_bpm: Optional[int] = None
    tags: Optional[List[str]] = None
    lyrics_text: Optional[str] = None
    notes: Optional[str] = None
    sacred_secular: Optional[str] = None


class RepertoireUpdate(BaseModel):
    title: Optional[str] = None
    composer: Optional[str] = None
    arranger: Optional[str] = None
    genre: Optional[str] = None
    voicing: Optional[str] = None
    difficulty_level: Optional[str] = None
    key_signature: Optional[str] = None
    time_signature: Optional[str] = None
    tempo_bpm: Optional[int] = None
    tags: Optional[List[str]] = None
    lyrics_text: Optional[str] = None
    notes: Optional[str] = None
    sacred_secular: Optional[str] = None


@router.get("")
async def list_repertoire(
    genre: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    voicing: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    current_member: dict = Depends(get_current_member),
):
    service_client = get_service_client()
    customer_id = current_member["customer_id"]

    query = (
        service_client.table("choirdir_repertoire")
        .select("*")
        .eq("customer_id", customer_id)
    )

    if genre:
        query = query.eq("genre", genre)
    if voicing:
        query = query.eq("voicing", voicing)
    if difficulty:
        query = query.eq("difficulty_level", difficulty)
    if search:
        query = query.or_(
            f"title.ilike.%{search}%,composer.ilike.%{search}%"
        )

    response = query.order("title").execute()

    if hasattr(response, "error") and response.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch repertoire",
        )

    return {"data": response.data, "count": len(response.data)}


@router.get("/{piece_id}")
async def get_piece(
    piece_id: str,
    current_member: dict = Depends(get_current_member),
):
    service_client = get_service_client()
    customer_id = current_member["customer_id"]

    response = (
        service_client.table("choirdir_repertoire")
        .select("*")
        .eq("id", piece_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Piece not found",
        )

    return {"data": response.data}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_piece(
    payload: RepertoireCreate,
    current_member: dict = Depends(get_current_member),
):
    service_client = get_service_client()
    customer_id = current_member["customer_id"]
    member_id = current_member["id"]

    insert_data = payload.dict(exclude_none=True)
    insert_data["customer_id"] = customer_id
    insert_data["created_by"] = member_id

    response = (
        service_client.table("choirdir_repertoire")
        .insert(insert_data)
        .execute()
    )

    if hasattr(response, "error") and response.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create piece",
        )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create piece",
        )

    return {"data": response.data[0]}


@router.put("/{piece_id}")
async def update_piece(
    piece_id: str,
    payload: RepertoireUpdate,
    current_member: dict = Depends(get_current_member),
):
    service_client = get_service_client()
    customer_id = current_member["customer_id"]

    existing = (
        service_client.table("choirdir_repertoire")
        .select("id")
        .eq("id", piece_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Piece not found",
        )

    update_data = payload.dict(exclude_none=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    response = (
        service_client.table("choirdir_repertoire")
        .update(update_data)
        .eq("id", piece_id)
        .eq("customer_id", customer_id)
        .execute()
    )

    if hasattr(response, "error") and response.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update piece",
        )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update piece",
        )

    return {"data": response.data[0]}


@router.delete("/{piece_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_piece(
    piece_id: str,
    current_member: dict = Depends(get_current_member),
):
    service_client = get_service_client()
    customer_id = current_member["customer_id"]

    existing = (
        service_client.table("choirdir_repertoire")
        .select("id")
        .eq("id", piece_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Piece not found",
        )

    response = (
        service_client.table("choirdir_repertoire")
        .delete()
        .eq("id", piece_id)
        .eq("customer_id", customer_id)
        .execute()
    )

    if hasattr(response, "error") and response.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete piece",
        )

    return None


@router.get("/{piece_id}/harmony-analysis")
async def get_harmony_analysis(
    piece_id: str,
    current_member: dict = Depends(get_current_member),
):
    service_client = get_service_client()
    customer_id = current_member["customer_id"]

    piece = (
        service_client.table("choirdir_repertoire")
        .select("id")
        .eq("id", piece_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not piece.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Piece not found",
        )

    response = (
        service_client.table("choirdir_harmony_analysis")
        .select("*")
        .eq("piece_id", piece_id)
        .eq("customer_id", customer_id)
        .order("created_at", desc=True)
        .execute()
    )

    if hasattr(response, "error") and response.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch harmony analysis",
        )

    return {"data": response.data, "count": len(response.data)}


@router.get("/{piece_id}/rehearsal-tracks")
async def get_rehearsal_tracks(
    piece_id: str,
    current_member: dict = Depends(get_current_member),
):
    service_client = get_service_client()
    customer_id = current_member["customer_id"]

    piece = (
        service_client.table("choirdir_repertoire")
        .select("id")
        .eq("id", piece_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not piece.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Piece not found",
        )

    response = (
        service_client.table("choirdir_rehearsal_tracks")
        .select("*")
        .eq("piece_id", piece_id)
        .eq("customer_id", customer_id)
        .order("voice_part")
        .execute()
    )

    if hasattr(response, "error") and response.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch rehearsal tracks",
        )

    return {"data": response.data, "count": len(response.data)}


@router.get("/{piece_id}/sheet-music")
async def get_sheet_music(
    piece_id: str,
    current_member: dict = Depends(get_current_member),
):
    service_client = get_service_client()
    customer_id = current_member["customer_id"]

    piece = (
        service_client.table("choirdir_repertoire")
        .select("id")
        .eq("id", piece_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not piece.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Piece not found",
        )

    response = (
        service_client.table("choirdir_sheet_music")
        .select("*")
        .eq("piece_id", piece_id)
        .eq("customer_id", customer_id)
        .order("created_at", desc=True)
        .execute()
    )

    if hasattr(response, "error") and response.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch sheet music",
        )

    return {"data": response.data, "count": len(response.data)}
