"""Elasticsearch names and mappings for Affinity (K1, owner: Karthik).

Source: docs/tasks/karthik.md, "Elasticsearch indices".
Privacy: no index may hold a name, card text or access needs. `people`,
`room-state`, `incidents` and `room-reports` use "dynamic": "strict", so
Elasticsearch rejects any field that is not listed here.
"""

INFERENCE_ID = "affinity-embed"
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_ID = "affinity-chat"  # K13: completion endpoint for Ask Affinity
CHAT_MODEL = "gpt-4.1-mini"

TALKS = "talks"
PEOPLE = "people"
ROOM_STATE = "room-state"
INCIDENTS = "incidents"
ROOM_REPORTS = "room-reports"  # a data stream
ROOM_REPORTS_TEMPLATE = "room-reports"
ROOM_REPORTS_POLICY = "room-reports-2d"

KEYWORD = {"type": "keyword"}
TEXT = {"type": "text"}
DATE = {"type": "date"}
BOOLEAN = {"type": "boolean"}
INTEGER = {"type": "integer"}
SEMANTIC = {"type": "semantic_text", "inference_id": INFERENCE_ID}


def talks_mapping(semantic: bool) -> dict:
    props = {
        "id": KEYWORD,
        "title": TEXT,
        "abstract": dict(TEXT),
        "speakers": TEXT,
        "track": KEYWORD,
        "room": KEYWORD,
        "slot": KEYWORD,
        "node": KEYWORD,  # "<slot>-<room>", the KWOK Node name
        "starts_at": DATE,  # with the America/Denver offset
    }
    if semantic:
        props["abstract"]["copy_to"] = "abstract_semantic"
        props["abstract_semantic"] = SEMANTIC
    # "false", not "strict": extra fields in talk data are kept but not indexed.
    return {"dynamic": "false", "properties": props}


def people_mapping(semantic: bool) -> dict:
    props = {
        "attendee_id": KEYWORD,  # random ID, never a name
        "interests": dict(TEXT),  # consented interest text only
        "updated_at": DATE,
    }
    if semantic:
        props["interests"]["copy_to"] = "interests_semantic"
        props["interests_semantic"] = SEMANTIC
    return {"dynamic": "strict", "properties": props}


def room_state_mapping() -> dict:
    return {
        "dynamic": "strict",
        "properties": {
            # Written by Karthik (K10)
            "room": KEYWORD,
            "status": KEYWORD,  # open | full | closed
            "signals": {
                "properties": {
                    "captions": KEYWORD,  # working | down | unknown
                    "very_loud": BOOLEAN,
                    "access_blocked": BOOLEAN,
                }
            },
            "confidence": {"type": "object", "enabled": False},
            "changed_at": DATE,
            "traceparent": {"type": "keyword", "index": False},
            # Written by Rishabh, with partial updates only
            "seats_total": INTEGER,
            "seats_free": INTEGER,
            "controller_seen_at": DATE,
        },
    }


def incidents_mapping() -> dict:
    return {
        "dynamic": "strict",
        "properties": {
            "id": KEYWORD,
            "room": KEYWORD,
            "kind": KEYWORD,
            "state": KEYWORD,  # open | acknowledged | resolved
            "opened_at": DATE,
            "acknowledged_at": DATE,
            "resolved_at": DATE,
        },
    }


def room_reports_policy() -> dict:
    # Roll over daily, delete two days after rollover.
    return {
        "phases": {
            "hot": {"actions": {"rollover": {"max_age": "1d"}}},
            "delete": {"min_age": "2d", "actions": {"delete": {}}},
        }
    }


def room_reports_template() -> dict:
    return {
        "index_patterns": [f"{ROOM_REPORTS}*"],
        "data_stream": {},
        "priority": 500,
        "template": {
            "settings": {"index.lifecycle.name": ROOM_REPORTS_POLICY},
            "mappings": {
                "dynamic": "strict",
                "properties": {
                    "@timestamp": DATE,
                    "room": KEYWORD,
                    "slot": KEYWORD,
                    "signal": KEYWORD,
                    "reporter_hash": KEYWORD,  # HMAC from app.auth.attendee_hash, never an ID
                },
            },
        },
    }


def indices(semantic: bool) -> dict[str, dict]:
    """Every plain index and its mapping. room-reports is a data stream, set up separately."""
    return {
        TALKS: talks_mapping(semantic),
        PEOPLE: people_mapping(semantic),
        ROOM_STATE: room_state_mapping(),
        INCIDENTS: incidents_mapping(),
    }
