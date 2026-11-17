/**
 * Zod mirrors of the Material Finder API (backend: app/modules/ai/material_agent/schemas.py).
 * Identification and quantities only: there is no money field anywhere.
 * Objects are "loose" so extra backend fields are kept, never rejected.
 */
import { z } from 'zod';

export const UNITS = ['ft', 'in', 'm', 'cm', 'mm'] as const;
export type LengthUnit = (typeof UNITS)[number];

export const confidenceSchema = z.enum(['high', 'medium', 'low']);

export const materialSchema = z.looseObject({
  id: z.string(),
  catalog_id: z.string().nullable().optional(),
  name: z.string(),
  display_name: z.string(),
  category: z.string(),
  surface: z.string(),
  location: z.string().optional().default(''),
  coverage_ratio: z.number().nullable().optional(),
  finish: z.string().optional().default(''),
  pattern: z.string().optional().default(''),
  colour: z.string().optional().default(''),
  size_hint: z.string().optional().default(''),
  confidence: confidenceSchema,
  look_alikes: z.array(z.string()).optional().default([]),
  evidence: z.string().optional().default(''),
  replaces: z.string().optional().default(''),
});
export type Material = z.infer<typeof materialSchema>;

export const breakdownSchema = z.looseObject({ label: z.string(), formula: z.string(), value: z.number() });

export const quantityLineSchema = z.looseObject({
  material_id: z.string(),
  material: z.string(),
  application: z.string(),
  surface_sqft: z.number(),
  coverage_ratio: z.number(),
  net_qty: z.number(),
  wastage_pct: z.number(),
  total_qty: z.number(),
  unit: z.string(),
  buy_qty: z.number().nullable().optional(),
  buy_unit: z.string().nullable().optional(),
  breakdown: z.array(breakdownSchema).optional().default([]),
  assumptions: z.array(z.string()).optional().default([]),
});
export type QuantityLine = z.infer<typeof quantityLineSchema>;

export const targetSchema = z.looseObject({
  source: z.enum(['manual', 'project', 'uploaded_plan']),
  label: z.string(),
  room: z
    .looseObject({ name: z.string(), area_sqft: z.number(), height_ft: z.number(), length_ft: z.number().optional(), width_ft: z.number().optional() })
    .nullable()
    .optional(),
  wall: z.looseObject({ width_ft: z.number(), height_ft: z.number(), label: z.string() }).nullable().optional(),
});
export type TargetSpace = z.infer<typeof targetSchema>;

export const supportLineSchema = z.looseObject({
  material_id: z.string(),
  material: z.string(),
  item: z.string(),
  qty: z.number(),
  unit: z.string(),
  basis: z.string(),
});
export type SupportLine = z.infer<typeof supportLineSchema>;

export const reportSchema = z.looseObject({
  version: z.number(),
  target: targetSchema.nullable().optional(),
  lines: z.array(quantityLineSchema),
  identified_only: z.array(z.string()).optional().default([]),
  assumptions: z.array(z.string()).optional().default([]),
  supporting: z.array(supportLineSchema).optional().default([]),
  explanation: z.string().optional().default(''),
  note: z.string(),
});
export type MaterialReport = z.infer<typeof reportSchema>;

export const replyStatusSchema = z.enum(['ok', 'needs_input', 'not_found', 'failed', 'working']);
export type ReplyStatus = z.infer<typeof replyStatusSchema>;

export const chatMessageSchema = z.looseObject({
  role: z.enum(['user', 'assistant']),
  text: z.string(),
  status: replyStatusSchema.nullable().optional(),
  options: z.array(z.string()).optional().default([]),
});
export type ChatMessage = z.infer<typeof chatMessageSchema>;

export const sessionSchema = z.looseObject({
  id: z.string(),
  project_id: z.string().nullable().optional(),
  project_name: z.string().nullable().optional(),
  focus: z.string().optional().default(''),
  scene: z.string().optional().default(''),
  focus_found: z.boolean().optional().default(true),
  focus_note: z.string().optional().default(''),
  materials: z.array(materialSchema),
  report: reportSchema.nullable().optional(),
  messages: z.array(chatMessageSchema).optional().default([]),
  pending_question: chatMessageSchema.nullable().optional(),
  uploaded_plan_name: z.string().nullable().optional(),
  saved: z.boolean().optional().default(false),
});
export type Session = z.infer<typeof sessionSchema>;

export const chatReplySchema = z.looseObject({
  status: replyStatusSchema,
  message: z.string(),
  options: z.array(z.string()).optional().default([]),
  job_id: z.string().nullable().optional(),
  session: sessionSchema,
});
export type ChatReply = z.infer<typeof chatReplySchema>;

export const analysisCreatedSchema = z.looseObject({ report_id: z.string(), job_id: z.string() });

/** What the person typed for the space being measured. */
export interface ManualSpace {
  kind: 'room' | 'wall';
  unit: LengthUnit;
  length: number;
  width?: number;
  height?: number;
  label?: string;
}

export interface Overrides {
  wastage_pct?: Record<string, number>;
  coverage_ratio?: Record<string, number>;
  ceiling_height_ft?: number;
}

export const MATERIAL_STAGES = [
  { stage: 'uploading', label: 'Uploading the photo' },
  { stage: 'analysing_image', label: 'Looking at the materials' },
  { stage: 'matching_materials', label: 'Matching to the catalog' },
  { stage: 'calculating', label: 'Calculating quantities' },
  { stage: 'writing_summary', label: 'Writing the summary' },
] as const;
