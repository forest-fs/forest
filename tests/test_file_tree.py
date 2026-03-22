"""Tests for ``forest.services.file_tree``."""

from __future__ import annotations

import uuid

from forest.models.file_node import FileNode, NodeType
from forest.services.file_tree import file_nodes_to_tree_lines


def _file(full_path: str, source_url: str | None = "https://x.example/a") -> FileNode:
    return FileNode(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        parent_id=None,
        name="x",
        node_type=NodeType.file,
        full_path=full_path,
        source_url=source_url,
        message_url=None,
        summary=None,
        embedding=None,
        external_key=None,
    )


def test_file_nodes_to_tree_lines_nested() -> None:
    nodes = [
        _file("/project/src/main.py"),
        _file("/project/src/util.py"),
        _file("/project/README.md", source_url=None),
    ]
    lines = file_nodes_to_tree_lines(nodes)
    assert lines == [
        "- *project/*",
        "  - README.md",
        "  - *src/*",
        "    - main.py — https://x.example/a",
        "    - util.py — https://x.example/a",
    ]


def test_file_nodes_to_tree_lines_sorted_siblings() -> None:
    nodes = [_file("/z/a"), _file("/m/b"), _file("/m/a")]
    lines = file_nodes_to_tree_lines(nodes)
    assert lines == [
        "- *m/*",
        "  - a — https://x.example/a",
        "  - b — https://x.example/a",
        "- *z/*",
        "  - a — https://x.example/a",
    ]


def test_file_nodes_to_tree_lines_slack_mrkdwn_links() -> None:
    nodes = [_file("/m/a")]
    lines = file_nodes_to_tree_lines(nodes, slack_mrkdwn_links=True)
    assert lines == [
        "- *m/*",
        "  - <https://x.example/a|a>",
    ]
