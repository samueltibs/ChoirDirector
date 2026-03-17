from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

from ..config import get_settings
from ..database import get_service_client
from ..auth import get_current_member

router = APIRouter(prefix="/events", tags=["events"])
settings = get_settings()


class EventCreate(BaseModel):
    title: str
    event_type: str
    venue: Optional[str] = None
    address: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    dress_code: Optional[str] = None
    call_time: Optional[datetime] = None
    notes: Optional[str] = None


class EventUpdate(BaseModel):
    title: Optional[str] = None
    event_type: Optional[str] = None
    venue: Optional[str] = None
    address: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    dress_code: Optional[str] = None
    call_time: Optional[datetime] = None
    notes: Optional[str] = None


class SetlistItemInput(BaseModel):
    repertoire_id: str
    position: int
    notes: Optional[str] = None


class SetlistCreate(BaseModel):
    name: str
    pieces: list[SetlistItemInput]


class SetlistItemsUpdate(BaseModel):
    pieces: list[SetlistItemInput]


@router.get("/upcoming")
async def get_upcoming_events(
    current_member: dict = Depends(get_current_member)
):
    client = get_service_client()
    now = datetime.utcnow().isoformat()
    response = (
        client.table("choirdir_events")
        .select("*")
        .gte("start_time", now)
        .order("start_time", desc=False)
        .limit(10)
        .execute()
    )
    return {"events": response.data}


@router.get("")
async def list_events(
    type: Optional[str] = Query(None, alias="type"),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    current_member: dict = Depends(get_current_member)
):
    client = get_service_client()
    query = client.table("choirdir_events").select("*")

    if type:
        query = query.eq("event_type", type)
    if from_date:
        query = query.gte("start_time", from_date)
    if to_date:
        query = query.lte("start_time", to_date)

    response = query.order("start_time", desc=False).execute()
    return {"events": response.data}


@router.get("/{event_id}")
async def get_event(
    event_id: str,
    current_member: dict = Depends(get_current_member)
):
    client = get_service_client()

    event_response = (
        client.table("choirdir_events")
        .select("*")
        .eq("id", event_id)
        .single()
        .execute()
    )

    if not event_response.data:
        raise HTTPException(status_code=404, detail="Event not found")

    event = event_response.data

    setlist_response = (
        client.table("choirdir_setlists")
        .select("*, choirdir_setlist_items(*, choirdir_repertoire(*)")
        .eq("event_id", event_id)
        .execute()
    )

    setlists = setlist_response.data or []
    for setlist in setlists:
        items = setlist.get("choirdir_setlist_items") or []
        items_sorted = sorted(items, key=lambda x: x.get("position", 0))
        setlist["choirdir_setlist_items"] = items_sorted

    event["setlists"] = setlists
    return event


@router.post("", status_code=201)
async def create_event(
    body: EventCreate,
    current_member: dict = Depends(get_current_member)
):
    client = get_service_client()

    payload = body.dict(exclude_none=True)
    for key in ["start_time", "end_time", "call_time"]:
        if key in payload and payload[key] is not None:
            payload[key] = payload[key].isoformat()

    payload["created_by"] = current_member["id"]

    response = client.table("choirdir_events").insert(payload).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create event")

    return response.data[0]


@router.put("/{event_id}")
async def update_event(
    event_id: str,
    body: EventUpdate,
    current_member: dict = Depends(get_current_member)
):
    client = get_service_client()

    existing = (
        client.table("choirdir_events")
        .select("id")
        .eq("id", event_id)
        .single()
        .execute()
    )

    if not existing.data:
        raise HTTPException(status_code=404, detail="Event not found")

    payload = body.dict(exclude_none=True)
    for key in ["start_time", "end_time", "call_time"]:
        if key in payload and payload[key] is not None:
            payload[key] = payload[key].isoformat()

    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")

    payload["updated_at"] = datetime.utcnow().isoformat()

    response = (
        client.table("choirdir_events")
        .update(payload)
        .eq("id", event_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to update event")

    return response.data[0]


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: str,
    current_member: dict = Depends(get_current_member)
):
    client = get_service_client()

    existing = (
        client.table("choirdir_events")
        .select("id")
        .eq("id", event_id)
        .single()
        .execute()
    )

    if not existing.data:
        raise HTTPException(status_code=404, detail="Event not found")

    client.table("choirdir_events").delete().eq("id", event_id).execute()
    return None


@router.get("/{event_id}/setlist")
async def get_setlist(
    event_id: str,
    current_member: dict = Depends(get_current_member)
):
    client = get_service_client()

    event_check = (
        client.table("choirdir_events")
        .select("id")
        .eq("id", event_id)
        .single()
        .execute()
    )

    if not event_check.data:
        raise HTTPException(status_code=404, detail="Event not found")

    setlist_response = (
        client.table("choirdir_setlists")
        .select("*, choirdir_setlist_items(*, choirdir_repertoire(*))")
        .eq("event_id", event_id)
        .execute()
    )

    setlists = setlist_response.data or []
    for setlist in setlists:
        items = setlist.get("choirdir_setlist_items") or []
        setlist["choirdir_setlist_items"] = sorted(items, key=lambda x: x.get("position", 0))

    return {"setlists": setlists}


@router.post("/{event_id}/setlist", status_code=201)
async def create_setlist(
    event_id: str,
    body: SetlistCreate,
    current_member: dict = Depends(get_current_member)
):
    client = get_service_client()

    event_check = (
        client.table("choirdir_events")
        .select("id")
        .eq("id", event_id)
        .single()
        .execute()
    )

    if not event_check.data:
        raise HTTPException(status_code=404, detail="Event not found")

    setlist_payload = {
        "event_id": event_id,
        "name": body.name,
        "created_by": current_member["id"],
    }

    setlist_response = (
        client.table("choirdir_setlists").insert(setlist_payload).execute()
    )

    if not setlist_response.data:
        raise HTTPException(status_code=500, detail="Failed to create setlist")

    setlist = setlist_response.data[0]
    setlist_id = setlist["id"]

    if body.pieces:
        items_payload = [
            {
                "setlist_id": setlist_id,
                "repertoire_id": piece.repertoire_id,
                "position": piece.position,
                "notes": piece.notes,
            }
            for piece in body.pieces
        ]
        items_response = (
            client.table("choirdir_setlist_items").insert(items_payload).execute()
        )
        setlist["items"] = items_response.data or []
    else:
        setlist["items"] = []

    return setlist


@router.put("/{event_id}/setlist/{setlist_id}/items")
async def update_setlist_items(
    event_id: str,
    setlist_id: str,
    body: SetlistItemsUpdate,
    current_member: dict = Depends(get_current_member)
):
    client = get_service_client()

    setlist_check = (
        client.table("choirdir_setlists")
        .select("id")
        .eq("id", setlist_id)
        .eq("event_id", event_id)
        .single()
        .execute()
    )

    if not setlist_check.data:
        raise HTTPException(status_code=404, detail="Setlist not found for this event")

    client.table("choirdir_setlist_items").delete().eq("setlist_id", setlist_id).execute()

    if body.pieces:
        items_payload = [
            {
                "setlist_id": setlist_id,
                "repertoire_id": piece.repertoire_id,
                "position": piece.position,
                "notes": piece.notes,
            }
            for piece in body.pieces
        ]
        items_response = (
            client.table("choirdir_setlist_items").insert(items_payload).execute()
        )
        new_items = items_response.data or []
    else:
        new_items = []

    new_items_sorted = sorted(new_items, key=lambda x: x.get("position", 0))

    return {"setlist_id": setlist_id, "items": new_items_sorted}
