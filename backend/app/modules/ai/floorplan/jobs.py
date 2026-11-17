"""Background generation jobs with progress events (in-process).

Generation takes 5-30 s (LLM + solver), so POST /generate returns a job id at once and
the work runs in a worker thread. Each step is recorded as a JobEvent; the SSE endpoint
replays the recorded events first (so a reconnect never misses one) and then waits for
new ones.

Limits: jobs live in this process's memory, so this needs a single API worker (as in
dev). A finished job is forgotten after JOB_TTL_S. Moving to Celery/Redis later only
changes this file.
"""

import logging
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.modules.ai.floorplan.schemas.api import JobEvent, JobState, JobStatus
from app.modules.ai.jobs_common import stream_events  # noqa: F401  (re-exported for the router)

logger = logging.getLogger("construtiva.ai.floorplan.jobs")

JOB_TTL_S = 3600
MAX_PARALLEL_JOBS = 2  # the solver is CPU heavy; more jobs wait in the queue

# rough share of the total time each stage starts at
STAGE_PROGRESS = {
    "queued": 0,
    "feasibility": 5,
    "program": 15,
    "layout": 35,
    "checking": 80,
    "saving": 92,
    "done": 100,
}


@dataclass
class Job:
    id: str
    owner_id: str
    status: JobStatus = "queued"
    events: list[JobEvent] = field(default_factory=list)
    plan_id: str | None = None
    error: str | None = None
    options: list[str] = field(default_factory=list)
    finished_at: float | None = None
    _cond: threading.Condition = field(default_factory=threading.Condition)

    def state(self) -> JobState:
        last = self.events[-1] if self.events else self._event("queued", "")
        return JobState(**last.model_dump(), events=list(self.events))

    def _event(self, stage: str, detail: str) -> JobEvent:
        pct = STAGE_PROGRESS.get(stage, self.events[-1].progress if self.events else 0)
        if stage == "layout" and "attempt" in detail:  # "attempt 2 of 3" moves the bar on
            try:
                n, total = (int(x) for x in detail.split("attempt", 1)[1].split("of"))
                pct = 35 + round(40 * (n - 1) / max(total, 1))
            except ValueError:
                pass
        return JobEvent(
            job_id=self.id,
            status=self.status,
            stage=stage,
            detail=detail,
            progress=pct,
            plan_id=self.plan_id,
            error=self.error,
            options=self.options,
        )

    def emit(self, stage: str, detail: str = "") -> None:
        with self._cond:
            if self.status == "queued":
                self.status = "running"
            self.events.append(self._event(stage, detail))
            self._cond.notify_all()

    def finish(self, plan_id: str | None, error: str | None, options: list[str]) -> None:
        with self._cond:
            self.plan_id, self.error, self.options = plan_id, error, options
            self.status = "done" if error is None else "failed"
            self.finished_at = time.time()
            stage, detail = ("done", "Plan ready") if error is None else ("failed", error)
            ev = self._event(stage, detail)
            if error is not None:
                ev.progress = self.events[-1].progress if self.events else 0
            self.events.append(ev)
            self._cond.notify_all()

    @property
    def finished(self) -> bool:
        return self.status in ("done", "failed")

    def wait_for(self, seen: int, timeout: float) -> None:
        """Block until there are more than `seen` events, the job ends, or timeout."""
        with self._cond:
            if len(self.events) <= seen and not self.finished:
                self._cond.wait(timeout)


# work(job) runs in a worker thread and returns (plan_id, error, options)
Work = Callable[[Job], tuple[str | None, str | None, list[str]]]


class JobManager:
    def __init__(self, max_parallel: int = MAX_PARALLEL_JOBS) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=max_parallel, thread_name_prefix="fp-job")

    def submit(self, owner_id: str, work: Work) -> Job:
        self._forget_old()
        job = Job(id=uuid.uuid4().hex, owner_id=owner_id)
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
            plan_id, error, options = work(job)
        except Exception:  # never leave a job running forever
            logger.exception("floor plan job %s crashed", job.id)
            plan_id, error, options = None, "Something went wrong while making the plan.", []
        job.finish(plan_id, error, options)

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
