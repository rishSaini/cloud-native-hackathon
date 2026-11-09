"""Create Affinity's Elasticsearch inference endpoint, indices and data stream (K1).

Safe to run again: it only creates what is missing.

    python scripts/es_setup.py           # or `make es-setup`
    python scripts/es_setup.py --reset   # dev only: delete everything first

Reads ES_URL, ES_API_KEY and OPENAI_API_KEY. Without OPENAI_API_KEY it still
works: the indices get no semantic_text fields, and search uses BM25 only.
In the cluster it runs as the one-off Job in deploy/jobs/es-setup-001.yaml.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from elasticsearch import Elasticsearch  # noqa: E402

from app import config  # noqa: E402
from app.search import setup  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="delete everything first (dev only)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("elastic_transport").setLevel(logging.WARNING)

    # OpenAI calls during inference setup can take a while, so allow more time than the app does.
    es = Elasticsearch(config.ES_URL, api_key=config.ES_API_KEY, request_timeout=60)
    if args.reset:
        setup.reset(es)
        print("Deleted the Affinity indices, data stream, template, policy and inference endpoint.")

    result = setup.ensure_all(es, os.getenv("OPENAI_API_KEY") or None)
    width = max(len(name) for name in result)
    for name, status in result.items():
        print(f"{name:<{width}}  {status}")


if __name__ == "__main__":
    main()
