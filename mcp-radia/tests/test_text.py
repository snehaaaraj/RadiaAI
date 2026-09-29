"""Unit tests for the shared rich-text flattening helpers."""

import pytest

from mcp_radia.connectors.text import adf_to_text, strip_html

pytestmark = pytest.mark.unit


# -- strip_html --------------------------------------------------------------


def test_paragraphs_become_separate_lines() -> None:
    assert strip_html("<p>One.</p><p>Two.</p>") == "One.\nTwo."


def test_list_items_become_separate_lines() -> None:
    assert strip_html("<ul><li>a</li><li>b</li></ul>") == "a\nb"


def test_entities_are_unescaped() -> None:
    assert strip_html("<p>a &gt; b &amp; c &#37;</p>") == "a > b & c %"


def test_script_and_style_content_is_dropped_entirely() -> None:
    """Stripping only the tags would leave code in the text."""
    html = "<p>Hi</p><script>alert('x')</script><style>.a{color:red}</style>"

    result = strip_html(html)

    assert result == "Hi"


def test_whitespace_runs_collapse_but_line_structure_survives() -> None:
    assert strip_html("<p>a     b</p>\n\n\n<p>c</p>") == "a b\nc"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_empty_inputs_give_empty_output(value: str | None) -> None:
    assert strip_html(value) == ""


# -- adf_to_text -------------------------------------------------------------


def test_text_runs_are_concatenated_within_a_paragraph() -> None:
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Hello "},
                    {"type": "text", "text": "world", "marks": [{"type": "strong"}]},
                ],
            }
        ],
    }

    assert adf_to_text(doc) == "Hello world"


def test_paragraphs_are_separated_by_newlines() -> None:
    doc = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "One"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Two"}]},
        ],
    }

    assert adf_to_text(doc) == "One\nTwo"


def test_mentions_and_emoji_render_their_labels() -> None:
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "mention", "attrs": {"id": "1", "text": "@Dana"}},
                    {"type": "text", "text": " "},
                    {"type": "emoji", "attrs": {"shortName": ":tada:"}},
                ],
            }
        ],
    }

    assert adf_to_text(doc) == "@Dana :tada:"


def test_cards_render_their_url() -> None:
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "inlineCard", "attrs": {"url": "https://x/1"}}],
            }
        ],
    }

    assert adf_to_text(doc) == "https://x/1"


def test_nested_lists_keep_one_item_per_line() -> None:
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "a"}]}
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "b"}]}
                        ],
                    },
                ],
            }
        ],
    }

    assert adf_to_text(doc) == "a\nb"


def test_hard_breaks_become_newlines() -> None:
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "a"},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "b"},
                ],
            }
        ],
    }

    assert adf_to_text(doc) == "a\nb"


def test_unknown_node_types_are_still_traversed() -> None:
    """A new ADF node type should degrade to plain text, not silently vanish."""
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "someFutureNode",
                "content": [{"type": "text", "text": "still here"}],
            }
        ],
    }

    assert adf_to_text(doc) == "still here"


@pytest.mark.parametrize("value", [None, {}, [], 0])
def test_non_document_inputs_give_empty_output(value: object) -> None:
    assert adf_to_text(value) == ""


def test_a_plain_string_body_is_passed_through() -> None:
    """Jira v2 returns a wiki-markup string rather than an ADF object."""
    assert adf_to_text("just text") == "just text"
