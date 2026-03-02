/**
 * @gamole/ai — Codebase Ingestion Service
 *
 * Clones (or pulls) a Git repository, walks the file tree, chunks and embeds
 * every eligible source file, and stores the result in `codebase_chunks`.
 *
 * RULES:
 * - G18: NO real-time indexing — called on a nightly schedule only
 * - Never store secrets: files matching .env or containing secret patterns are skipped
 * - Binary files, images, and compiled output are skipped
 */

import { readdir, readFile } from 'node:fs/promises'
import { join, relative } from 'node:path'
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'

import { embedBatch, chunkText } from '../embeddings'
import { classifyFile, isSecretFile, ALLOWED_EXTENSIONS } from './classifier'

// Type-only imports from @gamole/db — erased at runtime, safe even if DB unavailable
import type { db as DbType } from '@gamole/db'
import type { codebaseChunks as CodebaseChunksType } from '@gamole/db'

/** Stats returned by indexRepository(). */
export interface IndexStats {
  repoName: string
  filesIndexed: number
  chunksCreated: number
  errors: number
}

/** Base directory for cloned repos. */
const REPOS_BASE_DIR = '/tmp/gamole-repos'

// ---------------------------------------------------------------------------
// Git helpers
// ---------------------------------------------------------------------------

/**
 * Clone a repository (depth=1) or pull the latest changes if already present.
 *
 * @throws Error with a descriptive message if the clone fails.
 */
async function cloneOrPull(
  repoUrl: string,
  targetDir: string,
  branch?: string,
): Promise<void> {
  if (existsSync(targetDir)) {
    // Repo already cloned — just pull
    await runGit(['git', '-C', targetDir, 'pull'])
    return
  }

  // Fresh clone (shallow, to keep it fast)
  const args: string[] = ['git', 'clone', '--depth=1']
  if (branch) {
    args.push('-b', branch)
  }
  args.push(repoUrl, targetDir)

  const exitCode = await runGit(args)
  if (exitCode !== 0) {
    throw new Error(`git clone failed with exit code ${exitCode}`)
  }
}

/**
 * Run a git command as a child process and return the exit code.
 */
