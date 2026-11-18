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
 * The finished bill. Older keys the server may still send next to these (materials,
 * materials_by_key, level_summaries, room_breakdown) are dropped here, so they can never
 * reach the screen or an export request.
 */
export const boqResultSchema = z.object({
  items: z.array(boqItemSchema),
  warnings: z.array(z.string()),
  geometry_summary: boqGeometrySummarySchema,
  project_metadata: boqProjectMetadataSchema,
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
