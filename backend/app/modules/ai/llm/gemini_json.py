"""Gemini adapter for `JSONLLMClient`. The only module that knows Gemini's API.

Temperature is always 0. The API key travels in a header, never in the URL, so it cannot
end up in access logs or error messages.
"""

import base64
import logging
import os
import time
from collections.abc import Sequence
from typing import Any

import httpx

from app.modules.ai.llm.json_client import (
    LLMImage,
    LLMInvalidJSONError,
    LLMNotConfiguredError,
    LLMRequestRejectedError,
    LLMUnavailableError,
    extract_json_object,
    schema_instruction,
)

logger = logging.getLogger("construtiva.ai.llm.gemini_json")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Same model order the blueprint parser has always tried.
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_FALLBACK_MODELS = (
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "gemini-3.7-flash",
)

BUSY_STATUS = (429, 500, 502, 503, 504)
BUSY_RETRIES = 1  # extra tries on the same model before moving to the next one


def resolve_api_key(explicit: str = "") -> str:
    """Explicit key, else the Gemini variables, else the app's generic LLM key."""
    if explicit:
        return explicit
    from app.core.config import settings  # read at call time so tests can patch the env

    return (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or settings.gemini_api_key
        or settings.llm_api_key
        or ""
    )


class GeminiJSONClient:
    provider = "gemini"

    def __init__(
        self,
        *,
        model: str = "",
        fallback_models: Sequence[str] | None = None,
        api_key: str = "",
        timeout_s: float = 120.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        self.primary_model = model or DEFAULT_MODEL
        fallbacks = DEFAULT_FALLBACK_MODELS if fallback_models is None else fallback_models
        self.fallback_models = tuple(m for m in fallbacks if m and m != self.primary_model)
        self.model = self.primary_model
        self.timeout_s = timeout_s
        self._api_key = api_key
        self._transport = transport
        self._sleep = sleep

    def generate_json(
        self,
        *,
        system_prompt: str,
        images: Sequence[LLMImage],
        text: str,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = resolve_api_key(self._api_key)
        if not key:
            raise LLMNotConfiguredError(
                "No Gemini API key. Set GEMINI_API_KEY (or LLM_API_KEY) in .env."
            )
        system = system_prompt + (schema_instruction(json_schema) if json_schema else "")
        parts: list[dict[str, Any]] = [
            {
                "inline_data": {
                    "mime_type": img.mime_type,
                    "data": base64.b64encode(img.data).decode("ascii"),
                }
            }
            for img in images
        ]
        parts.append({"text": text})
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0, "response_mime_type": "application/json"},
        }
        headers = {"Content-Type": "application/json", "x-goog-api-key": key}

        last = "no model tried"
        for model in (self.primary_model, *self.fallback_models):
            ok, result = self._call_model(model, payload, headers)
            if ok:
                self.model = model
                if model != self.primary_model:
                    logger.warning(
                        "gemini: %s unavailable (%s); used %s", self.primary_model, last, model
                    )
                return extract_json_object(result)
            last = result
        raise LLMUnavailableError(f"Gemini request failed on every model ({last}).")

    def _call_model(
        self, model: str, payload: dict[str, Any], headers: dict[str, str]
    ) -> tuple[bool, str]:
        """(True, reply text), or (False, reason) when another model might still work.

        Raises LLMRequestRejectedError for failures no other model would fix.
        """
        last = ""
        for attempt in range(BUSY_RETRIES + 1):
            try:
                with httpx.Client(timeout=self.timeout_s, transport=self._transport) as http:
                    resp = http.post(GEMINI_URL.format(model=model), json=payload, headers=headers)
            except httpx.TimeoutException:
                return False, "timeout"
            except httpx.HTTPError as e:
                last = f"network error: {type(e).__name__}"
                self._sleep(1.0 * (attempt + 1))
                continue
            if resp.status_code == 200:
                return True, self._reply_text(resp)
            last = f"HTTP {resp.status_code}"
            if resp.status_code == 404:
                return False, last  # model retired or unknown: try the next one
            if resp.status_code in BUSY_STATUS:
                self._sleep(1.5 * (attempt + 1))
                continue
            raise LLMRequestRejectedError(f"Gemini rejected the request ({last}).")
        return False, last

    @staticmethod
    def _reply_text(resp: httpx.Response) -> str:
        try:
            body = resp.json()
        except ValueError as e:
            raise LLMInvalidJSONError(
                "Gemini returned a non-JSON HTTP body.", resp.text[:2000]
            ) from e
        candidates = body.get("candidates") or []
        if not candidates:
            reason = (body.get("promptFeedback") or {}).get("blockReason", "no candidates")
            raise LLMRequestRejectedError(f"Gemini returned no answer ({reason}).")
        candidate = candidates[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if candidate.get("finishReason") == "MAX_TOKENS":
            # A cut-off reply is not parseable JSON; report it as such so the caller can retry.
            raise LLMInvalidJSONError("Gemini stopped at its output limit (reply cut off).", text)
        return text
