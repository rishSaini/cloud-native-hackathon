"""Recompute every active room, so states decay without new reports (K10).

Runs every minute as CronJob room-state-sweep:  python -m app.reports.sweep
Active rooms: any room with a report in the last 30 minutes, and any room
whose state is not the plain default (full, captions down, loud, blocked).
"""

from elasticsearch import NotFoundError

from app.es import get_es
from app.reports import state
from app.search import mappings as m


def active_rooms(es) -> set[str]:
    rooms = set()
    try:
        agg = es.search(
            index=m.ROOM_REPORTS,
            size=0,
            query={"range": {"@timestamp": {"gte": f"now-{state.WINDOW}"}}},
            aggs={"rooms": {"terms": {"field": "room", "size": 500}}},
        )["aggregations"]
        rooms |= {b["key"] for b in agg["rooms"]["buckets"]}
    except NotFoundError:
        pass
    try:
        resp = es.search(
            index=m.ROOM_STATE,
            size=500,
            source=["room"],
            query={"bool": {"should": [
                {"term": {"status": "full"}},
                {"term": {"signals.captions": "down"}},
                {"term": {"signals.very_loud": True}},
                {"term": {"signals.access_blocked": True}},
            ]}},
        )
        rooms |= {h["_source"]["room"] for h in resp["hits"]["hits"]}
    except NotFoundError:
        pass
    return rooms


def main() -> None:
    es = get_es()
    rooms = sorted(active_rooms(es))
    changed = [r for r in rooms if state.recompute(r, es=es)["changed"]]
    print(f"room-state sweep: {len(rooms)} active rooms, {len(changed)} changed {changed}")


if __name__ == "__main__":
    main()
