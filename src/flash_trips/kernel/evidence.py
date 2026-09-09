from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """An opaque reference to the Evidence supporting a claim."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("Evidence reference must not be empty")