function runGit(args: string[]): Promise<number> {
  return new Promise((resolve, reject) => {
    const proc = spawn(args[0]!, args.slice(1), {
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    proc.on('error', reject)
    proc.on('close', resolve)
  })
}

/**
 * Derive a human-readable repo name from a Git URL.
 *
 * Examples:
 *   https://github.com/org/repo.git → "org-repo"
 *   git@github.com:org/repo.git    → "org-repo"
 */
function repoNameFromUrl(repoUrl: string): string {
  const clean = repoUrl.replace(/\.git$/, '')
  const parts = clean.split(/[/:]+/)
  // Take the last two path segments (owner + repo)
  const relevant = parts.slice(-2).join('-')
  // Sanitise to safe filesystem characters
  return relevant.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase()
}

// ---------------------------------------------------------------------------
// File-tree walking
// ---------------------------------------------------------------------------

/**
 * Recursively list all files under `dir` that have an allowed extension.
 * Skips common noise directories (node_modules, .git, dist, build, __pycache__).
 */
async function walkFiles(dir: string): Promise<string[]> {
  const SKIP_DIRS = new Set([
    'node_modules',
    '.git',
    'dist',
    'build',
    '__pycache__',
    '.turbo',
    '.next',
    'coverage',
    'vendor',
    '.venv',
    'venv',
  ])

  const results: string[] = []

  async function walk(current: string): Promise<void> {
    let entries: import('node:fs').Dirent[]
    try {
      entries = await readdir(current, { withFileTypes: true }) as import('node:fs').Dirent[]
    } catch {
      return // unreadable directory — skip
    }

    for (const entry of entries) {
      const name = String(entry.name)
      const fullPath = join(current, name)

      if (entry.isDirectory()) {
        if (!SKIP_DIRS.has(name)) {
          await walk(fullPath)
        }
      } else if (entry.isFile()) {
        const ext = name.split('.').pop()?.toLowerCase() ?? ''
        if (ALLOWED_EXTENSIONS.has(ext)) {
          results.push(fullPath)
        }
      }
    }
  }

  await walk(dir)
  return results
}

// ---------------------------------------------------------------------------
// Core indexing
// ---------------------------------------------------------------------------

/**
 * Index (or re-index) a Git repository into the `codebase_chunks` table.
 *
 * @param repoUrl  Full Git URL (HTTPS or SSH)
 * @param branch   Optional branch / tag to check out
 * @returns Stats: repoName, filesIndexed, chunksCreated, errors
 */
/** Maximum number of distinct repositories that may be indexed. */
const MAX_REPOS = 3

/**
 * Error code prefix thrown when the repo limit is exceeded.
 * The API route detects this prefix to return 422.
 */
export const REPO_LIMIT_ERROR_PREFIX = 'REPO_LIMIT_EXCEEDED'

export async function indexRepository(
  repoUrl: string,
  branch?: string,
): Promise<IndexStats> {
  const repoName = repoNameFromUrl(repoUrl)
  const targetDir = join(REPOS_BASE_DIR, repoName)

  const stats: IndexStats = {
    repoName,
    filesIndexed: 0,
    chunksCreated: 0,
    errors: 0,
  }

  // ------------------------------------------------------------------
  // 1. Dynamically load DB (startup-safe, same pattern as linear sync)
  // ------------------------------------------------------------------
  let db: typeof DbType
  let codebaseChunks: typeof CodebaseChunksType

  try {
    const dbModule = await import('@gamole/db')
    db = dbModule.db
    codebaseChunks = dbModule.codebaseChunks
  } catch (err) {
    throw new Error(
      `Database not available: ${err instanceof Error ? err.message : String(err)}`,
    )
  }

  // We need eq, and for WHERE clauses
  const { eq, and } = await import('drizzle-orm')

  // ------------------------------------------------------------------
  // 2. Enforce repo cap (max 3 distinct repos)
  // ------------------------------------------------------------------
  const existingRepos = await db
    .selectDistinct({ repoName: codebaseChunks.repoName })
    .from(codebaseChunks)

  const existingNames = new Set(existingRepos.map((r) => r.repoName))
  if (!existingNames.has(repoName) && existingNames.size >= MAX_REPOS) {
    throw new Error(
      `${REPO_LIMIT_ERROR_PREFIX}: Repository limit reached (max ${MAX_REPOS}). Remove an existing repo first.`,
    )
  }

  // ------------------------------------------------------------------
  // 3. Clone / pull
  // ------------------------------------------------------------------
  try {
    await cloneOrPull(repoUrl, targetDir, branch)
  } catch (err) {
    console.error(`[codebase] Clone/pull failed for ${repoUrl}:`, err)
    stats.errors++
    // Return early — nothing to index
    return stats
  }

  // ------------------------------------------------------------------
  // 3. Walk file tree
  // ------------------------------------------------------------------
  let filePaths: string[]
  try {
    filePaths = await walkFiles(targetDir)
  } catch (err) {
    console.error(`[codebase] File walk failed for ${targetDir}:`, err)
    stats.errors++
    return stats
  }

  // ------------------------------------------------------------------
  // 4. Process each file
  // ------------------------------------------------------------------
  for (const absPath of filePaths) {
    const relPath = relative(targetDir, absPath)

    let content: string
    try {
      content = await readFile(absPath, 'utf-8')
    } catch {
      stats.errors++
      continue
    }

    // Skip secret files
    if (isSecretFile(relPath, content)) {
      continue
    }

    // Classify
    const { domain, artifactType, language } = classifyFile(relPath)

    // Chunk
    const chunks = chunkText(content)
    if (chunks.length === 0) continue

    // Embed (batch)
    let embeddings: number[][]
    try {
      embeddings = await embedBatch(chunks)
    } catch (err) {
      console.error(`[codebase] Embed failed for ${relPath}:`, err)
      stats.errors++
      continue
    }

    // Delete old chunks for this (repoName, filePath) pair, then insert fresh ones
    try {
      await db
        .delete(codebaseChunks)
        .where(
          and(
            eq(codebaseChunks.repoName, repoName),
            eq(codebaseChunks.filePath, relPath),
          ),
        )
    } catch {
      // Non-fatal — old rows may stay; new insert will still work
    }

    // Insert new chunks
    for (let i = 0; i < chunks.length; i++) {
      const chunkContent = chunks[i]
      const embedding = embeddings[i]

      if (chunkContent === undefined || embedding === undefined) {
        stats.errors++
        continue
      }

      try {
        await db.insert(codebaseChunks).values({
          repoName,
          filePath: relPath,
          language,
          chunkText: chunkContent,
          domain,
          artifactType,
          embedding,
          lastIndexedAt: new Date(),
        })
        stats.chunksCreated++
      } catch {
        stats.errors++
      }
    }

    stats.filesIndexed++
  }

  return stats
}
