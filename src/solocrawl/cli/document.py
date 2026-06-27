"""Shared CLI formatting for fetched page content."""

from __future__ import annotations

import json

from solocrawl.core.models import FetchResult


def render_fetch_document(result: FetchResult) -> str:
    """Prepend a YAML front-matter block when page metadata is available."""
    front_matter = _front_matter(result)
    return f"{front_matter}{result.content}" if front_matter else result.content


def _front_matter(result: FetchResult) -> str:
    fields = [
        ("title", result.title),
        ("author", result.author),
        ("date", result.date),
        ("language", result.language),
        ("site_name", result.site_name),
    ]
    present = [(key, value) for key, value in fields if value]
    if not present:
        return ""

    lines = ["---", f"url: {_yaml_scalar(result.url)}"]
    lines.extend(f"{key}: {_yaml_scalar(value)}" for key, value in present)
    lines.append("---")
    lines.append("")
    return "\n".join(lines) + "\n"


def _yaml_scalar(value: str) -> str:
    # A JSON string literal is also a valid YAML double-quoted scalar.
    return json.dumps(value, ensure_ascii=False)
