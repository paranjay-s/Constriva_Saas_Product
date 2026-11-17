"""Generic pieces of the in-process background jobs shared by the AI features.

The floor plan generator (ai/floorplan/jobs.py) and the material finder
(ai/material_agent/jobs.py) both keep a list of progress events per job and stream them
as SSE. `stream_events` works with any job object that has:

    events: list[<pydantic model>]     every event so far, in order
    finished: bool                     True once the job is done or failed
    wait_for(seen: int, timeout: float) -> None   block until there is news
"""

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from pydantic import BaseModel


class StreamableJob(Protocol):
    events: Sequence[BaseModel]

    @property
    def finished(self) -> bool: ...

    def wait_for(self, seen: int, timeout: float) -> None: ...


async def stream_events(job: StreamableJob, heartbeat_s: float = 15.0) -> AsyncIterator[str]:
    """SSE text: every recorded event, then new ones as they come; ends when the job does."""
    sent = 0
    while True:
        while sent < len(job.events):
            ev = job.events[sent]
            sent += 1
            yield f"event: progress\nid: {sent}\ndata: {ev.model_dump_json()}\n\n"
        if job.finished and sent >= len(job.events):
            yield "event: end\ndata: {}\n\n"
            return
        before = sent
        await asyncio.to_thread(job.wait_for, sent, heartbeat_s)
        if len(job.events) == before and not job.finished:
            yield ": keep-alive\n\n"  # comment line keeps proxies from closing the stream
