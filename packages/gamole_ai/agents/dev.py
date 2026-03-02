"""Dev agent - ported from packages/ai/src/agents/dev.ts."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from .types import FLASH_MODEL, AgentInput, AgentOutput, critiques_to_text, has_google_api_key

DEV_AGENT_PROMPT = """You are a senior software engineer reviewing user stories for technical
feasibility. Check: Is the scope clear? Are there hidden technical complexities?
Are dependencies identified? Provide critique and implementation notes.

The context includes repository descriptions and code chunks from the actual codebase.
Use these to ground your technical review in reality: reference specific files, patterns,
and repositories when pointing out complexities or suggesting implementation approaches."""


def _build_fallback(critique: str) -> AgentOutput:
    return AgentOutput(
        critique=critique,
        risk_flags=[],
        confidence=0.75,
        ready=False,
    )


async def run(input: AgentInput) -> AgentOutput:
    if not has_google_api_key():
        return _build_fallback("Mock dev critique generated because GOOGLE_GENERATIVE_AI_API_KEY is unavailable.")

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
            ("system", DEV_AGENT_PROMPT),
            ("human", "{input}"),
        ])
        chain = prompt | structured_llm
        result = await chain.ainvoke({"input": prompt_text})
        if isinstance(result, AgentOutput):
            return result
        return _build_fallback("Unexpected output format from dev agent.")
    except Exception as e:
        return _build_fallback(f"Dev agent fallback after model error: {e}")
