from typing import Protocol

from flash_trips.kernel.service_status import ServiceStatus


class ServiceStatusPort(Protocol):
    def read(self) -> ServiceStatus: ...
