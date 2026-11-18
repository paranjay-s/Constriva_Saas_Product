"""Provider-neutral LLM layer: settings, registry, retry policy and both adapters.

Every HTTP exchange here goes through a mock transport. Nothing reaches a provider.
"""

import base64
import io
import json

import anthropic
import httpx
import httpx2
import pytest
from PIL import Image
from pydantic import SecretStr

from app.modules.ai.llm import json_client
from app.modules.ai.llm.anthropic_json import (
    MAX_IMAGE_LONG_EDGE_PX,
    AnthropicJSONClient,
    prepare_image,
    schema_fits_grammar,
)
from app.modules.ai.llm.gemini_json import GeminiJSONClient
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
    get_json_llm,
    known_providers,
    with_retries,
)
from app.modules.parsing import settings as parser_settings
from app.modules.parsing.llm_schema import WIRE_JSON_SCHEMA, LLMPlanDraft
from app.modules.parsing.settings import (
    PlanParserConfigError,
    PlanParserSettings,
    resolve_llm_config,
)

SECRET = "sk-test-not-a-real-key-123456"
no_sleep = lambda _seconds: None  # noqa: E731


def png(width: int = 40, height: int = 30) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


# --------------------------------------------------------------------------- settings


def make_settings(**values) -> PlanParserSettings:
    """Settings built from explicit values only, ignoring the machine's .env and environment."""
    return PlanParserSettings.model_construct(
        **{
            "llm_provider": "gemini",
            "llm_model": "",
            "llm_api_key": SecretStr(""),
            "llm_timeout_s": 300.0,
            "max_pdf_mb": 20.0,
            "max_pdf_pages": 10,
            "cache": "on",
            "cache_dir": "",
            **values,
        }
    )


@pytest.fixture
def no_legacy_keys(monkeypatch):
    monkeypatch.setattr(parser_settings, "_legacy_gemini_key", lambda: "")


def test_settings_resolve_to_provider_model_and_key(no_legacy_keys):
    config = resolve_llm_config(
        make_settings(
            llm_provider="Anthropic", llm_model=" claude-x ", llm_api_key=SecretStr(SECRET)
        )
    )
    assert (config.provider, config.model, config.api_key) == ("anthropic", "claude-x", SECRET)


def test_provider_defaults_to_gemini(no_legacy_keys):
    config = resolve_llm_config(
        make_settings(llm_provider="", llm_model="m", llm_api_key=SecretStr(SECRET))
    )
    assert config.provider == "gemini"
    assert PlanParserSettings.model_fields["llm_provider"].default == "gemini"


def test_unknown_provider_is_one_clear_error_naming_the_variable(no_legacy_keys):
    with pytest.raises(PlanParserConfigError) as caught:
        resolve_llm_config(
            make_settings(llm_provider="openai", llm_model="m", llm_api_key=SecretStr(SECRET))
        )
    message = str(caught.value)
    assert "PLAN_PARSER_LLM_PROVIDER" in message and "'openai'" in message
    assert "anthropic, gemini" in message


def test_missing_model_is_one_clear_error_naming_the_variable(no_legacy_keys):
    with pytest.raises(PlanParserConfigError, match="PLAN_PARSER_LLM_MODEL is not set"):
        resolve_llm_config(make_settings(llm_provider="anthropic", llm_api_key=SecretStr(SECRET)))


@pytest.mark.parametrize("provider", ["anthropic", "gemini"])
def test_missing_key_is_one_clear_error_naming_the_variable(provider, no_legacy_keys):
    with pytest.raises(PlanParserConfigError, match="PLAN_PARSER_LLM_API_KEY is not set"):
        resolve_llm_config(make_settings(llm_provider=provider, llm_model="m"))


