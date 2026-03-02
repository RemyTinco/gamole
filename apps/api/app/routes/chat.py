"""Chat with Linear: natural language queries over your Linear workspace."""

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.middleware import auth_dependency

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    token: str | None = Field(
        default=None,
        description="Linear API token (uses server config if omitted)",
    )


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    query_type: str = Field(alias="queryType")  # "live" or "cached" or "combined"

    model_config = {"populate_by_name": True}


# Linear GraphQL fragments the LLM can use
AVAILABLE_QUERIES = """
You have access to the Linear GraphQL API. You can build queries to answer user questions.

Available query patterns:

1. ISSUES BY FILTER:
   issues(filter: { assignee: { id: { eq: "USER_ID" } }, createdAt: { gte: "ISO_DATE" }, team: { name: { eq: "TEAM" } }, state: { type: { in: ["started", "completed", "backlog", "unstarted", "cancelled", "triage"] } } }) { nodes { id identifier title state { name type } assignee { name } creator { name } createdAt updatedAt priority labels { nodes { name } } } }

2. ISSUES BY CREATOR (who created the ticket):
   issues(filter: { creator: { id: { eq: "USER_ID" } }, createdAt: { gte: "ISO_DATE" } }) { nodes { id identifier title creator { name } createdAt } }

3. COUNTING ISSUES:
   There is NO issueCount field. To count issues, query the nodes and count the results array length.
   Example: issues(filter: { ... }) { nodes { id } }

4. TEAMS:
   teams { nodes { id name } }

5. USERS (use to resolve names before querying):
   users { nodes { id name email } }

6. PROJECTS:
   projects { nodes { id name state teams { nodes { name } } } }

7. CYCLES:
   cycles(filter: { team: { name: { eq: "TEAM" } } }) { nodes { id name startsAt endsAt completedScopeHistory } }

CRITICAL DISTINCTIONS:
- "created by" / "X created" / "X's tickets" = use the `creator` filter (who made the ticket)
- "assigned to" / "working on" = use the `assignee` filter (who is responsible)
- When in doubt about created vs assigned, use `creator`

Filter operators: eq, neq, in, nin, contains, containsIgnoreCase, startsWith, gt, gte, lt, lte, and, or

IMPORTANT: When an entity (user, team, project) has been resolved with an ID from the Known Entities
lists below, ALWAYS prefer id-based filters:
  - creator: { id: { eq: "USER_ID" } }    (preferred over name matching)
  - assignee: { id: { eq: "USER_ID" } }   (preferred over name matching)
  - team: { id: { eq: "TEAM_ID" } }        (preferred over name matching)
Only fall back to `containsIgnoreCase` when no ID is available.

Date format: MUST be ISO 8601 (e.g. "2026-02-01T00:00:00Z"). NEVER use relative dates like "3 weeks ago". Always calculate the actual date.

State types: backlog, unstarted, started, completed, cancelled, triage

Priority: 0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low
"""

SYSTEM_PROMPT = f"""You are a Linear workspace assistant. Users ask you questions about their project management data.

Your job:
1. Analyze the user's question
2. Use the Known Entities below to resolve any people, teams, labels, or projects mentioned
3. Build one or more GraphQL queries for the Linear API using resolved IDs when available
4. For broader questions (process, productivity, team improvements), collect evidence first then provide practical recommendations
5. Return a structured response

{AVAILABLE_QUERIES}

IMPORTANT RULES:
- ALWAYS use the exact names and IDs from the "Known Entities" lists when building queries.
- If an ENTITY RESOLUTION HINT suggests a correction (e.g. typo), use the corrected name/ID.
- For questions about counts, dates, assignees, or statuses: use LIVE Linear API queries.
- For questions about content similarity ("tickets like X", "related to Y"): use the search action.
- Always return valid GraphQL. Test your filter syntax mentally before outputting.
- For "last N weeks/days": calculate the date from today and use createdAt gte filter.
- Distinguish between "created" (use creator filter) and "assigned" (use assignee filter).
- To count issues, query nodes with just {{{{ id }}}} and count the array. Do NOT use issueCount — it does not exist.
- For process improvement / coaching questions, DO NOT refuse. Gather data first, then answer with concrete recommendations backed by evidence.
- Return the GraphQL query in a JSON block with key "graphql_query".
- You can run multiple rounds of evidence gathering: query + search + query before final answer.
- After getting results, summarize and analyze them in natural language.

When you need to build a query, output EXACTLY this JSON format:
{{{{"action": "query", "graphql_query": "{{ issues(...) {{ nodes {{ ... }} }} }}"}}}}

When you need semantic retrieval over cached issues/code context, output:
{{{{"action": "search", "query": "technical debt in origination handoff"}}}}

When you have the answer, output:
{{{{"action": "answer", "text": "Your natural language answer here", "details": []}}}}
"""

