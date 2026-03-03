"""Two-phase push to Linear - ported from packages/linear/src/push.ts.

G15: Create all issues first, then create relations.
G16: Rate limit = HTTP 400 with RATELIMITED code.

Supports per-epic team routing and cross-team project creation.
"""

from gamole_types import GeneratedOutput, LinearPushConfig, LinearPushResult
from gamole_types.schemas.linear import CreatedIssueInfo, CreatedRelationInfo

from .batch import IssueInput, RelationInput
from .client import LinearClient


def _is_rate_limited(error: Exception) -> bool:
    msg = str(error)
    return "RATELIMITED" in msg


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def _resolve_team_id(team_name: str | None, fallback_team_id: str | None) -> str | None:
    """Resolve a team name to a Linear team ID using stored team mappings."""
    if not team_name:
        return fallback_team_id

    try:
        from sqlalchemy import func as sa_func
        from sqlalchemy import select

        from gamole_db.models import LinearTeam
        from gamole_db.session import get_session

        async for session in get_session():
            # Exact match
            result = await session.execute(
                select(LinearTeam).where(LinearTeam.name == team_name)
            )
            team = result.scalar_one_or_none()
            if team:
                return team.linear_id

            # Case-insensitive match
            result = await session.execute(
                select(LinearTeam).where(
                    sa_func.lower(LinearTeam.name) == team_name.lower()
                )
            )
            team = result.scalar_one_or_none()
            if team:
                return team.linear_id
    except Exception:
        pass

    return fallback_team_id


async def _create_project(client: LinearClient, name: str, team_ids: list[str]) -> str | None:
    """Create a Linear project and return its ID. Returns None on failure."""
    try:
        # Use the first team as the creator, project is cross-team
        query = """
        mutation($name: String!, $teamIds: [String!]!) {
            projectCreate(input: { name: $name, teamIds: $teamIds }) {
                success
                project { id }
            }
        }
        """
        result = await client.raw_query(query, {"name": name, "teamIds": team_ids})
        project_data = result.get("data", {}).get("projectCreate", {})
        if project_data.get("success"):
            return project_data.get("project", {}).get("id")
    except Exception:
        pass
    return None


async def push_to_linear(
    output: GeneratedOutput,
    config: LinearPushConfig,
    token: str,
) -> LinearPushResult:
    """Push generated output to Linear using two-phase approach with per-epic team routing."""
    client = LinearClient(token)
    created_issues: list[CreatedIssueInfo] = []
    created_relations: list[CreatedRelationInfo] = []
    errors: list[str] = []
    created_by_key: dict[str, str] = {}

    # Resolve team IDs per epic
    epic_team_ids: dict[int, str | None] = {}
    unique_team_ids: set[str] = set()
    for idx, epic in enumerate(output.epics):
        resolved = await _resolve_team_id(epic.team_name, config.team_id)
        epic_team_ids[idx] = resolved
        if resolved:
            unique_team_ids.add(resolved)

    # Create project if cross-team and projectName is set
    project_id = config.project_id
    if output.project_name and len(unique_team_ids) > 1 and not project_id:
        project_id = await _create_project(
            client, output.project_name, list(unique_team_ids)
        )
        if project_id:
            errors.append(f"Created cross-team project: {output.project_name}")

    # Build pending issues with per-epic team routing
    pending_issues: list[dict] = []
    story_to_epic: list[dict] = []
    missing_teams: list[str] = []

    for epic_idx, epic in enumerate(output.epics):
        team_id = epic_team_ids.get(epic_idx) or config.team_id
        if not team_id:
            missing_teams.append(epic.epic_title or f"Epic {epic_idx + 1}")
            continue
        epic_key = f"epic:{epic_idx}"
        pending_issues.append({
            "key": epic_key,
            "title": epic.epic_title,
            "description": epic.epic_description,
            "team_id": team_id,
        })
        for story_idx, story in enumerate(epic.stories):
            story_key = f"story:{epic_idx}:{story_idx}"
            pending_issues.append({
                "key": story_key,
                "title": story.title,
                "description": story.description,
                "team_id": team_id,
            })
            story_to_epic.append({"epicKey": epic_key, "storyKey": story_key})

    if missing_teams:
        team_list = ", ".join(missing_teams)
        errors.append(
            f"No team ID resolved for: {team_list}. "
            f"Set a default teamId in push config or sync teams first."
        )

    if not pending_issues:
        await client.close()
        return LinearPushResult(
            createdIssues=created_issues,
            createdRelations=created_relations,
            errors=errors,
        )
    # Phase 1: Create issues in batches of 20
    batches = _chunk(pending_issues, 20)
    for batch_idx, batch in enumerate(batches):
        try:
            issue_inputs = [
                IssueInput(
                    title=item["title"],
                    description=item.get("description"),
                    team_id=item["team_id"],
                    project_id=project_id,
                    state_id=config.state_id,
                    label_ids=config.labels,
                )
                for item in batch
            ]
            created = await client.batch_create_issues(issue_inputs)

            for ci in created:
                created_issues.append(
                    CreatedIssueInfo(linearId=ci.id, identifier=ci.identifier, title=ci.title)
                )

            # Map created by title
            created_by_title: dict[str, list] = {}
            for item in created:
                created_by_title.setdefault(item.title, []).append(item)

            for pending in batch:
                matched = created_by_title.get(pending["title"], [])
                if matched:
                    next_item = matched.pop(0)
                    created_by_key[pending["key"]] = next_item.id

            if len(created) != len(batch):
                errors.append(
                    f"Issue batch {batch_idx + 1}: {len(batch) - len(created)} issue(s) were not created"
                )
        except Exception as e:
            rate_limited = _is_rate_limited(e)
            errors.append(
                f"Issue batch {batch_idx + 1} {'rate-limited (RATELIMITED)' if rate_limited else 'failed'}: {e}"
            )

    # Phase 2: Create relations
    relation_inputs: list[RelationInput] = []
    for pair in story_to_epic:
        story_id = created_by_key.get(pair["storyKey"])
        epic_id = created_by_key.get(pair["epicKey"])
        if story_id and epic_id:
            relation_inputs.append(
                RelationInput(issue_id=story_id, related_issue_id=epic_id, type="blocks")
            )

    rel_batches = _chunk(relation_inputs, 20)
    for batch_idx, batch in enumerate(rel_batches):
        try:
            created = await client.batch_create_relations(batch)
            for cr in created:
                created_relations.append(CreatedRelationInfo(id=cr.id, type=cr.type))
            if len(created) != len(batch):
                errors.append(
                    f"Relation batch {batch_idx + 1}: {len(batch) - len(created)} relation(s) were not created"
                )
        except Exception as e:
            rate_limited = _is_rate_limited(e)
            errors.append(
                f"Relation batch {batch_idx + 1} {'rate-limited (RATELIMITED)' if rate_limited else 'failed'}: {e}"
            )

    await client.close()

    return LinearPushResult(
        createdIssues=created_issues,
        createdRelations=created_relations,
        errors=errors,
    )
