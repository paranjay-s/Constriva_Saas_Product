# Constriva AI / LLM Integration Guide & Developer Handover

Welcome to the **Constriva AI Engineer Handover Guide**.

This document outlines the **exact 3 tasks** you need to implement, the **specific files you can edit**, the **API schemas**, and **how to test your work with single terminal commands** without needing to run the database, frontend, or server.

---

## 1. Architectural Overview & Work Division

The backend infrastructure (FastAPI, PostgreSQL tables on Supabase, private storage buckets, file uploads, authentication, project management, and cost sheet editing/exporting) is already built and running.

Your sole responsibility is to implement **3 specific Python functions** that connect to the Vision LLM (e.g. Gemini 2.0 Flash / Pro) to transform visual and geometric data:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 YOUR 3 TASKS                                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [TASK 1: Blueprint Parsing]                                                           │
│  Uploaded PDF ➔ 300 DPI PNG ➔ parse_blueprint_image_with_llm() ➔ PlanJSON ➔ Stored in DB│
│                                                                                        │
│  [TASK 2: Materials Mapping]                                                           │
│  PlanJSON ➔ map_plan_to_materials() ➔ 7 Core Materials List ➔ Stored in Cost Sheet     │
│                                                                                        │
│  [TASK 3: Site Photo Analysis]                                                         │
│  Phone Camera Photo ➔ analyze_construction_photo() ➔ Materials + Cost Estimate ➔ API   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. File Boundary Guide: What to Edit vs. What NOT to Touch

| File Path | Your Permission | Responsibility |
| :--- | :---: | :--- |
| `backend/app/modules/parsing/llm_parser.py` |  **CAN EDIT** | **Task 1**: Image ➔ PlanJSON extraction function |
| `backend/app/modules/sheets/llm_mapper.py` |  **CAN EDIT** | **Task 2**: PlanJSON ➔ 7 Materials mapping function |
| `backend/app/modules/ai/material_vision.py` |  **CAN EDIT** | **Task 3**: Phone Photo ➔ Material & Cost Vision |
| `backend/app/modules/ai/llm_client.py` |  **CAN EDIT** | Shared Gemini API caller / prompt helper |
| `.env` (in root or `backend/.env`) |  **CAN EDIT** | Add your `GEMINI_API_KEY=AIzaSy...` |
| `backend/app/core/*` | ❌ **DO NOT TOUCH** | Supabase database client, storage provisioner, JWT security |
| `backend/app/modules/auth/*` | ❌ **DO NOT TOUCH** | User registration, login, and profile management |
| `backend/app/modules/projects/*` | ❌ **DO NOT TOUCH** | Project CRUD operations |
| `backend/app/modules/files/*` | ❌ **DO NOT TOUCH** | Supabase Storage binary uploads and signed URLs |
| `backend/app/modules/sheets/router.py` | ❌ **DO NOT TOUCH** | Line item edit/delete APIs, CSV/PDF download handlers |
| `backend/app/main.py` | ❌ **DO NOT TOUCH** | FastAPI app bootstrap & CORS middleware |

---

## 3. Environment & API Key Setup

1. Open `.env` (or create `backend/.env`) and add your Gemini API Key:
   ```env
   GEMINI_API_KEY=AIzaSyYourGeminiApiKeyHere
   ```
2. Activate the backend Python virtual environment:
   ```powershell
   # On Windows PowerShell
   cd C:\Constriva-saas\Constriva_Saas_Product\backend
   .\.venv\Scripts\Activate.ps1
   ```

*(Note: The client in `app/modules/ai/llm_client.py` uses `httpx` to communicate directly with the Gemini 2.0 API. Zero extra SDK installations required!)*

---

## 4. TASK 1: 2D Blueprint Image ➔ PlanJSON

- **File**: `backend/app/modules/parsing/llm_parser.py`
- **Function**:
  ```python
  def parse_blueprint_image_with_llm(png_bytes: bytes) -> Dict[str, Any]
  ```