# Prompt injected after a query returns results, asking the LLM to interpret
INTERPRETATION_PROMPT = """Query result:
{result_json}

{entity_context}

INSTRUCTIONS FOR YOUR ANSWER:
1. Answer the user's original question in natural, conversational language.
2. Be specific: include names, counts, dates, statuses — not vague summaries.
3. If the result contains multiple items, organize them clearly (bullet points or groupings).
4. If the result is EMPTY (0 items):
   - If an entity correction was applied, mention it: "I found 'X' (you wrote 'Y')..."
   - If the entity name doesn't match any known entity, say so: "I couldn't find anyone matching 'X'. Known users are: [list]. Did you mean one of these?"
   - If the entity is valid but truly 0 results, say so clearly with context.
5. Add useful context when possible: trends, priority breakdown, next steps.
6. Never dump raw JSON or GraphQL in your answer.
7. If you auto-corrected a typo, mention it briefly.

Output: {{"action": "answer", "text": "your answer here"}}"""

# Prompt injected when a query returns 0 results — zero-result verification guard
ZERO_RESULT_PROMPT = """Query returned 0 results.

{entity_context}

BEFORE answering '0 results', VERIFY:
1. Is the person/team/label name correct? Check the Known Entities lists above.
2. Is the date filter too narrow? Consider widening it.
3. Is the state filter excluding results?
4. If the name doesn't match any known entity, say so explicitly and suggest alternatives.
5. If the name IS correct and there are truly 0 results, confirm that clearly.

If you need to retry with a corrected name/ID, output a new query.
If you're confident the answer is 0, output: {{"action": "answer", "text": "..."}}"""

ANALYSIS_PROMPT = """User question:
{user_message}

Linear query evidence:
{linear_evidence}

Semantic evidence (similar issues/code context):
{semantic_evidence}

INSTRUCTIONS:
1. Answer directly; do not refuse the question.
2. Ground recommendations in the evidence above.
3. For team/process questions, provide:
   - 2-4 concrete observations
   - 3 actionable improvements for day-to-day work
   - expected impact of each improvement
4. If evidence is weak, state assumptions and suggest what to measure next.
5. Never dump raw JSON or GraphQL in final text.

Output: {{"action": "answer", "text": "your answer here"}}"""

def _extract_action(content: str) -> dict[str, Any] | None:
    """Extract action JSON from LLM output, handling nested quotes in GraphQL."""
    # Strip markdown code fences if present
    text = content.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    # Try standard JSON parsing
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        try:
            return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            pass

    # Fallback: extract graphql_query by matching balanced braces inside the value
    query_match = re.search(r'"graphql_query"\s*:\s*"', text)
    if query_match and '"action"' in text and '"query"' in text:
        start = query_match.end()
        # Find the graphql query: everything from start to the last "}  or "} pattern
        # The query value is between quotes but may contain unescaped quotes,
        # so find the closing pattern: quote + optional whitespace + closing brace
        rest = text[start:]
        # Match up to the final "} of the JSON object
        close_match = re.search(r'"\s*}\s*$', rest)
        if close_match:
            gql = rest[:close_match.start()]
            return {"action": "query", "graphql_query": gql}

    # Fallback: extract answer text
    answer_match = re.search(r'"action"\s*:\s*"answer"', text)
    if answer_match:
        text_match = re.search(r'"text"\s*:\s*"(.*?)"\s*[,}]', text, re.DOTALL)
        if text_match:
            return {"action": "answer", "text": text_match.group(1)}

    return None


async def _execute_linear_query(query: str, token: str) -> dict[str, Any]:
    """Execute a GraphQL query against Linear API."""
    import httpx

    # Normalize: strip markdown fences, handle query wrapping
    q = query.strip()
    if q.startswith("```"):
        q = "\n".join(q.split("\n")[1:])
    if q.endswith("```"):
        q = q.rsplit("```", 1)[0]
    q = q.strip()

    # If LLM output starts with "query {" or "query($", wrap is already there
    if q.startswith("query"):
        full_query = q
    elif not q.startswith("{"):
        full_query = f"{{ {q} }}"
    else:
        full_query = q

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.linear.app/graphql",
            headers={"Authorization": token, "Content-Type": "application/json"},
            json={"query": full_query},
            timeout=15,
        )
        data = resp.json()
        # Return data even on errors so LLM can self-correct
        return data


