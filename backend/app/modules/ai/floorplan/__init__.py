"""2D floor plan generator: brief -> room program -> layout -> validated plan JSON -> renders.

The plan JSON (`schemas.plan.FloorPlan`, all geometry in integer cm) is the single
source of truth. The LLM never produces coordinates; code places rooms.
"""
