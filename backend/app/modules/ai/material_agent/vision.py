"""Step A + B: prepare the photos and ask the vision model what materials it sees.

Images are downscaled (long side 2000 px, JPEG) before they are sent or stored. The
result is cached on disk by (image hashes, focus, prompt version, model), so the same
photo with the same focus never costs a second model call; follow-up questions never
call the vision model at all.
"""

import hashlib
import io
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.modules.ai.llm.client import LLMError, VisionLLMClient
from app.modules.ai.material_agent.schemas import ImageAnalysis
from app.modules.ai.material_agent.settings import get_settings

logger = logging.getLogger("construtiva.ai.material.vision")

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "material"
PROMPT_VERSION = "v2"
MAX_SIDE_PX = 1600  # enough detail for finishes; smaller = faster upload and model call
ALLOWED_MIME = ("image/jpeg", "image/png", "image/webp")


class ImageError(ValueError):
    """The upload is not a usable image (message is safe to show)."""


@dataclass
class PreparedImage:
    data: bytes  # JPEG, downscaled
    mime: str
    sha256: str
    width: int
    height: int


def prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


def prepare_image(raw: bytes, mime: str | None = None) -> PreparedImage:
    s = get_settings()
    if not raw:
        raise ImageError("The image is empty.")
    if len(raw) > s.max_image_mb * 1024 * 1024:
        raise ImageError(f"Each image must be under {s.max_image_mb:g} MB.")
    if mime and mime not in ALLOWED_MIME:
        raise ImageError("Use a JPG, PNG or WEBP photo.")
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise ImageError("That file is not a readable image.") from e
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)
    data = out.getvalue()
    return PreparedImage(
        data=data,
        mime="image/jpeg",
        sha256=hashlib.sha256(data).hexdigest(),
        width=img.width,
        height=img.height,
    )


def cache_key(hashes: list[str], focus: str, model: str) -> str:
    text = json.dumps([sorted(hashes), focus.strip().lower(), PROMPT_VERSION, model])
    return hashlib.sha256(text.encode()).hexdigest()[:40]


def _cache_file(key: str) -> Path:
    return get_settings().cache_path / f"{key}.json"


def _read_cache(key: str) -> ImageAnalysis | None:
    f = _cache_file(key)
    try:
        return ImageAnalysis.model_validate_json(f.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        logger.warning("material vision cache entry %s unreadable; ignoring it", key)
        return None


def _write_cache(key: str, analysis: ImageAnalysis) -> None:
    f = _cache_file(key)
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(analysis.model_dump_json(), encoding="utf-8")
    except OSError as e:
        logger.warning("could not write material vision cache: %s", e)


def save_image(img: PreparedImage) -> None:
    """Keep the downscaled image locally so a new focus can be analysed later."""
    f = get_settings().cache_path / "images" / f"{img.sha256}.jpg"
    try:
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(img.data)
    except OSError as e:
        logger.warning("could not keep material image: %s", e)


def load_image(sha256: str) -> bytes | None:
    try:
        return (get_settings().cache_path / "images" / f"{sha256}.jpg").read_bytes()
    except OSError:
        return None


def focus_text(areas: list[str], text: str) -> str:
    parts = [a for a in areas if a] + ([text.strip()] if text.strip() else [])
    return ", ".join(parts)


def analyse(
    llm: VisionLLMClient,
    images: list[PreparedImage],
    focus: str,
    model_name: str,
) -> ImageAnalysis:
    """One structured vision call for all images of the request (cached)."""
    key = cache_key([i.sha256 for i in images], focus, model_name)
    cached = _read_cache(key)
    if cached is not None:
        logger.info("material vision cache hit %s", key)
        return cached
    user = (
        f"The person's request: {focus}"
        if focus
        else "The person's request: identify the main finishes in the photo."
    ) + f"\nNumber of photos: {len(images)} (same space)."
    try:
        result = llm.structured(
            system=prompt("material_vision"),
            user=user,
            schema=ImageAnalysis,
            task="material_vision",
            images=[(i.data, i.mime) for i in images],
        )
    except LLMError:
        raise
    _write_cache(key, result)
    return result
