"""Project ownership, for the modules that hold things inside a project.

A plan, a file or a parsing job belongs to a project, and a project belongs to one user.
Other modules ask here whether a user may see something that lives in a project.
"""

import logging

from app.core.supabase import get_supabase_client

logger = logging.getLogger("construtiva.projects.service")


def user_owns_project(project_id: str | None, user_id: str) -> bool:
    """True when the project exists and belongs to the user.

    False for a missing project and for someone else's, with no way to tell them apart.
    A database error counts as "no": access is never granted on a failed check.
    """
    if not project_id or not user_id:
        return False
    try:
        found = (
            get_supabase_client()
            .table("projects")
            .select("id")
            .eq("id", project_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if found.data:
            return True
    except Exception as e:
        logger.warning("Could not check the owner of project %s: %s", project_id, e)
    # Projects kept in memory because the database could not be written at the time.
    from app.modules.projects.router import FALLBACK_PROJECTS

    row = FALLBACK_PROJECTS.get(str(project_id))
    return bool(row) and str(row.get("user_id")) == str(user_id)