def test_gemini_falls_back_to_llm_api_key_then_gemini_api_key(monkeypatch):
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "llm_api_key", "legacy-llm-key")
    monkeypatch.setattr(app_settings, "gemini_api_key", "legacy-gemini-key")
    assert resolve_llm_config(make_settings(llm_model="m")).api_key == "legacy-llm-key"

    monkeypatch.setattr(app_settings, "llm_api_key", "")
    assert resolve_llm_config(make_settings(llm_model="m")).api_key == "legacy-gemini-key"

    # the parser's own key always wins when it is set
    chosen = resolve_llm_config(make_settings(llm_model="m", llm_api_key=SecretStr(SECRET)))
    assert chosen.api_key == SECRET


def test_only_gemini_has_the_legacy_key_fallback(monkeypatch):
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "llm_api_key", "legacy-llm-key")
    monkeypatch.setattr(app_settings, "gemini_api_key", "legacy-gemini-key")
    with pytest.raises(PlanParserConfigError, match="PLAN_PARSER_LLM_API_KEY is not set"):
        resolve_llm_config(make_settings(llm_provider="anthropic", llm_model="m"))


def test_the_key_never_appears_in_reprs(no_legacy_keys):
    settings = make_settings(llm_model="m", llm_api_key=SecretStr(SECRET))
    config = resolve_llm_config(settings)
    assert SECRET not in repr(settings) and SECRET not in str(settings)
    assert SECRET not in repr(config) and SECRET not in str(config)


def test_no_setting_is_named_after_a_vendor():
    for name in PlanParserSettings.model_fields:
        assert "gemini" not in name and "anthropic" not in name and "claude" not in name


@pytest.mark.parametrize(
    ("field", "value", "variable"),
    [
        ("max_pdf_mb", 0, "PLAN_PARSER_MAX_PDF_MB"),
        ("max_pdf_pages", 0, "PLAN_PARSER_MAX_PDF_PAGES"),
    ],
)
def test_upload_limits_are_validated(field, value, variable, no_legacy_keys):
    settings = make_settings(llm_model="m", llm_api_key=SecretStr(SECRET), **{field: value})
    with pytest.raises(PlanParserConfigError, match=variable):
        resolve_llm_config(settings)


# --------------------------------------------------------------------------- registry


def test_registry_has_one_entry_per_provider():
    assert known_providers() == ("anthropic", "gemini")
    assert isinstance(get_json_llm("gemini", model="m", api_key=SECRET), GeminiJSONClient)
    assert isinstance(get_json_llm("anthropic", model="m", api_key=SECRET), AnthropicJSONClient)
    assert get_json_llm("Anthropic", model="m", api_key=SECRET).provider == "anthropic"


def test_registry_rejects_an_unknown_provider_or_missing_values():
    with pytest.raises(LLMNotConfiguredError, match="Unsupported LLM provider"):
        get_json_llm("openai", model="m", api_key=SECRET)
    with pytest.raises(LLMNotConfiguredError, match="No model"):
        get_json_llm("gemini", model="", api_key=SECRET)
    with pytest.raises(LLMNotConfiguredError, match="No API key"):
        get_json_llm("anthropic", model="m", api_key="")


def test_adding_a_provider_is_one_registry_entry(monkeypatch):
    class Stub:
        provider, model, last_usage = "stub", "stub-1", None

        def generate_json(self, **_kw):
            return {"ok": True}

    monkeypatch.setitem(json_client._ADAPTERS, "stub", lambda model, key, timeout: Stub())
    assert "stub" in known_providers()
    assert get_json_llm("stub", model="x", api_key="k").generate_json() == {"ok": True}


# ---------------------------------------------------------------------------- retries


def test_rate_limits_and_5xx_are_retried_with_bounded_backoff():
    waits: list[float] = []
    outcomes = [LLMRateLimitError("429"), LLMServerError("503"), "done"]

    def call():
        result = outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    assert with_retries(call, sleep=waits.append) == "done"
    assert waits == [2.0, 6.0]


def test_retries_stop_after_three_tries():
    calls = []

    def call():
        calls.append(1)
        raise LLMRateLimitError("429")

    with pytest.raises(LLMRateLimitError):
        with_retries(call, sleep=no_sleep)
    assert len(calls) == 3


