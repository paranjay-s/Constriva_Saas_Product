"""Anthropic (Claude) adapter for `JSONLLMClient`, built on the official `anthropic` SDK.

The only module that knows the Claude API. What it does, and why (checked against the
docs at platform.claude.com/docs in November 2026):

  * The key is passed to the SDK explicitly. The client is never built without one, so
    the SDK's own lookup of ANTHROPIC_API_KEY and of login profiles is never used.
  * No sampling parameter is sent. The current API version rejects `temperature`, `top_p`
    and `top_k` on every model, and the SDK no longer accepts them.
  * Images go before the text, as the vision guide recommends. The API scales any image
    down to at most 2576 px on its long edge, so larger pages are scaled here first: the
    model sees the same pixels and the upload is smaller. An image is kept under the
    10 MB (base64) per-image limit.
  * JSON comes back through structured outputs (`output_config.format`) when the schema
    fits the documented grammar limits (24 optional and 16 union-typed parameters).
    A schema that does not fit is sent as instructions in the system prompt instead.
  * The reply is streamed, which the SDK requires for a large `max_tokens`.
  * The SDK's own retries are switched off. Retrying is done by `with_retries`, the same
    bounded policy every adapter uses: rate limits and 5xx only.
  * `thinking` and `effort` are left at the model's defaults, so any current Claude model
    can be configured without a code change.
"""

import base64
import io
import logging
import time
from collections.abc import Callable, Sequence
from typing import Any

import anthropic
from PIL import Image

from app.modules.ai.llm.json_client import (
    LLMAuthenticationError,
    LLMBillingError,
    LLMImage,
    LLMInvalidJSONError,
    LLMNotConfiguredError,
    LLMRateLimitError,
    LLMRequestRejectedError,
    LLMServerError,
    LLMUnavailableError,
    LLMUsage,
    extract_json_object,
    schema_instruction,
    with_retries,
)

logger = logging.getLogger("construtiva.ai.llm.anthropic_json")

# Largest long edge any current model processes (the high-resolution tier).
MAX_IMAGE_LONG_EDGE_PX = 2576
# Per-image limit on the Claude API is 10 MB of base64; stay well inside it.
MAX_IMAGE_BASE64_BYTES = 8 * 1024 * 1024
# Room for the plan JSON plus the model's own thinking. Streaming makes this safe.
MAX_OUTPUT_TOKENS = 64000

# Documented limits of the structured-output grammar.
MAX_OPTIONAL_PARAMETERS = 24
MAX_UNION_PARAMETERS = 16


def schema_fits_grammar(schema: dict[str, Any]) -> bool:
    """True when `schema` is within the structured-output limits on optional and union fields."""
    optional = unions = 0

    def walk(node: Any) -> None:
        nonlocal optional, unions
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                required = set(node.get("required") or [])
                optional += sum(1 for name in properties if name not in required)
                unions += sum(
                    1
                    for sub in properties.values()
                    if isinstance(sub, dict)
                    and ("anyOf" in sub or isinstance(sub.get("type"), list))
                )
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return optional <= MAX_OPTIONAL_PARAMETERS and unions <= MAX_UNION_PARAMETERS


