"""Provider-neutral "images + text in, one JSON object out" LLM interface.

    client = get_json_llm("anthropic", model="...", api_key="...")
    data = client.generate_json(
        system_prompt=..., images=[LLMImage(png)], text=..., json_schema=schema
    )

Callers depend on `JSONLLMClient` and on the error classes below, nothing else. Everything
that knows a vendor's URL, SDK, payload shape or error format lives in that vendor's
adapter module. Adding a vendor is one new adapter file and one entry in `_ADAPTERS`.

Rules every adapter follows:

  * the API key is passed in by the caller; an adapter never reads key variables itself;
  * exactly the configured model answers; there is no fallback to another model or vendor;
  * failures are raised as the typed errors below;
  * only rate limits and 5xx responses are retried, a bounded number of times
    (`with_retries`). Authentication and billing errors are never retried.

The floor plan generator and the material finder use the older `llm.client.GeminiClient`;
that module is unchanged.
"""

import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger("construtiva.ai.llm.json")


@dataclass(frozen=True)
class LLMImage:
    data: bytes
    mime_type: str = "image/png"


@dataclass(frozen=True)
class LLMUsage:
    """Tokens one call was billed for."""

    input_tokens: int = 0
    output_tokens: int = 0


# ----------------------------------------------------------------------------- errors


class JSONLLMError(RuntimeError):
    """Base class. Messages are safe to log: they never contain a key or file content."""


class LLMNotConfiguredError(JSONLLMError):
    """Unknown provider, or no model or API key was given."""


class LLMAuthenticationError(JSONLLMError):
    """The provider refused the API key (invalid, revoked, or not allowed). Never retried."""


class LLMBillingError(JSONLLMError):
    """The provider account has no credit, a payment problem, or hit its spend cap.

    Never retried: waiting does not fix it.
    """


class LLMRateLimitError(JSONLLMError):
    """Too many requests. Retried a bounded number of times, then raised."""

    def __init__(self, message: str, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class LLMUnavailableError(JSONLLMError):
    """The provider could not be reached, timed out, or kept failing."""


class LLMServerError(LLMUnavailableError):
    """A 5xx response. Retried a bounded number of times, then raised."""


class LLMRequestRejectedError(JSONLLMError):
    """The provider refused this request (bad request, unknown model, declined content)."""


class LLMInvalidJSONError(JSONLLMError):
    """The provider answered, but not with a JSON object. `raw_text` is that answer."""

    def __init__(self, message: str, raw_text: str = "") -> None:
        super().__init__(message)
        self.raw_text = raw_text


# -------------------------------------------------------------------------- interface


class JSONLLMClient(Protocol):
    provider: str
    model: str
    last_usage: LLMUsage | None  # usage of the most recent call, when the provider reports it

    def generate_json(
        self,
        *,
        system_prompt: str,
        images: Sequence[LLMImage],
        text: str,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the model's reply parsed as one JSON object.

        Raises LLMInvalidJSONError when the reply is not a JSON object, and another
        JSONLLMError subclass when no usable reply could be obtained.
        """
        ...


def schema_instruction(json_schema: dict[str, Any]) -> str:
    """Text that asks for JSON matching `json_schema`. Works with any provider."""
    return (
        "\n\nReply with ONE JSON object only (no prose, no markdown fences) that validates "
        "against this JSON Schema:\n" + json.dumps(json_schema, separators=(",", ":"))
    )


_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse the JSON object in a model reply.

    Accepts a bare object, an object inside a markdown fence, or an object with prose
    around it. Anything else raises LLMInvalidJSONError.
    """
    raw = (text or "").strip()
    if not raw:
        raise LLMInvalidJSONError("The model returned an empty reply.", raw)
    fenced = _FENCE.match(raw)
    candidates = [fenced.group(1)] if fenced else []
    candidates.append(raw)
    first, last = raw.find("{"), raw.rfind("}")
    if 0 <= first < last:
        candidates.append(raw[first : last + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise LLMInvalidJSONError("The model reply is not a JSON object.", raw)


# ---------------------------------------------------------------------------- retries

# Waits before the 2nd and 3rd try. Three tries at most, about 8 seconds of waiting.
RETRY_DELAYS_S: tuple[float, ...] = (2.0, 6.0)
# A provider's own "retry after" hint is honoured up to this many seconds.
MAX_RETRY_AFTER_S = 30.0


def with_retries[T](
    call: Callable[[], T],
    *,
    sleep: Callable[[float], None] = time.sleep,
    delays: Sequence[float] = RETRY_DELAYS_S,
) -> T:
    """Run `call`, retrying only a rate limit or a 5xx response, with bounded backoff.

    Any other failure, authentication and billing errors included, is raised at once.
    """
    for delay in (*delays, None):
        try:
            return call()
        except (LLMRateLimitError, LLMServerError) as e:
            if delay is None:
                raise
            hinted = getattr(e, "retry_after_s", None)
            wait = min(hinted, MAX_RETRY_AFTER_S) if hinted and hinted > 0 else delay
            logger.warning("llm call failed (%s); retrying in %.0fs", type(e).__name__, wait)
            sleep(wait)
    raise AssertionError("unreachable")  # the loop always returns or raises


# --------------------------------------------------------------------------- registry

# (model, api_key, timeout_s) -> client
AdapterFactory = Callable[[str, str, float], JSONLLMClient]


def _gemini(model: str, api_key: str, timeout_s: float) -> JSONLLMClient:
    from app.modules.ai.llm.gemini_json import GeminiJSONClient

    return GeminiJSONClient(model=model, api_key=api_key, timeout_s=timeout_s)


def _anthropic(model: str, api_key: str, timeout_s: float) -> JSONLLMClient:
    from app.modules.ai.llm.anthropic_json import AnthropicJSONClient

    return AnthropicJSONClient(model=model, api_key=api_key, timeout_s=timeout_s)


_ADAPTERS: dict[str, AdapterFactory] = {"anthropic": _anthropic, "gemini": _gemini}


def known_providers() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))


def get_json_llm(
    provider: str, *, model: str, api_key: str, timeout_s: float = 300.0
) -> JSONLLMClient:
    """Build the client for `provider`. The model and the key must both be given."""
    factory = _ADAPTERS.get((provider or "").strip().lower())
    if factory is None:
        raise LLMNotConfiguredError(
            f"Unsupported LLM provider {provider!r}. Known: {', '.join(known_providers())}."
        )
    if not model:
        raise LLMNotConfiguredError(f"No model was given for the {provider} provider.")
    if not api_key:
        raise LLMNotConfiguredError(f"No API key was given for the {provider} provider.")
    return factory(model, api_key, timeout_s)
