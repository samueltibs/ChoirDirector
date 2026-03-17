from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

from ..config import get_settings
from ..database import get_service_client

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# SATB voice ranges  (MIDI note numbers)
# C4 = 60, G5 = 79, G3 = 55, E5 = 76, C3 = 48, G4 = 67, E2 = 40, E4 = 64
# ---------------------------------------------------------------------------
VOICE_RANGES: dict[str, tuple[int, int]] = {
    "soprano": (60, 79),
    "alto": (55, 76),
    "tenor": (48, 67),
    "bass": (40, 64),
}

VOICE_ORDER = ["soprano", "alto", "tenor", "bass"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _note_name_to_midi(note: str) -> int | None:
    """Convert a note name like 'C4', 'F#3', 'Bb5' to a MIDI number."""
    if not note:
        return None
    note_map = {
        "C": 0, "D": 2, "E": 4, "F": 5,
        "G": 7, "A": 9, "B": 11,
    }
    note = note.strip()
    i = 0
    letter = note[i].upper()
    i += 1
    accidental = 0
    while i < len(note) and note[i] in ("#", "b", "
def", "s"):
        if note[i] == "#" or note[i] == "s":
            accidental += 1
        elif note[i] == "b":
            accidental -= 1
        i += 1
    try:
        octave = int(note[i:])
    except (ValueError, IndexError):
        return None
    base = note_map.get(letter)
    if base is None:
        return None
    return (octave + 1) * 12 + base + accidental


def _interval_semitones(midi_a: int, midi_b: int) -> int:
    return abs(midi_a - midi_b)


def _is_perfect_fifth(interval: int) -> bool:
    return interval % 12 == 7


def _is_octave(interval: int) -> bool:
    return interval % 12 == 0 and interval != 0


def _is_unison(interval: int) -> bool:
    return interval == 0


def _direction(a: int, b: int) -> int:
    """Return 1 ascending, -1 descending, 0 static."""
    if b > a:
        return 1
    if b < a:
        return -1
    return 0


def _severity_label(count: int, threshold_warn: int, threshold_error: int) -> str:
    if count >= threshold_error:
        return "error"
    if count >= threshold_warn:
        return "warning"
    return "info"


# ---------------------------------------------------------------------------
# Core analysis functions
# ---------------------------------------------------------------------------

def check_parallel_motion(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Detect parallel fifths and octaves between adjacent voice pairs.

    Expected note dict keys: voice, measure, beat, midi (or note_name).
    Returns a list of issue dicts.
    """
    issues: list[dict[str, Any]] = []

    # Group notes by measure then beat
    by_measure_beat: dict[tuple[int, float], dict[str, int]] = {}
    for n in notes:
        midi = n.get("midi")
        if midi is None:
            midi = _note_name_to_midi(n.get("note_name", ""))
        if midi is None:
            continue
        voice = n.get("voice", "").lower()
        measure = int(n.get("measure", 0))
        beat = float(n.get("beat", 1))
        key = (measure, beat)
        by_measure_beat.setdefault(key, {})[voice] = midi

    sorted_keys = sorted(by_measure_beat.keys())
    voice_pairs = [
        ("soprano", "alto"),
        ("soprano", "tenor"),
        ("soprano", "bass"),
        ("alto", "tenor"),
        ("alto", "bass"),
        ("tenor", "bass"),
    ]

    for idx in range(1, len(sorted_keys)):
        prev_key = sorted_keys[idx - 1]
        curr_key = sorted_keys[idx]
        prev_chord = by_measure_beat[prev_key]
        curr_chord = by_measure_beat[curr_key]

        for v1, v2 in voice_pairs:
            if v1 not in prev_chord or v2 not in prev_chord:
                continue
            if v1 not in curr_chord or v2 not in curr_chord:
                continue

            prev_interval = _interval_semitones(prev_chord[v1], prev_chord[v2])
            curr_interval = _interval_semitones(curr_chord[v1], curr_chord[v2])

            # Both voices must move in the same direction
            dir_v1 = _direction(prev_chord[v1], curr_chord[v1])
            dir_v2 = _direction(prev_chord[v2], curr_chord[v2])

            if dir_v1 == 0 or dir_v2 == 0:
                continue  # oblique motion â not parallel
            if dir_v1 != dir_v2:
                continue  # contrary motion â fine

            measure_num = curr_key[0]

            if _is_perfect_fifth(prev_interval) and _is_perfect_fifth(curr_interval):
                issues.append({
                    "type": "parallel_fifths",
                    "measure": measure_num,
                    "beat": curr_key[1],
                    "voice": f"{v1}/{v2}",
                    "description": (
                        f"Parallel fifths between {v1} and {v2} "
                        f"approaching measure {measure_num} beat {curr_key[1]}."
                    ),
                    "severity": "error",
                })
            elif (
                (_is_octave(prev_interval) or _is_unison(prev_interval))
                and (_is_octave(curr_interval) or _is_unison(curr_interval))
            ):
                issues.append({
                    "type": "parallel_octaves",
                    "measure": measure_num,
                    "beat": curr_key[1],
                    "voice": f"{v1}/{v2}",
                    "description": (
                        f"Parallel octaves/unisons between {v1} and {v2} "
                        f"approaching measure {measure_num} beat {curr_key[1]}."
                    ),
                    "severity": "error",
                })

    return issues


def check_voice_crossing(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Soprano 
def Alto 
def Tenor 
def Bass at every rhythmic position.
    Returns a list of issue dicts.
    """
    issues: list[dict[str, Any]] = []

    by_measure_beat: dict[tuple[int, float], dict[str, int]] = {}
    for n in notes:
        midi = n.get("midi")
        if midi is None:
            midi = _note_name_to_midi(n.get("note_name", ""))
        if midi is None:
            continue
        voice = n.get("voice", "").lower()
        measure = int(n.get("measure", 0))
        beat = float(n.get("beat", 1))
        key = (measure, beat)
        by_measure_beat.setdefault(key, {})[voice] = midi

    crossing_rules = [
        ("soprano", "alto", "Soprano below Alto"),
        ("alto", "tenor", "Alto below Tenor"),
        ("tenor", "bass", "Tenor below Bass"),
    ]

    for (measure, beat), chord in sorted(by_measure_beat.items()):
        for upper_voice, lower_voice, label in crossing_rules:
            if upper_voice not in chord or lower_voice not in chord:
                continue
            if chord[upper_voice] < chord[lower_voice]:
                issues.append({
                    "type": "voice_crossing",
                    "measure": measure,
                    "beat": beat,
                    "voice": f"{upper_voice}/{lower_voice}",
                    "description": (
                        f"{label} at measure {measure} beat {beat}."
                    ),
                    "severity": "warning",
                })

    return issues


def check_voice_ranges(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Check each note falls within the standard SATB range.
    Returns a list of issue dicts.
    """
    issues: list[dict[str, Any]] = []

    for n in notes:
        voice = n.get("voice", "").lower()
        if voice not in VOICE_RANGES:
            continue
        midi = n.get("midi")
        if midi is None:
            midi = _note_name_to_midi(n.get("note_name", ""))
        if midi is None:
            continue

        lo, hi = VOICE_RANGES[voice]
        measure = int(n.get("measure", 0))
        beat = float(n.get("beat", 1))

        if midi < lo:
            issues.append({
                "type": "out_of_range_low",
                "measure": measure,
                "beat": beat,
                "voice": voice,
                "description": (
                    f"{voice.capitalize()} note at measure {measure} beat {beat} "
                    f"is below standard range (MIDI {midi} < {lo})."
                ),
                "severity": "warning",
            })
        elif midi > hi:
            issues.append({
                "type": "out_of_range_high",
                "measure": measure,
                "beat": beat,
                "voice": voice,
                "description": (
                    f"{voice.capitalize()} note at measure {measure} beat {beat} "
                    f"is above standard range (MIDI {midi} > {hi})."
                ),
                "severity": "warning",
            })

    return issues


def _check_large_leaps(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag melodic leaps larger than an octave (13+ semitones)."""
    issues: list[dict[str, Any]] = []

    # Group by voice and sort by measure/beat
    by_voice: dict[str, list[dict[str, Any]]] = {}
    for n in notes:
        voice = n.get("voice", "").lower()
        midi = n.get("midi")
        if midi is None:
            midi = _note_name_to_midi(n.get("note_name", ""))
        if midi is None:
            continue
        entry = dict(n)
        entry["_midi"] = midi
        by_voice.setdefault(voice, []).append(entry)

    for voice, vnotes in by_voice.items():
        sorted_notes = sorted(
            vnotes,
            key=lambda x: (int(x.get("measure", 0)), float(x.get("beat", 1))),
        )
        for i in range(1, len(sorted_notes)):
            prev = sorted_notes[i - 1]
            curr = sorted_notes[i]
            leap = _interval_semitones(prev["_midi"], curr["_midi"])
            if leap > 12:  # more than an octave
                measure = int(curr.get("measure", 0))
                beat = float(curr.get("beat", 1))
                issues.append({
                    "type": "large_leap",
                    "measure": measure,
                    "beat": beat,
                    "voice": voice,
                    "description": (
                        f"{voice.capitalize()} makes a leap of {leap} semitones "
                        f"at measure {measure} beat {beat} (>octave)."
                    ),
                    "severity": "warning",
                })

    return issues


def _check_leading_tones(
    notes: list[dict[str, Any]],
    key_midi: int = 60,  # default C major â tonic = C4
) -> list[dict[str, Any]]:
    """
    Detect unresolved leading tones (semitone below tonic that don't resolve upward).
    leading_tone_midi = key_midi - 1 (mod 12).
    """
    issues: list[dict[str, Any]] = []
    leading_tone_pc = (key_midi - 1) % 12  # pitch class
    tonic_pc = key_midi % 12

    by_voice: dict[str, list[dict[str, Any]]] = {}
    for n in notes:
        voice = n.get("voice", "").lower()
        midi = n.get("midi")
        if midi is None:
            midi = _note_name_to_midi(n.get("note_name", ""))
        if midi is None:
            continue
        entry = dict(n)
        entry["_midi"] = midi
        by_voice.setdefault(voice, []).append(entry)

    for voice, vnotes in by_voice.items():
        sorted_notes = sorted(
            vnotes,
            key=lambda x: (int(x.get("measure", 0)), float(x.get("beat", 1))),
        )
        for i, curr in enumerate(sorted_notes):
            if curr["_midi"] % 12 == leading_tone_pc:
                # Check next note
                if i + 1 < len(sorted_notes):
                    nxt = sorted_notes[i + 1]
                    if nxt["_midi"] % 12 != tonic_pc:
                        measure = int(curr.get("measure", 0))
                        beat = float(curr.get("beat", 1))
                        issues.append({
                            "type": "unresolved_leading_tone",
                            "measure": measure,
                            "beat": beat,
                            "voice": voice,
                            "description": (
                                f"{voice.capitalize()} has an unresolved leading tone "
                                f"at measure {measure} beat {beat} â "
                                f"expected resolution to tonic."
                            ),
                            "severity": "warning",
                        })
                else:
                    # Last note is a leading tone â cannot tell, flag as info
                    measure = int(curr.get("measure", 0))
                    beat = float(curr.get("beat", 1))
                    issues.append({
                        "type": "unresolved_leading_tone",
                        "measure": measure,
                        "beat": beat,
                        "voice": voice,
                        "description": (
                            f"{voice.capitalize()} ends on a leading tone "
                            f"at measure {measure} beat {beat} with no following note."
                        ),
                        "severity": "info",
                    })

    return issues


def _compute_score(issues: list[dict[str, Any]]) -> int:
    """Compute a 0-100 harmony score from the issue list."""
    deductions = {"error": 10, "warning": 4, "info": 1}
    total_deduction = sum(deductions.get(i.get("severity", "info"), 1) for i in issues)
    score = max(0, 100 - total_deduction)
    return score


def _generate_suggestions(issues: list[dict[str, Any]]) -> list[str]:
    """Generate human-readable suggestions based on detected issues."""
    type_counts: dict[str, int] = {}
    for issue in issues:
        t = issue.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    suggestions: list[str] = []

    if type_counts.get("parallel_fifths", 0):
        suggestions.append(
            f"Found {type_counts['parallel_fifths']} instance(s) of parallel fifths. "
            "Use contrary or oblique motion between voice pairs to avoid parallel perfect intervals."
        )
    if type_counts.get("parallel_octaves", 0):
        suggestions.append(
            f"Found {type_counts['parallel_octaves']} instance(s) of parallel octaves/unisons. "
            "Ensure voices move independently by using contrary motion."
        )
    if type_counts.get("voice_crossing", 0):
        suggestions.append(
            f"Found {type_counts['voice_crossing']} instance(s) of voice crossing. "
            "Maintain proper voice ordering: Soprano above Alto, Alto above Tenor, Tenor above Bass."
        )
    if type_counts.get("out_of_range_low", 0) or type_counts.get("out_of_range_high", 0):
        total_range = type_counts.get("out_of_range_low", 0) + type_counts.get("out_of_range_high", 0)
        suggestions.append(
            f"{total_range} note(s) fall outside standard SATB ranges. "
            "Consider transposing or adjusting tessitura for singer comfort."
        )
    if type_counts.get("large_leap", 0):
        suggestions.append(
            f"{type_counts['large_leap']} melodic leap(s) exceed an octave. "
            "Large leaps can be difficult to sing accurately; consider stepwise alternatives or smaller intervals."
        )
    if type_counts.get("unresolved_leading_tone", 0):
        suggestions.append(
            f"{type_counts['unresolved_leading_tone']} unresolved leading tone(s) detected. "
            "Leading tones should resolve upward by a semitone to the tonic."
        )

    if not suggestions:
        suggestions.append(
            "No significant harmony issues detected. The arrangement follows standard voice-leading principles."
        )

    return suggestions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_voice_leading(
    project_id: str,
    customer_id: str,
) -> dict[str, Any]:
    """
    Full voice-leading analysis for a project.

    Fetches harmony_notes, runs all checks, persists to
    choirdir_harmony_analysis, and returns the result dict.
    """
    client = get_service_client()

    # ------------------------------------------------------------------
    # Fetch harmony notes
    # ------------------------------------------------------------------
    notes_resp = (
        client
        .table("choirdir_harmony_notes")
        .select("*")
        .eq("project_id", project_id)
        .eq("customer_id", customer_id)
        .execute()
    )

    notes: list[dict[str, Any]] = notes_resp.data or []

    if not notes:
        logger.warning(
            "analyze_voice_leading: no harmony notes found for project %s",
            project_id,
        )
        return {
            "project_id": project_id,
            "score": None,
            "issues": [],
            "suggestions": ["No harmony notes found for this project. Add notes to enable analysis."],
            "note_count": 0,
            "analysed_at": None,
        }

    # ------------------------------------------------------------------
    # Fetch harmony rules (optional â for future rule-driven checks)
    # ------------------------------------------------------------------
    rules_resp = (
        client
        .table("choirdir_harmony_rules")
        .select("*")
        .eq("customer_id", customer_id)
        .execute()
    )
    rules: list[dict[str, Any]] = rules_resp.data or []

    # Extract key_midi from rules if present
    key_midi = 60  # default C4
    for rule in rules:
        if rule.get("rule_type") == "key_midi" and rule.get("value"):
            try:
                key_midi = int(rule["value"])
            except (TypeError, ValueError):
                pass

    # ------------------------------------------------------------------
    # Run checks
    # ------------------------------------------------------------------
    all_issues: list[dict[str, Any]] = []
    all_issues.extend(check_parallel_motion(notes))
    all_issues.extend(check_voice_crossing(notes))
    all_issues.extend(check_voice_ranges(notes))
    all_issues.extend(_check_large_leaps(notes))
    all_issues.extend(_check_leading_tones(notes, key_midi=key_midi))

    # Sort issues by measure then beat
    all_issues.sort(key=lambda x: (x.get("measure", 0), x.get("beat", 0)))

    score = _compute_score(all_issues)
    suggestions = _generate_suggestions(all_issues)
    analysed_at = datetime.now(timezone.utc).isoformat()

    result = {
        "project_id": project_id,
        "customer_id": customer_id,
        "score": score,
        "issues": all_issues,
        "suggestions": suggestions,
        "note_count": len(notes),
        "issue_count": len(all_issues),
        "analysed_at": analysed_at,
    }

    # ------------------------------------------------------------------
    # Persist result
    # ------------------------------------------------------------------
    try:
        upsert_payload = {
            "project_id": project_id,
            "customer_id": customer_id,
            "score": score,
            "issues": all_issues,
            "suggestions": suggestions,
            "note_count": len(notes),
            "issue_count": len(all_issues),
            "analysed_at": analysed_at,
        }
        client.table("choirdir_harmony_analysis").upsert(
            upsert_payload,
            on_conflict="project_id,customer_id",
        ).execute()
    except Exception as exc:
        logger.error(
            "analyze_voice_leading: failed to persist analysis for project %s: %s",
            project_id,
            exc,
        )

    return result


async def get_analysis_for_repertoire(
    repertoire_id: str,
    customer_id: str,
) -> dict[str, Any]:
    """
    Fetch existing harmony analysis for a repertoire item.
    Returns an empty result with a hint if none exists.
    """
    client = get_service_client()

    # harmony_analysis may be linked by repertoire_id (alias for project_id)
    resp = (
        client
        .table("choirdir_harmony_analysis")
        .select("*")
        .eq("project_id", repertoire_id)
        .eq("customer_id", customer_id)
        .order("analysed_at", desc=True)
        .limit(1)
        .execute()
    )

    rows: list[dict[str, Any]] = resp.data or []

    if not rows:
        return {
            "repertoire_id": repertoire_id,
            "score": None,
            "issues": [],
            "suggestions": [
                "No harmony analysis found for this repertoire item. "
                "Run analyze_voice_leading to generate an analysis."
            ],
            "note_count": 0,
            "issue_count": 0,
            "analysed_at": None,
            "exists": False,
        }

    row = rows[0]
    return {
        "repertoire_id": repertoire_id,
        "project_id": row.get("project_id"),
        "score": row.get("score"),
        "issues": row.get("issues", []),
        "suggestions": row.get("suggestions", []),
        "note_count": row.get("note_count", 0),
        "issue_count": row.get("issue_count", 0),
        "analysed_at": row.get("analysed_at"),
        "exists": True,
    }
