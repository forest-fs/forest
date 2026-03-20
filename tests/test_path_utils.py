"""
Unit tests for :mod:`forest.services.path_utils` normalization rules.
"""

import pytest

from forest.services.path_utils import (
    leaf_name_from_path,
    normalize_full_path,
    parent_full_path,
    segments_under_root,
)


def test_normalize_root() -> None:
    """Empty and relative segments normalize to the virtual root ``/``."""
    assert normalize_full_path("") == "/"
    assert normalize_full_path("/") == "/"
    assert normalize_full_path("a/b") == "/a/b"


def test_normalize_rejects_dotdot() -> None:
    """Parent traversal segments must raise for safety."""
    with pytest.raises(ValueError):
        normalize_full_path("/a/../b")


def test_leaf_and_parent() -> None:
    """Leaf and parent helpers agree on simple nested paths."""
    assert leaf_name_from_path("/a/b/c.txt") == "c.txt"
    assert parent_full_path("/a/b/c.txt") == "/a/b"


def test_segments_under_root() -> None:
    """Directory segments under root exclude the final filename when path has depth."""
    assert segments_under_root("/a/b") == ["a", "b"]
