"""The floor plan generator's `LLMClient`, on the provider-neutral settings.

The generator's chat (brief, room sizes, edits) calls `structured(system=..., user=...,
schema=...)`. This adapter answers it with the provider-neutral JSON client
(`json_client.get_json_llm`) configured by PLAN_PARSER_LLM_PROVIDER / _MODEL / _API_KEY,
the same settings as the plan reader and every 3D AI feature, so the strongest model
configured there is used and a change of vendor is a change of settings only.

Invalid output gets one correction round with the validation errors (as GeminiClient
did). The model's name is on `.model`, so each plan version can record which model made
it. When the neutral settings are incomplete, `get_generator_llm` falls back to the older
FLOORPLAN_LLM_* Gemini client and logs why.
"""

import json
import logging
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.modules.ai.llm.client import LLMError, get_llm
from app.modules.ai.llm.json_client import JSONLLMClient, JSONLLMError, get_json_llm

logger = logging.getLogger("construtiva.ai.llm.neutral")
T = TypeVar("T", bound=BaseModel)


class NeutralLLM:
    def __init__(self, client: JSONLLMClient) -> None:
        self._client = client
        self.provider = client.provider
        self.model = client.model

    def structured(self, *, system: str, user: str, schema: type[T], task: str, images=None) -> T:
        from app.modules.ai.llm.json_client import LLMImage

        pics = [LLMImage(data, mime) for data, mime in images or []]
        json_schema = schema.model_json_schema()
        started = time.perf_counter()
        text = user
        for attempt in (1, 2):
            try:
                raw = self._client.generate_json(
                    system_prompt=system, images=pics, text=text, json_schema=json_schema
                )
            except JSONLLMError as e:
                raise LLMError(f"LLM request failed ({type(e).__name__})") from e
            try:
                result = schema.model_validate(raw)
                logger.info(
                    "llm task=%s model=%s ok in %.1fs",
                    task,
                    self.model,
                    time.perf_counter() - started,
                )
                return result
            except ValidationError as e:
                if attempt == 2:
                    raise LLMError(f"LLM output failed validation twice: {str(e)[:300]}") from e
                logger.info("llm task=%s invalid output, asking for a correction", task)
                text = (
                    user
                    + "\n\nYour previous reply was invalid:\n"
                    + json.dumps(raw, ensure_ascii=False)[:4000]
                    + "\nErrors: "
                    + str(e)[:1500]
                    + "\nReturn the corrected JSON object only."
                )
        raise LLMError("unreachable")  # pragma: no cover


def get_generator_llm():
    """The provider-neutral client when PLAN_PARSER_LLM_* are complete, else the older
    FLOORPLAN_LLM_* Gemini client. Raises LLMError when neither is configured."""
    from app.modules.parsing.settings import PlanParserConfigError, resolve_llm_config

    try:
        config = resolve_llm_config()
        client = get_json_llm(
            config.provider,
            model=config.model,
            api_key=config.api_key,
            timeout_s=min(config.timeout_s, 90.0),
        )
        return NeutralLLM(client)
    except (PlanParserConfigError, JSONLLMError) as e:
        logger.warning("provider-neutral LLM settings unusable (%s); using FLOORPLAN_LLM_*", e)
        return get_llm()