### What It Receives
- `png_bytes`: Raw binary bytes of the first page of the uploaded PDF floor plan, rasterized at **300 DPI**.

### What It Must Return
A Python dictionary conforming to the standard **PlanJSON** format used by our Three.js 3D viewer:

```json
{
  "version": 2,
  "units": "m",
  "scale_source": "dimension_label",
  "levels": [
    {
      "elevation": 0.0,
      "wall_height": 2.8,
      "walls": [
        {"id": "w_1", "start": [0.0, 0.0], "end": [10.5, 0.0], "thickness": 0.25},
        {"id": "w_2", "start": [10.5, 0.0], "end": [10.5, 5.0], "thickness": 0.25},
        {"id": "w_div_bed", "start": [6.0, 0.0], "end": [6.0, 5.0], "thickness": 0.15}
      ],
      "openings": [
        {"id": "op_main_door", "wall_id": "w_1", "type": "door", "offset": 2.0, "width": 1.0, "height": 2.1, "sill": 0.0},
        {"id": "op_bed_win", "wall_id": "w_2", "type": "window", "offset": 1.8, "width": 1.5, "height": 1.4, "sill": 0.9}
      ],
      "rooms": [
        {
          "id": "room_living",
          "name": "Living & Dining Room",
          "polygon": [[0.0, 0.0], [6.0, 0.0], [6.0, 5.0], [0.0, 5.0]]
        },
        {
          "id": "room_master_bed",
          "name": "Master Bedroom",
          "polygon": [[6.0, 0.0], [10.5, 0.0], [10.5, 5.0], [6.0, 5.0]]
        }
      ]
    }
  ],
  "confidence": {
    "w_1": 0.95
  }
}
```

### How the System Uses Your Output
The background worker automatically takes your returned dictionary and:
1. Writes it to the PostgreSQL `plans` table (`plan_json` column).
2. Sets `overall_confidence = 0.95` and status to `verified`.
3. Streams progress to the frontend via SSE (`GET /api/v1/parsing/stream/{task_id}`).
4. The React Three.js viewer immediately renders the walls, doors, and rooms in 3D!

### How to Test Task 1
Run this single command in terminal:
```powershell
python app/modules/parsing/llm_parser.py
```
*(It runs the built-in self-test and prints wall, opening, and room detection counts!)*

---

## 5. TASK 2: PlanJSON ➔ Material Estimation Sheet

- **File**: `backend/app/modules/sheets/llm_mapper.py`
- **Function**:
  ```python
  def map_plan_to_materials(plan_json: Dict[str, Any]) -> List[Dict[str, Any]]
  ```

### What It Receives
- `plan_json`: The architectural dictionary returned by Task 1 (walls, openings, room polygons).

### The 7 Core Materials You Must Output
Map the plan geometry to these **exact 7 materials**:

1. **Brick** (Category: `Masonry`, Unit: `pcs`, Rate: ~₹9.50)
2. **Steel/rebar rod** (Category: `Structural Steel`, Unit: `kg`, Rate: ~₹68.00)
3. **Cement** (Category: `Binder`, Unit: `bags`, Rate: ~₹380.00)
4. **Sand (fine aggregate)** (Category: `Aggregate`, Unit: `cu.m`, Rate: ~₹1,450.00)
5. **Ballast (coarse aggregate)** (Category: `Aggregate`, Unit: `cu.m`, Rate: ~₹1,650.00)
6. **Plaster (cement and gypsum)** (Category: `Wall Plaster & Finishes`, Unit: `sq.m`, Rate: ~₹185.00)
7. **Tiles (floor and wall)** (Category: `Flooring & Wall Tiling`, Unit: `sq.m`, Rate: ~₹620.00)

### What It Must Return
A list of dictionaries matching this structure:

```python
[
    {
        "name": "Brick",
        "category": "Masonry",
        "unit": "pcs",
        "quantity": 8500.0,         # Base quantity before waste
        "waste_factor": 0.05,       # 5% wastage
        "total_quantity": 8925.0,   # quantity * (1 + waste_factor)
        "unit_price": 9.50,         # Unit rate in INR
        "amount": 84787.50,         # total_quantity * unit_price
        "surface_tag": "masonry_walls",
        "is_custom": False,
    },
    # ... remaining 6 materials
]
```

### How the System Uses Your Output
When your function returns this list, `SheetService`:
1. Saves all items into the `public.sheet_items` table in Supabase.
2. Computes `subtotal`, automatically adds `5% site contingency`, and calculates `total_cost`.
3. Powers our frontend endpoints:
   - `GET /api/v1/sheets/{project_id}` ➔ Displays interactive table.
   - `PATCH /api/v1/sheets/{project_id}/items/{item_id}` ➔ User can edit quantities and rates inline.
   - `DELETE /api/v1/sheets/{project_id}/items/{item_id}` ➔ User can delete an item.
   - `GET /api/v1/sheets/{project_id}/export/csv` ➔ Downloads Excel CSV.
   - `GET /api/v1/sheets/{project_id}/export/pdf` ➔ Downloads ReportLab architectural PDF.

### How to Test Task 2
Run this single command in terminal:
```powershell
python app/modules/sheets/llm_mapper.py
```
*(It feeds a verified 2BHK plan into your function and displays the calculated quantities, rates, and total cost!)*

---

## 6. TASK 3: Site Photo ➔ Material & Cost Vision Analysis

- **File**: `backend/app/modules/ai/material_vision.py`
- **Function**:
  ```python
  def analyze_construction_photo(image_bytes: bytes, mime_type: str = "image/jpeg") -> Dict[str, Any]
  ```

### What It Receives
- `image_bytes`: Raw binary bytes of a camera photo taken by the user on site (JPG/PNG).
- `mime_type`: e.g. `'image/jpeg'` or `'image/png'`.

### What It Must Return
A structured dictionary analyzing the materials present in the photo and estimating costs:

```json
{
  "detected_materials": [
    {
      "name": "Vitrified Glazed Floor Tiles (600x600mm)",
      "category": "Flooring",
      "estimated_quantity": 18.0,
      "unit": "sq.m",
      "unit_rate_inr": 620.0,
      "estimated_amount_inr": 11160.0,
      "confidence": 0.92,
      "notes": "Double charged high-gloss finish."
    },
    {
      "name": "Red Clay Brickwork",
      "category": "Masonry",
      "estimated_quantity": 650.0,
      "unit": "pcs",
      "unit_rate_inr": 9.50,
      "estimated_amount_inr": 6175.0,
      "confidence": 0.95,
      "notes": "9-inch partition walling visible."
    }
  ],
  "total_estimated_cost_inr": 17335.0,
  "room_or_area_type": "Master Bedroom Interior",
  "construction_stage": "Finishing & Flooring",
  "observations": "Structural alignment is plumb. Wall plaster coat ready for primer.",
  "recommendations": [
    "Ensure tile adhesive cures for 24 hours before grouting joints",
    "Apply moisture-barrier primer before interior emulsion paint"
  ]
}
```

### How the System Uses Your Output
The API route `POST /api/v1/ai/analyze-materials` calls your function and serves this JSON payload directly to the user's dashboard!

### How to Test Task 3
Run this single command in terminal:
```powershell
python app/modules/ai/material_vision.py
```
*(It analyzes a sample photo and prints the detected materials, quantities, and cost breakdown!)*

---

## 7. Quick Verification Checklist

When you have edited your functions or updated prompts, run these 3 standalone commands from `backend/`:

```powershell
# 1. Test Blueprint Parsing (Task 1)
python app/modules/parsing/llm_parser.py

# 2. Test Materials Mapping (Task 2)
python app/modules/sheets/llm_mapper.py

# 3. Test Photo Material Vision (Task 3)
python app/modules/ai/material_vision.py
```

If all 3 print `SUCCESS`, your integration is complete and 100% operational across the entire Constriva platform!

