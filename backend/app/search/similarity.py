"""Interest similarity between attendees, from kNN on the `people` index (K7)."""


def similarity_matrix(attendee_ids: list[str], k: int = 20) -> dict[tuple[str, str], float]:
    """Symmetric, 0..1, only pairs within each person's top-k neighbours."""
    raise NotImplementedError("K7")
