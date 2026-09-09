import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from flash_trips.capabilities.travel_readiness import (
    FixtureTravelReadinessCapability,
    TravelReadinessAssessment,
    TravelReadinessInput,
    TravelReadinessRefusalReason,
    TravelReadinessResult,
)
from flash_trips.kernel.capability import (
    Capability,
    CapabilityComplete,
    CapabilityRefusal,
)


@pytest.mark.asyncio
async def test_fixture_capability_returns_the_versioned_evaluation_fixture() -> None:
    capability = FixtureTravelReadinessCapability()

    outcome = await capability.execute(TravelReadinessInput(cities=("Lisbon",)))

    assert isinstance(capability, Capability)
    assert outcome == CapabilityComplete(
        value=TravelReadinessResult(
            fixture_id="travel-readiness-lisbon-v1",
            assessment=TravelReadinessAssessment.READY,
            summary="No fixture Travel Readiness concerns were found for Lisbon.",
            observed_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
            evidence_references=(),
        )
    )


@pytest.mark.asyncio
async def test_fixture_capability_returns_a_typed_refusal_without_a_city() -> None:
    capability = FixtureTravelReadinessCapability()

    outcome = await capability.execute(TravelReadinessInput(cities=()))

    assert outcome == CapabilityRefusal(
        reason=TravelReadinessRefusalReason.MISSING_TRIP_STRUCTURE,
        detail="Travel Readiness requires at least one Trip city.",
    )


def test_evaluation_fixture_is_registered_as_permanent_and_versioned() -> None:
    # The assertions below validate the complete closed registry shape.
    registry = cast(
        dict[str, object],
        json.loads(Path("evaluation/fixtures/registry.json").read_text()),
    )
    fixtures = cast(list[dict[str, object]], registry["fixtures"])

    assert registry["schema_version"] == 1
    assert fixtures == [
        {
            "id": "travel-readiness-lisbon-v1",
            "path": (
                "src/flash_trips/capabilities/travel_readiness/fixtures/"
                "travel-readiness-lisbon-v1.json"
            ),
            "schema": "flash_trips.travel_readiness.fixture@1.0",
            "content_sha256": (
                "8fc324ca6d02525b7bd878129f9f8f66eeab4ac4b899688950e98bc6c09d6a9e"
            ),
            "permanent": True,
        }
    ]


def test_skeleton_implementation_names_its_open_replacement_feature() -> None:
    implementation = Path(
        "src/flash_trips/capabilities/travel_readiness/_implementation.py"
    ).read_text()

    assert "SKELETON_REPLACEMENT: issue 208 (FT-06)" in implementation