def test_a_retry_after_hint_is_honoured_up_to_a_cap():
    waits: list[float] = []
    outcomes = [
        LLMRateLimitError("429", retry_after_s=4),
        LLMRateLimitError("429", retry_after_s=900),
        "ok",
    ]

    def call():
        result = outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    with_retries(call, sleep=waits.append)
    assert waits == [4, 30.0]


@pytest.mark.parametrize(
    "error",
    [
        LLMAuthenticationError("401"),
        LLMBillingError("402"),
        LLMRequestRejectedError("400"),
        LLMUnavailableError("timeout"),
        LLMInvalidJSONError("not json"),
    ],
)
def test_nothing_else_is_ever_retried(error):
    calls = []

    def call():
        calls.append(1)
        raise error

    with pytest.raises(type(error)):
        with_retries(call, sleep=no_sleep)
    assert len(calls) == 1


# -------------------------------------------------------------------- JSON extraction


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        'Here you go:\n{"a": 1}\nHope it helps.',
        '  {"a": 1}  ',
    ],
)
def test_extract_json_object(text):
    assert extract_json_object(text) == {"a": 1}


@pytest.mark.parametrize("text", ["", "no json here", "[1, 2, 3]", '{"a": '])
def test_extract_json_object_rejects_non_objects(text):
    with pytest.raises(LLMInvalidJSONError) as caught:
        extract_json_object(text)
    assert caught.value.raw_text == text.strip()


# ----------------------------------------------------------------------------- Gemini


def gemini(handler, model: str = "model-a") -> GeminiJSONClient:
    return GeminiJSONClient(
        model=model, api_key=SECRET, transport=httpx.MockTransport(handler), sleep=no_sleep
    )


def gemini_answer(text: str, finish: str = "STOP") -> httpx.Response:
    body = {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}],
        "usageMetadata": {
            "promptTokenCount": 900,
            "candidatesTokenCount": 120,
            "thoughtsTokenCount": 30,
        },
    }
    return httpx.Response(200, json=body)


def gemini_error(
    code: int, status: str = "", message: str = "", reason: str = ""
) -> httpx.Response:
    details = [{"reason": reason}] if reason else []
    return httpx.Response(
        code,
        json={"error": {"code": code, "status": status, "message": message, "details": details}},
    )


def test_gemini_sends_a_neutral_request_with_the_key_only_in_a_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return gemini_answer('{"levels": []}')

    client = gemini(handler)
    out = client.generate_json(
        system_prompt="SYSTEM",
        images=[LLMImage(b"png-bytes")],
        text="USER",
        json_schema={"type": "object"},
    )
    assert out == {"levels": []}
    assert "model-a:generateContent" in seen["url"]
    assert SECRET not in seen["url"] and seen["key"] == SECRET
    body = seen["body"]
    assert body["generationConfig"] == {"temperature": 0, "response_mime_type": "application/json"}
    assert body["system_instruction"]["parts"][0]["text"].startswith("SYSTEM")
    assert '{"type":"object"}' in body["system_instruction"]["parts"][0]["text"]
    parts = body["contents"][0]["parts"]
    assert parts[0]["inline_data"]["mime_type"] == "image/png" and parts[-1] == {"text": "USER"}
    assert client.last_usage == LLMUsage(input_tokens=900, output_tokens=150)
    assert (client.provider, client.model) == ("gemini", "model-a")


def test_gemini_never_falls_back_to_another_model():
    tried = []

    def handler(request: httpx.Request) -> httpx.Response:
        tried.append(str(request.url).split("/models/")[1].split(":")[0])
        return gemini_error(404, "NOT_FOUND", "models/retired is not found")

    with pytest.raises(LLMRequestRejectedError, match="does not know this model"):
        gemini(handler, model="retired").generate_json(system_prompt="s", images=[], text="t")
    assert tried == ["retired"]