# ---------------------------------------------------------------------------
# Workspace context loading and entity resolution helpers
# ---------------------------------------------------------------------------


async def _load_workspace_context() -> dict[str, Any]:
    """Load cached workspace entities from DB.

    Returns dict with users/teams/labels/states/projects.
    Teams are enriched with descriptions from LinearTeam table.
    """
    from gamole_linear.sync import get_workspace_entities

    ws = await get_workspace_entities()

    # Also load teams from LinearTeam table (they have descriptions)
    teams: list[dict[str, Any]] = []
    try:
        from sqlalchemy import select

        from gamole_db.models import LinearTeam
        from gamole_db.session import get_session

        async for session in get_session():
            result = await session.execute(
                select(LinearTeam).order_by(LinearTeam.name)
            )
            db_teams = result.scalars().all()
            teams = [
                {"id": t.linear_id, "name": t.name, "description": t.description}
                for t in db_teams
            ]
    except Exception:
        pass

    ws["teams"] = teams or ws.get("teams", [])
    return ws


async def _ensure_minimal_cache(token: str, ws_context: dict[str, Any]) -> dict[str, Any]:
    """Live fallback: if no cached users, fetch entities on-the-fly."""
    if ws_context.get("users"):
        return ws_context

    logger.info("No cached workspace entities — fetching live for this request")
    try:
        from gamole_linear.sync import sync_workspace_entities

        await sync_workspace_entities(token)
        return await _load_workspace_context()
    except Exception:
        logger.warning("Live entity fetch failed", exc_info=True)
    return ws_context


def _format_workspace_context(ctx: dict[str, Any]) -> str:
    """Format all entity lists for injection into the LLM system prompt."""
    sections: list[str] = []

    users = ctx.get("users", [])
    if users:
        lines = [
            f"  - {u.get('name', '?')} (id: {u.get('id', '?')})"
            for u in users
        ]
        sections.append("Known Users:\n" + "\n".join(lines))

    teams = ctx.get("teams", [])
    if teams:
        lines = []
        for t in teams:
            desc = f": {t['description']}" if t.get("description") else ""
            lines.append(
                f"  - {t.get('name', '?')} (id: {t.get('id', '?')}){desc}"
            )
        sections.append("Known Teams:\n" + "\n".join(lines))

    labels = ctx.get("labels", [])
    if labels:
        unique = {lbl.get("name", "?"): lbl.get("id", "?") for lbl in labels}
        lines = [f"  - {name} (id: {lid})" for name, lid in unique.items()]
        sections.append("Known Labels:\n" + "\n".join(lines))

    projects = ctx.get("projects", [])
    if projects:
        lines = [
            f"  - {p.get('name', '?')} (id: {p.get('id', '?')})"
            for p in projects
        ]
        sections.append("Known Projects:\n" + "\n".join(lines))

    if not sections:
        return ""
    return "\n\nKnown Entities:\n" + "\n\n".join(sections)


