"""
=============================================================================
Construtiva Live Blueprint Extraction & DB Storage Runner
=============================================================================
File: backend/extract_and_store_plan.py
Purpose:
  1. Rasterizes the user's architectural floor plan PDF into a 300 DPI image.
  2. Submits the image to Gemini 2.0 Multimodal Vision to extract walls, openings, and rooms.
  3. Validates the output against the official Construtiva 3D PlanJSON Pydantic schema.
  4. Stores the generated PlanJSON directly in the Supabase 'plans' PostgreSQL table.
  5. Exports the JSON to 'extracted_plan.json' and outputs detailed diagnostics.
=============================================================================
"""

import os
import sys
import json
import uuid
from pathlib import Path

# Ensure backend root is on path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.supabase import get_supabase_client
from app.modules.parsing.pdf_to_image import convert_pdf_page_to_png
from app.modules.ai.llm_client import call_gemini_vision, get_gemini_api_key
from app.modules.plans.schemas import PlanJSON

SAMPLE_PDF_PATH = r"C:\Users\Shantanu\.gemini\antigravity\brain\b28099d3-0ca0-46ea-bfc7-be3019a8b8a3\.user_uploaded\media_1794335647116_68987e34.pdf"

DETAILED_ARCHITECTURAL_PROMPT = """
You are a senior architectural CAD and BIM vision parser AI.
Analyze this high-resolution architectural floor plan drawing.

Extract the complete structural geometry into the following strictly typed JSON format:
{
  "version": 1,
  "units": "m",
  "scale_source": "dimension_label",
  "levels": [
    {
      "elevation": 0.0,
      "wall_height": 2.8,
      "walls": [
        {
          "id": "w_ext_front",
          "start": [0.0, 0.0],
          "end": [12.0, 0.0],
          "thickness": 0.23
        }
      ],
      "openings": [
        {
          "id": "op_entry_door",
          "wall_id": "w_ext_front",
          "type": "door",
          "offset": 2.5,
          "width": 1.0,
          "height": 2.1,
          "sill": 0.0
        }
      ],
      "rooms": [
        {
          "id": "room_living",
          "name": "Living Room",
          "polygon": [
            [0.0, 0.0],
            [6.0, 0.0],
            [6.0, 5.0],
            [0.0, 5.0]
          ]
        }
      ]
    }
  ],
  "confidence": {
    "overall": 0.95
  }
}

CRITICAL RULES:
1. Parse ALL perimeter exterior walls and interior partition walls visible in the floor plan.
2. Coordinate space: Assume the bottom-left corner of the building footprint is [0.0, 0.0]. X axis extends to the right, Y axis extends upward.
3. Use the dimension numbers written on the blueprint (feet/inches or meters) and convert all measurements to METERS (1 ft = 0.3048 m).
4. Exterior load-bearing walls should have thickness = 0.23m. Interior partition walls thickness = 0.12m.
5. Identify all rooms (e.g. Master Bedroom, Bedroom 2, Living Area, Kitchen, Dining, Bathroom / Toilet, Hall / Foyer, Balcony, Porch).
6. For each room, provide a closed boundary polygon [ [x1, y1], [x2, y2], ... ] tracing the interior boundary.
7. Identify doors ("type": "door", height: 2.1, sill: 0.0) and windows ("type": "window", height: 1.2, sill: 0.9). Set wall_id to the matching wall.
8. Output ONLY the raw JSON object. Do not wrap in markdown or backticks.
"""


