/**
 * Zod mirrors of the 3D gateway (backend: /api/v1/3d) and of the messages the embedded
 * review page posts to this app.
 *
 * Nothing here changes a value (no defaults, no transforms) and every object is "loose",
 * so a field the server adds later does not break the pages.
 */
import { z } from 'zod';

export const plan3dQualityIdSchema = z.enum(['low', 'high']);
export type Plan3dQualityId = z.infer<typeof plan3dQualityIdSchema>;

/** One build quality the server names, and whether it can be built now. */
export const plan3dQualitySchema = z.looseObject({
  id: plan3dQualityIdSchema,
  label: z.string(),
  description: z.string(),
  available: z.boolean(),
  /** Why it cannot be built; empty when it can. */
  reason: z.string(),
});
export type Plan3dQuality = z.infer<typeof plan3dQualitySchema>;

/** GET /system: whether the 3D builder can take plans, and what is missing when it cannot. */
export const plan3dSystemSchema = z.looseObject({
  reachable: z.boolean(),
  ready: z.boolean(),
  /** One entry per requirement of the builder, e.g. `{ blender: { ok: false } }`. */
  checks: z.record(z.string(), z.unknown()),
  detail: z.string(),
  qualities: z.array(plan3dQualitySchema),
});
export type Plan3dSystem = z.infer<typeof plan3dSystemSchema>;

export const plan3dStageSchema = z.enum(['uploaded', 'detecting', 'detected', 'queued', 'building', 'done', 'failed']);
export type Plan3dStage = z.infer<typeof plan3dStageSchema>;

export const plan3dJobCreatedSchema = z.looseObject({ job_id: z.string() });

/** A job as GET /jobs and GET /jobs/{id} describe it. */
export const plan3dJobSchema = z.looseObject({
  job_id: z.string(),
  name: z.string(),
  project_id: z.string().nullable(),
  /** upload, the builder's sample, or a plan of the floor plan generator ("Open in 3D"). */
  source: z.enum(['upload', 'sample', 'floorplan']),
  stage: plan3dStageSchema,
  /** 0 to 100, of the detection or of the build. */
  progress: z.number(),
  message: z.string(),
  /** Names of the floors found in the drawing; empty until the plan is detected. */
  floors: z.array(z.string()),
  scale_source: z.string().nullable(),
  /** Seconds, while building. */
  eta_left: z.number().nullable(),
  /** 1 = next, while queued. */
  queue_position: z.number().nullable(),
  /** Of the house that is built, or being built. */
  quality: plan3dQualityIdSchema.nullable(),
  build_seconds: z.number().nullable(),
  /** While High builds: a Low house can already be walked through. */
  preview: z.boolean().optional().default(false),
  /** Rendered video tours of the built house, by quality. */
  tours: z.record(z.string(), z.looseObject({ file: z.string(), seconds: z.number().nullable() })).optional().default({}),
  created_at: z.string().nullable(),
  /** Who read the plan: detector, ai (our AI plan reader), stored (the floor plan generator),
   *  trace (nothing could be read: traced by hand); empty until it is read. */
  reader: z.string().optional(),
  /** What to check, from that reader. */
  notice: z.string().optional(),
});
export type Plan3dJob = z.infer<typeof plan3dJobSchema>;

export const plan3dJobListSchema = z.array(plan3dJobSchema);

/** POST /jobs/{id}/export: the name of the packed file under the job's `files_url`. */
export const plan3dExportSchema = z.looseObject({ file: z.string() });

/** A share link to the walkthrough: an embed path anyone with it can open, read-only, until it is turned off. */
export const plan3dShareSchema = z.looseObject({ url: z.string().startsWith('/api/v1/3d/embed/'), expires_in: z.number() });

/** Every embed URL is a path of this API under this prefix; it carries a signed token. */
export const EMBED_PATH_PREFIX = '/api/v1/3d/embed/';
const embedPath = z.string().startsWith(EMBED_PATH_PREFIX);

/**
 * POST /jobs/{id}/embed and POST /embed: where to point an iframe. The job's own URLs are
 * null for the furniture models page, which has no job.
 */
export const plan3dEmbedSchema = z.looseObject({
  base_url: embedPath,
  /** Seconds until the signed token in the URLs stops working. */
  expires_in: z.number(),
  review_url: embedPath.nullable(),
  walkthrough_url: embedPath.nullable(),
  furniture_url: embedPath,
  files_url: embedPath.nullable(),
});
export type Plan3dEmbed = z.infer<typeof plan3dEmbedSchema>;

// ------------------------------------------------------------- review page

const fromReviewPage = { source: z.literal('planto3d'), job: z.string() };

/**
 * What the review page posts to the page that frames it.
 *
 * `error` of `saved` may be missing altogether: the page reads it from the server's answer,
 * and an answer without one must still count as "not saved" instead of being ignored.
 */
export const plan3dFrameMessageSchema = z.discriminatedUnion('type', [
  z.looseObject({
    ...fromReviewPage,
    type: z.literal('ready'),
    floors: z.number(),
    reader: z.string().optional(),
    notice: z.string().optional(),
    /** False while the plan cannot be built yet (a traced plan with no walls or no scale). */
    buildable: z.boolean().optional(),
    problem: z.string().nullable().optional(),
  }),
  z.looseObject({
    ...fromReviewPage,
    type: z.literal('buildable'),
    buildable: z.boolean(),
    problem: z.string().nullable().optional(),
  }),
  z.looseObject({ ...fromReviewPage, type: z.literal('failed'), message: z.string() }),
  z.looseObject({ ...fromReviewPage, type: z.literal('saved'), ok: z.boolean(), error: z.string().nullable().optional() }),
]);
export type Plan3dFrameMessage = z.infer<typeof plan3dFrameMessageSchema>;

/** What this app posts to the review page: save the plan as it is now. */
export interface Plan3dSaveRequest {
  source: 'planto3d-host';
  type: 'save';
  furnish: boolean;
}

/** A long build that finished or failed (newest first), and whether the person gets emails about them. */
export const plan3dNotificationsSchema = z.looseObject({
  email: z.boolean(),
  items: z.array(
    z.looseObject({
      job_id: z.string(),
      outcome: z.enum(['done', 'failed']),
      title: z.string(),
      at: z.string(),
    }),
  ),
});
export type Plan3dNotifications = z.infer<typeof plan3dNotificationsSchema>;
