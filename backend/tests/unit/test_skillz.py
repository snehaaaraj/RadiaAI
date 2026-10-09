"""Unit tests for the Skillz rules package: zip parsing, deterministic checks and loading."""

from __future__ import annotations

import io
import zipfile

import pytest

from app.core.config import SkillzSettings
from radia_ai.features.jama_requirement_reviewer.skillz.checker import check_requirement_text
from radia_ai.features.jama_requirement_reviewer.skillz.package import (
    SkillzPackageError,
    parse_skillz_zip,
)
from radia_ai.features.jama_requirement_reviewer.skillz.service import SkillzService
from radia_ai.features.jama_requirement_reviewer.utils.requirement_normalization import (
    split_requirement_fields,
)

SKILL_MD = """---
name: acr-generator
description: Test package.
---

# WindRunner ACR generator

Revision 5.5. Proprietary.
"""

CORE_RULES_MD = """# Core ACR rules

## 1. Source and scope discipline

### C1 Current baseline

Treat the current exports as authoritative.

## 4. Requirement construction

### C12 Subject and modal

Use exactly one `shall`.

### C18 Forbidden and controlled language

Do not use `adequate` in a shall.

## 5. Faults

### C22 Failure definition

Define the failure.
"""

QUALITY_GATES_MD = """# Quality gates

## Q2. Requirement construction

Check the construction.

### Whole-set semantic consistency

Set-level review only.

## Q3. Language sweep

Sweep the language.
"""

OBLIGATION_FORMS_MD = """# Obligation-form precedents

| Obligation type | Accepted form |
|---|---|
| Ungated prevention | `shall prevent [X]` |
"""

CHECK_ACR_PY = """import os
FORBIDDEN_REQ = ["adequate", "safe", "etc"]
FORBIDDEN_BOTH = ["approved", "TBD"]
FORBIDDEN_DISPLAY = ["display", "displays"]
DEFINED_TERMS = ["unsafe takeoff configuration"]
LEXICON = {r"\\bthe pilot\\b": "the flightcrew"}
COMPUTED = os.getcwd()
os.system("echo this must never run")
"""


