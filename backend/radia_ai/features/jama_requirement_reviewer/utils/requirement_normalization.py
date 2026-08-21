"""Normalize requirement review inputs into a canonical review representation."""

from __future__ import annotations

import re
import unicodedata

from radia_ai.features.jama_requirement_reviewer.models.review_models import RequirementReviewInput

_FIELD_LABELS: tuple[tuple[str, str], ...] = (
    ("project id", "project_id"),
    ("global id", "global_id"),
    ("status", "status"),
    ("release", "release"),
    ("title", "title"),
    ("description", "description"),
    ("requirement volatility", "requirement_volatility"),
    ("rationale", "rationale"),
    ("fdal", "fdal"),
    ("sal", "sal"),
    ("derived requirement", "derived_requirement"),
    ("safety requirement", "safety_requirement"),
    ("security effectiveness requirement", "security_effectiveness_requirement"),
    ("validation method", "validation_method"),
    ("verification method", "verification_method"),
    ("assigned to", "assigned_to"),
    ("reference information", "reference_information"),
    ("created by", "created_by"),
    ("created date", "created_date"),
    ("modified by", "modified_by"),
    ("modified date", "modified_date"),
    ("last activity date", "last_activity_date"),
)


def normalize_requirement_review_input(payload: RequirementReviewInput) -> RequirementReviewInput:
    """Return a canonicalized copy of a review input.

    Fielded document text is reduced to the actual requirement statement, while
    supporting fields are preserved in metadata so pasted text and extracted
    document text review against the same semantic input.
    """
    normalized_text, extracted_metadata = _canonicalize_text(payload.text)
    merged_metadata = dict(payload.metadata)
    merged_metadata.update(extracted_metadata)

    requirement_id = payload.requirement_id or merged_metadata.get("project_id")
    if requirement_id:
        requirement_id = requirement_id.strip()

    updates: dict[str, object] = {
        "text": normalized_text,
        "metadata": merged_metadata,
    }
    if requirement_id:
        updates["requirement_id"] = requirement_id

    return payload.model_copy(update=updates)


def _canonicalize_text(text: str) -> tuple[str, dict[str, str]]:
    cleaned_lines = [_normalize_line(line) for line in _split_lines(text)]
    extracted: dict[str, str] = {}

    current_label: str | None = None
    current_value_parts: list[str] = []
    body_parts: list[str] = []      # text before any field label (PDF body pattern)
    description_parts: list[str] = []
    title_parts: list[str] = []
    rationale_parts: list[str] = []
    description_active = False
    title_active = False
    rationale_active = False
    seen_fields = False
    current_label_has_inline_value = False  # True when label+value were on the same line

    index = 0
    while index < len(cleaned_lines):
        line = cleaned_lines[index]
        if not line:
            index += 1
            continue

        label, span, value = _consume_label(cleaned_lines, index)
        if label is not None:
            if current_label is not None:
                _store_field(extracted, current_label, current_value_parts)
            seen_fields = True
            current_label = label
            current_value_parts = []
            current_label_has_inline_value = bool(value)
            description_active = label == "description"
            title_active = label == "title"
            rationale_active = label == "rationale"
            if value:
                current_value_parts.append(value)
                if description_active:
                    description_parts.append(value)
                elif title_active:
                    title_parts.append(value)
                elif rationale_active:
                    rationale_parts.append(value)
            index += span
            continue

        if seen_fields:
            # Only accumulate continuation lines when the label had no inline value.
            # If the label already had its value on the same line, the next non-label
            # line belongs to the following field (split label row in the PDF table).
            if current_label is not None and not current_label_has_inline_value:
                current_value_parts.append(line)
                if description_active:
                    description_parts.append(line)
                elif title_active:
                    title_parts.append(line)
                elif rationale_active:
                    rationale_parts.append(line)
                current_label_has_inline_value = True  # satisfied after first continuation
        else:
            body_parts.append(line)
        index += 1

    if current_label is not None:
        _store_field(extracted, current_label, current_value_parts)

    # Compose: prefer explicit description field, otherwise use pre-field body text
    body = " ".join(" ".join(description_parts or body_parts).split()).strip()
    title = " ".join(" ".join(title_parts).split()).strip()
    rationale = " ".join(" ".join(rationale_parts).split()).strip()

    if title or body or rationale:
        parts = []
        if title:
            parts.append(f"Title: {title}")
        if body:
            parts.append(f"Description: {body}")
        if rationale:
            parts.append(f"Rationale: {rationale}")
        return "\n\n".join(parts), extracted

    return " ".join(" ".join(cleaned_lines).split()), extracted


def _split_lines(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "".join(ch for ch in normalized if ch == "\n" or ch == "\t" or not unicodedata.category(ch).startswith("C"))
    return normalized.split("\n")


def _normalize_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line.replace("\t", " ")).strip()
    line = re.sub(r"^\s*[-*â€¢]+\s*", "", line)
    line = _strip_markdown_links(line)
    line = re.sub(r"^\*{1,2}", "", line)
    line = re.sub(r"\*{1,2}$", "", line)
    return line.strip()


def _strip_markdown_links(line: str) -> str:
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)


def _consume_label(lines: list[str], index: int) -> tuple[str | None, int, str]:
    max_width = min(4, len(lines) - index)
    for width in range(max_width, 0, -1):
        candidate_parts = [part for part in lines[index : index + width] if part]
        if not candidate_parts:
            continue

        candidate = " ".join(candidate_parts)
        lowered = candidate.lower().rstrip(":")
        for label, field in _FIELD_LABELS:
            if lowered == label:
                return field, width, ""
            if lowered.startswith(f"{label} "):
                remainder = candidate[len(label):].lstrip(" :\t-")
                return field, width, remainder.strip()
    return None, 0, ""


def _store_field(extracted: dict[str, str], field: str, parts: list[str]) -> None:
    value = " ".join(" ".join(parts).split()).strip()
    if value:
        extracted[field] = value

