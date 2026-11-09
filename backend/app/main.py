import json
from pathlib import Path

from elasticsearch import TransportError
from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from app import config
from app.es import get_es

app = FastAPI(title="TalkScout")

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "index.html"


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


# Routers. Append-only: one include line per router.
from app.search.routes import router as search_router  # noqa: E402

app.include_router(search_router)
