"""Step C: match what the vision model named to a catalog entry (aliases, no LLM).

The longest alias found in "name + pattern + category" wins, preferring entries that are
used on the detected surface. Nothing found -> kept as is with catalog_id None ("other");
the material is still shown, just without a buy unit.
"""

import re

from app.modules.ai.material_agent.data_files import catalog
from app.modules.ai.material_agent.schemas import DetectedMaterial, Material


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()


def match_catalog(name: str, surface: str = "", extra: str = "") -> dict | None:
    text = f" {_norm(name)} {_norm(extra)} "
    best: tuple[float, dict] | None = None
    for entry in catalog():
        for alias in entry["aliases"] + [entry["name"]]:
            a = _norm(alias)
            if not a or f" {a} " not in text:
                continue
            score = len(a) + (5 if surface and surface in entry["surfaces"] else 0)
            if _norm(name).startswith(a) or a in _norm(name):
                score += 3  # found in the name itself, not only in the pattern text
            if best is None or score > best[0]:
                best = (score, entry)
    return best[1] if best else None


def normalise(detected: list[DetectedMaterial]) -> list[Material]:
    out: list[Material] = []
    for i, d in enumerate(detected, start=1):
        entry = match_catalog(d.name, d.surface, f"{d.pattern} {d.category}")
        out.append(
            Material(
                id=f"m{i}",
                catalog_id=entry["id"] if entry else None,
                name=d.name.strip(),
                display_name=d.name.strip()[:1].upper() + d.name.strip()[1:],
                category=entry["category"] if entry else (d.category or "other"),
                surface=d.surface,
                location=d.location,
                coverage_ratio=d.coverage_ratio,
                finish=d.finish,
                pattern=d.pattern,
                colour=d.colour,
                size_hint=d.size_hint,
                confidence=d.confidence,
                look_alikes=d.look_alikes,
                evidence=d.evidence,
            )
        )
    return out


def find_material(materials: list[Material], query: str) -> list[Material]:
    """Materials of this session that match what the person typed ('marble', 'the veneer')."""
    q = _norm(query)
    if not q:
        return []
    words = [w for w in q.split() if len(w) > 2 and w not in {"the", "that", "this", "for", "and"}]
    direct = [m for m in materials if q in _norm(m.name) or _norm(m.name) in q]
    if direct:
        return direct
    entry = match_catalog(query)
    if entry:
        same = [m for m in materials if m.catalog_id == entry["id"]]
        if same:
            return same
    # words of the request in the material's own name ("the veneer"); a different
    # material of the same family ("granite" vs "marble") does not match
    return [m for m in materials if any(w in _norm(f"{m.name} {m.category}") for w in words)]
