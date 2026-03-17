from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel
from ..config import get_settings
from ..database import get_service_client
from ..auth import get_current_member

router = APIRouter(prefix="/attendance", tags=["attendance"])
settings = get_settings()


class AttendanceRecord(BaseModel):
    member_id: str
    event_date: date
    status: str
    event_type: Optional[str] = None
    event_id: Optional[str] = None
    notes: Optional[str] = None


class BulkAttendanceItem(BaseModel):
    member_id: str
    status: str
    notes: Optional[str] = None


class BulkAttendanceRequest(BaseModel):
    event_id: str
    event_date: date
    records: List[BulkAttendanceItem]


class AttendanceUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    event_date: Optional[date] = None
    event_type: Optional[str] = None


@router.post("")
async def record_attendance(
    record: AttendanceRecord,
    current_member: dict = Depends(get_current_member)
):
    service_client = get_service_client()

    existing = service_client.table("choirdir_attendance").select("id").eq(
        "member_id", record.member_id
    ).eq("event_date", record.event_date.isoformat())

    if record.event_id:
        existing = existing.eq("event_id", record.event_id)

    existing_result = existing.execute()

    data = {
        "member_id": record.member_id,
        "event_date": record.event_date.isoformat(),
        "status": record.status,
        "recorded_by": current_member["id"],
        "updated_at": datetime.utcnow().isoformat()
    }

    if record.event_type:
        data["event_type"] = record.event_type
    if record.event_id:
        data["event_id"] = record.event_id
    if record.notes:
        data["notes"] = record.notes

    if existing_result.data:
        attendance_id = existing_result.data[0]["id"]
        result = service_client.table("choirdir_attendance").update(data).eq(
            "id", attendance_id
        ).execute()
    else:
        data["created_at"] = datetime.utcnow().isoformat()
        result = service_client.table("choirdir_attendance").insert(data).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to record attendance")

    return result.data[0]


@router.post("/bulk")
async def record_bulk_attendance(
    bulk_request: BulkAttendanceRequest,
    current_member: dict = Depends(get_current_member)
):
    service_client = get_service_client()

    event_result = service_client.table("choirdir_events").select("*").eq(
        "id", bulk_request.event_id
    ).execute()

    if not event_result.data:
        raise HTTPException(status_code=404, detail="Event not found")

    event = event_result.data[0]
    now = datetime.utcnow().isoformat()
    results = []
    errors = []

    for item in bulk_request.records:
        existing = service_client.table("choirdir_attendance").select("id").eq(
            "member_id", item.member_id
        ).eq("event_id", bulk_request.event_id).execute()

        data = {
            "member_id": item.member_id,
            "event_id": bulk_request.event_id,
            "event_date": bulk_request.event_date.isoformat(),
            "status": item.status,
            "event_type": event.get("event_type"),
            "recorded_by": current_member["id"],
            "updated_at": now
        }

        if item.notes:
            data["notes"] = item.notes

        try:
            if existing.data:
                attendance_id = existing.data[0]["id"]
                result = service_client.table("choirdir_attendance").update(data).eq(
                    "id", attendance_id
                ).execute()
            else:
                data["created_at"] = now
                result = service_client.table("choirdir_attendance").insert(data).execute()

            if result.data:
                results.append(result.data[0])
            else:
                errors.append({"member_id": item.member_id, "error": "Failed to save"})
        except Exception as e:
            errors.append({"member_id": item.member_id, "error": str(e)})

    return {
        "saved": len(results),
        "errors": errors,
        "records": results
    }


@router.get("/event/{event_id}")
async def get_event_attendance(
    event_id: str,
    current_member: dict = Depends(get_current_member)
):
    service_client = get_service_client()

    event_result = service_client.table("choirdir_events").select("*").eq(
        "id", event_id
    ).execute()

    if not event_result.data:
        raise HTTPException(status_code=404, detail="Event not found")

    attendance_result = service_client.table("choirdir_attendance").select(
        "*, choirdir_members(id, first_name, last_name, email, voice_part, section)"
    ).eq("event_id", event_id).execute()

    records = []
    for record in attendance_result.data:
        member_data = record.pop("choirdir_members", None)
        if member_data:
            record["member_name"] = f"{member_data.get('first_name', '')} {member_data.get('last_name', '')}".strip()
            record["member_email"] = member_data.get("email")
            record["voice_part"] = member_data.get("voice_part")
            record["section"] = member_data.get("section")
        records.append(record)

    records.sort(key=lambda x: x.get("member_name", ""))

    summary = {
        "total": len(records),
        "present": sum(1 for r in records if r.get("status") == "present"),
        "absent": sum(1 for r in records if r.get("status") == "absent"),
        "late": sum(1 for r in records if r.get("status") == "late"),
        "excused": sum(1 for r in records if r.get("status") == "excused")
    }

    return {
        "event": event_result.data[0],
        "summary": summary,
        "records": records
    }


