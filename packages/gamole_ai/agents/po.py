"""PO agent - ported from packages/ai/src/agents/po.ts."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from .types import FLASH_MODEL, AgentInput, AgentOutput, critiques_to_text, has_google_api_key

PO_AGENT_PROMPT = """You are a product owner reviewing user stories for business value.
Check: Does this align with business goals? Is the priority justified?
Are there simpler alternatives? Provide critique and business risk flags."""


def _build_fallback(critique: str) -> AgentOutput:
    return AgentOutput(
        critique=critique,
        risk_flags=[],
        confidence=0.75,
        ready=False,
    )


async def run(input: AgentInput) -> AgentOutput:
    if not has_google_api_key():
        return _build_fallback("Mock PO critique generated because GOOGLE_GENERATIVE_AI_API_KEY is unavailable.")

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
            ("system", PO_AGENT_PROMPT),
            ("human", "{input}"),
        ])
        chain = prompt | structured_llm
        result = await chain.ainvoke({"input": prompt_text})
        if isinstance(result, AgentOutput):
            return result
        return _build_fallback("Unexpected output format from PO agent.")
    except Exception as e:
        return _build_fallback(f"PO agent fallback after model error: {e}")
