"""
Deterministic Skillz checks on requirement text.

These are the mechanical Skillz rules that need no judgment: controlled
vocabulary (C18), presentation lexicon (C21), a single ``shall`` with no competing
modal (C12), and no provisional values (C17). The vocabulary itself comes from
the Skillz package, so the checks follow whichever Skillz revision is loaded.
"""

from __future__ import annotations

import re

from radia_ai.features.jama_requirement_reviewer.models.review_models import SkillzCheckIssue
from radia_ai.features.jama_requirement_reviewer.skillz.package import SkillzWordLists

_PROVISIONAL_TERMS = {"tbd", "tbc"}
_COMPETING_MODALS = ("must", "should", "will")
_MASK = "\u2588"


def check_requirement_text(text: str, word_lists: SkillzWordLists) -> list[SkillzCheckIssue]:
    """Return every deterministic Skillz violation in *text*, one per rule and term."""
    issues: list[SkillzCheckIssue] = []
    seen: set[tuple[str, str]] = set()

    def add(rule_id: str, term: str, message: str) -> None:
        key = (rule_id, term.lower())
        if key not in seen:
            seen.add(key)
            issues.append(SkillzCheckIssue(rule_id=rule_id, term=term, message=message))

    stripped = text.strip()
    if not stripped:
        return issues

    # Adopted terms of art may contain an otherwise forbidden word (C18).
    masked = stripped
    for term in sorted(word_lists.defined_terms, key=len, reverse=True):
        masked = _word_pattern(term).sub(lambda match: _MASK * len(match.group(0)), masked)

    for term in word_lists.forbidden_requirement:
        if _word_pattern(term).search(masked):
            add("C18", term, f"'{term}' is forbidden or controlled language in a requirement.")

    for term in word_lists.forbidden_everywhere:
        if _word_pattern(term).search(masked):
            if term.lower() in _PROVISIONAL_TERMS:
                add("C17", term, f"'{term}' is a provisional value and is not permitted.")
            else:
                add("C18", term, f"'{term}' is not permitted before certification.")

    for term in word_lists.forbidden_display:
        if _word_pattern(term).search(masked):
            add("C21", term, f"'{term}' names equipment and is prohibited in requirement text.")

    for pattern, preferred in word_lists.lexicon.items():
        try:
            match = re.search(pattern, masked, re.IGNORECASE)
        except re.error:
            continue
        if match:
            add("C21", match.group(0), f"Use the settled term '{preferred}'.")

    shall_count = len(_word_pattern("shall").findall(stripped))
    if shall_count == 0:
        add("C12", "shall", "The requirement must state its obligation with 'shall'.")
    elif shall_count > 1:
        add("C12", "shall", "Use exactly one 'shall' per requirement.")

    for modal in _COMPETING_MODALS:
        if _word_pattern(modal).search(stripped):
            add("C12", modal, f"Do not use '{modal}' in the obligation; use one 'shall'.")

    whole_text_bracketed = stripped.startswith("[") and stripped.endswith("]")
    if not whole_text_bracketed and re.search(r"\[[^\]]*\]", stripped):
        add("C17", "[...]", "Bracketed provisional values are not permitted inside the text.")

    return issues


def _word_pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w-]){re.escape(term)}(?![\w-])", re.IGNORECASE)
