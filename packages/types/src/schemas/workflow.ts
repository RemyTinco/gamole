import { z } from 'zod';

// WorkflowStatus enum with all required states
export const WorkflowStatusSchema = z.enum([
  'INITIALIZED',
  'CONTEXT_RETRIEVED',
  'DRAFT_GENERATED',
  'QA_REVIEWED',
  'DEV_REVIEWED',
  'PO_REVIEWED',
  'SUPERVISOR_REFINED',
  'QUALITY_EVALUATED',
  'APPROVED_FINAL_AI',
  'USER_EDITING',
  'READY_TO_PUSH',
  'PUSHED_TO_LINEAR',
  'FAILED',
]);

export type WorkflowStatus = z.infer<typeof WorkflowStatusSchema>;

// WorkflowInput schema
export const WorkflowInputSchema = z.object({
  text: z.string().min(1).max(10000),
  mode: z.enum(['form', 'chat']),
  targetTeamId: z.string(),
  targetProjectId: z.string().optional(),
  labels: z.array(z.string()).optional(),
  priority: z.number().int().min(0).max(4).optional(),
});

export type WorkflowInput = z.infer<typeof WorkflowInputSchema>;

// DocumentVersionType enum
export const DocumentVersionTypeSchema = z.enum(['AI_FINAL', 'USER_EDITED']);

export type DocumentVersionType = z.infer<typeof DocumentVersionTypeSchema>;

// DocumentVersion schema
export const DocumentVersionSchema = z.object({
  id: z.string().optional(),
  workflowId: z.string().optional(),
  type: DocumentVersionTypeSchema,
  contentMarkdown: z.string(),
  createdAt: z.date().optional(),
});

export type DocumentVersion = z.infer<typeof DocumentVersionSchema>;
