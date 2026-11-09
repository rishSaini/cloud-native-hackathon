"""The controller loop: watches, resync timer, reconcilers and a health endpoint (R5)."""

import logging
import os
import queue
import re
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from kubernetes import watch

log = logging.getLogger("affinity.controller")

RESYNC_SECONDS = float(os.getenv("CONTROLLER_RESYNC_SECONDS", "10"))
HEALTH_PORT = int(os.getenv("CONTROLLER_HEALTH_PORT", "8081"))
NODE_SELECTOR = "type=kwok"
POD_SELECTOR = "affinity.dev/attendee"  # every attendee Pod has this label

Reconciler = Callable[["Controller"], None]
_REGISTRY: list[tuple[str, Reconciler]] = []


def register(name: str):
    """Decorator: add a reconciler that runs on every pass, in registration order."""

    def wrap(fn: Reconciler) -> Reconciler:
        _REGISTRY.append((name, fn))
        return fn

    return wrap


def pod_name(attendee_id: str, slot: str) -> str:
    """Deterministic Pod name, so creating the same placement twice is a no-op."""
    name = f"attendee-{attendee_id}-{slot}".lower()
    if not re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", name) or len(name) > 63:
        raise ValueError(f"not a valid Pod name: {name!r}")
    return name


class Controller:
    def __init__(self, core, namespace: str, reconcilers=None, resync: float = RESYNC_SECONDS):
        self.core = core
        self.namespace = namespace
        self.reconcilers = list(_REGISTRY if reconcilers is None else reconcilers)
        self.resync = resync
        self.events: queue.Queue = queue.Queue()
        self.passes = 0
        self.last_pass = 0.0
        self.stop = threading.Event()

    # ---- one pass ----
    def run_once(self) -> dict:
        nodes = self.core.list_node(label_selector=NODE_SELECTOR).items
        pods = self.core.list_namespaced_pod(self.namespace, label_selector=POD_SELECTOR).items
        failed = []
        for name, fn in self.reconcilers:
            try:
                fn(self)
            except Exception:  # one broken reconciler must not stop the others
                log.exception("reconciler %s failed", name)
                failed.append(name)
        self.passes += 1
        self.last_pass = time.monotonic()
        summary = {"pass": self.passes, "nodes": len(nodes), "pods": len(pods), "failed": failed}
        log.info("reconcile pass %(pass)d: %(nodes)d kwok nodes, %(pods)d attendee pods, failed=%(failed)s", summary)
        return summary

    # ---- watches ----
    def _watch(self, kind: str, list_fn, **kwargs) -> None:
        while not self.stop.is_set():
            try:
                for event in watch.Watch().stream(list_fn, timeout_seconds=60, **kwargs):
                    self.events.put((kind, event["type"], event["object"].metadata.name))
                    if self.stop.is_set():
                        return
            except Exception as err:  # reconnect after API errors and timeouts
                log.warning("%s watch ended (%s); reconnecting", kind, type(err).__name__)
                time.sleep(2)

    def start_watches(self) -> None:
        threading.Thread(target=self._watch, args=("node", self.core.list_node),
                         kwargs={"label_selector": NODE_SELECTOR}, daemon=True).start()
        threading.Thread(target=self._watch, args=("pod", self.core.list_namespaced_pod, ),
                         kwargs={"namespace": self.namespace, "label_selector": POD_SELECTOR},
                         daemon=True).start()

    # ---- health ----
    def healthy(self) -> bool:
        return self.last_pass > 0 and time.monotonic() - self.last_pass < 3 * self.resync + 30

    def start_health_server(self, port: int = HEALTH_PORT) -> ThreadingHTTPServer:
        controller = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                ok = self.path == "/healthz" and (controller.healthy() or controller.passes == 0)
                self.send_response(200 if ok else 503)
                self.end_headers()
                self.wfile.write(b"ok\n" if ok else b"stale\n")

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    # ---- main loop ----
    def run(self) -> None:
        self.start_watches()
        while not self.stop.is_set():
            try:
                self.events.get(timeout=self.resync)
                while not self.events.empty():  # one pass per burst of events
                    self.events.get_nowait()
            except queue.Empty:
                pass  # resync timer
            try:
                self.run_once()
            except Exception:
                log.exception("reconcile pass failed")
