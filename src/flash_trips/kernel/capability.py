from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class CapabilityComplete[CompleteT]:
    """One complete, validated Capability result."""

    value: CompleteT


@dataclass(frozen=True, slots=True)
class CapabilityRefusal[RefusalReasonT]:
    """A typed explanation of why a Capability could not produce a result."""

    reason: RefusalReasonT
    detail: str


@runtime_checkable
class Capability[InputT, CompleteT, RefusalReasonT](Protocol):
    """A bounded unit of typed planning work."""

    async def execute(
        self,
        capability_input: InputT,
    ) -> CapabilityComplete[CompleteT] | CapabilityRefusal[RefusalReasonT]: ...
