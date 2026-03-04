"""File classifier - ported from packages/ai/src/codebase/classifier.ts."""

import re
from dataclasses import dataclass

LANG_MAP: dict[str, str] = {
    "ts": "typescript",
    "tsx": "tsx",
    "js": "javascript",
    "jsx": "javascript",
    "py": "python",
    "go": "go",
    "md": "markdown",
    "yaml": "yaml",
    "yml": "yaml",
    "json": "json",
}

DOMAIN_SEGMENTS = {
    "api", "models", "services", "utils", "components", "hooks", "lib",
    "routes", "controllers", "middleware", "helpers", "types", "schema",
    "db", "database",
}

ALLOWED_EXTENSIONS = {
    "ts", "tsx", "js", "jsx", "py", "go", "md", "yaml", "yml", "json",
}


def detect_language(file_path: str) -> str | None:
    """Return tree-sitter language name for a file path, or None if unsupported.

    Maps file extensions to tree-sitter language names.
    Note: .tsx maps to 'tsx' (separate parser from 'typescript').
    """
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    return LANG_MAP.get(ext)

@dataclass
class FileClassification:
    domain: str
    artifact_type: str
    language: str


def classifyFile(file_path: str) -> FileClassification:
    """Classify a file by path."""
    parts = file_path.replace("\\", "/").split("/")
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

    language = LANG_MAP.get(ext, "unknown")

    domain = next((p for p in parts if p.lower() in DOMAIN_SEGMENTS), "general")

    artifact_type = "source"
    lower = file_path.lower()

    if any(x in lower for x in [".test.", ".spec.", "/test", "/tests", "/__tests__"]):
        artifact_type = "test"
    elif "config" in lower or ext in ("yaml", "yml", "json"):
        artifact_type = "config"
    elif ext == "md":
        artifact_type = "doc"
    elif "model" in lower or "schema" in lower:
        artifact_type = "model"
    elif any(x in lower for x in ["api", "route", "controller", "endpoint"]):
        artifact_type = "api"

    return FileClassification(domain=domain, artifact_type=artifact_type, language=language)


def isSecretFile(file_path: str, content: str) -> bool:
    """Detect whether a file should be skipped because it likely contains secrets."""
    if ".env" in file_path:
        return True
    if re.search(r"API_KEY\s*=|password\s*:|SECRET\s*=", content, re.IGNORECASE):
        return True
    return False
