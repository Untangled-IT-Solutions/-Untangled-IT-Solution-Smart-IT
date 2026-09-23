from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

_subscribers: dict[str, set[asyncio.Queue]] = {}


def publish(recipient: object, event: dict) -> None:
    key = str(recipient)
    for queue in tuple(_subscribers.get(key, ())):
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        queue.put_nowait(event)


@asynccontextmanager
async def subscribe(recipients: set[str]) -> AsyncIterator[asyncio.Queue]:
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    for key in recipients:
        _subscribers.setdefault(key, set()).add(queue)
    try:
        yield queue
    finally:
        for key in recipients:
            listeners = _subscribers.get(key)
            if listeners is not None:
                listeners.discard(queue)
                if not listeners:
                    _subscribers.pop(key, None)
