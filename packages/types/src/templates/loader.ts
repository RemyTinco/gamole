import type { Template } from '../schemas/template';
import standardUserStory from './standard-user-story.json';

const templates: Record<string, Template> = {
  'standard-user-story': standardUserStory as Template,
};

export function loadTemplate(name: string): Template {
  const template = templates[name];
  if (!template) {
    throw new Error(
      `Template "${name}" not found. Available: ${Object.keys(templates).join(', ')}`
    );
  }
  return template;
}

export function listTemplates(): string[] {
  return Object.keys(templates);
}
