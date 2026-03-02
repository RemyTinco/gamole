"""Structurer agent: converts refined prose into structured GeneratedOutput (epics + stories).

Assigns each epic to the most appropriate Linear team and suggests a project name for cross-team work.
"""

import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from gamole_types.schemas.generated import GeneratedOutput

from .types import FLASH_MODEL

STRUCTURER_PROMPT = """You are a requirements structuring engine. Given a refined requirements
document (user stories, acceptance criteria, technical notes), break it down into epics and stories.

Rules:
- Group related stories under epics
- Each epic needs a title and description
- Each story needs a title, description, acceptance criteria, assumptions, and optional technical notes
- Preserve all detail from the source document, do not summarize or lose information
- If the document only describes one feature, create one epic with multiple stories
- Stories should be small enough for a single sprint (1-2 weeks of work)

{team_context}"""

TEAM_CONTEXT_TEMPLATE = """Available Linear teams:
{team_list}

IMPORTANT: For each epic, assign the most appropriate team in the teamName and teamReason fields.
Different epics in the same output CAN and SHOULD go to different teams when the work spans multiple domains.
If multiple teams are involved, suggest a projectName for cross-team coordination (e.g. "Settlement Email Notifications").
If all epics belong to one team, projectName can be null."""

NO_TEAM_CONTEXT = """No team information available. Leave teamName as null for all epics."""


def _mock_output() -> GeneratedOutput:
    from gamole_types.schemas.generated import GeneratedEpic, GeneratedStory

    return GeneratedOutput(
        epics=[
            GeneratedEpic(
                epicTitle="Default Epic",
                epicDescription="Auto-generated from unstructured document",
                stories=[
                    GeneratedStory(
                        title="Implement feature",
                        description="Implement the described feature",
                        acceptanceCriteria=["Feature works as described"],
                        assumptions=["Standard tech stack"],
                    )
                ],
            )
        ],
    )


async def _get_team_context() -> str:
    """Fetch team descriptions from DB for agent context."""
    try:
        from sqlalchemy import select

        from gamole_db.models import LinearTeam
        from gamole_db.session import get_session

        async for session in get_session():
            result = await session.execute(select(LinearTeam).order_by(LinearTeam.name))
            teams = result.scalars().all()
            if not teams:
                return NO_TEAM_CONTEXT
            team_lines = [f"- {t.name}: {t.description}" for t in teams]
            return TEAM_CONTEXT_TEMPLATE.format(team_list="\n".join(team_lines))
    except Exception:
        return NO_TEAM_CONTEXT


async def run(document: str) -> GeneratedOutput:
    """Convert refined prose document into structured epics/stories with per-epic team assignments."""
    api_key = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY", "")
    if not api_key.startswith("AIza"):
        return _mock_output()

    team_context = await _get_team_context()

    try:
        llm = ChatGoogleGenerativeAI(model=FLASH_MODEL, temperature=0)
        structured_llm = llm.with_structured_output(GeneratedOutput)
        system_prompt = STRUCTURER_PROMPT.format(team_context=team_context)
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "Break this refined requirements document into structured epics and stories:\n\n{document}"),
        ])
        chain = prompt | structured_llm
        result = await chain.ainvoke({"document": document})
        if isinstance(result, GeneratedOutput):
            return result
        return _mock_output()
    except Exception:
        return _mock_output()
