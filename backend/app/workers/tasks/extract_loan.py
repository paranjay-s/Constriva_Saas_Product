"""
=============================================================================
Construtiva Celery Worker Task - Loan Comparison Analysis
=============================================================================
File: app/workers/tasks/extract_loan.py
Purpose:
  Asynchronous Celery task for comparing estimated construction material costs
  against target bank loan eligibility and interest amortization.
=============================================================================
"""

import logging
from typing import Dict, Any
from app.workers.celery_app import celery_app
from app.core.supabase import get_supabase_client
from app.modules.sheets.service import SheetService

logger = logging.getLogger("construtiva.workers.extract_loan")


@celery_app.task(
    name="app.workers.tasks.extract_loan.analyze_loan_comparison_task"
)
def analyze_loan_comparison_task(project_id: str, job_id: str) -> Dict[str, Any]:
    """
    Computes bank loan coverage against current BOQ material cost estimation.

    Args:
        project_id (str): UUID of project.
        job_id (str): UUID of job tracking record.

    Returns:
        Dict[str, Any]: Loan analysis metrics (coverage ratio, financing gap, recommended down payment).
    """
    logger.info(f"[Celery Worker] Running loan comparison for project {project_id}")
    supabase = get_supabase_client()

    try:
        # Fetch project details to retrieve target loan amount
        proj_res = supabase.table("projects").select("target_loan_amount").eq("id", project_id).execute()
        target_loan = float(proj_res.data[0].get("target_loan_amount") or 0.0) if proj_res.data else 0.0

        # Fetch current sheet total
        sheet = SheetService.get_or_create_sheet(project_id)
        total_construction_cost = float(sheet.get("total_cost") or 0.0)

        # Standard LTV (Loan-to-Value) calculation for construction: 75% max bank financing
        max_eligible_loan = round(total_construction_cost * 0.75, 2)
        required_down_payment = round(total_construction_cost * 0.25, 2)
        financing_gap = round(max(0.0, total_construction_cost - target_loan), 2)
        coverage_ratio = round((target_loan / total_construction_cost) * 100, 1) if total_construction_cost > 0 else 0.0

        analysis = {
            "project_id": project_id,
            "total_construction_cost": total_construction_cost,
            "target_loan_amount": target_loan,
            "max_eligible_bank_loan": max_eligible_bank_loan,
            "required_promoter_contribution": required_down_payment,
            "financing_gap": financing_gap,
            "coverage_ratio_percent": coverage_ratio,
            "status": "feasible" if target_loan <= max_eligible_loan else "needs_higher_equity",
        }

        # Update job
        supabase.table("jobs").update({
            "status": "done",
            "progress": 100,
            "step": "Loan feasibility analysis complete.",
            "result": analysis,
        }).eq("id", job_id).execute()

        return analysis

    except Exception as exc:
        logger.error(f"[Celery Worker] Loan analysis error: {exc}")
        supabase.table("jobs").update({
            "status": "failed",
            "error": str(exc),
        }).eq("id", job_id).execute()
        raise exc
