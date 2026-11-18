"""No upload ends on an error: the readers tried, in order, until one gives a plan to review.

1. PlanTo3D's own drawing reader (its detector). It starts as soon as the PDF is uploaded.
2. If it refuses or fails: our AI plan parser, its PlanJSON converted for PlanTo3D
   (convert.py) and imported with reader "ai" and a notice to check it.
3. If that fails too, or its plan looks implausible: the review page opens on the page image
   with whatever geometry there is (reader "trace"), for the person to trace the walls and
   set the scale.

A plan made by our floor plan generator skips all three: its stored plan is imported with
reader "stored" (see router.py).

Step 2 starts the first time the job's status is asked for after the detector failed, and
runs in the background; until it finishes the job reads as still being read. The state is
kept in this process: after a restart a failed job is simply tried again.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.modules.parsing.errors import PlanParseError
from app.modules.parsing.service import read_plan_with_ai
from app.modules.plan3d.client import Plan3dClient, Plan3dError
from app.modules.plan3d.convert import ConvertResult, planjson_to_planto3d

logger = logging.getLogger("construtiva.plan3d.fallback")

AiReader = Callable[[bytes], dict[str, Any]]

READING_MESSAGE = (
    "The drawing could not be read directly, so the AI plan reader is reading it. "
    "This can take a minute."
)
AI_NOTICE = "Read by the AI plan reader: check the walls, doors and sizes before you build."
TRACE_NOTICE = (
    "Neither reader could read this drawing{why}. Trace the walls over the page, "
    "then set the scale from a known length."
)
STORED_NOTICE = (
    'From your floor plan "{name}" (version {version}): it was not read from the drawing.'
)

_reading: dict[str, str] = {}  # job id -> what the person is told while the AI reader works
_tried: set[str] = set()
_tasks: set[asyncio.Task] = set()  # running fallbacks (a task nobody holds may be collected)


def get_ai_reader() -> AiReader:
    """The AI plan reader (a FastAPI dependency; tests replace it, no live model in tests)."""
    return read_plan_with_ai


def detector_failed(service: dict[str, Any] | None) -> bool:
    """PlanTo3D's detector gave up on this job (not a failed build, not an imported plan)."""
    return bool(
        service
        and service.get("stage") == "failed"
        and not service.get("floors")
        and not service.get("quality")
        and not service.get("reader")
    )


def reading_message(job_id: str) -> str | None:
    """What to say while the AI reader works on this job, or None when it is not."""
    return _reading.get(job_id)


def start(
    job_id: str, name: str, detector_message: str, client: Plan3dClient, ai: AiReader
) -> bool:
    """Start steps 2 and 3 for a job whose detector failed, once. True if started now."""
    if job_id in _tried:
        return False
    _tried.add(job_id)
    _reading[job_id] = READING_MESSAGE
    task = asyncio.get_running_loop().create_task(
        _read_elsewhere(job_id, name, detector_message, client, ai)
    )
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return True


def forget(job_id: str) -> None:
    """A deleted job: nothing more to do for it."""
    _tried.discard(job_id)
    _reading.pop(job_id, None)


async def _read_elsewhere(
    job_id: str, name: str, detector_message: str, client: Plan3dClient, ai: AiReader
) -> None:
    try:
        why = ""
        result: ConvertResult | None = None
        try:
            pdf = await client.source_pdf(job_id)
            plan_json = await run_in_threadpool(ai, pdf)
            result = planjson_to_planto3d(plan_json, source_name=name, reader="ai")
        except PlanParseError as e:
            why = str(e)
        except Plan3dError:
            raise
        except Exception:  # a reader bug must not leave the person at an error
            logger.exception("The AI plan reader failed on 3D job %s", job_id)
        if result is not None and result.plausible:
            notes = " ".join(result.notes[:3])
            await client.import_plan(job_id, result.plan, "ai", f"{AI_NOTICE} {notes}".strip())
            return
        if result is not None and result.usable:
            why = "; ".join(result.problems[:2])
        logger.info("3D job %s goes to tracing: %s / %s", job_id, detector_message, why)
        notice = TRACE_NOTICE.format(why=f" ({why})" if why else "")
        partial = result.plan if result is not None and result.usable else None
        try:
            await client.import_plan(job_id, partial, "trace", notice)
        except Plan3dError as e:
            if partial is None or e.status != 400:
                raise
            await client.import_plan(job_id, None, "trace", notice)  # the partial plan was refused
    except Plan3dError as e:
        logger.warning("3D job %s could not be given a plan to review: %s", job_id, e.message)
    finally:
        _reading.pop(job_id, None)


def stored_plan(plan_json: dict[str, Any], name: str) -> ConvertResult:
    """A generated plan for PlanTo3D (the generator measures openings from a wall's start)."""
    return planjson_to_planto3d(plan_json, source_name=name, reader="generator")
