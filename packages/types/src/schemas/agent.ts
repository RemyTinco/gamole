import { z } from 'zod';

// LinearArtifact schema
export const LinearArtifactSchema = z.object({
  linearId: z.string(),
  title: z.string(),
  description: z.string().optional(),
  similarity: z.number(),
  teamId: z.string().optional(),
});

export type LinearArtifact = z.infer<typeof LinearArtifactSchema>;

// CodeChunk schema
export const CodeChunkSchema = z.object({
  filePath: z.string(),
  repoName: z.string(),
  language: z.string(),
  chunkText: z.string(),
  similarity: z.number(),
  domain: z.string().optional(),
  artifactType: z.string().optional(),
});

export type CodeChunk = z.infer<typeof CodeChunkSchema>;

// ContextBundle schema
export const ContextBundleSchema = z.object({
  linearArtifacts: z.array(LinearArtifactSchema),
  codeChunks: z.array(CodeChunkSchema),
  keyFacts: z.array(z.string()),
  gaps: z.array(z.string()),
});

export type ContextBundle = z.infer<typeof ContextBundleSchema>;

// AgentResult schema
export const AgentResultSchema = z.object({
  agentName: z.string(),
  revisedDoc: z.string(),
  critique: z.string(),
  riskFlags: z.array(z.string()),
  missingInfoQuestions: z.array(z.string()),
  confidence: z.number().min(0).max(1),
  score: z.number().min(0).max(10),
});

export type AgentResult = z.infer<typeof AgentResultSchema>;
