"""Material finder orchestration.

    start_analysis   photos + focus (+ space) -> session + background job:
                     uploading -> analysing_image -> matching_materials -> calculating
                     -> writing_summary -> done
    recalculate      new dimensions / wastage / coverage -> new report (no vision call)
    chat             follow-up message (+ optional plan file) -> answer, one question,
                     or a job (plan parsing / new focus)

Quantities always come from calculator.py; the LLMs only see and classify.
"""

import logging
import re
import uuid
from dataclasses import dataclass, field

from app.modules.ai.llm.client import LLMClient, LLMError, VisionLLMClient
from app.modules.ai.material_agent import compose, explain, tools, vision
from app.modules.ai.material_agent.calculator import Applied, build_report, coverage_shares
from app.modules.ai.material_agent.chat import (
    MONEY_ANSWER,
    answer_to_pending,
    interpret,
    is_whole_design,
    space_from_text,
)
from app.modules.ai.material_agent.geometry import LAYOUT_OPTIONS, NeedsInput, application_area
from app.modules.ai.material_agent.jobs import Job, JobManager
from app.modules.ai.material_agent.normalise import find_material, normalise
from app.modules.ai.material_agent.plan_upload import (
    PLAN_MIME,
    PlanParser,
    PlanUploadError,
    store_file,
)
from app.modules.ai.material_agent.projects import ProjectSource, find_project, own_project
from app.modules.ai.material_agent.schemas import (
    ApplicationRequest,
    ChatIntent,
    ChatMessage,
    ChatReply,
    ManualSpace,
    Material,
    RecalculateRequest,
    RoomGeom,
    SessionView,
    TargetSpace,
)
from app.modules.ai.material_agent.settings import get_settings
from app.modules.ai.material_agent.space import (
    choice_labels,
    looks_like_a_choice,
    manual_target,
    match_room,
    plan_target,
    room_kind,
    rooms_from_plan,
)
from app.modules.ai.material_agent.store import Session, SessionStore
from app.modules.ai.material_agent.units import fmt, to_ft

logger = logging.getLogger("construtiva.ai.material.service")

APPLICATION_OPTIONS = {
    "Kitchen platform": "platform",
    "Floor": "floor",
    "All walls": "all_walls",
    "One wall": "one_wall",
    "Ceiling": "ceiling",
    "Backsplash": "backsplash",
}
APPLICATION_NAMES = {v: k.lower() for k, v in APPLICATION_OPTIONS.items()}


class ServiceError(ValueError):
    """Bad input; the message is safe to show (HTTP 400)."""


@dataclass
class Deps:
    store: SessionStore
    jobs: JobManager
    projects: ProjectSource
    vision_llm: VisionLLMClient | None
    text_llm: LLMClient | None
    plan_parser: PlanParser
    vision_model: str = ""
    store_files: bool = True


@dataclass
class Upload:
    data: bytes
    mime: str
    name: str = ""


@dataclass
class Reply:
    status: str
    message: str
    options: list[str] = field(default_factory=list)
    job_id: str | None = None


# ------------------------------------------------------------------- views


def view(s: Session) -> SessionView:
    pending = None
    if s.pending:
        pending = ChatMessage(
            role="assistant",
            text=s.pending.get("question", ""),
            status="needs_input",
            options=s.pending.get("options") or [],
        )
    return SessionView(
        id=s.id,
        project_id=s.project_id,
        project_name=s.project_name,
        focus=s.focus,
        scene=s.analysis.scene if s.analysis else "",
        focus_found=s.analysis.focus_found if s.analysis else True,
        focus_note=s.analysis.focus_note if s.analysis else "",
        materials=s.materials,
        report=s.report,
        messages=s.messages,
        pending_question=pending,
        uploaded_plan_name=s.uploaded_plan_name,
        saved=s.saved,
    )


def own_session(deps: Deps, sid: str, user_id: str) -> Session | None:
    s = deps.store.get(sid)
    return s if s and s.owner_id == user_id else None


# ----------------------------------------------------------- calculations


def recompute(deps: Deps, s: Session, *, explain: bool = False) -> list[NeedsInput]:
    version = (s.report.version + 1) if s.report else 1
    result = build_report(s.materials, s.target, s.applied, s.overrides, version)
    report = result.report
    report.explanation = (
        compose.explain(deps.text_llm, report, s.materials)
        if explain
        else compose.template_explanation(report, s.materials)
    )
    s.report = report
    return result.questions


def _project_rooms(deps: Deps, s: Session) -> tuple[list[RoomGeom], str] | None:
    """Rooms of the uploaded plan (preferred) or of the session's project plan."""
    if s.uploaded_plan:
        return rooms_from_plan(s.uploaded_plan), "uploaded_plan"
    if s.project_id:
        try:
            plan = deps.projects.latest_plan(s.project_id)
        except Exception as e:
            logger.warning("could not read project plan: %s", e)
            plan = None
        if plan:
            return rooms_from_plan(plan), "project"
    return None


def _initial_target(
    deps: Deps, user_id: str, space: ManualSpace | None, project_id: str | None, room: str
) -> tuple[TargetSpace | None, str | None, str | None]:
    """(target, project_id, project_name) for a new analysis."""
    if space is not None:
        try:
            return manual_target(space), project_id, None
        except ValueError as e:
            raise ServiceError(str(e)) from e
    if not project_id:
        return None, None, None
    project = own_project(deps.projects, user_id, project_id)
    if project is None:
        return None, None, None  # not the user's project: ignore it silently
    if not room:
        return None, project.id, project.name
    plan = deps.projects.latest_plan(project.id)
    rooms = rooms_from_plan(plan) if plan else []
    match = match_room(rooms, room)
    if match.room:
        return (
            plan_target(match.room, "project", project.id, project.name),
            project.id,
            project.name,
        )
    return None, project.id, project.name


# ---------------------------------------------------------------- analysis


