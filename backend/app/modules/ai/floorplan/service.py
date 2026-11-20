"""Floor plan use cases behind the API: parse a brief, generate (as a job), read, edit.

The router stays thin; everything here is plain synchronous code (it runs in worker
threads) and is easy to test without HTTP.
"""

import logging
import uuid
from datetime import UTC, datetime

from app.modules.ai.floorplan.jobs import Job
from app.modules.ai.floorplan.legacy_plan_json import to_legacy_plan_json
from app.modules.ai.floorplan.pipeline.brief_parser import parse_brief
from app.modules.ai.floorplan.pipeline.edit_engine import EditResult, edit_plan
from app.modules.ai.floorplan.pipeline.generate import generate_plan
from app.modules.ai.floorplan.pipeline.plan_tools import facing
from app.modules.ai.floorplan.pipeline.requirements import describe
from app.modules.ai.floorplan.schemas.api import (
    ChatMessage,
    EditRequest,
    EditResponse,
    FloorplanSummary,
    ParseBriefRequest,
    ParseBriefResponse,
    PlanResponse,
    VersionInfo,
)
from app.modules.ai.floorplan.schemas.brief import Brief, BriefForm
from app.modules.ai.floorplan.schemas.plan import FloorPlan
from app.modules.ai.floorplan.schemas.program import RoomProgram
from app.modules.ai.floorplan.store import MAX_HISTORY, PlanStore, StoredPlan
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
    from app.modules.ai.floorplan.model.areas import area_lines
    from app.modules.ai.floorplan.model.build import build_building

    areas = area_lines(build_building(res.plan).areas, brief.plot.input_unit)
    notes = [*areas, *brief.assumptions, *res.warnings]
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
    sp.model = getattr(llm, "model", "") or ""
    store.create(sp)
    return plan_id, None, []


def to_response(sp: StoredPlan) -> PlanResponse:
    return PlanResponse(
        id=sp.id,
        project_id=sp.project_id,
        name=sp.name,
        version=sp.version,
        plan=sp.plan,
        svg=preview_svg(sp),
        brief=sp.brief,
        notes=sp.notes,
        messages=[ChatMessage.model_validate(m) for m in sp.messages],
        plan_json=to_legacy_plan_json(sp.plan),
        saved=sp.saved,
        history=[
            VersionInfo(version=h["version"], change=h.get("change", ""), at=h.get("at", ""))
            for h in reversed(sp.history)
        ],
        facing=facing(sp.plan),
        areas=_area_lines(sp),
    )


def preview_svg(sp: StoredPlan) -> str:
    """The in-app preview: the same sheet as the PDF, font embedded (it is shown as an
    image, which cannot load fonts from the page)."""
    from app.modules.ai.floorplan.drawing.compose import compose_sheet
    from app.modules.ai.floorplan.drawing.emit import to_svg

    return to_svg(compose_sheet(building_for(sp)), embed_font=True)


def _area_lines(sp: StoredPlan) -> list[str]:
    from app.modules.ai.floorplan.model.areas import area_lines

    try:
        return area_lines(building_for(sp).areas, sp.plan.meta.unit_display)
    except Exception:  # the statement is informative; never fail a read over it
        logger.exception("could not compute the areas of plan %s", sp.id)
        return []


def list_plans(store: PlanStore, owner_id: str, project_id: str | None) -> list[FloorplanSummary]:
    return [FloorplanSummary.model_validate(r) for r in store.list_for(owner_id, project_id)]


def restore(sp: StoredPlan, version: int | None, store: PlanStore) -> EditResponse:
    """The Undo button / version list: same as asking "undo" in the chat."""
    asked = "Undo" if version is None else f"Go back to version {version}"
    sp.messages.append(ChatMessage(role="user", text=asked).model_dump())
    done, msg = revert(sp, version, store)
    status = "ok" if done else "no_change"
    sp.messages.append(
        ChatMessage(role="assistant", text=msg, status=status, version=sp.version).model_dump()
    )
    store.update(sp)
    return EditResponse(
        status=status, message=msg, summary=[msg] if done else [], plan=to_response(sp)
    )


