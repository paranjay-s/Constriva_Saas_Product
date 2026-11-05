# 06 Workers and realtime

Slow work never runs inside a request. The API starts a job, a Celery worker runs it, and the browser follows progress over SSE.

## Flow

```
Browser           FastAPI                Redis              Celery worker
  | POST parse --->  create job row                              |
  |                  enqueue task ---------> queue ------------> run
  | <--- 202 + job_id                                            |
  | GET /events/jobs/<id> (SSE)                                  | publish progress
  | <------------ events <---- subscribe <---- pub/sub <--------- |
  |                                                              | save result, mark job done
```

## `app/workers/`

| File | Purpose |
|---|---|
| `celery_app.py` | Celery configuration: Redis broker, queues, retry defaults, task time limits. |
| `tasks/parse_plan.py` | Loads the PDF from S3, runs `parsing.service`, saves a plan version, updates the job. |
| `tasks/build_report.py` | Builds the material report (PDF) or spreadsheet and stores it in S3. |
| `tasks/extract_loan.py` | Placeholder for loan document extraction. |

## Queues

| Queue | Used for | Notes |
|---|---|---|
| `default` | Light jobs | Small, fast tasks. |
| `parsing` | PDF parsing, image processing, model inference | Heavy. Can run on its own machine or GPU later. |
| `reports` | Report and export generation | Independent from parsing so one cannot starve the other. |

The worker image installs the same dependencies as the API. If the segmentation model grows heavy, build a separate image for the `parsing` queue that adds the `ml` extra.

## Job lifecycle

`queued -> running -> done | failed`, with a `progress` number from 0 to 100 and an `error` message on failure. Tasks update the `jobs` row and publish an event at each step.

## Events

| File | Purpose |
|---|---|
| `events/pubsub.py` | `publish(job_id, event)` and `subscribe(job_id)` on Redis channels. |
| `events/sse.py` | `GET /events/jobs/{job_id}`: checks the user owns the job, subscribes, and streams events. Sends a heartbeat so proxies keep the connection open. |

Event example:

```json
{ "job_id": "...", "status": "running", "progress": 60, "step": "validating plan" }
```

If the browser reconnects, the endpoint first sends the current job state from the database, so a missed event does not leave the UI stuck.

## Rules

1. Tasks must be idempotent: running one twice must not create duplicate plan versions.
2. Tasks read inputs from S3 and the database, never from request memory.
3. Every task updates its job row, including on failure.