def start_analysis(
    deps: Deps,
    user_id: str,
    images: list[Upload],
    focus_areas: list[str],
    focus_note: str,
    space: ManualSpace | None = None,
    project_id: str | None = None,
    room: str = "",
) -> tuple[Session, Job]:
    settings = get_settings()
    if not images:
        raise ServiceError("Add at least one photo.")
    if len(images) > settings.max_images:
        raise ServiceError(f"Up to {settings.max_images} photos at a time.")
    try:
        prepared = [vision.prepare_image(i.data, i.mime) for i in images]
    except vision.ImageError as e:
        raise ServiceError(str(e)) from e
    if space is None and not project_id:
        space = space_from_text(focus_note)  # a size typed in the prompt
    target, pid, pname = _initial_target(deps, user_id, space, project_id, room)
    s = Session(
        id=str(uuid.uuid4()),
        owner_id=user_id,
        project_id=pid,
        project_name=pname,
        focus=vision.focus_text(focus_areas, focus_note),
        image_hashes=[p.sha256 for p in prepared],
        target=target,
    )
    deps.store.create(s)

    def work(job: Job) -> str | None:
        job.emit("uploading")
        for p in prepared:
            vision.save_image(p)
            if deps.store_files:
                _store_photo(user_id, s, p)
        return _run_analysis(deps, s.id, prepared, job)

    job = deps.jobs.submit(user_id, s.id, work)
    return s, job


def _store_photo(user_id: str, s: Session, p: vision.PreparedImage) -> None:
    try:
        from app.core.supabase import upload_to_storage

        upload_to_storage(
            "site-photos", f"{user_id}/material_finder/{s.id}/{p.sha256[:16]}.jpg", p.data, p.mime
        )
    except Exception as e:  # the analysis does not depend on it
        logger.info("material photo not stored: %s", e)


def _run_analysis(
    deps: Deps, sid: str, prepared: list[vision.PreparedImage], job: Job
) -> str | None:
    s = deps.store.get(sid)
    if s is None:
        return "The session was lost. Please start again."
    if deps.vision_llm is None:
        return "Photo analysis is not configured (missing AI key)."
    job.emit("analysing_image")
    try:
        analysis = vision.analyse(deps.vision_llm, prepared, s.focus, deps.vision_model)
    except LLMError as e:
        logger.warning("material vision failed: %s", e)
        return "The photo could not be analysed right now. Please try again in a minute."
    job.emit("matching_materials")
    s.analysis = analysis
    s.materials = normalise(analysis.materials)
    s.applied = []
    job.emit("calculating")
    questions = recompute(deps, s, explain=False)
    job.emit("writing_summary")
    assert s.report is not None
    # the tables show the result; a template summary avoids another model call (speed)
    s.report.explanation = compose.template_explanation(s.report, s.materials)
    if not s.materials:
        text = analysis.focus_note or "I could not identify finish materials in this photo."
        s.say("assistant", text, status="not_found")
    elif not analysis.focus_found:
        s.say(
            "assistant",
            f"{analysis.focus_note or 'The area you asked for is not clearly visible.'} "
            "Showing the materials I can see.",
            status="ok",
        )
    else:
        s.say("assistant", _found_text(s), status="ok")
    for q in questions[:1]:
        s.say("assistant", q.question, status="needs_input", options=q.options)
    job.emit("saving")
    deps.store.update(s)
    return None


# ------------------------------------------------------------- recalculate


def recalculate(deps: Deps, s: Session, body: RecalculateRequest) -> Session:
    if body.space is not None:
        try:
            s.target = manual_target(body.space)
        except ValueError as e:
            raise ServiceError(str(e)) from e
    merged = s.overrides.model_copy(deep=True)
    merged.wastage_pct.update(body.overrides.wastage_pct)
    merged.coverage_ratio.update(
        {k: min(max(v, 0.0), 1.0) for k, v in body.overrides.coverage_ratio.items()}
    )
    if body.overrides.ceiling_height_ft is not None:
        merged.ceiling_height_ft = body.overrides.ceiling_height_ft
    s.overrides = merged
    recompute(deps, s, explain=False)  # instant: no LLM on panel edits
    deps.store.update(s)
    return s


# -------------------------------------------------------------------- chat


def chat(deps: Deps, s: Session, message: str, upload: Upload | None) -> ChatReply:
    text = (message or "").strip()
    s.say("user", text or f"(attached {upload.name or 'a plan'})")
    if upload is not None:
        reply = _start_plan_upload(deps, s, upload, text)
    else:
        reply = handle_message(deps, s, text)
        s.say("assistant", reply.message, status=reply.status, options=reply.options)
    deps.store.update(s)
    return ChatReply(
        status=reply.status,
        message=reply.message,
        options=reply.options,
        job_id=reply.job_id,
        session=view(s),
    )  # type: ignore[arg-type]


def _plan_room_names(s: Session) -> list[str]:
    """Uploaded plan rooms for the chat context (project plans are read only when needed)."""
    return [r.name for r in rooms_from_plan(s.uploaded_plan)][:30] if s.uploaded_plan else []


def _context(s: Session) -> dict:
    return {
        "photo_room_type": s.analysis.scene if s.analysis else None,
        "materials": [
            {"id": m.id, "name": m.display_name, "surface": m.surface} for m in s.materials
        ],
        "plan_rooms": _plan_room_names(s),
        "space": s.target.label if s.target else None,
        "project": s.project_name,
        "uploaded_plan": s.uploaded_plan_name,
        "last_question": (s.pending or {}).get("question"),
    }


def handle_message(deps: Deps, s: Session, text: str) -> Reply:
    if not text:
        return Reply(
            "needs_input",
            "What would you like to know? For example: how much marble for the kitchen platform?",
        )
    pending = s.pending
    if pending:
        filled = answer_to_pending(text, pending)
        if filled is not None:
            s.pending = None
            side = filled.pop("__side", None)
            return dispatch(deps, s, ChatIntent.model_validate(filled), side=side)
        not_clear = _unclear_pick(s, pending, text)
        if not_clear is not None:
            return not_clear
    intent = interpret(deps.text_llm, text, s.materials, _context(s))
    if intent.action in ("explain_quantity", "explain_material", "advise", "set_piece_size"):
        intent = intent.model_copy(update={"question": text[:200]})  # answer the exact question
    if pending and intent.action in ("unclear", pending["intent"].get("action")):
        merged = dict(pending["intent"])
        for k, v in intent.model_dump(exclude_none=True).items():
            if k != "action" and v not in ("", None):
                merged[k] = v
        s.pending = None
        return dispatch(deps, s, ChatIntent.model_validate(merged))
    reply = dispatch(deps, s, intent)
    # e.g. the person named a project to answer "which project?": continue the request
    if pending and reply.status == "ok" and intent.action in ("use_project",) and s.pending is None:
        s.say("assistant", reply.message, status="ok")
        return dispatch(deps, s, ChatIntent.model_validate(pending["intent"]))
    return reply


