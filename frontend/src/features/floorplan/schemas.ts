/**
 * Zod mirrors of the floor plan API bodies (backend: app/modules/ai/floorplan/schemas/api.py).
 * Responses are parsed with these so a backend change shows up as a clear error, not a
 * blank screen. Objects are "loose": extra backend fields are kept, never rejected.
 */
import { z } from 'zod';

export const SIDES = ['north', 'south', 'east', 'west'] as const;
export const sideSchema = z.enum(SIDES);
export type Side = z.infer<typeof sideSchema>;

/** Optional extras the form offers (backend RoomType values). */
export const EXTRA_ROOMS = [
  { value: 'dining', label: 'Dining' },
  { value: 'study', label: 'Study' },
  { value: 'store', label: 'Store' },
  { value: 'utility', label: 'Utility' },
  { value: 'toilet', label: 'Guest toilet' },
  { value: 'foyer', label: 'Foyer' },
  { value: 'parking', label: 'Parking' },
  { value: 'balcony', label: 'Balcony' },
  { value: 'courtyard', label: 'Courtyard' },
  { value: 'garden', label: 'Garden' },
  { value: 'deck', label: 'Sit-out' },
  { value: 'pool', label: 'Swimming pool' },
] as const;
export type ExtraRoom = (typeof EXTRA_ROOMS)[number]['value'];

/** Where the pool sits (backend pipeline/pool_layouts.py). */
export const POOL_LAYOUTS = [
  { value: 'side', label: 'Beside the house', hint: 'pool against a boundary, house next to it' },
  { value: 'u_shape', label: 'House around it (U)', hint: 'rooms on three sides, open to the back' },
  { value: 'centre', label: 'In the middle', hint: 'courtyard pool, rooms on all four sides' },
  { value: 'two_block', label: 'Between two blocks', hint: 'main house + guest block across the pool' },
] as const;
export type PoolLayout = (typeof POOL_LAYOUTS)[number]['value'];
export const poolLayoutSchema = z.enum(['side', 'u_shape', 'centre', 'two_block']);

// ------------------------------------------------------------------ the form

const optionalNumber = (min: number, max: number) =>
  z.preprocess(
    (v) => (v === '' || v === null || v === undefined || Number.isNaN(v) ? undefined : Number(v)),
    z.number().min(min).max(max).optional(),
  );

export const briefFormSchema = z
  .object({
    plot_width: optionalNumber(1, 2000),
    plot_depth: optionalNumber(1, 2000),
    unit: z.enum(['ft', 'm']),
    bedrooms: optionalNumber(0, 12),
    bathrooms: optionalNumber(0, 12),
    road_side: z.preprocess((v) => (v === '' ? undefined : v), sideSchema.optional()),
    pool_layout: z.preprocess((v) => (v === '' ? undefined : v), poolLayoutSchema.optional()),
    extras: z.array(z.string()),
    project_name: z.string().max(120),
    owner_name: z.string().max(120),
    prompt: z.string().max(4000),
  })
  .refine(
    (f) => (f.plot_width === undefined) === (f.plot_depth === undefined),
    { message: 'Give both width and depth, or leave both empty and describe the plot below.', path: ['plot_depth'] },
  )
  .refine((f) => f.prompt.trim() !== '' || f.plot_width !== undefined, {
    message: 'Enter the plot size or describe the house.',
    path: ['prompt'],
  });

export type BriefFormInput = z.input<typeof briefFormSchema>;
export type BriefFormValues = z.output<typeof briefFormSchema>;

export const EMPTY_FORM: BriefFormInput = {
  plot_width: undefined,
  plot_depth: undefined,
  unit: 'ft',
  bedrooms: undefined,
  bathrooms: undefined,
  road_side: undefined,
  pool_layout: undefined,
  extras: [],
  project_name: '',
  owner_name: '',
  prompt: '',
};

// ------------------------------------------------------------------ the brief

export const conflictSchema = z.looseObject({
  field: z.string(),
  form_value: z.string(),
  text_value: z.string(),
  resolution: z.string(),
});

export const roomRequestSchema = z.looseObject({
  type: z.string(),
  count: z.number(),
  attached_bath: z.boolean(),
  dress_room: z.boolean(),
  label: z.string().nullable().optional(),
});

export const briefSchema = z.looseObject({
  plot: z.looseObject({
    width_cm: z.number().nullable(),
    depth_cm: z.number().nullable(),
    input_unit: z.enum(['ft', 'm', 'cm']).or(z.string()),
    shape_assumed: z.boolean(),
  }),
  purpose: z.string().nullable().optional(),
  bedrooms: z.number().nullable().optional(),
  bathrooms: z.number().nullable().optional(),
  rooms: z.array(roomRequestSchema),
  road_side: sideSchema.nullable().optional(),
  pool_layout: poolLayoutSchema.nullable().optional(),
  project_name: z.string(),
  owner_name: z.string(),
  notes: z.string(),
  unknowns: z.array(z.string()),
  conflicts: z.array(conflictSchema),
  assumptions: z.array(z.string()),
  // how spoken or abbreviated words were read ("four year" -> foyer), to confirm on the card
  interpretation: z.array(z.string()).optional(),
});
export type Brief = z.infer<typeof briefSchema>;

