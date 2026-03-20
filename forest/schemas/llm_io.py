"""
Structured outputs expected from the chat model during onboarding and ingest routing.

All values are produced via OpenRouter (OpenAI-compatible API); prompts enforce JSON.
"""

from pydantic import BaseModel, Field


class BaseTreeFolder(BaseModel):
    """
    Recursive folder node for onboarding seeding (directories only).

    Attributes
    ----------
    name : str
        Single path segment (no slashes).
    children : list of BaseTreeFolder
        Nested folders under this node.

    Notes
    -----
    Files are not created at seed time; only directory rows are materialized.
    """

    name: str = Field(..., min_length=1, max_length=256)
    children: list["BaseTreeFolder"] = Field(default_factory=list)


BaseTreeFolder.model_rebuild()


class BaseTreeOutput(BaseModel):
    """
    Top-level JSON envelope returned by ``generate_base_tree``.

    Attributes
    ----------
    folders : list of BaseTreeFolder
        Forest of top-level directories under the virtual root.
    """

    folders: list[BaseTreeFolder] = Field(default_factory=list)


class RouteResult(BaseModel):
    """
    Routing decision for a single attachment or URL cue.

    Attributes
    ----------
    target_path : str
        Absolute virtual path including filename, starting with ``/``.
    create_missing_dirs : bool
        Hint for services; parent directories are ensured idempotently regardless.
    one_sentence_summary : str
        Stored on the ``FileNode`` and embedded for future search.
    suggested_name : str
        Preferred leaf name; may override or refine the path's final segment.

    Notes
    -----
    Services normalize paths and fall back to ``/Inbox`` when parsing or LLM calls fail.
    """

    target_path: str = Field(
        ...,
        description="Full virtual path including file name, starting with /",
    )
    create_missing_dirs: bool = True
    one_sentence_summary: str = ""
    suggested_name: str = ""
