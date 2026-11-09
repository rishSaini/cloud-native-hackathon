"""Load talks into Elasticsearch (K2).

    python scripts/ingest.py                     # data/sample-schedule.json -> talks
    python scripts/ingest.py data/sample.jsonl   # JSON Lines, one document per line

Works before and after scripts/es_setup.py. Without the index, Elasticsearch
creates one with a dynamic mapping. With it, the `semantic_text` field gets its
embeddings during the bulk load. Document IDs are talk IDs, so a rerun updates
documents and does not duplicate them.
Reads ES_URL, ES_API_KEY and ES_INDEX (default: talks).
"""

import json
import os
import sys
from pathlib import Path

from elasticsearch import Elasticsearch, helpers

DEFAULT = Path(__file__).resolve().parents[1] / "data" / "sample-schedule.json"
TALK_FIELDS = ("id", "title", "abstract", "speakers", "track", "room", "slot", "node", "starts_at")


def load_docs(path: Path) -> list[dict]:
    if path.suffix == ".jsonl":
        with open(path) as f:
            return [json.loads(line) for line in f if line.strip()]
    with open(path) as f:
        schedule = json.load(f)
    return [{key: talk[key] for key in TALK_FIELDS if key in talk} for talk in schedule["talks"]]


def actions(docs: list[dict], index: str):
    for doc in docs:
        action = {"_index": index, "_source": doc}
        if "id" in doc:
            action["_id"] = doc["id"]
        yield action


def main(path: Path) -> None:
    # Embeddings are computed during the bulk load, so allow more time than the app does.
    es = Elasticsearch(
        os.getenv("ES_URL", "http://localhost:9200"),
        api_key=os.getenv("ES_API_KEY") or None,
        request_timeout=120,
    )
    index = os.getenv("ES_INDEX", "talks")
    docs = load_docs(path)
    ok, errors = helpers.bulk(es, actions(docs, index), raise_on_error=False, chunk_size=50)
    es.indices.refresh(index=index)
    print(f"Indexed {ok} of {len(docs)} docs from {path.name} into '{index}' ({len(errors)} errors)")
    for err in errors[:5]:
        print(err)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]) if len(sys.argv) == 2 else DEFAULT)
