from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Problem:
    type: str
    title: str
    status: int
    detail: str
    code: str
    retryable: bool
    request_id: UUID
