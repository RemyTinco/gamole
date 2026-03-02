/**
 * @gamole/linear — barrel export
 *
 * Re-exports everything from client.ts and batch.ts so consumers can do:
 *   import { LinearClient, IssueInput, buildBatchIssuesMutation } from '@gamole/linear';
 */

export {
  LinearClient,
  type IssueFilter,
  type IssueSummary,
  type IssuesPage,
} from './client';

export {
  buildBatchIssuesMutation,
  buildBatchRelationsMutation,
  parseBatchIssueResults,
  parseBatchRelationResults,
  type IssueInput,
  type RelationInput,
  type CreatedIssue,
  type CreatedRelation,
  type BatchIssueResult,
  type BatchRelationResult,
} from './batch';

export { syncLinearIssues, type SyncStats } from './sync';
export { pushToLinear } from './push';
