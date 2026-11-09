"""Talk ranking for placement (K8).

Elasticsearch drives Kubernetes scheduling: the controller turns each
RankedNode into a preferredDuringSchedulingIgnoredDuringExecution entry, so
kube-scheduler prefers the talks that best match the person's interests.
"""

from dataclasses import dataclass

from elasticsearch import NotFoundError

from app.es import get_es
from app.search import mappings as m
from app.search.talks import search_talks


@dataclass(frozen=True)
class RankedNode:
    node: str  # "<slot>-<room>"
    weight: int  # 1..100, for preferredDuringScheduling


def closed_rooms(es) -> set[str]:
    try:
        resp = es.search(
            index=m.ROOM_STATE,
            size=100,
            source=["room"],
            query={"term": {"status": "closed"}},
        )
    except NotFoundError:
        return set()
    return {hit["_source"]["room"] for hit in resp["hits"]["hits"]}


def weights(n: int) -> list[int]:
    """Rank 1 gets 100, the last rank gets 1, evenly spaced in between."""
    if n <= 0:
        return []
    if n == 1:
        return [100]
    return [round(100 - i * 99 / (n - 1)) for i in range(n)]


def interests_of(es, attendee_id: str) -> str:
    try:
        doc = es.get(index=m.PEOPLE, id=attendee_id, source=["interests"])
    except NotFoundError:
        return ""
    return (doc.get("_source") or {}).get("interests", "")


def rank_talks_for(attendee_id: str, slot: str, k: int = 10) -> list[RankedNode]:
    """Rank the talk Nodes in `slot` for this attendee.

    Excludes rooms whose room-state status is "closed". Empty list if no interests.
    """
    es = get_es()
    interests = interests_of(es, attendee_id)
    if not interests:
        return []
    result = search_talks(es, interests, slot=slot, size=k, exclude_rooms=closed_rooms(es))
    nodes = [hit["node"] for hit in result["hits"] if hit.get("node")]
    return [RankedNode(node=node, weight=w) for node, w in zip(nodes, weights(len(nodes)), strict=True)]
