"""App settings, read from environment variables (see .env.example)."""

import os

APP_VERSION = os.getenv("APP_VERSION", "dev")

ES_URL = os.getenv("ES_URL", "http://localhost:9200")
ES_API_KEY = os.getenv("ES_API_KEY") or None
ES_INDEX = os.getenv("ES_INDEX", "talks")

# Dash0 website monitoring (RUM). Both empty = RUM off.
# The token is visible in the browser, so use an ingest-only token for one dataset.
DASH0_RUM_ENDPOINT = os.getenv("DASH0_RUM_ENDPOINT", "")
DASH0_RUM_TOKEN = os.getenv("DASH0_RUM_TOKEN", "")
