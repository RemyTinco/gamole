/**
 * GraphQL alias batch operation builders for Linear.
 *
 * Linear supports batching multiple mutations in a single request using
 * GraphQL aliases. This module builds those aliased mutation strings + variables.
 *
 * G14: Use `i0: issueCreate(...)` aliases — up to 20 per call.
 * G15: Create relations AFTER all issues are created (two-phase push).
 */

// ---------------------------------------------------------------------------
// Input / Output types
// ---------------------------------------------------------------------------

export interface IssueInput {
  title: string;
  teamId: string;
  description?: string;
  labelIds?: string[];
  stateId?: string;
  projectId?: string;
  /** 0=none 1=urgent 2=high 3=medium 4=low */
  priority?: number;
}

export interface RelationInput {
  issueId: string;
  relatedIssueId: string;
  type: 'blocks' | 'blocked_by' | 'duplicate_of' | 'related';
}

export interface CreatedIssue {
  id: string;
  identifier: string;
  title: string;
}

export interface CreatedRelation {
  id: string;
  type: string;
}

/** Shape returned by each aliased issueCreate */
export interface BatchIssueResult {
  issue: CreatedIssue | null;
  success: boolean;
}

/** Shape returned by each aliased issueRelationCreate */
export interface BatchRelationResult {
  issueRelation: CreatedRelation | null;
  success: boolean;
}

// ---------------------------------------------------------------------------
// Mutation builders
// ---------------------------------------------------------------------------

/**
 * Build a batched issueCreate mutation using GraphQL aliases.
 *
 * Returns the query string and variables object ready for rawRequest.
 * All string values are passed as typed variables to avoid injection.
 */
export function buildBatchIssuesMutation(
  issues: IssueInput[],
): { query: string; variables: Record<string, unknown> } {
  if (issues.length === 0) {
    return { query: 'mutation EmptyBatch { __typename }', variables: {} };
  }

  const varDecls: string[] = [];
  const aliases: string[] = [];
  const variables: Record<string, unknown> = {};

  for (let i = 0; i < issues.length; i++) {
    const issue = issues[i];
    if (!issue) continue;
    const p = `i${i}`;

    // Required fields
    varDecls.push(`$${p}Title: String!`, `$${p}TeamId: String!`);
    variables[`${p}Title`] = issue.title;
    variables[`${p}TeamId`] = issue.teamId;

    const inputFields = [`title: $${p}Title`, `teamId: $${p}TeamId`];

    // Optional string fields
    if (issue.description !== undefined) {
      varDecls.push(`$${p}Desc: String`);
      variables[`${p}Desc`] = issue.description;
      inputFields.push(`description: $${p}Desc`);
    }

    if (issue.stateId !== undefined) {
      varDecls.push(`$${p}StateId: String`);
      variables[`${p}StateId`] = issue.stateId;
      inputFields.push(`stateId: $${p}StateId`);
    }

    if (issue.projectId !== undefined) {
      varDecls.push(`$${p}ProjId: String`);
      variables[`${p}ProjId`] = issue.projectId;
      inputFields.push(`projectId: $${p}ProjId`);
    }

    if (issue.priority !== undefined) {
      varDecls.push(`$${p}Priority: Int`);
      variables[`${p}Priority`] = issue.priority;
      inputFields.push(`priority: $${p}Priority`);
    }

    if (issue.labelIds !== undefined && issue.labelIds.length > 0) {
      varDecls.push(`$${p}Labels: [String!]`);
      variables[`${p}Labels`] = issue.labelIds;
      inputFields.push(`labelIds: $${p}Labels`);
    }

    aliases.push(
      `${p}: issueCreate(input: { ${inputFields.join(', ')} }) {\n` +
        `    issue { id identifier title }\n` +
        `    success\n` +
        `  }`,
    );
  }

  const query =
    `mutation BatchCreateIssues(${varDecls.join(', ')}) {\n` +
    `  ${aliases.join('\n  ')}\n` +
    `}`;

  return { query, variables };
}

/**
 * Build a batched issueRelationCreate mutation using GraphQL aliases.
 *
 * Relation type is inlined as a GraphQL enum value (safe: TypeScript union
 * ensures only valid values reach this function).
 */
export function buildBatchRelationsMutation(
  relations: RelationInput[],
): { query: string; variables: Record<string, unknown> } {
  if (relations.length === 0) {
    return { query: 'mutation EmptyBatch { __typename }', variables: {} };
  }

  const varDecls: string[] = [];
  const aliases: string[] = [];
  const variables: Record<string, unknown> = {};

  for (let i = 0; i < relations.length; i++) {
    const rel = relations[i];
    if (!rel) continue;
    const p = `r${i}`;

    varDecls.push(`$${p}IssueId: String!`, `$${p}RelatedId: String!`);
    variables[`${p}IssueId`] = rel.issueId;
    variables[`${p}RelatedId`] = rel.relatedIssueId;

    // type is an enum: inline it safely (TypeScript union prevents injection)
    aliases.push(
      `${p}: issueRelationCreate(input: { issueId: $${p}IssueId, relatedIssueId: $${p}RelatedId, type: ${rel.type} }) {\n` +
        `    issueRelation { id type }\n` +
        `    success\n` +
        `  }`,
    );
  }

  const query =
    `mutation BatchCreateRelations(${varDecls.join(', ')}) {\n` +
    `  ${aliases.join('\n  ')}\n` +
    `}`;

  return { query, variables };
}

// ---------------------------------------------------------------------------
// Result parsers
// ---------------------------------------------------------------------------

/** Extract successfully created issues from a raw batch result record. */
export function parseBatchIssueResults(
  data: Record<string, unknown>,
): CreatedIssue[] {
  const results: CreatedIssue[] = [];
  for (const key of Object.keys(data)) {
    const item = data[key] as BatchIssueResult | undefined;
    if (item?.success && item.issue) {
      results.push(item.issue);
    }
  }
  return results;
}

/** Extract successfully created relations from a raw batch result record. */
export function parseBatchRelationResults(
  data: Record<string, unknown>,
): CreatedRelation[] {
  const results: CreatedRelation[] = [];
  for (const key of Object.keys(data)) {
    const item = data[key] as BatchRelationResult | undefined;
    if (item?.success && item.issueRelation) {
      results.push(item.issueRelation);
    }
  }
  return results;
}
