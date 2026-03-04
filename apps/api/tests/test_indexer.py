"""Tests for IndexStats dataclass and _repo_name_from_url helper."""

from gamole_ai.codebase.indexer import IndexStats


def test_indexstats_has_new_fields():
    stats = IndexStats(repo_name="test")
    assert hasattr(stats, "files_skipped")
    assert hasattr(stats, "orphans_deleted")
    assert stats.files_skipped == 0
    assert stats.orphans_deleted == 0


def test_indexstats_defaults():
    stats = IndexStats(repo_name="my-repo")
    assert stats.repo_name == "my-repo"
    assert stats.files_indexed == 0
    assert stats.chunks_created == 0
    assert stats.errors == 0
    assert stats.files_skipped == 0
    assert stats.orphans_deleted == 0


def test_indexstats_update():
    stats = IndexStats(repo_name="test")
    stats.files_indexed = 10
    stats.chunks_created = 50
    stats.files_skipped = 3
    stats.orphans_deleted = 2
    assert stats.files_indexed == 10
    assert stats.chunks_created == 50
    assert stats.files_skipped == 3
    assert stats.orphans_deleted == 2


def test_repo_name_from_https_url():
    from gamole_ai.codebase.indexer import _repo_name_from_url

    name = _repo_name_from_url("https://github.com/myorg/myrepo.git")
    assert name == "myorg-myrepo"


def test_repo_name_from_url_no_git():
    from gamole_ai.codebase.indexer import _repo_name_from_url

    name = _repo_name_from_url("https://github.com/myorg/myrepo")
    assert name == "myorg-myrepo"


def test_repo_name_from_url_special_chars():
    from gamole_ai.codebase.indexer import _repo_name_from_url

    name = _repo_name_from_url("https://github.com/my-org/my.repo.git")
    # Special chars replaced with underscores
    assert "my" in name
    assert " " not in name


def test_indexstats_import():
    from gamole_ai.codebase.indexer import REPO_LIMIT_ERROR_PREFIX, IndexStats  # noqa: F401

    assert REPO_LIMIT_ERROR_PREFIX == "REPO_LIMIT_EXCEEDED"
