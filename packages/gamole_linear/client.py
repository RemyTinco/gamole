"""Linear GraphQL client - ported from packages/linear/src/client.ts.

Uses httpx + raw GraphQL (no Python Linear SDK).
G16: Rate limit = HTTP 400 + errors[].extensions.code === "RATELIMITED"
"""

import asyncio
from dataclasses import dataclass

import httpx

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

API_URL = "https://api.linear.app/graphql"


def _is_rate_limited(error: Exception) -> bool:
    """Linear returns HTTP 400 (NOT 429) for rate limiting."""
    if isinstance(error, httpx.HTTPStatusError):
        try:
            body = error.response.json()
            errors = body.get("errors", [])
            return any(
                isinstance(e, dict)
                and e.get("extensions", {}).get("code") == "RATELIMITED"
                for e in errors
            )
        except Exception:
            pass
    return False


async def _with_retry(fn, delays=(2, 4, 8)):
    last_error = None
    for attempt in range(len(delays) + 1):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            if _is_rate_limited(e) and attempt < len(delays):
                await asyncio.sleep(delays[attempt])
                continue
            raise
    raise last_error


@dataclass
class IssueSummary:
    id: str
    identifier: str
    title: str
    description: str | None
    updated_at: str
    created_at: str


@dataclass
class IssuesPage:
    issues: list[IssueSummary]
    cursor: str | None
    has_next_page: bool


class LinearClient:
    """Typed wrapper around Linear GraphQL API."""

    def __init__(self, token: str):
        self._client = httpx.AsyncClient(
            headers={"Authorization": token, "Content-Type": "application/json"},
            timeout=30.0,
        )

    async def _raw_request(self, query: str, variables: dict | None = None) -> dict:
        response = await self._client.post(
            API_URL,
            json={"query": query, "variables": variables or {}},
        )
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            errors = data["errors"]
            # Check for rate limiting
            if any(e.get("extensions", {}).get("code") == "RATELIMITED" for e in errors):
                raise httpx.HTTPStatusError(
                    "Rate limited", request=response.request, response=response
                )
            # If data is null/missing, raise with the GraphQL error messages
            if data.get("data") is None:
                error_msgs = "; ".join(e.get("message", "Unknown error") for e in errors)
                raise RuntimeError(f"GraphQL errors: {error_msgs}")
        return data.get("data") or {}

    async def get_issues(
        self,
        cursor: str | None = None,
        team_id: str | None = None,
        updated_after: str | None = None,
    ) -> IssuesPage:
        """Paginated issue listing. updated_after is ISO 8601 for incremental sync."""
        filter_parts = []
        variables: dict = {"first": 50}
        if cursor:
            variables["after"] = cursor
        if team_id:
            filter_parts.append(f'team: {{ id: {{ eq: "{team_id}" }} }}')
        if updated_after:
            filter_parts.append(f'updatedAt: {{ gte: "{updated_after}" }}')

        filter_str = ", ".join(filter_parts)
        filter_arg = f", filter: {{ {filter_str} }}" if filter_str else ""

        query = f"""
        query($first: Int!, $after: String) {{
            issues(first: $first, after: $after{filter_arg}) {{
                nodes {{
                    id identifier title description updatedAt createdAt
                }}
                pageInfo {{ endCursor hasNextPage }}
            }}
        }}
        """

        return await _with_retry(lambda: self._fetch_issues(query, variables))

    async def _fetch_issues(self, query: str, variables: dict) -> IssuesPage:
        data = await self._raw_request(query, variables)
        issues_data = data.get("issues", {})
        nodes = issues_data.get("nodes", [])
        page_info = issues_data.get("pageInfo", {})

        issues = [
            IssueSummary(
                id=n["id"],
                identifier=n["identifier"],
                title=n["title"],
                description=n.get("description"),
                updated_at=n["updatedAt"],
                created_at=n["createdAt"],
            )
            for n in nodes
        ]

        return IssuesPage(
            issues=issues,
            cursor=page_info.get("endCursor"),
            has_next_page=page_info.get("hasNextPage", False),
        )

    async def batch_create_issues(self, issues: list[IssueInput]) -> list[CreatedIssue]:
        """Batch-create issues using GraphQL aliases (max 20 per call)."""
        chunk_size = 20
        results: list[CreatedIssue] = []

        for i in range(0, len(issues), chunk_size):
            chunk = issues[i : i + chunk_size]
            mutation = build_batch_issues_mutation(chunk)

            data = await _with_retry(
                lambda: self._raw_request(mutation["query"], mutation["variables"])
            )
            results.extend(parse_batch_issue_results(data))

        return results

    async def batch_create_relations(self, relations: list[RelationInput]) -> list[CreatedRelation]:
        """Batch-create issue relations using GraphQL aliases (max 20 per call)."""
        chunk_size = 20
        results: list[CreatedRelation] = []

        for i in range(0, len(relations), chunk_size):
            chunk = relations[i : i + chunk_size]
            mutation = build_batch_relations_mutation(chunk)

            data = await _with_retry(
                lambda: self._raw_request(mutation["query"], mutation["variables"])
            )
            results.extend(parse_batch_relation_results(data))

        return results

    async def raw_query(self, query: str, variables: dict | None = None) -> dict:
        """Execute a raw GraphQL query and return the full response."""
        response = await self._client.post(
            API_URL,
            json={"query": query, "variables": variables or {}},
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self._client.aclose()
