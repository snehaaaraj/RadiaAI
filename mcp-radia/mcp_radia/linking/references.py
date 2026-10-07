"""Finding cross-system identifiers written into prose.

The genuinely interesting hops in a digital thread are often not recorded as
first-class links at all - somebody types "traced to BMS-451" into a Jama
custom field, or writes "implements SRS-42" in a Confluence page. This module
spots those identifiers so the linking layer can try to resolve them.

This is a **heuristic**, which is why it is opt-in and why every item it
produces is tagged ``discovered_via="text"``. A key-shaped string is not proof
of a relationship.
"""

import re

#: Matches Jira-style and Jama-style document keys: an uppercase prefix, a
#: hyphen, and a number. Deliberately narrow - a looser pattern turns ordinary
#: hyphenated words and dates into false hits.
_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,19}-\d{1,9})\b")

#: Strings that match the key shape but are never item keys. Extend as needed.
_STOP_KEYS = frozenset(
    {
        "UTF-8",
        "ISO-8601",
        "SHA-1",
        "SHA-256",
        "RFC-2119",
        "IEC-61508",
        "ISO-26262",
        "DO-178",
        "MIL-STD",
    }
)


def extract_candidate_keys(*texts: str | None, exclude: str | None = None) -> list[str]:
    """Return candidate item keys found in ``texts``, in first-seen order.

    Args:
        texts: Any prose to scan. ``None`` entries are ignored.
        exclude: A key to drop - normally the item being asked about, which
            routinely names itself in its own description.

    Returns:
        Deduplicated candidate keys, order preserved so the most prominent
        reference stays first.
    """
    excluded = exclude.upper() if exclude else None
    seen: set[str] = set()
    found: list[str] = []
    for text in texts:
        if not text:
            continue
        for match in _KEY_RE.findall(text):
            key = str(match)
            if key in _STOP_KEYS or key in seen or key.upper() == excluded:
                continue
            seen.add(key)
            found.append(key)
    return found


def texts_from_mapping(values: dict[str, object]) -> list[str]:
    """Flatten a field map's string values, so custom fields get scanned too.

    Jama in particular hides cross-references in custom fields, which is where
    a "traced-to" note most often lives.
    """
    return [value for value in values.values() if isinstance(value, str) and value]
