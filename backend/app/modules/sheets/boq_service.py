"""The BOQ flow: uploaded PDF -> PlanJSON -> material rows.

    job = start_boq_job(jobs, owner_id, filename, pdf_bytes, parse_pdf)

`parse_pdf` is the plan parser (parsing/llm_parser.parse_plan_pdf by default). When it
fails the job fails with the parser's own typed error; no other plan is ever used in its
place, because quantities for the wrong building are worse than no quantities.
"""

import logging
from collections.abc import Callable
from typing import Any

from app.modules.sheets.boq_jobs import BoqJob, BoqJobFailure, BoqJobManager
from app.modules.sheets.llm_mapper import map_plan_to_materials

logger = logging.getLogger("construtiva.sheets.boq")

# pdf bytes -> PlanJSON dict; raises ValueError (PlanParseError) when the plan is unreadable
PlanPdfParser = Callable[[bytes], dict[str, Any]]


def default_pdf_parser(pdf_bytes: bytes) -> dict[str, Any]:
    from app.modules.parsing.llm_parser import parse_plan_pdf

    return parse_plan_pdf(pdf_bytes, min_rooms=1)


def build_boq_result(
    plan: dict[str, Any],
    source_file_name: str = "",
    *,
    false_ceiling_share: float = 1.0,
    plot_perimeter_m: float | None = None,
) -> dict[str, Any]:
    """PlanJSON -> the BOQ response: item rows, warnings, geometry summary, metadata.

    Keeps every key `map_plan_to_materials` already returned. The two optional inputs are
    the user inputs of the formula spec: the share of the dry indoor area that gets a false
    ceiling (0 to 1), and the plot perimeter in metres for the site hoarding.
    """
    result = map_plan_to_materials(
        plan, false_ceiling_share=false_ceiling_share, plot_perimeter_m=plot_perimeter_m
    )
    result["project_metadata"]["source_file_name"] = source_file_name
    return result


def start_boq_job(
    jobs: BoqJobManager,
    owner_id: str,
    filename: str,
    pdf_bytes: bytes,
    parse_pdf: PlanPdfParser = default_pdf_parser,
    *,
    false_ceiling_share: float = 1.0,
    plot_perimeter_m: float | None = None,
) -> BoqJob:
    def work(job: BoqJob) -> dict[str, Any]:
        job.emit("uploading")
        job.emit("parsing")
        try:
            plan = parse_pdf(pdf_bytes)
        except ValueError as e:
            code = getattr(e, "code", "plan_parse_failed")
            logger.warning("boq job %s: plan not parsed (%s): %s", job.id, code, e)
            raise BoqJobFailure(str(e), code) from e
        job.emit("calculating")
        try:
            return build_boq_result(
                plan,
                filename,
                false_ceiling_share=false_ceiling_share,
                plot_perimeter_m=plot_perimeter_m,
            )
        except ValueError as e:
            raise BoqJobFailure(
                f"Quantities could not be calculated: {e}", "calculation_failed"
            ) from e

    return jobs.submit(owner_id, filename, work)
