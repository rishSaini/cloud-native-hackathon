"""Load a JSON Lines file into Elasticsearch.

Usage: python scripts/ingest.py data/sample.jsonl

Each line is one document. An "id" field, if present, becomes the document id,
so running the script again updates documents and does not duplicate them.
Reads ES_URL, ES_API_KEY and ES_INDEX from the environment.
"""

import json
import os
import sys

from elasticsearch import Elasticsearch, helpers


def actions(path, index):
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            doc = json.loads(line)
            action = {"_index": index, "_source": doc}
            if "id" in doc:
                action["_id"] = doc["id"]
            yield action


def main(path):
    es = Elasticsearch(
        os.getenv("ES_URL", "http://localhost:9200"),
        api_key=os.getenv("ES_API_KEY") or None,
    )
    index = os.getenv("ES_INDEX", "talks")
    ok, errors = helpers.bulk(es, actions(path, index), raise_on_error=False)
    es.indices.refresh(index=index)
    print(f"Indexed {ok} docs into '{index}' ({len(errors)} errors)")
    for err in errors[:5]:
        print(err)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
