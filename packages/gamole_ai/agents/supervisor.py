"""Supervisor agent - ported from packages/ai/src/agents/supervisor.ts."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from .types import (
    FLASH_MODEL,
    MAX_CRITIQUE_ROUNDS,
    AgentInput,
    SupervisorOutput,
    critiques_to_text,
    has_google_api_key,
)

SUPERVISOR_AGENT_PROMPT = """You are a requirements quality supervisor. Review the document
and all critiques. Decide if the output is ready for delivery or needs another
revision round. Force stop after 5 rounds regardless of quality."""


def _force_stop_output(round: int) -> SupervisorOutput:
    return SupervisorOutput(
        ready=True,
        reason=f"Force stop at round {round} (max {MAX_CRITIQUE_ROUNDS} rounds).",
        force_stop=True,
        quality_score=0,
    )


def _mock_output(reason: str) -> SupervisorOutput:
    return SupervisorOutput(
        ready=False,
        reason=reason,
        force_stop=False,
        quality_score=60,
    )


async def run(input: AgentInput) -> SupervisorOutput:
    if input.round >= MAX_CRITIQUE_ROUNDS:
        return _force_stop_output(input.round)

    if not has_google_api_key():
        return _mock_output("Mock supervisor review generated because GOOGLE_GENERATIVE_AI_API_KEY is unavailable.")

    prompt_text = "\n\n".join([
        f"Document:\n{input.document}",
        f"Context:\n{input.context}",
        f"Round: {input.round}",
        f"All critiques:\n{critiques_to_text(input.previous_critiques)}",
    ])

    try:
        llm = ChatGoogleGenerativeAI(model=FLASH_MODEL, temperature=0)
        structured_llm = llm.with_structured_output(SupervisorOutput)
        prompt = ChatPromptTemplate.from_messages([
            ("system", SUPERVISOR_AGENT_PROMPT),
            ("human", "{input}"),
        ])
        chain = prompt | structured_llm
        result = await chain.ainvoke({"input": prompt_text})
        if isinstance(result, SupervisorOutput):
            result.force_stop = False
            return result
        return _mock_output("Unexpected output format from supervisor agent.")
    except Exception as e:
        return _mock_output(f"Supervisor fallback after model error: {e}")
