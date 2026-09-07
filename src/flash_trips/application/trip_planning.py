from flash_trips.kernel.service_status import ServiceStatus

from .ports import ServiceStatusPort


class TripPlanning:
    """Typed application interface for Flash Trips use cases."""

    def __init__(self, service_status: ServiceStatusPort) -> None:
        self._service_status = service_status

    def service_status(self) -> ServiceStatus:
        return self._service_status.read()
