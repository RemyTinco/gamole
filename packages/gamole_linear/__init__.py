"""Gamole Linear - httpx GraphQL client (replaces @linear/sdk)."""

from .batch import (
    CreatedIssue,
    CreatedRelation,
    IssueInput,
    RelationInput,
    build_batch_issues_mutation,
    build_batch_relations_mutation,
    parse_batch_issue_results,
    parse_batch_relation_results,
)
from .client import LinearClient
from .push import push_to_linear
from .sync import SyncStats, sync_linear_issues

__all__ = [
    "CreatedIssue",
    "CreatedRelation",
    "IssueInput",
    "LinearClient",
    "RelationInput",
    "SyncStats",
    "build_batch_issues_mutation",
    "build_batch_relations_mutation",
    "parse_batch_issue_results",
    "parse_batch_relation_results",
    "push_to_linear",
    "sync_linear_issues",
]
