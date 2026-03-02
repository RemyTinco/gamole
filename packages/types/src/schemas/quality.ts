import { z } from 'zod';

// QualityFlag enum
export const QualityFlagSchema = z.enum([
  'below_quality_threshold',
  'missing_nfrs',
  'ambiguous_acceptance_criteria',
  'low_grounding_coverage',
  'high_overlap_risk',
]);

export type QualityFlag = z.infer<typeof QualityFlagSchema>;

// QualityScore schema
export const QualityScoreSchema = z.object({
  score: z.number().min(0).max(10),
  flags: z.array(QualityFlagSchema),
  details: z.record(z.string(), z.unknown()),
});

export type QualityScore = z.infer<typeof QualityScoreSchema>;