def _ask(
    s: Session,
    intent: ChatIntent,
    missing: str,
    question: str,
    options: list[str],
    option_values: dict | None = None,
    rooms: list[RoomGeom] | None = None,
) -> Reply:
    last = next((m for m in reversed(s.messages) if m.role == "assistant"), None)
    if last is not None and last.status == "needs_input" and last.text == question:
        # never the same question twice in a row
        question = "Sorry, I still need this to go on: " + question
    s.pending = {
        "intent": intent.model_dump(mode="json"),
        "missing": missing,
        "question": question,
        "options": options,
        "option_values": option_values or {},
    }
    if rooms is not None:  # a pick among rooms: kept so typed answers can be matched
        s.pending["rooms"] = [r.model_dump(mode="json") for r in rooms]
    return Reply("needs_input", question, options)


def _unclear_pick(s: Session, pending: dict, text: str) -> Reply | None:
    """An answer to "which room?" that matches no choice but is clearly meant as one:
    say what was not understood and show the choices again as buttons (never the same
    question word for word, never a round trip through the AI)."""
    if pending.get("missing") != "room" or not pending.get("rooms"):
        return None
    rooms = [RoomGeom.model_validate(r) for r in pending["rooms"]]
    if not looks_like_a_choice(text, rooms):
        return None
    options = pending.get("options") or []
    kind = rooms[0].name.lower() if rooms else "room"
    msg = (
        f"I could not tell which {kind} you meant by “{text.strip()[:60]}”. Tap one below, "
        "say its number (for example “2” or “the second one”), its size, or “all of them”."
    )
    last = next((m for m in reversed(s.messages) if m.role == "assistant"), None)
    if last is not None and last.text == msg:  # never the same words twice in a row
        msg = "Still not sure, sorry. " + msg
    s.pending = {**pending, "question": msg}
    return Reply("needs_input", msg, options)


def dispatch(deps: Deps, s: Session, intent: ChatIntent, side: int | None = None) -> Reply:
    match intent.action:
        case "money_question":
            return Reply("ok", MONEY_ANSWER)
        case "use_project":
            return _use_project(deps, s, intent)
        case "apply_all":
            return _apply_all(deps, s, intent)
        case "apply_material":
            return _apply_material(deps, s, intent, side)
        case "recalculate":
            return _recalculate_from_chat(deps, s, intent)
        case "explain_material":
            return _explain_material(deps, s, intent)
        case "explain_quantity":
            return _explain_quantity(deps, s, intent)
        case "advise":
            return _advise(deps, s, intent)
        case "substitute":
            return _substitute(deps, s, intent)
        case "supporting_materials":
            return _supporting_materials(s, intent)
        case "set_coverage":
            return _set_coverage(deps, s, intent)
        case "set_piece_size":
            return _set_piece_size(deps, s, intent)
        case "totals":
            return _totals(s)
        case "change_focus":
            return _change_focus(deps, s, intent)
        case "upload_plan":
            return Reply(
                "needs_input", "Attach the floor plan (PDF, PNG or JPG) with the paperclip button."
            )
    q = (
        intent.question
        or "Which material and where? For example: how much marble for the kitchen platform?"
    )
    return Reply("needs_input", q)


def _use_project(deps: Deps, s: Session, intent: ChatIntent) -> Reply:
    if not intent.project_name:
        return _ask(
            s,
            intent,
            "project",
            "Which of your projects?",
            [p.name for p in find_project(deps.projects, s.owner_id, "").all_projects][:8],
        )
    match = find_project(deps.projects, s.owner_id, intent.project_name)
    if match.status == "ambiguous":
        return _ask(
            s,
            intent,
            "project",
            f'Which project do you mean by "{intent.project_name}"?',
            [p.name for p in match.options],
        )
    if match.status == "not_found" or match.project is None:
        names = ", ".join(p.name for p in match.all_projects[:8])
        return Reply(
            "not_found",
            f'I could not find a project called "{intent.project_name}" in your projects.'
            + (f" Your projects: {names}." if names else " You have no projects yet."),
            [p.name for p in match.all_projects[:8]],
        )
    s.project_id, s.project_name = match.project.id, match.project.name
    s.uploaded_plan, s.uploaded_plan_name = None, None
    rooms = _project_rooms(deps, s)
    if not rooms or not rooms[0]:
        return Reply(
            "ok",
            f"Using project {s.project_name}. It has no saved floor plan yet; "
            "attach one or type the room size.",
        )
    names = ", ".join(r.name for r in rooms[0][:12])
    return Reply("ok", f"Using project {s.project_name}. Rooms in its plan: {names}.")


def _space_for(deps: Deps, s: Session, intent: ChatIntent) -> TargetSpace | Reply:
    """The space a follow-up request refers to (typed size, plan room, or current)."""
    unit = intent.unit or "ft"
    if intent.length and intent.width:
        name = (intent.room or "Room").strip().title()
        return manual_target(
            ManualSpace(
                kind="room",
                unit=unit,
                length=intent.length,
                width=intent.width,
                height=intent.height,
                label=name,
            )
        )
    if not intent.room:
        if s.target is not None:
            return s.target
        return _ask(
            s,
            intent,
            "space",
            "Which room or wall? Type its size (for example 10 x 8 ft), name a project, "
            "or attach a floor plan.",
            [],
        )
    if intent.project_name:
        r = _use_project(
            deps, s, ChatIntent(action="use_project", project_name=intent.project_name)
        )
        if r.status != "ok":
            return r
    if (
        s.target
        and s.target.room
        and s.target.source == "manual"
        and _same_room(s.target.room.name, intent.room)
    ):
        return s.target
    rooms = _project_rooms(deps, s)
    if rooms is None:
        room_word = intent.room.lower()
        return _ask(
            s,
            intent,
            "space",
            f"Which project is the {room_word} in? Name one of your projects, attach a floor plan, "
            f"or type the {room_word} size (for example 10 x 8 ft).",
            [],
        )
    room_list, source = rooms
    chosen = _picked(room_list, intent.room)
    if chosen:  # one space here: the first room picked
        return plan_target(chosen[0], source, s.project_id, s.project_name, s.uploaded_plan_name)
    match = match_room(room_list, intent.room)
    if match.status == "ambiguous":
        labels = choice_labels(match.options)
        values = {
            lbl: _pick_value(room_list, r) for lbl, r in zip(labels, match.options, strict=True)
        }
        return _ask(
            s,
            intent,
            "room",
            f"Which {intent.room.lower()}?",
            labels,
            values,
            rooms=match.options,
        )
    if match.room is None:
        names = ", ".join(r.name for r in room_list[:15]) or "none"
        return Reply(
            "not_found",
            f'I could not find "{intent.room}" in the plan. Rooms: {names}.',
            [r.name for r in room_list[:15]],
        )
    return plan_target(match.room, source, s.project_id, s.project_name, s.uploaded_plan_name)


