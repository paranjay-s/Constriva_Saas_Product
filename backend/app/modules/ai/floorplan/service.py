"""Floor plan use cases behind the API: parse a brief, generate (as a job), read, edit.

The router stays thin; everything here is plain synchronous code (it runs in worker
threads) and is easy to test without HTTP.
"""

import logging
import uuid

from app.modules.ai.floorplan.jobs import Job
from app.modules.ai.floorplan.legacy_plan_json import to_legacy_plan_json
from app.modules.ai.floorplan.pipeline.brief_parser import parse_brief
from app.modules.ai.floorplan.pipeline.edit_engine import edit_plan
from app.modules.ai.floorplan.pipeline.generate import generate_plan
from app.modules.ai.floorplan.pipeline.requirements import describe
from app.modules.ai.floorplan.render.svg_renderer import render_svg
from app.modules.ai.floorplan.schemas.api import (
    ChatMessage,
    EditRequest,
    EditResponse,
    ParseBriefRequest,
    ParseBriefResponse,
    PlanResponse,
)
from app.modules.ai.floorplan.schemas.brief import Brief, BriefForm
from app.modules.ai.floorplan.store import PlanStore, StoredPlan
from app.modules.ai.llm.client import LLMClient

logger = logging.getLogger("construtiva.ai.floorplan.service")


def parse(req: ParseBriefRequest, llm: LLMClient | None) -> ParseBriefResponse:
    form = BriefForm.model_validate(req.model_dump())
    res = parse_brief(form, llm)
    return ParseBriefResponse(
        brief=res.brief,
        summary=describe(res.brief),
        warnings=res.warnings,
        missing=res.missing,
        ready=res.ready,
    )


def plan_name(brief: Brief) -> str:
    if brief.project_name.strip():
        return brief.project_name.strip()[:120]
    unit = brief.plot.input_unit
    if unit == "ft":
        w, d = round(brief.plot.width_cm / 30.48), round(brief.plot.depth_cm / 30.48)
        size = f"{w}x{d} ft"
    else:
        size = f"{brief.plot.width_cm / 100:g}x{brief.plot.depth_cm / 100:g} m"
    return f"{describe(brief).split(' (')[0].capitalize()} plan, {size}"


def run_generation(
    job: Job,
    brief: Brief,
    project_id: str | None,
    llm: LLMClient | None,
    store: PlanStore,
) -> tuple[str | None, str | None, list[str]]:
    """Job body: generate, save, and return (plan_id, error, options)."""
    plan_id = str(uuid.uuid4())

    def progress(stage: str, detail: str) -> None:
        if stage != "done":  # the job reports done itself, after the plan is saved
            job.emit(stage, detail)

    res = generate_plan(brief, llm=llm, progress=progress, plan_id=plan_id)
    if not res.ok or res.plan is None:
        options = res.feasibility.options if res.feasibility and not res.feasibility.ok else []
        return None, res.message or "No plan could be made for this brief.", options
    job.emit("saving", "Saving the plan")
    notes = [*brief.assumptions, *res.warnings]
    sp = StoredPlan(
        id=plan_id,
        owner_id=job.owner_id,
        name=plan_name(brief),
        project_id=project_id,
        plan=res.plan,
        program=res.program,
        brief=brief,
        notes=list(dict.fromkeys(notes)),
    )
    store.create(sp)
    return plan_id, None, []


def to_response(sp: StoredPlan) -> PlanResponse:
    return PlanResponse(
        id=sp.id,
        project_id=sp.project_id,
        name=sp.name,
        version=sp.version,
        plan=sp.plan,
        svg=render_svg(sp.plan),
        brief=sp.brief,
        notes=sp.notes,
        messages=[ChatMessage.model_validate(m) for m in sp.messages],
        plan_json=to_legacy_plan_json(sp.plan),
        saved=sp.saved,
    )


def edit(sp: StoredPlan, req: EditRequest, llm: LLMClient | None, store: PlanStore) -> EditResponse:
    res = edit_plan(sp.plan, sp.program, req.message, llm, allow_reflow=req.allow_reflow)
    sp.messages.append(ChatMessage(role="user", text=req.message).model_dump())
    if res.ok:
        sp.plan, sp.program = res.plan, res.program
        sp.version += 1
        reply = "Done. " + " ".join(res.summary) if res.summary else "Done."
    else:
        reply = res.message
        if res.alternatives:
            reply += " You could: " + " / ".join(res.alternatives)
    if res.warnings:
        reply += " (" + " ".join(res.warnings) + ")"
    sp.messages.append(
        ChatMessage(
            role="assistant", text=reply.strip(), status=res.status, version=sp.version
        ).model_dump()
    )
    store.update(sp)  # the chat history is kept even when nothing changed
    return EditResponse(
        status=res.status,
        message=res.message,
        summary=res.summary,
        alternatives=res.alternatives,
        warnings=res.warnings,
        plan=to_response(sp),
    )
