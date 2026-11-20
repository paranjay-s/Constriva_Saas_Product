"""The building model inside every exported PDF, signed, so our readers use it exactly.

    pdf = embed_model(pdf, building)          # attachments building.json + building.sig
    found = read_embedded_model(pdf)          # EmbeddedModel(building, signed, plan_id)

The signature is HMAC-SHA256 over the exact bytes of building.json with a server key:
FLOORPLAN_MODEL_SIGNING_KEY, or, when that is empty, a key derived from the already
configured PLAN3D_EMBED_SECRET or SUPABASE_JWT_SECRET. Without any key the model is still
attached (CAD users can read it) but unsigned, and our readers ignore it and read the
drawing instead. A valid signature means the model came from this server unchanged; it
says nothing about who may see the plan (the PDF's holder already has the drawing).
"""

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass

import pymupdf
from pydantic import ValidationError

from app.modules.ai.floorplan.model.building import Building

logger = logging.getLogger("construtiva.ai.floorplan.embed")
MODEL_FILE = "building.json"
SIG_FILE = "building.sig"
MAX_MODEL_BYTES = 5 * 1024 * 1024
_CONTEXT = b"constriva-building-model/1"


@dataclass(frozen=True)
class EmbeddedModel:
    building: Building
    signed: bool
    plan_id: str


def signing_key() -> bytes | None:
    """The configured key, or one derived from a configured server secret; None if the
    server has no secret at all (then nothing is signed)."""
    from app.modules.ai.floorplan.settings import get_settings

    own = get_settings().model_signing_key.get_secret_value()
    if own:
        return own.encode("utf-8")
    base = ""
    try:
        from app.modules.plan3d.settings import get_settings as plan3d_settings

        base = plan3d_settings().embed_secret.get_secret_value()
    except Exception:  # the 3D module's settings are optional here
        base = ""
    if not base:
        from app.core.config import settings as app_settings

        base = app_settings.supabase_jwt_secret or ""
    if not base:
        return None
    return hmac.new(base.encode("utf-8"), _CONTEXT, hashlib.sha256).digest()


def _sign(data: bytes, key: bytes) -> str:
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def embed_model(pdf: bytes, building: Building, key: bytes | None = None) -> bytes:
    data = json.dumps(building.to_json_dict(), separators=(",", ":")).encode("utf-8")
    key = key if key is not None else signing_key()
    sig = {
        "alg": "HMAC-SHA256" if key else "none",
        "sig": _sign(data, key) if key else "",
        "plan_id": building.meta.plan_id,
        "version": building.meta.version,
        "schema": building.schema_,
    }
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        doc.embfile_add(MODEL_FILE, data, filename=MODEL_FILE, desc="Constriva building model")
        doc.embfile_add(
            SIG_FILE,
            json.dumps(sig).encode("utf-8"),
            filename=SIG_FILE,
            desc="Signature of building.json",
        )
        return doc.tobytes(garbage=3, deflate=True)


def read_embedded_model(pdf: bytes, key: bytes | None = None) -> EmbeddedModel | None:
    """The attached model when it is there and parses; `signed` only when the signature
    verifies with this server's key. Never raises: the bytes come from a user."""
    try:
        with pymupdf.open(stream=pdf, filetype="pdf") as doc:
            names = set(doc.embfile_names())
            if MODEL_FILE not in names or SIG_FILE not in names:
                return None
            data = doc.embfile_get(MODEL_FILE)
            sig = json.loads(doc.embfile_get(SIG_FILE).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(data, bytes | bytearray) or len(data) > MAX_MODEL_BYTES:
        return None
    try:
        building = Building.model_validate_json(data)
    except (ValidationError, ValueError):
        return None
    key = key if key is not None else signing_key()
    given = str(sig.get("sig") or "") if isinstance(sig, dict) else ""
    signed = bool(
        key
        and given
        and sig.get("alg") == "HMAC-SHA256"
        and hmac.compare_digest(given, _sign(bytes(data), key))
    )
    return EmbeddedModel(building, signed, building.meta.plan_id)


def signed_model(pdf: bytes) -> Building | None:
    """The building model of a PDF this server exported and signed, else None."""
    found = read_embedded_model(pdf)
    return found.building if found and found.signed else None
