"""PDF -> PlanJSON parser.

    plan = parse_plan_pdf(pdf_bytes)          # a validated PlanJSON 2.0 dict

The same schema comes out whichever LLM is configured. The stages are:

  1. input      each PDF page rendered to PNG at a fixed DPI, plus the PDF's own text
                (pdf_input.py); identical for every provider
  2. model      one `JSONLLMClient.generate_json` call; the prompt lives in
                ai/prompts/parsing/plan_parser.md and the schema is `WIRE_JSON_SCHEMA`
  3. extract    the reply parsed as one JSON object
  4. validate   against `LLMPlanDraft` (llm_schema.py), then the scale checks
  5. repair     up to MAX_REPAIR_ATTEMPTS more calls, each given the previous reply and
                the exact problems found
  6. normalise  the deterministic normaliser (normalise.py): units, polygons, canonical
                order, stable ids, kinds, room types, warnings
  7. validate   against PlanJSON

A failure at any stage raises a `PlanParseError` subclass (errors.py). Partial JSON is
never returned, and a different building is never substituted.

The provider, model and key come from settings (`PLAN_PARSER_LLM_*`, settings.py).

Two things are cached (plan_cache.py). The model's reply is kept under the PDF's sha256,
the prompt version, the provider and the model, so a model is asked about a PDF once. The
PlanJSON is kept under those plus the parser and schema versions. Raising `PARSER_VERSION`
after a change to the normaliser or a rule builds the plan again from the stored reply,
without a model call; only a new PDF, prompt, provider or model reaches a model.

One log line is written per parse: provider, model, tokens, duration and whether it was a
cache hit. Nothing from the file and no key is ever logged.
"""

import json
import logging
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.modules.ai.llm.json_client import (
    JSONLLMClient,
    JSONLLMError,
    LLMAuthenticationError,
    LLMBillingError,
    LLMImage,
    LLMInvalidJSONError,
    LLMNotConfiguredError,
    LLMRateLimitError,
    LLMRequestRejectedError,
    get_json_llm,
)
from app.modules.parsing.errors import (
    NoFloorPlanError,
    ParserAuthError,
    ParserBillingError,
    ParserNotConfiguredError,
    ParserRateLimitedError,
    ParserRequestRejectedError,
    ParserUnavailableError,
    PlanNormalisationError,
    PlanOutputInvalidError,
    PlanParseError,
)
from app.modules.parsing.llm_schema import WIRE_JSON_SCHEMA, check_draft
from app.modules.parsing.normalise import (
    normalise_plan,
    synthesize_interior_walls_if_missing,
    to_metres,
)
from app.modules.parsing.normalise import unit_scale as drawing_unit_scale
from app.modules.parsing.pdf_input import load_plan_pdf, sha256_of
from app.modules.parsing.plan_cache import (
    PlanCache,
    default_plan_cache,
    plan_cache_key,
    reply_cache_key,
)
from app.modules.parsing.settings import PlanParserConfigError, resolve_llm_config
from app.modules.plans.schemas import PlanJSON

logger = logging.getLogger("construtiva.parsing.llm")

# Bump when the pipeline or the normaliser changes what a given PDF parses to.
PARSER_VERSION = "2.4.0"
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
    """The LLM client the settings name (PLAN_PARSER_LLM_PROVIDER / _MODEL / _API_KEY)."""
    try:
        config = resolve_llm_config()
        return get_json_llm(
            config.provider,
            model=config.model,
            api_key=config.api_key,
            timeout_s=config.timeout_s,
        )
    except (PlanParserConfigError, LLMNotConfiguredError) as e:
        raise ParserNotConfiguredError(
            "The plan reader is not set up on this server. Please contact support.",
            details=[str(e)],
        ) from e


def _typed_llm_failure(error: JSONLLMError) -> PlanParseError:
    """The parser error, with a message for the user, that matches a client error."""
    detail = [str(error)]
    if isinstance(error, LLMNotConfiguredError):
        return ParserNotConfiguredError(
            "The plan reader is not set up on this server. Please contact support.",
            details=detail,
        )
    if isinstance(error, LLMAuthenticationError):
        return ParserAuthError(
            "The plan could not be read because the AI service refused this server's access "
            "key. Please contact support.",
            details=detail,
        )
    if isinstance(error, LLMBillingError):
        return ParserBillingError(
            "The plan could not be read because the AI service account has run out of "
            "credit or has a billing problem. Please contact support.",
            details=detail,
        )
    if isinstance(error, LLMRateLimitError):
        return ParserRateLimitedError(
            "The AI service is receiving too many requests right now. Please try again in "
            "a minute.",
            details=detail,
        )
    if isinstance(error, LLMRequestRejectedError):
        return ParserRequestRejectedError(
            "The AI service did not accept the request for this drawing. Please contact "
            "support if it keeps happening.",
            details=detail,
        )
    return ParserUnavailableError(
        "The plan could not be read because the AI service did not respond. "
        "Please try again in a moment.",
        details=detail,
    )


