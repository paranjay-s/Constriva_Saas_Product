"""
=============================================================================
Construtiva Worker Tasks Initialization
=============================================================================
File: app/workers/tasks/__init__.py
Purpose:
  Imports Celery tasks so they register with Celery worker discovery on startup.
=============================================================================
"""

from app.workers.tasks.build_report import generate_report_task
from app.workers.tasks.extract_loan import analyze_loan_comparison_task

__all__ = [
    "generate_report_task",
    "analyze_loan_comparison_task",
]
