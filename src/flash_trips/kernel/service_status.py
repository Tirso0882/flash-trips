from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ServiceStatus:
    service: Literal["flash-trips-api"] = "flash-trips-api"
    status: Literal["ok"] = "ok"
    api_version: Literal["v1"] = "v1"
