"""
Simple in-process pub/sub for orchestration events.

The orchestrator publishes events here; WebSocket clients subscribe to receive them.
"""

import asyncio
from typing import Set

_subscribers: Set[asyncio.Queue] = set()


def subscribe() -> asyncio.Queue:
    """Register a new subscriber and return its queue."""
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    """Remove a subscriber queue (called when the client disconnects)."""
    _subscribers.discard(q)


async def publish(event: dict) -> None:
    """Broadcast an event dict to all connected clients."""
    for q in list(_subscribers):
        await q.put(event)
