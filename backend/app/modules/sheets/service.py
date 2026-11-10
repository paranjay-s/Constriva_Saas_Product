"""
=============================================================================
Construtiva Bill of Materials (BOQ) & Sheet Service
=============================================================================
File: app/modules/sheets/service.py
Purpose:
  Provides business logic for project cost sheets and material mappings:
  - Manages the master catalogue for the 7 primary construction materials:
    1. Brick (Masonry)
    2. Steel/rebar rod (Structural Steel)
    3. Cement (Binder)
    4. Sand (fine aggregate)
    5. Ballast (coarse aggregate)
    6. Plaster (cement and gypsum)
    7. Tiles (floor and wall)
  - Initializes project sheets with standard line items, default quantities, and unit rates.
  - Performs inline item updates (quantity, rate, wastage) and automatically recalculates
    line amounts, subtotal, 5% contingency, and total estimated construction cost.
  - Manages architectural surface mappings linking 2D/3D model elements to materials.
=============================================================================
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from app.core.supabase import get_supabase_client
from app.modules.sheets.schemas import (
    SheetItemCreate,
    SheetItemUpdate,
    SurfaceMappingItem,
)

logger = logging.getLogger("construtiva.sheets.service")


# Master construction materials requested for Construtiva BOQ sheets
DEFAULT_CONSTRUCTION_MATERIALS: List[Dict[str, Any]] = [
    {
        "name": "Brick",
        "category": "Masonry",
        "description": "Standard red clay modular building bricks (Class 1) for exterior and partition walls",
        "unit": "pcs",
        "unit_price": 9.50,
        "waste_factor": 0.05,
        "surface_tag": "masonry_walls",
        "default_quantity": 8500.0,
    },
    {
        "name": "Steel/rebar rod",
        "category": "Structural Steel",
        "description": "High-yield strength deformed TMT steel reinforcement bars (Fe 550D) for RCC structure",
        "unit": "kg",
        "unit_price": 68.00,
        "waste_factor": 0.03,
        "surface_tag": "structural_reinforcement",
        "default_quantity": 2800.0,
    },
    {
        "name": "Cement",
        "category": "Binder",
        "description": "Ordinary Portland Cement (OPC 53 Grade / PPC) for RCC casting and bricklaying mortar",
        "unit": "bags",
        "unit_price": 380.00,
        "waste_factor": 0.02,
        "surface_tag": "concrete_and_mortar",
        "default_quantity": 320.0,
    },
    {
        "name": "Sand (fine aggregate)",
        "category": "Aggregate",
        "description": "Clean manufactured sand (M-Sand / River sand Zone II) for plastering and concrete mix",
        "unit": "cu.m",
        "unit_price": 1450.00,
        "waste_factor": 0.05,
        "surface_tag": "fine_aggregate",
        "default_quantity": 28.0,
    },
    {
        "name": "Ballast (coarse aggregate)",
        "category": "Aggregate",
        "description": "Crushed blue metal stone aggregate (10mm - 20mm graded) for foundation and slabs",
        "unit": "cu.m",
        "unit_price": 1650.00,
        "waste_factor": 0.05,
        "surface_tag": "coarse_aggregate",
        "default_quantity": 36.0,
    },
    {
        "name": "Plaster (cement and gypsum)",
        "category": "Wall Plaster & Finishes",
        "description": "Interior gypsum smooth finish coat and exterior water-resistant 1:4 cement-sand plaster",
        "unit": "sq.m",
        "unit_price": 185.00,
        "waste_factor": 0.03,
        "surface_tag": "wall_plaster",
        "default_quantity": 240.0,
    },
    {
        "name": "Tiles (floor and wall)",
        "category": "Flooring & Wall Tiling",
        "description": "Double-charged vitrified floor tiles (600x600mm) and ceramic glazed bathroom wall tiles",
        "unit": "sq.m",
        "unit_price": 620.00,
        "waste_factor": 0.05,
        "surface_tag": "floor_and_wall_tiles",
        "default_quantity": 95.0,
    },
]


class SheetService:
    """
    Service coordinating cost sheet calculation, line item persistence, and material catalogue syncing.
    """

    @classmethod
    def get_material_catalogue(cls) -> List[Dict[str, Any]]:
        """
        Returns the master construction materials catalogue configured for Construtiva.
        """
        return DEFAULT_CONSTRUCTION_MATERIALS

    @classmethod
    def sync_materials_catalogue_to_db(cls) -> None:
        """
        Ensures the 7 master materials exist in the Supabase 'materials' and 'material_prices' tables.
        Executes an upsert based on unique material name.
        """
        supabase = get_supabase_client()
        try:
            for mat in DEFAULT_CONSTRUCTION_MATERIALS:
                # Upsert into public.materials
                mat_res = supabase.table("materials").upsert({
                    "name": mat["name"],
                    "category": mat["category"],
                    "description": mat["description"],
                    "unit": mat["unit"],
                    "waste_factor": mat["waste_factor"],
                    "is_active": True,
                }, on_conflict="name").execute()

                if mat_res.data:
                    material_id = mat_res.data[0]["id"]
                    # Insert active price in material_prices
                    supabase.table("material_prices").insert({
                        "material_id": material_id,
                        "price": mat["unit_price"],
                        "currency": "INR",
                        "region": "default",
                    }).execute()

            logger.info("Master construction materials catalogue synchronized to Supabase.")
        except Exception as e:
            logger.warning(f"Could not synchronize materials catalogue to DB: {e}")

    @classmethod
    def recalculate_sheet_totals(cls, sheet_id: str) -> Dict[str, float]:
        """
        Computes subtotal, 5% contingency, and total_cost from existing sheet items
        and updates the 'sheets' table row.

        Args:
            sheet_id (str): UUID of the target sheet.

        Returns:
            Dict[str, float]: Updated subtotal, contingency, and total_cost.
        """
        supabase = get_supabase_client()

        # Query all items for this sheet
        items_res = supabase.table("sheet_items").select("amount").eq("sheet_id", sheet_id).execute()
        items = items_res.data or []

        subtotal = round(sum(float(item.get("amount") or 0.0) for item in items), 2)
        contingency_rate = 0.05  # Standard 5% site contingency
        contingency = round(subtotal * contingency_rate, 2)
        total_cost = round(subtotal + contingency, 2)

        # Update sheet summary
        supabase.table("sheets").update({
            "subtotal": subtotal,
            "contingency_rate": contingency_rate,
            "contingency": contingency,
            "total_cost": total_cost,
            "status": "ready",
            "stale": False,
        }).eq("id", sheet_id).execute()

        return {
            "subtotal": subtotal,
            "contingency_rate": contingency_rate,
            "contingency": contingency,
            "total_cost": total_cost,
        }

    @classmethod
    def get_or_create_sheet(cls, project_id: str) -> Dict[str, Any]:
        """
        Retrieves the active cost sheet for a project. If no sheet exists yet, creates one
        and pre-populates it with the 7 mapped standard construction materials.

        Args:
            project_id (str): UUID of the parent project.

        Returns:
            Dict[str, Any]: Complete sheet record including nested items list.
        """
        supabase = get_supabase_client()

        # Check if sheet already exists for project
        res = supabase.table("sheets").select("*").eq("project_id", project_id).execute()

        if res.data:
            sheet = res.data[0]
            sheet_id = sheet["id"]
        else:
            # Initialize a new sheet record for this project
            sheet_id = str(uuid.uuid4())
            new_sheet = {
                "id": sheet_id,
                "project_id": project_id,
                "name": "Standard Construction Cost Estimate",
                "status": "draft",
                "stale": False,
                "currency": "INR",
                "subtotal": 0.0,
                "contingency_rate": 0.05,
                "contingency": 0.0,
                "total_cost": 0.0,
            }
            create_res = supabase.table("sheets").insert(new_sheet).execute()
            sheet = create_res.data[0] if create_res.data else new_sheet

            # Pre-populate with the 7 mapped standard materials
            initial_items = []
            for mat in DEFAULT_CONSTRUCTION_MATERIALS:
                qty = float(mat["default_quantity"])
                waste = float(mat["waste_factor"])
                tot_qty = round(qty * (1.0 + waste), 2)
                rate = float(mat["unit_price"])
                amount = round(tot_qty * rate, 2)

                initial_items.append({
                    "id": str(uuid.uuid4()),
                    "sheet_id": sheet_id,
                    "name": mat["name"],
                    "category": mat["category"],
                    "unit": mat["unit"],
                    "quantity": qty,
                    "waste_factor": waste,
                    "total_quantity": tot_qty,
                    "unit_price": rate,
                    "amount": amount,
                    "surface_tag": mat["surface_tag"],
                    "is_custom": False,
                })

            if initial_items:
                supabase.table("sheet_items").insert(initial_items).execute()
                # Compute grand totals
                totals = cls.recalculate_sheet_totals(sheet_id)
                sheet.update(totals)

        # Retrieve all items ordered by created_at
        items_res = (
            supabase.table("sheet_items")
            .select("*")
            .eq("sheet_id", sheet_id)
            .order("created_at", desc=False)
            .execute()
        )
        sheet["items"] = items_res.data or []

        return sheet

    @classmethod
    def recalculate_from_plan(cls, project_id: str, plan_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes PlanJSON, calls map_plan_to_materials to compute quantities for the 7 materials,
        replaces existing default sheet items, and recalculates grand totals.
        """
        from app.modules.sheets.llm_mapper import map_plan_to_materials
        sheet = cls.get_or_create_sheet(project_id)
        sheet_id = sheet["id"]
        supabase = get_supabase_client()

        # Delete existing non-custom items
        supabase.table("sheet_items").delete().eq("sheet_id", sheet_id).eq("is_custom", False).execute()

        new_items = map_plan_to_materials(plan_json)
        db_items = []
        for item in new_items:
            item_row = dict(item)
            item_row["id"] = str(uuid.uuid4())
            item_row["sheet_id"] = sheet_id
            db_items.append(item_row)

        if db_items:
            supabase.table("sheet_items").insert(db_items).execute()

        cls.recalculate_sheet_totals(sheet_id)
        return cls.get_or_create_sheet(project_id)

    @classmethod
    def add_sheet_item(cls, project_id: str, item_data: SheetItemCreate) -> Dict[str, Any]:
        """
        Adds a new line item to the project sheet and updates grand totals.

        Args:
            project_id (str): UUID of the project.
            item_data (SheetItemCreate): Line item details (name, quantity, rate, unit, etc.).

        Returns:
            Dict[str, Any]: Newly created sheet item.
        """
        sheet = cls.get_or_create_sheet(project_id)
        sheet_id = sheet["id"]
        supabase = get_supabase_client()

        # Calculate total quantity including wastage and line total amount
        qty = float(item_data.quantity)
        waste = float(item_data.waste_factor)
        tot_qty = round(qty * (1.0 + waste), 3)
        rate = float(item_data.unit_price)
        amount = round(tot_qty * rate, 2)

        new_row = {
            "id": str(uuid.uuid4()),
            "sheet_id": sheet_id,
            "material_id": item_data.material_id,
            "name": item_data.name,
            "category": item_data.category,
            "unit": item_data.unit,
            "quantity": qty,
            "waste_factor": waste,
            "total_quantity": tot_qty,
            "unit_price": rate,
            "amount": amount,
            "surface_tag": item_data.surface_tag,
            "is_custom": item_data.is_custom or True,
        }

        res = supabase.table("sheet_items").insert(new_row).execute()
        if not res.data:
            raise ValueError("Failed to insert sheet item.")

        # Recalculate sheet totals
        cls.recalculate_sheet_totals(sheet_id)
        return res.data[0]

    @classmethod
    def update_sheet_item(cls, project_id: str, item_id: str, updates: SheetItemUpdate) -> Dict[str, Any]:
        """
        Performs an inline edit of a line item, recalculating line total and sheet grand totals.

        Args:
            project_id (str): UUID of project.
            item_id (str): UUID of line item.
            updates (SheetItemUpdate): Fields to update.

        Returns:
            Dict[str, Any]: Updated item row.
        """
        supabase = get_supabase_client()

        # Fetch existing item to combine with updates
        cur_res = supabase.table("sheet_items").select("*").eq("id", item_id).execute()
        if not cur_res.data:
            raise ValueError(f"Sheet item with ID {item_id} not found.")

        current = cur_res.data[0]
        sheet_id = current["sheet_id"]

        new_qty = float(updates.quantity) if updates.quantity is not None else float(current["quantity"])
        new_waste = float(updates.waste_factor) if updates.waste_factor is not None else float(current.get("waste_factor") or 0.0)
        new_rate = float(updates.unit_price) if updates.unit_price is not None else float(current["unit_price"])

        new_tot_qty = round(new_qty * (1.0 + new_waste), 3)
        new_amount = round(new_tot_qty * new_rate, 2)

        update_payload: Dict[str, Any] = {
            "quantity": new_qty,
            "waste_factor": new_waste,
            "total_quantity": new_tot_qty,
            "unit_price": new_rate,
            "amount": new_amount,
        }

        if updates.name is not None:
            update_payload["name"] = updates.name
        if updates.category is not None:
            update_payload["category"] = updates.category
        if updates.unit is not None:
            update_payload["unit"] = updates.unit
        if updates.surface_tag is not None:
            update_payload["surface_tag"] = updates.surface_tag

        res = supabase.table("sheet_items").update(update_payload).eq("id", item_id).execute()
        if not res.data:
            raise ValueError("Failed to update sheet item.")

        # Recalculate sheet grand totals
        cls.recalculate_sheet_totals(sheet_id)
        return res.data[0]

    @classmethod
    def delete_sheet_item(cls, project_id: str, item_id: str) -> bool:
        """
        Removes a line item from a sheet and updates overall totals.

        Args:
            project_id (str): UUID of project.
            item_id (str): UUID of line item to delete.

        Returns:
            bool: True upon successful deletion.
        """
        supabase = get_supabase_client()

        cur_res = supabase.table("sheet_items").select("sheet_id").eq("id", item_id).execute()
        if not cur_res.data:
            raise ValueError(f"Sheet item {item_id} not found.")

        sheet_id = cur_res.data[0]["sheet_id"]

        supabase.table("sheet_items").delete().eq("id", item_id).execute()
        cls.recalculate_sheet_totals(sheet_id)
        return True

    @classmethod
    def get_surface_mappings(cls, project_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all architectural surface-to-material mappings for a project.
        """
        supabase = get_supabase_client()
        res = (
            supabase.table("material_mappings")
            .select("id, project_id, surface_tag, material_id, materials(name, category, unit)")
            .eq("project_id", project_id)
            .execute()
        )
        return res.data or []

    @classmethod
    def update_surface_mappings(cls, project_id: str, mappings: List[SurfaceMappingItem]) -> List[Dict[str, Any]]:
        """
        Updates architectural surface assignments (e.g. 'masonry_walls' -> 'Brick').

        Args:
            project_id (str): UUID of project.
            mappings (List[SurfaceMappingItem]): List of surface_tag and material_id pairs.

        Returns:
            List[Dict[str, Any]]: Updated mapping records.
        """
        supabase = get_supabase_client()
        updated = []

        for m in mappings:
            if not m.material_id:
                continue

            row = {
                "project_id": project_id,
                "surface_tag": m.surface_tag,
                "material_id": m.material_id,
            }
            res = (
                supabase.table("material_mappings")
                .upsert(row, on_conflict="project_id, surface_tag")
                .execute()
            )
            if res.data:
                updated.extend(res.data)

        return updated
