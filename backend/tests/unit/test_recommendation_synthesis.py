"""Unit tests for final recommendation synthesis and its code-enforced authority rules."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from tests.conftest import build_stub_finding
from tests.unit.test_skillz import FakeSkillzSource, build_skillz_zip

from app.core.config import SkillzSettings
from app.core.exceptions import LLMError
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    ConflictResolution,
    ConsolidatedReviewResult,
    ContributionStatus,
    RecommendationStatus,
    ReviewCompletion,
    ReviewFailureReason,
    ReviewFinding,
    SkillzStatus,
)
from radia_ai.features.jama_requirement_reviewer.skillz.service import SkillzService
from radia_ai.features.jama_requirement_reviewer.synthesis.recommendation_synthesizer import (
    RecommendationSynthesizer,
)

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

ORIGINAL = "The Fuel Quantity function shall report fuel quantity fast."


class ScriptedLLM:
    """Returns scripted responses in order and records every call."""

    def __init__(self, *responses: str | Exception) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        self.calls.append(messages)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _response(**overrides: Any) -> str:
    body: dict[str, Any] = {
        "recommended_description": "The Fuel Quantity function shall report fuel quantity within 2 s.",
        "summary": "Bounded the response time.",
        "contributions": [
            {"finding_id": "F1", "status": "applied", "contribution": "Bounded response time"},
            {"finding_id": "F2", "status": "merged_duplicate", "duplicate_of": "F1"},
        ],
        "skillz_changes": [],
        "conflicts": [],
        "open_items": [],
    }
    body.update(overrides)
    return json.dumps(body)


def _findings(count: int = 2) -> list[ReviewFinding]:
    return [
        build_stub_finding().model_copy(update={"finding_id": f"F{index}"})
        for index in range(1, count + 1)
    ]


def _skillz_service(*, fail: bool = False) -> SkillzService:
    source = (
        FakeSkillzSource(error=RuntimeError("graph down"))
        if fail
        else FakeSkillzSource(build_skillz_zip())
    )
    settings = SkillzSettings.model_validate(
        {"zip_path": "Skillz/pkg.zip", "applicable_levels": ["aircraft"]}
    )
    return SkillzService(settings, source)


def _synthesize(
    llm: ScriptedLLM,
    *,
    level: str = "System",
    findings: list[ReviewFinding] | None = None,
    skillz: SkillzService | None = None,
    text: str = ORIGINAL,
):
    synthesizer = RecommendationSynthesizer(llm, skillz)
    return synthesizer.synthesize(
        requirement_text=text,
        requirement_level=level,
        findings=_findings() if findings is None else findings,
    )


# ---------------------------------------------------------------------------
# Happy path and short circuits
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_merges_findings_into_one_ready_recommendation() -> None:
    llm = ScriptedLLM(_response())

    result = _synthesize(llm)

    assert result.status is RecommendationStatus.READY
    assert result.original_description == ORIGINAL
    assert result.recommended_description.endswith("within 2 s.")
    assert [c.status for c in result.contributions] == [
        ContributionStatus.APPLIED,
        ContributionStatus.MERGED_DUPLICATE,
    ]
    assert result.contributions[1].duplicate_of == "F1"
    assert result.skillz_status is SkillzStatus.NOT_APPLICABLE
    assert result.prompt_version == "synthesis.v1"
    assert len(llm.calls) == 1


@pytest.mark.unit
def test_rewrites_only_the_description_field() -> None:
    llm = ScriptedLLM(_response())

    result = _synthesize(
        llm,
        text=f"Title: Fuel Quantity\n\nDescription: {ORIGINAL}\n\nRationale: Crew awareness.",
    )

    payload = json.loads(llm.calls[0][1]["content"])
    assert result.original_description == ORIGINAL
    assert payload["original_description"] == ORIGINAL
    assert payload["context"] == {"title": "Fuel Quantity", "rationale": "Crew awareness."}


@pytest.mark.unit
def test_no_findings_and_no_skillz_issues_skips_the_llm() -> None:
    llm = ScriptedLLM()

    result = _synthesize(llm, findings=[])

    assert result.status is RecommendationStatus.NO_CHANGE
    assert result.recommended_description == ORIGINAL
    assert llm.calls == []


@pytest.mark.unit
def test_skillz_issue_in_original_triggers_synthesis_without_findings() -> None:
    llm = ScriptedLLM(
        _response(
            recommended_description="The Fuel Quantity function shall report fuel quantity.",
            contributions=[],
            skillz_changes=[{"rule_id": "C18", "change": "Removed 'adequate'"}],
        )
    )

    result = _synthesize(
        llm,
        level="Aircraft",
        findings=[],
        skillz=_skillz_service(),
        text="The Fuel Quantity function shall report adequate fuel quantity.",
    )

    payload = json.loads(llm.calls[0][1]["content"])
    assert payload["skillz_check_original"][0]["rule_id"] == "C18"
    assert result.status is RecommendationStatus.READY
    assert result.skillz_changes[0].rule_id == "C18"
    assert result.skillz_rules[0].rule_id == "C18"
    assert "adequate" in result.skillz_rules[0].text


# ---------------------------------------------------------------------------
# Authority enforcement
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_findings_cannot_override_each_other_without_skillz() -> None:
    response = _response(
        contributions=[
            {"finding_id": "F1", "status": "applied"},
            {"finding_id": "F2", "status": "overridden", "overridden_by_rule_ids": ["C18"]},
        ]
    )
    llm = ScriptedLLM(response, response)

    result = _synthesize(llm)

    overridden = result.contributions[1]
    assert overridden.status is ContributionStatus.CONFLICT_UNRESOLVED
    assert overridden.overridden_by_rule_ids == []
    assert overridden.conflict_id is not None
    assert result.conflicts[0].resolution is ConflictResolution.UNRESOLVED
    assert result.status is RecommendationStatus.NEEDS_REVIEW
    assert len(llm.calls) == 2, "an invalid override must trigger one repair round"


@pytest.mark.unit
def test_skillz_rule_overrides_a_standards_finding() -> None:
    llm = ScriptedLLM(
        _response(
            contributions=[
                {"finding_id": "F1", "status": "applied"},
                {
                    "finding_id": "F2",
                    "status": "overridden",
                    "reason": "Conflicts with C12.",
                    "overridden_by_rule_ids": ["C12"],
                    "conflict_id": "K1",
                },
            ],
            conflicts=[
                {
                    "conflict_id": "K1",
                    "finding_ids": ["F1", "F2"],
                    "description": "Different modal verbs.",
                    "resolution": "resolved_by_skillz",
                    "governing_rule_ids": ["C12"],
                }
            ],
        )
    )

    result = _synthesize(llm, level="Aircraft", skillz=_skillz_service())

    assert result.skillz_status is SkillzStatus.APPLIED
    assert result.skillz_revision == "5.5"
    assert result.contributions[1].status is ContributionStatus.OVERRIDDEN
    assert result.contributions[1].overridden_by_rule_ids == ["C12"]
    assert result.conflicts[0].resolution is ConflictResolution.RESOLVED_BY_SKILLZ
    assert [rule.rule_id for rule in result.skillz_rules] == ["C12"]
    assert result.status is RecommendationStatus.READY
    assert len(llm.calls) == 1


@pytest.mark.unit
def test_skillz_rules_and_authority_are_stated_in_the_prompt() -> None:
    llm = ScriptedLLM(_response())

    _synthesize(llm, level="Aircraft", skillz=_skillz_service())

    system = llm.calls[0][0]["content"]
    assert "Level 1: Skillz requirements-writing rules (acr-generator Revision 5.5)" in system
    assert "Every level-2 finding has EQUAL authority" in system
    assert "### [C18] Forbidden and controlled language (core-rules.md)" in system
    assert "[C1]" not in system


@pytest.mark.unit
def test_resolution_by_skillz_requires_a_loaded_rule() -> None:
    response = _response(
        contributions=[
            {"finding_id": "F1", "status": "conflict_unresolved", "conflict_id": "K1"},
            {"finding_id": "F2", "status": "conflict_unresolved", "conflict_id": "K1"},
        ],
        conflicts=[
            {
                "conflict_id": "K1",
                "finding_ids": ["F1", "F2"],
                "resolution": "resolved_by_skillz",
                "governing_rule_ids": ["C99"],
            }
        ],
    )
    llm = ScriptedLLM(response, response)

    result = _synthesize(llm, level="Aircraft", skillz=_skillz_service())

    assert result.conflicts[0].resolution is ConflictResolution.UNRESOLVED
    assert result.conflicts[0].governing_rule_ids == []
    assert result.status is RecommendationStatus.NEEDS_REVIEW


@pytest.mark.unit
def test_invented_skillz_rules_are_dropped() -> None:
    response = _response(
        skillz_changes=[
            {"rule_id": "C18", "change": "Removed 'fast'"},
            {"rule_id": "C77", "change": "Invented change"},
        ],
        open_items=[{"rule_id": "C99", "description": "Exact ACF function name is needed."}],
    )
    llm = ScriptedLLM(response, response)

    result = _synthesize(llm, level="Aircraft", skillz=_skillz_service())

    assert [change.rule_id for change in result.skillz_changes] == ["C18"]
    assert result.open_items[0].rule_id is None
    # Open items are follow-ups and do not block replacing the Description.
    assert result.status is RecommendationStatus.READY
    assert len(llm.calls) == 2


@pytest.mark.unit
def test_unresolved_conflict_keeps_both_suggestions_visible() -> None:
    llm = ScriptedLLM(
        _response(
            contributions=[
                {"finding_id": "F1", "status": "conflict_unresolved", "conflict_id": "K1"},
                {"finding_id": "F2", "status": "conflict_unresolved", "conflict_id": "K1"},
            ],
            conflicts=[
                {
                    "conflict_id": "K1",
                    "finding_ids": ["F1", "F2"],
                    "description": "OAuth versus SAML.",
                    "resolution": "unresolved",
                }
            ],
        )
    )

    result = _synthesize(llm)

    assert result.status is RecommendationStatus.NEEDS_REVIEW
    assert result.conflicts[0].finding_ids == ["F1", "F2"]
    assert {c.conflict_id for c in result.contributions} == {"K1"}
    assert len(llm.calls) == 1


# ---------------------------------------------------------------------------
# Provenance completeness and repair
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_missing_findings_are_repaired_or_surfaced() -> None:
    incomplete = _response(contributions=[{"finding_id": "F1", "status": "applied"}])
    llm = ScriptedLLM(incomplete, incomplete)

    result = _synthesize(llm)

    assert len(llm.calls) == 2
    repair_prompt = llm.calls[1][-1]["content"]
    assert "Finding F2 is missing from contributions." in repair_prompt
    assert result.contributions[1].finding_id == "F2"
    assert result.contributions[1].status is ContributionStatus.NOT_ADDRESSED
    assert result.status is RecommendationStatus.NEEDS_REVIEW


@pytest.mark.unit
@pytest.mark.parametrize(
    "contributions",
    [
        pytest.param(
            [
                {"finding_id": "F1", "status": "merged_duplicate", "duplicate_of": "F2"},
                {"finding_id": "F2", "status": "merged_duplicate", "duplicate_of": "F1"},
            ],
            id="circular",
        ),
        pytest.param(
            [
                {"finding_id": "F1", "status": "rejected_unsupported"},
                {"finding_id": "F2", "status": "merged_duplicate", "duplicate_of": "F1"},
            ],
            id="target-not-applied",
        ),
        pytest.param(
            [
                {"finding_id": "F1", "status": "applied"},
                {"finding_id": "F2", "status": "merged_duplicate", "duplicate_of": "F9"},
            ],
            id="unknown-target",
        ),
    ],
)
def test_duplicates_must_trace_to_an_applied_finding(contributions: list[dict[str, str]]) -> None:
    response = _response(contributions=contributions)
    llm = ScriptedLLM(response, response)

    result = _synthesize(llm)

    assert len(llm.calls) == 2, "an unbacked duplicate must trigger the repair round"
    assert ContributionStatus.MERGED_DUPLICATE not in {c.status for c in result.contributions}
    assert ContributionStatus.NOT_ADDRESSED in {c.status for c in result.contributions}
    assert result.status is RecommendationStatus.NEEDS_REVIEW


@pytest.mark.unit
def test_duplicate_chains_ending_at_an_applied_finding_are_accepted() -> None:
    llm = ScriptedLLM(
        _response(
            contributions=[
                {"finding_id": "F1", "status": "applied"},
                {"finding_id": "F2", "status": "merged_duplicate", "duplicate_of": "F1"},
                {"finding_id": "F3", "status": "merged_duplicate", "duplicate_of": "F2"},
            ]
        )
    )

    result = _synthesize(llm, findings=_findings(3))

    assert result.status is RecommendationStatus.READY
    assert [c.duplicate_of for c in result.contributions] == [None, "F1", "F2"]
    assert len(llm.calls) == 1


@pytest.mark.unit
def test_repair_round_result_replaces_the_first_draft() -> None:
    llm = ScriptedLLM(
        _response(contributions=[{"finding_id": "F1", "status": "applied"}]),
        _response(),
    )

    result = _synthesize(llm)

    assert result.status is RecommendationStatus.READY
    assert all(c.status is not ContributionStatus.NOT_ADDRESSED for c in result.contributions)


@pytest.mark.unit
def test_remaining_skillz_violations_are_reported() -> None:
    violating = _response(
        recommended_description="The Fuel Quantity function shall present adequate data on the display."
    )
    llm = ScriptedLLM(violating, violating)

    result = _synthesize(llm, level="Aircraft", skillz=_skillz_service())

    assert {issue.rule_id for issue in result.skillz_check_issues} == {"C18", "C21"}
    assert result.status is RecommendationStatus.NEEDS_REVIEW
    assert len(llm.calls) == 2


# ---------------------------------------------------------------------------
# Skillz availability and failures
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_unavailable_skillz_yields_labelled_standards_only_recommendation() -> None:
    llm = ScriptedLLM(_response())

    result = _synthesize(llm, level="Aircraft", skillz=_skillz_service(fail=True))

    assert result.skillz_status is SkillzStatus.UNAVAILABLE
    assert result.skillz_status_message.startswith("Skillz not applied")
    assert result.status is RecommendationStatus.READY
    assert "No Skillz rules apply" in llm.calls[0][0]["content"]


@pytest.mark.unit
def test_llm_failure_is_reported_without_raising() -> None:
    llm = ScriptedLLM(LLMError(message="boom", model="gpt-5"))

    result = _synthesize(llm)

    assert result.status is RecommendationStatus.FAILED
    assert "did not complete" in result.failure_message
    assert result.recommended_description is None


@pytest.mark.unit
def test_unparseable_responses_fail_after_one_repair() -> None:
    llm = ScriptedLLM("not json", '{"summary": "no description"}')

    result = _synthesize(llm)

    assert result.status is RecommendationStatus.FAILED
    assert len(llm.calls) == 2


@pytest.mark.unit
def test_cleans_labels_and_quotes_from_the_description() -> None:
    llm = ScriptedLLM(
        _response(recommended_description='Description: "The function shall report fuel."')
    )

    result = _synthesize(llm)

    assert result.recommended_description == "The function shall report fuel."


# ---------------------------------------------------------------------------
# Review endpoint and history
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_review_endpoint_returns_final_recommendation_with_provenance(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/review/requirement",
        json={"text": "The subsystem shall respond fast.", "requirement_level": "System"},
    )

    data = response.json()["data"]
    recommendation = data["final_recommendation"]
    assert data["requirement_text"] == "Description: The subsystem shall respond fast."
    assert data["findings"][0]["finding_id"] == "F1"
    assert data["findings"][0]["authority_level"] == 2
    assert recommendation["status"] == "ready"
    assert recommendation["original_description"] == "The subsystem shall respond fast."
    assert recommendation["recommended_description"] == (
        "The subsystem shall respond within 100 ms under nominal load."
    )
    assert recommendation["contributions"][0]["finding_id"] == "F1"
    assert recommendation["skillz_status"] == "not_applicable"


@pytest.mark.unit
def test_failed_review_has_no_final_recommendation(client: TestClient, review_engine) -> None:
    review_engine.install(
        ConsolidatedReviewResult(
            completion=ReviewCompletion.failed(ReviewFailureReason.LLM_CALL_FAILED)
        )
    )

    data = client.post("/api/v1/review/requirement", json={"text": "The system shall run."}).json()[
        "data"
    ]

    assert data["final_recommendation"] is None
    assert review_engine.synthesis_llm.calls == []


@pytest.mark.unit
def test_history_keeps_requirement_text_and_recommendation(client: TestClient) -> None:
    client.post(
        "/api/v1/review/requirement",
        json={"requirement_id": "REQ-9", "text": "The subsystem shall respond fast."},
    )

    entry = client.get("/api/v1/review/history").json()["data"]["entries"][0]

    assert entry["requirement_text"] == "Description: The subsystem shall respond fast."
    assert entry["final_recommendation"]["contributions"][0]["finding_id"] == "F1"


@pytest.mark.unit
def test_version_metadata_includes_synthesis_prompt(client: TestClient) -> None:
    data = client.get("/api/v1/review/version").json()["data"]

    assert data["determinism"]["prompt_versions"]["recommendation_synthesis"] == "synthesis.v1"
