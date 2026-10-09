"""
Parse a Skillz package zip into rules the synthesis step can cite.

The package is read entirely in memory and only as data: Markdown rule documents
are split into numbered rule sections, and the word lists in ``check_acr.py`` are
read with ``ast.literal_eval``. No file from the package is ever executed or
written to disk.
"""

from __future__ import annotations

import ast
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field

MAX_ZIP_BYTES = 10 * 1024 * 1024
MAX_MEMBER_BYTES = 2 * 1024 * 1024

APPLICABLE_RULE_IDS: tuple[str, ...] = (
    "C9",
    "C11",
    "C12",
    "C13",
    "C14",
    "C15",
    "C16",
    "C17",
    "C18",
    "C19",
    "C20",
    "C21",
    "C22",
    "C23",
    "C24",
    "C25",
    "C26",
    "C27",
    "C28",
    "Q2",
    "Q3",
    "Q4",
    "OFP",
)
"""
Skillz rules that govern a single requirement Description.

The remaining rules (source baselines, ACF/ACFD alignment, workbooks, rationale and
Reference Information fields, whole-set sweeps) need artifacts the reviewer does not
have, or govern fields other than the Description, so they are not sent to the
synthesis step.
"""

OBLIGATION_FORMS_RULE_ID = "OFP"

_SKILL_DOC = "SKILL.md"
_CORE_RULES_DOC = "references/core-rules.md"
_QUALITY_GATES_DOC = "references/quality-gates.md"
_OBLIGATION_FORMS_DOC = "references/obligation-form-precedents.md"
_CHECKER_SCRIPT = "scripts/check_acr.py"
_WANTED_DOCUMENTS = frozenset(
    {_SKILL_DOC, _CORE_RULES_DOC, _QUALITY_GATES_DOC, _OBLIGATION_FORMS_DOC, _CHECKER_SCRIPT}
)

_CORE_RULE_HEADING = re.compile(r"^### (C\d+)\s+(.+)$")
_QUALITY_GATE_HEADING = re.compile(r"^## (Q\d+)\.?\s+(.+)$")
_ANY_HEADING = re.compile(r"^#{1,3} ")
_REVISION = re.compile(r"\bRevision\s+(\d+(?:\.\d+)*)", re.IGNORECASE)
_FRONTMATTER_NAME = re.compile(r"^name:\s*(.+)$", re.MULTILINE)


class SkillzPackageError(ValueError):
    """The Skillz package could not be parsed into usable rules."""


@dataclass(frozen=True)
class SkillzRule:
    """One numbered rule section of the Skillz package."""

    rule_id: str
    title: str
    document: str
    text: str


@dataclass(frozen=True)
class SkillzWordLists:
    """Controlled-vocabulary lists published by the Skillz checker script."""

    forbidden_requirement: tuple[str, ...] = ()
    forbidden_everywhere: tuple[str, ...] = ()
    forbidden_display: tuple[str, ...] = ()
    defined_terms: tuple[str, ...] = ()
    lexicon: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillzPackage:
    """A parsed Skillz package and the identity of the exact bytes it came from."""

    name: str
    revision: str | None
    content_hash: str
    source_url: str | None
    rules: dict[str, SkillzRule]
    word_lists: SkillzWordLists

    def applicable_rules(self) -> list[SkillzRule]:
        """Rules that govern a single requirement Description, in a stable order."""
        return [self.rules[rule_id] for rule_id in APPLICABLE_RULE_IDS if rule_id in self.rules]

    @property
    def label(self) -> str:
        return f"{self.name} Revision {self.revision}" if self.revision else self.name