def _same_room(a: str, b: str) -> bool:
    from app.modules.ai.material_agent.space import room_kind

    return a.strip().lower() == b.strip().lower() or (
        room_kind(a) is not None and room_kind(a) == room_kind(b)
    )


# where each kind of surface in the photo goes in the person's room
SURFACE_APPLICATION = {
    "floor": "floor",
    "wall": "all_walls",
    "ceiling": "ceiling",
    "countertop": "platform",
    "backsplash": "backsplash",
}
ALL_ROOMS = "__all__:"
# A room picked from the choices: its position in the plan's room list ("__pick__:2,5").
# Names are not unique (three rooms called TOILET), so the answer must not go back through
# the name: that was the loop where picking one toilet asked "which toilet?" again.
ROOM_PICK = "__pick__:"


def _pick_value(room_list: list[RoomGeom], room: RoomGeom) -> str:
    return f"{ROOM_PICK}{next(i for i, r in enumerate(room_list) if r is room)}"


def _picked(room_list: list[RoomGeom], query: str | None) -> list[RoomGeom]:
    """The rooms a pick names. Rooms that share a name get their number ("Toilet 2"), so
    their lines in the report stay apart."""
    if not query or not query.startswith(ROOM_PICK):
        return []
    out = []
    for part in query[len(ROOM_PICK) :].split(","):
        if part.strip().isdigit() and int(part) < len(room_list):
            r = room_list[int(part)]
            same = [o for o in room_list if o.name.strip().lower() == r.name.strip().lower()]
            if len(same) > 1:
                r = r.model_copy(update={"name": f"{r.name.strip()} {same.index(r) + 1}"})
            out.append(r)
    return out


def _room_choice(deps: Deps, s: Session, intent: ChatIntent) -> list[TargetSpace] | Reply:
    """The room(s) that get the whole design: named, typed, or the photo's room type."""
    if intent.length and intent.width:
        target = _space_for(deps, s, intent)
        return target if isinstance(target, Reply) else [target]
    rooms = _project_rooms(deps, s)
    query = intent.room
    scene_kind = room_kind(s.analysis.scene) if s.analysis and s.analysis.scene else None
    if rooms is None:
        if s.target is not None and s.target.room is not None:
            return [s.target]
        what = (s.analysis.scene if s.analysis and s.analysis.scene else "room").lower()
        return _ask(
            s,
            intent,
            "space",
            f"Which {what} should get this design? Attach your floor plan with **+**, "
            f"name one of your projects, or type the size (for example {what} 12 x 10 ft).",
            [],
        )
    room_list, source = rooms
    if not room_list:
        return Reply(
            "not_found", "I could not find any rooms in that plan. Type the room size instead."
        )
    every = [r for r in room_list if r.area_sqft > 0]
    chosen = _picked(room_list, query)
    if chosen:
        return [
            plan_target(r, source, s.project_id, s.project_name, s.uploaded_plan_name)
            for r in chosen
        ]
    all_of = query.startswith(ALL_ROOMS)
    query = query[len(ALL_ROOMS) :] if all_of else (query or (scene_kind or ""))
    match = match_room(room_list, query) if query else None

    def targets(rs: list[RoomGeom]) -> list[TargetSpace]:
        return [
            plan_target(r, source, s.project_id, s.project_name, s.uploaded_plan_name) for r in rs
        ]

    if match and match.room:
        return targets([match.room])
    if match and match.options:
        if all_of:  # numbered when they share a name, so each keeps its own report lines
            idx = ",".join(_pick_value(room_list, r)[len(ROOM_PICK) :] for r in match.options)
            return targets(_picked(room_list, ROOM_PICK + idx))
        labels = choice_labels(match.options)
        values = {
            lbl: _pick_value(room_list, r) for lbl, r in zip(labels, match.options, strict=True)
        }
        values["All of them"] = ALL_ROOMS + query
        return _ask(
            s,
            intent,
            "room",
            f"Your plan has {len(match.options)} {query.replace('_', ' ').lower()}s. "
            "Which one gets this design?",
            [*labels, "All of them"],
            values,
            rooms=match.options,
        )
    seen = f"a {query.replace('_', ' ')}" if query else "the room in the photo"
    labels = choice_labels(every[:12])
    return _ask(
        s,
        intent,
        "room",
        f"I couldn't find {seen} in your plan. Which room should get this design?",
        labels,
        {lbl: _pick_value(room_list, r) for lbl, r in zip(labels, every[:12], strict=True)},
        rooms=every[:12],
    )


