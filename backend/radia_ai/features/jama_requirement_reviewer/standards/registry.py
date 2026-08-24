"""Deterministic standards registry."""

from radia_ai.features.jama_requirement_reviewer.models.standards_models import StandardReference


class StandardsRegistry:
    """Provides versioned standards metadata consumed by review engines."""

    def list_standards(self) -> list[StandardReference]:
        return [
            StandardReference(
                key="company-style-guide",
                name="Company Requirement Style Guide",
                version="1.0.0",
                source="internal",
                categories=["language", "structure", "naming"],
                description="Internal style guide for requirement clarity and consistency.",
            ),
            StandardReference(
                key="incose",
                name="INCOSE Guide for Writing Requirements",
                version="1.0.0",
                source="INCOSE",
                categories=["language", "verifiability", "structure"],
                description="Reference for verifiable, atomic, and testable requirements.",
            ),
            StandardReference(
                key="ears",
                name="EARS (Easy Approach to Requirements Syntax)",
                version="1.0.0",
                source="EARS",
                categories=["language", "structure"],
                description="Structured requirement pattern guidance.",
            ),
            StandardReference(
                key="cert-guidance",
                name="Certification Guidance",
                version="1.0.0",
                source="internal",
                categories=["certification", "traceability", "verification"],
                description="Certification and verification planning guidance.",
            ),
        ]
