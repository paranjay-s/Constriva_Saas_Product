import json
import uuid
import sys
from pathlib import Path
from dotenv import load_dotenv

backend_dir = Path(__file__).resolve().parent
load_dotenv(backend_dir / ".env")

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.supabase import get_supabase_client
from app.modules.plans.schemas import PlanJSON

def sync_to_supabase():
    plan_file = backend_dir / "extracted_plan.json"
    with open(plan_file, "r", encoding="utf-8") as f:
        plan_dict = json.load(f)

    # Validate
    PlanJSON(**plan_dict)

    supabase = get_supabase_client()
    proj_res = supabase.table("projects").select("id, name, user_id").order("created_at", desc=True).limit(1).execute()
    if proj_res.data:
        project_id = proj_res.data[0]["id"]
        project_name = proj_res.data[0]["name"]
        print(f"Using project: {project_name} ({project_id})")
    else:
        project_id = str(uuid.uuid4())
        users = supabase.auth.admin.list_users()
        user_id = users[0].id if users else str(uuid.uuid4())
        supabase.table("projects").insert({
            "id": project_id,
            "user_id": user_id,
            "name": "Single Family Architectural Project",
            "description": "Floor plan extracted by Gemini Vision",
            "status": "active"
        }).execute()
        print(f"Created project: {project_id}")

    plan_id = str(uuid.uuid4())
    supabase.table("plans").insert({
        "id": plan_id,
        "project_id": project_id,
        "name": "Precision Architectural Floor Plan (36'6\" x 55')",
        "origin": "extracted",
        "plan_json": plan_dict,
        "overall_confidence": 0.98,
        "status": "verified"
    }).execute()
    print(f"SUCCESS: Synced plan to Supabase with ID: {plan_id}")

if __name__ == "__main__":
    sync_to_supabase()
