from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import httpx
import logging

from ..config import get_settings
from ..database import get_service_client
from ..auth import get_current_member

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/harmony", tags=["harmony"])


class NoteCheckItem(BaseModel):
    midi_note: int
    voice_part: str


class VoiceCheckRequest(BaseModel):
    notes: List[NoteCheckItem]


VOICE_RANGES: Dict[str, Dict[str, int]] = {
    "soprano": {"min": 60, "max": 81},
    "mezzo_soprano": {"min": 57, "max": 79},
    "alto": {"min": 53, "max": 74},
    "tenor": {"min": 48, "max": 69},
    "baritone": {"min": 45, "max": 67},
    "bass": {"min": 40, "max": 64},
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_note_name(midi: int) -> str:
    octave = (midi // 12) - 1
    note = NOTE_NAMES[midi % 12]
    return f"{note}{octave}"


async def dispatch_harmony_analysis(
    repertoire_id: str,
    customer_id: str,
    member_id: str,
    analysis_id: str,
) -> None:
    settings = get_settings()
    supabase = get_service_client()

    try:
        harmony_service_url = getattr(settings, "HARMONY_ENGINE_URL", None)
        if not harmony_service_url:
            harmony_service_url = "http://harmony-engine:8001"

        repertoire_resp = (
            supabase.table("repertoire")
            .select("*")
            .eq("id", repertoire_id)
            .eq("customer_id", customer_id)
            .single()
            .execute()
        )

        if not repertoire_resp.data:
            raise ValueError(f"Repertoire {repertoire_id} not found")

        repertoire = repertoire_resp.data

        notes_resp = (
            supabase.table("harmony_notes")
            .select("*")
            .eq("repertoire_id", repertoire_id)
            .execute()
        )
        notes = notes_resp.data or []

        rules_resp = (
            supabase.table("harmony_rules")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        rules = rules_resp.data or []

        payload = {
            "analysis_id": analysis_id,
            "repertoire_id": repertoire_id,
            "customer_id": customer_id,
            "member_id": member_id,
            "repertoire": repertoire,
            "notes": notes,
            "rules": rules,
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{harmony_service_url}/analyze",
                json=payload,
                headers={"X-Internal-Service": "choir-director"},
            )
            response.raise_for_status()
            result = response.json()

        supabase.table("choirdir_harmony_analysis").update(
            {
                "status": "completed",
                "results": result.get("results", {}),
                "score": result.get("score"),
                "issues_count": result.get("issues_count", 0),
                "warnings_count": result.get("warnings_count", 0),
                "completed_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
        ).eq("id", analysis_id).execute()

        logger.info(
            f"Harmony analysis {analysis_id} completed for repertoire {repertoire_id}"
        )

    except httpx.HTTPError as e:
        logger.error(f"HTTP error during harmony analysis {analysis_id}: {e}")
        supabase.table("choirdir_harmony_analysis").update(
            {
                "status": "failed",
                "error_message": f"HTTP error: {str(e)}",
                "updated_at": datetime.utcnow().isoformat(),
            }
        ).eq("id", analysis_id).execute()

    except Exception as e:
        logger.error(f"Error during harmony analysis {analysis_id}: {e}")
        supabase.table("choirdir_harmony_analysis").update(
            {
                "status": "failed",
                "error_message": str(e),
                "updated_at": datetime.utcnow().isoformat(),
            }
        ).eq("id", analysis_id).execute()


@router.post("/analyze/{repertoire_id}")
async def trigger_harmony_analysis(
    repertoire_id: str,
    background_tasks: BackgroundTasks,
    current_member: dict = Depends(get_current_member),
):
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")
    member_id = current_member.get("id")

    if not customer_id:
        raise HTTPException(status_code=400, detail="Member has no associated customer")

    repertoire_resp = (
        supabase.table("repertoire")
        .select("id, title, customer_id")
        .eq("id", repertoire_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not repertoire_resp.data:
        raise HTTPException(
            status_code=404,
            detail=f"Repertoire piece {repertoire_id} not found or access denied",
        )

    pending_resp = (
        supabase.table("choirdir_harmony_analysis")
        .select("id, status")
        .eq("repertoire_id", repertoire_id)
        .eq("customer_id", customer_id)
        .in_("status", ["pending", "processing"])
        .execute()
    )

    if pending_resp.data:
        existing = pending_resp.data[0]
        return {
            "message": "Analysis already in progress",
            "analysis_id": existing["id"],
            "status": existing["status"],
        }

    now = datetime.utcnow().isoformat()
    analysis_data = {
        "repertoire_id": repertoire_id,
        "customer_id": customer_id,
        "triggered_by": member_id,
        "status": "pending",
        "results": None,
        "score": None,
        "issues_count": 0,
        "warnings_count": 0,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }

    insert_resp = (
        supabase.table("choirdir_harmony_analysis").insert(analysis_data).execute()
    )

    if not insert_resp.data:
        raise HTTPException(
            status_code=500, detail="Failed to create harmony analysis record"
        )

    analysis_id = insert_resp.data[0]["id"]

    supabase.table("choirdir_harmony_analysis").update(
        {"status": "processing", "updated_at": datetime.utcnow().isoformat()}
    ).eq("id", analysis_id).execute()

    background_tasks.add_task(
        dispatch_harmony_analysis,
        repertoire_id=repertoire_id,
        customer_id=customer_id,
        member_id=member_id,
        analysis_id=analysis_id,
    )

    return {
        "message": "Harmony analysis triggered successfully",
        "analysis_id": analysis_id,
        "status": "processing",
        "repertoire_id": repertoire_id,
    }


@router.get("/analysis/{repertoire_id}")
async def get_latest_analysis(
    repertoire_id: str,
    current_member: dict = Depends(get_current_member),
):
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")

    if not customer_id:
        raise HTTPException(status_code=400, detail="Member has no associated customer")

    repertoire_resp = (
        supabase.table("repertoire")
        .select("id")
        .eq("id", repertoire_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not repertoire_resp.data:
        raise HTTPException(
            status_code=404,
            detail=f"Repertoire piece {repertoire_id} not found or access denied",
        )

    analysis_resp = (
        supabase.table("choirdir_harmony_analysis")
        .select("*")
        .eq("repertoire_id", repertoire_id)
        .eq("customer_id", customer_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not analysis_resp.data:
        raise HTTPException(
            status_code=404,
            detail=f"No harmony analysis found for repertoire {repertoire_id}",
        )

    return {"analysis": analysis_resp.data[0]}


@router.get("/analysis")
async def list_all_analyses(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_member: dict = Depends(get_current_member),
):
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")

    if not customer_id:
        raise HTTPException(status_code=400, detail="Member has no associated customer")

    query = (
        supabase.table("choirdir_harmony_analysis")
        .select(
            "id, repertoire_id, status, score, issues_count, warnings_count, "
            "triggered_by, created_at, updated_at, completed_at, error_message"
        )
        .eq("customer_id", customer_id)
    )

    if status:
        valid_statuses = ["pending", "processing", "completed", "failed"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )
        query = query.eq("status", status)

    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    analyses_resp = query.execute()

    analyses = analyses_resp.data or []

    repertoire_ids = list({a["repertoire_id"] for a in analyses})
    repertoire_map: Dict[str, Any] = {}

    if repertoire_ids:
        rep_resp = (
            supabase.table("repertoire")
            .select("id, title, composer, arranger")
            .in_("id", repertoire_ids)
            .execute()
        )
        if rep_resp.data:
            for rep in rep_resp.data:
                repertoire_map[rep["id"]] = rep

    enriched = []
    for analysis in analyses:
        enriched_item = dict(analysis)
        enriched_item["repertoire"] = repertoire_map.get(analysis["repertoire_id"])
        enriched.append(enriched_item)

    return {
        "analyses": enriched,
        "total": len(enriched),
        "limit": limit,
        "offset": offset,
    }


@router.post("/voice-check")
async def voice_range_check(
    request: VoiceCheckRequest,
    current_member: dict = Depends(get_current_member),
):
    if not request.notes:
        raise HTTPException(status_code=400, detail="No notes provided for voice check")

    issues: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    supabase = get_service_client()
    rules_resp = (
        supabase.table("harmony_rules")
        .select("*")
        .eq("is_active", True)
        .eq("rule_type", "voice_range")
        .execute()
    )
    custom_rules = rules_resp.data or []

    custom_ranges: Dict[str, Dict[str, int]] = {}
    for rule in custom_rules:
        rule_params = rule.get("parameters", {})
        if isinstance(rule_params, dict):
            voice_part = rule_params.get("voice_part")
            if voice_part and "min_midi" in rule_params and "max_midi" in rule_params:
                custom_ranges[voice_part.lower()] = {
                    "min": rule_params["min_midi"],
                    "max": rule_params["max_midi"],
                }

    voice_part_notes: Dict[str, List[int]] = {}

    for note_item in request.notes:
        midi_note = note_item.midi_note
        voice_part = note_item.voice_part.lower()
        note_name = midi_to_note_name(midi_note)

        if voice_part not in voice_part_notes:
            voice_part_notes[voice_part] = []
        voice_part_notes[voice_part].append(midi_note)

        ranges = custom_ranges.get(voice_part) or VOICE_RANGES.get(voice_part)

        if ranges is None:
            issues.append(
                {
                    "type": "unknown_voice_part",
                    "severity": "warning",
                    "voice_part": voice_part,
                    "midi_note": midi_note,
                    "note_name": note_name,
                    "message": f"Unknown voice part '{voice_part}'. Cannot validate range.",
                }
            )
            continue

        range_min = ranges["min"]
        range_max = ranges["max"]
        comfort_min = range_min + 2
        comfort_max = range_max - 2

        if midi_note < range_min:
            issues.append(
                {
                    "type": "note_below_range",
                    "severity": "error",
                    "voice_part": voice_part,
                    "midi_note": midi_note,
                    "note_name": note_name,
                    "range_min": range_min,
                    "range_max": range_max,
                    "range_min_name": midi_to_note_name(range_min),
                    "range_max_name": midi_to_note_name(range_max),
                    "message": (
                        f"Note {note_name} is below the {voice_part} range "
                        f"({midi_to_note_name(range_min)}-{midi_to_note_name(range_max)})"
                    ),
                }
            )
        elif midi_note > range_max:
            issues.append(
                {
                    "type": "note_above_range",
                    "severity": "error",
                    "voice_part": voice_part,
                    "midi_note": midi_note,
                    "note_name": note_name,
                    "range_min": range_min,
                    "range_max": range_max,
                    "range_min_name": midi_to_note_name(range_min),
                    "range_max_name": midi_to_note_name(range_max),
                    "message": (
                        f"Note {note_name} is above the {voice_part} range "
                        f"({midi_to_note_name(range_min)}-{midi_to_note_name(range_max)})"
                    ),
                }
            )
        elif midi_note < comfort_min:
            warnings.append(
                {
                    "type": "note_low_comfort",
                    "severity": "warning",
                    "voice_part": voice_part,
                    "midi_note": midi_note,
                    "note_name": note_name,
                    "message": (
                        f"Note {note_name} is at the lower edge of comfortable "
                        f"{voice_part} range - may strain some singers"
                    ),
                }
            )
        elif midi_note > comfort_max:
            warnings.append(
                {
                    "type": "note_high_comfort",
                    "severity": "warning",
                    "voice_part": voice_part,
                    "midi_note": midi_note,
                    "note_name": note_name,
                    "message": (
                        f"Note {note_name} is at the upper edge of comfortable "
                        f"{voice_part} range - may strain some singers"
                    ),
                }
            )

    for voice_part, notes in voice_part_notes.items():
        if len(notes) < 2:
            continue
        span = max(notes) - min(notes)
        if span > 19:
            warnings.append(
                {
                    "type": "large_vocal_leap",
                    "severity": "warning",
                    "voice_part": voice_part,
                    "span_semitones": span,
                    "message": (
                        f"{voice_part.capitalize()} part has a span of {span} semitones - "
                        f"consider if all singers can manage this range"
                    ),
                }
            )

    summary = {
        "total_notes_checked": len(request.notes),
        "error_count": len(issues),
        "warning_count": len(warnings),
        "voice_parts_checked": list(voice_part_notes.keys()),
        "passed": len(issues) == 0,
    }

    return {
        "summary": summary,
        "issues": issues,
        "warnings": warnings,
    }


@router.get("/rules")
async def list_harmony_rules(
    rule_type: Optional[str] = None,
    current_member: dict = Depends(get_current_member),
):
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")

    if not customer_id:
        raise HTTPException(status_code=400, detail="Member has no associated customer")

    query = (
        supabase.table("harmony_rules")
        .select("*")
        .eq("is_active", True)
        .order("rule_type")
        .order("name")
    )

    if rule_type:
        query = query.eq("rule_type", rule_type)

    global_resp = query.execute()
    global_rules = global_resp.data or []

    customer_query = (
        supabase.table("harmony_rules")
        .select("*")
        .eq("is_active", True)
        .eq("customer_id", customer_id)
        .order("rule_type")
        .order("name")
    )

    if rule_type:
        customer_query = customer_query.eq("rule_type", rule_type)

    customer_resp = customer_query.execute()
    customer_rules = customer_resp.data or []

    seen_ids = set()
    combined_rules = []

    for rule in customer_rules:
        if rule["id"] not in seen_ids:
            rule["scope"] = "customer"
            combined_rules.append(rule)
            seen_ids.add(rule["id"])

    for rule in global_rules:
        if rule["id"] not in seen_ids:
            rule["scope"] = "global"
            combined_rules.append(rule)
            seen_ids.add(rule["id"])

    rule_types = list({r["rule_type"] for r in combined_rules if r.get("rule_type")})

    return {
        "rules": combined_rules,
        "total": len(combined_rules),
        "rule_types": sorted(rule_types),
    }


@router.get("/renders/{project_id}")
async def list_project_renders(
    project_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_member: dict = Depends(get_current_member),
):
    supabase = get_service_client()
    customer_id = current_member.get("customer_id")

    if not customer_id:
        raise HTTPException(status_code=400, detail="Member has no associated customer")

    project_resp = (
        supabase.table("projects")
        .select("id, name, customer_id")
        .eq("id", project_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not project_resp.data:
        raise HTTPException(
            status_code=404,
            detail=f"Project {project_id} not found or access denied",
        )

    project = project_resp.data

    query = (
        supabase.table("harmony_renders")
        .select("*")
        .eq("project_id", project_id)
        .eq("customer_id", customer_id)
    )

    if status:
        valid_statuses = ["pending", "processing", "completed", "failed"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )
        query = query.eq("status", status)

    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    renders_resp = query.execute()
    renders = renders_resp.data or []

    targets_map: Dict[str, Any] = {}
    render_ids = [r["id"] for r in renders]

    if render_ids:
        targets_resp = (
            supabase.table("harmony_targets")
            .select("*")
            .in_("render_id", render_ids)
            .execute()
        )
        if targets_resp.data:
            for target in targets_resp.data:
                rid = target["render_id"]
                if rid not in targets_map:
                    targets_map[rid] = []
                targets_map[rid].append(target)

    enriched_renders = []
    for render in renders:
        enriched = dict(render)
        enriched["targets"] = targets_map.get(render["id"], [])
        enriched_renders.append(enriched)

    status_counts: Dict[str, int] = {}
    for render in renders:
        s = render.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "project": {"id": project["id"], "name": project.get("name")},
        "renders": enriched_renders,
        "total": len(enriched_renders),
        "limit": limit,
        "offset": offset,
        "status_summary": status_counts,
    }