@dataclass
class _Usage:
    """Tokens and calls of one parse, summed over the first try and every repair."""

    input_tokens: int = 0
    output_tokens: int = 0
    attempts: int = 0

    def add(self, client: JSONLLMClient) -> None:
        self.attempts += 1
        usage = getattr(client, "last_usage", None)
        if usage is not None:
            self.input_tokens += usage.input_tokens
            self.output_tokens += usage.output_tokens


def _log_parse(
    client: Any, usage: _Usage, started: float, *, cache_hit: bool | str, outcome: str
) -> None:
    """`cache_hit` is False (a model was called), True (the stored plan was returned) or
    "reply" (the plan was built again from the stored model reply)."""
    logger.info(
        "plan parse: provider=%s model=%s input_tokens=%d output_tokens=%d attempts=%d "
        "duration_s=%.1f cache_hit=%s outcome=%s",
        getattr(client, "provider", "?"),
        getattr(client, "model", "?"),
        usage.input_tokens,
        usage.output_tokens,
        usage.attempts,
        time.monotonic() - started,
        cache_hit,
        outcome,
    )


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


def _accepted_reply(
    client: JSONLLMClient,
    images: Sequence[LLMImage],
    page_texts: Sequence[str],
    usage: _Usage,
    *,
    min_rooms: int,
) -> dict[str, Any]:
    """Stages 2 to 5: the model's reply that passed the checks, exactly as it was returned.

    Adds every model call it makes to `usage`.
    """
    system_prompt, _ = load_prompt()
    user_text = _user_text(list(page_texts) if page_texts else [""] * len(images))

    # The best structurally valid reply so far, and how many scale concerns it carries.
    accepted: dict[str, Any] | None = None
    accepted_concerns = 0
    problems: list[str] = []
    text = user_text
    for attempt in range(1 + MAX_REPAIR_ATTEMPTS):
        try:
            reply = client.generate_json(
                system_prompt=system_prompt,
                images=images,
                text=text,
                json_schema=WIRE_JSON_SCHEMA,
            )
        except LLMInvalidJSONError as e:
            usage.add(client)
            problems = [f"The reply was not a JSON object: {e}"]
            previous = e.raw_text
        except JSONLLMError as e:
            usage.attempts += 1
            if accepted is not None:
                break  # a usable reply is already in hand; keep it rather than fail
            raise _typed_llm_failure(e) from e
        else:
            usage.add(client)
            candidate, problems, concerns = check_draft(reply, min_rooms)
            if candidate is not None and not candidate.floor_plan_found:
                raise NoFloorPlanError(
                    "No floor plan was found in this PDF. Upload a drawing that shows a "
                    "floor plan with its rooms."
                )
            if candidate is not None:
                if accepted is None or len(concerns) <= accepted_concerns:
                    accepted, accepted_concerns = reply, len(concerns)
                if not concerns:
                    break
                problems = concerns
            previous = json.dumps(reply, separators=(",", ":"), default=str)
        logger.info(
            "plan parser attempt %d/%d not accepted: %d problem(s)",
            attempt + 1,
            1 + MAX_REPAIR_ATTEMPTS,
            len(problems),
        )
        text = _repair_text(user_text, previous, problems)

    if accepted is None:
        raise PlanOutputInvalidError(
            "The floor plan could not be read reliably from this drawing. "
            "Check that the PDF shows a clear, labelled floor plan and try again.",
            details=problems,
        )
    return accepted


def _plan_from_reply(
    reply: dict[str, Any],
    *,
    min_rooms: int,
    pdf_sha256: str | None,
    provider: str | None,
    model: str | None,
    usage: _Usage,
) -> dict[str, Any]:
    """Stages 6 and 7: a model reply -> validated PlanJSON. No model is involved.

    Used straight after a model call and again, later, on a reply read back from the
    cache, so a change to the normaliser or to a rule never needs a new model call.
    `usage` is what the model call that produced the reply cost.
    """
    draft, problems, _ = check_draft(reply, min_rooms)
    if draft is None or not draft.floor_plan_found:
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
        "prompt_version": prompt_version(),
        "provider": provider,
        "model": model,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "attempts": usage.attempts,
    }
    try:
        return PlanJSON.model_validate(plan).model_dump()
    except ValidationError as e:
        raise PlanNormalisationError(
            "The floor plan was read but could not be converted to a valid plan.",
            details=[str(e)[:500]],
        ) from e


