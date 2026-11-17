"""The only LLM wrapper used by the floor plan generator.

    client = get_llm()
    brief_text = client.structured(system=..., user=..., schema=TextBrief, task="brief")

Every call asks for JSON that must validate against a Pydantic model. Invalid output
gets one correction round with the exact validation errors; after that LLMError is
raised and the caller decides how to degrade. Swapping provider or model is a
settings change (FLOORPLAN_LLM_PROVIDER / FLOORPLAN_LLM_MODEL), not a code change.

The legacy `app.modules.ai.llm_client` (used by other features) is left untouched.
"""

import base64
import json
import logging
import os
import re
import time
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.modules.ai.floorplan.settings import get_settings

logger = logging.getLogger("construtiva.ai.llm")

T = TypeVar("T", bound=BaseModel)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAIN_MODEL_COOLDOWN_S = 300  # after the main model fails, use the fallback for this long

_unavailable_until: dict[str, float] = {}  # model -> monotonic time it may be retried


class LLMError(RuntimeError):
    """The LLM could not produce valid structured output (or is not configured)."""


# (image bytes, mime type) pairs sent with a structured call, e.g. [(jpg, "image/jpeg")]
Images = list[tuple[bytes, str]]


class LLMClient(Protocol):
    def structured(self, *, system: str, user: str, schema: type[T], task: str) -> T: ...


class VisionLLMClient(Protocol):
    def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        task: str,
        images: Images | None = None,
    ) -> T: ...


def _schema_instruction(schema: type[BaseModel]) -> str:
    return (
        "\n\nReply with ONE JSON object only (no prose, no markdown) that validates "
        "against this JSON Schema:\n"
        + json.dumps(schema.model_json_schema(), separators=(",", ":"))
    )


def _extract_json(text: str) -> str:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return fence.group(1) if fence else text


def parse_structured[M: BaseModel](raw: str, schema: type[M]) -> M:
    return schema.model_validate_json(_extract_json(raw))


class GeminiClient:
    def __init__(
        self,
        *,
        model: str,
        temperature: float,
        timeout_s: float,
        api_key: str,
        transport: httpx.BaseTransport | None = None,
        max_busy_retries: int = 1,
        thinking: str = "",
        fallback_model: str = "",
        connect_timeout_s: float = 10.0,
        fallback_timeout_s: float | None = None,
    ) -> None:
        self.model = model
        self.fallback_model = fallback_model
        self.temperature = temperature
        self.timeout_s = timeout_s
        self.connect_timeout_s = connect_timeout_s
        self.fallback_timeout_s = fallback_timeout_s  # None = same as timeout_s
        self._api_key = api_key
        self._transport = transport
        self._busy_retries = max_busy_retries
        self.thinking = thinking

    def _generate(self, system: str, messages: list[dict]) -> str:
        """Call the main model; if it is unavailable (timeout, busy, gone), the fallback."""
        if not self._api_key:
            raise LLMError("LLM is not configured (missing API key)")
        models = [self.model] + ([self.fallback_model] if self.fallback_model else [])
        cooling = self.fallback_model and _unavailable_until.get(self.model, 0) > time.monotonic()
        if cooling:
            models = models[1:]  # main model failed recently: do not make the user wait again
        last = "main model cooling down" if cooling else ""
        for model in models:
            ok, result = self._call_model(model, system, messages, thinking=model == self.model)
            if ok:
                if model != self.model:
                    logger.warning("llm main model unavailable (%s); used fallback %s", last, model)
                return result
            last = result
            if model == self.model:
                _unavailable_until[model] = time.monotonic() + MAIN_MODEL_COOLDOWN_S
        raise LLMError(f"LLM request failed ({last})")

    def _call_model(
        self, model: str, system: str, messages: list[dict], *, thinking: bool
    ) -> tuple[bool, str]:
        """(True, text) on success, (False, reason) if the model is unavailable.

        Raises LLMError for errors a different model would not fix (bad request, auth).
        """
        gen_cfg: dict = {"temperature": self.temperature, "response_mime_type": "application/json"}
        if thinking and self.thinking:
            gen_cfg["thinkingConfig"] = {"thinkingLevel": self.thinking}
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": messages,
            "generationConfig": gen_cfg,
        }
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._api_key}
        limit = self.timeout_s
        if model != self.model and self.fallback_timeout_s is not None:
            limit = self.fallback_timeout_s
        timeout = httpx.Timeout(limit, connect=self.connect_timeout_s)
        last = ""
        for attempt in range(self._busy_retries + 1):
            try:
                with httpx.Client(timeout=timeout, transport=self._transport) as http:
                    resp = http.post(GEMINI_URL.format(model=model), json=payload, headers=headers)
            except httpx.TimeoutException:
                return False, "timeout"  # already waited long: go to the fallback model
            except httpx.HTTPError as e:
                last = f"network error: {type(e).__name__}"
                time.sleep(1.0 * (attempt + 1))
                continue
            if resp.status_code == 200:
                try:
                    return True, resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError, ValueError) as e:
                    raise LLMError(f"unexpected LLM response shape: {e}") from e
            last = f"HTTP {resp.status_code}"
            if resp.status_code == 404:
                return False, last  # model retired or unknown
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            raise LLMError(f"LLM request rejected ({last})")
        return False, last

    def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        task: str,
        images: Images | None = None,
    ) -> T:
        """`images` is optional; text-only callers are unchanged."""
        started = time.perf_counter()
        sys_text = system + _schema_instruction(schema)
        parts: list[dict] = [
            {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}}
            for data, mime in images or []
        ]
        parts.append({"text": user})
        messages = [{"role": "user", "parts": parts}]
        raw = self._generate(sys_text, messages)
        try:
            result = parse_structured(raw, schema)
        except (ValidationError, ValueError) as first_error:
            logger.info("llm task=%s invalid output, asking for a correction", task)
            messages += [
                {"role": "model", "parts": [{"text": raw}]},
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": "That JSON is invalid: "
                            + str(first_error)[:1500]
                            + "\nReturn the corrected JSON object only."
                        }
                    ],
                },
            ]
            raw = self._generate(sys_text, messages)
            try:
                result = parse_structured(raw, schema)
            except (ValidationError, ValueError) as e:
                raise LLMError(f"LLM output failed validation twice: {str(e)[:300]}") from e
        logger.info("llm task=%s ok in %.1fs", task, time.perf_counter() - started)
        return result


def api_key() -> str:
    """The Gemini key from the environment / app settings (never stored in code)."""
    return _api_key()


def _api_key() -> str:
    from app.core.config import settings as app_settings  # read-only use of app settings

    return (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or app_settings.gemini_api_key
        or app_settings.llm_api_key
        or ""
    )


def get_llm() -> LLMClient:
    s = get_settings()
    if s.llm_provider != "gemini":
        raise LLMError(f"unsupported LLM provider: {s.llm_provider}")
    return GeminiClient(
        model=s.llm_model,
        temperature=s.llm_temperature,
        timeout_s=s.llm_timeout_s,
        api_key=_api_key(),
        thinking=s.llm_thinking,
        fallback_model=s.llm_fallback_model,
    )
