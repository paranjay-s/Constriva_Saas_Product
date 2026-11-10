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

from typing import Optional, List
from pydantic import BaseModel, Field


class SheetItemBase(BaseModel):
    """
    Base attributes for a construction sheet line item.
    """
    name: str = Field(..., min_length=1, description="Material or component name (e.g. 'Steel/rebar rod')")
    category: str = Field(..., description="Classification category (e.g. 'Structural Steel', 'Masonry')")
    unit: str = Field(..., description="Measurement unit (e.g. 'kg', 'pcs', 'bags', 'cu.m', 'sq.m')")
    quantity: float = Field(..., ge=0, description="Base measured quantity before wastage")
    waste_factor: float = Field(0.0, ge=0, le=1.0, description="Wastage allowance fraction (e.g. 0.05 for 5%)")
    unit_price: float = Field(..., ge=0, description="Unit rate/cost in currency (INR)")
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


class SheetItemResponse(SheetItemBase):
    """
    Representation of a saved sheet item returned to the client.
    """
    id: str
    sheet_id: str
    material_id: Optional[str] = None
    total_quantity: float = Field(..., description="Final quantity including wastage = quantity * (1 + waste_factor)")
    amount: float = Field(..., description="Line total amount = total_quantity * unit_price")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SheetResponse(BaseModel):
    """
    Full cost estimation sheet response including metadata, items table, and calculated totals.
    """
    id: str
    project_id: str
    name: str
    status: str
    stale: bool = Field(..., description="True if underlying 2D/3D PlanJSON geometry changed and sheet needs recalculation")
    currency: str = "INR"
    subtotal: float
    contingency_rate: float
    contingency: float
    total_cost: float
    items: List[SheetItemResponse] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


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
