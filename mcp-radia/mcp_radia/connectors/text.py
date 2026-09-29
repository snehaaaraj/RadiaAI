"""Turning vendor rich-text formats into plain text.

Every system in the digital thread stores prose in its own markup - Jama and
Confluence in HTML/XHTML, Jira in Atlassian Document Format (ADF) JSON. Handing
that markup to a model wastes tokens and reads badly, so each connector
flattens it here before returning.
"""

import html
import re
from typing import Any

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")

# Elements whose content is markup machinery, not prose. Dropped wholesale -
# stripping only the tags would leave CSS and JavaScript in the output.
_DROP_ELEMENTS_RE = re.compile(
    r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>",
)

# ADF node types that end a block and therefore imply a line break.
_ADF_BLOCK_TYPES = frozenset(
    {
        "doc",
        "paragraph",
        "heading",
        "blockquote",
        "codeBlock",
        "listItem",
        "panel",
        "rule",
        "taskItem",
        "tableRow",
        "mediaSingle",
        "expand",
    }
)


def normalize_lines(text: str) -> str:
    """Collapse runs of spaces and blank lines while preserving paragraph breaks."""
    lines = [_WS_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line != "").strip()


def strip_html(value: str | None) -> str:
    """Convert an HTML / XHTML fragment into readable plain text.

    Used for Jama rich-text fields and Confluence storage-format bodies.
    """
    if not value:
        return ""
    text = _DROP_ELEMENTS_RE.sub(" ", value)
    # Block-level breaks become newlines before the tags are stripped, so
    # paragraph structure is not lost.
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|h[1-6])\s*>", "\n", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    return normalize_lines(text)


def adf_to_text(node: object) -> str:
    """Flatten an Atlassian Document Format document into plain text.

    ADF is the JSON body format Jira Cloud's v3 API returns for descriptions
    and comments. Only the human-readable payload is kept: text runs, mention
    and emoji labels, and card URLs. Unknown node types are still traversed, so
    a format addition degrades to "text we did not specially handle" rather
    than silently dropping content.
    """
    if not isinstance(node, dict):
        # Jira returns a plain string here on v2, and null when empty.
        return normalize_lines(str(node)) if isinstance(node, str) else ""
    parts: list[str] = []
    _walk_adf(node, parts)
    return normalize_lines("".join(parts))


def _walk_adf(node: dict[str, Any], out: list[str]) -> None:
    node_type = node.get("type")

    if node_type == "text":
        out.append(str(node.get("text", "")))
        return
    if node_type == "hardBreak":
        out.append("\n")
        return
    if node_type == "mention":
        attrs = node.get("attrs") or {}
        out.append(str(attrs.get("text") or ""))
        return
    if node_type == "emoji":
        attrs = node.get("attrs") or {}
        out.append(str(attrs.get("text") or attrs.get("shortName") or ""))
        return
    if node_type in ("inlineCard", "blockCard", "embedCard"):
        attrs = node.get("attrs") or {}
        out.append(str(attrs.get("url") or ""))
        return

    content = node.get("content")
    if isinstance(content, list):
        for child in content:
            if isinstance(child, dict):
                _walk_adf(child, out)

    if node_type in _ADF_BLOCK_TYPES:
        out.append("\n")
