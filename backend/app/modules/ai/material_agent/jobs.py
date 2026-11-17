"""Background jobs of the material finder (photo analysis, plan parsing), in process.

Same model as the floor plan jobs: events are recorded, the SSE endpoint replays them and
then follows new ones (ai/jobs_common.stream_events). Needs a single API worker.
"""

import logging
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.modules.ai.material_agent.schemas import JobEvent, JobState, JobStatus

logger = logging.getLogger("construtiva.ai.material.jobs")

JOB_TTL_S = 3600
MAX_PARALLEL_JOBS = 2

STAGE_PROGRESS = {
    "queued": 0,
    "uploading": 5,
    "analysing_image": 15,
    "parsing_plan": 15,
    "matching_materials": 60,
    "calculating": 70,
    "writing_summary": 80,
    "saving": 92,
    "done": 100,
}
STAGE_TEXT = {
    "uploading": "Uploading",
    "analysing_image": "Looking at the photo",
    "parsing_plan": "Reading the floor plan",
    "matching_materials": "Matching materials",
    "calculating": "Calculating quantities",
    "writing_summary": "Writing the summary",
    "saving": "Saving",
}


@dataclass
class Job:
    id: str
    owner_id: str
    report_id: str
    status: JobStatus = "queued"
    events: list[JobEvent] = field(default_factory=list)
    error: str | None = None
    finished_at: float | None = None
    _cond: threading.Condition = field(default_factory=threading.Condition)

    def _event(self, stage: str, detail: str) -> JobEvent:
        pct = STAGE_PROGRESS.get(stage, self.events[-1].progress if self.events else 0)
        return JobEvent(
            job_id=self.id,
            status=self.status,
            stage=stage,
            detail=detail or STAGE_TEXT.get(stage, ""),
            progress=pct,
            report_id=self.report_id,
            error=self.error,
        )

    def state(self) -> JobState:
        last = self.events[-1] if self.events else self._event("queued", "")
        return JobState(**last.model_dump(), events=list(self.events))

    def emit(self, stage: str, detail: str = "") -> None:
        with self._cond:
            if self.status == "queued":
                self.status = "running"
            self.events.append(self._event(stage, detail))
            self._cond.notify_all()

    def finish(self, error: str | None) -> None:
        with self._cond:
            self.error = error
            self.status = "done" if error is None else "failed"
            self.finished_at = time.time()
            ev = self._event(
                "done" if error is None else "failed", "Ready" if error is None else error
            )
            if error is not None:
                ev.progress = self.events[-1].progress if self.events else 0
            self.events.append(ev)
            self._cond.notify_all()

    @property
    def finished(self) -> bool:
        return self.status in ("done", "failed")

    def wait_for(self, seen: int, timeout: float) -> None:
        with self._cond:
            if len(self.events) <= seen and not self.finished:
                self._cond.wait(timeout)


# work(job) runs in a worker thread and returns an error message or None
Work = Callable[[Job], str | None]


class JobManager:
    def __init__(self, max_parallel: int = MAX_PARALLEL_JOBS) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=max_parallel, thread_name_prefix="mat-job")

    def submit(self, owner_id: str, report_id: str, work: Work) -> Job:
        self._forget_old()
        job = Job(id=uuid.uuid4().hex, owner_id=owner_id, report_id=report_id)
        job.events.append(job._event("queued", "Waiting to start"))
        with self._lock:
            self._jobs[job.id] = job
        self._pool.submit(self._run, job, work)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    @staticmethod
    def _run(job: Job, work: Work) -> None:
        try:
            error = work(job)
        except Exception:
            logger.exception("material job %s crashed", job.id)
            error = "Something went wrong. Please try again."
        job.finish(error)

    def _forget_old(self) -> None:
        now = time.time()
        with self._lock:
            for jid in [
                j.id
                for j in self._jobs.values()
                if j.finished_at and now - j.finished_at > JOB_TTL_S
            ]:
                del self._jobs[jid]


_manager: JobManager | None = None


def get_jobs() -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager()
    return _manager
