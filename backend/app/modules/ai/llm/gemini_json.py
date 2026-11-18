"""Gemini adapter for `JSONLLMClient`. The only module that knows Gemini's API.

The key is passed in by the caller and travels in a header, never in the URL, so it
cannot end up in access logs or error messages. Temperature is 0; if a model rejects the
parameter the request is sent again without it.
"""

import base64
import logging
import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx

from app.modules.ai.llm.json_client import (
    JSONLLMError,
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

logger = logging.getLogger("construtiva.ai.llm.gemini_json")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _error_fields(resp: httpx.Response) -> tuple[str, str, list[str]]:
    """(status text, message, detail reasons) of a Gemini error body; blanks if unreadable."""
    try:
        error = resp.json().get("error") or {}
    except ValueError:
        return "", "", []
    reasons = [str(d.get("reason", "")) for d in error.get("details") or [] if isinstance(d, dict)]
    return str(error.get("status", "")), str(error.get("message", "")), reasons


def _retry_after(resp: httpx.Response) -> float | None:
    try:
        return float(resp.headers.get("retry-after", ""))
    except ValueError:
        return None


def _raise_for_status(resp: httpx.Response) -> None:
    """Turn a non-200 Gemini response into the matching typed error."""
    code = resp.status_code
    status, message, reasons = _error_fields(resp)
    lower = message.lower()
    summary = f"HTTP {code}" + (f" {status}" if status else "")

    # Gemini reports a bad key as 400 INVALID_ARGUMENT with reason API_KEY_INVALID.
    bad_key = "API_KEY_INVALID" in reasons or "api key not valid" in lower
    if code in (401, 403) and "billing" in lower:
        raise LLMBillingError(f"Gemini reports a billing problem on the account ({summary}).")
    if code in (401, 403) or bad_key:
        raise LLMAuthenticationError(f"Gemini refused the API key ({summary}).")
    if code == 429:
        raise LLMRateLimitError(
            f"Gemini rate limit or quota reached ({summary}).", _retry_after(resp)
        )
    if code >= 500:
        raise LLMServerError(f"Gemini server error ({summary}).")
    if code == 404:
        raise LLMRequestRejectedError(
            f"Gemini does not know this model, or the key cannot use it ({summary})."
        )
    raise LLMRequestRejectedError(f"Gemini rejected the request ({summary}): {message[:200]}")


class GeminiJSONClient:
    provider = "gemini"

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        timeout_s: float = 300.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not model:
            raise LLMNotConfiguredError("No Gemini model was given.")
        if not api_key:
            raise LLMNotConfiguredError("No Gemini API key was given.")
        self.model = model
        self.timeout_s = timeout_s
        self.last_usage: LLMUsage | None = None
        self._api_key = api_key
        self._transport = transport
        self._sleep = sleep
        self._send_temperature = True

    def generate_json(
        self,
        *,
        system_prompt: str,
        images: Sequence[LLMImage],
        text: str,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
        self.last_usage = None
        try:
            body = with_retries(lambda: self._post(system, parts), sleep=self._sleep)
        except LLMRequestRejectedError as e:
            if not (self._send_temperature and "temperature" in str(e).lower()):
                raise
            # This model does not take the sampling parameter: leave it out from now on.
            logger.info("gemini model %s rejects temperature; sending without it", self.model)
            self._send_temperature = False
            body = with_retries(lambda: self._post(system, parts), sleep=self._sleep)
        usage = body.get("usageMetadata") or {}
        self.last_usage = LLMUsage(
            input_tokens=int(usage.get("promptTokenCount") or 0),
            output_tokens=int(usage.get("candidatesTokenCount") or 0)
            + int(usage.get("thoughtsTokenCount") or 0),
        )
        return extract_json_object(self._reply_text(body))

    def _post(self, system: str, parts: list[dict[str, Any]]) -> dict[str, Any]:
        config: dict[str, Any] = {"response_mime_type": "application/json"}
        if self._send_temperature:
            config["temperature"] = 0
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": config,
        }
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._api_key}
        try:
            with httpx.Client(timeout=self.timeout_s, transport=self._transport) as http:
                resp = http.post(GEMINI_URL.format(model=self.model), json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise LLMUnavailableError("Gemini did not answer in time.") from e
        except httpx.HTTPError as e:
            raise LLMUnavailableError(f"Gemini could not be reached ({type(e).__name__}).") from e
        if resp.status_code != 200:
            _raise_for_status(resp)
        try:
            return resp.json()
        except ValueError as e:
            raise LLMInvalidJSONError(
                "Gemini returned a non-JSON HTTP body.", resp.text[:2000]
            ) from e

    @staticmethod
    def _reply_text(body: dict[str, Any]) -> str:
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


__all__ = ["GeminiJSONClient", "JSONLLMError"]
