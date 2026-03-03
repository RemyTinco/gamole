"""Discovery agent — generates clarifying questions and enriches user input."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from gamole_types.schemas.discovery import (
    DiscoveryAnswer,
    DiscoveryEnrichmentInput,
    DiscoveryEnrichmentOutput,
    DiscoveryQuestion,
    DiscoveryQuestionsOutput,
)

from .types import FLASH_MODEL, has_google_api_key

QUESTION_GENERATION_PROMPT = """You are a senior product analyst specializing in requirements discovery.
Analyze the user's feature request and the provided context (existing Linear issues and codebase).
Generate between 3 and 7 clarifying questions that, when answered, will significantly improve
the quality and completeness of the resulting ticket(s).

Focus your questions on gaps in:
- Scope boundaries (what's in vs out of scope)
- Acceptance criteria (how will "done" be verified?)
- Edge cases and error handling
- Technical constraints or dependencies on other systems
- User roles or personas affected
- Priority or sequencing

IMPORTANT:
- Generate between 3 and 7 questions (use fewer for simple requests, more for complex ones)
- Each question must be specific and actionable — not generic
- Do NOT ask questions that can be inferred from the context provided
- Questions must help produce BETTER ticket coverage, not just gather information
- Output structured JSON with questions array"""

ENRICHMENT_PROMPT = """You are a senior product manager. You have been given a feature request
and the user's answers to clarifying questions about it.

Your task: Rewrite and expand the original feature request into a comprehensive, well-structured
product specification that naturally incorporates all the information from the Q&A.

The output should:
- Read naturally as if a thorough product manager wrote it from scratch
- Include all details from the original request AND the Q&A answers
- Be specific about scope, acceptance criteria, and technical constraints mentioned
- NOT be formatted as a Q&A — write flowing prose describing the feature

This enriched specification will feed directly into ticket-generation agents."""


def _mock_questions() -> DiscoveryQuestionsOutput:
    return DiscoveryQuestionsOutput(
        questions=[
            DiscoveryQuestion(id="q1", text="What specific scope boundaries should this feature include or exclude?"),
            DiscoveryQuestion(id="q2", text="Which user roles or personas are affected, and how does each use this feature?"),
            DiscoveryQuestion(id="q3", text="What acceptance criteria will confirm this feature is complete and working correctly?"),
            DiscoveryQuestion(id="q4", text="What edge cases, failure states, or error scenarios must be handled?"),
            DiscoveryQuestion(id="q5", text="What technical constraints, dependencies, or integration limits should we account for?"),
        ]
    )


def _mock_enrichment(inp: DiscoveryEnrichmentInput) -> DiscoveryEnrichmentOutput:
    answers: list[DiscoveryAnswer] = inp.answers
    return DiscoveryEnrichmentOutput(
        enriched_document=inp.original_input
        + f" [enriched with {len(answers)} answers: "
        + "; ".join(f"{a.question_id}: {a.answer}" for a in answers)
        + "]"
    )


async def generate_questions(input_text: str, context: str) -> DiscoveryQuestionsOutput:
    if not has_google_api_key():
        return _mock_questions()

    prompt_text = f"Feature request:\n{input_text}\n\nContext:\n{context}"

    try:
        llm = ChatGoogleGenerativeAI(model=FLASH_MODEL, temperature=0)
        structured_llm = llm.with_structured_output(DiscoveryQuestionsOutput)
        prompt = ChatPromptTemplate.from_messages([
            ("system", QUESTION_GENERATION_PROMPT),
            ("human", "{input}"),
        ])
        chain = prompt | structured_llm
        result = await chain.ainvoke({"input": prompt_text})
        if isinstance(result, DiscoveryQuestionsOutput):
            return result
        return _mock_questions()
    except Exception:
        return _mock_questions()


async def enrich_document(inp: DiscoveryEnrichmentInput) -> DiscoveryEnrichmentOutput:
    if not has_google_api_key():
        return _mock_enrichment(inp)

    answer_lookup = {answer.question_id: answer.answer for answer in inp.answers}
    qa_pairs = "\n\n".join(
        f"Q: {question.text}\nA: {answer_lookup.get(question.id, '')}" for question in inp.questions
    )
    prompt_text = (
        f"Original feature request:\n{inp.original_input}\n\n"
        f"Context:\n{inp.context}\n\n"
        f"Q&A:\n{qa_pairs}"
    )

    try:
        llm = ChatGoogleGenerativeAI(model=FLASH_MODEL, temperature=0)
        structured_llm = llm.with_structured_output(DiscoveryEnrichmentOutput)
        prompt = ChatPromptTemplate.from_messages([
            ("system", ENRICHMENT_PROMPT),
            ("human", "{input}"),
        ])
        chain = prompt | structured_llm
        result = await chain.ainvoke({"input": prompt_text})
        if isinstance(result, DiscoveryEnrichmentOutput):
            return result
        return _mock_enrichment(inp)
    except Exception:
        return _mock_enrichment(inp)
