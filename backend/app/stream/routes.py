"""GET /api/stream (R9): this attendee's live updates as Server-Sent Events.

On connect it sends the latest placement first, so a phone that reconnected
after an API restart is up to date at once. Then it sends each new
notification: placed -> "placement", moved -> "reroute", group -> "group".
A comment every 15 seconds keeps proxies from closing the connection.
"""

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from opentelemetry import trace
from starlette.concurrency import run_in_threadpool

from app.auth import attendee_hash, current_attendee_id
from app.db import pool
from app.es import get_es
from app.stream.hub import hub
from app.telemetry.attrs import set_attrs

router = APIRouter()
tracer = trace.get_tracer("affinity")
EVENT_TYPES = {"placed": "placement", "moved": "reroute", "group": "group"}
HEARTBEAT_SECONDS = 15


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def latest_placement(attendee_id: str, es) -> dict | None:
    from app.placements.routes import to_response

    with pool().connection() as conn:
        row = conn.execute(
            "SELECT attendee_id, slot, pod_name, status, node, reason, scheduler_message, options"
            " FROM placements WHERE attendee_id = %s ORDER BY updated_at DESC LIMIT 1", (attendee_id,)).fetchone()
    return to_response(row, es) if row else None


def notification_event(attendee_id: str, notification_id: int, es) -> str | None:
    with pool().connection() as conn:
        row = conn.execute("SELECT kind, payload FROM notifications WHERE id = %s AND attendee_id = %s",
                           (notification_id, attendee_id)).fetchone()
    if row is None:
        return None
    kind, payload = row
    event = EVENT_TYPES.get(kind)
    if event is None:
        return None
    if event in ("placement", "reroute"):
        placement = latest_placement(attendee_id, es) or {}
        return sse(event, {**placement, "id": notification_id, "eventId": notification_id})
    return sse(event, {**payload, "id": payload.get("group", notification_id), "eventId": notification_id})


@router.get("/api/stream")
async def stream(request: Request, attendee_id: str = Depends(current_attendee_id), es=Depends(get_es)):
    queue = hub.subscribe(attendee_id)

    async def events():
        try:
            first = await run_in_threadpool(latest_placement, attendee_id, es)
            if first:
                yield sse("placement", first)
            while not await request.is_disconnected():
                try:
                    notification_id = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                with tracer.start_as_current_span("notification.sent") as span:
                    set_attrs(span, attendee_hash=attendee_hash(attendee_id))
                    message = await run_in_threadpool(notification_event, attendee_id, notification_id, es)
                if message:
                    yield message
        finally:
            hub.unsubscribe(attendee_id, queue)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