export const parseResponseSchema = z.object({
  brief: briefSchema,
  summary: z.string(),
  warnings: z.array(z.string()),
  missing: z.array(z.string()),
  ready: z.boolean(),
});
export type ParseResponse = z.infer<typeof parseResponseSchema>;

// -------------------------------------------------------------------- jobs

export const jobStatusSchema = z.enum(['queued', 'running', 'done', 'failed']);

export const jobEventSchema = z.looseObject({
  job_id: z.string(),
  status: jobStatusSchema,
  stage: z.string(),
  detail: z.string(),
  progress: z.number(),
  plan_id: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
  options: z.array(z.string()).optional().default([]),
});
export type JobEvent = z.infer<typeof jobEventSchema>;

export const jobStateSchema = jobEventSchema.extend({ events: z.array(jobEventSchema) });
export type JobState = z.infer<typeof jobStateSchema>;

// -------------------------------------------------------------------- plans

export const planRoomSchema = z.looseObject({
  id: z.string(),
  type: z.string(),
  label: z.string(),
  x: z.number(),
  y: z.number(),
  w: z.number(),
  h: z.number(),
  part_of: z.string().nullable().optional(),
});
export type PlanRoom = z.infer<typeof planRoomSchema>;

export const floorPlanSchema = z.looseObject({
  id: z.string(),
  meta: z.looseObject({ unit_display: z.string() }),
  plot: z.looseObject({ width: z.number(), depth: z.number(), road_side: sideSchema.nullable().optional() }),
  rooms: z.array(planRoomSchema),
});

export const chatMessageSchema = z.object({
  role: z.enum(['user', 'assistant']),
  text: z.string(),
  status: z.string().nullable().optional(),
  version: z.number().nullable().optional(),
});
export type ChatMessage = z.infer<typeof chatMessageSchema>;

export const versionInfoSchema = z.object({
  version: z.number(),
  change: z.string().default(''),
  at: z.string().default(''),
});
export type VersionInfo = z.infer<typeof versionInfoSchema>;

export const planResponseSchema = z.object({
  id: z.string(),
  project_id: z.string().nullable().optional(),
  name: z.string(),
  version: z.number(),
  plan: floorPlanSchema,
  svg: z.string(),
  brief: briefSchema.nullable().optional(),
  notes: z.array(z.string()),
  messages: z.array(chatMessageSchema),
  plan_json: z.record(z.string(), z.unknown()),
  saved: z.boolean(),
  history: z.array(versionInfoSchema).default([]),
  facing: z.string().nullable().optional(),
  areas: z.array(z.string()).optional().default([]),
  checks: z
    .array(
      z.object({
        code: z.string(),
        severity: z.enum(['critical', 'warning', 'info']),
        message: z.string(),
        rooms: z.array(z.string()).default([]),
        ref: z.string().default(''),
      }),
    )
    .optional()
    .default([]),
  model: z.string().optional().default(''),
});
export type PlanResponse = z.infer<typeof planResponseSchema>;

export const editStatusSchema = z.enum(['ok', 'no_change', 'impossible', 'needs_clarification', 'failed', 'info']);

export const floorplanSummarySchema = z.object({
  id: z.string(),
  project_id: z.string().nullable().optional(),
  name: z.string(),
  version: z.number(),
  created_at: z.string().default(''),
});
export type FloorplanSummary = z.infer<typeof floorplanSummarySchema>;

export const editResponseSchema = z.object({
  status: editStatusSchema,
  message: z.string(),
  summary: z.array(z.string()),
  alternatives: z.array(z.string()),
  warnings: z.array(z.string()),
  plan: planResponseSchema,
});
export type EditResponse = z.infer<typeof editResponseSchema>;

export const EXPORT_FORMATS = [
  { value: 'pdf', label: 'PDF (A3 at scale, vector)' },
  { value: 'dxf', label: 'DXF (CAD layers, mm)' },
  { value: 'dwg', label: 'DWG (AutoCAD 2018)' },
  { value: 'ifc', label: 'IFC (Revit, ArchiCAD)' },
  { value: 'svg', label: 'SVG (vector)' },
  { value: 'png', label: 'PNG (image)' },
] as const;
export type ExportFormat = (typeof EXPORT_FORMATS)[number]['value'];
