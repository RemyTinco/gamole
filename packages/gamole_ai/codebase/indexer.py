"""Codebase indexer - ported from packages/ai/src/codebase/index.ts.

G18: NO real-time indexing — called on a nightly schedule only.
"""

import asyncio
import hashlib
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func

from ..embeddings import chunk_text, embed_batch
from .ast_chunker import CodeChunkResult, chunk_code
from .classifier import ALLOWED_EXTENSIONS, classifyFile, detect_language, isSecretFile

logger = logging.getLogger(__name__)

REPOS_BASE_DIR = "/tmp/gamole-repos"
MAX_REPOS = 3
REPO_LIMIT_ERROR_PREFIX = "REPO_LIMIT_EXCEEDED"

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "__pycache__", ".turbo",
    ".next", "coverage", "vendor", ".venv", "venv",
}


@dataclass
class IndexStats:
    repo_name: str
    files_indexed: int = 0
    chunks_created: int = 0
    errors: int = 0
    files_skipped: int = 0
    orphans_deleted: int = 0


def _repo_name_from_url(repo_url: str) -> str:
    clean = repo_url.removesuffix(".git")
    parts = [p for p in clean.split("/") if p]
    # Also handle : separators (git@github.com:org/repo)
    if parts:
        last = parts[-1]
        if ":" in last:
            parts = parts[:-1] + last.split(":")
    relevant = "-".join(parts[-2:]) if len(parts) >= 2 else parts[-1] if parts else "unknown"
    import re
    return re.sub(r"[^a-zA-Z0-9_-]", "_", relevant).lower()


def _inject_token(repo_url: str, token: str | None) -> str:
    """Inject GitHub token into HTTPS URLs for private repo access."""
    if not token or not repo_url.startswith("https://"):
        return repo_url
    # https://github.com/org/repo.git -> https://<token>@github.com/org/repo.git
    return repo_url.replace("https://", f"https://{token}@", 1)


async def _clone_or_pull(repo_url: str, target_dir: str, branch: str | None = None, token: str | None = None) -> None:
    auth_url = _inject_token(repo_url, token)

    if os.path.exists(target_dir):
        # Update remote URL in case token changed
        _ = await asyncio.create_subprocess_exec(
            "git", "-C", target_dir, "remote", "set-url", "origin", auth_url,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", target_dir, "pull",
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _ = await proc.wait()
        return

    args = ["git", "clone", "--depth=1"]
    if branch:
        args.extend(["-b", branch])
    args.extend([auth_url, target_dir])

    proc = await asyncio.create_subprocess_exec(
        *args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    code = await proc.wait()
    if code != 0:
        raise RuntimeError(f"git clone failed with exit code {code}")


def _walk_files(dir_path: str) -> list[str]:
    results: list[str] = []
    for root, dirs, files in os.walk(dir_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            ext = f.rsplit(".", 1)[-1].lower() if "." in f else ""
            if ext in ALLOWED_EXTENSIONS:
                results.append(os.path.join(root, f))
    return results


async def index_repository(repo_url: str, branch: str | None = None, github_token: str | None = None) -> IndexStats:
    """Index (or re-index) a Git repository into the codebase_chunks table."""
    repo_name = _repo_name_from_url(repo_url)
    target_dir = os.path.join(REPOS_BASE_DIR, repo_name)

    stats = IndexStats(repo_name=repo_name)

    # Load DB
    from sqlalchemy import and_, delete, select

    from gamole_db import CodebaseChunk, get_session  # pyright: ignore[reportMissingTypeStubs]

    async for session in get_session():
        # Enforce repo cap
        result = await session.execute(
            select(CodebaseChunk.repo_name).distinct()
        )
        existing_names = {row[0] for row in result}
        if repo_name not in existing_names and len(existing_names) >= MAX_REPOS:
            raise RuntimeError(
                f"{REPO_LIMIT_ERROR_PREFIX}: Repository limit reached (max {MAX_REPOS}). Remove an existing repo first."
            )

        # Clone / pull
        try:
            await _clone_or_pull(repo_url, target_dir, branch, github_token)
        except Exception as e:
            logger.error(f"[codebase] Clone/pull failed for {repo_url}: {e}")
            stats.errors += 1
            return stats

        # Walk files
        file_paths = _walk_files(target_dir)
        found_paths = {os.path.relpath(p, target_dir) for p in file_paths}

        # Process each file
        for abs_path in file_paths:
            rel_path = os.path.relpath(abs_path, target_dir)

            try:
                content = Path(abs_path).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                stats.errors += 1
                continue

            if isSecretFile(rel_path, content):
                continue

            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

            existing_hash_result = await session.execute(
                select(CodebaseChunk.content_hash)
                .where(
                    and_(
                        CodebaseChunk.repo_name == repo_name,
                        CodebaseChunk.file_path == rel_path,
                    )
                )
                .limit(1)
            )
            existing_hash_row = existing_hash_result.first()
            if existing_hash_row and existing_hash_row[0] == content_hash:
                stats.files_skipped += 1
                continue

            classification = classifyFile(rel_path)
            language = detect_language(rel_path)
            ast_chunks: list[CodeChunkResult] | None = None
            if language:
                ast_chunks = chunk_code(content, language, rel_path)

            if ast_chunks is not None:
                chunk_texts = [c.text for c in ast_chunks]
                chunk_meta = ast_chunks
            else:
                raw_chunks = [c for c in chunk_text(content) if c and c.strip()]
                chunk_texts = raw_chunks
                chunk_meta = None

            if not chunk_texts:
                continue

            try:
                embeddings = await embed_batch(chunk_texts)
            except Exception:
                logger.error(f"[codebase] Embed failed for {rel_path}", exc_info=True)
                stats.errors += 1
                continue

            # Delete old chunks for this file
            try:
                _ = await session.execute(
                    delete(CodebaseChunk).where(
                        and_(
                            CodebaseChunk.repo_name == repo_name,
                            CodebaseChunk.file_path == rel_path,
                        )
                    )
                )
            except Exception:
                pass

            # Insert new chunks
            for j, chunk_content in enumerate(chunk_texts):
                embedding = embeddings[j] if j < len(embeddings) else None
                if not chunk_content or embedding is None:
                    stats.errors += 1
                    continue

                try:
                    meta = chunk_meta[j] if chunk_meta and j < len(chunk_meta) else None
                    session.add(CodebaseChunk(
                        repo_name=repo_name,
                        file_path=rel_path,
                        language=classification.language,
                        chunk_text=chunk_content,
                        domain=classification.domain,
                        artifact_type=classification.artifact_type,
                        embedding=embedding,
                        content_hash=content_hash,
                        chunk_index=meta.chunk_index if meta else j,
                        symbol_name=meta.symbol_name if meta else None,
                        parent_symbol=meta.parent_symbol if meta else None,
                        content_tsv=func.to_tsvector("simple", chunk_content),
                    ))
                    stats.chunks_created += 1
                except Exception:
                    stats.errors += 1

            stats.files_indexed += 1

        if found_paths:
            orphan_result = await session.execute(
                delete(CodebaseChunk)
                .where(
                    and_(
                        CodebaseChunk.repo_name == repo_name,
                        CodebaseChunk.file_path.not_in(found_paths),
                    )
                )
                .returning(CodebaseChunk.id)
            )
            stats.orphans_deleted = len(list(orphan_result))

        await session.commit()

    return stats
