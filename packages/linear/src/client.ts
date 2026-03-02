/**
 * @gamole/linear — LinearClient
 *
 * Typed wrapper around @linear/sdk with:
 * - Pagination helpers (Relay cursor)
 * - Batch mutations via GraphQL aliases (G14)
 * - Rate-limit retry with exponential backoff (G16)
 *
 * RULES:
 * - Accept token as constructor param — never read from env (G10)
 * - One-way push only — NO webhooks, NO sync-back (G9, G17)
 * - Rate limit = HTTP 400 + errors[].extensions.code === "RATELIMITED" (G16)
 */

import { LinearClient as LinearSDKClient } from '@linear/sdk';
import {
  buildBatchIssuesMutation,
  buildBatchRelationsMutation,
  parseBatchIssueResults,
  parseBatchRelationResults,
} from './batch';
import type {
  IssueInput,
  RelationInput,
  CreatedIssue,
  CreatedRelation,
  BatchIssueResult,
  BatchRelationResult,
} from './batch';

// Re-export input/output types for consumers
export type {
  IssueInput,
  RelationInput,
  CreatedIssue,
  CreatedRelation,
  BatchIssueResult,
  BatchRelationResult,
} from './batch';

// ---------------------------------------------------------------------------
// Public filter / page types
// ---------------------------------------------------------------------------

export interface IssueFilter {
  teamId?: string;
  updatedAfter?: Date;
  /** Relay cursor from previous page */
  cursor?: string;
}

export interface IssueSummary {
  id: string;
  identifier: string;
  title: string;
  description: string | undefined;
  updatedAt: Date;
  createdAt: Date;
}

export interface IssuesPage {
  issues: IssueSummary[];
  /** Relay cursor for the next page, undefined when no more pages */
  cursor: string | undefined;
  hasNextPage: boolean;
}

// ---------------------------------------------------------------------------
// Internal raw-client interface
// ---------------------------------------------------------------------------

/** Minimal interface for the graphql-request client embedded in LinearSDKClient */
interface RawGraphQLClient {
  rawRequest<T>(
    query: string,
    variables?: Record<string, unknown>,
  ): Promise<{ data: T } | T>;
}

// ---------------------------------------------------------------------------
// Rate-limit helpers (G16)
// ---------------------------------------------------------------------------

/**
 * Linear returns HTTP 400 (NOT 429) for rate limiting.
 * Detect by checking errors[].extensions.code === "RATELIMITED".
 */
function isRateLimited(error: unknown): boolean {
  if (error === null || typeof error !== 'object') return false;

  const checkErrors = (errors: unknown): boolean => {
    if (!Array.isArray(errors)) return false;
    return errors.some(
      (e) =>
        e !== null &&
        typeof e === 'object' &&
        'extensions' in e &&
        (e as { extensions?: { code?: string } }).extensions?.code ===
          'RATELIMITED',
    );
  };

  // graphql-request wraps errors in error.response.errors
  if ('response' in error) {
    const response = (error as { response?: unknown }).response;
    if (
      response !== null &&
      typeof response === 'object' &&
      'errors' in response
    ) {
      if (checkErrors((response as { errors: unknown }).errors)) return true;
    }
  }

  // Some SDK versions surface errors directly on the error object
  if ('errors' in error) {
    if (checkErrors((error as { errors: unknown }).errors)) return true;
  }

  return false;
}

/**
 * Exponential backoff retry: 3 retries, delays 2s / 4s / 8s.
 * Only retries on rate-limit errors; all other errors propagate immediately.
 */
async function withRetry<T>(fn: () => Promise<T>): Promise<T> {
  const delays = [2_000, 4_000, 8_000] as const;
  let lastError: unknown = new Error('Retry exhausted without attempt');

  for (let attempt = 0; attempt <= delays.length; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;

      if (isRateLimited(err) && attempt < delays.length) {
        const ms = delays[attempt as 0 | 1 | 2];
        await new Promise<void>((resolve) => setTimeout(resolve, ms));
        continue;
      }

      throw err;
    }
  }

  throw lastError;
}

// ---------------------------------------------------------------------------
// LinearClient
// ---------------------------------------------------------------------------

export class LinearClient {
  private readonly sdkClient: LinearSDKClient;

  /**
   * @param token  Linear personal API key or OAuth token.
   *               Passed directly — never stored in env vars.
   */
  constructor(token: string) {
    this.sdkClient = new LinearSDKClient({ apiKey: token });
  }

  // -------------------------------------------------------------------------
  // Read helpers
  // -------------------------------------------------------------------------

  /** List all teams accessible with the provided token. */
  async getTeams() {
    return withRetry(async () => {
      const conn = await this.sdkClient.teams();
      return conn.nodes;
    });
  }

  /** List projects for a specific team. */
  async getProjects(teamId: string) {
    return withRetry(async () => {
      const team = await this.sdkClient.team(teamId);
      const conn = await team.projects();
      return conn.nodes;
    });
  }

