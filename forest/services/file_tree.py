"""
Render captured file nodes as nested Markdown bullet lists (virtual path tree).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from forest.models.file_node import FileNode
from forest.services.path_utils import segments_under_root


@dataclass
class _PathTrie:
    children: dict[str, _PathTrie] = field(default_factory=dict)
    file: FileNode | None = None


def _insert(trie: _PathTrie, segments: list[str], node: FileNode) -> None:
    if not segments:
        return
    cur = trie
    for seg in segments[:-1]:
        cur = cur.children.setdefault(seg, _PathTrie())
    leaf_name = segments[-1]
    leaf = cur.children.setdefault(leaf_name, _PathTrie())
    leaf.file = node


def _slack_mrkdwn_file_link(name: str, url: str) -> str:
    """``<url|name>`` for Slack mrkdwn."""
    return f"<{url}|{name}>"


def _render_lines(trie: _PathTrie, depth: int, *, slack_mrkdwn_links: bool) -> list[str]:
    lines: list[str] = []
    indent = "  " * depth
    items = sorted(trie.children.items(), key=lambda kv: kv[0].casefold())
    for name, child in items:
        if child.file is not None:
            link = child.file.source_url or child.file.message_url or ""
            if link:
                if slack_mrkdwn_links:
                    content = _slack_mrkdwn_file_link(name, link)
                else:
                    content = f"{name} — {link}"
            else:
                content = name
            lines.append(f"{indent}- {content}")
        else:
            lines.append(f"{indent}- *{name}/*")
        lines.extend(
            _render_lines(
                child,
                depth + 1,
                slack_mrkdwn_links=slack_mrkdwn_links,
            )
        )
    return lines


def file_nodes_to_tree_lines(
    nodes: list[FileNode],
    *,
    slack_mrkdwn_links: bool = False,
) -> list[str]:
    """
    Build sorted, depth-first markdown list lines from file ``full_path`` values.

    Nested ``-`` bullets use two spaces per level; folders use ``*name/*`` (Slack bold).

    Parameters
    ----------
    nodes : list of FileNode
        File leaves (``node_type=file``); typically from
        :meth:`forest.repositories.file_node_repo.FileNodeRepository.list_files_flat`.
    slack_mrkdwn_links : bool, optional
        If True, render file leaves as ``<url|filename>`` for Slack mrkdwn.

    Returns
    -------
    list of str
        One output row per row; no outer markdown fences.
    """
    root = _PathTrie()
    for n in nodes:
        segs = segments_under_root(n.full_path)
        if not segs:
            continue
        _insert(root, segs, n)
    return _render_lines(root, 0, slack_mrkdwn_links=slack_mrkdwn_links)
