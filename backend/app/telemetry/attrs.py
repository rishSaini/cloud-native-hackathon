"""The span attribute allow-list from the telemetry contract.

Call it with dotted names or with underscores in place of dots:

    set_attrs(span, room_id="room-251", search_hits=3)
    set_attrs(span, **{"room.id": "room-251"})

K0 version: works now, so nobody's code has to wait. Unknown keys raise when
AFFINITY_STRICT_TELEMETRY=1 (tests set it) and are dropped otherwise.
K4 adds a counter for dropped keys, the logging filter, and the lint test.
"""

import os

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
            continue
        span.set_attribute(name, value)
