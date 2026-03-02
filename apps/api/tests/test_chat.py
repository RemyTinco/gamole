# pyright: reportMissingTypeStubs=false

from typing import Callable, cast

import app.routes.chat as chat
from app.services.entity_resolver import EntityRecord, EntityResolver, build_entity_hints

_extract_action = cast(Callable[[str], dict[str, object] | None], getattr(chat, "_extract_action"))
_extract_nodes = cast(Callable[[object], list[object]], getattr(chat, "_extract_nodes"))
_format_workspace_context = cast(
    Callable[[object], str],
    getattr(chat, "_format_workspace_context"),
)
_looks_like_scope_refusal = cast(
    Callable[[str], bool],
    getattr(chat, "_looks_like_scope_refusal"),
)
_content_to_text = cast(
    Callable[[object], str],
    getattr(chat, "_content_to_text"),
)


def test_extract_action_query_json():
    payload = '{"action": "query", "graphql_query": "{ issues { nodes { id } } }"}'
    parsed = _extract_action(payload)
    assert parsed == {
        "action": "query",
        "graphql_query": "{ issues { nodes { id } } }",
    }


def test_extract_action_answer_json():
    payload = '{"action": "answer", "text": "Found 12 issues"}'
    parsed = _extract_action(payload)
    assert parsed == {"action": "answer", "text": "Found 12 issues"}


def test_extract_action_search_json():
    payload = '{"action": "search", "query": "origination team bottlenecks"}'
    parsed = _extract_action(payload)
    assert parsed == {
        "action": "search",
        "query": "origination team bottlenecks",
    }


def test_extract_action_markdown_wrapped_json():
    payload = """```json
{"action":"query","graphql_query":"{ teams { nodes { id name } } }"}
```"""
    parsed = _extract_action(payload)
    assert parsed == {
        "action": "query",
        "graphql_query": "{ teams { nodes { id name } } }",
    }


def test_extract_action_invalid_or_missing_json_returns_none():
    assert _extract_action("No json here") is None
    assert _extract_action("action=query") is None


def test_extract_action_unescaped_nested_graphql_quotes_uses_fallback():
    payload = (
        '{"action":"query","graphql_query":"{ issues(filter: { title: { '
        'contains: "checkout" } }) { nodes { id } } }"}'
    )
    parsed = _extract_action(payload)
    assert parsed is not None
    assert parsed["action"] == "query"
    assert "contains: \"checkout\"" in str(parsed["graphql_query"])


def test_extract_nodes_returns_nodes_list():
    result = {"data": {"issues": {"nodes": [{"id": "1"}]}}}
    assert _extract_nodes(result) == [{"id": "1"}]


def test_extract_nodes_returns_empty_for_empty_or_missing_data():
    assert _extract_nodes({"data": {"issues": {"nodes": []}}}) == []
    assert _extract_nodes({"data": {}}) == []
    assert _extract_nodes({"errors": [{"message": "boom"}]}) == []


def test_format_workspace_context_with_all_sections_and_label_deduplication():
    ctx = {
        "users": [{"id": "u1", "name": "Nelly Musik"}],
        "teams": [{"id": "t1", "name": "Engineering", "description": "Core platform"}],
        "labels": [
            {"id": "l1", "name": "Bug"},
            {"id": "l2", "name": "Feature"},
            {"id": "l3", "name": "Bug"},
        ],
        "projects": [{"id": "p1", "name": "Checkout Redesign"}],
    }
    formatted = _format_workspace_context(ctx)

    assert "Known Entities:" in formatted
    assert "Known Users:" in formatted
    assert "Known Teams:" in formatted
    assert "Known Labels:" in formatted
    assert "Known Projects:" in formatted
    assert "Nelly Musik (id: u1)" in formatted
    assert "Engineering (id: t1): Core platform" in formatted
    assert "Checkout Redesign (id: p1)" in formatted
    assert formatted.count("  - Bug ") == 1


def test_format_workspace_context_with_empty_context_returns_empty_string():
    assert _format_workspace_context({}) == ""


def test_format_workspace_context_with_only_users_section():
    formatted = _format_workspace_context({"users": [{"id": "u1", "name": "Nelly Musik"}]})
    assert "Known Users:" in formatted
    assert "Known Teams:" not in formatted
    assert "Known Labels:" not in formatted
    assert "Known Projects:" not in formatted


def test_build_entity_hints_integration_with_chat_like_context():
    users: list[EntityRecord] = [{"id": "u1", "name": "Nelly Musik", "email": "nelly@company.com"}]
    teams: list[EntityRecord] = [{"id": "t1", "name": "Engineering"}]
    labels: list[EntityRecord] = [{"id": "l1", "name": "Bug"}]
    states: list[EntityRecord] = [{"id": "s1", "name": "In Progress"}]
    projects: list[EntityRecord] = [{"id": "p1", "name": "Checkout Redesign"}]
    resolver = EntityResolver(
        users=users,
        teams=teams,
        labels=labels,
        states=states,
        projects=projects,
    )

    hints = build_entity_hints(
        "How many tickets did Nally create in the last 2 weeks?",
        resolver,
    )
    assert "Nally" in hints
    assert "Nelly Musik" in hints


def test_scope_refusal_detector_matches_common_refusal_patterns():
    assert _looks_like_scope_refusal(
        "That's outside the scope of what I can answer as a Linear assistant."
    )
    assert _looks_like_scope_refusal("My capabilities are focused on retrieving data only.")
    assert not _looks_like_scope_refusal("I reviewed your team data and found 3 bottlenecks.")


def test_content_to_text_normalizes_string_and_message_parts():
    assert _content_to_text("plain answer") == "plain answer"
    assert _content_to_text([
        "Part 1",
        {"text": "Part 2"},
        {"ignored": "x"},
    ]) == "Part 1\nPart 2"
