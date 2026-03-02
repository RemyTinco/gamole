"""GraphQL alias batch builders - ported from packages/linear/src/batch.ts.

G14: Use `i0: issueCreate(...)` aliases — up to 20 per call.
G15: Create relations AFTER all issues are created (two-phase push).
"""

from dataclasses import dataclass


@dataclass
class IssueInput:
    title: str
    team_id: str
    description: str | None = None
    label_ids: list[str] | None = None
    state_id: str | None = None
    project_id: str | None = None
    priority: int | None = None


@dataclass
class RelationInput:
    issue_id: str
    related_issue_id: str
    type: str  # blocks | blocked_by | duplicate_of | related


@dataclass
class CreatedIssue:
    id: str
    identifier: str
    title: str


@dataclass
class CreatedRelation:
    id: str
    type: str


def build_batch_issues_mutation(issues: list[IssueInput]) -> dict:
    """Build a batched issueCreate mutation using GraphQL aliases."""
    if not issues:
        return {"query": "mutation EmptyBatch { __typename }", "variables": {}}

    var_decls: list[str] = []
    aliases: list[str] = []
    variables: dict = {}

    for i, issue in enumerate(issues):
        p = f"i{i}"

        var_decls.extend([f"${p}Title: String!", f"${p}TeamId: String!"])
        variables[f"{p}Title"] = issue.title
        variables[f"{p}TeamId"] = issue.team_id

        input_fields = [f"title: ${p}Title", f"teamId: ${p}TeamId"]

        if issue.description is not None:
            var_decls.append(f"${p}Desc: String")
            variables[f"{p}Desc"] = issue.description
            input_fields.append(f"description: ${p}Desc")

        if issue.state_id is not None:
            var_decls.append(f"${p}StateId: String")
            variables[f"{p}StateId"] = issue.state_id
            input_fields.append(f"stateId: ${p}StateId")

        if issue.project_id is not None:
            var_decls.append(f"${p}ProjId: String")
            variables[f"{p}ProjId"] = issue.project_id
            input_fields.append(f"projectId: ${p}ProjId")

        if issue.priority is not None:
            var_decls.append(f"${p}Priority: Int")
            variables[f"{p}Priority"] = issue.priority
            input_fields.append(f"priority: ${p}Priority")

        if issue.label_ids:
            var_decls.append(f"${p}Labels: [String!]")
            variables[f"{p}Labels"] = issue.label_ids
            input_fields.append(f"labelIds: ${p}Labels")

        fields_str = ", ".join(input_fields)
        aliases.append(
            f"  {p}: issueCreate(input: {{ {fields_str} }}) {{\n"
            f"    issue {{ id identifier title }}\n"
            f"    success\n"
            f"  }}"
        )

    var_str = ", ".join(var_decls)
    query = f"mutation BatchCreateIssues({var_str}) {{\n" + "\n".join(aliases) + "\n}"

    return {"query": query, "variables": variables}


def build_batch_relations_mutation(relations: list[RelationInput]) -> dict:
    """Build a batched issueRelationCreate mutation using GraphQL aliases."""
    if not relations:
        return {"query": "mutation EmptyBatch { __typename }", "variables": {}}

    var_decls: list[str] = []
    aliases: list[str] = []
    variables: dict = {}

    for i, rel in enumerate(relations):
        p = f"r{i}"

        var_decls.extend([f"${p}IssueId: String!", f"${p}RelatedId: String!"])
        variables[f"{p}IssueId"] = rel.issue_id
        variables[f"{p}RelatedId"] = rel.related_issue_id

        aliases.append(
            f"  {p}: issueRelationCreate(input: {{ issueId: ${p}IssueId, relatedIssueId: ${p}RelatedId, type: {rel.type} }}) {{\n"
            f"    issueRelation {{ id type }}\n"
            f"    success\n"
            f"  }}"
        )

    var_str = ", ".join(var_decls)
    query = f"mutation BatchCreateRelations({var_str}) {{\n" + "\n".join(aliases) + "\n}"

    return {"query": query, "variables": variables}


def parse_batch_issue_results(data: dict) -> list[CreatedIssue]:
    """Extract successfully created issues from a raw batch result."""
    results: list[CreatedIssue] = []
    for key, value in data.items():
        if isinstance(value, dict) and value.get("success") and value.get("issue"):
            issue = value["issue"]
            results.append(CreatedIssue(
                id=issue["id"],
                identifier=issue["identifier"],
                title=issue["title"],
            ))
    return results


def parse_batch_relation_results(data: dict) -> list[CreatedRelation]:
    """Extract successfully created relations from a raw batch result."""
    results: list[CreatedRelation] = []
    for key, value in data.items():
        if isinstance(value, dict) and value.get("success") and value.get("issueRelation"):
            rel = value["issueRelation"]
            results.append(CreatedRelation(id=rel["id"], type=rel["type"]))
    return results