def build_skillz_zip(*, root: str = "acr-generator/", include_core: bool = True) -> bytes:
    """Build an in-memory Skillz package shaped like the real Rev 5.5 zip."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"{root}SKILL.md", SKILL_MD)
        if include_core:
            archive.writestr(f"{root}references/core-rules.md", CORE_RULES_MD)
        archive.writestr(f"{root}references/quality-gates.md", QUALITY_GATES_MD)
        archive.writestr(f"{root}references/obligation-form-precedents.md", OBLIGATION_FORMS_MD)
        archive.writestr(f"{root}scripts/check_acr.py", CHECK_ACR_PY)
        archive.writestr(f"{root}references/flight-controls.md", "# Family module\n")
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Package parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("root", ["acr-generator/", ""])
def test_parse_skillz_zip_reads_rules_revision_and_word_lists(root: str) -> None:
    package = parse_skillz_zip(build_skillz_zip(root=root), source_url="https://sp/skillz.zip")

    assert package.name == "acr-generator"
    assert package.revision == "5.5"
    assert package.label == "acr-generator Revision 5.5"
    assert package.source_url == "https://sp/skillz.zip"
    assert len(package.content_hash) == 64
    assert package.rules["C12"].title == "Subject and modal"
    assert package.rules["C12"].text == "Use exactly one `shall`."
    assert package.rules["C18"].document == "core-rules.md"
    # A quality-gate section stops at its first sub-heading.
    assert package.rules["Q2"].text == "Check the construction."
    assert "shall prevent" in package.rules["OFP"].text
    assert package.word_lists.forbidden_requirement == ("adequate", "safe", "etc")
    assert package.word_lists.lexicon == {r"\bthe pilot\b": "the flightcrew"}


@pytest.mark.unit
def test_applicable_rules_exclude_rules_needing_unavailable_artifacts() -> None:
    package = parse_skillz_zip(build_skillz_zip())

    applicable = [rule.rule_id for rule in package.applicable_rules()]

    assert applicable == ["C12", "C18", "C22", "Q2", "Q3", "OFP"]
    assert "C1" in package.rules
    assert "C1" not in applicable


@pytest.mark.unit
def test_checker_script_is_parsed_not_executed(capfd: pytest.CaptureFixture[str]) -> None:
    package = parse_skillz_zip(build_skillz_zip())

    assert "this must never run" not in capfd.readouterr().out
    assert package.word_lists.forbidden_display == ("display", "displays")


@pytest.mark.unit
def test_parse_rejects_non_zip_and_incomplete_packages() -> None:
    with pytest.raises(SkillzPackageError, match="not a valid zip"):
        parse_skillz_zip(b"not a zip")
    with pytest.raises(SkillzPackageError, match="core-rules"):
        parse_skillz_zip(build_skillz_zip(include_core=False))


# ---------------------------------------------------------------------------
# Deterministic checks
# ---------------------------------------------------------------------------


def _rule_terms(text: str) -> set[tuple[str, str]]:
    word_lists = parse_skillz_zip(build_skillz_zip()).word_lists
    return {
        (issue.rule_id, issue.term.lower()) for issue in check_requirement_text(text, word_lists)
    }


@pytest.mark.unit
def test_checker_accepts_compliant_requirement() -> None:
    assert (
        _rule_terms("The Fuel Quantity function shall report fuel quantity to the flightcrew.")
        == set()
    )


@pytest.mark.unit
def test_checker_flags_controlled_vocabulary_by_rule() -> None:
    issues = _rule_terms(
        "The function shall provide adequate data, etc. to the display as approved, TBD."
    )

    assert ("C18", "adequate") in issues
    assert ("C18", "etc") in issues
    assert ("C18", "approved") in issues
    assert ("C17", "tbd") in issues
    assert ("C21", "display") in issues


@pytest.mark.unit
def test_checker_masks_defined_terms_and_respects_word_boundaries() -> None:
    issues = _rule_terms(
        "The function shall annunciate an unsafe takeoff configuration to the flightcrew for safety."
    )

    assert ("C18", "safe") not in issues


@pytest.mark.unit
def test_checker_enforces_single_shall_and_no_competing_modal() -> None:
    assert ("C12", "shall") in _rule_terms("The function shall do A and shall do B.")
    assert ("C12", "shall") in _rule_terms("The function provides A.")
    assert ("C12", "should") in _rule_terms("The function shall do A and should do B.")


@pytest.mark.unit
def test_checker_applies_lexicon_and_bracket_rules() -> None:
    issues = _rule_terms("The function shall alert the pilot within [5] seconds.")

    assert ("C21", "the pilot") in issues
    assert ("C17", "[...]") in issues
    assert ("C17", "[...]") not in _rule_terms("[The function shall alert the flightcrew.]")


# ---------------------------------------------------------------------------
# Loading service
# ---------------------------------------------------------------------------


class FakeSkillzSource:
    def __init__(self, data: bytes | None = None, error: Exception | None = None) -> None:
        self.data = data
        self.error = error
        self.calls = 0

    def download_drive_file(self, path: str) -> tuple[bytes, str | None]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.data is not None
        return self.data, "https://sp/skillz.zip"


def _settings(**overrides: object) -> SkillzSettings:
    values: dict[str, object] = {"zip_path": "Skillz/pkg.zip", "applicable_levels": ["aircraft"]}
    values.update(overrides)
    return SkillzSettings.model_validate(values)


@pytest.mark.unit
def test_skillz_applies_only_to_configured_levels() -> None:
    service = SkillzService(_settings(), FakeSkillzSource(build_skillz_zip()))

    assert service.applies_to("Aircraft")
    assert not service.applies_to("System")
    assert not service.applies_to(None)
    assert not SkillzService(_settings(enabled=False), None).applies_to("aircraft")


@pytest.mark.unit
def test_skillz_levels_accept_comma_separated_env_value() -> None:
    assert _settings(applicable_levels="aircraft, system").applicable_levels == [
        "aircraft",
        "system",
    ]


@pytest.mark.unit
def test_skillz_package_is_cached_between_loads() -> None:
    source = FakeSkillzSource(build_skillz_zip())
    service = SkillzService(_settings(), source)

    first = service.load()
    second = service.load()

    assert first.package is not None
    assert second.package is first.package
    assert source.calls == 1


@pytest.mark.unit
def test_skillz_serves_last_good_package_when_refresh_fails() -> None:
    source = FakeSkillzSource(build_skillz_zip())
    service = SkillzService(_settings(cache_ttl_seconds=0), source)
    good = service.load().package

    source.error = RuntimeError("graph down")
    stale = service.load()

    assert stale.package is good


@pytest.mark.unit
def test_skillz_reports_error_when_nothing_can_be_loaded() -> None:
    failing = SkillzService(_settings(), FakeSkillzSource(error=RuntimeError("graph down")))
    unconfigured = SkillzService(_settings(), None)

    assert failing.load().package is None
    assert "could not be loaded" in failing.load().error
    assert unconfigured.load().package is None
    assert "not configured" in unconfigured.load().error


@pytest.mark.unit
def test_failed_refresh_is_not_retried_on_every_review() -> None:
    source = FakeSkillzSource(error=RuntimeError("graph down"))
    service = SkillzService(_settings(), source)

    for _ in range(5):
        service.load()

    assert source.calls == 1


@pytest.mark.unit
def test_stale_package_is_served_without_waiting_for_a_refresh() -> None:
    source = FakeSkillzSource(build_skillz_zip())
    service = SkillzService(_settings(cache_ttl_seconds=0), source)
    good = service.load().package

    # Simulate another request in the middle of a slow refresh.
    service._refresh_lock.acquire()
    try:
        result = service.load()
    finally:
        service._refresh_lock.release()

    assert result.package is good
    assert source.calls == 1


# ---------------------------------------------------------------------------
# Description extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_split_requirement_fields_extracts_description() -> None:
    fields = split_requirement_fields(
        "Title: Fuel Quantity\n\nDescription: The function shall report fuel.\n\nRationale: Crew need."
    )

    assert fields.title == "Fuel Quantity"
    assert fields.description == "The function shall report fuel."
    assert fields.rationale == "Crew need."


@pytest.mark.unit
def test_split_requirement_fields_treats_plain_text_as_description() -> None:
    fields = split_requirement_fields("The function shall report fuel.")

    assert fields.description == "The function shall report fuel."
    assert fields.title == ""