def _extract_nodes(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract nodes from a Linear GraphQL response for zero-result detection."""
    data = result.get("data", result)
    for key in data:
        val = data[key]
        if isinstance(val, dict) and "nodes" in val:
            return val["nodes"]
    return []


def _looks_like_scope_refusal(answer: str) -> bool:
    text = answer.casefold()
    refusal_phrases = [
        "outside the scope",
        "outside my scope",
        "not equipped",
        "i can't answer",
        "i cannot answer",
        "my capabilities are focused",
    ]
    return any(phrase in text for phrase in refusal_phrases)


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(str(item["text"]))
        return "\n".join(parts)
    return str(content)


async def _chat_with_linear(
    message: str, history: list[ChatMessage], token: str
) -> ChatResponse:
    """Use LLM to convert natural language to Linear queries and answer."""
    import os

    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

    from gamole_ai.retrieval import RetrieveContextOptions, retrieve_context

    api_key = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY", "")
    if not api_key.startswith("AIza"):
        return ChatResponse(
            answer="Gemini API key not configured. Cannot process natural language queries.",
            sources=[],
            queryType="none",
        )

    # Load workspace context (cached entities)
    ws_context = await _load_workspace_context()
    ws_context = await _ensure_minimal_cache(token, ws_context)

    # Build entity resolver for fuzzy matching
    from ..services.entity_resolver import EntityResolver, build_entity_hints

    resolver = EntityResolver(
        users=ws_context.get("users", []),
        teams=ws_context.get("teams", []),
        labels=ws_context.get("labels", []),
        states=ws_context.get("states", []),
        projects=ws_context.get("projects", []),
    )

    # Generate entity correction hints for the user's message
    entity_hints = build_entity_hints(message, resolver)

    # Format the workspace context for injection
    workspace_section = _format_workspace_context(ws_context)

    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today_human = datetime.now(timezone.utc).strftime("%B %d, %Y")

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

    system_content = (
        SYSTEM_PROMPT
        + workspace_section
        + entity_hints
        + f"\n\nToday's date: {today_human} ({today})"
    )

    messages: list[BaseMessage] = [SystemMessage(content=system_content)]

    for h in history[-10:]:
        if h.role == "user":
            messages.append(HumanMessage(content=h.content))
        else:
            messages.append(AIMessage(content=h.content))

    messages.append(HumanMessage(content=message))

    # Step 1: Get the LLM to generate a query plan
    response = await llm.ainvoke(messages)
    content = _content_to_text(response.content)

    all_sources: list[dict[str, Any]] = []
    linear_evidence: list[dict[str, Any]] = []
    semantic_evidence: list[dict[str, Any]] = []
    query_type = "live"
    max_rounds = 5

    # Build entity context string for interpretation prompts
    entity_context = ""
    if entity_hints:
        entity_context = f"Entity corrections applied: {entity_hints}"

    for _ in range(max_rounds):
        action_data = _extract_action(content)
        if action_data is None:
            # No JSON found — LLM gave a natural language answer directly
            break

        if action_data.get("action") == "query" and "graphql_query" in action_data:
            gql = action_data["graphql_query"]
            logger.info(f"Executing Linear query: {gql[:200]}")

            try:
                result = await _execute_linear_query(gql, token)
                all_sources.append({"query": gql, "result": result})
                linear_evidence.append({"query": gql, "result": result})

                if "errors" in result:
                    error_msg = json.dumps(result["errors"])
                    messages.append(AIMessage(content=content))
                    messages.append(HumanMessage(
                        content=(
                            f"Query returned errors: {error_msg}\n\n"
                            "Fix the query and try again. "
                            "Remember to use valid Linear GraphQL syntax."
                        )
                    ))
                    response = await llm.ainvoke(messages)
                    content = _content_to_text(response.content)
                    continue

                # Check for zero results — trigger verification guard
                nodes = _extract_nodes(result)

                if len(nodes) == 0:
                    messages.append(AIMessage(content=content))
                    messages.append(HumanMessage(
                        content=ZERO_RESULT_PROMPT.format(
                            entity_context=entity_context,
                        )
                    ))
                    response = await llm.ainvoke(messages)
                    content = _content_to_text(response.content)
                    continue

                # Ask LLM to interpret the results with rich prompt
                messages.append(AIMessage(content=content))
                messages.append(HumanMessage(
                    content=INTERPRETATION_PROMPT.format(
                        result_json=json.dumps(result, indent=2),
                        entity_context=entity_context,
                    )
                ))
                response = await llm.ainvoke(messages)
                content = _content_to_text(response.content)
                continue

            except Exception as e:
                error_msg = str(e)
                messages.append(AIMessage(content=content))
                messages.append(HumanMessage(
                    content=(
                        f"Query failed with error: {error_msg}\n\n"
                        "Fix the GraphQL query and try again. Common issues: "
                        "wrong field names, invalid filter syntax, "
                        "missing required fields."
                    )
                ))
                response = await llm.ainvoke(messages)
                content = _content_to_text(response.content)
                continue

        elif action_data.get("action") == "search" and "query" in action_data:
            search_query = str(action_data.get("query", "")).strip() or message
            bundle = await retrieve_context(search_query, RetrieveContextOptions(top_k=10))

            search_result = {
                "query": search_query,
                "linearResults": [
                    {
                        "linearId": a.linear_id,
                        "title": a.title,
                        "description": (a.description or "")[:240],
                        "similarity": round(a.similarity, 3),
                        "teamId": a.team_id,
                    }
                    for a in bundle.linear_artifacts
                ],
                "codeResults": [
                    {
                        "repo": c.repo_name,
                        "filePath": c.file_path,
                        "language": c.language,
                        "snippet": c.chunk_text[:240],
                        "similarity": round(c.similarity, 3),
                    }
                    for c in bundle.code_chunks
                ],
            }

            semantic_evidence.append(search_result)
            all_sources.append({"search": search_result})

            messages.append(AIMessage(content=content))
            messages.append(
                HumanMessage(
                    content=(
                        "Search results are now available. Continue reasoning and either "
                        "request another query/search or return an answer.\n\n"
                        f"{json.dumps(search_result, indent=2)}"
                    )
                )
            )
            response = await llm.ainvoke(messages)
            content = _content_to_text(response.content)
            continue

        elif action_data.get("action") == "answer":
            if (
                not all_sources
                and _looks_like_scope_refusal(action_data.get("text", content))
            ):
                messages.append(AIMessage(content=content))
                messages.append(
                    HumanMessage(
                        content=(
                            "Do not refuse. Gather evidence first. Return either a query/search "
                            "action or an evidence-grounded answer."
                        )
                    )
                )
                response = await llm.ainvoke(messages)
                content = _content_to_text(response.content)
                continue

            if all_sources and (linear_evidence or semantic_evidence):
                messages.append(AIMessage(content=content))
                messages.append(
                    HumanMessage(
                        content=ANALYSIS_PROMPT.format(
                            user_message=message,
                            linear_evidence=json.dumps(linear_evidence, indent=2),
                            semantic_evidence=json.dumps(semantic_evidence, indent=2),
                        )
                    )
                )
                response = await llm.ainvoke(messages)
                final_text = _content_to_text(response.content)
                final_action = _extract_action(final_text)
                if final_action and final_action.get("action") == "answer":
                    return ChatResponse(
                        answer=final_action.get("text", final_text),
                        sources=all_sources,
                        queryType=query_type,
                    )

            return ChatResponse(
                answer=action_data.get("text", content),
                sources=all_sources,
                queryType=query_type,
            )

        else:
            # Unknown action — treat as natural language
            break

    # Fallback: return whatever the LLM said
    # Strip any JSON artifacts
    clean_answer = content
    try:
        json_start = content.find("{")
        if json_start >= 0:
            parsed = json.loads(content[json_start:content.rfind("}") + 1])
            if "text" in parsed:
                clean_answer = parsed["text"]
    except Exception:
        pass

    return ChatResponse(
        answer=clean_answer,
        sources=all_sources,
        queryType=query_type,
    )


@router.post("/chat/linear", dependencies=[Depends(auth_dependency)])
async def chat_linear(body: ChatRequest):
    """Chat with your Linear workspace using natural language."""
    from ..config import settings

    token = body.token or settings.linear_api_token
    if not token:
        raise HTTPException(
            status_code=400,
            detail="No Linear token provided and none configured (LINEAR_API_TOKEN env)",
        )

    result = await _chat_with_linear(body.message, body.history, token)
    return result.model_dump(by_alias=True)


@router.post("/chat/search", dependencies=[Depends(auth_dependency)])
async def chat_search(body: ChatRequest):
    """Semantic search across cached Linear issues using natural language."""
    from gamole_ai.retrieval import RetrieveContextOptions, retrieve_context

    bundle = await retrieve_context(body.message, RetrieveContextOptions(top_k=10))

    if not bundle.linear_artifacts:
        return {
            "answer": "No similar issues found. Try syncing your Linear issues first (POST /api/sync/linear).",
            "results": [],
            "queryType": "cached",
        }

    results = [
        {
            "linearId": a.linear_id,
            "title": a.title,
            "description": (a.description or "")[:200],
            "similarity": round(a.similarity, 3),
            "teamId": a.team_id,
        }
        for a in bundle.linear_artifacts
    ]

    # Use LLM to summarize if available
    import os

    if os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY", "").startswith("AIza"):
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        summary_prompt = f"User asked: {body.message}\n\nHere are the most similar Linear issues:\n"
        for r in results[:5]:
            summary_prompt += f"- {r['title']} (similarity: {r['similarity']})\n"
        summary_prompt += "\nBriefly summarize what you found and how it relates to the user's question."

        resp = await llm.ainvoke(summary_prompt)
        answer = resp.content
    else:
        answer = f"Found {len(results)} similar issues."

    return {
        "answer": answer,
        "results": results,
        "queryType": "cached",
    }
