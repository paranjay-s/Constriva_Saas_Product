"""
=============================================================================
Construtiva LLM & Gemini Client Service
=============================================================================
File: app/modules/ai/llm_client.py
Purpose:
  Provides centralized access to the Gemini 2.0 API for multimodal architectural vision:
  - Supports calling the Gemini API via direct HTTPS using `httpx` (zero external SDK setup needed)
    or via the official `google-genai` SDK.
  - Automatically loads GEMINI_API_KEY from environment or settings.
  - Sends image bytes (PNG/JPG) alongside engineering prompts and enforces structured JSON returns.
=============================================================================
"""

import sys
from pathlib import Path
_backend_root = str(Path(__file__).resolve().parents[3])
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

import os
import json
import base64
import logging
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger("construtiva.ai.client")


def get_gemini_api_key() -> str:
    """
    Retrieves the Gemini API key from environment variables or application settings.
    Checks: GEMINI_API_KEY, GOOGLE_API_KEY, settings.gemini_api_key, or settings.llm_api_key.
    """
    key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or settings.gemini_api_key
        or settings.llm_api_key
    )
    if not key:
        logger.warning("GEMINI_API_KEY is not set. Set it in .env to enable live LLM calls.")
    return key or ""


def call_gemini_vision(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/png",
    model: str = "gemini-3.5-flash-lite",
) -> Dict[str, Any]:
    """
    Sends an image payload and prompt to the Gemini Multimodal Vision API,
    requesting a structured JSON response.

    Args:
        prompt (str): Detailed architectural instruction or schema requirement.
        image_bytes (bytes): Binary bytes of the blueprint PNG or site photo.
        mime_type (str): MIME type of the image ('image/png' or 'image/jpeg').
        model (str): Gemini model identifier (default: 'gemini-2.0-flash').

    Returns:
        Dict[str, Any]: Parsed JSON dictionary returned by Gemini.

    Raises:
        ValueError: If API key is missing or response is not valid JSON.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing. Please set GEMINI_API_KEY in your .env file.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    # Encode image bytes to base64 string
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64_image
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1,  # Low temperature for deterministic geometric parsing
        }
    }

    headers = {"Content-Type": "application/json"}

    # Ordered candidate models in case of high load (503) or unavailability (404)
    candidate_models = [model]
    for m in [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3-flash-preview",
        "gemini-3.1-pro-preview",
        "gemini-3.7-flash",
    ]:
        if m not in candidate_models:
            candidate_models.append(m)

    import time
    last_error = None

    for target_model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
        logger.info(f"Invoking Gemini model: {target_model}...")

        for attempt in range(2):
            try:
                with httpx.Client(timeout=120.0) as client:
                    response = client.post(url, json=payload, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        return json.loads(raw_text)
                    elif response.status_code == 503:
                        logger.warning(f"Model {target_model} returned 503 (high demand). Backing off 2s...")
                        time.sleep(2.0)
                        continue
                    else:
                        logger.warning(f"Model {target_model} returned HTTP {response.status_code}: {response.text[:120]}")
                        last_error = response.text
                        break
            except Exception as e:
                logger.warning(f"Error querying {target_model} (attempt {attempt+1}): {e}")
                last_error = str(e)
                time.sleep(1.0)

    raise ValueError(f"All Gemini vision models failed. Last error: {last_error}")


def call_gemini_text(
    prompt: str,
    system_instruction: Optional[str] = None,
    json_mode: bool = True,
    model: str = "gemini-2.5-flash",
) -> Dict[str, Any]:
    """
    Calls the Gemini Generative Language API with text prompts and system instructions,
    returning structured JSON or plain text.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing. Please set GEMINI_API_KEY in your .env file.")

    candidate_models = [
        model,
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-3.5-flash-lite",
        "gemini-2.5-pro",
    ]

    parts = [{"text": prompt}]
    payload: Dict[str, Any] = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
        }
    }

    if json_mode:
        payload["generationConfig"]["response_mime_type"] = "application/json"

    if system_instruction:
        payload["system_instruction"] = {
            "parts": [{"text": system_instruction}]
        }

    headers = {"Content-Type": "application/json"}
    last_error = None

    for target_model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    if json_mode:
                        return json.loads(raw_text)
                    return {"text": raw_text}
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:120]}"
        except Exception as e:
            last_error = str(e)
            continue

    raise ValueError(f"Gemini text models failed. Last error: {last_error}")


# =============================================================================
# STANDALONE TEST SCRIPT:
# Run: python app/modules/ai/llm_client.py
# =============================================================================
if __name__ == "__main__":
    print("-----------------------------------------------------------------")
    print("Testing Construtiva Gemini LLM Client...")
    print("-----------------------------------------------------------------")
    key = get_gemini_api_key()
    print(f"Detected GEMINI_API_KEY: {'*' * (len(key)-4) + key[-4:] if len(key) >= 4 else 'NOT SET'}")
    if not key:
        print("Please add 'GEMINI_API_KEY=your_key_here' to your .env file.")
    else:
        print("Key configured! Client is ready to send multimodal vision requests.")
    print("-----------------------------------------------------------------")
