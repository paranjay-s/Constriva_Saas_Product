"""No upload ends on an error: the readers tried, in order, until one gives a plan to review.

1. PlanTo3D's own drawing reader (its detector). It starts as soon as the PDF is uploaded.
2. If it refuses or fails: the scan reader (scan_reader.py: OpenCV walls, OCR names and
   sizes, scale fitted to the labels; no AI), imported with reader "scan" when it finds at
   least SCAN_MIN_NAMED named rooms. Otherwise our AI plan parser, its PlanJSON converted
   for PlanTo3D (convert.py) and imported with reader "ai" and a notice to check it.
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
# The review pages say which reader made the plan and what to check; the notice adds what
# this reader itself has to say (what it dropped or changed, why nothing could be read).
AI_NOTICE = "What the AI plan reader changed:"
SCAN_NOTICE = "Read from the scan."
SCAN_MIN_NAMED = 3  # named rooms a scan reading needs before it is preferred to the AI reader
TRACE_NOTICE = "Neither reader could read this drawing{why}."

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
        pdf = await client.source_pdf(job_id)
        scanned = await run_in_threadpool(scan_read, pdf)
        if scanned is not None:
            await client.import_plan(job_id, scanned[0], "scan", scanned[1])
            return
        try:
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
            await client.import_plan(
                job_id, result.plan, "ai", f"{AI_NOTICE} {notes}" if notes else ""
            )
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


def scan_read(pdf: bytes) -> tuple[dict[str, Any], str] | None:
    """The scan reader's plan and its notice, or None when it is off, fails or reads too
    little (fewer than SCAN_MIN_NAMED named rooms): the AI reader is tried next."""
    from app.modules.plan3d.settings import get_settings

    if not get_settings().scan_reader:
        return None
    try:
        from app.modules.plan3d.scan_reader import read_scan_pdf

        res = read_scan_pdf(pdf)
    except Exception:  # a reader bug or a file it cannot open: the AI reader is next
        logger.exception("The scan reader failed")
        return None
    if res.plan is None:
        return None
    named = sum(1 for f in res.plan["floors"] for r in f["rooms"] if r.get("label"))
    if named < SCAN_MIN_NAMED:
        return None
    off = (
        f" Rooms more than 2% from their label: {'; '.join(res.rooms_off[:4])}."
        if res.rooms_off
        else ""
    )
    return res.plan, f"{SCAN_NOTICE} {' '.join(res.notes[-2:])}{off}"


def stored_plan(stored: dict[str, Any], name: str) -> ConvertResult:
    """A generated plan for PlanTo3D.

    Plans of the floor plan generator carry their building model's own PlanTo3D plan
    (`planto3d`, made from the model without reading a drawing: every wall, opening,
    room, stair flight and site area exactly). Older stored plans only have the legacy
    PlanJSON (openings measured from a wall's start), which is converted."""
    direct = stored.get("planto3d")
    if isinstance(direct, dict) and direct.get("floors"):
        return ConvertResult(dict(direct, source=name))
    return planjson_to_planto3d(stored["plan_json"], source_name=name, reader="generator")
