/**
 * File classifier for codebase ingestion.
 *
 * Classifies files by:
 * - language (from extension)
 * - domain (from path segments)
 * - artifactType (API/model/config/test/doc/source)
 *
 * Also detects secret files that should be skipped.
 */

/**
 * Classification result for a single file.
 */
export interface FileClassification {
  domain: string
  artifactType: string
  language: string
}

const LANG_MAP: Record<string, string> = {
  ts: 'typescript',
  tsx: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  py: 'python',
  go: 'go',
  md: 'markdown',
  yaml: 'yaml',
  yml: 'yaml',
  json: 'json',
}

const DOMAIN_SEGMENTS = new Set([
  'api',
  'models',
  'services',
  'utils',
  'components',
  'hooks',
  'lib',
  'routes',
  'controllers',
  'middleware',
  'helpers',
  'types',
  'schema',
  'db',
  'database',
])

/**
 * Classify a file by path.
 *
 * @param filePath - Relative or absolute file path
 * @returns Classification: domain, artifactType, language
 */
export function classifyFile(filePath: string): FileClassification {
  const parts = filePath.replace(/\\/g, '/').split('/')
  const ext = filePath.split('.').pop()?.toLowerCase() ?? ''

  // Language from extension
  const language = LANG_MAP[ext] ?? 'unknown'

  // Domain: first matching path segment
  const domain =
    parts.find((p) => DOMAIN_SEGMENTS.has(p.toLowerCase())) ?? 'general'

  // Artifact type from path and extension
  let artifactType = 'source'
  const lower = filePath.toLowerCase()

  if (lower.includes('.test.') || lower.includes('.spec.') || lower.includes('/test') || lower.includes('/tests') || lower.includes('/__tests__')) {
    artifactType = 'test'
  } else if (lower.includes('config') || ext === 'yaml' || ext === 'yml' || ext === 'json') {
    artifactType = 'config'
  } else if (ext === 'md') {
    artifactType = 'doc'
  } else if (lower.includes('model') || lower.includes('schema')) {
    artifactType = 'model'
  } else if (lower.includes('api') || lower.includes('route') || lower.includes('controller') || lower.includes('endpoint')) {
    artifactType = 'api'
  }

  return { domain, artifactType, language }
}

/**
 * Detect whether a file should be skipped because it likely contains secrets.
 *
 * Skips if:
 * - Path contains `.env`
 * - Content matches API_KEY=, password:, or SECRET= patterns
 *
 * @param filePath - File path (relative or absolute)
 * @param content  - File content as a string
 * @returns true if the file should be excluded
 */
export function isSecretFile(filePath: string, content: string): boolean {
  if (filePath.includes('.env')) return true
  if (/API_KEY\s*=|password\s*:|SECRET\s*=/i.test(content)) return true
  return false
}

/**
 * The allowed source-code and text extensions for indexing.
 */
export const ALLOWED_EXTENSIONS = new Set([
  'ts', 'tsx', 'js', 'jsx', 'py', 'go', 'md', 'yaml', 'yml', 'json',
])
