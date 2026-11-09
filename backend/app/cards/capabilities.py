"""What the opaque capability codes mean (R2). The only place that knows.

Kubernetes objects, Elasticsearch, logs, spans and the board see only codes
such as `cap-c3`. Anyone who reads the cluster (Radar, MCP, AI investigations)
therefore cannot learn a person's access needs from a Pod or a Node.
"""

# code -> what a room or table offers (shown to the attendee in plain words)
MEANINGS = {
    "cap-c1": "Live captions",
    "cap-c2": "Step-free access",
    "cap-c3": "Quiet space",
    "cap-c4": "Good lighting",
    "cap-c5": "Sign language interpreter",
    "cap-c6": "Reserved seats near the front",
    "cap-c7": "Hearing loop",
    "cap-c8": "Seat with back support",
}

# Room-report signal (Karthik's K9/K10) -> the code that signal takes away.
# The controller (R7) removes this label from the room's Node while the signal holds.
SIGNAL_REMOVES = {
    "captions_down": "cap-c1",
    "access_blocked": "cap-c2",
    "very_loud": "cap-c3",
}


def label(code: str) -> str:
    """The Node and Pod label for a code: cap-c3 -> affinity.dev/cap-c3."""
    if code not in MEANINGS:
        raise ValueError(f"unknown capability code: {code}")
    return f"affinity.dev/{code}"
