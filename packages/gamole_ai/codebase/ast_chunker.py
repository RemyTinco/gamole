from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from tree_sitter import Node, Parser, Tree
from tree_sitter_language_pack import SupportedLanguage

from ..embeddings import chunk_text

MAX_CHUNK_CHARS = 2048 * 4
ChunkableLanguage = Literal["python", "typescript", "tsx", "javascript", "go"]

LANGUAGE_PARSER_MAP: dict[str, ChunkableLanguage] = {
    "py": "python",
    "python": "python",
    "ts": "typescript",
    "typescript": "typescript",
    "tsx": "tsx",
    "js": "javascript",
    "javascript": "javascript",
    "go": "go",
}

BOUNDARY_TYPES: dict[ChunkableLanguage, set[str]] = {
    "python": {
        "function_definition",
        "class_definition",
        "decorated_definition",
    },
    "typescript": {
        "function_declaration",
        "class_declaration",
        "method_definition",
        "arrow_function",
        "export_statement",
    },
    "tsx": {
        "function_declaration",
        "class_declaration",
        "method_definition",
        "arrow_function",
        "export_statement",
    },
    "javascript": {
        "function_declaration",
        "class_declaration",
        "method_definition",
        "arrow_function",
        "export_statement",
    },
    "go": {
        "function_declaration",
        "method_declaration",
        "type_declaration",
    },
}


@dataclass
class CodeChunkResult:
    text: str
    symbol_name: str | None
    parent_symbol: str | None
    chunk_index: int


@lru_cache(maxsize=10)
def _get_parser(lang: SupportedLanguage):
    from tree_sitter_language_pack import get_parser

    return get_parser(lang)


def _node_name(node: Node | None) -> str | None:
    if node is None:
        return None

    name_node = node.child_by_field_name("name")
    if name_node is not None:
        name_text = name_node.text
        if name_text is not None:
            return name_text.decode("utf-8").strip() or None

    if node.type == "decorated_definition":
        for child in node.named_children:
            if child.type in {"function_definition", "class_definition"}:
                return _node_name(child)

    for child in node.named_children:
        if child.type in {"identifier", "property_identifier", "type_identifier"}:
            child_text = child.text
            if child_text is not None:
                return child_text.decode("utf-8").strip() or None

    return None


def _header(file_path: str, parent_symbol: str | None) -> str:
    if not file_path:
        return ""
    if parent_symbol:
        return f"# file: {file_path} | {parent_symbol}\n"
    return f"# file: {file_path}\n"


def _append_chunk(
    results: list[CodeChunkResult],
    text: str,
    symbol_name: str | None,
    parent_symbol: str | None,
    file_path: str,
) -> None:
    prefix = _header(file_path, parent_symbol)

    if len(text) > MAX_CHUNK_CHARS:
        for sub_chunk in chunk_text(text):
            if not sub_chunk.strip():
                continue
            results.append(
                CodeChunkResult(
                    text=f"{prefix}{sub_chunk}",
                    symbol_name=symbol_name,
                    parent_symbol=parent_symbol,
                    chunk_index=len(results),
                )
            )
        return

    stripped = text.strip()
    if not stripped:
        return

    results.append(
        CodeChunkResult(
            text=f"{prefix}{stripped}",
            symbol_name=symbol_name,
            parent_symbol=parent_symbol,
            chunk_index=len(results),
        )
    )


def chunk_code(source: str, language: str, file_path: str = "") -> list[CodeChunkResult] | None:
    normalized_language = LANGUAGE_PARSER_MAP.get(language.lower())
    if normalized_language is None:
        return None

    try:
        parser: Parser = _get_parser(normalized_language)
        tree: Tree = parser.parse(source.encode("utf-8"))
    except Exception:
        return None

    if tree.root_node.has_error:
        return None

    boundary_types = BOUNDARY_TYPES[normalized_language]
    chunks: list[CodeChunkResult] = []

    for child in tree.root_node.named_children:
        if child.type not in boundary_types:
            continue
        node_text_bytes = child.text
        if not node_text_bytes:
            continue
        node_text = node_text_bytes.decode("utf-8")
        symbol_name = _node_name(child)
        _append_chunk(
            results=chunks,
            text=node_text,
            symbol_name=symbol_name,
            parent_symbol=None,
            file_path=file_path,
        )

    if chunks:
        return chunks

    _append_chunk(
        results=chunks,
        text=source,
        symbol_name=None,
        parent_symbol=None,
        file_path=file_path,
    )
    return chunks
