"""Tests for gamole_linear push service and client error handling.

Tests the push_to_linear function's team_id validation logic and
the LinearClient._raw_request null data handling. These are unit
tests that mock the Linear API and DB — no network or DB needed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from gamole_linear.client import LinearClient
from gamole_linear.push import push_to_linear
from gamole_types import GeneratedOutput, LinearPushConfig
from gamole_types.schemas.generated import GeneratedEpic, GeneratedStory

# --- Helpers ---

def _make_story(title: str = "Story 1", description: str = "Desc") -> GeneratedStory:
    return GeneratedStory(
        title=title,
        description=description,
        acceptanceCriteria=["AC1"],
        assumptions=[],
        technicalNotes=None,
    )


def _make_epic(
    title: str = "Epic 1",
    team_name: str | None = "Backend",
    stories: list[GeneratedStory] | None = None,
) -> GeneratedEpic:
    return GeneratedEpic(
        epicTitle=title,
        epicDescription="Epic desc",
        teamName=team_name,
        teamReason="Reason",
        stories=stories or [_make_story()],
    )


def _make_output(epics: list[GeneratedEpic] | None = None) -> GeneratedOutput:
    return GeneratedOutput(
        epics=epics if epics is not None else [_make_epic()],
        projectName="Test Project",
        overallNotes=None,
    )


# =============================================================================
# push_to_linear — team_id validation
# =============================================================================


class TestPushTeamIdValidation:
    """Test that push_to_linear handles missing team_id correctly."""

    @pytest.mark.asyncio
    async def test_all_epics_missing_team_id_returns_errors(self):
        """When no epic has a resolvable team_id and no default is set, push returns
        early with errors and zero created issues."""
        output = _make_output(epics=[
            _make_epic(title="Epic A", team_name=None),
            _make_epic(title="Epic B", team_name=None),
        ])
        config = LinearPushConfig()  # no default team_id

        with patch("gamole_linear.push._resolve_team_id", new_callable=AsyncMock, return_value=None):
            result = await push_to_linear(output, config, "lin_api_test")

        assert len(result.created_issues) == 0
        assert len(result.errors) >= 1
        assert "Epic A" in result.errors[0]
        assert "Epic B" in result.errors[0]

    @pytest.mark.asyncio
    async def test_some_epics_missing_team_id_skips_those_epics(self):
        """Epics without a resolved team_id are skipped; epics with team_id proceed."""
        output = _make_output(epics=[
            _make_epic(title="Epic With Team", team_name="Backend"),
            _make_epic(title="Epic No Team", team_name=None),
        ])
        config = LinearPushConfig()

        async def mock_resolve(team_name, fallback):
            if team_name == "Backend":
                return "team-backend-id"
            return None

        mock_client = AsyncMock()
        mock_client.batch_create_issues.return_value = [
            AsyncMock(id="issue-1", identifier="BACK-1", title="Epic With Team"),
            AsyncMock(id="issue-2", identifier="BACK-2", title="Story 1"),
        ]
        mock_client.batch_create_relations.return_value = []
        mock_client.close = AsyncMock()

        with (
            patch("gamole_linear.push._resolve_team_id", side_effect=mock_resolve),
            patch("gamole_linear.push.LinearClient", return_value=mock_client),
        ):
            result = await push_to_linear(output, config, "lin_api_test")

        # The epic with a team was pushed
        assert len(result.created_issues) == 2
        # The missing team epic generated an error
        assert any("Epic No Team" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_config_team_id_used_as_fallback(self):
        """When config.team_id is set, it is used for epics without a team name."""
        output = _make_output(epics=[
            _make_epic(title="Epic No Name", team_name=None),
        ])
        config = LinearPushConfig(teamId="fallback-team")

        async def mock_resolve(team_name, fallback):
            return fallback  # Returns the fallback team_id

        mock_client = AsyncMock()
        mock_client.batch_create_issues.return_value = [
            AsyncMock(id="issue-1", identifier="FALL-1", title="Epic No Name"),
            AsyncMock(id="issue-2", identifier="FALL-2", title="Story 1"),
        ]
        mock_client.batch_create_relations.return_value = []
        mock_client.close = AsyncMock()

        with (
            patch("gamole_linear.push._resolve_team_id", side_effect=mock_resolve),
            patch("gamole_linear.push.LinearClient", return_value=mock_client),
        ):
            result = await push_to_linear(output, config, "lin_api_test")

        assert len(result.created_issues) == 2
        # No missing team errors
        assert not any("No team ID resolved" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_empty_epics_returns_empty_result(self):
        """An output with zero epics returns empty result with no errors."""
        output = _make_output(epics=[])
        config = LinearPushConfig()

        result = await push_to_linear(output, config, "lin_api_test")

        assert len(result.created_issues) == 0
        assert len(result.created_relations) == 0
        assert len(result.errors) == 0


# =============================================================================
# LinearClient._raw_request — null data handling
# =============================================================================


class TestLinearClientRawRequest:
    """Test _raw_request error handling for null/missing GraphQL data."""

    def _mock_response(self, json_data, request=None):
        """Create a mock httpx response with sync .json() method."""
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = json_data
        if request:
            resp.request = request
        return resp

    @pytest.mark.asyncio
    async def test_null_data_with_errors_raises_runtime_error(self):
        """When GraphQL returns data: null with errors, _raw_request raises RuntimeError."""
        mock_resp = self._mock_response({
            "data": None,
            "errors": [
                {"message": "Variable 'teamId' is required but was not provided"},
            ],
        })

        client = LinearClient("lin_api_test")
        client._client = AsyncMock()
        client._client.post.return_value = mock_resp

        with pytest.raises(RuntimeError, match="Variable.*teamId.*required"):
            await client._raw_request("mutation { ... }")

        await client.close()

    @pytest.mark.asyncio
    async def test_null_data_without_errors_returns_empty_dict(self):
        """When GraphQL returns data: null but no errors array, returns empty dict."""
        mock_resp = self._mock_response({"data": None})

        client = LinearClient("lin_api_test")
        client._client = AsyncMock()
        client._client.post.return_value = mock_resp

        result = await client._raw_request("query { ... }")
        assert result == {}

        await client.close()

    @pytest.mark.asyncio
    async def test_valid_data_returned_normally(self):
        """Normal GraphQL response with data returns the data dict."""
        mock_resp = self._mock_response({
            "data": {"issueCreate": {"success": True, "issue": {"id": "abc"}}},
        })

        client = LinearClient("lin_api_test")
        client._client = AsyncMock()
        client._client.post.return_value = mock_resp

        result = await client._raw_request("mutation { ... }")
        assert result == {"issueCreate": {"success": True, "issue": {"id": "abc"}}}

        await client.close()

    @pytest.mark.asyncio
    async def test_rate_limited_raises_http_error(self):
        """Rate-limited response (errors with RATELIMITED code) raises HTTPStatusError."""
        mock_resp = self._mock_response(
            {
                "data": None,
                "errors": [
                    {
                        "message": "Rate limited",
                        "extensions": {"code": "RATELIMITED"},
                    },
                ],
            },
            request=httpx.Request("POST", "https://api.linear.app/graphql"),
        )

        client = LinearClient("lin_api_test")
        client._client = AsyncMock()
        client._client.post.return_value = mock_resp

        with pytest.raises(httpx.HTTPStatusError, match="Rate limited"):
            await client._raw_request("mutation { ... }")

        await client.close()

    @pytest.mark.asyncio
    async def test_graphql_errors_with_valid_data_returns_data(self):
        """When GraphQL returns both data and errors (partial success), returns data."""
        mock_resp = self._mock_response({
            "data": {"issues": {"nodes": []}},
            "errors": [{"message": "Some warning"}],
        })

        client = LinearClient("lin_api_test")
        client._client = AsyncMock()
        client._client.post.return_value = mock_resp

        result = await client._raw_request("query { ... }")
        assert result == {"issues": {"nodes": []}}

        await client.close()
