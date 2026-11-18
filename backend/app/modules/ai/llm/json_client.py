"""Provider-neutral "images + text in, one JSON object out" LLM interface.

    client = get_json_llm("gemini", model="...", api_key="...")
    data = client.generate_json(
        system_prompt=..., images=[LLMImage(png)], text=..., json_schema=schema
    )

Callers depend on `JSONLLMClient` only. Everything that knows a provider's URL, payload
shape, model names or key variables lives in that provider's adapter module, so moving to
another model means writing one adapter and registering it in `_ADAPTERS`.

The floor plan generator and the material finder use the older `llm.client.GeminiClient`;
that module is unchanged.
"""

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMImage:
    data: bytes
    mime_type: str = "image/png"


class JSONLLMError(RuntimeError):
    """Base class. `message` is safe to log; it never contains the API key."""


class LLMNotConfiguredError(JSONLLMError):
    """Unknown provider, or no API key for it."""


class LLMUnavailableError(JSONLLMError):
    """The provider could not be reached or kept failing (timeouts, 429, 5xx)."""


class LLMRequestRejectedError(JSONLLMError):
    """The provider refused the request (bad request, bad key, blocked content)."""


class LLMInvalidJSONError(JSONLLMError):
    """The provider answered, but not with a JSON object. `raw_text` is that answer."""

    def __init__(self, message: str, raw_text: str = "") -> None:
        super().__init__(message)
        self.raw_text = raw_text


class JSONLLMClient(Protocol):
    provider: str
    model: str  # the model that answered the most recent call

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
        JSONLLMError subclass when no reply could be obtained.
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


# (model, fallback_models, api_key, timeout_s) -> client
AdapterFactory = Callable[[str, Sequence[str] | None, str, float], JSONLLMClient]


def _gemini(
    model: str, fallback_models: Sequence[str] | None, api_key: str, timeout_s: float
) -> JSONLLMClient:
    from app.modules.ai.llm.gemini_json import GeminiJSONClient

    return GeminiJSONClient(
        model=model, fallback_models=fallback_models, api_key=api_key, timeout_s=timeout_s
    )


_ADAPTERS: dict[str, AdapterFactory] = {"gemini": _gemini}


def get_json_llm(
    provider: str,
    *,
    model: str = "",
    fallback_models: Sequence[str] | None = None,
    api_key: str = "",
    timeout_s: float = 120.0,
) -> JSONLLMClient:
    """Build the client for `provider`.

    An empty `model` or `api_key`, and `fallback_models=None`, mean "the adapter's own
    default" (its default model, its usual environment variables, its fallback list).
    """
    factory = _ADAPTERS.get((provider or "").strip().lower())
    if factory is None:
        known = ", ".join(sorted(_ADAPTERS))
        raise LLMNotConfiguredError(f"Unsupported LLM provider {provider!r}. Known: {known}.")
    return factory(model, fallback_models, api_key, timeout_s)
