"""In-process background jobs of the BOQ flow: PDF -> parse -> calculate.

Same model as the floor plan and material finder jobs: every progress event is recorded,
and the SSE endpoint replays them and then follows new ones (ai/jobs_common.stream_events).
Jobs and their results live in memory for JOB_TTL_S, so this needs a single API worker.
"""

import logging
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from app.modules.sheets.boq_schemas import BoqJobEvent, BoqJobState, BoqJobStatus

logger = logging.getLogger("construtiva.sheets.boq_jobs")

JOB_TTL_S = 3600
MAX_PARALLEL_JOBS = 2

STAGE_PROGRESS = {"queued": 0, "uploading": 5, "parsing": 15, "calculating": 85, "done": 100}
STAGE_TEXT = {
    "queued": "Waiting to start",
    "uploading": "Upload received",
    "parsing": "Reading the floor plan",
    "calculating": "Calculating quantities",
    "done": "Ready",
}


class BoqJobFailure(Exception):
    """Raised by a job's work to fail it with a message that is safe to show."""

    def __init__(self, message: str, code: str = "boq_failed") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass
class BoqJob:
    id: str
    owner_id: str
    filename: str
    status: BoqJobStatus = "queued"
    events: list[BoqJobEvent] = field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
    result: dict[str, Any] | None = None
    finished_at: float | None = None
    _cond: threading.Condition = field(default_factory=threading.Condition)

    def _event(self, stage: str, detail: str = "") -> BoqJobEvent:
        previous = self.events[-1].progress if self.events else 0
        return BoqJobEvent(
            job_id=self.id,
            status=self.status,
            stage=stage,
            detail=detail or STAGE_TEXT.get(stage, ""),
            progress=STAGE_PROGRESS.get(stage, previous),
            error=self.error,
            error_code=self.error_code,
        )

    def state(self) -> BoqJobState:
        last = self.events[-1] if self.events else self._event("queued")
        return BoqJobState(**last.model_dump(), events=list(self.events))

    def emit(self, stage: str, detail: str = "") -> None:
        with self._cond:
            if self.status == "queued":
                self.status = "running"
            self.events.append(self._event(stage, detail))
            self._cond.notify_all()

    def finish(self, result: dict[str, Any]) -> None:
        with self._cond:
            self.result = result
            self.status = "done"
            self.finished_at = time.time()
            self.events.append(self._event("done"))
            self._cond.notify_all()

    def fail(self, message: str, code: str) -> None:
        with self._cond:
            self.error, self.error_code = message, code
            self.status = "failed"
            self.finished_at = time.time()
            self.events.append(self._event("failed", message))
            self._cond.notify_all()

    @property
    def finished(self) -> bool:
        return self.status in ("done", "failed")

    def wait_for(self, seen: int, timeout: float) -> None:
        with self._cond:
            if len(self.events) <= seen and not self.finished:
                self._cond.wait(timeout)


# work(job) runs in a worker thread, reports progress with job.emit and returns the result
Work = Callable[[BoqJob], dict[str, Any]]


class BoqJobManager:
    def __init__(self, max_parallel: int = MAX_PARALLEL_JOBS) -> None:
        self._jobs: dict[str, BoqJob] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=max_parallel, thread_name_prefix="boq-job")

    def submit(self, owner_id: str, filename: str, work: Work) -> BoqJob:
        self._forget_old()
        job = BoqJob(id=uuid.uuid4().hex, owner_id=owner_id, filename=filename)
        job.events.append(job._event("queued"))
        with self._lock:
            self._jobs[job.id] = job
        self._pool.submit(self._run, job, work)
        return job

    def get(self, job_id: str) -> BoqJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    @staticmethod
    def _run(job: BoqJob, work: Work) -> None:
        try:
            result = work(job)
        except BoqJobFailure as e:
            job.fail(e.message, e.code)
        except Exception:
            logger.exception("boq job %s crashed", job.id)
            job.fail(
                "Something went wrong while preparing the BOQ. Please try again.", "boq_failed"
            )
        else:
            job.finish(result)

    def _forget_old(self) -> None:
        now = time.time()
        with self._lock:
            expired = [
                j.id
                for j in self._jobs.values()
                if j.finished_at and now - j.finished_at > JOB_TTL_S
            ]
            for job_id in expired:
                del self._jobs[job_id]


_manager: BoqJobManager | None = None


def get_boq_jobs() -> BoqJobManager:
    global _manager
    if _manager is None:
        _manager = BoqJobManager()
    return _manager
