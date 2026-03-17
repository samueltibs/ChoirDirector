from datetime import datetime, timezone
from typing import Optional
from ..config import get_settings

settings = get_settings()


async def send_notification(
    customer_id: str,
    recipient_id: str,
    channel: str,
    notify_type: str,
    subject: str,
    body: str,
    payload: dict,
    service_client,
) -> str:
    """
    Inserts a notification record into choirdir_bisa_notify with status=pending.
    Returns the notification id.
    """
    data = {
        "customer_id": customer_id,
        "recipient_id": recipient_id,
        "channel": channel,
        "notify_type": notify_type,
        "subject": subject,
        "body": body,
        "payload": payload,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    response = (
        service_client.table("choirdir_bisa_notify")
        .insert(data)
        .execute()
    )

    if not response.data:
        raise ValueError("Failed to insert notification record")

    return response.data[0]["id"]


async def notify_rehearsal_reminder(
    customer_id: str,
    event_id: str,
    service_client,
) -> list:
    """
    Fetches event details and sends rehearsal reminder notifications to all active members.
    Returns list of notification ids.
    """
    event_response = (
        service_client.table("choirdir_events")
        .select("*")
        .eq("id", event_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not event_response.data:
        raise ValueError(f"Event {event_id} not found")

    event = event_response.data

    members_response = (
        service_client.table("choirdir_members")
        .select("*")
        .eq("customer_id", customer_id)
        .eq("status", "active")
        .execute()
    )

    members = members_response.data or []

    event_title = event.get("title", "Rehearsal")
    event_date = event.get("start_time") or event.get("event_date", "")
    event_location = event.get("location", "")

    notification_ids = []
    for member in members:
        subject = f"Rehearsal Reminder: {event_title}"
        body = (
            f"Dear {member.get('first_name', 'Member')},\n\n"
            f"This is a reminder about the upcoming rehearsal:\n"
            f"Event: {event_title}\n"
            f"Date/Time: {event_date}\n"
            f"Location: {event_location}\n\n"
            f"Please make sure to attend and be prepared.\n\n"
            f"Best regards,\nChoir Director"
        )
        payload = {
            "event_id": event_id,
            "event_title": event_title,
            "event_date": event_date,
            "event_location": event_location,
        }

        notification_id = await send_notification(
            customer_id=customer_id,
            recipient_id=member["id"],
            channel="email",
            notify_type="rehearsal_reminder",
            subject=subject,
            body=body,
            payload=payload,
            service_client=service_client,
        )
        notification_ids.append(notification_id)

    return notification_ids


async def notify_practice_assignment(
    customer_id: str,
    assignment_id: str,
    service_client,
) -> list:
    """
    Fetches assignment and target members, sends notifications to each target member.
    Returns list of notification ids.
    """
    assignment_response = (
        service_client.table("choirdir_practice_assignments")
        .select("*")
        .eq("id", assignment_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not assignment_response.data:
        raise ValueError(f"Assignment {assignment_id} not found")

    assignment = assignment_response.data

    target_member_ids = assignment.get("member_ids") or []

    if not target_member_ids:
        voice_part = assignment.get("voice_part")
        if voice_part:
            members_query = (
                service_client.table("choirdir_members")
                .select("*")
                .eq("customer_id", customer_id)
                .eq("status", "active")
                .eq("voice_part", voice_part)
            )
        else:
            members_query = (
                service_client.table("choirdir_members")
                .select("*")
                .eq("customer_id", customer_id)
                .eq("status", "active")
            )
        members_response = members_query.execute()
        members = members_response.data or []
    else:
        members_response = (
            service_client.table("choirdir_members")
            .select("*")
            .eq("customer_id", customer_id)
            .in_("id", target_member_ids)
            .execute()
        )
        members = members_response.data or []

    assignment_title = assignment.get("title", "Practice Assignment")
    due_date = assignment.get("due_date", "")
    description = assignment.get("description", "")

    notification_ids = []
    for member in members:
        subject = f"New Practice Assignment: {assignment_title}"
        body = (
            f"Dear {member.get('first_name', 'Member')},\n\n"
            f"You have been assigned a new practice task:\n"
            f"Assignment: {assignment_title}\n"
            f"Description: {description}\n"
            f"Due Date: {due_date}\n\n"
            f"Please complete this assignment before the due date.\n\n"
            f"Best regards,\nChoir Director"
        )
        payload = {
            "assignment_id": assignment_id,
            "assignment_title": assignment_title,
            "due_date": due_date,
        }

        notification_id = await send_notification(
            customer_id=customer_id,
            recipient_id=member["id"],
            channel="email",
            notify_type="practice_assignment",
            subject=subject,
            body=body,
            payload=payload,
            service_client=service_client,
        )
        notification_ids.append(notification_id)

    return notification_ids


async def notify_arrangement_complete(
    customer_id: str,
    request_id: str,
    service_client,
) -> str:
    """
    Notifies the requesting member that their arrangement is ready.
    Returns the notification id.
    """
    request_response = (
        service_client.table("choirdir_arrangement_requests")
        .select("*")
        .eq("id", request_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    if not request_response.data:
        raise ValueError(f"Arrangement request {request_id} not found")

    request = request_response.data
    requesting_member_id = request.get("member_id") or request.get("requested_by")

    if not requesting_member_id:
        raise ValueError(f"No requesting member found for arrangement request {request_id}")

    member_response = (
        service_client.table("choirdir_members")
        .select("*")
        .eq("id", requesting_member_id)
        .eq("customer_id", customer_id)
        .single()
        .execute()
    )

    member = member_response.data if member_response.data else {}

    arrangement_title = request.get("title") or request.get("song_title", "Your Arrangement")

    subject = f"Arrangement Ready: {arrangement_title}"
    body = (
        f"Dear {member.get('first_name', 'Member')},\n\n"
        f"Great news! Your requested arrangement is now ready:\n"
        f"Arrangement: {arrangement_title}\n\n"
        f"You can access your arrangement in the Choir Director platform.\n\n"
        f"Best regards,\nChoir Director"
    )
    payload = {
        "request_id": request_id,
        "arrangement_title": arrangement_title,
    }

    notification_id = await send_notification(
        customer_id=customer_id,
        recipient_id=requesting_member_id,
        channel="email",
        notify_type="arrangement_complete",
        subject=subject,
        body=body,
        payload=payload,
        service_client=service_client,
    )

    return notification_id


async def mark_notification_sent(
    notification_id: str,
    service_client,
) -> None:
    """
    Updates a notification record status to sent and sets sent_at timestamp.
    """
    update_data = {
        "status": "sent",
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }

    response = (
        service_client.table("choirdir_bisa_notify")
        .update(update_data)
        .eq("id", notification_id)
        .execute()
    )

    if not response.data:
        raise ValueError(f"Failed to update notification {notification_id} status to sent")