def _apply_all(deps: Deps, s: Session, intent: ChatIntent) -> Reply:
    """Every material of the photo on its natural surface of the chosen room(s)."""
    if not s.materials:
        return Reply("not_found", "No materials were identified in the photo yet.")
    wanted = intent.application
    if wanted == "one_wall":
        wanted = "all_walls"
    mats = [
        m
        for m in s.materials
        if m.surface in SURFACE_APPLICATION
        and (not wanted or SURFACE_APPLICATION[m.surface] == wanted)
    ]
    if not mats:
        where = APPLICATION_NAMES.get(wanted or "", "a floor, wall, ceiling or counter")
        return Reply("not_found", f"None of the materials in the photo go on {where}.")
    chosen = _room_choice(deps, s, intent)
    if isinstance(chosen, Reply):
        return chosen
    if s.target is not None and any(t.label == s.target.label for t in chosen):
        s.target = None  # the room is now covered by the applied lines below
    needs_layout = any(SURFACE_APPLICATION[m.surface] in ("platform", "backsplash") for m in mats)
    done_labels = {t.label for t in chosen}
    s.applied = [
        a
        for a in s.applied
        if a.target.label not in done_labels or a.material_id not in {m.id for m in mats}
    ]
    for target in chosen:
        groups: dict[str, list] = {}
        for m in mats:
            groups.setdefault(SURFACE_APPLICATION[m.surface], []).append(m)
        for app, group in groups.items():
            if app in ("platform", "backsplash") and intent.layout is None:
                continue  # asked below, once
            req = ApplicationRequest(application=app, layout=intent.layout)  # type: ignore[arg-type]
            if isinstance(application_area(target, req), NeedsInput):
                continue
            shares, _ = coverage_shares(group, s.overrides.coverage_ratio)
            s.applied += [
                Applied(material_id=m.id, request=req, target=target, coverage=shares[m.id])
                for m in group
            ]
    recompute(deps, s)
    assert s.report is not None
    done = {a.material_id for a in s.applied if a.target.label in done_labels}
    where = chosen[0].label if len(chosen) == 1 else f"{len(chosen)} rooms"
    n = len(done)
    text = (
        f"Done: quantities for **{n} material{'s' if n != 1 else ''}** in the **{where}** "
        "are in the table."
    )
    others = [m.display_name.lower() for m in s.materials if m.surface not in SURFACE_APPLICATION]
    if others:
        verb = "is a fitting" if len(others) == 1 else "are fittings"
        text += f" {_join(others[:3]).capitalize()} {verb}, so no area quantity."
    kitchenish = any(
        t.room and (t.room.kind == "kitchen" or room_kind(t.room.name) == "kitchen") for t in chosen
    )
    if needs_layout and intent.layout is None and (kitchenish or len(chosen) == 1):
        room_q = intent.room or (chosen[0].room.name if chosen[0].room else "")
        return _ask(
            s,
            intent.model_copy(update={"room": room_q}),
            "layout",
            (
                text + " One thing I need for the counter top: what is the platform layout?"
                if done
                else f"To work out the counter top and backsplash for the **{where}**, "
                "I need one thing: what is the platform layout?"
            ),
            list(LAYOUT_OPTIONS),
        )
    return Reply("ok", text)


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _apply_material(deps: Deps, s: Session, intent: ChatIntent, side: int | None) -> Reply:
    if not s.materials:
        return Reply("not_found", "No materials were identified in the photo yet.")
    if not intent.material and len(s.materials) > 1:
        # no single material named: work out every material that fits the request
        return _apply_all(deps, s, intent)
    if intent.material:
        mats = find_material(s.materials, intent.material)
        if not mats:
            found = ", ".join(m.display_name for m in s.materials[:8])
            return Reply(
                "not_found",
                f"I don't see {intent.material} in this photo. Materials found: {found}.",
                [m.display_name for m in s.materials[:8]],
            )
        if len(mats) > 1:
            return _ask(
                s, intent, "material", f"Which {intent.material}?", [m.display_name for m in mats]
            )
        material = mats[0]
    elif len(s.materials) == 1:
        material = s.materials[0]
    else:
        return _ask(
            s, intent, "material", "Which material?", [m.display_name for m in s.materials[:8]]
        )
    if intent.application is None:
        return _ask(
            s,
            intent,
            "application",
            f"Where should the {material.display_name.lower()} go?",
            list(APPLICATION_OPTIONS),
        )
    target = _space_for(deps, s, intent)
    if isinstance(target, Reply):
        return target
    depth = to_ft(intent.depth, intent.unit or "ft") if intent.depth else None
    req = ApplicationRequest(
        application=intent.application, layout=intent.layout, depth_ft=depth, side=side
    )
    area = application_area(target, req)
    if isinstance(area, NeedsInput):
        intent_room = intent.model_copy(
            update={"room": intent.room or (target.room.name if target.room else "")}
        )
        return _ask(s, intent_room, area.missing, area.question, area.options)
    s.applied = [
        a
        for a in s.applied
        if not (
            a.material_id == material.id
            and a.request.application == req.application
            and a.target.label == target.label
        )
    ] + [Applied(material_id=material.id, request=req, target=target)]
    if intent.wastage_pct is not None:
        s.overrides.wastage_pct[material.id] = intent.wastage_pct
    recompute(deps, s, explain=False)
    assert s.report is not None
    line = next(
        ln
        for ln in reversed(s.report.lines)
        if ln.material_id == material.id and ln.application == area.label
    )
    return Reply("ok", _line_text(line) + " The working is in the table.")


def _line_text(line) -> str:
    """One short line: '**35.2 sq ft** of marble for the Kitchen platform (L-shape), ...'."""
    buy = f" (about **{fmt(line.buy_qty)} {line.buy_unit}**)" if line.buy_qty is not None else ""
    return (
        f"**{fmt(line.total_qty)} sq ft** of {line.material.lower()} for the "
        f"{line.application}{buy}, including {fmt(line.wastage_pct)}% wastage."
    )


def _found_text(s: Session) -> str:
    n = len(s.materials)
    head = f"Found **{n} material{'s' if n != 1 else ''}**, listed in the table."
    if is_whole_design(s.focus) and not (s.report and s.report.lines):
        return head + (
            " Attach your floor plan with **+** (or name your project) and I'll work out the "
            "quantities of every material for the matching room."
        )
    if s.report and s.report.lines:
        return head + " Quantities are below it; open **How** on a line to see the working."
    return head + ' For quantities, tell me a size (e.g. "kitchen 10 x 8 ft") or a project.'