@pytest.mark.parametrize(
    ("response", "error", "requests_made"),
    [
        (
            gemini_error(
                400,
                "INVALID_ARGUMENT",
                "API key not valid. Please pass a valid API key.",
                "API_KEY_INVALID",
            ),
            LLMAuthenticationError,
            1,
        ),
        (gemini_error(401, "UNAUTHENTICATED", "bad credentials"), LLMAuthenticationError, 1),
        (
            gemini_error(403, "PERMISSION_DENIED", "caller does not have permission"),
            LLMAuthenticationError,
            1,
        ),
        (
            gemini_error(403, "PERMISSION_DENIED", "Billing is disabled for this project"),
            LLMBillingError,
            1,
        ),
        (gemini_error(429, "RESOURCE_EXHAUSTED", "quota exceeded"), LLMRateLimitError, 3),
        (gemini_error(503, "UNAVAILABLE", "overloaded"), LLMServerError, 3),
        (gemini_error(400, "INVALID_ARGUMENT", "bad request"), LLMRequestRejectedError, 1),
    ],
)
def test_gemini_errors_are_typed_and_only_429_and_5xx_are_retried(response, error, requests_made):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(1)
        return response

    with pytest.raises(error) as caught:
        gemini(handler).generate_json(system_prompt="s", images=[], text="t")
    assert len(seen) == requests_made
    assert SECRET not in str(caught.value)


def test_gemini_recovers_when_a_retry_succeeds():
    responses = [gemini_error(503, "UNAVAILABLE"), gemini_answer('{"ok": true}')]
    client = gemini(lambda request: responses.pop(0))
    assert client.generate_json(system_prompt="s", images=[], text="t") == {"ok": True}
    assert client.model == "model-a"


def test_gemini_omits_temperature_when_the_model_rejects_it():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body["generationConfig"])
        if "temperature" in body["generationConfig"]:
            return gemini_error(
                400, "INVALID_ARGUMENT", "temperature is not supported for this model"
            )
        return gemini_answer('{"ok": true}')

    client = gemini(handler)
    assert client.generate_json(system_prompt="s", images=[], text="t") == {"ok": True}
    assert client.generate_json(system_prompt="s", images=[], text="t") == {"ok": True}
    assert ["temperature" in b for b in bodies] == [True, False, False]  # remembered


def test_gemini_network_failures_are_unavailable_and_not_retried():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(1)
        raise httpx.ConnectError("no route")

    with pytest.raises(LLMUnavailableError):
        gemini(handler).generate_json(system_prompt="s", images=[], text="t")
    assert len(seen) == 1


def test_gemini_reports_a_cut_off_reply_as_invalid_json():
    client = gemini(lambda request: gemini_answer('{"levels": [', "MAX_TOKENS"))
    with pytest.raises(LLMInvalidJSONError) as caught:
        client.generate_json(system_prompt="s", images=[], text="t")
    assert caught.value.raw_text == '{"levels": ['


def test_gemini_needs_a_model_and_a_key():
    with pytest.raises(LLMNotConfiguredError):
        GeminiJSONClient(model="", api_key=SECRET)
    with pytest.raises(LLMNotConfiguredError):
        GeminiJSONClient(model="m", api_key="")


# -------------------------------------------------------------------------- Anthropic


def sse(reply: str, stop_reason: str = "end_turn") -> httpx2.Response:
    """A streamed Messages API reply with one text block."""
    events = [
        (
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-test",
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 1,
                        "cache_creation_input_tokens": 5000,
                        "cache_read_input_tokens": 0,
                    },
                },
            },
        ),
        (
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
        ),
        (
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": reply},
            },
        ),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        (
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"output_tokens": 420},
            },
        ),
        ("message_stop", {"type": "message_stop"}),
    ]
    body = "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)
    return httpx2.Response(
        200, headers={"content-type": "text/event-stream"}, content=body.encode()
    )


def api_error(
    code: int,
    kind: str,
    message: str = "nope",
    details: dict | None = None,
    headers: dict | None = None,
) -> httpx2.Response:
    error = {"type": kind, "message": message}
    if details:
        error["details"] = details
    return httpx2.Response(code, json={"type": "error", "error": error}, headers=headers or {})


def claude(handler, model: str = "claude-test") -> AnthropicJSONClient:
    return AnthropicJSONClient(
        model=model,
        api_key=SECRET,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)),
        sleep=no_sleep,
    )


