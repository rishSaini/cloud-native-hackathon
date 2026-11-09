"""POST /api/rooms/{room_id}/reports (K9)."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from opentelemetry import metrics, trace
from pydantic import BaseModel, Field

from app.auth import attendee_hash, current_attendee_id
from app.es import get_es
from app.reports.ingest import SIGNALS, recently_reported, record_report
from app.telemetry.attrs import set_attrs

router = APIRouter()
tracer = trace.get_tracer("affinity")
reports_total = metrics.get_meter("affinity").create_counter(
    "talkscout.room_reports", description="Room reports accepted, by signal"
)

Signal = Literal[SIGNALS]  # type: ignore[valid-type]


class ReportIn(BaseModel):
    signal: Signal
    slot: str | None = Field(None, pattern=r"^[a-z]{3}-\d{4}$")


def recompute_state(room: str, es):
    """Run K10's room-state engine (inline, so one request can flip the room)."""
    from app.reports.state import recompute

    return recompute(room, es=es)


@router.post("/api/rooms/{room_id}/reports", status_code=status.HTTP_202_ACCEPTED)
def report_room(
    body: ReportIn,
    room_id: str = Path(pattern=r"^room-[a-z0-9-]{1,30}$"),
    attendee_id: str = Depends(current_attendee_id),
    es=Depends(get_es),
):
    reporter = attendee_hash(attendee_id)
    with tracer.start_as_current_span("talkscout.room.report.received") as span:
        set_attrs(span, room_id=room_id, report_signal=body.signal, attendee_hash=reporter)
        if recently_reported(es, room_id, body.signal, reporter):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="You reported this for this room in the last 2 minutes.",
            )
        record_report(es, room_id, body.signal, reporter, body.slot)
        reports_total.add(1, {"report.signal": body.signal})
        state = recompute_state(room_id, es)
    return {"accepted": True, "room": room_id, "signal": body.signal, "state": state}
