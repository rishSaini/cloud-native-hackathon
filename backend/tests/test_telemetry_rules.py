"""K4: telemetry rules hold across the codebase."""

import logging
import re
from pathlib import Path

from app.telemetry.attrs import set_attrs
from app.telemetry.logs import AccessLogScrubber, scrub

APP = Path(__file__).resolve().parents[1] / "app"


def test_no_direct_set_attribute_outside_telemetry():
    offenders = [
        f"{path.relative_to(APP)}:{n}"
        for path in APP.rglob("*.py") if "telemetry" not in path.parts
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if re.search(r"\.set_attribute\(", line)
    ]
    assert offenders == [], f"use app.telemetry.attrs.set_attrs instead: {offenders}"


def test_unknown_keys_are_dropped_in_production(recording_span, monkeypatch):
    monkeypatch.setenv("AFFINITY_STRICT_TELEMETRY", "0")
    set_attrs(recording_span, card_name="Alex", room_id="room-101")
    assert recording_span.attributes == {"room.id": "room-101"}


def test_access_log_drops_user_text_and_tokens():
    assert scrub("/api/talks/search?q=I%20read%20lips") == "/api/talks/search?<redacted>"
    assert scrub("/api/search?q=secret") == "/api/search?<redacted>"
    assert scrub("/c/abc123signedtoken") == "/c/<token>"
    assert scrub("/api/staff/login?token=s3cret") == "/api/staff/login?<redacted>"
    assert scrub("/api/board?slot=tue-1430") == "/api/board?slot=tue-1430"
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                               ("1.2.3.4", "GET", "/api/search?q=private", "1.1", 200), None)
    AccessLogScrubber().filter(record)
    assert "private" not in record.getMessage()


def test_service_is_named_affinity_api():
    root = APP.parents[1]
    assert "value: affinity-api" in (root / "deploy" / "deployment.yaml").read_text()
    assert "talkscout" not in (APP / "main.py").read_text().lower()