def _recalculate_from_chat(deps: Deps, s: Session, intent: ChatIntent) -> Reply:
    unit = intent.unit or "ft"
    changed = []
    if intent.length and (s.target is None or s.target.wall is not None) and not intent.width:
        old_wall = s.target.wall if s.target else None
        height_ft = (
            to_ft(intent.height, unit)
            if intent.height
            else (old_wall.height_ft if old_wall else None)
        )
        if height_ft is None:
            return _ask(s, intent, "space", "How high is the wall?", [])
        s.target = manual_target(
            ManualSpace(
                kind="wall",
                unit="ft",
                length=to_ft(intent.length, unit),
                height=height_ft,
                label=old_wall.label if old_wall else "Wall",
            )
        )
        changed.append("wall size")
    elif intent.length and intent.width:
        if s.target is not None and s.target.wall is not None and intent.height is None:
            # "12 x 10" on a wall = width x height
            s.target = manual_target(
                ManualSpace(
                    kind="wall",
                    unit=unit,
                    length=intent.length,
                    height=intent.width,
                    label=s.target.wall.label,
                )
            )
        else:
            name = s.target.room.name if s.target and s.target.room else "Room"
            s.target = manual_target(
                ManualSpace(
                    kind="room",
                    unit=unit,
                    length=intent.length,
                    width=intent.width,
                    height=intent.height,
                    label=name,
                )
            )
        changed.append("size")
    elif intent.height:
        h = to_ft(intent.height, unit)
        if s.target and s.target.wall:
            s.target = s.target.model_copy(deep=True)
            assert s.target.wall is not None
            s.target.wall.height_ft = h
            s.target.label = f"{s.target.wall.label}, {fmt(s.target.wall.width_ft)} × {fmt(h)} ft"
        else:
            s.overrides.ceiling_height_ft = h
        changed.append("height")
    if intent.wastage_pct is not None:
        mats = find_material(s.materials, intent.material) if intent.material else s.materials
        for m in mats:
            s.overrides.wastage_pct[m.id] = intent.wastage_pct
        changed.append("wastage")
    if not changed:
        return Reply("needs_input", "What should I change: the size, the height or the wastage?")
    recompute(deps, s, explain=False)
    assert s.report is not None
    if not s.report.lines:
        return Reply("ok", f"Updated the {' and '.join(changed)}.")
    return Reply("ok", f"Updated the {' and '.join(changed)}. The table shows the new quantities.")


# ------------------------------------------------------------- analysis tools


def _material_for(s: Session, intent: ChatIntent, *, ask_why: str) -> Material | Reply:
    """The material a question is about: named, 'this one' (last discussed) or the only one."""
    if intent.material:
        mats = find_material(s.materials, intent.material)
        if len(mats) == 1:
            return mats[0]
        if len(mats) > 1:
            return _ask(
                s, intent, "material", f"Which {intent.material}?", [m.display_name for m in mats]
            )
        return Reply(
            "not_found",
            f"I don't see {intent.material} in this photo. Materials found: "
            + ", ".join(m.display_name for m in s.materials[:8])
            + ".",
            [m.display_name for m in s.materials[:8]],
        )
    last = next((m for m in s.materials if m.id == s.last_material_id), None)
    if last is not None:
        return last
    if len(s.materials) == 1:
        return s.materials[0]
    if not s.materials:
        return Reply("not_found", "No materials were identified in the photo yet.")
    return _ask(s, intent, "material", ask_why, [m.display_name for m in s.materials[:8]])


def _place_of(s: Session, intent: ChatIntent, m: Material | None) -> str:
    if intent.place:
        return intent.place
    if intent.room:
        return intent.room
    for a in s.applied:
        if m is not None and a.material_id == m.id and a.target.room:
            return a.target.room.name
    if s.target and s.target.room:
        return s.target.room.name
    return s.analysis.scene if s.analysis else ""


def _advice_text(topic: str, facts: dict) -> str:
    """The answer without an LLM: the facts, in plain sentences."""
    p = facts.get("material", {})
    name = p.get("name", "This material")
    match topic:
        case "alternatives":
            opts = facts.get("options", [])
            if not opts:
                return f"I have no suitable alternatives for {name} in the catalog for this place."
            rows = [
                f"Instead of **{name}**"
                + (f" for the {facts['place']}" if facts.get("place") else "")
                + ":"
            ]
            for o in opts:
                why = "; ".join(o["why"]) if o["why"] else ""
                watch = f" (watch out: {o['watch_out'][0]})" if o["watch_out"] else ""
                rows.append(f"- **{o['name']}**: {why}{watch}")
            return "\n".join(rows)
        case "compare":
            a, b = facts["a"], facts["b"]
            rows = [f"**{a['name']}** vs **{b['name']}**:"]
            for key, label in (
                ("durability", "Durability"),
                ("water", "Water"),
                ("maintenance", "Care"),
            ):
                rows.append(f"- {label}: {a.get(key) or '—'} / {b.get(key) or '—'}")
            rows.append(
                f"- Best for: {', '.join(a.get('good_for') or [])} / "
                f"{', '.join(b.get('good_for') or [])}"
            )
            return "\n".join(rows)
        case "suitability":
            verdict = {True: "Yes", False: "Not recommended", None: "Probably"}[
                facts.get("suitable")
            ]
            return f"**{verdict}** for {facts.get('place') or 'that place'}: " + " ".join(
                facts.get("reasons", [])
            )
        case "maintenance":
            return f"**{name}**: {p.get('maintenance') or 'no care notes in the catalog yet.'}"
        case "durability":
            return f"**{name}**: {p.get('durability') or '—'} {p.get('water') or ''}".strip()
        case "installation":
            return f"**{name}**: {p.get('install') or 'no installation notes in the catalog yet.'}"
    pros = ", ".join(p.get("pros") or []) or "—"
    cons = ", ".join(p.get("cons") or []) or "—"
    best = ", ".join(p.get("good_for") or []) or "—"
    return f"**{name}**\n- Good: {pros}\n- Watch out: {cons}\n- Best for: {best}"


