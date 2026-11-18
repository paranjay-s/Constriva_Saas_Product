"""PDF -> PlanJSON parser.

    plan = parse_plan_pdf(pdf_bytes)          # a validated PlanJSON 2.0 dict

The same schema comes out whichever LLM is configured. The stages are:

  1. input      each PDF page rendered to PNG at a fixed DPI, plus the PDF's own text
                (pdf_input.py); identical for every provider
  2. model      one `JSONLLMClient.generate_json` call (temperature 0); the prompt lives in
                ai/prompts/parsing/plan_parser.md
  3. extract    the reply parsed as one JSON object
  4. validate   against `LLMPlanDraft` (llm_schema.py)
  5. repair     up to MAX_REPAIR_ATTEMPTS more calls, each given the previous reply and
                the exact validation errors
  6. normalise  the deterministic normaliser (normalise.py): units, polygons, canonical
                order, stable ids, kinds, warnings
  7. validate   against PlanJSON

A failure at any stage raises a `PlanParseError` subclass (errors.py). Partial JSON is
never returned, and a different building is never substituted.

Results are cached by the PDF's sha256 plus the parser, prompt and schema versions
(plan_cache.py), so the same PDF always yields the same PlanJSON.
"""

import json
import logging
import re
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.modules.ai.llm.json_client import (
    JSONLLMClient,
    JSONLLMError,
    LLMImage,
    LLMInvalidJSONError,
    LLMNotConfiguredError,
    get_json_llm,
)
from app.modules.parsing.errors import (
    NoFloorPlanError,
    ParserNotConfiguredError,
    ParserUnavailableError,
    PlanNormalisationError,
    PlanOutputInvalidError,
    PlanParseError,
)
from app.modules.parsing.llm_schema import DRAFT_JSON_SCHEMA, check_draft
from app.modules.parsing.normalise import (
    normalise_plan,
    synthesize_interior_walls_if_missing,
    to_metres,
)
from app.modules.parsing.normalise import unit_scale as drawing_unit_scale
from app.modules.parsing.pdf_input import load_plan_pdf, sha256_of
from app.modules.parsing.plan_cache import PlanCache, default_plan_cache, plan_cache_key
from app.modules.parsing.settings import get_settings
from app.modules.plans.schemas import PlanJSON

logger = logging.getLogger("construtiva.parsing.llm")

# Bump when the pipeline or the normaliser changes what a given PDF parses to.
PARSER_VERSION = "2.0.0"
MAX_REPAIR_ATTEMPTS = 2
MAX_PREVIOUS_REPLY_CHARS = 60_000

PROMPT_PATH = Path(__file__).resolve().parents[1] / "ai" / "prompts" / "parsing" / "plan_parser.md"
_VERSION_LINE = re.compile(r"^<!--\s*prompt_version:\s*([\w.\-]+)\s*-->\s*\n?")

__all__ = [
    "MAX_REPAIR_ATTEMPTS",
    "PARSER_VERSION",
    "PlanParseError",
    "parse",
    "parse_blueprint_image_with_llm",
    "parse_plan_images",
    "parse_plan_pdf",
    "sanitize_and_normalize_plan",
    "synthesize_interior_walls_if_missing",
]


@lru_cache
def load_prompt() -> tuple[str, str]:
    """(prompt text, prompt version) from the one versioned prompt file."""
    raw = PROMPT_PATH.read_text(encoding="utf-8")
    match = _VERSION_LINE.match(raw)
    if not match:
        raise RuntimeError(f"{PROMPT_PATH.name} must start with a prompt_version comment.")
    return raw[match.end() :].strip(), match.group(1)


def prompt_version() -> str:
    return load_prompt()[1]


def build_client() -> JSONLLMClient:
    """The LLM client named by the environment (PLAN_PARSER_* / LLM_PROVIDER)."""
    settings = get_settings()
    try:
        return get_json_llm(
            settings.provider(),
            model=settings.llm_model,
            fallback_models=settings.fallback_models(),
            timeout_s=settings.llm_timeout_s,
        )
    except LLMNotConfiguredError as e:
        raise ParserNotConfiguredError(str(e)) from e


def _user_text(page_texts: Sequence[str]) -> str:
    lines = [
        f"The drawing has {len(page_texts)} page(s); the images are in page order.",
        "Extract every floor plan into the JSON object described in your instructions.",
    ]
    for number, text in enumerate(page_texts, start=1):
        if text.strip():
            lines.append(f"\nText printed on page {number}:\n{text.strip()}")
        else:
            lines.append(f"\nPage {number} has no text layer; read its labels from the image.")
    return "\n".join(lines)


def _repair_text(user_text: str, previous_reply: str, problems: Sequence[str]) -> str:
    listed = "\n".join(f"- {p}" for p in problems)
    return (
        f"{user_text}\n\n"
        "Your previous reply could not be used.\n\n"
        f"Previous reply:\n{previous_reply[:MAX_PREVIOUS_REPLY_CHARS]}\n\n"
        f"Problems found:\n{listed}\n\n"
        "Return the complete, corrected JSON object. Fix every problem listed and keep "
        "everything that was already right."
    )