def _parse_images(
    client: JSONLLMClient,
    images: Sequence[LLMImage],
    page_texts: Sequence[str],
    usage: _Usage,
    *,
    min_rooms: int,
    pdf_sha256: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Stages 2 to 7. Returns (PlanJSON, the model reply it was built from)."""
    reply = _accepted_reply(client, images, page_texts, usage, min_rooms=min_rooms)
    plan = _plan_from_reply(
        reply,
        min_rooms=min_rooms,
        pdf_sha256=pdf_sha256,
        provider=getattr(client, "provider", None),
        model=getattr(client, "model", None),
        usage=usage,
    )
    return plan, reply


def parse_plan_images(
    images: Sequence[LLMImage],
    page_texts: Sequence[str] | None = None,
    *,
    client: JSONLLMClient | None = None,
    min_rooms: int = 1,
    pdf_sha256: str | None = None,
) -> dict[str, Any]:
    """Already-rendered pages -> PlanJSON dict. Raises a PlanParseError subclass."""
    if not images:
        raise PlanParseError("There is no page image to read.")
    client = client or build_client()
    usage, started = _Usage(), time.monotonic()
    try:
        plan, _ = _parse_images(
            client, images, page_texts or [], usage, min_rooms=min_rooms, pdf_sha256=pdf_sha256
        )
    except PlanParseError as e:
        _log_parse(client, usage, started, cache_hit=False, outcome=e.code)
        raise
    _log_parse(client, usage, started, cache_hit=False, outcome="ok")
    return plan


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

    A model is called only when its reply for this PDF is not in the cache: that is, for a
    new PDF, prompt version, provider or model. Otherwise the stored plan is returned, or
    built again from the stored reply when the parser version has changed.

    A PDF over the size or page limit (PLAN_PARSER_MAX_PDF_MB, PLAN_PARSER_MAX_PDF_PAGES;
    `max_pages` overrides the latter) is rejected before any model call.
    """
    started = time.monotonic()
    client = client or build_client()
    cache = cache if cache is not None else default_plan_cache()
    pdf_sha256 = sha256_of(pdf_bytes)
    key = plan_cache_key(
        pdf_sha256, PARSER_VERSION, prompt_version(), client.provider, client.model
    )
    reply_key = reply_cache_key(pdf_sha256, prompt_version(), client.provider, client.model)
    wanted = max(min_rooms, 1)

    cached = cache.get(key) if pdf_bytes else None
    if cached and len(cached["levels"][0]["rooms"]) >= wanted:
        _log_parse(client, _Usage(), started, cache_hit=True, outcome="ok")
        return cached

    stored = cache.get_reply(reply_key) if pdf_bytes else None
    if stored:
        plan = _plan_from_stored_reply(stored, client, min_rooms=min_rooms, pdf_sha256=pdf_sha256)
        if plan is not None:
            cache.put(key, plan)
            _log_parse(client, _Usage(), started, cache_hit="reply", outcome="ok")
            return plan

    usage = _Usage()
    try:
        # Checks the size and page limits before anything is sent to a model.
        pdf = load_plan_pdf(pdf_bytes, max_pages)
        plan, reply = _parse_images(
            client,
            [LLMImage(page.png) for page in pdf.pages],
            [page.text for page in pdf.pages],
            usage,
            min_rooms=min_rooms,
            pdf_sha256=pdf.sha256,
        )
    except PlanParseError as e:
        _log_parse(client, usage, started, cache_hit=False, outcome=e.code)
        raise
    cache.put_reply(
        reply_key,
        {
            "pdf_sha256": pdf.sha256,
            "prompt_version": prompt_version(),
            "provider": client.provider,
            "model": client.model,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "attempts": usage.attempts,
            "reply": reply,
        },
    )
    cache.put(key, plan)
    _log_parse(client, usage, started, cache_hit=False, outcome="ok")
    return plan


def _plan_from_stored_reply(
    stored: dict[str, Any], client: JSONLLMClient, *, min_rooms: int, pdf_sha256: str
) -> dict[str, Any] | None:
    """PlanJSON from a cached model reply, or None when that reply can no longer be used.

    None happens when today's checks reject the stored reply, or it has fewer rooms than
    this caller needs. The PDF is then sent to the model again.
    """

    def count(name: str) -> int:
        value = stored.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    usage = _Usage(count("input_tokens"), count("output_tokens"), count("attempts"))
    try:
        return _plan_from_reply(
            stored["reply"],
            min_rooms=min_rooms,
            pdf_sha256=pdf_sha256,
            provider=client.provider,
            model=client.model,
            usage=usage,
        )
    except PlanParseError as e:
        logger.info("stored model reply not used (%s); the PDF will be parsed again", e.code)
        return None


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
