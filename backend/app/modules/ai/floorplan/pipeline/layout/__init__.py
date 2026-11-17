"""Room placement: templates first, then the CP-SAT solver. Code places rooms, not the LLM."""

from app.modules.ai.floorplan.pipeline.layout.engine import LayoutResult, assemble, generate_layout

__all__ = ["LayoutResult", "assemble", "generate_layout"]