def parse_plan_images(
    images: Sequence[LLMImage],
    page_texts: Sequence[str] | None = None,
    *,
    client: JSONLLMClient | None = None,
    min_rooms: int = 1,
    pdf_sha256: str | None = None,
) -> dict[str, Any]:
    """Stages 2 to 7 for already-rendered pages. Returns a PlanJSON dict or raises."""
    if not images:
        raise PlanParseError("There is no page image to read.")
    client = client or build_client()
    system_prompt, prompt_ver = load_prompt()
    user_text = _user_text(list(page_texts) if page_texts else [""] * len(images))

    # The best structurally valid reply so far, and how many scale concerns it carries.
    draft = None
    draft_concerns = 0
    problems: list[str] = []
    text = user_text
    for attempt in range(1 + MAX_REPAIR_ATTEMPTS):
        try:
            reply = client.generate_json(
                system_prompt=system_prompt,
                images=images,
                text=text,
                json_schema=DRAFT_JSON_SCHEMA,
            )
        except LLMInvalidJSONError as e:
            problems = [f"The reply was not a JSON object: {e}"]
            previous = e.raw_text
        except LLMNotConfiguredError as e:
            raise ParserNotConfiguredError(str(e)) from e
        except JSONLLMError as e:
            if draft is not None:
                break  # a usable reply is already in hand; keep it rather than fail
            raise ParserUnavailableError(
                "The plan could not be read because the AI service did not respond. "
                "Please try again in a moment.",
                details=[str(e)],
            ) from e
        else:
            candidate, problems, concerns = check_draft(reply, min_rooms)
            if candidate is not None and not candidate.floor_plan_found:
                raise NoFloorPlanError(
                    "No floor plan was found in this PDF. Upload a drawing that shows a "
                    "floor plan with its rooms."
                )
            if candidate is not None:
                if draft is None or len(concerns) <= draft_concerns:
                    draft, draft_concerns = candidate, len(concerns)
                if not concerns:
                    break
                problems = concerns
            previous = json.dumps(reply, separators=(",", ":"), default=str)
        logger.info(
            "plan parser attempt %d/%d not accepted: %d problem(s), first: %s",
            attempt + 1,
            1 + MAX_REPAIR_ATTEMPTS,
            len(problems),
            problems[0] if problems else "",
        )
        text = _repair_text(user_text, previous, problems)

    if draft is None:
        raise PlanOutputInvalidError(
            "The floor plan could not be read reliably from this drawing. "
            "Check that the PDF shows a clear, labelled floor plan and try again.",
            details=problems,
        )

    try:
        plan = normalise_plan(draft.model_dump())
    except (ValueError, ValidationError) as e:
        raise PlanNormalisationError(
            "The floor plan was read but could not be converted to a valid plan.",
            details=[str(e)[:500]],
        ) from e

    kept = len(plan["levels"][0]["rooms"])
    if kept < max(min_rooms, 1):
        raise PlanOutputInvalidError(
            f"Only {kept} room(s) of the floor plan could be used; at least "
            f"{max(min_rooms, 1)} are needed.",
            details=plan["warnings"],
        )

    plan["parser"] = {
        "pdf_sha256": pdf_sha256,
        "parser_version": PARSER_VERSION,
        "prompt_version": prompt_ver,
        "provider": getattr(client, "provider", None),
        "model": getattr(client, "model", None),
    }
    try:
        validated = PlanJSON.model_validate(plan).model_dump()
    except ValidationError as e:
        raise PlanNormalisationError(
            "The floor plan was read but could not be converted to a valid plan.",
            details=[str(e)[:500]],
        ) from e
    logger.info(
        "plan parsed: %d level(s), %d room(s) on level 0, %d warning(s), model %s",
        len(validated["levels"]),
        kept,
        len(validated["warnings"]),
        validated["parser"]["model"],
    )
    return validated


def parse_plan_pdf(
    pdf_bytes: bytes,
    *,
    client: JSONLLMClient | None = None,
    min_rooms: int = 1,
    cache: PlanCache | None = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """PDF bytes -> PlanJSON dict. Raises a PlanParseError subclass on any failure.

    `min_rooms` is the fewest rooms the lowest floor must have. A cached plan with fewer
    rooms than that is not accepted; the PDF is parsed again.
    """
    cache = cache if cache is not None else default_plan_cache()
    key = plan_cache_key(sha256_of(pdf_bytes), PARSER_VERSION, prompt_version())
    cached = cache.get(key) if pdf_bytes else None
    if cached and len(cached["levels"][0]["rooms"]) >= max(min_rooms, 1):
        logger.info("plan cache hit %s", key[:12])
        return cached

    pdf = load_plan_pdf(pdf_bytes, max_pages or get_settings().max_pages)
    plan = parse_plan_images(
        [LLMImage(page.png) for page in pdf.pages],
        [page.text for page in pdf.pages],
        client=client,
        min_rooms=min_rooms,
        pdf_sha256=pdf.sha256,
    )
    if pdf.skipped_pages:
        plan["warnings"].append(
            f"Only the first {len(pdf.pages)} of {pdf.page_count} pages were read."
        )
    cache.put(key, plan)
    return plan


parse = parse_plan_pdf


# ------------------------------------------------------------------ earlier entry points


def parse_blueprint_image_with_llm(png_bytes: bytes, min_rooms: int = 6) -> dict[str, Any]:
    """One rendered page -> PlanJSON. Kept for callers that already hold an image.

    `min_rooms` defaults to 6, the blueprint import's threshold; the material finder
    passes 1 so small plans are accepted.
    """
    return parse_plan_images([LLMImage(png_bytes)], [""], min_rooms=min_rooms)


def sanitize_and_normalize_plan(raw_plan: dict[str, Any]) -> dict[str, Any]:
    """Model output (or any plan-shaped dict) -> validated PlanJSON. See normalise.py."""
    return normalise_plan(raw_plan)


def determine_unit_scale(raw_plan: dict[str, Any]) -> float:
    """Metres per drawing unit, decided once for the whole drawing."""
    return drawing_unit_scale(raw_plan.get("units")) or 1.0


def parse_numeric_length(val: Any, unit_scale: float = 1.0) -> float:
    """A number or a feet-and-inches string as metres; 0.0 when it cannot be read."""
    metres = to_metres(val, unit_scale)
    return metres if metres is not None else 0.0
