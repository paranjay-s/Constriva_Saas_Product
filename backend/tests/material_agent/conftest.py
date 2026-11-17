"""Shared fixtures for the Material Finder tests (no network, no database)."""

import pytest

from app.modules.ai.llm.client import LLMError
from app.modules.ai.material_agent import settings as mat_settings
from app.modules.ai.material_agent.schemas import DetectedMaterial, ImageAnalysis

FT = 0.3048


def rect_m(x_ft: float, y_ft: float, w_ft: float, h_ft: float) -> list[list[float]]:
    x, y, w, h = x_ft * FT, y_ft * FT, w_ft * FT, h_ft * FT
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


def plan_json(
    rooms: list[tuple[str, float, float, float, float]],
    doors: list[tuple] = (),
    wall_height_m: float = 3.048,
) -> dict:
    """PlanJSON in metres. doors: (wall start ft, wall end ft, offset ft, width ft)."""
    walls, openings = [], []
    for i, (start, end, offset, width) in enumerate(doors):
        walls.append(
            {
                "id": f"w{i}",
                "start": [start[0] * FT, start[1] * FT],
                "end": [end[0] * FT, end[1] * FT],
                "thickness": 0.23,
            }
        )
        openings.append(
            {
                "id": f"d{i}",
                "wall_id": f"w{i}",
                "type": "door",
                "offset": offset * FT,
                "width": width * FT,
                "height": 7 * FT,
            }
        )
    return {
        "version": 1,
        "units": "m",
        "levels": [
            {
                "elevation": 0,
                "wall_height": wall_height_m,
                "walls": walls,
                "openings": openings,
                "rooms": [
                    {"id": f"r{i}", "name": n, "polygon": rect_m(x, y, w, h)}
                    for i, (n, x, y, w, h) in enumerate(rooms)
                ],
            }
        ],
    }


TV_WALL = ImageAnalysis(
    scene="living room",
    materials=[
        DetectedMaterial(
            name="fluted walnut veneer panel",
            category="wood_panel",
            surface="wall",
            location="TV wall, left and centre",
            coverage_ratio=0.7,
            pattern="vertical flutes",
            confidence="high",
            evidence="regular vertical grooves with wood grain",
        ),
        DetectedMaterial(
            name="Statuario marble",
            category="stone",
            surface="wall",
            location="TV wall, right panel",
            coverage_ratio=0.3,
            finish="polished",
            confidence="medium",
            look_alikes=["marble-look porcelain slab"],
        ),
        DetectedMaterial(
            name="engineered oak flooring",
            category="wood_floor",
            surface="floor",
            confidence="medium",
        ),
    ],
)


class FakeVision:
    """Vision LLM double: returns a fixed analysis, counts calls."""

    def __init__(self, analysis: ImageAnalysis = TV_WALL, fail: bool = False) -> None:
        self.analysis = analysis
        self.fail = fail
        self.calls = 0
        self.last_images = None

    def structured(self, *, system, user, schema, task, images=None):
        self.calls += 1
        self.last_images = images
        if self.fail:
            raise LLMError("timeout")
        assert schema is ImageAnalysis
        return self.analysis


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("MATERIAL_CACHE_DIR", str(tmp_path / "cache"))
    mat_settings.get_settings.cache_clear()
    yield tmp_path / "cache"
    mat_settings.get_settings.cache_clear()


def jpeg_bytes(colour=(120, 90, 60), size=(64, 48)) -> bytes:
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, format="JPEG")
    return out.getvalue()
