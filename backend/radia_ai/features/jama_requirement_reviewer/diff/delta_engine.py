"""Deterministic delta engine for requirements revisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    DeltaChangeSummary,
    RequirementReviewInput,
    RequirementRevision,
)
from radia_ai.features.jama_requirement_reviewer.utils.requirement_normalization import (
    normalize_requirement_review_input,
)


@dataclass(frozen=True)
class DeltaComputationResult:
    """Internal representation of computed change sets."""

    change_summary: DeltaChangeSummary
    changed_revisions: list[RequirementRevision]


def compute_delta(
    baseline_requirements: list[RequirementReviewInput],
    updated_requirements: list[RequirementReviewInput],
) -> DeltaComputationResult:
    """Compute new/modified/deleted requirements between revisions."""
    baseline_requirements = [
        normalize_requirement_review_input(requirement) for requirement in baseline_requirements
    ]
    updated_requirements = [
        normalize_requirement_review_input(requirement) for requirement in updated_requirements
    ]

    baseline_map = _key_requirements(baseline_requirements)
    updated_map = _key_requirements(updated_requirements)

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

    changed_ids = set(new_ids) | set(modified_ids)
    # Iterate the updated set so results follow the order the user supplied them.
    changed_revisions = [
        RequirementRevision(
            key=requirement_id,
            requirement=requirement,
            # A newly added requirement has no previous version to compare against.
            baseline_text=(
                baseline_map[requirement_id].text if requirement_id in baseline_map else None
            ),
        )
        for requirement_id, requirement in updated_map.items()
        if requirement_id in changed_ids
    ]

    summary = DeltaChangeSummary(
        new_requirement_ids=new_ids,
        modified_requirement_ids=sorted(modified_ids),
        deleted_requirement_ids=deleted_ids,
    )
    return DeltaComputationResult(change_summary=summary, changed_revisions=changed_revisions)


def _key_requirements(
    requirements: list[RequirementReviewInput],
) -> dict[str, RequirementReviewInput]:
    """
    Key each requirement so a baseline entry can be paired with its updated form.

    Requirements carrying an explicit ID are keyed by it. Requirements without one
    are paired by **position**: the Nth unidentified baseline requirement is the
    previous version of the Nth unidentified updated requirement.

    Position is the only usable signal here. Keying unidentified requirements by
    their text would mean a revision — which by definition changes the text —
    could never match its baseline, so every edit would be reported as a deletion
    plus an addition and would be scored with no previous version to compare
    against. That is precisely the pasted-original-vs-revision workflow.
    """
    keyed: dict[str, RequirementReviewInput] = {}
    unidentified_position = 0

    for requirement in requirements:
        if requirement.requirement_id:
            key = requirement.requirement_id.strip()
        else:
            unidentified_position += 1
            key = f"Requirement {unidentified_position}"
        keyed[key] = requirement

    return keyed


def _fingerprint(requirement: RequirementReviewInput) -> str:
    payload = {
        "text": " ".join(requirement.text.lower().split()),
        "requirement_level": (requirement.requirement_level or "").lower(),
        "metadata": {key: requirement.metadata[key] for key in sorted(requirement.metadata)},
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