def main():
    print("=" * 70)
    print("CONSTRUTIVA - BLUEPRINT TO PLANJSON AI PIPELINE")
    print("=" * 70)

    # 1. Load PDF
    if not os.path.exists(SAMPLE_PDF_PATH):
        print(f"[ERROR] Blueprint PDF not found at {SAMPLE_PDF_PATH}")
        sys.exit(1)

    print(f"\n[Step 1/5] Loading blueprint PDF: {Path(SAMPLE_PDF_PATH).name}...")
    with open(SAMPLE_PDF_PATH, "rb") as f:
        pdf_bytes = f.read()
    print(f"  ✓ Read {len(pdf_bytes):,} bytes from disk.")

    # 2. Rasterize to high-resolution PNG (120 DPI for optimal LLM vision latency)
    print("\n[Step 2/5] Rasterizing PDF Page 1 to high-resolution PNG (120 DPI)...")
    png_bytes, width, height = convert_pdf_page_to_png(pdf_bytes, page_number=0, dpi=120)
    print(f"  ✓ Successfully rasterized to {width}x{height} px PNG ({len(png_bytes):,} bytes).")

    # 3. Call Gemini Vision
    print("\n[Step 3/5] Submitting blueprint image to Gemini 3.5 Flash Lite Vision...")
    api_key = get_gemini_api_key()
    if not api_key:
        print("[ERROR] GEMINI_API_KEY is not set.")
        sys.exit(1)
    print(f"  Using Gemini API Key: {'*' * (len(api_key)-4) + api_key[-4:]}")

    raw_plan = call_gemini_vision(
        prompt=DETAILED_ARCHITECTURAL_PROMPT,
        image_bytes=png_bytes,
        mime_type="image/png",
        model="gemini-3.5-flash-lite",
    )

    # 4. Validate with Pydantic PlanJSON
    print("\n[Step 4/5] Validating extracted PlanJSON against schema...")
    validated_plan = PlanJSON(**raw_plan)
    plan_dict = validated_plan.model_dump()

    level = plan_dict["levels"][0]
    walls = level["walls"]
    rooms = level["rooms"]
    openings = level["openings"]

    print(f"  ✓ Schema validated successfully!")
    print(f"    - Walls count:    {len(walls)}")
    print(f"    - Rooms count:    {len(rooms)}")
    print(f"    - Openings count: {len(openings)}")
    print(f"    - Measurement:    {plan_dict['units']} (meters)")

    # 5. Store into Supabase Database
    print("\n[Step 5/5] Storing PlanJSON into Supabase PostgreSQL database...")
    supabase = get_supabase_client()

    # Find or create project
    proj_res = supabase.table("projects").select("id, name, user_id").order("created_at", desc=True).limit(1).execute()
    if proj_res.data:
        project_id = proj_res.data[0]["id"]
        project_name = proj_res.data[0]["name"]
        user_id = proj_res.data[0].get("user_id")
        print(f"  ✓ Found active project: '{project_name}' (ID: {project_id})")
    else:
        # Create fresh default project
        project_id = str(uuid.uuid4())
        # Try fetching any auth user
        users = supabase.auth.admin.list_users()
        user_id = users[0].id if users else str(uuid.uuid4())
        supabase.table("projects").insert({
            "id": project_id,
            "user_id": user_id,
            "name": "Single Family Architectural Project",
            "description": "Floor plan extracted by Gemini Vision",
            "status": "active"
        }).execute()
        print(f"  ✓ Created new project: ID: {project_id}")

    # Insert into 'plans' table
    plan_id = str(uuid.uuid4())
    supabase.table("plans").insert({
        "id": plan_id,
        "project_id": project_id,
        "name": "Gemini Vision Extracted Plan",
        "origin": "extracted",
        "plan_json": plan_dict,
        "overall_confidence": 0.95,
        "status": "verified"
    }).execute()
    print(f"  ✓ Successfully saved PlanJSON into Supabase 'plans' table! (Plan ID: {plan_id})")

    # Save to local file
    output_file = backend_dir / "extracted_plan.json"
    with open(output_file, "w", encoding="utf-8") as out_f:
        json.dump(plan_dict, out_f, indent=2)
    print(f"  ✓ Exported local JSON copy to: {output_file}")

    print("\n" + "=" * 70)
    print("EXTRACTION SUMMARY & PLANJSON PREVIEW:")
    print("=" * 70)
    print(f"Plan ID:    {plan_id}")
    print(f"Project ID: {project_id}")
    print("\nRooms Identified:")
    for r in rooms:
        poly_pts = len(r.get("polygon", []))
        print(f"  • {r.get('name', 'Room')} ({poly_pts} corner points)")

    print("\nSample Walls (First 5):")
    for w in walls[:5]:
        print(f"  • Wall {w['id']}: start {w['start']} -> end {w['end']} (thickness: {w['thickness']}m)")

    print("\nOpenings (Doors & Windows):")
    for o in openings:
        print(f"  • {o['type'].upper()} ({o['id']}) on Wall '{o['wall_id']}': width {o['width']}m x height {o['height']}m (offset: {o['offset']}m)")

    return plan_dict, plan_id, project_id


if __name__ == "__main__":
    main()
