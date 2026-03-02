import { z } from 'zod';

// Template schema
export const TemplateSchema = z.object({
  name: z.string(),
  description: z.string().optional(),
  requiredHeadings: z.array(z.string()),
  defaultSections: z.array(
    z.object({
      heading: z.string(),
      placeholder: z.string(),
    })
  ),
  customFieldMappings: z.record(z.string(), z.string()).optional(),
});

export type Template = z.infer<typeof TemplateSchema>;
