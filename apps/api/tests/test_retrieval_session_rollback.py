"""Regression test: retrieve_context must not let a failed query poison the DB session.

When linear_issue_cache doesn't exist, the first query fails and PostgreSQL aborts the
transaction. Subsequent queries (repositories, codebase_chunks) must still work because
retrieve_context rolls back after each failure.

See: https://www.postgresql.org/docs/current/errcodes-appendix.html
     "current transaction is aborted, commands ignored until end of transaction block"
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gamole_ai.retrieval import EMPTY_BUNDLE, retrieve_context


@pytest.mark.asyncio
async def test_retrieve_context_rolls_back_after_linear_table_missing():
    """When linear_issue_cache query fails, repositories and codebase queries must still run."""
    fake_embedding = [0.1] * 768
    call_count = {"execute": 0}

    class FakeLinearError(Exception):
        """Simulates UndefinedTableError for linear_issue_cache."""

    class FakeSession:
        """Mock async session that fails on the first execute (linear query) but succeeds after rollback."""

        _failed = False
        _rolled_back = False

        async def execute(self, stmt, params=None):
            call_count["execute"] += 1

            # First call = linear_issue_cache query → fail
            if call_count["execute"] == 1:
                self._failed = True
                raise FakeLinearError("relation \"linear_issue_cache\" does not exist")

            # If session was failed but not rolled back, simulate PG's "transaction aborted" error
            if self._failed and not self._rolled_back:
                raise Exception("current transaction is aborted, commands ignored until end of transaction block")

            # Return empty results for successful queries
            mock_result = MagicMock()
            mock_result.scalars.return_value = iter([])
            mock_result.__iter__ = lambda self: iter([])
            return mock_result

        async def rollback(self):
            self._failed = False
            self._rolled_back = True

    fake_session = FakeSession()

    async def fake_get_session():
        yield fake_session

    with (
        patch("gamole_ai.retrieval.embed_query", new_callable=AsyncMock, return_value=fake_embedding),
        patch("gamole_db.get_session", fake_get_session),
    ):
        result = await retrieve_context("test query")

    # Should return a valid bundle (not crash), with empty linear artifacts
    assert result.linear_artifacts == []
    # Session.execute should have been called at least 3 times:
    # 1) linear_issue_cache (fails), 2) repositories, 3) codebase_chunks vector query
    assert call_count["execute"] >= 3, (
        f"Expected at least 3 execute calls (linear + repos + codebase), got {call_count['execute']}. "
        "Session rollback likely missing — failed transaction poisoned subsequent queries."
    )


@pytest.mark.asyncio
async def test_retrieve_context_returns_empty_bundle_when_embed_fails():
    """When embedding fails, retrieve_context returns EMPTY_BUNDLE without touching DB."""
    with patch("gamole_ai.retrieval.embed_query", new_callable=AsyncMock, side_effect=RuntimeError("embed failed")):
        result = await retrieve_context("test query")

    assert result == EMPTY_BUNDLE
