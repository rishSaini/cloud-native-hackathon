"""Create the Elasticsearch pieces Affinity needs, only where they are missing (K1).

Run through scripts/es_setup.py. A second run changes nothing.
"""

import logging

from elasticsearch import NotFoundError

from app.search import mappings as m

log = logging.getLogger("affinity.es_setup")


def ensure_inference(es, openai_key: str | None) -> str:
    """Make sure the `affinity-embed` endpoint exists. Returns "exists", "created" or "skipped"."""
    try:
        es.inference.get(inference_id=m.INFERENCE_ID)
        return "exists"
    except NotFoundError:
        pass
    if not openai_key:
        log.warning(
            "OPENAI_API_KEY is not set: creating indices without semantic_text. "
            "Search falls back to BM25 only."
        )
        return "skipped"
    es.inference.put(
        task_type="text_embedding",
        inference_id=m.INFERENCE_ID,
        inference_config={
            "service": "openai",
            "service_settings": {"api_key": openai_key, "model_id": m.EMBEDDING_MODEL},
        },
    )
    return "created"


def ensure_index(es, name: str, mapping: dict) -> str:
    if es.indices.exists(index=name):
        return "exists"
    es.indices.create(index=name, mappings=mapping)
    return "created"


def ensure_room_reports(es) -> dict[str, str]:
    result = {}
    try:
        es.ilm.get_lifecycle(name=m.ROOM_REPORTS_POLICY)
        result["ilm policy"] = "exists"
    except NotFoundError:
        es.ilm.put_lifecycle(name=m.ROOM_REPORTS_POLICY, policy=m.room_reports_policy())
        result["ilm policy"] = "created"

    if es.indices.exists_index_template(name=m.ROOM_REPORTS_TEMPLATE):
        result["index template"] = "exists"
    else:
        es.indices.put_index_template(name=m.ROOM_REPORTS_TEMPLATE, **m.room_reports_template())
        result["index template"] = "created"

    if es.indices.exists(index=m.ROOM_REPORTS):
        result[f"data stream {m.ROOM_REPORTS}"] = "exists"
    else:
        es.indices.create_data_stream(name=m.ROOM_REPORTS)
        result[f"data stream {m.ROOM_REPORTS}"] = "created"
    return result


def has_semantic_field(es, index: str, field: str) -> bool:
    props = es.indices.get_mapping(index=index)[index]["mappings"].get("properties", {})
    return props.get(field, {}).get("type") == "semantic_text"


def reset(es) -> None:
    """Dev only: delete everything this module creates."""
    for name in m.indices(semantic=True):
        es.indices.delete(index=name, ignore_unavailable=True)
    for call in (
        lambda: es.indices.delete_data_stream(name=m.ROOM_REPORTS),
        lambda: es.indices.delete_index_template(name=m.ROOM_REPORTS_TEMPLATE),
        lambda: es.ilm.delete_lifecycle(name=m.ROOM_REPORTS_POLICY),
        lambda: es.inference.delete(inference_id=m.INFERENCE_ID),
    ):
        try:
            call()
        except NotFoundError:
            pass


def ensure_all(es, openai_key: str | None) -> dict[str, str]:
    """Create whatever is missing. Returns {thing: "created" | "exists" | "skipped"}."""
    result = {f"inference {m.INFERENCE_ID}": ensure_inference(es, openai_key)}
    semantic = result[f"inference {m.INFERENCE_ID}"] != "skipped"
    for name, mapping in m.indices(semantic).items():
        result[f"index {name}"] = ensure_index(es, name, mapping)
    result.update(ensure_room_reports(es))

    # Indices made before the key existed have no semantic_text fields, and a
    # mapping cannot gain copy_to on an existing field. Say so, plainly.
    if semantic and result[f"index {m.TALKS}"] == "exists" and not has_semantic_field(
        es, m.TALKS, "abstract_semantic"
    ):
        log.warning(
            "Index %s has no semantic_text field: it was created without OPENAI_API_KEY. "
            "Run `python scripts/es_setup.py --reset`, then ingest again.",
            m.TALKS,
        )
    return result
