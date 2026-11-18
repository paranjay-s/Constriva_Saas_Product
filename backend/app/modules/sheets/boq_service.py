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
from app.modules.sheets.boq_schemas import BoqAssumptions
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
    assumptions: BoqAssumptions | None = None,
) -> dict[str, Any]:
    """PlanJSON -> the BOQ response: item rows, warnings, geometry summary, metadata.

    Keeps every key `map_plan_to_materials` already returned. `assumptions` are the
    user's settings; the values actually used come back under `assumptions`.
    """
    chosen = assumptions or BoqAssumptions()
    result = map_plan_to_materials(
        plan,
        tile_pattern=chosen.tile_pattern,
        tile_size_mm=chosen.tile_size_mm,
        global_ceiling_height_m=chosen.ceiling_height_m,
        false_ceiling_share=chosen.false_ceiling_share,
        plot_perimeter_m=chosen.plot_perimeter_m,
        building_type=chosen.building_type,
    )
    result["project_metadata"]["source_file_name"] = source_file_name
    return result


def start_boq_job(
    jobs: BoqJobManager,
    owner_id: str,
    filename: str,
    pdf_bytes: bytes,
    parse_pdf: PlanPdfParser = default_pdf_parser,
    assumptions: BoqAssumptions | None = None,
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
        job.plan = plan
        job.emit("calculating")
        try:
            return build_boq_result(plan, filename, assumptions)
        except ValueError as e:
            raise BoqJobFailure(
                f"Quantities could not be calculated: {e}", "calculation_failed"
            ) from e

    return jobs.submit(owner_id, filename, work)


def recalculate_boq(job: BoqJob, assumptions: BoqAssumptions) -> dict[str, Any]:
    """The bill of a finished job again, with other assumptions.

    Works from the plan the job already parsed: no PDF is read and no model is called.
    Raises ValueError when the job has no plan (it failed, or is still running).
    """
    if job.plan is None or job.status != "done":
        raise ValueError("This bill has no parsed plan to calculate from.")
    result = build_boq_result(job.plan, job.filename, assumptions)
    job.replace_result(result)
    return result
