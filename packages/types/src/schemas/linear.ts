import { z } from 'zod';

// LinearPushConfig schema
export const LinearPushConfigSchema = z.object({
  teamId: z.string(),
  projectId: z.string().optional(),
  labels: z.array(z.string()).optional(),
  stateId: z.string().optional(),
  mode: z.enum(['create', 'update']).default('create'),
  existingIssueId: z.string().optional(),
});

export type LinearPushConfig = z.infer<typeof LinearPushConfigSchema>;

// LinearPushResult schema
export const LinearPushResultSchema = z.object({
  createdIssues: z.array(
    z.object({
      linearId: z.string(),
      identifier: z.string(),
      title: z.string(),
    })
  ),
  createdRelations: z.array(
    z.object({
      id: z.string(),
      type: z.string(),
    })
  ),
  errors: z.array(z.string()),
});

export type LinearPushResult = z.infer<typeof LinearPushResultSchema>;