def test_anthropic_request_shape_matches_the_documented_api(monkeypatch):
    # keys in the environment must never be used: the adapter passes its key explicitly
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-must-not-be-used")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "env-token-must-not-be-used")
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return sse('{"levels": []}')

    client = claude(handler)
    out = client.generate_json(
        system_prompt="SYSTEM", images=[LLMImage(png())], text="USER", json_schema=WIRE_JSON_SCHEMA
    )
    assert out == {"levels": []}
    assert seen["url"].endswith("/v1/messages")

    credentials = " ".join(
        v for k, v in seen["headers"].items() if k.lower() in ("x-api-key", "authorization")
    )
    assert SECRET in credentials
    assert "env-key-must-not-be-used" not in json.dumps(seen["headers"])
    assert "env-token-must-not-be-used" not in json.dumps(seen["headers"])

    body = seen["body"]
    assert body["model"] == "claude-test" and body["stream"] is True
    assert body["system"] == "SYSTEM"  # the schema travels as output_config, not as prompt text
    for sampling in ("temperature", "top_p", "top_k"):
        assert sampling not in body  # the current API rejects all three
    assert "thinking" not in body  # left at the model's default

    content = body["messages"][0]["content"]
    assert [block["type"] for block in content] == ["image", "text"]  # images before text
    assert (
        content[0]["source"]["type"] == "base64"
        and content[0]["source"]["media_type"] == "image/png"
    )
    assert content[0]["cache_control"] == {"type": "ephemeral"}
    assert content[1] == {"type": "text", "text": "USER"}

    fmt = body["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"]["additionalProperties"] is False
    assert set(fmt["schema"]["required"]) == set(fmt["schema"]["properties"])
    assert "effort" not in body["output_config"]

    assert client.last_usage == LLMUsage(input_tokens=5100, output_tokens=420)
    assert (client.provider, client.model) == ("anthropic", "claude-test")


def test_anthropic_puts_a_schema_too_complex_for_the_grammar_in_the_prompt():
    lenient = LLMPlanDraft.model_json_schema()
    assert schema_fits_grammar(WIRE_JSON_SCHEMA) and not schema_fits_grammar(lenient)
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        return sse('{"levels": []}')

    claude(handler).generate_json(
        system_prompt="SYSTEM", images=[], text="USER", json_schema=lenient
    )
    assert "output_config" not in seen["body"]
    assert seen["body"]["system"].startswith("SYSTEM") and "JSON Schema" in seen["body"]["system"]


def test_the_wire_schema_stays_inside_the_documented_grammar_limits():
    schema = json.dumps(anthropic.transform_schema(WIRE_JSON_SCHEMA))
    assert schema.count('"anyOf"') <= 16
    for unsupported in ("minItems", "maxItems", "minimum", "maximum", "minLength", "maxLength"):
        assert f'"{unsupported}"' not in schema


@pytest.mark.parametrize(
    ("response", "error", "requests_made"),
    [
        (api_error(401, "authentication_error", "invalid x-api-key"), LLMAuthenticationError, 1),
        (api_error(403, "permission_error"), LLMAuthenticationError, 1),
        (api_error(402, "billing_error", "payment required"), LLMBillingError, 1),
        (
            api_error(
                400,
                "invalid_request_error",
                "Your credit balance is too low to access the Anthropic API.",
            ),
            LLMBillingError,
            1,
        ),
        (
            api_error(
                429, "rate_limit_error", details={"error_code": "enforced_spend_limit_reached"}
            ),
            LLMBillingError,
            1,
        ),
        (api_error(429, "rate_limit_error", headers={"retry-after": "1"}), LLMRateLimitError, 3),
        (api_error(500, "api_error"), LLMServerError, 3),
        (api_error(529, "overloaded_error"), LLMServerError, 3),
        (api_error(404, "not_found_error", "model: nope"), LLMRequestRejectedError, 1),
        (
            api_error(400, "invalid_request_error", "max_tokens too large"),
            LLMRequestRejectedError,
            1,
        ),
    ],
)
def test_anthropic_errors_are_typed_and_only_429_and_5xx_are_retried(
    response, error, requests_made
):
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(1)
        return response

    with pytest.raises(error) as caught:
        claude(handler).generate_json(system_prompt="s", images=[], text="t")
    assert len(seen) == requests_made  # the SDK's own retries are off; ours are bounded
    assert SECRET not in str(caught.value)


