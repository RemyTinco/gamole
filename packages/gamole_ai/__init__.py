"""Gamole AI - LangChain agents, embeddings, retrieval (replaces Vercel AI SDK)."""

from .agents import (
    MAX_CRITIQUE_ROUNDS,
    run_dev_agent,
    run_draft_agent,
    run_po_agent,
    run_qa_agent,
    run_supervisor_agent,
)
from .agents.types import AgentInput, AgentOutput, SupervisorOutput
from .codebase.classifier import ALLOWED_EXTENSIONS, classifyFile, isSecretFile
from .codebase.indexer import REPO_LIMIT_ERROR_PREFIX, IndexStats, index_repository
from .embeddings import EMBEDDING_DIMENSIONS, chunk_text, embed_batch, embed_text
from .overlap import OverlapResult, detect_overlaps
from .quality import QualityFlags, compute_quality_score
from .retrieval import RetrieveContextOptions, retrieve_context

__all__ = [
    "ALLOWED_EXTENSIONS",
    "EMBEDDING_DIMENSIONS",
    "MAX_CRITIQUE_ROUNDS",
    "REPO_LIMIT_ERROR_PREFIX",
    "AgentInput",
    "AgentOutput",
    "IndexStats",
    "OverlapResult",
    "QualityFlags",
    "RetrieveContextOptions",
    "SupervisorOutput",
    "chunk_text",
    "classifyFile",
    "compute_quality_score",
    "detect_overlaps",
    "embed_batch",
    "embed_text",
    "index_repository",
    "isSecretFile",
    "retrieve_context",
    "run_dev_agent",
    "run_draft_agent",
    "run_po_agent",
    "run_qa_agent",
    "run_supervisor_agent",
]
