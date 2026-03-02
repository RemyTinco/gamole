"""Codebase indexer - ported from packages/ai/src/codebase/index.ts.

G18: NO real-time indexing — called on a nightly schedule only.
"""

import asyncio
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..embeddings import chunk_text, embed_batch
from .classifier import ALLOWED_EXTENSIONS, classifyFile, isSecretFile

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
        await asyncio.create_subprocess_exec(
            "git", "-C", target_dir, "remote", "set-url", "origin", auth_url,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", target_dir, "pull",
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        await proc.wait()
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

    from gamole_db import CodebaseChunk, get_session

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

            classification = classifyFile(rel_path)
            chunks = [c for c in chunk_text(content) if c and c.strip()]
            if not chunks:
                continue

            try:
                embeddings = await embed_batch(chunks)
            except Exception:
                logger.error(f"[codebase] Embed failed for {rel_path}", exc_info=True)
                stats.errors += 1
                continue

            # Delete old chunks for this file
            try:
                await session.execute(
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
            for j, chunk_content in enumerate(chunks):
                embedding = embeddings[j] if j < len(embeddings) else None
                if not chunk_content or embedding is None:
                    stats.errors += 1
                    continue

                try:
                    session.add(CodebaseChunk(
                        repo_name=repo_name,
                        file_path=rel_path,
                        language=classification.language,
                        chunk_text=chunk_content,
                        domain=classification.domain,
                        artifact_type=classification.artifact_type,
                        embedding=embedding,
                    ))
                    stats.chunks_created += 1
                except Exception:
                    stats.errors += 1

            stats.files_indexed += 1

        await session.commit()

    return stats
