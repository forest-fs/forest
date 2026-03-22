"""
``LLMService``: chat completions and embeddings through OpenRouter.

Uses :class:`openai.AsyncOpenAI` with ``base_url`` from settings. Parses JSON-shaped
model outputs into Pydantic schemas with a single repair pass on validation failure.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from openai import APIStatusError, AsyncOpenAI, RateLimitError
from pydantic import ValidationError

from forest.config import Settings, get_settings
from forest.models.file_node import EMBEDDING_VECTOR_DIMENSIONS
from forest.schemas.llm_io import BaseTreeOutput, RouteResult

_log = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_markdown_fences(text: str) -> str:
    """
    Remove common ``` / ```json fences around model output.

    Parameters
    ----------
    text : str
        Raw assistant message content.

    Returns
    -------
    str
        Stripped text suitable for ``json.loads``.
    """
    text = text.strip()
    text = _JSON_FENCE.sub("", text).strip()
    return text


def _parse_json_object(raw: str) -> dict[str, Any]:
    """
    Parse a single JSON object from model text.

    Parameters
    ----------
    raw : str
        Model output after fence stripping.

    Returns
    -------
    dict
        Parsed JSON object.

    Raises
    ------
    json.JSONDecodeError
        If content is not valid JSON.
    """
    cleaned = _strip_markdown_fences(raw)
    return json.loads(cleaned)


class LLMService:
    """
    Facade for onboarding tree generation, per-file routing, and summary embeddings.

    Parameters
    ----------
    settings : Settings, optional
        If omitted, uses :func:`forest.config.get_settings()` (process singleton).

    Notes
    -----
    Retries transient HTTP failures (429, selected 5xx) with exponential backoff for
    chat and embedding calls. Never logs secrets or full prompts at INFO.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        headers: dict[str, str] = {}
        if self._settings.openrouter_http_referer:
            headers["HTTP-Referer"] = self._settings.openrouter_http_referer
        if self._settings.openrouter_app_name:
            headers["X-Title"] = self._settings.openrouter_app_name
        self._client = AsyncOpenAI(
            api_key=self._settings.openrouter_api_key.get_secret_value(),
            base_url=self._settings.openrouter_base_url,
            default_headers=headers or None,
        )

    async def _chat_text(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        """
        Low-level chat completion returning assistant text only.

        Parameters
        ----------
        system : str
            System prompt.
        user : str
            User message (often JSON context).
        temperature : float, optional
            Sampling temperature forwarded to the API.

        Returns
        -------
        str
            First choice message content (may be empty string).

        Raises
        ------
        Exception
            Last error from OpenRouter after retries exhausted.

        Notes
        -----
        Non-retryable ``APIStatusError`` (except selected codes) is re-raised immediately.
        """
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = await self._client.chat.completions.create(
                    model=self._settings.chat_model_id,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                )
                choice = resp.choices[0]
                content = choice.message.content or ""
                return content
            except (RateLimitError, APIStatusError, TimeoutError) as e:
                last_err = e
                if isinstance(e, APIStatusError) and getattr(e, "status_code", None) not in (
                    None,
                    429,
                    500,
                    502,
                    503,
                    504,
                ):
                    raise
                delay = 0.5 * (2**attempt)
                _log.warning(
                    "llm chat retry",
                    extra={
                        "operation": "chat",
                        "attempt": attempt + 1,
                        "llm_backend": "openrouter",
                    },
                )
                await asyncio.sleep(delay)
        assert last_err is not None
        raise last_err

    async def generate_base_tree(
        self,
        channel_names: list[str],
        workspace_name: str | None,
        *,
        channel_histories: list[dict[str, Any]] | None = None,
    ) -> BaseTreeOutput:
        """
        Propose a nested folder tree from channel names, optional message
        excerpts, and workspace metadata.

        Parameters
        ----------
        channel_names : list of str
            Channel / thread labels as routing hints (order matches histories when present).
        workspace_name : str or None
            Optional workspace display name for context.
        channel_histories : list of dict, optional
            Rows with keys ``channel``, ``excerpt``, ``messages_scanned``, ``truncated`` from
            a full-history scan (excerpts may be capped).

        Returns
        -------
        BaseTreeOutput
            Validated folder forest under ``folders``.

        Notes
        -----
        On JSON or schema failure, performs one follow-up "fix JSON only" completion.
        """
        system = (
            "You output JSON only, no prose. "
            "Design a sensible folder tree for organizing files shared in a team workspace. "
            "Return shape: {\"folders\":[{\"name\":string,\"children\":[...]}]}. "
            "Max depth 4. Names short, filesystem-safe (no slashes). "
            "Use channel names and, when present, message excerpts to infer topics, projects, and "
            "how people actually discuss work—not only channel titles. Merge related topics. "
            "If excerpts are truncated or missing for a channel, rely on its name."
        )
        payload: dict[str, Any] = {
            "workspace_name": workspace_name,
            "text_channels": channel_names,
        }
        if channel_histories:
            payload["channel_histories"] = channel_histories
        user = json.dumps(payload, ensure_ascii=False)
        raw = await self._chat_text(system, user, temperature=0.3)
        try:
            data = _parse_json_object(raw)
            return BaseTreeOutput.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            _log.warning(
                "llm base tree parse failed, retrying with fix instruction",
                extra={"operation": "generate_base_tree", "llm_backend": "openrouter"},
            )
            fix = await self._chat_text(
                "Return only valid JSON matching {\"folders\":[{\"name\":string,\"children\":[]}]}",
                f"Fix this to valid JSON only:\n{raw[:8000]}",
                temperature=0.0,
            )
            data = _parse_json_object(fix)
            return BaseTreeOutput.model_validate(data)

    async def route_file(
        self,
        *,
        context_transcript: str,
        cue_title: str,
        source_url: str,
        directory_paths: list[str],
    ) -> RouteResult:
        """
        Decide a target virtual path and summary for one attachment/link cue.

        Parameters
        ----------
        context_transcript : str
            Compact recent chat context (capped before the LLM).
        cue_title : str
            Filename or URL label.
        source_url : str
            Canonical asset URL.
        directory_paths : list of str
            Existing directory ``full_path`` values from the database.

        Returns
        -------
        RouteResult
            Validated routing JSON.

        Notes
        -----
        Uses the same JSON repair strategy as :meth:`generate_base_tree`.
        """
        system = (
            "You classify where a shared link or attachment should live in a virtual folder tree. "
            "Output JSON only: "
            '{"target_path":"/path/with/filename.ext","create_missing_dirs":true,'
            '"one_sentence_summary":"...","suggested_name":"filename.ext"} '
            "target_path must start with / and include the file name. "
            "Prefer existing directory paths when they fit. "
            "Keep paths shallow when unsure; use /Inbox for ambiguous items."
        )
        user = json.dumps(
            {
                "context_transcript": context_transcript[:8000],
                "cue_title": cue_title,
                "source_url": source_url,
                "existing_directories": directory_paths[:500],
            },
            ensure_ascii=False,
        )
        raw = await self._chat_text(system, user, temperature=0.2)
        try:
            data = _parse_json_object(raw)
            return RouteResult.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            fix = await self._chat_text(
                "Return only valid JSON for keys "
                "target_path, create_missing_dirs, one_sentence_summary, suggested_name.",
                f"Fix this to valid JSON only:\n{raw[:8000]}",
                temperature=0.0,
            )
            data = _parse_json_object(fix)
            return RouteResult.model_validate(data)

    async def embed_summary(self, text: str) -> list[float]:
        """
        Embed summary text using the configured ``EMBEDDING_MODEL_ID``.

        Sends ``dimensions=EMBEDDING_VECTOR_DIMENSIONS`` so OpenAI-compatible models
        that support shortening (e.g. ``text-embedding-3-small``) return vectors that
        match the ``pgvector`` column.

        Parameters
        ----------
        text : str
            Input truncated to a safe size before the API call.

        Returns
        -------
        list of float
            Embedding vector (dimension must match the database column).

        Raises
        ------
        Exception
            Last error after retries exhausted.
        """
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = await self._client.embeddings.create(
                    model=self._settings.embedding_model_id,
                    input=text[:8000],
                    dimensions=EMBEDDING_VECTOR_DIMENSIONS,
                )
                vec = list(resp.data[0].embedding)
                if len(vec) != EMBEDDING_VECTOR_DIMENSIONS:
                    raise ValueError(
                        f"Embedding length {len(vec)} does not match schema "
                        f"{EMBEDDING_VECTOR_DIMENSIONS}. Pick an embedding model with "
                        "that output size, or change the pgvector column and "
                        "EMBEDDING_VECTOR_DIMENSIONS in code via migrations "
                        "(see docs/llm-configuration.md)."
                    )
                return vec
            except (RateLimitError, APIStatusError, TimeoutError) as e:
                last_err = e
                if isinstance(e, APIStatusError) and getattr(e, "status_code", None) not in (
                    None,
                    429,
                    500,
                    502,
                    503,
                    504,
                ):
                    raise
                await asyncio.sleep(0.5 * (2**attempt))
        assert last_err is not None
        raise last_err