# --------------------------------------------------------------------- history


def _snapshot(sp: StoredPlan, change: str) -> None:
    """Keep the current version so it can be restored ("undo", "go back to version 3")."""
    sp.history.append(
        {
            "version": sp.version,
            "floorplan": sp.plan.model_dump(mode="json", by_alias=True),
            "program": sp.program.model_dump(mode="json") if sp.program else None,
            "change": change[:200],
            "at": datetime.now(UTC).isoformat(),
            "model": sp.model,
        }
    )
    sp.history = sp.history[-MAX_HISTORY:]


def _sync_brief(sp: StoredPlan) -> None:
    """Keep the stored brief's plot in step with the plan (after a turn, a plot change)."""
    if sp.brief is None:
        return
    plot = sp.brief.plot.model_copy(
        update={"width_cm": sp.plan.plot.width, "depth_cm": sp.plan.plot.depth}
    )
    update: dict = {"plot": plot}
    if "road_side" in type(sp.brief).model_fields:
        update["road_side"] = sp.plan.plot.road_side
    try:
        sp.brief = sp.brief.model_copy(update=update)
    except Exception as e:  # the brief is informative only; never fail an edit over it
        logger.warning("could not update the brief of plan %s: %s", sp.id, e)


def revert(sp: StoredPlan, version: int | None, store: PlanStore) -> tuple[bool, str]:
    """Restore an earlier version as the newest one. Returns (done, message)."""
    if not sp.history:
        return False, "There is no earlier version to go back to yet."
    if version is None:
        target = sp.history[-1]
    else:
        target = next((h for h in sp.history if h["version"] == version), None)
        if target is None:
            if version == sp.version:
                return False, f"This is already version {version}."
            kept = ", ".join(str(h["version"]) for h in sp.history)
            return (
                False,
                f"Version {version} is not kept any more. Versions you can go back to: {kept}.",
            )
    idx = sp.history.index(target)
    sp.history = sp.history[:idx]  # versions after it are dropped, like a normal undo stack
    sp.plan = FloorPlan.model_validate(target["floorplan"])
    sp.program = RoomProgram.model_validate(target["program"]) if target.get("program") else None
    old = target["version"]
    sp.version += 1
    _sync_brief(sp)
    return True, f"Back to version {old} (saved as version {sp.version})."


def _choose_option(sp: StoredPlan, n: int) -> EditResult:
    if not 1 <= n <= len(sp.options):
        msg = (
            "There is no layout option to choose right now."
            if not sp.options
            else f"Choose option 1 to {len(sp.options)}."
        )
        return EditResult("no_change", sp.plan, sp.program or RoomProgram(rooms=[]), message=msg)
    opt = sp.options[n - 1]
    plan = FloorPlan.model_validate(opt["floorplan"])
    program = RoomProgram.model_validate(opt["program"])
    res = EditResult("ok", plan, program, summary=[f"Used option {n}, {opt['label']}."])
    res.resolved = True
    return res


def edit(
    sp: StoredPlan,
    req: EditRequest,
    llm: LLMClient | None,
    store: PlanStore,
    progress=None,
) -> EditResponse:
    res = edit_plan(
        sp.plan, sp.program, req.message, llm, allow_reflow=req.allow_reflow, progress=progress
    )
    sp.messages.append(ChatMessage(role="user", text=req.message).model_dump())
    if res.choose is not None:
        res = _choose_option(sp, res.choose)
    if res.options:
        sp.options = [
            {
                "label": o.label,
                "floorplan": o.plan.model_dump(mode="json", by_alias=True),
                "program": o.program.model_dump(mode="json"),
            }
            for o in res.options[:2]
        ]
    if res.undo is not None:
        done, msg = revert(sp, res.undo.version, store)
        res = EditResult("ok" if done else "no_change", sp.plan, sp.program, message=msg)
        res.summary = [msg] if done else []
        reply = msg
    elif res.status == "info":
        reply = res.message
    elif res.ok:
        _snapshot(sp, req.message)
        sp.plan, sp.program = res.plan, res.program
        sp.model = getattr(llm, "model", "") or ""
        sp.options = []  # offered layouts belong to the version they were offered for
        sp.version += 1
        _sync_brief(sp)
        reply = "Done. " + " ".join(res.summary) if res.summary else "Done."
        lines = _area_lines(sp)
        if lines:
            reply += " " + lines[0] + "."
    else:
        reply = res.message
        if res.alternatives:
            reply += " You could: " + " / ".join(res.alternatives)
    if res.warnings and res.status != "info":
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