def test_anthropic_recovers_when_a_retry_succeeds():
    responses = [api_error(529, "overloaded_error"), sse('{"ok": true}')]
    assert claude(lambda request: responses.pop(0)).generate_json(
        system_prompt="s", images=[], text="t"
    ) == {"ok": True}


def test_anthropic_network_failure_is_unavailable_and_not_retried():
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(1)
        raise httpx2.ConnectError("no route")

    with pytest.raises(LLMUnavailableError):
        claude(handler).generate_json(system_prompt="s", images=[], text="t")
    assert len(seen) == 1


def test_anthropic_cut_off_and_declined_replies_are_typed():
    with pytest.raises(LLMInvalidJSONError) as cut_off:
        claude(lambda r: sse('{"levels": [', "max_tokens")).generate_json(
            system_prompt="s", images=[], text="t"
        )
    assert cut_off.value.raw_text == '{"levels": ['
    with pytest.raises(LLMRequestRejectedError, match="declined"):
        claude(lambda r: sse("I can't help with that.", "refusal")).generate_json(
            system_prompt="s", images=[], text="t"
        )
    with pytest.raises(LLMInvalidJSONError):
        claude(lambda r: sse("Sorry, no JSON today.")).generate_json(
            system_prompt="s", images=[], text="t"
        )


def test_anthropic_needs_a_model_and_a_key_and_ignores_the_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-must-not-be-used")
    with pytest.raises(LLMNotConfiguredError):
        AnthropicJSONClient(model="m", api_key="")  # an env key does not rescue a missing one
    with pytest.raises(LLMNotConfiguredError):
        AnthropicJSONClient(model="", api_key=SECRET)


def test_images_are_scaled_to_what_the_api_processes():
    media_type, data = prepare_image(LLMImage(png(5000, 3500)))
    scaled = Image.open(io.BytesIO(base64.b64decode(data)))
    assert media_type == "image/png"
    assert max(scaled.size) == MAX_IMAGE_LONG_EDGE_PX
    assert abs(scaled.width / scaled.height - 5000 / 3500) < 0.01

    small = png(800, 600)
    assert prepare_image(LLMImage(small)) == ("image/png", base64.b64encode(small).decode())
    assert prepare_image(LLMImage(png(5000, 3500))) == (media_type, data)  # deterministic


# ---------------------------------------------------------------------------- startup


def run_lifespan():
    import asyncio

    import app.main as main

    async def start() -> None:
        async with main.lifespan(main.app):
            pass

    asyncio.run(start())


def test_startup_stops_with_one_error_naming_the_variable(monkeypatch):
    import app.main as main

    def invalid():
        raise PlanParserConfigError("PLAN_PARSER_LLM_MODEL is not set.")

    started = []
    monkeypatch.setattr(parser_settings, "resolve_llm_config", invalid)
    monkeypatch.setattr(main, "ensure_storage_buckets", lambda: started.append("buckets"))
    with pytest.raises(PlanParserConfigError, match="PLAN_PARSER_LLM_MODEL is not set"):
        run_lifespan()
    assert started == []  # nothing else starts on a bad configuration


def test_startup_continues_with_a_valid_configuration(monkeypatch, caplog):
    import logging

    import app.main as main

    started = []
    config = parser_settings.LLMConfig(provider="anthropic", model="claude-x", api_key=SECRET)
    monkeypatch.setattr(parser_settings, "resolve_llm_config", lambda: config)
    monkeypatch.setattr(main, "ensure_storage_buckets", lambda: started.append("buckets"))
    with caplog.at_level(logging.INFO, logger="construtiva.app"):
        run_lifespan()
    assert started == ["buckets"]
    assert "provider=anthropic model=claude-x" in caplog.text
    assert SECRET not in caplog.text
