"""Logging rules (K4): the access log never records what people typed.

uvicorn's access log prints the full path, including the query string. For
routes where the query holds user text (search, ask) or the path holds a
secret (card share links), the filter removes it. Request bodies are never
logged by any route; this keeps the access log in line.
"""

import logging

# path prefix -> what to keep
_DROP_QUERY = ("/api/search", "/api/talks/search", "/api/ask", "/api/card", "/api/staff/login")
_REDACT_PATH = ("/c/",)  # share-link tokens


def scrub(path: str) -> str:
    base = path.split("?", 1)[0]
    if base.startswith(_REDACT_PATH):
        return base.split("/c/", 1)[0] + "/c/<token>"
    if base.startswith(_DROP_QUERY) and "?" in path:
        return base + "?<redacted>"
    return path


class AccessLogScrubber(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # uvicorn.access args: (client, method, full_path, http_version, status_code)
        if isinstance(record.args, tuple) and len(record.args) >= 3 and isinstance(record.args[2], str):
            args = list(record.args)
            args[2] = scrub(args[2])
            record.args = tuple(args)
        return True


def install_log_filters() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, AccessLogScrubber) for f in access.filters):
        access.addFilter(AccessLogScrubber())
