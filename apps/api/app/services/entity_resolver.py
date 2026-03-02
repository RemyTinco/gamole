from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypedDict

from rapidfuzz import fuzz, process

_STOPWORDS = {
    "What",
    "How",
    "When",
    "Where",
    "Who",
    "Why",
    "Which",
    "Show",
    "Find",
    "List",
    "Get",
    "Tell",
    "The",
    "Is",
    "Are",
    "Do",
    "Does",
    "Did",
    "Can",
    "Could",
    "Will",
    "Would",
    "Should",
    "In",
    "On",
    "At",
    "By",
    "From",
    "To",
    "For",
    "With",
    "About",
    "After",
    "Before",
    "Last",
    "Next",
    "This",
    "That",
    "All",
    "Any",
    "No",
    "Not",
    "My",
    "Our",
    "Their",
}


class EntityRecord(TypedDict, total=False):
    id: str
    name: str
    email: str


@dataclass(slots=True)
class ResolvedEntity:
    raw: str
    resolved: str
    entity_type: str
    confidence: int
    entity_id: str | None
    alternatives: list[str]


class EntityResolver:
    users: list[EntityRecord]
    teams: list[EntityRecord]
    labels: list[EntityRecord]
    states: list[EntityRecord]
    projects: list[EntityRecord]
    _user_name_to_id: dict[str, str]
    _team_name_to_id: dict[str, str]
    _label_name_to_id: dict[str, str]
    _project_name_to_id: dict[str, str]
    _user_aliases: dict[str, str]

    def __init__(
        self,
        users: list[EntityRecord],
        teams: list[EntityRecord],
        labels: list[EntityRecord],
        states: list[EntityRecord],
        projects: list[EntityRecord],
    ) -> None:
        """Initialize resolver indexes from Linear metadata collections."""
        self.users = users
        self.teams = teams
        self.labels = labels
        self.states = states
        self.projects = projects

        self._user_name_to_id = self._build_name_to_id(users)
        self._team_name_to_id = self._build_name_to_id(teams)
        self._label_name_to_id = self._build_name_to_id(labels)
        self._project_name_to_id = self._build_name_to_id(projects)

        self._user_aliases = self._build_user_aliases(users)

    def resolve_user(self, raw: str, threshold: int = 70) -> ResolvedEntity | None:
        """Resolve a user from fuzzy input text."""
        return self._resolve_entity(
            raw=raw,
            entity_type="user",
            name_to_id=self._user_name_to_id,
            threshold=threshold,
            aliases=self._user_aliases,
        )

    def resolve_team(self, raw: str, threshold: int = 70) -> ResolvedEntity | None:
        """Resolve a team from fuzzy input text."""
        return self._resolve_entity(
            raw=raw,
            entity_type="team",
            name_to_id=self._team_name_to_id,
            threshold=threshold,
        )

    def resolve_label(self, raw: str, threshold: int = 70) -> ResolvedEntity | None:
        """Resolve a label from fuzzy input text."""
        return self._resolve_entity(
            raw=raw,
            entity_type="label",
            name_to_id=self._label_name_to_id,
            threshold=threshold,
        )

    def resolve_project(self, raw: str, threshold: int = 70) -> ResolvedEntity | None:
        """Resolve a project from fuzzy input text."""
        return self._resolve_entity(
            raw=raw,
            entity_type="project",
            name_to_id=self._project_name_to_id,
            threshold=threshold,
        )

    def resolve_any(self, raw: str) -> ResolvedEntity | None:
        """Resolve input text against users, teams, labels, and projects."""
        candidates = [
            self.resolve_user(raw),
            self.resolve_team(raw),
            self.resolve_label(raw),
            self.resolve_project(raw),
        ]
        matches = [candidate for candidate in candidates if candidate is not None]
        if not matches:
            return None
        return max(matches, key=lambda item: item.confidence)

    @staticmethod
    def _build_name_to_id(entities: list[EntityRecord]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for entity in entities:
            name = str(entity.get("name", "")).strip()
            entity_id = entity.get("id")
            if name and isinstance(entity_id, str):
                mapping[name] = entity_id
        return mapping

    @staticmethod
    def _build_user_aliases(users: list[EntityRecord]) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for user in users:
            name = str(user.get("name", "")).strip()
            if not name:
                continue

            email = str(user.get("email", "")).strip()

            # If name looks like an email, extract readable parts from it
            if "@" in name:
                local = name.split("@", 1)[0].casefold()
                # "nelly.trakidou" → alias "nelly" (first part before dot)
                parts = local.replace("-", ".").split(".")
                for part in parts:
                    if part and len(part) > 1 and part not in aliases:
                        aliases[part] = name
            else:
                # Normal "First Last" name → first name alias
                first_name = name.split(maxsplit=1)[0].casefold()
                if first_name and first_name not in aliases:
                    aliases[first_name] = name

            # Also index email prefix and first part of email prefix
            if "@" in email:
                email_prefix = email.split("@", 1)[0].casefold()
                if email_prefix and email_prefix not in aliases:
                    aliases[email_prefix] = name
                # "nelly.trakidou" → also alias "nelly"
                email_parts = email_prefix.replace("-", ".").split(".")
                if email_parts and email_parts[0] and email_parts[0] not in aliases:
                    aliases[email_parts[0]] = name
        return aliases

    def _resolve_entity(
        self,
        raw: str,
        entity_type: str,
        name_to_id: dict[str, str],
        threshold: int,
        aliases: dict[str, str] | None = None,
    ) -> ResolvedEntity | None:
        query = raw.strip()
        if not query or not name_to_id:
            return None

        for known_name, entity_id in name_to_id.items():
            if query.casefold() == known_name.casefold():
                alternatives = [name for name in name_to_id if name != known_name][:3]
                return ResolvedEntity(
                    raw=query,
                    resolved=known_name,
                    entity_type=entity_type,
                    confidence=100,
                    entity_id=entity_id,
                    alternatives=alternatives,
                )

        # Exact alias match (case-insensitive)
        if aliases:
            alias_target = aliases.get(query.casefold())
            if alias_target and alias_target in name_to_id:
                alternatives = [name for name in name_to_id if name != alias_target][:3]
                return ResolvedEntity(
                    raw=query,
                    resolved=alias_target,
                    entity_type=entity_type,
                    confidence=95,
                    entity_id=name_to_id.get(alias_target),
                    alternatives=alternatives,
                )

        # Fuzzy match against canonical names
        matches = process.extract(
            query,
            list(name_to_id.keys()),
            scorer=fuzz.WRatio,
            limit=5,
        )
        best_name = None
        best_score = 0
        if matches:
            best_name = str(matches[0][0])
            best_score = int(round(float(matches[0][1])))

        # Also fuzzy match against aliases (handles typos like "Nally" → "nelly")
        # Use fuzz.ratio for aliases since they're short strings where
        # character-level similarity matters more than token reordering.
        # Casefold the query since alias keys are already lowercase.
        if aliases:
            alias_matches = process.extract(
                query.casefold(),
                list(aliases.keys()),
                scorer=fuzz.ratio,
                limit=3,
            )
            if alias_matches:
                alias_key = str(alias_matches[0][0])
                alias_score = int(round(float(alias_matches[0][1])))
                alias_target = aliases.get(alias_key, "")
                # Prefer alias match if it scores better
                if alias_score > best_score and alias_target in name_to_id:
                    best_name = alias_target
                    best_score = alias_score

        if not best_name or best_score < threshold:
            return None

        alt_names = [n for n in name_to_id if n != best_name][:3]
        return ResolvedEntity(
            raw=query,
            resolved=best_name,
            entity_type=entity_type,
            confidence=max(0, min(100, best_score)),
            entity_id=name_to_id.get(best_name),
            alternatives=alt_names,
        )


def build_entity_hints(message: str, resolver: EntityResolver) -> str:
    """Build correction hints for likely entity names in a user message."""
    candidates = _extract_entity_candidates(message)
    seen_resolutions: set[tuple[str, str]] = set()
    hints: list[str] = []

    for candidate in candidates:
        resolved = resolver.resolve_any(candidate)
        if resolved is None:
            continue
        if resolved.confidence == 100:
            continue

        key = (resolved.raw.casefold(), resolved.resolved.casefold())
        if key in seen_resolutions:
            continue
        seen_resolutions.add(key)

        hints.append(
            f'⚠️ "{resolved.raw}" → did you mean "{resolved.resolved}"? '
            + f"(confidence: {resolved.confidence}%)"
        )

    if not hints:
        return ""

    return (
        "\n\nENTITY RESOLUTION HINTS (use corrected names in queries):\n"
        + "\n".join(hints)
    )


def _extract_entity_candidates(message: str) -> list[str]:
    tokens = [
        match.group(0)
        for match in re.finditer(r"\b[A-Z][A-Za-z0-9'\-]*\b", message)
        if match.group(0) not in _STOPWORDS
    ]

    candidates: list[str] = []
    seen: set[str] = set()

    for index in range(len(tokens) - 1):
        phrase = f"{tokens[index]} {tokens[index + 1]}"
        lowered = phrase.casefold()
        if lowered not in seen:
            seen.add(lowered)
            candidates.append(phrase)

    for token in tokens:
        lowered = token.casefold()
        if lowered not in seen:
            seen.add(lowered)
            candidates.append(token)

    return candidates