def _advise(deps: Deps, s: Session, intent: ChatIntent) -> Reply:
    topic = intent.topic or "general"
    if topic == "compare" and intent.material and intent.other_material:
        a: Material | str = (find_material(s.materials, intent.material) or [intent.material])[0]
        b: Material | str = (
            find_material(s.materials, intent.other_material) or [intent.other_material]
        )[0]
        facts = tools.compare(a, b)
        m = a if isinstance(a, Material) else None
    else:
        if not intent.material and topic != "general" and s.materials:
            got = _material_for(s, intent, ask_why=_WHICH_FOR.get(topic, "Which material?"))
        elif intent.material:
            found = find_material(s.materials, intent.material)
            got = found[0] if found else intent.material  # a catalog material not in the photo
        else:
            got = None  # a general question about the design
        if isinstance(got, Reply):
            return got
        m = got if isinstance(got, Material) else None
        place = _place_of(s, intent, m)
        if got is None:
            facts = {
                "photo_room_type": s.analysis.scene if s.analysis else "",
                "materials": [tools.profile(x) for x in s.materials[:8]],
                "place": place,
            }
        else:
            facts = {"material": tools.profile(got), "place": place}
            if topic == "alternatives":
                facts["options"] = tools.alternatives(got, place)
            if topic == "suitability":
                ok, reasons = tools.suitability(got, intent.place or place)
                facts.update({"suitable": ok, "reasons": reasons, "place": intent.place or place})
    if m is not None:
        s.last_material_id = m.id
    fallback = _advice_text(topic, facts)
    text = explain.advise(deps.text_llm, intent.question or topic, facts, fallback)
    already = re.search(r"\buse [^.\n]+ instead", text.lower())  # the answer says how to switch
    if topic == "alternatives" and facts.get("options") and not already:
        first = facts["options"][0]["name"].split(" (")[0].lower()
        text += f'\n\nSay "use {first} instead" and I will recalculate the quantities.'
    return Reply("ok", text)


_WHICH_FOR = {
    "alternatives": "Alternatives for which material?",
    "suitability": "Which material should I check?",
    "maintenance": "Care notes for which material?",
    "durability": "Which material?",
    "installation": "Installation of which material?",
    "pros_cons": "Pros and cons of which material?",
}


def _substitute(deps: Deps, s: Session, intent: ChatIntent) -> Reply:
    old = _material_for(s, intent, ask_why="Which material do you want to replace?")
    if isinstance(old, Reply):
        return old
    s.last_material_id = old.id
    if not intent.other_material:
        options = [o["name"] for o in tools.alternatives(old, _place_of(s, intent, old))]
        return _ask(
            s,
            intent.model_copy(update={"material": old.display_name}),
            "other_material",
            f"What should replace the {old.display_name.lower()}?",
            options,
        )
    new = tools.substitute(old, intent.other_material)
    place = _place_of(s, intent, old)
    ok, reasons = tools.suitability(new, place) if place else (True, [])
    s.materials = [new if m.id == old.id else m for m in s.materials]
    s.overrides.wastage_pct.pop(old.id, None)  # the new material has its own standard wastage
    s.overrides.piece_size.pop(old.id, None)
    recompute(deps, s)
    assert s.report is not None
    lines = [ln for ln in s.report.lines if ln.material_id == old.id]
    text = f"Swapped **{old.display_name}** for **{new.display_name}**."
    if lines:
        text += "\n" + "\n".join(f"- {_line_text(ln)}" for ln in lines)
    else:
        text += " It has no quantity yet; give me a size or a room for it."
    if ok is False:
        text += "\n\nCareful: " + " ".join(reasons)
    if new.catalog_id is None:
        text += (
            "\n\nIt is not in the catalog, so the standard 10% wastage and no buy unit are used."
        )
    return Reply("ok", text)


def _supporting_materials(s: Session, intent: ChatIntent) -> Reply:
    if not s.report or not s.report.supporting:
        if not (s.report and s.report.lines):
            return Reply(
                "ok",
                "There are no quantities yet. Give me a size, a project or a floor plan first.",
            )
        return Reply(
            "ok", "None of these materials needs extra supporting items in the catalog rules."
        )
    items = s.report.supporting
    if intent.material:
        ids = {m.id for m in find_material(s.materials, intent.material)}
        items = [i for i in items if i.material_id in ids] or items
    rows = ["Along with the main materials you will need (also in the **Also needed** table):"]
    rows += [
        f"- **{fmt(i.qty)} {i.unit}** {i.item.lower()} for {i.material.lower()} ({i.basis})"
        for i in items[:12]
    ]
    rows.append("\nThese use standard coverage values, to be verified with the firm.")
    return Reply("ok", "\n".join(rows))


def _set_coverage(deps: Deps, s: Session, intent: ChatIntent) -> Reply:
    m = _material_for(s, intent, ask_why="Which material's share should I change?")
    if isinstance(m, Reply):
        return m
    if intent.percent is None:
        return _ask(
            s, intent, "space", f"What share of the surface is {m.display_name.lower()} (in %)?", []
        )
    s.last_material_id = m.id
    s.overrides.coverage_ratio[m.id] = intent.percent / 100
    recompute(deps, s)
    assert s.report is not None
    lines = [ln for ln in s.report.lines if ln.material_id == m.id]
    text = f"Set **{m.display_name}** to **{fmt(intent.percent)}%** of its surface."
    if lines:
        text += "\n" + "\n".join(f"- {_line_text(ln)}" for ln in lines)
    return Reply("ok", text)


def _set_piece_size(deps: Deps, s: Session, intent: ChatIntent) -> Reply:
    size = tools.parse_piece_size(intent.question)
    if size is None:
        return Reply(
            "needs_input", 'What size are the pieces? For example "2 x 4 ft" or "600 x 1200 mm".'
        )
    m = _material_for(s, intent, ask_why=f"Which material comes in {size.label} pieces?")
    if isinstance(m, Reply):
        return m
    s.last_material_id = m.id
    s.overrides.piece_size[m.id] = size
    recompute(deps, s)
    assert s.report is not None
    lines = [ln for ln in s.report.lines if ln.material_id == m.id]
    if not lines:
        return Reply(
            "ok",
            f"Noted: {m.display_name} in {size.label} pieces. "
            "Give me a size or room to count them.",
        )
    return Reply(
        "ok",
        f"**{m.display_name}** in **{size.label}** pieces:\n"
        + "\n".join(f"- {_line_text(ln)}" for ln in lines),
    )


def _totals(s: Session) -> Reply:
    if not s.report or not s.report.lines:
        return Reply(
            "ok", "There are no quantities yet. Give me a size, a project or a floor plan first."
        )
    rows = ["Totals across everything calculated so far:"]
    for t in tools.totals(s.report.lines):
        buy = ", ".join(f"{fmt(n)} {u}" for u, n in t["buy"].items())
        where = f"{len(t['places'])} places" if len(t["places"]) > 1 else t["places"][0]
        rows.append(
            f"- **{t['material']}**: **{fmt(t['total_sq_ft'])} sq ft**"
            + (f" ({buy})" if buy else "")
            + f", {where}"
        )
    return Reply("ok", "\n".join(rows))


