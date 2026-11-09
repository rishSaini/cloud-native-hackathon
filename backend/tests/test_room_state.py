"""K10: decay, hysteresis and the room-state write."""

from datetime import datetime, timedelta, timezone

import pytest

from app.reports import state

NOW = datetime(2026, 11, 10, 14, 30, tzinfo=timezone.utc)


def agg(signal_minutes: dict[str, list[tuple[int, int]]]) -> dict:
    """signal -> [(minutes ago, count)] as an ES aggregation response."""
    buckets = []
    for sig, minutes in signal_minutes.items():
        per = [{"key": (NOW - timedelta(minutes=ago + 0.5)).timestamp() * 1000 + 0, "doc_count": n} for ago, n in minutes]
        buckets.append({"key": sig, "per_minute": {"buckets": per}})
    return {"signals": {"buckets": buckets}}


def test_fresh_reports_count_fully_and_old_ones_fade():
    assert state.confidences(agg({"full": [(0, 3)]}), NOW)["full"] == pytest.approx(3.0, abs=0.01)
    assert state.confidences(agg({"full": [(10, 3)]}), NOW)["full"] == pytest.approx(3 / 2.718, abs=0.02)


def test_three_full_reports_make_a_room_full():
    assert state.derive({}, {"full": 3.0})["status"] == "full"
    assert state.derive({}, {"full": 2.0})["status"] == "open"


def test_hysteresis_keeps_full_until_below_clear_threshold():
    full = {"status": "full"}
    assert state.derive(full, {"full": 1.5})["status"] == "full"  # between thresholds: stays
    assert state.derive({"status": "open"}, {"full": 1.5})["status"] == "open"  # does not flip on
    assert state.derive(full, {"full": 0.9})["status"] == "open"


def test_full_clears_about_eleven_minutes_after_three_reports():
    def status_after(minutes):
        conf = state.confidences(agg({"full": [(minutes, 3)]}), NOW)
        return state.derive({"status": "full"}, conf)["status"]

    assert status_after(9) == "full"
    assert status_after(12) == "open"


def test_seats_available_counts_against_full():
    assert state.derive({"status": "full"}, {"full": 3.0, "seats_available": 2.5})["status"] == "open"


def test_closed_stays_closed():
    assert state.derive({"status": "closed"}, {"seats_available": 5.0})["status"] == "closed"


def test_captions_states():
    assert state.derive({}, {"captions_down": 3.0})["signals"]["captions"] == "down"
    assert state.derive({}, {"captions_working": 1.0})["signals"]["captions"] == "working"
    assert state.derive({}, {})["signals"]["captions"] == "unknown"
    was_down = {"signals": {"captions": "down"}}
    assert state.derive(was_down, {"captions_down": 1.2})["signals"]["captions"] == "down"


class FakeStateES:
    def __init__(self, prev=None, aggregation=None):
        self.prev = prev
        self.aggregation = aggregation or {"signals": {"buckets": []}}
        self.updates = []

    def get(self, index, id):
        if self.prev is None:
            from elastic_transport import ApiResponseMeta, HttpHeaders
            from elasticsearch import NotFoundError

            meta = ApiResponseMeta(status=404, http_version="1.1", headers=HttpHeaders(), duration=0.0, node=None)
            raise NotFoundError("missing", meta=meta, body={})
        return {"_source": self.prev}

    def search(self, index, **kwargs):
        return {"aggregations": self.aggregation}

    def update(self, index, id, doc, doc_as_upsert, refresh):
        self.updates.append((id, doc, doc_as_upsert))


def test_recompute_writes_only_karthiks_fields_on_change(monkeypatch):
    es = FakeStateES(prev={"room": "room-251", **state.DEFAULT_STATE, "seats_free": 4}, aggregation=agg({"full": [(0, 3)]}))
    monkeypatch.setattr(state, "get_es", lambda: es)
    result = state.recompute("room-251", now=NOW)
    assert result["status"] == "full" and result["changed"]
    room, doc, upsert = es.updates[0]
    assert room == "room-251" and upsert
    assert set(doc) == {"room", "status", "signals", "confidence", "changed_at", "traceparent"}


def test_recompute_does_not_write_when_nothing_changed(monkeypatch):
    es = FakeStateES(prev={"room": "room-251", **state.DEFAULT_STATE})
    monkeypatch.setattr(state, "get_es", lambda: es)
    assert state.recompute("room-251", now=NOW)["changed"] is False
    assert es.updates == []


def test_traceparent_is_set_inside_a_real_span():
    from opentelemetry.sdk.trace import TracerProvider

    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("room.state.updated") as span:
        header = state.current_traceparent()
        ctx = span.get_span_context()
        assert header.startswith(f"00-{ctx.trace_id:032x}-{ctx.span_id:016x}-")