def parse_skillz_zip(data: bytes, *, source_url: str | None = None) -> SkillzPackage:
    """Parse a Skillz package zip. Raises ``SkillzPackageError`` when unusable."""
    if len(data) > MAX_ZIP_BYTES:
        raise SkillzPackageError("Skillz package exceeds the maximum supported size.")

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise SkillzPackageError("Skillz package is not a valid zip archive.") from exc

    with archive:
        documents = _read_documents(archive)

    skill_text = documents.get(_SKILL_DOC)
    core_rules_text = documents.get(_CORE_RULES_DOC)
    if skill_text is None or core_rules_text is None:
        raise SkillzPackageError(
            "Skillz package must contain SKILL.md and references/core-rules.md."
        )

    rules: dict[str, SkillzRule] = {}
    for rule in _split_sections(core_rules_text, _CORE_RULE_HEADING, "core-rules.md"):
        rules.setdefault(rule.rule_id, rule)
    quality_gates_text = documents.get(_QUALITY_GATES_DOC)
    if quality_gates_text:
        for rule in _split_sections(quality_gates_text, _QUALITY_GATE_HEADING, "quality-gates.md"):
            rules.setdefault(rule.rule_id, rule)
    obligation_forms_text = documents.get(_OBLIGATION_FORMS_DOC)
    if obligation_forms_text:
        rules[OBLIGATION_FORMS_RULE_ID] = SkillzRule(
            rule_id=OBLIGATION_FORMS_RULE_ID,
            title="Obligation-form precedents",
            document="obligation-form-precedents.md",
            text=_strip_title(obligation_forms_text),
        )

    if not rules:
        raise SkillzPackageError("Skillz package contains no numbered rules.")

    name_match = _FRONTMATTER_NAME.search(skill_text)
    revision_match = _REVISION.search(skill_text)
    checker_text = documents.get(_CHECKER_SCRIPT)

    return SkillzPackage(
        name=name_match.group(1).strip() if name_match else "Skillz",
        revision=revision_match.group(1) if revision_match else None,
        content_hash=hashlib.sha256(data).hexdigest(),
        source_url=source_url,
        rules=rules,
        word_lists=parse_word_lists(checker_text) if checker_text else SkillzWordLists(),
    )


def parse_word_lists(source: str) -> SkillzWordLists:
    """
    Read the controlled-vocabulary constants from the Skillz checker script.

    The script is parsed, never executed: only top-level assignments of literal
    values are evaluated, so any other code in the file is ignored.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return SkillzWordLists()

    literals: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            literals[target.id] = ast.literal_eval(node.value)
        except (ValueError, TypeError, SyntaxError, RecursionError):
            continue

    return SkillzWordLists(
        forbidden_requirement=_string_tuple(literals.get("FORBIDDEN_REQ")),
        forbidden_everywhere=_string_tuple(literals.get("FORBIDDEN_BOTH")),
        forbidden_display=_string_tuple(literals.get("FORBIDDEN_DISPLAY")),
        defined_terms=_string_tuple(literals.get("DEFINED_TERMS")),
        lexicon=_string_mapping(literals.get("LEXICON")),
    )


def _read_documents(archive: zipfile.ZipFile) -> dict[str, str]:
    """Return the wanted documents keyed by their path relative to the package root."""
    documents: dict[str, str] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        relative = _relative_to_package_root(info.filename)
        if relative not in _WANTED_DOCUMENTS or relative in documents:
            continue
        if info.file_size > MAX_MEMBER_BYTES:
            raise SkillzPackageError(f"Skillz document {relative} exceeds the maximum size.")
        with archive.open(info) as handle:
            content = handle.read(MAX_MEMBER_BYTES + 1)
        if len(content) > MAX_MEMBER_BYTES:
            raise SkillzPackageError(f"Skillz document {relative} exceeds the maximum size.")
        documents[relative] = content.decode("utf-8", errors="replace")
    return documents


def _relative_to_package_root(filename: str) -> str:
    """
    Strip the single top-level folder the package is zipped under, if any.

    ``acr-generator/references/core-rules.md`` and ``references/core-rules.md``
    both resolve to ``references/core-rules.md``.
    """
    parts = [part for part in filename.replace("\\", "/").split("/") if part]
    if len(parts) >= 2 and parts[0] not in {"references", "scripts"}:
        parts = parts[1:]
    return "/".join(parts)


def _split_sections(text: str, heading: re.Pattern[str], document: str) -> list[SkillzRule]:
    """Split a Markdown document into rule sections that each run to the next heading."""
    rules: list[SkillzRule] = []
    current: tuple[str, str] | None = None
    body: list[str] = []

    for line in [*text.splitlines(), "# end"]:
        match = heading.match(line)
        if match or _ANY_HEADING.match(line):
            if current is not None:
                rules.append(
                    SkillzRule(
                        rule_id=current[0],
                        title=current[1].strip(),
                        document=document,
                        text="\n".join(body).strip(),
                    )
                )
            current = (match.group(1), match.group(2)) if match else None
            body = []
        elif current is not None:
            body.append(line)
    return rules


def _strip_title(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, list | tuple):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _string_mapping(value: object) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            key: replacement
            for key, replacement in value.items()
            if isinstance(key, str) and isinstance(replacement, str)
        }
    return {}
