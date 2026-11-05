# Plan schema

`plan.schema.json` is generated from the Pydantic model `PlanJSON` in
`backend/app/modules/plans/schemas.py`. Do not edit it by hand.

Regenerate it, and the TypeScript types in `frontend/src/types/plan.ts`, with:

    uv --directory backend run python -m app.modules.plans.export_schema
    pnpm --dir frontend gen:types

