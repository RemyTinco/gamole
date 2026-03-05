import { z } from 'zod';

// TraceEvent schema
export const traceEventSchema = z.object({
  id: z.string(),
  workflowId: z.string(),
  agentName: z.string(),
  eventType: z.string(),
  roundNumber: z.number(),
  promptText: z.string().nullable().optional(),
  responseText: z.string().nullable().optional(),
  modelName: z.string().nullable().optional(),
  latencyMs: z.number().nullable().optional(),
  tokenIn: z.number().nullable().optional(),
  tokenOut: z.number().nullable().optional(),
  costUsd: z.number().nullable().optional(),
  success: z.boolean().default(true),
  errorType: z.string().nullable().optional(),
  critiqueMarkdown: z.string().nullable().optional(),
  metadataJson: z.record(z.unknown()).nullable().optional(),
  createdAt: z.string(),
});

export type TraceEvent = z.infer<typeof traceEventSchema>;

// TraceEventSummary schema
export const traceEventSummarySchema = z.object({
  agentName: z.string(),
  eventType: z.string(),
  roundNumber: z.number(),
  latencyMs: z.number().nullable().optional(),
  tokenIn: z.number().nullable().optional(),
  tokenOut: z.number().nullable().optional(),
  success: z.boolean().default(true),
  timestamp: z.string(),
});

export type TraceEventSummary = z.infer<typeof traceEventSummarySchema>;