def prepare_image(image: LLMImage) -> tuple[str, str]:
    """(media type, base64 data) of an image the API accepts without further scaling.

    Deterministic: the same bytes in always give the same bytes out.
    """
    data, media_type = image.data, image.mime_type
    try:
        picture = Image.open(io.BytesIO(data))
        picture.load()
    except Exception:
        # Not an image Pillow can open: send it as it is and let the API judge it.
        return media_type, base64.standard_b64encode(data).decode("ascii")

    long_edge = max(picture.size)
    if long_edge > MAX_IMAGE_LONG_EDGE_PX:
        ratio = MAX_IMAGE_LONG_EDGE_PX / long_edge
        size = (max(1, round(picture.width * ratio)), max(1, round(picture.height * ratio)))
        picture = picture.convert("RGB").resize(size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        picture.save(buffer, format="PNG", optimize=True)
        data, media_type = buffer.getvalue(), "image/png"

    encoded = base64.standard_b64encode(data)
    if len(encoded) > MAX_IMAGE_BASE64_BYTES:
        # A dense scan: a high-quality JPEG is far smaller and keeps the drawing legible.
        buffer = io.BytesIO()
        picture.convert("RGB").save(buffer, format="JPEG", quality=90)
        encoded, media_type = base64.standard_b64encode(buffer.getvalue()), "image/jpeg"
    return media_type, encoded.decode("ascii")


def _spend_cap_reached(error: anthropic.APIStatusError) -> bool:
    """A 429 that waiting will not clear: the organisation's spend cap."""
    body = error.body if isinstance(error.body, dict) else {}
    details = (body.get("error") or {}).get("details") or {}
    return isinstance(details, dict) and details.get("error_code") == "enforced_spend_limit_reached"


def _retry_after(error: anthropic.APIStatusError) -> float | None:
    try:
        return float(error.response.headers.get("retry-after", ""))
    except ValueError:
        return None


class AnthropicJSONClient:
    provider = "anthropic"

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        timeout_s: float = 300.0,
        http_client: anthropic.DefaultHttpxClient | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not model:
            raise LLMNotConfiguredError("No Anthropic model was given.")
        if not api_key:
            raise LLMNotConfiguredError("No Anthropic API key was given.")
        self.model = model
        self.last_usage: LLMUsage | None = None
        self._sleep = sleep
        # max_retries=0: retrying is `with_retries`' job, with one policy for all vendors.
        self._client = anthropic.Anthropic(
            api_key=api_key, max_retries=0, timeout=timeout_s, http_client=http_client
        )

    def generate_json(
        self,
        *,
        system_prompt: str,
        images: Sequence[LLMImage],
        text: str,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = []
        for image in images:
            media_type, data = prepare_image(image)
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": data},
                }
            )
        if content:
            # The instructions and the pages are identical on a repair attempt: cache them.
            content[-1]["cache_control"] = {"type": "ephemeral"}
        content.append({"type": "text", "text": text})

        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "system": system_prompt,
            "messages": [{"role": "user", "content": content}],
        }
        if json_schema and schema_fits_grammar(json_schema):
            request["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": anthropic.transform_schema(json_schema),
                }
            }
        elif json_schema:
            request["system"] = system_prompt + schema_instruction(json_schema)

        self.last_usage = None
        message = with_retries(lambda: self._send(request), sleep=self._sleep)

        usage = message.usage
        self.last_usage = LLMUsage(
            input_tokens=int(usage.input_tokens or 0)
            + int(usage.cache_creation_input_tokens or 0)
            + int(usage.cache_read_input_tokens or 0),
            output_tokens=int(usage.output_tokens or 0),
        )
        reply = "".join(block.text for block in message.content if block.type == "text")
        if message.stop_reason == "refusal":
            raise LLMRequestRejectedError("Claude declined to answer this request.")
        if message.stop_reason == "max_tokens":
            raise LLMInvalidJSONError("Claude stopped at its output limit (reply cut off).", reply)
        return extract_json_object(reply)

    def _send(self, request: dict[str, Any]) -> anthropic.types.Message:
        """One streamed request, with every SDK error turned into its typed equivalent."""
        try:
            with self._client.messages.stream(**request) as stream:
                return stream.get_final_message()
        except anthropic.AuthenticationError as e:
            raise LLMAuthenticationError("Anthropic refused the API key (HTTP 401).") from e
        except anthropic.PermissionDeniedError as e:
            raise LLMAuthenticationError(
                "The Anthropic API key is not allowed to make this request (HTTP 403)."
            ) from e
        except anthropic.RateLimitError as e:
            if _spend_cap_reached(e):
                raise LLMBillingError("The Anthropic account reached its spend limit.") from e
            raise LLMRateLimitError(
                "Anthropic rate limit reached (HTTP 429).", _retry_after(e)
            ) from e
        except anthropic.NotFoundError as e:
            raise LLMRequestRejectedError(
                f"Anthropic does not know model {self.model!r}, or the key cannot use it "
                "(HTTP 404)."
            ) from e
        except anthropic.BadRequestError as e:
            if "credit balance" in str(e.message).lower():
                raise LLMBillingError("The Anthropic account has no credit left.") from e
            raise LLMRequestRejectedError(
                f"Anthropic rejected the request (HTTP 400): {str(e.message)[:300]}"
            ) from e
        except anthropic.APIStatusError as e:
            if e.status_code == 402 or e.type == "billing_error":
                raise LLMBillingError(
                    "Anthropic reports a billing problem on the account (HTTP 402)."
                ) from e
            if e.status_code >= 500:
                raise LLMServerError(f"Anthropic server error (HTTP {e.status_code}).") from e
            raise LLMRequestRejectedError(
                f"Anthropic rejected the request (HTTP {e.status_code})."
            ) from e
        except anthropic.APITimeoutError as e:
            raise LLMUnavailableError("Anthropic did not answer in time.") from e
        except anthropic.APIConnectionError as e:
            raise LLMUnavailableError("Anthropic could not be reached.") from e