@router.get("/member/{member_id}")
async def get_member_attendance(
    member_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_member: dict = Depends(get_current_member)
):
    service_client = get_service_client()

    member_result = service_client.table("choirdir_members").select(
        "id, first_name, last_name, email, voice_part, section"
    ).eq("id", member_id).execute()

    if not member_result.data:
        raise HTTPException(status_code=404, detail="Member not found")

    query = service_client.table("choirdir_attendance").select(
        "*, choirdir_events(id, title, event_type, start_time)"
    ).eq("member_id", member_id)

    if start_date:
        query = query.gte("event_date", start_date.isoformat())
    if end_date:
        query = query.lte("event_date", end_date.isoformat())

    query = query.order("event_date", desc=True).range(offset, offset + limit - 1)
    attendance_result = query.execute()

    records = []
    for record in attendance_result.data:
        event_data = record.pop("choirdir_events", None)
        if event_data:
            record["event_title"] = event_data.get("title")
            record["event_start_time"] = event_data.get("start_time")
        records.append(record)

    all_query = service_client.table("choirdir_attendance").select(
        "status"
    ).eq("member_id", member_id)

    if start_date:
        all_query = all_query.gte("event_date", start_date.isoformat())
    if end_date:
        all_query = all_query.lte("event_date", end_date.isoformat())

    all_result = all_query.execute()
    all_records = all_result.data

    total = len(all_records)
    present = sum(1 for r in all_records if r.get("status") == "present")
    late = sum(1 for r in all_records if r.get("status") == "late")
    absent = sum(1 for r in all_records if r.get("status") == "absent")
    excused = sum(1 for r in all_records if r.get("status") == "excused")
    attendance_rate = round((present + late) / total * 100, 1) if total > 0 else 0.0

    return {
        "member": member_result.data[0],
        "summary": {
            "total_events": total,
            "present": present,
            "late": late,
            "absent": absent,
            "excused": excused,
            "attendance_rate": attendance_rate
        },
        "records": records,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total
        }
    }


@router.get("/report")
async def get_attendance_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    event_type: Optional[str] = None,
    section: Optional[str] = None,
    current_member: dict = Depends(get_current_member)
):
    service_client = get_service_client()

    members_query = service_client.table("choirdir_members").select(
        "id, first_name, last_name, email, voice_part, section"
    ).eq("is_active", True)

    if section:
        members_query = members_query.eq("section", section)

    members_result = members_query.order("last_name").execute()
    members = members_result.data

    attendance_query = service_client.table("choirdir_attendance").select("*")

    if start_date:
        attendance_query = attendance_query.gte("event_date", start_date.isoformat())
    if end_date:
        attendance_query = attendance_query.lte("event_date", end_date.isoformat())
    if event_type:
        attendance_query = attendance_query.eq("event_type", event_type)

    attendance_result = attendance_query.execute()
    attendance_records = attendance_result.data

    events_set = set()
    for rec in attendance_records:
        if rec.get("event_id"):
            events_set.add(rec["event_id"])
        else:
            events_set.add(rec["event_date"])

    total_events = len(events_set)

    member_map = {}
    for member in members:
        member_map[member["id"]] = {
            "member_id": member["id"],
            "member_name": f"{member.get('first_name', '')} {member.get('last_name', '')}".strip(),
            "email": member.get("email"),
            "voice_part": member.get("voice_part"),
            "section": member.get("section"),
            "present": 0,
            "absent": 0,
            "late": 0,
            "excused": 0,
            "total": 0,
            "attendance_rate": 0.0
        }

    for rec in attendance_records:
        mid = rec.get("member_id")
        if mid in member_map:
            status = rec.get("status", "")
            member_map[mid]["total"] += 1
            if status == "present":
                member_map[mid]["present"] += 1
            elif status == "absent":
                member_map[mid]["absent"] += 1
            elif status == "late":
                member_map[mid]["late"] += 1
            elif status == "excused":
                member_map[mid]["excused"] += 1

    report = []
    for mid, stats in member_map.items():
        counted = stats["present"] + stats["late"]
        total = stats["total"]
        stats["attendance_rate"] = round(counted / total * 100, 1) if total > 0 else 0.0
        report.append(stats)

    report.sort(key=lambda x: x["member_name"])

    overall_present = sum(r["present"] for r in report)
    overall_absent = sum(r["absent"] for r in report)
    overall_late = sum(r["late"] for r in report)
    overall_excused = sum(r["excused"] for r in report)
    overall_total = sum(r["total"] for r in report)
    overall_rate = round((overall_present + overall_late) / overall_total * 100, 1) if overall_total > 0 else 0.0

    return {
        "report": report,
        "total_events": total_events,
        "total_members": len(members),
        "filters": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "event_type": event_type,
            "section": section
        },
        "overall_summary": {
            "present": overall_present,
            "absent": overall_absent,
            "late": overall_late,
            "excused": overall_excused,
            "total_records": overall_total,
            "overall_attendance_rate": overall_rate
        }
    }


@router.put("/{attendance_id}")
async def update_attendance(
    attendance_id: str,
    update_data: AttendanceUpdate,
    current_member: dict = Depends(get_current_member)
):
    service_client = get_service_client()

    existing = service_client.table("choirdir_attendance").select("*").eq(
        "id", attendance_id
    ).execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    update_fields = {"updated_at": datetime.utcnow().isoformat()}

    if update_data.status is not None:
        update_fields["status"] = update_data.status
    if update_data.notes is not None:
        update_fields["notes"] = update_data.notes
    if update_data.event_date is not None:
        update_fields["event_date"] = update_data.event_date.isoformat()
    if update_data.event_type is not None:
        update_fields["event_type"] = update_data.event_type

    result = service_client.table("choirdir_attendance").update(update_fields).eq(
        "id", attendance_id
    ).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update attendance record")

    return result.data[0]
