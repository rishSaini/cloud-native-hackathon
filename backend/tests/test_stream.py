"""R9: SSE framing and the hub's fan-out (no database needed)."""

import asyncio

from app.stream.hub import Hub
from app.stream.routes import sse


def test_sse_frame():
    assert sse("placement", {"room": "room-101"}) == 'event: placement\ndata: {"room": "room-101"}\n\n'


def test_hub_delivers_only_to_the_right_attendee():
    async def run():
        hub = Hub()
        hub.thread = object()  # don't start a real LISTEN thread
        mine, other = hub.subscribe("ab12"), hub.subscribe("zz99")
        hub.deliver("ab12:42")
        got = await asyncio.wait_for(mine.get(), 1)
        assert got == 42 and other.empty()
        hub.unsubscribe("ab12", mine)
        assert "ab12" not in hub.subscribers

    asyncio.run(run())
