"""QA agent - ported from packages/ai/src/agents/qa.ts."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from .types import FLASH_MODEL, AgentInput, AgentOutput, critiques_to_text, has_google_api_key

QA_AGENT_PROMPT = """You are a QA engineer reviewing user stories for testability.
Check: Are acceptance criteria specific and measurable? Are edge cases covered?
Are there ambiguous terms? Provide critique and risk flags.

When the provided context includes relevant code (test files, modules under test),
reference them in your critique to ground your feedback. For example:
"The existing tests in `apps/api/tests/test_retrieval.py` don't cover this edge case."
Only cite files that appear in the provided context."""


def _build_fallback(critique: str) -> AgentOutput:
    return AgentOutput(
        critique=critique,
        risk_flags=[],
        confidence=0.75,
        ready=False,
    )


async def run(input: AgentInput) -> AgentOutput:
    if not has_google_api_key():
        return _build_fallback("Mock QA critique generated because GOOGLE_GENERATIVE_AI_API_KEY is unavailable.")

    prompt_text = "\n\n".join([
        f"Document:\n{input.document}",
        f"Context:\n{input.context}",
        f"Round: {input.round}",
        f"Previous critiques:\n{critiques_to_text(input.previous_critiques)}",
    ])

    try:
        llm = ChatGoogleGenerativeAI(model=FLASH_MODEL, temperature=0)
        structured_llm = llm.with_structured_output(AgentOutput)
        prompt = ChatPromptTemplate.from_messages([
            ("system", QA_AGENT_PROMPT),
            ("human", "{input}"),
        ])
        chain = prompt | structured_llm
        result = await chain.ainvoke({"input": prompt_text})
        if isinstance(result, AgentOutput):
            return result
        return _build_fallback("Unexpected output format from QA agent.")
    except Exception as e:
        return _build_fallback(f"QA agent fallback after model error: {e}")
