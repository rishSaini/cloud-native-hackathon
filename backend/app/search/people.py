"""The `people` index: consented interest text under a random attendee ID (K7).

Never store a name, card text or access needs here.
"""


def upsert_person(attendee_id: str, interests: str) -> None:
    raise NotImplementedError("K7")


def delete_person(attendee_id: str) -> None:
    raise NotImplementedError("K7")
