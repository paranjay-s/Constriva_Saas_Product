"""
=============================================================================
Construtiva Celery Worker Task - BOQ Report & PDF Export Generator
=============================================================================
File: app/workers/tasks/build_report.py
Purpose:
  Asynchronous Celery task for generating heavy architectural cost estimation
  reports and exporting PDF/CSV documents directly to Supabase Storage.
=============================================================================
"""

import uuid
import logging
from typing import Dict, Any
from app.workers.celery_app import celery_app
from app.core.supabase import get_supabase_client, upload_to_storage
from app.modules.sheets.service import SheetService
from app.modules.sheets.export import generate_sheet_pdf

logger = logging.getLogger("construtiva.workers.build_report")


@celery_app.task(
    bind=True,
    name="app.workers.tasks.build_report.generate_report_task",
    max_retries=2,
)
def generate_report_task(self, project_id: str, user_id: str, job_id: str) -> Dict[str, Any]:
    """
    Renders an architectural PDF report for a project in the background and uploads
    it to the 'blueprints' or 'reports' Supabase Storage bucket.

    Args:
        project_id (str): UUID of the project.
        user_id (str): UUID of the requesting user.
        job_id (str): UUID of the background tracking job.

    Returns:
        Dict[str, Any]: Storage key and public/signed file ID.
    """
    logger.info(f"[Celery Worker] Generating BOQ report for project {project_id}")
    supabase = get_supabase_client()

    try:
        # 1. Fetch active sheet
        sheet = SheetService.get_or_create_sheet(project_id)

        # 2. Render PDF bytes via ReportLab / PyMuPDF
        pdf_bytes = generate_sheet_pdf(sheet, project_name=f"Project_{project_id[:8]}")

        # Cache in Redis so user can download instantly
        try:
            import redis
            from app.core.config import settings
            r = redis.from_url(settings.redis_url, socket_timeout=1)
            r.setex(f"cache:pdf:{project_id}", 3600, pdf_bytes)
            logger.info(f"[Celery Worker] Cached generated PDF for project {project_id} in Redis.")
        except Exception as redis_err:
            logger.debug(f"[Celery Worker] Redis cache write skipped: {redis_err}")

        # 3. Upload to Supabase Storage
        file_id = str(uuid.uuid4())
        storage_path = f"{project_id}/reports/BOQ_Report_{file_id[:8]}.pdf"
        storage_key = upload_to_storage(
            bucket_name="blueprints",
            file_path=storage_path,
            file_bytes=pdf_bytes,
            content_type="application/pdf",
        )

        # 4. Record in public.files
        supabase.table("files").insert({
            "id": file_id,
            "project_id": project_id,
            "user_id": user_id,
            "kind": "report",
            "name": f"BOQ_Cost_Report_{project_id[:8]}.pdf",
            "storage_key": storage_key,
            "mime_type": "application/pdf",
            "size_bytes": len(pdf_bytes),
            "status": "uploaded",
        }).execute()

        # 5. Update job status
        supabase.table("jobs").update({
            "status": "done",
            "progress": 100,
            "step": "Report generated and archived successfully.",
            "result": {"file_id": file_id, "storage_key": storage_key},
        }).eq("id", job_id).execute()

        return {"file_id": file_id, "storage_key": storage_key}

    except Exception as exc:
        logger.error(f"[Celery Worker] Report generation failed: {exc}")
        supabase.table("jobs").update({
            "status": "failed",
            "error": str(exc),
        }).eq("id", job_id).execute()
        raise self.retry(exc=exc)
