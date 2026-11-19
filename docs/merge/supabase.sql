-- SQL for Supabase, in order: the three Alembic migrations of feat/merged (only feat/run3 added any;
-- the UI branch added none). Generated with `uv --directory backend run alembic upgrade head --sql`
-- (offline: no database was touched). Paste into the Supabase SQL editor and run once.
--
-- BEFORE YOU RUN IT: if you already created plan3d_jobs from docs/08-3d.md, skip the block marked
-- "20261118_0001" (the table, its two indexes, row-level security and its policy) and instead run only
-- the alembic_version lines, so Alembic knows where it stands:
--   CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY);
--   INSERT INTO alembic_version (version_num) VALUES ('20261118_0001');
-- then run the 20261119_0001 and 20261119_0002 blocks as they are.
--
-- asset_library has no row-level security: only the server writes it (the 3D library's index works
-- from a JSON file until this table is used).

BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 20261118_0001

CREATE TABLE plan3d_jobs (
    id TEXT NOT NULL, 
    user_id UUID NOT NULL, 
    project_id UUID, 
    name TEXT DEFAULT '' NOT NULL, 
    source TEXT DEFAULT 'upload' NOT NULL, 
    quality TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT plan3d_jobs_id_format CHECK (id ~ '^[a-f0-9]{12}$'), 
    CONSTRAINT plan3d_jobs_source CHECK (source in ('upload', 'sample')), 
    CONSTRAINT plan3d_jobs_quality CHECK (quality is null or quality in ('low', 'medium', 'high')), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL
);

CREATE INDEX plan3d_jobs_user_created ON plan3d_jobs (user_id, created_at);

CREATE INDEX plan3d_jobs_project ON plan3d_jobs (project_id);

alter table plan3d_jobs enable row level security;

create policy plan3d_jobs_owner_read on plan3d_jobs for select using (auth.uid() = user_id);

INSERT INTO alembic_version (version_num) VALUES ('20261118_0001') RETURNING alembic_version.version_num;

-- Running upgrade 20261118_0001 -> 20261119_0001

CREATE TABLE asset_library (
    id TEXT NOT NULL, 
    kind TEXT NOT NULL, 
    room_types TEXT[] DEFAULT '{}' NOT NULL, 
    fits JSONB DEFAULT '{}' NOT NULL, 
    shape TEXT DEFAULT 'rectangular' NOT NULL, 
    style_tags TEXT[] DEFAULT '{}' NOT NULL, 
    browser_model TEXT, 
    detailed_model TEXT, 
    tris_browser INTEGER, 
    tris_detailed INTEGER, 
    preview TEXT, 
    source TEXT NOT NULL, 
    licence TEXT NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    review TEXT DEFAULT 'unreviewed' NOT NULL, 
    prompt TEXT, 
    cost_usd NUMERIC(10, 4), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT asset_library_kind CHECK (kind IN ('room_kit', 'furniture', 'appliance', 'fixture', 'material', 'lighting', 'parametric')), 
    CONSTRAINT asset_library_shape CHECK (shape IN ('rectangular', 'l_shaped', 'irregular', 'circular')), 
    CONSTRAINT asset_library_review CHECK (review IN ('unreviewed', 'approved', 'rejected'))
);

CREATE INDEX asset_library_kind_review ON asset_library (kind, review);

CREATE INDEX asset_library_room_types ON asset_library USING gin (room_types);

UPDATE alembic_version SET version_num='20261119_0001' WHERE alembic_version.version_num = '20261118_0001';

-- Running upgrade 20261119_0001 -> 20261119_0002

ALTER TABLE plan3d_jobs ADD COLUMN share_id TEXT;

ALTER TABLE plan3d_jobs ADD CONSTRAINT plan3d_jobs_share_id CHECK (share_id is null or share_id ~ '^[a-f0-9]{24}$');

UPDATE alembic_version SET version_num='20261119_0002' WHERE alembic_version.version_num = '20261119_0001';

COMMIT;

