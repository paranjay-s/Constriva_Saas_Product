/**
 * Zod mirrors of the BOQ raw-material API (backend: /api/v1/sheets/boq).
 *
 * Nothing here changes a value (no defaults, no transforms) and rows are "loose", so a
 * parsed result can be sent back to the export endpoints exactly as the server gave it.
 * The rows are data-driven: no row count, category list or item code is assumed.
 */
import { z } from 'zod';

export const boqJobCreatedSchema = z.looseObject({ job_id: z.string() });

/** Decimals to show for a quantity; the API sends 0 (counts) or 2 (measures). */
const decimalsSchema = z.number().int().min(0).max(6).nullable().optional();

export const boqComponentSchema = z.looseObject({
  label: z.string(),
  quantity: z.number(),
  unit: z.string(),
  quantity_decimals: decimalsSchema,
});
export type BoqComponent = z.infer<typeof boqComponentSchema>;

export const boqCalcTypeSchema = z.enum(['geometry', 'count', 'allowance']);
export const boqQuoteStatusSchema = z.enum(['INCLUDED', 'EXCLUDED_FROM_QUOTE']);

export const boqItemSchema = z.looseObject({
  /** 1..59; split rows carry a letter ("17a") and arrive as strings. */
  serial_no: z.union([z.number(), z.string()]),
  item_code: z.string(),
  category: z.string(),
  category_code: z.string().nullable().optional(),
  sub_category: z.string(),
  name: z.string(),
  unit: z.string(),
  quantity: z.number(),
  quantity_decimals: decimalsSchema,
  components: z.array(boqComponentSchema),
  calc_type: boqCalcTypeSchema,
  quote_status: boqQuoteStatusSchema,
  note: z.string(),
});
export type BoqItem = z.infer<typeof boqItemSchema>;

export const boqGeometrySummarySchema = z.looseObject({
  a_built_total_m2: z.number(),
  a_built_total_sqft: z.number().nullable().optional(),
  levels_count: z.number(),
  rooms_count: z.number(),
  bathrooms_count: z.number(),
});
export type BoqGeometrySummary = z.infer<typeof boqGeometrySummarySchema>;

const optionalText = z.string().nullable().optional();

export const boqProjectMetadataSchema = z.looseObject({
  project_title: optionalText,
  client: optionalText,
  subject: optionalText,
  building_type: optionalText,
  source_file_name: optionalText,
});
export type BoqProjectMetadata = z.infer<typeof boqProjectMetadataSchema>;

/**
 * What the bill was calculated with: the values actually used and where they come from.
 *
 * The values are plain strings, not enums, on purpose: a building type is whatever the plan
 * states, and a value this page does not know yet must not make the whole bill unreadable.
 * Known today: building_type_source "user" | "plan" | "default"; ceiling_height_source
 * "user" | "plan" | "assumed" | "mixed"; tile_size_mm and tile_pattern as in
 * `BoqAssumptionsInput`.
 */
export const boqAssumptionsSchema = z.looseObject({
  building_type: z.string(),
  building_type_source: z.string(),
  /** One per level. */
  ceiling_heights_m: z.array(z.number()),
  ceiling_height_source: z.string(),
  tile_size_mm: z.string(),
  tile_pattern: z.string(),
  /** 0 to 1: the share of the dry indoor area that gets a false ceiling. */
  false_ceiling_share: z.number(),
  /** null: estimated from the plan. */
  plot_perimeter_m: z.number().nullable(),
});
export type BoqAssumptions = z.infer<typeof boqAssumptionsSchema>;

export type BoqBuildingType = 'villa' | 'apartment' | 'other';
export type BoqTileSize = '600x600' | '800x800' | '1200x600';
export type BoqTilePattern = 'standard' | 'herringbone';

/**
 * The body of POST /jobs/{id}/recalculate: what a person chose. Every field is optional and
 * a field that is left out means "the default" (the server rejects unknown fields).
 */
export interface BoqAssumptionsInput {
  /** Left out or null: what the plan says. */
  building_type?: BoqBuildingType | null;
  /** 2 to 8 m, for every level. Left out or null: each level's own height from the plan. */
  ceiling_height_m?: number | null;
  tile_size_mm?: BoqTileSize;
  tile_pattern?: BoqTilePattern;
  /** 0 to 1. */
  false_ceiling_share?: number;
  /** Above 0, at most 100000. Left out or null: estimated from the plan. */
  plot_perimeter_m?: number | null;
}

/**
 * The finished bill. Older keys the server may still send next to these (materials,
 * materials_by_key, level_summaries, room_breakdown) are dropped here, so they can never
 * reach the screen or an export request. `assumptions` is missing from an older server.
 */
export const boqResultSchema = z.object({
  items: z.array(boqItemSchema),
  warnings: z.array(z.string()),
  geometry_summary: boqGeometrySummarySchema,
  project_metadata: boqProjectMetadataSchema,
  assumptions: boqAssumptionsSchema.optional(),
});
export type BoqResult = z.infer<typeof boqResultSchema>;

export type BoqExportFormat = 'pdf' | 'xlsx';

/** The three steps the page shows while a plan is turned into a bill. */
export const BOQ_STEPS = [
  { id: 'uploading', label: 'Uploading', hint: 'Sending the PDF' },
  { id: 'parsing', label: 'Parsing', hint: 'Reading the floor plan' },
  { id: 'calculating', label: 'Calculating', hint: 'Working out the quantities' },
] as const;
export type BoqStepId = (typeof BOQ_STEPS)[number]['id'];
