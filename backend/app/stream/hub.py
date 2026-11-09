"""One LISTEN connection per API replica, fanning notifications out to its SSE clients (R9).

The controller (any replica of anything) inserts a `notifications` row; a trigger
runs pg_notify('affinity', '<attendee>:<id>'); every API replica hears it, and the
replica holding that attendee's stream sends the event. So it works with 2 replicas.
"""

import asyncio
import logging
import threading
import time
from collections import defaultdict

import psycopg

from app.db import database_url

log = logging.getLogger("affinity.stream")


class Hub:
    def __init__(self):
        self.subscribers: dict[str, set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = defaultdict(set)
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None

    def subscribe(self, attendee_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        with self.lock:
            self.subscribers[attendee_id].add((asyncio.get_running_loop(), queue))
            if self.thread is None:
                self.thread = threading.Thread(target=self._listen, daemon=True)
                self.thread.start()
        return queue

    def unsubscribe(self, attendee_id: str, queue: asyncio.Queue) -> None:
        with self.lock:
            self.subscribers[attendee_id] = {s for s in self.subscribers[attendee_id] if s[1] is not queue}
            if not self.subscribers[attendee_id]:
                del self.subscribers[attendee_id]

    def deliver(self, payload: str) -> None:
        attendee_id, _, notification_id = payload.partition(":")
        with self.lock:
            targets = list(self.subscribers.get(attendee_id, ()))
        for loop, queue in targets:
            loop.call_soon_threadsafe(queue.put_nowait, int(notification_id))

    def _listen(self) -> None:
        while True:
            try:
                with psycopg.connect(database_url(), autocommit=True) as conn:
                    conn.execute("LISTEN affinity")
                    for note in conn.notifies():
                        self.deliver(note.payload)
            except Exception as err:  # database restart: listen again
                log.warning("LISTEN connection lost (%s); reconnecting", type(err).__name__)
                time.sleep(2)


hub = Hub()
