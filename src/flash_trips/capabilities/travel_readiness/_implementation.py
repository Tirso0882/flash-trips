import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from importlib.resources import files
from typing import cast

from flash_trips.kernel.capability import (
    Capability,
    CapabilityComplete,
    CapabilityRefusal,
)

# SKELETON_REPLACEMENT: issue 208 (FT-06) replaces this fixture executor.

_FIXTURE_PACKAGE = "flash_trips.capabilities.travel_readiness.fixtures"
_FIXTURE_NAME = "travel-readiness-lisbon-v1.json"


class TravelReadinessAssessment(StrEnum):
    READY = "ready"


class TravelReadinessRefusalReason(StrEnum):
    MISSING_TRIP_STRUCTURE = "missing_trip_structure"
    UNSUPPORTED_CITY = "unsupported_city"


@dataclass(frozen=True, slots=True)
class TravelReadinessInput:
    cities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TravelReadinessResult:
    fixture_id: str
    assessment: TravelReadinessAssessment
    summary: str
    observed_at: datetime
    evidence_references: tuple[str, ...]


class FixtureTravelReadinessCapability(
    Capability[
        TravelReadinessInput,
        TravelReadinessResult,
        TravelReadinessRefusalReason,
    ]
):
    async def execute(
        self,
        capability_input: TravelReadinessInput,
    ) -> (
        CapabilityComplete[TravelReadinessResult]
        | CapabilityRefusal[TravelReadinessRefusalReason]
    ):
        if not capability_input.cities:
            return CapabilityRefusal(
                reason=TravelReadinessRefusalReason.MISSING_TRIP_STRUCTURE,
                detail="Travel Readiness requires at least one Trip city.",
            )
        if capability_input.cities != ("Lisbon",):
            return CapabilityRefusal(
                reason=TravelReadinessRefusalReason.UNSUPPORTED_CITY,
                detail="The skeleton Evaluation Fixture supports Lisbon only.",
            )

        fixture = _fixture()
        content_value = fixture.get("content")
        if not isinstance(content_value, dict):
            raise ValueError("Evaluation Fixture content must be an object")
        # JSON object keys are strings; each consumed value is checked below.
        content = cast(dict[str, object], content_value)
        fixture_id = _required_string(fixture, "fixture_id")
        assessment = _required_string(content, "assessment")
        summary = _required_string(content, "summary")
        observed_at = _required_string(content, "observed_at")
        evidence_references = _string_tuple(content, "evidence_references")
        return CapabilityComplete(
            value=TravelReadinessResult(
                fixture_id=fixture_id,
                assessment=TravelReadinessAssessment(assessment),
                summary=summary,
                observed_at=datetime.fromisoformat(observed_at.replace("Z", "+00:00")),
                evidence_references=evidence_references,
            )
        )


def _fixture() -> dict[str, object]:
    fixture_path = files(_FIXTURE_PACKAGE).joinpath(_FIXTURE_NAME)
    raw: object = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Travel Readiness Evaluation Fixture must be an object")
    # JSON object keys are strings; each consumed value is checked by its reader.
    parsed = cast(dict[str, object], raw)
    content = parsed["content"]
    canonical_content = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if sha256(canonical_content).hexdigest() != parsed["content_sha256"]:
        raise ValueError("Travel Readiness Evaluation Fixture digest does not match")
    return parsed


def _required_string(fields: dict[str, object], name: str) -> str:
    value = fields.get(name)
    if not isinstance(value, str):
        raise ValueError(f"Evaluation Fixture {name} must be a string")
    return value


def _string_tuple(fields: dict[str, object], name: str) -> tuple[str, ...]:
    value = fields.get(name)
    if not isinstance(value, list):
        raise ValueError(f"Evaluation Fixture {name} must be a string list")
    # JSON arrays have unknown element types; the comprehension validates each one.
    items = cast(list[object], value)
    if not all(isinstance(item, str) for item in items):
        raise ValueError(f"Evaluation Fixture {name} must be a string list")
    return tuple(item for item in items if isinstance(item, str))
