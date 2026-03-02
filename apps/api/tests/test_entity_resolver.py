# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false

from app.services.entity_resolver import (
    EntityRecord,
    EntityResolver,
    _extract_entity_candidates,
    build_entity_hints,
)

USERS: list[EntityRecord] = [
    {"id": "u1", "name": "Nelly Musik", "email": "nelly@company.com"},
    {"id": "u2", "name": "Jean Dupont", "email": "jean.dupont@company.com"},
    {"id": "u3", "name": "Alice Martin", "email": "alice@company.com"},
]
TEAMS: list[EntityRecord] = [
    {"id": "t1", "name": "Engineering"},
    {"id": "t2", "name": "Product"},
    {"id": "t3", "name": "Origination"},
]
LABELS: list[EntityRecord] = [{"id": "l1", "name": "Bug"}, {"id": "l2", "name": "Feature"}]
STATES: list[EntityRecord] = [{"id": "s1", "name": "In Progress"}]
PROJECTS: list[EntityRecord] = [{"id": "p1", "name": "Checkout Redesign"}]


def _resolver(
    users: list[EntityRecord] | None = None,
    teams: list[EntityRecord] | None = None,
    labels: list[EntityRecord] | None = None,
    states: list[EntityRecord] | None = None,
    projects: list[EntityRecord] | None = None,
) -> EntityResolver:
    return EntityResolver(
        users=USERS if users is None else users,
        teams=TEAMS if teams is None else teams,
        labels=LABELS if labels is None else labels,
        states=STATES if states is None else states,
        projects=PROJECTS if projects is None else projects,
    )


def test_resolve_user_exact_match_casefold():
    resolved = _resolver().resolve_user("nelly musik")
    assert resolved is not None
    assert resolved.resolved == "Nelly Musik"
    assert resolved.entity_type == "user"
    assert resolved.entity_id == "u1"
    assert resolved.confidence == 100


def test_resolve_user_typo_correction_matches_nelly():
    resolved = _resolver().resolve_user("Nally")
    assert resolved is not None
    assert resolved.resolved == "Nelly Musik"
    assert resolved.confidence >= 70


def test_resolve_user_first_name_alias():
    resolved = _resolver().resolve_user("nelly")
    assert resolved is not None
    assert resolved.resolved == "Nelly Musik"
    assert resolved.confidence == 95


def test_resolve_user_email_prefix_alias():
    users: list[EntityRecord] = [{"id": "u1", "name": "Someone Else", "email": "nelly@company.com"}]
    resolved = _resolver(users=users).resolve_user("nelly")
    assert resolved is not None
    assert resolved.resolved == "Someone Else"
    assert resolved.confidence == 95


def test_resolve_user_no_match_returns_none():
    assert _resolver().resolve_user("Zzzzxxx") is None


def test_resolve_team_exact_and_fuzzy_match():
    resolver = _resolver()
    exact = resolver.resolve_team("engineering")
    fuzzy = resolver.resolve_team("Enginering")

    assert exact is not None
    assert exact.resolved == "Engineering"
    assert exact.confidence == 100

    assert fuzzy is not None
    assert fuzzy.resolved == "Engineering"
    assert fuzzy.confidence >= 70


def test_resolve_label_exact_match():
    resolved = _resolver().resolve_label("bug")
    assert resolved is not None
    assert resolved.resolved == "Bug"
    assert resolved.confidence == 100


def test_resolve_project_exact_match():
    resolved = _resolver().resolve_project("checkout redesign")
    assert resolved is not None
    assert resolved.resolved == "Checkout Redesign"
    assert resolved.confidence == 100


def test_resolve_any_picks_best_entity_type_match():
    resolved = _resolver().resolve_any("Nally")
    assert resolved is not None
    assert resolved.entity_type == "user"
    assert resolved.resolved == "Nelly Musik"


def test_build_entity_hints_typo_name_produces_hint():
    hints = build_entity_hints("How many issues did Nally create?", _resolver())
    assert "Nally" in hints
    assert "Nelly Musik" in hints


def test_build_entity_hints_correct_name_returns_empty_string():
    hints = build_entity_hints("how many issues did nelly musik create?", _resolver())
    assert hints == ""


def test_build_entity_hints_without_entity_like_words_returns_empty_string():
    hints = build_entity_hints("how many issues last week", _resolver())
    assert hints == ""


def test_extract_entity_candidates_capitalized_words_bigrams_and_stopwords():
    candidates = _extract_entity_candidates(
        "How many issues did Nally create with Alice Martin in Engineering?"
    )
    assert "How" not in candidates
    assert "Nally Alice" in candidates
    assert "Alice Martin" in candidates
    assert "Martin Engineering" in candidates
    assert "Nally" in candidates
    assert "Engineering" in candidates


def test_edge_cases_empty_entities_message_and_single_char_input():
    resolver = _resolver(users=[], teams=[], labels=[], states=[], projects=[])
    assert resolver.resolve_user("Nelly") is None
    assert resolver.resolve_team("Engineering") is None
    assert resolver.resolve_label("Bug") is None
    assert resolver.resolve_project("Checkout Redesign") is None
    assert resolver.resolve_any("Nally") is None
    assert _extract_entity_candidates("") == []
    assert _extract_entity_candidates("A") == ["A"]
