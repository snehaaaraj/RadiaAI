"""
Synthesize ONE replacement Description from the individual findings of a review.

The LLM merges the findings, but it does not decide authority. The application
states the source hierarchy in the prompt, and every response is validated in
code before it is returned:

- every finding is accounted for exactly once (missing ones are surfaced as
  ``not_addressed`` rather than silently dropped);
- a finding may only be ``overridden`` by a Skillz rule that was actually loaded,
  because Skillz rules are the only higher authority than a standards finding;
- a conflict may only be ``resolved_by_skillz`` when it cites a loaded rule;
- cited rule IDs must exist; invented ones are removed;
- the final text is checked against the deterministic Skillz rules.

Any problem triggers one repair round. Whatever remains is shown to the user
rather than hidden, so nothing that contributed to, conflicted with, or was
overridden during synthesis loses its provenance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from app.core.logging import get_logger
from app.prompts.review_prompts import (
    RECOMMENDATION_SYNTHESIS_PROMPT_VERSION,
    RECOMMENDATION_SYNTHESIS_SYSTEM,
    SYNTHESIS_AUTHORITY_WITH_SKILLZ,
    SYNTHESIS_AUTHORITY_WITHOUT_SKILLZ,
)
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    ConflictResolution,
    ContributionStatus,
    FinalRecommendation,
    FindingContribution,
    RecommendationConflict,
    RecommendationOpenItem,
    RecommendationStatus,
    ReviewFinding,
    SkillzChange,
    SkillzCheckIssue,
    SkillzRuleReference,
    SkillzStatus,
)
from radia_ai.features.jama_requirement_reviewer.skillz.checker import check_requirement_text
from radia_ai.features.jama_requirement_reviewer.utils.requirement_normalization import (
    split_requirement_fields,
)

if TYPE_CHECKING:
    from radia_ai.features.jama_requirement_reviewer.skillz.package import SkillzPackage
    from radia_ai.features.jama_requirement_reviewer.skillz.service import SkillzService

logger = get_logger(__name__)

_UNRESOLVED_STATUSES = {ContributionStatus.CONFLICT_UNRESOLVED, ContributionStatus.NOT_ADDRESSED}


class ChatCompletionClient(Protocol):
    """The subset of ``OpenAIClient`` the synthesizer needs."""

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class _SkillzContext:
    package: SkillzPackage | None
    status: SkillzStatus
    message: str


@dataclass
class _Draft:
    text: str
    summary: str
    contributions: list[FindingContribution]
    skillz_changes: list[SkillzChange]
    conflicts: list[RecommendationConflict]
    open_items: list[RecommendationOpenItem]
    check_issues: list[SkillzCheckIssue]
    problems: list[str] = field(default_factory=list)


class RecommendationSynthesizer:
    """Turns the findings of a completed review into one traceable recommendation."""

    def __init__(
        self,
        llm: ChatCompletionClient,
        skillz_service: SkillzService | None = None,
    ) -> None:
        self._llm = llm
        self._skillz = skillz_service

    @property
    def prompt_version(self) -> str:
        return RECOMMENDATION_SYNTHESIS_PROMPT_VERSION

    def synthesize(
        self,
        *,
        requirement_text: str,
        requirement_level: str | None,
        findings: list[ReviewFinding],
    ) -> FinalRecommendation:
        """Build the final recommendation. Never raises: failures are reported in the result."""
        fields = split_requirement_fields(requirement_text)
        try:
            skillz = self._resolve_skillz(requirement_level)
        except Exception:
            logger.exception("recommendation_skillz_resolution_failed")
            skillz = _SkillzContext(
                package=None,
                status=SkillzStatus.UNAVAILABLE,
                message="Skillz not applied: the Skillz rules could not be loaded.",
            )

        try:
            return self._synthesize(
                fields.title, fields.description, fields.rationale, findings, skillz
            )
        except Exception:
            logger.exception("recommendation_synthesis_failed")
            return self._result(
                skillz,
                status=RecommendationStatus.FAILED,
                original_description=fields.description,
                failure_message=(
                    "The final recommendation could not be generated. The individual "
                    "suggestions below are still available."
                ),
            )

    # -- pipeline -------------------------------------------------------------

    def _synthesize(
        self,
        title: str,
        description: str,
        rationale: str,
        findings: list[ReviewFinding],
        skillz: _SkillzContext,
    ) -> FinalRecommendation:
        if not description:
            return self._result(
                skillz,
                status=RecommendationStatus.FAILED,
                original_description="",
                failure_message="No Description was found in the reviewed text to rewrite.",
            )

        findings = _with_finding_ids(findings)
        original_issues = (
            check_requirement_text(description, skillz.package.word_lists) if skillz.package else []
        )
        if not findings and not original_issues:
            return self._result(
                skillz,
                status=RecommendationStatus.NO_CHANGE,
                original_description=description,
                recommended_description=description,
                summary="No changes are recommended.",
            )

        messages = [
            {"role": "system", "content": _system_prompt(skillz)},
            {
                "role": "user",
                "content": _user_message(title, description, rationale, findings, original_issues),
            },
        ]

        try:
            raw = self._llm.chat_completion(messages)
        except Exception:
            logger.exception("recommendation_synthesis_llm_call_failed")
            return self._failed_call(skillz, description)

        draft = _build_draft(raw, findings, skillz.package)
        if draft is None or draft.problems:
            problems = (
                draft.problems
                if draft
                else ["The response was not valid JSON in the required shape."]
            )
            logger.warning("recommendation_synthesis_repair", problems=problems)
            repair_messages = [
                *messages,
                {"role": "assistant", "content": raw},
                {"role": "user", "content": _repair_message(problems)},
            ]
            try:
                repaired = _build_draft(
                    self._llm.chat_completion(repair_messages), findings, skillz.package
                )
            except Exception:
                logger.exception("recommendation_synthesis_repair_call_failed")
                repaired = None
            if repaired is not None:
                draft = repaired

        if draft is None:
            return self._result(
                skillz,
                status=RecommendationStatus.FAILED,
                original_description=description,
                failure_message=(
                    "The AI synthesis returned a response that could not be interpreted. "
                    "Running the review again usually resolves this."
                ),
            )

        return self._finalize(draft, description, skillz)

    def _resolve_skillz(self, requirement_level: str | None) -> _SkillzContext:
        level_label = requirement_level or "unspecified"
        if self._skillz is None or not self._skillz.applies_to(requirement_level):
            return _SkillzContext(
                package=None,
                status=SkillzStatus.NOT_APPLICABLE,
                message=f"Skillz not applicable: no Skillz rules govern {level_label}-level requirements.",
            )
        loaded = self._skillz.load()
        if loaded.package is None:
            return _SkillzContext(
                package=None,
                status=SkillzStatus.UNAVAILABLE,
                message=(
                    "Skillz not applied: the Skillz rules could not be loaded, so this is a "
                    f"standards-only recommendation. {loaded.error}".strip()
                ),
            )
        return _SkillzContext(
            package=loaded.package,
            status=SkillzStatus.APPLIED,
            message=f"Skillz applied: {loaded.package.label}.",
        )

    def _finalize(
        self, draft: _Draft, original: str, skillz: _SkillzContext
    ) -> FinalRecommendation:
        # Open items (e.g. a verification method still to record) are follow-ups for
        # other fields and do not stop the Description from being replaced.
        needs_review = (
            any(c.status in _UNRESOLVED_STATUSES for c in draft.contributions)
            or any(c.resolution is ConflictResolution.UNRESOLVED for c in draft.conflicts)
            or bool(draft.check_issues)
        )
        if needs_review:
            status = RecommendationStatus.NEEDS_REVIEW
        elif draft.text == original:
            status = RecommendationStatus.NO_CHANGE
        else:
            status = RecommendationStatus.READY

        return self._result(
            skillz,
            status=status,
            original_description=original,
            recommended_description=draft.text,
            summary=draft.summary,
            contributions=draft.contributions,
            skillz_changes=draft.skillz_changes,
            conflicts=draft.conflicts,
            open_items=draft.open_items,
            skillz_check_issues=draft.check_issues,
            skillz_rules=_cited_rules(draft, skillz.package),
        )

    def _failed_call(self, skillz: _SkillzContext, description: str) -> FinalRecommendation:
        return self._result(
            skillz,
            status=RecommendationStatus.FAILED,
            original_description=description,
            failure_message=(
                "The AI synthesis call did not complete. The individual suggestions below are "
                "still available; run the review again to generate the final recommendation."
            ),
        )

    def _result(self, skillz: _SkillzContext, **values: object) -> FinalRecommendation:
        package = skillz.package
        return FinalRecommendation.model_validate(
            {
                "skillz_status": skillz.status,
                "skillz_status_message": skillz.message,
                "skillz_package": package.name if package else None,
                "skillz_revision": package.revision if package else None,
                "skillz_content_hash": package.content_hash if package else None,
                "skillz_source_url": package.source_url if package else None,
                "prompt_version": RECOMMENDATION_SYNTHESIS_PROMPT_VERSION,
                **values,
            }
        )


# -- prompt construction ------------------------------------------------------


def _system_prompt(skillz: _SkillzContext) -> str:
    package = skillz.package
    if package is None:
        reason = (
            "the Skillz rules are unavailable"
            if skillz.status is SkillzStatus.UNAVAILABLE
            else "this requirement level is not governed by Skillz"
        )
        return (
            f"{RECOMMENDATION_SYNTHESIS_SYSTEM}\n\n"
            f"{SYNTHESIS_AUTHORITY_WITHOUT_SKILLZ.format(reason=reason)}"
        )

    rules = "\n\n".join(
        f"### [{rule.rule_id}] {rule.title} ({rule.document})\n{rule.text}"
        for rule in package.applicable_rules()
    )
    return (
        f"{RECOMMENDATION_SYNTHESIS_SYSTEM}\n\n"
        f"{SYNTHESIS_AUTHORITY_WITH_SKILLZ.format(skillz_label=package.label)}\n\n"
        f"## Skillz rules - authority level 1 ({package.label})\n\n{rules}"
    )


def _user_message(
    title: str,
    description: str,
    rationale: str,
    findings: list[ReviewFinding],
    original_issues: list[SkillzCheckIssue],
) -> str:
    payload = {
        "original_description": description,
        "context": {"title": title or None, "rationale": rationale or None},
        "findings": [
            {
                "finding_id": finding.finding_id,
                "source_type": finding.source_type.value,
                "authority_level": finding.authority_level,
                "source": finding.reference_title or finding.reference,
                "source_page": finding.source_page,
                "source_section": finding.source_section,
                "category": finding.category,
                "severity": finding.severity.value,
                "rule": finding.rule,
                "problem": finding.explanation,
                "evidence": finding.evidence,
                "recommendation": finding.recommendation,
                "suggested_rewrite": finding.suggested_rewrite,
            }
            for finding in findings
        ],
        "skillz_check_original": [issue.model_dump() for issue in original_issues],
    }
    return json.dumps(payload, indent=1, ensure_ascii=False)


def _repair_message(problems: list[str]) -> str:
    listed = "\n".join(f"- {problem}" for problem in problems)
    return (
        "Your previous response had these problems:\n"
        f"{listed}\n\n"
        "Return the complete corrected JSON response, following every rule in the system "
        "message. Respond ONLY with valid JSON."
    )


# -- response validation ------------------------------------------------------


def _build_draft(
    raw: str, findings: list[ReviewFinding], package: SkillzPackage | None
) -> _Draft | None:
    """Parse and validate one LLM response. Returns None when it is unusable."""
    data = _parse_json_object(raw)
    if data is None:
        return None
    text = _clean_description(data.get("recommended_description"))
    if not text:
        return None

    problems: list[str] = []
    finding_ids = [finding.finding_id for finding in findings if finding.finding_id]
    known_findings = set(finding_ids)
    rule_ids = {rule.rule_id for rule in package.applicable_rules()} if package else set()

    conflicts = _validate_conflicts(data.get("conflicts"), known_findings, rule_ids, problems)
    contributions = _validate_contributions(
        data.get("contributions"), finding_ids, rule_ids, conflicts, problems
    )
    skillz_changes = _validate_skillz_changes(data.get("skillz_changes"), rule_ids, problems)
    open_items = _validate_open_items(data.get("open_items"), rule_ids)

    check_issues = check_requirement_text(text, package.word_lists) if package else []
    for issue in check_issues:
        problems.append(
            f"Skillz rule {issue.rule_id} is still violated in the recommended text: {issue.message}"
        )

    return _Draft(
        text=text,
        summary=_text(data.get("summary")),
        contributions=contributions,
        skillz_changes=skillz_changes,
        conflicts=conflicts,
        open_items=open_items,
        check_issues=check_issues,
        problems=problems,
    )


def _validate_conflicts(
    raw: object, known_findings: set[str], rule_ids: set[str], problems: list[str]
) -> list[RecommendationConflict]:
    conflicts: list[RecommendationConflict] = []
    seen: set[str] = set()
    for index, item in enumerate(_dicts(raw), start=1):
        conflict_id = _text(item.get("conflict_id")) or f"K{index}"
        if conflict_id in seen:
            continue
        seen.add(conflict_id)
        involved = [fid for fid in _strings(item.get("finding_ids")) if fid in known_findings]
        governing = [rid for rid in _strings(item.get("governing_rule_ids")) if rid in rule_ids]
        resolution = (
            _enum(ConflictResolution, item.get("resolution"), None) or ConflictResolution.UNRESOLVED
        )
        if resolution is ConflictResolution.RESOLVED_BY_SKILLZ and not governing:
            problems.append(
                f"Conflict {conflict_id} is marked resolved_by_skillz without citing a provided "
                "Skillz rule; only a provided Skillz rule can resolve a conflict."
            )
            resolution = ConflictResolution.UNRESOLVED
        conflicts.append(
            RecommendationConflict(
                conflict_id=conflict_id,
                finding_ids=involved,
                description=_text(item.get("description")),
                resolution=resolution,
                governing_rule_ids=governing,
            )
        )
    return conflicts


def _validate_contributions(
    raw: object,
    finding_ids: list[str],
    rule_ids: set[str],
    conflicts: list[RecommendationConflict],
    problems: list[str],
) -> list[FindingContribution]:
    known = set(finding_ids)
    conflicts_by_id = {conflict.conflict_id: conflict for conflict in conflicts}
    by_finding: dict[str, FindingContribution] = {}

    for item in _dicts(raw):
        finding_id = _text(item.get("finding_id"))
        if finding_id not in known or finding_id in by_finding:
            continue

        status = _enum(ContributionStatus, item.get("status"), None)
        if status is None or status is ContributionStatus.NOT_ADDRESSED:
            problems.append(f"Finding {finding_id} has an invalid status.")
            status = ContributionStatus.NOT_ADDRESSED
        reason = _text(item.get("reason"))
        overridden_by = [
            rid for rid in _strings(item.get("overridden_by_rule_ids")) if rid in rule_ids
        ]
        duplicate_of: str | None = _text(item.get("duplicate_of")) or None
        conflict_id: str | None = _text(item.get("conflict_id")) or None

        if status is ContributionStatus.OVERRIDDEN and not overridden_by:
            # Findings share one authority level, so only a Skillz rule can override one.
            problems.append(
                f"Finding {finding_id} is marked overridden without citing a provided Skillz "
                "rule; findings never override each other."
            )
            status = ContributionStatus.CONFLICT_UNRESOLVED
            reason = (
                "Not overridden: no applicable Skillz rule supports overriding this suggestion."
            )

        if status is not ContributionStatus.MERGED_DUPLICATE or duplicate_of not in known:
            duplicate_of = None

        if conflict_id not in conflicts_by_id:
            conflict_id = next(
                (c.conflict_id for c in conflicts if finding_id in c.finding_ids), None
            )
        if status is ContributionStatus.CONFLICT_UNRESOLVED and conflict_id is None:
            conflict_id = _add_conflict(conflicts, conflicts_by_id, [finding_id])
        if (
            status is ContributionStatus.APPLIED
            and conflict_id is not None
            and conflicts_by_id[conflict_id].resolution is ConflictResolution.UNRESOLVED
        ):
            problems.append(
                f"Finding {finding_id} was applied although its conflict {conflict_id} is "
                "unresolved; leave that aspect of the original text unchanged."
            )

        by_finding[finding_id] = FindingContribution(
            finding_id=finding_id,
            status=status,
            contribution=_text(item.get("contribution")),
            reason=reason,
            overridden_by_rule_ids=overridden_by if status is ContributionStatus.OVERRIDDEN else [],
            duplicate_of=duplicate_of,
            conflict_id=conflict_id,
        )

    for finding_id in finding_ids:
        if finding_id not in by_finding:
            problems.append(f"Finding {finding_id} is missing from contributions.")
            by_finding[finding_id] = FindingContribution(
                finding_id=finding_id,
                status=ContributionStatus.NOT_ADDRESSED,
                reason="The synthesis did not account for this suggestion; review it manually.",
            )

    _verify_duplicates(by_finding, problems)
    return [by_finding[finding_id] for finding_id in finding_ids]


def _verify_duplicates(by_finding: dict[str, FindingContribution], problems: list[str]) -> None:
    """
    Accept a duplicate only when its chain ends at a finding that was actually applied.

    Otherwise the suggestion would be dropped without any source having been applied:
    circular duplicates, duplicates of rejected or overridden findings, and missing
    targets are surfaced as ``not_addressed`` instead.
    """
    unbacked: list[str] = []
    for finding_id, contribution in by_finding.items():
        if contribution.status is not ContributionStatus.MERGED_DUPLICATE:
            continue
        seen = {finding_id}
        target = contribution.duplicate_of
        while target is not None and target not in seen:
            seen.add(target)
            target_contribution = by_finding.get(target)
            if target_contribution is None:
                target = None
            elif target_contribution.status is ContributionStatus.APPLIED:
                break
            elif target_contribution.status is ContributionStatus.MERGED_DUPLICATE:
                target = target_contribution.duplicate_of
            else:
                target = None
        else:
            unbacked.append(finding_id)

    for finding_id in unbacked:
        problems.append(
            f"Finding {finding_id} is marked merged_duplicate, but duplicate_of does not lead to "
            "an applied finding."
        )
        by_finding[finding_id] = by_finding[finding_id].model_copy(
            update={
                "status": ContributionStatus.NOT_ADDRESSED,
                "duplicate_of": None,
                "reason": (
                    "Marked as a duplicate, but no applied suggestion makes this change; "
                    "review it manually."
                ),
            }
        )


def _add_conflict(
    conflicts: list[RecommendationConflict],
    conflicts_by_id: dict[str, RecommendationConflict],
    finding_ids: list[str],
) -> str:
    index = len(conflicts) + 1
    while f"K{index}" in conflicts_by_id:
        index += 1
    conflict = RecommendationConflict(
        conflict_id=f"K{index}",
        finding_ids=finding_ids,
        description="This suggestion conflicts with the requirement and could not be resolved safely.",
    )
    conflicts.append(conflict)
    conflicts_by_id[conflict.conflict_id] = conflict
    return conflict.conflict_id


def _validate_skillz_changes(
    raw: object, rule_ids: set[str], problems: list[str]
) -> list[SkillzChange]:
    changes: list[SkillzChange] = []
    for item in _dicts(raw):
        rule_id = _text(item.get("rule_id"))
        change = _text(item.get("change"))
        if not change:
            continue
        if rule_id not in rule_ids:
            problems.append(
                f"skillz_changes cites '{rule_id}', which is not a provided Skillz rule."
            )
            continue
        changes.append(
            SkillzChange(rule_id=rule_id, change=change, reason=_text(item.get("reason")))
        )
    return changes


def _validate_open_items(raw: object, rule_ids: set[str]) -> list[RecommendationOpenItem]:
    items: list[RecommendationOpenItem] = []
    for item in _dicts(raw):
        description = _text(item.get("description"))
        if not description:
            continue
        rule_id = _text(item.get("rule_id"))
        items.append(
            RecommendationOpenItem(
                rule_id=rule_id if rule_id in rule_ids else None, description=description
            )
        )
    return items


def _cited_rules(draft: _Draft, package: SkillzPackage | None) -> list[SkillzRuleReference]:
    if package is None:
        return []
    cited: list[str] = []
    for contribution in draft.contributions:
        cited.extend(contribution.overridden_by_rule_ids)
    for conflict in draft.conflicts:
        cited.extend(conflict.governing_rule_ids)
    cited.extend(change.rule_id for change in draft.skillz_changes)
    cited.extend(item.rule_id for item in draft.open_items if item.rule_id)
    cited.extend(issue.rule_id for issue in draft.check_issues)

    references: list[SkillzRuleReference] = []
    for rule_id in dict.fromkeys(cited):
        rule = package.rules.get(rule_id)
        if rule is not None:
            references.append(
                SkillzRuleReference(
                    rule_id=rule.rule_id,
                    title=rule.title,
                    document=rule.document,
                    text=rule.text,
                    source_url=package.source_url,
                )
            )
    return references


# -- helpers ------------------------------------------------------------------


def _with_finding_ids(findings: list[ReviewFinding]) -> list[ReviewFinding]:
    """Guarantee every finding has a unique ID the synthesis can reference."""
    if all(f.finding_id for f in findings) and len({f.finding_id for f in findings}) == len(
        findings
    ):
        return findings
    return [f.model_copy(update={"finding_id": f"F{i}"}) for i, f in enumerate(findings, start=1)]


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        logger.warning("recommendation_synthesis_parse_failed", raw=raw[:200])
        return None
    return data if isinstance(data, dict) else None


def _clean_description(value: object) -> str:
    text = _text(value)
    if text.lower().startswith("description:"):
        text = text[len("description:") :].strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    return " ".join(text.split())


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _enum[E: (ContributionStatus, ConflictResolution)](
    enum_type: type[E], value: object, default: E | None
) -> E | None:
    if isinstance(value, str):
        try:
            return enum_type(value.strip().lower())
        except ValueError:
            return default
    return default
