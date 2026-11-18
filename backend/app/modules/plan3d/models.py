"""The `plan3d_jobs` table: which user and project a PlanTo3D job belongs to.

The table is created by migrations/versions/20261118_0001_plan3d_jobs.py and is read and
written through the Supabase client in store.py, like the rest of the app.

    id          text primary key     PlanTo3D's job id (12 hex characters)
    user_id     uuid not null        the owner (Supabase auth user id)
    project_id  uuid null            the project it was uploaded into, if any
    name        text not null        the uploaded file's name
    source      text not null        'upload' or 'sample'
    quality     text null            the quality of the last build asked for: low, medium, high
    created_at  timestamptz not null
    updated_at  timestamptz not null
"""

TABLE = "plan3d_jobs"
