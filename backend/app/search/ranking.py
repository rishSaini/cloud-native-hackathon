"""Talk ranking for placement (K8). The controller turns each RankedNode into a
preferredDuringSchedulingIgnoredDuringExecution entry."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RankedNode:
    node: str  # "<slot>-<room>"
    weight: int  # 1..100, for preferredDuringScheduling


def rank_talks_for(attendee_id: str, slot: str, k: int = 10) -> list[RankedNode]:
    """Rank the talk Nodes in `slot` for this attendee.

    Excludes rooms whose room-state status is "closed". Empty list if no interests.
    """
    raise NotImplementedError("K8")
