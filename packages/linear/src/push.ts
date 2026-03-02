import type { GeneratedOutput, LinearPushConfig, LinearPushResult } from '@gamole/types'
import { LinearClient } from './client'
import type { RelationInput } from './batch'

interface PendingIssue {
  key: string
  title: string
  description?: string
}

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  }

  return String(error)
}

function isRateLimited(error: unknown): boolean {
  if (error === null || typeof error !== 'object') return false

  const checkErrors = (errors: unknown): boolean => {
    if (!Array.isArray(errors)) return false

    return errors.some(
      (entry) =>
        entry !== null &&
        typeof entry === 'object' &&
        'extensions' in entry &&
        (entry as { extensions?: { code?: string } }).extensions?.code ===
          'RATELIMITED',
    )
  }

  if ('response' in error) {
    const response = (error as { response?: unknown }).response
    if (
      response !== null &&
      typeof response === 'object' &&
      'errors' in response &&
      checkErrors((response as { errors: unknown }).errors)
    ) {
      return true
    }
  }

  if ('errors' in error) {
    return checkErrors((error as { errors: unknown }).errors)
  }

  return false
}

function chunk<T>(items: T[], size: number): T[][] {
  const chunks: T[][] = []

  for (let i = 0; i < items.length; i += size) {
    chunks.push(items.slice(i, i + size))
  }

  return chunks
}

function buildPendingIssues(
  output: GeneratedOutput,
): {
  issues: PendingIssue[]
  storyToEpic: Array<{ epicKey: string; storyKey: string }>
} {
  const issues: PendingIssue[] = []
  const storyToEpic: Array<{ epicKey: string; storyKey: string }> = []

  output.epics.forEach((epic, epicIndex) => {
    const epicKey = `epic:${epicIndex}`

    issues.push({
      key: epicKey,
      title: epic.epicTitle,
      description: epic.epicDescription,
    })

    epic.stories.forEach((story, storyIndex) => {
      const storyKey = `story:${epicIndex}:${storyIndex}`

      issues.push({
        key: storyKey,
        title: story.title,
        description: story.description,
      })

      storyToEpic.push({ epicKey, storyKey })
    })
  })

  return { issues, storyToEpic }
}

export async function pushToLinear(
  output: GeneratedOutput,
  config: LinearPushConfig,
  token: string,
): Promise<LinearPushResult> {
  const client = new LinearClient(token)
  const createdIssues: LinearPushResult['createdIssues'] = []
  const createdRelations: LinearPushResult['createdRelations'] = []
  const errors: string[] = []
  const createdByKey = new Map<string, string>()

  const { issues: pendingIssues, storyToEpic } = buildPendingIssues(output)

  const issueBatches = chunk(pendingIssues, 20)

  for (let index = 0; index < issueBatches.length; index++) {
    const batch = issueBatches[index]
    if (!batch) continue

    try {
      const created = await client.batchCreateIssues(
        batch.map((issue) => ({
          title: issue.title,
          description: issue.description,
          teamId: config.teamId,
          projectId: config.projectId,
          stateId: config.stateId,
          labelIds: config.labels,
        })),
      )

      createdIssues.push(
        ...created.map((issue) => ({
          linearId: issue.id,
          identifier: issue.identifier,
          title: issue.title,
        })),
      )

      const createdByTitle = new Map<string, typeof created>()
      for (const item of created) {
        const existing = createdByTitle.get(item.title)
        if (existing) {
          existing.push(item)
        } else {
          createdByTitle.set(item.title, [item])
        }
      }

      for (const pending of batch) {
        const matched = createdByTitle.get(pending.title)
        const next = matched?.shift()

        if (next) {
          createdByKey.set(pending.key, next.id)
        }
      }

      if (created.length !== batch.length) {
        errors.push(
          `Issue batch ${index + 1}: ${batch.length - created.length} issue(s) were not created`,
        )
      }
    } catch (error) {
      const rateLimited = isRateLimited(error)
      errors.push(
        rateLimited
          ? `Issue batch ${index + 1} rate-limited (RATELIMITED): ${toErrorMessage(error)}`
          : `Issue batch ${index + 1} failed: ${toErrorMessage(error)}`,
      )
    }
  }

  const relationInputs: RelationInput[] = []

  for (const pair of storyToEpic) {
    const storyId = createdByKey.get(pair.storyKey)
    const epicId = createdByKey.get(pair.epicKey)

    if (!storyId || !epicId) continue

    relationInputs.push({
      issueId: storyId,
      relatedIssueId: epicId,
      type: 'blocks',
    })
  }

  const relationBatches = chunk(relationInputs, 20)
  for (let index = 0; index < relationBatches.length; index++) {
    const batch = relationBatches[index]
    if (!batch) continue

    try {
      const created = await client.batchCreateRelations(batch)

      createdRelations.push(
        ...created.map((relation) => ({
          id: relation.id,
          type: relation.type,
        })),
      )

      if (created.length !== batch.length) {
        errors.push(
          `Relation batch ${index + 1}: ${batch.length - created.length} relation(s) were not created`,
        )
      }
    } catch (error) {
      const rateLimited = isRateLimited(error)
      errors.push(
        rateLimited
          ? `Relation batch ${index + 1} rate-limited (RATELIMITED): ${toErrorMessage(error)}`
          : `Relation batch ${index + 1} failed: ${toErrorMessage(error)}`,
      )
    }
  }

  return {
    createdIssues,
    createdRelations,
    errors,
  }
}
