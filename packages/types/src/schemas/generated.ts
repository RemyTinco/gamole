import { z } from 'zod';

// GeneratedStory schema
export const GeneratedStorySchema = z.object({
  title: z.string(),
  description: z.string(),
  acceptanceCriteria: z.array(z.string()),
  assumptions: z.array(z.string()),
  technicalNotes: z.string().optional(),
});

export type GeneratedStory = z.infer<typeof GeneratedStorySchema>;

// GeneratedEpic schema
export const GeneratedEpicSchema = z.object({
  epicTitle: z.string(),
  epicDescription: z.string(),
  stories: z.array(GeneratedStorySchema),
});

export type GeneratedEpic = z.infer<typeof GeneratedEpicSchema>;

// GeneratedOutput schema
export const GeneratedOutputSchema = z.object({
  epics: z.array(GeneratedEpicSchema),
  overallNotes: z.string().optional(),
});

export type GeneratedOutput = z.infer<typeof GeneratedOutputSchema>;
