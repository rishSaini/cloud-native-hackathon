"""The span attribute allow-list from the telemetry contract.

Call it with dotted names or with underscores in place of dots:

    set_attrs(span, room_id="room-251", search_hits=3)
    set_attrs(span, **{"room.id": "room-251"})

Unknown keys raise when AFFINITY_STRICT_TELEMETRY=1 (tests set it). In
production they are dropped and counted in affinity_telemetry_dropped_attributes_total,
so a typo never leaks data and never breaks a request.
A test (tests/test_telemetry_rules.py) fails if code outside app/telemetry/
calls span.set_attribute directly.
"""

import os

from opentelemetry import metrics

_dropped = metrics.get_meter("affinity").create_counter(
    "affinity_telemetry_dropped_attributes_total",
    description="Span attributes dropped because they are not in the allow-list",
)

ALLOWED_ATTRIBUTES = frozenset(
    {
        "room.id",
        "slot.id",
        "report.signal",
        "placement.outcome",
        "group.size",
        "solver.duration_ms",
        "attendee.hash",
        "search.hits",
        "search.query_length",
    }
)

# "room_id" -> "room.id", "search_query_length" -> "search.query_length", ...
_BY_UNDERSCORE = {name.replace(".", "_"): name for name in ALLOWED_ATTRIBUTES}


class UnknownAttributeError(ValueError):
    pass


def set_attrs(span, **kw) -> None:
    strict = os.getenv("AFFINITY_STRICT_TELEMETRY") == "1"
    for key, value in kw.items():
        name = key if key in ALLOWED_ATTRIBUTES else _BY_UNDERSCORE.get(key)
        if name is None:
            if strict:
                raise UnknownAttributeError(f"span attribute {key!r} is not in the allow-list")
            _dropped.add(1)  # never record the key itself: it could be the leak
            continue
        span.set_attribute(name, value)
