"""
=============================================================================
Construtiva Celery Worker Task - 2D Floor Plan Blueprint Parsing
=============================================================================
File: app/workers/tasks/parse_plan.py
Purpose:
  Asynchronous Celery task for long-running blueprint processing:
  1. Ingests raw PDF bytes from Supabase Storage or request payload.
  2. Rasterizes Page 1 to high-resolution 300 DPI PNG via PyMuPDF.
  3. Prepares raster image for Vision LLM geometric coordinate extraction.
  4. Saves PlanJSON into Supabase 'plans' and updates 'jobs' table progress
     (10% -> 45% -> 65% -> 90% -> 100%) so SSE can stream updates to the frontend.
=============================================================================
"""

import asyncio
import logging
from typing import Dict, Any
from app.workers.celery_app import celery_app
from app.modules.parsing.service import ParsingService

logger = logging.getLogger("construtiva.workers.parse_plan")


@celery_app.task(
    bind=True,
    name="app.workers.tasks.parse_plan.process_blueprint_task",
    max_retries=3,
    default_retry_delay=10,
)
def process_blueprint_task(
    self,
    pdf_bytes_hex: str,
    filename: str,
    project_id: str,
    user_id: str,
    job_id: str,
) -> Dict[str, Any]:
    """
    Celery background worker entrypoint for processing architectural floor plan blueprints.

    Args:
        pdf_bytes_hex (str): Hex-encoded or base64 binary content of the PDF.
        filename (str): Original uploaded file name.
        project_id (str): UUID of the parent project.
        user_id (str): UUID of the requesting user.
        job_id (str): UUID of the job record in public.jobs.

    Returns:
        Dict[str, Any]: Extracted plan ID, storage keys, and dimensions.
    """
    logger.info(f"[Celery Worker] Starting parsing job {job_id} for project {project_id}")

    try:
        pdf_bytes = bytes.fromhex(pdf_bytes_hex)

        # Run asynchronous parsing pipeline synchronously inside worker thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            ParsingService.process_blueprint_pdf(
                pdf_bytes=pdf_bytes,
                filename=filename,
                project_id=project_id,
                user_id=user_id,
                job_id=job_id,
            )
        )
        loop.close()

        logger.info(f"[Celery Worker] Successfully completed parsing job {job_id}")
        return result

    except Exception as exc:
        logger.error(f"[Celery Worker] Error during blueprint parsing: {exc}")
        ParsingService.update_job_progress(
            job_id=job_id,
            step=f"Worker processing failed: {str(exc)}",
            progress=0,
            status="failed",
        )
        raise self.retry(exc=exc)
