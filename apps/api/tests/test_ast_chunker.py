"""Tests for the AST-based code chunker."""

from gamole_ai.codebase.ast_chunker import chunk_code


def test_python_function_chunking():
    source = "def hello():\n    return 42\n\ndef world():\n    return 99"
    chunks = chunk_code(source, "python", "test.py")
    assert chunks is not None
    assert len(chunks) == 2
    assert chunks[0].symbol_name == "hello"
    assert chunks[1].symbol_name == "world"
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1


def test_python_decorator_preserved():
    source = "@staticmethod\ndef hello():\n    return 42\n\ndef world():\n    return 99"
    chunks = chunk_code(source, "python", "test.py")
    assert chunks is not None
    assert len(chunks) == 2
    # First chunk should contain the decorator
    assert "@staticmethod" in chunks[0].text
    assert "hello" in chunks[0].text


def test_tsx_parser_used():
    source = "export function App() { return 42; }"
    chunks = chunk_code(source, "tsx", "App.tsx")
    assert chunks is not None
    assert len(chunks) >= 1


def test_unsupported_language_returns_none():
    result = chunk_code("# Hello", "markdown", "readme.md")
    assert result is None


def test_malformed_code_returns_none():
    result = chunk_code("def ((( broken {{{", "python", "bad.py")
    assert result is None


def test_file_path_in_header():
    source = "def foo():\n    pass"
    chunks = chunk_code(source, "python", "src/utils.py")
    assert chunks is not None
    assert len(chunks) >= 1
    assert "src/utils.py" in chunks[0].text


def test_typescript_function_chunking():
    source = "function greet(name: string): string {\n    return `Hello ${name}`;\n}"
    chunks = chunk_code(source, "typescript", "greet.ts")
    assert chunks is not None
    assert len(chunks) >= 1


def test_go_function_chunking():
    source = (
        'package main\n\nfunc Hello() string {\n    return "hello"\n}\n\n'
        'func World() string {\n    return "world"\n}'
    )
    chunks = chunk_code(source, "go", "main.go")
    assert chunks is not None
    assert len(chunks) >= 1


def test_python_class_chunking():
    source = "class Foo:\n    def bar(self):\n        pass\n\nclass Baz:\n    pass"
    chunks = chunk_code(source, "python", "models.py")
    assert chunks is not None
    assert len(chunks) == 2
    assert any(c.symbol_name == "Foo" for c in chunks)
    assert any(c.symbol_name == "Baz" for c in chunks)


def test_language_aliases():
    source = "def foo():\n    pass"
    # Both "py" and "python" should work
    chunks_py = chunk_code(source, "py", "test.py")
    chunks_python = chunk_code(source, "python", "test.py")
    assert chunks_py is not None
    assert chunks_python is not None
    assert len(chunks_py) == len(chunks_python)