def _explain_quantity(deps: Deps, s: Session, intent: ChatIntent) -> Reply:
    """'How did you calculate this?', 'why 10% wastage?', 'why 3 sheets?' and the like."""
    lines = s.report.lines if s.report else []
    if not lines:
        return Reply(
            "ok",
            "There are no quantities yet, so nothing has been calculated. Give me a size "
            '(for example "kitchen 10 x 8 ft"), a project, or attach your floor plan.',
        )
    ids = {m.id for m in find_material(s.materials, intent.material)} if intent.material else set()
    words = " ".join(x for x in (intent.question, intent.application or "", intent.room) if x)
    chosen = explain.pick_lines(lines, s.materials, ids, words)
    target = next(
        (a.target for a in s.applied for ln in chosen if a.material_id == ln.material_id), None
    )
    text = explain.answer(
        deps.text_llm,
        intent.question or "How was this calculated?",
        chosen,
        s.materials,
        target or s.target,
        s.overrides,
        s.report.assumptions if s.report else [],
    )
    if "assumptions panel" not in text.lower():
        text += "\n\nYou can change any of these values in the Assumptions panel."
    return Reply("ok", text)


def _explain_material(deps: Deps, s: Session, intent: ChatIntent) -> Reply:
    mats = find_material(s.materials, intent.material) if intent.material else []
    if not mats and intent.question and s.report and s.report.lines:
        return _explain_quantity(deps, s, intent)
    if not mats:
        return Reply(
            "not_found",
            f"I don't see {intent.material or 'that material'} in this photo.",
            [m.display_name for m in s.materials[:8]],
        )
    m = mats[0]
    details = ", ".join(x for x in (m.finish, m.pattern, m.colour, m.size_hint) if x)
    text = f"{m.display_name}" + (f" ({details})" if details else "") + f", on the {m.surface}"
    text += f" ({m.location})." if m.location else "."
    if m.evidence:
        text += f" Recognised from: {m.evidence}."
    text += f" Confidence: {m.confidence}."
    if m.look_alikes:
        text += " It could also be: " + ", ".join(m.look_alikes) + "."
    if deps.text_llm is not None and intent.question:
        lines = [ln for ln in (s.report.lines if s.report else []) if ln.material_id == m.id]
        text = explain.answer(
            deps.text_llm, intent.question, lines, [m], s.target, s.overrides, [], fallback=text
        )
    return Reply("ok", text)


def _change_focus(deps: Deps, s: Session, intent: ChatIntent) -> Reply:
    images = []
    for h in s.image_hashes:
        data = vision.load_image(h)
        if data is None:
            return Reply(
                "failed",
                "The photo is no longer available here; please upload it again with the new focus.",
            )
        images.append(
            vision.PreparedImage(data=data, mime="image/jpeg", sha256=h, width=0, height=0)
        )
    s.focus = intent.focus or s.focus
    sid = s.id

    def work(job: Job) -> str | None:
        return _run_analysis(deps, sid, images, job)

    deps.store.update(s)
    job = deps.jobs.submit(s.owner_id, s.id, work)
    return Reply("working", f"Looking at the photo again for: {s.focus}.", job_id=job.id)


# -------------------------------------------------------------- plan upload


def _start_plan_upload(deps: Deps, s: Session, upload: Upload, text: str) -> Reply:
    settings = get_settings()
    if upload.mime not in PLAN_MIME:
        reply = Reply("failed", "Attach the plan as a PDF, PNG or JPG.")
        s.say("assistant", reply.message, status=reply.status)
        return reply
    if len(upload.data) > settings.max_plan_mb * 1024 * 1024:
        reply = Reply("failed", f"The plan must be under {settings.max_plan_mb:g} MB.")
        s.say("assistant", reply.message, status=reply.status)
        return reply
    sid, owner, project_id = s.id, s.owner_id, s.project_id
    pending_question = text

    def work(job: Job) -> str | None:
        job.emit("parsing_plan")
        if deps.store_files:
            store_file(owner, upload.name or "plan", upload.data, upload.mime, project_id)
        try:
            plan = deps.plan_parser(upload.data, upload.mime)
        except PlanUploadError as e:
            return _finish_upload(deps, sid, None, str(e))
        except Exception as e:  # parser / model failure: say so, never invent rooms
            logger.warning("uploaded plan could not be parsed: %s", e)
            return _finish_upload(
                deps, sid, None, "I could not read that plan. You can type the room size instead."
            )
        job.emit("calculating")
        return _finish_upload(
            deps, sid, (plan, upload.name or "the uploaded plan"), pending_question
        )

    job = deps.jobs.submit(owner, s.id, work)
    return Reply("working", "Reading the floor plan…", job_id=job.id)


def _finish_upload(deps: Deps, sid: str, parsed: tuple[dict, str] | None, text: str) -> str | None:
    s = deps.store.get(sid)
    if s is None:
        return "The session was lost. Please start again."
    if parsed is None:
        s.say("assistant", text, status="failed")
        deps.store.update(s)
        return None  # the job worked; the answer explains the problem
    plan, name = parsed
    s.uploaded_plan, s.uploaded_plan_name = plan, name
    rooms = rooms_from_plan(plan)
    names = ", ".join(r.name for r in rooms[:15]) or "no rooms"
    s.say(
        "assistant",
        f"Read {name}: {names}. This plan is used for this chat only; "
        "the project's saved plan is not changed.",
        status="ok",
    )
    reply: Reply | None = None
    pending = s.pending
    s.pending = None
    intent = interpret(deps.text_llm, text, s.materials, _context(s)) if text.strip() else None
    generic = intent is None or intent.action in (
        "unclear",
        "upload_plan",
        "use_project",
        "recalculate",
    )
    if generic and pending:
        # "here is my plan": continue the question that was waiting for the plan
        reply = dispatch(deps, s, ChatIntent.model_validate(pending["intent"]))
    elif generic:
        # a plan sent with a general request means: put this design into my plan
        room = intent.room if intent else ""
        layout = intent.layout if intent else None
        reply = dispatch(deps, s, ChatIntent(action="apply_all", room=room, layout=layout))
    else:
        assert intent is not None
        reply = dispatch(deps, s, intent)
    if reply is not None:
        s.say("assistant", reply.message, status=reply.status, options=reply.options)
    deps.store.update(s)
    return None
