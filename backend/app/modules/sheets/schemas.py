"""
=============================================================================
Construtiva Bill of Materials (BOQ) & Cost Estimation Schemas
=============================================================================
File: app/modules/sheets/schemas.py
Purpose:
  Defines Pydantic request and response schemas for construction cost estimation sheets:
  - Material line item CRUD operations (name, category, unit, quantity, wastage, rate, amount).
  - Cost sheet summary, contingency calculation, and stale flag status.
  - Surface-to-material mapping schemas (Brick, Steel, Cement, Sand, Ballast, Plaster, Tiles).
=============================================================================
"""

import uuid
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, model_validator


class SheetItemBase(BaseModel):
    """
    Base attributes for a construction sheet line item.
    """
    name: str = Field(..., min_length=1, description="Material or component name (e.g. 'Steel/rebar rod')")
    category: str = Field(..., description="Classification category (e.g. 'Structural Steel', 'Masonry')")
    unit: str = Field(..., description="Measurement unit (e.g. 'kg', 'pcs', 'bags', 'cu.m', 'sq.m')")
    quantity: float = Field(..., ge=0, description="Base measured quantity before wastage")
    waste_factor: float = Field(0.0, ge=0, le=1.0, description="Wastage allowance fraction (e.g. 0.05 for 5%)")
    unit_price: Optional[float] = Field(0.0, ge=0, description="Unit rate/cost in currency (INR)")
    area: Optional[float] = Field(None, description="Measured architectural surface or footprint area in m²")
    area_unit: Optional[str] = Field("m2", description="Area unit of measure (default 'm2')")
    secondary_quantity: Optional[float] = Field(None, description="Secondary metric quantity (e.g. rods, tons, m3)")
    secondary_unit: Optional[str] = Field(None, description="Secondary unit of measure")
    surface_tag: Optional[str] = Field(None, description="Linked architectural tag (e.g. 'masonry_walls', 'floor_tiles')")
    is_custom: bool = Field(False, description="Flag indicating user-added custom item")


class SheetItemCreate(SheetItemBase):
    """
    Payload for manually adding a line item to a project cost sheet.
    """
    material_id: Optional[str] = Field(None, description="Optional UUID reference to master material catalogue")


class SheetItemUpdate(BaseModel):
    """
    Payload for inline editing of an existing sheet item.
    Any non-None field will be updated, triggering automatic recalculation of line amount and sheet totals.
    """
    name: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = Field(None, ge=0)
    waste_factor: Optional[float] = Field(None, ge=0, le=1.0)
    unit_price: Optional[float] = Field(None, ge=0)
    surface_tag: Optional[str] = None
    area: Optional[float] = None
    secondary_quantity: Optional[float] = None
    secondary_unit: Optional[str] = None


class SheetItemResponse(SheetItemBase):
    """
    Representation of a saved sheet item returned to the client.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sheet_id: str = "default_sheet"
    material_id: Optional[str] = None
    total_quantity: float = Field(default=0.0, description="Final quantity including wastage = quantity * (1 + waste_factor)")
    amount: Optional[float] = Field(default=0.0, description="Line total amount = total_quantity * unit_price")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_item_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("id"):
                data["id"] = str(uuid.uuid4())
            if not data.get("sheet_id"):
                data["sheet_id"] = "default_sheet"
            qty = float(data.get("quantity") or 0.0)
            waste = float(data.get("waste_factor") or 0.0)
            rate = float(data.get("unit_price") or 0.0)
            if data.get("total_quantity") is None:
                data["total_quantity"] = round(qty * (1.0 + waste), 2)
            if data.get("amount") is None:
                tot_qty = float(data.get("total_quantity") or 0.0)
                data["amount"] = round(tot_qty * rate, 2)
        return data


class SheetResponse(BaseModel):
    """
    Full cost estimation sheet response including metadata, items table, and calculated totals.
    """
    id: str
    project_id: str
    plan_id: Optional[str] = None
    name: str = "Standard Construction Cost Estimate"
    status: str = "ready"
    stale: bool = Field(default=False, description="True if underlying 2D/3D PlanJSON geometry changed and sheet needs recalculation")
    currency: str = "INR"
    subtotal: float = 0.0
    contingency_rate: float = 0.05
    contingency: float = 0.0
    contingency_percent: Optional[float] = 5.0
    contingency_amount: Optional[float] = 0.0
    total_cost: float = 0.0
    items: List[SheetItemResponse] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_contingency_and_stale(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data.setdefault("stale", False)
            data.setdefault("status", "ready")
            subtotal = float(data.get("subtotal") or 0.0)

            # Resolve contingency amount and rate
            amt = data.get("contingency")
            if amt is None:
                amt = data.get("contingency_amount")
            if amt is None:
                amt = round(subtotal * 0.05, 2)
            data["contingency"] = float(amt)
            data["contingency_amount"] = float(amt)

            rate = data.get("contingency_rate")
            if rate is None:
                pct = data.get("contingency_percent")
                if pct is not None:
                    rate = float(pct) / 100.0 if float(pct) > 1.0 else float(pct)
                else:
                    rate = 0.05
            data["contingency_rate"] = float(rate)
            data["contingency_percent"] = float(data.get("contingency_percent") or (float(rate) * 100.0))

            if not data.get("total_cost"):
                data["total_cost"] = round(subtotal + float(data["contingency"]), 2)
        return data


class MaterialCatalogueItem(BaseModel):
    """
    Standard material item entry in the master catalogue.
    """
    id: Optional[str] = None
    name: str
    category: str
    description: str
    unit: str
    unit_price: float
    waste_factor: float
    surface_tag: str
    default_quantity: float


class MaterialCatalogueResponse(BaseModel):
    """
    Catalogue response returning the 7 standard construction materials.
    """
    materials: List[MaterialCatalogueItem]
    count: int


class SurfaceMappingItem(BaseModel):
    """
    Mapping pair associating an architectural surface tag with a specific material.
    """
    surface_tag: str = Field(..., description="Architectural surface identifier (e.g. 'masonry_walls')")
    material_id: Optional[str] = Field(None, description="UUID of material in catalogue")
    material_name: Optional[str] = Field(None, description="Human readable material name (e.g. 'Brick')")


class UpdateSurfaceMappingsRequest(BaseModel):
    """
    Payload for updating project surface material assignments.
    """
    mappings: List[SurfaceMappingItem]
