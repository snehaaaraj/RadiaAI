"""Deterministic delta engine for requirements revisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.models.review_models import (
    DeltaChangeSummary,
    RequirementReviewInput,
    TraceLinkChange,
)


@dataclass(frozen=True)
class DeltaComputationResult:
    """Internal representation of computed change sets."""

    change_summary: DeltaChangeSummary
    changed_requirements: list[RequirementReviewInput]


def compute_delta(
    baseline_requirements: list[RequirementReviewInput],
    updated_requirements: list[RequirementReviewInput],
    changed_trace_links: list[TraceLinkChange],
) -> DeltaComputationResult:
    """Compute new/modified/deleted requirements and trace link deltas."""
    baseline_map = {_requirement_key(req): req for req in baseline_requirements}
    updated_map = {_requirement_key(req): req for req in updated_requirements}

    baseline_ids = set(baseline_map)
    updated_ids = set(updated_map)

    new_ids = sorted(updated_ids - baseline_ids)
    deleted_ids = sorted(baseline_ids - updated_ids)

    shared_ids = sorted(baseline_ids & updated_ids)
    modified_ids = [
        requirement_id
        for requirement_id in shared_ids
        if _fingerprint(baseline_map[requirement_id]) != _fingerprint(updated_map[requirement_id])
    ]

    changed_trace_ids = {link.requirement_id for link in changed_trace_links}
    for requirement_id in shared_ids:
        baseline_parent = baseline_map[requirement_id].metadata.get("parent_id", "").strip()
        updated_parent = updated_map[requirement_id].metadata.get("parent_id", "").strip()
        if baseline_parent != updated_parent:
            changed_trace_ids.add(requirement_id)

    changed_ids = sorted(set(new_ids + modified_ids))
    changed_requirements = [updated_map[requirement_id] for requirement_id in changed_ids]

    summary = DeltaChangeSummary(
        new_requirement_ids=new_ids,
        modified_requirement_ids=sorted(modified_ids),
        deleted_requirement_ids=deleted_ids,
        changed_trace_link_requirement_ids=sorted(changed_trace_ids),
    )
    return DeltaComputationResult(change_summary=summary, changed_requirements=changed_requirements)


def _requirement_key(requirement: RequirementReviewInput) -> str:
    if requirement.requirement_id:
        return requirement.requirement_id.strip()
    normalized_text = " ".join(requirement.text.lower().split())
    digest = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()[:12]
    return f"anon-{digest}"


def _fingerprint(requirement: RequirementReviewInput) -> str:
    payload = {
        "text": " ".join(requirement.text.lower().split()),
        "requirement_level": (requirement.requirement_level or "").lower(),
        "metadata": {key: requirement.metadata[key] for key in sorted(requirement.metadata)},
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
