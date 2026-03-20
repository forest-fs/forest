"""
Pure path normalization helpers for virtual ``full_path`` strings.

Security note: ``..`` segments are rejected to avoid path escape attacks when
mapping LLM output to stored paths.
"""


def normalize_full_path(path: str) -> str:
    """
    Normalize a user- or model-supplied path to a leading-slash absolute form.

    Parameters
    ----------
    path : str
        Raw path; backslashes are converted to forward slashes.

    Returns
    -------
    str
        ``"/"`` for empty or root-like input; otherwise ``"/seg1/seg2/..."``.

    Raises
    ------
    ValueError
        If any segment is ``".."`` (parent traversal not allowed).

    Notes
    -----
    Empty and ``"."`` segments are dropped. A lone ``"/"`` or whitespace-only
    input becomes the virtual root path ``"/"``.
    """
    path = path.strip().replace("\\", "/")
    if not path.startswith("/"):
        path = "/" + path
    parts: list[str] = []
    for segment in path.split("/"):
        if not segment or segment == ".":
            continue
        if segment == "..":
            raise ValueError("path must not contain parent segments")
        parts.append(segment)
    if not parts:
        return "/"
    return "/" + "/".join(parts)


def path_segments_for_directories(full_path: str) -> list[str]:
    """
    Return directory segments for a **file** path (exclude the leaf filename).

    Parameters
    ----------
    full_path : str
        Normalized or raw path; normalized internally.

    Returns
    -------
    list of str
        Segments for parent directories only. Empty list if file is at root (invalid
        for real files) or path is ``/``.

    Examples
    --------
    ``"/a/b/c.txt"`` → ``["a", "b"]``
    """
    norm = normalize_full_path(full_path)
    if norm == "/":
        return []
    parts = norm.strip("/").split("/")
    return parts[:-1]


def leaf_name_from_path(full_path: str) -> str:
    """
    Return the final path segment (file or directory name).

    Parameters
    ----------
    full_path : str
        Absolute path with at least one segment under root.

    Returns
    -------
    str
        Last ``/``-delimited component.

    Raises
    ------
    ValueError
        If ``full_path`` normalizes to root ``"/"`` (no leaf name).
    """
    norm = normalize_full_path(full_path)
    if norm == "/":
        raise ValueError("invalid file path")
    return norm.rsplit("/", 1)[-1]


def parent_full_path(full_path: str) -> str:
    """
    Return the parent directory's absolute path.

    Parameters
    ----------
    full_path : str
        Child path (typically a file path).

    Returns
    -------
    str
        Parent path, or ``"/"`` if the parent is the virtual root.

    Raises
    ------
    ValueError
        If ``full_path`` normalizes to root (no parent).
    """
    norm = normalize_full_path(full_path)
    if norm == "/":
        raise ValueError("invalid path")
    parent, _, _ = norm.rpartition("/")
    return parent if parent else "/"


def segments_under_root(path: str) -> list[str]:
    """
    Split a normalized absolute path into segments under the virtual root.

    Parameters
    ----------
    path : str
        Path to normalize.

    Returns
    -------
    list of str
        Segments without leading or trailing slashes; empty for root ``"/"``.

    Notes
    -----
    Used by :meth:`forest.repositories.file_node_repo.FileNodeRepository.ensure_path`
    to walk/create directory chains.
    """
    norm = normalize_full_path(path)
    if norm == "/":
        return []
    return norm.strip("/").split("/")
