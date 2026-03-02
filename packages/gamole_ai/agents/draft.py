"""Draft agent - ported from packages/ai/src/agents/draft.ts."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from .types import FLASH_MODEL, AgentInput, AgentOutput, critiques_to_text, has_google_api_key

DRAFT_AGENT_PROMPT = """You are a senior product manager specializing in agile requirements.
Given a feature request and context, generate clear, delivery-ready user stories
in the format: As a [user], I want [action] so that [benefit]. Include acceptance
criteria, technical notes, and out-of-scope items.

The context may include:
- Similar existing Linear issues (use these to match naming conventions and scope)
- Relevant code chunks from the codebase (use these for accurate technical notes)
- Repository descriptions (use these to understand the tech stack and reference specific repos in technical notes)"""


def _build_fallback(input: AgentInput, critique: str) -> AgentOutput:
    return AgentOutput(
        revised_doc=input.document or "Mock draft user story output",
        critique=critique,
        risk_flags=[],
        confidence=0.8,
        ready=False,
    )


async def run(input: AgentInput) -> AgentOutput:
    if not has_google_api_key():
        return _build_fallback(input, "Mock draft generated because GOOGLE_GENERATIVE_AI_API_KEY is unavailable.")

    prompt_text = "\n\n".join([
        f"Feature request:\n{input.document}",
        f"Context:\n{input.context}",
        f"Round: {input.round}",
        f"Previous critiques:\n{critiques_to_text(input.previous_critiques)}",
    ])

    try:
        llm = ChatGoogleGenerativeAI(model=FLASH_MODEL, temperature=0)
        structured_llm = llm.with_structured_output(AgentOutput)
        prompt = ChatPromptTemplate.from_messages([
            ("system", DRAFT_AGENT_PROMPT),
            ("human", "{input}"),
        ])
        chain = prompt | structured_llm
        result = await chain.ainvoke({"input": prompt_text})
        if isinstance(result, AgentOutput):
            if result.revised_doc is None:
                result.revised_doc = input.document
            return result
        return _build_fallback(input, "Unexpected output format from draft agent.")
    except Exception as e:
        return _build_fallback(input, f"Draft agent fallback after model error: {e}")