  /**
   * Paginated issue listing with optional team/date/cursor filter.
   * Uses Relay cursor pagination (first: 50, after: cursor).
   */
  async getIssues(filter: IssueFilter): Promise<IssuesPage> {
    return withRetry(async () => {
      // Build the SDK filter object — cast to `any` at the boundary because
      // LinearSDKClient.issues() expects deeply-nested generated filter types
      // that would require importing dozens of type aliases from the SDK.
      const sdkFilter: Record<string, unknown> = {};

      if (filter.teamId !== undefined) {
        sdkFilter['team'] = { id: { eq: filter.teamId } };
      }
      if (filter.updatedAfter !== undefined) {
        sdkFilter['updatedAt'] = { gt: filter.updatedAfter.toISOString() };
      }

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const result = await this.sdkClient.issues({
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        filter: sdkFilter as any,
        first: 50,
        after: filter.cursor,
      });

      const issues: IssueSummary[] = result.nodes.map((issue) => ({
        id: issue.id,
        identifier: issue.identifier,
        title: issue.title,
        description: issue.description ?? undefined,
        updatedAt: issue.updatedAt,
        createdAt: issue.createdAt,
      }));

      return {
        issues,
        cursor: result.pageInfo.endCursor ?? undefined,
        hasNextPage: result.pageInfo.hasNextPage,
      };
    });
  }

  /** List all issue labels for a team. */
  async getLabels(teamId: string) {
    return withRetry(async () => {
      const team = await this.sdkClient.team(teamId);
      const conn = await team.labels();
      return conn.nodes;
    });
  }

  /** List all workflow states for a team. */
  async getStates(teamId: string) {
    return withRetry(async () => {
      const team = await this.sdkClient.team(teamId);
      const conn = await team.states();
      return conn.nodes;
    });
  }

  // -------------------------------------------------------------------------
  // Write helpers
  // -------------------------------------------------------------------------

  /**
   * Batch-create issues using GraphQL aliases (max 20 per call).
   * Automatically chunks larger arrays.
   *
   * G14: alias pattern — `i0: issueCreate(input: {...}) { issue { id } success }`
   */
  async batchCreateIssues(issues: IssueInput[]): Promise<CreatedIssue[]> {
    const CHUNK = 20;
    const results: CreatedIssue[] = [];

    for (let i = 0; i < issues.length; i += CHUNK) {
      const chunk = issues.slice(i, i + CHUNK);
      const { query, variables } = buildBatchIssuesMutation(chunk);

      const data = await withRetry(async () => {
        const raw = await this.executeRaw<Record<string, BatchIssueResult>>(
          query,
          variables,
        );
        return raw;
      });

      results.push(...parseBatchIssueResults(data as Record<string, unknown>));
    }

    return results;
  }

  /**
   * Batch-create issue relations using GraphQL aliases (max 20 per call).
   * Create AFTER all issues exist (G15: two-phase push).
   */
  async batchCreateRelations(
    relations: RelationInput[],
  ): Promise<CreatedRelation[]> {
    const CHUNK = 20;
    const results: CreatedRelation[] = [];

    for (let i = 0; i < relations.length; i += CHUNK) {
      const chunk = relations.slice(i, i + CHUNK);
      const { query, variables } = buildBatchRelationsMutation(chunk);

      const data = await withRetry(async () => {
        const raw = await this.executeRaw<Record<string, BatchRelationResult>>(
          query,
          variables,
        );
        return raw;
      });

      results.push(
        ...parseBatchRelationResults(data as Record<string, unknown>),
      );
    }

    return results;
  }

  /**
   * Add a comment to an issue.
   */
  async createComment(
    issueId: string,
    body: string,
  ): Promise<{ id: string }> {
    return withRetry(async () => {
      const payload = await this.sdkClient.createComment({ issueId, body });
      const comment = await payload.comment;
      if (!comment) {
        throw new Error(`createComment returned no comment for issue ${issueId}`);
      }
      return { id: comment.id };
    });
  }

  // -------------------------------------------------------------------------
  // Private helpers
  // -------------------------------------------------------------------------

  /**
   * Execute a raw GraphQL request via the underlying SDK client.
   *
   * The SDK wraps graphql-request; rawRequest may return `{ data: T }` or
   * `T` directly depending on SDK version. We normalise to always return T.
   */
  private async executeRaw<T>(
    query: string,
    variables?: Record<string, unknown>,
  ): Promise<T> {
    // Access the underlying GraphQL client via the SDK's .client property.
    // We use an unknown cast because the SDK types LinearGraphQLClient with
    // elaborate generics that aren't worth reproducing here.
    const raw = this.sdkClient.client as unknown as RawGraphQLClient;
    const result = await raw.rawRequest<T>(query, variables);

    // graphql-request v7 rawRequest returns ClientRawResponse<T> with .data
    if (
      result !== null &&
      typeof result === 'object' &&
      'data' in result &&
      result.data !== undefined
    ) {
      return (result as { data: T }).data;
    }

    return result as T;
  }
}
