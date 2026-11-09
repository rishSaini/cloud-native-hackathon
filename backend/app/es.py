"""One shared Elasticsearch client for the whole app."""

from functools import lru_cache

from elasticsearch import Elasticsearch

from app import config


@lru_cache
def get_es() -> Elasticsearch:
    # The official client sends an OpenTelemetry span for every request
    # when the app runs under `opentelemetry-instrument`.
    return Elasticsearch(config.ES_URL, api_key=config.ES_API_KEY, request_timeout=10)