def building_for(sp: StoredPlan):
    """The building model of a stored plan's current version, with its revision list
    (one line per kept version) and the AI model that made each version."""
    from app.modules.ai.floorplan.model.build import build_building
    from app.modules.ai.floorplan.model.building import Revision

    # history[i] is version history[i].version, kept when the message history[i].change
    # made the next version; so each version's description is the previous entry's change
    versions = [(h["version"], (h.get("at") or "")[:10], h.get("model", "")) for h in sp.history]
    now = datetime.now(UTC).strftime("%Y-%m-%d")
    versions.append((sp.version, now, getattr(sp, "model", "") or ""))
    changes = ["First issue"] + [(h.get("change") or "Revision")[:80] for h in sp.history]
    revisions = [
        Revision(rev=f"V{v}", date=d, description=c, model=m)
        for (v, d, m), c in zip(versions, changes, strict=True)
    ]
    return build_building(
        sp.plan, version=sp.version, revisions=revisions[-6:], model=getattr(sp, "model", "")
    )


def run_edit(
    job: Job, sp: StoredPlan, req: EditRequest, llm: LLMClient | None, store: PlanStore
) -> tuple[str | None, str | None, list[str]]:
    """Job body of a chat edit: progress goes to the chat (a full re-solve takes up to
    FLOORPLAN_FULL_RESOLVE_S); the reply is the newest assistant message of the plan."""
    job.emit("layout", "Reading your request")
    edit(sp, req, llm, store, progress=lambda stage, detail: job.emit(stage, detail))
    return sp.id, None, []


def plan_for_3d(plan_id: str, owner_id: str, store: PlanStore | None = None) -> dict | None:
    """A generated plan, for the 3D builder: its name, version, PlanJSON and the PDF export
    the review page shows behind it. None unless the plan exists and is the user's."""
    from app.modules.ai.floorplan.render.exports import export_plan
    from app.modules.ai.floorplan.store import get_store

    try:
        sp = (store or get_store()).get(plan_id)
    except Exception:  # the plan store is unreachable: the 3D builder reads the drawing instead
        logger.warning("could not look up floor plan %s for 3D", plan_id)
        return None
    if sp is None or not owner_id or sp.owner_id != owner_id:
        return None
    from app.modules.ai.floorplan.model.planto3d import to_planto3d

    building = building_for(sp)
    return {
        "id": sp.id,
        "name": sp.name,
        "version": sp.version,
        "project_id": sp.project_id,
        "plan_json": to_legacy_plan_json(sp.plan),
        "planto3d": to_planto3d(building, source_name=f"{sp.name}.pdf"),
        "building": building.to_json_dict(),
        "pdf": export_plan(sp.plan, "pdf", version=sp.version, building=building).data,
    }


def stored_plan_for_pdf(
    pdf_bytes: bytes, owner_id: str, store: PlanStore | None = None
) -> dict | None:
    """The generated plan an uploaded PDF was exported from (its plan reference), when that
    plan exists and is the user's; else None. See plan_for_3d."""
    from app.modules.ai.floorplan.render.exports import read_plan_reference

    ref = read_plan_reference(pdf_bytes)
    return plan_for_3d(ref.plan_id, owner_id, store) if ref else None
