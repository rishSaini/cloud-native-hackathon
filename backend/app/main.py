import json
import logging
from pathlib import Path

from elasticsearch import NotFoundError, TransportError
from fastapi import Depends, FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from opentelemetry import metrics, trace

from app import config
from app.es import get_es

log = logging.getLogger("talkscout")

# These are no-ops until the app runs under `opentelemetry-instrument`.
tracer = trace.get_tracer("talkscout")
meter = metrics.get_meter("talkscout")
search_requests = meter.create_counter(
    "talkscout.search.requests",
    description="Search requests, split by whether they returned any results",
)

app = FastAPI(title="TalkScout")

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
STATIC_DIR = FRONTEND.parent / "static"

# The frontend's CSS and JavaScript modules. No build step: files are served as-is.
app.mount("/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static")


# Kubernetes probes. They do not check Elasticsearch, so a slow Elasticsearch
# does not take the web page down.
@app.get("/healthz", response_class=PlainTextResponse)
@app.get("/readyz", response_class=PlainTextResponse)
def probe():
    return "ok\n"


@app.get("/health")
def health(es=Depends(get_es)):
    try:
        es_up = bool(es.ping())
    except TransportError:
        es_up = False
    return {
        "status": "ok",
        "version": config.APP_VERSION,
        "elasticsearch": "up" if es_up else "down",
    }


@app.get("/api/search")
def search(
    q: str = Query(min_length=1),
    size: int = Query(10, ge=1, le=50),
    es=Depends(get_es),
):
    with tracer.start_as_current_span("search.keyword") as span:
        span.set_attribute("search.query_length", len(q))
        try:
            resp = es.search(
                index=config.ES_INDEX,
                size=size,
                query={"multi_match": {"query": q, "fields": ["*"], "lenient": True}},
            )
        except NotFoundError:
            log.warning("index %s not found", config.ES_INDEX)
            return {
                "hits": [],
                "total": 0,
                "note": f"Index '{config.ES_INDEX}' not found. Run: make ingest",
            }

        hits = [
            {"id": h["_id"], "score": h["_score"], **h["_source"]}
            for h in resp["hits"]["hits"]
        ]
        span.set_attribute("search.hits", len(hits))

    search_requests.add(1, {"has_results": bool(hits)})
    if not hits:
        log.info("zero-result search: %s", q)
    return {"hits": hits, "total": resp["hits"]["total"]["value"]}


@app.get("/rum.js")
def rum_config():
    """Starts Dash0 website monitoring when DASH0_RUM_* are set. Otherwise does nothing."""
    if not (config.DASH0_RUM_ENDPOINT and config.DASH0_RUM_TOKEN):
        return Response("// Dash0 RUM is off\n", media_type="text/javascript")
    settings = json.dumps(
        {
            "serviceName": "talkscout-web",
            "endpoint": {"url": config.DASH0_RUM_ENDPOINT, "authToken": config.DASH0_RUM_TOKEN},
            "additionalSignalAttributes": {"service.version": config.APP_VERSION},
        }
    )
    script = (
        "(function(d,a,s,h,z){d[a]||((z=d[a]=function(){h.push(arguments)}),"
        "(z._t=new Date()),(z._v=1),(h=z._q=[]));})(window,'dash0');\n"
        f"dash0('init', {settings});\n"
        "var s=document.createElement('script');s.defer=true;s.crossOrigin='anonymous';\n"
        "s.src='https://unpkg.com/@dash0/sdk-web@0.18.1/dist/dash0.iife.js';\n"
        "document.head.appendChild(s);\n"
    )
    return Response(script, media_type="text/javascript")


@app.get("/", response_class=HTMLResponse)
def index():
    # The page prints the version, so you can check which commit is live.
    return FRONTEND.read_text().replace("{{VERSION}}", config.APP_VERSION)


from app.placements.routes import router as placements_router  # noqa: E402

app.include_router(placements_router)
